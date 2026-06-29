# Increment 197 — accounts SP3a: E2E sync crypto + local change-tracking foundation (no egress)

The first slice of **opt-in, end-to-end-encrypted, multi-device, metadata-first sync** (design spec
`…/specs/2026-06-29-accounts-sync-design.md`). SP3 is the **invariant-touching** feature (the only step that moves
library data off the machine), so the **Principles/A-A gate was run** before design: **A5** (sovereignty over what
leaves the machine) is honored by E2E + opt-in/default-off; **A4** (no silent overwrite) by **conflict-surfacing,
not clobbering**. Three non-negotiables: **real E2E**, **opt-in/default-off**, **conflicts surfaced**. SP3a ships the
**local, hermetically-testable, no-egress** core (crypto + change-tracking/merge); SP3b adds the endpoint + push/pull;
SP3c the opt-in UI + conflict review.

## Implemented

- **`app/backend/sync/crypto.py`** — a random **DEK** encrypts each record (**AES-256-GCM**, fresh per-record
  nonce). The DEK is **sealed** under a **passphrase** KEK *and* a **recovery-code** KEK (both via **`scrypt`**,
  `cryptography.hazmat` — already a dep via `PyJWT[crypto]`, **no new dependency**). `create_keyring`/
  `unlock_with_passphrase`/`unlock_with_recovery`/`rewrap_passphrase`/`encrypt_payload`/`decrypt_payload`. The
  **keyring** (the two sealed-DEK blobs + salts) is the only thing persisted (SP3c) — **no key/passphrase/code/
  plaintext**. Wrong key / tampered blob → `SyncCryptoError` (**fails closed**). **No server-side reset** — the
  recovery code is the only non-passphrase unlock. Rotation re-wraps without re-encrypting data.
- **`app/backend/sync/changeset.py`** — change-tracking is a **hash-diff** vs `sync_state` (no write-hooks):
  `collect_local` (generic over the `SYNCABLE` registry; table/columns are constants → rule #3), `record_hash`,
  `local_changeset` (add/edit → change with bumped version; gone → tombstone). The merge is **per-record LWW that
  surfaces conflicts** — `merge_remote` returns `to_apply` (remote wins when strictly newer) + `conflicts` (the
  overwritten **local** payload kept, recoverable — A4); pure of network/crypto.
- **`app/backend/persistence/schema_sync.py`** + **migration `0022_sync`** — `sync_state` (per-record
  content_hash/version/tombstone) + `sync_conflicts` (the surfaced losing side). **Local-only — never synced;**
  additive/guarded; re-exported from `schema.py`.
- **`SYNCABLE`** (the syncable set, v1) = papers, tags, paper_tags, notes, annotations, axes, summaries. **NOT
  synced** (rebuilt/re-linked locally on each device): embeddings/vectors, derived signals/caches, **and PDF
  bytes**. (cluster_node_papers-manual + profile → SP3b, filtered/field-selected.)

## Key technical detail

**Two-KEK E2E:** a single random DEK is wrapped twice (passphrase + recovery), so the passphrase rotates without
re-encrypting data and the recovery code is an independent unlock — and the server (SP3b) only ever sees AES-GCM
ciphertext keyed by a DEK it never receives. **Change-tracking without hooks:** hashing each row's canonical payload
and diffing against `sync_state` means *no* instrumentation at the dozens of write sites — the change-set is computed
at sync time. **LWW + A4:** remote (higher version) wins, but the overwritten local payload is **kept** in
`sync_conflicts` (surfaced for review), never silently dropped.

## Manual verification script

Hermetic only (no UI/endpoint in this slice): `pytest tests/test_sync_crypto.py`. The live multi-device round-trip
is gated on SP3b (the endpoint) + the maintainer standing it up.

## Gates

- **pytest 684 passed, 1 skipped** (+14 `tests/test_sync_crypto.py`: key round-trips [passphrase + recovery],
  fail-closed on wrong key/tampered/foreign-DEK, the **opaque-blob guarantee** [no plaintext in the ciphertext],
  rotation, dict round-trip; change-tracking add/edit/delete against a seeded DB; merge newer/conflict/older/
  tombstone). `ruff` clean.
- **Audit `…/security-audits/2026-06-29_sync-crypto-sp3a.md` PASS** (real E2E, per-record nonces, fail-closed, the
  opaque-blob guarantee, conflict-surfacing-not-clobber; no egress/endpoint/dependency this slice).
- **QA (rule #10):** no new API/FE surface (pure backend modules + local-only tables) → surface **132/132 API +
  661/661 FE, 0 uncovered**, no new route. **Principles → gate run** (A5/A4 honored; the three non-negotiables are
  the audit's pass conditions). **Migration 0022** (additive/guarded; head via `alembic_head()`). No new dependency.

## NEXT

**SP3b** — the **account-authenticated sync endpoint** (OIDC-gated; stores opaque per-record blobs + assigns
sequences) + the client **push/pull engine** (collect → encrypt → push; pull → decrypt → merge → apply + record
conflicts). **The first slice where ciphertext leaves the machine — its own security audit + the maintainer stands
up the endpoint.** Then **SP3c** — the opt-in Settings → Sync UI (passphrase/recovery flow, per-device enroll, sync
status, the conflict review) + a rule-#11 experience pass. (PDF-file sync + real-time + CRDTs remain deferred.)
