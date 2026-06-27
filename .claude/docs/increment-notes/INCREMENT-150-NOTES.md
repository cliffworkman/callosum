# Increment 150 — Multi-provider Settings UI (#39, part 2)

## Implemented

The Settings → AI features section becomes **provider-aware**, completing #39 (the engine shipped in inc 149).

- **`app/backend/api/routers/settings.py`** — `PUT /settings` extended: `provider` (allowlisted → 422 on unknown),
  per-provider `api_key` via `api_key_provider` (default: the active provider; gemini stays the inc-146 `api_key`
  field), `local_base_url` (**loopback-validated → 422** otherwise), `model`. `SettingsStatus` gained `provider`,
  `local_base_url`, `model`, and `provider_keys_set` (which cloud providers have a key — **never a key value**); the
  active-provider key status drives `api_key_set`/`source`. **`POST /settings/test-key` is now provider-aware** —
  it validates the active provider via `providers.complete()` (cloud still egress-gated; a loopback local provider
  runs regardless and only ever hits the loopback endpoint). The gemini-only `_ping_gemini` was removed (rule #5).
- **`app/frontend/js/35_settings.jsx`** (`AiSettings`) — a **Model provider** dropdown (Gemini / OpenAI / Anthropic
  / Local). Cloud providers show a key field (+ a per-provider "Get a key →" link) + the **Allow AI features**
  egress toggle; **Local** shows a `base_url` field + a "nothing leaves your machine — no consent needed" note and
  **no egress toggle**. The inc-147 Test button reads "Test key" (cloud) / "Test connection" (local). Reuses the
  existing settings recipes (`.settings-input` on the `<select>`); no new CSS.

## Key technical detail

The **local-no-egress** claim is enforced in **two** places: the settings-write boundary (`PUT` 422s a non-loopback
`local_base_url`) AND `complete()` (inc 149). So a non-loopback "local" endpoint can never be stored, and
`requires_egress("local") == False` stays honest. Per-provider keys are **write-only over the wire** — `GET
/settings` reports only `provider_keys_set` booleans + the active source, never a value (the inc-146 secrecy test
still holds). Switching providers in the UI clears the stale key input + test result.

## Audit

Addendum to `.claude/security-audits/2026-06-26_multi-provider-llm.md` **PASS** — the `PUT` schema extension
(provider allowlist, loopback-422 at the write boundary, per-provider key isolation + write-only, provider-aware
test-key). No new endpoint path, no new dependency, no migration.

## Manual verification

**Headed, no cloud egress** (`.local/visual/drive_inc150_provider_ui.py`): a fake loopback OpenAI-compatible server;
provider=Local + that base_url + egress OFF → the AI section shows the base_url field (no key field, no egress
toggle), **Test connection** succeeds against the loopback server, and **0 requests hit any cloud LLM host**;
switching to OpenAI reveals the key field + egress toggle. 0 console/page errors.

## Pytest

**550** (+4 net: `test_settings.py` provider set/422, loopback-only base_url, per-provider key isolation,
local-test-without-egress; the inc-147 test-key tests updated to monkeypatch `providers.complete`; a redaction
test moved to `test_providers.py`). `ruff` clean; QA surface **109/109 API + 559/559 FE, 0 uncovered**
(`route_35_settings.md` extended); help corpus AI/privacy sections updated (`HELP-DOCS-SYNCED` → 150). No migration.

## This completes #39 (multi-provider BYOK: engine inc 149 + Settings UI inc 150)

**The BYOK follow-on batch is done:** inc 147 Test-key · inc 148 synthesis nudge · inc 149 provider engine · inc 150
provider UI. NEXT (deferred): OS-keychain key storage (the documented hardening, ties to desktop-shell packaging);
migrate the help-assistant to a per-provider model where useful; real OpenAI/Anthropic/Ollama round-trips are the
user's manual check with a real key / local server.
