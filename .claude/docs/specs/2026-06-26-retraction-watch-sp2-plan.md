# Retraction Watch DB SP2 — implementation plan (increment 132)

**Goal:** The Retraction Watch DB as a bulk third checker: download (Crossref Labs CSV) → `retraction_records`
table → offline DOI match → merged into the SP1 producer + a "Refresh database" UI. Design:
`2026-06-26-retraction-watch-sp2-design.md`.

**Global constraints:** bound-param SQL (rule #3); files < 600 (rule #1); no new dependency (stdlib `csv`); no
Gemini gate (public bulk metadata, uses `CALLOSUM_CROSSREF_MAILTO`); injectable fetcher → hermetic; migration
head derived by tests (never hardcoded — inc 99); fail-closed (mailto-absent / fetch error → job error, never
500); TDD; commit per task; ruff before push; CI green.

---

## Task 1 — storage + download adapter + parser (no network)

**Files:** `app/backend/persistence/schema.py` (+`retraction_records`), `alembic/versions/0017_retraction_records.py`
(new), `app/backend/persistence/retraction_repo.py` (new), `integrations/retraction_watch/__init__.py` +
`adapter.py` (new); `tests/test_retraction_watch.py` (new).

**Interfaces produced:**
- table `retraction_records(id, original_doi[idx], status, nature, date, reason, notice_doi, notice_url, retrieved_at)`.
- `retraction_repo.replace_retraction_records(conn, records, *, retrieved_at)`,
  `lookup_retraction_record(conn, doi) -> dict | None`, `retraction_db_status(conn) -> {count, retrieved_at}`.
- `RetractionWatchClient(fetcher=…, mailto=…)` + `RetractionWatchFetcher` Protocol; `parse_retraction_csv(text)
  -> list[dict]`; `download_retraction_database(client, conn) -> int`; `RW_STATUS_BY_NATURE` map; `MAX_RW_BYTES`,
  `MAX_RW_ROWS`.

- [ ] **Step 1 — failing tests** (`tests/test_retraction_watch.py`): `parse_retraction_csv` over a fake RW CSV
  (header row + 4 data rows: a Retraction with reason+notice, a Correction, an "Expression of concern", a
  "Reinstatement" [skipped], a no-DOI row [skipped]) → 3 records mapped (nature→status, date, reason, notice_url
  derived from notice DOI); `replace_retraction_records` then `lookup_retraction_record` picks most-severe for a
  DOI with two rows; `retraction_db_status` count+as-of; `download_retraction_database` with an injected fake
  fetcher → count==3; mailto-absent client → a clear error (raises a typed error or returns a sentinel the job
  maps to "error"). Run → FAIL.

- [ ] **Step 2 — schema + migration.** Add `retraction_records` to `schema.py` (Index on `original_doi`).
  Create `0017_retraction_records.py` (guarded create, `down_revision="0016_paper_findings"`, mirror 0016).

- [ ] **Step 3 — retraction_repo.py.** `replace_retraction_records` (DELETE all + bulk INSERT, one txn),
  `lookup_retraction_record` (rows by normalized DOI → most-severe via a STATUS_RANK), `retraction_db_status`.

- [ ] **Step 4 — integrations/retraction_watch/adapter.py.** `RetractionWatchClient` (injectable size-capped
  https fetcher mirroring `acquisition/fetch.py`; `mailto` from arg/`CALLOSUM_CROSSREF_MAILTO`; **absent mailto →
  raise `RetractionWatchUnavailable`**); `parse_retraction_csv` (stdlib `csv.DictReader`; tolerant case-insensitive
  header map; map nature→status via `RW_STATUS_BY_NATURE`; skip no-DOI / unrecognized-nature / reinstatement;
  cap rows); `download_retraction_database(client, conn)` (fetch text → parse → `replace_retraction_records(...,
  retrieved_at=<passed in>)` → count). `__init__.py` re-exports. Run `pytest tests/test_retraction_watch.py -q`
  → PASS.

- [ ] **Step 5 — ruff + commit.** `git commit -m "feat(retraction-watch): table + repo + CSV download adapter (inc 132 t1)"`.

## Task 2 — the third checker + refresh endpoints + DEFAULT_CHECKERS

**Files:** `app/backend/methods/retraction.py`, `app/backend/api/routers/methods.py`, `app.py`;
`tests/test_retraction_watch.py` (+endpoints) + `tests/test_health.py`.

- [ ] **Step 1 — failing tests.** `methods/retraction.py`: `DEFAULT_CHECKERS[0].source == "retraction-watch"`;
  the RW checker over a seeded record → a `RetractionSignal(source="retraction-watch", reason=…)`; empty table →
  None; a `detect_retraction` with all three (RW seeded + a fake Crossref) merges RW's `reason`. Endpoints:
  `POST /methods/retraction/database/refresh` (inject `app.state.retraction_watch_client` = a fake) → job done,
  count; `GET /methods/retraction/database` → `{count, retrieved_at}`; route-surface in `test_health.py`. FAIL.

- [ ] **Step 2 — the checker.** In `methods/retraction.py`: `_retraction_watch_fetch(conn, paper)` (via
  `retraction_repo.lookup_retraction_record`) + `RETRACTION_WATCH_CHECKER`; prepend to `DEFAULT_CHECKERS`.

- [ ] **Step 3 — endpoints + app state.** `app.py`: `api.state.retraction_db_jobs = JobStore()` +
  `api.state.retraction_watch_client = RetractionWatchClient()` (overridable). `methods.py`: the refresh
  POST/GET (async; `_run_retraction_db_refresh_job` calls `download_retraction_database`; a
  `RetractionWatchUnavailable` / any error → `jobs.mark_error` with the message) + the `GET
  /methods/retraction/database` status. **Check `wc -l methods.py`** — if > 560, extract `routers/retraction.py`.
  Run `pytest tests/test_retraction_watch.py tests/test_health.py -q` → PASS.

- [ ] **Step 4 — ruff + commit.** `git commit -m "feat(retraction-watch): RW checker + refresh endpoints (inc 132 t2)"`.

## Task 3 — frontend: as-of line + Refresh database

**Files:** `app/frontend/js/08_methods_findings.jsx`, `styles.css`; rebuild `callosum-app.html`.

- [ ] **Step 1 — the RW database panel** in `RetractionBatch` (or a sibling): fetch `GET
  /methods/retraction/database` → "Retraction Watch database: N records · as of <date>" (or "not downloaded —
  Refresh to enable the richest source") + a **Refresh database** button (`POST .../database/refresh`, poll, on
  done refresh the line + `ctx.onRetractionRan`). Token CSS (`.retraction-db`).
- [ ] **Step 2 — build + assembly.** `python tools/build_frontend.py` + `pytest tests/test_frontend_assembly.py -q`.
- [ ] **Step 3 — commit.** `git commit -m "feat(retraction-watch): refresh-database UI + as-of line (inc 132 t3)"`.

## Task 4 — gates, QA, docs, verify, push

- [ ] **Step 1 — audit** `.claude/security-audits/2026-06-26_retraction-watch.md`: the CSV download (https-only
  fixed host, size + row caps, mailto from env, fail-closed), untrusted-CSV parsing (tolerant, skips bad rows,
  caps), bound-param replace, no Gemini egress, reinstatements never flagged, no new dependency. **PASS**.
- [ ] **Step 2 — QA route** `.claude/qa-routes/route_40_retraction_watch.md` (assert: richest-source merge, the
  as-of/refresh UI, reinstatement-not-flagged, no genai, fail-closed on mailto-absent). `build_surface_map.py
  extract && check` → 0 uncovered.
- [ ] **Step 3 — headed verify (offline)** `.local/visual/drive_inc132_retraction_watch.py`: seed
  `retraction_records` + a matching paper; confirm the as-of line + the FactMark shows the RW **reason**; the
  Refresh button is present (don't click — real download). 0 console/page/genai.
- [ ] **Step 4 — docs.** `INCREMENT-132-NOTES.md`; `changes.md` (HELP-DOCS-SYNCED → 132 if help touched); help
  corpus "Checking for retractions" gains the RW-database paragraph; `RECOVERY-LOG.md`; CLAUDE footer + status
  (tests) + layout enums (the new `integrations/retraction_watch/`, `retraction_repo.py`, migration head 0017);
  backlog #31 (SP2 done; on-import + TTL next). DESIGN note if CSS added.
- [ ] **Step 5 — full gate + push.** `ruff check . && ruff format --check .`; full `pytest -q`; commit docs;
  `git push origin main`; CI green.

## Critical files
- **New:** `alembic/versions/0017_retraction_records.py`, `app/backend/persistence/retraction_repo.py`,
  `integrations/retraction_watch/{__init__,adapter}.py`, `tests/test_retraction_watch.py`,
  `.claude/security-audits/2026-06-26_retraction-watch.md`, `.claude/qa-routes/route_40_retraction_watch.md`,
  `.local/visual/drive_inc132_retraction_watch.py`, `INCREMENT-132-NOTES.md`.
- **Modify:** `schema.py`, `methods/retraction.py`, `routers/methods.py`, `app.py`,
  `08_methods_findings.jsx`, `styles.css`, `tests/test_health.py`, docs.
- **Reuse:** the SP1 merge/detect/apply + RetractionChecker; `acquisition/fetch.py` size-capped fetcher pattern;
  the 0016 guarded-migration pattern; the inc-97 statcheck batch/JobStore; the inc-130 FactMark.

## Build-time verification NOT to skip
- The hermetic tests assume the **RW CSV column names + the Crossref Labs URL**. These are the one thing not
  verified offline — flag the **real-download check** (the user's, needs their mailto) prominently in the notes;
  make the parser tolerant so a header drift degrades gracefully.
