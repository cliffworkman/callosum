# Security audit — WIP Transparency disclosure checks

**Increment:** 441
**Date:** 2026-08-02
**Status:** COMPLETE — PASS

## Scope and trust boundary

This increment adds `POST /wip/manuscripts/{manuscript_id}/checks/transparency` and two local UI entry points over
the same result. It reuses the existing WIP primary-file resolver, content-identity extractor, snapshot/tool-run/
finding tables, and the existing deterministic `detect_transparency` function. It adds no migration, dependency,
provider integration, upload, arbitrary path input, or new secret.

The source is unpublished manuscript text, so the endpoint inherits `wip_checks.router`'s
`require_local_wip` dependency. Authenticated remote and read-only companion requests remain denied; the operation is
available only on the local read-write Callosum instance.

## Input validation and resource bounds

- `manuscript_id` is FastAPI-parsed as an integer and must resolve to an existing WIP record (404 otherwise).
- The request has no user-controlled options, regex, nested payload, destination, or file path.
- `prepare_snapshot` chooses only the registered primary `wip_files` row, resolves it through `trusted_child`,
  rejects missing/unavailable/unsupported files, and uses the existing 256 MiB WIP primary-file limit. Plain-text
  extraction has the tighter existing 32 MiB cap.
- The detector runs seven fixed server-owned regex families over locally extracted blocks. Patterns contain no
  user-controlled compilation and return only the first bounded 200-character evidence snippet per category.
- The route performs one synchronous extraction/check/persist cycle. The UI disables both check controls while one
  request is active and performs no automatic or unbounded retry.

Residual local resource risk is the same as existing WIP Statcheck/checkpoint extraction: a maximum-size complex PDF
can consume local CPU/memory during parsing. It is bounded by the registered-file and size checks, local-only trust
boundary, and one explicit user action; no new public abuse surface is introduced.

## Data handling, egress, and secrets

- No HTTP/provider/LLM client is imported or called. The primary manuscript, extracted blocks, quotes, and findings
  remain local.
- Persistence stores existing bounded snapshot identity/provenance plus seven small detector rows and positive
  evidence snippets. It does not copy the manuscript file or create a new durable content store.
- No environment variable, API key, token, credential, clipboard value, arbitrary log, or device identifier is read.
- Errors use existing bounded local WIP messages; no provider body, header, secret, or arbitrary stack trace is
  returned.
- Activity rows name only the tool, summary counts, version, and snapshot id; they do not log manuscript text,
  evidence quotes, absolute paths, or raw request bodies.

## Injection, output encoding, and database safety

- All writes use SQLAlchemy Core bound values. Client input cannot select a table, column, tool id, detector, or
  finding type.
- Detector evidence is rendered through ordinary React text interpolation and `EvidenceQuote`; there is no raw HTML,
  Markdown execution, URL opening, or client-supplied formatting structure.
- The client cannot submit a claimed detector result. The endpoint computes the report server-side and persists only
  that result against the exact extracted-text hash.
- Positive detections are stored as `kind="fact"`, `severity="info"`, with no review disposition. The repository now
  rejects attempts to assign candidate-review state to a fact, preventing a caller from manufacturing unresolved WIP
  work from a disclosure fact.
- Not-detected and not-applicable statuses remain only in `structured_result_json`; they never create negative facts,
  candidate findings, accusations, or a score.

## Coordinate and source integrity

- The detector's evidence quote remains bounded and tied to the run's exact snapshot/file/hash.
- Only PDF primary files retain a page number and `region` precision. Generic document extractors synthesize page 1
  for non-paginated DOCX/ODT/HTML/Markdown/text/TeX, so the WIP persistence boundary deliberately clears those page
  values and stores no coordinate precision rather than presenting a fictional page target.
- The UI's source action calls the existing manuscript/file-scoped open endpoint. No arbitrary local path or URL is
  accepted from the result.

## Supply chain and deployment

No dependency, migration, environment setting, build service, network permission, or deployment topology changes.
The generated frontend contains no manuscript content or configuration value.

## Negative-path verification

- Backend tests prove nonexistent-manuscript 404, missing-primary bounded 422, remote-host denial, FACT disposition
  mutation denial, no negative findings for a no-detection report, snapshot invalidation after a source change, and
  PDF-region versus non-PDF-null coordinate behavior.
- The committed Chromium test drives both UI surfaces, asserts that FACTs have no candidate disposition control,
  runs at 1440 px and 375 px without overflow, captures browser requests after app mount, and observes **zero outbound
  requests** while the local WIP disclosure check runs.
- The route accepts no body schema, path, URL, formatting, or nested object. Oversized primary manuscripts and
  unsupported/extraction-failure inputs remain bounded by the existing tested WIP content-identity boundary.
- Baseline-ratcheted Bandit over all runtime Python packages exits 0. Runtime `pip-audit --strict` finds no known
  vulnerability. The development audit reports only the already accepted pytest 8.4.2 advisory.
- Targeted added-line patterns found no Slack webhook, provider token, private-key marker, or feedback secret and no
  network/client import in any changed production source. `gitleaks` was unavailable in this environment; this is not
  claimed as run. `git diff --check` passed.
- The full 1,834-test root collection and all 11 opt-in Chromium tests pass; focused detector/WIP/frontend coverage is
  91/91 passing. Strict QA mapping covers 355/355 API and 1579/1579 frontend surfaces.

## Result

**Security Audit: PASS**

No high or medium unresolved issue was found. Residual risk is limited to local parsing cost for a deliberately
selected maximum-size complex PDF and the detector's documented false-positive/false-negative limits. Neither creates
egress, an accusation, a score, a public abuse surface, or a new secret-bearing boundary.
