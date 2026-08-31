# Increment 549 — showcase.html: meticulously-measured invisible image map (Phase 4)

## Implemented

`www/showcase.html`'s Navigator section (`#fig-library-map`) previously had 6 visible, bordered
rounded-rectangle "hotspot" overlays drawn on top of the Library-workspace screenshot — a
decorative-button treatment the user explicitly flagged as wrong, plus one badly mis-scaled box
(`evaluate`: `left:74.8%;top:89.4%;width:20%;height:8%`, an unrelated corner of the image) from
hand-typed percentages that were never checked against the real screenshot.

This increment replaces it with **53 precisely-measured, invisible-at-rest hotspots**:

- **Recaptured `www/shots/app_current.png`** (1600×1000) against an isolated
  `CALLOSUM_SETTINGS_PATH` + the real ~200-paper testing DB, reproducing the same Library
  workspace / selected-paper / expanded-both-panels state the original screenshot showed, so the
  image still looks like a real, populated library rather than the small demo corpus.
- **Measured every target element's real `getBoundingClientRect()`** via Playwright against the
  live app in that exact state (top nav, left-pane axis tabs/controls/rows/icons, middle-pane
  add/saved menus, signal chips, TO REVIEW row, search/filter bar, right-pane item-type/tags/
  accordion sections) — never hand-typed. Converted each to percentages of 1600×1000.
- **Mapped each measured element to the most specific matching `cap-*` id** already in
  `showcase.html`'s capability catalogue (falling back to a `fig-*` figure or chapter id only
  where no specific capability pill exists) — discovered along the way that `.cap:target` already
  has a highlight style (`box-shadow`/`border-color` pulse), which is the intended fine-grained
  landing spot, not just the coarser figures.
- **Rewrote `.hotspot`/`.app-map` CSS**: stripped the visible `border`/`background`/`box-shadow`/
  text chrome from the rest state; hotspots are now fully invisible until `:hover`/`:focus-visible`
  (a subtle `rgba(107,95,220,.16)` tint) with `cursor:pointer` always and a real
  `outline`/`outline-offset` on keyboard focus. Kept `display:flex;align-items:center;
  justify-content:center` so the existing small-screen (`max-width:560px`) visible-dot fallback
  still centers correctly inside each (now-invisible) box. Removed the now-meaningless
  `.hotspot{border-width:1px}` line from the 850px breakpoint. `.map-fallback`'s plain-text link
  row is untouched.
- **Updated `www/showcase-coverage.json`** via `python tools/qa/check_website_coverage.py
  --refresh --note "..."` (the inc-540 precedent) to record the new image's checksum/dimensions
  as reviewed.

## Key technical detail

Positioning is per-element **inline `style="left:…%;top:…%;width:…%;height:…%"`** rather than
per-name CSS classes — at 53 elements, hand-maintained `.hotspot.<name>{…}` rules would have been
both unreadable and exactly the kind of hand-typed-percentage surface that produced the original
mis-scaled box. `.hotspot` itself only carries shared interaction styling now.

A real bug was caught by the click-through verification pass, not by inspection: an initial
`mid-paper-selected` hotspot (measured from `document.querySelectorAll('.paper')[0]`) resolved to
an oversized/mispositioned element (`top:6.95%;height:9.48%`) that visually overlapped and, being
later in DOM order, painted **on top of** several smaller row hotspots underneath it (the TO
REVIEW row's Duplicates/Citations/etc. buttons), intercepting their clicks entirely
(`locator.click()` timed out with "element intercepts pointer events"). Removed that one hotspot
— `#cap-details` was already covered by the `right-item-type` hotspot — rather than trying to
patch stacking order, since the underlying measurement was untrustworthy to begin with.

## Manual verification script

1. Serve `www/` (`python -m http.server` in that directory) and open `showcase.html` at a
   1600×1000 viewport.
2. Scroll to the Navigator section — the screenshot should render with **zero visible boxes,
   borders, or text overlays**, confirmed via a rest-state screenshot.
3. Hover any control in the image (e.g. a paper's Tags chip, an axis row, a nav item) — a faint
   indigo tint should appear; `cursor` should be a pointer.
4. Click a sample across all four zones and confirm the URL hash lands on the intended anchor:
   `#cap-mypubs` (top nav), `#cap-duplicates` (middle-pane TO REVIEW row), `#cap-tags` (right-pane
   Tags row), `#cap-axes` (left-pane axis row), `#fig-reporting` (right-pane Checklists
   accordion) — all 5 verified live via Playwright this increment, no interception errors.
5. `document.querySelectorAll('.hotspot')` → 53; every `href` target resolves to a real element
   id in the document (verified programmatically, 0 missing).

## Pytest

`pytest tests/test_check_website_coverage.py -q` → 5 passed.
`python tools/qa/check_website_coverage.py` → `OK — 69 QA routes (1 excluded), 6 external
surfaces, 21 current figures` (clean after the `--refresh`).
