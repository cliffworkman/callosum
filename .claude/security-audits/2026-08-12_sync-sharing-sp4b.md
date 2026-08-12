# Security audit — Sync SP4b: share (round 3, item #4, stage B of 4)

**Date:** 2026-08-12
**Status:** COMPLETE.
**Feature:** the sender side of backlog #15's SP4 sharing — a new hybrid-encryption "sealed" content-key wrap
(`app/backend/sync/sharing.py`, X25519 ECDH + HKDF-SHA256 + AES-256-GCM, the same construction shape as
libsodium's `crypto_box_seal` / an HPKE base-mode ciphersuite), a new sync-server `shares` table + endpoint
(`sync_server/`, reachable only via the caller's own authenticated `sub` as sender), and a local
`POST /sync/share` endpoint that reuses the already-audited B2 `build_bundle()` (portable, no-PDF payload,
`2026-07-01_library-bundle.md`) and `crypto.py`'s existing AES-GCM primitive for content encryption. **This
stage is sender-only** — no receiving/importing capability exists yet (SP4c). Design:
`.claude/backups/plans/2026-08-12_sync-sp4b-share.md`.
**Audit triggers:** new API endpoints (1 local + 1 server); a new crypto primitive; a new server table.

## Threat review

- **The wrap/unwrap construction — soundness — PASS.** X25519 ECDH between a **fresh, one-time ephemeral
  keypair** (generated per call, never persisted) and the recipient's long-term public key, run through
  HKDF-SHA256 (a fixed versioned `info=b"callosum-share-v1"`) to derive a 32-byte AES key, then AES-256-GCM
  with a fresh random nonce encrypts the content key — the ephemeral public key is bound as AES-GCM associated
  data, so swapping it (even for another valid X25519 key) invalidates the auth tag rather than silently
  deriving a different, wrong shared secret (`test_tampered_ephemeral_public_key_fails_closed`). This is the
  same shape as libsodium's `crypto_box_seal` and RFC 9180 HPKE's base-mode DHKEM(X25519)+HKDF-SHA256+AES-GCM
  ciphersuite — a standard, reviewed construction, not a novel design. `cryptography`'s `X25519PrivateKey.
  exchange`/`HKDF`/`AESGCM` primitives are used directly (no hand-rolled math). Verified empirically (not just
  reasoned about): a real ECDH round-trip between two independently generated keypairs produces a symmetric
  shared secret (`tests/test_sync_sharing.py::test_wrap_unwrap_roundtrip`); a wrong recipient private key,
  tampered ciphertext, and tampered ephemeral key all fail closed with `SyncCryptoError`; repeated wraps of the
  identical content key never reuse an ephemeral key or nonce.
- **No sender authentication in the envelope — why that's safe here — PASS.** The envelope itself carries no
  signature or MAC tying it to the sender (matching `crypto_box_seal`'s own documented posture — anonymous
  sender, confidentiality-only). This is safe because the `shares.sender_sub` column is populated exclusively
  from `Identity.sub`, which `sync_server/auth.py`'s `_identity` dependency derives from the **verified bearer
  token** — never from the request body (`test_share_sender_sub_comes_from_token_not_body` proves an
  attacker-supplied `sender_sub` field in the JSON body is silently ignored by Pydantic, not honored). The
  transport layer is the authentication boundary; the envelope only needs to guarantee confidentiality.
- **Resource caps — PASS.** Local: `paper_ids` bounded 1–200 (`MAX_SHARE_PAPERS`, a Pydantic
  `Field(min_length=1, max_length=200)` — empty or oversized → 422); a selection resolving to zero actual
  papers (all ids nonexistent/trashed) → 422 ("none of the selected papers could be shared"), never an empty
  share. Server: `ciphertext` ≤ 21 MB (`MAX_SHARE_CIPHERTEXT_LEN`, matching `library_bundle.MAX_BUNDLE_BYTES`'s
  own ~20 MB headroom — duplicated as an independent literal rather than imported, since `sync_server` is
  tach-fenced from importing any `app.backend` module); `wrapped_key` ≤ 1000 bytes (a fixed-shape small
  envelope, not bulk data) — both tested (`test_create_share_rejects_oversized_wrapped_key`,
  `test_create_share_rejects_oversized_ciphertext`). The share endpoint reuses the exact same
  `_rate_limited`/per-`sub` `RateLimiter` every other server endpoint already uses (`test_share_rate_limit_applies`)
  — no new, unreviewed rate-limiting logic.
- **The recipient is always a previously fingerprint-surfaced id, never raw/unconfirmed — PASS.** The UI's
  `ShareModal` requires resolving a recipient via the **existing** `/sync/identity/lookup` endpoint (SP4a) —
  which surfaces a fingerprint with "confirm this matches what they told you" copy — before the passphrase
  field or the Share button even render. The backend endpoint independently re-resolves the recipient's
  public key via a **fresh** server lookup on every call (never a client-cached/stale key), and 404s if the
  recipient isn't registered — a share can never be silently created addressed to nobody.
- **Reuse of the already-audited B2 bundle payload — no new content-shape risk — PASS.** The share's plaintext
  content is `build_bundle(conn, scope="selection", paper_ids=...)`, called completely unmodified — the exact
  function `2026-07-01_library-bundle.md` already audited (no PDFs, bound-param SQL, bounded per-paper
  tag/annotation counts, `my_publications` axes never exported). SP4b adds no new serialization logic for the
  content itself; only the *key* needed new wrapping to reach a different person's key material.
- **Server input validation — PASS.** Pydantic caps on the new `CreateShareRequest` model (`recipient_sub` ≤
  255, `wrapped_key` ≤ 1000, `ciphertext` ≤ 21 MB); bound-param SQLAlchemy Core throughout
  (`share_store.create_share`) — no interpolated identifiers, no user-controlled SQL text.
- **Supply chain — PASS.** `cryptography.hazmat.primitives.kdf.hkdf.HKDF` and
  `cryptography.hazmat.primitives.ciphers.aead.AESGCM` — already available via the existing `cryptography`
  dependency (the same package SP4a's `identity.py` already uses for X25519). No new dependency.
- **Migration — PASS.** `shares` is a **new** table on `sync_server`'s existing `metadata` — created for free
  by the already-existing `metadata.create_all(engine)` lifespan call; no idempotent-ALTER dance needed.
- **Module boundary (tach) — PASS.** The new `app.backend.api.routers.sync` → `app.backend.metadata.
  library_bundle` import was verified against `tach.toml`'s declared module boundaries (`python -m tach check`
  passes) — `app.backend.metadata` isn't itself a fenced module, so this import is unrestricted by design, not
  by omission.

## Negative-path checks (concrete results)

- wrap/unwrap round-trip recovers the exact content key — **PASS** (`test_wrap_unwrap_roundtrip`).
- wrong recipient private key / tampered ciphertext / tampered ephemeral public key all fail closed with
  `SyncCryptoError` — **PASS** (`test_wrong_recipient_private_key_fails_closed`,
  `test_tampered_ciphertext_fails_closed`, `test_tampered_ephemeral_public_key_fails_closed`).
- wrap rejects wrong-length content keys / public keys — **PASS** (`test_wrap_rejects_wrong_length_inputs`).
- repeated wraps of the same content key never reuse an ephemeral key or nonce — **PASS**
  (`test_repeated_wraps_never_reuse_ephemeral_key_or_nonce`).
- malformed `WrappedKey` dicts fail closed — **PASS** (`test_wrapped_key_from_dict_rejects_malformed_data`).
- server: a share persists addressed to the correct `recipient_sub`, ids increment, auth required, oversized
  `wrapped_key`/`ciphertext` rejected, `sender_sub` cannot be spoofed via the body, rate limiting applies —
  **PASS** (7 tests in `tests/test_sync_server.py`).
- local endpoint: happy path creates a genuinely decryptable share (proved via the recipient's REAL private
  key, not just existence), refused when sync isn't ready, refused without a sharing identity, wrong passphrase
  fails closed with zero server-side egress, unknown recipient → 404, empty/oversized `paper_ids` → 422,
  all-nonexistent `paper_ids` → 422 — **PASS** (7 tests in `tests/test_sync_endpoints.py`, including a real
  end-to-end crypto round-trip: alice shares a real paper, bob's real X25519 private key unwraps the content
  key and decrypts the bundle back to the exact original title).

## Result

**Security Audit: PASS.** A standard, reviewed hybrid-encryption construction (not novel cryptography);
sender identity is transport-authenticated, never envelope- or body-supplied; every new input is bounded on
both the local and server sides; the recipient is always freshly re-resolved server-side, never a client-
cached key; the share's content reuses the already-audited B2 bundle payload unmodified; no new dependency; no
migration risk. **No record can be received/imported in this stage** — SP4c (list/decrypt/import + cross-user
provenance) is the next audit-triggering slice, not covered here.
