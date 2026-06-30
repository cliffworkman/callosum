# Increment 223 — "By priority" unset-tier secondary order

## Implemented

A close-out of the inc-220 reading-markers thread (experience-pass finding #4). The **"By priority"** library
sort ranked high→normal→low→unset, but within each tier — most visibly the large **unset** bucket — the only
tiebreak was the global `papers.id ASC` tail, so the whole unset tier collapsed into one undifferentiated
oldest-imported-first block.

Fix (`app/backend/persistence/repository.py:107`): the `"priority"` sort entry gains a recency tiebreak —
`[_PRIORITY_RANK.asc(), papers.c.id.desc()]`. `id DESC` is the same recency proxy `"recent"` (`:92`) already
uses, so within each priority tier the most-recently-added papers come first. The global `papers.id.asc()` tail
appended at `:113` stays as the deterministic pagination tiebreak (redundant-but-harmless after `id.desc()` since
`id` is unique).

## Key technical detail

`papers` has no `created_at` column; `papers.id` is the import-order/recency proxy throughout `_paper_sort_order`
(`"added"` = `id ASC`, `"recent"` = `id DESC`), so `id DESC` is the idiomatic in-file recency expression. The fix
is a single ORDER-BY append — a user-chosen sort order, never an AI rank (the inc-207 declined-ratings posture).

## Manual verification script

Backend-only, fully unit-testable (no headed needed): `GET /papers?sort=priority`. New test
`tests/test_papers.py::test_priority_sort_recency_tiebreak_within_tier` seeds two high + two unset papers with
non-monotonic priority assignment and asserts the order is `[high-new, high-old, unset-new, unset-old]` — tier
order preserved, recency within each tier. The existing `test_paper_priority_marker` (one paper per tier) still
asserts `[hi, lo, un]`.

## Pytest

**786** (+1). ruff check + format clean; QA surface unchanged (161/161 API + 719/719 FE, 0 uncovered — no surface
change). No migration / egress / endpoint / dependency / audit / Principles trigger.
