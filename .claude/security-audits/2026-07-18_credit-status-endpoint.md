# Security audit — `POST /library/credit/status` (credit-the-lineage presence check)

**Date:** 2026-07-18
**Feature:** the read-only DOI-presence endpoint backing the credit-the-lineage "＋ add missing to library"
button state (inc 293, branch `feature/library-ux-polish`). Retroactive stub — the audit gate (new API
endpoint) was not opened during implementation; filled on review.
**Files:** `app/backend/api/routers/library.py` (`CreditStatusRequest`/`CreditStatusItem`/`CreditStatusResponse`
+ `credit_status`), consuming `persistence/repository.find_existing_paper_by_identity`; caller
`app/frontend/js/05_method_credit.jsx` (`MethodCreditButton`).

## What it does

Given a list of DOIs, returns `[{doi, present: bool}]` — whether each DOI already exists in the local library —
so the credit button can import **only the missing** source papers and label itself honestly. Purely a read; it
imports nothing (import stays on the existing `/library/import`).

## Threat review

- **Input validation (boundary, rule #4):** `dois: list[str]` is capped at **100** items (pydantic
  `max_length=100`). Each DOI is normalized (strip, lowercase, drop `https://doi.org/` + `doi:` prefixes) and
  **rejected with 422 if > 255 chars**; blanks dropped; duplicates collapsed before any DB work.
- **Injection (rule #3):** presence is resolved via `find_existing_paper_by_identity(conn, doi=...)` — the
  canonical SQLAlchemy Core **bound-parameter** identity lookup. No string interpolation; no table/column names
  from request data.
- **SSRF / external calls:** **none.** The handler only reads the local SQLite DB (`engine.begin()`); it makes
  no outbound request. Egress gate (invariant #3) not implicated — no library text or DOI leaves the machine.
- **Secret handling:** none (no keys, no tokens touched).
- **Resource caps:** bounded work — ≤100 identity lookups per call, each an indexed point lookup; DOI length
  capped at 255. No unbounded scan, no pagination hole.
- **Output encoding:** returns booleans + the normalized DOI echoed back, serialized by pydantic/FastAPI as
  JSON; no server-side reflection into HTML. The DOI echo is the caller's own normalized input.
- **File-path safety:** no filesystem access, no path construction.
- **Supply-chain:** no new dependency.
- **Auth surface:** rides the existing `AccessControlMiddleware` (default-off; when Remote access is on it needs
  the bearer token like every non-exempt route). It is **not** on the cloudflared cite-only allowlist, so it is
  not reachable via the single-user tunnel — appropriate (it's a desktop-app convenience read).

## Negative-path checks (run 2026-07-18)

- `dois` with **101 items** → rejected by pydantic `max_length` (**422** at the boundary). ✓
- **Normalization + dedupe:** `["10.1/abc", "https://doi.org/10.1/ABC", "DOI:10.1/abc"]` → one unique
  `10.1/abc` (case + prefix variants collapse). ✓
- **> 255-char DOI** → the endpoint's length guard raises **422**. ✓
- Normal small batch → accepted; presence resolved per-DOI via the parameterized lookup. ✓
- Covered by `tests/test_citation_import.py` (endpoint behavior) and the frontend assembly guard
  (`MethodCreditButton` present/wired).

## Verdict

Read-only, local, parameterized, input-capped, no egress, no new dependency. No new attack surface beyond a
bounded library-membership read.

**Security Audit: PASS**
