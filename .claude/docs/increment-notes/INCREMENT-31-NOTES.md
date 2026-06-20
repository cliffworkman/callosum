# Increment 31 Notes

Annotation suite **increment B**: comments/notes on highlights + a per-paper annotation
management panel. The `note` column from A is now writable; the project gains its first
**update** endpoint. Strictly additive — increment A's highlight behavior and the
verified-citation overlays are untouched.

## Implemented

- **Note on a highlight.** Clicking an existing highlight now opens a **note + color editor**
  popover (textarea + swatch row + Save/Delete/Cancel) instead of the old delete-only confirm.
  Save issues a PATCH; Delete removes it. A's fast path is intact: a swatch click still creates
  a note-less highlight instantly — **a note is always optional, never forced.**
- **Note indicator.** Highlights carrying a note show a small accent dot on their first rect
  box (`.has-note::after`); hovering shows the note text in the box title.
- **Management panel.** A collapsible in-viewer drawer (toggled by a "Notes (N)" button in the
  PDF toolbar) lists every annotation for the open paper — color chip, page, `anchor_text`
  snippet, and the note. Clicking a row **jumps to that page and flashes the highlight**; each
  item has Edit-note and Delete affordances mirroring the popover.
- **Backend.** `note` added to `AnnotationCreateRequest` (optional; default preserves A);
  new `PATCH /annotations/{id}` updating note and/or color on one annotation;
  `update_annotation` repository helper; note length capped at 4000 (the A-flagged hardening).

## Why a collapsible in-viewer panel (not a RightPane tab)

`RightPane` (Synthesis/Detail) is keyed off `selected` (the library row), which can differ
from the paper open in the active PDF tab — a right-pane annotations tab could list a
*different* paper's notes than the one on screen. The in-viewer drawer is inherently scoped to
the open PDF, already owns the `annotations` state + render DOM, makes jump-to-page+flash a
local call (no cross-component target plumbing), and touches **neither synthesis nor history**.

## Why PATCH (not PUT)

Only `note` and `color` are mutable; geometry/page/anchor/source are immutable after creation.
PATCH models partial update cleanly and lets a note be **cleared** (`note: null`) while leaving
color — distinguished from "field omitted" via Pydantic v2 `model_fields_set`. PUT would imply
full replacement of an otherwise-immutable resource.

## Backend specifics

- `app/backend/api/app.py`: `AnnotationCreateRequest.note`; `AnnotationUpdateRequest`
  (`note`/`color`, both optional); `ANNOTATION_NOTE_MAX_LEN = 4000` + `_validate_annotation_note`
  (enforced on create **and** PATCH); `PATCH /annotations/{annotation_id}` (404 unknown; 422 on
  empty patch / off-allowlist color / over-cap note; reuses `_annotation_response`).
- `app/backend/persistence/repository.py`: `update_annotation(conn, id, *, note=_UNSET,
  color=_UNSET)` — a `_UNSET` sentinel distinguishes "omitted" from explicit `None`; sets
  `updated_at` explicitly (belt-and-suspenders with the column's `onupdate`); returns rowcount bool.
- **No migration** — the `note` column already exists (added in 0002). Single head stays `0002`.

## Verification

- **pytest: 113 passed** (107 from A + 6 new: create-with-note, PATCH note+color, clear-note,
  PATCH 404/422s, create over-cap note, route-surface updated; `update_annotation` round-trip).
- **Headless E2E (Playwright/Chromium): PASS.** create highlight → click → add note + change
  color → Save (PATCH persisted: note ✓, color ✓) → note indicator + panel show it → **reload +
  reopen: note persists AND highlight re-renders at 0.0 px drift** (no regression to A's
  fidelity) → panel row click flashes the highlight → edit note via panel (2nd PATCH persisted)
  → delete from panel → gone from UI and DB (0 remaining). **No console errors.**

## Launch command

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```
Open `http://127.0.0.1:8080/`, double-click a paper with a local PDF, select text → swatch to
highlight, click the highlight to add a note/change color, and toggle **Notes (N)** for the panel.

## Rough edges / known limitations

- PATCH partial semantics rely on `model_fields_set` (omitted vs explicit-null note).
- Editor popover is fixed-positioned near the click/panel button; clamped to the viewport but
  not collision-aware with the panel.
- Note indicator dot sits on the **first** rect of a multi-line highlight (one dot, not per line).
- Panel is scoped to the open PDF tab (by design); it appears only when a PDF is open.
- One note per highlight (threaded/multi-comment is out of scope).
- Unchanged from A: cross-page selections collapse to the start page; rotated pages draw no overlay.
