# Increment 254 — In-app recovery from a remote-access lockout

## Context (why this exists)

Discovered live: the maintainer's own instance began throwing `HTTP 401 on /papers` / `/summaries`. Root
cause — **Remote access** (inc 168) was left ON (`remote_access_enabled: true`) while the browser held no
matching bearer token, so `AccessControlMiddleware` 401'd **every** endpoint except the static shell (`/`,
`/health`, `/oauth/callback`). Because `GET /settings` 401s too, the user couldn't even reach the UI to turn it
back off — a genuine dead-end — and the on-screen error ("Start the backend… `uvicorn …`") wrongly blamed a
dead server. This increment builds a **testable, in-app escape hatch** a locked-out user (or beta tester) can
actually use.

## Implemented

**Backend**
- `app/backend/api/access_recovery.py` (NEW) — the recovery-code model. `start_recovery()` mints a 128-bit
  single-use code (`secrets.token_urlsafe(16)`), writes it to `~/.callosum/recovery-code.txt` (owner-only),
  and returns **only the path** (the code is never logged or returned). `verify_recovery(code)` constant-time
  compares against the pending code, honoring a 10-min TTL, and consumes it (single-use) + deletes the file.
  State is an in-process module global (`_pending`) — never persisted to the settings store.
- `app/backend/api/routers/access.py` (NEW) — `POST /access/recover`. `{}` → start (returns `code_path`);
  `{code}` → verify → on success `app_settings.set_remote_access_enabled(False)`. `RecoverRequest.code` is
  capped via `Field(max_length=RECOVERY_CODE_MAX_LEN)`.
- `app/backend/api/access_control.py` — new `_RECOVERY_PATHS = {"/access/recover"}`; a dispatch branch lets it
  through **without a token** (the user is locked out) but **still rate-limited** under a `"recover"` key (kept
  OUT of `_EXEMPT_PATHS`, which bypass the limiter). Docstring recovery note updated.
- `app/backend/api/app.py` — register `access.router`.

**Frontend**
- `app/frontend/js/00_lib.jsx` — every `api*` helper now flags a 401 as `{status:401, authRequired:true}` and
  calls a single registered `onAuthRequired` handler; added `startAccessRecovery()` / `submitAccessRecovery(code)`
  / `clearAccessToken()`.
- `app/frontend/js/01_recovery.jsx` (NEW) — `AccessLockOverlay`: honest copy ("Remote access is on — this
  browser isn't authorized"), two tabs — **I have the token** (paste → `setAccessToken` → reload) and **I lost
  it — turn remote access off** (start reset → read the local-file code → submit → gate off → reload).
- `app/frontend/js/40_app.jsx` — `authLocked` state; register the handler once; render `<AccessLockOverlay />`
  in the shared `modals` fragment (covers desktop + mobile).
- `app/frontend/js/03_library.jsx` — propagate `authRequired` into the list error state.
- `app/frontend/js/10_pdf_layer.jsx` — errbox branches: a 401 shows "Remote access is locked", not the
  "start the backend / uvicorn" text (that stays only for a true connection failure).
- `app/frontend/js/35_settings.jsx` — replaced the stale "remove the token from `~/.callosum/app-settings.json`"
  hint (wrong for keychain users) with a pointer to the recovery panel.
- `app/frontend/styles.css` — `.lockout-*` rules, reusing the canonical `.axis-modal` shell (backdrop / card /
  shadow / radius); amber (`--flag-*`) for the "locked/unresolved" status message (DESIGN §4). Tokens only.

## Key technical detail — why a local-file code is the right proof

The middleware **cannot distinguish a local-browser request from a cloudflared-tunnel request**: both arrive on
loopback and the `Host` header is attacker-controllable (documented in `access_control.py`). So the token is
normally the only boundary — but a locked-out user has no token. Recovery therefore can't authorize on *anything
in the request*; it has to prove the caller is **physically at the machine**. The mechanism: the server writes a
high-entropy one-time code to a local file, and the caller must read it back. A remote/tunnel caller can POST
`/access/recover` but **cannot read the file**, so it can't complete phase 2 (128-bit entropy + single-use +
10-min TTL + rate limit defeat guessing). And the endpoint is **disable-only** — the worst a caller can achieve
is returning the app to its safe local-only default; it never mints/reveals a token or reads library data. Under
the recommended cloudflared allowlist (`/papers`, `/papers/export`, `/citations/*`) the path isn't forwarded at
all — defense in depth.

## Manual verification script

1. `pip`-install deps, `npm install`, `python tools/build_frontend.py`.
2. Enable the lockout (simulating the live bug): start the app; in Settings → **Remote access**, turn it ON and
   copy the token. Then in the browser console: `localStorage.removeItem('callosum.accessToken')` and reload.
3. **Expect:** the app shows the **AccessLockOverlay** ("Remote access is on — this browser isn't authorized"),
   NOT a "start the backend" box. (Behind it, the library errbox reads "Remote access is locked.")
4. **Path 1 (token):** tab **I have the token** → paste the copied token → **Unlock** → the app reloads and the
   library/synthesis load normally.
5. **Path 2 (reset):** re-lock (remove the token again, reload). Tab **I lost it — turn remote access off** →
   **Start reset**. Open the shown file (`~/.callosum/recovery-code.txt`) on the machine, copy the code, paste
   it, **Turn off remote access** → the app reloads; Settings now shows Remote access OFF and everything loads
   with no token.
6. **Negatives (curl/devtools):** `POST /access/recover {"code":"wrong"}` → `{"status":"invalid"}` and
   `GET /papers` still 401; the start response's body never contains the code; an oversized code → 422; rapid
   repeats → 429.

## Pytest

`tests/test_access_recovery.py` — **+11** (module: write-to-file, single-use, expiry, overwrite; endpoint:
start-returns-only-path, valid-disables, wrong-leaves-on, never-reveals-token, oversized-422, rate-limit-429,
harmless-when-off). Focused run `test_access_recovery.py + test_access_control.py` → **19 passed**. **Full suite:
992 passed, 1 skipped** (`--ignore=tests/test_mcp_server.py` — the optional `mcp` package isn't installed in this
environment, a pre-existing gap unrelated to this change). The frontend copy/CSS refinements from the experience
pass land after that run but touch no Python/test, so the count stands.

## Gates

- **Security audit:** `.claude/security-audits/2026-07-02_access-recovery.md` → **PASS** (disable-only,
  local-possession-gated, input-capped + constant-time, rate-limited, no new dependency, no egress).
- **QA (rule #10):** `route_35_settings.md` extended — `/access/recover` + `01_recovery.jsx` declared; a
  disable-only/local-possession standing assertion + a recovery step added. `build_surface_map.py check` →
  195/195 API + 901/901 FE, **0 uncovered**.
- **DESIGN (rule #8):** reused the `.axis-modal` recipe + existing tokens; no new raw hex.
- **Experience (rule #11):** dispatched a persona-grounded agent *in character as the non-technical locked-out
  beta tester with a paper due*. Verdict: reception is reassuring (the 🔒 card answers "did I lose my library?"
  in its first line; no traps), and path 2 is a real non-technical exit — but the **make-or-break gap** was that
  path 2 showed a bare file path (`C:\Users\…\.callosum\recovery-code.txt`) with **no guidance a non-dev could
  use to open it**. Fixed in-increment (all cheap): (1) the code-file step now says it's a plain-text file
  (Notepad/TextEdit) + a **Copy path** button + "paste into File Explorer/Finder" tip; (2) the subtitle now names
  the actual toggle the user flipped — **Allow citing from Google Docs** — not abstract "a setting you turned on";
  (3) the reset button reads **"Get my recovery code"** not "Start reset" (which scanned as *erase my data*);
  (4) dropped "Bearer token" jargon → "sent securely with each request"; (5) success now shows a **green**
  confirmation ("Remote access is off — your library is available locally again") for ~1.4s before the reload,
  instead of the reassurance being lost to an instant refresh; (6) the last-resort footer now points a
  non-technical user at "ask whoever helped you set up remote access" before the env-var. Backlog: none
  outstanding — every finding was fix-cheap and shipped here.
