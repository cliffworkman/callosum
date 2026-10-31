# Final validation and commit receipt (inc 611)

**Branch:** `integrate/inc607-608-ask`.
**Worktree:** `C:\Users\cliff\callosum-worktrees\integrate-607-608`.
**Parent:** inc 610 `9d9417f92792deef15c09aa6912a4ccccca6b46e` (the tree was clean at the start).

The commit containing this file is local only: no push, merge, tag, deploy or release. The 607–610 history is
untouched (new commit on top).

## Gates (run on the final tree)

| Gate | Result |
|---|---|
| `ruff check` (touched files) | All checks passed |
| `ruff format --check` (touched files) | 12 files already formatted |
| `tools/check_line_budget.py` | OK, 674 files under 600 (`pipeline.py` 519, `chunk_structure.py` 417, `source_role.py` 201, `reference_rescue.py` 99) |
| `tach check` | All modules validated |
| `bandit -ll` (changed app modules) | No issues |
| `tools/qa/build_surface_map.py check` | OK, every gated surface claimed (no API or UI surface changed) |
| Focused pytest (serial, 15 files) | **227 passed** |
| Mutation check (both repairs disabled) | 11 new tests fail, as intended |
| `test_frontend_assembly` | Not runnable here: no `node_modules`, esbuild absent. No frontend change |

The full suite was not run, per the task's resource rules. CI or a quiet machine should run `pytest -n auto -q`
before any merge.

## Constraint compliance

**Hardcoding.** No chunk id, paper, DOI or title special-cased. A grep of `app/` and the backfill for the six
known ids returns nothing. 607 is not globally disabled. Discussion-labelled chunks are not exempted. Section
metadata is never assumed correct: the shared assessment never reads it.

**No thresholds were tuned to adjudicated outcomes.** The floors (20 words, stopword ratio 0.22) come from the
existing prose veto. Three shape errors found while reading unadjudicated population samples were fixed and are
documented.

**Model and retrieval semantics are unchanged:**
- no LLM, NLI or remote service was used;
- MiniLM default and Arctic S opt-in;
- identity-scoped search, the fail-closed index check, 8 slots and deterministic ranking;
- DeBERTa untouched, along with inc 609 and inc 610 behaviour.

**607 scope.** 607 is not extended to faceted or broad synthesis.

**Protected data.** The protected databases, the four-condition experiment directory, the installed desktop
library, the master library, JUNO and production configuration were not touched. The source snapshot's SHA-256
was identical before and after the copy. All persisted reclassification happened in a fresh disposable copy.

**Resources.** No models were downloaded and no concurrent model workers ran; MiniLM and Arctic S were loaded
serially, local files only. No network was required.

**Experiments.** The historical 40-question pilot was not re-run. The replay is labelled in-sample and mechanistic.

## Files in the commit

**App:**
- `app/backend/pdf_processing/source_role.py` (new);
- `app/backend/pdf_processing/chunk_structure.py`;
- `app/backend/persistence/schema_chunk_structure.py`;
- `app/backend/summarization/reference_rescue.py` (new);
- `app/backend/summarization/chunk_filtering.py`;
- `app/backend/summarization/pipeline.py`;
- `app/backend/summarization/faceted_pipeline.py`;
- `app/backend/summarization/evidence_selection.py` (docstring only).

**Tool:** `tools/backfill_chunk_structure.py`.

**Tests:**
- `tests/test_source_role_repair.py` (new);
- `tests/test_source_role_migration.py` (new);
- `tests/test_reference_exclusion.py`.

**Docs:**
- this directory's six documents;
- `.claude/docs/increment-notes/INCREMENT-611-NOTES.md`;
- `.claude/security-audits/2026-10-30_source-role-repair.md`;
- `.claude/changes.md`;
- `.claude/CLAUDE.md`.

**Excluded:** private scholarly text and experimental databases. The replay artifacts stay in
`C:\Users\cliff\callosum-data\experiments\source-role-repair-20261030\`.

## Next steps (not started; each requires explicit authorization)

1. A held-out, source-verified evaluation of the new rules: precision on genuine references, recall on cited
   prose and the rescue population.
2. A v2 backfill of any real library. The installed and master libraries require approval.
3. A full-suite run before merge.
