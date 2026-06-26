# Security audit — BYOK: Gemini API key + egress consent in Settings (inc 146)

**Date:** 2026-06-26
**Trigger (audit gate):** a new API endpoint (`GET`/`PUT /settings`); new secret-handling (the user's Gemini
API key set from the UI); a new file-write path (the local settings file). No new third-party dependency
(the gitignored-local-file storage choice avoids `keyring`).

## What it does

Lets a "bring-your-own-key" user set their Gemini API key + turn on data egress **from the Settings UI**
instead of environment variables, so AI features are usable end-to-end without editing a `.env`. The key +
egress consent persist in a small JSON file at `~/.callosum/app-settings.json` (overridable via
`CALLOSUM_SETTINGS_PATH`) — **outside the git repo and outside the project's synced Dropbox folder**, so the
secret never travels with a copy of the library `.sqlite`. Env vars (`GOOGLE_API_KEY` /
`CALLOSUM_ALLOW_DATA_EGRESS`) remain the fallback, so existing setups are unaffected.

## Threat review

- **Secret handling.** The key is **write-only over the wire**: `PUT /settings` accepts it; `GET /settings`
  returns **status only** (`api_key_set`, `api_key_source` ∈ {ui, env, null}) — *never the key value*. The key
  is never logged (the store writes JSON; nothing logs its contents) and never committed (the file is in the
  user's home dir, outside the repo; `os.replace` atomic write; best-effort `chmod 0600`). `resolved_api_key()`
  passes it only to `genai.Client(api_key=...)` — the same single sink as today.
- **Input validation (rule #4).** `PUT /settings` caps the key at 512 chars (real keys ~40) → oversized = 422;
  `data_egress_enabled` is a strict bool; the key is trimmed; empty/whitespace clears it. No shell, no SQL.
- **Egress invariant (#3) — unchanged.** Egress is still **default-OFF**: the stored flag is absent until the
  user explicitly toggles it, and absent → falls back to the env flag (default off). The UI toggle is an
  *explicit, labeled, default-off opt-in* — it moves the consent surface from an env var to a UI control, it
  does **not** weaken the gate. The `EgressGated*` wrappers + `DataEgressDisabledError` path are byte-unchanged;
  they just read `GeminiConfig.from_environment()`, which now overlays the stored value over the env default.
- **File-path safety.** The settings path is fixed (`~/.callosum/...`) or from a trusted env override — **never**
  built from request data → no traversal. `mkdir(parents=True, exist_ok=True)` only under the user's home.
- **SSRF / external calls.** None added. The key reaches only the existing Gemini client sink.
- **Supply chain.** No new dependency (stdlib `json`/`os`/`pathlib` only).
- **CORS / exposure.** `PUT /settings` is a mutating endpoint; CORS stays localhost-GET-only, so a browser
  cross-origin `PUT` is blocked. (Pre-deploy note: like all mutating routes, re-review auth before any hosted
  deployment — added to the deployment checklist.)

## Negative-path checks (to record at completion)

- `GET /settings` after setting a key → `api_key_set:true`, **no key value in the body**. ✅ (test)
- `PUT` with a 5000-char key → **422**, nothing written. ✅ (test)
- Egress OFF stored (or unset + env off) → summary generation still raises `DataEgressDisabledError`. ✅ (test)
- Stored key overlays env; stored egress overlays env; both fall back to env when absent. ✅ (test)
- The real settings file is never touched by the suite (conftest points `CALLOSUM_SETTINGS_PATH` at tmp). ✅

## Result

**Security Audit: PASS.** All negative paths confirmed by `tests/test_settings.py` (8 tests) + the headed run
`.local/visual/drive_inc146_byok.py` (PASS): the key never appears in the `GET /settings` body *or* the DOM,
the egress toggle defaults OFF, an oversized key is 422'd with nothing written, and stored-egress-OFF still
raises `DataEgressDisabledError` even with a key present. 532 pytest green; QA surface 108/108 API + 547/547 FE.
(Pre-deploy: the new `PUT /settings` is a mutating route — re-review auth before any hosted deployment; added
to the deployment-checklist class with the other server-side write paths.)
