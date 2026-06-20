# Increment 49 Notes — Editable Details pane (Mendeley-style) + DOI correction / re-resolve

Backlog item **G**, the "reference manager first" centerpiece: the Detail pane is now a fully
**editable, inline, Mendeley-style** bibliographic editor, and a wrong/missing **DOI can be
corrected and re-fetched from Crossref**. Metadata quality is upstream of clustering, dedup,
citations, and synthesis — so this is high leverage.

## Implemented

### Backend
- **`app/backend/metadata/paper_edits.py` (new, pure):** `build_paper_update(existing_row, edits)`
  computes a safe partial update — copies the existing `csl_json`, merges **only** the changed keys
  (never a blind re-projection → no wiping untouched fields), keeps the affected scalar columns in
  sync, and stamps `imported_source="user-edited"`. Handles the date triple (year/month/day →
  `issued.date-parts`, stop-at-first-None, + `year`/`publication_date` columns), authors (→ CSL
  `{literal}` + first-token `first_author_family_name`), DOI normalisation, and a generic scalar
  passthrough for non-core csl keys (reserved keys skipped).
- **`enrichment.py`:** `USER_EDITED_SOURCE = "user-edited"` (deliberately NOT in
  `_can_update_from_crossref`'s allowlist, so the batch enrich won't clobber hand-edits) + a `force`
  flag on `enrich_paper_metadata_from_crossref` (the explicit re-resolve overrides the guard).
- **`routers/papers.py`:** `PaperUpdateRequest` (all optional, length/range-capped; generic `csl`
  patch key/value-validated). **`PATCH /papers/{id}`** → `build_paper_update` →
  `update_paper_metadata` + `refresh_processing_tier`; DOI-UNIQUE clash → **409**; empty title /
  no fields → **422**. **`POST /papers/{id}/re-resolve`** → re-run Crossref (force) on the paper's
  DOI; no DOI → **422**; Crossref miss → `crossref-unresolved`, **200** (graceful, never 500).
  `_crossref(app)` accessor mirrors the other injectables.
- **`app.py`:** `create_app(crossref_client=…)` + `api.state.crossref_client` (hermetic test injection).

### Frontend (`app/frontend/js/25_detail.jsx` — new chunk; `DetailContent` moved out of `20_synthesis.jsx`)
- Mendeley-style **inline, always-editable** pane: every field reads as text until hover/focus, grey
  "Add …" placeholder when empty, **auto-saves on blur** (one-field PATCH → refresh from response).
- **Literature Type** dropdown (Mendeley vocabulary → CSL types; preserves an unknown stored value),
  large editable **Title**, then the core fields directly (no "KEY INFORMATION" header), a collapsible
  **Identifiers** section (DOI + 🔎 re-resolve, ArXiv, PMID, Cite key, ISBN, ISSN), a **More** section
  that auto-surfaces any *extra scalar field a DOI populated* (the DOI decides what shows), a compact
  **Files** list (each opens its PDF — merge substrate), and the honest provenance footer (metadata
  source incl. `user-edited`/`crossref` + tier).
- Abstract editable with Expand/collapse. `RightPane`/`App` thread `onOpenPaper` (= `openPdf`).
- CSS: token-only inline-editable recipe (`.detail-edit`, focus-ring on hover/focus); removed the now-
  dead `.detail-title`/`.author-list`/`.abstract`/`.v a` rules. Rebuilt `callosum-app.html`.

## Key technical detail
`csl_json` **is** the canonical bibliographic record; the scalar columns (title/year/venue/doi/…)
are projections. So the editor needs **no migration**: volume/issue/page/dates/URL/ISSN/ISBN/PMID/
arXiv/type all live in `csl_json` (already returned wholesale). The partial-merge in
`build_paper_update` is the linchpin — it edits a *copy* and writes only changed columns, so a single
field PATCH can't wipe the rest of the record, while **re-resolve** intentionally replaces the record
from Crossref (overwrite = a fresh authoritative fetch the user asked for; it drops fields Crossref
omits, e.g. a manually-added `publisher`).

## Manual verification script
1. Rebuild (`python tools/build_frontend.py`), restart uvicorn, hard-reload, open a paper, click **Detail**.
2. Click the **Journal** field, type a value, click elsewhere → it persists; the provenance footer
   flips to `user-edited`.
3. In **Identifiers**, paste a real DOI and click **🔎** → the title/authors/year/journal fill from
   Crossref and the footer flips to `crossref`. (Offline → a gentle "couldn't resolve" note, no crash.)
4. Change **Literature Type**; toggle **Identifiers**/**More**; **Expand** the abstract; confirm a
   file under **Files** opens the PDF.

## Verification
- **pytest: 172** (+22): `tests/test_paper_edits.py` (12 pure-mapping cases) + PATCH/re-resolve
  integration in `tests/test_papers.py` + route-surface invariant updated (`tests/test_health.py`).
- **Live E2E** (`.local/detail_edit_e2e/`, fake Crossref, no network): More passthrough + files render;
  inline edit auto-saves (prov→user-edited); DOI re-resolve fills metadata (prov→crossref); **0 console
  errors**. Screenshot captured.
- **Audit:** `.claude/security-audits/2026-06-19_paper-edit-doi.md` → PASS.

## Backlog / deferred
Done: **G** (editable Details + DOI re-resolve). Deferred (noted): **per-attachment PDF serving** (the
Files list opens the primary PDF today — true per-file routing lands *with* duplicate-merge, which adds
multi-PDF records); multiple URLs; Translator(s); an "add arbitrary field" menu in **More** (today it
only surfaces fields a DOI populated). Next queued: tier-tag ✓-confirm, B′ eyeball, library
multi-select/dedup/merge, suggest-optimal-axes.
