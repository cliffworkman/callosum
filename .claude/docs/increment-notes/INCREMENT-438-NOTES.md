# Increment 438 — duplicate-safe axis scoring

## Outcome

Axis scoring now emits at most one result per paper even when a long-lived database contains several logically current
embedding records for that paper. Re-scoring no longer fails on the `cluster_node_papers` composite primary key, and
assigned/uncertain counts cannot be inflated by storage duplication.

## Root cause and implementation

The desktop app uses its persistent app-data database, unlike the repository browser/dev default. Read-only inspection
found 45 paper/model embedding groups with duplicates (162 extra rows, up to five copies). Paper 46—the id in the
reported exception—had five current `all-MiniLM-L6-v2` embeddings created within one second. All duplicate paper
embeddings were created in one 65-second burst while several first-time axis jobs overlapped.

`PaperEmbeddingRepresentation` correctly returned every matching embedding id, but
`_score_candidate_embeddings` treated each vector hit as a distinct paper result. `_replace_axis_assignments` then
deleted the old axis membership and attempted one insert per score, so the second hit for the same paper violated
`PRIMARY KEY (cluster_node_id, paper_id)`.

The scorer now aggregates raw vector hits by `paper_id` before assignment-mode tiering. It retains the strongest
confidence and uses the lowest/oldest embedding id as a deterministic tie-break for identical vectors. This places the
invariant at the signal boundary rather than hiding the error with `INSERT OR IGNORE`, which would leave duplicate
scores and misleading counts. Existing embedding rows and vectors are not deleted or rewritten; no migration or live
data repair is required.

## Principles and experience pass

- **Principles 3, 4, and 7; worked Example 2:** an axis score is a deterministic, inspectable candidate signal about a
  paper. Storage duplication must not manufacture repeated signals or alter a visible count. The easy misaligned patch
  was to ignore the duplicate assignment insert; the aligned patch canonicalizes the deterministic score stream first.
- **Corpus builder:** Score should complete and show each paper once. This backend reliability correction introduces no
  new control, workflow, label, or output, so reception and intended use need no UI change or persona-agent pass.
- **Help:** no documented workflow changed; the existing Axes help remains current.

## QA and verification

- Added a hermetic five-copy regression matching the desktop failure; it failed with the same SQLAlchemy/SQLite
  `UNIQUE constraint failed` stack before the fix and passes afterward.
- Extended Axes QA route 15 to overlap several fresh scoring jobs and require unique per-paper cluster results.
- `pytest tests/test_axis_scoring.py tests/test_axes.py -q` — **42 passed**.
- `pytest -n auto -q` — **1788 passed, 1 skipped**.
- Ruff format/check — clean.
- `python tools/check_line_budget.py` — all **459** application-source files within the 600-line cap.
- `python tools/qa/build_surface_map.py check --strict` — **352/352 API** and **1545/1545 frontend** surfaces covered.

### Desktop-data validation

The live app-data DB was inspected read-only and never modified. SQLite's backup API copied it into `.local/`; the
current source then auto-migrated and scored axis 2 on that disposable copy. The job completed with **23 assigned, 12
uncertain**, and `GET /axes/2/clusters` returned **30 members / 30 unique paper ids**. The temporary copy was retained
under `.local/inc438-desktop-copy/` because the execution sandbox blocked its attempted cleanup; it contains no new
source data beyond the user's already-local database copy.

## Security and privacy

No endpoint, request/response contract, egress, model, dependency, filesystem path, or authorization behavior changed.
The diagnostic used only local read-only inspection plus a local disposable backup; no library content left the
machine.

## Rollback

Restore `_score_candidate_embeddings` to append every embedding hit directly and remove the focused regression/QA
step. No schema or user-data rollback is required.
