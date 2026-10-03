# Confirmation provenance mirror repair — local increment 605

## Anchor and preserved evidence

Start: `fix/capture-admission-paper-index`, exact HEAD
`d3ab14426923650ff40d1027a229814c9fc411f2`. Tracked-clean; existing untracked
`.claude/paper-index-evidence/` preserved. PR #103 remains OPEN/draft on
`browser-capture-research`, remote head `fcaabb7a76ec48620a5404c04e974f2a98e9f9a9`.
No remote mutation. New local receipts live in `.claude/sidecar-evidence/`.

All 28 original acceptance hashes and ten failed-run artifact hashes matched. The previous
failure-diagnosis report hash was calculated from LF text before Windows wrote CRLF; normalized
text matches exactly. New anchor pins its actual byte hash and its unchanged hash-record file:
40 preserved files total. This bookkeeping correction does not rewrite or weaken any FAIL receipt.

Failed run: `C:/Users/cliff/Callosum-Windows-QA-0516-20260930/targeted-index-d3ab1442-20261002/run-20261002T234103Z-4aa874f3`.
FAIL receipt SHA-256: `644e33ee64e4f0c1b5a8b461b6ccfc919a79bf75036b5e6afe9fc4565b47543c`.

## Cause and smallest shared repair

Confirmation first commits `user_confirmed_candidate`/`user_entered_doi`. It constructs `_Evidence`
from the original observations and calls `attempt_attach_to_paper`. That function replaces
`evidence_json` with `_Evidence`'s serialization, then refreshes the sidecar. The review caller's
`_reattach_user_actions` restores history to the DB but previously never refreshed its mirror.
The failed run retains the action in the DB, lacks it in the sidecar, and marks that sidecar `ok`.
All other evidence agrees. This is independent of the now-working paper-indexing repair.

Pass the existing Library root into `_reattach_user_actions`, then call the existing late-bound
`provisional._refresh_sidecar` after its `run_write` commit. Four call sites cover unresolved
confirmation and admission, plus retry's initial and final restoration. No automatic path calls
this helper: automatic promotion already refreshes its final `_Evidence` and is regression-tested.
Production change: **one file, 9 added / 5 removed lines**. No schema, serializer, identity policy,
DB authority, filesystem ownership, indexing, model, dependency or runtime change. Existing
sidecar-write failures remain nonfatal and marked `error`.

## Regression and validation

Extend the existing import-queue matrix with one reusable whole-evidence mirror assertion; reuse
it in the real Ioannidis review test. Preserve observed candidates/title/resolution fields and
ordered confirmation/retry chronology. Cover failed resolution, successful/manual/candidate
confirmation, ambiguous selection, attachment conflict, failed/successful retry, and injected
sidecar OSError without undoing admission or DB history.

Red before production edit: **7 failed, 50 passed in 61.05 seconds**, all missing action history
at sidecar/DB equality. Raw receipt: `.claude/sidecar-evidence/red.log`.
Green on development Anaconda Python 3.12.7: **90 focused passed in 98.74s** (import queue,
provisional DOI review, admission indexing, embeddings), then **180 broader passed, 2 skipped
in 177.85s** (capture, responsiveness, updates, trust boundaries, filesystem authority, module
seams, DOI admission, acquisition, SQLite retries and library scans). The skips are POSIX-only
permission-bit tests on Windows. Commands use `-B -m pytest -p no:tach ... -q --tb=short
--show-capture=no`; Tach runs independently. Local fixture extraction differs from the managed
runtime, so these tests assert coverage of actual extracted chunks, not a fabricated 122 count.

Ruff import ordering was corrected after the first static check. The first hook invocations used
an interpreter without pre-commit/Bandit/Tach; use the existing standalone pre-commit executable
with Anaconda's existing toolchain on PATH. No packages were installed. API surface coverage and
website coverage pass (marketing review explicitly deferred through 605, not a new visual review).
The relevant pre-commit hooks must pass before the local commit; the commit log records them.
Fresh remote full-suite CI/packaging remains a later release gate; no push is authorized here.

## Gates and limits

The original human Windows Chrome run remains PARTIAL; the `d3ab1442` isolated replay remains FAIL.
Only a fresh isolated real-runtime replay completing all assertions, idempotency and backend reopen
can close the downstream gate. It will preserve synthetic-confirmation provenance and report
backend timing, never browser/UI latency. No full Chrome rerun, accepted-QA repair or runtime change.

No new endpoint, input or path mechanism is introduced: the same owned artifact ID, Library root
and atomic writer are used after an already-required DB commit. Existing queue-authority tests and
Bandit remain checks. No end-user surface contract or help instructions change. Experience pass
is trivial for this backend-only mirror correction. Principles 1/3/5/8 apply; no history is invented.

Inherited documentation drift: the overview still cites increment 580 and old test counts; the
scoped increment history is now 605. The old release paragraph calls the updater unbuilt, but later
increments and the current `desktop-shell-release.yml` already implement signed updater artifacts
and `latest.json`. Follow the existing bump tool, annotated tag and GitHub Release/updater workflow
only after separate release approval; do not build a parallel release mechanism.

Next release step after successful targeted replay: request approval to integrate the exact local
Windows fixes and obtain fresh remote CI/packaging evidence, then resolve the remaining claimed
support-matrix gates (Apple Silicon/Chrome remains distinct; Edge and older OS floors conditional).
No push, PR-ready transition, merge, version bump/tag, runtime/updater publication or release here.

2026-10-02 | Evidence/authorization | Cliff: genuine Windows acceptance and targeted replay execution.
2026-10-02 | Scope | Lucien: shared post-restoration refresh and fresh isolated verification.
2026-10-02 | Diagnosis/implementation | Cody/ChatGPT: traced mirror ordering, wrote tests and minimal fix.
