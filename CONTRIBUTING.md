# Contributing to Biddy

Read the [README](README.md) for setup and the [implementation contract](docs/SPEC.md) before changing extraction or review behavior.

## Local checks

```bash
npm ci
npm test
npm run build
```

With the Python environment from the README installed:

```bash
cd backend
../.venv/bin/python -m pytest tests -q
../.venv/bin/python -m evals.run --output ../artifacts/eval-results.json
```

Keep fixes narrow. Add regression coverage for changed behavior rather than tests that merely repeat implementation details. Database changes need a new Alembic migration; do not rewrite an already applied migration.

Every extracted finding must retain an exact source quote and page/section reference. Do not bypass the human review gate, silently guess missing procurement facts, or present rules output as an LLM result. Keep the sample and synthetic benchmarks explicitly labeled.

Commit synthetic or intentionally public test material only. Keep provider keys, workspace tokens, `.env`, database files, uploaded solicitation data and local runtime state out of the repository.

For a pull request, state the observed problem, resulting behavior and checks performed. Report untested provider or deployment paths plainly. Do not replace real pilot measurements with synthetic test results.
