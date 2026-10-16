# v0.1 implementation contract

## Data model

| Table | Purpose |
|---|---|
| users | Stable configured workspace owner ID and a company profile |
| solicitations | Retained text/pages, source URL, hash, status and current analysis |
| processing_jobs | Durable queue, attempt count, availability, lease token, heartbeat timestamp and sanitized failure |
| requirements | One source-linked extracted finding per row |
| briefs | Immutable snapshots and content versions |
| review_decisions | Append-only reviewer decisions, rationale, reviewed fact IDs and brief version |
| eval_results | Measured eval output with provider and run timestamp |

Migrations include owner/date/hash indexes, requirement indexes and a Postgres GIN index over `to_tsvector('english', content)`. A workspace ID remains stable when its access token is rotated. Individual reviewer identity and SaaS multi-tenancy are future work.

## Citation shape

```json
{
  "document_id": "solicitation UUID",
  "page": 2,
  "start": 124,
  "end": 181,
  "quote": "Literal passage copied from the retained page or section."
}
```

`page` refers to an original PDF page or an explicitly labeled text/DOCX section. `start:end` must slice to `quote` in that retained source. Model-suggested offsets are never trusted: the server calculates them. The frontend locates the exact quote again to account for JavaScript/Python Unicode index differences. An exact quote is a necessary evidence check, not an entailment guarantee.

## API surface

All routes except health and generated docs/schema require `Authorization: Bearer <workspace token>`.

| Method | Path | Behavior |
|---|---|---|
| GET | /api/health | Process health/version |
| GET | /api/config | Provider/model readiness; never secrets |
| POST | /api/solicitations/text | Queue text import, return 202 and IDs |
| POST | /api/solicitations/upload | Parse bounded multipart PDF/DOCX/TXT/MD upload |
| POST | /api/solicitations/url | Retrieve a public HTTPS `.gov` document |
| GET | /api/solicitations?q= | Owner-filtered, bounded full-text search |
| GET | /api/solicitations/{id} | Source sections, current brief and review history |
| GET | /api/solicitations/{id}/events | SSE `status`, verified `fact`, `ready` or `reconnect` events |
| POST | /api/solicitations/{id}/retry | Requeue a failed document |
| POST | /api/solicitations/{id}/review | Validate reviewed IDs, gaps, rationale and version; append decision |
| GET | /api/solicitations/{id}/export | Markdown with source passages and draft/review status |
| GET / PUT | /api/profile | Read/save company context |

Errors: 401 invalid/missing workspace token; 404 missing/not-owned document; 409 incomplete or changed brief / wrong retry state; 422 invalid input or unmet review requirements. Provider failures are persisted without upstream bodies or keys.

## Processing lifecycle

`queued → processing → ready → reviewed`; failed attempts return to `queued` with exponential delay until the configured maximum, then become `failed`. Explicit retry creates a new job. Postgres claims use row locking with `SKIP LOCKED`. A random lease token identifies each claim, heartbeats renew it during processing, stale leases can be recovered, and only the current lease holder may publish output. SQLite is for one local worker only.

Chunks contain up to 14,000 characters, retaining original page numbers and overlap for long pages. Provider requests are bounded by `LLM_CONCURRENCY`. Results are validated against Pydantic and checked against the complete retained source. The brief is capped at 100 findings and flags truncation. Cache reuse requires the same owner, source hash and provider/model/endpoint/prompt/schema fingerprint, and produces new document-bound fact IDs.

The API streams validated findings after extraction, rather than forwarding partially generated model claims. Human approval remains unavailable during processing. SSE connections are bounded and can reconnect; the current frontend asks the user to reconnect if a job outlasts the stream window.

## Deployment split

Sites hosts only `dist/`. Docker Compose runs Nginx, FastAPI, a Python worker, Postgres and a migration task. The same React application speaks to the configured API. It starts in a clearly labeled local mode; connecting switches to the API's documents rather than uploading local demo records implicitly. LLM calls occur only in the Python service. Local data and company profile stay in this browser unless the reviewer explicitly imports them into a connected API.
