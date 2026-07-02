# Security audit — PUBLISHERS "where to submit" journal-finder, SP1a (2026-07-01, inc TBD)

Backlog #40. A METHODS tool that, from an abstract, matches candidate journals **locally** and shows a uniform
factual profile per journal. SP1a = the backend engine + endpoint (two new external fetches + one new endpoint).

## Trigger
- New API endpoint (`POST/GET /methods/publishers/run`).
- Two new external fetch paths: OpenAlex `/topics` + `/works` + `/sources` (`integrations/openalex/sources.py`);
  DOAJ journals API (`integrations/doaj/journals.py`).

## Threat review

- **The abstract never leaves the machine (the load-bearing invariant).** The candidate pool is derived from a
  *topic* (a library paper's OpenAlex `primary_topic`, or an OpenAlex `/topics?search=<subject>` resolution of a
  user-typed subject keyword), never from the abstract. The abstract is embedded **locally** (SPECTER) and only
  re-ranks the pool. Only topic ids / a subject keyword / source ids / ISSNs leave the machine. **Test:**
  a recording transport asserts the abstract text appears in **no** outbound request path/params. → *to verify below.*
- **SSRF / injection.** Every id is validated **before** the request: topic `^T\d+$`, source `^S\d+$`, ISSN
  `^\d{4}-\d{3}[\dX]$`. The subject keyword is passed only as a bound query **param** (`search=`), never as the host
  or path. Constant hosts (`https://api.openalex.org`, `https://doaj.org`). No user-supplied URL is ever fetched; no
  PDF is retrieved (this is a metadata tool, not the acquisition lane). → *to verify below.*
- **Egress class.** Public bibliographic metadata (the inc-183/227 posture) — **NOT** the Gemini library-text gate.
  User-initiated (a Run action). Cached via `integrations/api_cache.py` (providers `openalex-sources`, `doaj-journals`),
  so re-runs are cheap; failures are cached non-poisoningly (`status_code=None` → returns None, retryable).
- **Secret handling.** Optional `CALLOSUM_DOAJ_API_KEY` sent as a header only if present — never in a URL, cache key,
  or log. OpenAlex polite-pool mailto via `resolved_mailto` (already audited).
- **Resource caps (rule #4).** `MAX_CANDIDATES` journals profiled; `MAX_BYIDS` (50) per `/sources` batch; a bounded
  works-sample page for the pool; abstract length cap at the endpoint. Fail-closed everywhere (any fetch error →
  cached error row → None; the worker's whole body is `try/except → mark_error`).
- **No SQL written by the feature** (reads a paper's stored abstract/DOI via bound-param selects; the result is an
  ephemeral job, no table/migration).
- **Supply-chain.** No new dependency (SPECTER rides the existing sentence-transformers stack; httpx already present).

## Principles / A-A vetoes (encoded as tests, not prose)
- No composite/openness/legitimacy **score** in any response (the ranking is a re-order; the shown rationale is the
  components + `elevated_for` goods).
- **No "predatory" label** anywhere.
- A journal clearing **no** legitimacy signal still appears (gate the boost, never the listing).
- Closed journals appear with their facts (not an OA-only filter).
- Absence of a legitimacy signal renders as neutral fact, never a flag.

## Negative-path checks (all in `tests/test_publishers.py`, hermetic — fake fetchers + a fake embed model)
- **Abstract never transmitted** — `test_abstract_never_transmitted`: a recording transport captures every OpenAlex
  (`/topics`,`/works`,`/sources`) + DOAJ request; a `SECRETABSTRACTTOKEN`-prefixed abstract appears in **none** of
  them (and requests were actually made). ✓
- **Id validation before any fetch** — `test_topic_resolution_and_candidate_pool_and_details`: a `bad-id` topic and a
  `"bad"` source id are rejected without a request; `test_doaj_journal_parse_and_validation`: `"not-an-issn"` → no
  request. ✓
- **Fail-closed** — `test_sources_client_fail_closed`: a 500 fetcher → topic None / pool [] / details {}; the worker
  wraps its whole body → `mark_error` (never a crash). ✓
- **Endpoint validation** — `test_endpoint_validation`: neither input → 422, both inputs → 422, nonexistent paper →
  404, no-DOI paper → 422, unknown job → 404. ✓
- **No composite score / no "predatory"** — `test_build_profiles_no_composite_score_no_predatory` +
  `test_endpoint_paste_path`: the response JSON has no `*score*` key and no "predator" substring. ✓
- **Gate the boost, not the listing** — `test_build_profiles_fit_orders_and_every_candidate_appears` +
  `test_endpoint_paste_path`: a **closed** journal (not in DOAJ, `is_oa=False`) still appears with `oa_color:"closed"`. ✓
- **Elevate, don't denigrate** — `test_build_profiles_weighting_elevates_open_goods`: weighting>0 elevates the
  diamond+Seal journal with `elevated_for` populated; the closed journal's `elevated_for` is empty (no deficit flag). ✓

## Result
**Security Audit: PASS.** All negative-path checks pass (13 tests, `tests/test_publishers.py`). SSRF is closed by
validating every id before the request + constant hosts + the subject as a bound query param; the abstract is embedded
locally and provably absent from all outbound requests; egress is public bibliographic metadata (not the Gemini gate),
cached + fail-closed; the Principles/A-A vetoes (no composite score, no "predatory" label, every candidate listed,
elevate-don't-denigrate) are enforced structurally and pinned by tests; no new dependency; no migration.

---

## Addendum — SP1b (the panel + the local publisher prefs), inc 246

SP1b adds the METHODS panel (`08e_methods_publishers.jsx`), the first-use choice gate, and two **local
preferences** (`publisher_weighting` + `publisher_breadth`) on the existing `/settings` endpoint. **No new external
fetch, no new endpoint beyond the additive `/settings` fields, no migration, no new dependency.**

- **Preferences are local + never transmitted externally.** They live in the gitignored `app_settings` file store
  (like `data_egress_enabled` / `contact_email`), are returned only to the local UI over loopback `GET /settings`
  (not off-machine transmission), and the weighting reaches **only** the local `/methods/publishers/run` endpoint,
  where it is a `build_profiles` ordering param — **never forwarded to OpenAlex/DOAJ**. The SP1a recording-transport
  test (`test_abstract_never_transmitted`) already proves the outbound requests carry only topic/subject/ids — the
  weighting appears in none of them.
- **The prefs are not secrets** (a ranking preference, not a credential) → file store + returned by `GET /settings`,
  the `contact_email` posture; there is no key-leak surface.
- **Input validation at the boundary** (`PUT /settings`): the weighting must be `0.0 ≤ w ≤ 1.0` (else 422); the
  breadth is allowlisted to `{focused, broad}` (else 422); a rejected PUT writes nothing (tested).
- **The choice gate is a UX + honesty control, not a security boundary** — it withholds *output*, not access; no
  privilege or egress decision hangs on it.

## Result (SP1b)
**Security Audit: PASS (addendum).** SP1b introduces no new external fetch / endpoint / dependency / migration; the
new prefs are local, validated at the boundary, and never transmitted externally (the weighting never reaches a
fetch — proven by the SP1a recording-transport test). The Principles/A-A vetoes remain structural + test-pinned.
