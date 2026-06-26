# Increment 149 — Multi-provider LLM engine (#39, part 1)

## Implemented

A provider-neutral completion seam so every AI feature can run on **Gemini, OpenAI, Anthropic, or a local
OpenAI-compatible endpoint** — hand-rolled via httpx (no new dependency). The local provider is the flagship:
summaries with **zero egress**.

- **`app/backend/llm/providers.py`** (new) — `complete(config, prompt, *, http_client=None) -> CompletionResult`
  dispatches on `config.provider`: gemini → google-genai SDK; openai/local → `POST {base}/v1/chat/completions`;
  anthropic → `POST /v1/messages`. `CompletionResult.usage_metadata` is shaped (`prompt_/candidates_/total_token_count`)
  so `log_usage` works unchanged. `requires_egress(provider)` (cloud → True, local → False) +
  `is_loopback_url(url)`. `complete()` **rejects a non-loopback `local` base_url** (`ProviderError`). All errors
  redacted (`_redact` — never the key) + httpx timeout + response-shape validation, fail-closed.
- **`integrations/gemini/generator.py`** — `GeminiConfig` renamed to **`LLMConfig`** (back-compat alias
  `GeminiConfig = LLMConfig`, ~12 import sites unaffected): new `provider` + `base_url` fields; `from_environment()`
  reads the stored provider / per-provider key / model / `local_base_url` (overlay over env); `resolved_api_key()`
  returns the active provider's key (GOOGLE_API_KEY env fallback only for gemini). `DEFAULT_MODELS` per provider.
- **The 6 generators** (`generator`, `axis_terms`, `axis_cluster_labeler`, `research_summary`, `overview`,
  `help_assistant`) — each replaced its `genai.Client().generate_content()` block with `complete(self.config, …)`
  + a provider-aware self-check (`requires_egress(provider) and not data_egress_enabled → raise`). Uniform ×6.
- **`app/backend/llm/egress.py`** — each cloud-gated `EgressGated*` wrapper gained a `provider` field; the gate is
  now `if requires_egress(self.provider) and not self.data_egress_enabled: raise`. (Help assistant keeps its own
  independent toggle.) The 6 router factories pass `provider=config.provider`.
- **`app/backend/app_settings.py`** — `set_provider` / `set_model` / `set_local_base_url` / `set_provider_key`
  (per-provider; gemini stays under the inc-146 `api_key` field) + the read path via `load_settings`.

## Principles alignment gate (rule #9) — the local-no-egress decision

**Touches:** invariant #3 (local-first, egress-off by default) + the egress gate. **Resembles:** the egress-seam
work (inc 58) + the DOI-re-resolve precedent (an explicit user action sending non-library data).

**The misaligned easy path:** let the `local` provider accept *any* `base_url` under a "no egress" label — then a
"local" config could quietly POST library text to an arbitrary remote host while the egress toggle reads off. That
would break the promise.

**The aligned design (taken):** a `local` provider is **loopback-restricted** (`complete()` rejects non-loopback;
inc 150 422s it at the write boundary). The egress invariant protects *library text leaving the machine*; a
loopback model keeps the text on the machine, so consent-to-egress is correctly **N/A** — `requires_egress("local")`
is False. This is not a loosening of the promise; it is the promise correctly recognizing that local ≠ egress.
Choosing the local provider IS the opt-in. Cloud providers (gemini/openai/anthropic) are unchanged — still gated.

## Manual verification

Hermetic (`tests/test_providers.py`, 10 tests): per-provider request shape + parse + usage mapping (injected fake
client, no network); loopback truth table + non-loopback rejection; the gate (local skips egress, cloud blocks);
per-provider key resolution; **the headline** — a local-provider summary generates with the egress toggle OFF.
The existing LLM tests (`test_summarization`/`test_help`/`test_axes`, 73 green) confirm the gemini path is
behavior-preserved through the seam. (A real OpenAI/Anthropic/Ollama round-trip is the user's manual check with a
real key / local server.)

## Audit

`.claude/security-audits/2026-06-26_multi-provider-llm.md` **PASS** — SSRF (loopback-only local; cloud hosts are
constants), per-provider key redaction, fail-closed httpx, no new dependency, the local-no-egress gate change.

## Pytest

**546** (+10 `test_providers.py`). `ruff` clean; **no migration**, no new endpoint (engine-only) → route + QA
surface unchanged. No frontend change (the provider UI is inc 150).

## Next

inc 150 — the Settings provider UI (a provider dropdown + per-provider key / local base_url + the egress toggle
auto-satisfied for local) + `PUT /settings` extension with a loopback-422; help corpus "choosing a provider".
