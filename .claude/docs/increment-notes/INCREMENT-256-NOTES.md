# INCREMENT 256 — Unified multi-provider BYOK (custom LLM providers)

**Origin:** Jeff's "Add model provider" mockup. Turn the fixed gemini/openai/anthropic/local set into **one
editable provider list** so a user can add arbitrary, user-named LLM providers
`{name, base_url, api_key, wire_format, models[]}`. Design dialogue + scope calls in
`.claude/docs/custom-providers-spec.md` (approved 2026-07-03): **(1) all three wire formats** incl. the new
OpenAI `/responses` parser; **(2) unify** — the four presets become pre-seeded, editable rows in one list, not a
separate "custom" bucket.

## Implemented

- **`app/backend/providers_store.py` (NEW, 250 lines)** — the roster model. The four builtins are **synthesized
  on every read** from `_BUILTIN_META` overlaid with the existing flat inc-149 fields (`local_base_url`, the
  per-provider keys, the `model` override); they are **never persisted**. Only **custom** providers are stored
  (`custom_providers` in the settings file). The active selection **reuses the existing flat `provider` (id) +
  `model` fields** — no new `active_provider_id`/`active_model` fields, full inc-149 back-compat, no migration.
  Public API: `list_providers` / `provider_ids` / `get_provider` / `is_builtin` / `active_provider` /
  `active_model` / `add_custom` / `update_custom` / `delete_custom` / `set_active`. Validators `_norm_name`
  (≤80), `_norm_base` (http/https only, netloc required, ≤500, trailing slash stripped), `_norm_wire`
  (`CUSTOM_WIRE_FORMATS` allowlist — gemini excluded), `_norm_models` (item ≤120, ≤32 items, blanks dropped);
  caps `MAX_CUSTOM_PROVIDERS=50`. Custom ids are server-generated `uuid4().hex`.
- **`app/backend/api/routers/settings_providers.py` (NEW, 129 lines)** — the CRUD sub-router:
  `GET /settings/providers` (roster, status-only — `key_set: bool`, never a value; carries `active_provider` +
  the `wire_formats` allowlist), `POST /settings/providers` (add custom, server-gen id), `PUT
  /settings/providers/{pid}` + `DELETE /settings/providers/{pid}` (custom-only — builtin id → **400**, unknown →
  **404**). The active-selection + per-provider key continue to ride the existing `PUT /settings` channel (the
  roster is the id allowlist for `provider`).
- **`app/backend/llm/providers.py`** — dispatch on `config.wire_format`: added `_complete_responses` (POST
  `{base}/v1/responses`, body `{model, input}`, parse flat `output_text` else walk `output[].content[].text` via
  `_responses_text`) alongside the existing gemini-SDK / messages / chat_completions branches.
  **`requires_egress` is now dual-mode:** a **string** arg stays name-based (`provider in CLOUD_PROVIDERS` —
  preserves the legacy `EgressGatedSummaryGenerator(provider=…)` call + old tests); a **config** arg is
  **endpoint-based** — gemini wire → True, else `not is_loopback_url(base_url)`, else (no base) fall back to the
  name. This is the load-bearing move: a custom cloud URL is gated identically to Gemini, a custom loopback URL
  is honestly no-egress (invariant #3 for an arbitrary user URL, for free).
- **`integrations/gemini/generator.py`** — `LLMConfig` gains `wire_format` + `base_url`; `from_environment()`
  resolves the **active roster record** (`providers_store.active_provider()`/`active_model()`) and its id-keyed
  secret, falling back to the env key only for gemini. The 5 generators + `test-key` pass the config through so
  the endpoint-based egress decision reaches every call site.
- **Frontend split — `app/frontend/js/35b_providers.jsx` (NEW, 362 lines)**, `35_settings.jsx` **471** (was
  604/over-cap; the AI block moved out via the shared-IIFE function hoist — `function AiSettings()` is still
  called unchanged from `SettingsModal`; the inc-208/222 precedent). The new chunk renders the collapsible
  **provider roster** (each `ProviderRow`: wire-format badge, **Active** pill / **Use** button, **Delete** on
  customs; body = the loopback base_url field for Local, the key field + "Get a key →" + "Sends to …" endpoint
  line for cloud/custom, plus the active provider's model picker + **Test** button), the **+ Add provider** form
  (`AddProviderForm` → `ProviderFields` + `ProviderModelsEditor`, the mockup layout with the API-format
  dropdown), and preserves the egress toggle + help-assistant toggle + verified-locally note.
- **`app/frontend/styles.css`** — a tokens-only `.provider-*` block (list / card / head / toggle / caret / name
  / badge / actions / active / body / endpoint / models) + `.provider-add-btn` (green `--verified` add
  affordance, DESIGN §2).

## Key technical detail

**The synthesized-builtins bridge.** The spec's "one list of `{id,name,wire_format,base_url,models,builtin}`"
is realized **without** persisting a `providers` array or adding new active-selection fields. `list_providers()`
= `[synthesize(gemini), synthesize(openai), synthesize(anthropic), synthesize(local), *custom_providers]`,
where each builtin is `_BUILTIN_META[id]` overlaid with today's flat settings (so editing a builtin's key still
writes the *same* fixed field it always did, and Local's base_url still comes from `local_base_url`). The only
new persisted state is the additive `custom_providers` list + id-keyed custom secrets (`provider_key::<uuid>`).
Consequence: **zero rewrite of the user's real keychain/vault, and no lazy back-fill** — there is no array to
migrate; a fresh settings file yields the four presets by pure synthesis (`"custom_providers" not in settings`).

**Model-override reset on switch (latent-bug pre-empt).** Exposing per-provider model selection means switching
the active provider could otherwise leak the previous provider's model string. `AiSettings.activate(id, model)`
sends `{provider:id, set_model:true, model: model||""}`, and `providers_store.delete_custom` clears the override
when it resets the active provider to gemini — so the active model always belongs to the active provider.

## Manual verification script

1. `python tools/build_frontend.py` (done — esbuild OK), start the app on **:8888**, open **Settings → AI
   features**. Confirm the four presets render as collapsible cards (Gemini active by default), each with a
   wire-format badge; Gemini shows the **Active** pill, the others a **Use** button.
2. Expand **Local** → a loopback `base_url` field + the "nothing leaves your machine" note. Expand **OpenAI** →
   its (masked) key field + **Get a key →** + a "Sends to https://api.openai.com" line. Click **Use** on OpenAI
   → it becomes Active, the model chooser appears; switch back to Gemini → confirm the model resets to
   `gemini-2.5-flash-lite` (no cross-provider leak).
3. **+ Add provider** → Name `DeepSeek`, Base URL `https://api.deepseek.com`, API format **Chat completions**,
   add model `deepseek-chat`, paste a key → **Add provider**. It appears as a non-builtin card with **Edit** +
   **Delete**. Edit its name/models (PUT) → Save; **Use** it → the summary generator would now route to it.
   Confirm `GET /settings/providers` (Network tab) contains **no** key value, only `key_set:true`.
4. **Egress honesty:** with **Allow AI features** OFF and the DeepSeek (cloud) provider active, **Test
   connection** reports "Turn on Allow AI features…" and fires **no** outbound request. Point a *second* custom
   provider at `http://127.0.0.1:11434` and make it active → no consent needed (loopback = local).
5. **Delete** the custom provider → removed; if it was active, active falls back to Gemini.

## Gates

- **Security audit:** `.claude/security-audits/2026-07-03_custom-providers.md` — **PASS** (egress endpoint-based
  + fails closed; keys write-only + id-keyed outside the synced store; no gemini-SDK hijack on customs; base-URL
  scheme/length validated; server-gen ids, no traversal; untrusted `/responses` parsed defensively; no new dep).
- **Principles gate (#9):** advances "local-first & **provider-swappable**"; the change **expands the egress
  surface**, so the aligned design keeps it behind the consent gate by making egress endpoint-based (the
  misaligned easy path — "the user typed a URL, so that's consent" — would silently widen egress). Values layer:
  a **confirmed** value **extended** (4 fixed → N user-defined); no veto boundary tripped.
- **QA (#10):** `route_35_settings.md` extended — `/settings/providers` + `/settings/providers/{pid}` +
  `35b_providers.jsx` in the coverage header, a Critical "custom providers are endpoint-egress-gated +
  write-only" standing assertion, and step 8 rewritten as the unified roster + a custom add/edit/delete
  sub-bullet. Surface check: **199 API / 944 FE, 0 uncovered.**
- **Experience pass (#11):** persona "Dana, the cost-conscious power user" wiring up DeepSeek — the agent found
  6 first-run traps, all cheap + localized, **fixed in-increment**: (1) the Add-form now defaults to **Chat
  completions** (the majority endpoint; was Anthropic-messages, which would silently break a DeepSeek add); (2)
  the Base URL placeholder is host-only (`https://api.deepseek.com`) + a hint that Callosum adds the `/v1/…`
  path, and `_norm_base` **trims a trailing `/v1`** so a pasted documented base can't double it (`{base}/v1/…`);
  (3) an added provider is now **auto-activated** ("add DeepSeek and use it" is one step, not two) with a
  "…added and set as active" toast; (4) the active card shows an amber **"AI features are off — Callosum won't
  contact X"** nudge when a cloud provider is active but egress is off (the success-vs-dead-end blocker); (5)
  the **egress-posture line now shows on custom cloud providers too** (was builtin-only) — "Sends to `<url>` —
  your library text goes there when you generate a summary", plus a loopback-address reassurance on a
  custom-loopback provider (the principle-adjacent honesty gap). An API-format helper line names which endpoints
  use which format. The `/v1`-strip is covered by a new assertion in `test_add_update_delete_custom_roundtrip`.

## Pytest

`tests/test_providers.py` (responses parser × 2, endpoint-based `requires_egress`, redaction, the existing
per-provider suite) + `tests/test_providers_roster.py` (NEW — store-level synthesis/CRUD/validation/egress + the
roster & CRUD API) + `tests/test_settings.py` → **57 passed** focused. **Full suite: 1008 passed, 1 skipped**
(excluding the optional `mcp` suite, uncollectable without the `mcp` package here).
