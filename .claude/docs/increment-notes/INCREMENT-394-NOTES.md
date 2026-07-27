# Increment 394 — Tauri desktop shell: click-to-install packaging (Windows working, macOS CI-only)

**Date:** 2026-07-27
**Status:** Windows path fully built and verified end-to-end. macOS path built (CI workflow) but
genuinely unverified — no Mac hardware available in this environment.

## Context

Backlog #21 ("Packaging & distribution, post-V1"). Building toward a click-to-install desktop app
for callosum's first external adopter (a non-technical, AI-skeptic labmate), on a 2-day deadline.
Builds directly on the 2026-07-23 research spike (`.claude/docs/future-tracks/
desktop-packaging-tauri.md`, `INCREMENT-343-NOTES.md`), which scoped the real problem (bundling
Python + its ML dependency stack into a Tauri shell) but explicitly deferred committing to it.

## Implemented

New `app/desktop-shell/` subsystem (scaffolded from the throwaway spike at
`C:\tauri-spike\callosum-shell-spike\` — icons/build.rs/main.rs reused, everything else new):

- **`src-tauri/src/backend.rs`** — resolves bundled-resource paths (`BaseDirectory::Resource`),
  picks a free loopback port, spawns `python-runtime/python.exe -m uvicorn app.backend.api.app:app`
  with `CALLOSUM_DB_URL`/`CALLOSUM_LIBRARY_DIR` overridden to per-user app-data/documents
  directories (the bundled resource dir is read-only once installed), polls `/health` tolerating
  connection-refused (uvicorn doesn't bind until after eager ML imports finish), and kills the whole
  process tree on shutdown — a Windows Job Object (`win32job`, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`)
  so descendants die even on our own crash, a process-group signal on Unix.
- **`src-tauri/src/lib.rs`** — `tauri_plugin_single_instance` (second launch focuses the existing
  window instead of spawning a second backend), a static splash window + a dynamically-created
  `main` window once `/health` returns 200, a `retry_backend` command for the splash's Retry button,
  `RunEvent::ExitRequested`/`Exit` cleanup.
- **`tauri.conf.json`** — splash-only static window (the main window's URL is only known once a port
  is picked at runtime); `bundle.resources` ships the whole portable-Python-plus-source directory
  tree (not `externalBin`/sidecar — that's single-binary-shaped, wrong fit for a whole interpreter +
  venv); NSIS-only target, `installMode: currentUser` (no UAC prompt).
- **`Info.plist`** — an ATS exception for `127.0.0.1`/`localhost` (WKWebView blocks plain `http://`
  navigation by default on macOS; WebView2 has no equivalent restriction, so this is a macOS-only gap
  Windows testing can't surface).
- **`packaging/`** — `stage_source.py` (copies `app/backend`, `alembic`, `alembic.ini`,
  `integrations/`, and the prebuilt `callosum-app.html` into `resources/callosum-src/`),
  `build_python_windows.ps1` / `build_python_macos.sh` (download `python-build-standalone`, `pip
  install` this project's real `requirements.txt` into it — not PyInstaller/Nuitka freezing, per the
  spike's own recommendation), `smoke_test_backend.py` (spawn the bundled interpreter standalone, no
  Tauri, confirm `/health` — the required blocking CI gate for the macOS build).
- **`.github/workflows/desktop-shell-macos.yml`** — builds an arm64-only portable Python on
  `macos-latest`, runs the blocking smoke test, then `tauri build` for a `.dmg`. Not on every
  push — `workflow_dispatch` + path-filtered.
- **`FIRST-LAUNCH-NOTE.md`** — a plain-language explainer for the labmate: exactly what the Windows
  SmartScreen / macOS Gatekeeper dialogs look like and what to click. No code signing/notarization on
  either platform in this window — not a corner cut, a door that isn't open (Apple Developer
  enrollment alone exceeds 2 days; a same-day Windows cert wouldn't stop SmartScreen either, since
  its reputation builds over time).
- **Small unrelated UI fix, same session:** the WIP tab button showed both a `wip-badge` pill AND the
  words "Work in progress" — redundant and too wide. Collapsed to just "WIP" (`30c_frame.jsx`).

## Key technical details

**Two real bugs found only by actually running this, not by review:**

1. **A pipe deadlock in the test harness, not the product.** `smoke_test_backend.py`'s first version
   read the spawned uvicorn's `stdout=PIPE` only after detecting the child had exited. uvicorn's
   startup alone emits dozens of multi-line Alembic migration log lines — enough to fill the ~64KB
   Windows pipe buffer, at which point the child blocks on its own next write and never finishes
   booting. Every run timed out at 150s looking exactly like "still starting." Fixed by continuously
   draining the pipe on a background thread into a bounded tail buffer — which is exactly what the
   real Rust launcher's `drain_output` already does for the same reason, so the product code was
   never at risk here, only the diagnostic script.
2. **A real missing-dependency bug in `stage_source.py`.** The first staged build crashed on launch
   with `ModuleNotFoundError: No module named 'integrations'` — `stage_source.py` copied
   `app/backend`, `alembic`, and the frontend HTML, but the backend also imports a top-level
   `integrations/` package (Crossref/OpenAlex/arXiv/Gemini adapters etc.) that was never staged.
   Confirmed via grep that `integrations` is the *only* other top-level package `app/backend`
   imports (adapters/mcp_server/ops/research/sync_server/www are never imported from here) and fixed
   `stage_source.py` accordingly.

**A Windows-specific packaging bug, root-caused and fixed:** the first real `tauri build` succeeded
through Rust compilation and NSIS setup, then **`makensis` itself aborted** on a 276-character path:
`torch-2.13.0.dist-info/licenses/third_party/kineto/libkineto/third_party/dynolog/third_party/DCGM/
testing/python3/libs_3rdparty/colorama/LICENSE.txt`. This is torch vendoring license copies for its
*internal C++ profiler's own vendored build/test tools* — pure attribution text, zero functional
code, ~106 files, all under one `dist-info/licenses/third_party/` subtree. Pruned that subtree
specifically (torch's own top-level `licenses/LICENSE` is untouched) in both `build_python_windows.
ps1` and `build_python_macos.sh` — a real, narrow licensing-completeness tradeoff, flagged rather
than done silently, not just cleanup.

**A real gap in the project's own tooling, caught and fixed in the same session:**
`tools/check_line_budget.py` globs `app/**/*.py` with no gitignore-awareness — it started silently
walking into `app/desktop-shell/resources/` (a build-time-bundled portable Python + its full
pip-installed dependency tree, thousands of vendored `.py` files) and `src-tauri/target/` (Cargo's
build output), turning a 6-second check into a multi-minute one with meaningless "violations" against
third-party code. Fixed by switching `collect()` from `Path.rglob` (which still traverses into a
directory before you can filter its contents) to `os.walk` with in-place `dirnames` pruning, and
excluding `resources`/`target`/`node_modules` by bare directory name — verified no legitimate
directory under `app/`/`integrations/` collides with any of those three names first.

**Verified end-to-end on this machine (Windows), not just built:**
- Standalone backend smoke test (no Tauri): portable CPython 3.11 + every real dependency
  (`torch==2.13.0`, `sentence-transformers`, `PyMuPDF`, `scikit-learn`, `sqlite-vec`, etc.) installed
  via plain `pip` (not `uv` — `uv`'s HTTP client hit a reproducible TLS/SNI mismatch against
  pythonhosted.org's Fastly CDN in this sandbox; plain `pip` worked against the identical URL) —
  `/health` returns 200 in ~20s from a warm run.
- **MAX_PATH check at a real install-like deep path** (`%LOCALAPPDATA%\Programs\callosum-shell\
  resources\python-runtime\...`, 157 characters to the deepest torch header): `import torch,
  sentence_transformers, fitz, sklearn, sqlite_vec` succeeds cleanly.
- **The actual NSIS installer, built and silently installed for real** (`Callosum_0.1.0_x64-setup.exe
  /S`, 230MB) — not `cargo tauri dev`. Confirmed via process/network inspection (no GUI automation
  available in this environment, so this could not be visually verified — see Manual verification
  debt below): `callosum-shell.exe` spawned the bundled interpreter as a child on a freshly-picked
  port; `/health` returned 200; the real frontend then loaded and fired its **entire normal startup
  API cascade** against the bundled backend — `/`, `/axes`, `/papers`, `/tags`, `/settings`,
  `/my-publications/dashboard`, `/feed`, `/funding-discovery/*`, `/methods/*/summary` (statcheck,
  retraction, transparency, lmm, meta-analysis, bayes), `/citations/styles`, `/wip/*` — all **200
  OK**, proving the splash→spawn→health-poll→main-window swap genuinely works, not just that a
  process launches.
- **Cleanup verified**: killing the shell process (`Stop-Process`) killed the spawned Python child
  too (Job Object working) — no orphaned process, no held SQLite lock.
- **Single-instance verified**: launching the installed app a second time did not spawn a second
  backend; the existing process/window remained the only one running.

## Manual verification debt (real, not closed)

No GUI-automation tool is available in this environment to click an actual window. Everything above
was verified through process inspection, log files, and direct HTTP calls to the backend the shell
spawned — not by looking at the screen. **Cliff still needs to actually watch the splash page render,
confirm the window looks right, and click through a real install/launch/close cycle himself** before
trusting this beyond "the mechanics are sound." The `.claude/backups/plans/2026-07-27_tauri-desktop-
shell-packaging.md` plan file has the full day-by-day verification sequence if useful as a checklist.

**Windows Sandbox test (originally planned Day 1 step 5) was not run** — enabling it requires a
reboot of this shared working machine, which wasn't taken unilaterally. Worth running before handing
the installer to someone whose machine may lack VC++ redistributables this dev machine already has.

**macOS is genuinely unverified beyond CI's backend-only smoke test** (see the workflow file's own
header comment) — no Mac hardware exists in this environment. It proves the real dependency stack
(torch/PyMuPDF/scikit-learn, arm64 wheels) imports and serves; it does not prove Gatekeeper lets the
app open or that the webview loads. **arm64-only is a deliberate bet**, confirmed with Cliff given
the labmate's Mac architecture is unknown — an Intel Mac cannot run this build at all (a hard crash,
not friction).

## Files changed

- `app/desktop-shell/{README.md,FIRST-LAUNCH-NOTE.md,package.json,package-lock.json}`
- `app/desktop-shell/src-tauri/{tauri.conf.json,Info.plist,Cargo.toml,Cargo.lock,build.rs,.gitignore}`
- `app/desktop-shell/src-tauri/src/{main.rs,lib.rs,backend.rs}`
- `app/desktop-shell/src-tauri/capabilities/default.json`
- `app/desktop-shell/src-tauri/icons/*` (reused from the spike)
- `app/desktop-shell/splash/{index.html,splash.css,splash.js}`
- `app/desktop-shell/packaging/{stage_source.py,build_python_windows.ps1,build_python_macos.sh,smoke_test_backend.py}`
- `.github/workflows/desktop-shell-macos.yml`
- `tools/check_line_budget.py` (directory-pruning fix)
- `.gitignore` (excludes `app/desktop-shell/resources/`)
- `app/frontend/js/30c_frame.jsx`, `tests/test_frontend_assembly.py`, `callosum-app.html` (WIP tab
  label fix, unrelated small UX request from the same session)

## Verification

- Frontend assembly + migrations: **58 passed**.
- Ruff check/format: clean (543 files). Line budget: **406 files**, all within cap (after the tool
  fix above).
- Manual end-to-end run against the real installed NSIS build: confirmed working per the section
  above — install, spawn, health, real-UI-load, cleanup, single-instance all verified via process/
  network inspection. No visual/GUI confirmation possible in this environment (flagged, not claimed).
- macOS: CI workflow written, not yet run (needs a push + `workflow_dispatch` to actually exercise
  GitHub's `macos-latest` runner) — genuinely unverified beyond that.
