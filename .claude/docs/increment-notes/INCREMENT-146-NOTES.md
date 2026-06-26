# Increment 146 — BYOK: Gemini API key + egress consent from the Settings UI

## Implemented

A **bring-your-own-key** path: set the Gemini API key **and** turn on data egress from **Settings → AI features**,
instead of editing environment variables — so a GitHub user can enable AI summaries end-to-end from the UI.

- **`app/backend/app_settings.py`** (new) — a tiny local settings store: `load_settings`/`set_api_key`/
  `set_data_egress`/`stored_api_key`/`stored_egress`. Reads/writes a JSON file at **`~/.callosum/app-settings.json`**
  (override `CALLOSUM_SETTINGS_PATH`) — *outside the git repo and the project's synced Dropbox folder*, so the
  secret never travels with a copy of the library `.sqlite`. Atomic write (`os.replace`), best-effort `chmod 0600`,
  fail-soft load (absent/malformed → `{}`).
- **`integrations/gemini/generator.py`** — `GeminiConfig.from_environment()` now **overlays** the stored key +
  egress over the env defaults (lazy import of `app_settings`). Stored value wins when present; env is the
  fallback. Because all ~12 call sites already build config via `from_environment()`, BYOK reaches every AI
  feature (summaries, axis-suggest, research-summary, overview) with **zero call-site changes**. `resolved_api_key()`
  already prefers `self.api_key` over `os.getenv` → stored key wins.
- **`app/backend/api/routers/settings.py`** (new) — `GET /settings` returns **status only**
  (`api_key_set`, `api_key_source` ∈ {ui, env, null}, `data_egress_enabled`, `egress_source`) — **never the key
  value**; `PUT /settings` (`set_api_key` + `api_key` + `data_egress_enabled`) sets/clears the key / toggles egress.
  Registered in `app.py`.
- **`app/frontend/js/35_settings.jsx`** — an **AI features** section: a password-masked key input + Save/Clear (+
  a "Get a key →" link), and an **"Allow AI features (sends text to Google)"** toggle (default OFF). Self-fetches
  `GET /settings`; PUTs on save/toggle. One CSS class `.settings-keyrow` (tokens only, rule #8).

## Key technical detail

The egress invariant (#3) is **unchanged**: egress stays default-OFF (stored flag absent → falls back to the env
flag, default off), and the `EgressGated*` gate logic + `DataEgressDisabledError` path are byte-identical. The UI
toggle is an *explicit, labeled, default-off opt-in* — it only moves the consent surface from an env var to a UI
control. A present key does **not** bypass the gate (test: stored egress OFF + a key set → generation still raises
`DataEgressDisabledError` before any network). The overlay means a `.env`-based setup is unaffected (no stored value
→ env default), and the **stored value wins** only once the user touches the UI.

## Principles / security

- **Gate run:** the only honesty-relevant axis is the egress posture; it is preserved (default-off, explicit opt-in,
  gate logic untouched), so this is principle-aligned, not a relaxation. The key is **write-only over the wire** —
  `GET` exposes a set/not-set status, never the value (inspectability without exposing the secret).
- **Audit:** `.claude/security-audits/2026-06-26_byok-api-key.md` **PASS** — secret never logged/returned/committed
  (home-dir file, atomic write, 0600 best-effort); key length-capped (≤512 → 422); fixed/env settings path (no
  traversal); no new dependency; egress-off still blocks (negative-path tested).
- **Storage choice (user's call):** a gitignored local file (the user picked it over OS-keychain / DB / in-memory);
  realized at `~/.callosum/` to keep the secret out of the synced DB. OS-keychain is the documented hardening
  upgrade for the eventual desktop-shell packaging.

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc146_byok.py`): open Settings → AI features renders with the egress
toggle **OFF**; paste a fake key → Save → status shows "A key is saved on this machine" and `GET /settings` body
contains **no** key value; toggle egress on → off (writes the local store, **0 genai requests**); Clear → "Not set".
0 console/page errors.

## Pytest

**532** (+8 `test_settings.py`: store round-trip/clear, GET-never-returns-key, PUT set/clear/toggle, oversized-key
422, env-source status, config overlay of stored key + stored egress, egress-off-still-blocks). Route-surface test
extended (`/settings` GET + PUT). `ruff` clean; build + assembly green; QA surface **108/108 API + 547/547 FE,
0 uncovered** (`route_35_settings.md` extended with the BYOK steps + the key-secrecy / egress-default-off
assertions). No migration.

## Next

OS-keychain storage (hardening, ties to the desktop-shell packaging); a "test this key" button (a cheap egress-gated
ping); surfacing the egress state in the synthesis pane (an inline "AI is off — enable in Settings" nudge).
