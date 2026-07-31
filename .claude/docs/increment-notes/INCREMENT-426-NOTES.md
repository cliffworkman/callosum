# Increment 426 — registration-reference extraction and local attachment

**Date:** 2026-07-31
**Status:** implemented

## Outcome

The Transparency panel now separates preregistration/registration language from an actionable external reference.
Callosum locally extracts, normalizes, persists, and source-anchors registration references without resolving them,
attaching a provider candidate, or implying that a reference is the correct registration for the paper.

This increment adds no registry discovery or network acquisition. Those remain user-triggered later increments.

## Architecture and decisions

- `methods/registration_references.py` is a deterministic local extractor for OSF URLs/DOIs, AsPredicted
  URLs/identifiers, ClinicalTrials.gov NCT identifiers, PROSPERO CRD identifiers, and generic DOI/URL references only
  when registration context is present. A language-only statement remains a transparency signal with zero references.
- PyMuPDF extraction now retains URI annotations. Link rectangles are associated to word-level visible text (so a link
  on “here” is not widened to its whole sentence), plus nearby evidence and an explicit association class. A hidden
  target is stored as not explicitly printed.
- `paper_registration_references` stores evidence records separately from both `open_science_signals` and the future
  candidate/confirmed registration-link model. Machine rows are attachment-scoped and replaceable on reprocessing;
  manual rows are idempotent and preserved.
- PDF/text ingest extracts reference evidence after chunks are created. Reprocessing refreshes rows for the exact
  attachment. Legacy chunks are still detected live by the read-only Transparency endpoint; reprocessing makes those
  rows persistent.
- The API returns four local states: `not-detected`, `language-detected`, `reference-detected`, and
  `multiple-references-detected`, with source evidence and attachment/page location where available.
- Manual controls save a URL/DOI/identifier, upload a selected local PDF as a managed `preregistration` attachment,
  or assign that role to an existing attachment. Saving a string never resolves it. Upload remains a separate
  browser-selected local action and does not fetch a URL.
- The Increment-425 scope invariant remains pinned: newly attached registration chunks are readable by exact
  attachment only and excluded from ordinary article synthesis/search/Methods/processing counts.

## Epistemic boundary

- “Reference detected” means an identifier/link was located, not that it is the correct registration.
- “Language detected” and “not detected” never mean a registration is absent.
- No prospective-timing claim is made, so the UI uses registration/preregistration according to the source wording
  and does not certify that a record predates data collection.
- No compliance, integrity, risk, author, or paper score/verdict exists.

## Security and privacy

- Audit: `.claude/security-audits/2026-07-31_registration-reference-local-acquisition.md` — **PASS**.
- Detection, normalization, persistence, PDF-link annotation, and chunking are local and deterministic.
- Local upload is loopback-only/read-write-only, streamed under the existing 80 MiB cap, `%PDF-` + PyMuPDF validated,
  safely named inside the managed library, and cleaned up on failure.
- “Open externally” is an explicit browser navigation. The server performs no request.
- No provider, credential, cookie, dependency, arbitrary URL fetch, AI call, or egress surface was added.

## QA and help

- Help documents the language/reference distinction, local states, manual fallback, and no-resolution boundary.
- QA route 63 covers printed and hidden references, malformed/manual input, local file attachment, role reassignment,
  persistence, egress absence, and the document-scope regression.

## Rollback

Revert Increment 426's code/tests/docs commit. Migration 0059 is additive and its downgrade deliberately preserves the
local evidence table; leaving it orphaned is harmless. To remove it manually after rollback, first export any manual
reference evidence, then drop `paper_registration_references`. Delete managed registration PDFs only by using the
normal paper/attachment lifecycle—never by broad filesystem cleanup. Increment 425 must not be rolled back while any
registration attachment remains chunked.

## Verification

- Final registration/document-scope/PDF/transparency/migration focused suite: **57 passed**; the later
  assembly/migration/reference/document-scope gate passed **81/81**.
- PDF/papers/transparency/document-scope/migration/frontend integration slice: **188 passed** before rebuilding the
  intentionally stale frontend artifact; frontend assembly then passed **58/58**.
- Ruff: **565 files formatted**, all checks passed. Touched application files remain ≤600 lines after splitting PDF
  link annotations and registration schema ownership into focused modules.
- Full suite: **1731 passed, 1 skipped** in **896.78s** (`pytest -n auto -q`).
