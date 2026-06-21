# Increment 82 — Library-card tidy + double-click/text-select fix

Two small library-card UX chores (frontend-only, `app/frontend/js/10_pdf_layer.jsx`).

## Implemented
- **Tidy library cards (drop chunked-row content).** Removed the `{p.chunk_count} chunks` chip from the card
  foot — chunk count is processing-internal detail, not bibliographic. Cards now show title · authors · year ·
  venue + the processing-tier pill, the file-count chip (has-PDF), and the actionable `needs DOI` flag.
  (`p.chunk_count` stays in the API response; only the card stopped displaying it.)
- **Fix double-click vs. text selection.** A card's `onDoubleClick` opened the PDF unconditionally, so
  double-clicking a word in the title (to select/copy it) also opened the PDF. Now it opens **only when the
  double-click did not select text** (`window.getSelection().isCollapsed`): double-click a word → it selects,
  no open; double-click empty card space → opens. Tooltip updated to say so.

## Key technical detail
`isCollapsed` is the right gate: a double-click on a word leaves a non-collapsed selection (a range), while a
double-click on whitespace collapses the selection — and the browser updates the selection on mousedown before
`onDoubleClick` fires, so the check reflects *this* gesture. Text selection wins (the user's stated priority);
opening stays available on the card's non-text area (and via the Detail → Files list).

## Manual verification script
1. Hard-refresh (Ctrl+Shift+R).
2. Confirm library cards no longer show "N chunks"; title/authors/year/venue + tier/file/needs-DOI remain.
3. Double-click a word in a card's title → the word selects (copyable), the PDF does NOT open. Double-click the
   card's empty area → the PDF opens. _(Visual check delegated to the user.)_

## Pytest
**370 passed, 1 skipped** — unchanged (frontend-only; no Python touched). No migration, no endpoint, no egress,
no CSS change (a chip was removed, its class is unaffected). Help corpus unchanged (the "double-click to open"
note still holds).
