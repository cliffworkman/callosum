# Increment 596 — Paper-scoped Ask in the PDF reader ("Stay with the paper")

A compact **✦ Ask** action in the reader toolbar opens a modal over the undisturbed PDF, scoped to the current
paper, runs the **ordinary production Ask pipeline**, shows the same grounded answer + evidence, and closes back
to the exact reading position. It is a **new front end onto canonical Ask, not a new Ask** — a thin frontend-only
projection with **zero backend change**, which structurally guarantees the non-negotiable 0.6/0.7 isolation
(no `experiments/**`, no `summarization/**`, no prompt/retrieval/verification/adjudication file is touched).

## Implemented
- **`app/frontend/js/30j_reader_ask.jsx` (new):** `ReaderAsk({ paperId, title, onOpenCitation, onSaveHighlight,
  onOpenSettings })` — a self-contained toolbar button + modal. Submits the canonical call
  `apiPost("/summarize", { scope_type:"papers", paper_ids:[paperId], query, top_k:8 })`, polls via the shared
  global `observeJobUntilTerminal`, and renders results with the SAME components as Synthesize → Ask
  (`GroupedSummarySentences`, `SynthesisFailure`). Also exports the pure `readerAskRequest`/`readerAskPaperValid`.
- **Reader wiring (prop threading only, no new logic):** `30_viewer.jsx` (signature + one toolbar button placed
  on the spacer line — net 0, stays 599), `30c_frame.jsx` (`LibraryFrame` signature + `PdfViewer` mount),
  `40_app.jsx` (append `onOpenCitation`/`onSaveHighlight`/`onOpenSettings` to an existing `LibraryFrame` prop
  line — stays at 600), `styles.css` (`.pdf-ask-btn` + `.reader-ask-*`, reusing the `axis-modal`/token vocab).
- **QA route** `route_95_reader_ask.md`; **help** corpus note under "Highlights and notes"/reader.

## Key technical detail — the canonical one-paper *question* scope already existed
The production Ask contract already supports a question restricted to one paper: `scope_type="papers"` restricts
the candidate pool to `paper_ids` at the SQL level (`pipeline.py:256-258`), a `query` still ranks within that
pool (`_rank_chunks_for_query`, `preserve_paper_coverage=True`), and `SummaryScope.to_ref()` carries the `query`
so the generator answers it. The production frontend already sends this exact shape for "summarize selection with
a focus" (`20_synthesis.jsx:258-259`). So the reader needs **no new scope seam and no reader-side filtering** —
it just calls the canonical endpoint with a single-paper scope.

## Amendment decisions (from the approval)
- **(1) Honest no-answer state:** reuses canonical Ask's own language — `sentences.length === 0` →
  "No groundable summary produced. The generator returned no sentences — your question may not be addressed in
  this paper." (a claim about generation, not an overstated claim that the paper lacks the content). No
  reader-invented "no evidence" text; no friendly upgrade past verification.
- **(2) Drift guard (no clean submit/request seam):** the production submit/poll logic
  (`launch`/`launchPrepared`/`pollJob`) is **closure-bound inside `SynthesisPane`** — not reusable without
  refactoring that component (which would risk the "Synthesize unchanged" invariant and broaden scope). So the
  reader reuses the genuinely-shared pieces (`observeJobUntilTerminal` poller; `GroupedSummarySentences`/
  `SynthesisFailure` renderers) and keeps its own thin request body, **pinned by
  `tests/test_reader_ask_scope.py`**: papers+query single-paper scope restricts retrieval to exactly that paper
  (no other paper's chunks leak in) AND passes the question to the generator — i.e. reader Ask == canonical Ask
  semantics except for the deterministic single-paper scope.
- **(3) Wording:** the readout uses "Retrieved N source chunk(s) from this paper", never "coverage".

## Paper relationship / provenance
A reader-launched Ask is an **ordinary summary artifact** whose `scope_ref_json` records `paper_ids:[id]`
(`schema_summaries.py`) — discoverable by paper later (the future paper hub) with no reader-local copy.
"Deduplicate the object, not its relationships."

## Evidence navigation + mobile
Clicking a citation's **Open source** calls the canonical `openCitation` (navigates the already-open reader tab
to the page/precision), then closes the modal so the page is revealed. Plain **Close** never moves the PDF
(page/scroll/zoom preserved — the overlay never remounts `PdfViewer`). The modal reuses the responsive
`axis-modal` (`min(680px, 94vw)`), so it works at narrow widths without depending on any desktop right-hand pane.

## Failure / epistemics
`SynthesisFailure` (canonical) renders backend/provider failures with a working **Open Settings** door on the
AI-off case (`onOpenSettings` threaded). Weak/flagged results show canonical chrome. Nothing is upgraded because
the interaction started in the reader.

## Principles gate (rule #9)
Unchanged epistemics — same verifier, evidence schema, coordinate honesty, confidence display; the reader is only
another client of the canonical pipeline. No opaque score, no friendly-answer upgrade. The misaligned easy path
(a reader-local "chatbot" with its own answer representation) is declined by construction.

## Security / audit
Audit gate **not triggered** — frontend-only client of the already-audited, egress-gated `/summarize` (no new
endpoint, external fetch, ingestion path, or auth). The question text rides the same AI-egress consent gate as
every Ask; the request fires only on the explicit Ask click (never on opening the reader).

## Manual verification (owed — native window not scriptable here)
1. Open a paper with chunks; confirm **✦ Ask** in the toolbar. 2. Click → modal over the PDF, "Asking about:
{title}"; confirm 0 `/summarize` until submit. 3. Submit → one `/summarize` with `scope_type:"papers",
paper_ids:[thisPaper]`; answer + evidence render. 4. Evidence **Open source** → current PDF navigates + modal
closes. 5. **Close** → PDF unchanged. 6. Egress off → canonical failure, PDF usable, **Open Settings** works.
7. Library selection + Synthesize pane unchanged. 8. Narrow width usable. **Packaged-Tauri reader-modal
focus/scroll smoke is owed against the next installer.**

## Gates
- **Pytest:** `tests/test_reader_ask_scope.py` — **2 passed** (drift guard). `tests/test_frontend_assembly.py`
  — **87 passed**. Ruff check clean.
- **QA:** `build_surface_map.py check` → API 440/440 (no new API surface; reuses `/summarize`); `route_95`
  covers the new FE control/view-state.
- **Line budget:** all files ≤600 (`40_app.jsx` 600, `30_viewer.jsx` 599 — both held by appending to existing
  lines; new logic in `30j`).
- **Drift gates:** demo + website re-declined at inc 596 (frontend-only; no dedicated showcase/demo entry yet);
  `route_95` recorded in `excluded_qa_routes`.

## Not built (explicit non-goals)
Selection-scoped "Ask this passage", persistent highlights/anchored artifacts, the paper hub, Critique/reference/
triage integration, 0.7 orchestration, a conversational thread system, side-pane co-existence of answer + page,
any Synthesize redesign. Known limitation: evidence **Open source** closes the modal to reveal the page (no
side-by-side answer+page — that is the future hub/side-pane, out of scope); the Ask run is saved as an ordinary
summary, recoverable in Synthesize history.
