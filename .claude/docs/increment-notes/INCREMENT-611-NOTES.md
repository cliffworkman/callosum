# Increment 611: Scientific prose no longer excluded or demoted as bibliography

**Branch and status.** Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`),
on inc 610 `9d9417f9`. Not pushed, not merged.

**Deliverables:** `.claude/docs/research/2026-10-30_source-role-repair/`.

**Evidence status.** The motivating cases were adjudicated by blinded AI reviewers and never source-verified.
They are development evidence. The validation below is in-sample.

## Implemented

**`source_role.py` (new).** A pure, label-blind judgement of text form: substantive prose, prose-then-entries,
short finite clause, or not prose. It judges the text with citation apparatus stripped, and it detects entry
structure and entry starts so reference titles are not mistaken for prose.

**`chunk_structure.py`.** This file contains the inc-607 classifier.
- Inside an inferred reference region, substantive cited prose becomes `body_prose` / scientific
  (`ref_region.prose_veto.citations_stripped`).
- Fragments and prose-then-entries chunks become `unknown` (`ref_region.ambiguous.*`).
- The shape rule no longer claims substantive prose.
- Region provenance and the old reason codes are kept.

**`DERIVATION_VERSION` is now `chunk-structure-v2`.** v1 rows are stale: recorded, never obeyed. `--summary` in
`tools/backfill_chunk_structure.py` reports version coverage. The backfill is unchanged otherwise: per-paper,
resumable, idempotent, and writes only to `chunk_structure`.

**`reference_rescue.py` (new).** It replaces the categorical heading filter with `reference_filtered_rows`.
- The SQL exclusion is unchanged.
- A narrow `(id, chunk_version)` pass, memoized per process, rescues references-labelled chunks whose text is
  demonstrably not a reference list, excluding publisher notices.
- The rescue runs before boilerplate and vector retrieval, in the whole-library and faceted pools.

## Key technical detail

**The old prose veto's defect.** It capped `biblio_score` below 1.5. But in-text citations alone score 1.8:
0.8 for "et al." plus 1.0 for three years. So every well-cited Discussion paragraph inside an overextended region
was labelled bibliography.

**Why rescued rows merge by chunk id.** The heading rescue merges rescued rows back in chunk-id order. Ranking
input therefore equals what a single ordered query would have produced.

**Latency.** The first version materialised and re-assessed all 13,404 labelled rows on every query, costing
about 2.5 s. The shipped version costs a median 0.33 s per warm whole-library Ask; see the replay document.

## Manual verification script

1. Make a disposable copy:
   `python C:\Users\cliff\callosum-data\experiments\source-role-repair-20261030\make_copy.py`
   This refuses if the copy already exists.
2. Replay the old code: `python replay.py before`. It reproduces the frozen B/D selections, 10/10.
3. Reclassify the copy:
   `python tools/backfill_chunk_structure.py --db-url sqlite:///…/replay.sqlite`, then the same command with
   `--summary`. Expect 151/151 current at v2.
4. Replay the new code: `python replay.py after`, then `python lineage_diff.py`.
   - 5399 should be selected for WL15 under both profiles.
   - 58052 and 56894 should be selected for WL18 under MiniLM.
   - 56618 should be selected for D_q2 and D_p2.
   - SP18 should be unchanged.
5. Confirm only `chunk_structure` changed: run `python fingerprint.py fingerprints_after.json` and diff it against
   the before fingerprints.

## Pytest

227 passed (serial, focused, 15 files):
- 56 new in `test_source_role_repair`;
- 4 new in `test_source_role_migration`;
- 1 new in `test_reference_exclusion`.

`test_frontend_assembly` is not runnable in this worktree because `node_modules` is absent.
