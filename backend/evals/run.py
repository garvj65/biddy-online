"""Small synthetic smoke eval, not evidence of real-solicitation accuracy."""
import argparse
import asyncio
import json
import statistics
from pathlib import Path
from app.config import settings
from app.db import EvalResult, Session
from app.extraction import analyze


async def evaluate(path: Path):
    rows, totals = [], {'tp': 0, 'fp': 0, 'fn': 0, 'invalid_citations': 0}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        fixture = json.loads(line)
        pages = [{'number': 1, 'text': fixture['text'], 'kind': 'section'}]
        result = await analyze(pages, fixture['id'])
        gold = {(x['category'], x['quote']) for x in fixture['expected']}
        predicted = {(x['category'], x['citation']['quote']) for x in result['facts']}
        tp, fp, fn = len(gold & predicted), len(predicted - gold), len(gold - predicted)
        invalid = sum(pages[0]['text'][f['citation']['start']:f['citation']['end']] != f['citation']['quote'] for f in result['facts'])
        for key, value in [('tp', tp), ('fp', fp), ('fn', fn), ('invalid_citations', invalid)]:
            totals[key] += value
        rows.append({'id': fixture['id'], 'tp': tp, 'fp': fp, 'fn': fn,
                     'missing_checks_pass': all(any(g in m for m in result['missing_information']) for g in fixture.get('must_flag_missing', [])),
                     'human_gate_preserved': result['recommendation'] == 'review_required',
                     'processing_ms': result['metrics']['processing_ms'], 'cost_usd': result['metrics']['cost_usd']})
    if not rows:
        raise ValueError('The evaluation dataset must contain at least one fixture.')
    precision = totals['tp'] / max(1, totals['tp'] + totals['fp'])
    recall = totals['tp'] / max(1, totals['tp'] + totals['fn'])
    return {'dataset': 'synthetic-smoke-v1', 'real_solicitations': 0, 'fixtures': len(rows),
            'provider': settings().llm_provider, 'model': settings().llm_model,
            'precision': round(precision, 4), 'recall': round(recall, 4),
            'f1': round(2 * precision * recall / max(0.0001, precision + recall), 4),
            **totals, 'median_processing_ms': statistics.median(r['processing_ms'] for r in rows), 'cases': rows}


def quality_failures(result, min_f1):
    failures = []
    if result['f1'] < min_f1:
        failures.append(f'F1 is below the required threshold of {min_f1}.')
    if result['invalid_citations']:
        failures.append('At least one citation failed the exact source match.')
    if not result['cases']:
        failures.append('The evaluation contains no cases.')
    for case in result['cases']:
        if not case['missing_checks_pass']:
            failures.append(f'{case["id"]}: required missing-information check failed.')
        if not case['human_gate_preserved']:
            failures.append(f'{case["id"]}: human review gate was not preserved.')
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures', type=Path, default=Path(__file__).with_name('fixtures.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('../artifacts/eval-results.json'))
    parser.add_argument('--persist', action='store_true', help='Store the run in the migrated eval_results table')
    parser.add_argument('--min-f1', type=float, default=0.9, help='Minimum exact category/quote F1; safety and gap checks must always pass')
    args = parser.parse_args()
    if not 0 <= args.min_f1 <= 1:
        parser.error('--min-f1 must be between 0 and 1.')
    result = asyncio.run(evaluate(args.fixtures))
    failures = quality_failures(result, args.min_f1)
    result['quality_gate'] = {'passed': not failures, 'min_f1': args.min_f1, 'failures': failures}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    if args.persist:
        with Session.begin() as db:
            db.add(EvalResult(provider=settings().llm_provider, result=result))
    print(json.dumps(result, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
