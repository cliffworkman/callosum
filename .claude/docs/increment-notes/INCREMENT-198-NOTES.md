# Increment 198 — accounts SP3b: the client sync engine + `sync_uid` identity (top-level collections)

## Implemented

The **client sync engine** (the pull → decrypt → merge → apply → push loop) over an injectable transport, plus the
**`sync_uid` global-identity layer** that makes multi-device sync correct. **No live egress this slice** — a fake
in-memory transport drives the tests; the reference sync-server (where ciphertext actually leaves) is the next slice
("engine first, server next"). Scope = the **top-level, FK-free collections (papers, tags, axes)**, the maintainer's
chosen first slice; the FK-bearing tables + FK-translation are a focused follow-on.

- **`app/backend/persistence/schema_sync.py`** (+ re-export from `schema.py`) — new **`sync_identity`** table
  (`collection`, `local_id`, `sync_uid`; PK `(collection, local_id)`, UNIQUE `(collection, sync_uid)`). Local-only;
  never in `SYNCABLE`, never synced.
- **`alembic/versions/0023_sync_identity.py`** — create `sync_identity`, additive + guarded (revises `0022_sync`).
  No backfill — the engine assigns uids lazily.
- **`app/backend/sync/changeset.py`** (revised) — `SyncableCollection` gains `pk` (the local-id column; default
  `"id"`); the transported payload is the row **minus its local PK** (device-independent content). `SYNCABLE` narrows
  to **papers/tags/axes**. New identity helpers `uid_map` / `local_id_for_uid` / `bind_identity` / `forget_identity` /
  `ensure_identities` (assigns a `uuid4` to any current row lacking a `sync_identity` entry — the canonical point a
  device-local row gains its global id). `collect_local` now keys on `(collection, sync_uid)` (via the map). `Key` =
  `(collection, sync_uid)`. `local_changeset` calls `ensure_identities` first (self-contained). `read_sync_state` /
  `merge_remote` / `record_hash` unchanged (generic on the key).
- **`app/backend/sync/engine.py`** (new) — `SyncBlob` (collection, record_id=sync_uid, version, deleted,
  ciphertext|None) + `PullResult` + the `SyncTransport` Protocol (`pull(since) → {records, seq}` / `push(records) →
  seq`) + `SyncRunResult`. `run_sync(conn, dek, transport, *, since=0)`:
  1. `pull(since)` → decrypt each non-tombstone blob (`decrypt_payload`, **fails closed**) → `RemoteRecord`s.
  2. `merge_remote` over the local sync_state versions + the local changeset (the locally-changed set) → remote
     winners + conflicts.
  3. **apply** each winner (`_apply_record`: UPDATE-in-place by sync_uid / INSERT+bind a new identity / DELETE+forget
     on a tombstone — never INSERT-OR-REPLACE; `_coerce_for_write` writes only known columns + parses ISO strings back
     to datetimes for DateTime columns; `_typed_pk` compares integer PKs as ints) + update `sync_state`.
  4. record conflicts into `sync_conflicts` (`_json_safe` normalizes the losing payload for the JSON column).
  5. recompute the local changeset (post-apply) → encrypt + `push` → update `sync_state` (+ `forget_identity` on a
     pushed tombstone).
  - The engine is **cursor-store-agnostic** (`since` in, `new_cursor` out — the caller persists; the
    endpoint/SP3c wires it) and **transport-agnostic** (Protocol). It holds only the unsealed **DEK**; the transport
    only ever sees opaque AES-GCM blobs.

## Key technical detail

**Cross-device identity is the crux:** device-local auto-increment `id`s differ across devices, so the engine keys on
a global `sync_uid` (UUID) and transports payloads **without the local PK**. The `sync_identity` map (collection,
local_id ↔ sync_uid) does the translation in both directions; on apply, a remote `sync_uid` either maps to an existing
local row (UPDATE) or is new (INSERT the row, then bind `new_local_id ↔ sync_uid`). This leaves the domain tables
untouched and is the same layer FK-translation will reuse (resolve a referenced row's sync_uid ↔ local id).

**The content-hash round-trip is stable across encrypt/decrypt + datetime coercion:** `record_hash` and
`encrypt_payload` both serialize with `default=str`, and `_coerce_for_write` parses the decrypted ISO string back to a
datetime — so a `datetime` and its round-tripped string hash identically, and a converged pair re-syncs to **0 pushes
/ 0 applies** (asserted). The one gotcha surfaced in testing: `sync_conflicts.losing_payload` is a JSON column and the
local payload carries a raw `datetime` (created_at) → `_json_safe` normalizes it before insert.

## Manual verification script

This slice has **no UI / no endpoint** — it's exercised by the hermetic engine tests (a fake transport + two simulated
devices with independent local ids). To eyeball the convergence logic:
`HF_HUB_OFFLINE=1 python -m pytest tests/test_sync_engine.py -q` → 4 passed (converge-via-sync_uid + 0-push re-sync;
concurrent-edit conflict surfaced + recoverable; tombstone propagates + idempotent; foreign blob fails closed).

## Gates

- **pytest:** full suite green — **688 passed, 1 skipped** (+4 `tests/test_sync_engine.py`; the SP3a changeset test
  `test_local_changeset_tracks_add_edit_delete` updated to assert on the `sync_uid` instead of the local PK).
- **ruff** check + format clean.
- **migration head** via `alembic_head()` (no test edit; head now `0023_sync_identity`).
- **QA surface unchanged** — 132/132 API + 661/661 FE, 0 uncovered (no new endpoint/control this slice → no route).
- **Audit** `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` **PASS**.
- **Principles/A-A:** the SP3 gate was run in SP3a (A5 sovereignty via E2E + opt-in; A4 via conflict-surfacing). This
  slice adds no new claim/signal → non-triggering beyond honoring those (real E2E held: DEK never crosses the
  transport; opaque blobs only; conflicts surfaced).
- **No new dependency, no egress, no UI.**

## NEXT

The **FK-bearing collections** (paper_tags, annotations, notes, summaries, manual cluster_node_papers) + the
**FK-translation layer** (resolve a referenced row's sync_uid ↔ local id via `sync_identity`) — a focused follow-on.
Then the **reference sync-server** (the slice where ciphertext actually leaves → its own audit) + the `app_settings`
sync cursor wiring. Then **SP3c** (the opt-in Settings → Sync UI + conflict review). PDF-file sync, real-time, CRDTs
remain deferred.
