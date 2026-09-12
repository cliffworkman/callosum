# Increment 590 — In-reader PDF find/search (backlog #42)

The PDF reader had no in-document find. The website's `cap-pdf-search` claim advertised "PDF text search" for a
feature that was never built (found auditing demo coverage) — so this is both a real feature gap and a website
**over-claim to correct**. This makes the claim true.

## Approach — search the already-rendered text layer, not pdf.js `FindController`
The viewer (`30_viewer.jsx`) uses a **custom** render pipeline: `getDocument` + a manual per-page
`renderTextLayer`, deliberately NOT pdf.js's `PDFViewer`/`EventBus` component stack that `FindController`
requires. Retrofitting that stack would be a large, risky rewrite of the whole viewer. Instead, since every page
already renders real selectable text into `.textLayer span` elements, find searches that DOM directly — fully
local, no new dependency, and it finds exactly what is visually present. (Same "search the text we already have"
spirit as the existing full-text library search.)

## Implemented
- **New `app/frontend/js/30i_pdf_find.jsx`** — a `usePdfFind({ pagesRef, scrollRef })` hook + a presentational
  `PdfFindBar`. The hook:
  - **Pure, unit-testable core:** `findAllMatchStarts(haystack, needle)` (case-insensitive, non-overlapping,
    capped at 500) and `buildPageTextIndex(segments)` (concatenate a page's text nodes + a char-range→node map).
  - **DOM/layout:** for each match, build a `Range` over the mapped text nodes and draw an overlay rect per line
    fragment (`range.getClientRects()` → percentage-of-page) into a per-page `.pdf-find-layer` — mirroring
    `renderUserAnnotations`' overlay pattern. It **never mutates the text layer**, so native selection +
    annotations are untouched, and a match spanning multiple spans/lines paints correctly.
  - Tracks a current match (scrolled into view + `.current` emphasis), wraps prev/next, exposes `recompute()`.
  - Owns the **Ctrl/Cmd+F** listener (guarded on `scrollRef` visibility, so a background viewer never hijacks the
    shortcut and the browser's own find is overridden only for the live reader).
- **`30_viewer.jsx`** (minimal wiring, kept at the 600-line cap): mount the hook, a toolbar **Find** button,
  render `<PdfFindBar>`, and — one line — call `find.recompute(true)` at the end of the page-render effect so
  highlights re-paint after a zoom / fit-mode re-render. Esc-to-close lives on the find input.
- **`styles.css`** — `.pdf-find-bar` reuses the toolbar chrome; match overlays are transient "here"-markers, so
  **amber** (`--flag-soft` / `--flag`), never verified-green / danger-red / provenance-indigo (DESIGN §4). The
  current match is the stronger `--flag`.

## Scope (YAGNI)
Find-in-page only: all-pages search (the viewer renders every page eagerly, so this is what users expect from
Ctrl+F), plain case-insensitive substring, no regex / whole-word / case toggle in v1. Recapturing
`www/shots/app_current.png` + the `.app-map` hotspot redesign the issue bundles is a **separate follow-up**
(keeps this change code-only; avoids website-drift churn here).

## Verification
- **Live Playwright** against the committed real 2-page fixture (`tests/fixtures/seed.pdf`, via the seed
  library's "Renderable Seed Paper"): opened find (Ctrl+F **and** the toolbar button), searched — "signal
  detection" → 1 match correctly on **page 2** (cross-page + phrase-within-span), "Facial"/"social" → page 1;
  "s" → **11 matches**, Next advanced 1→2→3, Prev 3→2, Enter advanced, exactly one `.current` at a time; a
  no-match term → "No matches", 0 overlays; **Esc closed the bar AND cleared all highlights**.
- **Pure matcher** verified standalone (9 assertions: cross-span offset, case-insensitivity, non-overlapping,
  empty-needle/haystack guards). No committed node harness exists for frontend chunks, so this is a dev-time
  check; the DOM behavior is the Playwright run above.
- Frontend rebuilt; `test_frontend_assembly.py` 87 green; line budget OK (`30_viewer.jsx` at 600, `30i` 198);
  QA surface map OK. No backend/Python change; no new dependency; no egress. No security-audit trigger (pure
  local DOM search).

## Note
`30_viewer.jsx` is at the 600-line cap exactly — the next addition there must extract a chunk first.
