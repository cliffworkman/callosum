# Increment 312 — the account platform goes live: Authentik + sync_server on juno, plus three real bugs the live round-trip surfaced

## Context
Backlog #15's last open piece was infra, not code: an actual running Authentik instance for "Sign in with ORCID"
and a running `sync_server` for cross-device sync. The maintainer offered a spare Debian box on the LAN — **juno**
(`brain@10.0.0.123`) — instead of paying for hosting. This increment stands both services up there, exposed the
same way this project already exposes local callosum for the Google Docs add-on and mobile reading: an
**outbound-only Cloudflare Tunnel**, no inbound port, no hosting bill. Getting the *live* round-trip working (not
just the code) surfaced three genuine, previously-invisible bugs — each fixed in this increment rather than filed,
since they directly block the account/sync features from ever working for real.

## Implemented

**Infrastructure (juno, no callosum code):**
- Docker Compose v2 CLI plugin (static binary, no new apt repo) + a cloned `sync_server/` checkout under
  `~/callosum-accounts/`.
- **Authentik** (`ghcr.io/goauthentik/server:2026.5.5`, official docker-compose quickstart) — server/worker/postgres,
  web ports bound to **127.0.0.1 only** (never exposed except through the tunnel).
- **cloudflared**, a new named tunnel `callosum-accounts` with two ingress rules on the already-Cloudflare-managed
  `clffwrkmn.net` zone: `auth.clffwrkmn.net` → `:9000` (Authentik), `sync.clffwrkmn.net` → `:8770` (sync_server) —
  installed as a systemd service, survives reboots.
- **sync_server**, run as a bare systemd unit (not Docker) against a **second Postgres database**
  (`callosum_sync`, its own role) inside Authentik's *same* Postgres container — Postgres's own port also bound to
  127.0.0.1 only, reachable from the host-level sync_server process via loopback.
- The maintainer registered an ORCID API client, added ORCID as an Authentik federation source + the `orcid` scope
  mapping, and created the callosum Public/PKCE OAuth2 application — all per the existing
  `ops/accounts-authentik-setup.md` runbook (still accurate, no changes needed).
- `.env` (gitignored) now carries `CALLOSUM_OIDC_ISSUER` / `CALLOSUM_OIDC_CLIENT_ID` / `CALLOSUM_OIDC_SCOPES` /
  `CALLOSUM_OIDC_CLAIM_ORCID` for the real deployment.

**Three real bugs found via the live round-trip, fixed in code:**

1. **PyJWT's zero-leeway timestamp checks are too strict for any self-hosted, cross-machine deployment.**
   `app/backend/api/auth/oidc.py`'s `_verify_id_token` and `sync_server/auth.py`'s `JwksVerifier.verify` both called
   `jwt.decode(...)` with no `leeway`, so completely normal clock drift between callosum's machine and the
   account-platform host (a few seconds to a couple of minutes) produced `Signature has expired` / `token is not
   yet valid (iat)`. Both now pass `leeway=60`. (Separately, juno's own clock had drifted ~18 minutes because
   `systemd-timesyncd` had never actually synced — fixed operationally by restarting it — but the zero-leeway gap
   was a real code bug independent of that specific drift.)
2. **`sync_server/auth.py`'s `JwksVerifier` stripped the issuer's trailing slash for building the JWKS URL, then
   reused that *stripped* value as the exact-match `issuer=` check against the JWT's real `iss` claim** — which
   Authentik always emits *with* a trailing slash. This silently failed the issuer check on every single token,
   independent of the leeway issue. Fixed by keeping the original issuer string verbatim for the `jwt.decode`
   check, and only stripping the slash when building the default JWKS URL.
3. **`app/backend/api/routers/sync.py`'s `/sync/run` reused the access token from the *original* sign-in
   indefinitely, never refreshing it via the stored `refresh_token`.** Authentik's access tokens are short-lived by
   design; any sync run happening more than a few minutes after sign-in failed with `Signature has expired`. Added
   `OidcClient.refresh_access_token` (mirrors `exchange_code`'s shape exactly — same `token_endpoint` POST, same
   `OidcError` wrapping, public/PKCE client, no secret) and a new `_fresh_access_token(request)` in `sync.py` that
   refreshes when the stored `expires_at` is within 30s of now (or past), persists the refreshed session, and falls
   back to the existing (already-correct) 401→502 fail-closed path on any refresh problem. `expires_in` from the
   refresh response becomes a *more* accurate expiry going forward than the original ID-token-`exp` proxy used at
   first sign-in.
   - **The refresh code alone wasn't enough to prove out live**, and the fallback-on-any-failure design (by intent,
     to preserve the existing fail-closed behavior) meant a broken refresh failed *silently* — indistinguishable
     from "never attempted" without instrumentation. Added `logger.info`/`logger.warning` lines to
     `_fresh_access_token` (skip/success/failure, each with the reason) — this is what caught the actual live gap
     in seconds: `has_refresh_token=False`. Root cause: Authentik only *issues* a refresh token when the client
     requests the **`offline_access`** scope — the "Refresh Token" grant-type checkbox being enabled on the
     provider only means it's *allowed*, not requested. Added `offline_access` to the callosum provider's Selected
     Scopes and to `CALLOSUM_OIDC_SCOPES`; `ops/accounts-authentik-setup.md` step 5/6 updated so this isn't a
     re-discovered gap on the next Authentik setup.

**A fourth issue, found but not a bug** — `transport.py`'s `pull`/`push` discarded the response body on a non-200,
so a 422 just read "HTTP 422" with no detail. Now includes `resp.text[:500]` in the raised `SyncServerError` — this
is what surfaced bug/gap #5 below in five seconds instead of more blind guessing.

**A real capacity gap, also found live and fixed:** `engine.py`'s `run_sync` pushed the *entire* changeset in one
`transport.push()` call. The maintainer's first-ever sync had 1,514 changed records (everything counts as "new" on
a first sync) against `sync_server`'s `MAX_RECORDS_PER_PUSH = 1000` cap → a 422. Now chunks pushes into batches of
`_PUSH_BATCH_SIZE = 500` (comfortably under any reasonable server cap), persisting `_set_sync_state` per
successfully-pushed chunk so a mid-run failure doesn't lose track of what's already landed.

**Two Cloudflare zone-config gotchas** (operational, not code): a **WAF Managed Rules** block on the well-known
`Python-urllib` user-agent (used internally by `PyJWKClient`) needed a custom-rule skip for the two new hostnames;
a separate, older **Browser Integrity Check** setting (Security → Settings, not WAF) was blocking the same
signature independently and had to be disabled too. Both are now off for `auth.clffwrkmn.net`/`sync.clffwrkmn.net`.

## Key technical detail
The issuer-string bug (#2 above) is the subtle one: `issuer.rstrip("/")` is the *right* thing to do when building a
derived URL (`{issuer}/jwks/` must not have a double slash), but the *wrong* thing when the same variable is reused
for an exact-string `issuer=` claim check — OIDC issuers conventionally carry a trailing slash in their canonical
form (confirmed via `auth.clffwrkmn.net`'s own `.well-known/openid-configuration`, whose `"issuer"` field is
`https://auth.clffwrkmn.net/application/o/callosum/`), and PyJWT's issuer check is exact-match, not
trailing-slash-tolerant. `oidc.py`'s own `_verify_id_token` never had this bug because it always sourced the
`issuer=` parameter from the discovery document's own `"issuer"` field rather than re-deriving it from a
stripped copy.

## Manual verification (live, against the real juno deployment — this session)
1. `https://auth.clffwrkmn.net` and `https://sync.clffwrkmn.net` both resolve through the tunnel; Postgres/Authentik
   ports confirmed unreachable except via loopback.
2. Settings → Account → Sign in with ORCID → real ORCID login (not the Authentik admin session) → landed back
   signed in; `GET /settings` showed `account.signed_in: true`, no token value anywhere in the body.
3. Settings → Cross-device sync: chose a passphrase (recovery code shown once), enabled, entered
   `https://sync.clffwrkmn.net`, **Run sync now** → `Pushed 1514, applied 0` (first-ever sync, chunked in batches of
   500 without erroring). A second run → `Pushed 0, applied 0` (idempotent, as expected).
4. Confirmed unauthenticated `sync_server` requests still 401 (fail-closed), `/health` reports `configured: true`.
5. **The refresh fix's real test:** signed in, ran a successful sync, waited 6 minutes (past the access token's real
   lifetime), ran again → reproduced `Signature has expired` — the diagnostic logging showed `has_refresh_token=
   False`, i.e. no refresh token had ever been issued. Added `offline_access` to the provider's scopes (Authentik
   only issues a refresh token when it's requested, regardless of the "Refresh Token" grant-type checkbox) +
   `CALLOSUM_OIDC_SCOPES`, signed out/in again, repeated the same wait-6-minutes-then-sync test → succeeded with no
   re-authentication needed.

## Pytest
`tests/test_sync_endpoints.py` + `tests/test_sync_engine.py` + `tests/test_sync_server.py` + `tests/test_auth_oidc.py`
all pass; full suite **1291 passed, 1 skipped** (up from 1289 — the two new token-refresh tests).
`ruff check .` + `ruff format --check .` clean; `python tools/check_line_budget.py` clean (347 files).

## Gates
- **Security:** no new endpoint, no new request/response contract, no new egress destination or secret type (the
  `refresh_token` was already stored and trusted from the original code exchange) — no new audit needed for the
  refresh fix. The juno deployment itself follows the existing `ops/accounts-authentik-setup.md` +
  `sync_server/README.md` runbooks as-is (both proved accurate).
- **Principles (#9):** none of tonight's fixes touch a claim/signal/judgment surface — pure plumbing correctness.

## Next
Backlog #15 is now fully live for the maintainer's own use. Remaining, later items: pre-public server hardening
(per-user rate-limiting, retention, a backup runbook, a real DB migration tool — `sync_server/README.md` already
flags these as deliberately deferred for "a few accounts, a few devices each"), and SP4 sharing (a live shared
library). The maintainer's own juno checkout should move from the manual live-debugging patches applied tonight to
a clean `git pull` once this increment is pushed.
