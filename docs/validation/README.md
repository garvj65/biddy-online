# Recorded verification — 2026-10-15

- Production TypeScript/Vite build passed; the latest initial frontend bundle is about 244 kB uncompressed / 75 kB gzip before stylesheet transfer.
- Frontend domain tests: 5 passed. Backend API/processing tests: 18 passed, including readable PDF/DOCX parsing, blank cover pages and concurrent first imports.
- Alembic upgrade applied successfully on SQLite. Postgres schema generation succeeded; `postgres-schema.sql` is generated SQL, not evidence of executing Postgres.
- `rules-baseline.json`: six synthetic fixtures, with a deadline-negation false positive and a duplicate question/submission classification. The missing-deadline gap check failed.
- `rules-current.json`: same six extraction examples after corrections, plus a timezone-gap assertion. All 21 labeled category/quote pairs matched and all gap/human-gate checks passed. These tiny, synthetic examples are development smoke tests. They do not measure accuracy on unseen government solicitations.
- `local-load-before-fix.json`: concurrent first imports exposed a workspace initialization race; incomplete runs are retained rather than summarized as successful latency measurements.
- `local-load.json`: six unique synthetic documents, concurrency 3, all completed through real local HTTP API calls and the separate background worker. p50 1,066 ms; p95 1,099 ms. Rules provider, temporary SQLite database, one worker, short input, no model calls. Polling and queue wait are included. The test is too small to estimate deployment capacity or LLM performance.

No paid provider inference, external hosting of the Python/Postgres stack, Docker execution, live Postgres run, browser visual QA, real contractor pilot, or GitHub Actions run was completed here. The corresponding code/configuration and commands are included so each can be verified in its target environment.
