# Increment 171 — Google Docs SP3: Suggest-from-the-selection + Flatten

Parity for the Google Docs add-on (mirrors Word SP3): suggest citations for the sentence you're writing, and
flatten the live citations to plain text when done. All in `adapters/googledocs/`, **no callosum code change**.

## Implemented
- **Suggest-from-the-selection** — `Code.gs::suggestFromSelection` reads the selected text (`_selectionText`,
  concatenated across range elements), else the cursor's paragraph (`_cursorParagraphText`), picks the query via
  the pure `CallosumCore.pickQueryText`, and POSTs `CallosumCore.buildSuggestRequest(query, 8)` to
  **`/citations/suggest`** (inc 156). The sidebar renders `CallosumCore.formatSuggestRows` —
  `[stance] Author Year · match N.NN — "quote…"` (the quote IS the reason — signal not verdict) — each with an
  **Insert** button (reuses `insertCitation`).
- **Insert now collapses a selection to its END** (`_cursorOrSelectionEnd`): if no cursor but a selection is
  active (the Suggest flow), it sets the cursor to the selection's end so the citation lands *after* the sentence
  rather than replacing it (mirrors Word SP3's collapse-to-end). `insertCitation` uses it.
- **Flatten** — `Code.gs::flattenCitations` removes every `CALLOSUM_CITATION_*` + the `CALLOSUM_BIBLIOGRAPHY`
  NamedRange and clears the DocumentProperties side-store. **The text stays** — Apps Script `NamedRange.remove()`
  keeps the underlying content (unlike the LibreOffice ReferenceMark, which deleted it; like Word Content
  Controls). One-way: Refresh no longer manages the citations. A two-click confirm in the sidebar (no dialog
  dependency).
- **`gdocs_core.js`** gained `pickQueryText` / `buildSuggestRequest` (caps text 4000) / `formatSuggestRows`
  (mirrors the Word core exactly) → `node --test` **13/13** (+3). **`sidebar.html`** gained a "Suggest from
  selection" button (reuses the results list) + a "Flatten…" button (armed-confirm). README §7 updated (Suggest +
  Flatten now ship; only true document-order remains deferred).

## Key technical detail / gotchas
- **Order is still insertion-order** (the deferred SP3 piece): reliable NamedRange *document-order* scanning in
  Apps Script is genuinely hard (no stable element identity / `getNamedRanges` isn't doc-ordered) and untestable
  from the repo — left as the remaining follow-up. Cut/paste-reordering a citation isn't reflected on Refresh.
- Flatten is safe in GAS because `remove()` keeps text — the opposite of the LibreOffice trap; no re-insert needed.
- The selection is still active when the user clicks Insert from the Suggest rows (sidebar clicks don't clear the
  doc selection), so collapse-to-end fires; after the first insert it leaves a cursor (sequential inserts append).

## Gates
- **Audit:** no new gate — reuses `/citations/suggest` (audited inc 156) over the already-audited bridge (inc 169)
  + the add-on audit (inc 170); Flatten is local DOM; no new endpoint/secret/external-fetch-type/dependency.
- **Principles:** Suggest surfaces stance + the verbatim quote and the author picks (the inc-156 posture — signal
  not verdict, candidates-not-verdicts) — the add-on only displays the proven contract → non-triggering.
- **QA (rule #10):** no new callosum API/FE surface → surface map unchanged (121/121 API + 604/604 FE).
- **Help corpus:** the Remote-access note already points at the add-on (unchanged this increment).

## Verification reality
The in-Docs glue (`Code.gs`, `sidebar.html`) runs only in Google's cloud — the user's manual check. The value is
the pure mapping (`gdocs_core.test.js` 13/13) + the proven contracts (`/citations/suggest` inc-156-tested; the
bridge live-verified inc 170). `node --check` on `gdocs_core.js` + `Code.gs`; manifest unchanged.

## Pytest / checks
**619** unchanged (SP3 touches no Python). `node --test` 13/13; `node --check` clean; `ruff` n/a (no Python
changed); no frontend rebuild.

## Next
- **Deferred:** true document-order scanning on Refresh (the insertion-order v1 limit). Then the user's live
  in-Docs check (install per README §7 with the tunnel + callosum running) — the only thing that exercises the glue.
- **This completes the Google Docs adapter (SP1 bridge inc 168/169 + SP2 add-on inc 170 + SP3 inc 171)**, and with
  it the cite-while-you-write surfaces: LibreOffice (108/162) + Word (164–166) + Google Docs (168–171).
