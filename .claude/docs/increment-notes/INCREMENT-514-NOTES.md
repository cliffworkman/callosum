# Increment 514 — a combined dev launcher so Word's HTTPS server can't silently drift from the main one

## Implemented

Today's whole debugging arc (styles empty → Remote Access token needed on desktop → trash not reflected in
diagnostics → Word add-in error) traced back to one structural problem underneath all of it: **Word's task
pane needs its own separate HTTPS server process** (`tools/run_https.py`, `:8443`) because Office.js
categorically refuses to load a task pane over plain HTTP — not a port-choice limitation, a protocol
requirement. The main dev server runs plain HTTP (`:8888`). Started as two independent commands, these two
processes silently drifted: different `CALLOSUM_DB_URL` (confirmed live — one was reading a stale/leftover DB
while the other read the real library), different code versions (confirmed via mismatched `app_version` in
`/health`, one from before today's session even started), and eventually one simply wasn't running at all
(confirmed: `run_https.py` had been stopped and nobody had a way to notice until Word threw "ADD-IN ERROR").
Cliff called this out directly: *"this isn't a tenable long term solution... shouldn't [the add-in] be port
agnostic?"* — the literal ask (port-agnostic) wasn't quite the actual fix (Word refuses HTTP regardless of
port), but the underlying complaint (don't make me run and keep two things in sync) was exactly right.

**Two real options were researched and presented** (not just the first idea that came to mind): (A) a combined
launcher script running both servers as subprocesses of one parent, guaranteed the same environment; (B) a true
single-process merge (two `uvicorn.Server` instances via `asyncio` in one process, relocating inc 511's
Remote-Access exemption from a process-wide env var to a per-request check of which socket — `scope["server"]`
— the connection arrived on). Cliff chose (A): smaller, no touch to security-relevant code, directly fixes the
actual failure mode (drift / one-not-running) without a deeper redesign. (B) is filed conceptually as the
"more thorough" option if (A) turns out not to be enough.

Also confirmed while researching, worth recording: **Word has never worked with the packaged Tauri desktop
app** — `backend.rs::pick_free_port` picks a random port every launch and serves plain HTTP only; Word support
has only ever existed in the dev-workflow. Cliff asked for this to be backlogged rather than silently left
out of scope — done (`INCREMENT-BACKLOG.md` #33/#34).

### Files

- `tools/run_dev.py` (NEW) — spawns `uvicorn app.backend.api.app:app --host 127.0.0.1 --port <HTTP_PORT>`
  (default 8888, override via `--port` or `CALLOSUM_HTTP_PORT`) and, only if the dev cert is installed
  (reuses `run_https.py`'s own `_dev_cert_paths()` — no duplicated logic), `python tools/run_https.py`
  unchanged — as two subprocesses of one parent, both inheriting the exact same environment (so
  `CALLOSUM_DB_URL` can never disagree between them). A simple poll loop (0.5s) detects either child exiting,
  stops the other, and exits non-zero naming which one died and its exit code; `Ctrl-C` stops both cleanly.
  If the dev cert isn't installed yet, HTTPS is skipped with a one-line note rather than an error — most
  callosum use never touches Word.
- `adapters/word/README.md` — the one-time setup's step 2 now points at `run_dev.py` as the primary path,
  with the old two-separate-commands approach kept as an explicitly-flagged fallback (documenting the drift
  risk if used, rather than silently removing it).
- `README.md` — one line pointing at `run_dev.py` as the "also want Word" alternative to the plain `uvicorn`
  start command, without replacing that command for the common case.
- `.claude/CLAUDE.md` — Commands table gains the `run_dev.py` row; `INCREMENT-BACKLOG.md` gains the new
  "Word support in the packaged desktop app" entry under #33/#34, with the two real obstacles found while
  researching (no per-machine cert-trust tooling available to an installed app; the random-port-per-launch
  design is incompatible with a static sideloaded manifest's fixed URL) recorded so a future session doesn't
  have to re-derive them.

**No backend/security changes** — this is a pure process-supervision script, matching `run_https.py`'s own
"thin dev-convenience script" precedent (inc 508's notes).

## Key technical detail

`run_dev.py` deliberately does **not** duplicate `_dev_cert_paths()` — it imports it from `tools.run_https`
(a proper package, confirmed via `tools/__init__.py`). This is the same "don't guess, reuse" discipline this
session applied throughout: the cert-existence check needs to match `run_https.py`'s own check exactly, since
divergence there would mean `run_dev.py` deciding to skip/attempt HTTPS based on a check that disagrees with
what `run_https.py` itself would actually do.

## Manual verification script

Live-verified end to end, including the failure path (Cliff explicitly granted standing permission to kill/
start servers as needed for this): killed the two stale/drifted processes from earlier in the session, started
`CALLOSUM_DB_URL=... python tools/run_dev.py`, confirmed both `:8888/health` and `:8443/health` report the
same `app_version` and resolve the same library search result (paper id 2) — the exact drift this increment
fixes, now gone. **Then killed only the `:8888` child directly** (found its real PID via its listening socket,
confirmed both children shared one parent PID first) and confirmed the supervisor noticed
(`"[run_dev] http exited (code 4294967295) -- stopping the rest."`, that exit code being Windows' encoding of
a forced kill), tore down the `:8443` child too rather than leaving it orphaned, and the parent process itself
exited (code 1) — both ports confirmed free afterward. Restarted cleanly afterward for continued use.

## Pytest / tests

No new tests — `run_dev.py` is a process supervisor, not app logic, mirroring `run_https.py`'s own untested
status (inc 508's notes: "a thin dev-convenience script, not app logic").
