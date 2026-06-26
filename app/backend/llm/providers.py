"""Provider-neutral LLM completion seam (inc 149 — multi-provider BYOK).

Every generator builds its own prompt + parses its own response; the only provider-specific step is "send a
text prompt, get text back". This module is that step. ``complete(config, prompt)`` dispatches on
``config.provider`` (gemini via the google-genai SDK; openai / anthropic / local via httpx — no new dependency)
and returns a ``CompletionResult`` whose ``usage_metadata`` is shaped so ``llm.usage.log_usage`` works unchanged.

**Local provider = no egress, honestly.** A ``local`` provider must point at a LOOPBACK address
(127.0.0.1 / localhost / ::1); a non-loopback ``base_url`` is rejected here (and at the settings-write boundary).
That is what lets ``requires_egress("local")`` return False without weakening invariant #3: a loopback model keeps
library text on the machine, so consent-to-egress is correctly N/A. (Choosing the local provider IS the opt-in.)

This module imports neither ``app.backend.llm.egress`` nor ``integrations.gemini.*`` (``egress`` imports
``requires_egress`` from here; the config is duck-typed — any object with ``provider`` / ``model`` /
``resolved_api_key()`` / ``base_url``), so there is no import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

CLOUD_PROVIDERS = ("gemini", "openai", "anthropic")
ALL_PROVIDERS = (*CLOUD_PROVIDERS, "local")
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
_HTTP_TIMEOUT = 60.0
_MAX_TOKENS = 2048  # anthropic requires an explicit cap; a generous bound for our prompts


class ProviderError(RuntimeError):
    """A provider call failed (bad key, network, malformed response, or a non-loopback local base_url)."""


@dataclass(frozen=True)
class _Usage:
    prompt_token_count: int | None = None
    candidates_token_count: int | None = None
    total_token_count: int | None = None


@dataclass(frozen=True)
class CompletionResult:
    text: str
    usage_metadata: object  # duck-typed for log_usage (prompt_/candidates_/total_token_count)


def requires_egress(provider: str) -> bool:
    """Cloud providers leave the machine (egress); a loopback ``local`` provider does not."""
    return provider in CLOUD_PROVIDERS


def is_loopback_url(url: str | None) -> bool:
    """True iff ``url`` is an http(s) URL whose host is a loopback address."""
    if not url:
        return False
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "") in _LOOPBACK_HOSTS


def complete(config, prompt: str, *, http_client=None) -> CompletionResult:
    """Send ``prompt`` to ``config``'s provider and return the text + usage. Raises ``ProviderError`` on failure.

    ``http_client`` (an httpx.Client) is injectable so tests run with no network.
    """
    provider = getattr(config, "provider", "gemini") or "gemini"
    model = config.model
    if provider == "gemini":
        return _complete_gemini(model, config.resolved_api_key(), prompt)
    if provider == "anthropic":
        return _complete_anthropic(model, config.resolved_api_key(), prompt, http_client)
    if provider == "openai":
        return _complete_openai_compatible(
            "https://api.openai.com", model, config.resolved_api_key(), prompt, http_client
        )
    if provider == "local":
        base = getattr(config, "base_url", None)
        if not is_loopback_url(base):
            raise ProviderError(
                "The local provider requires a loopback base_url (127.0.0.1 / localhost) — refusing to send to "
                f"{base!r} under the no-egress 'local' label."
            )
        return _complete_openai_compatible(base.rstrip("/"), model, config.resolved_api_key(), prompt, http_client)
    raise ProviderError(f"Unknown LLM provider: {provider!r}")


def _complete_gemini(model: str, api_key: str | None, prompt: str) -> CompletionResult:
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(_redact(str(exc), api_key)) from exc
    return CompletionResult(
        text=str(getattr(response, "text", "") or ""), usage_metadata=getattr(response, "usage_metadata", None)
    )


def _complete_openai_compatible(
    base: str, model: str, api_key: str | None, prompt: str, http_client
) -> CompletionResult:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    data = _post(f"{base}/v1/chat/completions", payload, headers, api_key, http_client)
    try:
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        meta = _Usage(
            prompt_token_count=usage.get("prompt_tokens"),
            candidates_token_count=usage.get("completion_tokens"),
            total_token_count=usage.get("total_tokens"),
        )
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Malformed chat-completions response.") from exc
    return CompletionResult(text=str(text or ""), usage_metadata=meta)


def _complete_anthropic(model: str, api_key: str | None, prompt: str, http_client) -> CompletionResult:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key or "",
        "anthropic-version": "2023-06-01",
    }
    payload = {"model": model, "max_tokens": _MAX_TOKENS, "messages": [{"role": "user", "content": prompt}]}
    data = _post("https://api.anthropic.com/v1/messages", payload, headers, api_key, http_client)
    try:
        text = data["content"][0]["text"]
        usage = data.get("usage") or {}
        inp, out = usage.get("input_tokens"), usage.get("output_tokens")
        meta = _Usage(
            prompt_token_count=inp,
            candidates_token_count=out,
            total_token_count=(inp + out) if isinstance(inp, int) and isinstance(out, int) else None,
        )
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Malformed Anthropic response.") from exc
    return CompletionResult(text=str(text or ""), usage_metadata=meta)


def _post(url: str, payload: dict, headers: dict, api_key: str | None, http_client) -> dict:
    import httpx

    try:
        if http_client is not None:
            resp = http_client.post(url, json=payload, headers=headers, timeout=_HTTP_TIMEOUT)
        else:
            resp = httpx.post(url, json=payload, headers=headers, timeout=_HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        body = ""
        try:
            body = exc.response.text[:200]
        except Exception:
            pass
        raise ProviderError(_redact(f"HTTP {exc.response.status_code}: {body}", api_key)) from exc
    except Exception as exc:  # noqa: BLE001 — network / decode failures
        raise ProviderError(_redact(str(exc), api_key)) from exc


def _redact(msg: str, api_key: str | None) -> str:
    """Never let a key leak into an error message; cap the length."""
    out = msg.replace(api_key, "***") if api_key else msg
    return out[:300]
