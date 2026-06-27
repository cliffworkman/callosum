# Increment 166 — Word add-in SP3: parity (Suggest + one-click style switch + Flatten)

**What the user asked for:** "SP3!!!!!" — finish the Word adapter. SP3 completes parity with the LibreOffice plugin:
**Suggest from the sentence**, a **one-click whole-document style switch**, and **Flatten** (live → static). All in
`adapters/word/`, reusing already-audited+tested endpoints — **no backend change**. The user has no Word, so (as in
SP1/SP2) the in-Word Office.js glue ships best-effort-correct and the verification leans on the pure-logic
`node --test` + the proven backend contracts.

## Implemented (all in `adapters/word/`)

- **`taskpane_core.js`** — new SP3 pure helpers (`node --test`-able):
  - `pickQueryText(selectionText, paragraphText)` — the Suggest query = the highlighted selection, else the
    paragraph the cursor sits in (trimmed; both empty → `""`).
  - `buildSuggestRequest(text, topK)` — the `/citations/suggest` body; **caps text at 4000** (the endpoint's limit),
    default `top_k` 8, `evaluate:true` (so each candidate carries a stance).
  - `formatSuggestRows(suggestions)` — pick-rows `"[stance] Author Year · match N.NN — \"quote…\""` keyed by
    `paper_id`; missing stance → `[?]`; id-less dropped. (The quote IS the reason — signal not verdict.)
- **`taskpane.js`** — Office.js glue:
  - **Suggest** — `Word.run` reads `getSelection().text` + the first paragraph's text → `pickQueryText` →
    `POST /citations/suggest` → render rows in a separate `#suggestions` list → pick → `insertCitation(paper_id)`.
  - **Insert now collapses to the selection END** (`getSelection().getRange(Word.RangeLocation.end)` →
    `insertText`), so a sentence-scoped Suggest inserts *after* the sentence instead of replacing it (also safer for
    the search path if text was selected).
  - **One-click style switch** — the style dropdown's `change` calls `refreshDocument()` (re-render the whole doc in
    the new style) + persists the choice per-document via `Office.context.document.settings` (loaded on
    `Office.onReady`, so a programmatic set doesn't fire `change`).
  - **Flatten** — two-click confirm (button text toggles "Click again to flatten"; a 4s reset) → `Word.run`:
    `cc.delete(true)` on every Content Control whose tag is a citation or the bibliography (keeps the rendered text,
    drops the live field; one-way). No `window.confirm`/dialog dependency.
- **`taskpane.html`/`.css`** — a **Suggest from the sentence** button + a `#suggestions` list + a **Flatten** button;
  a `.secondary` button recipe.
- **`taskpane_core.test.js`** — +3 SP3 tests (→ **11** total): `pickQueryText` precedence, `buildSuggestRequest`
  4000-cap/defaults, `formatSuggestRows` formatting incl. missing-stance → `[?]` + id-less dropped.

## Key technical detail
- **No backend change.** SP3 reuses `POST /citations/suggest` (inc 156), `GET /citations/styles` (inc 106),
  `POST /citations/render-document` (inc 107), `POST /papers/export` (inc 70) — all already audited + pytest-tested.
  So **no new endpoint, surface, migration, egress, dependency, or audit gate**; the inc-164 audit posture
  (same-origin loopback, zero egress) is unchanged.
- **GOTCHA (carry to Google Docs):** insert at the selection END (collapse-to-end) so a sentence-scoped Suggest
  doesn't overwrite the sentence; `cc.delete(true)` keeps content (flatten); `Office.context.document.settings`
  is the per-document persistence slot (saveAsync).
- **Verification reality.** No headless Word + the user has no Word → the Office.js glue (`taskpane.js`) is exercised
  by no one; it ships best-effort-correct per the Office.js docs. The testable surface (the pure logic) is `node
  --test` **11/11**, and every endpoint it calls is covered by the Python suite.

## Manual verification (theoretical — needs desktop Word, which the user does not have)
Setup per `adapters/word/README.md` (cert + `tools/run_https.py` + sideload). Then: Suggest from a sentence →
candidates with stance + quote → insert; change the style dropdown → whole doc re-renders; Flatten → citations
become static text.

**Automated (this increment):**
- `node --test "adapters/word/*.test.js"` → **11/11**.
- `pytest tests/test_word_addin.py` → **10/10** (the rewritten assets serve with the right types + no AI host).
- Surface **120/120 API + 599/599 FE, 0 uncovered** (no surface change); `ruff` clean; no frontend rebuild.

## Gates
- **Audit:** no new trigger (no new endpoint/fetch/dependency; reuses audited same-origin endpoints; zero egress).
- **Principles (rule #9):** non-triggering — a thin field-placer; Suggest surfaces ranked candidates with their
  quote as the reason (the inc-156 posture), the author picks, nothing auto-inserts; formatting stays in citeproc.
- **QA (rule #10):** no new surface; `route_35_settings.md`'s Word section already flags the in-Word flow as MANUAL.
- **Help corpus:** "Citing in Microsoft Word" now covers Suggest / style switch / Flatten (`HELP-DOCS-SYNCED` → 166).

## Pytest
**611** unchanged (adapter/frontend-only). `node --test` 11/11.

## Next
**This completes the Word adapter (SP1 inc 164 + SP2 inc 165 + SP3 inc 166).** Then **Google Docs** via the future
authenticated **clffwrkmn.net relay** (its own design-led increment: a tunnel + auth + rate-limiting on callosum
[Security baseline] + the add-on, opt-in egress); and/or beyond-library discovery to feed Suggest (#30 SP2).
Carried: the **`40_app.jsx` 630/600 split** (rule #1).
