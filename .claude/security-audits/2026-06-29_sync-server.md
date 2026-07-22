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

---

## Addendum — backlog #15 (per-user rate limiting + tombstone retention + backup runbook)

**Why:** the original audit's own "Pre-public deploy — RECORDED" line (above) named four follow-ons before any
public/multi-tenant deploy: per-user rate-limiting, blob retention/quota, a backup runbook, and a real migration
tool. Cliff asked for the first three now (a per-user storage *quota* and the general migration tool remain
explicitly out of scope for this pass — see `sync_server/README.md`'s "Not yet" section).

**What changed:**
- **Rate limiting** (`sync_server/rate_limit.py`, new): a standalone reimplementation of the main app's
  `access_control.RateLimiter` sliding-window shape (not imported — `sync_server` stays fenced from `app/`, per
  this audit's own line 40-43). Keyed by the caller's OIDC `sub` (the only identity this server has), applied to
  both `/sync/records` routes via a `_rate_limited` dependency that composes on top of the existing `_identity`
  check. Over the limit → `429` + a `Retry-After` header. Defaults (60 req/60s) are env-tunable
  (`CALLOSUM_SYNC_RATE_LIMIT_MAX`/`_WINDOW_SECONDS`), generous enough not to trip on normal periodic-poll sync
  traffic (`test_generous_default_limit_does_not_throttle_normal_use`).
- **Retention** (`sync_server/store.py::prune_tombstones`, new; `sync_server/schema.py`: new `updated_at` column):
  tombstones (`deleted=1` rows) older than `CALLOSUM_SYNC_RETENTION_DAYS` (default 90) are eligible for removal.
  Deliberately a **plain CLI script** (`python -m sync_server.prune_tombstones`, meant for the maintainer's own
  cron/systemd timer) rather than an in-process background scheduler — keeps the request-serving process simple
  and the retention job independently runnable/retryable. The correctness trade-off (a device offline longer
  than the retention window could resurrect an already-pruned tombstone on its next push, since there's no
  per-device read-cursor to confirm every device has seen it) is stated explicitly in the docstring, the README,
  and `OPERATIONS.md` — not hidden. **Live (non-tombstone) records and rows with no recorded age (a pre-migration
  NULL `updated_at`) are never pruned** — the query's `WHERE deleted=1 AND updated_at < cutoff` fails toward
  preservation on both counts (`test_prune_tombstones_never_touches_live_records`,
  `test_prune_tombstones_skips_rows_with_no_recorded_age`).
- **Schema change on an already-deployed table:** `metadata.create_all()` (the existing v1 approach) never alters
  an existing table, so an already-deployed `sync_records` table would silently lack `updated_at` forever.
  `schema.ensure_updated_at_column` is a single, targeted, idempotent `ALTER TABLE ... ADD COLUMN` that runs on
  every startup (a no-op once the column exists, checked via `Inspector` first) — explicitly **not** a general
  migration tool (that stays a separate, un-scoped follow-on), just a defensive self-heal for this one addition.
- **Backup runbook:** new `sync_server/OPERATIONS.md` — `pg_dump`/`pg_restore` procedure, and (the honesty point
  worth restating here) what a sync-server backup actually protects: opaque ciphertext + sync-state routing
  metadata only, never a user's plaintext library (the server never holds a DEK; each device's own local DB
  remains the true source of truth for that user's papers).

**Threat review of the new surface:**
- **Rate limiter correctness/DoS:** bounded memory (one `deque` per distinct `sub` seen; a malicious caller can't
  grow this meaningfully faster than legitimate distinct users would, and this server already requires a valid
  signed JWT before the limiter is ever consulted — an attacker without a valid token gets 401, not a limiter
  entry). No new dependency; pure stdlib (`collections.deque`, `threading.Lock`), matching the main app's own
  already-audited pattern.
- **Retention correctness:** covered above — fails toward preservation in every ambiguous case (unknown age,
  live record). The one accepted risk (long-offline-device resurrection) is a data-consistency trade-off, not a
  confidentiality/integrity/availability vulnerability — the resurrected record is still the same user's own
  data, still legitimately encrypted by that same user's own device.
- **The `ensure_updated_at_column` ALTER:** runs with the same DB credentials the server already has full
  read/write access with (no privilege escalation); the SQL is a fixed, hardcoded string with no interpolated
  input (rule #3 — no injection surface); it only ever adds a column, never drops/alters existing data.
- **No new egress, no new dependency, no new auth path** — everything above operates entirely within the
  already-audited OIDC/tenant-isolation boundary from the original audit.

**Negative-path checks (concrete results):**
- User A's requests never count against user B's rate-limit bucket → **PASS** (`test_rate_limit_is_per_user_not_global`).
- Exceeding the limit on both `GET /sync/records` and `POST /sync/records` → `429` + a `Retry-After` header, not
  a 500 or a silent drop → **PASS** (`test_rate_limit_is_per_user_not_global`, `test_rate_limit_applies_to_push_too`).
- A live (non-tombstone) record is never pruned regardless of age → **PASS**.
- A tombstone with no recorded age (NULL `updated_at`) is never pruned → **PASS**.
- Only tombstones strictly older than the configured window are removed; recent tombstones survive → **PASS**
  (`test_prune_tombstones_removes_only_old_ones`).
- `ensure_updated_at_column` against a table built without the column adds it exactly once; calling it again is
  a safe no-op → **PASS** (`test_ensure_updated_at_column_is_idempotent`).
- The CLI script's `--dry-run` reports without deleting; a real run removes exactly the eligible rows; a second
  real run finds nothing left → **PASS** (`test_prune_cli_dry_run_and_real_run`).
- Full `sync_server`-scoped suite: **17 passed** (`tests/test_sync_server.py`).

**Addendum result: PASS.** Closes three of the four pre-public-deploy follow-ons this audit originally recorded
(rate-limiting, retention, backup runbook); a per-user storage quota and a general migration tool remain
explicitly open (see `sync_server/README.md`'s "Not yet" section) — neither was in this pass's scope.
