# Bug (diagnosed, queued) — "papers" scope synthesis degenerates to front-matter, not a narrative

**Date:** 2026-06-25 · **Status:** root cause found (systematic-debugging Phase 1–3 complete); fix QUEUED by user
(do statcheck→METHODS first). **Reporter framing:** "synthesis doesn't actually provide syntheses — no text-based
summaries, just relevant sections from papers; it should provide a summary too."

## Evidence (from `.local/validation-summarize/validation.sqlite`, both real `gemini-summary-generator` runs)

- **Summary #1** — scope **query** ("judgments of anomalous faces") → a **real narrative**: "Hypothesis 1.
  Anomalous faces are subject to an 'anomalous-is-bad' stereotype… We found that people with facial anomalies are
  associated with negative characteristics…". ✅ Works.
- **Summary #7** — scope **papers** ("3 papers", the inc-62 select-papers→summarize path, no query) → both its
  `summaries.content` AND its `summary_sentences.text` are **PDF front-matter fragments**: "Original Manuscript",
  the paper title, "Social Psychological and Personality Science 1-10 © The Author(s) 2021 … DOI…", "r Human Brain
  Mapping 38:3391–3401", author lists. ❌ The reported symptom.

The frontend (`SynthesisPane` → `summary_sentences.text`) faithfully renders what was generated — so this is NOT a
render bug; the *generated content itself* is fragments.

## Root cause

The **no-query "papers" scope** feeds the LLM the papers' **front-matter / non-content chunks** (first chunks =
titles, manuscript headers, journal mastheads, author lists, DOIs, reference-list lines) and, with **no focusing
question** to synthesize toward, the model returns those fragments as "sentences." Query-scoped synthesis works
because the query drives retrieval to substantive content. Contributing files: `summarization/pipeline.py`
(`_source_chunks_for_scope` + `_round_robin_by_paper`, the inc-62 multi-paper no-query path) and the retrieval/
chunk selection feeding it. (Known rough edge: inc-112 "LLM/UX needs eyes-on review"; TDL #7.)

## Fix direction (when picked up — design-led; needs egress to verify final LLM output)

1. **Exclude front-matter / non-content chunks from synthesis retrieval** — deterministic + testable WITHOUT egress
   (assert which chunks are selected): skip title/header/masthead/DOI/reference-list chunks (heuristics: page-1
   header blocks, very short chunks, reference-list patterns, masthead/DOI regexes). This improves *all* scopes.
2. **Give the no-query papers scope something real to synthesize** — prefer body chunks; consider an implicit
   "summarize the key findings/claims of these papers" instruction so the model narrates rather than extracts.
3. Verify: a papers-scope synthesis over real papers yields a narrative (needs egress + a Gemini key), AND a
   deterministic test that front-matter chunks are filtered from the candidate set.

Likely its own brainstorm→spec→plan (overlaps inc-62/112 + TDL #7). **Also surfaced:** the user was unsure of
their egress/key state → the BYOK-in-Settings track (TDL #40) would make "can I even generate?" self-evident.
