# Increment 428 — confirmed registration acquisition and immutable versions

**Date:** 2026-07-31
**Status:** implemented

## Outcome

A reader can explicitly acquire a confirmed public OSF or AsPredicted registration, or use an already attached local
registration. The selected artifact becomes a managed `preregistration` attachment with a content hash and an
immutable version record. Opening Methods, finding a reference, discovering candidates, and confirming a candidate
still perform no acquisition. Acquisition does not run a comparison.

## Architecture and decisions

- `registration_acquisition` is a provider registry separate from metadata discovery. Providers receive only the
  confirmed persisted link; unsupported providers fail visibly and cannot fall through to an arbitrary URL fetch.
- OSF acquisition resolves fixed API endpoints and preserves registration metadata, contributors, identifiers,
  resources, files metadata, schema/version, schema blocks, every revision response, response ordering, amendment
  keys/justification, and endpoint snapshots. A deterministic Markdown rendering of structured responses is the
  primary chunked attachment; the original structured representation remains in the version row.
- AsPredicted accepts a normalized provider URL/identifier. Modern direct PDFs are downloaded after MIME and PDF
  validation. Legacy `blind.php?x=` pages may expose one same-origin PDF link; redirects and discovered PDF URLs are
  revalidated against AsPredicted's HTTPS origin. Standard numbered questions are retained when detectable.
- Local PDFs enter the identical `registration_document_versions` seam as `manual-local`, with no invented registry
  metadata and no network request.
- `registration_document_versions` stores one row per confirmed-link/content-hash pair. Re-acquiring identical bytes
  reuses the prior attachment/version; a changed hash creates a new attachment and leaves the prior version intact.
  The confirmed link points to the latest version without erasing history.
- UI states distinguish “linked, not acquired” from “attached, not compared.” Re-acquisition is the explicit **Check
  for an updated version** action. No acquisition runs on panel load.
- Registration chunks remain excluded from article synthesis/search/Methods by Increment 425's structural scope pin.

## Epistemic boundary

Acquisition establishes only which artifact and version the user selected. It does not establish prospective timing,
correct matching, adherence, compliance, integrity, or absence of discrepancies. Registry state is retained, and
withdrawn, unavailable, or embargoed artifacts cannot be confirmed/acquired through this public route.

## Security and privacy

Audit: `.claude/security-audits/2026-07-31_registration-acquisition.md` — **PASS**.

No dependency was added. Fixed-origin HTTPS validation, manual redirect validation, timeouts, 5 MiB JSON / 80 MiB
artifact bounds, MIME and PDF-magic validation, SHA-256 hashes, safe hash-derived filenames, isolated temporary files,
and transactional persistence are test-pinned. No credentials, cookies, paper text, or registration content are sent
to an external model.

## Rollback

Revert Increment 428's code/tests/docs commit. Migration 0061 is additive and has a no-op downgrade to prevent silent
loss of registration versions. Before manually dropping `registration_document_versions`, export its structured JSON
and source snapshots and retain referenced managed attachments. Increments 425–427 remain valid independently.

## Verification

- Acquisition/provider/document-scope focused suite: 26 passed.
- Acquisition/discovery/reference/frontend/health regression gate: 97 passed.
- Migration/status/document-scope gate: 41 passed.
- Full suite: **1749 passed, 1 skipped** in **916.94s** (`pytest -n auto -q`).
- Ruff formatting and lint: clean.
