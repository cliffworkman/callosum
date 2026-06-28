# Security audit — Remote access: auth + rate-limiting (inc 168, Google Docs SP0)

**Date:** 2026-06-27
**Feature:** The security foundation for reaching local callosum from the Google Docs add-on via a (later) cloudflared
tunnel. An **opt-in, default-OFF** bearer-token gate (`AccessControlMiddleware`) + a hand-rolled rate limiter + a
**Remote access** Settings surface (mint token / toggle). Files: `app/backend/api/access_control.py` (new),
`app/backend/api/app.py` (wire), `app/backend/app_settings.py` (token + flag store; secret-store refactor),
`app/backend/api/routers/settings.py` (status/update + `POST /settings/access-token`),
`app/frontend/js/00_lib.jsx` (same-origin bearer fetch shim), `app/frontend/js/35_settings.jsx` (UI).
**Audit triggers:** (1) new endpoint + request-schema change, (4) **new auth/authorization logic**, (5) 3+ files.

## Threat model shift
This is the increment that **crosses the Security baseline** ("no auth, no rate limiting — add both before exposing").
The decisive fact: a cloudflared tunnel runs **locally** and forwards to `localhost:8080`, so the app sees a tunnel
request and the local browser **identically** — `request.client.host` is loopback for both, and `Host` is
attacker-controllable. **Therefore the app cannot use any network signal as a trust boundary; the bearer token is
the only one.** It is applied uniformly to every sensitive endpoint when the feature is on.

## Threat review
- **Auth logic.** When `remote_access_enabled` is on, every request needs `Authorization: Bearer <token>`, compared
  **constant-time** (`secrets.compare_digest`), except `GET /health` (liveness) and `GET /` (the static shell —
  carries no library data). Missing/blank/wrong token → **401 JSON** (never a stack trace). The flag + token are read
  fresh per request from `app_settings` so the toggle takes effect live.
- **Default-OFF safety.** `stored_remote_access()` defaults False → the middleware is a **pure pass-through**: zero
  behavior change for every localhost-only user (and the full 611-test suite, confirmed). Off is the safe default.
- **Lockout / recovery.** Enabling requires a token to already be minted (`PUT /settings` → 422 otherwise) so the UI
  can never strand itself "gated but tokenless." If the user loses the token, two **local-only** recovery hatches:
  `CALLOSUM_DISABLE_REMOTE_ACCESS=1` (env, honored by `stored_remote_access`) or edit `~/.callosum/app-settings.json`.
  A remote attacker can do neither (no env/filesystem access on the user's box).
- **Secret handling.** The token is stored exactly like the BYOK keys — OS keychain if available, else the gitignored
  `~/.callosum/` file (the `_get_secret`/`_set_secret` refactor; the BYOK provider keys now route through it too,
  behavior-preserving — covered by `test_settings.py`). It is **returned exactly once** by `POST /settings/access-token`
  (so the user can copy it into the add-on) and **never again**: `GET /settings` reports only `access_token_set`
  (booleans), never the value (tested). Never logged. The frontend keeps it in `localStorage`, **never** injected into
  the served HTML — so there is no token-leak-via-`/` path.
- **Egress posture (invariant #3).** Turning Remote access ON **is** the explicit, default-off, user-controlled
  consent to expose the library remotely (the A-A consent value). It changes no existing egress path; the Gemini gate
  is untouched. The Settings copy states plainly what enabling exposes.
- **CORS / preflight.** Unchanged. The gate exempts `OPTIONS` (preflight carries no auth by design) and is added
  after CORS so CORS stays outermost.
- **Rate-limiting.** A small in-memory sliding-window limiter (no dependency), 120 req/60s, **429 + Retry-After** on
  breach; active only when remote access is on (the heavy local-only user is never throttled). Bounded memory.
- **Resource / file-read routes.** `POST /library/scan`, `POST /library/watched/rescan`, and the launch/focus
  library-folder auto-read read arbitrary **server files**. When remote access is on they are token-gated like
  everything else — **but the token holder (the add-on) should never be able to trigger a filesystem scan.** The hard
  guarantee is **SP1's cloudflared ingress allowlist: forward ONLY the cite endpoints** (`/papers`, `/papers/export`,
  `/citations/*`) to `localhost:8080`, 404 everything else — so `/`, `/settings`, and the scan routes are
  **unreachable via the tunnel**. **REQUIRED SP1 CONTROL (recorded here):** SP1 must ship + verify that ingress
  allowlist; until then, no tunnel should be pointed at this app.
- **Supply chain.** No new dependency (hand-rolled limiter; `secrets` stdlib; `keyring` already optional). No migration.

## Negative-path checks (tests/test_access_control.py + tests/test_settings.py)
- remote OFF → `GET /papers` 200 with no token; `GET /settings` reports `remote_access_enabled:false`. ✔
- remote ON → `GET /papers` no token / wrong token → **401**; correct bearer → 200. ✔
- `GET /health` exempt when on. ✔
- `CALLOSUM_DISABLE_REMOTE_ACCESS=1` forces the gate off (recovery). ✔
- rate limit (lowered to 3) → 429 after the budget. ✔ (+ a pure `RateLimiter` unit test).
- `PUT /settings {remote_access_enabled:true}` with no token minted → **422**. ✔
- `POST /settings/access-token` returns the value once; `GET /settings` has `access_token_set:true` and the token
  value is **absent** from the body. ✔
- (headed) enabling → the local browser keeps working under the gate (the fetch shim carries the token); 0 console/
  page/genai.

## Result
**Security Audit: PASS** — for SP0 as a **local foundation**. The token is the sole, uniform, constant-time boundary;
default-off; secret never logged/returned/injected; recovery hatches are local-only; rate-limited. **Exposure does
not begin until SP1**, which **must** ship the cloudflared ingress allowlist (the recorded required control) before
any tunnel is pointed at callosum; that step gets its own audit (egress + the live tunnel).
