# Retraction Watch DB — SP2 design (the bulk third source)

**Increment:** 132 (SP2 of the retraction arc; SP1 = inc 131, Crossref + OpenAlex per-DOI).
**Goal:** Add the **Retraction Watch Database** (Crossref-hosted, CC0) as a **third checker** for the retraction
producer — the richest source (nature, date, **reason**, notice). Download it once into a local table, match every
library DOI **offline**, refresh on demand. The merge layer already accepts another checker, so this is additive.

## Why / gates

- **Audit gate** — a new external fetch (the CSV download) + a new file-write/storage path (the table) + a new
  migration. → `.claude/security-audits/2026-06-26_retraction-watch.md`.
- **Principles** — same FACT producer as SP1 (a registry record relayed verbatim; evidence-carried; no
  accusation; silence ≠ clean). No new claim *type*, so the posture is established; the value-level note is the
  **bulk download + local storage** (a one-time public-data fetch, the user's machine, manual-triggered).
- Egress: **public bulk metadata** (the RW DB), uses the existing `CALLOSUM_CROSSREF_MAILTO` — **not** the Gemini
  library-text gate.

## Data source

- **Crossref Labs Retraction Watch endpoint:** `https://api.labs.crossref.org/data/retractionwatch?<mailto>` →
  the full RW database as a **CSV** (~tens of MB). The endpoint expects a contact email (polite pool); we pass
  `CALLOSUM_CROSSREF_MAILTO`. **Absent mailto → the refresh fails closed** with a clear message ("set
  CALLOSUM_CROSSREF_MAILTO to download the Retraction Watch database"), never a silent broken state.
- **CSV schema (the columns we read; verify against a real download — see Verification):** `OriginalPaperDOI`
  (the match key), `RetractionNature` (→ status), `RetractionDate`, `Reason`, `RetractionDOI` (notice), `URLS`.
  Parsing is **column-name-driven + tolerant** (case-insensitive header match + a small alias map) so a minor
  header change degrades to "field absent", not a crash. `RetractionNature` → status:
  `Retraction`/`Withdrawal`/`Removal` → `retracted`; `Correction`/`Erratum` → `correction`; `Expression of
  concern` → `concern`; **`Reinstatement` and unrecognized natures → skipped** (a reinstatement is NOT a
  retraction; never flag it).
- A paper can have multiple RW rows (multiple notices); we store each row, and the checker picks the
  **most-severe** status for a DOI.

## Architecture (additive over SP1)

### Storage — `retraction_records` table (migration 0017, additive/guarded)

Columns: `id`, `original_doi` (String, indexed — normalized lower), `status` (mapped), `nature` (raw label, for
display), `date` (String|null), `reason` (Text|null), `notice_doi` (String|null), `notice_url` (String|null),
`retrieved_at` (String — the download timestamp). Guarded create (mirrors 0016). A separate single-row sense of
"as of" is just `MAX(retrieved_at)` / `COUNT(*)` over the table (no extra table).

### Data access — `app/backend/persistence/retraction_repo.py` (new)

- `replace_retraction_records(conn, records, *, retrieved_at)` — DELETE all + bulk INSERT in one txn (the RW DB
  is authoritative; a withdrawn record must disappear). `records` = parsed dicts.
- `lookup_retraction_record(conn, doi) -> dict | None` — rows for a normalized DOI, pick most-severe → a signal
  dict `{status, nature, date, reason, notice_doi, notice_url}` or None.
- `retraction_db_status(conn) -> {count, retrieved_at}` — for the as-of line.

### Download adapter — `integrations/retraction_watch/adapter.py` (new)

- `RetractionWatchClient(fetcher=…, mailto=…)` with an **injectable** `fetcher` Protocol (size-capped https GET,
  mirrors `acquisition/fetch.py::PdfFetcher`) → returns the CSV **text**; `MAX_RW_BYTES` cap (~80 MiB),
  https-only, timeout, fail-closed.
- `parse_retraction_csv(text) -> list[dict]` (stdlib `csv` — **no new dependency**; tolerant header map; row +
  byte caps; skips rows with no `OriginalPaperDOI` or an unrecognized/reinstatement nature). Returns the records
  for `replace_retraction_records`.
- `download_retraction_database(client, conn) -> int` — fetch → parse → replace → return the record count.

### The third checker (`methods/retraction.py`)

- `_retraction_watch_fetch(conn, paper)` → `RetractionSignal(source="retraction-watch", **row)` via
  `retraction_repo.lookup_retraction_record`. `RETRACTION_WATCH_CHECKER = RetractionChecker("retraction-watch", …)`.
- **`DEFAULT_CHECKERS = [RETRACTION_WATCH_CHECKER, CROSSREF_CHECKER, OPENALEX_CHECKER]`** — RW **first** so its
  richer detail wins `merge_signals.first(...)`. If the table is empty (never downloaded), the RW checker returns
  None for everything → the SP1 sources still work (graceful).

### Endpoints (`routers/methods.py`)

- `POST /methods/retraction/database/refresh` + `GET /methods/retraction/database/refresh/{job_id}` — async
  download job (`app.state.retraction_db_jobs` + an injectable `app.state.retraction_watch_client` for tests),
  returns a count on done; mailto-absent / fetch error → job `error` with a clear detail (never 500).
- `GET /methods/retraction/database` → `{count, retrieved_at}` (the as-of line).

### Frontend (`08_methods_findings.jsx`)

In the Review section's retraction area: a **"Retraction Watch database: N records · as of <date>"** line + a
**"Refresh database"** button (async, poll; on done → refresh the line + the chip). When the table is empty:
"Retraction Watch database: not downloaded — Refresh to enable the richest source." Tokens-only CSS.

## Honesty / Principles invariants (unchanged from SP1, re-asserted)

- A retraction is a **FACT** relayed from the registry; RW adds **reason/date** detail, still verbatim.
- **Reinstatements are never flagged** (an un-retraction is the opposite of a finding).
- Silence ≠ clean (the SP1 status row still records checked/none/unchecked); the RW source only *adds* coverage.
- No accusation; the chip stays a filter count.

## Out of scope (SP2 → later)

- On-import auto-check; automatic TTL/cadence refresh (SP2 = manual "Refresh database", with `retrieved_at`
  shown — the world-state staleness is visible, the user refreshes).
- Streaming/incremental parse (we load the CSV text in memory under the byte cap — fine for ~tens of MB).
- statcheck/p-curve/GRIM emitting candidates into the findings store (a separate later increment).

## Tests (hermetic — fake fetcher, no network)

- `parse_retraction_csv`: a representative fake RW CSV → records mapped (nature→status, date, reason, notice);
  a `Reinstatement`/unknown nature row → skipped; a no-DOI row → skipped; row/byte caps.
- `retraction_repo`: replace-all (re-replace removes withdrawn rows); `lookup_retraction_record` picks
  most-severe for a DOI; `retraction_db_status` count + as-of.
- `download_retraction_database` with an injected fake fetcher → count; mailto-absent → clear error.
- the RW checker wraps a stored record → `RetractionSignal(source="retraction-watch", …)`; empty table → None.
- `DEFAULT_CHECKERS` includes RW first; a `detect_retraction` over all three merges RW's richer detail.
- endpoints: refresh (with injected client), database status; route-surface (`test_health.py`).

## Verification

- pytest green (+ ~12 `test_retraction_watch.py`); ruff clean; build + assembly; surface map (new `route_40`) 0
  uncovered; migration head derived by tests (0017).
- Headed, **no egress**, offline: seed `retraction_records` directly + drive the as-of line + a paper whose DOI
  matches an RW record → its FactMark shows the RW reason; the "Refresh database" button is present (the real
  download is the user's manual check). 0 console/page errors, **0 genai hits**.
- **Real-download check (the user's, optional):** with `CALLOSUM_CROSSREF_MAILTO` set, click "Refresh database"
  → confirm the count + that a known-retracted DOI in the library flags. (Verifies the live URL + CSV schema —
  the one thing the hermetic tests assume; flagged, not assumed correct.)
