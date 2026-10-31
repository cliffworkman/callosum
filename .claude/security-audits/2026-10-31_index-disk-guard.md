# Security audit: index-build disk guard (inc 616)

**Date:** 2026-10-31.
**Scope:** `app/backend/embeddings/disk_guard.py`, its use in `index_worker.py` and `index_supervisor.py`, migration
`0087_index_run_waiting_disk`, and the `disk` field/`waiting_disk` state on the embedding-profile index-run response.
**Triggers:** a request/response schema change on an existing endpoint, a schema migration, 3+ files.

## Threat review
| Area | Finding |
|---|---|
| **Resource exhaustion** | This is the control being added: the build never starts a batch unless the library's filesystem has a 1 GB reserve + 64 MB WAL allowance + room for the next four batches; a runtime `SQLITE_FULL`/`ENOSPC` stops the worker with every committed batch intact. Retries are a fixed 60 s recheck (one `disk_usage` syscall and, when due, one row update), so a shortage cannot cause a tight loop |
| **Data safety** | No code path deletes, truncates or vacuums anything. MiniLM vectors and user data are untouched (byte-identical in tests). A failing batch rolls back in one transaction; `PRAGMA integrity_check` is `ok` after interrupted and retried writes |
| **Migration** | 0087 rebuilds only `embedding_index_runs` (build lifecycle rows; no vectors, no user data, no inbound foreign keys) using a fixed column list (no interpolated input; `nosec B608` documented). Idempotent; a no-op on fresh or upgraded databases. Rows are copied unchanged (tested) |
| **Output / information disclosure** | Status and the API carry byte counts only. The library path, drive and filename never enter a row or a response (tested against the response body and `/status/jobs`). Messages contain no exception text; diagnostics stay in the existing bounded, home-scrubbed field |
| **Input validation** | No new input. Free bytes come from `shutil.disk_usage` on a path derived from the configured database URL; an unreadable volume is treated as unmeasurable (non-blocking) rather than raising |
| **Injection** | No SQL built from data; the only dynamic SQL is the fixed migration column list. Test-only `PRAGMA max_page_count` lives in `tests/` |
| **Egress / secrets / dependencies** | None. Stdlib only (`shutil`, `sqlite3`, `errno`); no `psutil` |

## Negative-path checks (automated, `tests/test_index_disk_guard.py`, 14 passed)
- Low disk before the first batch: `waiting_disk`, no worker launched, no model loaded.
- Disk exhausted after committed batches: committed rows kept; batch size unchanged; breaker untouched.
- Genuine SQLite "database or disk is full" (thread and real subprocess): whole-batch rollback, six retries past a
  breaker limit of three without `failed`, integrity `ok`, MiniLM rows unchanged, full recovery once space returns.
- App killed while waiting; restart with space still low (stays waiting) and with space (completes).
- Pause during a disk wait and during a disk exit: `paused`, durable across restart.
- Unmeasurable volume and in-memory database: never blocks.
- `database is locked`, `EACCES` and `MemoryError` are not misclassified as a full disk.
- Status/API bodies contain no library path or filename.

**Security Audit: PASS**
