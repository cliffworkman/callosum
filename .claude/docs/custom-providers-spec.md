# Design spec — unified multi-provider BYOK (custom providers) · inc 256

**Status:** approved (design dialogue 2026-07-03). Origin: Jeff's "Add model provider" mockup — let a user add
arbitrary, user-named LLM providers (base URL + key + wire-format + a model list), unifying the fixed
gemini/openai/anthropic/local set into one editable list.

**Scope calls locked with the user:** (1) **all three wire formats** incl. the OpenAI `/responses` parser; (2)
**unify** — the four presets become pre-seeded, editable rows in one provider list (a settings-file migration),
not a separate "custom" bucket alongside them.

---

## The load-bearing idea — egress becomes *endpoint-based*, not *name-based*

Today `requires_egress(provider: str)` returns `provider in ("gemini","openai","anthropic")`. The unify move
swaps it for an endpoint test so invariant #3 stays honest for an arbitrary user URL **for free**:

```
requires_egress(config):
    config.wire_format == "gemini"  -> True            # SDK always egresses to Google
    otherwise                       -> not is_loopback_url(config.base_url)
```

A custom provider at `api.deepseek.com` is egress-gated **exactly** like Gemini; one at `localhost` is
no-egress — the same rule that already governs `local`, no longer hardcoded to one provider name. This is the
**aligned alternative** (Principles gate, rule #9) to the easy-but-wrong "the user typed a URL, so that's
consent" path, which would silently widen egress.

---

## Data model — synthesized builtins + persisted customs (AS SHIPPED)

The design goal ("one editable list") is realized WITHOUT persisting a `providers` array or introducing new
`active_provider_id`/`active_model` fields. The four presets are **synthesized on every read** from module
constants (`providers_store._BUILTIN_META`) overlaid with the existing flat inc-149 fields, and only **custom**
providers are persisted (`custom_providers` in the settings file). The **active selection reuses the existing
flat `provider` (id) + `model` fields** — full back-compat with inc 149, no migration.

```jsonc
// settings file — ONLY the custom rows are stored; the four builtins are never written:
"custom_providers": [
  {"id":"<uuid>", "name":"DeepSeek", "wire_format":"chat_completions", "base_url":"https://api.deepseek.com", "models":["deepseek-chat"]}
],
"provider":"gemini",   // the ACTIVE provider id (a builtin id OR a custom uuid) — the inc-149 flat field, reused
"model":"",            // the active model override ("" ⇒ the active provider's first model)
"local_base_url":"http://localhost:11434"   // overlays the synthesized `local` preset's base_url
```

The synthesized roster (`providers_store.list_providers()`) presents the same shape the UI/spec describe —
`{id, name, wire_format, base_url, models[], builtin}` — with the four builtins first, then the customs:

- **`builtin` presets** (`gemini`/`openai`/`anthropic`/`local`): synthesized, so `name`/`wire_format`/`base_url`
  are **fixed** (protects Gemini's SDK path; a user cannot edit "gemini" into an HTTP endpoint). Their **key** is
  editable (via `PUT /settings`) and `local`'s `base_url` is overlaid from `local_base_url`. They cannot be
  edited/deleted through the custom-CRUD router (`is_builtin` → 400).
- **Custom providers**: everything user-set; `wire_format` ∈ the three custom formats only (a custom provider
  **cannot** claim `gemini`/SDK). `id` is **server-generated** (uuid4 hex), never client-supplied.
- **Active model**: `active_model()` = the flat `model` override if set, else the active provider's first model.

### Decision A — secrets are NOT migrated in the keychain (chosen)
Builtin presets keep resolving their key from the **existing** fixed fields (`api_key`/GOOGLE_API_KEY,
`openai_api_key`, `anthropic_api_key`). Only **custom** providers get an id-keyed secret (`provider_key::<uuid>`).
Because builtins are synthesized (never persisted) and the active selection reuses the flat fields, the change
touches **only** the additive `custom_providers` list + id-keyed custom secrets — **zero rewrite of the user's
real keychain/vault, and no lazy back-fill needed** (there is no `providers` array to back-fill).

---

## Wire formats (dispatch on `config.wire_format`)

| format | endpoint | body | notes |
|---|---|---|---|
| `gemini` | google-genai SDK | — | unchanged; `base_url` ignored |
| `messages` | `{base}/v1/messages` | Anthropic messages | generalize the hardcoded `api.anthropic.com` |
| `chat_completions` | `{base}/v1/chat/completions` | `{model, messages}` | already base-parametric (`_complete_openai_compatible`) |
| `responses` | `{base}/v1/responses` | `{model, input}` | **new** `_complete_responses`; parse `output[]` → `output_text` |

### Decision B — base-URL convention (chosen): base = host, we append `/v1/<suffix>`
`/v1/chat/completions`, `/v1/messages`, `/v1/responses`. Keeps today's `local`/`openai` paths working with **no
URL migration**, makes the three formats symmetric, and is less error-prone than asking users to hand-include
`/v1`. Dropdown labels read `/v1/chat/completions` · `/v1/messages` · `/v1/responses` (a tidy of Jeff's mockup,
which was inconsistent — `/v1/messages` but bare `/chat/completions`). Base-URL placeholder → `https://api.example.com`.

### The `/responses` envelope (confirm against live docs at implementation)
`POST {base}/v1/responses` → `{ "output": [ { "type":"message", "content":[ {"type":"output_text","text": "..."} ] } ], "usage": {"input_tokens","output_tokens"} }`.
Parser: first `output` item of type `message` → concatenate its `output_text` content parts. Usage maps to the
`CompletionResult` token fields like the other branches.

---

## API — a dedicated `routers/settings_providers.py` sub-router (Decision C)

| method | path | purpose |
|---|---|---|
| GET | `/settings/providers` | list (status-only — **never** a key value; each row carries `key_set: bool`; carries `active_provider` + the `wire_formats` allowlist) |
| POST | `/settings/providers` | add a **custom** provider (server-gen `uuid4().hex` id) |
| PUT | `/settings/providers/{id}` | edit a **custom** provider's name/base_url/wire_format/models (builtin id → **400**; unknown → **404**) |
| DELETE | `/settings/providers/{id}` | remove a **custom** provider (builtin id → **400**; if it was active, active falls back to gemini) |

**AS SHIPPED — no `/key` or `/active` sub-routes.** The per-provider **key** and the **active selection** ride the
existing `PUT /settings` channel (inc 146/149), unchanged: `{set_api_key, api_key, api_key_provider:<id>}` writes a
key (write-only, id-keyed `provider_key::<uuid>`); `{provider:<id>, set_model, model}` sets the active provider +
model (the roster is the id allowlist for `provider`). This is why there is **no** `active_provider_id`/`active_model`
field — see the Data model section.

Boundary validation (rule #4): name non-empty + capped; `base_url` **http/https only**, ≤500, required for
non-gemini; `wire_format` ∈ {`messages`,`chat_completions`,`responses`}; models each capped + list length
capped; key ≤ `API_KEY_MAX_LEN`. `GET /settings` keeps the existing status shape, its `provider` +
`provider_keys_set` derived from the new list for back-compat.

---

## Frontend — split then build

`app/frontend/js/35_settings.jsx` is **already 604 lines (over the 600 cap)** — the feature forces the split we
want anyway: extract the AI-provider block into new **`35b_providers.jsx`** (shared-IIFE hoist, the
inc-208/222 precedent). It houses: the **provider list** (name · format badge · key-set dot · active radio ·
edit/delete), the mockup **Add-provider form** (Name / Base URL / API key / API-format dropdown / model list
with "+ Add model"), and the active-provider + active-model pickers (model options come from the active
provider's `models`). Rebuild via `tools/build_frontend.py`.

---

## Gates (all owed in-increment)

- **Security audit** — `.claude/security-audits/2026-07-03_custom-providers.md`. Negative paths: egress-off +
  custom-cloud provider ⇒ **fails closed** (no outbound); a custom key is **never** in `GET /settings` /
  provider list and **never** logged (extend `_redact`); base_url scheme (reject `file://`/non-http) + length +
  httpx timeout; loopback-custom ⇒ correctly **no-egress**; a custom provider **cannot** set `wire_format=gemini`
  (no SDK hijack); id is server-generated (no client id injection / path traversal via `{id}`).
- **Principles gate (rule #9)** — advances "local-first & provider-swappable"; **expands the egress surface** so
  it must stay behind the consent gate — the endpoint-based rule above is the aligned design. Values layer: a
  **confirmed** value being **extended** (4 fixed → N user-defined); no veto boundary (no paywall circumvention /
  no reaching into other tools' stores / no accusation) is tripped.
- **QA (rule #10)** — extend the settings route with the provider-CRUD surface + a custom-provider egress-honesty
  assertion (a loopback custom is local/no-egress; a cloud custom is gated).
- **Experience pass (rule #11)** — persona: a user wiring up **DeepSeek** or a **local vLLM** — is add → save key
  → test-key → set-active → generate discoverable and legible; does the key-set state read clearly.

---

## Files (~8–10) & line-count watch

`app/backend/providers_store.py` (new — keeps the list logic out of `app_settings.py`, already 516) ·
`integrations/gemini/generator.py` (`LLMConfig.wire_format` + `from_environment`) · `app/backend/llm/providers.py`
(dispatch + `_complete_responses` + `requires_egress` signature) · `app/backend/llm/egress.py` (call sites) ·
the 5 generators (`requires_egress(self.config)`) · `app/backend/api/routers/settings.py` (align `_status`) +
new `routers/settings_providers.py` · `app/frontend/js/35_settings.jsx` **split** → new `js/35b_providers.jsx` ·
`app/frontend/styles.css` · tests · docs · QA route · security audit.

**Caps to respect:** `35_settings.jsx` 604 → must drop under 600 via the split; `app_settings.py` 516 → list
logic goes in the new `providers_store.py`, not here; `settings.py` 235 → CRUD in the sub-router, not here.

**The `requires_egress(provider)` → `requires_egress(config)` refactor** spans ~10 sites (5 generators +
`egress.py` ×5 + test-key) — mechanical, but part of the increment's blast radius.
