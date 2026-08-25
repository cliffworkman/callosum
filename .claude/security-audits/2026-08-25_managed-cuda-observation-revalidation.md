# Security audit — managed CUDA observation revalidation

**Date:** 2026-08-25
**Scope:** developer-only llama.cpp b10516 execution observation, self-contained runtime-bundle launch, extended
synthesis Overview qualification search, and unchanged sidecar privacy/egress controls

## Findings

| Area | Finding |
|---|---|
| Version-qualified observation | The rebuilt b10516 CUDA package emits `llama_prepare_model_devices: using device CUDA<N>` instead of the previously qualified `ggml_cuda_init` form. Only the two observed b10516 forms are admitted, and only when version output proves build 10516 / commit b95502ba9. Unknown versions, loose CUDA text, absent numeric device evidence, and malformed prefixes remain unverified. |
| Byte-safe observation | Startup metadata can contain non-UTF-8 bytes. Stream draining now decodes each bounded line lossily only for narrow evidence matching, rather than aborting observation. Raw runtime output is still discarded and never persisted. |
| Runtime-bundle launch | The managed server and its `--version` identity probe now execute with the canonical runtime bundle root as working directory. This permits adjacent allowlisted Linux shared libraries without adding search paths, shell interpolation, or traversal. Non-zero version-probe exit fails closed. |
| Requested/observed equality | Every live cohort run published a target only after exact requested/observed CUDA layer equality (17–41 layers depending on artifact). A controlled requested-CPU/observed-CUDA mismatch remained unpublished and cleaned up. |
| Authentication and loopback | Literal `127.0.0.1`, random private bearer file, authenticated model/inference readiness, no proxy inheritance, opaque alias, disabled web UI, and direct argv remain unchanged. |
| Privacy/logging | The observer retains only backend and numeric layer counts. Prompts, outputs, tokens, filesystem paths, and runtime trace text are not logged or added to descriptors/receipts. Qualification fixtures are synthetic. |
| Egress/fallback | The developer target remains Overview-only and `DEVELOPER_TEST_ONLY`; no local failure selects a cloud provider. The qualification harness uses the existing provider transport only after managed publication. |

## Residual boundaries

- The startup evidence remains a version-qualified text contract because b10516 exposes no machine-readable actual
  offload count. Any future trace/version must be separately qualified and otherwise fails closed.
- Bundle-root working-directory behavior assumes execution libraries are canonical direct children already covered by
  the hardened manifest boundary. It does not add arbitrary recursive or environment-based library search.
- The seven research artifacts all failed the frozen mechanical assay. No model, runtime/model pair, or Automatic AI
  capability became production-qualified.

## Result

**Security Audit: PASS.** Trustworthy CUDA observation was restored narrowly for the pinned build; mismatch,
loopback, authentication, output-discard, process cleanup, and no-cloud-fallback invariants remain intact.
