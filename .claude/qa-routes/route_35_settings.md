<!-- qa-coverage
api: /settings, /settings/providers, /settings/providers/{pid}, /settings/test-key, /settings/repair-summary-cache, /settings/access-token, /access/recover, /citations/styles*, /integrations/libreoffice/*, /integrations/word/*
fe: 35_settings.jsx, 35b_providers.jsx, 35d_citation_styles.jsx, 01_recovery.jsx
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
- **Custom providers are endpoint-egress-gated + write-only (inc 256).** The unified roster (`GET /settings/providers`) + custom CRUD (`POST /settings/providers`, `PUT`/`DELETE /settings/providers/{pid}`) never expose a key value — a key string in any `GET /settings/providers` body is **Critical**. A custom provider's id is a **server-generated** uuid (never client-supplied); a builtin id (`gemini`/`openai`/`anthropic`/`local`) accepted by `PUT`/`DELETE /settings/providers/{pid}` (not 400) is a bug. The `gemini` SDK wire format must **not** be assignable to a custom provider (`wire_format:"gemini"` on `POST` → **422**). Egress for a custom provider is **endpoint-based**: with egress OFF, a custom provider whose `base_url` is a cloud host must be gated exactly like Gemini (no outbound call from **Test key**); a custom provider whose `base_url` is loopback is honestly no-egress. A custom cloud `base_url` that fires an LLM request while egress is OFF is **Critical** (invariant #3).
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.
- **Citation styles are local document formatting (inc 365).** Catalog search, fixed-example preview, favorites,
  recents, locale, and application default must fire no external request. Preview text must be the named fictional
  examples, never library content. Changing the application default affects new documents only; an existing
  word-processor document must retain its embedded style and locale.
- **Custom CSL install is local and bounded (inc 366).** `POST /citations/styles/validate` preflights text from
  one local `.csl` file without writing; `POST /citations/styles/install` performs the explicit mutation. Neither
  accepts a path or URL. DTD/entities, oversized/deep/overpopulated XML, invalid CSL metadata or layout, and
  missing dependent parents must fail before persistence. Bundled styles are immutable. Any external request from
  install/validation is **Critical**.
- **LibreOffice install is local-only (inc 162).** The plugin install/download builds + opens a FIXED bundled `.oxt`; it must fire **no egress** (no genai/external host) and must degrade gracefully (`{opened:false}` + a download fallback), never 500. A request to any external host from the install path is **Critical**.
- **Remote access is OFF by default + token-gated (inc 168).** On a clean instance, `GET /settings` reports
  `remote_access_enabled:false`; the gate is a no-op (the data API works with no token). Enabling without a token →
  **422** (would lock the local UI out). `POST /settings/access-token` returns the token value **once**; `GET
  /settings` must report `access_token_set` but **never the token value** (the value in the GET body is **Critical**).
  With remote access ON, a data request with no/wrong bearer token → **401** (`GET /health` + `GET /` stay exempt).
  The egress posture is unchanged for everyone who leaves it off.
- **Lockout recovery is disable-only + local-possession-gated (inc 254).** With remote access ON and no valid
  token, a data call 401s and the app shows ONE honest recovery overlay (`AccessLockOverlay`), never a "start the
  backend / uvicorn" box. `POST /access/recover` with `{}` writes a one-time code to a LOCAL file and returns
  **only its path** — the code value appearing in the response body is **Critical** (it would let a remote/tunnel
  caller recover). A valid code turns remote access **OFF**; a wrong/expired code leaves the gate **ON**. The path
  never reveals the token and can only DISABLE remote access. It is gate-exempt (the user is locked out) but
  rate-limited (429).
- **Word add-in is local-only + zero-egress (inc 164).** The `/integrations/word/*` routes serve FIXED bundled task-pane files + the manifest from `adapters/word/`; an undefined filename must be a plain 404 (no traversal). The served `taskpane.html`/`taskpane.js` may reference Microsoft's `appsforoffice.microsoft.com` office.js (the required Office SDK) but **must not** reference any AI/library host (`generativelanguage`/`openai`/`anthropic`/`clffwrkmn.net`) — such a reference is **Critical**. `POST /integrations/word/install` opens a local folder and degrades to `{opened:false}`, never 500. (The in-Word task-pane round-trip is desktop-Word-only and is the user's MANUAL check — not Playwright-drivable.)

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open settings. Confirm all controls render: theme, AI features (key + egress toggle), local maintenance, default axis cutoff, hide uncertain, watched-folder auto-rescan, help assistant section, and **Metadata access** (contact email).
2. Toggle theme on/off. Confirm app chrome changes and PDF page rendering remains light/readable.
3. Move the default-axis-cutoff slider through min/mid/max. Confirm labels/count previews stay signal-only.
4. Toggle hide-uncertain and watched-folder auto-rescan. Reload and confirm intended persistence or documented session-only behavior.
5. Open and close help-assistant settings. With egress unset, no genai request is allowed.
6. **AI features (BYOK).** Confirm the section renders: a (password-masked) Gemini API key input + Save, and an "Allow AI features" toggle that is **OFF** on the clean instance. Paste a fake key, Save; reload and confirm a "key saved" status with **no key value shown anywhere** (inspect `GET /settings` — body must not contain the pasted string). Toggle egress on then off; confirm no genai request fires (egress unset; this only writes the local store). Clear the key; confirm it reverts to "Not set".
7. **Test key (egress-gated).** With a key saved and **egress OFF**, click **Test key** → the result reports "Turn on Allow AI features…" and **no genai/`generativelanguage` request fires** (the egress toggle's promise: off ⟹ no outbound call). `POST /settings/test-key` returns `{ok:false}`; the response/DOM never contains the key value.
8. **Unified provider roster (inc 149/150/256).** The AI-features section is now ONE editable list (`GET /settings/providers`): the four presets — **Gemini / OpenAI / Anthropic / Local** — pre-seeded first, each a collapsible card showing a wire-format badge + an **Active** pill or a **Use** control. Expand a cloud preset → its (password-masked) key field + a **Get a key →** link + an endpoint line ("Sends to …"); expand **Local** → a loopback `base_url` field + a "nothing leaves your machine" note. Click **Use** on OpenAI → it becomes Active and the model chooser appears; switching providers must reset the model override (no cross-provider model leak). Save a loopback `base_url` on Local → accepted; a non-loopback → **422**. With Local active + egress off, **Test connection** must not hit any cloud LLM host.
   - **Add a custom provider.** Click **+ Add provider** (a green add affordance): fill Name (`e.g. DeepSeek`), Base URL (`https://api.example.com/v1`), API format dropdown (default **Anthropic messages (/v1/messages)**; also **Chat completions (/chat/completions)** and **Responses (/responses)** — never a Gemini option), a Model list (+ Add model), and an optional key → **Add provider** (`POST /settings/providers`). It appears in the roster as a non-builtin card with **Edit** + **Delete**. Edit its name/URL/models (`PUT /settings/providers/{pid}`) and Save; **Delete** removes it (`DELETE /settings/providers/{pid}`) and, if it was active, resets active to Gemini. Adversarial: empty name / non-http base_url / `wire_format:"gemini"` via the API → **422**; `PUT`/`DELETE` a builtin id → **400**; edit/delete an unknown id → **404**. Inspect `GET /settings/providers` — the body must contain NO key value for any provider (only `key_set`).
9. **Citation styles (inc 365).** Deep-link to `#citation-styles`; the Settings workspace and full-width
   **Citation styles** card must open and scroll into view. Search by full name, acronym (`MLA`), discipline
   (`psychology`), and a no-match value; queries longer than 120 characters fail with 422. Switch among
   **Installed / Favorites / Recent**, favorite and unfavorite a style, and reload to verify persistence. Select a
   style and locale; confirm its canonical title, citation format, independent/dependent status, field summary,
   and description render without exposing a raw CSL id as the primary label. Preview must call
   `POST /citations/styles/preview` and show the fixed fictional Rivera/Chen and Okafor examples formatted by the
   chosen style. Make IEEE the application default, reload, and confirm it remains selected and appears in Recent;
   changing the default must not mutate any existing document. Restore APA/en-US. At `375x812`, confirm the list,
   detail, preview, default action, and long labels remain reachable with no horizontal overflow.
   Click **Install .csl** and choose a valid independent test style: confirm it appears as **Personal style**,
   searches by title/field, previews through citeproc, can become the default/favorite/recent, and persists after
   reload. Re-import the exact file → "already installed" with no rewrite. Change its title/content while retaining
   its canonical `<id>` → an explicit replacement confirmation; cancel leaves the installed version unchanged,
   confirm updates it under the same local id. Try a bundled canonical id, malformed XML, a non-CSL extension,
   DTD/entity declarations, missing title/id/citation layout, an unknown dependent parent, and a file above
   1000 KB: each fails with a specific reason and no new catalog row. Expected preflight failures create no
   console error. A dependent style whose parent is installed may install and must preview through that parent.
10. **Local maintenance.** Click **Repair synthesis cache** (`POST /settings/repair-summary-cache`). It must report scanned and removed row counts, fire no external request, and not delete saved summaries, verified citations, chunks, or evidence records. A response that claims to "verify" or improve synthesis quality is a wording bug: this only deletes malformed cached AI draft rows.
11. **Metadata access (inc 158).** Under **Metadata access**, save a **Contact email** (e.g. `you@example.com`); `GET /settings` reports `contact_email` + `contact_email_source: "ui"`. Submit `not-an-email` → **422**, nothing persisted. The email is NOT a secret (it IS returned by `GET /settings` — it's the polite-pool contact for Crossref/OpenAlex/Retraction Watch), but saving it must fire **no genai request**. Clear it → reverts to empty.
12. **LibreOffice plugin (inc 162).** Under **LibreOffice plugin**, confirm the section renders (Install plugin button + Download .oxt link + the "restart Writer / app must be running" note). The **Download .oxt** link (`GET /integrations/libreoffice/plugin.oxt`) serves a non-empty `.oxt` (a zip). Clicking **Install** (`POST /integrations/libreoffice/install`) returns 200 with `{opened: …, detail}` and fires **no genai/external request** (it only opens a local file handler); on a headless runner where no handler exists it must report `opened:false` with a download fallback, not crash.
13. **Microsoft Word add-in (inc 164).** Under **Microsoft Word add-in (desktop)**, confirm the section renders (the 3-step one-time setup note + a **Download manifest** link + an **Open add-in folder** button). The **Download manifest** link (`GET /integrations/word/manifest.xml`) serves a non-empty XML manifest whose SourceLocation is `https://localhost:8443/integrations/word/taskpane.html`. `GET /integrations/word/taskpane.html` serves the task pane (its only external reference is Microsoft's office.js — never an AI/library host). Clicking **Open add-in folder** (`POST /integrations/word/install`) returns 200 `{opened, detail}`, fires **no genai/external request**, and on a headless runner reports `opened:false` without crashing. `GET /integrations/word/secrets.txt` → 404 (no traversal). *(The actual in-Word task pane is desktop-Word-only — a documented MANUAL check, not driven here.)*
14. **Remote access (inc 168).** Under **Remote access (Google Docs)**, confirm the toggle is **OFF** on a clean
   instance. Turn it ON → an access token is shown **once** (a readonly field); `GET /settings` now reports
   `remote_access_enabled:true` + `access_token_set:true` with **no token value in the body**. Confirm the data API
   still works in this browser (the token was saved to `localStorage`). Toggle OFF → back to frictionless. (Direct
   API: `PUT /settings {remote_access_enabled:true}` with no token minted → 422; with remote ON, `GET /papers` with
   no/`wrong` bearer → 401; `GET /health` → 200.) No genai/external request from any of this.
15. **Lockout recovery (inc 254).** With Remote access ON, clear this browser's token
   (`localStorage.removeItem('callosum.accessToken')`) and reload → the app shows the **AccessLockOverlay**
   ("Remote access is on — this browser isn't authorized"), **not** a "start the backend" error, and the library
   errbox behind it reads "Remote access is locked." Tab **I have the token** → paste the token → Unlock → the app
   reloads and loads normally. Tab **I lost it — turn remote access off** → **Start reset** (`POST /access/recover
   {}`) returns a `code_path` (the response body must NOT contain the code); read the code from that file, paste
   it, **Turn off remote access** (`POST /access/recover {code}`) → `recovered`, the app reloads, `GET /settings`
   reports `remote_access_enabled:false`. Direct API negatives: `{code:"wrong"}` → `invalid` + gate stays ON
   (`GET /papers` still 401); an oversized code → 422; rapid repeats → 429. No genai/external request from any of it.
16. Resize to mobile while settings is open; confirm controls remain reachable and labels do not overflow.

## Pass criteria

- Every settings control is reachable, responsive, and has clear state.
- 0 console/page errors and 0 genai-host requests.
- Settings do not create hidden composite scores or accusation language.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_35_settings.md` + `screenshots/` (see `_TEMPLATE.md`).
