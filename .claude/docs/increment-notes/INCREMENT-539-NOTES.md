# Increment 539 — Public website (`www/`) frontend overhaul: Phase 1 of the website/demo improvement plan

**Date:** 2026-08-30
**Scope:** Cliff asked for a frontend-focused pass over `www/` and `demo/` while Codex continues the Mendeley/
EndNote handoff. Full plan: `.claude/backups/plans/2026-08-30_website-demo-improvements.md`. This increment is
Phase 1 (the `www/` frontend overhaul) plus the start of Phase 2 (live-verification via Playwright).

## Implemented

- **Fixed a real cross-page color-token bug.** `index.html`'s inline `<style>` genuinely matched the real app's
  tokens (`app/frontend/styles.css`: `--paper:#fbfaf7`, `--accent:#2f2a6b`, etc.) — the correct, deliberate
  choice. But `showcase.html`, `how-it-works.html`, and the shared `site-header.js` (used by all three pages,
  including index.html itself) all used a second, drifted palette (`#f7f4ed`/`#37306f`). The homepage's own
  floating nav bar didn't match its own body color. Canonicalized everywhere on the real app values.
- **Extracted `www/site.css`** — the canonical `:root` token block + the genuinely-shared base rules (reset,
  typography, `.wrap`/`.eyebrow`, `.btn`/`.btn-primary`/`.btn-ghost` (aliased to each page's own existing class
  names, e.g. `.btn.primary`/`.btn.secondary`), `.reveal`/`[data-d]` scroll-reveal mechanics, and
  `prefers-reduced-motion`) that all three pages previously redefined identically inline. Each page's own
  `<style>` block now keeps only its genuinely page-specific rules, with a short header comment pointing at
  site.css. Page-specific token additions (`how-it-works.html`'s `--accent-2`/`--local`/`--local-soft`) stay
  local to that page, not moved to the shared file.
- **Extracted `www/site.js`** — the scroll-reveal `IntersectionObserver` logic, previously hand-copied into
  `index.html` and `how-it-works.html` separately (with slightly different threshold/margin values each time —
  now unified on one behavior). Each page's own remaining inline `<script>` keeps only its genuinely
  page-specific logic (index.html's animated "verify demo" replay; how-it-works.html's keyboard-navigable
  pipeline tabs).
- **De-inlined two embedded base64 images from `index.html`.** The favicon (~7.7KB base64, previously
  triplicated across all three HTML files) and the footer brand logo (~55KB base64, a single HTML line) are now
  real files — `www/favicon.png` and `www/assets/logo-mark.png` — referenced via ordinary `<link>`/`<img src>`.
  Byte-identical to the original embedded images (extracted via direct base64 decode, not re-exported/
  re-compressed), so this is a pure de-inlining with zero visual change: same pixels, ~40KB+ lighter HTML, and
  the files are readable/diffable again. `site-header.js`'s Shadow DOM already read the page's own
  `<link rel="icon">` for its brand mark, so it picked up the new file with no code change needed there.
- **`site-header.js`'s Shadow DOM styles switched from hardcoded drifted hex to `var(--token)` references.**
  Confirmed (not assumed) that CSS custom properties inherit across shadow boundaries — encapsulation blocks
  selector matching, not property-value inheritance — so `var(--accent)` etc. inside the shadow tree correctly
  resolves to whatever `:root` the host page defines via `site.css`. This also future-proofs it: any future
  token change in `site.css` now automatically propagates to the header instead of needing a parallel edit.
- **Deleted 53 of 73 files in `www/shots/`** — computed precisely (not estimated) by scanning all three HTML
  files plus `showcase-coverage.json` for every `shots/*.png` reference, then diffing against the actual
  directory listing. The orphaned set was a superseded July-14 screenshot batch later replaced by an August
  `_current` recapture that was never deleted (confirmed via the `X.png`/`X_current.png` naming pattern and the
  clean mtime split). Spot-checked the orphaned filenames against the whole repo (README, changes.md, code) to
  confirm nothing else referenced them before deleting — found only one historical mention in
  `.claude/changes.md` (an append-only past-tense changelog entry, not a live reference). ~4.9MB removed.
- **Live-verified all three pages** with Playwright against a local static server (`python3 -m http.server` over
  `www/`): zero console errors/warnings on any page, screenshots confirm the header/body color-drift bug is
  visibly fixed (the nav bar now blends seamlessly into the page on all three pages, where it previously showed
  a visible cream/indigo seam), and the how-it-works.html pipeline-tab keyboard/click interaction still works
  correctly after the JS split (confirmed the URL hash updates on tab click).

## Verification

- `python tools/qa/check_website_coverage.py` → `[website] OK — 69 QA routes (1 excluded), 6 external surfaces,
  20 current figures` (unaffected by the CSS/JS refactor or the screenshot cleanup, since all 20 referenced
  figures are untouched).
- `pytest tests/test_check_website_coverage.py tests/test_website_how_it_works.py -q` → **11 passed**.
- Playwright: 0 console errors/warnings on `index.html`/`showcase.html`/`how-it-works.html`; visual screenshots
  taken and reviewed directly (not just "looks fine" — actually inspected pixel output) for all three pages;
  pipeline-tab click interaction confirmed working post-refactor.

## Next

Phase 2 (screenshot refresh — a mobile-view capture is a real, currently-unfilled gap since `index.html`
explicitly promises "a read-only view for your phone" with zero visual evidence anywhere on the site; spot-check
the 20 `_current` shots for drift since their 2026-08-24 capture date) and Phase 3 (the demo's own data gaps —
Synthesize and Discover have no clean example anywhere in the demo per `demo/README.md`'s own coverage table)
remain — see the plan doc for full scope.
