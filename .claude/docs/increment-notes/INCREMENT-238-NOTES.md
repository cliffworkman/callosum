# Increment 238 — B5 SP2: the read-only companion UI (B5 complete)

SP1 (inc 237) made the tunnel *block* writes (the `CALLOSUM_READ_ONLY` method gate + a read-only ingress). SP2 makes
the app *read clean* when it's a read-only instance — no dead buttons, no doomed writes. Maintainer fork
(AskUserQuestion): **comprehensive** (hide every write control across all panels, not just the reader core).

## Detection (a UX signal, not the boundary)

`GET /health` gains an additive `read_only` boolean (`app_settings.read_only_mode()`). This is the one endpoint that
is **forwarded over the read-only tunnel AND token-exempt**, so the client can read it to decide. The enforcement is
still the SP1 method gate + ingress; `/health.read_only` only tells the UI to hide controls.

**Tri-state `readOnly`.** The App's `readOnly` starts `undefined` (health not resolved), then becomes true/false. This
matters because a background *read-implemented-as-POST* (CiteRow's `/citations/render`) would otherwise fire during the
brief pre-health window while `readOnly` was still `false`. With the tri-state, CiteRow only fetches when read-write is
**confirmed** (`readOnly === false`). The write-control gates treat `undefined` as falsy (controls show for the ~instant
health takes to resolve, then hide on a read-only instance). `readOnly` is threaded into `paneCtx` + `libraryProps` +
a fixed `.read-only-badge`.

## Comprehensive hiding

- **Library** (`10_pdf_layer.jsx`): the header write cluster (`.lib-head-actions`) hidden; `selecting` dropped (no
  checkboxes / bulk bar / copy); the per-card read/priority markers hidden.
- **Details** (`25_detail.jsx` + `24_detail_fields.jsx`): a `DetailReadOnly` React **context** (in 24) consumed by
  `EditableRow`/`EditableText`/`IdentifierRow` → they render **plain text** instead of inputs — **zero call-site churn**
  across ~20 fields. Fill-metadata / re-resolve (🔎) / OCR / +Reading-queue / tag add-remove / AddField / CiteRow all
  hidden or gated.
- **Synthesis** (`20_synthesis.jsx`): the run controls (textarea + Synthesize), Re-verify, Save-as-highlight (a null
  `onSaveHighlight` — CitationCard already guards on it), and history Delete are hidden. Reading saved syntheses works.
- **Axes** (`15_axes.jsx` + `15b_axis_card.jsx`): the toolbar (✨/📌/+), quickname, bulk-bar, the per-axis
  checkbox/✎/＋/❄/↩/🗑, the re-score row, drop-to-add, member drag-reorder, and the per-row ✓/×/⠿/★ are hidden.
  Filtering (the count badge), 📊 dashboard, and open-paper stay.
- **Tags** (`25b_tags.jsx`): the color dot, × remove, add input, ✨ Suggest, and suggestion chips hidden; chip-name
  filtering stays.
- **Queue** (`16_queue.jsx`): card-drop-to-add, row drag-reorder, ⠿ grip, ✓ done, × remove hidden; open-a-row stays.
- **METHODS analysis sections**: a new pane-registry **`hideInReadOnly`** flag on `registerPaneSection` — statcheck,
  GRIM, findings, citation-equity, citation-context, and the 3 coming-soon placeholders drop off a read-only companion
  (`PaneAccordion` filters them). Details stays.
- **Discover/Feed tabs** (`30c_frame.jsx`): hidden.

## No doomed writes on load (the honest part)

A read-only companion must not *fire* a write it will 403 (else the console shows errors and the reader sees flicker):
- The on-launch watched-folder rescan (`POST /library/watched/rescan`) is gated on `healthLoaded && !readOnly`
  (`03_library.jsx`) — `healthLoaded` closes the race where the launch rescan fired before `/health` resolved.
- CiteRow's `/citations/render` (`25_detail.jsx`) only fetches when `readOnly === false`.

Headed: **0 request-403s on load** in read-only mode (was 2 before these gates).

## Widened read ingress

The read-only cloudflared allowlist (`adapters/mobile/cloudflared-config.yml`) now forwards the core library **read**
GETs (`/axes`, `/axes/{id}/clusters`, `/tags`, `/tags/colors`, `/reading-queue`, `/papers/{id}/annotations`,
`/papers/{id}/chunks`) so those panels *load* read-only over the tunnel. Every mutating method on those paths is still
403'd by the method gate; the analysis/config routes (`/settings`, `/library/*`, `/methods/*`, `/discovery/*`, `/gaps`,
`/agent/*`) stay 404 at the tunnel.

## Rule-#1 split (25_detail.jsx)

`25_detail.jsx` was **624 at HEAD** — a pre-existing violation the "583" watch note had drifted on (the inc-226
IdentifierRow generalization took it over; the read-only additions worsened it). The inline-field primitives
(`EditableRow`/`EditableText`/`TypeSelect`/`IdentifierRow` + the `DetailReadOnly` context) → new
**`js/24_detail_fields.jsx`** (159; sorts before 25 so the `const` initializes first; the functions hoist in the IIFE)
→ `25_detail.jsx` **492**.

## Verification

`HF_HUB_OFFLINE=1 python -m pytest -q` → **884 passed, 1 skipped** (+11 `tests/test_mobile_ingress.py`: the broadened
forward list [`/axes`, `/axes/3/clusters`, `/tags`, `/tags/colors`, `/reading-queue`, `/papers/5/annotations`,
`/papers/5/chunks`] + the broadened block list [`/methods/statcheck/run`, `/discovery/*`, `/feed`, `/gaps`,
`/findings/overview`, `/papers/citation-counts/refresh`, `/papers/ocr/run`, `/axes/3/score`, `/axes/suggest`,
`/citations/render`] + a `/health.read_only` truth test). `ruff` + `format` clean; frontend rebuilt
(`test_frontend_assembly` 5/5); **QA surface 173/173 API + 758/758 FE, 0 uncovered** (`route_30_detail_pane.md` claims
`24_detail_fields.jsx`; the `read_only` flag rides the already-claimed `/health`). Audit **addendum** to
`2026-07-01_mobile-reading.md` PASS. No new endpoint, no migration, no new dependency.

**Headed-verified, 0 errors** (`.local/visual/drive_inc238_readonly.py` — serves twice): `CALLOSUM_READ_ONLY=1` → the
badge shows, the library write cluster + Discover tab are hidden, 20 Details fields are static (`.detail-ro`), no Fill
button, **0 console/page errors + 0 request-403s on load**; the read-write control run → the badge is absent + the
write cluster + Discover + Fill all return.

## Deferred (own increment if wanted)

A mobile-tuned PDF reader + synthesis→PDF exact-highlight overlays on mobile (the desktop pdf.js overlay path).
