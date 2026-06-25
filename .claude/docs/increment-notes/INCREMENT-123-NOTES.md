# Increment 123 — synthesis no-query scope prefers content over front matter (Part A)

Part A of the inc-123/124 synthesis-overview design
(`.claude/docs/specs/2026-06-25-synthesis-overview-design.md`). Fixes root cause #1 of the user's report that
"synthesis doesn't provide a real summary, just relevant sections" — the no-query papers scope was feeding the
LLM front-matter chunks (title pages, mastheads, DOIs, author lines), so the verified claims were mastheads
(validation summary #7). Part B (the evidence-traceable Overview) is inc 124.

## Implemented

- **New `app/backend/summarization/chunk_filtering.py`** — `is_front_matter_chunk(text) -> bool`, a pure,
  conservative classifier.
- **`app/backend/summarization/pipeline.py`** — new `_select_no_query(rows, top_k)`; the no-query branch of
  `_source_chunks_for_scope` now returns `_select_no_query(rows, top_k)` instead of
  `_round_robin_by_paper(rows)[:top_k]`. Two-phase: round-robin the **content** chunks across papers first, then
  the **front-matter** chunks as fallback, then slice `top_k`. So every selected chunk is body content when any
  exists; a paper with only front matter still contributes once content is exhausted (never empty).
- **Tests:** `tests/test_chunk_filtering.py` (classifier unit tests over the real summary-#7 mastheads vs body
  sentences) + `tests/test_summarize_selected.py::test_no_query_papers_scope_prefers_content_over_front_matter`
  (a 2-paper fixture whose first chunk is a masthead, second is body → the papers-scope no-query selection
  captures the two content chunks, not the front-matter first-chunks, and still spans both papers).

## Key technical detail

- **Conservative classifier (errs toward "content").** A chunk is front-matter if it has a DOI / publisher /
  ©-access boilerplate; OR ≥2 author-affiliation superscripts (`,1*` `,2`); OR is short (<12 words) with a
  journal volume:page run (`38:3391–3401`); OR is short, ends without sentence punctuation, and has <10% function
  words (title/masthead/author lines like "Original Manuscript"). A real short sentence ("Paper B chunk 1
  discusses cortex.") is kept because it **ends in `.`/`?`/`!`**. **Titles are deliberately not caught** (they
  read like topical prose; catching them risks dropping real content) — only masthead garbage is flagged.
- **Front matter is fallback, never dropped.** `_select_no_query` concatenates `round_robin(content) +
  round_robin(front)`, so a false "front-matter" only deprioritizes a chunk; a paper with only front matter still
  contributes. This keeps the fix safe against classifier imperfection.
- **Query/cluster scopes untouched** — query retrieval already ranks past front matter; applying the classifier
  there would risk dropping a chunk the query actually wanted (YAGNI + safety).
- **Principles gate non-triggering** — a retrieval-quality change (cf. inc-66 trashed-paper exclusion), not a new
  claim/signal; inspectability, provenance, and egress posture are unchanged (every verified claim still carries
  its quote/page/confidence). Backend-only: no `/summarize` contract change, no new endpoint, no migration, no
  egress, no new dependency → no rule-#10 route change (surface check 0 uncovered) and no audit-gate trigger.

## Manual verification

- `pytest tests/test_chunk_filtering.py tests/test_summarize_selected.py` (the classifier + the
  content-over-front-matter selection assertion). No UI verification needed (backend-only; `/summarize` contract
  unchanged).
- Optional eyes-on (needs egress + a Gemini key): re-run a papers-scope synthesis over real papers and confirm
  the verified claims are body text, not "Original Manuscript / © The Author(s) / DOI / author lists."

## Pytest

440 passed, 1 skipped (437 + 3 new test functions: 2 classifier + 1 selection). `ruff` clean; QA surface check
0 uncovered (88 API / 460 FE).
