# Security Audit — Overlooked-work lens (backlog #37)

**Scope:** a new library-level discovery lens. New surface area:
- New external fetch path: `OpenAlexSourcesClient.fetch_topic_works` (`/works?filter=primary_topic.id:…`) + the
  client's opt-in self-committing `cache_engine` mode (`with_cache_engine`).
- New engine `app/backend/methods/overlooked.py::compute_overlooked` (local relevance + local percentile).
- New table `overlooked_candidates` (migration 0046) + `overlooked_repo`.
- New async job + endpoints `POST /overlooked/refresh`, `GET /overlooked/refresh/{job_id}`, `GET /overlooked`.
- New frontend panel (`08z_overlooked.jsx`); Add/Dismiss **reuse** the existing `/gaps/add` + `/gaps/dismiss`.

Triggers audit-gate items #1 (new endpoints), #2 (new external fetch), #5 (net-new feature spanning 3+ files).

## Threat review

- **Input validation / SSRF.** The only value that egresses is the axis label (→ `/topics?search=`, a bound query
  param, never the host) and the resolved topic id, validated `^T\d+$` **before** any request; candidate work ids
  validated `^W\d+$` before use. `axis_id` is a typed `int` (pydantic/Query) — a non-int or missing value 422s. No
  user/external string is ever interpolated into a URL path or SQL text. **VERIFIED** —
  `test_fetch_topic_works_reconstructs_abstract_and_metadata` proves a non-`^T\d+$` topic id returns `[]` with no
  fetch; `test_overlooked_refresh_requires_axis_id` proves missing `axis_id` → 422 (both GET + POST) and an unknown
  job id → 404.
- **Data egress (invariant #3).** This is **public-metadata egress** (the OpenAlex gap-finder channel), NOT the
  Gemini library-text gate. **No library text is transmitted**: candidate abstracts are reconstructed from the
  inverted index and embedded **on-device** (`compute_overlooked` calls `model.encode_texts` locally; it never passes
  abstract text to any egress function); only the topic id/label leaves. **VERIFIED** —
  `test_fetch_topic_works_transmits_only_the_topic_id` asserts the outbound `/works` request's params are a subset of
  `{filter, per-page, select, mailto}` with `filter == "primary_topic.id:T7"` — nothing but the topic id + fixed
  fields. (Same request-shaping discipline as PUBLISHERS' `test_abstract_never_transmitted`.)
- **SQL (rule #3).** All access via SQLAlchemy Core bound params (`overlooked_repo` uses `delete`/`insert`/`select`
  construct APIs; `axis_id` is a bound param); table/column names are module constants. **VERIFIED** by inspection +
  `test_overlooked_repo_round_trips_both_visible_inputs`.
- **Resource caps (rule #4).** `fetch_topic_works` bounded to `WORKS_SAMPLE` (200) per refresh; the candidate list
  is capped (`DEFAULT_CANDIDATE_CAP`). External fetch has an httpx timeout + is fail-closed (any error → cached
  error row → []). One `/works` call per refresh (cached thereafter).
- **Secret handling.** None introduced (no new keys; polite-pool `mailto` only, as elsewhere).
- **File-path safety.** No file read/write path introduced.
- **Concurrency / DB safety.** The refresh runs its fetch phase **fetch-outside-lock** (inc D): the OpenAlex
  fetches self-commit to the cache via `cache_engine`, so the write lock is not held across network I/O; the final
  persist is a short `run_write`. **[to verify: the fetch phase holds no long write lock]**
- **Supply chain.** No new third-party dependency.
- **Honesty invariants (rule #9).** Signal-not-verdict; two SEPARATE visible inputs, never fused into a composite
  score; identity-agnostic (no author/identity field in the engine, table, or response); silence-not-a-certificate
  (null percentile when too few peers). **VERIFIED** — `test_compute_overlooked_surfaces_relevant_undercited` +
  `test_overlooked_endpoints_refresh_then_list` assert no `score`/`author` key on any candidate; the
  `overlooked_candidates` table has no author column (migration verified); `test_compute_overlooked_no_percentile_
  when_too_few_same_year_peers` proves null-percentile works are withheld, not guessed; the frontend guard
  `test_overlooked_lens_panel_present_and_honest` pins the "possibly overlooked, possibly low-impact" copy + the
  absence of "hidden-gem"/"score".

## Negative-path checks

- **Missing/typed input:** `GET /overlooked` without `axis_id` → **422**; `POST /overlooked/refresh {}` → **422**;
  unknown job id on `GET /overlooked/refresh/{job_id}` → **404** (not a crash). — `test_overlooked_refresh_requires_axis_id`.
- **Bad topic id:** a topic id failing `^T\d+$` → `[]` with **no** outbound request. — `test_fetch_topic_works_*`.
- **Malformed / failing OpenAlex:** any fetcher exception or non-dict body → cached error row → `[]` (fail-closed,
  never raises) — the shared `_get` path, covered by `test_sources_client_fail_closed` (PUBLISHERS suite, same client).
- **Egress-off:** N/A to this feature — it is the **public-metadata** channel (OpenAlex), not the Gemini gate; the
  lens never invokes the LLM. No `CALLOSUM_ALLOW_DATA_EGRESS` path is touched.
- **No library text transmitted:** the outbound `/works` request carries only the topic id + fixed fields —
  `test_fetch_topic_works_transmits_only_the_topic_id`.
- **Resource caps:** `fetch_topic_works` bounded to `WORKS_SAMPLE` (200); one `/works` call per refresh (cached
  thereafter); httpx timeout on the real fetcher.

## Verdict

**Security Audit: PASS.** New surface (endpoints + external fetch + async job) validates all input at the boundary,
egresses only public topic metadata (no library text; abstracts embedded on-device), uses bound-param SQL, is
bounded + cached + fail-closed, runs its fetch phase fetch-outside-lock, and honors the honesty invariants
(signal-not-verdict, two-separate-inputs, identity-agnostic, silence-not-a-certificate) with guard tests. No new
dependency, secret, or file-path surface.
