# Increment 170 — Google Docs SP2: the Apps Script cite-while-you-write add-on

The third word-processor adapter's add-on (after LibreOffice + Word), riding the inc-169 cloudflared bridge. A
Google Docs sidebar that cites from the LOCAL callosum library: search → insert → refresh (renumber + bibliography)
→ style switch. Reaches callosum over `https://callosum.clffwrkmn.net` with the inc-168 bearer token; the bridge's
cite-only ingress (inc 169) keeps it to the citation endpoints.

## Implemented (all in `adapters/googledocs/`, no callosum code change)
- **`gdocs_core.js`** — the PURE request/response mapping, the Zotero-pattern helpers (NamedRange name / the
  DocumentProperties side-store / the insertion-order list). The **same file** is both `node --test`-ed AND loaded
  by the Apps Script project: in Node it `module.exports`; in Apps Script (V8) `module` is undefined so the IIFE
  sets `globalThis.CallosumCore`, which `Code.gs` calls — **no duplication**, and the bug-prone mapping is covered.
- **`gdocs_core.test.js`** — `node --test` **10/10** (authorLabel/search-rows, csl-first, buildDocumentRequest
  positional ids + defaults, inTextResults, bibliographyEntries split/trim, order parse/serialize/append-dedupe,
  parseItems malformed→[], rangeName).
- **`Code.gs`** — the Apps Script glue (untestable outside Google's cloud): `onOpen`/`showSidebar`; Settings
  (UserProperties: bridge URL + token; **token never returned** to the sidebar); `_fetch` (UrlFetchApp,
  `Authorization: Bearer`, friendly 401/404/4xx); `searchPapers` (`GET /papers?q=`), `insertCitation`
  (`POST /papers/export` csl-json → a `[…]` placeholder wrapped in a NamedRange + CSL-JSON in DocumentProperties +
  the id appended to the order → Refresh), `refreshDocument` (collect live citations in insertion order, prune
  dead ids, `POST /citations/render-document`, write each NamedRange's text back, rebuild the **References** block),
  `listStyles`/`setStyle`. DOM helpers `_wrapNamedRange` / `_setRangeText` (replace + **recreate** the range — the
  setString-destroys-the-mark trap, as in LibreOffice) / `_rebuildBibliography`.
- **`sidebar.html`** — the HtmlService UI (connection settings, style picker, search→Insert, Refresh), `google.script.run`.
- **`appsscript.json`** — V8; OAuth scopes `documents.currentonly` + `script.external_request` + `script.container.ui`.
- **`README.md` §7** — the install (bound-script paste, or `clasp push`) + use runbook + the verification-reality +
  v1-limits notes; the Status note updated (SP1 + SP2 both ship).

## Key technical detail
- **Citation model (Zotero pattern):** each citation = a Google Docs **NamedRange** (`CALLOSUM_CITATION_<uuid>`)
  whose cited work's CSL-JSON lives in **DocumentProperties** (`cite:<uuid>`); an **insertion-order** id list lives
  in DocumentProperties (`CALLOSUM_ORDER`). The add-on **never formats** — citeproc does (server-side via
  `/citations/render-document`), so output matches the in-app "Cite as…". Credits the Zotero `CSL_CITATION`
  embedded-CSL-JSON *pattern* (THIRD-PARTY-NOTICES.md), as the LO/Word adapters do.
- **Order is insertion-order (v1):** `refreshDocument` renders in the order ids were inserted, not true document
  position (reliable document-order scanning of NamedRanges in Apps Script is hard + untestable here) — so
  cut/paste-reordering a citation isn't reflected on Refresh. A documented v1 limit; true doc-order is a follow-up.
- **No callosum change:** reuses `/papers?q=`, `/papers/export` (csl-json), `/citations/render-document`,
  `/citations/styles` — all already audited + pytest-tested. No new endpoint/surface/migration/dependency.

## Verification reality
The in-Docs glue (`Code.gs`, `sidebar.html`) runs only in Google's cloud — exercised by no one in this repo; it
ships best-effort-correct per the Apps Script docs. The value is the **pure mapping** (`gdocs_core.js`, `node --test`
10/10) + the **proven contracts** it calls (the inc-169 bridge was verified live; `/citations/render-document` is
pytest-proven, inc 107). The in-Docs round-trip is the **user's manual check** (install per README §7, with the
tunnel + callosum running).

## Gates
- **Audit `.claude/security-audits/2026-06-28_googledocs-addon.md` PASS** (token now also in Google UserProperties
  — the user's opt-in, inherent to a cloud add-on; minimal OAuth scopes; egress = cite metadata to the user's own
  bridge with their token, the same posture the inc-169 audit already covers; cite-only ingress still the hard
  boundary; no callosum code change; no dependency).
- **Principles:** a field-placer reusing the audited citeproc render — formatting only, no new claim/signal →
  non-triggering (Suggest, deferred to SP3, would ride the same inc-156 contract).
- **QA (rule #10):** no new callosum API/FE surface (an external add-on reusing existing endpoints) → surface map
  unchanged (**121/121 API + 604/604 FE, 0 uncovered**), no new route — like the inc-157 LibreOffice suggest macro.
- **Help corpus:** the Remote-access note now mentions the Google Docs add-on (`HELP-DOCS-SYNCED` → 170).

## Pytest / checks
**619** unchanged (SP2 touches no Python app code; only `adapters/googledocs/` + docs). `node --test` 10/10;
`node --check` on `gdocs_core.js` + `Code.gs`; `appsscript.json` valid JSON; `ruff` clean. No frontend rebuild.

## Next
- **SP3:** Suggest-from-the-selection (`/citations/suggest`, inc 156) + Flatten (live → static) + true
  document-order scanning. Then the user's live in-Docs check (install + cite end-to-end).
- This completes the cite-while-you-write surfaces: **LibreOffice** (inc 108/162) + **Word** (164–166) +
  **Google Docs bridge & add-on** (168–170).
