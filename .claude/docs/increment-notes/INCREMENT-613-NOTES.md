# Increment 613 — Source-role v2 derivation moved into packaged application code

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on inc 612
`af53b1d2`. Local commit only: not pushed, not merged.

This is step 1 of the 0.6.0 modernization sequence, under the 2026-10-31 steering. Plan and audit:
`.claude/docs/research/2026-10-31_release-060-audit/`.

## Implemented
- **`app/backend/pdf_processing/structure_backfill.py` (new, 350 lines).** It holds the cache-only reference
  resolution and the per-paper, committed, resumable derivation of `chunk_structure`, moved **verbatim** from
  `tools/backfill_chunk_structure.py`:
  - `doi_owners`, `load_reference_metadata`, `infer_reference_region`, `detect_repeats`, `_paper_rows`;
  - `backfill`, `coverage`;
  - the constants they use.
- **Why it had to move.** The desktop installer stages only `app/backend`, `alembic` and `integrations`
  (`app/desktop-shell/packaging/stage_source.py:23`), so code living in `tools/` could never classify a user's
  library.
- **`tools/backfill_chunk_structure.py`** is now a thin CLI: argument parsing, `--inspect`, `--summary`, over the
  packaged functions.
- **Tests.**
  - `tests/test_backfill_doi_owners.py` and `tests/test_source_role_migration.py` import from the packaged module.
  - New `tests/test_structure_backfill_packaging.py` pins three things:
    - the module sits inside a staged directory;
    - it imports nothing first-party outside `app.backend`;
    - the CLI's `backfill`/`coverage` *are* the packaged functions, so the CLI and a future background job cannot
      diverge.
- **Documentation.** `.claude/CLAUDE.md` names the new owner. The `chunk_structure.py` docstring points at the new
  caller.

**Unchanged:**
- no rule, threshold or reason code;
- `DERIVATION_VERSION` stays `chunk-structure-v2`;
- no migration, no endpoint, no UI, no egress.

## Key technical detail: identity verification
The inc-612 tool (`git show af53b1d2:tools/backfill_chunk_structure.py`) and the packaged module each classified
their **own disposable copy** of three libraries, with sockets refused.

Copies:
- made with the SQLite backup API from read-only, immutable sources;
- stored under `.local/inc613-identity/`;
- the protected sources were never opened writable.

Comparison: a SHA-256 over every `chunk_structure` column except `created_at`, ordered by `chunk_id`, plus the
returned stats. Receipt: `.local/inc613-identity/IDENTITY_RECEIPT.json`.

| Library copy | Papers derived | Rows (all v2) | Identical rows / stats | Re-run | Other tables unchanged |
|---|---|---|---|---|---|
| Held-out `base_v2` (30 papers, Crossref anchored) | 30 | 5,105 | yes / yes | 0 re-derived | yes |
| Desktop snapshot 2026-10-29 (151 papers, previously 0 rows) | 151 | 42,044 | yes / yes | 0 re-derived | yes |
| Research master (v1 rows present) | 154 | 55,138 | yes / yes | **2 re-derived (both versions)** | yes |

Times: 10–128 s per library on this laptop, single-threaded and CPU-light. The desktop copy's other 26,042 chunks
belong to soft-deleted papers, which are correctly out of scope.

### Pre-existing defect found (not fixed here; reported)
`papers_with_current_structure` (`persistence/chunk_structure_repo.py:232`) counts **every** chunk of a paper, but
`_paper_rows` derives only article-role chunks.

**Effect.** A paper with a preregistration (or other non-article) attachment can never become current. On the
research master, papers 25 and 61 are re-derived on every run (74 and 75 preregistration chunks), and `coverage`
reports `papers_needing_derivation = 2` forever.

**Why it matters later.** It is harmless for the developer CLI. An automatic background job, however, would never
reach 100 % and would re-derive those papers on every tick.

**Smallest fix.** Restrict the currentness predicate to the same article document roles. This changes no derived
row; it changes only which papers count as current. It is proposed as the first item of the next increment.

## Manual verification script
1. `python tools/backfill_chunk_structure.py --db-url sqlite:///<disposable copy> --summary`. It reports v2 coverage
   exactly as before.
2. Run the same command without `--summary`, then again. The second run re-derives 0 papers on a library without
   non-article attachments.
3. Optionally, `python -I identity.py` from the session scratchpad
   (`C:\Users\cliff\AppData\Local\Temp\claude\C--Users-cliff-Dropbox-Dropbox-01-Work-callosum\3c115352-5d53-477d-81a4-047b43969fb2\scratchpad\inc613\identity.py`)
   re-runs the three-library identity comparison. It refuses to overwrite existing copies.

## Pytest
88 passed (focused):
- `test_structure_backfill_packaging`, `test_backfill_doi_owners`, `test_source_role_migration`;
- `test_chunk_structure`, `test_source_role_repair`, `test_reference_exclusion`.

Also green: ruff check and format on touched files, `check_line_budget.py` (675 files within the cap), `tach check`.

**Known pre-existing failure, not touched:** `check_demo_experience_coverage.py` and `check_website_coverage.py`
already fail on this branch at 612 (the deferral receipts stop at 610). Extending them needs Cliff's authorization,
as for 607–610.
