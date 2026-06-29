<!-- qa-coverage
api: /auth/login, /oauth/callback, /auth/logout
fe: 35_settings.jsx
-->

# ROUTE 45 - Optional account (Sign in with ORCID)

**Tier:** 1 local-stateful
**Goal:** Exhaust the SP1 optional-account surface (Settings → Account) and its safety boundaries WITHOUT a live OIDC
provider. The full ORCID round-trip needs a stood-up account platform (Authentik) and is the maintainer's MANUAL
check — not Playwright-drivable; this route verifies everything around it.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** The seeded instance has **no OIDC env**
(`CALLOSUM_OIDC_ISSUER` / `CALLOSUM_OIDC_CLIENT_ID` unset), so sign-in is **not configured** — that is the expected
default state to test. Register console/pageerror/request listeners before navigating.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.** Any visible control that can't be completed through the UI is a bug.
- **Identity-only, no library egress (the core SP1 promise).** Nothing about the library, PDFs, or notes may be sent
  on any auth action. With egress unset, **any** request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Local-first stays the default.** With no account configured and not signed in, the app must work **exactly** as
  today (no gating of any feature on an account). An account requirement that blocks a core feature is **Critical**.
- **Tokens are write-only (the inc-146/168 discipline).** `GET /settings` reports the `account` block (`configured`,
  `signed_in`, `display_name`, `orcid`, `expires_at`) but **never** a token (`access_token`/`refresh_token`/`id_token`).
  Any token value in the `GET /settings` body is **Critical**.
- **Default-off.** On the clean (unconfigured) instance, `account.configured` is **false** and `account.signed_in`
  is **false**; the Account section shows the "not set up yet" note (no Sign-in button that 503s on click is fine —
  but ideally the button is hidden when unconfigured).
- **Loopback-only redirect (no open-redirect).** `GET /auth/login?origin=https://evil.example` → **422**;
  `GET /auth/login` with no origin (and no `CALLOSUM_OAUTH_REDIRECT`) → **422**. (These need the issuer/client
  configured to reach the validation — see the direct-API note; on the unconfigured instance `/auth/login` → 503.)
- **Callback gate-exemption is safe.** `GET /oauth/callback` is reachable without a bearer even when Remote access is
  on (it's a browser navigation) — but it carries only an opaque code+state validated against the stored PKCE
  verifier; a bad/missing state → a redirect to `/?signin=error`, **never** a signed-in session.
- **Signal not verdict / coordinate honesty.** Unchanged here (no claims/coordinates on this surface).

## Adversarial checklist

- click any Account control rapidly / double-click
- `GET /auth/login` with a non-loopback / missing origin (direct API)
- `GET /oauth/callback?code=x&state=WRONG` (direct API) → must NOT sign in
- deep-link `/?signin=ok` and `/?signin=error` (the callback's redirect targets) — the app must load normally
- resize to `375x812`, hard refresh — no horizontal overflow

## Steps

1. Open Settings → confirm an **Account** section renders with the "Optional account — Sign in with ORCID" label and
   the "works fully offline with no account · identity only · your library never leaves your machine" explanation.
2. On the clean (unconfigured) instance: confirm it shows the **"Sign-in isn't set up on this Callosum yet"** note
   and **no** Sign-in button (or a button that, if present, surfaces a graceful 503, never a console error).
3. `GET /settings` (direct) → `account.configured:false`, `account.signed_in:false`; the body contains **no**
   `access_token`/`refresh_token`/`id_token`.
4. Confirm every core feature (library list, a PDF open, axes, synthesis pane) works with no account — local-first
   is unblocked.
5. **Direct-API safety (no live provider needed):**
   - `GET /auth/login` (unconfigured) → **503**.
   - `GET /oauth/callback?code=x&state=nope` → **303** redirect to `/?signin=error` (no session created;
     `GET /settings` still `signed_in:false`).
   - `POST /auth/logout` → **204** (idempotent; no session to clear).
6. Deep-link `/?signin=ok` then `/?signin=error` — the app loads normally (the query param is cosmetic).
7. Resize to mobile while Settings is open; the Account section's controls/labels don't overflow.
8. **Egress check:** across all of the above, **zero** requests to any genai/cloud host; no request carries library
   text.

## Manual-only (note in the report; not driven here)

The full sign-in (Settings → Sign in with ORCID → the Authentik/ORCID consent → `/oauth/callback` → signed-in,
My-Publications populated with the verified ORCID) needs a stood-up account platform + an ORCID account, so it is the
**maintainer's manual check** (like the LibreOffice/Word/Google-Docs adapters). Verify the unit-tested flow contract
instead (`tests/test_auth_oidc.py`): state+PKCE setup, callback exchange, write-only token storage, verified-ORCID →
profile, callback exemption, logout.

## Pass criteria

- The Account section renders; the unconfigured default is honest (not-set-up note, no signed-in state).
- 0 console/page errors and 0 genai-host requests; no library text leaves the machine on any auth action.
- Tokens never appear in `GET /settings`; the bad-state callback never signs in.
- Local-first works fully with no account. Mobile viewport: no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_45_account.md` + `screenshots/` (see `_TEMPLATE.md`).
