# Increment 248 — Accordion panels polish: headers always visible, section-body padding, Cite tabs

## Implemented

The maintainer's three next-up asks (all frontend), plus a stale-stub cleanup surfaced during verification.

**(A) Headers always visible** (maintainer chose "open section scrolls internally"). The accordion panes stop
scrolling as a whole; the OPEN section's body scrolls in a bounded region so every collapsed section header stays in
view (a long Details section no longer buries the METHODS headers below it). `styles.css`:
- `.pane-sidebar`, `.pane-detail` → `display:flex; flex-direction:column; overflow:hidden` (the center `.pane-list`
  keeps its normal `overflow-y:auto`); `.pane-sidebar > .pane-head` → `flex:0 0 auto`.
- `.pane-accordion` → `flex:1 1 auto; min-height:0`; `.acc-section` → `flex:0 0 auto` (collapsed = header only);
  `.acc-section.open` → `flex:0 1 auto` (natural height when short, shrinkable when the pane is full);
  `.acc-header` → `flex:0 0 auto`; `.acc-section.open .acc-body` → `overflow-y:auto`.
- Height-agnostic → works at desktop `100vh` and mobile `100%` with no guard.

**(C) Section-body padding.** `.acc-body` gained `padding: 2px 14px 14px` (tokens; horizontal 14px matches the
header) so the 9 previously-flush section bodies (GRIM, statcheck, Cite, citation-concentration/context, Review,
mixed-model, bayesian, meta-analysis) aren't against the resize bar. DETAILS carried its own inline `padding:
12px 18px 32px` on `.detail-edit-pane` → changed to `10px 0 24px` (vertical only) so it doesn't double-pad.

**(B) Cite tabs** (maintainer chose "per-tab hideInReadOnly; keep 'Cite'"). Citation concentration
(`08b_methods_citation_equity.jsx`) + How-it's-cited (`08c_methods_citation_context.jsx`) moved from standalone
METHODS sections to **tabs of the THEORY "Cite" section**: `[Suggest | Citation concentration | How it's cited]`.
`05_panes.jsx` reworked:
- `registerPaneSection` now **owns** the section's label/paneId/order/hideInReadOnly (authoritative regardless of
  chunk-load order — so 08b/08c, which load before 37_cite, only seed a placeholder) + a `tabLabel` option (Cite's
  first tab reads "Suggest").
- `registerPaneTab` seeds a not-yet-`defined` section from its host; a `tab` may carry `hideInReadOnly`.
- `sectionTabs(section, readOnly)` drops per-tab hideInReadOnly tabs read-only; `PaneAccordion` hides a section only
  when it's explicitly hideInReadOnly OR every tab is hidden (Cite keeps Suggest read-only, drops the 2 analysis tabs).
- 37_cite adds `tabLabel:"Suggest"`; 08b/08c switch `registerPaneSection`→`registerPaneTab` (host id `cite`,
  `hideInReadOnly:true`).

**Stale-stub cleanup (rule #5 + the inc-163 convention).** Verification surfaced a duplicate "Bayesian statistics"
header + a mis-ordered "Mixed-model reporting": `09_placeholders.jsx` still had coming-soon stubs whose real panels
shipped — `id:"bayesian"` (real: inc 241, `id:"bayes"`) + `id:"lmm"` (real: inc 247, same id → collided; my inc-248
metadata-override would have mis-ordered the real one). Removed both stubs; META-ANALYSIS (#37, no real feature) +
the statcheck "More checks" tab (#27) stay.

## Key technical detail

The internal-scroll uses `flex:0 1 auto` (NOT `flex:1`) on the open section so a *short* section keeps its natural
height with headers right below it (the maintainer's option description), and only a *long* section shrinks-then-scrolls.
`registerPaneSection` owning metadata is what lets Cite's definer (37_cite, load order 37) win over the tab-adding
08b/08c (load order 08) that run first — the placeholder they create is overwritten authoritatively.

## Manual verification script

`HF_HUB_OFFLINE=1 python .local/visual/drive_inc248_panels.py` → "PASS":
- METHODS headers = Details/GRIM/Statistics check/Bayesian statistics/Mixed-model reporting/Where to submit/Review/
  Meta-analysis — **no duplicate Bayesian, no Citation concentration/How-cited** (they moved).
- `.pane-detail` overflow `hidden`; the open `.acc-body` overflow-y `auto`; the last header is within the pane viewport.
- Open GRIM → its `.acc-body` padding-left is `14px`.
- Open THEORY → Cite → tab strip `[Suggest | Citation concentration | How it's cited]`; switch to Citation
  concentration → its panel (Run audit) renders.
- 0 console/page errors, 0 genai-host requests.

## Gates

- **No backend change** (all JS/CSS + docs). No migration, no egress, no new dependency, no new endpoint.
- **No audit** (no new fetch/data-path/endpoint/dependency; a layout + IA move). **Principles non-triggering** (no
  new claim/signal; the moved panels' honesty posture is unchanged — same endpoints, same signal-not-verdict framing).
- **QA (rule #10):** `route_51`/`route_53` prose repointed to the THEORY Cite tabs; `route_42` notes the tabbed Cite
  section. Coverage keys on the unchanged jsx files → surface **177/177 API + 796/796 FE, 0 uncovered**.
- **DESIGN.md (rule #8):** recorded the internal-scroll accordion layout + per-tab hideInReadOnly + section-definer-
  owns-metadata + `tabLabel`.

## Pytest

**938 passed, 1 skipped** (unchanged — inc 248 touched no Python; `test_frontend_assembly` 5/5 confirms the rebuilt
`callosum-app.html` is in sync). `ruff check` + `ruff format --check` clean.

## Notes

help corpus's "Checking citation concentration" + "Seeing how a paper is cited" now point to the THEORY → Cite tabs
(`HELP-DOCS-SYNCED` → 248). Deferred within the maintainer's asks: none — all three shipped.
