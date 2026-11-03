# Increment 630: isolated full regression validation (630 to 630E, attempts 1 and 2)

Release-validation increment for 0.6.0 on the unpushed `integrate/inc607-608-ask` branch. Nothing was pushed, merged,
tagged or deployed. Application code did not change in this increment. The only commit is five test corrections.

**Result: full regression PASS on `c7c645fe17a861f2a5b876596a21629b311c2c8c`** (attempt-2, 2026-11-03), after
attempt-1 FAILED on its parent `5571723b`. The PASS covers the pytest regression suite only. It is not packaged-model,
browser, cross-platform or release qualification; see "What this does not show".

## Why a dedicated procedure
The last complete suite before this ran on Anaconda (Python 3.12, torch 2.6), which matches neither CI nor the packaged
runtime. The last locked-stack CI receipt was `80025d1a`, before the 0.6.0 work. The Claude Code host cannot run the full
suite reliably (its low-memory reaper stopped runs twice, inc 622). The maintainer's Windows account holds the real
0.5.16 install and the research libraries, and the user-scope `CALLOSUM_DB_URL` points at the research master.

So the suite ran:
- in a dedicated standard (non-administrator) Windows account, `callosum-val`;
- from a fresh clone of a git bundle into a disposable root;
- on Python 3.11.14 with the locked stack (`uv.lock`, torch 2.13.0);
- from a hash-bound command file, launched by a line that refuses to run if the file's SHA-256 changed;
- between a BEFORE and an AFTER stage, both run from the maintainer's administrator terminal, which start no Python.

## Procedure (as executed for attempt-2)
1. **SETUP** (administrator): disposable root, tools, bundle, pinned test inventory, caches. Starts no Python.
2. **BEFORE** (administrator): refuses before writing anything if the desktop app or a model port is open, or if
   disk or free commit is low (8 GB commit floor). Then records the protected-data manifest (file hashes and trees of
   the research master, the desktop database and snapshots, app data, `~/.callosum`, the Hugging Face hub cache, the
   integration worktree's `.local`), the main checkout's HEAD and status, a seal of attempt-1's evidence, and 30
   access-denial targets. Writes a one-time run token.
3. **WINDOW** (administrator): opens the `callosum-val` PowerShell window.
4. **PREP / FOCUSED / RUN** (in that window), each behind:
   - an identity guard (token account name, not in Administrators, registered and effective profile path);
   - an environment guard (removes everything outside an allowlist, resets profile variables to the account's own
     folders, rebuilds `Path`, confirms blocked names such as `CALLOSUM_DB_URL` and `SSL_CERT_FILE` are absent, scans
     values for protected paths);
   - a child-process environment proof and a child database-path proof that the default database lies inside the clone;
   - a check that all 30 protected targets are denied to the account.

   FOCUSED runs a small gate first; RUN refuses without a FOCUSED-PASS for the same token and refuses a reused token.
5. **AFTER** (administrator): waits for the account's processes to end, recomputes the manifest, and writes the only
   file that can state a final result. Precedence: SAFETY-STOP, then INCONCLUSIVE, then FAIL, then PASS.

Network protection was **proxy suppression only** (`HTTP(S)_PROXY=http://127.0.0.1:9`, `HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`), never full isolation. Every verdict line says so.

## Attempt-1 (2026-11-02, `5571723b`): FAIL
3,845 tests: 3,825 passed, **6 failed, 1 error**, 13 skipped (5 unexpected). Protected changes 0, surviving processes 0.
Triage (630B, read-only) found no release-blocking application defect. Causes:
- the administrator terminal was conda-activated and leaked `SSL_CERT_FILE` into the test window (two TUI tests and
  the first layer of three others);
- tests that needed a real model or live network (retraction, registration references, funding discovery) failed
  under the offline guard;
- inc 625 added raw hex without extending `test_design_drift`'s allowlist, and a `from PIL` import with Pillow absent
  from `uv.lock`;
- the v3 harness's skip classifier read only `classname`, which is empty for collection skips, so it could never pass.

It also surfaced issue #110 (below). Attempt-1's evidence was sealed and is unchanged: attempt-2's AFTER compared its
seal before and after with 0 differences.

## 630B to 630E: corrections
- **630C:** five tests corrected (no application code): `tests/test_design_drift.py`, `tests/e2e/test_demo_static.py`,
  `tests/test_retraction.py`, `tests/test_registration_references.py`, `tests/test_funding_discovery.py`. 15/15 scratch
  fault injections were caught. Pillow was **not** added: `pyproject.toml` and `uv.lock` are runtime-ID inputs.
- **630D:** harness v4 qualified 292/0 under a reduced restricted token. Three fail-closed defects fixed in the harness
  (environment removal was a no-op, database-proof module lookup, suite-line order). Pinned inventory: 3,845 ids, 14
  expected skips, the same ids as attempt-1.
- **630E:** the five corrections committed as `c7c645fe` (diff equals the reviewed 630C patch). Command file rebuilt and
  bound to that commit (SHA-256 `43F14220CB556C32E67C049796F69F8C5CEC527C2E619A603F990CE6880E2AC2`). WINDOW gained a
  `cmd.exe` fallback because attempt-1's direct alternate-credential launch had failed once.

## Attempt-2 (2026-11-03, `c7c645fe`): PASS
Final verdict written by AFTER at 16:02 local time (America/New_York):

`PASS | protected-changes 0 | surviving-processes 0 | problems:  | network proxy-suppressed only, not isolated | FOCUSED-PASS | ... | SUITE-PROVISIONAL-PASS | ...`

| Measure | Result |
|---|---|
| Tests (junit, recounted from the XML) | 3,845 |
| Passed / failed / errors | 3,831 / 0 / 0 |
| Skipped | 14, all expected; 0 unexpected |
| Inventory differences vs the pinned list | 0 |
| Worker crash | none (`pytest -n 2`) |
| Suite time | 1,083.7 s |
| Clone dirty after the run / fallback writes | 0 / 0 |
| Default database created in the clone | no |
| Protected-data changes (manifest diff) | 0 |
| Attempt-1 seal | unchanged |
| Surviving `callosum-val` processes | 0 |
| Focused gate | 7 tests, 0 failures, 1 expected skip |

The 14 skips: six browser E2E modules (need `CALLOSUM_RUN_E2E=1`); the curated demo source database; symlink creation
(unavailable to ordinary Windows processes); two POSIX permission-bit tests; **the real pinned Arctic S and DeBERTa
snapshot checks (no snapshot in the account's Hub cache)**; the real Crossref smoke (manual by design); the staged
connector launch (needs `packaging/stage_connector.py`).

Free commit was 6.87 GB at the first BEFORE, which refused (`LOW COMMIT`) without writing anything. BEFORE passed at
12.88 GB after the maintainer closed other applications. The floor was not changed.

### Evidence (private, not in git)
- Verdict: `%USERPROFILE%\callosum-worktrees\validation-630\attempt-2\FINAL-VERDICT.txt`, SHA-256
  `2A7CEB81551F3DC23850CBED2C1B2AAFE28A03F358DDB9375ED2704923A39E76`. This is beside attempt-1, **not** under the
  integration worktree's `.local` as the 630E handoff first said (handoff corrected in inc 631).
- Attempt-1 verdict: same folder's `attempt-1\FINAL-VERDICT.txt`, SHA-256
  `329BF54F81DA0F344350BFB643492C246B819181E5DBE64C1F8B2B0DAE39F648`.
- Run evidence (`pytest.xml`, logs, guard receipts) is under `attempt-2\evidence`. Neither attempt's evidence was edited.

### Receipt-keeping defects found afterwards (result unaffected)
- The operator ran FOCUSED and RUN a second time; both were refused by their guards, as designed. But the environment
  guard writes `env-check-<stage>.txt` **before** the token check, so each refused call overwrote that stage's
  environment receipt (focused: 14:07 to 15:00; run: 15:00 to 15:59). The replacement files are ENV-CHECK PASS for the
  same token and session. The run's own child-environment, database-path and access-denial receipts (15:00) are intact,
  and RUN cannot start pytest unless the guard passes. A future harness should check the token before writing.
- The operator first ran AFTER inside the `callosum-val` window; it could not read the command file and did nothing.
- The window's PowerShell tried the maintainer's Temp folder and PSReadLine history at startup. The `cmd.exe` route
  passed the administrator terminal's variables through before the guard ran. Both were denied, and the manifest
  shows no change.

## What this does not show
- **No real Arctic S or DeBERTa inference ran.** Both real-snapshot tests skipped; model-backed tests use fakes. The
  suite proves nothing about real model loading, packaged-runtime behaviour or CPU/memory cost.
- Not the packaged layout: the locked stack ran from a source clone, not the installed app or its portable runtime.
- Windows only, x86-64. macOS (including the separate Intel lane on torch 2.2.2 / transformers 4.57.6) and Linux
  were not run.
- Browser E2E did not run (six skipped modules).
- Network was proxy-suppressed, not isolated; a test that bypassed proxies could have reached the network.
- A PASS at `c7c645fe` does not transfer to a later HEAD that changes code. The inc 631 documentation commit changes
  no code, tests or dependencies.

## Issue #110
Provisional **P1**, open, not fixed. Attempt-1 surfaced it: an embedding failure during import skips the automatic
retraction check while the job reports success. Not downgraded because the code predates 0.6.0.

## Manual verification script
1. `Get-FileHash %USERPROFILE%\callosum-worktrees\validation-630\attempt-2\FINAL-VERDICT.txt` equals `2A7CEB81…`.
2. Open `attempt-2\evidence\pytest.xml`: `tests=3845 failures=0 errors=0 skipped=14`.
3. `attempt-2\protected-diff.txt` and `surviving-processes.txt` are empty; `hash-before.txt` and `hash-after.txt`,
   `tree-before.txt` and `tree-after.txt`, `attempt1seal-before.txt` and `attempt1seal-after.txt` are pairwise identical.
4. `evidence\config.txt` names head `c7c645fe…`, Python 3.11.14 and the proxy-only network note.

## Pytest
3,831 passed, 14 skipped (attempt-2, the full suite, `pytest -n 2`).
