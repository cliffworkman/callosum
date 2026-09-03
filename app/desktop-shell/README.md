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

Tauri doesn't run Python. Callosum manages a **portable CPython 3.11** (from
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)) plus the exact
dependency set exported from `uv.lock`, then spawns that interpreter directly with
`std::process::Command`:

```
<app-local-data>/python-runtimes/<runtime-id>/python.exe -m uvicorn app.backend.api.app:app ...
```

The Python environment is not a Tauri bundle resource. It is an independently published immutable
artifact keyed by OS, CPU architecture, CPython build, dependency lock, packaging schema, and build
recipe—never by Callosum's app version. On first use, `src-tauri/src/python_runtime.rs` downloads a
Minisign-authenticated manifest and exact archive, enforces size/path bounds, verifies archive and
canonical extracted-tree SHA-256 identities, smoke-tests key imports, and atomically promotes the
staging directory under Tauri's per-user `app_local_data_dir()`. Later app updates continue to ship
the shell, frontend, and `callosum-src`, while reusing the same runtime ID without reinstalling it.
Old IDs are retained as known-good rollback material rather than incrementally changed with pip.

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

# 3. Confirm this platform's immutable runtime release already exists. Maintainers build/publish a
# new runtime only when package_python_runtime.py derives a new ID; see
# .github/workflows/desktop-python-runtime.yml.
python app/desktop-shell/packaging/package_python_runtime.py verify

# 4. Build the (runtime-free) installer
cd app/desktop-shell
npm install
npx tauri build
```

`packaging/build_python_{windows,macos,linux}.*` plus `package_python_runtime.py` are CI artifact
factory inputs, not ordinary app-build steps. The factory verifies the pinned base CPython archive,
installs locked dependencies, runs `smoke_test_backend.py`, packages deterministically, and signs the
manifest with the same Minisign trust root used by the Tauri updater.

Windows upgrades from the former bundled-runtime layout retain that legacy resource long enough for
the new shell to reuse it only when its complete tree matches the signed manifest. macOS app
replacement and Debian package replacement cannot reliably preserve an old app resource, so their
first persistent-runtime build performs one verified download. On Debian/Ubuntu, the `.deb` itself is
still upgraded through the package/release-page flow; the runtime lives under the user's XDG local
data directory, not root-owned `/usr/lib`, and survives `dpkg` replacement.

## Local AI Preview

On Windows x64 and native Apple Silicon or Intel macOS builds, **Settings → AI features → Local AI → Set up Local AI** installs Callosum's one supported managed
preview configuration: the publisher-owned Qwen2.5-1.5B-Instruct Q4_K_M GGUF and an official pinned llama.cpp CPU
runtime. Callosum downloads both from immutable sources, verifies their exact byte sizes and SHA-256 digests, and
promotes only complete verified files. No API key, provider account, terminal, endpoint, Ollama installation, or
manual model download is required. Each macOS architecture receives a native, separately verified app, Python
runtime, llama.cpp bundle, and updater artifact; Linux setup still reports its unsupported architecture explicitly.

After setup, Local AI is a first-class generative provider. Compatible features resolve through the same shared
provider seam as Gemini/OpenAI/Anthropic, but execute through the managed loopback target. A local timeout, crash,
parse failure, or unavailable model never causes cloud fallback; users must explicitly choose another provider.
The former advanced user-managed **Local endpoint** remains separate and unchanged.

Tauri owns the llama-server process for the application lifetime. It binds to literal `127.0.0.1` on an ephemeral
port, provisions a random bearer token outside argv/frontend, suppresses prompt/output logging, and publishes a
private descriptor only after authenticated model/inference readiness and requested-versus-observed CPU/offload
matching. Runtime identity covers a deterministic launcher/shared-library manifest. Shutdown removes transient
descriptor/token eligibility before graceful or forced process-tree cleanup; the verified installation remains for
restart reuse and can be repaired by running setup again.

Evidence state is separate from availability. Synthesis Overview is **Evaluated** for this exact model under the
completed Callosum study; other compatible generative features are **Testing** while task-specific comparative
evaluation continues. Neither label means scientifically qualified or error-free. AI output remains a research aid:
review important claims against Callosum's cited passages, verified claims, and other available provenance.

The older developer-supplied runtime/GGUF environment variables remain only for qualification and lifecycle tests;
they are not part of the ordinary setup flow or an arbitrary-GGUF product surface. Automatic provider routing,
hardware selection, GPU recommendations, and a multi-model catalog remain out of scope for this preview.

## Known, deliberate limits (see the increment notes for the full writeup)

- **No code signing or notarization on either platform.** `FIRST-LAUNCH-NOTE.md` is the mitigation —
  a plain-language explanation of the SmartScreen/Gatekeeper click-through, linked from the release
  and the download page.
- **The macOS builds are never manually verified before shipping** — there's no Mac hardware available
  in this project's dev environment. CI's blocking native arm64 and x86_64 jobs prove each real
  dependency stack imports and serves, exercise managed Local AI, and mount/open each `.dmg`; they do
  not substitute for a human checking the complete UI on both Mac architectures.
