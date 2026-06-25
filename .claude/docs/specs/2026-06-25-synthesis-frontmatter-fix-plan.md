# Synthesis front-matter fix (inc 123, Part A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the no-query papers-scope synthesis from feeding the LLM front-matter chunks (titles, mastheads,
DOIs, author/affiliation lines), so the verified claims are real body text.

**Architecture:** A small pure classifier `is_front_matter_chunk(text)` partitions each paper's chunks; the
no-query path in `_source_chunks_for_scope` round-robins **content chunks first across papers**, then front-matter
chunks only as fallback, before the `top_k` slice. Deterministic, backend-only, no egress, no migration.

**Tech Stack:** Python (stdlib `re`), SQLAlchemy Core, pytest.

## Global Constraints

- **Part A of the inc-123/124 design** (`.claude/docs/specs/2026-06-25-synthesis-overview-design.md`). Part B
  (the Overview) is inc 124 — **not in this plan**.
- **Backend-only.** No frontend, no `/summarize` request/response contract change, no new endpoint, no migration,
  no egress, no new dependency. → **no rule-#10 QA-route change** (no new end-user surface; route_55 already
  covers `/summarize`), **no audit-gate trigger** (no new endpoint/fetch/ingestion, <300 LOC), **Principles gate
  non-triggering** (a retrieval-quality change like inc-66 trashed-exclusion; no new claim/signal; inspectability,
  provenance, and egress posture all unchanged — every verified claim still carries its quote/page/confidence).
- **Conservative classifier:** err toward "content." A false "content" just isn't deprioritized; a false
  "front-matter" only *deprioritizes* (never drops — front matter is fallback, so a paper with only front matter
  still contributes). Titles are deliberately NOT caught (avoids false positives on topical prose) — documented
  limitation; the masthead/DOI/author-line garbage from summary #7 is what gets caught.
- **600-line cap (rule #1):** `pipeline.py` is ~334 lines; the classifier lives in its own module to keep it lean.
- This is **increment 123**. Commit after each task; push only at session end on the user's OK.

---

### Task 1: front-matter classifier (`is_front_matter_chunk`)

**Files:**
- Create: `app/backend/summarization/chunk_filtering.py`
- Test: `tests/test_chunk_filtering.py`

**Interfaces:**
- Produces: `is_front_matter_chunk(text: str) -> bool` (pure; no DB/IO).

- [ ] **Step 1: Write the failing test** (`tests/test_chunk_filtering.py`):

```python
from __future__ import annotations

from app.backend.summarization.chunk_filtering import is_front_matter_chunk

# The masthead/front-matter strings are the actual degenerate "sentences" from validation summary #7
# (papers scope) — see .claude/docs/specs/2026-06-25-synthesis-overview-design.md §0.
FRONT_MATTER = [
    "Original Manuscript",
    "Social Psychological and Personality Science 1-10 © The Author(s) 2021 Article reuse guidelines: "
    "sagepub.com/journals-permissions DOI: 10.1177/19485506211031722 journals.sagepub.com/home/spp",
    "r Human Brain Mapping 38:3391–3401 (2017) r",
    "Frederick S. Barrett ,1* Clifford I. Workman,1 Haris I. Sair,2",
    "Journal of Affective Disorders Reports 10 (2022) 100380 Contents lists available at ScienceDirect",
    "",
    "   ",
]

CONTENT = [
    "We found that people with facial anomalies are associated with negative characteristics.",
    "Paper A chunk 1 discusses cortex.",
    "Paper B chunk 1 discusses cortex.",
    "Anomalous faces were rated more negatively in terms of warmth and competence than typical faces.",
    "Participants completed a trust game in which they allocated money to partners shown as faces.",
]


def test_front_matter_strings_are_flagged() -> None:
    for s in FRONT_MATTER:
        assert is_front_matter_chunk(s) is True, f"expected front-matter: {s!r}"


def test_body_sentences_are_content() -> None:
    for s in CONTENT:
        assert is_front_matter_chunk(s) is False, f"expected content: {s!r}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_chunk_filtering.py -q`
Expected: FAIL — `ModuleNotFoundError: app.backend.summarization.chunk_filtering`.

- [ ] **Step 3: Implement the classifier** (`app/backend/summarization/chunk_filtering.py`):

```python
"""Classify a chunk as paper front-matter / non-content (title-page mastheads, DOIs, journal headers,
author/affiliation lines) vs body content, so synthesis retrieval can prefer real content over a title page.

Conservative by design: it errs toward "content". A false "content" just isn't deprioritized; a false
"front-matter" only deprioritizes a chunk (front matter is used as fallback, never dropped — see
summarization/pipeline.py::_select_no_query), so a paper with only front matter still contributes. Titles are
deliberately NOT caught (they read like topical prose; catching them risks dropping real content) — only the
masthead/DOI/journal-header/author-line garbage is flagged.
"""

from __future__ import annotations

import re

_DOI = re.compile(r"\b10\.\d{4,9}/\S+", re.IGNORECASE)
# A journal volume:page run like "38:3391-3401" (hyphen or en/em dash).
_VOLUME = re.compile(r"\b\d{1,4}\s?[:;]\s?\d+\s?[-–—]\s?\d+")
# Author/affiliation superscripts: ",1*", ",2" — repeated across an author list.
_AFFIL_SUPERSCRIPT = re.compile(r",\s?\d\*?")
# Publisher / copyright / access boilerplate (substring match, lowercased).
_PUBLISHER_BOILER = (
    "article reuse guidelines", "sagepub", "journals.", "doi.org", "downloaded from",
    "contents lists available", "sciencedirect", "the author(s)", "©", "(c) ",
    "rights reserved", "creativecommons",
)
_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "as", "is",
    "are", "was", "were", "be", "been", "that", "this", "these", "those", "it", "its", "from", "we", "our",
    "they", "their", "than", "which", "into",
}


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text)


def is_front_matter_chunk(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True  # empty/whitespace contributes nothing to a synthesis
    low = t.lower()
    if _DOI.search(t) or any(s in low for s in _PUBLISHER_BOILER):
        return True  # DOI / publisher / copyright / access boilerplate
    if len(_AFFIL_SUPERSCRIPT.findall(t)) >= 2:
        return True  # an author/affiliation line ("Barrett ,1* Workman,1 Sair,2")
    words = _word_tokens(t)
    n = len(words)
    if n < 12:  # short lines only — long prose is left as content
        if _VOLUME.search(t):
            return True  # "r Human Brain Mapping 38:3391-3401 (2017) r"
        # A title/masthead line has almost no function words AND no sentence-ending punctuation; a real short
        # sentence ("Paper B chunk 1 discusses cortex.") ends in . ? ! and is kept.
        if t[-1] not in ".?!" and n > 0:
            stop = sum(1 for w in words if w.lower() in _STOPWORDS)
            if stop / n < 0.10:
                return True
    return False
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_chunk_filtering.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/backend/summarization/chunk_filtering.py tests/test_chunk_filtering.py
git commit -m "feat(synthesis): front-matter chunk classifier (inc 123 t1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: prefer content chunks in the no-query papers scope

**Files:**
- Modify: `app/backend/summarization/pipeline.py` (import the classifier; add `_select_no_query`; change the
  no-query return at `_source_chunks_for_scope`)
- Test: `tests/test_summarize_selected.py` (add a front-matter-then-content integration test)

**Interfaces:**
- Consumes: `is_front_matter_chunk` (Task 1); the existing `_round_robin_by_paper(rows) -> list[SourceChunk]`.
- Produces: `_select_no_query(rows: list[SourceChunk], top_k: int) -> list[SourceChunk]`.

- [ ] **Step 1: Write the failing integration test** — append to `tests/test_summarize_selected.py`:

```python
def _seed_two_papers_frontmatter_then_content(db_url: str) -> dict[str, int]:
    """Each paper's FIRST chunk (lowest id) is front matter, its SECOND is body content. A naive selection that
    takes the first chunk of each paper (the old _round_robin_by_paper[:top_k]) would feed the LLM mastheads;
    the fix must prefer the content chunks."""
    engine = make_engine(db_url)
    fm = {
        "a": "Original Manuscript",
        "b": "Social Psychological and Personality Science 1-10 © The Author(s) 2021 "
        "DOI: 10.1177/19485506211031722",
    }
    body = {
        "a": "Anomalous faces were rated more negatively in warmth and competence than typical faces.",
        "b": "Participants allocated more money to partners whose faces appeared more typical.",
    }
    out: dict[str, int] = {}
    with engine.begin() as conn:
        for key in ("a", "b"):
            paper_id = create_paper(
                conn,
                title=f"Paper {key.upper()}",
                processing_tier="fully-chunked",
                csl_json={"type": "article-journal", "title": f"Paper {key.upper()}"},
            )
            attachment_id = create_attachment(
                conn,
                paper_id=paper_id,
                storage_mode="linked",
                availability="available",
                content_type="application/pdf",
                checksum=f"chk-{key}",
                import_source="test",
                attachment_type="pdf",
                role="primary",
            )
            out[f"p{key}"] = paper_id
            for n, text in ((1, fm[key]), (2, body[key])):
                chunk_id = create_chunk(
                    conn,
                    paper_id=paper_id,
                    attachment_id=attachment_id,
                    text=text,
                    page_start=n,
                    page_end=n,
                    bbox_coordinate_system="pdf-points-top-left",
                    extraction_tool="fixture",
                    extraction_version="1",
                    chunking_strategy="paragraph",
                    chunk_version=f"{key}{n}",
                    source_attachment_checksum=f"chk-{key}",
                    bbox_json=[{"page": n, "x0": 1, "y0": 2, "x1": 3, "y1": 4}],
                )
                out[f"{key}{n}"] = chunk_id
    engine.dispose()
    return out


def test_no_query_papers_scope_prefers_content_over_front_matter(temp_db_url: str) -> None:
    seed = _seed_two_papers_frontmatter_then_content(temp_db_url)
    gen = CapturingSummaryGenerator(
        [
            CandidateSummarySentence(
                text="Typicality shapes social judgments.",
                citations=[CandidateCitation(chunk_id=seed["a2"], quote="")],
            )
        ]
    )
    client = TestClient(_summarization_app(temp_db_url, generator=gen))

    started = client.post(
        "/summarize", json={"scope_type": "papers", "paper_ids": [seed["pa"], seed["pb"]], "top_k": 2}
    )
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["status"] == "done"
    assert gen.captured is not None
    captured_ids = {c.chunk_id for c in gen.captured}
    assert captured_ids == {seed["a2"], seed["b2"]}  # the two CONTENT chunks, not the front-matter first-chunks
    assert seed["a1"] not in captured_ids and seed["b1"] not in captured_ids
    assert {c.paper_id for c in gen.captured} == {seed["pa"], seed["pb"]}  # still spans both papers
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_summarize_selected.py::test_no_query_papers_scope_prefers_content_over_front_matter -q`
Expected: FAIL — `captured_ids` is `{a1, b1}` (the front-matter first-chunks) under the current
`_round_robin_by_paper(rows)[:top_k]`.

- [ ] **Step 3: Implement `_select_no_query` and use it.** In `app/backend/summarization/pipeline.py`, add the
  import near the other summarization imports (after the `generators` import, line ~22):

```python
from app.backend.summarization.chunk_filtering import is_front_matter_chunk
```

  Replace the no-query return in `_source_chunks_for_scope` (currently the last lines of that function):

```python
    # No query → prefer real body content over title-page/masthead chunks, then spread the budget across the
    # selected papers so a multi-paper summary covers them all (rows are chunk-id-ordered = import order, so the
    # first chunk of each paper is its front matter). Single paper → still drops its own masthead first.
    return _select_no_query(rows, top_k)
```

  And add the helper just above `_round_robin_by_paper`:

```python
def _select_no_query(rows: list[SourceChunk], top_k: int) -> list[SourceChunk]:
    """Round-robin content chunks across papers first, then front-matter chunks as fallback, then slice top_k.
    Front matter (titles/mastheads/DOIs/author lines) is never dropped outright — a paper with only front matter
    still contributes once content is exhausted."""
    content = [chunk for chunk in rows if not is_front_matter_chunk(chunk.text)]
    front = [chunk for chunk in rows if is_front_matter_chunk(chunk.text)]
    ordered = list(_round_robin_by_paper(content)) + list(_round_robin_by_paper(front))
    return ordered[:top_k]
```

- [ ] **Step 4: Run the new test + the existing pipeline-selection tests**

Run: `python -m pytest tests/test_summarize_selected.py -q`
Expected: PASS (all 5 — the new test plus `test_round_robin_interleaves_papers`,
`test_round_robin_single_paper_is_identity`, `test_multi_paper_summary_covers_all_selected_papers`
[its body text isn't front matter, so selection is unchanged], `test_focus_query_ranks_within_the_selection_only`
[query scope, untouched]).

- [ ] **Step 5: Commit**

```bash
git add app/backend/summarization/pipeline.py tests/test_summarize_selected.py
git commit -m "fix(synthesis): no-query papers scope prefers content over front matter (inc 123 t2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: verify + docs

**Files:**
- Modify: `.claude/changes.md`, `RECOVERY-LOG.md`, `.claude/CLAUDE.md` (footer + increment number)
- Create: `.claude/docs/increment-notes/INCREMENT-123-NOTES.md`

- [ ] **Step 1: Full suite + lint.**

Run: `ruff check . && ruff format --check . && python -m pytest -q`
Expected: ruff clean; pytest PASS (record the count — should be **439**: 437 + the 2 new test functions, minus
none; confirm the exact number from the run).

- [ ] **Step 2: Confirm no QA-surface regression** (backend-only, no new surface → expect green, no route edit).

Run: `python tools/qa/build_surface_map.py extract && python tools/qa/build_surface_map.py check`
Expected: `check` exits 0 — API surfaces unchanged (no new endpoint), 0 uncovered.

- [ ] **Step 3: Increment notes** — create `.claude/docs/increment-notes/INCREMENT-123-NOTES.md`:
  **Implemented** (`chunk_filtering.is_front_matter_chunk` + `_select_no_query`; the no-query papers/single-paper
  scope now prefers content over front matter), **Key technical detail** (conservative classifier — DOI/publisher/
  ©/affiliation/journal-volume/short-no-stopword-no-terminal-punct; two-phase round-robin content-then-front-matter
  so front matter is fallback-only, never dropped; titles intentionally not caught; query/cluster scopes
  untouched; Principles non-triggering — retrieval-quality, like inc-66), **Manual verification** (the
  `test_no_query_papers_scope_prefers_content_over_front_matter` assertion; optionally re-run a real papers-scope
  synthesis with egress on and confirm the claims are body text — needs a key), **Pytest** (the count from Step 1).

- [ ] **Step 4: `changes.md`** — add a top entry (no `HELP-DOCS-SYNCED` move; Part A is invisible to the help
  corpus):

```markdown
## 2026-06-25 — Increment 123: synthesis no-query scope prefers content over front matter (Part A)
- **Files:** NEW `app/backend/summarization/chunk_filtering.py`; `app/backend/summarization/pipeline.py`,
  `tests/{test_chunk_filtering,test_summarize_selected}.py`, `INCREMENT-123-NOTES.md`.
- **What:** A conservative `is_front_matter_chunk` classifier + a two-phase `_select_no_query` so the no-query
  papers (and single-paper) synthesis scope feeds real body content, not title-page mastheads/DOIs/author lines.
- **Why:** Root cause #1 of "synthesis gives no real summary, just front matter" (validation summary #7) — the
  old `_round_robin_by_paper(rows)[:top_k]` fed the first chunk of each paper (its masthead). Part A of the
  inc-123/124 synthesis-overview design.
- **Revert:** restore the `_round_robin_by_paper(rows)[:top_k]` return in `_source_chunks_for_scope`.
```

- [ ] **Step 5: RECOVERY-LOG.md** — append one line (chronological; use the real timestamp from
  `date +"%Y-%m-%dT%H:%M:%S%z"`):
  `[<ts>] increment 123 (synthesis front-matter fix, Part A) — commits <t1>/<t2>/+docs — is_front_matter_chunk classifier + two-phase _select_no_query: no-query papers/single-paper synthesis scope prefers body content over title-page mastheads/DOIs/author lines (root cause #1 of the no-text-summary report). Backend-only, no egress/migration/API change; Principles non-triggering (retrieval quality, cf. inc-66). pytest <N>; ruff clean. NEXT: inc 124 Part B (evidence-traceable Overview).`

- [ ] **Step 6: CLAUDE.md** — bump "currently at **Increment 123**" (line ~24) and add an inc-123 footer block
  at the top of the footer narrative (demote inc 122 to "Earlier — increment 122"), concise, matching the recent
  footer style; note Part A done, Part B (inc 124) next.

- [ ] **Step 7: Commit**

```bash
git add .claude/changes.md RECOVERY-LOG.md .claude/CLAUDE.md \
  .claude/docs/increment-notes/INCREMENT-123-NOTES.md
git commit -m "docs(synthesis): inc 123 notes/changes/RECOVERY-LOG/CLAUDE (Part A)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage** (against design §2 Part A): classifier → Task 1; content-first two-phase selection in
`_source_chunks_for_scope` → Task 2; no-egress/no-migration/no-frontend, query path untouched → honored
throughout; verification (unit + integration, no UI) → Tasks 1–3. Part B (§3) is explicitly out of scope (inc
124). ✔

**Placeholder scan:** all code shown in full; commands have expected output; the only deferred value is the
pytest count (resolved at run time in Task 3) and the RECOVERY-LOG timestamp/commit-hashes (resolved at execution
— a log line, not code). ✔

**Type/name consistency:** `is_front_matter_chunk(text:str)->bool` defined Task 1, consumed Task 2;
`_select_no_query(rows, top_k)` defined + used Task 2; `_round_robin_by_paper` reused unchanged; test helper
`CapturingSummaryGenerator` reused from the existing file. ✔
