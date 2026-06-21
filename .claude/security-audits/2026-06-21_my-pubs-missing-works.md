# Security audit — My Publications missing-works review + import (inc 85)

**Date:** 2026-06-21
**Feature:** a review queue for OpenAlex-indexed works missing from the library — accept (import) / reject
(dismiss) per work, reusing the inc-74–76 import lane. **Gate trigger:** 2 new API endpoints + a create-paper /
import path + a migration.

## Surface added
- Migration **0013** (`profile.dismissed_work_dois` JSON; additive, idempotent).
- `build_dashboard` → `missing_works` (cached author works whose DOI ∉ live library ∉ dismissed; cache-only).
- `POST /my-publications/works/import {doi}` → `import_missing_work` (validate DOI ∈ author works →
  `create_paper` + `enrich_paper_metadata_from_crossref(force=True)` + confirmed My-Pubs membership).
- `POST /my-publications/works/dismiss {doi}` → `dismiss_work`.
- Frontend: a collapsible "indexed works not in your library" dashboard section (Import / Dismiss per row).

## Threat review

**Input validation / arbitrary-DOI minting.** The import endpoint takes a `{doi}`; `import_missing_work`
**validates the normalized DOI is one of the resolved author's cached OpenAlex works** before creating
anything — you cannot mint a paper from an arbitrary DOI through this path (returns `not-author-work` → 422).
Blank DOI → `invalid` → 422. Unresolved profile → `not-resolved` → 409. Already-in-library → idempotent
(`exists`, returns the existing paper id; no duplicate, no DOI-UNIQUE violation). `dismiss_work` normalizes +
stores the DOI in a JSON list (bound-param).

**Data egress (invariant #3).** The missing-works list + dismiss are **local / cache-only** (no network). The
import does **one Crossref DOI lookup** (`enrich_paper_metadata_from_crossref`, cached, fail-closed) — public
metadata infrastructure, the **same posture as re-resolve / wanted-list import**, explicitly **NOT** the Gemini
`CALLOSUM_ALLOW_DATA_EGRESS` gate. No library text leaves the machine.

**File-path safety.** The import is **metadata-only** — `create_paper` + Crossref enrich; **no PDF download, no
file write** (the OA-PDF path stays the separate, already-audited per-paper "Acquire OA copy" flow). No path is
built from any input.

**SQL / injection.** SQLAlchemy bound parameters throughout (the `papers.doi IN (...)` match, the JSON writes,
`create_paper`). DOIs are normalized (lower/strip) before comparison + storage.

**Secret handling / supply chain.** No new secret, no new dependency. The Crossref client is injectable
(`app.state.crossref_client`) for hermetic tests.

**Inspectability / facts-vs-candidates (PRINCIPLES).** OpenAlex-attributed works are **candidates**, shown
attributed (title · year · citations · DOI — inspectable), and the **human imports or dismisses** them; nothing
is auto-imported. This mirrors the inc-78 candidate confirm/reject, extended to external works. No composite
score. **No-accusation** honored — it's the user's own works, no judgment of others. An imported work joins My
Pubs as a confirmed member (the user chose it).

## Negative-path checks (recorded)
- **DOI not among the author's works → import:** `not-author-work` → 422 (`test_import_rejects_non_author_doi`). ✓
- **Already in library → import:** `exists`, returns the existing id, no duplicate. ✓
- **Dismiss → filtered:** a dismissed DOI drops from `missing_works` + persists (`test_dismiss_work_persists`). ✓
- **Import → library + My Pubs + drops from missing:** `test_import_missing_work_adds_to_library_and_mypubs`. ✓
- **Crossref unresolved on import:** the paper is still created + joins My Pubs (the explicit confirmed-member
  add is cache-/Crossref-independent). ✓

## Result
**Security Audit: PASS.** Import is guardrailed to the author's own indexed works (no arbitrary minting),
metadata-only (no PDF/file write), and its only egress is the already-audited Crossref DOI lookup (not the
Gemini gate). The list + dismiss are local. SQL is bound-param; the human drives every import/dismiss (no
auto-action); works are shown as inspectable candidates.
