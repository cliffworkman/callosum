# Increment 168 — Google Docs SP0: the remote-access security foundation (auth + rate-limiting)

**What the user asked for:** the **Google Docs adapter** ("let's do it" → "build what's needed, be safe"). The user
chose **cloudflared on the local machine** as the bridge (Google's cloud can't reach localhost). SP0 builds the
**security foundation** the Security baseline mandates before any exposure — fully in-codebase + pytest-verifiable;
the cloudflared bridge (SP1) and the Apps Script add-on (SP2, manual-test-only) follow.

**The make-or-break safety fact:** cloudflared runs locally and forwards to `localhost:8080`, so the app sees a
tunnel request and the local browser **identically** (both loopback; `request.client.host` can't distinguish them;
`Host` is attacker-controllable). **So the only safe boundary is a bearer token applied to every sensitive
endpoint** — that shaped the whole design.

## Implemented

- **`app/backend/api/access_control.py`** (new) — `AccessControlMiddleware` (Starlette `BaseHTTPMiddleware`):
  - **OFF (default) → pure pass-through** (a no-op; **zero change** for localhost-only users + the whole suite).
  - **ON → require `Authorization: Bearer <token>`** (constant-time `secrets.compare_digest`) on every request
    except `GET /health`, `GET /` (the static shell — no library data), and `OPTIONS` (CORS preflight). Bad/missing
    → **401 JSON**. Flag + token read **fresh per request** so the toggle is live.
  - **`RateLimiter`** — a tiny in-memory sliding-window limiter (no dependency), 120 req/60s, **429 + Retry-After**;
    active only when remote access is on. Defaults resolved at construction so a test can lower them.
- **`app/backend/app_settings.py`** — refactored the keychain/file secret core into reusable
  `_get_secret(field)`/`_set_secret(field, value)` (provider keys now route through them — behavior-preserving,
  covered by `test_settings.py`), and added `remote_access_enabled` (file flag, like `data_egress`) +
  `access_token` (secret, keychain/file) + `generate_access_token()` (`secrets.token_urlsafe(32)`) +
  `stored_remote_access()` (honors `CALLOSUM_DISABLE_REMOTE_ACCESS=1`, the local recovery hatch).
- **`app/backend/api/routers/settings.py`** — `remote_access_enabled` + `access_token_set` on `GET /settings`
  (**never the value**); the toggle on `PUT /settings` (**422 if enabling with no token minted** — lockout-safe);
  `POST /settings/access-token` (mint → return the value **once**).
- **`app/backend/api/app.py`** — `api.add_middleware(AccessControlMiddleware)` after CORS (CORS stays outermost).
- **`app/frontend/js/00_lib.jsx`** — `getAccessToken`/`setAccessToken` (localStorage) + a **same-origin `fetch`
  shim** that injects the bearer header on same-origin requests from ONE place, so the `api*` helpers **and** every
  raw fetch (exports, PDF bytes) carry the token uniformly. The token is **never injected into the served HTML** →
  no leak path.
- **`app/frontend/js/35_settings.jsx`** — a `RemoteAccessSettings` section: a default-OFF toggle (enable = mint a
  token → save to localStorage → flip on; the token is shown once to copy into the add-on), Regenerate, and the
  recovery note.

## Key technical detail
- **Why the token gates everything:** cloudflared makes tunnel == local at the app layer, so no network signal is a
  trust boundary. The exemptions (`/health`, `/`, `OPTIONS`) carry no library data.
- **Lockout-safe + recoverable:** can't enable without a minted token (422); if the token is lost, two **local-only**
  hatches (`CALLOSUM_DISABLE_REMOTE_ACCESS=1` env, or edit `~/.callosum/app-settings.json`) — neither reachable by a
  remote attacker.
- **No HTML injection:** the token lives only in localStorage; the fetch shim reads it there. (Contrast: injecting it
  into `/` would leak it to any caller that can fetch `/`.)
- **REQUIRED SP1 control (recorded in the audit):** the cloudflared ingress must forward **only** the cite endpoints
  (`/papers`, `/papers/export`, `/citations/*`) → `localhost:8080`, so `/`, `/settings`, and the file-read/scan
  routes are **unreachable via the tunnel** (defense-in-depth over the token). No tunnel should point at callosum
  until SP1 ships that.
- **No new dependency** (hand-rolled limiter; `secrets`/`keyring` already present); **no migration** (settings file).

## Manual verification
**Headed, no egress** (`.local/visual/drive_inc168_remote_access.py`, isolated `CALLOSUM_SETTINGS_PATH`, file store
forced): the library loads (gate off) → Settings → **Remote access** toggle is OFF → enable → an access token is
shown **once** → `GET /settings` reports `remote_access_enabled` + `access_token_set` with **no token value** → a
**reload still loads the library under the gate** (the fetch shim sends the token) → toggle off; **0 console/page/genai**.

**Automated:** `pytest tests/test_access_control.py` — the limiter; gate off→no-op; on→401 (no/wrong token) / 200
(right token); `GET /health` exempt; `CALLOSUM_DISABLE_REMOTE_ACCESS` hatch; 429; enable-without-token→422;
mint-once-then-status-only (token absent from `GET /settings`). + `test_settings.py` (BYOK refactor preserved) +
`test_health.py` route-surface.

## Gates
- **Audit `.claude/security-audits/2026-06-27_remote-access-auth.md` PASS** (token sole constant-time boundary;
  default-off; secret never logged/returned/injected; local recovery; the SP1 ingress-allowlist required control).
- **Principles (rule #9):** access/egress posture, not a claim/signal → the **A-A consent value** (explicit, opt-in,
  default-off, user-controlled egress). Aligned.
- **QA (rule #10):** `route_35_settings.md` extended; surface **121/121 API + 604/604 FE, 0 uncovered**.
- **Help corpus:** privacy section gained a "Remote access" note (`HELP-DOCS-SYNCED` → 168).

## Pytest
**619** (+8 `tests/test_access_control.py`; `test_settings.py`/`test_health.py` adjusted). `ruff` clean; build +
assembly green.

## Next
**SP1 — the cloudflared bridge:** docs + a `tools/run_tunnel.py`-style helper + the **ingress allowlist** (forward
only the cite endpoints) + a Settings field for the public URL; its own audit (the live egress) + the user's manual
tunnel check. **SP2 — the Apps Script Google Docs add-on** (`adapters/googledocs/`: a sidebar; `UrlFetchApp` → the
tunnel URL with the bearer token; citations as NamedRange + DocumentProperties, the Zotero pattern; reuses
`/papers?q=` + `/papers/export` + `/citations/render-document` + `/citations/suggest`); manual-test-only.
