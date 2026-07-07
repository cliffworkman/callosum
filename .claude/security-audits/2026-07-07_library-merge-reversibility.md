# Security Audit — Reversible un-merge (#16)

**Date:** 2026-07-07
**Feature:** A reversibility net for the inc-161 non-destructive paper merge. `paper_merge.merge_papers` records a
self-contained reversal snapshot on a `merge_operations` row + marks husks `merged_into`; `paper_unmerge.unmerge`
replays it exactly; two new endpoints — `POST /merge/{merge_operation_id}/undo`, `GET /papers/{paper_id}/merge-origin`.
**Audit gate triggers:** new API endpoints (#1) + a net-new feature spanning 3+ files (#5). No new dependency, no
new external fetch, no new file-write path.

## Threat review

- **Input validation.** `merge_operation_id` / `paper_id` are `int` path params (FastAPI coerces + 422s on
  non-int). `unmerge` fails closed: unknown op → `UnmergeError` (422); already-undone op → 422. `merge_origin`
  returns `null` for a paper that is not the survivor of an active merge. No request body is trusted for table or
  column names.
- **SQL injection (rule #3).** All statements are SQLAlchemy Core bound-parameter UPDATE/DELETE/SELECT. The only
  table names used come from a **hardcoded** constant (`_REPOINT_TABLES` → `_REPOINT_BY_NAME`); the snapshot's
  `table` keys are looked up against that fixed map (a KeyError, not an injection, on an unknown name) — never
  interpolated. Column names are literals.
- **Data egress (invariant #3).** Un-merge + merge-origin are **entirely local** — no external call, no library
  text leaves the machine. The Gemini gate is untouched. (QA route asserts 0 genai-host requests.)
- **Data safety / atomicity.** Un-merge runs inside the endpoint's single transaction (`conn.commit()` once at
  the end); any failure rolls the whole reversal back — no partial un-merge. Every un-merge step is an
  UPDATE/DELETE (no row re-insertion), so there is no autoincrement-id collision or timestamp-coercion hazard.
  The survivor's record is restored **before** a husk reclaims a freed UNIQUE id (e.g. a DOI), so the UNIQUE
  constraint cannot trip. Exact restoration is proven by the merge→un-merge round-trip test.
- **No dangling undo record.** `purge_paper` refuses to purge **either** a merged-away husk (`merged_into` set) or
  an active-merge survivor (a `merge_operations` row with `status='active'` names it as canonical); `purge_all_trashed`
  skips merged-away papers. So the undo record + its husks can never be hard-deleted out from under an un-merge.
- **Access control.** Un-merge is a mutating `POST` → blocked with **403** under `CALLOSUM_READ_ONLY` and requires
  the bearer token when Remote access is enabled (the `AccessControlMiddleware` gates it like every write).
  `merge-origin` is a read `GET` (allowed in read-only). The frontend gates the Un-merge control on `!readOnly`.
- **Resource caps.** Bounded by the merge's own limit (`MAX_MERGE_PAPERS = 20` husks) and the paper's finite row
  counts; no unbounded loop or recursion. The snapshot is bounded JSON on one row.
- **File-path safety.** No filesystem access — attachments only have their `paper_id` re-pointed; PDF files on
  disk are never moved, read, or written.
- **Supply chain.** No new dependency.

## Negative-path checks (results)

- `POST /merge/{unknown}/undo` → **422** ("Merge operation not found."). ✓ (`test_unmerge_endpoint_roundtrip`)
- Second `POST /merge/{id}/undo` on an already-undone op → **422** ("already been un-merged."). ✓
- `GET /papers/{non-survivor}/merge-origin` → **null** (not an error). ✓ (`test_merge_origin_and_double_unmerge_guard`)
- Purge a merged-away husk → **False** (blocked); purge an active-merge survivor → **False** (blocked). ✓
  (`test_merged_away_husk_hidden_from_trash_and_not_purgeable`)
- Round-trip: merge → un-merge restores the survivor's record + the husk's moved PDFs/tags/highlights + removes
  the survivor's added union links, exactly. ✓ (`test_merge_then_unmerge_restores_survivor_and_husk`)

## Verification

`pytest` full suite **1061 passed, 1 skipped**; the 16-test reversibility suite + the inc-161 merge suite green;
QA API surface coverage 209/209 (route 24 extended). Frontend built clean; frontend-assembly test green.

## Result

**Security Audit: PASS.** Local, bound-param, all-or-nothing reversal with a fixed table allowlist, guarded so the
undo record can't be orphaned, and gated behind the standard read-only/access-control middleware for the write path.
