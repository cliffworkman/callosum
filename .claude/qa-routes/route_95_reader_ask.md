<!-- qa-coverage
fe: 30j_reader_ask.jsx
-->

# ROUTE 95 — Paper-scoped Ask in the reader ("stay with the paper")

**Tier:** 2 (canonical Ask; provider AI when egress is on)
**Goal:** Exercise the reader-hosted Ask — a **thin client of canonical Ask**, not a new Ask. In the PDF
reader, the toolbar **✦ Ask** button opens a modal over the undisturbed PDF, scoped to the current paper, and
runs the ORDINARY production Ask: `POST /summarize` with `{scope_type:"papers", paper_ids:[currentPaperId],
query, top_k:8}` → the shared `observeJobUntilTerminal` poller → the SAME result/evidence/failure components
(`GroupedSummarySentences`, `SynthesisFailure`) as Synthesize → Ask. Inc 596.
**No new API surface** — `/summarize` is covered by `route_55_synthesis_verification`; this route covers the new
reader control + view-state and the honesty invariants specific to the reader projection.

## Environment

Clean seeded instance with a paper that has extracted chunks. To exercise the full path with a real answer,
**egress ON** with a provider key; to exercise the honesty/failure paths, **egress OFF** (the ordinary Ask
failure must surface unchanged). Register console/pageerror/request listeners before navigation.

## Standing assertions

- **Thin projection — no new Ask.** The reader Ask MUST hit `POST /summarize` (never a reader-only endpoint),
  poll via the shared job poller, and render through `GroupedSummarySentences`/`SynthesisFailure`. There is no
  reader-local retrieval, prompt, generator, verification, evidence schema, coverage calc, artifact type, or
  provenance representation.
- **Deterministic single-paper scope, explicit + visible.** The request carries **exactly** the current reader
  paper (`paper_ids:[currentPaperId]`, `scope_type:"papers"`) — never a reselect, never a hidden broadening. The
  modal always shows **"Asking about: {title}"**. (The backend single-paper-scope invariant is pinned by
  `tests/test_reader_ask_scope.py`: no other paper's chunks leak in, and the query reaches the generator.)
- **No canonical paper → unavailable, not silent.** If there is no valid current paper (`paperId` not a positive
  int) the **✦ Ask** button is disabled; the reader never silently broadens scope to the library.
- **Failure stays failure; no reader upgrade.** A backend/provider failure renders the canonical
  `SynthesisFailure` (with a working **Open Settings** door on the AI-off case). A weak/insufficient result is
  shown faithfully: `sentences.length === 0` → the canonical "No groundable summary produced. The generator
  returned no sentences — your question may not be addressed in this paper." (a claim about generation, NOT an
  overstated claim that the paper lacks the content); a flagged-only result shows the canonical flagged chrome.
  Nothing is upgraded to a friendly answer merely because it originated in the reader.
- **"Retrieved N source chunks", never "coverage".** The result readout uses the canonical "Retrieved N source
  chunk(s) from this paper" wording — it never labels a retrieval count as coverage.
- **Explicit egress.** The `/summarize` request fires ONLY on the explicit **Ask** click (or Ctrl/Cmd+Enter) —
  never on opening the reader or the modal. Opening the modal and NOT submitting issues **0** `/summarize`.
- **Stay with the paper.** The modal is a fixed overlay; the PDF stays mounted underneath. Plain **Close** does
  not move the PDF (page/scroll/zoom unchanged). Evidence **"Open source"** navigates the current reader tab to
  the citation page/precision (the cited paper IS this paper) and closes the modal so the page is revealed.
- **No scope leakage.** Running reader Ask does not change the Library selection, the Synthesize workspace scope,
  or any saved-search/focus state. Synthesize → Ask behavior is unchanged.
- **Coordinate honesty preserved.** Evidence "Open source and highlight" only for exact-coordinate verified
  citations; region/null render their honest notes (inherited unchanged from `CitationCard`).

## Adversarial checklist

- Open the modal, do NOT submit → **0** `/summarize` requests
- Submit a question → exactly one `/summarize` with `scope_type:"papers"`, `paper_ids:[currentPaperId]` only
- Answer + evidence render via the ordinary components; verified/flagged/contradicted chrome identical to Synthesize
- No canonical paper → **✦ Ask** disabled
- Egress OFF (or provider error) → canonical `SynthesisFailure`, PDF still usable; **Open Settings** works
- `sentences.length === 0` → canonical "No groundable summary produced…", no "no evidence in this paper" overstatement
- Close → PDF page/scroll/zoom unchanged; Evidence "Open source" → current PDF navigates to the page, modal closes
- Library selection / Synthesize scope unchanged after a reader Ask
- Narrow/mobile width → the modal is usable (responsive `axis-modal`)

## Steps

1. Open a paper with chunks in the reader. Confirm the **✦ Ask** button in the toolbar; confirm a paper with no
   canonical id (n/a in practice) would disable it.
2. Click **✦ Ask** → modal opens over the PDF with "Asking about: {title}". Confirm no `/summarize` fired yet.
3. Submit a question → confirm one `POST /summarize` with `{scope_type:"papers", paper_ids:[thisPaper], query,
   top_k:8}`; the answer + evidence render via `GroupedSummarySentences`.
4. Click a citation's **Open source** → the current PDF navigates to the page/passage and the modal closes.
5. Re-open **✦ Ask**, **Close** without asking → the PDF is exactly where it was.
6. Turn egress OFF (or force a provider error) → submit → canonical `SynthesisFailure`; the PDF stays usable;
   **Open Settings** navigates to Settings.
7. Confirm the Library selection and the Synthesize → Ask pane are unchanged by the reader Ask.

## Pass criteria

- Reader Ask is provably a thin client of canonical Ask (same endpoint/poller/result+failure components); scope
  is the deterministic single reader paper, explicit and visible; failure/weak-evidence shown faithfully with no
  reader-specific upgrade; explicit egress; no scope leakage; stay-with-the-paper close + evidence navigation.
- 0 console/page errors.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_95_reader_ask.md` + `screenshots/` (see `_TEMPLATE.md`).
