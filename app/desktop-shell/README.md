# Desktop Shell

A Tauri v2 wrapper that launches callosum's own FastAPI/uvicorn backend as a child process and shows
its real UI in a native window — a click-to-install path for a non-technical user, with no separate
Python install required.

Originally tracked under **"Packaging & distribution (post-V1)"** (backlog #21, now closed — this
shell is built and shipping) in `.claude/docs/INCREMENT-BACKLOG.md`; the in-app auto-updater is the
remaining piece, tracked as backlog **#49**. Design background: `.claude/docs/future-tracks/
desktop-packaging-tauri.md` (the 2026-07-23 feasibility research + throwaway spike) and the
increment notes for the increment that actually built this.

**Getting an installer:** every tagged release publishes Windows/macOS/Linux installers to
[GitHub Releases](https://github.com/cliffworkman/callosum/releases/latest) — see
`FIRST-LAUNCH-NOTE.md` for the first-run trust dialogs (unsigned build, no app-store distribution
yet). `.github/workflows/desktop-shell-release.yml` is what publishes them, fired only by a pushed
version tag (see `.claude/CLAUDE.md`'s Backup & snapshot protocol §5 for the release ritual).

## How it works

Tauri doesn't run Python. This bundles a **portable CPython 3.11** (from
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)) plus this project's
real dependencies (installed via `pip`, not frozen with PyInstaller/Nuitka — that was evaluated and
rejected as too fragile for this dependency stack, see the future-tracks doc above) as a `bundle.
resources` directory, and spawns that interpreter directly with `std::process::Command`:

```
python-runtime/python.exe -m uvicorn app.backend.api.app:app --host 127.0.0.1 --port <dynamic>
```

The Rust shell (`src-tauri/src/backend.rs`) picks a free loopback port, overrides
`CALLOSUM_DB_URL`/`CALLOSUM_LIBRARY_DIR` to point at per-user app-data/documents directories (the
bundled resource directory is read-only once installed), polls `GET /health` with a splash window
shown meanwhile, then swaps the splash window for the real callosum UI once healthy. Closing the
window (or any abnormal exit) kills the whole backend process tree — a Windows Job Object on
Windows, a process-group signal on Unix — so nothing orphans and holds the SQLite file locked.

## Building it yourself

```
# 1. Build the frontend the shell will serve
npm install && python tools/build_frontend.py

# 2. Stage the real source tree into resources/callosum-src/
python app/desktop-shell/packaging/stage_source.py

# 3. Build the portable Python runtime into resources/python-runtime/ (Windows)
pwsh app/desktop-shell/packaging/build_python_windows.ps1
# ...or on macOS (CI only — see .github/workflows/desktop-shell-macos.yml):
# bash app/desktop-shell/packaging/build_python_macos.sh

# 4. Build the installer
cd app/desktop-shell
npm install
npx tauri build
```

`packaging/smoke_test_backend.py` spawns the bundled interpreter standalone (no Tauri) and confirms
`/health` — run it after step 3 to catch a broken dependency bundle before touching Rust at all.

## Developer-only managed local AI POC

The shell can own a developer-supplied `llama-server` and already-downloaded GGUF for the supplementary
synthesis Overview only. This is qualification infrastructure, not a shipped Automatic AI feature: no runtime or
model is bundled, no Settings control exists, and normal users cannot enable it accidentally.

```powershell
$env:CALLOSUM_LOCAL_AI_ENABLED = "1"
$env:CALLOSUM_LOCAL_AI_RUNTIME = "C:\path\to\llama-server.exe"
$env:CALLOSUM_LOCAL_AI_MODEL = "C:\path\to\model.gguf"
# Optional test backend controls (not routing policy):
$env:CALLOSUM_LOCAL_AI_GPU_LAYERS = "0"
$env:CALLOSUM_LOCAL_AI_THREADS = "4"
```

Tauri canonicalizes both paths, binds the child to literal `127.0.0.1` on an ephemeral port, provisions a
per-launch bearer token in the app's private data directory, suppresses runtime content logs, and publishes a
private target descriptor to Python only after `/health`, the opaque model alias, and an authenticated one-token
inference probe succeed. Python accepts only that strict descriptor with `DEVELOPER_TEST_ONLY` qualification and
routes Overview through the existing Chat Completions transport and parser. A missing, stale, or failed local
target disables that Overview attempt; it never falls through to a cloud provider. Tauri removes descriptor/token
eligibility before bounded shutdown and owns all graceful/forced process-tree cleanup.

The optional GPU-layer value is a developer experiment, not a recommendation or hardware threshold. The tested
model is not qualified for scientific/product use.

## Known, deliberate limits (see the increment notes for the full writeup)

- **No code signing or notarization on either platform.** `FIRST-LAUNCH-NOTE.md` is the mitigation —
  a plain-language explanation of the SmartScreen/Gatekeeper click-through, linked from the release
  and the download page.
- **macOS is arm64-only.** An Intel Mac cannot run this build at all (not just friction — it won't
  launch). This was a deliberate bet given the 2-day build window; revisit if it matters.
- **The macOS build is never manually verified before shipping** — there's no Mac hardware available
  in this project's dev environment. CI's blocking `smoke_test_backend.py` step proves the real
  dependency stack imports and serves on real macOS arm64 hardware; it does not prove Gatekeeper lets
  the app open or that the webview loads.
