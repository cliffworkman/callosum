# Increment 158 — Contact email (polite-pool mailto) in Settings

A UX fix the user flagged: the Retraction Watch database download (inc 132) hard-required the
`CALLOSUM_CROSSREF_MAILTO` **environment variable** ("Set CALLOSUM_CROSSREF_MAILTO to download…"), while
everything else configurable now lives in Settings (the inc-146 BYOK pattern). Now a single **Contact email** in
**Settings → Metadata access** supplies the polite-pool contact for **all** the public metadata APIs — Crossref,
OpenAlex, and the Retraction Watch download — overlaying the env vars. Set it once → the RW download (and polite
OpenAlex/Crossref access) just works, no env var needed.

## Implemented

- **`app/backend/app_settings.py`** — `set_contact_email` / `stored_contact_email` (file-stored, **not** a
  secret) + `resolved_mailto(env_var)` = `stored_contact_email() or os.environ.get(env_var)`. One stored email
  overlays **both** `CALLOSUM_CROSSREF_MAILTO` and `CALLOSUM_OPENALEX_MAILTO`. `CONTACT_EMAIL_MAX_LEN = 254`.
- **The 4 metadata clients** — `CrossrefClient`, `RetractionWatchClient`, `OpenAlexClient`,
  `OpenAlexAuthorClient` now resolve their mailto via `resolved_mailto(...)` (UI contact email overlays the env
  var) instead of reading `os.environ` directly (the now-unused `import os` was dropped from each). The RW
  fail-closed message → "Set a contact email in Settings → Metadata access (or the CALLOSUM_CROSSREF_MAILTO env
  var)…".
- **`routers/settings.py`** — `SettingsStatus` gains `contact_email` (the stored value, for the input) +
  `contact_email_source` (`ui`|`env`|null); `SettingsUpdate` gains `set_contact_email` + `contact_email`
  (`max_length=254` → 422); `PUT` validates (non-empty must contain `@` → 422) + stores.
- **`app/frontend/js/35_settings.jsx`** — a `MetadataSettings` block ("Metadata access" → Contact email +
  Save), placed before My Publications. Shows the env-source note when set via env.

## Key technical detail

- **Not a secret.** Unlike the API key, the contact email is **sent to public metadata APIs** as the polite-pool
  contact (exactly as the env vars did) — so it's stored in the local file (not the OS keychain) and **is**
  returned by `GET /settings` (the input value + source). No new egress vector: the email was already
  transmitted to Crossref/OpenAlex/RW when the env var was set; this only moves the config to the UI.
- **One email, all pools.** `resolved_mailto` is the single overlay used by all four clients, so the user sets
  their email once and it applies to Crossref + OpenAlex + Retraction Watch (the natural mental model).
- **Import direction:** the clients (`integrations/`) top-level-import `from app.backend.app_settings import
  resolved_mailto` — acyclic (app_settings imports only stdlib + optional keyring; `integrations/api_cache.py`
  already imports `app.backend.*`, establishing the direction).

## Principles / security

- **No new claim/signal** — a config affordance. **Audit:** an **addendum** to
  `.claude/security-audits/2026-06-26_byok-api-key.md` (the `PUT /settings` schema gained a field) — additive
  non-secret field, validated at the boundary (max_length + `@`), no new egress/host/dependency/migration; the
  email reaches only the public metadata APIs it was always destined for. **PASS.**
- **Rule #10:** `route_35_settings.md` (+ a Metadata-access step + 422 assertion) and `route_40_retraction_watch.md`
  (the error-message + "settable in Settings" notes) updated; **no new endpoint** (reuses `GET`/`PUT /settings`)
  → surface **110/110 API + 573/573 FE, 0 uncovered**.
- help corpus: the Retraction Watch + Settings sections now point to **Settings → Metadata access** instead of
  the env var (`HELP-DOCS-SYNCED` → 158).

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc158_contact_email.py`, with `CALLOSUM_SETTINGS_PATH` isolated to a
temp file): open Settings → Metadata access → save `qa@example.com` → the "Saved" note shows and `GET /settings`
returns `contact_email: "qa@example.com"`, `contact_email_source: "ui"`; reload + reopen → the field is
pre-filled (persisted). **0 console / 0 page / 0 genai.** (The real RW CSV download with the UI-set email is the
user's spot-check — same as inc 132.)

## Pytest

**578** (+6 `test_settings.py`: contact-email store/clear + `resolved_mailto` overlay; env fallback + stored-wins;
PUT/GET round-trip + source; env-source reporting; invalid-email 422; `RetractionWatchClient` picks up the stored
email with no env var). `ruff` clean (the 4 clients' unused `os` imports removed); build + assembly green; no
migration.

## Next

Back to **#30** — a formatted "Cite as… (style)" copy in the in-app Cite pane (the deadline-writer persona's
ask, via the inc-106 render engine), then SP2 beyond-library discovery.
