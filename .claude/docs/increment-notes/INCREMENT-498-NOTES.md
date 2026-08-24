# Increment 498 — developer managed local AI sidecar POC

## Implemented

- Tauri exclusively owns an explicitly enabled, developer-supplied llama-server: canonical runtime/GGUF paths,
  ephemeral literal-IPv4 loopback port, per-launch private bearer token, opaque model alias, fixed test settings,
  authenticated model/inference readiness, unexpected-exit invalidation, and bounded process-tree shutdown.
- Only after readiness does Tauri pass the private descriptor path to its Python child. The descriptor carries
  runtime/model/template/settings identity but no bearer token, runtime path, or model path.
- Python strictly validates the descriptor and credential reference, disables proxy inheritance for this local HTTP
  pool, and resolves it exclusively for supplementary synthesis Overview. Existing `complete()`, prompt, parser,
  claim-reference filtering, persistence, and failure isolation remain unchanged. A local failure never falls
  through to cloud.
- No runtime/model/download/catalog/router/hardware policy/LAN endpoint/cloud fallback/Settings UI ships. Every
  target remains `DEVELOPER_TEST_ONLY`; the test model is not qualified.

## Key technical detail

Readiness is a four-part contract: child still alive, `/health` successful, `/v1/models` contains the expected
opaque alias, and authenticated `/props` plus a one-token authenticated Chat Completions request succeed. The props
template is hashed for target identity. Tauri does not publish eligibility before all checks pass. Descriptor/token
files are removed before shutdown or after crash, so stale state cannot become an authoritative target.

Windows token and descriptor files use non-inherited ACLs granted only to the current user SID. Unix builds use
0700/0600. `--log-disable`, discarded child streams, `--offline`, no UI, direct argv, literal `127.0.0.1`, and
proxy-disabled HTTP close the POC's main content/secrets paths.

## Manual verification script

1. Download a trusted llama-server build and a small instruction GGUF outside git.
2. Set `CALLOSUM_LOCAL_AI_ENABLED=1`, `CALLOSUM_LOCAL_AI_RUNTIME`, `CALLOSUM_LOCAL_AI_MODEL`, optional bounded
   GPU/thread values, and launch the desktop shell.
3. Confirm the private target descriptor appears only after model load/inference readiness and states
   `DEVELOPER_TEST_ONLY`; confirm token text is absent.
4. Confirm `/v1/models` exposes `callosum-managed-local`, missing/wrong bearer gets 401, and authenticated Overview
   reaches the existing parser/lifecycle.
5. Kill the server during idle/Overview and confirm Callosum survives, descriptor/token disappear, Overview fails
   independently, primary synthesis stays usable, and no cloud request occurs.
6. Exit Callosum and verify no llama-server descendant remains.

## Validation receipt

- Managed Rust lifecycle/security tests: strict argv, RNG/descriptor privacy, private files, missing paths,
  authenticated readiness/malformed responses, short timeout cleanup, crash invalidation, normal shutdown, and
  forced shutdown.
- Live Windows POC: official llama.cpp b10516 (`b95502ba9`), executable SHA-256
  `5a3cbd5613c45ef2d53d3afc6734fd9e67229c0066c2415626ddc7c18901d36c`, CPU-only; public 0.5B GGUF instrument
  SHA-256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`. Existing Python Overview transport/parser
  succeeded. This is not model qualification.
- Python focused tests cover strict descriptor validation, developer gating, no-fallback resolution, secret-safe
  configuration, proxy isolation, existing parser transport, auth failure, malformed-output primary isolation, and
  target-aware timing identity.
- Final validation: root `pytest -n auto -q` **2476 passed, 3 skipped** in 22m32s; affected Python suite **122
  passed**; Rust lifecycle/security suite **13 passed, 1 developer-live test ignored by default**, and the ignored
  official-runtime test passed separately. Cargo check, strict all-target Clippy, Ruff, Bandit, Tach, line-budget,
  formatting, and diff checks passed.

## Boundaries

Windows lifecycle behavior is directly measured; Unix process-group code is compile-only in this phase. There is no
quality, hardware-routing, packaging, downloader, end-user activation, or general Automatic AI claim.
