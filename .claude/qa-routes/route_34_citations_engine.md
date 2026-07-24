<!-- qa-coverage
api: /citations*
fe: 25_detail.jsx, 35d_citation_styles.jsx, 37_cite.jsx
-->

# ROUTE 34 - Citations engine

**Tier:** 1 local-stateful
**Goal:** Exhaust citation style listing, single citation rendering, and document bibliography rendering.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.
- **Style previews are fixed-example-only (inc 365).** `POST /citations/styles/preview` renders bundled fictional
  records through local citeproc. A preview request must never include or retrieve library text and must fire no
  external request.
- **Installed style XML is server-owned (inc 366).** Runtime style ids resolve only to bundled files or
  server-generated `custom-*` files under the local settings directory. A request-supplied id/path/URL must never
  select arbitrary XML. The Node sidecar receives validated XML from Python and performs no network request.
- **Personal-style lifecycle is local and guarded (inc 367).** Export returns only the selected validated
  `custom-*` CSL with a constrained portable id marker. Removal cannot accept a path, remove a bundled/default
  style, or orphan an installed dependent. Neither operation may make an external request.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open "Cite as..." for a seeded paper. Confirm styles load (`GET /citations/styles`) with stable ids plus parsed
   CSL metadata, locales, favorite/recent state, and a valid application default. Search by full name, acronym,
   journal/discipline term, and no-match; query length above 120 → 422.
2. Switch styles and render (`POST /citations/render`). Confirm preview updates, copy succeeds, and missing CSL fields degrade cleanly.
3. Render a bibliography/document export (`POST /citations/render-document`) using multiple selected papers. Confirm ordering, escaping, and selected style are honored. With `chicago-notes-bibliography`, send ordered clusters with `noteIndex` 1, 2, and 3 (repeat the first source at 3); confirm the repeated note uses citeproc's subsequent-note form rather than repeating the first-note form.
4. Preview APA, IEEE, and Chicago notes (`POST /citations/styles/preview`) with en-US/en-GB. Confirm the response
   contains formatted citation/note/bibliography examples for the fixed fictional records, including first and
   subsequent note positions where applicable. Unknown style/locale → 422; unavailable engine → 503; rendering
   failure → 502.
5. Update (`PUT /citations/styles/preferences`) the application default, locale, favorite, and recent style.
   Reload and confirm bounded persistence, deduplicated recents, and that recording a document style does not
   implicitly replace the application default. Unknown style/locale → 422.
6. Install a valid local style (`POST /citations/styles/install`) and use its server-generated `custom-*` id with
   both `/citations/render` and `/citations/render-document`. Confirm output follows the custom layout and the
   style remains available after app restart. Validation preflight returns `already_installed` for an exact
   duplicate and `update_available` for changed content under the same canonical CSL id, without writing. A direct
   changed install without `replace:true` remains 409. A dependent style resolves only through an installed
   canonical parent. Bundled canonical ids cannot be replaced.
7. Export the personal style (`GET /citations/styles/{style_id}/export`): confirm a `.csl` attachment with the
   exact portable `callosum-style-id` marker, no private path, and no mutation. Reinstall it against a clean local
   settings directory and confirm the same id plus `already_installed` on an exact repeat. A malformed/misplaced
   marker fails validation. Bundled/unknown export → 409/404.
8. Remove the personal style (`DELETE /citations/styles/{style_id}`). Confirm application-default and
   installed-parent removal → 409 with no mutation; bundled/unknown removal → 409/404. After choosing another
   default and removing dependents first, deletion succeeds, cleans Favorites/Recent, and subsequent render by
   the removed id → 422.
9. Try an unknown style, no selected papers, malformed paper id state, and `noteIndex` values that are negative, above 5000, fractional, or boolean. Confirm validation messaging/422 responses and no crash.
10. Confirm no citation surface presents papers as good/bad or ranked by hidden score.

## Pass criteria

- Style list, citation preview, copy, and document render complete.
- 0 console/page errors and 0 genai-host requests.
- Bad inputs fail cleanly; output is visibly tied to the selected style and note position.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_34_citations_engine.md` + `screenshots/` (see `_TEMPLATE.md`).
