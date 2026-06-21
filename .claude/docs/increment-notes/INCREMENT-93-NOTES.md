# Increment 93 — BibTeX / RIS / CSL-JSON import

The patter's **carrot** (chores were inc 91 filter-by-type + inc 92 un-dismiss). The inverse of inc-70 export:
drop in a `.bib` / `.ris` / `.json` → parse → dedup → create metadata-only library papers → embed. Reference-
manager-first parity (accept libraries from Zotero/Mendeley/EndNote). New ingestion path → security-audit gate
fired (PASS); fact-gathering ingestion, so the Principles gate is light (same posture as the Zotero importer +
the inc-87 scan).

## Implemented
- **`app/backend/metadata/citation_import.py`** (NEW, ~315 lines) — **hand-rolled, no new dependency** (project
  ethos; cf. inc-75 arXiv): `parse_bibtex` (linear brace-matcher over `@type{key, field = {…}|"…"|bareword}`;
  skips `@comment`/`@preamble`/`@string`; `{`-delimited only), `parse_ris` (`TAG  - value` lines, `TY`…`ER`
  records), `parse_csl_json` (stdlib `json`; list or `{items:[…]}`), `detect_format` (sniff). All produce
  **CSL-shaped dicts** (inverting `citation_export`'s field/type maps); `csl_record_to_paper_fields` maps a CSL
  record → `create_paper` kwargs (`csl_json` stored whole → CSL-JSON round-trips losslessly; `item_type` = the
  CSL type so the inc-91 Type facet labels it). `import_citations(conn, content, fmt)` parses → per-record
  `begin_nested()` savepoint → dedup via `find_existing_paper_by_identity` (DOI → title+year+author) → else
  `create_paper(imported_source="<fmt>-import")`; returns `{created, duplicate, failed, format}`. Caps
  `MAX_IMPORT_BYTES` 5 MB + `MAX_IMPORT_RECORDS` 5000.
- **`app/backend/api/routers/library.py`** — `POST /library/import {content, format}` (async, 202) +
  `GET /library/import/{job_id}`, reusing the inc-87 scan scaffolding (`JobStore`, `_embedding_model`/
  `_vector_store`, `embed_papers`). `_run_import_job`: `import_citations` → `embed_papers(new ids)` → counts.
  New `app.state.library_import_jobs` in `create_app`.
- **Frontend** — new chunk `28_import.jsx` (`ImportModal`, clones `ScanModal`): a `<input type="file"
  accept=".bib,.ris,.json,.txt">` → browser reads the text → infers format from the extension → `POST
  /library/import` → polls → "N imported · M already in library · K skipped". An **Import** button in the
  library `.lib-head` (`10_pdf_layer.jsx`, next to **Scan folder**); `40_app.jsx` `importOpen` state. Reuses
  existing `.scan-row`/`.axis-*`/`.btn-*` styles — **no new CSS**. Rebuilt `callosum-app.html`.

## Key technical detail
**Entirely local — no egress.** The file's metadata is authoritative, so import calls no external service (no
Crossref, no Gemini); the browser reads the file and POSTs its **text in the JSON body** (no multipart/upload
surface, and — unlike the inc-87 scan — no server-side file path, so no traversal surface). `<fmt>-import` is
deliberately outside enrichment's `_can_update_from_crossref` allowlist, so a later batch-enrich won't clobber
the imported metadata (same guard as user-edits, inc 49). The BibTeX `{{…}}` author form is preserved as a CSL
`literal` (organisation) by stripping only the **outer** field delimiter before author-splitting — a generic
full-brace-strip would have turned "World Health Organization" into a person.

## Manual verification script
1. Export a few papers → BibTeX (bulk bar → `export…`). Click **Import** → choose that `.bib` → "N imported".
2. Import it again → all "already in library" (deduped, no copies).
3. Import a real Zotero/Mendeley `.ris` → papers appear with title/author/year, filterable by **type**.
   _(Visual check delegated to the user.)_

## Pytest
**395 passed, 1 skipped** (+9 in `test_citation_import.py`: the three parsers, `detect_format`, the mapping,
create+dedup+isolate, the export→import round-trip, the endpoint, and unrecognised-content). `ruff` clean; audit
`.claude/security-audits/2026-06-21_citation-import.md` **PASS**. No migration, no egress, no new dependency.
