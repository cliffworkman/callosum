# Sync-server design (accounts SP3b — the reference server: the slice where ciphertext leaves the machine)

**Status:** design (approved decisions captured 2026-06-29; spec for review before the build).
**Builds on:** the SP3a crypto (`sync/crypto.py`) + the SP3b client engine (`sync/engine.py`, `sync/changeset.py`,
incs 197–201) + accounts SP1 (Authentik OIDC, `api/auth/`). Parent arc: `2026-06-29-accounts-sync-design.md`.

## What this is

The first slice where data **leaves the machine** — so it is **opt-in, default-off**, gated like the BYOK egress
toggle, and it leaves only **opaque AES-GCM blobs** (the client encrypts before push / decrypts after pull). The
server **never sees plaintext or the DEK** — that is the end-to-end guarantee; it is a dumb, per-user blob store with
a monotonic sequence, serving exactly the `pull(since)/push` Protocol the inc-198 engine already calls.

## Approved decisions (from the maintainer, 2026-06-29)

1. **Stack:** FastAPI + **Postgres**, self-hosted (production). To keep it pytest-testable in-process, the server uses
   **SQLAlchemy Core** (dialect-portable, like the main app) — tests run against **SQLite** by default; an **opt-in CI
   Postgres service** validates the production dialect. The schema uses no Postgres-only features (one table + a
   per-user counter), so portability is real.
2. **Code home:** in the callosum repo under **`sync-server/`** — a *separate deployable* with its **own**
   `requirements.txt` (FastAPI, SQLAlchemy, psycopg, PyJWT[crypto]). **The local app gains no new dependency** — it
   only adds a client `HttpSyncTransport` over **httpx (already present)**. `sync-server/` is fenced from `app/` (it
   is not imported by the local app; the 600-line rule applies to its source too).
3. **Scope (this increment):** the **server + the client `HttpSyncTransport` + the opt-in consent gate**, together —
   all pytest-tested in-process (server via `TestClient`, transport against it). The **live deploy + live-Authentik
   token validation** is the maintainer's manual step (mirrors SP1's "the live ORCID round-trip is manual"). The rich
   Settings → Sync **UI + conflict-review screen is SP3c** (deferred); this slice ships a **minimal enable/setup/run**
   surface so opt-in sync is actually usable + testable.

## Architecture — callosum is one OIDC client; the sync-server is an OIDC resource server

accounts SP1 made callosum an OIDC **client** of the account platform (Authentik). The sync-server is a **second
component of that platform** — an OIDC **resource server**: each request carries the Authentik **access token**
(`Authorization: Bearer …`); the server validates it (issuer + audience + signature via Authentik's **JWKS**, lazy
PyJWT[crypto]), extracts the **`sub`** claim, and **scopes every row to that user**. No callosum library text or DEK
ever reaches it.

**Testability:** the token check is an injectable **`TokenVerifier` Protocol** (a fake returning a fixed `sub` in
tests; the real one does JWKS validation) — mirrors SP1's injectable OIDC client, so the server is fully testable
without a live Authentik.

## The wire contract (matches the inc-198 `SyncTransport` exactly)

- `GET /sync/records?since=<int>` → `{ "records": [ {collection, record_id, version, deleted, ciphertext|null} … ],
  "seq": <int> }` — the caller's records with server-seq **> since**, plus the caller's current high seq (the next
  cursor). `ciphertext` is null iff `deleted`.
- `POST /sync/records` body `{ "records": [ {collection, record_id, version, deleted, ciphertext|null} … ] }` →
  `{ "seq": <int> }` — upsert each by `(user, collection, record_id)` with **LWW by version** (store only if
  `version` > the stored version, exactly as the fake transport models), assigning each stored record the **next
  per-user seq**; returns the new high seq.
- Both require a valid bearer token (401 otherwise); bodies are size-/count-capped (rule #4); `ciphertext` is treated
  as an opaque base64 string (length-capped), never parsed.

## Storage — one table, per user (`sync_records`)

| col | notes |
|---|---|
| `user_id TEXT` | the OIDC `sub` — scopes every row |
| `collection TEXT`, `record_id TEXT` | the engine's keys (sync_uid, or a link's endpoint-pair) |
| `version INT`, `deleted INT` | LWW + tombstone |
| `ciphertext TEXT` | opaque AES-GCM blob (base64); NULL for a tombstone |
| `seq BIGINT` | per-user monotonic, assigned on each write (the cursor) |

PK `(user_id, collection, record_id)`; index `(user_id, seq)` for the `since` scan. The per-user seq is assigned
inside the push transaction from a per-user counter row (`SELECT … FOR UPDATE` on Postgres; SQLite serializes writes)
— avoids the `MAX(seq)+1` race under concurrent pushes from one user. (Its own tiny `sync_cursor(user_id, seq)` table,
or a `MAX+1` guarded by the row lock.)

## Client side (in the local app — the opt-in vertical)

- **`HttpSyncTransport(base_url, token)`** (`app/backend/sync/transport.py`) — implements the `SyncTransport`
  Protocol: `pull`/`push` over httpx to the server, bearer = the Authentik access token from the SP1 session;
  validates response shape, sets timeouts, **fails closed** (a non-200 / malformed response raises, never silently
  drops). The local app's only addition; **no new dependency** (httpx is present).
- **`app_settings`** gains: `sync_enabled` (opt-in, **default off**), `sync_server_url`, the per-device **`sync_cursor`**
  (now a real caller → the inc-198 deferral is resolved), and the sealed **`SyncKeyring`** (SP3a — created on setup).
- **A minimal `routers/sync.py`** (local app):
  - `GET /sync/status` → `{enabled, configured (keyring set), server_url, signed_in, last_cursor, last_synced_at}`.
  - `PUT /sync/settings {enabled, server_url}` — the opt-in toggle + server URL (enabling requires *configured* +
    *signed-in* → else 422, lockout-safe like the inc-168 remote-access toggle).
  - `POST /sync/setup {passphrase}` → `create_keyring` (SP3a) → store the **sealed** keyring in app_settings → return
    the **recovery code ONCE** (write-only, like BYOK keys).
  - `POST /sync/run {passphrase}` → unlock the keyring → **DEK** → `run_sync(conn, dek, HttpSyncTransport(server_url,
    token), since=sync_cursor)` → persist the new cursor + `last_synced_at` → `{pushed, applied, conflicts}`. The DEK
    lives only for the call (not persisted in memory) — the passphrase is supplied per run (SP3c can add a
    remember-for-session option).

## The egress / consent gate (the invariant-touching part)

- **Default off.** No sync runs unless `sync_enabled` AND a server URL is set AND the user is **signed in** (an
  Authentik session, SP1) AND the keyring is configured. Each precondition fails closed (422/409), never silently.
- **Opaque-only egress.** What leaves is AES-GCM ciphertext the server can't read — the library-text egress invariant
  (#3, the Gemini gate) is **untouched**; this is a *separate*, explicitly-consented channel. The A-A pass from SP3a
  carries over: **A5 sovereignty** (the user owns the toggle + holds the only keys; E2E), **A4** (conflicts already
  surfaced by the engine). A fresh **security audit** covers the new endpoints + the egress path.

## Verification

- **Server:** pytest in-process (`TestClient`) — push/pull round-trip, LWW-by-version, per-user scoping (user A can't
  see user B's rows), the `since` cursor delta, 401 on a bad/absent token (injected `TokenVerifier`), body caps.
- **Client:** `HttpSyncTransport` against the in-process server → a **full two-device convergence** test driven through
  the real HTTP transport (not the fake) — the inc-198/199/200/201 scenarios end-to-end over the wire.
- **Opt-in:** `/sync/{status,settings,setup,run}` — setup→enable→run round-trip; enabling without configured/signed-in
  → 422; run while disabled → 409; the recovery code returned once + never in `GET /sync/status`.
- **Live (maintainer, manual):** deploy `sync-server/` (Postgres + the Authentik audience/JWKS env), point a real
  callosum at it, sign in, enable sync, run → two real devices converge. (The flow + contracts are pytest-proven; only
  the live deploy + live-token validation is manual — the SP1 pattern.)
- **Gates:** ruff; QA routes for the new local `/sync/*` endpoints (rule #10) — the server's endpoints live in
  `sync-server/` (outside the app surface map, like the adapters); security audit (new endpoints + egress); CLAUDE
  layout/decision-log/footer + increment notes + changes.

## Out of scope (follow-ons)

SP3c: the rich Settings → Sync UI + the **conflict-review screen** (read `sync_conflicts`, pick a side). PDF-file
sync, real-time push, CRDTs. Multi-user *sharing* (SP4). Server ops hardening (rate-limiting per user, retention,
backup runbook) — sketched in the server README, deepened pre-public.

## Open sub-decisions (my call unless you'd rather weigh in)

1. **Per-user seq mechanism:** a `sync_cursor(user_id, seq)` counter row with `FOR UPDATE` (clean, race-safe) vs
   `MAX(seq)+1` guarded by a row lock. → I'll use the counter row.
2. **Where `/sync/run` orchestration lives:** a local `routers/sync.py` (above) vs a `tools/` CLI. → I'll do the
   router (it's the SP3c UI's backend anyway) + keep handlers thin.
3. **Passphrase handling for a run:** supplied per-run (no persisted in-memory DEK) for this slice; a
   remember-for-session option is SP3c. → per-run.
