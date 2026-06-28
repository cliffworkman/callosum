<!-- qa-coverage
api: /settings, /settings/test-key, /settings/access-token, /integrations/libreoffice/*, /integrations/word/*
fe: 35_settings.jsx
-->

# ROUTE 35 - Settings

**Tier:** 1 local-stateful
**Goal:** Exhaust settings controls and persistence boundaries without touching external services.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **BYOK key secrecy (inc 146).** `GET /settings` must return STATUS ONLY — the response body containing the literal API-key value is **Critical**. The "Allow AI features" egress toggle must default to OFF on a clean instance; defaulting ON without an explicit toggle is **Critical** (invariant #3).
- **Local = no egress, honestly (inc 149/150).** With provider = **Local** and a loopback `base_url`, no request to a cloud LLM host (`generativelanguage` / `api.openai.com` / `api.anthropic.com`) may fire — that is the whole point. A non-loopback local `base_url` accepted by `PUT /settings` (no 422) is **Critical** (it would let data leave under a "no egress" label).
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.
- **LibreOffice install is local-only (inc 162).** The plugin install/download builds + opens a FIXED bundled `.oxt`; it must fire **no egress** (no genai/external host) and must degrade gracefully (`{opened:false}` + a download fallback), never 500. A request to any external host from the install path is **Critical**.
- **Remote access is OFF by default + token-gated (inc 168).** On a clean instance, `GET /settings` reports
  `remote_access_enabled:false`; the gate is a no-op (the data API works with no token). Enabling without a token →
  **422** (would lock the local UI out). `POST /settings/access-token` returns the token value **once**; `GET
  /settings` must report `access_token_set` but **never the token value** (the value in the GET body is **Critical**).
  With remote access ON, a data request with no/wrong bearer token → **401** (`GET /health` + `GET /` stay exempt).
  The egress posture is unchanged for everyone who leaves it off.
- **Word add-in is local-only + zero-egress (inc 164).** The `/integrations/word/*` routes serve FIXED bundled task-pane files + the manifest from `adapters/word/`; an undefined filename must be a plain 404 (no traversal). The served `taskpane.html`/`taskpane.js` may reference Microsoft's `appsforoffice.microsoft.com` office.js (the required Office SDK) but **must not** reference any AI/library host (`generativelanguage`/`openai`/`anthropic`/`clffwrkmn.net`) — such a reference is **Critical**. `POST /integrations/word/install` opens a local folder and degrades to `{opened:false}`, never 500. (The in-Word task-pane round-trip is desktop-Word-only and is the user's MANUAL check — not Playwright-drivable.)

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open settings. Confirm all controls render: theme, AI features (key + egress toggle), default axis cutoff, hide uncertain, watched-folder auto-rescan, help assistant section, and **Metadata access** (contact email).
2. Toggle theme on/off. Confirm app chrome changes and PDF page rendering remains light/readable.
3. Move the default-axis-cutoff slider through min/mid/max. Confirm labels/count previews stay signal-only.
4. Toggle hide-uncertain and watched-folder auto-rescan. Reload and confirm intended persistence or documented session-only behavior.
5. Open and close help-assistant settings. With egress unset, no genai request is allowed.
6. **AI features (BYOK).** Confirm the section renders: a (password-masked) Gemini API key input + Save, and an "Allow AI features" toggle that is **OFF** on the clean instance. Paste a fake key, Save; reload and confirm a "key saved" status with **no key value shown anywhere** (inspect `GET /settings` — body must not contain the pasted string). Toggle egress on then off; confirm no genai request fires (egress unset; this only writes the local store). Clear the key; confirm it reverts to "Not set".
7. **Test key (egress-gated).** With a key saved and **egress OFF**, click **Test key** → the result reports "Turn on Allow AI features…" and **no genai/`generativelanguage` request fires** (the egress toggle's promise: off ⟹ no outbound call). `POST /settings/test-key` returns `{ok:false}`; the response/DOM never contains the key value.
8. **Multi-provider (inc 149/150).** Use the **Model provider** dropdown. Selecting **OpenAI / Anthropic** shows that provider's key field + the egress toggle; selecting **Local model** shows a `base_url` field + a "nothing leaves your machine" note and **no egress toggle**. Save a loopback `base_url` (e.g. `http://127.0.0.1:11434`) → accepted; a non-loopback URL → **422**. With Local selected + loopback + egress off, **Test connection** must not hit any cloud LLM host.
9. **Metadata access (inc 158).** Under **Metadata access**, save a **Contact email** (e.g. `you@example.com`); `GET /settings` reports `contact_email` + `contact_email_source: "ui"`. Submit `not-an-email` → **422**, nothing persisted. The email is NOT a secret (it IS returned by `GET /settings` — it's the polite-pool contact for Crossref/OpenAlex/Retraction Watch), but saving it must fire **no genai request**. Clear it → reverts to empty.
10. **LibreOffice plugin (inc 162).** Under **LibreOffice plugin**, confirm the section renders (Install plugin button + Download .oxt link + the "restart Writer / app must be running" note). The **Download .oxt** link (`GET /integrations/libreoffice/plugin.oxt`) serves a non-empty `.oxt` (a zip). Clicking **Install** (`POST /integrations/libreoffice/install`) returns 200 with `{opened: …, detail}` and fires **no genai/external request** (it only opens a local file handler); on a headless runner where no handler exists it must report `opened:false` with a download fallback, not crash.
11. **Microsoft Word add-in (inc 164).** Under **Microsoft Word add-in (desktop)**, confirm the section renders (the 3-step one-time setup note + a **Download manifest** link + an **Open add-in folder** button). The **Download manifest** link (`GET /integrations/word/manifest.xml`) serves a non-empty XML manifest whose SourceLocation is `https://localhost:8443/integrations/word/taskpane.html`. `GET /integrations/word/taskpane.html` serves the task pane (its only external reference is Microsoft's office.js — never an AI/library host). Clicking **Open add-in folder** (`POST /integrations/word/install`) returns 200 `{opened, detail}`, fires **no genai/external request**, and on a headless runner reports `opened:false` without crashing. `GET /integrations/word/secrets.txt` → 404 (no traversal). *(The actual in-Word task pane is desktop-Word-only — a documented MANUAL check, not driven here.)*
12. **Remote access (inc 168).** Under **Remote access (Google Docs)**, confirm the toggle is **OFF** on a clean
   instance. Turn it ON → an access token is shown **once** (a readonly field); `GET /settings` now reports
   `remote_access_enabled:true` + `access_token_set:true` with **no token value in the body**. Confirm the data API
   still works in this browser (the token was saved to `localStorage`). Toggle OFF → back to frictionless. (Direct
   API: `PUT /settings {remote_access_enabled:true}` with no token minted → 422; with remote ON, `GET /papers` with
   no/`wrong` bearer → 401; `GET /health` → 200.) No genai/external request from any of this.
13. Resize to mobile while settings is open; confirm controls remain reachable and labels do not overflow.

## Pass criteria

- Every settings control is reachable, responsive, and has clear state.
- 0 console/page errors and 0 genai-host requests.
- Settings do not create hidden composite scores or accusation language.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_35_settings.md` + `screenshots/` (see `_TEMPLATE.md`).

