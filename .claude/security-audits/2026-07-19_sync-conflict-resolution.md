# Security audit — SP3c backend slice: list + resolve sync conflicts

**Date:** 2026-07-19
**Feature:** Two new local `/sync/*` endpoints — `GET /sync/conflicts` (list unresolved rows, each paired with the
live domain value for a mine-vs-current diff) and `POST /sync/conflicts/{conflict_id}/resolve {side: "mine"|"theirs"}`
— the read/resolve half of the conflict-review screen (the write/list half of SP3c; the frontend is planned
separately). Files: `app/backend/api/routers/sync.py` (2 new endpoints), `app/backend/persistence/sync_conflicts_repo.py`
(new), `app/backend/sync/engine.py` (new `apply_conflict_resolution`), `.claude/qa-routes/route_46_sync.md` (extended).
No migration (reads/writes the existing `sync_conflicts` table from SP3a). Design specs
`…/specs/2026-06-29-accounts-sync-design.md` + `…-sync-server-design.md` (both name this exact slice as SP3c).
**Audit triggers:** a new API endpoint (rule #1); a new write path onto domain tables from a resolve action.

## Threat review

- **The request body cannot inject data — PASS.** `ResolveConflictBody` accepts exactly one field, `side` (a
  2-value enum, "mine"|"theirs"); there is no `payload`/`value`/free-form field anywhere in the request shape. The
  data ever written for a "mine" resolution is **always** `sync_conflicts.losing_payload` — something the engine
  itself captured from a legitimate local edit at merge time (`run_sync`/`merge_remote`, SP3a/b), never anything
  the resolve request supplies. A malicious or buggy client can pick *which* stored side wins; it cannot make the
  server write arbitrary new content.
- **"Mine" reuses the exact remote-apply write path — PASS.** `apply_conflict_resolution` builds a synthetic
  `RemoteRecord` from the stored `losing_payload` and hands it to the same `_apply_record`/`_apply_link` dispatch a
  real remote winner goes through — same `_coerce_for_write` column allowlist (a payload can't write a column the
  table doesn't have, rule #4), same FK-translation (`by_name`, the constant `SYNCABLE` registry — rule #3, never
  request data), same link-table (composite-PK) handling. No new ad-hoc UPDATE statement was written for this
  slice; the resolution can't do anything a normal sync apply couldn't already do.
- **"Theirs" is inert — PASS.** The remote value already won and is live in the domain table by the time a
  conflict row exists (the engine applies before recording the conflict); resolving "theirs" only flips
  `sync_conflicts.resolved`. **Proven:** `test_resolve_theirs_just_marks_resolved` asserts the domain value is
  unchanged after resolving.
- **Fails closed, never silently succeeds — PASS.** `resolve_conflict` (repo) returns `False` — surfaced by the
  router as **409** — for an unknown id, an already-resolved id, or (for "mine") when the underlying apply itself
  returns `False` (an unresolved FK dependency, e.g. the referenced paper isn't local yet). The conflict is marked
  resolved **only** after a successful apply — there is no path that flips `resolved=1` without the value having
  actually been restored. **Proven:** `test_resolve_unknown_or_already_resolved_conflict_fails_closed`.
- **No versioning workaround, no egress — PASS.** The resolution deliberately does **not** touch `sync_state` or
  invent a new version number; it relies entirely on the *existing* hash-diff changeset mechanism (`changeset.py`)
  — the next ordinary `run_sync` sees the restored value differs from what's recorded and pushes it as a normal
  local change, out-versioning the remote side. Neither new endpoint touches a transport, a passphrase, or the DEK
  — both are pure local reads/writes of already-decrypted domain/bookkeeping tables. Zero new egress surface.
  **Proven:** `test_resolve_mine_restores_the_losing_value` confirms the domain value round-trips back to the
  local edit after resolution (the next-sync-pushes-it behavior is exercised by the existing engine-level
  convergence tests, unchanged by this slice).
- **Conflicts are surfaced, never auto-picked (value A4, unchanged) — PASS.** `GET /sync/conflicts` lists only
  unresolved rows; nothing in this slice auto-resolves anything. `list_sync_conflicts` pairs each row with the
  live domain value (`current`, via the same `collect_local` device-independent-payload transform the sync engine
  itself uses) purely for **display** (a mine-vs-current diff) — read-only, no write side effect.
- **Recreating a deleted row is intentional, not an oversight.** If the local row was deleted after the conflict
  was recorded, `_apply_record`'s insert branch re-creates it (bound to the same `sync_uid`) rather than failing —
  "keep mine" legitimately means restoring the value even if something else removed the row in between. This
  mirrors exactly how a normal remote-apply insert already behaves; no new logic was added for it.
- **No multi-tenant/user-scoping gap.** `sync_conflicts` is a **local-only** table (schema comment: "never synced")
  in a single-user, local-first app — the same trust model as every other local table (papers, tags, …). There is
  no cross-user boundary to enforce here; this is unchanged by the new endpoints.
- **QA surface — PASS.** `route_46_sync.md` extended with both endpoints + standing assertions (fails-closed
  resolve, no-default side, theirs-is-inert); `tools/qa/build_surface_map.py check` → 250/250 API, 0 uncovered.

## Negative-path checks (concrete results)

- Resolving `side="theirs"` → 200, conflict no longer listed, domain value unchanged. **PASS.**
- Resolving `side="mine"` → 200, conflict no longer listed, domain value restored to the losing payload. **PASS.**
- Resolving an unknown conflict id (`999`) → **409**. **PASS.**
- Resolving an already-resolved conflict id a second time → **409** (no silent no-op-as-success). **PASS.**
- `GET /sync/conflicts` returns `losing_payload` (mine) and `current` (theirs) as distinct, correctly-differing
  values for a genuine two-device conflict (produced via the same two-device recipe as `test_sync_engine.py`).
  **PASS.**
- `ruff check` + `ruff format --check` clean on all touched files; `pytest tests/test_sync_endpoints.py
  tests/test_sync_engine.py tests/test_sync_server.py -q` → 29 passed.

## Result

**Security Audit: PASS.** The new endpoints add no egress, no new write surface beyond what the existing
remote-apply path already permits, and fail closed on every invalid resolve. The request body cannot supply data
to write — only a choice between two server-held values. Conflicts remain surfaced-not-auto-resolved (A4). The
frontend half of SP3c (the Settings → Sync UI + the conflict-review screen itself) is a separate, subsequent
piece of work and gets its own review when it lands.
