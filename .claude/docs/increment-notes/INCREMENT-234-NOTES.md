# Increment 234 — Portable library bundle (B2 SP1, file-based collaboration)

The first of the collaboration track. Share a library — or a slice of one — **without a server and without shipping
copyrighted PDFs**: export to a versioned JSON file (metadata + tags + annotations + axis definitions, **NO PDFs**),
import/merge it into another library. The file-based, copyright-safe realization of the accounts-SP4 sharing
direction.

Maintainer forks (AskUserQuestion): **syntheses deferred to SP2** (they'd need citation re-anchoring to travel
honestly — SP1 is the clean "annotated bibliography" bundle); **axis definitions included** (whole-library only —
curated members travel by identity, keyword axes are definition-only + re-scored locally); **both whole-library +
selection** export.

## The design in one line

A **standalone** exporter/importer keyed on **natural identifiers** (paper by identity, tag by name, axis by label),
reusing the inc-93 citation-import async-job pattern + the inc-70 export download — borrowing the sync feature's
identity *idea*, not its crypto/`SyncTransport`/conflict engine (welded + private).

## Implemented

- **`app/backend/metadata/library_bundle.py`** (NEW):
  - `build_bundle(conn, *, scope, paper_ids)` → the bundle dict. `scope="library"` = all live papers + tags +
    annotations + **axis definitions** (`_axis_entries` — `standard`/`curated` only, never `my_publications`;
    curated axes carry their manual members by identity + position). `scope="selection"` = the chosen papers only,
    **no axes**.
  - `parse_bundle(content)` → bounded (`MAX_BUNDLE_BYTES = 20 MB`) + version-checked (`callosum_bundle == 1`, a
    `papers` list) → `BundleError` on a bad file (caught by the worker → a graceful job error).
  - `import_bundle(conn, bundle)` → `{summary, created}`. Per paper (in a `begin_nested()` savepoint):
    `find_existing_paper_by_identity` — **keeps the matched row** as the merge target (the correction vs.
    citation-import, which discards it). Existing → **metadata untouched**, gains the bundle's tags + annotations;
    new → `create_paper(imported_source="bundle-import")`. Tags get-or-create by name (a tag is colored only if
    uncolored); annotations dedup by `(page, bboxes, note)` + **drop `attachment_id`** (per-device pointer, applied
    NULL — coordinate honesty #2). Then axes (referenced-last): get-or-create by label (existing definition left
    as-is), curated members resolved by identity + added idempotently.
- **`routers/library.py`** — `POST /library/bundle/export` (sync raw `Response`, constant filename) +
  `POST /library/bundle/import` (202 → an async job that `import_bundle`s then **embeds the created papers** so they
  join search/axis-scoring) + `GET .../import/{job_id}`; `app.state.library_bundle_import_jobs` (app.py).
- **Frontend** — `28b_bundle.jsx` (`BundleImportModal`, clones `28_import.jsx`); `downloadBundle` (`00_lib.jsx`, a
  tokened raw POST so it carries the Remote-access token — the inc-172 lesson); "+ Add ▾" **Import bundle…** /
  **Export library bundle…** items (`10b_libmenus.jsx`); a selection bulk-bar **bundle** action (`10_pdf_layer.jsx`);
  the wiring in `03_library.jsx` (`bulkExportBundle`) + `40_app.jsx` (`bundleImportOpen`, `onExportBundle`).

## Honesty / values

No claim/signal/score → the rule-#9 gate is non-triggering. The **values layer** applies (collaboration/sharing is
an *emergent* value): adopted deliberately as the file-based, copyright-safe slice — **no PDFs** honors the
acquisition / no-paywall-circumvention veto (the recipient re-acquires their own copies), and a portable, open,
inspectable JSON with no lock-in / no server *strengthens* A5 sovereignty. Merge is additive & non-destructive (never
overwrites the recipient's metadata; `bundle-import` provenance kept out of the enrich-clobber allowlist). Audit
`.claude/security-audits/2026-07-01_library-bundle.md` PASS.

## Verification

`HF_HUB_OFFLINE=1 python -m pytest tests/test_library_bundle.py -q` → **8 passed** (hermetic, two throwaway SQLite
DBs): build-shape / selection-no-axes / round-trip-into-empty / re-import-idempotent / merge-non-destructive [existing
paper keeps its title + `user-edited` provenance, gains the tags + highlight] / curated-members-resolve-keyword-
definition-only / annotation-`attachment_id`-dropped / parse-caps [malformed / unknown version / oversized]. Full
suite **842 passed, 1 skipped**. QA surface **172/172 API + 753/753 FE, 0 uncovered** (`route_54_library_bundle.md`).
No egress, no PDFs, no new dependency, no migration.

**Headed-verified, no egress** (`.local/visual/drive_inc234_bundle.py`): a seeded library (paper + tag + highlight +
curated axis) with a fake embed model — **+ Add ▾ → Export library bundle…** downloads a `.json` (1 paper, tag +
note + curated axis, **NO** pdf/attachment), then **Import bundle…** → set the file → Import → the summary reports a
**merged** round-trip; 0 console/page errors, 0 off-machine (non-loopback) requests.

## Deferred (SP2)

**Syntheses** in the bundle — portable only with citation re-anchoring (each citation as quote + page + source-DOI →
region precision on the recipient's matching paper, flagged "the sender's verification, not re-checked here"). Its own
increment (touches `summaries`/`citation_mappings`/`evidence_quotes` + the synthesis renderer). PDFs never travel
(copyright). Fill-empty-on-merge stays out of scope (the inc-217 enricher does that on demand).
