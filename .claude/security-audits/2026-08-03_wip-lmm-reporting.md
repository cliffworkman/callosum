# Security audit — WIP mixed-model reporting audit

**Increment:** 442
**Date:** 2026-08-03
**Status:** COMPLETE — PASS

## Scope and trust boundary

This increment adds `POST /wip/manuscripts/{manuscript_id}/checks/lmm` and two local UI surfaces for its stored
result. It reuses the local-only WIP router, registered-primary-file resolver, bounded content extractor, generic
snapshot/tool-run/finding tables, and existing deterministic `audit_lmm` function. It adds no migration, dependency,
provider, upload, public endpoint, background job, client-selected file, or secret.

Unpublished manuscript text remains inside the local read-write Callosum instance. The router-level
`require_local_wip` dependency rejects forwarded/non-loopback access; read-only mode continues to reject the POST.

## Input and resource controls

- FastAPI parses the manuscript id as an integer; the record must exist and must have an available registered primary
  file. The request body provides no detector options, regex, path, URL, destination, formatting, or nested object.
- `prepare_snapshot` resolves the stored relative path through `trusted_child` and applies the existing WIP file/type
  and extraction limits (256 MiB primary-file ceiling; tighter 32 MiB plain-text ceiling).
- The server owns the mixed-model gate and seven fixed regex checks. No user text is compiled as a pattern. Evidence
  extraction is bounded by the existing detector and produces at most one result per fixed checklist row.
- One explicit action performs one synchronous extraction/audit/persist cycle. The UI disables duplicate checklist
  actions during a request and has no silent or unbounded retry.

Residual resource risk is local parsing cost for a deliberately selected maximum-size complex PDF, unchanged from
existing WIP checkpoints, Statcheck, and Transparency.

## Data, egress, and secrets

- No HTTP, provider, LLM, telemetry, environment-secret, clipboard, or device-identity path is imported or called.
- Persistence contains existing snapshot identity plus the seven bounded detector rows and review state. It does not
  copy the manuscript, add arbitrary logs, or create a second durable content store.
- Activity records contain fixed tool/version/snapshot/count information. Extraction failures use a fixed activity
  message, not parser exceptions, manuscript text, or paths.
- Errors expose bounded local validation messages only. There is no remote response, credential, header, or webhook
  body to leak.

## Injection, evidence, and epistemic integrity

- SQLAlchemy Core uses bound values; the client cannot choose a tool id, finding type, table, destination, or claimed
  detector result.
- React interpolates labels, evidence, and context as text. No raw HTML, Markdown execution, arbitrary URL, or
  client-supplied Slack/provider formatting exists.
- The persisted receipt contains every detector status. Only `not-found` rows become `kind="candidate"`,
  `severity="info"` review prompts; they have no quote or fabricated coordinate. Present and not-applicable rows are
  not findings. A gate-off report creates no findings.
- Coverage and UI text state that a miss is not proof of omission, a gate-off report is not proof that no mixed model
  exists, and the audit is never a model run, correctness verdict, score, rank, or accusation.
- Real PDF evidence may retain page/region precision. Synthetic page 1 from non-paginated extractors is cleared.
  Every run remains bound to the exact file/hash snapshot and visibly stales when the source changes.

## Verification

Backend coverage proves valid/gate-off/PDF/non-PDF cases, one candidate per detector miss, review-state transitions,
snapshot staleness, missing-manuscript 404, missing-primary 422, and non-loopback denial. Frontend contracts pin both
entry points, the generic endpoint wiring, preview/caveat language, and shared checklist shell. The bounded Chromium
route uses the real API and assembled app, checks both visible surfaces and mobile layout, and observes zero outbound
requests and zero console/page errors.

Final formatting, full-suite, strict QA, dependency, Bandit, secret-pattern, and diff checks are recorded with exact
results in `INCREMENT-442-NOTES.md`.

## Result

**Security Audit: PASS.** No unresolved high or medium issue was found. Residual risk is the documented local parser
cost and ordinary fixed-pattern false positives/negatives; neither adds egress, public abuse, a secret boundary, a
score, or an accusation.
