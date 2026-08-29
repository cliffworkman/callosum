<!-- qa-coverage
api: /settings, /settings/providers, /settings/providers/{pid}, /settings/test-key, /settings/repair-summary-cache, /settings/access-token, /access/recover, /citations/styles*, /integrations/libreoffice/*, /integrations/word/*, /usage/events, /usage/summary, /usage/export, /usage/clear
fe: 35_settings.jsx, 35b_providers.jsx, 35ca_citation_style_provenance.jsx, 35cb_citation_style_editor.jsx, 35d_citation_styles.jsx, 01_recovery.jsx, 35f_usage.jsx
-->

# ROUTE 35 - Settings

**Tier:** 1 local-stateful
**Goal:** Exhaust settings controls and persistence boundaries without touching external services. **Inc 450**
adds the local-only, zero-egress "Your usage" dashboard (backlog #38A) — the one Settings toggle on this whole
route that defaults **ON**, since nothing it does ever leaves the machine.

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
- **Personal CSL export/removal is portable and guarded (inc 367).** Download must return only the selected
  personal CSL with its stable Callosum id marker; reinstalling that file on another device retains the id.
  **Remove** warns that existing documents require reinstallation and is disabled for the application default.
  The backend also refuses bundled styles and parents of installed dependents. Any external request or arbitrary
  filesystem read/delete is **Critical**.
- **Repository/URL CSL import is explicit and guarded (inc 368).** Installed/Favorites/Recent search and preview
  remain zero-egress. **Repository** may fetch only the fixed Zotero catalog/style host after an explicit Search
  or Install; the typed query is matched locally and must not be transmitted to Zotero. **Import URL** may fetch
  only after its explicit submit and must reject non-HTTPS/non-443 URLs, credentials/fragments, private/local DNS
  answers or connected peers, an unsafe redirect hop, excessive redirects/dependency depth, and bodies above
  1000 KB. Both paths must preflight a complete dependent-style parent chain before writing and reuse the exact
  duplicate/update confirmation. Any library/PDF/manuscript text in an external request is **Critical**.
- **Personal-style source editing is local and revision-safe (inc 370).** Only independent personal styles may
  be edited directly; bundled and dependent styles must first be duplicated. Validation and draft preview use
  the unsaved XML locally, never library text or egress. Save must preserve the canonical CSL id, re-run schema,
  macro, and citeproc validation, and reject a stale exact revision rather than overwrite another edit.
- **CSL lifecycle provenance is inspectable and explicit (inc 369).** Every import must pass the official local
  CSL 1.0.2 schema plus macro-reference validation. Personal detail shows local/repository/URL/copy source and
  available timestamps. No update request may occur until **Check for updates** is pressed; a confirmed update
  consumes the exact preflighted chain and includes an installed custom parent. **Duplicate** must create a new
  independent style/canonical id without mutating its source. A dependent copy that still requires its parent,
  hidden background update request, or unlabelled remote source is High.
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
- **Local usage instrumentation is on by default and zero-egress (inc 450, backlog #38A).** Unlike every other
  toggle on this page, `GET /settings`'s `usage_events_enabled` is **true** on a clean instance — this is
  intentional (nothing here ever leaves the machine, so the egress-consent "off by default" pattern doesn't
  apply) and must NOT be flagged as a regression against the usual off-by-default standing assertion. `GET
  /usage/summary`/`GET /usage/export` must never contain any field beyond `event_type`/`count`/`duration_ms`/
  `created_at`/`label`/`enabled` — a payload/content/title/query field appearing anywhere in either response is
  **Critical**. `POST /usage/clear` and `GET /usage/export` must work identically whether the toggle is on or
  off — gating only recording, never reading/exporting/clearing, is **Critical** if violated. No request to any
  external host from any `/usage/*` call is **Critical**.
- **Word add-in is local-only + zero-egress (inc 164; category/batch/order/section/link surface incs 521-525).** The `/integrations/word/*` routes serve FIXED bundled task-pane files + the manifest from `adapters/word/`; an undefined filename must be a plain 404 (no traversal). The served `taskpane.html`/`taskpane.js` may reference Microsoft's `appsforoffice.microsoft.com` office.js (the required Office SDK) but **must not** reference any AI/library host (`generativelanguage`/`openai`/`anthropic`/`clffwrkmn.net`) — such a reference is **Critical**. The served category editor, checkbox/batch controls, staged order editor, current-section insert/remove controls, and opt-in bibliography-link checkbox are statically guarded by the Word Node suite; actual document-setting/render behavior remains an explicit MANUAL Word check, not Playwright-drivable. `POST /integrations/word/install` opens a local folder and degrades to `{opened:false}`, never 500.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow
- `POST /usage/events` with an unknown `event_type` -> 422; with `count: 0` or `count: 5000` -> 422
- toggle "Track local usage" OFF, trigger a real instrumented action (e.g. Copy BibTeX) -> the count does not
  increase; **Export usage log** and **Clear usage log** still work while off

## Steps

1. Open settings. Confirm all controls render: theme, AI features (key + egress toggle), local maintenance, default axis cutoff, hide uncertain, watched-folder auto-rescan, help assistant section, **Metadata access** (contact email), and **Your usage**.
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
   Select a personal style and click **Download .csl**: confirm the browser downloads a valid CSL backup and the
   catalog remains unchanged. Reinstall that file against a clean settings directory and confirm its exact local
   id is retained. While it is the application default, **Remove** is disabled with an instruction to choose
   another default. Change the default, click **Remove**, and cancel the warning: the style remains. Confirm the
   warning: the style disappears, Favorites/Recent are cleaned, and the UI selects the application default.
   Removing a parent with an installed dependent reports that the dependent must be removed first. The warning
   explicitly says existing documents will not render until the same CSL style is reinstalled and recommends
   exporting first. Open **Repository**, search for `Journal of Experimental Psychology`, and confirm the only
   external request is the fixed catalog fetch: the query text must not occur in any outbound URL/body. Install a
   dependent journal result and confirm the requested style appears as Personal together with any non-bundled
   parent, then previews through that parent. Repeat the search within six hours and confirm the in-memory catalog
   avoids another fetch. Use **Import URL** with a valid independent style and with a dependent style; both install
   through the same update confirmation. Direct API negatives: HTTP, credentials, fragment, non-443 port,
   loopback/private literal, a hostname resolving or connecting privately, redirect to private, oversized body,
   dependency cycle/depth, invalid CSL, and bundled canonical duplicate all fail before persistence.
   Confirm a schema-invalid attribute and missing macro produce specific local validation errors. Select local,
   repository, URL, and duplicated styles and verify the displayed source/timestamps. Reload to prove provenance
   persistence; corrupt the provenance sidecar and verify the catalog fails soft as source-not-recorded. Confirm
   merely opening/searching/previewing sends no update request. Press **Check for updates** on a remote style:
   current and available states name the check, and accepting an update consumes its preflight token without a
   second fetch. Duplicate bundled, independent-personal, and dependent styles; each copy gets a new canonical id,
   selects immediately, previews, and is independent while the original remains unchanged.
   Select an independent personal style and click **Edit source**. Change its title and citation affixes, then
   **Validate & preview**: the fictional preview changes but the installed catalog and source remain unchanged.
   Save and confirm the same local style id and canonical CSL id remain selected, the edited title/output persist
   after reload, and the source reports its local edit timestamp. Make an out-of-band second save using the
   original revision and confirm 409 with no overwrite. Changing the canonical `<id>`, introducing schema-invalid
   CSL, or making the style dependent fails before persistence. Bundled and dependent styles offer
   **Duplicate to edit** instead; the new independent copy opens in the editor while the source remains unchanged.
   Close a dirty editor and cancel the warning to keep editing, then discard it and confirm no mutation.
   Desktop/mobile flows complete with zero console/page errors. Installed-only operations have zero external
   requests; repository/URL operations have only the explicit expected requests and send no library content.
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
17. **Your usage (inc 450, backlog #38A).** Confirm the **Your usage** card renders with the toggle already
   **ON** (the one on-by-default control on this page) and the honest disclosure paragraph naming what's counted
   (citation export / duplicate resolution / metadata re-resolve / locating a quote / reviewing a flagged
   reference) and what never is (PDF text, searches, library contents). Confirm five count rows render, each
   showing "N all time · M in the last 30 days," in the fixed order above — never sorted by count. Perform a
   real instrumented action elsewhere (e.g. Work → Cite → "Open source region" on a real match, or Copy BibTeX
   from a paper card) and return here: confirm the matching count increased by exactly the expected amount.
   Click **Export usage log**: confirm a `callosum-usage-log.json` download containing only
   `event_type`/`count`/`duration_ms`/`created_at` per row — no title, DOI, query text, or any other field.
   Click **Clear usage log**, confirm the browser prompt, confirm: all counts reset to 0, and a confirmation
   message reports the number of events removed. Toggle **Track local usage** OFF; repeat the same real
   instrumented action; confirm the count does NOT increase. Toggle it back ON. Confirm zero requests to any
   external host anywhere in this flow.
18. **Plugins (backlog #41, inc 483).** Under the **Plugins** card, confirm the toggle is **OFF** on a clean
   instance, with copy explaining this is a foundation for a future curated, review-gated plugin store and
   that nothing is installable yet. Turn it ON; `GET /settings` now reports `plugins_enabled:true`. Confirm no
   install/download/plugin-list UI appears anywhere in the app as a result — the toggle is deliberately inert;
   nothing else in the app currently reads this flag. Reload and confirm the toggle stays on (persisted).
   Toggle it back OFF. No genai/external request from any of this.

## Pass criteria

- Every settings control is reachable, responsive, and has clear state.
- 0 console/page errors and 0 genai-host requests.
- Settings do not create hidden composite scores or accusation language.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_35_settings.md` + `screenshots/` (see `_TEMPLATE.md`).
