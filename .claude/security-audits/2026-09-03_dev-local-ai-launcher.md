# Security Audit: developer Local AI launcher (`tools/run_local_ai.py`)

Date: 2026-09-03
Increment: 569 (backlog #72)

## Scope

A developer-only tool that starts the managed llama.cpp runtime for a **source-checkout** backend, so
Local-AI-backed features can be exercised in a browser dev session without a Tauri rebuild (previously an
hours-long loop). It publishes a descriptor that the **unmodified** `load_preview_target()` validates.

Trigger: audit gate #3 (new file-write path) and #5 (net-new tool). No new endpoint, no new dependency,
no new external fetch.

## Why this does not weaken the shipped product

CLAUDE.md records that **Tauri alone owns the managed llama-server lifecycle** (incs 498/547). That
invariant governs what an *end user's installed app* does. This is a developer tool under `tools/`,
outside production paths — the inc-542 precedent (developer-only MariaDB executor). The boundary is
structural, not a promise:

- **Zero production code changed.** No file under `app/` or `integrations/` references this tool, and it
  is unreachable from the packaged app or any route. It only writes files the existing validator already
  inspects and is free to reject. Verified: the entire increment's `app/` diff is the Settings-label fix,
  which contains no reference to the launcher.
- **The trust decision still belongs to `managed_local.py`.** The tool cannot widen what the backend
  accepts; it can only produce a candidate descriptor. Every constraint in `_target_from_payload`
  (schema/kind/wire-format/alias/family/qualification/target-id/endpoint/execution/context/output/
  temperature/seed) still applies unchanged.

## Threat review

**Supply chain / artifact integrity.** The tool **never downloads anything** — there is no network code
except its own loopback readiness probe. It reuses only artifacts the packaged app already fetched and
verified. Before `exec`, it re-hashes the launcher binary and the `.gguf` and requires equality with
`install.json`'s `runtime_launcher_sha256` / `model_sha256`, and additionally requires the model to equal
`EXPECTED_PREVIEW_MODEL_DIGEST`. A swapped binary or model is refused rather than launched. Negative path
exercised below.

**Credential handling.** A fresh 32-byte (64 hex char) token per launch from `secrets.token_hex`. It is
passed to llama-server as `--api-key-file <path>`, **never `--api-key <token>`** — an inline token would
be readable in the process table by every other process on the machine. This matches
`managed_local_ai.rs::server_args` exactly; an earlier draft of this tool used the inline form and was
corrected before any run. The file is `0600` on POSIX (Windows inherits the user-profile ACL), lives
beside the descriptor as `auth-token` (required by `_credential_path`), is never logged, and is removed
on shutdown.

**Credential cannot reach the repository.** The default dev directory is `.local/dev-app-data/`, and
`.gitignore:1` ignores `.local/` wholesale — verified with `git check-ignore -v`, and `git status` never
lists the pair. A per-launch bearer token committed to a public repo would be the worst outcome here, so
this is checked rather than assumed.

**Network exposure.** Bound to literal `127.0.0.1` on an ephemeral port, never `0.0.0.0`/`localhost`/
`::1`. `_strict_endpoint` independently re-checks this at load time, so a descriptor naming any other host
is rejected by the backend regardless of what the tool wrote. `--no-webui` disables llama.cpp's browser
UI; `--offline` prevents any model fetch by the runtime.

**Execution-claim honesty.** `_target_from_payload` requires `requested_execution == observed_execution`,
so writing that pair unexamined would assert something never observed. The tool positively parses
llama.cpp's own trace line (`offloaded N/M layers to GPU`, which is why `--log-verbosity 4` is mandatory),
requires `N == 0`, and **fails closed when the line is absent** rather than defaulting to "cpu". Silence is
not accepted as proof of CPU execution.

A first draft also scanned for CUDA/ROCm/Vulkan/SYCL device-discovery lines and refused on any match. A
test written against that behaviour showed it was wrong in both directions: it missed the real format
(`ggml_cuda_init: found 1 CUDA devices`), and — more seriously — had it matched, it would have refused to
start on any developer machine that merely *has* a GPU, even though `-ngl 0` with zero offloaded layers is
genuine CPU execution. The offload count is now the sole signal, matching `observation.rs`'s own rule
(backend is CPU iff `gpu_layers == 0`).

**Stale-descriptor risk (found and fixed during this audit).** A descriptor outliving its llama-server
would make `/settings` report Local AI as available while every request fails — the exact silent-lie class
inc 568 removed. Observed empirically: a hard stop left `target.json` behind, and a Windows
`CTRL_BREAK_EVENT` terminated the interpreter outright (exit `0xC000013A`) without running `finally`.
Fixed with three layers: (1) `SIGTERM`/`SIGBREAK` handlers that raise `KeyboardInterrupt` so cleanup
unwinds; (2) `run_dev.py` clears the pair both before spawning and on teardown; (3) the launcher removes
any stale pair at start. A true hard kill (`TerminateProcess`/`SIGKILL`) cannot be intercepted in-process
— layer (3) is the backstop, and the residual window is disclosed in the tool's docstring.

**Path safety.** Paths come from a fixed layout plus two explicit developer-supplied flags; nothing is
request-derived. The tool refuses `--dev-dir` equal to the packaged app's data directory, so it cannot
clobber the real app's descriptor. Both may run concurrently (separate dirs, separate ephemeral ports) —
verified: two live llama-server processes, the packaged descriptor untouched.

**Subprocess safety.** Every `subprocess` call uses a fixed argv list with `shell=False`; the only
variable elements are locally-determined paths, a locally-chosen port, and our own child's PID. No
request-derived or network-derived value reaches a command line.

**Resource use.** One llama-server, one ~1 GiB model, CPU-only, `-ngl 0`, 4 threads — identical to the
packaged app's production configuration. Bounded readiness timeout (300 s) with the child's liveness
checked each poll, so a dead child fails fast rather than hanging to the deadline.

## Negative paths exercised

| Check | Result |
|---|---|
| Corrupted model byte (digest mismatch) | Refused before launch: `model digest mismatch`, no process started |
| Descriptor accepted by the real validator | `load_preview_target()` accepted; `target_id`, all three artifact digests, and `chat_template_digest` byte-identical to the packaged app's own descriptor |
| Real generation through the production seam | `complete()` returned `'Hippocampus'` in 1.7 s with no Tauri present |
| Graceful shutdown | exit 0, descriptor + token removed, zero orphan llama-server |
| Hard stop (pre-fix) | stale descriptor left behind → **fixed**, re-verified clean |
| Coexistence with the packaged app | two independent servers/ports; packaged descriptor unmodified |
| Token in process table | not present — `--api-key-file` passes a path, not the secret |

## Residual risks (accepted, disclosed)

1. **Hard kill leaves a stale descriptor** until the next start. No in-process handler can prevent
   `TerminateProcess`/`SIGKILL`; the packaged app uses a Windows Job Object, which would require a new
   dependency for a dev-only tool. Mitigated by start-time removal in both the launcher and `run_dev.py`,
   and the failure is loud at request time (inc 568), not silent.
2. **`--install-dir` is trusted to name a real installation.** A developer pointing it at an attacker-
   controlled directory with a matching `install.json` could run that binary — but the digests must agree
   with the pinned preview model, and a developer who can write that directory can already run anything.
3. **Windows-only verification.** macOS/Linux paths are written but unexercised; stated plainly rather
   than implied to work.

**Security Audit: PASS.**

Verified against the code and by live execution, not from a plan. Three defects were found and fixed
before this verdict, none by inspection alone: the inline-token argv (caught by reading the Rust the tool
claims to mirror), the stale descriptor after abnormal termination (caught by actually killing it), and
the over-broad GPU-marker refusal (caught by a test written against the intended behaviour).
