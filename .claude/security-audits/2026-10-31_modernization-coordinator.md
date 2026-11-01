# Security audit: background modernization coordinator (inc 617)

**Date:** 2026-10-31.
**Scope:**
- `app/backend/modernization/` (new);
- `app/backend/api/routers/modernization.py` (new);
- the lifespan wiring in `api/app.py`;
- the `derive_paper` extraction in `pdf_processing/structure_backfill.py`;
- the launch lease in `embeddings/index_lock.py` and `index_supervisor.py`.

**Triggers:** new API endpoints (3), a net-new feature over 3+ files and ~300+ LOC, new lock files beside the library.

## Threat review
| Area | Finding |
|---|---|
| **Data egress** | None. Classification uses the inc-613 derivation over stored chunks and the local `external_api_cache`/`reference_instances`. It makes no network call (tested with `socket.connect` refused). The coordinator never downloads a model: it schedules indexing only once the inc-615 track reports `verified`. Model status is a local file read with no hashing. |
| **Resource exhaustion** | Background thread only; no synchronous startup work. Passes are bounded (50 papers) with one transaction per paper. Memory (`ResourcePolicy`) and disk (`disk_guard.check`) are checked before any write. Shortages and lock contention back off for 60 s; an idle library checks every 60 s with a cheap aggregate, and the expensive coverage queries run only on change or every 30 min. Failing papers are remembered, not retried in a loop. One coordinator per library across processes (OS lock). |
| **Data safety** | Writes only `chunk_structure` rows (through the existing derivation) and two `library_settings` keys. It does not change papers, chunks, annotations, MiniLM vectors or the active retrieval preference (all byte-compared in tests). `PRAGMA integrity_check` is `ok` after forced termination mid-paper. |
| **Concurrency** | The launch lease closes a duplicate-worker race between two app processes (regression-tested with real subprocess workers). Lock files sit beside the library, named from fixed suffixes. An in-memory DB gets a no-op lock. |
| **API surface / authorization** | `GET /modernization`, `POST /modernization/pause`, `POST /modernization/resume`. They take no body and no parameters, are gated by the existing `AccessControlMiddleware` like every endpoint, and are blocked by `CALLOSUM_READ_ONLY` (POST). Pause/Resume can only stop or allow background work the app would otherwise do; they cannot trigger downloads or change scientific settings. |
| **Output / information disclosure** | Counts, enum states and fixed English detail only. No path, filename, passage or exception text (tested against the response body). |
| **Input validation / injection** | No user input. Settings values are compared to fixed constants; `resumed_at` is parsed with `datetime.fromisoformat` inside a try, and an unparsable value means "not resumed". SQL uses SQLAlchemy Core with bound parameters only. |
| **Secrets / dependencies** | None added. No `psutil`. |

## Negative-path checks (automated, `tests/test_modernization.py`, 25 passed)
- Forced termination (TerminateProcess) of a real leader process mid-paper. The paper rolls back, this process takes
  over and finishes, no paper is re-derived, and integrity is `ok`.
- Two coordinators on one library: one leader. Two supervisors while a worker is still starting: no second launch.
- Malformed paper: isolated, reported, not retried in a loop, retried after its chunks change.
- `database is locked` → `database_busy`, recovers, not counted as a paper failure.
- Low memory, low disk and genuine "database or disk is full": no write while short, committed papers kept.
- Model unverified: no start and no supervisor row (no download path opened); it starts once verified.
- Durable Pause across restart; an explicit Cancel is not restarted after an import or a restart.
- The API response carries no path or home-directory text.

## Pending
The plugin security-review hook reviews fresh commits only and has no manual mode. An independent review of inc 616
(`0686a5f6`) and of this increment's commit is therefore **pending**, not done.

**Security Audit: PASS** (for the scope above, by this threat review and the automated negative-path checks; the
independent hook review is recorded as pending).
