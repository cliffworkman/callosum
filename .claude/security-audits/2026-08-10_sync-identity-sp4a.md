# Security audit — Sync SP4a: sharing identity (round 3, item #4, stage A of 4)

**Date:** 2026-08-10
**Status:** COMPLETE.
**Feature:** the identity layer for backlog #15's SP4 sharing — a per-account X25519 keypair (private key sealed
under the existing sync DEK, `app/backend/sync/identity.py`), a server-side public-key directory
(`sync_server/`, reachable only by exact `sub`), local endpoints (`GET /sync/identity/status`,
`POST /sync/identity/setup`, `GET /sync/identity/lookup`), and a human fingerprint-verification UI
(`35c_sync.jsx`'s `SharingIdentityPanel`). **No record is shared in this stage** — SP4a only makes "who is this
collaborator, cryptographically" answerable. Design: `.claude/backups/plans/2026-08-10_sync-sp4a-identity.md`.
**Audit triggers:** new API endpoints (3 local + 2 server); new auth-adjacent identity surface; ~500 LOC across
8 files.

## Threat review

- **Private-key-at-rest — PASS.** The X25519 private key is sealed under the **existing sync DEK** via
  `crypto.py`'s unmodified `encrypt_payload`/`decrypt_payload` (AES-256-GCM, fresh nonce per seal) — the same
  guarantee the DEK itself already gives every other syncable record. Stored locally via `app_settings._set_secret`
  (OS keychain where available, else the local file — never in the repo or the synced Dropbox folder). No
  endpoint response (`/sync/identity/status`, `/sync/identity/setup`) ever includes the private key, wrapped or
  otherwise — both return only `{fingerprint, own_sub}` (+ `has_identity` on status), asserted directly by
  `test_identity_setup_happy_path_registers_and_returns_fingerprint`'s `set(body) == {"fingerprint", "own_sub"}`.
  A wrong DEK or tampered wrapped-key blob fails closed with `SyncCryptoError` (`test_unlock_private_key_wrong_dek_fails_closed`,
  `test_unlock_private_key_tampered_blob_fails_closed`).
- **Server-side exposure surface (exact-id-only, no enumeration) — PASS.** `sync_server/identity_store.py`'s
  `lookup_public_key` takes an exact `user_id` and has no listing/search counterpart — structurally, not just by
  convention (there is no query path that iterates `share_identities`). `test_lookup_never_lists_or_fuzzy_matches`
  proves a case/whitespace/substring near-miss all 404, and that no `/identity` or `/identity/list` endpoint
  exists. This is backlog #15's own divergence fence from `.claude/APPROACH-AVOIDANCE.md`'s gate framing: a
  public-key lookup is not a user directory, and never becomes one.
- **`display_name` is UX-only, never a security claim — PASS.** The server stores exactly what the caller sends
  at registration time (`schema.py`'s own comment: "the server never verifies it"); nothing in the identity flow
  reads or compares `display_name` for any authorization or trust decision — only `public_key` (via the
  fingerprint) is ever compared by a human. Documented inline in `schema.py`, `identity_store.py`, and the
  frontend copy ("confirm the fingerprint... before sharing anything" — never "confirm the name").
- **Egress/consent — its own explicit gate, distinct from the sync-enabled toggle — PASS.** `_require_egress_ready`
  (shared by `/sync/identity/setup` and `/sync/identity/lookup`) requires the identical four preconditions
  `/sync/run` already requires (enabled + configured + signed-in + server URL) — no weaker than the existing
  egress gate. Registering/looking up identity is additionally its own **explicit action** (a dedicated button +
  passphrase entry in the UI, a dedicated endpoint on the backend) — it never happens as a side effect of an
  ordinary sync run. `test_identity_setup_refused_when_sync_not_ready` / `test_identity_lookup_refused_when_sync_not_ready`
  confirm the 409 fail-closed path; `test_identity_setup_wrong_passphrase_fails_closed_no_egress` confirms a
  failed local unlock reaches the server with **zero** registration calls (mirrors the existing
  `test_run_with_wrong_passphrase_does_not_egress` pattern exactly).
- **Rate limiting reuse — PASS.** The two new server endpoints run through the exact same `_rate_limited`
  dependency (and thus the same per-`sub` `RateLimiter`) every `/sync/records` call already uses — no new,
  unreviewed rate-limiting logic introduced.
- **Server input validation — PASS.** Pydantic caps on both new server models: `public_key` ≤ 100 chars
  (base64 of a raw 32-byte key is ~44 chars — generous but still tightly bounded), `display_name` ≤ 200 chars,
  `sub` (query param) ≤ 255 chars. `test_register_rejects_oversized_public_key` confirms 422. Bound-param
  SQLAlchemy Core throughout (rule #3) — no interpolated identifiers.
- **Malformed server response fails closed, not a raw 500 — PASS.** `sync_identity_lookup` wraps the
  server-returned public key's base64-decode + fingerprint computation in a `try/except (SyncCryptoError,
  ValueError, TypeError)`, converting a malformed value into a clean 502 rather than an unhandled exception.
- **Supply chain — PASS.** `cryptography.hazmat.primitives.asymmetric.x25519` — already available via the
  existing `cryptography` dependency (`PyJWT[crypto]`), confirmed importable against the pinned version
  (43.0.0). No new dependency, matching `crypto.py`'s own established discipline.
- **Migration — PASS.** `share_identities` is a **new** table on `sync_server`'s existing `metadata` — created
  for free by the already-existing `metadata.create_all(engine)` lifespan call; no idempotent-ALTER dance
  needed (unlike `sync_records.updated_at`'s prior retrofit, which only applies to columns added to an
  already-deployed table).

## Negative-path checks (concrete results)

- wrong DEK / tampered wrapped-private-key blob → `SyncCryptoError` (fails closed) — **PASS**
  (`test_unlock_private_key_wrong_dek_fails_closed`, `test_unlock_private_key_tampered_blob_fails_closed`,
  `tests/test_sync_identity.py`).
- identity setup/lookup refused (409) when sync isn't enabled+configured+signed-in+URL'd — **PASS**
  (`test_identity_setup_refused_when_sync_not_ready`, `test_identity_lookup_refused_when_sync_not_ready`).
- wrong passphrase on setup → 422, zero server-side registration — **PASS**
  (`test_identity_setup_wrong_passphrase_fails_closed_no_egress`).
- a second setup call → 409 (no silent re-key) — **PASS** (`test_identity_setup_twice_is_409_no_silent_rekey`).
- lookup of an unregistered / near-miss / case-varied / substring `sub` → 404, never a match — **PASS**
  (`test_lookup_unknown_sub_is_404`, `test_lookup_never_lists_or_fuzzy_matches`).
- no `/identity` or `/identity/list` endpoint exists on the server — **PASS** (`test_lookup_never_lists_or_fuzzy_matches`).
- identity endpoints require a valid bearer token — **PASS** (`test_identity_endpoints_require_auth`).
- oversized `public_key` rejected — **PASS** (`test_register_rejects_oversized_public_key`).
- re-registering rotates the current key (an intentional, disclosed non-goal: no key history in SP4a) — **PASS**
  (`test_re_register_rotates_the_current_key`).
- live browser check (isolated scratch instance, `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`): setup
  against a real-but-unreachable server URL fails cleanly with an inline error, no console exception beyond the
  expected non-2xx fetch log line, and "Look up a collaborator" correctly stays hidden until `has_identity` is
  true — confirmed via Playwright, not assumed from a static read.

## Result

**Security Audit: PASS.** The private key is exactly as protected as the sync DEK itself; the public-key
directory is structurally exact-id-only (no listing/search surface exists to audit around); egress is gated
identically to an ordinary sync run plus its own explicit consent action; every new input is bounded; no new
dependency. **No record is shared in this stage** — SP4b (wrapping a per-share content key under a looked-up
public key) is the next audit-triggering slice, not covered here.
