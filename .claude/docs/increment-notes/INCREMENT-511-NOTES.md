# Increment 511 — desktop Word structurally exempt from the Remote Access gate (supersedes inc 510's workaround)

## Implemented

Inc 510 fixed the immediate 401 (desktop Word's API calls blocked by Remote Access, on from tunnel testing) by
letting desktop's task pane carry the same Bearer token the tunnel path already uses, revealed reactively on a
401. Cliff pushed back on this as a genuine product concern, not just user error: *"if an end user has to
generate and paste access tokens every time they use desktop word, this is a real problem."* Right call — a
design that asks an ordinary end user to manually copy a secret between two apps isn't good UX even as a
nominal one-time step, and it's exactly the kind of friction that would make Remote Access + desktop Word
together feel broken rather than "an advanced feature you set up once."

**The real fix, found by re-examining the actual network topology rather than the app-level flag:** desktop
Word and the Word-on-the-web/Google Docs tunnel already run through **two genuinely separate local processes**
today — `tools/run_https.py` (`:8443`, desktop Word only) and whatever serves the plain HTTP dev port (`:8888`
on this machine, the one `cloudflared`'s ingress actually targets, confirmed by reading the real
`~/.cloudflared/config.yml`). `AccessControlMiddleware` gates by a single app-wide `remote_access_enabled` flag
applied uniformly to every request regardless of which process served it — that's *why* turning Remote Access
on for the tunnel also broke desktop. But the flag doesn't have to be uniform: **`app_settings.stored_remote_
access()`** already has a per-process override, the existing `CALLOSUM_DISABLE_REMOTE_ACCESS` env var (inc
168/254's recovery hatch) — read fresh from `os.environ` on every call, which means it's inherently scoped to
*whichever process has it set*, since `os.environ` is per-OS-process, not shared state.

So `tools/run_https.py` now sets `CALLOSUM_DISABLE_REMOTE_ACCESS=1` in its **own** environment, unconditionally,
before starting uvicorn. Since it's a separate process from whatever serves `:8888` (the tunnel's actual
target), this affects **only** desktop Word's dedicated HTTPS server — the tunnel-facing process, running with
its own untouched environment, keeps enforcing the token exactly as strict as the Remote Access setting says.
**Zero changes to `access_control.py`'s logic** — an existing, already-audited mechanism gets a second,
legitimate automatic caller. Desktop Word and an active Google Docs/Word-on-the-web tunnel now work
simultaneously with no manual token step on the desktop side at all.

This is a materially different (and safer) claim than the ORIGINAL framing I proposed and Cliff initially
approved — "trust loopback-originated requests." Reading `access_control.py` before writing that version
surfaced its own docstring already explaining why that's unsafe: `cloudflared`'s local forward makes tunnel
traffic and genuinely-local traffic indistinguishable at the TCP layer (both arrive as connections from
127.0.0.1), so IP-based trust would silently let anyone reaching the public tunnel hostname bypass the token
entirely. The port-based fix is different in kind: it doesn't infer trust from the connection's origin at all —
it trusts a **specific, dedicated process** that is architecturally *structurally incapable* of ever receiving
tunnel-relayed traffic, because `cloudflared`'s own ingress config can only ever target one fixed port, and that
port isn't :8443. This distinction is documented explicitly in all four touched files so a future reader (or a
future me) doesn't conflate the two.

### Files

- `tools/run_https.py` — sets `CALLOSUM_DISABLE_REMOTE_ACCESS=1` in its own process before `uvicorn.run(...)`;
  extensive docstring explaining why this is safe specifically for this dedicated process.
- `app/backend/app_settings.py` — `stored_remote_access()` docstring documents the second legitimate caller.
- `app/backend/api/access_control.py` — module docstring documents the same, explicit about the distinction
  from (unsafe) general loopback trust.
- `adapters/googledocs/cloudflared-config.yml` — new warning comment: never point any `service:` at :8443.
- `adapters/word/README.md` / `adapters/word/taskpane.js` — updated to reflect that desktop needs no token
  dance under normal operation; inc 510's reveal-on-401 UI stays as a defense-in-depth fallback (a signal
  something's misconfigured, not the expected flow) rather than being ripped out.
- `tests/test_run_https.py` (NEW) — `test_main_sets_the_disable_hatch_before_starting_uvicorn` (mocks `uvicorn`
  + `_dev_cert_paths`, asserts the env var is set and `uvicorn.run` receives the right kwargs) and
  `test_main_refuses_without_a_dev_cert`. Unlike inc 508's sys.path fix (no coverage, "thin dev-convenience
  script"), this one gets real coverage — it's security-relevant behavior now, not just a startup convenience.

## Key technical detail

`app_settings.stored_remote_access()` reads `os.getenv("CALLOSUM_DISABLE_REMOTE_ACCESS", ...)` fresh on every
call (confirmed by reading it, not assumed) — this is what makes the fix work at all: `os.environ` mutations
are process-local, so setting it in `run_https.py` before `uvicorn.run()` (which resolves `"app.backend.api.
app:app"` via a deferred import *inside that same process*) means every request `AccessControlMiddleware`
handles in that process sees the override, while a separately-launched `:8888` process never does.

## Manual verification script

With Remote Access ON: run `python tools/run_https.py`, open desktop Word's task pane — confirm styles/search/
insert/suggest/refresh/composer all work immediately, no token field ever appears. Confirm the Word-on-the-web/
Google Docs tunnel, hit through `cloudflared` on `:8888`, still requires the token exactly as before (a request
without one still 401s). Then flip Remote Access OFF and re-confirm desktop is unaffected either way (it was
never gated in this state to begin with).

## Pytest / tests

`pytest tests/test_access_control.py tests/test_run_https.py -v` → 11/11 passed (9 existing + 2 new), confirmed
no state leakage between the new test and the existing suite. `node --test adapters/word/taskpane_core.test.js`
→ 19/19 passed (unchanged — this increment's JS changes are comments + fallback-framing only, no logic change).
`ruff format`/`ruff check` clean on all four touched Python files.
