# Increment 53 Notes — Polish pass (SRI · radius scale · in-app HELP · favicon dark-swap)

A batch of four deferred low-risk polish items. Frontend-only; no backend, no migration, no new endpoint.

## Implemented

### 1. SRI on the CDN scripts (`index.html`)
Added `integrity="sha384-…" crossorigin="anonymous"` to the React, ReactDOM, and Babel-standalone
`<script>` tags (hashes computed from the exact immutable cdnjs files). If a hash were wrong the browser
would block the script and the app wouldn't render — the live E2E (app renders + 0 console errors) is the
proof the hashes are correct. (pdf.js is loaded dynamically at runtime, not a static tag — left as-is.)

### 2. Radius scale tokens (`styles.css`, DESIGN.md §3 #6)
Added `--radius-sm:5px` / `--radius-lg:12px` / `--radius-pill:999px` (alongside the existing `--radius:7px`)
and migrated the unambiguous values: every `999px`/`20px` pill → `--radius-pill` (the noted 20px↔999px
inconsistency standardized to fully-round), the `12px` modal → `--radius-lg`. **Conservative on purpose:**
the messy middle (4/5/6/8/9px) was left as-is rather than force a value-shifting app-wide consolidation
while the app is in active use — the tokens now exist for new code, and the rest stays a §3 worklist item
(along with the `.btn-*` class DRY, which is too regression-prone to bundle into a polish pass).

### 3. In-app HELP viewer (`18_help.jsx` new, `10_pdf_layer.jsx`, `40_app.jsx`)
A **?** button in the sidebar header (top-left, mirroring the ⚙ top-right) opens `HelpModal` — the axes/
tiers/cutoff tips that lived in `.claude/HELP.md`, now surfaced in-app (reuses the `.axis-modal` overlay).
App owns `helpOpen`; the content is static.

### 4. Favicon dark-swap (`index.html`, `inline_brand_assets.py`)
The single favicon `<link>` became **two media-query links** —
`media="(prefers-color-scheme: light)"` (favicon.png) and `"…: dark)"` (favicon_dm.png) — so the browser
swaps the tab icon to the OS color scheme with **no JS**. Trade-off: the favicon follows the OS scheme, not
the in-app dark-mode toggle (a tab-icon edge case, acceptable). `inline_brand_assets.py` now maintains both
favicon data URIs (two media-attr regex targets). A one-off surgery script did the base64-line split
(`index.html`'s favicon line is too large to hand-edit), then was removed.

## Key technical detail
SRI hashes must match the exact bytes the browser fetches; the immutable versioned cdnjs URLs guarantee
this, and the E2E (real browser, real CDN) is the authoritative check. The favicon media-query approach
needs no JS and no theme-bootstrap change — the cost is OS-scheme (not in-app-toggle) coupling.

## Manual verification script
1. `python tools/build_frontend.py`, restart uvicorn, hard-reload.
2. App loads normally (React/Babel under SRI). Click **?** (top-left) → the Help & tips modal with the
   axes/tiers explanation. Set the OS to dark → the browser tab icon swaps to the dark favicon.

## Verification
- **pytest: 179** (unchanged — frontend-only).
- **Live E2E** (`.local/polish_e2e/`): app renders under SRI (hashes correct); both favicon media links
  present; the ? help modal opens with the tips; **0 console errors**. Screenshot captured.
- No audit gate (SRI is hardening; no new endpoint/egress/ingestion/dependency). `15_axes.jsx` 348,
  `18_help.jsx` 33 — all < 600.

## Backlog
Done: **SRI**, **in-app HELP viewer**, **favicon dark-swap**, **radius scale tokens** (partial). Remaining
DESIGN.md §3: the `.btn-*` class DRY + the full radius consolidation (4/5/6/8/9px). Next: library
multi-select + bulk delete (D, destructive → soft-delete/undo decision + plan); dedup (E); synthesis split
(F); library merge (last); terms-as-first-class.
