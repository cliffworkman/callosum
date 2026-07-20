# Security audit — accounts SP3b: the reference sync-server + client transport + opt-in (the egress slice)

**Date:** 2026-06-29
**Feature:** the first path where data **leaves the machine** — a self-hosted **sync-server** (`sync_server/`,
FastAPI + SQLAlchemy Core, deployed on Postgres / tested on SQLite) storing **opaque AES-GCM blobs** per user, an
OIDC **resource server** (validates Authentik access tokens, scopes by `sub`); a client **`HttpSyncTransport`** (httpx,
implements the inc-198 Protocol); and the **opt-in** local `/sync/*` endpoints (setup/settings/status/run) that drive
`run_sync` over the HTTP transport. Design spec `…/specs/2026-06-29-sync-server-design.md`.
**Audit triggers:** new external network egress (the first library-data-leaving path); new API endpoints (local +
server); new auth (the server validates OIDC tokens); a new dependency (server-only: psycopg, PyJWT already present).

## Threat review
- **Egress / consent — PASS.** Opt-in, **default-off** (`GET /sync/status` on a clean instance →
  `enabled:false, configured:false, signed_in:false`). `POST /sync/run` runs only when **enabled AND configured AND
  signed-in AND a server URL is set** — each precondition → 409 otherwise (tested). What leaves is **opaque AES-GCM
  ciphertext** (the engine encrypts before push; the server stores it as text it never decodes) and the **DEK never
  leaves** (it's unlocked locally from the passphrase, used for the call, discarded). The Gemini library-text gate
  (#3) is a *separate* channel, untouched. A5 sovereignty (user owns the toggle + holds the only keys); A4 (the
  engine surfaces conflicts). Test `test_run_with_wrong_passphrase_does_not_egress` confirms a failed unlock reaches
  the server with **0 records**.
- **Server auth / tenant isolation — PASS.** Every `/sync/*` server request requires a valid bearer token
  (`_identity` → `TokenVerifier.verify`; `JwksVerifier` checks issuer + audience + RS256 signature via Authentik's
  JWKS, fail-closed; an unconfigured server → 503, default-closed). All rows are scoped to the token's `sub`.
  `test_tenant_isolation` proves user A's records are invisible to user B and a same-`record_id` push by B doesn't
  touch A's row. `test_auth_required`: no/invalid token → 401; `/health` is the only unauthenticated route.
- **Server input validation — PASS.** Pydantic caps: `collection`≤60, `record_id`≤200, `ciphertext`≤2 MB,
  ≤1000 records/push (`test_push_record_cap` → 422). `ciphertext` is an **opaque** string — never parsed/decoded
  server-side. Bound-param SQLAlchemy Core throughout (rule #3); LWW-by-version (an older version is ignored —
  `test_last_write_wins_by_version`), so a replay can't downgrade a record.
- **Client transport — PASS.** `HttpSyncTransport` sets an httpx timeout, validates response shape, and **fails
  closed** — a non-200 or malformed response raises `SyncServerError`, never silently dropping a record
  (`test_transport_fails_closed_on_error`). The bearer is the SP1 access token (read server-side from the stored
  session; never logged; never returned to the browser).
- **Opt-in endpoints — PASS.** `/sync/setup` returns the recovery code **once** and `GET /sync/status` never carries
  it (`test_setup_returns_recovery_once_then_409`); a second setup → 409 (no silent re-key). Enabling is lockout-safe
  (422 unless configured + signed-in + URL — `test_enable_requires_setup_signin_and_url`). The sealed keyring is
  stored via `_set_secret` (keychain/file; SP3a: no plaintext/passphrase/DEK — safe at rest). `/sync/run` unlocks the
  DEK from the per-run passphrase (401 on wrong; not persisted) and commits the local txn only on success (a
  sync-server error rolls back → no half-apply).
- **Supply chain — PASS.** Server-only deps (`fastapi`, `sqlalchemy`, **psycopg**, `PyJWT[crypto]`) live in
  `sync_server/requirements.txt`; **the local app gains no new dependency** (only httpx, already present). `sync_server/`
  is fenced from `app/` — the local app never imports it; the server's test path lazy-imports neither psycopg
  (SQLite) nor jwt (fake verifier), so CI needs no extra deps.
- **Pre-public deploy — RECORDED.** Per-user rate-limiting, blob retention/quota, a backup runbook, and a real
  migration (vs create-on-start) — sketched in `sync_server/README.md`; deepened before any public multi-tenant
  deploy. This slice targets the maintainer's self-host.

## Negative-path checks (concrete results)
- user A's token cannot read or push into user B's records → **PASS** (`test_tenant_isolation`).
- absent/invalid token → 401; too-many-records → 422 (not 500) → **PASS** (`test_auth_required`, `test_push_record_cap`).
- sync disabled / not-signed-in / not-configured → `/sync/run` 409, no egress → **PASS** (`test_run_refused_when_off…`).
- wrong passphrase on `/sync/run` → 401, **0 records reach the server** → **PASS** (`test_run_with_wrong_passphrase_does_not_egress`).
- recovery code returned once, never by `GET /sync/status` → **PASS**.
- unconfigured server (no verifier) → 503 (default-closed) → **PASS** (`test_unconfigured_server_refuses`).

## Result
**Security Audit: PASS.** Opt-in/default-off egress of opaque E2E ciphertext only; per-user tenant isolation behind
Authentik token validation; bounded inputs; fail-closed transport + unlock; the local app gains no dependency and the
server is fenced from it. The **live deploy + live-Authentik token validation** is the maintainer's manual step (the
pure flow + contracts are pytest-proven); per-user rate-limiting + retention are recorded for the pre-public pass.

---

## Addendum — inc 310/311 (Sync UI, SP3c): `/sync/run` wrong-passphrase status changed 401 → 422

**Why:** building the first real frontend caller of `/sync/run` (the Settings → Sync UI) surfaced that this audit's
own "wrong passphrase → 401" behavior (lines 38/52/original) collides with an app-wide convention: every `api*`
fetch helper in the frontend (`00_lib.jsx`) treats **any** 401 response, from **any** endpoint, as "the
remote-access bearer token is invalid" and fires the inc-254 `AccessLockOverlay` global lockout-recovery flow. A
user who mistypes their **local sync passphrase** would have been shown that unrelated, confusing full-screen
recovery overlay instead of a simple "wrong passphrase" message. Fixed by changing the status to **422**
(`app/backend/api/routers/sync.py::sync_run`) — matching `sync_setup`'s own `SyncCryptoError` handling, which
already used 422 for the equivalent failure at setup time. The **security-relevant invariant this audit
tests — a wrong passphrase causes zero records to reach the sync server — is unchanged**; only the HTTP status
code changed. `test_run_refused_when_off_or_wrong_passphrase` and `test_run_with_wrong_passphrase_does_not_egress`
updated to assert 422. `.claude/qa-routes/route_46_sync.md` updated to match.

**Addendum result: PASS — no security-relevant behavior changed, only a status-code/frontend-integration fix.**
