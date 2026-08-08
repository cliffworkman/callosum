# Security audit — Citation-equity audit (inc 227, backlog #25)

**Feature:** an identity-agnostic, structural audit of a library paper's reference list (its OpenAlex
`referenced_works`), shown against a sample of the paper's field. New async endpoint
(`POST`/`GET /methods/citation-equity/run`), a new OpenAlex egress shape (a field-sample query + reading more
per-work fields), a pure analyzer, and a new METHODS panel. **No new ingestion path** (the input is a library
paper — *simpler* than the spec's word-processor-bibliography assumption), **no new dependency, no migration.**

## Threat review

- **Input validation / boundary (rule #4).** The endpoint takes only `{paper_id: int}` (Pydantic). The worker
  reads the paper's stored `doi`/`csl_json`/`first_author_family_name` from the DB. The OpenAlex responses are
  untrusted: every parse (`_meta_from_work`, `fetch_field_sample`) is defensive (`isinstance` guards, `.get`
  with defaults) and fail-closed (a bad/absent field → None/[]; a per-reference fetch error is skipped + counted
  in coverage, never fatal). The analyzer caps inputs (`MAX_REFS=1000`, `MAX_FIELD=1000`, `MAX_BASIS=10`); the
  reference fetch is already capped (`MAX_REFERENCED=500`) and the field sample at 200.
- **SSRF / external calls.** All OpenAlex requests go to the constant `OPENALEX_BASE_URL`
  (`https://api.openalex.org/works`) via the existing audited client. The new `fetch_field_sample` builds its
  query from a **`topic_id` validated `^T\d+$` before any request** (so a topic id can never reach the URL as
  anything but a known-shape token), passed as a bound `filter` param (not the host/path). The focal DOI is the
  paper's own stored DOI, resolved by the existing `_endpoint_for` (the inc-49/210 posture). httpx timeouts are
  set; the fetcher is fail-closed (a network error → cached error → None/[], never raises).
- **Output encoding.** The report is JSON (FastAPI). The frontend renders strings as React text (no
  `dangerouslySetInnerHTML`); the basis lines (titles/venues/countries from OpenAlex) are inert text. The
  inline bar width is a computed numeric `%` (no injection surface).
- **Injection.** No SQL is built from external input — the worker uses SQLAlchemy Core bound parameters
  (`select(...).where(papers.c.id == paper_id)`); rule #3 holds.
- **Secret handling.** No secret introduced. The OpenAlex polite-pool `mailto` is the existing
  `resolved_mailto("CALLOSUM_OPENALEX_MAILTO")` (a contact email, not a credential), never logged.
- **Data egress.** Egress is **public bibliographic metadata** — a DOI + an OpenAlex topic id leave the machine
  (the same posture as the inc-87/183/210 OpenAlex/Crossref calls). It is **NOT** the Gemini library-text gate
  (`CALLOSUM_ALLOW_DATA_EGRESS`): no library text, no abstract, no LLM. The audit is **user-initiated** ("Run
  audit" — never auto-run on section open), so a metadata fetch only happens on an explicit click. Cached, so
  re-runs are cheap and re-fetch nothing.
- **No identity inference (the load-bearing line).** There is **no gender/race/sex code path** anywhere in the
  core — proven behaviorally (`test_no_identity_inference_in_core`: injecting `gender`/`sex`/`race` fields into
  the inputs changes nothing) and statically (`test_analyzer_source_has_no_gender_keying`: the analyzer never
  keys on those fields). The gender/identity module is **deferred behind its own gate and absent** (the spec).
  The "Global South" grouping is a documented, contestable convention shown with the full country breakdown — a
  geographic affiliation signal about institutions, never an attribute inferred about a person; no per-author
  label is ever produced.
- **Resource caps.** Bounded as above; one field-sample query + ≤500 cached per-reference fetches per audit. The
  job is ephemeral + process-local (`JobStore`); no table, no migration.
- **File-path safety.** No filesystem path is built from input.
- **Supply-chain.** No new dependency.

## Negative-path checks (covered by `tests/test_citation_equity.py`)

- `POST /methods/citation-equity/run` for a missing paper → **404**; for a no-DOI paper → **422** (no fetch).
- `GET …/run/{job_id}` for an unknown job → **404**.
- A focal work with empty `referenced_works` → a graceful report (`references_total == 0`), the UI shows
  "nothing to audit" (not an error).
- A focal work with no `primary_topic` → no field baseline; the own-shape signals still compute (no crash).
- `fetch_field_sample` with a non-`^T\d+$` id → `[]` (no request issued); a non-200 response → `[]` (fail-closed).
- A reference whose OpenAlex fetch 404s → skipped, counted in the honest coverage line, never fatal.

## Result

**Security Audit: PASS.** Public-metadata egress (not the Gemini gate); SSRF-safe (constant host + validated/bound
topic id + the paper's own DOI); fail-closed parsing; bounded inputs; bound-param SQL; no new ingestion path /
dependency / migration / secret. No identity inference in the core (the gender module is deferred + absent),
proven by test.

---

## Increment 228 addendum — overlooked-work remediation (SP2)

The Citation-equity panel gains a **"Find overlooked work"** action: surface topically-relevant work the reference
list OMITS, ranked by a **local** scientific-paper embedding cosine, with a one-click **metadata-only add**.
New async endpoint `POST`/`GET /methods/citation-equity/overlooked` (the inc-227 JobStore scaffold;
`app.state.overlooked_jobs`); a new pure ranker `methods/overlooked_work.py`; OpenAlex candidate machinery added to
`adapter.py`. **No migration; no new dependency.**

- **SSRF / external calls.** The candidate pool is the focal paper's OpenAlex `related_works` (read from the cached
  focal blob) ∪ the topic sample. Both reach OpenAlex only as **validated, bound** tokens: `fetch_works_by_ids`
  builds a `?filter=openalex_id:W1|W2|…` from ids each validated **`^W\d+$` before the request** (≤MAX_BYIDS=50;
  invalid ids dropped → no request if none valid), and `fetch_topic_candidates` reuses the inc-227
  `primary_topic.id:^T\d+$`-validated field-sample call (just parses the abstract too). Constant host; bound
  `filter` params; httpx timeouts; fail-closed (any non-200/error → []).
- **The add path = metadata only, NO PDF (A-A no-paywall-circumvention veto).** ＋ Add calls the already-audited
  inc-183 `POST /discovery/save` → `save_item` — deduped (`find_existing_paper_by_identity`), `imported_source=
  "discovery-import"`, and **fetches no PDF** (the OA-acquire lane is untouched). A candidate is a paper the user
  chooses to add as metadata; **nothing auto-inserts into the document and nothing is dropped** (there is no
  "remove citation" path anywhere — structural).
- **No identity inference / no opaque score.** The ranker (`overlooked_work.py`) has **no gender/race/sex code
  path** — proven behaviorally (`test_no_identity_in_ranker`: injecting `gender`/`sex`/`race` into a candidate
  changes the output not at all). Candidates are ranked by **topical cosine, never by citation count** (which
  would amplify the Matthew effect the audit measures); the displayed "topical match 0.NN" is callosum's own
  inspectable cosine + the shared-concept "why", never a verdict (#2/#7/#8).
- **Egress / the embedding.** The focal + candidate **title+abstract** are embedded **locally** (SPECTER v1
  `sentence-transformers/allenai-specter` — loaded through the existing sentence-transformers stack; a ~440 MB
  **model download** on first use, **not a new package** → no supply-chain change). Only DOIs / W-ids / the topic
  id leave the machine (the OpenAlex metadata fetches, cached) — **public bibliographic metadata, NOT the Gemini
  library-text gate**. The action is user-initiated (a click), never auto-run.
- **Resource caps.** MAX_RELATED=50, MAX_BYIDS=50 (one batch call), topic sample ≤200, MAX_CANDIDATES=1000 to
  embed, top_k=12, relevance threshold 0.55 (below-bar candidates are not shown — no fabricated relevance). One
  batch fetch + one topic fetch (both cached) per run; the embedding is one local batch.
- **Negative paths** (`tests/test_overlooked_work.py`): 404 (missing paper) / 422 (no DOI); unknown job → 404;
  no related-works + empty topic → an honest empty report (`shown == 0`); an already-cited work that is also
  "related" is **excluded**; `fetch_works_by_ids` drops non-`^W\d+$` ids and fail-closes on non-200.

**Security Audit (inc 228 addendum): PASS.** Public-metadata egress (not the Gemini gate); SSRF-safe (validated +
bound ids/topic); the add path is metadata-only with no PDF fetch (no paywall circumvention); local embedding,
no new dependency; bounded; no identity inference (proven by test); add-only / no-drop by construction.

---

## inc 229 addendum — geography signal + nationality extraction REMOVED (values rework)

The geography ("Global South spread") signal and the gender framing were removed (rejected on principle: sorting
cited authors into a group to measure bias reifies the category). This is a **removal + narrowing**, no new audit
trigger: no new endpoint/fetch/dependency/ingestion. The egress surface is **strictly smaller** —
`integrations/openalex/adapter.py::_meta_from_work` **no longer extracts `country_codes`** at all (the data layer no
longer collects author nationality), and the analyzer carries no `GLOBAL_NORTH`/`country_code`/gender/race/sex
keying (now enforced by a static guard test `test_analyzer_source_has_no_people_categorization`). Same per-reference
+ field OpenAlex fetches as inc 227/228 (public metadata, cached, SSRF-safe, NOT the Gemini gate); the panel was
renamed "Citation concentration"; the API path keeps the historical `/methods/citation-equity/*` slug.

**Security Audit (inc 229 addendum): PASS.** Removal + egress-narrowing; no new surface; no-people-categorization
enforced structurally (data layer no longer extracts nationality) + guard-tested.

---

## inc 457 addendum — self-citation field baseline wired in (bounded new egress, no new endpoint)

Self-citation was the one signal whose `field_pct` was hardcoded `None` since inc 227/229. Inc 456 built and
empirically calibrated a reusable count-only primitive (`OpenAlexClient.fetch_self_citation_hit_count`,
audited implicitly as part of the existing `fetch_field_sample`/`fetch_works_by_ids` egress shape — same host,
same validated-id posture). Inc 457 wires that primitive into the live `POST /methods/citation-equity/run` job
via a new router-local helper, `_compute_self_citation_baseline`. **No new endpoint, no new dependency, no
migration** — this is additional egress volume on an already-audited call shape, not a new surface.

- **SSRF / external calls.** `fetch_self_citation_hit_count` reuses the same constant `OPENALEX_BASE_URL` host
  and the same **validated-before-request** id discipline as `fetch_works_by_ids`: reference ids are checked
  `^W\d+$` and author ids `^A\d+$` before being interpolated into a bound `filter=openalex_id:{...},
  authorships.author.id:{...}` param (never the host/path); invalid ids are dropped, and a chunk with no valid
  ids issues no request. Chunked at `MAX_BYIDS=50`; httpx timeouts inherited from the shared client; fail-closed
  (`None` on any non-200/parse error — a paper is skipped, never silently counted as a zero self-citation rate).
- **Resource caps (the dual cap, a deliberate, disclosed design choice).** `_compute_self_citation_baseline`
  stops at whichever comes first: `SELF_CITATION_BASELINE_TARGET_N = 40` field papers with a resolved rate, or
  `SELF_CITATION_BASELINE_MAX_CHECKS = 100` raw count-queries attempted. Inc 456's real study found "computable"
  field-paper coverage (a field paper having both a reference list and author ids) varies 18%–74% by field —
  without the second cap, a low-coverage field could otherwise drive up to 200 count-queries (one per field
  sample paper) per interactive audit run. The max-checks cap bounds worst-case added egress to a predictable
  ceiling regardless of field coverage; a thin baseline (fewer than 40 resolved) is disclosed via the visible
  "N papers checked" count, never hidden or padded.
- **Data egress.** Same posture as the rest of this file: public bibliographic metadata (reference/author
  OpenAlex ids + a count), not the Gemini library-text gate. User-initiated only (the existing "Run audit"
  click); no auto-run on section open.
- **No identity inference.** The baseline is a count over reference/author id sets — no name, no
  gender/race/nationality field is read or extracted by this path (the inc-229 removal stands; the new query
  reads only `openalex_id` and `authorships.author.id`, both bare identifiers).
- **Negative paths** (`tests/test_citation_equity.py`): a field paper missing either `referenced_works` or
  `author_ids` is skipped (never fabricated as 0% or counted toward N); an id that fails `^W\d+$`/`^A\d+$` drops
  from its chunk pre-request; the target-N cap stops early even with more computable papers available (proven:
  exactly 40 requests issued, not 50); the max-checks cap stops at exactly 100 raw attempts even with 110
  eligible papers available, correctly reporting a thin (3-paper) baseline rather than blocking or padding it.

**Security Audit (inc 457 addendum): PASS.** Bounded new egress volume on an already-audited call shape (same
host, same validated/bound-id posture, same fail-closed parsing); no new endpoint/dependency/migration; the
dual cap is a disclosed, tested design choice, not an unbounded cost; no identity inference; user-initiated
only.
