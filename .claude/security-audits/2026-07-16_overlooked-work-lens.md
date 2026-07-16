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
  user/external string is ever interpolated into a URL path or SQL text. **[to verify: negative-path checks]**
- **Data egress (invariant #3).** This is **public-metadata egress** (the OpenAlex gap-finder channel), NOT the
  Gemini library-text gate. **No library text is transmitted**: candidate abstracts are reconstructed from the
  inverted index and embedded **on-device**; only the topic id/label leaves. (Guarded like the PUBLISHERS
  `test_abstract_never_transmitted` invariant.) **[to verify]**
- **SQL (rule #3).** All access via SQLAlchemy Core bound params (`overlooked_repo`); table/column names are
  constants. **[to verify]**
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
  (null percentile when too few peers). Pinned by guard tests. **[to verify]**

## Negative-path checks

_[filled in Task 6 — bad axis_id → 422; malformed OpenAlex → fail-closed []; egress-off is N/A (metadata channel);
abstract-never-transmitted; no author/score field on any output]_

## Verdict

_Pending (finalized in Task 6)._
