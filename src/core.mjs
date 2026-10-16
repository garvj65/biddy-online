/** Exact source references are the only way to create a local finding. */
export function sourceReference(documentId, pages, pageNumber, quote) {
  const page = pages.find(p => p.number === pageNumber);
  const start = page?.text.indexOf(quote) ?? -1;
  if (!quote || start < 0) throw new Error('The cited passage does not exist in the source.');
  return {document_id: documentId, page: pageNumber, start, end: start + quote.length, quote};
}

export function canReview(facts, checkedIds, acknowledged, notes) {
  return facts.length > 0 && facts.every(f => checkedIds.includes(f.id)) && acknowledged && notes.trim().length >= 10;
}

export function briefMarkdown(document) {
  const a = document.analysis;
  if (!a) throw new Error('This brief is not ready yet.');
  const review = document.reviews.find(r => r.brief_version === a.version);
  const lines = [`# ${document.title}`, '', `Status: ${review ? review.decision.toUpperCase().replace('_', ' ') : 'DRAFT — NOT REVIEWED'}`,
    `Analysis: ${a.provider} / ${a.model}`, '', '## Source-linked findings', ''];
  for (const f of a.facts) {
    const p = document.pages.find(p => p.number === f.citation.page);
    lines.push(`### ${f.label}`, f.value, '', `> ${f.citation.quote}`, `Source: ${document.filename}, ${p?.kind || 'page'} ${f.citation.page}, characters ${f.citation.start}–${f.citation.end}.`, '');
  }
  lines.push('## Missing information / checks', ...a.missing_information.map(x=>`- ${x}`));
  if (review) lines.push('', '## Human decision', review.notes, `Recorded: ${review.created_at}`);
  return lines.join('\n');
}

export function localScan(documentId, pages) {
  const rules = [
    ['deadline', 'Response deadline', /(?:response|proposal|quotation|quote|offer|submission|bid)s?\s+(?:are\s+)?(?:due|deadline|must be received)|closing date/i],
    ['deadline', 'Questions deadline', /questions?\s+(?:are\s+)?(?:due|deadline|must be (?:submitted|received))/i],
    ['eligibility', 'Business eligibility', /set.aside|small business|NAICS|HUBZone|8\(a\)|size standard/i],
    ['certification', 'Registration / certification', /\bSAM\b|CMMC|FedRAMP|ISO\s*\d|certification|security clearance/i],
    ['submission', 'Submission instruction', /submit|submission|page limit|volume|electronic proposal/i],
    ['scope', 'Scope of work', /shall provide|must provide|scope of work|contractor (?:shall|will)|period of performance/i],
    ['commercial', 'Contract terms', /fixed.price|payment|option year|contract ceiling|not.to.exceed/i],
    ['risk', 'Delivery constraint', /on.site|onsite|mandatory site|liquidated damages|bonding|amendment|supersedes/i]
  ];
  const facts = [];
  const started = performance.now();
  for (const page of pages) {
    const paragraphs = page.text.split(/\n+/).map(x=>x.trim()).filter(x=>x.length>=8 && x.length<=2000);
    for (const quote of paragraphs) for (const [category,label,pattern] of rules) {
      if (category==='deadline' && /\b(?:no|not)\b.*(?:specified|published|provided|available)|not (?:yet )?set|to be (?:determined|announced)/i.test(quote)) continue;
      if (category==='submission' && rules.some(([c,,p])=>c==='deadline'&&p.test(quote))) continue;
      if (pattern.test(quote) && facts.length < 100) facts.push({id:crypto.randomUUID(),category,label,value:quote.slice(0,800),severity:category==='risk'?'watch':'normal',citation:sourceReference(documentId,pages,page.number,quote)});
    }
  }
  const missing = ['Local rules scan only. Check the full solicitation and all amendments; this scan may miss requirements.', 'Company eligibility, staffing availability and commercial fit need human confirmation.'];
  const responses=facts.filter(f=>f.category==='deadline'&&!/question/i.test(f.label+' '+f.citation.quote));
  if(!responses.length)missing.push('Response deadline was not verified in the supplied document.');
  if(new Set(responses.map(f=>f.citation.quote)).size>1)missing.push('Multiple response deadlines are present. Confirm the controlling date in the latest amendment.');
  for(const f of facts.filter(f=>f.category==='deadline'))if(!/\b(?:UTC|GMT|ET|CT|MT|PT|EST|EDT|CST|CDT|MST|MDT|PST|PDT|IST|Eastern|Central|Mountain|Pacific)\b|[+-]\d{2}:\d{2}/i.test(f.citation.quote))missing.push(`Confirm the time and timezone for "${f.label}"; no explicit timezone was verified.`);
  for (const [category,label] of [['eligibility','Eligibility / set-aside'],['submission','Submission instructions']]) {
    if (!facts.some(f=>f.category===category)) missing.push(`${label} was not verified in the supplied document.`);
  }
  return {version:crypto.randomUUID(),title:'Local screening',facts,missing_information:missing,recommendation:'review_required',provider:'local-rules',model:'deterministic',metrics:{processing_ms:Math.round(performance.now()-started),chunks:pages.length,verified_facts:facts.length,rejected_facts:0,cache_hit:false,cost_usd:0,usage:[]}};
}
