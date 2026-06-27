# Increment 165 — Word add-in SP2: live cite-while-you-write (Content Controls + Refresh/renumber + bibliography)

**What the user asked for:** push ahead with SP2 of the Word add-in (after SP1's HTTPS spine, inc 164). The user
**has no Word**, so this is acknowledged as theoretical-in-Word regardless — which sharpened the verification posture
(lean on the pure-logic `node --test` + the already-proven backend contract; ship the Office.js glue
best-effort-correct).

SP2 upgrades SP1's "insert a formatted citation as static text" to the **Zotero-style cite-while-you-write loop**:
live citations that re-render + renumber across the whole document, with a managed bibliography.

## Implemented (all in `adapters/word/`, client code — no backend change)

- **`taskpane_core.js`** (pure logic, `node --test`-able) — new SP2 helpers; the SP1-only per-item helpers
  (`buildRenderRequest`/`inTextFromRender`) were removed (rule #5, superseded by the document path):
  - `encodeCitationTag(items)` / `isCitationTag(tag)` / `decodeCitationTag(tag)` — the content-control tag is
    `"CALLOSUM_CITATION <base64 of {items:[csl,…]}>"` (UTF-8-safe base64 via TextEncoder/btoa, unicode author names
    round-trip); malformed → `null` (never guesses). `CITATION_PREFIX` + `BIB_TAG` constants.
  - `buildDocumentRequest(itemsList, style, locale)` — the `/citations/render-document` body from the per-cluster
    CSL-JSON item arrays in document order (positional `citationID`s `c0,c1,…`).
  - `inTextResults(data)` (→ the per-cluster `text` strings in order) + `bibliographyText(data)` (→ `bibliography_text`).
  - `firstCslRecord(arr)` (the CSL record from a `/papers/export` csl-json array) + `authorLabel`/`formatSearchRows` (SP1).
- **`taskpane.js`** (thin Office.js glue, rewritten):
  - **Insert** = `POST /papers/export {format:"csl-json"}` → `Word.run`: `getSelection().insertText("…")` →
    `.insertContentControl()` around it → set `.tag = encodeCitationTag([csl])`, `.appearance = Hidden` → then **Refresh**.
  - **Refresh** = `Word.run`: `body.contentControls.load("items/tag")`; collect citation CCs **in document order** +
    the bibliography CC; `POST /citations/render-document` (`buildDocumentRequest`); write each CC's text back with
    `cc.insertText(text, "Replace")` (Office.js keeps the control); find-or-create the **References** CC
    (`insertParagraph("References")` + a CC tagged `CALLOSUM_BIBLIOGRAPHY`) and set its text; one `ctx.sync()`.
  - Search + the style dropdown (which now feeds Refresh) are unchanged from SP1.
- **`taskpane.html`/`.css`** — a **Refresh / renumber + bibliography** button.
- **`taskpane_core.test.js`** — rewritten for the SP2 helpers (8 cases): search rows, `firstCslRecord`, the
  encode/decode round-trip (incl. unicode), `isCitationTag` discrimination, malformed/empty → null, the
  document-request builder, and the response extractors.

## Key technical detail
- **No backend change.** SP2 reuses `POST /papers/export` (inc 70) + `POST /citations/render-document` (inc 107) —
  both already audited + pytest-tested. So **no new endpoint, surface, migration, egress, dependency, or audit gate**;
  the inc-164 audit posture (same-origin loopback, zero egress, no traversal) is unchanged.
- **Content Controls over ADDIN fields** (the plan's default) — the more mature/robust Office.js primitive. The
  `.tag` is the carrier (content controls have no arbitrary data slot like fields' `.data`), so the discriminator
  prefix + base64 payload ride together; the rendered citation is the control's text. Positional `citationID`s mean
  no persisted per-citation id is needed (the response echoes input order).
- **GOTCHA (carry to Google Docs):** `cc.insertText(text, "Replace")` **preserves** the content control (unlike
  LibreOffice's `setString` which destroys a ReferenceMark); `body.contentControls.items` iterate in document order.
- **Verification reality.** There is no headless Word **and the user has no Word**, so the Office.js glue
  (`taskpane.js`) is exercised by no one — it ships best-effort-correct per the Office.js docs. The pure logic lives
  in `taskpane_core.js` precisely so the testable part is large.

## Manual verification (theoretical — needs desktop Word, which the user does not have)
Same setup as SP1 (`adapters/word/README.md`): cert + `tools/run_https.py` + sideload → Word → Callosum → Show
Citations → search + click → a live citation inserts; **Refresh** renumbers + builds the References block.

**Automated (this increment):**
- `node --test "adapters/word/*.test.js"` → **8/8** (encode/decode incl. unicode + malformed→null; request/response mapping).
- `pytest tests/test_word_addin.py` → **10/10** (the rewritten assets still serve with the right types + no AI host).
- Surface **120/120 API + 599/599 FE, 0 uncovered** (no surface change); `ruff` clean; no frontend rebuild (only `adapters/word/`).

## Gates
- **Audit:** no new gate trigger (no new endpoint/fetch/dependency; reuses audited same-origin endpoints; zero egress).
- **Principles (rule #9):** non-triggering (a thin field-placer; formatting stays in citeproc).
- **QA (rule #10):** no new surface; `route_35_settings.md`'s Word section already flags the in-Word round-trip as a
  MANUAL check.
- **Help corpus:** "Citing in Microsoft Word" updated to live citations + Refresh (`HELP-DOCS-SYNCED` → 165).

## Pytest
**611** unchanged (SP2 is adapter/frontend-only; the existing `tests/test_word_addin.py` re-confirms the rewritten
assets). `node --test` 8/8.

## Next
**SP3 (inc 166)** — **Suggest** (`/citations/suggest`, relevance-from-the-sentence — our novel complement) + a
one-click whole-document **style switch** + **Flatten** (live → static). Then **Google Docs** via the future
authenticated **clffwrkmn.net relay** (its own design-led increment). Carried: the **`40_app.jsx` 630/600 split**
(rule #1).
