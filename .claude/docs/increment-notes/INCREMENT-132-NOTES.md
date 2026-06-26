# Increment 132 — Retraction Watch DB (SP2: the bulk third source)

## Implemented

Completes the user's "all three sources" ask: the **Retraction Watch Database** (Crossref-hosted, CC0) joins
Crossref + OpenAlex (SP1, inc 131) as the **third checker** for the retraction producer. Download it once into a
local mirror, match every library DOI **offline**, refresh on demand. It's the **richest** source (nature, date,
**reason**, notice), so the merge prefers its detail. Additive — the SP1 merge layer already accepts another
checker.

- **Storage:** new `retraction_records` table (migration **0017**, additive/guarded) — one row per RW notice
  (`original_doi` [indexed], `status`, `nature`, `date`, `reason`, `notice_doi`, `notice_url`, `retrieved_at`).
  `persistence/retraction_repo.py`: `replace_retraction_records` (DELETE-all + bulk INSERT in one txn — the RW DB
  is authoritative, so a withdrawn record disappears on refresh), `lookup_retraction_record` (most-severe row for
  a DOI), `retraction_db_status` (count + as-of).
- **Download adapter** (`integrations/retraction_watch/adapter.py`): `RetractionWatchClient` (injectable
  size-capped https fetcher mirroring `acquisition/fetch.py`; mailto from `CALLOSUM_CROSSREF_MAILTO`; **absent →
  `RetractionWatchUnavailable`**, fail-closed) + `parse_retraction_csv` (stdlib `csv` — **no new dependency**;
  tolerant case-insensitive headers; `RW_STATUS_BY_NATURE`; **skips no-DOI + Reinstatement + unknown natures**;
  row cap) + `download_retraction_database` (fetch → parse → replace → count).
- **The third checker** (`methods/retraction.py`): `RETRACTION_WATCH_CHECKER` (via `lookup_retraction_record`),
  **prepended** to `DEFAULT_CHECKERS` so its richer detail wins `merge_signals`' first-non-null pick; an empty
  mirror returns None and the SP1 sources still work.
- **Endpoints** (`routers/methods.py`): `GET /methods/retraction/database` (`{count, retrieved_at}`), async
  `POST`/`GET /methods/retraction/database/refresh` (download via `app.state.retraction_watch_client`;
  `RetractionWatchUnavailable` → a clear job `error`, never 500). `app.state` gains `retraction_db_jobs` +
  `retraction_watch_client` (overridable in tests).
- **Frontend** (`08_methods_findings.jsx`): a **"Retraction Watch database: N records · as of <date>"** line + a
  **Refresh database** button in the Review section ("not downloaded — refresh to enable the richest source" when
  empty); the retraction FactMark's tooltip now carries the **RW reason**. Tokens-only CSS.

## Key technical detail

**The CSV schema + the Crossref Labs URL are the one thing not verified offline.** The hermetic tests use a
representative fake CSV; the parser is **tolerant** (case-insensitive header map + skip-on-missing) so a header
drift degrades to "field absent", not a crash. The **real-download check is the user's** (it needs their
`CALLOSUM_CROSSREF_MAILTO` + a ~tens-of-MB fetch) — flagged below, not assumed correct.

**Reinstatements are never surfaced** — `RW_STATUS_BY_NATURE` maps only retraction/correction/concern natures; a
"Reinstatement" (an *un*-retraction) and any unknown nature are dropped in the parser. An un-retraction is the
opposite of a finding.

**Replace-all keeps the mirror honest.** Each refresh DELETEs + re-INSERTs, so a record withdrawn upstream
disappears (no stale flag); `retrieved_at` (shown in the UI) makes the snapshot's age visible — the world-state
staleness is the user's to refresh.

## Manual verification script

1. Seed the mirror + a matching paper's FACT offline (no network): `replace_retraction_records(...)` for a live
   paper's DOI, then `apply_retraction(..., detect_retraction(..., checkers=[RETRACTION_WATCH_CHECKER]))`. (See
   `.local/visual/drive_inc132_retraction_watch.py`.)
2. Start the app (egress unset). METHODS → Review: the **"Retraction Watch database: 1 records · as of …"** line
   + a **Refresh database** button.
3. Open the seeded paper → its FactMark shows "⚠ Retracted" + a **notice** link, and its tooltip carries the RW
   **reason**.

Automated equivalent: `.local/visual/drive_inc132_retraction_watch.py` — **PASS**, 0 console/page errors, **0
genai hits**. **Real-download check (the user's, optional):** set `CALLOSUM_CROSSREF_MAILTO`, click "Refresh
database" → confirm the count + that a known-retracted library DOI flags (verifies the live URL + CSV schema).

## Pytest

**501** (493 → +8 `test_retraction_watch.py`: parse [nature map / skip reinstatement+no-DOI], replace+lookup
most-severe, replace-is-authoritative, download with injected fetcher, mailto-absent fail-closed, the RW checker
first+wraps, detect merges RW reason, the refresh endpoint+status; route-surface extended). `ruff` clean. QA
surface **101/101 API + 506/506 FE, 0 uncovered** (`route_40_retraction_watch.md`). Audit
`.claude/security-audits/2026-06-26_retraction-watch.md` **PASS**. methods.py at **463/600** — a
`routers/retraction.py` split is the next time it grows.

## Next

This **completes the retraction arc (SP1 inc 131 + SP2 inc 132)** with all three sources. Deferred: an
on-import auto-check (piggyback the enrich's cached Crossref response) + automatic TTL/cadence refresh (SP2 =
manual refresh with `retrieved_at` shown). Then statcheck / p-curve / GRIM can optionally emit **candidates**
into the same findings store + a unified library-wide "needs review" facet.
