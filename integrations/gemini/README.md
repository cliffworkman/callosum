# Gemini Integration Scope

## Purpose

Gemini should be used selectively for generation tasks that genuinely need an LLM, especially citation-oriented summarization.

## Planned Responsibilities

- Generate summaries from retrieved, bounded context.
- Optionally clean up cluster labels.
- Optionally classify borderline stance cases.
- Track prompts, model names, token usage, rate-limit failures, and response provenance.
- Cache completed outputs.

## Constraints

- Free-tier limits are volatile and must be verified before implementation.
- As of the planning baseline, Google cut Gemini free-tier daily request quotas substantially in December 2025, and stronger models moved behind billing-account requirements in 2026. Design Stage 4 around Flash or Flash-Lite class models, batching, caching, and 429 backoff.
- Free-tier data-use terms may not suit sensitive libraries.
- Gemini output must be independently verified before being shown as supported.
- Per-library or per-action data-egress settings must control whether source text can leave the machine. The default for uncleared or sensitive libraries should be no cloud LLM calls.

## First Validation

Run one bounded summary prompt over retrieved chunks and store raw output for independent verification.
