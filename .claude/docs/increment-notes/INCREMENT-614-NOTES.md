# Increment 614 — Classification currentness covers exactly the classified population

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on inc 613
`829f35f4`. Local commit only: not pushed, not merged.

Authorized by the 2026-10-31 "Increment 614 and Bounded DeBERTa Qualification" instruction, §1. It removes the
modernization blocker found in inc 613 (`RELEASE_060_BLOCKER_MATRIX.md` B4).

## Implemented
- **`app/backend/persistence/chunk_structure_repo.py`**
  - Adds `CLASSIFIED_DOCUMENT_ROLES` (= `ARTICLE_DOCUMENT_ROLES`).
  - Adds `classified_chunks_clause()`: one predicate over `chunks JOIN attachments` naming exactly the chunks the
    source-role derivation classifies.
  - Adds `papers_with_classified_chunks()`.
  - `papers_with_current_structure` now evaluates only that population: same join, same predicate. A preregistration,
    protocol, supplement or other chunk can no longer keep a paper stale forever.
- **`app/backend/pdf_processing/structure_backfill.py`**
  - `_paper_rows` uses the **same** `classified_chunks_clause()`, replacing its private
    `attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES)`. The two populations are now one definition rather
    than two copies.
  - `coverage()` counts as targets only live papers that have classified chunks.
  - It adds `papers_without_classified_chunks`, so a registration-only paper is visibly neither current nor pending.
- **`tests/test_structure_currentness.py`** (new, 5 tests):
  - the population constant;
  - a mixed-attachment paper (article + preregistration + supplement + other) and a legacy `primary` + protocol
    paper become current and stay current, while a clean all-article paper is unaffected;
  - a paper with no classified chunks is neither pending nor looping, and gets no rows;
  - a new article chunk makes the paper pending, but a new registration chunk does not;
  - text-hash, chunk-version and derivation-version changes on classified chunks invalidate; edits to non-classified
    chunks do not.

**Unchanged:**
- every classifier rule and threshold;
- `DERIVATION_VERSION = chunk-structure-v2`;
- the per-paper transactional replace (`replace_paper_structure`);
- which chunks are eligible scientific evidence (inc 425 document scope);
- every retrieval reader;
- no migration, endpoint, UI or egress.

## Currentness and eligibility contract (as of inc 614)
1. **Classified population:** chunks whose attachment's canonical document role is in `CLASSIFIED_DOCUMENT_ROLES`
   (article full text, with legacy `primary`/blank roles normalized by `document_roles`).
2. **A paper is a derivation target** iff it is live and has at least one classified chunk.
3. **A paper is current** iff every classified chunk has a `chunk_structure` row with:
   - `derivation_version == DERIVATION_VERSION`;
   - `raw_sha == sha256(live text)`;
   - `chunk_version == live chunk_version`.
4. **Pending** = target and not current. A target with no classified chunks cannot exist, so a registration-only
   paper never loops.
5. This defines classification progress only. It is **not** the evidence-eligibility rule: retrieval keeps its own
   inc 425 document-scope predicates and treats unclassified or stale chunks fail-open, exactly as before.

## Key technical detail: output identity and idempotence receipt
The inc-613 code (`829f35f4` copies of `structure_backfill.py` and `chunk_structure_repo.py`) and the inc-614 code
each ran **three times** on their **own disposable copy** of each library. Copies were made with the SQLite backup
API from immutable read-only sources, with sockets refused. Receipt:
`C:\Users\cliff\callosum-worktrees\integrate-607-608\.local\inc614-identity\IDENTITY_RECEIPT_614.json`.

| Library copy | Rows | Identical `chunk_structure` after run 1 / after run 3 | Run-1 stats identical | Re-derived on runs 2, 3: inc 613 → inc 614 | Pending after: 613 → 614 | Other tables unchanged |
|---|---|---|---|---|---|---|
| Held-out `base_v2` | 5,105 | yes / yes | yes | 0, 0 → 0, 0 | 0 → 0 | yes |
| Desktop snapshot | 42,044 | yes / yes | yes | 0, 0 → 0, 0 | 0 → 0 | yes |
| Research master | 55,138 | yes / yes | yes | **2, 2 → 0, 0** | **2 → 0** | yes |

On the research master, inc 613 left papers 25 and 61 pending; under inc 614 both are current:
- paper 25: 322 `primary` chunks plus 74 `preregistration` chunks;
- paper 61: 68 `primary` chunks plus 75 `preregistration` chunks.

None of the three libraries has a registration-only paper (`papers_without_classified_chunks = 0`). That case is
covered by the synthetic test.

**Red check:** run on the inc-613 code, the mixed-paper scenario re-derives the same paper on every run and reports it
pending forever (reproduced before the fix).

## Manual verification script
1. On a disposable library copy: `python tools/backfill_chunk_structure.py --db-url sqlite:///<copy>`, then repeat.
   The second run reports `papers: 0`, and `--summary` shows `papers_needing_derivation: 0`.
2. On a copy of the research master, papers 25 and 61 no longer appear as re-derived on the second run.

## Pytest
- **113 passed (focused).**
  - The new currentness file (5), the inc-613 packaging tests and `doi_owners`;
  - `source_role_migration`, `chunk_structure`, `source_role_repair` and `reference_exclusion`: 93 together with the
    above;
  - `ask_integration_607_608`, `evidence_eligibility` and `reference_eligibility_selection`: 20.
- **Also green:** ruff check and format on the touched files, `check_line_budget.py`, `tach check`.
- The full suite was not run (it is the pre-RC gate).
