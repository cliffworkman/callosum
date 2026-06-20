# Integrations

`integrations/` contains provider-specific adapters and planned adapter stubs. Core local behavior does not require network access after data is imported.

## Implemented

- `zotero/`: Zotero library import adapter. The backend import surface is in `app/backend/importers/zotero.py`.
- `crossref/`: Crossref metadata adapter used for DOI resolution, enrichment, and keyword/tag import.
- `gemini/`: optional generation adapters for summaries, help/axis assistance, and labels. These are disabled unless `CALLOSUM_ALLOW_DATA_EGRESS` is explicitly enabled.

## Planned - Not Yet Implemented

- `openalex/`: citation graph, discovery, gap-finder, My Publications, and open-access metadata support.
- `semantic-scholar/`: citation contexts, recommendations, and complementary discovery signals.
- `grobid/`: structured scholarly PDF parsing for sections, references, and citation structure.
- `mendeley/`: constrained import bridge, likely through Zotero or interchange exports rather than direct local database integration.

All adapters that send content off-machine must preserve the local-first consent posture and keep provider output inspectable rather than authoritative.
