# Increment 583 — Exclude reference lists from Ask evidence by default (backlog #82 / GitHub issue #35)

## Context

Reference lists are the single biggest section a query-scope synthesis can retrieve (measured inc 575:
5,635 of 23,875 chunks, ~24%), and a bibliography entry is keyword-dense across many topics, so a
multi-construct question finds them irresistible — a real four-construct query pulled 4 of 8 chunks
from `section='references'`. A reference-list entry is a pointer *to* a finding, not a finding, so it
can never be the verbatim evidence for a scientific claim; excluding it from the claim-evidence pool
is principled, not merely a quality heuristic.

**The backlog framed this as a cheap default flip; it wasn't.** The existing `sections` filter is an
*allow-list* (`chunks.section.in_(...)`) that (a) would drop the ~4,282 `None`-labelled chunks and
(b) **gates off inc 581/582's faceted broad-Ask** (`summaries.py` routes to faceting only when
`not request.sections`). So references exclusion had to be a *separate deny-mechanism*. It also had to
cover **two** candidate-pool builders — `_source_chunks_for_scope` (single-query) and
`_load_article_pool` (faceted). Cliff chose **exclude-by-default (toggleable), both paths,
GROBID-preferred** over the more conservative "deprioritize" (inc 581 already deprioritizes
`bibliographic` chunks via inc 577's `evidence_role`; this coarser, more reliable *section*-level
signal is a peer, not a contradiction — and it's reversible).

## Implemented

- **`summarization/pipeline.py`** — new shared `exclude_reference_sections(stmt)` helper: outer-joins
  `paper_sections` on `chunks.grobid_section_id` and keeps a row unless
  `COALESCE(paper_sections.section_kind, chunks.section) == 'references'` — GROBID-preferred over the
  heuristic (the same strict preference `candidate_section_family` uses), and **`NULL`/unlabelled
  chunks are kept** (`or_(family.is_(None), family != 'references')`). New `SummaryScope.exclude_references:
  bool = True`; `to_ref()` records it **only when False** (default rows unchanged; a references-included
  run is inspectable in its own provenance). `_source_chunks_for_scope` applies the exclusion when
  `scope_type == "query" and exclude_references and not sections`, and — mirroring the inc-577
  boilerplate discipline — computes boilerplate-detection keys from the **un-narrowed** whole-paper pool
  whenever any narrowing (section allow-list OR references exclusion) is applied.
- **`summarization/faceted_pipeline.py`** — `_load_article_pool(conn, *, exclude_references=True)` and
  `summarize_faceted(..., exclude_references=True)` thread the flag; the persisted
  `SummaryScope(scope_type="query", ...)` records it.
- **`api/routers/summaries.py`** — `SummarizeRequest.exclude_references: bool = True`, threaded to the
  scope and to `summarize_faceted`.
- **`frontend/js/20_synthesis.jsx`** — an **Include reference lists** checkbox under the section-filter
  row (default off; sends `exclude_references:false`), disabled when an explicit section allow-list is
  chosen (the allow-list governs then). The idle status line discloses the default at the point of
  action: `… · reference lists excluded` / `· incl. reference lists`.
- **Help corpus** + **QA route 55** (standing assertion + a step) + tests.

## Key technical detail

`chunks.section` (heuristic `SectionTracker`) and `paper_sections.section_kind` (GROBID, via
`classify_section_title` → `detect_section_heading`) both spell a reference-list section `"references"`
(`pdf_processing/sections.py`: `"references": {"bibliography", "references"}`), which is what makes the
single `COALESCE(...) = 'references'` filter correct for both. **The `or_(family.is_(None), …)` guard is
load-bearing**: a plain `family != 'references'` would silently drop every `NULL`-family chunk (SQL
`NULL != 'x'` is `NULL`, not true) — and unlabelled chunks are the largest class and hold real evidence
(silence is not a certificate). GROBID-preferred means a chunk the heuristic mislabelled `references` but
GROBID mapped to `methods` is **kept**, and vice-versa — proven both directions in the tests.

## Manual verification script

- `pytest tests/test_reference_exclusion.py` — 3 pass: references excluded / `None`+methods kept;
  GROBID preferred both directions + NULL-kind fallback; `to_ref` records only a non-default policy.
- `pytest tests/test_summaries.py tests/test_summarization.py tests/test_faceted_synthesis.py
  tests/test_summarize_selected.py` — 52 pass (no regression). `tests/test_frontend_assembly.py` — 87 pass.
- Deterministic SQL check against a real library (no model): `exclude_reference_sections` removes exactly
  the `COALESCE(section_kind, section)='references'` rows and keeps every `NULL`-family row.
  (Could not be run this session — no testing DB present on the machine; the fixture tests cover the
  mechanism, and the vacuous→substantive *output-quality* effect was already measured in inc 575.)
- **Deferred:** a live end-to-end Ask run reproducing the inc-575 vacuous→substantive demo needs the
  ~200-paper testing DB restored; flagged, not claimed done.

## Pytest

`tests/test_reference_exclusion.py` 3 passed; the 4 summarization suites 52 passed; frontend assembly 87
passed. Both ruff gates clean on the changed files. QA API coverage gate green (route 55 already claims
`/summarize*`; extended for the new behavior).
