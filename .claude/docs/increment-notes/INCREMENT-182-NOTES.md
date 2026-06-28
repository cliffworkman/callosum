# Increment 182 — extract LibraryFrame from 30_viewer (discovery SP0 prerequisite)

A behavior-preserving split (the inc-176 precedent) that clears the maxed `30_viewer.jsx` (599/600) **and** gives
the discovery Search tab (#28) a home.

## Implemented
- New chunk **`app/frontend/js/30c_frame.jsx`** = `LibraryFrame` (the center tab shell: the Library tab + one tab
  per open PDF / dashboard), moved verbatim from `30_viewer.jsx`. Function declaration hoists in the shared IIFE,
  so it still references `PdfViewer` / `PaperList` / `MyPubsDashboard` regardless of chunk order; `App` (40_app.jsx)
  still renders `<LibraryFrame>` unchanged. `30_viewer.jsx` **599 → 557** (comfortable headroom for the search-tab
  branch, which lands in 30c_frame).
- **QA (rule #10):** LibraryFrame's tab/close/reading-mode elements moved chunks → `route_00_smoke_readonly.md`
  `fe:` repointed to add `30c_frame.jsx` (a surface relocation; 618/618 covered).
- Also commits the discovery design spec `.claude/docs/specs/2026-06-28-discovery-search-design.md`.

## Verification
Frontend-only; no backend/migration/egress. `test_frontend_assembly` 5/5; surface **121/121 API + 618/618 FE**;
pytest **619**. **Behavior-preserving (headed, no egress):** re-ran `.local/visual/drive_inc176_notesfilter.py` —
opening a PDF tab via `LibraryFrame` + the notes filter still work; 0 console/page/genai.

## Next
SP1 (inc 183): the discovery Search tab — the SourceProvider registry + the Crossref provider + the
`/discovery/{search,save}` endpoints + the Search tab in `30c_frame.jsx`.
