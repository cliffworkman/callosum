# Increment 47 Notes — Connection status shown by the logo

Retired the textual `● connected · local-verifier-v1` status line; the **brand logo now carries the
signal** — a green dot in the brain's cell-body when connected — using the user's `logo_on` assets.
Frontend-only; no backend/migration/egress.

## Implemented
- **Logo as a 4-state CSS background-image** (theme × connection). Four `--logo-*` tokens in `styles.css`
  `:root` hold the base64 (`logo.png` / `logo_on.png` / `logo_dm.png` / `logo_dm_on.png`); `.brand-logo`
  is a `<div>` whose `background-image` is picked by `[data-theme]` × a `.connected` class:
  `--logo-light-off` (default), `.connected` → `--logo-light-on`, dark overrides → `--logo-dark-off` /
  `--logo-dark-on`. **Keeping the base64 in CSS (not the inline Babel script)** is deliberate — four logos
  in the Babel script would blow its 500KB deopt cap (the same trap as inc 46).
- `10_pdf_layer.jsx`: the two themed `<img>` (inc 46) → one `<div className={"brand-logo" + (conn.state
  === "ok" ? " connected" : "")} role="img" aria-label="Callosum" title=…>`; the title preserves the
  detail on hover (`Connected (<version>)` / `Disconnected` / `Connecting...`). **Removed the `ConnStatus`
  component + its usage** and the dead `.conn` / `.led*` CSS. Kept the "local reference workbench" subtitle
  (its removal is a separate B″ item).
- **Losslessly recompressed `logo_on.png` + `logo_dm_on.png`** (423KB → ~57KB each; identical pixels).
- `inline_brand_assets.py`: logo targets repointed from the JSX `<img src>` to the four `--logo-*: url(…)`
  tokens in `styles.css` (favicon target unchanged).

## Key technical detail
Connection state lives in App (`conn.state`, from the `/health` check) and flows to `Sidebar`, which sets
the `.connected` class on the logo div; CSS does the rest (theme via `[data-theme]`, the on/off variant via
`.connected`). The logo's `data:` base64 now lives in the plain CSS block, so `10_pdf_layer.jsx` dropped to
199 lines and the Babel script no longer carries any logo bytes (no >500KB deopt).

## Manual verification script
1. Rebuild + restart uvicorn; hard-reload. The brain logo shows a **green dot** in its cell-body (connected).
2. Stop the backend → the dot disappears (the "off" logo). Restart → it returns.
3. Toggle dark mode (gear → Settings) → the dark logo variant (with/without dot) shows.

## Verification
- **pytest: 149** (frontend-only, unchanged).
- **Live E2E** (`.local/conn_logo_e2e/`): `.brand-logo.connected` present, old `.conn` line gone,
  background-image is a data URI, **swaps on connection** (remove `.connected` → different image) and **on
  theme** (dark → different image); **0 console errors** (no Babel >500KB note). Dark screenshot confirms
  the green dot.
- No audit gate (frontend-only; no new endpoint/egress/ingestion/dep).

## Backlog
Connection-in-logo done. **Remaining B″ (sidebar density):** drop the "local reference workbench" subtitle
+ "local-verifier-v1" entirely, an axis **filter** field, and "+ new" → a green **"+"** on one no-wrap row.
Also queued: favicon dark-swap; DESIGN.md `.btn-*` DRY + radius scale; HELP viewer; terms-as-first-class;
tier-tag ✓-confirm; library focus-mode/multi-select/dedup/merge; synthesis split + editable Details + DOI
re-search; suggest-optimal-axes; SRI hardening.
