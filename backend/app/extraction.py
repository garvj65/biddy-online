import asyncio
import hashlib
import json
import re
import time
from .config import settings
from .schemas import RawAnalysis, RawFact
from .db import uid
from . import providers


def cache_fingerprint():
    s = settings()
    text = json.dumps({'provider': s.llm_provider, 'model': s.llm_model, 'endpoint': s.llm_base_url,
                       'schema': RawAnalysis.model_json_schema(), 'prompt': providers.PROMPT}, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def token_metrics(usages):
    s = settings()
    input_tokens = sum(u.get('prompt_tokens', u.get('input_tokens', u.get('promptTokenCount', 0))) for u in usages)
    output_tokens = sum(u.get('completion_tokens', u.get('output_tokens', u.get('candidatesTokenCount', 0))) for u in usages)
    cost = 0 if s.llm_provider == 'rules' else None
    if input_tokens and s.llm_input_usd_per_million is not None and s.llm_output_usd_per_million is not None:
        cost = round((input_tokens * s.llm_input_usd_per_million + output_tokens * s.llm_output_usd_per_million) / 1_000_000, 6)
    return {'input_tokens': input_tokens, 'output_tokens': output_tokens, 'cost_usd': cost,
            'cost_basis': 'configured-rate estimate' if cost is not None and s.llm_provider != 'rules' else 'no model calls' if s.llm_provider == 'rules' else 'pricing not configured'}

RULES = [
    ('deadline', 'Response deadline', r'(?:response|proposal|quotation|quote|offer|submission|bid)s?\s+(?:are\s+)?(?:due|deadline|must be received)|closing date'),
    ('deadline', 'Questions deadline', r'questions?\s+(?:are\s+)?(?:due|deadline|must be (?:submitted|received))'),
    ('eligibility', 'Set-aside / eligibility', r'set.aside|8\(a\)|HUBZone|woman.owned|veteran.owned|small business|NAICS|size standard'),
    ('certification', 'Required registration / certification', r'\bSAM\b|ISO\s*\d|CMMC|FedRAMP|certification|security clearance'),
    ('submission', 'Submission instruction', r'submit|submission|page limit|volume|electronic proposal|email.*proposal'),
    ('scope', 'Scope of work', r'shall provide|must provide|scope of work|contractor (?:shall|will)|performance period|period of performance'),
    ('commercial', 'Contract terms', r'fixed.price|time.and.materials|payment|option year|contract ceiling|not.to.exceed'),
    ('risk', 'Delivery constraint', r'on.site|onsite|mandatory site|liquidated damages|incumbent|bonding|amendment|supersedes|cancelled|canceled'),
]


def ambiguous_date_notes(facts):
    notes = []
    deadlines = [f for f in facts if f['category'] == 'deadline']
    responses = [f for f in deadlines if not re.search(r'question', f['label'] + ' ' + f['citation']['quote'], re.I)]
    if not responses:
        notes.append('Response deadline was not verified in the supplied document.')
    if len({f['citation']['quote'] for f in responses}) > 1:
        notes.append('Multiple response deadlines are present. Confirm the controlling date in the latest amendment.')
    timezone_pattern = r'\b(?:UTC|GMT|ET|CT|MT|PT|EST|EDT|CST|CDT|MST|MDT|PST|PDT|IST|Eastern|Central|Mountain|Pacific)\b|[+-]\d{2}:\d{2}'
    for f in deadlines:
        if not re.search(timezone_pattern, f['citation']['quote'], re.I):
            notes.append(f'Confirm the time and timezone for "{f["label"]}"; no explicit timezone was verified.')
    return notes


def rules_extract(pages: list[dict]) -> RawAnalysis:
    facts = []
    seen = set()
    for page in pages:
        for match in re.finditer(r'[^\n]+', page['text']):
            quote = match.group().strip()
            if not 8 <= len(quote) <= 2000:
                continue
            for category, label, pattern in RULES:
                if re.search(pattern, quote, re.I) and (category, quote) not in seen:
                    if category == 'deadline' and re.search(r'\b(?:no|not)\b.*(?:specified|published|provided|available)|not (?:yet )?set|to be (?:determined|announced)', quote, re.I):
                        continue
                    if category == 'submission' and any(re.search(p, quote, re.I) for c, _, p in RULES if c == 'deadline'):
                        continue
                    # Preserve the source as the claim in rules mode; don't invent a paraphrase.
                    facts.append(RawFact(category=category, label=label, value=quote[:800], quote=quote,
                                         page=page['number'], severity='watch' if category == 'risk' else 'normal'))
                    seen.add((category, quote))
    title = next((line[:250] for page in pages for line in page['text'].splitlines() if line.strip()), 'Untitled solicitation')
    return RawAnalysis(title=title, agency=None, solicitation_number=None,
                       facts=facts[:100], missing_information=['Rules mode is a conservative text scan; confirm requirements in the complete solicitation and amendments.'])


def verify_facts(raw: RawAnalysis, pages: list[dict], doc_id: str) -> tuple[list[dict], int]:
    by_number = {p['number']: p['text'] for p in pages}
    facts, rejected, seen = [], 0, set()
    for f in raw.facts:
        text = by_number.get(f.page, '')
        start = text.find(f.quote)
        if start < 0:
            rejected += 1
            continue
        signature = (f.category, f.page, start, f.quote)
        if signature in seen:
            continue
        seen.add(signature)
        facts.append({'id': uid(), 'category': f.category, 'label': f.label, 'value': f.value,
                      'severity': f.severity, 'citation': {'document_id': doc_id, 'page': f.page,
                      'start': start, 'end': start + len(f.quote), 'quote': f.quote}})
    return facts, rejected


def chunks(pages: list[dict], budget=14000):
    """Group pages, splitting long ones with overlap and preserving original page numbers."""
    group, size = [], 0
    for page in pages:
        text = page['text']
        for i in range(0, max(1, len(text)), budget - 600):
            part = {**page, 'text': text[i:i + budget]}
            if group and size + len(part['text']) > budget:
                yield group
                group, size = [], 0
            group.append(part)
            size += len(part['text'])
    if group:
        yield group


async def analyze(pages: list[dict], doc_id: str) -> dict:
    started = time.perf_counter()
    s = settings()
    semaphore = asyncio.Semaphore(s.llm_concurrency)

    async def part(chunk):
        async with semaphore:
            if s.llm_provider == 'rules':
                return rules_extract(chunk), {}
            return await providers.extract(chunk)

    parts = await asyncio.gather(*(part(c) for c in chunks(pages)))
    all_facts = [f for r, _ in parts for f in r.facts]
    raw = RawAnalysis(title=parts[0][0].title, agency=parts[0][0].agency,
                      solicitation_number=parts[0][0].solicitation_number,
                      facts=all_facts[:100],
                      missing_information=list(dict.fromkeys(g for r, _ in parts for g in r.missing_information))[:20])
    facts, rejected = verify_facts(raw, pages, doc_id)
    missing = raw.missing_information.copy()
    if len(all_facts) > 100:
        missing.append('This brief is limited to the first 100 extracted findings. Review the full source for additional requirements.')
    missing.extend(ambiguous_date_notes(facts))
    for category, label in [('eligibility', 'Eligibility / set-aside'), ('submission', 'Submission instructions')]:
        if not any(f['category'] == category for f in facts):
            missing.append(f'{label} was not verified in the supplied document.')
    if rejected:
        missing.append(f'{rejected} extracted facts were withheld because their quotes did not match the source.')
    if not facts:
        missing.append('No source-verified requirements were found. Do not make a decision from this brief alone.')
    result = {'title': raw.title, 'facts': facts,
              # Uncited metadata is kept out of the decision brief.
              'missing_information': missing, 'recommendation': 'review_required',
              'provider': s.llm_provider, 'model': s.llm_model or ('deterministic' if s.llm_provider == 'rules' else 'provider-default'),
              'cache_fingerprint': cache_fingerprint(),
              'metrics': {'processing_ms': round((time.perf_counter() - started) * 1000), 'chunks': len(parts),
                          'verified_facts': len(facts), 'rejected_facts': rejected,
                          'usage': [u for _, u in parts], **token_metrics([u for _, u in parts]), 'cache_hit': False}}
    result['version'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result
