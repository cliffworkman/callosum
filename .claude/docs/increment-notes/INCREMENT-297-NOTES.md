# Increment 297 — Discover Feed restored as its own sub-tab

Group B from the 2026-07-18 Search/Synthesize handoff: undo the inc-285 embedded-Feed placement and make Feed a
first-class Discover sub-tab again.

## Implemented

- `app/frontend/js/04b_workspaces.jsx`: registered a **Feed** tab under the Discover workspace with order 10, before
  Search. It renders `FeedPane` standalone, without the `embedded` prop.
- `app/frontend/js/30d_discover.jsx`: removed the embedded `<FeedPane ... embedded />` from the Search results body.
  Search now owns only search input/results plus Wanted/Gaps/Overlooked launchers.
- `app/frontend/js/09_placeholders.jsx`, `.claude/DESIGN.md`, `.claude/qa-routes/route_44_feed.md`,
  `.claude/qa-routes/route_73_workspaces.md`, and `app/backend/help/help_content.md`: updated durable wording for
  **Discover → Feed** and the Discover tab order **Feed · Search · Journals · Funding**.
- `tests/test_frontend_assembly.py`: updated assembly guards to require the standalone Feed tab and reject the old
  embedded Search placement.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Principle boundary

No claim/signal behavior changed. This is navigation IA only: Feed remains pull-only and opt-in, Search still shows
the complete returned list and keeps relevance as a hint.

## Experience pass

Persona: corpus builder checking new literature while also running targeted searches. Finding: putting Feed back as
the first Discover sub-tab makes the ongoing monitoring mode immediately available without burying it under query
results, while Search remains focused on explicit searches and discovery launchers. No further UX follow-up filed.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m pytest tests/test_frontend_assembly.py tests/test_help.py tests/test_feed.py -q`: **57 passed**.
- `python tools/qa/build_surface_map.py check` reported **248/248 API** and **1141/1141 FE** covered.
- `python -m ruff check .` passed.
- `python -m ruff format --check .` passed (`464 files already formatted`).
- `python tools/check_line_budget.py` passed (`all 343 application-source files within the 600-line cap`).
- `python -m pytest` on the final tree: **1259 passed, 1 skipped** in 22:33.
