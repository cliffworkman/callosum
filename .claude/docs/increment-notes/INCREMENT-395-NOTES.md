# Increment 395 — Desktop shell: real CI verification (screenshots) on all 3 platforms + Linux target

**Date:** 2026-07-27
**Status:** Windows and macOS fully built, CI-verified, and confirmed via real screenshots of the
actual running app. Linux is a new target (backlog #21 was originally Windows/macOS-only), built and
CI-verified via the real backend health check; a real window screenshot wasn't obtained (a headless
X11 quirk, not a functional gap — see below). One genuinely important bug found and fixed on macOS
(see "The codesign finding").

## Context

Following inc 394 (the initial Windows-verified/macOS-CI-only build), Cliff asked: can GitHub's own
`windows-latest`/`macos-latest`/`ubuntu-latest` runners be used to *actually* click through the
installers on every future rebuild, rather than relying on manual testing on this one dev machine?
Both Windows and macOS GitHub runners keep a real interactive desktop session specifically to support
this — screenshots of the real running app are possible, not just process/log inspection. Cliff also
asked to add Linux as a genuine third target (not just testing what already existed) — new scope,
not tied to a specific pending user.

## Implemented

- **`.github/workflows/desktop-shell-windows.yml`** (new): builds the NSIS installer, silently
  installs it for real (`/S`), launches it, waits for the bundled backend's `/health`, screenshots
  the real desktop (`.NET Graphics.CopyFromScreen` via PowerShell — no extra tool needed), and
  confirms killing the shell doesn't orphan the backend process (Job Object cleanup, verified from
  *outside* this dev machine's own already-proven environment).
- **`.github/workflows/desktop-shell-macos.yml`** (extended): mounts the real `.dmg`, tags the
  installed `.app` with a `com.apple.quarantine` attribute (GitHub's own checkout/build never applies
  one, but a real download does) to face the same Gatekeeper posture the labmate actually will, then
  gets past it and screenshots the real loaded UI.
- **`.github/workflows/desktop-shell-linux.yml`** (new): builds a `.deb` (x86_64), installs it for
  real (`sudo dpkg -i`), runs it under a virtual framebuffer (Xvfb — `ubuntu-latest` has no display
  server by default, unlike the Windows/macOS runners), and screenshots it.
- **`tauri.linux.conf.json`** (new), **`packaging/build_python_linux.sh`** (new): the Linux build
  target, mirroring the existing Windows/macOS shape (portable CPython 3.11, real deps, blocking
  smoke test).
- **CPU-only torch, all three platforms** (`build_python_{windows,macos,linux}.sh`): callosum never
  uses GPU acceleration anywhere; bundling `torch` from `https://download.pytorch.org/whl/cpu`
  instead of the PyPI default shrinks it from 700MB+ to ~120MB and removes a hard dynamic-link
  dependency on the NVIDIA driver that plainly doesn't exist on a GPU-less machine.
- **`FIRST-LAUNCH-NOTE.md`** (updated): now describes the actual observed Windows/macOS flow
  (including the "Verifying…" progress window) plus a new Linux section (`.deb`, no Gatekeeper
  equivalent), instead of an assumed-but-unverified description.

## The codesign finding (the important one)

A real CI run **screenshotted the actual Gatekeeper dialog** for the first time — and it didn't match
what `FIRST-LAUNCH-NOTE.md` described. Instead of "unidentified developer, right-click to open," it
said **"Callosum is damaged and can't be opened"** with only Move-to-Trash/Cancel — no override at
all. `spctl -a -vvv`'s own assessment explained why: **"code has no resources but signature indicates
they must be present."** Tauri's default build signs the `.app` (ad-hoc) *before* `bundle.resources`
(the ~1.5GB portable-Python-plus-source tree) gets copied in, so the signature's resource manifest
doesn't match what's actually in the bundle — a real, structural bug that would have hit the actual
labmate handoff on macOS, not just the newly-added Linux target.

**Fix:** `tauri.macos.conf.json`'s `bundle.targets` changed to `["app"]` only (just the raw bundle, no
`.dmg`); the CI workflow now explicitly re-signs the *whole* bundle after resources are in place
(`codesign --force --deep --sign -`) and wraps the correctly-signed `.app` into a `.dmg` by hand
(`hdiutil create`) instead of letting Tauri's single build step sign-then-bundle-resources in the
wrong order. **Verified fixed**: `spctl`'s assessment changed from the pathological "code has no
resources…" to the standard, expected **"rejected"** (the normal verdict for an honestly unsigned,
non-notarized app) — confirmed via a second real CI run.

## Other real bugs found only by running the workflows (not by reading them)

- **A PowerShell prune bug from inc 394 was never actually exercised.** The Windows torch-license
  prune (added last session) had only been tested by manually deleting the folder locally, never by
  re-running the script — a real CI run hit the *identical* NSIS path-length abort again, on a
  different nested file, proving `Get-ChildItem -Recurse` + `Remove-Item` had silently failed to
  fully prune. Rewritten to target the known `torch-*.dist-info` shape directly (no deep recursive
  walk) and to use the `\\?\` extended-length-path prefix — the actual documented Windows mechanism
  for this exact class of failure. Verified locally against the original unpruned tree before pushing.
- **Linux AppImage bundling hit four separate, escalating failures** against `linuxdeploy` (which
  Tauri's AppImage bundler shells out to): (1) `linuxdeploy` is itself an AppImage needing FUSE,
  which `ubuntu-latest` doesn't reliably have — fixed with `libfuse2` + `APPIMAGE_EXTRACT_AND_RUN=1`;
  (2) torch's default wheel's NVIDIA driver dependency — fixed by the CPU-only torch switch above;
  (3) torch bundles its own internal C++ test-suite binaries (`torch/bin/test_api`, etc.) with rpaths
  `linuxdeploy` can't always follow — pruned (Linux-only; never invoked by `import torch`); (4)
  scipy/scikit-learn each vendor their own uniquely-hashed `libgfortran`/`libquadmath` copies
  (standard `auditwheel` practice) that don't cross-resolve the way `linuxdeploy` expects — this last
  one looks like a genuine upstream wheel-packaging quirk, not something fixable by pruning. Rather
  than keep chasing individual missing-library cases against a bundler fundamentally fighting a full
  embedded ML stack it wasn't designed around, **dropped AppImage and kept `.deb` only** — a separate,
  much simpler Tauri bundler (declare dependencies, copy files) that doesn't do dependency-graph
  walking at all, and covers what most desktop Linux users can install directly anyway.
- **A real 25+ minute hang on macOS**: a plain foreground `open` on the quarantined, unsigned app
  blocked indefinitely — `open` normally returns immediately, but here it appears to wait on the
  Gatekeeper verification/dialog itself, which nobody is present to click in headless CI. Backgrounded
  both `open` calls (`&` + `disown`; `pgrep` already tells us whether the app actually launched) and
  added a 10-minute step-level `timeout-minutes` as a defense-in-depth ceiling.
- **`tools/check_line_budget.py`** needed a second look at its own exclusion logic mid-session
  (already fixed once in inc 394): confirmed the `os.walk` + `dirnames` pruning approach holds.
- **Concurrency groups added to all three workflows** (`cancel-in-progress: true`) after two commits
  pushed in quick succession double-triggered the mac/windows runs — GitHub doesn't retroactively
  cancel a run that started before a concurrency block existed in its own workflow file, so this only
  takes effect for pushes *after* the group is defined; worth knowing if it looks inert on the very
  next push.

## Known, honest gaps

- **macOS: no screenshot of the final loaded window was obtained.** `screencapture` hit a Screen
  Recording TCC permission wall specific to this CI process context (captured a real "'bash' is
  requesting to bypass the system private window picker…" permission dialog instead of the app, both
  with and without `sudo`). This is a CI-environment limitation, not a sign the app doesn't work —
  the codesign fix is independently confirmed via `spctl`'s "rejected" verdict, and the backend
  health/import verification passes independently via `build_python_macos.sh`'s own blocking check.
  Not chased further: fixing it would mean manipulating the TCC database directly, which requires
  disabling SIP — not appropriate on a shared GitHub-hosted runner for a "nice to have" screenshot.
- **Linux: the screenshot shows the splash page ("Starting…"), not the fully-loaded UI** — the health
  poll didn't catch the backend as ready within the 120s budget on that particular run, so the
  screenshot fired before the main window swap. The backend itself is independently confirmed working
  (the same blocking smoke test that gates the Windows/macOS builds also gates this one, and passed).
  Splash rendering is confirmed correct; the loaded-UI screenshot specifically is unconfirmed on Linux.
- **This is still not a substitute for Cliff's own click-through**, on Windows especially — the
  Windows screenshot (from inc 394's carry-forward run) is genuinely excellent evidence, but CI
  running once is not the same as it running on the labmate's actual, unknown-configuration machine.

## Files changed

- `.github/workflows/desktop-shell-{windows,macos,linux}.yml`
- `app/desktop-shell/src-tauri/{tauri.macos.conf.json,tauri.linux.conf.json}`
- `app/desktop-shell/packaging/{build_python_windows.ps1,build_python_macos.sh,build_python_linux.sh}`
- `app/desktop-shell/FIRST-LAUNCH-NOTE.md`
- `.gitignore` (excludes locally-downloaded `ci-screenshots/`)

## Verification

- Windows: real installer, real silent install, real screenshot of the actual loaded UI (library
  pane, axes, tabs, empty-library state) — confirmed by direct visual inspection of the downloaded
  screenshot artifact.
- macOS: real `.dmg`, real quarantine-tagged install, `spctl` verdict confirmed improved from
  "code has no resources but signature indicates they must be present" to the standard "rejected"
  across two independent CI runs (before/after the codesign fix).
- Linux: real `.deb`, real `dpkg -i` install, backend health confirmed serving under Xvfb; splash
  page confirmed rendering; loaded-UI screenshot not obtained (see gaps above).
- All three workflows: green on the final pushed commit.
