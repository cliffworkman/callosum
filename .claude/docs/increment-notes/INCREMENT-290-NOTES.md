# Increment 290 — Library selected-paper tab + PDF tab reorder

Group C from the `feature/library-ux-polish` handoff: make the selected paper visible in the Library tab strip before
it is opened, and let users reorder open PDF reader tabs.

## Implemented

- `app/frontend/js/30c_frame.jsx`: added a pinned selected-paper tab immediately after **Library**. It renders only
  when the app-level selected paper is not already open as a PDF tab, has no close button, is not draggable, and
  opens the PDF through the existing `onOpenPdf` path when clicked.
- `app/frontend/js/30c_frame.jsx`: made normal open PDF tabs HTML5 drag sources/drop targets. Drag-over uses the same
  dashed accent invite as other pending drop targets, and dropping one PDF tab on another reorders the open-tab array.
- `app/frontend/js/40_app.jsx`: added selected-paper tab metadata lookup from `/papers/{id}`, suppresses the
  selected-paper tab when the paper is already open, and owns `reorderPdfTabs` so active tab state stays keyed by the
  same `pdf:<paper_id>` value.
- `app/frontend/styles.css`: added `.frame-tab-selected` and `.frame-tab.dragover` using token-only dashed
  `--accent` border + `--accent-soft` fill.
- `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, and
  `tests/test_frontend_assembly.py`: updated user help, design contract, route 73 manual checks, and assembly guards.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Experience pass

Persona: a user triaging many Library papers, selecting papers to inspect Details/Methods before deciding which PDFs
to open, then keeping several reader tabs in a working order.

Finding: fix-now complete. The selected paper is visible in the reader tab strip without being conflated with an open
reader tab, and the moment the user opens it the temporary tab disappears into the real PDF tab. Users can now put
multiple open reader tabs into their own sequence without closing/reopening PDFs.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py`: **38 passed**.
- `python tools/qa/build_surface_map.py check` reported **245/245 API** and **1147/1147 FE** covered.
- Browser smoke against the fresh static bundle with mocked Library APIs confirmed:
  selected-paper tab appears pinned after **Library**, is not draggable, opens the PDF through the reader path, hides
  when the paper is open, and open PDF tabs reorder by drag/drop.
- `python -m pytest` on the final code path: **1242 passed, 1 skipped** in 21:17.
- `ruff check .` passed.
- `ruff format --check .` passed (`464 files already formatted`) after formatting the new assembly guard.
- `python tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
