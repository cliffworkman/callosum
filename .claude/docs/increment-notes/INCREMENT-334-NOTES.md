# Increment 334 — Backlog #9: tag provenance vocabulary formalization

## Context
Working through the 12-item decision queue Cliff answered in one pass. For #9 he chose the bigger scope
("formalize the vocabulary too", not just group tags by source in the UI). Research before touching anything
found the vocabulary was **not actually formalized anywhere** — only `keyword:crossref`/`keyword:openalex`/
`keyword:pubmed` used the `{namespace}:{origin}` shape the docs already described as a future-track reservation;
`zotero`, `user`, and `ai-agent` were bare, unnamespaced strings. `system:{...}` (planned for #19's retraction
tags) appeared only in prose, never in code.

## Implemented
- `app/backend/persistence/tags_repo.py`: `TAG_SOURCE_NAMESPACES` (`user`/`import`/`keyword`/`agent`/`system`) +
  `tag_source_namespace(source)` — the authoritative parser/contract. `remove_tag_from_paper`'s inc-143
  suppression check now reads `tag_source_namespace(...) == "keyword"` instead of a raw `.startswith("keyword:")`
  — behavior-identical (keyword values are unaffected by the rename below), just expressed through the formal
  helper.
- Renamed the two non-conformant producers, **tag-column only**:
  - `app/backend/importers/zotero.py`: new `ZOTERO_TAG_SOURCE = "import:zotero"` used at the one tag-insert call
    site (`_upsert_tags`). `ZOTERO_IMPORT_SOURCE = "zotero"` is untouched and still marks Zotero-origin
    papers/attachments/collections/notes/annotations — a separate vocabulary on five other tables, out of #9's
    scope.
  - `app/backend/metadata/enrichment.py` / `app/backend/api/routers/agent.py`: new `AI_AGENT_TAG_SOURCE =
    "agent:mcp"` used only for the MCP agent's tag-creation endpoint. `AI_AGENT_SOURCE = "ai-agent"` is
    untouched for `papers.imported_source` / `notes.import_source`.
- `alembic/versions/0047_tag_source_vocabulary.py`: idempotent data migration renaming existing
  `tags.import_source` rows (`zotero`→`import:zotero`, `ai-agent`→`agent:mcp`); scoped to `tags` only, zero
  touch on the other five tables' provenance columns.
- Frontend: `app/frontend/js/00_lib.jsx` — `tagSourceLabel` updated for the renamed values + a new
  `tagSourceGroupLabel(source)` (short group-header text, distinct from the tooltip sentence). The sidebar Tags
  browser (`TagsPanel`) now groups the visible list by exact source with a header per group ("Your tags",
  "Crossref subjects", "Zotero import", "Agent-added", …) when more than one source is present in the current
  view — extracted to a new `js/10e_tagspanel.jsx` (grouping pushed `10_pdf_layer.jsx` to 614/600; the
  inc-208/222 shared-IIFE hoist precedent). New `.tags-panel-group-label` CSS reuses the existing muted-eyebrow
  recipe (cf. `.merge-eyebrow`) rather than inventing a token (DESIGN.md rule #8).

## Key technical detail
Two producer constants (`AI_AGENT_SOURCE`, `ZOTERO_IMPORT_SOURCE`) were each shared across **multiple
independent provenance columns** (`papers.imported_source`, `notes.import_source`, `attachments`/`collections`/
`annotations.import_source`, and `tags.import_source`) purely because they happened to reuse the same string
literal — not because the columns' vocabularies are actually coupled. Formalizing tags' vocabulary required
splitting each into a tags-only sibling constant rather than renaming the shared one, which would have silently
changed the meaning of unrelated columns outside #9's scope. This is the same "don't widen the diff past what
was asked" discipline applied to constants, not just code paths.

## Principles/A-A gate (rule #9)
This touches provenance, one of the gate's explicit triggers. The aligned design keeps every fact inspectable:
the formal vocabulary makes provenance *legible* (a written, enforceable contract instead of five ad-hoc
strings) without inventing any new opaque signal. `system:{fact}` is reserved but deliberately **not produced**
by anything here — #19 (the findings-subsystem retraction tags) is a separate, still-open design/build decision,
and shipping the reservation without the producer avoids pre-committing #19 to a shape before its own design
pass. The suppression-check rewrite was checked against scope creep: it would have been easy to also broaden
suppression to `import:*`/`agent:*` removals while touching this line, but that's a behavior change nobody
asked for — preserved byte-for-byte via the namespace helper instead.

## Tests
- `tests/test_tags.py` (+3): `tag_source_namespace` across every namespace + the `"other"` defensive fallback;
  a regression test proving only `keyword:*` removals still suppress (guards the rename didn't silently widen
  inc-143 behavior); a migration test building a DB at `0046`, inserting legacy bare-value tag rows via raw
  SQL, upgrading to head, and asserting the rename + the untouched `"user"` sentinel.
- `tests/test_agent_writes.py`: updated assertion (`"ai-agent"` → `"agent:mcp"` for the tag; the paper-level
  `imported_source == "ai-agent"` assertion elsewhere in the same file is untouched, confirming the split).
- `tests/test_zotero_importer.py`: added an assertion that Zotero-imported tags carry `import:zotero` (no
  prior test checked tag provenance here at all).
- `tests/test_frontend_assembly.py`: unaffected, all green (46 passed) after the `10e_tagspanel.jsx` extraction.
- Full suite: **1354 passed, 1 skipped** (`pytest -n auto -q`, ~9 min) — up from 1351 (+3, matching the new
  test count above).

## Manual verification script
1. Start the app against the real library DB (`CALLOSUM_DB_URL` → `callosum-data/library.sqlite`).
2. Open the sidebar Tags browser (THEORY accordion → Tags tab). If the library has tags from more than one
   source (Zotero import + Crossref/OpenAlex/PubMed keyword backfills + any manual tags), confirm each source
   now renders under its own small uppercase header with a count, "Your tags" first.
3. Confirm the existing All/Yours/Keywords filter still narrows the list as before (unchanged, still shown
   only when both kinds are present) — grouping and filtering compose.
4. Hover a tag chip to confirm the tooltip text still reads correctly for a Zotero-imported tag ("Imported from
   Zotero") — the renamed `import:zotero` value routes through the updated `tagSourceLabel` fallback ladder.

## Documentation
- `.claude/docs/data-contracts.md` / `.claude/docs/glossary.md`: the tag provenance entries now describe the
  shipped contract instead of a "future-track reservation."
- `.claude/docs/INCREMENT-BACKLOG.md`: #9 removed (closed → `INCREMENT-BACKLOG-DONE.md`); #19's entry updated to
  note the vocabulary half is done and to sketch the recommended naming-only path for its remaining per-link
  question.
- **Not touched:** `HELP-DOCS-SYNCED` marker — tag provenance is an internal/backend contract with no
  user-facing help-text implication (the sidebar grouping is discoverable on sight, per the existing "Tags"
  help section's generic description).

## Next
#19 (tags ↔ findings/system-facts) is next in the decision queue — its design is now largely pre-answered by
this increment (use `system:{fact}` tag names, no schema change, per the backlog note above).
