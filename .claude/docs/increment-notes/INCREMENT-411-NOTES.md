# Increment 411 — friendly pre-flight check for a missing provider API key (the shared LLM seam)

## Implemented

A second real external bug report (same colleague, Isabella Bobrow), this time with a screenshot: clicking
**"search related terms"** in the Axis edit modal always failed with a raw provider error dumped straight into
the UI — `Term suggestion failed: ProviderError: HTTP 401: {"type":"error","error":{"type":"authentication_error",
"message":"x-api-key header is required"}, ...}`.

Traced to the exact mechanics: `POST /axes/suggest-terms` (`app/backend/api/routers/axes.py`) calls
`GeminiAxisTermSuggester.suggest()` → `app.backend.llm.providers.complete(config, prompt)` — the one shared
seam every LLM-backed feature routes through (axis-terms, summary generation, research summary, help chat,
critique, funding triage, assisted extraction, …). When the active provider has no API key resolved (here:
Anthropic selected with no key saved), `complete()` previously went ahead and made the real HTTP call anyway —
`_complete_anthropic` sends `"x-api-key": api_key or ""`, Anthropic correctly 401s with its own JSON body, and
that raw body became the entire error text shown to the user.

The fix lands in exactly one place, `complete()` itself, right after resolving `key`: if
`requires_egress(config)` is true (a cloud provider, or a non-loopback custom endpoint) and no key is resolved,
raise `ProviderError` immediately with a friendly, actionable message — *before* any network call. Because
every one of the ~8 generator modules (`integrations/gemini/{axis_terms,research_summary,overview,
help_assistant,critical_review,critical_review_set,extraction_assistant,axis_cluster_labeler}.py`) and
`funding/llm_triage.py` routes through this same seam, and every router already catches the resulting exception
generically (`except Exception as exc: raise HTTPException(502, f"... failed: {type(exc).__name__}: {exc}")`),
this one change fixes the friendliness of the error message everywhere at once — no router-by-router changes
needed, and nothing to keep in sync across 8+ files.

This mirrors a pre-existing precedent already in the codebase: `POST /settings/test-key`
(`app/backend/api/routers/settings.py`) already does exactly this same `requires_egress(cfg) and not
cfg.resolved_api_key()` check before its own probe call, returning "No API key is set for this provider. Paste
one above and Save." The gap was that this check existed only in the Settings "Test key" button's own code
path, not in the shared seam every *other* AI feature actually calls through.

A loopback/local provider (Ollama etc.) legitimately needs no key — `requires_egress` already returns False for
it, so the new check correctly exempts it; `test_complete_local_loopback_uses_openai_shape` (passing `api_key=
None` for a loopback provider) already covers this and continues to pass unchanged.

## Key technical detail

The check is placed after `key = config.resolved_api_key()` but before the `wire == "gemini"` dispatch, so it
covers all four wire formats (gemini SDK, Anthropic messages, OpenAI chat_completions, OpenAI responses)
uniformly — a custom OpenAI-compatible provider (DeepSeek, Together, Groq, OpenRouter, vLLM, a non-loopback
custom endpoint) with a missing key gets the same friendly refusal as a builtin.

## Manual verification

- Screenshot from the bug report confirmed the exact code path (the error text matches `suggest_axis_terms`'s
  except-block format verbatim), so the fix targets the actual reported failure, not a guess.
- New test `test_complete_blocks_before_network_when_no_key_for_cloud_provider` (`tests/test_providers.py`)
  injects an `http_client` stub whose `.post()` raises `AssertionError` if ever called — proving the new guard
  refuses *before* any network attempt, not just producing a nicer message after a real failed call.
- `pytest tests/test_providers.py -q` → **15 passed** (1 new).
- Full suite: `pytest -n auto -q` → **1683 passed, 1 skipped** (up from 1682 post-inc-410; +1 new test here).

## Pytest

`tests/test_providers.py`: 15 passed. Full suite: 1683 passed, 1 skipped.
