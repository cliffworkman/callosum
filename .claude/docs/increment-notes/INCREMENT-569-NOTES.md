# Increment 569 Notes — Local AI in the dev browser build (backlog #72)

## Why

`_preview_descriptor_path()` requires `CALLOSUM_APP_DATA_DIR`, and the only thing that ever sets it is the
Tauri shell (`backend.rs:202`). So a source-checkout backend — `run_dev.py` or a bare `uvicorn` — could
never reach Local AI: every generative feature failed with `app_data_missing`. Inc 568 made that failure
honest; it did not make it go away. Testing any Local-AI-backed change therefore meant a full Tauri
rebuild, which Cliff called "totally unfeasible for continued development."

Cliff's explicit call for this increment: the dev server must work **with the desktop app closed**.

## Implemented

- **`tools/run_local_ai.py`** (new, developer-only) — verifies the already-installed artifacts, starts
  llama-server on literal loopback, waits for authenticated readiness, verifies observed execution, and
  publishes a descriptor into a **dev** app-data dir.
- **`tools/run_dev.py --local-ai`** — supervises it as a third child and sets `CALLOSUM_APP_DATA_DIR` for
  both servers. Off by default; without the flag nothing changes.
- **`app/frontend/js/35b_providers.jsx`** — the Settings card no longer claims "Unsupported architecture"
  in a browser session (see below).
- **`tests/test_run_local_ai.py`** — 11 tests over the decidable logic.

## Key technical detail: zero production code changed

The whole design turns on one fact — `load_preview_target()` reads `CALLOSUM_APP_DATA_DIR` and nothing
else. Point it at a dev-owned directory and the app's existing resolution and validation path works
unmodified and still fail-closed. Nothing in `app/` or `integrations/` knows this tool exists; it cannot
widen what the backend accepts, only offer a candidate descriptor the validator may reject.

Everything a valid descriptor needs is already on disk. `managed-local-ai-install/install.json` carries
`model_sha256`, `runtime_launcher_sha256`, and `runtime_bundle_manifest_sha256`; `runtime_version` is
length-bounded but not value-checked, so the launcher records what the binary actually reports; and
`chat_template_digest` is read back from the server's own `/props` during readiness.

**The published descriptor's `target_id`, all three artifact digests, and `chat_template_digest` came out
byte-identical to the packaged app's own descriptor** — faithful reproduction, not approximation.

## Boundary: the one deliberate exception to "Tauri alone owns the lifecycle"

CLAUDE.md states that invariant (incs 498/547) for the **shipped product** — what an end user's installed
app does. This is a developer tool in `tools/`, outside production paths, following inc 542's
developer-only-executor precedent. It never downloads; it re-hashes the launcher and model against
`install.json` before exec; it writes only into a separate dev dir and refuses `--dev-dir` equal to the
packaged app's. CLAUDE.md's Local-AI bullet now records the exception explicitly, so the next reader does
not take "Tauri alone" literally and be wrong.

## Three defects found by running it, none by inspection

1. **The bearer token was in argv.** My first draft passed `--api-key <token>`, which is readable in the
   process table by every other process on the machine. Reading the Rust this tool claims to mirror showed
   it uses `--api-key-file <path>`, deliberately. Fixed before any run. Reading the thing you claim to
   copy is what caught this.
2. **A stale descriptor survived abnormal termination.** Observed by actually killing the launcher: the
   descriptor remained, pointing at a dead port — so `/settings` would report Local AI available and every
   request would fail. That is exactly the silent-lie class inc 568 removed. A Windows `CTRL_BREAK_EVENT`
   also terminated the interpreter outright (exit `0xC000013A`) without running `finally`. Fixed in three
   layers: `SIGTERM`/`SIGBREAK` handlers that unwind, `run_dev.py` clearing the pair on entry and exit, and
   the launcher removing any stale pair at start. A true hard kill still cannot be intercepted in-process;
   that residual window is disclosed rather than papered over.
3. **The GPU check would have blocked every developer with an NVIDIA card.** A first draft refused to start
   on any CUDA/ROCm/Vulkan/SYCL device-discovery line. A test written against the intended behaviour showed
   it both missed the real format (`ggml_cuda_init: found 1 CUDA devices`) and was wrong in principle: a GPU
   being *present* is not a GPU being *used*, and `-ngl 0` with zero offloaded layers is genuine CPU
   execution. Now the offload count is the sole signal, matching `observation.rs`'s own rule.

Execution is **observed, never assumed**: the launcher parses llama.cpp's `offloaded N/M layers to GPU`
trace line (which is why `--log-verbosity 4` is mandatory) and **fails closed when it is absent** rather
than defaulting to "cpu" — the validator requires `requested == observed`, and writing that pair unlooked
would assert something never seen.

## Also fixed: Settings claimed an architecture verdict it never checked

`refreshLocalAi` hard-coded `state: "unsupported"` in any non-Tauri session, which `localAiStatusLabel`
renders as **"Unsupported architecture"** — the same string a genuine Intel-Mac CPU failure produces, and
flatly contradicted by its own detail text ("available in the installed desktop app"). With dev Local AI
working it became an outright falsehood. The browser case now has its own `desktop_required` state, and the
card prefers the backend's own verdict — inc 568's `generation_provider_available` /
`generation_provider_detail` already report the truth with no Tauri bridge. `unsupported` keeps its
original meaning for the real architecture case (incs 566/567).

## Manual verification script (all run for real, Windows)

1. `python tools/run_local_ai.py` → descriptor published in ~12 s.
2. `load_preview_target()` under the dev dir → **accepted**; digests identical to the packaged descriptor.
3. `complete(resolve_llm_config(app), "Name one brain structure involved in memory…")` with no Tauri
   present → **`'Hippocampus'` in 1.7 s**; `/settings` reported `generation_provider_available: true`,
   `generation_provider_detail: null`.
4. Corrupted-artifact run → refused before launch (`runtime launcher digest mismatch`), no process spawned,
   no dev directory created.
5. Ctrl-C teardown → exit 0, descriptor and token removed, zero orphan llama-server.
6. Coexistence → two independent servers/ports alongside the running packaged app, whose own descriptor was
   untouched.

The process lifecycle is proven by these real runs rather than faked in pytest — the LibreOffice-adapter
posture. **Platform honesty: Windows only.** The artifact layout is resolved dynamically and macOS/Linux
paths are written, but they are UNVERIFIED; do not read this as parity.

## Pytest

`tests/test_run_local_ai.py` — **11 passed**. The load-bearing one asserts the launcher's descriptor is
accepted by the unmodified production validator, so a future drift between writer and validator fails here
instead of costing a developer an afternoon. Full suite result recorded in `.claude/changes.md`.

Security audit: `.claude/security-audits/2026-09-03_dev-local-ai-launcher.md` — **PASS**.
