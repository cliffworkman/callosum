# Increment 536 — imported reference-manager folders → axes

**Date:** 2026-08-30
**Scope:** backlog #57 Phase 6C. Surface imported Zotero structure through the existing Axis model and establish
the shared source-generic seam future native Mendeley/EndNote importers can populate. No native Mendeley/EndNote
client, provider/model behavior, citation/document semantics, or manual folder hierarchy was added.

## Design

Zotero's adapter already read `parentCollectionID`; the importer discarded it. `_upsert_collections` is now a
two-pass operation: establish every local id, then persist names/parents regardless of source order. Re-reading a
library imported before this increment backfills the previously lost hierarchy.

`GET /library/imported-collections/axes` previews top-level collections with descendant-inclusive paper counts.
`POST` is an explicit one-time snapshot:

- default `curated`: exact descendant-inclusive papers become manual, ordered assignments;
- opt-in `standard`: exact papers become unordered manual anchors, then ordinary existing Axis scoring jobs score
  the rest of the library locally by the folder label.

The `imported_collection_axes` provenance table links one source collection to one ordinary axis. It prevents
duplicates but does not put import semantics on `axes`. Re-import never edits the axis; deleting either side
removes only the link and permits a clean later replacement.

The UI lives in the existing Zotero import body, so it is discoverable both from Library and onboarding and also
surfaces collections from an earlier import when the dialog is reopened. Existing pre-536 imports should be read
once more before axis creation to restore nesting.

## Boundaries

- Sources are allowlisted to `zotero | mendeley | endnote`; kinds to `curated | standard`.
- 2,000 collections, 100,000 memberships, and 100 axes per action are hard caps; labels are capped at 200.
- Parent outside the source, cycles, and no-root hierarchies fail closed before axis mutation.
- Empty top-level folders are skipped. Nested membership is a deterministic set union ordered by paper id.
- Scoring reuses `run_axis_score_job`; no scoring/provider logic is duplicated and no provider call occurs.
- This does not add Callosum-native folders or nesting. Axes remain the only product organization model.

## Verification

- Focused Zotero importer/collection-axis/API: **21 passed** in 75.68s.
- Focused collection-axis/frontend assembly after boundary/cascade additions: **90 passed** in 34.33s.
- Axes/status/migrations/startup/frontend affected suite: **154 passed** in 171.18s.
- Final combined importer/API/axis/status/migration/access/help/frontend affected suite: **239 passed** in
  286.81s.
- `python tools/build_frontend.py` wrote the assembled app successfully; sync test passed in the 90-test run.
- Ruff format/check on all touched Python files: passed.
- Bandit and Tach (`[OK] All modules validated!`): passed.
- QA surface map: **437/437 API surfaces covered**; Route 93 extended for every new control/contract.
- Line-budget gate passed without `--list`; the optional watch-list rendering hit this Windows console's
  pre-existing cp1252 inability to print `≤`, not a source violation.
- Website coverage review: **69 QA routes, 6 external surfaces, 20 current figures**; copy refreshed and the
  existing library-map visual remains representative.
- Full collection: **2600 tests** in 15.78s. A fresh serial full-suite run hit its fixed one-hour timeout without
  producing a final summary. The separately reproduced `tests/test_summary_overview.py` collection-order circular
  import follows `overview_lifecycle -> api.__init__ -> app -> summaries -> summary_overview` and does not import
  any inc-536 module; both are pre-existing harness limitations, not represented as passes.
- Real browser interaction was not run at the user's request; Route 93 steps 15–20 are queued for the later
  consolidated manual checklist.
- Final staged pre-commit passed every hook: whitespace/EOF, merge markers, added-file size, Ruff format/check,
  line budget, Bandit, and Tach. Added-line secret/private-path scan and `git diff --check` passed; the personal
  EndNote fixture directory remains gitignored. An initial `--all-files` hygiene probe found pre-existing
  historical whitespace/EOF drift; its hook-only edits were reversed and are not part of this increment.
- Commit and remote CI follow this receipt.

## Revert

Revert this increment commit. The additive provenance table may remain harmless on an existing migrated DB;
collections and user-owned axes are not deleted by the migration or downgrade convention.
