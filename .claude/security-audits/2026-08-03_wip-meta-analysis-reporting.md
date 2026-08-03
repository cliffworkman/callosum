# Security audit — WIP meta-analysis reporting audit

**Increment:** 444
**Date:** 2026-08-03
**Status:** COMPLETE — PASS

## Scope and trust boundary

This increment adds `POST /wip/manuscripts/{manuscript_id}/checks/meta-analysis` and two local UI surfaces for its
stored result. It reuses the local-only WIP router, registered-primary resolver, bounded content extractor, generic
exact-snapshot/tool-run/finding tables, and existing deterministic meta-analysis reporting detector. It adds no
migration, dependency, provider, upload, public endpoint, background job, client-selected path, or secret.

Unpublished manuscript text remains inside the local read-write Callosum instance. The router-level
`require_local_wip` dependency rejects forwarded/non-loopback access; read-only mode rejects the POST.

## Input and resource controls

- FastAPI parses the manuscript id as an integer. The manuscript and registered primary file must exist. The empty
  request body supplies no detector option, pattern, path, URL, destination, or nested object.
- `prepare_snapshot` resolves the stored relative path through `trusted_child` and enforces existing WIP file/type
  and extraction limits (256 MiB primary-file ceiling; 32 MiB for plain text).
- The server owns the fixed meta-analysis gate and seven fixed regular-expression checks. User text is never compiled
  as code or a pattern. A run has at most seven checklist rows and seven candidate writes.
- One click performs one synchronous extraction/audit/persist cycle. The UI disables duplicate actions and has no
  silent or unbounded retry.

Residual resource risk is local parsing and fixed-pattern matching cost for a deliberately selected maximum-size
document; existing extraction ceilings and the fixed seven-row output bound it.

## Data, egress, and secrets

- No HTTP client, provider, LLM, telemetry, environment secret, clipboard, or device identity is imported or called.
- Persistence contains existing snapshot identity plus bounded evidence snippets, seven checklist rows, fixed
  explainers/bases/coverage, and review state. It does not copy the manuscript file.
- Activity rows contain fixed tool/version/snapshot/count summaries. Extraction failure activity uses a fixed
  message, not parser exceptions, text, or local paths.
- Errors expose only bounded local validation detail. There is no remote body, credential, header, or destination.

## Injection, evidence, and epistemic integrity

- SQLAlchemy Core binds all values. The client cannot choose a tool id, detector, result, finding type, severity,
  table, or destination.
- React interpolates evidence as text. No raw HTML, executable Markdown, arbitrary URL, or formatting structure is
  accepted.
- The receipt keeps all seven statuses. Only a gate-on `not-found` row becomes a candidate, every candidate is
  `info`, and present/not-applicable/gate-off states create no findings.
- Copy states that tables/figures are incompletely read, not detected never proves omission, and no result pools,
  models, recomputes, scores, ranks, judges, or accuses.
- Real PDF evidence may retain region/page precision. Synthetic non-PDF page 1 is cleared. Every run is exact-snapshot
  bound and visibly stales after source change.

## Verification

Backend tests cover seven-row candidate mapping, gate-off, PDF/non-PDF coordinates, disposition, staleness, missing
manuscript/primary, and non-loopback denial. Frontend tests pin both entry points, shared endpoint wiring, receipt
copy, and caveats. The bounded Chromium route exercises both surfaces at desktop/mobile width while asserting no
outbound requests or console/page errors.

Final formatting, full-suite, strict QA, dependency, Bandit, secret-pattern, and diff results are recorded exactly in
`INCREMENT-444-NOTES.md`.

## Result

**Security Audit: PASS.** No unresolved high or medium issue was found. Residual risk is bounded local parser cost
and fixed-pattern false positives/negatives; neither adds egress, remote abuse, a secret boundary, synthesis output,
objective severity, score, or accusation.
