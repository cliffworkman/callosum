# Security audit — accounts SP3b: the sync engine (client) + sync_uid identity (top-level collections)

**Date:** 2026-06-29
**Feature:** The client **sync engine** — pull→decrypt→merge→**apply (write decrypted remote rows into the local
DB)**→push — over an injectable `SyncTransport` (a fake in tests; **no live server / no egress this slice**, per the
maintainer's "engine first, server next"). Plus the **`sync_uid` global identity** (a UUID per syncable row, held in
the new `sync_identity` map) that makes cross-device sync correct (local auto-increment ids differ across devices).
Scope: the **top-level, FK-free collections — papers, tags, axes**. Files: `app/backend/sync/engine.py` (new),
`app/backend/sync/changeset.py` (revised to key on sync_uid), `app/backend/persistence/schema_sync.py` +
`schema.py` (+`sync_identity`), `alembic/versions/0023_sync_identity.py`. Design spec
`…/specs/2026-06-29-accounts-sync-design.md`; builds on SP3a (`crypto.py`).
**Audit triggers:** a new write path (decrypted remote data → the local DB); a schema migration; the egress contract.

## Threat review
- **Cross-device identity — PASS.** Sync keys every record on a `sync_uid` (UUID, `sync_identity` map), never the
  device-local int `id`. The transported payload is the row **minus its local PK** (`collect_local` excludes
  `c.pk`), so a record's content is device-independent and device B's rows can't be conflated with A's. **Proven:**
  `test_two_devices_converge_via_sync_uid` — two DBs with independent local ids converge to the same content per uid
  while the uid→local_id maps differ (`assert _uid_to_localid(ea) != _uid_to_localid(eb)`).
- **Apply write-back safety — PASS.** Decrypted remote rows are upserted **by sync_uid** (`_apply_record`:
  find-local-id-for-uid → UPDATE in place, else INSERT + bind a new identity) — **not** INSERT-OR-REPLACE, so no
  FK-cascade surprise. A tombstone DELETEs the mapped row + `forget_identity` (so a later re-create is a clean
  insert, not a stale-id UPDATE-of-nothing). `_coerce_for_write` writes **only columns the table actually has**
  (`k in table.c`) — a decrypted payload cannot inject columns (rule #4). Table/columns come from the constant
  `SYNCABLE` registry, never request data (rule #3); all SQL is bound-param SQLAlchemy Core. Integer PKs are
  compared as ints (`_typed_pk`) so SQLite affinity can't silently mismatch.
- **Crypto boundary / E2E — PASS.** `run_sync` takes the already-unsealed **DEK**; it never sees a passphrase or
  recovery code, and the transport only ever receives **opaque AES-GCM blobs** (`encrypt_payload`) — the DEK never
  crosses the `SyncTransport`. A decrypt failure **fails closed**: a foreign/tampered blob raises `SyncCryptoError`
  and **nothing is written** (`test_foreign_remote_blob_fails_closed` asserts the run raises AND the DB stays empty).
- **Conflict surfacing (A4) — PASS.** A remote winner that was also changed locally records the **losing local
  payload** into `sync_conflicts` (JSON-normalized via `_json_safe`), recoverable — never silently dropped
  (`test_concurrent_edit_surfaces_conflict`: remote wins the live row, B's edit is preserved in `sync_conflicts`).
- **No egress this slice — PASS.** The transport is injected; there is **no in-repo default** and no endpoint wires
  it (the reference server is the next slice). The tests use an in-memory `FakeTransport`; nothing leaves the
  machine. The egress invariant (#3, Gemini gate) is untouched.
- **Idempotence / no data loss — PASS.** Re-sync after convergence pushes/applies nothing
  (`test_two_devices_converge` second round: `pushed == 0 and applied == 0`) — the content-hash round-trip through
  encrypt/decrypt + datetime coercion is stable, so no phantom re-sync. A propagated delete is idempotent
  (`test_tombstone_propagates_and_resync_is_idempotent`: no resurrection, no duplicate).
- **Migration — PASS.** `0023_sync_identity` creates `sync_identity` (additive + guarded `if not in table_names`,
  revises `0022_sync`); no backfill (the engine assigns uids lazily via `ensure_identities`). Head asserted via
  `alembic_head()` (no hardcoded revision). `sync_identity`/`sync_state`/`sync_conflicts` are **local-only** — never
  in `SYNCABLE`, never synced. No new dependency (`uuid`, `json`, `cryptography` all already present).

## Negative-path checks (concrete results)
- Two devices, independent local ids → converge via sync_uid; uid→local_id maps differ. **PASS.**
- Foreign-DEK remote blob → `run_sync` raises `SyncCryptoError`, DB unchanged. **PASS.**
- Concurrent edit → exactly 1 surfaced conflict, remote wins the live row, local loser recoverable. **PASS.**
- Tombstone → delete propagates; re-sync applies/pushes nothing, no resurrection. **PASS.**
- `ruff check` clean; the full pytest suite green (see increment notes).

## Result
**Security Audit: PASS.** Local, no-egress, fail-closed, bound-param; cross-device identity + apply are
sync_uid-keyed and column-validated; conflicts surfaced (A4); E2E DEK boundary intact. The **live egress** boundary
(where ciphertext actually leaves) is the next slice (the reference sync-server) and gets its own audit.

---

## Addendum — inc 199: FK-translation for child tables (notes, annotations)

**Feature:** extend `SYNCABLE` to the FK-bearing child tables **notes** + **annotations** (both: own `id` + a
`paper_id` FK to the already-synced `papers`), with a generic **FK-translation layer**. Same engine, same apply path
— **no new endpoint / migration / egress / dependency** (sync_identity + the engine already exist). Files:
`changeset.py` (`SyncableCollection.fks`/`.drop`; `collect_local` translates FK columns local-id → the referenced
row's sync_uid + applies `drop`), `engine.py` (`_apply_record` translates back uid → this device's local id; apply
runs referenced-collections-first). Deferred (recorded): `paper_tags` (composite-PK link table — a distinct identity
model), `summaries` (JSON-embedded scope refs + version-keyed verification), `cluster_node_papers` (depends on
un-synced `cluster_nodes`).

- **FK-translation safety — PASS.** Outbound, an FK column's device-local id is replaced by the referenced row's
  **sync_uid** (device-independent), so the content + its hash are identical on every device. Inbound,
  `_apply_record` resolves each FK sync_uid → **this device's** local id via `local_id_for_uid(referenced
  collection)`; the `fks` map is from the constant registry, never the payload (rule #3); a translated FK value is an
  int PK (`_typed_pk`). **Proven:** `test_child_tables_fk_translate_across_devices` — a note + an annotation sync to a
  device whose local ids are offset, and their `paper_id` lands on that device's local paper (`note.paper_id == bpid
  and bpid != pid_a`).
- **Apply ordering — PASS.** Remote winners are applied **referenced-first** (sorted by `SYNCABLE` rank), so a
  record's FK targets exist locally before it is written. A record whose FK target still isn't local is **skipped**
  (`_apply_record` returns False; its `sync_state` is not advanced) rather than written with a dangling/wrong FK —
  conservative, no corruption. (With referenced-first ordering + same-batch sync this is rare; the residual "skipped
  link not retried until re-pushed" is a documented v1 limitation, not a safety hole.)
- **Device-local data not leaked — PASS.** `annotations.attachment_id` is a **per-device** pointer (PDFs aren't
  synced) → declared in `drop`, so it's omitted from the payload entirely (never encrypted/transported) and applied
  as NULL on the far device (the highlight re-associates by paper + page + bboxes). Test asserts `ann.attachment_id
  is None` on the synced copy.
- **Hash round-trip — PASS.** The uid-form FK payload round-trips through encrypt/decrypt + apply stably → a converged
  pair re-syncs to **0 push / 0 apply** (`test_child_tables_… again.pushed == 0 and again.applied == 0`).
- **Unchanged posture — PASS.** No new write *surface* (the same `run_sync`); no egress (fake transport); fail-closed
  decrypt unchanged; no new dependency/endpoint/migration. QA surface unchanged (engine-only).

**Addendum result: PASS.**
