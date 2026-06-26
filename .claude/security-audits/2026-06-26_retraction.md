# Security Audit — Retraction producer (SP1: Crossref + OpenAlex), inc 131

**Date:** 2026-06-26
**Feature:** The first findings producer. For each library paper's DOI, query multiple sources (Crossref +
OpenAlex in SP1) for a retraction / correction / expression-of-concern, merge, and persist a FACT in
`paper_findings` + a per-paper check-status row in `open_science_signals` (which also powers the library
"Retracted" filter). New endpoints: `GET /papers/{id}/retraction`, `POST`/`GET /methods/retraction/run`,
`GET /methods/retraction/summary`.

**Audit-gate triggers:** #1 (new API endpoints), #2 (a new use of external fetches — Crossref/OpenAlex
retraction reads), #5 (net-new feature spanning 3+ files). Not #3 (no file ingest/write), not #6 (no new dep).

## Threat review

- **Input validation.** `paper_id` + `job_id` are path params (FastAPI coercion; non-int → 422). The batch
  reads DOIs from the DB (trusted) and normalizes them (`_normalize_doi`) before the lookups. The **external
  responses are untrusted** and parsed defensively: `_parse_retraction` only reads `message.update-to` when it
  is a list, skips non-dict entries, maps `type` via a fixed allowlist (unknown types ignored), and coerces
  `DOI`/`label`/`updated` with guards; OpenAlex's `is_retracted` is read with `is True` (only an explicit boolean
  flags). A non-200 / non-dict response → None. PASS.
- **SSRF / external calls.** All fetches go only to the **fixed** Crossref (`api.crossref.org`) + OpenAlex
  (`api.openalex.org`) hosts via the existing audited adapters — never to an attacker-controlled URL. The
  `notice_url` in a FACT is **only ever derived** as `https://doi.org/<normalized notice_doi>` (never a URL taken
  verbatim from the response and never server-fetched); it is rendered as a client-side `<a target="_blank"
  rel="noopener noreferrer">` the user may click (browser navigation, not a server request). PASS.
- **Output encoding.** Finding payload + status render via React text nodes (auto-escaped); no
  `dangerouslySetInnerHTML`. The notice link's `href` is the derived doi.org URL. A malicious registry string
  can't inject script. PASS.
- **Data egress.** Public **DOI metadata** lookups only (the inc-49/74 posture — DOI resolve / OA acquisition),
  explicitly **not** the Gemini library-text gate; no library text leaves the machine. The headed run
  (`drive_inc131_retraction.py`, egress unset) recorded **0** requests to any genai/Gemini host. PASS.
- **Resource caps / fail-closed.** The batch is bounded by the live-library size; per-DOI responses are cached
  in `external_api_cache` (re-runs hit cache). Each source runs best-effort — a checker raising is **skipped**
  (`detect_retraction` try/except per checker), never aborting the run or 500-ing; a source with no record
  returns None (honest "none found"), and a paper with no DOI is "unchecked" (never implied clean). PASS.
- **Secret handling.** No new secret. The optional polite-pool `mailto` (Crossref/OpenAlex) already comes from
  env. PASS.
- **SQL.** SQLAlchemy Core bound params throughout: the signals OR-REPLACE upsert, `findings_repo.upsert_findings`,
  and the `SIGNAL_FILTERS["retraction-retracted"]` bound IN-subquery (the key indexes a fixed allowlist, never
  interpolated — rule #3). PASS.
- **File-path safety.** No filesystem access. PASS.
- **Supply chain.** No new dependency (reuses the Crossref + OpenAlex adapters). PASS.
- **Authorization.** Local single-user model unchanged. The batch endpoint is unauthenticated like every other
  endpoint (the standing "before hosted deploy: add auth + rate-limiting" note covers this globally — and a
  remote caller could trigger many outbound DOI lookups, so the batch is part of that gate).

## Principle / value posture (the rule-#9 gate, run)

- **Deterministic substrate, model only relays (#4):** the FACT is the *registry's* record (Crossref/OpenAlex),
  relayed verbatim — no LLM, no inference, no callosum-invented verdict.
- **Evidence carried (#1/#8):** the FACT lists its flagging `sources` + links the **notice** (inspectable).
- **FACT vs CANDIDATE (#3):** a retraction is a FACT (`review_state=None`), not a "candidate to confirm".
- **Silence is not a certificate (#6):** a checked-clean paper gets a positive `none` status; a no-DOI paper is
  `unchecked`; the UI never shows "unchecked" as "clean".
- **Signal not verdict / no opaque score (#2/#7):** the "N retracted" chip is a **filter** count, not a rank.
- **No accusation (A-A veto):** it reports the registry record + links the notice; it never labels an author, and
  there is no author-level / reputation aggregate. **Declined easy paths:** an "author has N retractions"
  reputation signal; treating unchecked papers as clean.

## Negative-path checks (run)

- `GET /papers/{missing}/retraction` → **404** (`test_retraction.py`).
- A checker raising → skipped; the other source still flags; the run completes (`test_detect_skips_a_raising_checker`).
- A previously-retracted paper that the registry no longer flags → the FACT is **superseded** + the status flips
  to `none` (`test_apply_unretraction_supersedes_fact`).
- No DOI → `unchecked`, no source consulted (`test_detect_no_doi_is_unchecked_and_calls_nothing`).
- Headed run (egress unset): **0** genai-host requests; **0** console/page errors.

## Result

**Security Audit: PASS.** Local public-metadata lookups, defensive untrusted-response parsing, derived-only
notice URLs (no SSRF), escaped output, bound-param SQL, fail-closed per source, no new dependency, no Gemini
egress. SP2 (the Retraction Watch DB bulk download) will get its own audit for the new fetch/storage pattern.

## Addendum — on-import auto-check (inc 134)

`auto_check_retractions(conn, paper_ids, *, checkers)` runs the **same** detect+apply over newly-imported papers
(the scan + citation-import jobs), using `app.state.retraction_checkers`. No new fetch type/host (the inc-131
Crossref+OpenAlex checkers + the inc-132 RW mirror) — the threat review above is unchanged. New considerations:
- **Best-effort isolation:** each paper's check is wrapped in `try/except` (on top of `detect_retraction`'s
  per-source guard), so a source error / a missing row **never aborts the import** or 500s — the paper is simply
  left unchecked (honest, not "clean").
- **Cost:** bounded by the count of *new* papers per import; the Crossref checker reads the cache the enrich just
  populated (free), the RW checker is offline, OpenAlex is one cached lookup — marginal on an already-async job.
- No new endpoint, no migration, no egress beyond the already-audited DOI metadata lookups. **Still PASS.**
