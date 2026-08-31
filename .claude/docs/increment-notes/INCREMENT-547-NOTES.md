# Increment 547 — managed Local AI Preview provider

**Date:** 2026-08-30
**Scope:** Windows-first productization of the previously developer-only managed llama.cpp owner as an explicit,
first-class generative provider. No automatic provider routing, silent fallback, model catalog, arbitrary GGUF,
LAN inference, benchmark redesign, or change to the frozen Phase 5A evidence.

## Product decision

**Local AI** is a provider, not an Overview exception. A user selects it explicitly, runs one setup flow, and the
shared `resolve_llm_config()` seam supplies the readiness-gated managed target to every compatible generator that
already calls `complete(config, prompt)`. Missing setup, a crashed runtime, transport/parser failure, or absent
benchmark evidence fails locally and never selects Gemini/OpenAI/Anthropic. A clean profile still defaults to
Gemini; existing manual Local endpoint and custom-provider semantics remain available unchanged.

Evidence status is descriptive metadata, never an availability gate:

- managed Qwen + synthesis Overview: **Evaluated**;
- incumbent Gemini + synthesis Overview: **Evaluated**; and
- every other currently exposed provider-backed generative capability: **Testing** unless later task-specific
  evidence establishes otherwise.

Neither status claims safety, universal qualification, or transfer to another task. Generated work remains a
research aid whose important claims should be checked against Callosum's evidence/provenance.

## Complete provider-gated feature inventory

| Feature / call site | Existing contract and safeguards | Local compatibility / delta | Status |
|---|---|---|---|
| Primary synthesis (`summaries.py` → `GeminiSummaryGenerator`) | JSON array of 4–7 sentences with 1–3 exact chunk quotes; unchanged parser, batched retrieval/NLI verification, provenance, cache, persistence | Compatible with a managed-only request-scoped llama.cpp JSON schema at the managed client boundary; cloud/manual-provider payloads and parsers unchanged | Testing |
| Supplementary Overview (`summary_overview.py`) | JSON sentences with integer verified-claim references; unchanged 256-token cap, parser, reference filtering, isolated lifecycle | Directly compatible through `complete()`; this is the Phase 5A evaluated task | Evaluated |
| Help assistant (`help.py` → `GeminiHelpAssistant`) | JSON answer + live Help section IDs; separate opt-in and defensive parser | Whole current corpus exceeds the 4,096-token target, so managed Local AI deterministically selects up to six relevant sections within 14,000 characters; cloud providers retain whole-corpus behavior | Testing |
| My Publications research summary (`my_publications.py`) | Bounded publication titles/abstracts → plain research summary | Directly compatible | Testing |
| Assisted meta-analysis extraction (`workbench.py`) | JSON field candidates with exact evidence quotes; deterministic local anchoring and human accept/reject | Directly compatible | Testing |
| Analytic flexibility, Library + WIP (`analytic_flexibility.py`, `wip_checks.py`) | Structured categories with verbatim evidence; proposal only | Directly compatible | Testing |
| Critical Review single-paper Tier 2 (`critical_review.py`) | Structured critique candidates; unchanged exact-quote grounding/verification and review lifecycle | Directly compatible | Testing |
| Critical Review set (`critical_review.py`) | Structured cross-paper critique candidates; unchanged evidence verification | Directly compatible | Testing |
| Critical Review optional triage (`critical_review_triage.py`) | Closed JSON labels/rationales over already-bounded items; never changes evidence/finding state | Directly compatible | Testing |
| Axis related-term suggestions (`axes.py`) | JSON list of 8–12 candidate terms, all deselected for user choice | Directly compatible | Testing |
| Axis cluster-label polishing (`axes.py`) | JSON label/description over representative titles/terms; deterministic local labels remain fallback | Directly compatible | Testing |
| Registration comparison optional triage (`registration_comparisons.py`) | Closed JSON annotations/rationales over bounded comparison evidence | Directly compatible | Testing |
| Funding optional triage (`funding.py`) | Closed JSON annotations/rationales; only an inspection aid | Directly compatible | Testing |
| Provider connection test (`settings.py`) | Tiny non-library prompt | Directly compatible after managed readiness; reports local repair, never a cloud-key requirement | Operational only |

No provider-backed generator was found to require tools, multimodality, streaming, or another irreducible cloud
primitive. Purpose-built embeddings, CrossEncoders/NLI, rerankers, OCR, deterministic parsers, metadata services,
and local clustering are not routed through Qwen.

## Exact managed identities

Model:

- `Qwen/Qwen2.5-1.5B-Instruct-GGUF` at revision
  `91cad51170dc346986eccefdc2dd33a9da36ead9`;
- `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1,117,320,736 bytes;
- SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e`;
- Q4_K_M, Apache-2.0; publisher-owned GGUF; and
- Phase 4 C03 chat-template identity
  `4e9918361c284a93880606d182d64da6a9fe97cdc1f5c5a78c1c8840444246fc` remains in the runtime descriptor.

Tuesday Windows runtime:

- upstream llama.cpp b10516 / commit `b95502ba9`, official CPU x64 archive;
- archive 18,506,923 bytes, SHA-256
  `fbbbc55e0eb2e1b07f9dcb9488616c98ed47d9003b90e15e7c8c7812c4307cd3`;
- launcher SHA-256 `5a3cbd5613c45ef2d53d3afc6734fd9e67229c0066c2415626ddc7c18901d36c`;
- allowlisted launcher/DLL bundle-manifest SHA-256
  `7748201a13dd4e2269a97a8144aa02fc5a0325e10bb777518241ce95e721366c`; and
- MIT; explicit CPU backend and `--n-gpu-layers 0`.

This Windows package is the same pinned upstream release/commit as C03's qualification platform but necessarily a
different platform bundle identity. Phase 5A results are not rewritten or claimed to transfer by bundle equality.

## Acquisition and lifecycle

`managed_local_ai/install.rs` is deliberately one pinned installer, not a catalog. It uses allowlisted HTTPS hosts,
bounded redirects/connect timeout/one-hour overall timeout, exact response length, 64 KiB streaming SHA-256, private
`.partial` files, fsync, safe root-only ZIP extraction, an allowlist of `llama-server.exe` plus adjacent DLLs, and
atomic promotion. Partial files are reset on retry. Setup re-hashes an installed model and runtime bundle before use;
a corrupt cache causes a fresh verified repair rather than target publication.

Tauri remains the only process owner. It launches direct argv on an ephemeral literal `127.0.0.1` port, provisions a
random bearer token through a restricted file rather than argv/frontend, disables the web UI and prompt/output logs,
requires authenticated model/inference readiness, verifies requested CPU/0 equals observed CPU/0, publishes schema-2
descriptor state only after readiness, reuses the process app-wide, invalidates on crash, and removes credential/
descriptor state during clean or forced process-tree cleanup. The verified install remains for restart reuse.

Production output cap is 2,048 tokens; Overview retains its evaluated 256-token request cap. A managed-only client
adapter supplies those caps and a bounded 600-second timeout around the existing byte-frozen provider transport;
cloud/manual-provider request semantics are unchanged. The primary synthesis adapter uses llama.cpp b10516's
request-scoped JSON schema to require exact quote-bearing citations while retaining the unchanged production prompt,
parser, and local verifier as authorities. Its managed contract is also explicit in the synthesis cache signature.

## User experience and platform boundary

Settings shows **Local AI → Set up Local AI → Local AI: Ready**, local-only privacy copy, evidence status, and an
optional technical-details disclosure. It never asks the ordinary user for Qwen/llama.cpp/quantization/GGUF/port/
endpoint/Ollama knowledge. Setup becomes the active provider only after success. Switching providers is explicit and
stops the managed process. The current automatic installer is Windows x64 only; non-Windows surfaces report that
boundary instead of improvising an unvalidated package.

## Live product smoke

On Windows 11 Pro (i7-8565U, 16 GB RAM, GTX 1050 Max-Q 2 GB), an isolated profile with every cloud key removed
reused the checksum-verified model, started authenticated CPU/0 execution, and completed the real production Overview,
primary synthesis, and Help contracts through their existing parsers. Runtime readiness plus the three requests took
786.16 seconds on this deliberately modest CPU path. The verified install occupied 1,163,519,165
bytes. Shutdown removed target/token state and left zero `llama-server` processes. A prior run identified the old
60-second Help timeout; the final managed-only 600-second policy passed without changing cloud semantics. This is
operational evidence, not a scientific qualification claim or hardware recommendation.

## Manual Tuesday checks still owed

Run QA route 35's managed Local AI item in the packaged UI: first-install progress, interrupted-download retry,
same-size corruption repair in an isolated profile, Overview/synthesis/Help, app restart, explicit provider switch,
and traffic capture proving no cloud. The headless Rust acceptance proves the backend contracts but does not substitute
for watching the final packaged UI and installer progress on the meeting machine.

## Revert

Revert the increment's exact commits. Model/runtime files live only in the app-data install root and can be removed as
user cache; no database migration or Phase 5A artifact changes require rollback.
