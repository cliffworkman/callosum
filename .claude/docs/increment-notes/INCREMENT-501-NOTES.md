# Increment 501 — Automatic AI Phase 4.1 extended model search

## Implemented

- Revalidated CUDA observation for pinned llama.cpp b10516 / commit b95502ba9 without accepting arbitrary future
  trace text. Observation is version-qualified, byte-safe, bounded, non-persistent, and fail-closed.
- Launches the server and version probe from the canonical runtime bundle root so a self-contained Linux package can
  resolve its adjacent, manifest-covered shared libraries without ambient build-tree paths.
- Froze a separate seven-artifact Phase 4.1 cohort while preserving the original Phase 4 battery aggregate exactly.
  Added a thin developer-only runner adapter and privacy-safe aggregate receipt index; raw outputs and weights remain
  outside git.

## Key technical detail

The scientific contract stayed byte-for-byte frozen at aggregate
`5fbba390a2fcfbb51121763612fcf8f14cbc8a8fb4462313da160edbb179c707`. The separate search aggregate is
`89f4c3def6ebd6f13eb6edeb16cffb975df332e1287f3574f626a8f20810c5d6`. Every target proved exact CUDA
requested/observed equality before the unchanged production Overview prompt, `complete()`, parser, and reference
filter ran.

All seven exact artifacts failed frozen Stage 1 reliability: P01 missed sentence adherence (20/24); P02, P03, and
P05 failed JSON/reference mechanics (P03/P05 also exhausted the output cap); P04 and P06 had five structural-
reference failures each; P07 returned empty arrays. No Stage 2 candidate run, semantic candidate packet, human
adjudication, or challenge-holdout access occurred. The decision remains **EXTEND MODEL SEARCH**.

## Manual verification

On Juno, use the exact pinned runtime bundle and a privacy-safe GGUF fixture. Run the ignored managed-live test with
explicit CUDA layers and verify the emitted privacy-safe identity has equal requested/observed values. Then run
`live_runtime_execution_mismatch_is_not_published` while deliberately expecting CPU; it must reject publication,
remove descriptor/token, terminate the runtime, and leave no orphan.

## Validation

- Focused managed-runtime Rust tests: **21 passed, 3 developer-live tests ignored**.
- Focused qualification/Overview/egress/status Python set: **85 passed**.
- Real Juno qualification executions: **7 × 24 outputs**, all exact CUDA matches and clean shutdown; controlled live
  mismatch rejected with no orphan.
- Full Python suite: **2491 passed, 3 skipped** in **1068.32 s (17:48)** with `pytest -n auto -q`.
- Full Rust rerun: **25 passed, 3 developer-live tests ignored**. One readiness-probe test failed once in the first
  all-target run, then passed five valid isolated repetitions and the complete rerun; it is retained as a flaky/
  order-sensitive observation rather than hidden.
- Cargo check, strict all-target Clippy, targeted rustfmt, repository Ruff, configured Bandit, Tach, the **563-file**
  line-budget gate, scoped pre-commit hooks, secret/private-path scan, and `git diff --check` passed.

## Boundary

No user-facing Automatic AI, production routing, prompt/parser/reference semantics, model download/catalog,
hardware policy, LAN target, cloud fallback, cache, provider default, or scientific qualification was added.
