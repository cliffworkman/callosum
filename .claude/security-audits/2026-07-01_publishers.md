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

---

## Addendum — SP2 (SciELO + TOP Factor legitimacy signals), inc 448

Wires two of the four `LEGITIMACY_DEFERRED` sources: **SciELO** (a live per-ISSN regional-index lookup) and
**TOP Factor** (a periodic bulk CSV mirror from the Center for Open Science — the first schema/migration this
tool has ever needed). Open Policy Finder (green-route/self-archiving), AJOL/Redalyc/Latindex, COPE/OASPA
membership, and PubMed/Scopus indexing remain untouched and deferred.

### Trigger
- Two new external fetch paths: SciELO's ArticleMeta API (`integrations/scielo/journals.py`, one live call per
  candidate journal); the TOP Factor CSV bulk download (`integrations/top_factor/adapter.py`, OSF-hosted).
- Two new endpoints: `GET/POST /methods/top-factor/database[/refresh]` (mirrors the existing, already-audited
  Retraction Watch DB download-trigger shape).
- New schema + migration (`top_factor_records`, `alembic/versions/0066_top_factor_records.py`) — additive only,
  no destructive change, guarded create.

### Threat review
- **SciELO SSRF/injection.** ISSN validated `^\d{4}-\d{3}[\dX]$` before any request (identical regex to DOAJ's);
  constant HTTPS host (`https://articlemeta.scielo.org`); the ISSN is passed only as a bound query param, never
  the host/path. Confirmed live before implementation that the endpoint serves HTTPS (not just the `http://`
  shown in some third-party documentation) — used HTTPS throughout, matching every other client's posture.
- **SciELO egress class.** Public bibliographic metadata (journal indexing status), no auth, no API key, cached
  via `integrations/api_cache.py` (provider `scielo-journals`) exactly like DOAJ; fail-closed (any error →
  cached error row → `None`, never raises). One live call per candidate journal (no cheap OA/DOAJ-style
  pre-filter exists — a closed journal can still be SciELO-indexed), bounded by the existing `MAX_CANDIDATES=60`
  cap already applied upstream in `fetch_candidate_sources`.
- **TOP Factor is not a live per-request call at all.** It is a periodic bulk-download mirror, downloaded only
  by an explicit Settings action (never auto-triggered from a Publishers run, unlike Retraction Watch's
  best-effort auto-refresh) — `build_profiles`'s per-candidate TOP Factor lookups are pure local `SELECT`s
  against `top_factor_records`, zero HTTP at request time. This was a deliberate design constraint (not an
  accidental omission) so a Publishers run's network surface stays fully described by the OpenAlex/DOAJ/SciELO
  calls already covered above.
- **TOP Factor download bounds (rule #4).** `MAX_TOP_FACTOR_BYTES` (20 MiB, ~5x the confirmed real ~4.2 MiB
  file) and `MAX_TOP_FACTOR_ROWS` (50,000, TOP Factor covers a few thousand journals) — mirrors
  `retraction_watch/adapter.py`'s exact size/row-cap posture. Streaming download with `follow_redirects=True`
  (OSF's real URL redirects twice — `files.osf.io` then a signed `storage.googleapis.com` URL — confirmed live);
  a malformed/missing score cell omits that category rather than fabricating a 0; a malformed `Total` cell is
  derived from the sum of the parsed category scores rather than silently accepted or dropping the row.
- **No SQL written unsafely.** `top_factor_repo.py` uses SQLAlchemy Core bound parameters throughout (`select`/
  `insert`/`delete`, no string interpolation); `replace_top_factor_records` deletes-then-inserts in one
  transaction (a fresh snapshot is authoritative, matching `replace_retraction_records`'s exact pattern).
- **Secret handling.** Neither new client uses a secret — SciELO has no auth at all; TOP Factor's download URL
  is a fixed public OSF link with no credential.
- **Supply-chain.** No new dependency — both clients reuse `httpx` (already present) and the existing
  `integrations/api_cache.py` helper.

### Principles / A-A vetoes (extended, same structural enforcement as SP1a/SP1b)
- **No opaque score (Principles #7, the new consideration this addendum introduces).** TOP Factor's `Total` is
  COS's own defined sum, not a callosum-invented composite — but it is never shown bare: the frontend's
  `<details>` "show the basis" block always sits beside it, exposing all 9-10 category sub-scores +
  justifications. `legitimacy_signals` deliberately carries only `"Has a TOP Factor transparency assessment"`
  (a coverage fact), never the bare number as a floating chip.
- **Gate the boost, never the listing (extended to the 2 new sources).** A journal with neither SciELO nor TOP
  Factor data still appears unchanged — both new `JournalProfile` fields are simply empty/`None`.
- **Silence isn't a certificate (Principles #6, the never-downloaded honesty resolution).** A per-journal
  `top_factor: None` is ambiguous in isolation ("no row for this journal" vs. "the mirror was never
  downloaded"). Resolved at the **report level**: `PublishersReport.top_factor_coverage` (`{count,
  retrieved_at}`, the exact shape `retraction_db_status()` already uses) is populated once per run; when
  `count == 0`, the UI shows one explicit footer note rather than letting every silent `top_factor: None` read
  as "checked, absent." This can never affect ranking or the candidate list — a display caption only.

### Negative-path checks (new, in `tests/test_publishers.py` + new `tests/test_top_factor.py`)
- **Abstract still never transmitted** — `test_abstract_never_transmitted` extended to also record + assert on
  SciELO requests (a `SECRETABSTRACTTOKEN` never appears; SciELO was actually queried — sanity that the test
  isn't vacuous). ✓
- **SciELO id validation before any fetch** — `test_scielo_journal_parse_and_validation`: `"not-an-issn"` → no
  request. ✓
- **SciELO fail-closed on the confirmed real "not indexed" shape** — an empty `[]` response → `None`, no
  exception; cached and reproduced identically on a second lookup (`test_scielo_journal_cache_roundtrip`). ✓
- **SciELO multi-collection merge** — `test_scielo_multi_collection_parse`: a journal indexed under multiple
  SciELO collections merges into one `ScieloJournal`, not silently truncated to the first hit. ✓
- **No new opaque score** — `test_build_profiles_no_composite_score_no_predatory` extended: no key on a profile
  ends with `"score"` (the only bare numeric fact is the pre-existing labeled `fit`); the narrowed
  `LEGITIMACY_DEFERRED` strings are asserted exactly. ✓
- **Gate the boost, not the listing (2 new sources)** — `test_build_profiles_wires_scielo_and_top_factor_facts`:
  a candidate with no SciELO/TOP Factor data still appears with empty/`None` fields and no fabricated signal
  chips. ✓
- **Never-downloaded honesty** — `test_build_profiles_top_factor_never_downloaded_is_honest` +
  `test_top_factor_db_status_reports_never_downloaded_then_counts`: an empty mirror reports
  `{"count": 0, "retrieved_at": None}` at both the repo and report level, distinguishable from "checked,
  absent" at the UI. ✓
- **TOP Factor CSV parse bounds** — `test_malformed_score_cell_omits_category_not_fabricates_zero`,
  `test_malformed_total_cell_is_derived_from_summed_category_scores`, `test_parse_maps_categories_and_skips_rows_without_any_issn`
  (a row with neither ISSN nor EISSN is unreachable by matching and is skipped, not stored with a null key). ✓
- **TOP Factor mirror is authoritative** — `test_replace_is_authoritative`: a re-download that no longer lists
  a journal removes it, matching Retraction Watch's exact replace-all posture. ✓
- **Migration drift** — `test_top_factor_records_table_is_at_head` (`tests/test_migrations.py`): the migration's
  columns match the SQLAlchemy model exactly (CI's `alembic check` gate). ✓

### Result
**Security Audit: PASS (SP2 addendum).** SSRF is closed for SciELO by the same id-validation + constant-host +
bound-param posture as DOAJ; TOP Factor introduces zero request-time HTTP (a local mirror only), with its one
download path bounded, streaming, and fail-closed on oversize/network error. No new secret, no new dependency.
The new schema is additive-only and migration-drift-tested. The Principles/A-A vetoes — now including the
never-downloaded honesty resolution and TOP Factor's basis-always-visible treatment — are enforced structurally
and pinned by 41 tests across `tests/test_publishers.py` + `tests/test_top_factor.py`. Live-verified against the
real SciELO API and a real TOP Factor download (3,209 journals) before this audit was written, not assumed.

**Post-audit correction (same session, before shipping).** The "basis-always-visible" claim above describes the
intended design; a first pass of the frontend actually violated it — `<summary>TOP Factor: {total} — show the
basis</summary>` rendered the bare `Total` on every card whether or not the `<details>` was expanded, since a
`<summary>` is always visible on a collapsed `<details>` element. Live Playwright verification with real
downloaded TOP Factor data caught this directly (the rendered page text showed "TOP Factor: 4" with nothing
expanded) — no pytest coverage exercises rendered DOM text, so this was only catchable by actually looking at the
page. Fixed by moving `Total` out of the `<summary>` into the expanded content only; re-verified live that the
collapsed state carries no number. No test asserted the old (wrong) behavior, so no test needed updating — this
was a pure frontend-markup fix.

---

## Addendum — SP4 (NLM/MEDLINE indexing signal), inc 452

Wires a fifth `LEGITIMACY_DEFERRED` source: **NLM/MEDLINE indexing status**, a live per-ISSN lookup against
NCBI's free, no-key **E-utilities** `esearch` endpoint (`db=nlmcatalog`) — mirrors SciELO's live shape (inc 448),
not TOP Factor/AJOL's periodic-mirror shape. Scopus indexing, and raw "any PubMed presence" beyond MEDLINE, are
never named anywhere in this codebase — proprietary/no free API for the former, never promised for the latter.

### Trigger
- One new external fetch path: `integrations/nlm/journals.py`, one live call per candidate journal (no
  pre-filter, same posture as SciELO — a closed/non-OA/non-SciELO journal can still be MEDLINE-indexed).
- No new endpoint, no new schema/migration, no Settings UI, no `.env.example` addition — an additive field on
  `PUBLISHERS`'s existing async job response.

### Threat review
- **SSRF/injection.** ISSN validated `^\d{4}-\d{3}[\dX]$` before any request (identical regex to DOAJ/SciELO);
  constant HTTPS host (`https://eutils.ncbi.nlm.nih.gov/entrez/eutils`, the same host+constant this codebase's
  existing `discovery/pubmed_provider.py` already trusts for Search/Feed); the ISSN, `tool`, `email`, and search
  term are all bound query **params**, never the host/path. No user-supplied URL is ever fetched.
- **Egress class.** Public NLM Catalog metadata (indexing status), no auth, no secret of any kind — unlike DOAJ's
  optional API-key header, this client has no credential surface at all. `email` reuses the existing, already-
  audited `resolved_mailto("CALLOSUM_CROSSREF_MAILTO")` convention `pubmed_provider.py` already sends to the same
  host family — no new env var introduced.
- **Fail-closed, never raises.** A malformed ISSN, a well-formed-but-unindexed ISSN (`esearchresult.count == 0`),
  and a network/parse error all collapse to `False` — cached via the existing, unmodified
  `integrations/api_cache.py` (`get_cached`/`put_cached`), matching SciELO's exact fail-closed contract. This is
  a deliberate scope choice (confirmed by the user this session): the richer "never indexed" vs. "deselected
  since" distinction NLM's catalog data *can* express is intentionally not built — a plain binary signal, matching
  SciELO's own precedent of no richer status.
- **A real correctness bug found live before ship: "PubMed" and "MEDLINE" are NOT the same claim, and the query
  only checks the latter.** NLM's own catalog record treats "MEDLINE" and "PubMed" as independent
  `IndexingSourceName` values with independent status. Live-verified for *World Psychiatry* (WPA's flagship,
  unambiguously legitimate, ISSNs `1723-8617`/`2051-5545`): its real NLM Catalog record shows PubMed
  "Currently-indexed" but carries **no MEDLINE entry at all**, so the `currentlyindexed[all]` query term (which
  empirically tracks MEDLINE status — confirmed against two real MEDLINE-indexed journals as positive controls)
  correctly returns `count: 0` for it. The first implementation pass named the resulting field/signal
  "PubMed/MEDLINE" — an overclaim, since a real, major journal that IS PubMed-searchable would have silently read
  as "not indexed" under a label that promised to check PubMed too. Caught via live re-verification during manual
  QA (not by the hermetic tests, which use a synthetic fetcher and can't catch a wrong real-world query mapping),
  fixed before ship by renaming end-to-end: `JournalProfile.indexed_in_medline` (was `indexed_in_pubmed`), the
  chip text is `"Indexed in MEDLINE"` (was `"Indexed in MEDLINE/PubMed"`), `fetch_medline_indexed()` (was
  `fetch_indexed()`). The underlying query and its correctness were never wrong — only the label overclaimed what
  it checks. Broader raw-PubMed presence (including PubMed-only, non-MEDLINE-curated content) stays unchecked
  and is not named as a signal; MEDLINE indexing is a complete, well-defined legitimacy signal on its own terms.
- **Rate-limit correctness, not just performance.** Live-confirmed via `curl` before implementation: NCBI
  enforces roughly 3 requests/second without an API key (real 429s reproduced after 4 rapid requests). A
  `PUBLISHERS` run makes one live call per candidate, sequentially, up to `MAX_CANDIDATES` — a naive unthrottled
  loop could 429 partway through and silently misreport later candidates as "not indexed," which is a
  correctness/honesty defect (a false negative on a real journal), not merely a slowdown. Rather than add an
  optional `CALLOSUM_NCBI_API_KEY` (config surface most users would never set up, so it wouldn't protect the
  default path), `NlmJournalsClient` self-paces: it tracks the monotonic timestamp of its last live call and
  sleeps the remainder of a ~350ms window before firing the next one (only on a cache miss — cached reads never
  pace). This protects every user by default with no setup step. Live-verified end-to-end: a real 25-candidate
  broad run completed with consistent `indexed_in_medline` values across two identical re-runs.
- **No SQL written unsafely.** No new table; the client only calls the existing, unmodified
  `integrations/api_cache.py` bound-parameter helpers.
- **Supply-chain.** No new dependency — reuses `httpx` (already present) and `resolved_mailto` (already present).

### Principles / A-A vetoes (extended, same structural enforcement as SP1a/SP1b/SP2/SP3)
- **Every claim carries its evidence, precisely (Principles #1/#2, the load-bearing lesson of this addendum).**
  The World Psychiatry catch above is a direct instance of the "signal not verdict" commitment applied to a
  *label*, not just a numeric confidence: a correctly-computed fact under an imprecisely-named field is still a
  form of overclaiming. Renaming to match exactly what the query checks (MEDLINE, not PubMed generally) closes it.
- **Never an opaque score or an elevation good.** `_elevated_goods()` gained no new parameter — MEDLINE indexing
  is exposed only via `legitimacy_signals` (`"Indexed in MEDLINE"`, a coverage fact), never `elevated_for`,
  matching SciELO's identical precedent (indexing is a discoverability fact, not an "open-science good" the
  weighting should reward). Test-pinned explicitly (`test_build_profiles_wires_medline_indexing_fact` + an
  explicit assertion added to `test_build_profiles_weighting_elevates_open_goods`).
- **Gate the boost, never the listing (extended).** A journal with no MEDLINE data still appears unchanged —
  `indexed_in_medline` is simply `False`, `legitimacy_signals` carries no fabricated entry.
- **`LEGITIMACY_DEFERRED` narrowed honestly.** `"PubMed / Scopus indexing"` is dropped whole rather than split
  into a residual entry — mirrors exactly how "AJOL" silently dropped out of the old "AJOL, Redalyc, Latindex"
  string once AJOL was wired (inc 451); the increment notes + this addendum carry the record of Scopus having
  been considered and declined (proprietary, no free API), not the deferred-sources list.

### Negative-path checks (new, in `tests/test_publishers.py`)
- **ISSN validation before any fetch + fail-closed on unindexed** — `test_nlm_medline_indexing_validation_and_parse`:
  a malformed ISSN → `False`, no request; a well-formed-but-unindexed ISSN → `False`, no exception. ✓
- **Cache roundtrip** — `test_nlm_medline_indexing_cache_roundtrip`: a second lookup for the same ISSN is served
  from cache, not the fetcher. ✓
- **Pacing guard fires on a real (non-cached) call** — `test_nlm_medline_indexing_client_paces_live_requests`: a
  primed `_last_request_at` forces the next live call to wait out the ~350ms floor. ✓
- **Abstract still never transmitted** — `test_abstract_never_transmitted` extended to also record + assert on
  NLM requests (the secret token never appears; NLM was actually queried — sanity, not vacuous). ✓
- **Gate the boost, not the listing + never elevates** — `test_build_profiles_wires_medline_indexing_fact`: a
  matched journal gets `indexed_in_medline=True` + the signal string, even at `weighting=1.0` it never appears in
  `elevated_for`; an unmatched candidate gets `False` with no fabricated signal. ✓
- **Deferred-list narrowing + no overclaim** — `test_build_profiles_no_composite_score_no_predatory` extended:
  "MEDLINE" no longer appears in `legitimacy_absent`; neither "Scopus" nor "PubMed" appears anywhere in the
  response shape at all — the wired signal claims exactly what it checks. ✓

### Result
**Security Audit: PASS (SP4 addendum).** SSRF is closed by the same id-validation + constant-host + bound-param
posture as DOAJ/SciELO; the endpoint has no request-time credential of any kind; fail-closed is proven for
malformed/unindexed/network-error cases alike; the live-confirmed rate-limit risk is closed by a self-contained
client-side pacing guard rather than an optional, easy-to-skip API key. A real overclaim (labeling a
MEDLINE-only check "PubMed/MEDLINE") was caught by live re-verification against a real, prominent journal before
ship and fixed by precise renaming, not a query change — the underlying query was always correct. No new secret,
dependency, schema, or migration. The Principles/A-A vetoes — never-elevates, gate-the-boost, honest narrowing,
precise labeling — are enforced structurally and pinned by 6 new tests in `tests/test_publishers.py`.
Live-verified against the real NCBI E-utilities endpoint before this audit was written (including a live 429
reproduction and the World Psychiatry MEDLINE/PubMed distinction), not assumed.

Wires a third `LEGITIMACY_DEFERRED` source: **AJOL** (African Journals Online), via a locally-mirrored,
**third-party CC-BY-4.0** compiled dataset (Alonso-Álvarez 2025, Zenodo) — not a live per-request AJOL API (none
exists publicly; a real OAI-PMH feed exists but is article-indexed and would need a heavy multi-page harvest,
deferred). Redalyc (a documented API blocked by a live TLS hostname mismatch on `api.redalyc.org`, reconfirmed
this session, plus a maintainer-only registration requirement) and Latindex (confirmed still closed, no public
API on any plausible endpoint) remain deferred.

### Trigger
- One new external fetch path: the Zenodo record-file download (`integrations/ajol/adapter.py`), mirroring TOP
  Factor's bulk-mirror shape exactly, not SciELO's live-per-ISSN shape.
- Two new endpoints: `GET/POST /methods/ajol/database[/refresh]` (mirrors the already-audited TOP Factor
  download-trigger shape).
- New schema + migration (`ajol_records`, `alembic/versions/0068_ajol_records.py`) — additive only, no
  destructive change, guarded create.

### Threat review
- **AJOL is not a live per-request call at all** — same posture as TOP Factor: a periodic (here, one-time)
  bulk-download mirror, downloaded only by an explicit Settings action, never auto-triggered from a Publishers
  run. `build_profiles`'s per-candidate AJOL lookups are pure local `SELECT`s against `ajol_records`, zero HTTP
  at request time.
- **Download bounds (rule #4).** `MAX_AJOL_BYTES` (2 MiB, comfortably above the confirmed real file size) and
  `MAX_AJOL_ROWS` (10,000, the real dataset has 739 rows) bound the streaming download; a malformed `is_diamond`
  cell parses to `None` (unknown) rather than a fabricated `False`; a row where both `eissn`/`issn_print` are
  missing (including the real file's `"NA"`-string encoding of "missing," not just an empty cell — the one real
  correctness bug this feature's design closes) is skipped, never stored with a bogus matchable key.
- **Untrusted external data, `source_url` (rule #4, new to this addendum).** Only values starting with the fixed
  `https://www.ajol.info/` prefix are kept; anything else (including a malformed or third-party-injected URL in
  a future re-download) is dropped rather than stored/rendered as a clickable link to an untrusted host.
- **No SQL written unsafely.** `ajol_repo.py` uses SQLAlchemy Core bound parameters throughout (`select`/
  `insert`/`delete`, no string interpolation); `replace_ajol_records` deletes-then-inserts in one transaction
  (a fresh snapshot is authoritative, matching `replace_top_factor_records`'s exact pattern).
- **Secret handling.** No secret at all — the Zenodo download URL is a fixed public record-file link, no
  credential, no auth header.
- **Supply-chain.** No new dependency — reuses `httpx` (already present).

### Principles / A-A vetoes (extended, same structural enforcement as SP1a/SP1b/SP2)
- **`jpps_status` renders plainly, including cautionary values — a deliberate, considered choice, not an
  oversight.** AJOL's own official rating ranges from positive (`1/2/3 Stars`) to cautionary (`Ceased`,
  `Inactive Title`). `APPROACH-AVOIDANCE.md`'s no-accusation veto is explicitly scoped to *individuals*; an
  AJOL-tracked journal's own publicly-published operational status is an institutional/venue fact, the same
  class already shown plainly today via `retraction_records.status`. Principles #6 (silence isn't a certificate)
  argues affirmatively *for* showing it — an unqualified "Indexed in AJOL" chip with a `Ceased` journal's status
  hidden would itself be a worse silence-as-certificate failure. Each status carries a plain-language `title=`
  tooltip gloss (informative, not editorial).
- **Elevate, don't denigrate — extended with a new gate.** `_AJOL_STAR_TIERS = {"1 Star", "2 Stars", "3 Stars"}`
  is the *only* set of `jpps_status` values that may ever appear in `elevated_for`; `Inactive Title`/`Ceased`/
  `Pending`/`NA`/`No Stars` structurally cannot (`_elevated_goods` checks membership in this frozen set, not an
  exclusion list — a cautionary/neutral status can never accidentally read as a boost by falling through a gap).
  A confirmed `is_diamond` gets its own independently-labeled `"AJOL-confirmed diamond OA"` string, kept apart
  from the existing DOAJ-derived diamond bucket (two independently-sourced claims stay provenance-legible).
- **Gate the boost, never the listing (extended to AJOL).** A journal with no AJOL data still appears unchanged
  — `ajol_status` is simply `None`.
- **Silence isn't a certificate (extended to AJOL).** `PublishersReport.ajol_coverage` (`{count, retrieved_at}`,
  the same shape as `top_factor_coverage`) disambiguates "no AJOL row for this journal" from "the mirror was
  never downloaded" at the report level.
- **A new honesty axis TOP Factor didn't need: "Download," never "Refresh."** Unlike TOP Factor (COS
  periodically republishes the same file) or DOAJ/SciELO (live), this Zenodo record is immutable and dated to a
  fixed February-2024 vintage — a future update would land at a *new* record id, not this one. Re-running the
  action always re-fetches byte-identical data. The UI button reads "Download database" (never "Refresh"), and
  the status line keeps the fixed `AJOL_SNAPSHOT_DATE` constant visibly separate from the local `retrieved_at`
  download timestamp — reusing TOP Factor's "as of {date}" copy verbatim would make an implicit false-freshness
  claim on every future click.
- **Crediting (`CREDIT-THE-LINEAGE.md`).** The credit block cites both Zenodo DOIs the dataset's own `readme.csv`
  names as the correct citation (the dataset `10.5281/zenodo.14899380` + its companion methods report
  `10.5281/zenodo.14900054`), framed explicitly as a third-party CC-BY-4.0 compilation of AJOL's own public
  records — never implying it's AJOL's own official feed.

### Negative-path checks (new, `tests/test_ajol.py` + `tests/test_publishers.py` extensions)
- **`"NA"`-marker regression** — `test_NA_marker_treated_as_missing_not_a_bogus_issn_key`: confirms no parsed
  record ever has `issn == "NA"` or `eissn == "NA"`, against a fixture reproducing the real file's encoding. ✓
- **Malformed `is_diamond` not fabricated** — `test_malformed_is_diamond_cell_is_none_not_fabricated_false`: a
  malformed cell parses to `None`; a real `"0"` cell parses to `False` cleanly; a `Ceased` status passes through
  unfiltered. ✓
- **Untrusted `source_url` dropped** — `test_source_url_outside_ajol_prefix_is_dropped`. ✓
- **Replace/lookup by issn-or-eissn + authoritative replace + never-downloaded-then-counts + injected-fetcher
  download + refresh endpoint (asserting `snapshot_date` present even before any download) + unknown-job 404** —
  `tests/test_ajol.py`, mirroring the full `test_top_factor.py` contract (10 tests total). ✓
- **Gate the boost, not the listing + star-tier-only elevation** —
  `test_build_profiles_wires_ajol_facts_and_elevates_only_star_tiers`: a `2 Stars` + confirmed-diamond match
  produces both `"AJOL 2 Stars rating"` and `"AJOL-confirmed diamond OA"` in `elevated_for` (plus the unfolded
  DOAJ-derived diamond string, proving the two stay separate); a `Ceased` match's `elevated_for` contains no
  AJOL string despite full weighting, while its `ajol_status`/`"Indexed in AJOL"` signal still render. ✓
- **Never-downloaded honesty** — `test_build_profiles_ajol_never_downloaded_is_honest`: an empty mirror reports
  `{"count": 0, "retrieved_at": None}` at the report level; every profile's `ajol_status` is `None`; no
  fabricated `"Indexed in AJOL"` signal appears. ✓
- **Deferred-list narrowing** — `test_build_profiles_no_composite_score_no_predatory` extended: "AJOL" no longer
  appears in `legitimacy_absent`; "regional indexes (Redalyc, Latindex)" replaces the old three-source string. ✓
- **Migration drift** — `test_ajol_records_table_is_at_head` (`tests/test_migrations.py`): the migration's
  columns match the SQLAlchemy model exactly (CI's `alembic check` gate). ✓

### Result
**Security Audit: PASS (SP3 addendum).** AJOL introduces zero request-time HTTP (a local mirror only, like TOP
Factor), with its one download path bounded, streaming, and fail-closed on oversize/malformed rows/network
error; the `"NA"`-marker missing-value bug was caught and fixed before ship, not after. No new secret, no new
dependency. The new schema is additive-only and migration-drift-tested. The Principles/A-A vetoes — including a
new structural (set-membership, not exclusion-list) star-tier elevation gate and the "Download never Refresh"
honesty distinction this source specifically requires — are enforced structurally and pinned by 12 new tests
across `tests/test_ajol.py` + `tests/test_publishers.py` + `tests/test_migrations.py`. Live-verified against the
real Zenodo-hosted CSV (739 rows, confirmed 11 real all-`"NA"` rows) before this audit was written, not assumed.
