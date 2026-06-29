# Security audit — accounts SP3a: sync crypto + local change-tracking foundation

**Date:** 2026-06-29
**Status:** COMPLETE.
**Feature:** The **local, no-egress** foundation for E2E-encrypted multi-device sync (design spec
`…/specs/2026-06-29-accounts-sync-design.md`): the encryption layer (`app/backend/sync/crypto.py` — passphrase →
`scrypt` KEK → AES-256-GCM record encryption; a recovery code as an independent unlock; passphrase rotation), a
`sync_state`/`sync_conflicts` schema (`schema_sync.py` + migration `0022_sync`), and a content-hash change-tracking +
per-record last-write-wins **conflict-surfacing** merge core (`app/backend/sync/changeset.py`). **No server, no
egress, no new endpoint** in this slice (that's SP3b). **Audit triggers:** crypto/secret handling; a feature
spanning 3+ files; a schema migration.

## The SP3 acceptance criteria this slice owns
1. **Real E2E — PASS.** The DEK is random; KEKs derive from the **passphrase/recovery code on the machine** (`scrypt`,
   `cryptography.hazmat`); the keyring persists only the **sealed** DEK + salts (no key/passphrase/code/plaintext).
   The DEK/passphrase/code are never returned, never logged, and (SP3a) never transmitted.
3. **Conflicts surfaced — PASS.** `merge_remote` records the overwritten **local** payload as a `Conflict` (kept in
   `sync_conflicts`, recoverable) whenever a remote win collides with a local change — never a silent drop (A4).
   (#2 opt-in/default-off is a SP3b/SP3c concern — this slice wires no sync.)

## Threat review
- **Key derivation — PASS.** `scrypt` N=2¹⁵/r=8/p=1 (~32 MB, interactive-grade), per-vault random 16-byte salt; the
  derived key + passphrase are local-only, never written in plaintext / never logged.
- **Symmetric encryption — PASS.** AES-256-GCM with a **fresh random 12-byte nonce per `_seal` call** (no nonce
  reuse); the auth tag is verified on `_open`; a wrong key / tampered blob → `InvalidTag` → `SyncCryptoError` (**fails
  closed**, tested). The two-KEK design lets the passphrase rotate without re-encrypting data (`rewrap_passphrase`).
- **Recovery code — PASS.** A ~115-bit base32 code; an independent KEK unwraps the same DEK; **no server escrow / no
  server-side reset** — the code is the only non-passphrase recovery (tested incl. format/case normalization).
- **Opaque-blob guarantee — PASS.** `encrypt_payload` → base64(nonce‖AES-GCM ct); a test asserts a known plaintext
  value appears **neither** in the base64 string **nor** the raw bytes. The blob a future endpoint stores carries no
  field name or value.
- **Merge correctness — PASS.** Per-record LWW by version; concurrent change → a surfaced conflict (loser kept);
  remote older/equal → skipped; tombstones apply without resurrection (tested). `collect_local` reads table/columns
  from the **constant** `SYNCABLE` registry, never request data (rule #3).
- **No egress — PASS.** This slice makes no network call; nothing leaves the machine (the engine/endpoint is SP3b).
- **Supply chain — PASS.** No new dependency (`cryptography` present via `PyJWT[crypto]`).
- **Migration — PASS.** `sync_state` + `sync_conflicts` additive + guarded (the 0021 pattern); head derived by
  `alembic_head()` (no hardcoded-revision test edit). Local-only tables; never synced.

## Negative-path checks (verified by `tests/test_sync_crypto.py`, 14 tests)
- wrong passphrase / wrong recovery code → `SyncCryptoError` (fails closed). ✔
- a tampered ciphertext → `SyncCryptoError`; a different keyring's DEK can't decrypt. ✔
- the encrypted blob contains no known plaintext (string + raw bytes). ✔
- change-tracking: seeded rows are new → recorded → quiescent → an edit is one change (v2) → a delete is a tombstone. ✔
- merge: newer-applies / concurrent-surfaces-conflict / older-skipped / tombstone-applies. ✔

## Result
**Security Audit: PASS.** Real E2E (passphrase/recovery → scrypt KEK → AES-256-GCM; the keyring holds only the sealed
DEK; nothing secret leaves the machine), per-record nonces, fail-closed decryption, the opaque-blob guarantee, and a
conflict-surfacing merge that never silently drops a local edit (A4). No egress, no new endpoint, no new dependency
in this slice. SP3b (the sync endpoint + push/pull — the first slice where ciphertext leaves) gets its own audit.
