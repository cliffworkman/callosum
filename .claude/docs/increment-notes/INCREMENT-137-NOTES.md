# Increment 137 — Gap-finder v2: forward gap + axis-scoped + persistent cache

## Implemented

Rounds out the inc-135 backward gap-finder with the user-chosen scope (forward gap + axis-scoped ranking +
a persistent cache):

- **Forward gap** (`clustering/gapfinder.py`): a `direction` param on `compute_gaps`. **backward** (inc 135)
  aggregates each paper's `referenced_works`; **forward** (new) aggregates the works that **cite** each paper
  (`fetch_work_id` → `fetch_citing_works`), keyed by the citing work's OA id with metadata from the citing dicts
  (no second fetch). Candidates = works related to ≥ `min_citations` of your papers, excluding in-library +
  dismissed. Direction-specific coverage note.
- **Axis-scoped** (`compute_gaps(axis_id=…)`): `_scoped_paper_rows` restricts the scanned papers to an axis's
  members (the inc-63 `cluster_node_papers JOIN cluster_nodes WHERE axis_id` subquery); the coverage `total` is
  the scope's paper count.
- **OpenAlex adapter** (`integrations/openalex/adapter.py`): `fetch_work_id(conn, ref)` (the bare `W…` id from the
  cached DOI→work fetch) + `fetch_citing_works(conn, work_id)` (`?filter=cites:<W…>`, validated `^W\d+$`, cached
  `citing:<id>`, capped `MAX_CITING=200`, fail-closed → meta dicts).
- **Persistent cache** (`gap_candidates` table, migration **0019**; `persistence/gap_repo.py`):
  `replace_gap_candidates(direction, axis_id, …)` (authoritative DELETE-all + bulk INSERT per scope) +
  `read_gap_candidates` (rows + the snapshot `computed_at`).
- **Endpoints** (`routers/gaps.py`): **`GET /gaps {direction, axis_id}`** reads the cache and **filters dismissed
  / now-in-library at read time** (so Add/Dismiss take effect with no recompute), **`POST /gaps/refresh`** +
  **`GET /gaps/refresh/{job_id}`** (async job → `compute_gaps` → `replace_gap_candidates`; result carries
  `checked`/`total`/`note`/`count`). The inc-135 `/gaps/find*` endpoints were **removed** (superseded). `add` /
  `dismiss` unchanged.
- **Frontend** (`36_gaps.jsx`): a **direction toggle** (Works you cite ⇄ Works citing you) + an **axis dropdown**
  (All / each axis, excluding My Publications) + a **Refresh** button. Opening / toggling reads the cache instantly
  (`GET /gaps`); a "Last refreshed <date>" / "Not computed yet — Refresh" line; per-row Add/Dismiss re-`GET /gaps`
  (the read-time filter drops the row). The library-header Gaps tooltip now names both directions.
- **Rule-#1 schema split (prerequisite):** `schema.py` had drifted to **611 (>600)** from inc 130/132. Split out
  `schema_base.py` (the shared `metadata`) + `schema_findings.py` (open_science_signals / paper_findings /
  retraction_records / **gap_candidates**), re-exported from `schema.py` (now **558**). No circular import
  (schema_findings imports `schema_base`, not `schema`); zero blast radius (the 66 importers keep
  `from …schema import X`); `metadata.create_all` still includes every table (the re-export registers them).

## Key technical detail

- **Forward needs no per-candidate metadata fetch** — `fetch_citing_works` returns full meta dicts
  (`_meta_from_work`), so `compute_gaps` forward keys `counts[citing_work] = set(paper_id)` *and* stashes the meta
  from the same dict. Backward still needs `fetch_work_meta` per surviving candidate (bounded to `max*3` over the
  threshold). **Gotcha (cost the headed driver a debug loop):** OpenAlex ids are `W` + **digits** — the backward
  path validates `^W\d+$` and silently drops a non-digit id, so test/seed data must use real `W<digits>` ids
  (`W9000001`), not mnemonics like `WGAP`.
- **Read-time filtering keeps the cache honest** — a dismissed (OA id *or* DOI) or now-in-library (by DOI)
  candidate is dropped at GET, so a stale cache row can never resurface an owned/dismissed work without a refresh.
- **The cache is scoped, not global** — `replace_gap_candidates` deletes only `(direction, axis_id)`, so a
  backward refresh never touches the forward cache (test-pinned).

## Manual verification script

1. `python .local/visual/drive_inc137_gaps.py` (a free port + own-process-alive check; pre-seeds `external_api_cache`
   so the **real** OpenAlex client runs **offline**). It drives: Gaps → modal → Refresh (backward) →
   "**A Foundational Reference Several Papers Cite · cited by 3 of your papers**" + the coverage/last-refreshed
   line → toggle **forward** → Refresh → "**cites 3 of your papers**" → **Dismiss** → the row drops.
2. Result: **PASS** — 0 console errors, 0 page errors, **0 genai hits**. (Add is covered by the TestClient unit
   test, which exercises add → imported → drops; it does a Crossref lookup, so the headed run stays offline.)

## Gates

- **Principles (#2/#3/#6/#7 + A-A):** forward adds **no new judgment** — same posture, the other citation direction.
  The count is "cited by / cites N of *your* papers" (a library count, **not** a global importance/quality rank);
  coverage + last-refreshed are stated; candidates-not-verdicts; Add is metadata-only (no PDF → no paywall
  circumvention). Declined easy path: a "must-read importance leaderboard".
- **Audit:** addendum to `.claude/security-audits/2026-06-26_gapfinder.md` — the `cites:` fetch is the same
  host/pattern/posture as the audited inc-119 citing fetch (validated, cached, capped, fail-closed); migration
  0019 additive/guarded; bound-param SQL; no new dependency; no Gemini egress. **PASS.**
- **Rule #10:** `route_41_gaps.md` updated (both directions, axis scope, the cache + Refresh); surface map
  **106/106 API + 528/528 FE, 0 uncovered**.

## Pytest

**519 passed, 1 skipped** (+5 net over inc 136's 514: `fetch_work_id`, `fetch_citing_works`,
`compute_gaps_forward`, `compute_gaps_axis_scoped`, `gap_repo` replace/read, + 2 endpoint tests replacing the old
find-endpoint tests). `ruff` clean; build + assembly green; migration head **0019**.

## Next (queued)

- Auto-select the top library paper on load (Details populated).
- The accordion-tabs design rule (tabs-within-a-section for like-with-like; Axes+Tags tabs; order Data-consistency
  before Statistics-check; codify in `DESIGN.md`).
- Gap-finder followed-authors / embedding-similarity candidate ranking; a cadence auto-refresh (manual Refresh +
  the persistent cache is v2).
- **Watch (rule #1):** `clustering/my_publications.py` at **594/600** — split before the next backend addition there.
