"""Start the real API + worker, measure a synthetic run, then shut both down.
Uses a temporary SQLite database by default. CI can set BIDDY_VERIFY_DATABASE_URL
to run the same network + job-queue check against its ephemeral Postgres service.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import httpx

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='biddy-verify-') as temporary:
    env = dict(os.environ)
    env.update(DATABASE_URL=env.get('BIDDY_VERIFY_DATABASE_URL', f'sqlite:///{temporary}/verify.db'),
               BIDDY_ACCESS_TOKEN='isolated-verification-only', BIDDY_WORKSPACE_ID='verification-workspace',
               LLM_PROVIDER='rules', LLM_API_KEY='', LLM_MODEL='')
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=root / 'backend', env=env, check=True)
    children = []
    with open(Path(temporary) / 'service.log', 'w') as log:
        try:
            children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8099'], cwd=root / 'backend', env=env, stdout=log, stderr=log))
            children.append(subprocess.Popen([sys.executable, '-m', 'app.worker'], cwd=root / 'backend', env=env, stdout=log, stderr=log))
            for _ in range(150):
                if any(child.poll() is not None for child in children):
                    log.flush()
                    print((Path(temporary) / 'service.log').read_text())
                    raise RuntimeError('A verification service exited before readiness.')
                try:
                    if httpx.get('http://127.0.0.1:8099/api/health', trust_env=False, timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.2)
            else:
                log.flush()
                print((Path(temporary) / 'service.log').read_text())
                raise RuntimeError('Verification API did not start; inspect configuration.')
            subprocess.run([sys.executable, str(root / 'scripts/load_test.py'), '--url', 'http://127.0.0.1:8099',
                            '--concurrency', '3', '--requests', '6', '--output', str(root / 'docs/validation/local-load.json')], cwd=root, env=env, check=True)
        except Exception:
            log.flush()
            print((Path(temporary) / 'service.log').read_text())
            raise
        finally:
            for child in children:
                child.terminate()
            for child in children:
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
