# Increment 152 — OS-keychain key storage (optional `keyring`, file fallback)

The last deferred #39 item: per-provider BYOK keys can live in the **OS keychain** instead of the gitignored file.

## Implemented

- **`app/backend/app_settings.py`** — an optional keychain layer:
  - `_keyring()` returns the `keyring` module **iff** it's importable AND has a usable backend (not the `fail`
    backend), else `None`. `keychain_available()` exposes that.
  - `get_provider_key(provider)` reads the OS keychain first, then the file — so a pre-keychain key is **never
    lost**. `set_provider_key(provider, key)`, when the keychain is available, writes the vault **and removes any
    plaintext copy from the file** (migration on save); clearing deletes from both. Every keyring call is wrapped
    in `try/except` → graceful fall-through to the file (never crashes).
  - `set_api_key` / `stored_api_key` (the inc-146 gemini entry points) now route through the per-provider layer.
- **`integrations/gemini/generator.py`** — `_resolve_key(provider)` reads via `get_provider_key` (keychain/file) +
  the per-provider env fallback (no longer reads the JSON dict directly).
- **`app/backend/api/routers/settings.py`** — `_stored_key(provider)` uses `get_provider_key`; `SettingsStatus`
  gains `key_storage` ("keychain" | "file") so the UI can show where keys live; the inc-149 `_KEY_FIELD` map (now
  unused here) was removed (rule #5).
- **`app/frontend/js/35_settings.jsx`** — the key-field note reflects `key_storage` ("saved in your OS keychain" vs
  "saved in a local file on this machine").
- **`requirements.txt`** — a commented **optional** entry: `pip install keyring` enables vault storage; it is NOT a
  hard dependency.

## Key technical detail

`keyring` is **optional**. With it absent (the default, incl. dev/CI), everything uses the gitignored file store
exactly as before — so all existing tests + behavior are unchanged. When present, keys move to the OS vault
(encrypted at rest), and a key written before installing keyring still works (file fallback) and migrates to the
vault on the next save. Keys remain **write-only over the wire** — `GET /settings` reports only `provider_keys_set`
+ `key_storage`, never a value. The ethos holds: no new hard dependency.

## Audit

`.claude/security-audits/2026-06-27_keychain-storage.md` **PASS** — a strictly-stronger at-rest store with a safe
fallback; no key loss; no plaintext lingering after migration; fail-closed to the file; keys never logged/returned;
optional dependency.

## Manual verification

Hermetic (`tests/test_settings.py`, +4): an in-memory fake keyring → `set_provider_key` writes the vault not the
file; migration from a file key on re-save; a backend error falls back to the file; `GET /settings` reports
`key_storage`. **Headed, no egress** (`.local/visual/drive_inc152_keystorage.py`): the key-storage note renders
(file branch — keyring not installed here), the key never appears in the DOM, 0 console/page/genai. **The real
OS-vault round-trip (with `keyring` installed) is the user's spot-check** — it writes to the real OS Credential
Manager, so it isn't exercised in CI/dev (the logic is mock-tested; the file fallback is headed-verified).

## Pytest

**556** (+4 `test_settings.py`). `ruff` clean; build + assembly green; QA surface **109/109 API + 561/561 FE, 0
uncovered** (no new surface — `key_storage` is a status field, the UI change is text-only); help corpus + privacy
sections note the keychain option (`HELP-DOCS-SYNCED` → 152). No migration.

## This completes the BYOK deferred-items pass

inc 151 (validation disclaimer + help-assistant toggle) + inc 152 (OS-keychain). With inc 146–150, **the whole BYOK
arc (#10 + #39) and its follow-ons are shipped.** NEXT (truly deferred): a validation-lock "quality" disclaimer is
done as text — a heavier "lock" UX isn't planned; real cloud/Ollama/keychain round-trips are the user's manual
checks. The open backlog below is the next pick.
