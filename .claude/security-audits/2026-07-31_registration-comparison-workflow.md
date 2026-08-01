# Security and privacy audit — registration comparison workflow

**Date:** 2026-07-31
**Increments:** 425–432
**Status:** PASS

## Boundaries

- **Local detection/extraction:** transparency language, URL/DOI/PDF-link extraction, attachment parsing, canonical
  commitments, section/study retrieval, deterministic comparison, persistence, staleness, and review notes are local.
- **Registry discovery:** only an explicit confirmed disclosure sends paper DOI/title and detected identifiers to
  fixed OSF/DataCite metadata APIs. It sends no document text; authors/year remain local matching inputs.
- **Acquisition:** only an explicit action on a user-confirmed link downloads the selected public OSF/AsPredicted
  artifact. Manual/local attachments have no egress.
- **Comparison AI:** none. Local cached embeddings rank bounded passages. No registration or publication content is
  sent to an external model. Any future model mapping must use the existing AI/egress gate and narrow paired fields.

## Security properties

- Provider-specific HTTPS origins/identifiers; no arbitrary URL fetch, internal-network route, browser cookies,
  credentials, authenticated scraping, or search-engine scraping.
- Redirect targets revalidated; bounded timeouts and 5 MiB JSON / 2 MiB HTML / 80 MiB artifact caps.
- Content-type, PDF magic/PyMuPDF validity, SHA-256, controlled extensions/hash filenames, and system-temp staging.
- Provider errors classified/visible/isolated. Failed download/import cannot corrupt prior links, files, or versions.
- Registration versions immutable by content hash; article/supplement/extraction/chunk/pipeline fingerprints stale old
  comparisons. Incorrect/rejected links cannot start new comparisons, including stale-client races.
- Exact searched chunk IDs and attachment checksums are persisted per row; timing cannot inspect text outside that
  receipt. Empty extraction fails closed as an `extraction-uncertain` row rather than an empty positive-looking run.
- Local attachment-role changes make the affected registration link unavailable and stale prior comparisons. Both
  acquisition and comparison recheck confirmation inside their final write transaction.
- Document-scope API/AST guard structurally excludes preregistration/protocol/other chunks from ordinary article
  synthesis/search/Methods/embeddings and from the publication side of comparison.
- SQLAlchemy bound expressions and FK/check constraints protect controlled states. React renders provider/evidence
  text, notes, and metadata as text. External opening uses a no-opener context.
- No dependency added across the workflow. Hermetic tests use fixture transports/models and perform no provider or AI
  egress. Local embedding fallback requires cached weights and cannot download from this workflow.

## Epistemic abuse review

- No compliance, integrity, risk, deviation, reproducibility, or author score exists in schema/API/UI.
- Candidates never auto-attach; similarity candidates require confirmation; incorrect match is recoverable.
- Every comparison row copies both evidence locations when available, exact search scope, and uncertainty.
- One-sided evidence explicitly names non-detection; “not located” is never absence. All-aligned runs deny a positive
  certificate. Timing uses “supported”/“appears” and does not call OSF records preregistrations without date support.
- Review/dismiss/note state cannot rewrite evidence or deterministic status.

## Verification evidence

- Dedicated discovery and acquisition audits remain applicable and are incorporated by reference.
- Structural document-scope, provider negative-path, migration, staleness, incorrect-match race, frontend assembly,
  QA surface-map, and curated evaluation-manifest tests pass in the final gate.
- Increment 433 final full suite: **1778 passed, 1 skipped**; computed QA coverage remains **351/351 API** and
  **1537/1537 frontend**, zero uncovered.

## Result

**PASS.** Network actions are explicit, fixed-origin, bounded, credential-free, and isolated; comparison content stays
local; source/version scope is auditable; and the UI cannot turn the crosswalk into an aggregate integrity verdict.
