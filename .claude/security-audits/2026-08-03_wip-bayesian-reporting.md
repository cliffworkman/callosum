# Security audit — WIP Bayesian reporting audit

**Increment:** 443
**Date:** 2026-08-03
**Status:** COMPLETE — PASS

## Scope and trust boundary

This increment adds `POST /wip/manuscripts/{manuscript_id}/checks/bayes` and two local UI surfaces for its stored
result. It reuses the local-only WIP router, registered-primary resolver, bounded content extractor, generic exact-
snapshot/tool-run/finding tables, and existing deterministic Bayesian recomputation/checklist code. It adds no
migration, dependency, provider, upload, public endpoint, background job, client-selected path, or secret.

Unpublished manuscript text remains inside the local read-write Callosum instance. The router-level
`require_local_wip` dependency rejects forwarded/non-loopback access; read-only mode rejects the POST.

## Input and resource controls

- FastAPI parses the manuscript id as an integer. The manuscript and registered primary file must exist. The empty
  request body supplies no prior, tolerance, detector option, regex, path, URL, destination, or nested object.
- `prepare_snapshot` resolves the stored relative path through `trusted_child` and enforces existing WIP file/type
  and extraction limits (256 MiB primary-file ceiling; 32 MiB for plain text).
- The server owns the fixed default priors, factor-of-two-equivalent log tolerance, Bayesian gate, checklist, and
  advisory patterns. No user text is compiled as code or a pattern.
- `MAX_RESULTS = 500` bounds recomputation rows; the checklist is three fixed rows and advisories are two bounded
  kinds. One click performs one synchronous extraction/audit/persist cycle. The UI disables duplicate actions and
  has no silent retry.

Residual resource risk is local parsing/numerical integration cost for a deliberately selected maximum-size complex
document with many supported inline BFs. The fixed result cap and existing extraction ceilings bound this risk.

## Data, egress, and secrets

- No HTTP client, provider, LLM, telemetry, environment secret, clipboard, or device identity is imported or called.
- Persistence contains existing snapshot identity plus bounded matched snippets, numeric recomputations, assumptions,
  three checklist rows, up to two advisories, and review state. It does not copy the manuscript file.
- Activity rows contain fixed tool/version/snapshot/count summaries. Extraction failure activity uses a fixed message,
  not parser exceptions, text, or local paths.
- Errors expose only bounded local validation detail. There is no remote body, credential, header, or destination.

## Injection, evidence, and epistemic integrity

- SQLAlchemy Core binds all values. The client cannot choose a tool id, prior, tolerance, result, finding type,
  severity, table, or destination.
- React interpolates evidence as text. No raw HTML, executable Markdown, arbitrary URL, or formatting structure is
  accepted.
- The receipt keeps reproduced and non-reproduced rows, all checklist statuses, all advisories, and fixed assumptions.
  Only a Bayesian-gated mismatch, `not-found`/`coherence-flag` row, or advisory becomes a candidate. Every candidate
  is `info`; none claims an error or objective severity. Gate-off creates no findings.
- Copy states that different priors/design interpretations commonly explain mismatch; not detected never means absent;
  advisories require expert judgment; and no result is a model fit, score, verdict, rank, or accusation.
- Real PDF evidence may retain region/page precision. Synthetic non-PDF page 1 is cleared. Every run is exact-snapshot
  bound and visibly stales after source change.

## Verification

Backend tests cover default assumptions, mismatch/checklist/advisory mapping, correlation reproduction, gate-off,
PDF/non-PDF coordinates, disposition, staleness, missing manuscript/primary, and non-loopback denial. Frontend tests
pin both entry points, shared endpoint wiring, receipt fields, and caveats. The bounded Chromium route exercises both
surfaces at desktop/mobile width while asserting no outbound requests or console/page errors.

Final formatting, full-suite, strict QA, dependency, Bandit, secret-pattern, and diff results are recorded exactly in
`INCREMENT-443-NOTES.md`.

## Result

**Security Audit: PASS.** No unresolved high or medium issue was found. Residual risk is bounded local parser/
integration cost and fixed-pattern false positives/negatives; neither adds egress, remote abuse, a secret boundary,
objective severity, score, or accusation.
