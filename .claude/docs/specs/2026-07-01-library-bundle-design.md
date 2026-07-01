# Portable Library Bundle — B2 SP1 design

**Status:** approved (brainstorm 2026-07-01) → this spec → plan → build.
**Backlog:** B2 (collaboration / shared libraries — the file-based, copyright-safe realization of the accounts-SP4
sharing direction).

## Goal

Export a callosum library — or a selection of papers — to a **versioned JSON file** carrying the user's **metadata,
tags, annotations, and axis definitions but NO PDF files**, and import/merge such a file into another library. A file
the user hands off: **no server, no automatic egress**. Copyright-safe (the recipient re-acquires their own PDFs via
the OA lane / their own manager). SP1 is the "annotated bibliography" bundle; **syntheses are SP2** (they need
citation re-anchoring to be honest — see Deferred).

## Why this shape

Two proven anchors, reused verbatim:
- **inc-93 citation-import** (`metadata/citation_import.py` + `routers/library.py`): the async-job import pattern
  (`POST /library/import` → 202 + `JobStore`; `GET .../import/{job_id}`; per-record `begin_nested()` savepoints;
  byte/record caps; file text in the JSON `content` string, so **no multipart / no server-side path → no traversal**).
- **inc-70 citation-export** (`metadata/citation_export.py` + `POST /papers/export`): the download mechanism (a raw
  `fastapi.Response` with a **constant** `Content-Disposition` filename; the frontend `_downloadBlob` raw-fetch, since
  `apiPost` forces `.json()`).

Plus the **cross-library identity primitive** `repository.find_existing_paper_by_identity(conn, *, doi,
openalex_work_id, semantic_scholar_paper_id, zotero_library_id, zotero_item_key, title, year,
first_author_family_name) -> tuple[str, RowMapping] | None` — dedup precedence DOI → OpenAlex → S2 → zotero-pair →
title+year+author. **The load-bearing correction vs. citation-import:** citation-import discards the returned row; the
bundle **keeps `existing_row["id"]`** as the merge target its tags/annotations attach onto.

The E2E-sync machinery (`sync/changeset.py`, `sync/engine.py`) proved the identity/FK-translation *concept* but is
welded to crypto + `SyncTransport` + `sync_state`/conflict bookkeeping (its `_apply_*` are private). A **standalone**
exporter/importer keyed on **natural identifiers** (paper: the identity fields; tag: name; axis: label) is the cleaner
call — re-attach on import is by content match, not a shared UUID map. Sync is not imported.

## Bundle format (JSON, versioned)

```jsonc
{
  "callosum_bundle": 1,               // schema version; import rejects an unknown/absent version (422)
  "exported_at": "<ISO-8601>",        // server-stamped (datetime.now(UTC)); display-only
  "generator": "callosum",
  "scope": "library" | "selection",
  "papers": [
    {
      "identity": {                   // for dedup on import (any subset present)
        "doi": "...", "openalex_work_id": "...", "pmid": "...", "arxiv": "...",
        "title": "...", "year": 2020, "first_author_family_name": "..."
      },
      "csl_json": { ... },            // the canonical record (title/year/venue/authors/DOI/…)
      "item_type": "article-journal",
      "abstract": "...",              // raw (nullable); csl_json may also carry it
      "tags": [ { "name": "...", "color": "blue"|null, "source": "keyword:crossref"|null } ],
      "annotations": [
        { "page": 3, "bboxes_json": [...], "note": "...", "color": "yellow"|null,
          "anchor_text": "...", "prefix": "...", "suffix": "...", "source": "user" }
      ]
    }
  ],
  "axes": [                           // whole-library export only (omitted for a selection)
    { "label": "...", "description": "...", "scoring_gain": 0.35, "kind": "standard"|"curated",
      "members": [ { "identity": { ... }, "position": 0 } ]   // curated axes only; keyword axes carry no members
    }
  ]
}
```

Notes:
- `bboxes_json` is stored in `pdf-points-top-left` (the inc-29 overlay basis). It travels verbatim; the **overlay only
  re-renders once the recipient acquires the same PDF** (the honest limitation — the note + page always land, and
  `anchor_text` is the text-anchored recovery hint). This is coordinate honesty #2: we never draw a box against a PDF
  that isn't there.
- `attachment_id` is **dropped** (per-device PDF pointer), exactly as sync's annotation `drop` does.
- Papers carry no `id` / no local FK ids — identity is by content.

## Export

`POST /library/bundle/export` `{ scope: "library" | "selection", paper_ids?: [int] }`
- `scope="library"` → every **live** paper (`deleted_at IS NULL`) + its tags + annotations + **all axes** (standard
  definitions + curated members that resolve to an exported paper's identity).
- `scope="selection"` → the given `paper_ids` (bounded; 422 if empty) + their tags + annotations; **no axes** (a
  selection is a transient set, not a library-level structure).
- Returns a **raw `Response`** (media type `application/json`, `Content-Disposition: attachment;
  filename="callosum-library-bundle.json"` — a **constant** filename, no request data in the path). Synchronous
  (serialize rows; no heavy compute — the `/papers/export` posture).
- Bound-param reads; live papers only; tags via `tags_repo`, annotations via `annotations_repo` (native sources only:
  `source IN ('user','synthesis')` — imported Zotero rows are left out; SP1 exports the user's own marks).

## Import

`POST /library/bundle/import` `{ content: <bundle JSON text> }` → **202** `{ job_id, status }` (async, mirrors
citation-import). `GET /library/bundle/import/{job_id}` → `{ job_id, status, detail, summary, progress }`.

- **Boundary caps (rule #4):** `content` is a Pydantic `Field(min_length=1, max_length=MAX_BUNDLE_BYTES + slack)`;
  the parser enforces `MAX_BUNDLE_BYTES = 20_000_000` (~20 MB — annotations add bulk vs. citation-import's 5 MB) and
  `MAX_BUNDLE_PAPERS = 20_000`; a paper's `tags`/`annotations` are each capped (e.g. 200/paper) to bound work.
  `json.loads` failure / bad shape / unknown `callosum_bundle` version → the job errors gracefully (never a crash);
  the endpoint 422s on an empty/oversized `content` before the job starts.
- **Worker** (`_run_bundle_import_job`, one `engine.begin()`):
  1. **Papers** — per paper, in a `begin_nested()` savepoint (a bad record is skipped + counted, never fatal):
     `find_existing_paper_by_identity(...)` (pass all identity fields incl. `openalex_work_id`). Found → **merge
     target** = `existing_row["id"]`, **metadata untouched** (`papers_merged += 1`). Not found →
     `create_paper(imported_source="bundle-import", **csl_record_to_paper_fields(csl_json))` (`papers_created += 1`);
     collect its id for embedding.
  2. **Tags** — per paper tag: `tags_repo.add_tag_to_paper(conn, paper_id, name, import_source=source)` (get-or-create
     by name; idempotent link), then `set_tag_color` if a color is carried (`tags_applied += 1`).
  3. **Annotations** — per annotation: skip if the paper already has one with the same `(page, bboxes_json, note)`
     (idempotent re-import); else `annotations_repo.create_annotation(paper_id, attachment_id=None, page, bboxes_json,
     note, color, anchor_text/prefix/suffix, source)` (`annotations_added += 1`).
  4. **Axes** (whole-library bundles) — per axis: **get-or-create by label**. Existing axis → **reuse it, its
     definition is left as-is** (non-destructive: the recipient's axis wins). New axis → `create_axis(kind=…,
     description, scoring_gain)` (`axes_created += 1`). Then, for a **curated** axis (new or existing), resolve each
     member's identity → local `paper_id` and add it as a **manual member** (confidence NULL) with `position` via the
     inc-211 `append_member_position`/`set_member_order` — **idempotent** (an already-present member is skipped);
     members that don't resolve to a local paper are skipped; each newly-added member counts in `axes_members_added`.
     A **keyword** axis carries **definition only** (the recipient runs Score; the bundle has no scored memberships).
  5. **Embed** the newly-created papers (`embed_papers(conn, model=app.state.embedding_model, vector_store=…,
     paper_ids=new_ids, on_progress=…)`, mirroring citation-import) so they join axis-scoring / dedup.
  6. `mark_done` with `summary = { papers_created, papers_merged, tags_applied, annotations_added, axes_created,
     axes_members_added, skipped }`.
- `app.state.library_bundle_import_jobs = JobStore()` (one line in `app.py`, beside `library_import_jobs`).

**Merge is additive & non-destructive:** an existing paper keeps its own metadata/edits; the bundle only *adds* its
tags + annotations onto it. (Filling a merged paper's empty fields is deliberately **out of scope** — that is the
separate inc-217 gap-fill enricher.)

## Frontend

- **Import bundle…** — a "+ Add ▾" (`10b_libmenus.jsx` `AddMenu`) item (alongside "Import citations…") →
  `BundleImportModal` (cloned from `28_import.jsx`): file picker (`await file.text()`) → `POST /library/bundle/import`
  → poll `GET …/import/{job_id}` (`<ProgressBar>`) → summary (papers created/merged, tags applied, annotations added,
  axes created; skipped) → `onImported()` refreshes the library + axes.
- **Export library bundle…** — a "+ Add ▾" item (the menu is the library data-in/out home) → `downloadBundle(scope:
  "library")` (a raw tokened `fetch` → `_downloadBlob(await res.blob(), "callosum-library-bundle.json")`, the inc-70 /
  inc-172 pattern so it carries the Remote-access token).
- **Export bundle** — a selection bulk-bar action (`10_pdf_layer.jsx`, beside summarize/export/merge) →
  `downloadBundle(scope: "selection", paper_ids)`.
- No new CSS beyond the cloned modal (reuse `.scan-*` / `.progress-*` recipes; tokens only, rule #8).

## Gates

- **Security audit** (`.claude/security-audits/2026-07-01_library-bundle.md`) — triggers: new endpoints (#1) + a new
  file-ingestion path (#3). Cover: input validation + size/record/per-paper caps (rule #4); bound-param inserts (rule
  #3); text-in-body → **no path traversal** (the citation-import posture); constant export filename; `bundle-import`
  provenance kept out of the enrich-clobber allowlist; **no egress** (a local file the user hands off — NOT the Gemini
  gate, and no network call at all); no new dependency. End PASS.
- **Principles / values** — **aligned, adopted deliberately.** No PDFs honors the acquisition / no-paywall-circumvention
  veto (the recipient re-acquires their own copies). A portable, open-JSON, no-server, no-lock-in bundle *strengthens*
  A5 (data sovereignty — inspectability over authority, defaults are the user's). Coordinate honesty #2 preserved
  (annotation boxes only render against a present PDF). Nothing here produces a claim/score/judgment → the rule-#9
  claim/signal gate is non-triggering; the **values layer** applies because "collaboration/sharing" is an *emergent*
  value — adopted deliberately here as the file-based, copyright-safe slice, no divergent tension.
- **Rule #10 (QA):** new `route_54_library_bundle.md` (the 3 endpoints + the modal + the two export controls);
  assertions: additive/non-destructive merge, no-PDF, no-egress, identity dedup, the annotation-needs-same-PDF caveat.
  Keep surface 0-uncovered.
- **Rule #1:** `library_bundle.py` (build + import, well under 600); `routers/library.py` gains 3 endpoints (re-measure
  — split the bundle endpoints to `routers/library_bundle.py` if it crosses 600). No migration.

## Verification

- **pytest `tests/test_library_bundle.py`** (hermetic — a fake embedding model + vector store, no network):
  build a bundle from a seeded library (papers + tags + annotations + a curated + a keyword axis); **round-trip** into a
  second empty DB → the papers/tags/annotations/axes land; **re-import is idempotent** (no dup papers/tags/annotations/
  members); **merge is non-destructive** (an existing paper with different metadata keeps it, gains the bundle's tags +
  annotations); **selection export** carries only the chosen papers + no axes; a **curated axis** member resolves by
  identity, a **keyword axis** imports definition-only; **caps** (oversized `content` → 422; a malformed record →
  skipped, counted; unknown version → job error); the **annotation `attachment_id` is dropped** (applied NULL).
- **Headed, no egress** (`.local/visual/drive_inc234_bundle.py`): seeded library → **Export library bundle** downloads
  a JSON file → **Import bundle** into a fresh instance → the summary reports created/merged/tags/annotations/axes and
  the papers + tags + a highlight land; 0 console/page/genai.
- Full suite green; `ruff` + `format`; `python tools/build_frontend.py` (+ `test_frontend_assembly`); QA `check`
  0-uncovered; help corpus "Sharing a library (bundle export/import)" (`HELP-DOCS-SYNCED`); commit (excluding `www/`),
  push, watch CI.

## Deferred (SP2 and beyond)

- **Syntheses** — portable only with citation **re-anchoring**: each citation travels as `quote + page +
  source-paper-DOI`, re-attaches to the recipient's matching paper at **region precision** (open-at-page, no fabricated
  box), and the synthesis is flagged "imported — the sender's verification, not re-checked here." Its own increment
  (touches `summaries`/`citation_mappings`/`evidence_quotes` + the synthesis renderer).
- **PDFs** — never in the bundle (copyright); the recipient uses the OA-acquire lane.
- **Fill-empty on merge** — the inc-217 gap-fill enricher already does this on demand; the bundle stays purely additive.
- **Whole-library axes for a selection** / a manifest of "what the recipient is missing" — later, if wanted.
