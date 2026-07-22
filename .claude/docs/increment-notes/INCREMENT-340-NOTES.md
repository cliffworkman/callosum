# Increment 340 Notes — Permanent delete removes managed attachment files

## Implemented

- Added `app/backend/paper_purge.py`, a filesystem-aware service around the existing database/vector purge.
- `DELETE /papers/{paper_id}/permanent` and `POST /papers/trash/empty` now delete exclusively owned attachment
  files inside `CALLOSUM_LIBRARY_DIR` when their attachment is marked `managed`.
- Linked/URL attachments, out-of-root paths, symlinks, directories, missing files, and files referenced by another
  surviving paper are preserved.
- Managed files are staged with reversible same-volume renames. File-lock/staging failures return 409 and keep the
  paper in Trash; database/vector failures restore staged files before propagating.
- Updated the destructive confirmations, served Help, and QA route 40 to state and verify the ownership boundary.
- Removed the now-dead database-only bulk-purge helper; bulk commit coordination lives in the new service.

## Key technical detail

Filesystem deletion cannot participate in SQLite rollback. The service therefore resolves the managed root, stages
eligible files into a verified real directory inside that root, performs the existing embedding/vector/paper purge,
commits, and only then unlinks the staged files. Normal pre-commit failure restores the original paths. Path identity
is normalized before checking surviving attachment references, so a shared file is never removed prematurely.

No schema change, migration, endpoint, dependency, or egress path was added.

## Principles / values check

The literature-claim gate does not trigger. Approach/Avoidance A4 does: the user owns irreversible acts. This is a
confirmed extension of the explicit Trash -> permanent-delete flow. The unsafe shortcut (delete every recorded
attachment path) was rejected; only Callosum-managed, root-contained files are eligible.

## Manual verification script

1. Set `CALLOSUM_LIBRARY_DIR` to a disposable directory and start Callosum against a disposable migrated database.
2. Add one managed PDF inside that directory and one linked PDF outside it to a disposable paper.
3. Move the paper to Trash and choose **Delete forever**. Confirm the managed PDF disappears, the linked PDF remains,
   and the paper no longer appears after reload.
4. Repeat with two trashed papers and **Empty Trash**; confirm the response count and managed-file cleanup.
5. Lock a managed PDF in a way that prevents rename, then retry. Confirm the UI reports the error and the paper and
   file remain in Trash for recovery.

## Verification

- Focused permanent-delete lifecycle: **7 passed**.
- Short-write invariant plus purge lifecycle: **8 passed**.
- Merge/route regressions: **12 passed**.
- Frontend assembly: **46 passed**.
- QA surface map: **260/260 API surfaces covered** (frontend checklist reported only the existing 21 unrelated
  settings/tags entries).
- Line budget: **351/351 application-source files <= 600 lines**.
- Full suite: **1388 passed, 1 skipped** (`pytest -n auto -q`).
- Disposable live instance (`127.0.0.1:8098`): served bundle contained both ownership-boundary confirmation
  sentences; `DELETE /papers/1/permanent` returned 204; managed file changed present -> absent; Trash count became
  zero. Headed Playwright was not available because its shared browser profile was locked by another process, so
  no visual result is claimed.
- Security audit: `.claude/security-audits/2026-07-22_managed-file-permanent-delete.md` — **PASS**.
