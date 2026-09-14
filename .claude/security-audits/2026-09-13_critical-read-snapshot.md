# Security audit — persisted single-paper critique snapshot (inc 601)

**Date:** 2026-09-13
**Scope:** a new persistent table (`critical_read_snapshots`, migration 0083), a worker write in
`_run_critical_read_job` (`routers/critical_review.py`), a new read endpoint
`GET /papers/{paper_id}/critical-read/snapshot` (`routers/critical_review_snapshot.py`), repo functions
(`critical_review_repo.py`), and the frontend modal (`08x2_critical_modal.jsx`).
**Trigger:** audit gate #1 (new API endpoint) + #3 (new file-write/persistence path) + #5 (net-new feature
spanning 3+ files).

## What it does
The single-paper Critical Read (backlog #12) already computed a deterministic Tier-1 backbone (method signals +
corpus-contested claims) but discarded it in the in-memory job store. This persists exactly that backbone,
one current-only row per paper, so a reader-launched critique (inc 598) is reopenable without recompute. The
critique **computation is unchanged and already audited**; this increment only caches and re-reads its output.

## Threat review
- **Input validation.** The only request input is `paper_id` (a path int, FastAPI-validated). No body, no
  free-text, no client-supplied payload is persisted — the stored `backbone_json` is produced solely by the
  server's own critique computation; the client can never write a snapshot (there is no POST/PUT to this table).
- **Injection.** All DB access is SQLAlchemy Core bound parameters (rule #3): `read_backbone_snapshot` /
  `save_backbone_snapshot` use `select`/`insert`/`delete` with bound values. No SQL text is built from input.
- **Data egress.** **None.** The read endpoint queries local SQLite only; the worker write is local; the content
  fingerprint (`compute_content_fingerprint`) is a local chunk/attachment hash. No external call, no provider,
  not the Gemini gate. `compute_content_fingerprint` is called on read only for the paper in the path.
- **Output encoding / trust.** The persisted payload is validated on read through the canonical
  `ScrutinyBackboneResponse` pydantic schema (+ a version check); an incompatible or unparseable payload returns
  `refresh_required` rather than being rendered — so a corrupted/old row can neither crash the endpoint nor
  surface a malformed critique. The frontend renders values as React text nodes (no `dangerouslySetInnerHTML`).
- **Resource caps.** Exactly one row per paper (UNIQUE(paper_id); delete-then-insert on write) — the table
  cannot grow unbounded per paper. The backbone payload is bounded by the critique computation's own caps
  (≤12 claim sentences, bounded method signals — unchanged). The read endpoint returns one row.
- **Race / integrity.** Snapshot replacement is guarded by a monotonic `requested_at`: an out-of-order (older)
  run's completion never overwrites a newer snapshot (`save_backbone_snapshot` returns False). The start
  endpoint dedups to one in-flight run per paper (`create_or_get_active_matching`), so overlap is prevented at
  the source. Best-effort persistence: a write failure is swallowed and never fails the critique the user has.
- **File-path safety.** None — no filesystem path is built or read.
- **Auth / access.** Same posture as every other `/papers/{id}` route (local single-user; the existing
  `AccessControlMiddleware` gate applies unchanged when Remote access is on — a read-only GET).
- **FK / lifecycle.** `paper_id` FK ON DELETE CASCADE — a purged paper's snapshot is removed automatically
  (verified by test). No orphan rows.
- **Supply chain.** No new dependency (stdlib `datetime`, existing pydantic/SQLAlchemy, existing
  `compute_content_fingerprint`).

## Negative-path checks (concrete results, `tests/test_critical_read_snapshot.py`)
- No snapshot saved → endpoint returns `backbone: null` (no crash).
- Version-mismatched payload → `refresh_required: true`, `backbone: null` (no misrender).
- Structurally-invalid payload (`method_signals` not a list) → `refresh_required: true` (parse guarded).
- Out-of-order older run → write refused; the newer snapshot is retained.
- Content fingerprint changed → `stale: true` (the narrow, honest hint); unchanged → `stale: false`.
- Paper hard-deleted → snapshot cascade-removed (0 rows).
- Egress: no external host is contacted (local SQLite + local fingerprint only).

## Result
**Security Audit: PASS.** Local-only read/write of a server-produced, schema-validated, size-bounded,
one-row-per-paper cache of an already-audited computation; no egress, no injection surface, no client-writable
payload, race-guarded replacement, and honest fail-closed handling of incompatible/corrupt rows.
