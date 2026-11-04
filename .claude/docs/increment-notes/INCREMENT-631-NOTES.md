# Increment 631: close regression validation; scope packaged-model qualification

Documentation only. No application code, tests, fixtures, dependencies, migrations, model configuration or thresholds
changed. Nothing was run against models, browsers, installers or the research data. Nothing was pushed or merged.

## Implemented
- **Receipts verified** against the claims before writing anything: attempt-2's verdict hash, the junit XML recount
  (3,845 / 0 / 0 / 14), empty protected-diff and surviving-process files, pairwise-identical before/after manifests,
  trees, main-checkout state and attempt-1 seal, and attempt-1's verdict (3,825 passed, 6 failed, 1 error, 13 skipped).
  No receipt disagreed with the reported result. One receipt-keeping defect was found and recorded (inc 630 notes:
  refused duplicate stage calls overwrote the environment receipts; the result is unaffected).
- **`INCREMENT-630-NOTES.md`:** the full 630 to 630E history, both attempts, evidence paths and hashes, limitations.
- **`RELEASE_060_PACKAGED_MODEL_QUALIFICATION_PLAN.md`:** what the code implements for Arctic S and DeBERTa, the two
  qualification matrices, a Windows-first local plan (P1 to P4), and why JUNO is not needed.
- **`RELEASE_060_BLOCKER_MATRIX.md`:** a "Status after inc 630 and 631" section with the gate table and the issue #110
  assessment. **`RELEASE_060_TEST_AND_PACKAGING_PLAN.md`:** §3b. **`changes.md`**, **`CLAUDE.md`** (current-state lines).
- **Private handoff** (`validation-630\HANDOFF-v4.md`, not in git): the verdict location corrected to
  `%USERPROFILE%\callosum-worktrees\validation-630\attempt-2\`.

## Key technical detail
- **Provenance stays with `c7c645fe`.** This documentation commit's HEAD differs from the validated commit but changes
  no executable or test file; the PASS is not reassigned to it.
- **The suite never loaded a real model.** `test_real_pinned_snapshot_verifies_offline_when_present[arctic-s]` and
  `[deberta-v3-base]` skipped (no snapshot in the account's cache). Real model behaviour is still unproven anywhere in
  a packaged runtime.
- **Packaged runtime reuse.** The committed Windows runtime ID (`win-x86_64-py3.11-s1-2094b5a287a1dd54`) equals the
  runtime installed by 0.5.16, so Windows packaged-interpreter qualification needs no installer build and no runtime
  download; only the two model snapshots (about 0.5 GB) would be downloaded, under authorization.
- **Every shipped runtime is CPU-only torch;** Intel macOS uses torch 2.2.2 with transformers 4.57.6, a separate lane.
- **Issue #110:** the existing harness evidence already shows the misleading state (completed job, unchecked paper,
  UI identical to "checked, none found"). What is missing is frequency, not mechanism.

## Correction, 2026-11-03 (incs 632A, 632B, 632B-R, 632C)
The two bullets above were written in inc 631 and are kept as written. Two of their statements are wrong:
- **"Real model behaviour is still unproven anywhere in a packaged runtime."** Wrong. On 2026-10-31, a compatibility
  smoke probe loaded both pinned checkpoints (Arctic S `e596f507…`, DeBERTa `6f5cf0a2…`) in the installed 0.5.16
  packaged interpreter. It used direct `SentenceTransformer`/`CrossEncoder` calls, offline, from the maintainer's cache.
  Against the development environment it gave Arctic cosine ≥ 0.999999866 and DeBERTa max |Δp| 2.65e-5. That was a
  **smoke check**, not formal qualification: no app loader, no manifest verification (manifests came in inc 615), no
  `verify_nli_checkpoint`, no isolation, and only 3 texts and 2 pairs. Formal P1 qualification has not started.
- **"…needs no installer build and no runtime download."** Disproved. The smoke probe ran the installed interpreter in
  place as `python.exe -I`. `-I` ignores `PYTHONDONTWRITEBYTECODE`, and Python replaced 3,195 shipped `.pyc` files. In
  inc 632B the installed tree's digest (`63d7609e…`) no longer matched the signed `a51f65b3…`. The installed runtime
  has **not** been repaired.
- **Inc 632B-R** downloaded the signed runtime archive once (SHA-256 `ce0d2052…`, matching the manifest and the
  install receipt), extracted it without executing it and reproduced `a51f65b3…` exactly, twice. The manifest
  signature was **not** re-verified, because the verifier crate was not available offline. The binding is the hash
  chain to the original install receipt.
- **Revised P1 source:** a fresh per-experiment copy of that recovered pristine runtime, launched as `python.exe -I -B`.
  `callosum-val` is denied write access, and the file digest and directory inventory are checked before and after.
  No installer build is needed. Details: `RELEASE_060_PACKAGED_MODEL_QUALIFICATION_PLAN.md`, Revision 2.

## Manual verification script
1. `git show --stat HEAD` lists only Markdown files under `.claude/`.
2. `git diff c7c645fe HEAD -- app tests pyproject.toml uv.lock alembic integrations tools adapters` is empty.
3. The verdict hash in `INCREMENT-630-NOTES.md` matches `Get-FileHash` on the private verdict file.

## Pytest
Not run (documentation only; the inc 630 PASS at `c7c645fe` stands). Pre-commit hooks ran on the commit.
