# Security audit: Tauri desktop shell (backlog #21, increment 394)

**Date:** 2026-07-27
**Trigger:** audit-gate #3 (new file-write path — the shell writes an app-data DB + logs on a user's
own machine), #5 (net-new feature, far over 300 LOC across dozens of files), #6 (new third-party
dependencies: `win32job`, `tauri-plugin-single-instance`, `reqwest`, `tokio`, `libc` as Rust
dependencies; `python-build-standalone` + Tauri's own toolchain as build-time tooling).

## What this actually is

A Tauri v2 native-window shell that spawns callosum's own existing FastAPI backend as a child
process on the **same machine** it's installed on, and points a webview at `http://127.0.0.1:<port>`.
It does not add any new backend endpoint, does not change the backend's own egress/access-control
posture, and does not introduce any new remote-network-facing surface — the packaged backend is the
identical code that already runs in dev, unpacked onto the end user's own disk and launched with two
environment variables overridden.

## Threat review

- **Input validation / injection:** the Rust launcher spawns a **fixed** command
  (`python-runtime/python[.exe] -m uvicorn app.backend.api.app:app --host 127.0.0.1 --port <n>`) with
  **no user-controllable arguments** — the only variable is the port, which Rust itself picks (an
  ephemeral OS-assigned port via `TcpListener::bind("127.0.0.1:0")`), never taken from user input,
  network input, or a file. There is no shell (`std::process::Command` execs directly, no `cmd.exe`/
  `sh -c` involved) and therefore no command-injection surface. `smoke_test_backend.py`/CI similarly
  invoke the interpreter with a fixed argv.
- **File-path safety:** the shell resolves every path it touches through Tauri's own `app.path()`
  resolver (`BaseDirectory::Resource` for the bundled interpreter/source, `app_data_dir()`/
  `document_dir()` for the writable DB/library/log locations) — none of these are constructed from
  user input, request data, or anything reachable over a network. `CALLOSUM_DB_URL`/
  `CALLOSUM_LIBRARY_DIR` are set to fixed, OS-appropriate per-user directories, not overridable by
  the end user (no UI/CLI flag exposes them). This is the fix for a real bug (the packaged app would
  otherwise try to write its DB inside its own read-only install directory), not new user-facing
  attack surface.
- **Secrets:** no secret is introduced, stored, or transmitted by this shell. BYOK keys continue to
  flow through the existing keychain/file mechanism (`app_settings.py`) inside the spawned backend,
  unchanged.
- **Egress / SSRF:** the shell itself makes exactly one HTTP call — polling its own freshly-spawned
  `127.0.0.1:<port>/health` (via `reqwest`, plain loopback, no redirects followed, no external host
  ever reachable through this code path). It does not proxy, forward, or otherwise expose the backend
  beyond loopback — same posture as running `uvicorn --host 127.0.0.1` by hand today. Invariant #3
  (egress off by default) is untouched: the packaged backend is the same code, gated the same way.
- **Resource caps:** the health-poll loop is bounded (120s deadline, checks the child hasn't exited
  each iteration so a crash surfaces immediately rather than burning the full timeout); spawn retries
  are capped at 3 attempts. No unbounded loop or unbounded resource consumption was introduced.
- **Process lifecycle / orphan risk:** the opposite of a new risk — a Windows Job Object
  (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) and a Unix process-group signal specifically *close* the
  orphaned-process/held-DB-lock failure mode that a naive `child.kill()` would leave open (the same
  class of bug incs 272-281 fought at the app layer).
- **Supply chain:** all five new Rust dependencies are widely-used, actively-maintained crates
  (`tauri-plugin-single-instance` and `tauri`/`tauri-build` themselves are first-party Tauri
  packages; `reqwest`/`tokio` are the Rust ecosystem's de facto standard HTTP client/async runtime;
  `win32job` is a small, single-purpose wrapper around a documented Win32 API; `libc` is a stdlib-
  adjacent FFI crate). All are pinned via the committed `Cargo.lock`. `python-build-standalone` is
  Astral's own maintained project (the same org behind `uv`), fetched over HTTPS from GitHub
  Releases at **build time only** — never by the shipped app itself, so it carries no runtime attack
  surface for an end user.
- **What's genuinely new and worth naming plainly:** this is the first time callosum code runs
  **outside a context the user explicitly started** (a Tauri window auto-launches a backend process
  on double-click, versus a technical user manually running `uvicorn` today). The mitigations above
  (fixed argv, no shell, loopback-only, OS-resolved paths, existing egress gate untouched) are what
  make that an acceptable posture rather than new risk — but it's a real shift in *how* the backend
  gets started, not just packaging, and worth remembering if a future increment gives the shell any
  additional capability beyond "spawn and supervise this one fixed process."

## Negative-path checks actually run (not just described)

- Killed the shell process directly (not via its own window-close path) and confirmed the spawned
  Python child died with it (Job Object) rather than orphaning and holding the SQLite file locked.
- Launched the installed app twice; confirmed the second launch did not spawn a second backend
  process (single-instance plugin).
- Ran the real NSIS installer (not `cargo tauri dev`) and confirmed the resulting install directory
  contains exactly the bundled interpreter + staged source + Tauri's own binary — no unexpected
  files, no secrets baked in.

## Security Audit: PASS

No new remote-facing attack surface, no injection vector, no secret-handling change, no egress-gate
change. The one real behavioral shift (auto-launching a backend process without an explicit terminal
command) is mitigated by a fixed, non-user-influenced command line and loopback-only networking.
