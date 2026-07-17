# Increment 286 — Synthesis + Work workspace split

Follow-up to the workspace navigation polish on `feature/workspaces-ux-polish`: move broad synthesis and writing/cite
work out of the THEORY side accordion and into center workspaces.

## Implemented

- `app/frontend/js/04b_workspaces.jsx`: added the **Work** workspace after Discover, moved Extract later in the order,
  and added a small `registerCiteTab` registry for nested Work → Cite tabs.
- `app/frontend/js/20_synthesis.jsx`: moved **Synthesis** from a THEORY pane section to its own center workspace after
  Library and before Discover.
- `app/frontend/js/37_cite.jsx`: moved **Cite** from a THEORY pane section to **Work → Cite**, with nested tabs using
  the shared `.tags-srcfilter`/`.pane-tab` mount-but-hide pattern.
- `app/frontend/js/08j_reference_integrity.jsx`: moved **Meta Reference List** into Work → Cite, ordered after
  Suggest and before Citation concentration.
- `app/frontend/js/08b_methods_citation_equity.jsx` and `08c_methods_citation_context.jsx`: moved
  **Citation concentration** and **How it's cited** into the Work → Cite nested tab set.
- `app/frontend/js/38_credit.jsx`: moved **CRediT statement** out of THEORY and into **Work** as a top-level Work tab.
- `app/frontend/js/03_library.jsx` + `40_app.jsx`: selection **summarize** now opens the Synthesis workspace; paper
  card **ref signal** jumps now select Work → Cite → Meta Reference List.
- `app/frontend/js/30c_frame.jsx`: updated the one-time Library layout notice to include Synthesis and Work moves.
- `app/frontend/styles.css`: constrained `.menubar` overflow to an internal horizontal scroll so the expanded menu bar
  cannot overlap the divider/right pane when the center column is narrow.
- `tests/test_frontend_assembly.py`, `.claude/DESIGN.md`, `app/backend/help/help_content.md`, and
  `.claude/qa-routes/route_73_workspaces.md`: updated guards and docs for the new workspace locations.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Key technical detail

The moved tools reuse their existing components. `SynthesisPane`, `CitePane`, `MetaReferenceList`,
`CitationEquitySection`, `CitationContextSection`, and `CreditSection` still receive the same app-level context; only
their registration location changed. The Work → Cite nested tab registry exists because Work itself has top-level
tabs (`Cite`, `CRediT statement`) while Cite also needs a stable sub-order (`Suggest`, `Meta Reference List`,
`Citation concentration`, `How it's cited`).

## Experience pass

Persona: a user switching between reading, synthesis, discovery, writing, and extraction.

Finding: fix-now complete. The THEORY side pane is less crowded and keeps compact paper-context lenses. The center
menu bar now owns the broader modes: Synthesis for corpus answers and Work for writing/citation/contribution work.
Meta Reference List remains close to citation work instead of becoming a standalone top-level workspace.

## Manual verification

Playwright against the local app on `http://127.0.0.1:8888/`:

- Desktop/narrow center-pane smoke confirmed the menu bar now shows Profile, Library, Synthesis, Discover, Work,
  Extract, Help, and Settings without intercepting the right pane. At a 340px center width, `.menubar` reports
  `overflowX: auto`, `scrollWidth > clientWidth`, and hit-testing beyond the center hits the right pane, not menu
  buttons.
- Work renders top-level **Cite** and **CRediT statement** tabs.
- Work → Cite renders nested tabs in order: **Suggest**, **Meta Reference List**, **Citation concentration**,
  **How it's cited**.
- Work → Cite → Meta Reference List renders the selected paper's reference-check panel.
- Synthesis renders as its own workspace and has no console errors.
- Narrow mobile viewport (`390x844`) loads without console errors; the menu bar remains horizontally scrollable.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py` **35 passed**.
- `python tools/qa/build_surface_map.py check` reported **245/245 API** and **1145/1145 FE** covered.
- `python -m pytest` on the final formatted tree: **1237 passed, 1 skipped** in 20:46.
- `ruff check .` passed.
- `ruff format --check .` passed (`464 files already formatted`).
- `python tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
