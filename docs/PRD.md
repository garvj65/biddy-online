# Biddy v0.1 product brief

## User and decision

A small government contractor receives a solicitation and must decide whether it is worth spending scarce proposal time. The first review needs reliable dates, eligibility, registrations, required personnel, delivery constraints, scope, submission instructions and commercial risks. Each extracted requirement should be easy to verify in the source.

This problem framing comes from Garv's RFP/RFQ/RFI work. It is a hypothesis for user research, not a substitute for contractor interviews.

## Primary workflow

1. Add one readable solicitation by upload, text, or public `.gov` document link.
2. Track processing, then receive a draft containing source-linked facts and explicit missing information.
3. Open each finding, inspect the highlighted passage and mark it reviewed.
4. Compare the conditions with the company's actual capabilities, registrations and available staff.
5. Acknowledge outstanding checks, choose Bid / No bid / Hold and enter a reason.
6. Save a version-linked decision and export a brief retaining the original quotes and references.

## Acceptance criteria

- A new document can reach a useful brief through the actual API + worker + database path.
- All displayed extracted facts resolve to an exact passage in retained text.
- Invalid quotes are withheld and counted; missing fields are explicitly unknown.
- Question deadlines, response deadlines and amendment dates are not silently collapsed.
- Approval rejects an incomplete checklist, missing gap acknowledgement, empty rationale or old brief version.
- The same document can be re-imported from cache with fresh IDs and citations bound to the new document.
- Failures are visible, retryable and do not turn into automatic approval.
- Model choice is configurable, and no provider key appears in browser assets or error responses.
- The sample, local rules scan, paid model results and actual benchmark results are clearly distinguishable.

## Scope choices

v0.1 uses a single shared workspace token, a database queue, structured extraction and a composed brief. It deliberately leaves the final bid decision to a reviewer. It supplies company context rather than manufacturing a numerical fit score before that score can be validated.

The frontend is deployed independently because available hosting cannot run Python/Postgres. The requested stack remains implemented in the Docker project. The live standalone workspace has working local scans and review/export; it is not evidence that the Python stack is already hosted.

## Pilot success measures

Measure the time a reviewer needs to identify eligibility blockers, missed deadline rate, critical requirement omissions, correction rate per field, reviewer confidence with and without citations, actual upload-to-brief latency, token usage and estimated cost. Treat rejection of an unsuitable opportunity as a useful outcome.

No target is reported as achieved before measurement. Begin with 5–8 discovery interviews and 5–10 pilot reviewers. Use 30–50 independently labeled real documents, a held-out evaluation subset, and reviewer agreement on critical fields. Compare human review time with the existing spreadsheet/manual workflow.

## Follow-on milestones

1. Deploy the API, worker and Postgres to a Docker host; verify a real paid-provider run.
2. Observe contractor reviews on real documents and repair the most costly mistakes.
3. Add original-file retention and page-aware PDF rendering if reviewers need layout fidelity.
4. Add multi-document/amendment grouping and explicit source precedence.
5. Integrate authenticated SAM.gov discovery and per-user workspaces only after validating the intake workflow.
