# Focused code review — 2026-10-16

Scope: a minor correctness and repository-readiness review of Biddy v0.1, starting from the Site source commit `d864905b7a943af839574e93e90dc7d89a02d84b`. This is not an exhaustive security audit or an independent production-readiness assessment.

## Findings addressed

| Priority | Finding | Resulting change | Regression coverage |
|---|---|---|---|
| Medium | Concurrent `POST /retry` requests could all read `failed` and each enqueue another job. Multiple workers could then publish competing analyses for one solicitation. | Claim the `failed → queued` transition with a conditional database update in the same transaction as creating the new job. Exactly one request succeeds; competing retries return 409. | Four requests are forced to read the same failed snapshot; exactly one new queued job is created. |
| Medium | `LLM_CONCURRENCY=0` could wait indefinitely; zero attempts left jobs permanently queued; nonpositive lease settings could immediately expire work. | Validate positive concurrency and attempt counts, and a lease of at least three seconds, when loading settings. Invalid configuration fails at startup. | Zero and negative values are rejected for all three settings. |
| Medium | The eval command printed failed required-gap or human-review checks but returned success, allowing CI to stay green after important regressions. | Add a quality gate: citation, required-gap and human-review checks must pass, with a configurable minimum F1 (default 0.9). Failure reports are still saved, then the command exits nonzero. | CLI regression cases cover gap, human gate, citation, low F1 and empty-case failures, plus a passing run. |

Repository preparation adds a contribution guide, explicit line endings, minimal read permissions and time bounds for CI. Provider/workspace keys, `.env`, uploads, database/runtime files, dependency directories and build output are excluded from publication. The Sites project binding is intentionally excluded because it belongs to the existing hosted Site rather than the portable GitHub/Docker project.

## Reviewed contracts

- A displayed extracted fact needs an exact page/section quote; a quote match does not prove semantic entailment.
- The API enforces the review checklist, rationale, acknowledged gaps and current brief version.
- Provider keys remain server-side. Example and test tokens are deliberately nonproduction values.
- Cache reuse stays workspace-scoped and rebinds citation/fact IDs to the new document.
- Worker claims, lease renewal, stale-output protection and retry limits remain present.
- Public demo mode is labeled, and synthetic results are not presented as real contractor accuracy.

## Remaining limitations

Paid-provider requests, browser visual QA and local Docker/Postgres execution still require verification. The CI configuration includes an ephemeral Postgres integration path; its actual GitHub run must be checked after upload. Six synthetic eval fixtures do not establish accuracy on unseen solicitations. The API remains a single-workspace MVP, with a documented development token that must be replaced before Internet exposure.

DOCX preserves extracted paragraph/table content rather than original page geometry; cross-document amendment precedence and multi-file consolidation are future work. The original-file binary is not retained. These are existing v0.1 product boundaries, not functionality added by this review.

The reviewed GitHub package is prepared separately from the already published Site. The review fixes do not imply that the existing Site's backend was deployed or updated.
