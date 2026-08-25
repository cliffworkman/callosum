# Increment 500 — synthesis Overview model qualification battery

## Why

Transport/parser success from the managed-local POC is not scientific qualification. Automatic AI needs a frozen,
task-specific assay that can reject structurally unreliable or scientifically misleading Overview configurations
before any model is exposed to users.

## Battery and invariants

- A reusable developer-only harness invokes the unchanged `overview-v1` production prompt, provider-neutral
  `complete()`, Chat Completions transport, parser, and production reference filter.
- Four calibration fixtures, 24 qualification fixtures, eight challenge fixtures, nine canned controls, a semantic
  codebook, reliability/scientific gates, stopping rules, and eight pinned artifact identities were frozen before
  model output. All content is privacy-safe synthetic evidence.
- Qualification is exact to artifact digest, quantization, chat-template digest, llama.cpp runtime/bundle,
  generation settings, and observed execution. A family/model name never inherits qualification.
- Human blinded semantic review remains the only scientific authority. Mechanical reliability failure independently
  prevents qualification, so no candidate packet or holdout is opened when every configuration fails mechanics.
- Raw outputs and model weights remain outside git. The tracked receipt index contains only digests, numeric
  aggregates, platform identity, and failure categories.

## Empirical result

- Eight candidates spanning Qwen2.5, Gemma 3, SmolLM2, Granite 3.3, and Ministral 3 were registered (0.5B–8B,
  491 MB–4.94 GB). Seven executed; Ministral 3B failed managed execution observation twice and published no target.
- Only Qwen 1.5B passed every 24-output Stage 1 gate, then failed Stage 2 with structural-reference and maximal-context
  failures. Qwen 0.5B, Gemma 1B, SmolLM2 1.7B, Granite 2B, Qwen 3B, and Granite 8B failed Stage 1 reliability.
- Qwen 0.5B was initially advanced in error after 21/24 sentence-count adherence (87.5%), below the frozen 90% gate.
  Its extra Stage 2 run is retained for audit but excluded from qualification evidence; it did not influence any
  model, gate, prompt, or stopping decision and cannot create a false acceptance.
- Granite 8B produced 24/24 usable structurally valid responses but only 12/24 met the required 2–4 sentence contract.
  Larger capacity therefore did not automatically satisfy the fixed task contract.
- No exact configuration qualified. No semantic candidate adjudication or challenge holdout was run. The correct
  outcome is **EXTEND MODEL SEARCH**, without weakening the frozen gates.

## Platform deviation

The rebuilt pinned b10516 CUDA bundle used a `CUDA0` trace marker rather than the Phase-3.5 observer's qualified
`ggml_cuda` marker. CUDA therefore failed closed as designed. All executable receipts use explicit requested and
observed CPU/zero offload on Juno. This exact CPU receipt cannot transfer to CUDA or the deleted Phase-3.5 bundle.

## Boundary

No production routing, provider behavior, prompt, parser, lifecycle, model download/manager, user setting, cache,
LAN target, cloud fallback, or scientific feature changed. A tiny pure reference-filter extraction lets the research
harness call the exact production filter without importing the full API graph. The managed target remains
`DEVELOPER_TEST_ONLY`.

## Verification

- Frozen qualification harness/control tests: **9 passed**; affected managed-local and Overview lifecycle set:
  **48 passed**.
- Full root suite: **2487 passed, 3 skipped** in **1067.19 s (17:47)** with `pytest -n auto -q`.
- Full Rust all-target suite: **22 passed, 3 developer-live tests ignored by default**; Cargo check and all-target
  Clippy with warnings denied passed; the touched Rust file passes rustfmt.
- Repository-wide Ruff format/check, configured Bandit, Tach, the **563-file** line-budget gate, changed-file
  pre-commit hooks, and `git diff --check` passed.
- Real Juno managed executions preserved strict loopback/auth, requested=observed CPU/zero offload, existing
  `complete()`/parser/filter semantics, bounded shutdown, no orphan after successful runs, and no cloud fallback.
