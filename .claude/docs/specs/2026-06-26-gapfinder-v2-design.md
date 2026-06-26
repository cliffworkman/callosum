# Gap-finder v2 — forward gap + axis-scoped + persistent cache (inc 137)

**Goal:** Round out the inc-135 backward gap-finder with the user-chosen scope: a **forward gap** (works that
**cite** many of your papers but you don't have), **axis-scoped** ranking ("gaps for [axis]"), and a **persistent
cache** so the modal opens instantly.

## Architecture (extends inc 135)

### Persistent cache — `gap_candidates` table (migration 0019, additive/guarded)

One row per cached candidate, scoped by `(direction, axis_id)`. Columns: `id`, `direction`
(`"backward"|"forward"`), `axis_id` (Integer, nullable — NULL = whole library), `openalex_work_id` (String),
`doi` (String), `title` (Text), `authors` (JSON), `year` (Integer, nullable), `cited_by_in_library` (Integer),
`computed_at` (String). Index `(direction, axis_id)`. The refresh **replaces** all rows for a scope.
`persistence/gap_repo.py`: `replace_gap_candidates(conn, direction, axis_id, candidates, *, computed_at)`,
`read_gap_candidates(conn, direction, axis_id) -> (rows, computed_at)`.

### compute_gaps — `direction` + `axis_id` (`clustering/gapfinder.py`)

- `compute_gaps(conn, *, openalex_client, dismissed, direction="backward", axis_id=None, min_citations, max_candidates)`.
- **Scoped papers** = live papers with a DOI; if `axis_id` given, restrict to that axis's members (the inc-63
  `cluster_node_papers JOIN cluster_nodes WHERE axis_id` subquery).
- **backward** (inc 135): aggregate `fetch_referenced_works` (works your papers cite).
- **forward** (new): for each scoped paper, `wid = openalex_client.fetch_work_id(conn, ref)`; then
  `citing = openalex_client.fetch_citing_works(conn, wid)` (works that cite it); accumulate
  `counts[citing_work] = set(paper_id)` keyed by the citing work's OA id; candidate metadata comes from the
  citing dicts (no separate `fetch_work_meta`). Candidates = works that cite ≥ `min_citations` of your papers,
  excluding in-library + dismissed.
- Returns `(candidates, coverage)` (coverage = `{checked, total, note}`; the note is direction-specific).

### OpenAlex adapter additions (`integrations/openalex/adapter.py`)

- `fetch_work_id(conn, ref) -> str | None`: `(self._fetch_work(conn, ref) or {}).get("id")` → bare `W…` (cached).
- `fetch_citing_works(conn, work_id, *, cap=200) -> list[dict]`: paginated `?filter=cites:<W…>` (validate
  `^W\d+$`, cache key `citing:<id>`, fail-closed), each → `{openalex_work_id, doi, title, authors, year}`
  (mirrors `author._citing_from_obj` but returns dicts + the OA id). Caps pages + total.

### Endpoints (`routers/gaps.py` — rework the inc-135 find endpoint; keep add/dismiss)

- **`GET /gaps {direction, axis_id}`** → `read_gap_candidates`, **filter out** dismissed (profile) + now-in-library
  (`find_existing_paper_by_identity` by DOI) at read time, order by `cited_by_in_library` desc → `{candidates,
  computed_at}` (so the cached view stays accurate after Add/Dismiss without a recompute).
- **`POST /gaps/refresh {direction, axis_id}`** + **`GET /gaps/refresh/{job_id}`** (async; `app.state.gap_jobs`):
  the job runs `compute_gaps(direction, axis_id)` → `replace_gap_candidates(...)`; the job result carries the
  coverage (`checked`/`total`) for the post-refresh "scanned M of N" line.
- `POST /gaps/add` + `POST /gaps/dismiss` — unchanged (inc 135). **Removed:** the inc-135 `POST /gaps/find` +
  `GET /gaps/find/{job_id}` (superseded by refresh + the cache).

### Frontend (`36_gaps.jsx`)

The modal gains a **direction toggle** (Works your papers cite ⇄ Works that cite your papers) + an **axis
dropdown** (All / each axis, from `GET /axes`). On open / toggle / axis-change → `GET /gaps?direction=&axis_id=`
(instant, from cache) + a "last refreshed <date>" line (or "not computed yet — Refresh"). A **Refresh** button →
`POST /gaps/refresh` → poll → reload the cache + show "scanned M of N". Per-row Add/Dismiss re-`GET /gaps` (the
read-time filter drops the row). The empty/coverage states reuse v1's honest framing.

## Honesty / Principles (unchanged from inc 135, re-asserted)

- Candidates, not verdicts; the count is **"cited by / cites N of *your* papers"** (a library count, **not** a
  global importance/quality rank); coverage stated; Add is metadata-only (no PDF → no paywall circumvention).
- Forward adds no new judgment — same posture, the other citation direction.

## Out of scope (v2 → later)

- Followed-authors gap; embedding-similarity ranking of candidates; auto-refresh on a cadence (manual Refresh +
  the persistent cache is v2).

## Tests (hermetic — injected fake client, no network)

- adapter: `fetch_work_id` (work body → bare id; no work → None); `fetch_citing_works` (paginated cites → dicts
  with the OA id; bad id → []).
- `compute_gaps(direction="forward")`: 3 papers, an external work W cites 2 of them (min=2) → candidate cited_by 2;
  axis-scoped restricts to an axis's members (a paper outside the axis doesn't count).
- `gap_repo`: replace-all per (direction, axis_id) is isolated (refreshing backward doesn't touch forward);
  `read_gap_candidates` returns the rows + computed_at.
- endpoints: `GET /gaps` reads the cache + filters dismissed/in-library; `POST /gaps/refresh` populates it; the
  direction + axis_id params thread through; route-surface (`test_health.py`); migration head 0019.

## Verification

- pytest green (+ ~12); ruff clean; build + assembly + the **e2e suite**. QA `route_41` updated (the cache + the
  two directions + axis-scope) + surface map 0 uncovered. Headed, no egress (pre-seed `external_api_cache` for
  both a referenced-works and a cites query so the real path runs offline): toggle backward/forward, an axis
  scope, Refresh → cached list, Add/Dismiss. 0 console/page/genai.
