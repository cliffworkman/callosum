# Increment 164 — Microsoft Word add-in (Office.js), SP1: HTTPS spine + search-and-insert task pane

**What the user asked for:** the **Word add-in** — the second word-processor adapter after LibreOffice (inc 108/162).
Built as **Architecture A** (the user's choice, asked + answered in plan mode): **local HTTPS, desktop-only, zero
egress**. The make-or-break constraint from research: an Office.js task pane must be served over **HTTPS** and
**cannot reliably `fetch()` `http://localhost`** (and Word-on-the-web can't reach localhost at all). So callosum
serves the task pane over HTTPS **same-origin** with its API (`https://localhost:8443`) — the add-in reaches the
local library with **no egress and no CORS change**; the one cost is a one-time local-cert trust step.

SP1 is the spine that ships something + proves the platform end-to-end (read + write in real Word): **search your
library → insert a formatted citation as static text at the cursor**. Live fields + renumbering = SP2; suggest/
style/flatten = SP3 (a 3-SP arc mirroring LibreOffice).

## Implemented

- **`adapters/word/`** (new — shipped client code, sibling of `adapters/libreoffice/`; exempt from the 600-line cap):
  - `manifest.xml` — XML add-in-only manifest, fixed GUID `b7e8c1d2-…`, SourceLocation `https://localhost:8443/…
    /taskpane.html`, a ribbon button **Home → Callosum → Show Citations** (VersionOverrides v1.0), `ReadWriteDocument`.
  - `taskpane.html` — loads office.js (MS CDN) + `taskpane_core.js` + `taskpane.js` + `taskpane.css`; search box + results.
  - `taskpane_core.js` — **pure logic, no Office.js/DOM** (UMD: `module.exports` in Node, `globalThis.CallosumCore`
    in the browser): `authorLabel`, `formatSearchRows`, `buildRenderRequest`, `inTextFromRender`.
  - `taskpane.js` — thin Office.js glue: `Office.onReady` → debounced search → `fetch('/papers?q=')`; on pick →
    `fetch('/citations/render')` → `Word.run(ctx => getSelection().insertText(inText, replace))`. **Same-origin relative
    URLs.** API data is HTML-escaped before any `innerHTML`.
  - `taskpane.css`, `README.md` (the 3-step setup + credit + limitations), `taskpane_core.test.js` (8 `node --test` cases),
    `icon.png` (the brand favicon, served as the ribbon icon at all sizes).
- **`app/backend/api/routers/word.py`** (new) — explicit per-filename `FileResponse` routes (`taskpane.html|js|core.js|
  css|icon.png` via a fixed `_FILES` media-type allowlist; **no `{filename}` param → no traversal**) +
  `GET /integrations/word/manifest.xml` + `POST /integrations/word/install` (opens the add-in folder via the OS handler
  — sideloading can't be automated on desktop — graceful `{opened:false}`, never 500). Registered in `app.py`.
- **`tools/run_https.py`** (new) — locates the `office-addin-dev-certs` cert (`~/.office-addin-dev-certs/localhost.{crt,key}`)
  and runs uvicorn with TLS on :8443; clear message if the cert is absent.
- **`app/frontend/js/35_settings.jsx`** — a `WordSettings` section (Download manifest link + Open-add-in-folder button +
  the 3-step note + the desktop-only/HTTPS caveat), wired into `SettingsModal` after `LibreOfficeSettings`.

## Key technical detail

- **Same-origin is the whole trick.** Because the task pane is served from `https://localhost:8443` and its `fetch`es
  go to the same origin, CORS never applies (CORSMiddleware only handles cross-origin) — so the existing GET-only
  allowlist is untouched **and** nothing leaves the machine. The plan's "no CORS change / no egress" both fall out of A.
- **office.js cannot take SRI.** It is the one external `<script>`; Microsoft updates it in place at the fixed
  `…/lib/1/hosted/office.js` URL, so a pinned `integrity` hash would break the add-in on every Office update (unlike the
  inc-53 immutable cdnjs pins). Documented exception (in the audit + README).
- **No headless Word.** Unlike LibreOffice's UNO socket, Word can't be driven headlessly — so the **in-Word round-trip
  is the user's manual check**. Verification here = pytest (the routes) + `node --test` (the pure logic) + a headed
  Settings drive (the section renders + the assets serve, no egress). The pure logic lives in `taskpane_core.js` precisely
  so most of it *is* testable.
- **No new dependency.** office.js is CDN-loaded by Word; `office-addin-dev-certs` is run via `npx` (not committed);
  `node --test` is built into Node. No migration, no egress.

## Manual verification script (the in-Word check is the user's — desktop Word only)

1. `npx office-addin-dev-certs install` (once).
2. `python tools/run_https.py` → open `https://localhost:8443`.
3. Settings → **Microsoft Word add-in → Download manifest**; sideload it (Windows: Trusted Add-in Catalog folder;
   Mac: `~/Library/Containers/com.microsoft.Word/Data/Documents/wef/`). See `adapters/word/README.md`.
4. Word → **Home → Callosum → Show Citations** → pick a style, search, click a result → the formatted citation is
   inserted at the cursor.

**Automated (this increment):**
- `node --test "adapters/word/*.test.js"` → 8/8 (the pure logic).
- Headed, no egress (`.local/visual/drive_inc164_word.py`): the WordSettings section renders, the manifest serves with
  SourceLocation `https://localhost:8443/…`, the task pane references office.js + **no** AI/library host, Open-add-in-folder
  posts a result (OS opener stubbed) → **PASS**, 0 console/page/genai.

## Gates
- **Audit** `.claude/security-audits/2026-06-27_word-addin.md` **PASS** (no traversal; HTTPS local cert, no secret;
  egress NONE; office.js = MS SDK / SRI-not-applicable; no new dep; local-only → pre-hosted-deploy gate recorded).
- **Principles (rule #9):** non-triggering (packaging + thin field-placer; reuses the audited citeproc render).
- **QA (rule #10):** `route_35_settings.md` extended with `/integrations/word/*` + a Word step + a local-only/no-egress
  standing assertion; surface **120/120 API + 599/599 FE, 0 uncovered**.
- **Help corpus:** new "Citing in Microsoft Word (desktop)" section; `HELP-DOCS-SYNCED` → 164.

## Pytest
**+7** (`tests/test_word_addin.py`): file/manifest serving + content types, manifest SourceLocation + GUID, unknown
file → 404 (no traversal), install opens folder / degrades, no-AI-host in the served assets. Full suite green; `ruff`
clean; build + assembly in sync.

## Next
**SP2 (inc 165)** — live cite-while-you-write: insert as Content Controls carrying CSL-JSON + a Refresh that scans in
document order → `POST /citations/render-document` → renumber + bibliography (the Zotero-parity loop). **SP3 (inc 166)**
— Suggest / style picker / flatten. (Word-on-the-web + Google Docs ride the future authenticated clffwrkmn.net relay.)
Carried: the **`40_app.jsx` 630/600 split** (rule #1).
