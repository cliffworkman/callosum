# Increment 319 — scroll-to-reveal the selected paper in the library list

## Context
Two small same-session fixes preceded this one (uncommitted alongside it): the selected/open-paper cue now
renders on every workspace tab, and a single `activeTab`-keyed effect in `40_app.jsx` keeps the library's
`selected` paper in sync with whichever PDF tab is focused, however it was opened. That second fix exposed a
gap: `selected` changing no longer guarantees the paper is *visible* — if it's on another page, or the list is
showing a filtered/search view, nothing scrolls to reveal it.

The requirement, refined with the user over several rounds to its precise final form: whenever `selected`
changes, the library should auto-locate and scroll to that paper — but only within whatever filter is currently
active, and never by clearing or overriding it. If the paper matches the active filter (at any page within it),
jump to its page and scroll/flash it into view. If it doesn't match at all, skip the reveal entirely.

This needed "what page would paper X be on under these exact filters+sort" — a capability `GET /papers` cannot
answer (no rank/window function) — so a new backend endpoint was required, graduating this from a quick fix to
a planned, multi-file change.

**Principles gate (rule #9):** this feature only narrates an existing, already-visible fact (which page a paper
the user already selected sits on, under a filter the user already chose) — no claim, score, or provenance
change, no egress-posture change. The one real misalignment risk — clearing/relaxing the user's filter to force
a jump — was explicitly declined; a non-match is a silent no-op, never a filter override.

## Implemented
1. **New endpoint: `GET /papers/{paper_id}/position`** (`app/backend/api/routers/papers.py`) — accepts the same
   filter+sort query parameters as `GET /papers` (everything but `limit`/`offset`). Returns `{"index": <0-based
   rank>}` if the paper matches, or **404** if it doesn't (deleted/trashed mismatch, or excluded by any filter).
   `papers_index`'s 13 inline `Query(...)` params were extracted into a `PaperFilterParams` FastAPI dependency
   class, shared by both endpoints — `GET /papers`'s wire contract is unchanged (FastAPI flattens `Depends()`
   sub-params into the same query string).
2. **Backend rank logic** (`app/backend/persistence/paper_query_repo.py`): `list_papers`'s where-clause chain
   was extracted into `_paper_filter_clauses` (deleted-scope + q/axis/tag/item_type/needs_review/signal/finding/
   read_status/priority/missing_pdf), reused by both `list_papers` (adds order_by+limit/offset) and the new
   `get_paper_rank` (adds a `ROW_NUMBER() OVER (...)` window, selecting only `id`+rank — cheaper than the display
   list's attachment/chunk/cited-by/retraction subqueries). Sharing one helper means the list view and the
   position lookup can never answer "does this paper match" differently.
3. **Line-budget move (rule #1):** the whole listing/filter/sort/rank cluster (`list_papers`,
   `_paper_filter_clauses`, `_paper_sort_order`, `_search_clause`, the cited-by/retraction subqueries,
   `SIGNAL_FILTERS`/`FINDING_FILTERS`/`SEARCH_FIELDS`/`NEEDS_REVIEW_SOURCES`/`DEFAULT_AXIS_CUTOFF`,
   `PRIORITY_LEVELS`, and the new `get_paper_rank`) moved from `repository.py` (back at 597/600) into the
   existing sibling `paper_query_repo.py` (already home to `get_papers_for_export`/`list_item_types`/
   `titles_for_ids`) — `repository.py` dropped to **338 lines**; `paper_query_repo.py` is now **402**.
   `list_papers`/`PRIORITY_LEVELS`/`get_paper_rank` are re-exported from `repository.py` unchanged (the
   established inc-220/262/264 pattern) — zero call-site impact for `papers.py` or the 4 test modules that
   import them from `repository`.
4. **`app/frontend/js/03_library.jsx`:** the fetch effect's qs-building was consolidated into one
   `buildFilterQs()` (`useCallback`), used both by the main fetch and a new reveal effect keyed **only** on
   `[selected]` (a filter changing alone must never trigger a jump — only `selected` changing does; the effect
   body is a fresh closure each render, so it still reads live filter values whenever it fires). The effect
   skips entirely if the paper is already on the loaded page, or if a **local-only** filter (Text-Health/
   Reference-warnings) is active — a deliberate v1 scope limit (see below) — otherwise calls the new endpoint
   and jumps `page` on a match, doing nothing on a 404.
5. **`app/frontend/js/10d_papercard.jsx`:** the scroll+flash lives on `PaperCard` itself, not centrally in
   `10_pdf_layer.jsx` (which sits at 589/600 — too tight for a new effect). A `cardRef` + an `isSelected`-keyed
   effect (`scrollIntoView({block:"nearest"})` + a `.flash` class toggled via `setTimeout`) fires whether the
   card was already on-screen (its `isSelected` flips true) or mounts fresh already selected (after the reveal
   effect jumps the page) — one mechanism covers both. A `data-paper-id` attribute was added as a QA/debugging
   hook (mirrors the `data-row` precedent in `30d_discover.jsx`).
6. **CSS** (`app/frontend/styles.css`): `@keyframes cardflash` + `.paper.flash`, using `--accent-soft` (the
   neutral/provenance flavor, not the amber `--flag` `.statcheck-item.flash` uses — this isn't a warning),
   mirroring the existing `helpflash`/`.help-section.flash` recipe.

## v1 scope decision (flagged for visibility, not silently decided)
The two local-only client-computed filters — Text-Health and Reference-warnings — are excluded from the
cross-page jump. They're rare, modal-triggered secondary views computed by walking all pages and intersecting
with a client-side `paperIds` set, not a backend filter; replicating "find this paper's index within that walk"
is real added complexity for a rarely-hit combination. If the selected paper isn't on the *current* page while
one of these is active, the reveal is skipped — consistent with "filter active + paper not part of the current
view → skip." Easy to extend later if it turns out to matter in practice.

## Key technical detail
The rank query is a single `ROW_NUMBER() OVER (ORDER BY ...)` window function over the exact same filtered
subquery `list_papers` builds, reusing `_paper_sort_order` verbatim — so a rank under `sort=recent` and a rank
under the default `sort=added` are answered by the identical filter-composition code path, just a different
`ORDER BY`. This is what makes the "does it match / what's its rank" question correctness-guaranteed to agree
with what `GET /papers` itself would show, rather than a parallel reimplementation that could drift.

## Manual verification
1. `pytest tests/test_papers.py tests/test_frontend_assembly.py -q` → all green, including three new backend
   tests (`test_paper_position_matches_list_order`, `test_paper_position_404_when_excluded_by_filter`,
   `test_paper_position_unknown_paper_404`) and two new frontend assembly tests
   (`test_library_reveals_selected_paper_via_position_endpoint`, `test_paper_card_scrolls_and_flashes_when_selected`).
2. Also ran the 4 test modules that import `list_papers`/`PRIORITY_LEVELS` directly from `repository`
   (`test_tags.py`, `test_statcheck.py`, `test_citation_counts.py`, `test_findings_review.py`) plus
   `test_library_merge.py` — all green, confirming the re-export left every existing call site unaffected.
3. `python tools/build_frontend.py` + `python tools/check_line_budget.py` — clean; every touched file (`papers.py`
   525, `paper_models.py` 171, `repository.py` 338, `paper_query_repo.py` 402, `03_library.jsx` 517,
   `10d_papercard.jsx` 126) sits comfortably under the 600-line cap.
4. `python tools/qa/build_surface_map.py check` → API 251/251 covered (0 uncovered — the new endpoint is claimed
   by the extended `route_40_papers_crud_trash.md`); FE unchanged pre-existing 15-surface `35a_mypubs.jsx` gap.

## Pytest
Full suite: see the session's closing test run for the final count (targeted runs before it: 149/149 passed
across `test_papers.py`+`test_frontend_assembly.py`+the four `list_papers`-importing test modules
+`test_library_merge.py`).

## Gates
- **QA (#10):** `route_40_papers_crud_trash.md` extended — `api:` header gained
  `GET /papers/{paper_id}/position`, `fe:` gained `10d_papercard.jsx`/`03_library.jsx`, a new Step 10 and a new
  Pass criterion covering the match/jump and no-match/no-op paths.
- **Security audit (new endpoint, gate #1):** `.claude/security-audits/2026-07-21_paper-position.md` — PASS.
  Read-only, no egress, bound-param filters reused verbatim from the existing allowlists, 404 discloses nothing
  beyond what `GET /papers/{paper_id}` already does.
- **Principles/A-A (rule #9):** named explicitly above — the design never clears/relaxes the user's filter to
  force a reveal; a non-match is silent, matching the user's explicit requirement.
- **DESIGN.md:** the flash keyframe mirrors an existing recipe (`helpflash`) with the correct semantic color
  (`--accent-soft`, neutral — not a warning); no new token or recipe introduced.

## Next
None outstanding from this slice. Tasks (a) (selected-paper cue everywhere) and (b) (selection/focus sync) from
earlier this session, plus this one, are ready to commit together.
