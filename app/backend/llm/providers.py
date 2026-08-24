"""Provider-neutral LLM completion seam (inc 149 — multi-provider BYOK; inc 256 — unified custom providers).

Every generator builds its own prompt + parses its own response; the only provider-specific step is "send a
text prompt, get text back". This module is that step. ``complete(config, prompt)`` dispatches on
``config.wire_format`` (``gemini`` via the google-genai SDK; ``messages`` / ``chat_completions`` / ``responses``
via httpx — no new dependency) and returns a ``CompletionResult`` whose ``usage_metadata`` is shaped so
``llm.usage.log_usage`` works unchanged. For back-compat the wire format is derived from ``config.provider`` when
a config carries no ``wire_format`` (the builtin names), so an object with only ``provider`` still dispatches.

**Egress is endpoint-based (inc 256), honestly.** ``requires_egress(config)`` is True for the gemini SDK and
otherwise True iff the ``base_url`` is non-loopback — so a custom cloud provider is gated exactly like Gemini and
a loopback provider (the builtin ``local`` or a custom localhost endpoint) is honestly no-egress, without
weakening invariant #3. ``requires_egress`` also accepts a provider NAME (string) for the builtins, where the
name alone decides. The builtin ``local`` preset additionally must point at a LOOPBACK address (rejected here if
not) — that is the promise its "no data leaves" label makes; custom providers are egress-gated instead.

This module imports neither ``app.backend.llm.egress`` nor ``integrations.gemini.*`` (``egress`` imports
``requires_egress`` from here; the config is duck-typed — any object with ``provider`` / ``model`` /
``resolved_api_key()`` / optional ``wire_format`` / ``base_url``), so there is no import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from app.backend.provider_runtime import ProviderClientRuntime

CLOUD_PROVIDERS = ("gemini", "openai", "anthropic")
ALL_PROVIDERS = (*CLOUD_PROVIDERS, "local")
WIRE_FORMATS = ("gemini", "messages", "chat_completions", "responses")
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
_HTTP_TIMEOUT = 60.0
_MAX_TOKENS = 2048  # anthropic requires an explicit cap; a generous bound for our prompts
_ANTHROPIC_VERSION = "2023-06-01"

# Back-compat: derive the wire format + a default endpoint from a builtin provider NAME when a config carries no
# explicit ``wire_format`` (a directly-constructed config, or a bare provider-name string).
_DEFAULT_WIRE = {"gemini": "gemini", "openai": "chat_completions", "anthropic": "messages", "local": "chat_completions"}
_DEFAULT_BASE = {
    "messages": "https://api.anthropic.com",
    "chat_completions": "https://api.openai.com",
    "responses": "https://api.openai.com",
}


def _wire_of(config) -> str:
    """The config's wire format — its explicit ``wire_format`` if present, else derived from ``provider``."""
    wire = getattr(config, "wire_format", None)
    if wire:
        return wire
    return _DEFAULT_WIRE.get(getattr(config, "provider", None) or "gemini", "chat_completions")


@dataclass(frozen=True)
class CompletionRequestIdentity:
    """Output-affecting provider request semantics, excluding model, prompt, and credentials.

    This is deliberately narrower than provider-client reuse identity: proxy, TLS, and pool settings affect
    transport reuse but do not define whether an already-generated synthesis is semantically reusable.
    """

    wire_format: str
    base_url: str | None
    generation_parameters: tuple[tuple[str, str | int], ...]


def completion_request_identity(config) -> CompletionRequestIdentity:
    """Resolve the same wire, endpoint, and fixed generation settings used by :func:`complete`."""
    wire = _wire_of(config)
    base = None
    if wire != "gemini":
        base = (getattr(config, "base_url", None) or _DEFAULT_BASE.get(wire) or "").rstrip("/") or None
    parameters: tuple[tuple[str, str | int], ...]
    if wire == "gemini":
        parameters = (("request_shape", "models.generate_content"),)
    elif wire == "messages":
        parameters = (
            ("anthropic_version", _ANTHROPIC_VERSION),
            ("max_tokens", _MAX_TOKENS),
            ("request_shape", "messages"),
        )
    elif wire == "responses":
        parameters = (("request_shape", "responses"),)
    else:
        parameters = (("request_shape", "chat_completions"),)
    return CompletionRequestIdentity(wire_format=wire, base_url=base, generation_parameters=parameters)


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


def requires_egress(config_or_provider) -> bool:
    """Does this provider's endpoint leave the machine?

    Accepts either a config object (endpoint-based — the honest rule for arbitrary custom providers) or a
    provider NAME string (the builtins, decided by name). Gemini's SDK always egresses to Google; otherwise a
    request egresses iff its ``base_url`` is non-loopback. A loopback endpoint (the builtin ``local`` or a custom
    localhost provider) is honestly no-egress (invariant #3)."""
    if isinstance(config_or_provider, str):
        return config_or_provider in CLOUD_PROVIDERS
    config = config_or_provider
    if _wire_of(config) == "gemini":
        return True
    base = getattr(config, "base_url", None)
    if base:
        return not is_loopback_url(base)
    return getattr(config, "provider", None) in CLOUD_PROVIDERS


def is_loopback_url(url: str | None) -> bool:
    """True iff ``url`` is an http(s) URL whose host is a loopback address."""
    if not url:
        return False
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "") in _LOOPBACK_HOSTS


def complete(
    config,
    prompt: str,
    *,
    http_client=None,
    provider_runtime: ProviderClientRuntime | None = None,
) -> CompletionResult:
    """Send ``prompt`` to ``config``'s provider and return the text + usage. Raises ``ProviderError`` on failure.

    Dispatches on the config's wire format (``gemini`` / ``messages`` / ``chat_completions`` / ``responses``).
    ``http_client`` (an httpx.Client) is injectable so tests run with no network and always takes precedence over
    the app-scoped runtime. A config created by the FastAPI dependency resolver carries that runtime for normal
    production calls; directly constructed configs retain the legacy fallback.
    """
    provider = getattr(config, "provider", "gemini") or "gemini"
    runtime = provider_runtime or getattr(config, "provider_runtime", None)
    request_identity = completion_request_identity(config)
    wire = request_identity.wire_format
    model = config.model
    key = config.resolved_api_key()
    if requires_egress(config) and not key:
        # Refuse before any network call — every LLM feature (axis-terms, summaries, help, …) routes through
        # this one seam, so this is the single place to catch "no key set for this provider" and give a
        # friendly, actionable message instead of letting a real provider 401 (e.g. Anthropic's raw
        # "x-api-key header is required" JSON) reach the user. Mirrors /settings/test-key's own pre-check.
        # A loopback/local provider legitimately needs no key, so requires_egress correctly exempts it.
        raise ProviderError(f"No API key is set for the '{provider}' provider. Add one in Settings and Save.")
    if wire == "gemini":
        return _complete_gemini(model, key, prompt, runtime)
    base = getattr(config, "base_url", None)
    # The builtin ``local`` preset promises no data leaves → its endpoint MUST be loopback (custom providers are
    # egress-gated instead of loopback-restricted, so an arbitrary custom URL is allowed but gated).
    if provider == "local" and not is_loopback_url(base):
        raise ProviderError(
            "The local provider requires a loopback base_url (127.0.0.1 / localhost) — refusing to send to "
            f"{base!r} under the no-egress 'local' label."
        )
    base = request_identity.base_url or ""
    if not base:
        raise ProviderError(f"No base URL configured for provider {provider!r} (wire format {wire!r}).")

    def dispatch(active_http_client):  # type: ignore[no-untyped-def]
        if wire == "messages":
            return _complete_anthropic(base, model, key, prompt, active_http_client)
        if wire == "responses":
            return _complete_responses(base, model, key, prompt, active_http_client)
        if wire == "chat_completions":
            return _complete_openai_compatible(base, model, key, prompt, active_http_client)
        raise ProviderError(f"Unknown wire format: {wire!r}")

    if http_client is not None:
        return dispatch(http_client)
    if runtime is not None:
        return runtime.run_http(
            base_url=base,
            timeout=_HTTP_TIMEOUT,
            trust_env=bool(getattr(config, "http_trust_env", True)),
            operation=dispatch,
        )
    return dispatch(None)


def _complete_gemini(
    model: str,
    api_key: str | None,
    prompt: str,
    provider_runtime: ProviderClientRuntime | None,
) -> CompletionResult:
    try:

        def generate(client):  # type: ignore[no-untyped-def]
            return client.models.generate_content(model=model, contents=prompt)

        if provider_runtime is not None:
            response = provider_runtime.run_gemini(api_key=api_key, operation=generate)
        else:
            from google import genai

            response = generate(genai.Client(api_key=api_key))
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


def _complete_anthropic(base: str, model: str, api_key: str | None, prompt: str, http_client) -> CompletionResult:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key or "",
        "anthropic-version": _ANTHROPIC_VERSION,
    }
    payload = {"model": model, "max_tokens": _MAX_TOKENS, "messages": [{"role": "user", "content": prompt}]}
    data = _post(f"{base}/v1/messages", payload, headers, api_key, http_client)
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


def _complete_responses(base: str, model: str, api_key: str | None, prompt: str, http_client) -> CompletionResult:
    """The OpenAI Responses API (``POST {base}/v1/responses``, body ``{model, input}``). The response is untrusted
    (a custom endpoint) — parse defensively: prefer the flattened ``output_text``, else walk ``output[]``."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "input": prompt}
    data = _post(f"{base}/v1/responses", payload, headers, api_key, http_client)
    try:
        text = _responses_text(data)
        usage = data.get("usage") or {}
        inp, out = usage.get("input_tokens"), usage.get("output_tokens")
        total = (inp + out) if isinstance(inp, int) and isinstance(out, int) else usage.get("total_tokens")
        meta = _Usage(prompt_token_count=inp, candidates_token_count=out, total_token_count=total)
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderError("Malformed Responses API response.") from exc
    return CompletionResult(text=str(text or ""), usage_metadata=meta)


def _responses_text(data: dict) -> str:
    """Extract the assistant text from a Responses-API payload. Tolerant of the SDK's convenience ``output_text``
    and the raw ``output[]`` message structure."""
    flat = data.get("output_text")
    if isinstance(flat, str):
        return flat
    parts: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and content.get("type") in ("output_text", "text"):
                piece = content.get("text")
                if isinstance(piece, str):
                    parts.append(piece)
    return "".join(parts)


# Known-status friendly lead-ins (inc 413) — a wrong/expired key, a rate limit, or a provider outage produced
# the same raw-JSON-dump text as the "no key at all" case the pre-check in complete() catches; this covers the
# cases that still reach the network. Unclassified statuses keep today's plain "HTTP {code}: {body}" — we only
# guess a friendly interpretation for codes we're confident about, never for an arbitrary custom provider's
# unknown error shape. The raw detail is always appended, never hidden (evidence always shown, invariant #4).
def _friendly_status_prefix(status: int) -> str | None:
    if status in (401, 403):
        return "Authentication failed for this provider — check the saved API key in Settings."
    if status == 429:
        return "Rate limited by the provider — wait a moment and try again."
    if 500 <= status < 600:
        return "The provider is temporarily unavailable — try again shortly."
    return None


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
        detail = f"HTTP {exc.response.status_code}: {body}"
        friendly = _friendly_status_prefix(exc.response.status_code)
        raise ProviderError(_redact(f"{friendly} ({detail})" if friendly else detail, api_key)) from exc
    except Exception as exc:  # noqa: BLE001 — network / decode failures
        raise ProviderError(_redact(str(exc), api_key)) from exc


def _redact(msg: str, api_key: str | None) -> str:
    """Never let a key leak into an error message; cap the length."""
    out = msg.replace(api_key, "***") if api_key else msg
    return out[:300]
