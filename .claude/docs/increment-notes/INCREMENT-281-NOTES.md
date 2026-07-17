# Increment 281 — Short-write `run_write` uniform sweep (the last "database is locked" piece)

The residual edge of the `database is locked` work (inc 272–278): a short handler using the `get_connection`
dependency does a **deferred BEGIN** — it reads (takes a snapshot), then writes; if another writer commits in
between, WAL returns `SQLITE_BUSY` **immediately** (a snapshot-upgrade conflict that `busy_timeout` can't break).
This sweep routes the short SELECT-then-write API handlers through **`run_write`** (transaction-level retry on a
fresh connection — inc 272), so the snapshot-upgrade BUSY is retried instead of 500ing. Design/scope:
`.claude/backups/plans/2026-07-16_short-write-run_write-sweep.md` (user chose "full uniform sweep"). Branch
`feature/short-write-sweep`.

## Implemented

- **`get_engine(request) -> Engine`** (`app/backend/api/dependencies.py`) — the dependency short mutating handlers
  take instead of `get_connection`, so they wrap their read+write unit in `run_write(engine, _do)`.
- **The conversion (17 routers):** each committing handler became
  `def handler(payload, engine=Depends(get_engine)): def _do(conn): …reads/writes…; return resp; return run_write(engine, _do)`
  — the raw `conn.commit()` removed (`run_write` commits), pure input validation kept OUTSIDE the closure, `HTTPException`
  (404/422/409) raised inside (propagated un-retried; e.g. papers' `IntegrityError → 409`). Converted:
  **findings, saved_searches, paper_urls, annotations, feed, wanted, papers (CRUD), axes, duplicates, critical_review
  (accept/reject), summaries (delete), gaps, discovery, agent (tag/axis/note/revert), settings (repair-cache),
  my_publications (all 10), workbench (11 CRUD/convert/accept/reject).** GET handlers keep `get_connection`.
- **Idempotent I/O-mixed → wrap whole (documented):** `gaps_add`, my-pubs `import_missing_work` / `import_citing_work`,
  `discovery_save` reuse the citing-import flow which **dedupes by identity + caches the Crossref lookup**, so a
  lock-retry re-runs them safely (no double egress).
- **The invariant, machine-enforced:** `tests/test_short_write_sweep.py` fails on any **new** raw `conn.commit()` in
  `routers/**`; a small `ALLOWED_RAW_COMMITS` allowlist documents the genuine exceptions (below). The
  `SqliteWriteRetryMiddleware` stays as the belt-and-suspenders backstop.

## Key technical detail — what legitimately stays raw (the allowlist)

Not every committing handler is a *short* write. These keep their own transaction because a lock-retry would re-run
the expensive work or **re-fire a side effect**:
- **Heavy / non-transactional:** `papers` reprocess-pdf (re-extract + re-embed) + purge + empty-trash (sqlite-vec
  vector removal); `summaries` reverify (local retrieval + NLI); `critical_review` candidate-generate (NLI); `workbench`
  `propose_row` (LLM egress).
- **I/O-mixed that must not re-fire on retry:** `paper_enrich` re-resolve + fill-metadata (**force** a fresh
  Crossref/OpenAlex fetch → double-egress risk); `agent_save_reference` (Crossref `resolve_doi` caches through the
  request connection); `sync` setup (round-trips the sync server before the commit).

The distinction the sweep drew: **wrap the whole handler** when it's pure-DB or idempotent (cached) I/O; **leave raw**
when a retry would repeat an un-cached fetch, an LLM call, a heavy re-extraction, or a vector-store mutation. (No
engine-level `BEGIN IMMEDIATE`: the rejected alternative would force reads + the inc 273–278 long-job fetch
connections to grab the write lock, re-introducing the starvation just removed.)

## Manual verification script

Hammer a couple of converted short-write endpoints concurrently (e.g. rapid `POST /papers/{id}/read`-adjacent writes
+ a background scan) — they return a value instead of a `database is locked` 500. The QA driver's route_15 (axes) /
route_50 (read-marker) repro from the 2026-07-02 runs should no longer 500 on the converted endpoints.

## Pytest

`tests/test_short_write_sweep.py` (the invariant guard) green; each converted router's suite green (findings 18,
saved/urls/annotations 19, feed/wanted 26, papers 52, axes 32, duplicates/critical/summaries 128, gaps/discovery/agent
+ my-pubs/settings + workbench all green). Full suite: **1237 passed, 1 skipped** (24 min).
