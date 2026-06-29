# Increment 194 — accounts SP1: "Sign in with ORCID" (optional, identity-only)

The first slice of the **optional-account** arc (backlog #15), reframed via a brainstorm into **local-first + an
opt-in account** (the Zotero shape). Design spec `…/specs/2026-06-29-accounts-optional-identity-design.md`; plan
`~/.claude/plans/would-you-mind-reading-wise-peacock.md`; platform eval `…/research/2026-06-29-oidc-platform-eval.md`
(→ **Authentik**, the maintainer's pick). The app stays fully local/offline with **no account by default**; signing
in is opt-in + additive and **identity-only — no library data leaves the machine**.

## Implemented

- **`app/backend/api/auth/oidc.py`** — the OIDC client: authorization-code + **PKCE** (`generate_pkce` = S256),
  loopback redirect, discovery (cached), token exchange, and **id-token verification** (JWKS sig + `iss`/`aud`/`exp`)
  via **lazy-imported `PyJWT[crypto]`** (so the app + hermetic suite run without the dep; only the live path needs
  it). `OidcClient` is **injectable** (`create_app(oidc_client=…)`) so tests use a fake; `build_oidc_client_from_env`
  builds the default from `CALLOSUM_OIDC_ISSUER`/`CLIENT_ID` (None → sign-in off).
- **`app/backend/api/auth/router.py`** — `GET /auth/login?origin=` → `{authorize_url}` (a fetch; sets up the
  single-use state+PKCE flow; **503** if unconfigured, **422** on a non-loopback origin), `GET /oauth/callback` →
  validate state → exchange (+verifier) → verify id-token → store session → **`profile_repo.upsert_profile`** (the
  payoff) → redirect `/?signin=ok|error`, `POST /auth/logout` → clear the session.
- **`app/backend/app_settings.py`** — `oidc_config()`/`oidc_configured()` (env), single-use `set_oauth_flow`/
  `pop_oauth_flow`, write-only `set_oauth_session`/`stored_oauth_session`/`clear_oauth_session` (via the inc-152
  `_set_secret`), and `oauth_account_status()` (the non-secret status — never tokens).
- **`app/backend/api/access_control.py`** — `/oauth/callback` added to `_EXEMPT_PATHS` (a browser navigation → no
  bearer header, the inc-172 gotcha; it carries only an opaque code+state).
- **`routers/settings.py`** — an `account` block on `GET /settings` (`configured`, `signed_in`, `display_name`,
  `orcid`, `expires_at`) — verified identity only.
- **`app/frontend/js/35_settings.jsx`** — an **Account** section: Sign in with ORCID (→ `/auth/login` → navigate to
  the IdP), signed-in identity + Sign out, or an honest "not set up yet" note when unconfigured. No new CSS (reuses
  the existing settings recipes).
- **`requirements.txt`** — `PyJWT[crypto]>=2.8,<3` (justified; lazy-imported). `app.py` — wire the router +
  `oidc_client` injectable.

## Key technical detail

callosum is **one OIDC client of the callosum account platform** (Authentik), **not ORCID directly** — the platform
brokers ORCID and passes the **verified ORCID iD as a claim** (`CALLOSUM_OIDC_CLAIM_ORCID`, default `orcid`). So SP2's
email/Google are **platform-config, no app change**. The **loopback redirect**: uvicorn binds the port, so the app
doesn't know it → the redirect URI = the **browser's own loopback origin** + `/oauth/callback`, **validated
loopback-only** (no open-redirect; `CALLOSUM_OAUTH_REDIRECT` override also validated). The PKCE flow is **single-use**
(popped on the callback before validation → no replay); a bad/missing state → error redirect, **no token exchange**.

## Manual verification script

The **live ORCID round-trip is the maintainer's manual check** (needs a stood-up Authentik + an ORCID account, like
the LibreOffice/Word/Docs adapters): stand up Authentik, add ORCID as a generic OIDC source + map the iD to an
`orcid` claim, register the callosum client with the loopback redirect, set `CALLOSUM_OIDC_ISSUER`/`CLIENT_ID`,
restart, then Settings → Account → Sign in with ORCID → consent → land back signed-in with My Publications pre-filled.
The flow + pure helpers are pytest-covered (`tests/test_auth_oidc.py`, 12 tests); the unconfigured UI was headed-
verified (`.local/visual/drive_inc194_account.py` — renders the not-set-up note, no Sign-in button, no token in
`/settings`, 0 console/page/genai).

## Gates

- **pytest 666 passed, 1 skipped** (+12 `tests/test_auth_oidc.py`: not-configured/503, login→callback signs in +
  populates the profile, bad-state→no-exchange, logout, non-loopback→422, callback-exempt-under-remote-access, +
  PKCE/authorize-URL/claim-mapping/config units). `ruff check .` + `ruff format` clean.
- **QA (rule #10):** new `route_45_account.md` (the 3 endpoints + the Account FE flow) → surface **132/132 API +
  661/661 FE, 0 uncovered**.
- **Audit `…/security-audits/2026-06-29_orcid-account.md` PASS** (PKCE+state, loopback-validated redirect, JWKS
  id-token verify, write-only tokens, SSRF-safe config-derived endpoints, the safe callback exemption, default-off).
- **Principles → A-A consent value** (emergent value adopted deliberately; opt-in, default-off, identity-only — no
  library egress; the egress invariant is untouched).
- help corpus + README + CLAUDE (layout / decision-log / security-baseline) updated; `HELP-DOCS-SYNCED` → 194.
- **No migration** (`profile.orcid` already existed; tokens live in the settings store, not the DB).

## NEXT

- **Superuser role** (backlog ▲ NEXT UP) — the maintainer's ORCID (`0000-0002-2206-0325`) via a
  `CALLOSUM_SUPERUSER_ORCIDS` env allowlist → an `is_superuser` flag on the verified account; capabilities TBD.
- **SP2** email/Google login (platform-config, no app change) → **SP3** opt-in **sync** (the library-egress step —
  its own design + heavy A-A pass) → **SP4** sharing. The maintainer stands up the auth platform (host-agnostic) +
  the ORCID connector before the live round-trip.
