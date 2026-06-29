# Increment 202 — accounts SP3b: the reference sync-server + client transport + opt-in (the egress slice)

## Implemented

The first path where data **leaves the machine** — built as the maintainer chose: **server + client transport +
opt-in, together**, **FastAPI + Postgres** (SQLAlchemy Core → SQLite in tests / Postgres in prod), in the callosum repo
under **`sync_server/`**. What leaves is **opaque AES-GCM ciphertext** the server can't read (E2E; the DEK never
leaves), so it's **opt-in, default-off**, gated like the BYOK egress toggle. Design spec
`…/specs/2026-06-29-sync-server-design.md`.

- **`sync_server/`** (a separate deployable, its own `requirements.txt`; the local app gains **no** dependency):
  - `schema.py` — `sync_records` (latest opaque blob per `(user, collection, record_id)` + version + per-user `seq`)
    + `sync_cursor` (the per-user high-water counter, locked on push); dialect-portable.
  - `auth.py` — a `TokenVerifier` Protocol (fake in tests) + `JwksVerifier` (Authentik issuer + audience + RS256 via
    JWKS, lazy `PyJWT[crypto]`, fail-closed → `InvalidToken`). The server is an OIDC **resource server**.
  - `store.py` — `push` (LWW by version; assign the next per-user seq from the locked cursor row) + `pull` (records
    with `seq > since` + the high seq); bound params; never decodes a blob.
  - `app.py` — `create_server(engine, verifier)`: `GET /sync/records?since=` + `POST /sync/records` (bearer-auth,
    scoped to `sub`; Pydantic caps — ≤1000 records, ≤2 MB ciphertext) + `GET /health`; module-level `app` from env.
  - `README.md` — the self-host runbook (Postgres + Authentik env).
- **`app/backend/sync/transport.py`** — `HttpSyncTransport` implementing the inc-198 `SyncTransport` over httpx
  (injectable client; bearer = the SP1 access token; timeouts; **fails closed** on non-200/malformed). The local
  app's only addition.
- **`app/backend/api/routers/sync.py`** — the opt-in vertical: `GET /sync/status`, `PUT /sync/settings` (lockout-safe
  enable), `POST /sync/setup` (create keyring → return the recovery code **once**), `POST /sync/run` (unlock the DEK
  from the passphrase → `run_sync` over the HTTP transport → persist the cursor). `app_settings` gained
  `sync_enabled`/`sync_server_url`/`sync_cursor` (the inc-198 cursor deferral resolved) + the sealed keyring (secret
  store). `create_app(sync_transport=…)` injects a transport for tests; `app.py` includes the router.

## Key technical detail

**Postgres in prod, SQLite in tests, one codebase:** the server uses SQLAlchemy Core with no Postgres-only features,
so the same code runs on SQLite (tests, via `StaticPool` for a shared in-memory DB) and Postgres (deploy). The
**per-user monotonic seq** is assigned from a locked `sync_cursor` counter row (`SELECT … FOR UPDATE` on Postgres;
SQLite serializes writes) — avoiding a `MAX(seq)+1` race. **The whole stack is pytest-tested in-process**: the client
`HttpSyncTransport` binds to the in-process server's `TestClient` (real HTTP semantics, no socket), and a two-device
convergence test runs the engine → transport → server → store → back over the wire. The token check is an injectable
`TokenVerifier` (a fake `sub` in tests) — so no live Authentik is needed; the live deploy + live-token validation is
the maintainer's manual step (the SP1 pattern).

**The egress gate (the invariant-touching part):** `/sync/run` refuses (409) unless enabled + configured + signed-in +
a server URL is set; a wrong passphrase → 401 with **zero records reaching the server** (proven by a test). Default-off;
the recovery code is shown once and never by `/status`; the DEK is held only for the call.

## Manual verification script

In-process (no live infra): `HF_HUB_OFFLINE=1 python -m pytest tests/test_sync_server.py tests/test_sync_endpoints.py -q`
→ server contract (round-trip, LWW, tenant isolation, cursor, 401, caps) + the two-device convergence over the real
HTTP transport + the opt-in gate (setup-once, lockout-safe enable, run preconditions, wrong-passphrase-no-egress).

**Live (maintainer, manual):** deploy `sync_server/` (Postgres + the Authentik audience/JWKS env per its README),
point a real callosum at it (Settings → Sync, SP3c), sign in, set up + enable, run → two real devices converge.

## Gates

- **pytest:** full suite green — **709 passed, 1 skipped** (+17: `tests/test_sync_server.py` 9, `tests/test_sync_endpoints.py` 8).
- **ruff** check + format clean (incl. `sync_server/`).
- **QA surface** — **136/136 API** (+4: the `/sync/*` local endpoints; new `route_46_sync.md`) **+ 661/661 FE, 0
  uncovered**. The server's own endpoints (`sync_server/`) are outside the app surface map (like the adapters),
  covered by `test_sync_server.py`.
- **Audit** `.claude/security-audits/2026-06-29_sync-server.md` **PASS**.
- **Principles/A-A:** the SP3 gate ran in SP3a (A5 sovereignty via E2E + opt-in; A4 conflict-surfacing) — this slice
  realizes that egress channel exactly as gated.
- **No migration** (the local app's sync tables already exist; the server creates its own on start). **No new
  dependency in the local app** (server-only deps in `sync_server/requirements.txt`).

## NEXT

The live deploy is the maintainer's (stand up `sync_server/` on Postgres + wire the Authentik audience). Then
**SP3c** — the rich Settings → Sync UI (set up / enable / run, with a passphrase prompt) + the **conflict-review
screen** (read `sync_conflicts`, pick a side). Pre-public server hardening (per-user rate-limiting, retention, a
backup runbook, a migration tool) is recorded in the server README. PDF-file sync, real-time push, CRDTs, and
multi-user *sharing* (SP4) remain deferred.
