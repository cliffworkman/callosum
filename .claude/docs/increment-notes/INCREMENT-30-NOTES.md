# Increment 30 Notes

First increment where the user authors and owns persistent data: **text-selection
highlighting** in the PDF viewer (annotation suite, increment A). No comments, no
synthesis-linking, no re-anchoring recovery yet — just durable, text-selected highlights.

## Implemented

- **Selectable text.** The PDF.js **text layer** is now rendered over each page canvas
  (`renderTextLayer`, with `--scale-factor` set per page), so native browser selection
  works. Layer order per page: canvas → user-highlight layer → citation layer → text
  layer (top, for selection).
- **Create.** Selecting text shows a small floating swatch picker (5 preset colors);
  choosing one POSTs the highlight and renders it immediately.
- **Load + render.** Opening a paper GETs its highlights and draws them on their pages.
- **Delete.** Clicking a highlight (click hit-test, since overlays are
  `pointer-events:none` so they never block selection) opens a "Remove highlight?"
  confirm → DELETE → overlay removed.
- **Zoom-robust.** Highlights reuse increment-29's percentage-of-source-dimensions
  overlay model, so they stay aligned across zoom (verified 0% drift).
- **Distinct styling.** User highlights are a translucent color fill with no border/glow
  (`.pdf-user-highlight`), visually distinct from the bordered indigo citation overlay
  (`.pdf-highlight`), and live in a separate `.pdf-annotation-layer` so the two systems
  never clobber each other.

## Backend

- **Schema.** Extended the existing `annotations` table (which the Zotero importer
  already writes to) with nullable native columns: `color`, `bboxes_json`, `anchor_text`,
  `prefix`, `suffix`, `source`, `note`, `updated_at`
  (`app/backend/persistence/schema.py`). One table holds imported + user (+ future
  synthesis) annotations, discriminated by `source`; imported rows leave it NULL.
- **Migration** `alembic/versions/0002_annotation_highlights.py` — idempotent
  (inspects existing columns). Because migration 0001 is `metadata.create_all` over live
  schema, a *fresh* DB already has the columns (no-op); an *existing* DB is upgraded via a
  `batch_alter_table(recreate="always")` table rebuild (required: SQLite `ADD COLUMN`
  rejects `updated_at`'s non-constant `CURRENT_TIMESTAMP` default). Simulated upgrade of a
  pre-0002 DB preserved the Zotero-import row, FK `ON DELETE CASCADE`, and indexes.
- **Repository** (`repository.py`): `create_annotation` (defaults `source="user"`, stamps
  `coordinate_system="pdf-points-top-left"`), `get_annotation`, `list_annotations_for_paper`
  (scoped to `source IN ('user','synthesis')` so imported rows are not surfaced),
  `delete_annotation`.
- **Endpoints** (`api/app.py`, new Pydantic models only — no existing shape changed):
  `POST /papers/{paper_id}/annotations` (201; validates body + color allowlist + bbox
  sanity; 404 unknown paper), `GET /papers/{paper_id}/annotations`,
  `DELETE /annotations/{annotation_id}` (204; 404 unknown). Mutation pattern mirrors
  `summary_delete` (Depends(get_connection) + commit).

## Coordinate mapping (selection → bbox)

Stored rects are `pdf-points-top-left` (the increment-29 basis), so they render through
the existing transform. From a selection's per-line `range.getClientRects()` and the page
wrapper rect:

- `sx = sourceWidth / wrapRect.width`, `sy = sourceHeight / wrapRect.height`
  (points-per-displayed-px — robust to CSS down-scaling, not just `scale`)
- `x0 = (r.left - wrapRect.left) * sx`, `y0 = (r.top - wrapRect.top) * sy`, etc.

A multi-line (and multi-column, in two-column papers) selection yields **multiple rects**,
one per line fragment — all stored in `bboxes_json` and each drawn as its own overlay.
`anchor_text` = the selection string; `prefix`/`suffix` = ~40 chars of verbatim context
captured via cloned ranges (stored now for a later re-anchoring increment; no recovery yet).

## Manual verification script

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
# one-time on an existing DB: bring it to the new schema
alembic -x sqlalchemy.url="$env:CALLOSUM_DB_URL" upgrade head   # or: set the url in alembic.ini
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/`, double-click a paper that has a local PDF, then:
1. Select a passage → pick a color → confirm the highlight lands on the selected text.
2. Reload the page, reopen the paper → confirm the highlight reappears in the same place.
3. Zoom in/out → confirm it stays aligned.
4. Click the highlight → Remove → confirm it's gone from the UI (and `GET .../annotations` is empty).

## Automated verification (headless, this session)

A throwaway Playwright (Chromium 138) E2E built a controlled DB pointing at a real
`library/` PDF and drove the full flow. Result — **PASS**:

- text layer rendered + selectable; **no console errors** (only the benign in-browser-Babel notice)
- highlight union covered **98.6%** of the selected text's bbox (lands on the text)
- after full reload + reopen, the highlight re-rendered at **0.0 px** drift (durable + correct)
- across a zoom step, alignment drift **0.0%**
- delete removed it from the UI and the DB (**0** remaining)

## Pytest

```text
107 passed in ~80s
```
(101 baseline + 6 new: API create/list/delete round-trip, native-scope exclusion of
imported rows, unknown-paper 404, invalid-payload 422s, route-surface invariant updated;
repository round-trip, cascade-on-paper-delete.)

## Rough edges / known limitations

- **Cross-page selections** are reduced to the start page's rects (the picker keys off the
  selection's start page). Multi-column *within a page* is fully handled (per-fragment rects).
- **Rotated pages**: user highlights, like citation overlays, are not drawn on pages with
  nonzero rotation (inherited increment-29 limitation).
- **Selecting over an existing highlight**: overlays are `pointer-events:none`, so this works;
  but a brand-new selection that begins exactly on highlighted glyphs can be fiddly.
- **No length caps** yet on `anchor_text`/`prefix`/`suffix`/`bboxes` (local-disk concern
  only; flagged for public-exposure hardening in the security audit).
- `renderTextLayer` API is 3.11.174-specific (`textContentSource`); a PDF.js bump may need
  a tweak.
