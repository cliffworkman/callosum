<!-- qa-coverage
api: GET /health, GET /papers, GET /papers/item-types, GET /papers/{paper_id}, GET /tags, GET /axes, GET /summaries
fe: 05_panes.jsx, 06_methods_statcheck.jsx, 08d_methods_bayes.jsx, 08f_methods_lmm.jsx, 08g_methods_metaanalysis.jsx, 08h_methods_transparency.jsx, 08i_methods_effectsize.jsx, 08j_reference_integrity.jsx, 08k_funding_discovery.jsx, 08l_funding_saved.jsx, 08x_methods_critical.jsx, 10_pdf_layer.jsx, 15_axes.jsx, 20_synthesis.jsx, 25_detail.jsx
-->

# ROUTE 70 - Tool pane visual drift

**Tier:** 0 read-only visual smoke
**Goal:** Catch runtime aesthetic drift in the THEORY and METHODS tool panes relative to `.claude/DESIGN.md`.

This route complements `tests/test_design_drift.py`. The pytest suite catches static recipe drift; this route catches
rendered breakage such as overflow, hidden accordion headers, overlapping tool chrome, and console/page errors.

## Environment

Stand up a clean seeded instance using the standard throwaway fixture contract. Keep egress unset. Register
console/pageerror/request listeners before navigation. Use desktop `1366x900` and mobile `375x812` viewports.

## Standing assertions

- Console-error budget = 0.
- Page-error budget = 0.
- No request to Gemini/generativelanguage/genai hosts with egress unset.
- No document-level horizontal overflow at either viewport.
- Visible `.pane-sidebar`, `.pane-detail`, and `.acc-section.open .acc-body` elements do not horizontally overflow.
- Accordion headers remain visible while each section is opened.
- Tool bodies scroll internally when needed; they must not bury the rest of the accordion headers.
- Tool cards and evidence blocks stay inside their pane bounds.
- The rendered UI preserves DESIGN.md semantics: dense neutral chrome, token-based semantic accents, no hero/landing
  styling, no card-within-card overload, no visible overlapping text, no color-only state distinction.

## Steps

1. Load `/` at `1366x900`. Wait for React mount. Take `tool-panes-desktop-initial.png`.
2. Walk every visible THEORY accordion header in `.pane-sidebar`: click it, assert `aria-expanded="true"`, assert all
   headers remain visible, assert no horizontal overflow in the sidebar/open body, and take a screenshot for any visual
   anomaly.
3. Walk every visible METHODS accordion header in `.pane-detail` with the same assertions.
4. Resize/reload at `375x812`. Confirm no horizontal overflow in the Library view.
5. Open the mobile **Panels** region. Walk visible THEORY headers with the same assertions.
6. Open the mobile **Details** region. Walk visible METHODS headers with the same assertions.
7. Compare visually against DESIGN.md: any raw-feeling color accent, one-off button recipe, over-large heading, nested
   decorative card, clipped text, or overlap is a **Visual** finding unless it blocks use, in which case escalate.

## Pass criteria

- Runtime visual drift test passes at desktop and mobile.
- Every visible tool section can be opened without horizontal overflow or hidden accordion headers.
- No console/page errors.
- No genai egress.
- Static design drift tests pass:
  `pytest -q tests/test_design_drift.py tests/test_frontend_assembly.py`
- Opt-in Playwright drift test passes when Chromium is installed:
  `$env:CALLOSUM_RUN_E2E='1'; pytest -q tests/e2e/test_smoke.py -k tool_panes_resist_visual_drift`

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_70_tool_pane_visual_drift.md` + screenshots under
`.claude/qa-inbox/<RUN_ID>/screenshots/`.
