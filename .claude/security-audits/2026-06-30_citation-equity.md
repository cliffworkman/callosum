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
