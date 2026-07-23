# Desktop packaging: Tauri shell — feasibility research + spike findings

**Authorship note:** unlike the `opus4.8_*`/`chatgpt5.*` files in this folder (imported deep-research passes),
this doc is a Claude Code session's own hands-on research + a throwaway build spike (2026-07-23), written to
inform backlog **#21** ("Packaging & distribution, post-V1"). Kept in `future-tracks/` because it's genuinely
longer-horizon, not because it followed that import convention.

## What #21 actually asks for
Per `INCREMENT-BACKLOG.md`: a Tauri desktop shell (`app/desktop-shell/` — currently a placeholder README), an
OS keychain for `GOOGLE_API_KEY` + future secrets, and desktop distribution + GROBID service ops (deferred —
Track C Stage-4 section-scoping, which would need GROBID, hasn't landed; SP2/Stage-3 shipped inc 271/272
without it).

**First finding: the keychain half is already mostly done.** Inc 152 shipped optional OS-keychain storage for
BYOK provider keys (`app/backend/app_settings.py`'s `_keyring()`/`_set_secret`/`_get_secret` — the `keyring`
package with a graceful file fallback, service name + usernames as constants, no request data ever reaches
it). The only gap for a *packaged desktop build* specifically: `keyring` needs to become a **hard** dependency
in that build (not optional) so a non-technical user's secrets always land in the OS vault, never the file
fallback. No new design needed here — just a packaging-time dependency decision.

## The real open question: how does the Python backend get into a Tauri app at all?
Tauri wraps a **native window + a Rust process**; callosum's actual application logic is a **Python FastAPI
process** (`uvicorn`) plus a large ML dependency stack (PyMuPDF, scikit-learn, sentence-transformers → torch).
Tauri doesn't run Python — the shell has to **launch and manage callosum's own backend as a child process**,
then point its webview at `http://127.0.0.1:<port>`. Three shapes this could take:

1. **Freeze the backend with PyInstaller/Nuitka into a single native binary**, ship it as a Tauri **sidecar**
   (Tauri's documented pattern for exactly this: an external binary the shell spawns/manages/kills alongside
   its own lifecycle). Fully self-contained for the end user — no Python install required.
   - **Risk:** freezing `sentence-transformers`/`torch`/`scikit-learn` is a known-gnarly PyInstaller case
     (hidden imports, native extension discovery, large single-file startup latency); AV false-positives on
     big single-file EXEs are a real, recurring nuisance for exactly this kind of app.
2. **Bundle a portable CPython** (e.g. `python-build-standalone`) + the app's own venv site-packages, and have
   the shell spawn *that* interpreter directly on the real source tree — sidesteps PyInstaller's import-
   discovery fragility, at the cost of shipping a full unpacked venv (no size win over option 1).
3. **Require a pre-existing Python/venv on the machine** and have the shell just spawn it — trivial to build,
   but defeats the actual point of a desktop shell (a non-technical user still has to set up Python first).

**Either self-contained option (1 or 2) inherits the same core problem: the dependency footprint is large.**
Measured on this machine: `torch` alone is **1.19 GB on disk** (CPU build) before `sentence-transformers`,
`scikit-learn`, or anything else. A "download this desktop app" story built on today's dependency set means a
multi-hundred-MB-to-multi-GB installer — worth confronting **before** committing engineering time to a
sidecar build, not after. **A real mitigation exists**: `sentence-transformers` supports an **ONNX Runtime**
backend for many models, and `onnxruntime`'s CPU wheel is dramatically smaller than full PyTorch — swapping
the embedding backend (not the model itself) could shrink the distributable by an order of magnitude. This
would be its own scoped increment, evaluated on accuracy/speed parity against the current `all-MiniLM-L6-v2`/
`bge-base-en-v1.5` setup — not something to fold silently into a packaging pass.

## What else a real shell needs (beyond "spawn a process and load a URL")
The spike below proves the trivial case (point a webview at an *already-running* backend). A real shell adds:
- **Dynamic port selection** (today's dev setup hardcodes `:8888`; a packaged app can't assume it's free).
- **Startup ordering**: the backend takes real time to import `sentence-transformers`/load models before it's
  ready to serve — the shell needs a splash/loading state and a readiness poll (`GET /health`), not an
  immediate `url` load racing the child process's own startup.
- **Clean shutdown**: kill the child process when the window closes (an orphaned uvicorn process holding the
  SQLite file locked is the exact failure mode this project's `database is locked` saga, incs 272-281, was
  built to prevent at the app layer — a shell-level orphan defeats that work).
- **Single-instance enforcement**: two copies both binding the same DB file is a real hazard; Tauri has a
  built-in single-instance plugin for this.

## Platform notes
- **Windows:** WebView2 Runtime ships with Windows 11 by default (this dev machine confirmed) — no extra
  install for most users. Rust's default `x86_64-pc-windows-msvc` target needs the MSVC linker; this machine
  already had Visual Studio 2022's C++ tools installed, which is what let the spike below build at all. A
  machine without them would need the (multi-GB) VS Build Tools installer first — a real first-run-experience
  cost for a contributor without them already.
- **macOS:** uses the system WKWebView — no extra runtime to ship.
- **Linux:** needs `webkit2gtk` (usually a system package, not bundled) — the one platform where "just
  install our app" isn't quite true without also documenting a system dependency.
- **Licensing:** Tauri is MIT/Apache-2.0 — no conflict with AGPL-3.0. It's a launcher/wrapper process, not a
  modification of callosum's own source, so this doesn't change callosum's own license obligations.

## The spike (2026-07-23)
Scaffolded a minimal Tauri v2 app (`npm create tauri-app@latest`, vanilla template) and pointed its single
window's `url` directly at `http://127.0.0.1:8888` — the actual callosum backend, already running on this
machine for other work this session. This answers exactly the narrow question asked: **can a bare Tauri shell
launch and display the real, already-running callosum UI in a native window** — not the sidecar-process
question above, which is a separate, larger increment.

**Environment friction hit and fixed, both worth remembering for next time:**
- Rust wasn't installed; added via `winget install Rustlang.Rustup` (Visual Studio 2022's C++ tools were
  already present, avoiding the much bigger Build Tools install).
- The **first build attempt failed with a Windows `MAX_PATH` linker error** (`LNK1104: cannot open file ...`)
  — Rust's build-artifact paths (`target/debug/build/<crate>-<hash>/...`) are long, and this session's default
  scratchpad directory (nested under a GUID-named session folder) pushed a real path to **263 characters**,
  over the 260-char Windows limit. Fix: build Rust/Tauri projects from a **short root path** (`C:\tauri-spike\`
  here), not deep inside a scratch/session-nested directory. Worth remembering for any future Rust work on
  Windows in this environment, not just Tauri.

**Result: confirmed working.** Cliff watched the native window open and load the real callosum library UI —
the actual running app, not a placeholder — inside a plain Tauri window frame (no browser chrome). The
narrow question is answered: a Tauri shell **can** launch and display callosum's existing frontend against
an already-running backend, on this machine, today. This says nothing yet about the sidecar/bundling question
above, which remains the real gating work for an actual shippable build.

## Recommendation
Don't commit to the sidecar-packaging build yet. The keychain half is already done; the real remaining
engineering (freezing/bundling Python + its ML stack, or shrinking that stack via ONNX first) is substantial
and worth its own scoped decision — not something to back into via "let's just wrap it in Tauri." Suggested
next slice, if/when #21 comes back up: evaluate the ONNX Runtime swap for the embedding backend on its own
merits (size + speed + accuracy), independent of packaging — it either makes the sidecar path meaningfully
more viable or it doesn't, and that's worth knowing before the packaging work itself starts.
