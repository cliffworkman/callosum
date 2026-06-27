# Increment 153 — Synthesis coverage readout + top_k + answerability (#7)

The remaining autonomous part of backlog #7 (Skeptical-synthesizer follow-ups). Frontend-only.

## Implemented (`app/frontend/js/20_synthesis.jsx`)

- **Coverage readout** for the papers (selection) scope: a new `scopeMeta` state `{total, topK}` captured when a
  papers-scope summarize launches; on `done`, the pane computes `drewFromPapers` = distinct `paper_id` across the
  result's citations and renders *"Drew from **M** of N selected papers · top K chunks"* — plus *"· K contributed
  no cited passage"* when M < N. So the synthesizer sees which of their selected papers actually fed the summary.
- **top_k cap** shown in that line (the papers scope previously only showed the chunk cap when n > 50).
- **Answerability note:** when the synthesis returns claims but **none cleared verification** (`verifiedCount === 0`),
  a `.synth-coverage-warn` line — *"No claim cleared local verification — your question may not be well-addressed in
  these papers."* The 0-sentence empty state's copy was also sharpened to an answerability hint.
- `scopeMeta` is cleared on a query-scope run + on loading a saved synthesis (the original selection size isn't
  recorded), so the readout only shows where N is meaningful.
- CSS: one `.synth-coverage` recipe (+ `.synth-coverage-warn` amber), tokens only (rule #8).

## Key technical detail

Display-only — computed entirely from the existing summary result (`citations[].paper_id`) + `scopeMeta`; it does
**not** change generation or retrieval, so the "eyes on the first live run" caveat (which was about LLM quality)
doesn't apply. **No Principles trigger** (no new claim; it makes coverage honest/inspectable). No new endpoint,
migration, or backend change.

## Manual verification

**Headed, no real egress** (`.local/visual/drive_inc153_coverage.py`): a fake-generator app (no Gemini) seeded with
2 papers, the fake citing only one → select both → summarize → the coverage line reads *"Drew from 1 of 2 selected
papers · top 8 chunks · 1 contributed no cited passage"*; 0 console/page/genai (the injected fake ran, not Gemini).

## Pytest

**556** unchanged (frontend-only; the data path — citations carry `paper_id` — is already covered by
`test_summaries`; the readout is headed-verified). `ruff` clean; build + assembly green; QA surface **109/109 API +
561/561 FE, 0 uncovered**. No migration.
