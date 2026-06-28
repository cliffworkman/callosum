# Increment 179 — mark-nav keyboard hotkeys (reading-pane)

The keyboard pairing for the inc-177 ◂ Mark / Mark ▸ buttons: **`[`** and **`]`** step to the previous/next
highlight (page-ordered, wrapping, flashing each via `jumpToAnnotation`).

## Implemented (`app/frontend/js/30_viewer.jsx`)
- A `window` keydown effect calling `stepMark(±1)` on `[` / `]`, **gated** to (a) this viewer being visible
  (`scrollRef.current.offsetParent !== null` — a mounted-but-hidden tab has a null offsetParent, so only the active
  PDF tab responds) and (b) not typing (`activeElement` not INPUT/TEXTAREA/contentEditable). `preventDefault` on a
  handled key. The Mark button tooltips now show the key hint (`( [ )` / `( ] )`) for discoverability.

## Gates
- Frontend-only; no backend/migration/egress; Principles non-triggering. Surface **121/121 API + 616/616 FE** (a
  window listener, not a tracked element; buttons unchanged). Frontend rebuilt; `test_frontend_assembly` 5/5;
  pytest **619**; no Python → ruff n/a.

## Verification
**Headed, no egress** (`.local/visual/drive_inc179_markkeys.py`): `]` → a highlight flashes; again → the next;
`[` → the previous; 0 console/page/genai.

## ⚠ Rule-#1: the viewer is now maxed
`30_viewer.jsx` is at **599/600**. **Any further viewer feature requires another split first** (the inc-176
Notes-panel extraction is the precedent — extract another cohesive, low-coupling unit before adding). The
reading-pane run (175–179) is complete for now; remaining items (fit-page, note colors, a minimap) are gated on
that next split + are diminishing-value.
