# Increment 492 — app-scoped LLM provider-client reuse

## Implemented

- `app/backend/provider_runtime.py` introduces one explicit `ProviderClientRuntime` per FastAPI application. It
  lazily owns persistent synchronous HTTPX connection pools and Google GenAI SDK clients, with no mutable module
  singleton and no cross-app sharing.
- Raw HTTP pools are keyed by a non-reversible endpoint fingerprint plus client-scoped timeout, TLS verification,
  `trust_env`, and proxy/certificate environment identity. Provider model and API key remain request-scoped and do
  not unnecessarily split the transport pool.
- Gemini clients are keyed by a non-reversible API-credential fingerprint plus the SDK's Vertex/project/location
  environment identity. A credential or environment rotation therefore creates a distinct client and cannot send
  a new request through stale SDK credentials.
- Every production LLM feature resolves current settings through `api/dependencies.py::resolve_llm_config`, which
  attaches the owning app's runtime. An explicitly injected `complete(..., http_client=...)` still wins and never
  constructs an app-scoped client; directly constructed configs retain the legacy fallback for compatibility.
- The app lifespan closes every constructed HTTPX and Gemini client before releasing local-model and database
  resources. Cleanup is idempotent, construction is guarded per identity, failed construction is retryable, and
  ordinary calls never hold a registry-wide lock.

## Concurrency and safety decisions

No provider-call concurrency was added. Existing concurrent callers may share compatible clients without a new
serialization lock: HTTPX documents `Client` as shareable between threads, while the installed Google GenAI SDK
test suite explicitly exercises concurrent synchronous `generate_content` calls and credential initialization /
refresh locking. Construction and shutdown remain guarded independently.

Configuration snapshots are resolved per operation. Raw HTTP API-key rotation safely reuses the transport pool
because authentication is rebuilt in the request headers; tests prove the new request contains only the new key.
Gemini embeds the credential in the SDK client, so key rotation necessarily resolves a separate identity. Old
compatible clients remain owned until shutdown instead of being closed underneath an in-flight operation.

Request URLs, JSON payloads, headers, provider dispatch, response parsing, error classification/redaction, and the
60-second request timeout are unchanged. No credential or endpoint is logged or exposed through runtime identity
diagnostics.

## Offline measured proof

No paid or external provider request was made.

- Raw HTTP, local HTTP/1.1 server, five rounds of 20 production `complete()` calls:
  - reference top-level path: first-request median **0.3811 s**, requests 2–20 median **0.3856 s**, p90
    **0.4383 s**, median round total **7.9557 s**, **100 constructors**, and 20 TCP connections per round;
  - app-scoped path: first-request median **0.3814 s**, requests 2–20 median **0.001375 s**, p90 **0.001705 s**,
    median round total **0.4166 s**, **5 constructors**, and one TCP connection per round;
  - later-request median fell 99.64% and median round total fell 94.76%. Localhost does not represent real
    provider/TLS latency, but it directly proves construction and pool reuse.
- Gemini, actual `google.genai.Client` construction with fake invalid keys and no request:
  - 20 reference constructions: first **1.2938 s**, later median **1.1152 s**, total **22.8622 s**, 20 constructors;
  - 20 managed acquisitions: first **1.1134 s**, later median **0.0000138 s**, total **1.1137 s**, one constructor;
  - key A acquired ten times and key B acquired ten times produced exactly two distinct constructors.

## Verification

- New provider-runtime suite: **16 passed**. It covers same-config reuse, raw/Gemini rotation, non-disclosure,
  explicit injection precedence, all raw request shapes, timeout/status/malformed/Gemini errors, simultaneous first
  construction plus failure retry, app isolation, cleanup, config wiring, and non-serialized existing SDK calls.
- Affected provider/LLM/router/model-runtime/Critical Read suite: **358 passed**.
- Full parallel suite: **2375 passed, 3 skipped in 1724.97 s (0:28:44)**.
- Ruff format/check, Tach module boundaries, and the **555-file** line budget passed. Bandit is not installed in
  this environment (`python -m bandit` reports no module), so no Bandit result is claimed. No security-audit
  trigger was introduced: this adds no endpoint, dependency, provider, destination, egress path, auth surface,
  schema, input, file access, or deployment boundary.

## Boundaries

No async/streaming/concurrency, retry, prompt, output-cap, model-routing, response-cache, synthesis-overview,
local-model, Critical Read batching, scientific output, API/frontend, or schema behavior changed. Help was
reviewed and intentionally left unchanged because provider-client ownership is invisible to users.
