# Security Audit — Paper position endpoint (reveal the selected paper in the library, inc 319)

**Date:** 2026-07-21
**Increment:** 319
**Trigger:** audit gate #1 (a new API endpoint, `GET /papers/{paper_id}/position`) + #5 (spans backend + frontend,
~6 files).

## Change under review
Two prior small fixes this session (the selected-paper cue on every workspace tab; keeping the library's
`selected` state in sync with whichever PDF tab is focused) exposed a gap: `selected` changing no longer
guarantees the paper is visible in the library list. This adds a new read-only endpoint,
`GET /papers/{paper_id}/position`, returning `{"index": <0-based rank>}` of a paper within the exact
filtered+sorted set `GET /papers` would return for the same params, or 404 if it doesn't match. The frontend
uses this to jump the library to the right page and scroll/flash the card into view — but only when the paper
matches the currently active filter; a 404 is a silent no-op, never license to clear/relax the filter.

Backend refactor: `list_papers`'s where-clause chain (q/axis/tag/item_type/needs_review/signal/finding/
read_status/priority/missing_pdf) was extracted into a shared `_paper_filter_clauses` helper in
`paper_query_repo.py`, reused by both `list_papers` and the new `get_paper_rank` (a `ROW_NUMBER() OVER (...)`
window query) — so the list view and the position lookup can never answer "does this paper match" differently.
The whole listing/filter/sort/rank cluster moved from `repository.py` (which was back at the 597/600 cap) into
the existing `paper_query_repo.py` sibling module; both `list_papers` and the new `get_paper_rank`, plus
`PRIORITY_LEVELS`, are re-exported from `repository.py` unchanged (zero call-site impact, the established inc-
220/262/264 pattern). `papers_index`'s 13 inline `Query(...)` params were extracted into a `PaperFilterParams`
FastAPI dependency class, shared by the new endpoint — `GET /papers`'s wire contract is byte-identical.

## Threat review
- **No new external calls, no egress.** The endpoint reads only the local SQLite DB via the existing
  `get_connection` dependency. It cannot reach a Gemini/genai host and doesn't touch invariant #3's gate at all.
- **Parameterized SQL only (rule #3).** `get_paper_rank`/`_paper_filter_clauses` reuse the exact same SQLAlchemy
  Core bound-param query-building `list_papers` already used (verbatim, moved not rewritten) — no new string
  interpolation. `sort`/`signal`/`finding`/`priority`/`read_status` are matched against the same fixed allowlists
  as today (`_paper_sort_order`, `SIGNAL_FILTERS`, `FINDING_FILTERS`, `PRIORITY_LEVELS`); unknown values are
  ignored/fall back exactly as `GET /papers` already does.
- **Path parameter.** `paper_id` is FastAPI-typed `int` — a non-integer path segment 422s before reaching any
  query logic; no injection surface.
- **Information disclosure.** The 404 response reveals only "this id doesn't match these filters" — no more than
  `GET /papers/{paper_id}` already discloses for a nonexistent/trashed id today. The rank query selects only
  `id` + a computed row number (no title/abstract/csl_json leak beyond what the caller's own filter params
  already scope them to see via `GET /papers`).
- **Resource caps.** No new unbounded query — the window function runs over the same filtered/deleted-scoped
  row set `list_papers` already scans; no pagination bypass (the endpoint returns one integer, never rows).
- **No new file I/O, no new third-party dependency, no secrets.**
- **Principles gate (rule #9, already run in the plan).** The endpoint only narrates an existing, already-
  visible fact (which page a paper the user selected sits on, under a filter the user chose) — no claim, score,
  or provenance change. The one real risk — clearing/relaxing the user's filter to force a reveal — is the
  misaligned path explicitly declined; the frontend treats 404 as "skip," never as license to touch the filter.

## Negative-path checks (run)
- `GET /papers/{id}/position` for a paper excluded by an active filter (axis_id not containing it) → **404**,
  and the frontend issues no follow-up write/page-clear (`test_paper_position_404_when_excluded_by_filter`).
- A trashed paper with the default (`deleted` unset) scope → **404**; the same id with `deleted=true` → matches
  correctly (same test).
- A non-existent paper id → **404**, not a crash (`test_paper_position_unknown_paper_404`).
- Index parity: the position returned for a given id under a given `sort` always equals that id's index in a
  `GET /papers` call with identical params, for both the default sort and a reordering sort
  (`test_paper_position_matches_list_order`).
- Full suite (`pytest -n auto -q`) green after the `repository.py` → `paper_query_repo.py` extraction, confirming
  no existing caller (`papers.py`, 4 test modules importing `list_papers`/`PRIORITY_LEVELS` from `repository`)
  broke from the re-export.

## Verdict
**Security Audit: PASS.** Read-only, local-only, no egress; reuses the existing bound-param filter/sort
allowlists verbatim (extracted, not rewritten); 404 discloses nothing beyond what `GET /papers/{paper_id}`
already does; no new dependency, file path, or secret. Full suite green (see `INCREMENT-319-NOTES.md`).
