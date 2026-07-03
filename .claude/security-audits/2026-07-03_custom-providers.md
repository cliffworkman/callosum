# Security audit — unified multi-provider BYOK (custom providers) · inc 256

**Opened:** 2026-07-03 (task-start stub; filled as the increment lands).
**Trigger(s):** new request-schema (provider CRUD endpoints) · new external-fetch pattern (arbitrary user
base URLs) · new secret storage (per-id provider keys) · net-new feature spanning 3+ files / ~300+ LOC.

**Feature:** the fixed gemini/openai/anthropic/local provider set becomes one editable list; a user can add a
custom provider `{name, base_url, api_key, wire_format ∈ messages|chat_completions|responses, models[]}`. See
`.claude/docs/custom-providers-spec.md`.

**Threat model:** local, single-user, `127.0.0.1`-bound. The user *is* the operator, so an arbitrary base URL
is user-initiated, not attacker-pivoted. The live concerns are therefore (a) **egress honesty** — a custom URL
must not silently bypass invariant #3; (b) **secret handling** — a custom key must stay write-only + out of the
synced repo/Dropbox; (c) **untrusted-response handling** — a custom endpoint's response is untrusted input; (d)
**input validation** at the CRUD boundary. Classic SSRF is out-of-scope for the single-user local model but the
URL is still validated + documented for the future hosted pass.

## Review checklist

- [x] **Egress gate honesty (invariant #3).** `requires_egress(config)` is endpoint-based
      (`app/backend/llm/providers.py:69`): gemini wire → True; else `not is_loopback_url(base_url)`; with no
      base_url it falls back to the provider name (`provider in CLOUD_PROVIDERS`). `GeminiConfig.from_environment`
      resolves the active custom record's `wire_format`/`base_url`/key, so a custom **cloud** provider is gated
      exactly like Gemini and a custom **loopback** provider is honestly no-egress. The 5 generator call sites +
      `EgressGatedSummaryGenerator` pass the config through; `test-key` gates on `requires_egress(cfg)`.
      Covered by `test_active_custom_cloud_provider_is_egress_gated` + `test_requires_egress_config_is_endpoint_based`.
- [x] **No SDK hijack.** `CUSTOM_WIRE_FORMATS = (messages, chat_completions, responses)` — `gemini` is not in the
      set, so `_norm_wire` raises `ValueError` → the router returns **422**. Only the synthesized `gemini` preset
      carries `wire_format=gemini`, and builtins are never mutated by the CRUD router (`is_builtin` → 400). Covered
      by `test_custom_validation_raises_value_error` + `test_create_validation_422`.
- [x] **Secret handling.** A custom key is stored under the id-keyed field `provider_key::<uuid>` via the
      keychain-or-file store (`app_settings.set_provider_key`); `GET /settings/providers` returns only
      `key_set: bool` (`_key_set`), never the value; `_redact(msg, api_key)` covers the key in every
      `ProviderError`. `delete_custom` drops the orphaned secret. Covered by
      `test_custom_key_is_write_only_and_reported_as_set` (asserts the value is absent from the GET body) +
      `test_complete_redacts_the_key_from_provider_errors`. Keys live outside the repo/Dropbox (`~/.callosum/`).
- [x] **Base-URL validation.** `_norm_base` restricts the scheme to `http`/`https` (rejects `file://`, `ftp://`,
      `gopher://`, …), requires a netloc, caps length ≤ `BASE_URL_MAX_LEN` (500), strips a trailing slash;
      required for a custom provider. `_post` sets `_HTTP_TIMEOUT=60s`. Covered by
      `test_custom_validation_raises_value_error` (`ftp://` → ValueError → 422).
- [x] **CRUD input validation.** `_norm_name` (non-empty, ≤80), `_norm_models` (item ≤120, ≤32 items),
      `_norm_wire` (allowlist), `MAX_CUSTOM_PROVIDERS=50`. The `{pid}` is a server-generated `uuid4().hex` — a
      client cannot inject an id, so a path param can't be steered onto a builtin's key field or traverse a store
      key; `is_builtin(pid)` guards edit/delete (400) and unknown ids 404. Covered by
      `test_builtins_cannot_be_edited_or_deleted` + `test_edit_or_delete_unknown_custom_404`.
- [x] **Untrusted response.** Each wire parser validates shape before use and raises a redacted `ProviderError`
      on `KeyError/IndexError/TypeError` (`_complete_responses` also `AttributeError`); `_responses_text` walks
      `output[]` defensively, skipping non-message items. Covered by `test_complete_responses_*`. A non-200 is a
      redacted `ProviderError` (`_post`), never a crash.
- [x] **Supply chain.** No new dependency — `httpx` already present, `uuid`/`urllib.parse` are stdlib.

## Negative-path results

- **Egress OFF + custom cloud provider** → `requires_egress(cfg)` True ⟹ `test-key` returns `{ok:false, "Turn
  on Allow AI features…"}` and `complete()` is never called (the existing `test_test_key_egress_off_does_not_ping`
  pattern applies to any cloud config; the endpoint-based rule extends it to custom cloud URLs). Fails closed. ✅
- **Custom loopback provider, egress OFF** → `requires_egress(cfg)` False ⟹ runs without consent (no cloud
  call). Honest no-egress. ✅ (`test_active_custom_cloud_provider_is_egress_gated`, loopback branch.)
- **Key absent from `GET /settings/providers`** → the literal `sk-acme-secret` is not in the response text; only
  `key_set:true`. ✅ (`test_custom_key_is_write_only_and_reported_as_set`.)
- **Malformed base_url** (`ftp://x.ai`, `x.ai` with no scheme) → **422**, nothing persisted. ✅
- **`wire_format:"gemini"` on a custom** → **422** (no SDK hijack). ✅
- **Builtin edit/delete** (`PUT`/`DELETE /settings/providers/gemini|openai`) → **400**. ✅
- **Unknown id** edit/delete → **404**. ✅
- **Malformed `/responses` payload** (missing `output_text` + no `output[]`) → empty text, no crash; a
  structurally-broken payload raises a redacted `ProviderError`. ✅ (`test_complete_responses_walks_output_structure`.)
- **Oversized key** (`api_key` > `API_KEY_MAX_LEN`) via `PUT /settings` → **422**, nothing written (unchanged
  inc-146 guard, `test_put_oversized_key_is_rejected_and_nothing_written`). ✅

Full targeted suite green: `tests/test_providers.py` + `tests/test_providers_roster.py` + `tests/test_settings.py`
→ **57 passed**; full suite green (excluding the optional `mcp` suite).

## Verdict

**Security Audit: PASS.** The unified custom-provider feature preserves invariant #3 by moving the egress
decision to the endpoint (a custom cloud URL is gated identically to Gemini; a loopback URL is honestly
no-egress), keeps keys write-only + id-keyed outside the synced store, forbids the gemini SDK format on customs
(no SDK hijack), validates the base URL scheme + all CRUD inputs at the boundary, uses server-generated ids (no
traversal), and parses untrusted provider responses defensively. No new dependency. SSRF via a user-supplied URL
remains a documented item for the future **hosted** pass (out of scope for the single-user `127.0.0.1` model);
the URL is already scheme/length-validated.
