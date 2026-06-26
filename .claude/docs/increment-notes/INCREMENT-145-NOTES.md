# Increment 145 — Discoverable multi-paper focus query (Skeptical synthesizer ↔ backlog #7)

## Experience pass (rule #11)

**Persona:** the **Skeptical synthesizer** (selects several papers, wants a synthesis *focused on a sub-question*,
and trusts it only as far as each claim's evidence is checkable). A dispatched persona agent drove the
select→summarize flow. **Found:** the trust machinery is strong — every verified claim carries a verbatim quote +
page + Retrieval/Quote/Support confidences + a coordinate-precision badge + an Open-source button, and the
verified-vs-flagged split + the traceable Overview are honest. **The capability they wanted already exists** —
a focus query makes the selection summary *query-ranked* (inc 111) — **but it is invisible at the moment of
action**: the focus lived only in the Synthesis pane's textarea (a different accordion section), and the selection
bar's `summarize` gave no hint, so a user gets the generic no-query path and never discovers the focused one (the
help even *misframed* selection-summarize as "without phrasing a question"). Verdict: *trustworthy, but they'd walk
away thinking it only does generic selection-summaries.* (6th persona run → 6th real gap — a pure discoverability
gap, like the Migrator's progress finding.)

## Implemented

Make the focus query discoverable **where the action is** — a **"Focus on… (optional)"** input in the library
selection bar. Frontend + a help fix:

- **`10_pdf_layer.jsx`:** a `bulkFocus` state + a `.bulk-focus` input in `.axis-bulk-bar`; **summarize** now passes
  it (`onBulkSummarize(bulkFocus)`, Enter also fires).
- **`40_app.jsx`:** `bulkSummarizePapers(focus)` threads it onto `pendingSummarize.focus`.
- **`20_synthesis.jsx`:** the multi-paper effect **prefers `pendingSummarize.focus`** (falls back to the textarea —
  the inc-111 behavior) and **reflects it into the Synthesis textarea** so it's visible; a non-empty focus →
  `body.query = focus` (query-ranked coverage) + the scope-note "… · focused on '…'".
- **Help corpus:** the selection-summarize section now documents the Focus box (it previously said "without phrasing
  a question").

## Key technical detail

This is **discoverability, not a new capability** — the backend papers-scope already honored `query`
(`_rank_chunks_for_query`); inc 145 only surfaces the input at the selection bar and routes it. So the **verification
spine + honesty contract are unchanged** (the focus *ranks* coverage; every claim still carries its quote/page/
confidence and is shown verified or flagged — it never fabricates). **Principles gate: non-triggering** (no new
claim type; an existing, already-principled feature made findable).

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc145_focus.py`): select 2 papers → the **Focus on…** input appears →
type a question → **summarize** → the intercepted `POST /summarize` body is
`{scope_type:"papers", query:"the role of sleep in memory consolidation", paper_ids:[1,2]}`, the scope-note reads
"… · focused on '…'", and the Synthesis textarea reflects the focus. 0 console/page/genai (egress off → the focus is
*passed*; the focused-synthesis quality is the existing inc-111 behavior, not re-tested here).

## Triage of the remaining synthesizer findings (filed to backlog #7)

Shipped: the discoverable focus query + the help fix. **Remaining:** a **coverage readout** ("drew from 6 of 8
selected papers"; name the papers that contributed nothing); an **answerability** note ("your question may not be
addressed in these papers" when no chunk clears retrieval); show the `top_k` cap in the scope-note for all cases.

## Pytest

**524** unchanged (frontend-only + a help edit; the wiring is headed-verified). `ruff` clean; build + assembly green;
surface **106/106 API + 539/539 FE, 0 uncovered**. No new endpoint/migration/egress.

## The build-and-test slate is complete

inc 141 (deadline citer / statcheck) · **142** (migrator / progress) · **143** (librarian / tags) · **144** (close
reader / export) · **145** (skeptical synthesizer / focus) — **6 persona runs, 6 real gaps found and fixed.** The
experience pass (rule #11) and its persona-agent mechanism are validated: every persona surfaced a specific gap a
generic test wouldn't, and several were gaps the backlog items had only *partly* anticipated (the real gap was
discoverability/completeness, not the headline feature). **NEXT: BYOK** (Gemini API key in Settings → full
bring-your-own-key) — user-prioritized to the top of the pile now that the slate is done.
