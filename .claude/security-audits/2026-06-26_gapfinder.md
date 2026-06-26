# Security Audit — Literature gap-finder, inc 135

**Date:** 2026-06-26
**Feature:** Aggregate each library paper's OpenAlex `referenced_works`; surface works cited by >= N of the user's
papers that the library doesn't have ("cited by N of your papers") as Add/Dismiss candidates. New endpoints:
`POST`/`GET /gaps/find`, `POST /gaps/add`, `POST /gaps/dismiss`. New OpenAlex fetches + an additive migration.

**Audit-gate triggers:** #1 (new endpoints), #2 (a new external-fetch *use* of the OpenAlex adapter —
`referenced_works` + fetch-by-id), #5 (net-new feature 3+ files). Not #6 (no new dependency).

## Threat review

- **The OpenAlex fetches.** Both ride the **existing audited adapter** — fixed host (`api.openalex.org`), cached
  in `external_api_cache`, fail-closed. `fetch_referenced_works` parses the `referenced_works` list defensively
  (skip non-strings; keep only ids matching `^W\d+$`; cap `MAX_REFERENCED=500`). `fetch_work_meta` **validates
  the id** with `re.fullmatch(r"W\d+", work_id)` **before any fetch** (a bad id → None, no request), caches under
  `work:<id>`, and maps the body with guards. A non-200 / non-dict → None / []. PASS.
- **Resource caps / fail-closed.** The gap job scans live papers **with a DOI** (cached after the first run); a
  per-paper fetch error is swallowed (`compute_gaps` try/except → []). Candidate metadata fetches are bounded
  (`max_candidates*3` ranked ids; `GAP_MAX_CANDIDATES=50`). The job is async (`gap_jobs`); a failure → `mark_error`,
  never a 500. PASS.
- **Add — no arbitrary minting / no paywall circumvention.** `POST /gaps/add` reuses the **already-audited inc-119
  `import_citing_work`**: normalize DOI → `find_existing_paper_by_identity` dedup (idempotent) → metadata-only
  `create_paper(imported_source="gap-import")` → Crossref **DOI-lookup** enrich (a bad DOI → `crossref-unresolved`
  gracefully, never a crash). **No PDF is fetched** — the OA-acquire lane is untouched (the A-A no-paywall-
  circumvention veto holds). A blank DOI → **422**. PASS.
- **Dismiss.** `POST /gaps/dismiss` stores the OA id + DOI in `profile.dismissed_gap_works` (a bound-param JSON
  upsert; inserts a minimal profile row if none — no other profile field is touched). PASS.
- **SQL.** SQLAlchemy Core bound params throughout (the `compute_gaps` live-DOI query, the dismiss upsert,
  `find_existing_paper_by_identity`). The migration adds one nullable JSON column, guarded (additive). PASS.
- **Output encoding.** Candidate title/authors/year render via React text nodes (escaped); no
  `dangerouslySetInnerHTML`. PASS.
- **Data egress.** Public **OpenAlex metadata** (referenced-works + work-by-id) + a Crossref DOI lookup on Add —
  the inc-81/119 metadata posture, explicitly **not** the Gemini library-text gate; no library text leaves. The
  headed run (egress unset, fully cache-backed) recorded **0** genai-host requests. PASS.
- **Secret handling.** No new secret (the polite mailto already comes from env). PASS.
- **Supply chain.** No new dependency. PASS.
- **Authorization / deployment.** A remote caller could trigger a library-wide outbound fetch — covered by the
  standing "before hosted deploy: add auth + rate-limiting" note.

## Principle / value posture (the rule-#9 gate, run)

- **Facts vs candidates (#3):** nothing is auto-added; the human Adds or Dismisses each candidate.
- **Evidence carried (#1/#8):** each candidate shows **"cited by N of your papers"** — a count over the user's own
  library, inspectable, not a hidden score.
- **No opaque composite score / not a rank (#2/#7):** the count is a fact about the user's library's citing, **not
  a global importance/quality ranking**. **Declined easy path:** a "must-read importance score" / a "papers you
  should read" leaderboard.
- **Silence is not a certificate (#6):** coverage is **stated** — "scanned M of N papers (the rest have no DOI);
  based on the references OpenAlex has — partial." A missing work isn't "unimportant", just not surfaced.
- **No accusation (A-A):** discovery only; no judgment of any paper or author. Add stays metadata-only (no PDF →
  no paywall circumvention).

## Negative-path checks (run)

- `POST /gaps/add` with a blank DOI → **422**; idempotent (a second add → `exists`) — `test_gapfinder.py`.
- a dismissed candidate → excluded on the next find (`test_gap_dismiss_endpoint_excludes_candidate`).
- a candidate already in the library (by DOI) → excluded (`test_compute_gaps_excludes_in_library_and_dismissed`).
- a bad work id → `fetch_work_meta` returns None without a fetch.
- Headed run (egress unset, cache-backed): **0** genai-host requests; **0** console/page errors.

## Result

**Security Audit: PASS.** Public OpenAlex/Crossref metadata (bounded, validated, cached, fail-closed), reuse of
the audited citing-import (metadata-only, deduped, no PDF/paywall), bound-param SQL, additive migration, escaped
output, no Gemini egress, no new dependency, candidates-not-verdicts.

---

## Addendum — inc 137 (forward gap + axis-scoped + persistent cache)

inc 137 extends the gap-finder: a **forward** direction (works that CITE your papers), **axis-scoped** scanning,
and a **persistent cache** (`gap_candidates`). Re-audited the deltas; the inc-135 posture above is preserved.

**New external fetch (`fetch_citing_works`).** `OpenAlexClient.fetch_citing_works(conn, work_id)` queries
`?filter=cites:<W…>` — the **same host, pattern, and posture** as the inc-119 `OpenAlexAuthorClient.fetch_citing_works`
(already audited): `work_id` is validated `^W\d+$` **before** any request; results are **cached** (`citing:<id>`),
**capped** (`MAX_CITING=200`, a documented coverage limit), and **fail-closed** (any exception / non-200 → `[]`).
`fetch_work_id` reads the bare `W…` id from the already-cached DOI→work fetch (no new request). Public metadata,
**not** the Gemini gate.

**New migration / table (0019 `gap_candidates`).** Additive + guarded (`if "gap_candidates" not in
inspector.get_table_names()`), same idempotent pattern as 0002-0018; no down-migration. `axis_id` is a plain
scope tag (**no FK**) — a stale row for a deleted axis is simply never read (the axis won't appear in the
dropdown). All writes/reads are SQLAlchemy Core **bound parameters** (`gap_repo.py`); `replace_gap_candidates`
deletes + re-inserts the scope authoritatively (no stale candidate survives).

**Schema split (rule #1).** `schema.py` had drifted to 611 (>600) from inc 130/132; the findings/signals/retraction
tables + the new `gap_candidates` moved to `schema_findings.py` (importing the shared `metadata` from a new
`schema_base.py`), re-exported from `schema.py` (now 558). Behaviour-preserving — verified by the full suite +
`metadata.create_all` still includes every table (the re-export registers them).

**Read-time filtering (`GET /gaps`).** The cache is filtered at read time against `dismissed_gaps` (OA id **or**
DOI) and `find_existing_paper_by_identity` (now-in-library by DOI) — so Add/Dismiss take effect with no recompute
and a dismissed/owned work can never be re-surfaced from a stale cache row.

**New endpoints.** `GET /gaps` (read-only), `POST /gaps/refresh` + `GET /gaps/refresh/{job_id}` (async job, reuses
`app.state.gap_jobs`). `direction` is a `Literal["backward","forward"]` (FastAPI rejects other values → 422);
`axis_id` is an optional int. The inc-135 `/gaps/find*` endpoints were removed (superseded). `/gaps/add` +
`/gaps/dismiss` are unchanged. No new dependency, no Gemini egress.

**Negative-path (run):** invalid `direction` → 422 (FastAPI Literal); a bad work id → `fetch_citing_works` returns
`[]` without a request; forward + backward caches are isolated (`test_gap_refresh_forward_direction_is_independent`,
`test_gap_repo_replace_and_read_isolated_by_scope`); axis-scope restricts the scan
(`test_compute_gaps_axis_scoped_restricts_to_members`). Full suite **519 passed**.

**Result: PASS** (addendum). Same OA-metadata posture, bound-param SQL, additive/guarded migration, validated
inputs, fail-closed fetches, no new dependency, no Gemini egress, candidates-not-verdicts.
