# Increment 296 — Discover Search selectable sources

Group A from the 2026-07-18 Search/Synthesize handoff: let users choose which discovery provider(s) Search queries
without changing the complete-list, AI-augments-never-filters contract.

## Implemented

- `app/backend/discovery/providers.py`: added registry `kinds`, `source_meta`, `get(...)`, and `search_one(...)`.
  Provider errors still fail closed; unknown provider kinds raise at the registry boundary.
- `app/backend/discovery/{crossref_provider,pubmed_provider}.py`: added display labels for the registry-driven UI.
- `app/backend/discovery/search.py`: `run_search(..., source=None)` preserves prior all-provider fan-out when no
  source is selected, or queries one named provider before running the same dedup + `in_library` marking pass.
- `app/backend/api/routers/discovery.py`: added read-only `GET /discovery/sources` and optional `source` on
  `GET /discovery/search`; unknown `source` values return 422.
- `app/frontend/js/30d_discover.jsx`: added an **All sources / Crossref / PubMed / ...** dropdown using the existing
  `lib-sort` recipe. The selected value appends `&source=<kind>` only when not **All sources**.
- `app/backend/help/help_content.md`, `.claude/qa-routes/route_43_discovery.md`, and
  `tests/test_{discovery,frontend_assembly}.py`: updated help, QA route coverage, and regression tests.
- `callosum-app.html`: rebuilt with `python tools/build_frontend.py`.

## Principle boundary

This is not an AI filter. The source dropdown changes **where Search asks**: all registered providers or one selected
provider. The response still shows the complete deduped returned list for that provider set, preserves source pills,
and keeps axis relevance as a visible hint rather than a rank/filter/verdict.

## Security

Audit: `.claude/security-audits/2026-07-18_discovery-search-source-picker.md` — **PASS**.

The new endpoint is read-only in-memory registry metadata. The new `source` parameter is length-capped, normalized,
validated against registered provider kinds, and never controls a host/path/URL. Selecting one source reduces the
existing public-metadata egress surface; the Gemini/library-text egress gate is untouched.

## Experience pass

Persona: corpus builder scoping a literature search. Finding: the control is discoverable where the provider choice
matters, but it should not be read as an AI filter. The visible hint and help now say source choice controls where to
query and the complete returned list is still shown. No further UX follow-up filed for Group A.

## Verification

- `python tools/build_frontend.py` rebuilt `callosum-app.html`.
- `python -m ruff check app/backend/api/routers/discovery.py app/backend/discovery/providers.py app/backend/discovery/search.py app/backend/discovery/crossref_provider.py app/backend/discovery/pubmed_provider.py tests/test_discovery.py tests/test_frontend_assembly.py`
  passed.
- `python -m pytest tests/test_discovery.py tests/test_frontend_assembly.py tests/test_help.py -q`: **65 passed**.
- `python tools/qa/build_surface_map.py check` reported **248/248 API** and **1141/1141 FE** covered.
- `python tools/check_line_budget.py` passed (`all 343 application-source files within the 600-line cap`).
- `python -m ruff check .` passed.
- `python -m ruff format --check .` passed (`464 files already formatted`).
- `python -m pytest` on the final tree: **1259 passed, 1 skipped** in 23:08.
