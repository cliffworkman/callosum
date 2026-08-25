# Increment 499 — managed local runtime identity hardening

## Why

The Phase 3 backend characterization exposed three control-plane defects in the developer-only managed llama-server
POC: a 1 MiB stack hash buffer overflowed a normal Windows process owner; requesting zero GPU layers omitted the
argument and let llama.cpp auto-offload while the descriptor claimed CPU; and Windows CPU/CUDA packages could share
the launcher bytes while differing in their execution DLLs. Scientific model qualification remains blocked until
the runtime can prove what actually ran.

## Implemented invariants

- File identity uses streaming SHA-256 with a 64 KiB heap buffer. It never loads a runtime binary/library wholesale
  and never relies on a larger thread stack.
- The owner always passes `--n-gpu-layers <requested>`, including zero. The developer must also declare the supplied
  package as `cpu` or `cuda`; a CPU package cannot request GPU layers.
- Requested execution (`backend`, `gpu_layers`) and observed execution are distinct immutable descriptor records.
  The requested backend derives from the exact layer request; the observed backend/layer count derives from bounded
  llama.cpp startup evidence. Process/health/alias/authenticated-props/authenticated-inference readiness remains
  necessary but is no longer sufficient: missing or mismatched execution evidence fails closed, shuts down the
  runtime, and publishes neither descriptor nor credential.
- llama.cpp b10516 does not expose the actual offloaded layer count through its machine-readable `/props` response.
  The owner therefore captures the narrow upstream startup line `offloaded X/Y layers to GPU` plus the CUDA backend
  marker at trace verbosity. It retains only numeric execution evidence and discards all other stream content as it
  is read. Prompt/output/token/model content is never written to a Callosum log, descriptor, terminal, or file.
- Runtime identity is a versioned canonical manifest of the launcher plus adjacent allowlisted execution libraries:
  all DLLs/dylibs and only llama.cpp `libggml*`, `libllama*`, or `libmtmd*` shared objects on Unix. Entries are direct
  children only and contain sorted relative path, byte size, and SHA-256. Canonicalized entries must remain under the
  runtime root; absolute paths, models, caches, logs, nested directories, and symlink escapes are excluded/rejected.
- Python independently validates descriptor schema 2, bundle digest, declared backend, execution record shape, and
  requested/observed equality. Existing strict loopback, private bearer, no-proxy, developer-only qualification,
  Overview-only routing, and no-cloud-fallback gates remain unchanged.

## Operational evidence

- A standalone Windows owner using the exact production hash helper completed a full runtime-bundle identity pass on
  a normal default stack. A 512 KiB-stack unit test also hashes an 8 MiB file and matches the ordinary-thread digest.
- Official llama.cpp b10516 (`b95502ba9`) Windows CPU and CUDA 12.4 bundles still had the same launcher SHA-256
  `5a3cbd5613c45ef2d53d3afc6734fd9e67229c0066c2415626ddc7c18901d36c`, but canonical bundle digests differed:
  CPU `7748201a13dd4e2269a97a8144aa02fc5a0325e10bb777518241ce95e721366c`; CUDA
  `76ac3bb669d3d590f5e0b334005efa619335f0e0b50d0bc3da9b5f7dff0c155f`.
- Windows Machine A (GTX 1050 Max-Q 2 GB) and Machine B (GTX 1650 Max-Q 4 GB) each passed explicit 0/8/25-layer
  managed launches. Requested and observed execution matched, an authenticated production Overview prompt/parser
  smoke succeeded, bounded shutdown completed, and no llama-server orphan remained.
- A controlled Windows CUDA launch with 8 actual layers but an expected CPU/zero contract was rejected with
  `ExecutionMismatch`; the owner removed private eligibility and terminated the process without cloud egress.
- Debian/Juno (RTX 3050 8 GB) used a CUDA-enabled build of the same b10516 commit and the same model digest. Explicit
  0/8/25-layer launches observed CPU0/CUDA8/CUDA25 exactly; the production Overview prompt/parser smoke passed,
  bounded Unix process-group shutdown left no orphan, and the bundle manifest digest was
  `3203e4bd16df3dd097be0dccb86bbf5df072eee4b02c7e840eec888cddb0273b`.

## Boundaries

This increment does not qualify the 0.5B test instrument, select CPU/GPU/offload defaults, add hardware profiling,
route production work, cache Overview, download artifacts, expose UI, add LAN operation, or permit cloud fallback.
The startup-line observation is intentionally specific to the tested llama.cpp family/version and must itself be
part of future runtime qualification identity. A future runtime whose execution cannot be proven must remain
ineligible rather than silently reusing requested intent.

## Verification

- Focused Python managed-local tests: **17 passed**.
- Affected managed-local, Overview lifecycle, provider/runtime, egress, status/timing, and frontend suites:
  **111 passed**.
- Full root suite: **2478 passed, 3 skipped** in **1102.39 s (18:22)** with `pytest -n auto -q`.
- Full Rust all-target suite: **22 passed, 3 developer-live tests ignored by default**; Cargo check and all-target
  Clippy with warnings denied passed. All four touched Rust files pass rustfmt; repository-wide rustfmt still reports
  pre-existing drift in three untouched desktop files, which this increment deliberately did not rewrite.
- Full-repository Ruff format/check, Bandit, Tach, the **563-file** line-budget gate, and `git diff --check` passed.
- The live Windows default-stack hashing regression, CPU/CUDA package identity check, controlled execution mismatch,
  and three-machine explicit 0/8/25 smoke matrix passed. Temporary runtimes, models, harnesses, and remote smoke
  directories were removed; no downloaded upstream binary/model is committed.
