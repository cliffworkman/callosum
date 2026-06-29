# Security audit — callosum accounts SP1: "Sign in with ORCID" (OIDC client, identity-only)

**Date:** 2026-06-29
**Status:** COMPLETE.
**Feature:** An opt-in OIDC sign-in (authorization-code + PKCE) to the callosum account platform (Authentik, which
brokers ORCID). On success, the verified ORCID iD + name populate the My-Pubs profile. **Identity-only — no library
data leaves the machine.** Design spec `…/specs/2026-06-29-accounts-optional-identity-design.md`; plan
`~/.claude/plans/would-you-mind-reading-wise-peacock.md`; platform eval `…/research/2026-06-29-oidc-platform-eval.md`.
**Audit triggers:** new API endpoints; new auth/authorization logic; secret/PII handling; a new external fetch
(issuer discovery/token/JWKS); a new dependency (`PyJWT[crypto]`).

**Code:** `app/backend/api/auth/oidc.py` (OIDC client), `app/backend/api/auth/router.py` (`/auth/login`,
`/oauth/callback`, `/auth/logout`), `app/backend/app_settings.py` (config + flow/session storage),
`app/backend/api/access_control.py` (callback exemption), `routers/settings.py` (`account` status block),
`app/backend/api/app.py` (wiring + injectable). Default-OFF: no issuer/client_id env → no client → `/auth/login` 503.

## Threat review
- **PKCE + state — PASS.** `generate_pkce()` makes an S256 challenge (base64url(sha256(verifier)), no padding —
  unit-tested); `generate_state()` is `secrets.token_urlsafe(32)`. The flow (state + verifier + redirect_uri) is
  stored single-use and **popped on the callback before validation** (no replay); the callback rejects an
  absent/mismatched state → redirect to `/?signin=error`, **no token exchange** (test:
  `test_callback_rejects_bad_state_no_exchange`).
- **Loopback redirect_uri (open-redirect) — PASS.** `_resolve_redirect_uri` accepts only an `http` URL whose host is
  `127.0.0.1`/`localhost`/`::1` (a configured `CALLOSUM_OAUTH_REDIRECT` is validated the same way); a non-loopback
  origin or a missing origin → **422** (test: `test_login_rejects_non_loopback_redirect`). The redirect_uri is the
  only request-derived value reaching the provider.
- **id-token verification — PASS (live path).** `_verify_id_token` uses `PyJWT[crypto]` with the issuer's JWKS
  (`PyJWKClient(jwks_uri)`), `algorithms=["RS256","ES256"]`, and **requires + checks** `iss`/`aud`/`exp`
  (`audience=client_id`, `issuer=discovery.issuer`). Any verification failure raises `OidcError` → the callback
  redirects to error; an unverified claim is never trusted. (Verification runs only on the live path; lazy-imported,
  so the app + hermetic suite don't require the dep installed.)
- **Token/PII handling — PASS.** Tokens (access/refresh/id) + the identity are stored via the inc-152
  `_set_secret` (OS keychain when available, else the gitignored `~/.callosum/` file), write-only. `GET /settings`
  returns only `account` = {configured, signed_in, display_name, orcid, expires_at} — **never a token**
  (test: the happy-path asserts the token values are absent from the response body). Nothing is logged.
- **SSRF — PASS.** The issuer/discovery/token/JWKS URLs derive from `CALLOSUM_OIDC_ISSUER` (server config), never
  from request data; discovery is a fixed `<issuer>/.well-known/openid-configuration`. The only request-derived URL
  value is the loopback-validated redirect_uri.
- **Callback exemption — PASS.** `/oauth/callback` is added to `_EXEMPT_PATHS` because it is a browser navigation
  back from the IdP (no Authorization header — the inc-172 gotcha). It carries only an opaque `code`+`state`
  validated against the stored PKCE verifier; it exposes no library data. Verified reachable (303, not 401) under
  Remote access ON while `/settings` still 401s without the bearer (test: `test_callback_exempt_under_remote_access`).
- **Egress posture (invariant #3 / A-A) — PASS.** Sign-in is opt-in + default-off (no issuer configured → no
  sign-in; `account.configured` False). The handshake to the account platform sends **no library text** (identity
  only); the Gemini/library egress gate is untouched. This is an emergent value adopted deliberately (A-A consent):
  an explicit, user-initiated, identity-only egress. Cross-device **sync** (the library-egress step) is **not** built.
- **Supply chain — PASS.** `PyJWT[crypto]>=2.8,<3` pinned in `requirements.txt`, chosen over hand-rolling JWT/JWKS
  verification (the high-risk path). Lazy-imported so its absence can't break the app, only the live sign-in.
- **Resource caps / negative paths — PASS.** Malformed callbacks (missing code/state, bad state) → graceful error
  redirect, never 500; the OIDC client wraps all network/verify failures in `OidcError` → the router catches them.

## Negative-path checks (all verified by `tests/test_auth_oidc.py`, 12 tests)
- no/expired/mismatched state → 303 `/?signin=error`, no exchange, stays signed-out. ✔
- tokens absent from `GET /settings` (searched the response body for both fake token values). ✔
- non-loopback origin → 422; missing origin + no override → 422. ✔
- not configured (no env / no client) → `account.configured:false`, `/auth/login` → 503. ✔
- `/oauth/callback` reachable with remote access ON (exempt); `/settings` still 401 without the bearer. ✔
- logout clears the session (signed_in → false). ✔
- (live ORCID round-trip = the maintainer's MANUAL check — needs a stood-up platform + an ORCID account.)

## Result
**Security Audit: PASS.** Default-off, identity-only, opt-in; PKCE + state + loopback-validated redirect + JWKS
id-token verification; tokens write-only and never returned; SSRF-safe (config-derived endpoints); the callback
exemption carries no library data. No library text leaves the machine on sign-in. The inc-168 remote-access gate is
reused, not re-rolled. Future cross-device sync (SP3) — the only step that would move library data off-machine — gets
its own design + a heavier Principles/A-A pass before it is built.
