# Integrations

`integrations/` contains provider-specific adapters. Core local behavior does not require network access after
data is imported; every adapter here is public-metadata or discovery egress (never the Gemini/LLM gate) unless
noted otherwise.

## Implemented

- `zotero/`: Zotero library import adapter. The backend import surface is in `app/backend/importers/zotero.py`.
- `crossref/`: Crossref metadata adapter used for DOI resolution, enrichment, keyword/tag import, and discovery search.
- `openalex/`: citation-graph client (`referenced_works`/`related_works`/citing-works, work metadata, OA/retraction
  lookups) backing the gap-finder, beyond-library citation suggest (backlog #30), and metadata enrichment. DB-cached
  via `api_cache.py`; a `mailto` contact param + descriptive User-Agent for politeness.
- `semantic_scholar/`: citation-context / reference-context client (`fetch_citation_contexts`/`fetch_reference_contexts`),
  used by the citation-context stance surface (`app/backend/api/routers/citation_context.py`, B4). Does **not**
  yet wrap Semantic Scholar's recommendations endpoint — adding that would be a new external fetch (audit-gated).
- `arxiv/`, `biorxiv/`, `core/`, `doaj/`, `europepmc/`, `osf/`: discovery-source adapters feeding the Search/Feed
  registry (`app/backend/discovery/`) and beyond-library citation suggest.
- `retraction_watch/`: local mirror client backing the retraction-check methods signal.
- `gemini/`: optional generation adapters for summaries, help/axis assistance, and labels. Disabled unless
  `CALLOSUM_ALLOW_DATA_EGRESS` is explicitly enabled — the only channel that isn't public-metadata egress.
- `api_cache.py`: the shared DB-backed cache (`external_api_cache` table) every provider adapter above reads/writes
  through — keyed `(provider, cache_key)`, with a commit-outside-lock helper for long background jobs.

## Planned — not yet implemented

- `grobid/`: structured scholarly PDF parsing for sections, references, and citation structure — needed for Track C
  Stage-4 (section-scoped citation suggest).
- `mendeley/`: constrained import bridge, likely through Zotero or interchange exports rather than direct local
  database integration.

All adapters that send content off-machine must preserve the local-first consent posture and keep provider output
inspectable rather than authoritative.
