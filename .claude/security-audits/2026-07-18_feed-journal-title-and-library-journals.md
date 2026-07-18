# Security audit — Feed: journal-by-title source + `GET /feed/library-journals` (inc 295)

**Date:** 2026-07-18
**Feature:** follow journals by **title** (`discovery/journal_title_source.py`, replacing the ISSN source) + a new
read-only endpoint `GET /feed/library-journals` (`routers/feed.py` + `feed_repo.list_library_journals`) that powers a
"Suggest" modal + follow typeahead from the user's own library journals. Branch `feature/library-ux-polish`.
**Triggers:** a new API endpoint + a new external-fetch pattern (Crossref `/journals`).

## What's new

- `GET /feed/library-journals` → `{journals:[{journal,count}]}` — distinct `papers.venue` (live library) with paper
  counts, most-frequent first. **Read-only, local, no egress.**
- `JournalTitleFeedSource.fetch(title)` — resolves a journal **title → ISSN** via Crossref `/journals?query=<title>`
  (top match), then reuses the audited ISSN→works fetch; falls back to `/works?query.container-title=<title>`. Egress
  only on the feed's opt-in **Refresh** (not the Gemini library-text gate).

## Threat review

- **Input validation (rule #4):** the follow `value` (journal title) is capped at 500 (pydantic
  `SubscriptionRequest.value`) and again at `MAX_TITLE_CHARS=300` in `fetch` (blank/oversized → no fetch). The
  library-journals endpoint takes **no input**.
- **SSRF / external calls:** the title reaches Crossref **only as a URL-encoded query param** (`params={"query":
  title}` / `{"query.container-title": title}` via httpx — never concatenated into the host/path). Hosts are the
  fixed, **already-audited** `api.crossref.org/journals` + `/works` constants; httpx `timeout` set; non-200 →
  `[]` (fail-closed). No user-controlled URL. The `/journals` endpoint is the same host/auth posture as the existing
  `/works` fetch — no new host, no new secret.
- **Injection (rule #3):** `list_library_journals` is SQLAlchemy Core bound/parameterized (`select(papers.c.venue,
  func.count()).group_by(...)`) — no string SQL, no request data in identifiers.
- **Egress posture (invariant #3):** `library-journals` is local (reads `papers.venue`); the journal poll egresses
  to Crossref **only on Refresh**, the feed's existing opt-in public-metadata channel — **not** the Gemini gate. No
  library *text* leaves; only a journal title (the user's own follow input) is sent to resolve the ISSN.
- **Secret handling:** none new (the optional Crossref `mailto` is the existing polite-pool identifier, not a secret).
- **Resource caps:** works `rows` clamped to ≤50; the ISSN lookup requests `rows=1`; library-journals is a single
  bounded GROUP BY.
- **Output encoding:** JSON via pydantic/FastAPI; the endpoint echoes the library's own venue strings + integer
  counts (no reflection into HTML server-side).
- **Supply-chain:** no new dependency (httpx already used).

## Negative-path checks (covered by `tests/test_feed.py`, inc 295)

- `JournalTitleFeedSource.fetch("")` → `[]` (blank title → no fetch); an oversized title (>300) → `[]`.
- Title with an ISSN match → the exact `filter=issn:` works path; **no** ISSN match → the fuzzy
  `query.container-title` path (both mapped via the audited `message_to_item`).
- `GET /feed/library-journals` → venues with counts, most-frequent first; a paper with **no venue is excluded**;
  empty library → `[]`. No external request in the endpoint.

## Verdict

New endpoint is read-only/local/parameterized; the journal-title fetch reuses the audited Crossref host with a
validated, URL-encoded query param (no SSRF), egress only on the existing opt-in Refresh. No new dependency, no new
secret, no library-text egress.

**Security Audit: PASS**
