# Increment 176 — Notes-panel extraction + noted-only filter + note search (reading-pane)

Unblocks the reading-pane follow-ups by relieving the `30_viewer.jsx` 595/600 cap, then adds the first two
panel-local features. "Follow your heart" continuation of inc 175.

## Part 1 — the split (behavior-preserving)
- New chunk **`app/frontend/js/30b_notes.jsx`**: a purely-presentational **`AnnotationsPanel`** (the Notes panel —
  Copy/Export + the per-row jump/edit/delete list). All state + handlers stay in `PdfViewer` and arrive as props
  (`annotations`, `onCopy`, `onExport`, `onJump`, `onEdit`, `onDelete`). `30_viewer.jsx` replaces the ~24-line
  inline panel with a 3-line `<AnnotationsPanel .../>` → **595 → 573** (comfortable headroom). The function
  declaration hoists within the shared IIFE, so load order vs. `30_viewer` doesn't matter (raw-assembly inclusion
  + a successful build is the gate, per the inc-121 esbuild-DCE note).
- **Verified behavior-preserving** by re-running the inc-144 driver (`drive_inc144_marks.py`) — Copy/Export still
  assemble the exact highlights+notes digest (read back off the clipboard); 0 console/page/genai.
- **QA (rule #10):** the panel's 9 elements moved chunks → `route_32_viewer_annotations.md` `fe:` repointed to
  `30_viewer.jsx, 30b_notes.jsx` (a surface relocation, not new surface).

## Part 2 — the features (in the extracted panel)
- **Noted-only filter** — a "Noted" checkbox shows only highlights that carry a note.
- **Note search** — a search box filters by **note OR highlighted text** (case-insensitive). The head count shows
  `shown / total` when filtered; an empty result shows "No highlights match this filter."
- Local state in `AnnotationsPanel` (`notedOnly`, `query`) — no PdfViewer change. CSS: `.pdf-annot-filter` /
  `.pdf-annot-search` (conforms to the `.searchbar input` recipe + tokens, rule #8) / `.pdf-annot-notedonly`.

## Gates
- Frontend-only; no backend/endpoint/migration/egress → no audit; Principles non-triggering.
- Surface **121/121 API + 612/612 FE, 0 uncovered** (route_32 claims the new chunk; the search input + checkbox
  are the +4 FE surfaces, covered). Frontend rebuilt; `test_frontend_assembly` 5/5; pytest **619**. No Python →
  ruff n/a.

## Verification
**Headed, no egress** (`.local/visual/drive_inc176_notesfilter.py`): seed 2 highlights (one noted) → search
'positional'→1 (text match), 'core'→1 (note match), Noted→1; 0 console/page/genai. Plus the inc-144 driver for
the behavior-preserving split.

## Reading-pane remainder
`30_viewer.jsx` now has headroom (573) for the rest: next/prev-mark hotkeys (PdfViewer; mind hotkey conflicts),
keyboard zoom (Ctrl+± fights browser zoom — a UX call), fit-page, free-form note colors, a minimap marker.
