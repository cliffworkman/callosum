# Long-job incremental commits — Increment A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the reusable `commit_each` primitive and convert the scan / watched-rescan jobs' per-paper enrich+embed+retraction phase to per-item commits, so those jobs release the SQLite write lock between papers instead of holding it for the whole run.

**Architecture:** `commit_each(engine, items, process, on_item_error="skip")` runs each item in its own short transaction via `run_write` (inc 272). `_process_scan_result` is rewritten to take an `engine` and process each scanned paper (enrich → embed its chunks → embed the paper → retraction check) in its own committed transaction; `_run_scan_job` / `_run_watched_rescan_job` commit the `scan_library_folder` insert phase as its own unit first, then call the per-paper processor, then a final short commit for the watched-folder bookkeeping.

**Tech Stack:** Python 3.11, SQLAlchemy Core 2.0 (SQLite/WAL), FastAPI BackgroundTasks, pytest.

## Global Constraints

- App-source files stay **under 600 lines** (`python tools/check_line_budget.py`); the pre-commit hook enforces it — `--no-verify` skips it, so run the check manually before committing.
- Parameterized SQL only (SQLAlchemy bound params); no string-interpolated SQL.
- `ruff check .` and `ruff format --check .` must pass (CI runs both).
- `pytest` (full suite) green before a task is done. Run with `-p no:cacheprovider`.
- **Atomicity becomes per-item, not per-job — this is an intended, recorded behavior change.** A mid-run failure leaves earlier papers committed (partial progress is usable; scan is idempotent via content-hash dedup, inc 45). Record it in the increment notes.
- `run_write` already exists at `app/backend/persistence/sqlite_retry.py` (inc 272): `run_write(engine, operation, *, attempts=5, delay_seconds=0.05, sleeper=time.sleep)` — opens a fresh connection, runs `operation(conn)`, commits, retries the whole unit on `database is locked`.
- **Out of scope for this increment (separate follow-up plans):** A2 = `scan_library_folder` per-file *extraction* commits (savepoint→commit ingest refactor); A3 = axis-score `score_axis` embed-phase hoist. Increment A commits the extraction phase as one unit and leaves the axis-score job untouched.

---

### Task 1: The `commit_each` primitive

**Files:**
- Modify: `app/backend/persistence/sqlite_retry.py` (append `commit_each`)
- Test: `tests/test_sqlite_retry.py` (append)

**Interfaces:**
- Consumes: `run_write(engine, operation)` (existing, same file).
- Produces: `commit_each(engine, items, process, *, on_item_error="skip", logger=None) -> list` — iterates `items`, runs `process(conn, item)` for each in its own committed transaction (via `run_write`), returns the per-item results in order (`None` for a skipped item). `on_item_error="skip"` catches a non-lock exception, logs via `logger` (if given) and continues; `"raise"` propagates it.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_sqlite_retry.py`)

```python
def test_commit_each_commits_each_item_independently(temp_db_url):
    """A failure at item K leaves items 1..K-1 committed (the per-item boundary; a per-job txn would lose them)."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (v INTEGER PRIMARY KEY)"))

    def process(conn, item):
        if item == 3:
            raise ValueError("bad item 3")
        conn.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": item})
        return item

    results = commit_each(engine, [1, 2, 3, 4], process, on_item_error="skip")
    assert results == [1, 2, None, 4]  # item 3 skipped
    with engine.connect() as conn:
        assert [r[0] for r in conn.execute(text("SELECT v FROM t ORDER BY v"))] == [1, 2, 4]
    engine.dispose()


def test_commit_each_raise_propagates(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (v INTEGER PRIMARY KEY)"))

    def process(conn, item):
        if item == 2:
            raise ValueError("boom")
        conn.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": item})

    with pytest.raises(ValueError):
        commit_each(engine, [1, 2, 3], process, on_item_error="raise")
    with engine.connect() as conn:
        assert [r[0] for r in conn.execute(text("SELECT v FROM t ORDER BY v"))] == [1]  # item 1 committed before the raise
    engine.dispose()


def test_commit_each_retries_transient_lock_per_item(temp_db_url):
    """A transient lock on one item retries (via run_write) and still commits it."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (v INTEGER PRIMARY KEY)"))
    seen = {"n": 0}

    def process(conn, item):
        if item == 2 and seen["n"] == 0:
            seen["n"] += 1
            raise _locked()
        conn.execute(text("INSERT INTO t (v) VALUES (:v)"), {"v": item})

    commit_each(engine, [1, 2], process, on_item_error="raise")
    with engine.connect() as conn:
        assert [r[0] for r in conn.execute(text("SELECT v FROM t ORDER BY v"))] == [1, 2]
    engine.dispose()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_sqlite_retry.py -k commit_each -q -p no:cacheprovider`
Expected: FAIL — `ImportError: cannot import name 'commit_each'`. (Also add `commit_each` to the existing `from app.backend.persistence.sqlite_retry import ...` line at the top of the test file.)

- [ ] **Step 3: Implement `commit_each`** (append to `app/backend/persistence/sqlite_retry.py`)

```python
def commit_each(
    engine: Engine,
    items: Iterable[T],
    process: Callable[[Connection, T], object],
    *,
    on_item_error: str = "skip",
    logger: object | None = None,
) -> list:
    """Process each item in its OWN short transaction (via run_write), releasing the SQLite write lock between
    items — the long-job counterpart to run_write. ``on_item_error="skip"`` logs a non-lock failure and continues
    (resilient batch: one bad item never aborts the run); ``"raise"`` propagates it. Returns per-item results
    (None for a skipped item). A transient writer lock on an item is retried by run_write, not skipped."""
    results: list = []
    for item in items:
        try:
            results.append(run_write(engine, lambda conn, it=item: process(conn, it)))
        except Exception as exc:  # noqa: BLE001 — batch resilience is the contract
            if on_item_error == "raise":
                raise
            if logger is not None:
                logger.warning("commit_each: skipped an item: %s: %s", type(exc).__name__, exc)
            results.append(None)
    return results
```

Add `from collections.abc import Callable, Iterable` (extend the existing `from collections.abc import Callable` import to include `Iterable`).

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_sqlite_retry.py -q -p no:cacheprovider`
Expected: PASS (the 9 existing + 3 new).

- [ ] **Step 5: Ruff + line budget + commit**

```bash
ruff check --fix app/backend/persistence/sqlite_retry.py tests/test_sqlite_retry.py
ruff format app/backend/persistence/sqlite_retry.py tests/test_sqlite_retry.py
PYTHONIOENCODING=utf-8 python tools/check_line_budget.py
git add app/backend/persistence/sqlite_retry.py tests/test_sqlite_retry.py
git commit --no-verify -m "feat(db): commit_each primitive for per-item long-job commits (inc A)"
```

---

### Task 2: Per-paper commits in the scan / watched-rescan enrich+embed phase

**Files:**
- Modify: `app/backend/api/routers/library.py` — `_process_scan_result` (currently ~124-151), `_run_scan_job` (~164-190), `_run_watched_rescan_job` (~256-300)
- Test: `tests/test_library_scan.py` (append a partial-progress test)

**Interfaces:**
- Consumes: `commit_each(engine, items, process, on_item_error="skip", logger=_log)` (Task 1); `run_write(engine, op)`; existing `scan_library_folder(conn, folder, on_progress=…) -> {"added":[{paper_id, chunk_ids}], …}`, `enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=…)`, `embed_chunks(conn, model=…, vector_store=…, chunk_ids=…)`, `embed_papers(conn, model=…, vector_store=…, paper_ids=…)`, `auto_check_retractions(conn, paper_ids, checkers=…)`, `add_watched_folder(conn, folder)`, `touch_last_scanned(conn, folder)`.
- Produces: `_process_scan_result(engine, scanned, *, model, store, crossref, retraction_checkers, on_progress=None) -> None` — **now takes `engine`, not `conn`**, and commits per scanned paper.

- [ ] **Step 1: Write the failing partial-progress test** (append to `tests/test_library_scan.py`)

```python
def test_scan_commits_per_paper_partial_progress(temp_db_url, monkeypatch, tmp_path):
    """If embedding paper #2 raises, paper #1 stays enriched/embedded (per-paper commit, not all-or-nothing)."""
    # (Use the module's existing scan fixtures/helpers; seed two importable PDFs into tmp_path, then force
    # embed_papers to raise on the SECOND paper_id. After the scan job, assert paper #1 has embeddings and
    # paper #2 does not, and the job status is "done" with an error recorded — never a full rollback.)
    ...  # concrete body written against test_library_scan.py's existing helpers during implementation
```

Note: this test is written concretely against `tests/test_library_scan.py`'s existing seeding helpers (which the implementer reads first). The load-bearing assertions: (a) paper #1's chunks have embeddings after the run; (b) paper #2's do not; (c) the job completed (`status == "done"`), proving per-paper commit + skip-on-error rather than a whole-job rollback.

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_library_scan.py -k partial_progress -q -p no:cacheprovider`
Expected: FAIL — under the current single-transaction job, paper #2's failure rolls back paper #1 too (no embeddings for #1), or the job errors out.

- [ ] **Step 3: Rewrite `_process_scan_result` to per-paper commits**

```python
def _process_scan_result(
    engine,  # was: conn
    scanned,
    *,
    model,
    store,
    crossref,
    retraction_checkers=None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> None:
    """Enrich + embed each newly scanned paper in its OWN committed transaction (per-paper), so the write lock is
    released between papers. One paper's hard failure is skipped (logged), never aborting the rest — partial
    progress is usable + the scan is idempotent (content-hash dedup). Crossref stays resilient (unresolved →
    Unsorted) and is NOT the Gemini gate."""
    added = scanned["added"]  # [{paper_id, chunk_ids}]
    total = len(added)

    def process_one(conn, item):
        paper_id = int(item["paper_id"])
        chunk_ids = [int(c) for c in (item.get("chunk_ids") or [])]
        try:
            enrich_paper_metadata_from_crossref(conn, paper_id, crossref_client=crossref)
        except Exception as exc:  # enrich stays best-effort (unresolved → Unsorted view)
            _log.warning("library scan: enrich failed for paper %s: %s", paper_id, exc)
        if chunk_ids:
            embed_chunks(conn, model=model, vector_store=store, chunk_ids=chunk_ids)
        embed_papers(conn, model=model, vector_store=store, paper_ids=[paper_id])
        if retraction_checkers:
            auto_check_retractions(conn, [paper_id], checkers=retraction_checkers)

    for index, item in enumerate(added, start=1):
        if on_progress:
            on_progress("Processing", index, total)
        commit_each(engine, [item], process_one, on_item_error="skip", logger=_log)
```

(Using `commit_each` per single item keeps the skip-on-error + retry semantics and the progress cadence; the loop stays for the progress callback. Import `commit_each` + `run_write` at the top of `library.py`.)

- [ ] **Step 4: Rewire `_run_scan_job` to commit the scan-insert phase, then process per paper**

```python
def _run_scan_job(app: FastAPI, job_id: str, folder: str) -> None:
    jobs = app.state.library_scan_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app)
        store = _vector_store(app)
        crossref = app.state.crossref_client
        engine = app.state.engine
        # Phase 1 (extraction + insert) commits as its own unit; A2 will make it per-file.
        scanned = run_write(
            engine,
            lambda conn: scan_library_folder(
                conn, folder, on_progress=lambda i, n, name: jobs.mark_progress(job_id, i, n, f"Reading {name}")
            ),
        )
        # Phase 2 (enrich + embed) commits per paper — the lock is released between papers.
        _process_scan_result(
            engine, scanned, model=model, store=store, crossref=crossref,
            retraction_checkers=app.state.retraction_checkers,
            on_progress=lambda label, i, n: jobs.mark_progress(job_id, i, n, label),
        )
        run_write(engine, lambda conn: (add_watched_folder(conn, folder), touch_last_scanned(conn, folder)))
        jobs.mark_done(job_id, ScanJobResponse(job_id=job_id, status="done", summary=_scan_summary(scanned)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        _clear_active_scan_family_job(app, job_id)
```

- [ ] **Step 5: Rewire `_run_watched_rescan_job` the same way** — replace its single `with app.state.engine.begin() as conn:` block so each folder's `scan_library_folder` runs via `run_write(engine, …)`, then `_process_scan_result(engine, scanned, …)`, then `run_write(engine, lambda c: touch_last_scanned(c, folder))`. The missing-folder / aggregation bookkeeping (`agg`, `error_details`) stays in the job's local scope (it's plain Python, no transaction needed). Keep the library-folder-always-first ordering (inc 160).

```python
def _run_watched_rescan_job(app: FastAPI, job_id: str) -> None:
    jobs = app.state.library_scan_jobs
    jobs.mark_running(job_id)
    try:
        model = _embedding_model(app); store = _vector_store(app); crossref = app.state.crossref_client
        engine = app.state.engine
        agg = {"added": 0, "unchanged": 0, "removed": 0, "errors": 0}
        error_details: list[ScanError] = []
        lib = library_dir(); lib_key = _path_key(lib)
        targets = ([str(lib)] if lib.is_dir() else []) + [
            r["path"] for r in run_write(engine, lambda c: list_watched_folders(c))
            if _path_key(Path(r["path"])) != lib_key
        ]
        for folder in targets:
            if not Path(folder).is_dir():
                agg["errors"] += 1
                if len(error_details) < _SCAN_ERROR_DETAIL_CAP:
                    error_details.append(ScanError(path=folder, error="watched folder no longer exists"))
                continue
            scanned = run_write(engine, lambda c, f=folder: scan_library_folder(
                c, f, on_progress=lambda i, n, name: jobs.mark_progress(job_id, i, n, f"Reading {name}")))
            _process_scan_result(engine, scanned, model=model, store=store, crossref=crossref,
                retraction_checkers=app.state.retraction_checkers,
                on_progress=lambda label, i, n: jobs.mark_progress(job_id, i, n, label))
            run_write(engine, lambda c, f=folder: touch_last_scanned(c, f))
            for key in agg:
                agg[key] += len(scanned[key])
            for e in scanned["errors"]:
                if len(error_details) < _SCAN_ERROR_DETAIL_CAP:
                    error_details.append(ScanError(path=e["path"], error=e["error"]))
        jobs.mark_done(job_id, ScanJobResponse(job_id=job_id, status="done",
            summary=ScanSummary(**agg, error_details=error_details)))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
    finally:
        _clear_active_scan_family_job(app, job_id)
```

(`list_watched_folders` reads inside a `run_write` — a read wrapped in a write txn is harmless; alternatively read via `with engine.connect() as c:`. Keep whichever the implementer finds cleaner; the behavior is identical.)

- [ ] **Step 6: Run the partial-progress test + the whole scan suite**

Run: `python -m pytest tests/test_library_scan.py tests/test_watched_folders.py -q -p no:cacheprovider`
Expected: PASS (the new partial-progress test + all existing scan/rescan tests — the happy path is behavior-preserving).

- [ ] **Step 7: Full suite + ruff + line budget**

Run: `python -m pytest -q -p no:cacheprovider` → all pass. Then `ruff check .`, `ruff format --check .`, `PYTHONIOENCODING=utf-8 python tools/check_line_budget.py` (library.py must stay < 600 — re-measure; if the rewiring pushes it over, extract the two `_run_*` job bodies to a `routers/library_jobs.py` sibling, the inc-226 pattern).

- [ ] **Step 8: Commit**

```bash
git add app/backend/api/routers/library.py tests/test_library_scan.py
git commit --no-verify -m "perf(db): per-paper commits in scan/watched-rescan enrich+embed (inc A)"
```

---

### Task 3: Increment notes + changes.md + backlog

**Files:** `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md` (bump NN), `.claude/changes.md`, `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/CLAUDE.md` (increment number + test count).

- [ ] **Step 1:** Write the increment notes: what changed (`commit_each`; scan/rescan phase-2 per-paper commits; scan-insert committed as its own unit); the **atomicity-becomes-per-item** intended change + why (partial progress usable, idempotent re-scan, fixes the poisoned-transaction latent bug); the two deferrals (A2 extraction per-file, A3 axis-score) + rationale; the manual verification script (scan a folder while toggling a read marker in another tab → the toggle succeeds instead of 500ing). Record the passing test count.
- [ ] **Step 2:** `changes.md` entry (Files/What/Why/Verify/Revert). No help-doc change (no user-facing surface change) → no HELP-DOCS-SYNCED marker move.
- [ ] **Step 3:** Update the backlog's `database is locked` item: note the scan/rescan enrich+embed phase is now per-paper (inc A); A2 (extraction) + A3 (axis-score) + increments B–D remain.
- [ ] **Step 4: Commit**

```bash
git add .claude/
git commit --no-verify -m "docs(inc A): long-job per-item commits — notes + backlog"
```

---

## Self-Review

- **Spec coverage:** `commit_each` primitive ✓ (T1); per-item boundary for scan + watched-rescan ✓ (T2); atomicity-per-item recorded ✓ (T2/T3); testing (partial-progress proof) ✓ (T1/T2); the spec's axis-score + extraction-per-file are **explicitly deferred** to A3/A2 with rationale (scope-check: distinct subsystems) — surfaced to the user at handoff, not silently dropped. The other jobs (B–D) are later increments per the spec's sequencing.
- **Placeholder scan:** Task 2 Step 1's test body is described against `tests/test_library_scan.py`'s existing helpers rather than fully coded — the only such case, because the seeding fixtures are established in that file and the implementer must read them; the load-bearing assertions are spelled out explicitly. Everything else carries complete code.
- **Type consistency:** `_process_scan_result` signature changes `conn` → `engine` consistently across its definition (T2 S3) and both call sites (T2 S4/S5); `commit_each(engine, items, process, on_item_error, logger)` used identically in T1 and T2; `scan_library_folder`/`enrich`/`embed_*`/`auto_check_retractions` keep their existing `conn`-based signatures (called inside the per-item `run_write` conn).
