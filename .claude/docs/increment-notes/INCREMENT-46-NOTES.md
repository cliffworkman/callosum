# Increment 46 Notes — DESIGN.md token consolidation + dark mode + Settings modal

Finished DESIGN.md's color-token consolidation (the dark-mode groundwork) and shipped a warm-dark theme
behind a new (sparse) Settings modal. Frontend-only; no backend/migration/egress.

## Implemented

**Phase 1 — token consolidation (`styles.css`)**
- New `:root` tokens (from DESIGN.md Pass-2): `--hover`, `--accent-line`, `--flag-line`, `--flag-ink`,
  `--danger`/`--danger-line`, `--accent-overlay`, `--on-fill`. Replaced the scattered raw hex usages with
  them (property-qualified replacements so the new token *definitions* weren't clobbered). This was
  required for dark mode — anything still hardcoded wouldn't darken. Reconciled the split destructive color
  (axis delete `--flag` amber vs highlight delete `#b3261e` red) → **`--danger`** for all destructive
  actions; `--flag` is now status-only.

**Phase 2 — dark theme (`styles.css` + `index.html`)**
- `:root[data-theme="dark"]` overrides every chrome token to a **warm-dark palette** (not pure black).
- **No-flash bootstrap:** a synchronous `<script>` in `index.html` `<head>` sets `data-theme` on `<html>`
  from `localStorage["callosum.theme"]` (else `prefers-color-scheme`) **before paint**.
- **The rendered PDF page stays light in both themes** (its `#fff` + on-page overlay rgba + `--accent-overlay`
  are intentionally not themed); only app chrome themes. `--on-fill` flips (light fills → dark text) so
  primary buttons + status badges stay legible.
- **Logo swap:** the brand renders two inlined `<img>` (`.brand-logo-light` / `.brand-logo-dark` =
  `logo.png` / `logo_dm.png`), CSS-toggled by `[data-theme]` (no JS, no flash). `inline_brand_assets.py`
  extended to inline both. **Losslessly recompressed `logo_dm.png` 427KB → 57KB** (same pixels) — the
  oversized export had pushed the inline Babel script past its 500KB deopt threshold (a console note); the
  served HTML dropped 989KB → 495KB.

**Phase 3 — Settings modal (`35_settings.jsx`, `40_app.jsx`, `10_pdf_layer.jsx`)**
- New `SettingsModal` (reuses the `.axis-modal` overlay): a sparse Appearance → **Dark mode** toggle switch,
  with a "more coming" note. A **gear icon** (⚙) in the sidebar header opens it. `40_app.jsx` owns
  `theme` + `settingsOpen` state and `setTheme` (writes `data-theme` + localStorage); the logo + tokens
  follow via CSS.

## Key technical detail — theming via token-value overrides + no-flash bootstrap

Dark mode = override token *values* under `:root[data-theme="dark"]`; because every chrome color already
flows through a token (Phase 1), nothing else needs touching. The flash-of-light is avoided by setting
`data-theme` in a head `<script>` that runs before the body paints. The PDF page is deliberately excluded
from theming (it's the document, not chrome). See `.claude/DESIGN.md` §1b for the rules.

## Manual verification script
1. Rebuild + restart uvicorn; open `/` and hard-reload.
2. Click the **gear** (sidebar header) → Settings → toggle **Dark mode**: the whole chrome goes warm-dark,
   the brain logo swaps to its dark variant, and an open PDF's page stays white.
3. **Reload** — it stays dark with no light flash. Toggle back → light.

## Verification
- **pytest: 149** (frontend-only; unchanged).
- **Live E2E** (`.local/dark_mode_e2e/`): gear→toggle→`data-theme=dark` + computed `--bg` = `#1a1815` +
  dark logo shown / light hidden; persists across reload; toggle back to light; **0 console errors**.
- **Security audit:** `.claude/security-audits/2026-06-19_dark-mode-settings.md` — PASS (no new
  endpoint/egress/ingestion/dep; localStorage-only).
- Line caps: `10_pdf_layer.jsx` 208, `35_settings.jsx` 29, `40_app.jsx` 178, `styles.css` ~660 (exempt —
  non-code) — all fine.

## Backlog
DESIGN.md is now the rule-#8 CSS tether; **remaining worklist:** `.btn-*` class DRY + a radius scale
(DESIGN.md §3). Queued: favicon dark-swap; **B″ sidebar density** (incl. the `_on` connection-in-logo —
those `_on` PNGs are also oversized, recompress when used); in-app HELP viewer; terms-as-first-class;
tier-tag ✓-confirm; library focus-mode / multi-select / dedup / merge; synthesis split + editable Details +
DOI re-search; suggest-optimal-axes. New hardening item: **add SRI to the CDN `<script>` tags** (React/
ReactDOM/Babel) — pre-existing, flagged this increment.
