# Security Audit — Retraction Watch DB bulk source (SP2), inc 132

**Date:** 2026-06-26
**Feature:** Download the Crossref-hosted Retraction Watch Database (CC0) as CSV into a local
`retraction_records` mirror, and match every library DOI against it offline as a **third checker** for the
retraction producer. New endpoints: `GET /methods/retraction/database`, `POST`/`GET
/methods/retraction/database/refresh`. New table (migration 0017).

**Audit-gate triggers:** #1 (new endpoints), #2 (a new external fetch — the CSV download), #3 (a new
write path — the bulk table replace + the migration), #5 (net-new feature 3+ files). Not #6 (no new dependency
— stdlib `csv`).

## Threat review

- **The download.** https-only, **fixed host** (`api.labs.crossref.org/data/retractionwatch`) via the existing
  httpx pattern; a streaming fetch with a **size cap** (`MAX_RW_BYTES` = 80 MiB) enforced **mid-stream** (aborts
  before exhausting memory); a timeout; **fail-closed** → `RetractionWatchUnavailable` mapped to a job `error`
  (never a 500). The contact email comes from `CALLOSUM_CROSSREF_MAILTO`; **absent → a clear error**, never a
  silent broken state. The URL is built from the env mailto only (`quote`d), not from request data. PASS.
- **Untrusted CSV parsing.** The CSV is treated as **untrusted** even though the host is trusted: parsing is
  tolerant (case-insensitive header map), **caps rows** (`MAX_RW_ROWS`), **skips** rows with no `OriginalPaperDOI`
  and any unrecognized / **Reinstatement** nature (an un-retraction is never a finding), and coerces fields with
  defaults. A malformed row degrades to "skipped", not a crash. PASS.
- **SSRF.** The only URL constructed is the fixed RW endpoint (server fetch). The per-record `notice_url` is
  **derived-only** (`https://doi.org/<notice_doi>`) and **never fetched** — it's a client-side link the user may
  click. No attacker-controlled URL is ever requested server-side. PASS.
- **Storage / SQL.** `replace_retraction_records` = `DELETE` + a bound-param `executemany` `INSERT` in one
  transaction (rule #3). `original_doi` is normalized (lower) before store + lookup. The migration is additive +
  guarded (mirrors 0016). The replace-all model means a record withdrawn upstream disappears on the next refresh
  (no stale accusation). PASS.
- **Output encoding.** The RW `reason` / `nature` render via React text nodes (escaped) — the reason appears in
  the FactMark tooltip + the payload; no `dangerouslySetInnerHTML`. PASS.
- **Data egress.** Public **bulk metadata** (the CC0 RW DB) — explicitly **not** the Gemini library-text gate; no
  library text leaves the machine. The headed run (egress unset) recorded **0** genai-host requests. PASS.
- **Resource caps.** Download byte cap + parse row cap; the table is ~tens of thousands of small rows (fine in
  SQLite); the match is an indexed equality lookup. PASS.
- **Secret handling.** No new secret (reuses the Crossref polite mailto). PASS.
- **Supply chain.** No new dependency (stdlib `csv`/`io`). PASS.
- **Authorization / deployment.** The refresh is a server-side outbound fetch on the user's machine (127.0.0.1).
  A remote caller could trigger a large download — covered by the standing "before hosted deploy: add auth +
  rate-limiting + re-review server-side fetches" note (the inc-87/98 server-side-read gate).

## Principle / value posture

- Same FACT producer as SP1 — a registry record relayed verbatim (no LLM), evidence-carried (RW adds
  reason/date/notice), **no accusation** (a filter, not an author signal), silence-honest (the SP1 status row is
  unchanged; RW only adds coverage). **Reinstatements are never surfaced** (the opposite of a finding). The
  value-level note (A-A): a **one-time public-data bulk download**, the user's machine, **manual-triggered**, with
  the snapshot date (`retrieved_at`) shown — no covert/standing data movement.

## Negative-path checks (run)

- mailto absent → `RetractionWatchUnavailable` → the refresh job reports `error` with a clear message, never 500
  (`test_mailto_absent_fails_closed` + the job's `except RetractionWatchUnavailable`).
- a `Reinstatement` / no-DOI CSV row → **skipped** (`test_parse_maps_natures_and_skips_reinstatement_and_no_doi`).
- a later (smaller) download removes withdrawn records (`test_replace_is_authoritative_removes_withdrawn`).
- Headed run (egress unset): **0** genai-host requests; **0** console/page errors.

## Result

**Security Audit: PASS.** Fixed-host size/row-capped download, untrusted-CSV-tolerant parse, derived-only notice
URLs (no SSRF), bound-param replace, escaped output, fail-closed on mailto-absent, reinstatements never flagged,
no Gemini egress, no new dependency.
