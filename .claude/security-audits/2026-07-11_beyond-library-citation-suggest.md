# Security audit: beyond-library citation suggestions

Date: 2026-07-11

## Scope

`POST /citations/suggest` gained an opt-in `include_beyond_library` mode used by the in-app Cite pane's
**Also search beyond my library** checkbox. The default library-only path remains local.

Changed surfaces:

- `app/backend/citations/beyond_library.py`
- `app/backend/api/routers/citations.py`
- `app/frontend/js/37_cite.jsx`
- `app/backend/help/help_content.md`

## Data egress

Default state: no external metadata search. The existing local embedding/NLI Cite path is unchanged.

Opt-in state: Callosum sends the bounded draft sentence or research description pasted into Cite to public metadata
providers through the existing discovery registry plus OpenAlex work search. It also sends DOI identifiers for the top
local Cite matches to OpenAlex to fetch bounded reference/cited-by/related-work graph neighborhoods. It does not send
PDFs, full manuscript text, notes, private annotations, library excerpts, or generated summaries.

This is metadata-provider egress, not LLM egress. The local stance classifier remains local. If outside-library
stance is shown, it is computed against public abstract text and labeled abstract-level.

## Provider boundary

Providers are allowlisted code adapters, not arbitrary URLs. OpenAlex work search uses the existing
`OPENALEX_BASE_URL` constant; graph-neighborhood expansion reuses the existing `OpenAlexClient`, identifier
validation, and cache-backed bounded methods. Provider failures are isolated into source-coverage rows and do not fail
the local library suggestions.

No commercial provider scraping or licensed-data path was added.

## Write boundary

Outside-library cards do not modify the library by default. **Add to library** reuses the existing `/discovery/save`
endpoint and creates/returns a normal metadata-only library record. There is no auto-insert into manuscripts and no
automatic citation selection.

## Product / judgment boundary

The UI separates **In your library** from **Outside your library**. Outside-library candidates are described as public
metadata candidates; when OpenAlex graph evidence surfaced an item, the card shows the relationship to the local
anchor paper. Metadata overlap is visible as a ranking aid, not a correctness score or recommendation.

No hidden paper confidence score, funding/citation probability, "verified good", or "best citation" language was
introduced.

## Checks

- `pytest -q tests/test_citations_suggest.py` -> 13 passed
- `ruff check app/backend/citations/beyond_library.py app/backend/api/routers/citations.py app/backend/api/app.py tests/test_citations_suggest.py` -> passed
- `python -m compileall -q app/backend/citations/beyond_library.py app/backend/api/routers/citations.py app/backend/api/app.py` -> passed
- `python tools/build_frontend.py` -> passed

Result: PASS.
