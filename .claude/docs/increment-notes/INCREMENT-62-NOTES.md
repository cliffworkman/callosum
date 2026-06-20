# Increment 62 Notes — Summarize selected papers (multi-paper verified synthesis from the library)

The crown-jewel verified synthesis could already run over a set of papers (the `/summarize` `papers` scope),
and the library already had checkbox multi-select (inc 54) — but the checkboxes only wired to *delete*. This
increment wires **"summarize N"** into the library bulk bar: select papers → get a verified, citation-grounded
synthesis of exactly that subset, in the always-on Synthesis pane. Reuses the existing summarize +
verification + inc-61 cache spine. The **critical-review supplement is deferred** (gated on the Auditability
standard).

## Implemented
- **Backend coverage fix** (`app/backend/summarization/pipeline.py`): `_round_robin_by_paper` — for a
  multi-paper, **no-query** scope, interleave chunks across the selected papers (paper1.c1, paper2.c1, …)
  before the `top_k` slice, so the budget **spans all selected papers**. (Previously `rows[:top_k]` took the
  first `top_k` chunks by id — which, since ids are import-ordered, filled from the lowest-id paper and
  ignored the rest.) **≤1 paper → identity**; the query path (`_rank_chunks_for_query`) already spreads, so
  it's untouched. Also improves the existing cluster-node scope (shares the path). No new endpoint/migration;
  the inc-61 cache keys on the resulting chunk set, so it works unchanged.
- **Frontend wiring:**
  - `10_pdf_layer.jsx`: a **"summarize"** link in the library bulk bar (beside delete/clear) → `onBulkSummarize`.
  - `40_app.jsx`: `pendingSummarize` state + `bulkSummarizePapers` (mirrors `bulkDeletePapers`) — sets a
    nonce-bumped `{paper_ids, count, nonce}`, forces the right pane open, clears the selection; threaded into
    `libraryProps` (→ `LibraryFrame` spreads to `PaperList`) and into `RightPane`.
  - `20_synthesis.jsx`: `start()`'s POST+poll refactored into a shared `launch(body, msg)` (used by the query
    button AND a new `pendingSummarize`-nonce `useEffect` that runs a `papers` scope with
    `top_k = min(max(8, n), 24)`). A `scopeNote` badge ("Summary of **N selected papers**") shows what's being
    summarized; cleared on a query run or a History reload. `RightPane` forwards `pendingSummarize`.
  - Egress-off / error / History-refresh / citation-open all reuse the existing query-scope machinery (a
    papers-scope job renders identically; History shows the backend-derived "N papers" scope label).

## Key technical detail
The summary scopes over **the selection, not a query**, so there's no query to rank chunks by — hence the
round-robin, which guarantees representation across the chosen papers within a bounded token budget
(`top_k ≤ 24`, each selected paper gets ≥1 chunk up to that cap). It's a correctness/coverage fix, not a
quality trade: single-paper and query scopes are unchanged, and there was no prior multi-paper UI behavior to
regress.

## Verification
- **pytest: 226** (+3, `tests/test_summarize_selected.py`): `_round_robin_by_paper` interleaves (and is
  identity for ≤1 paper); a **capturing fake generator** proves a 2-paper papers-scope summary (2 chunks
  each, `top_k=2`) feeds chunks spanning **both** papers. Existing summarize/egress/cache suites stay green.
- **Live E2E** (`.local/summarize_selected_e2e/`, injected fake, egress on): check 2 library papers → click
  **summarize** → the Synthesis pane shows the **"2 selected papers"** scope note + a verified synthesis
  (`summary #1 · verified`), History logs "2 papers", **0 console errors**; screenshot captured.
- Audit: `.claude/security-audits/2026-06-20_summarize-selected.md` — **PASS** (no new endpoint/egress/
  ingestion; reuses the audited summarize path + the egress gate + local verification).

## Backlog
The **selection→summarize wiring is done**; the **critical-review supplement** remains deferred (must clear
the Auditability standard). Also deferred: an optional **focus query** for a multi-paper summary
(query-ranked coverage); coverage beyond the 24-paper cap. Other queued items unchanged.
