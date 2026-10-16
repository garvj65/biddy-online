"""Measure real upload-to-ready latency against a running API and worker.
Usage: python scripts/load_test.py --url http://localhost:8080 --concurrency 5 --requests 20
Token is read from BIDDY_ACCESS_TOKEN, never from CLI arguments.
"""
import argparse
import asyncio
import json
import math
import os
import statistics
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
import httpx


async def main(args):
    token = os.environ.get('BIDDY_ACCESS_TOKEN')
    if not token:
        raise SystemExit('Set BIDDY_ACCESS_TOKEN in the environment.')
    semaphore = asyncio.Semaphore(args.concurrency)
    local = urlsplit(args.url).hostname in {'localhost', '127.0.0.1', '::1'}
    async with httpx.AsyncClient(base_url=args.url, headers={'Authorization': f'Bearer {token}'}, timeout=30, trust_env=not local) as client:
        async def run(i):
            async with semaphore:
                started = time.perf_counter()
                text = f'LOAD TEST — SYNTHETIC {uuid.uuid4()}\nThe contractor shall provide cloud support.\nProposals are due November 30, 2026 at 5 PM ET.\nSubmit two separate volumes via the agency portal.\n'
                response = await client.post('/api/solicitations/text', json={'title': f'Synthetic load test {i}', 'text': text})
                response.raise_for_status()
                sid = response.json()['id']
                while time.perf_counter() - started < args.timeout:
                    result = await client.get(f'/api/solicitations/{sid}')
                    result.raise_for_status()
                    data = result.json()
                    if data['status'] in {'ready', 'reviewed'}:
                        return {'id': sid, 'status': 'ok', 'time_to_brief_ms': round((time.perf_counter()-started)*1000), 'metrics': data['analysis']['metrics']}
                    if data['status'] == 'failed':
                        return {'id': sid, 'status': 'failed', 'error': data['error']}
                    await asyncio.sleep(.25)
                return {'id': sid, 'status': 'timeout'}
        results = await asyncio.gather(*(run(i) for i in range(args.requests)), return_exceptions=True)
    rows = [r if isinstance(r, dict) else {'status': 'request_error', 'error_type': type(r).__name__,
            'http_status': r.response.status_code if isinstance(r, httpx.HTTPStatusError) else None} for r in results]
    times = sorted(r['time_to_brief_ms'] for r in rows if r['status'] == 'ok')
    output = {'concurrency': args.concurrency, 'requests': args.requests, 'completed': len(times),
              'p50_ms': statistics.median(times) if times else None,
              'p95_ms': times[max(0, math.ceil(.95*len(times))-1)] if times else None,
              'note': 'Synthetic local load only. Includes queue wait and polling overhead. Unique text avoids cache hits.', 'runs': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='runs'}, indent=2))
    if len(times) != args.requests:
        raise SystemExit('Some requests failed or timed out; inspect the saved run before reporting latency.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://localhost:8080')
    parser.add_argument('--concurrency', type=int, default=5)
    parser.add_argument('--requests', type=int, default=20)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--output', type=Path, default=Path('artifacts/load-results.json'))
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 50 or not 1 <= args.requests <= 500:
        parser.error('Use concurrency 1–50 and requests 1–500.')
    asyncio.run(main(args))
