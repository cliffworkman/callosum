# Increment 621 — Release stabilization and browser acceptance

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `70273c01`.
Local only: not pushed, not merged, no version bump, no gate armed. Feature freeze: one narrow defect repair.

Evidence (gitignored, local): `C:\Users\cliff\callosum-worktrees\integrate-607-608\.local\validation-621\`.
`browser\result.json` and screenshots, `upgrade\result.json`, `ops\result.json`, `suite-*.{log,xml,meta.txt,memory.csv}`,
`pip-freeze.txt`, plus the harnesses `browser_acceptance.py`, `upgrade_path.py`, `ops_failures.py`, `idle_cost.py`.

## Implemented (the one repair)
- **Defect D1, a mounted Settings panel goes stale.**
  - *Reproduction:* Settings open at complete; import papers. The backend detected catch-up in 0.4 s. The panel still
    said "complete", "24 of 24" and "Ask retrieval right now: Arctic S" after the 45 s window and after catch-up
    finished, while Ask had moved to MiniLM. Same for paused (a resume from another window) and action-required (a
    model becoming valid).
  - *Expected:* the panel reflects the change without reopening Settings.
  - *Severity:* release-critical. A trust surface states which model Ask uses, and the statement could stay false until
    Settings was reopened.
  - *Root cause:* `modernizationPollDelay` returned `null` for those states, ending the only loop. Nothing restarted it:
    `libRefresh` is per-page and the capture long-poll covers only browser capture, so neither sees another window or a
    coordinator-detected change.
  - *Correction:* a 15 s idle tick in the same one loop (`04f_modernization_logic.jsx`, `35j_modernization.jsx`). Measured
    on the 68,086-chunk copy, `GET /embedding-profiles` costs 3.4 s and `GET /modernization` 5 ms (about 0.9 s once per
    60 s when its cache expires). So the idle tick reads only `/modernization` and does the full read only when
    `modernizationSignature` changes. Still one timer site; no new endpoint, no backend change, no timer while disabled.
  - *Regression tests:* `test_settings_poll_keeps_running_through_waits_including_waiting_disk` (failed first, on the old
    `null`) and the existing one-timer guard, which rejected a first draft with two `setTimeout` sites.
  - *Scientific behaviour:* frontend scheduling only. No retrieval, identity, threshold, source-role or provenance code
    changed; the code diff is two frontend chunks, the built bundle and one test.
- Historical receipt left unchanged: the inc-620 audit's "stops in paused / complete" row describes that increment. This
  note supersedes it for the current tree.

## Key technical detail
- Latency after the fix: the panel saw catch-up in 11.2 s, a resume in 14.9 s, a newly valid model in 14.8 s. Over a
  settled 31 s: 2 `/modernization` and 0 `/embedding-profiles` requests.
- Harness corrections, none a product finding: Settings is `role=tab`; Playwright's sync API does not dispatch events
  during `time.sleep` (this had made an early "polling stopped" pass meaningless, so it was re-measured); `fail_papers`
  was set after the server started; Cancel was clicked at the very end of a short build; a keep-alive race at exactly
  uvicorn's 5 s timeout; activation is recorded one coordinator check after completion. Each failed run was investigated
  rather than discarded. Reported results are the reruns after the fix.
- The "Index: 0 of N" shown for MiniLM in the browser screenshots is the synthetic fixture's identity. On the real
  snapshot copy MiniLM coverage reads 42,044 of 42,044.

## Results
Stand-ins everywhere a model would run: Arctic and baseline encoders, generator, support scorer, model readiness, memory
and disk probes. **No real Arctic or DeBERTa inference ran.** Classification on the upgrade path is the real code over
all 151 real papers. The blocker matrix carries the per-blocker labels; the receipts are:

| Check | Tree | Result |
|---|---|---|
| Full suite, `python -m pytest -n 2 -q -p no:cacheprovider` | `70273c01`, before the repair | 3791 passed, 12 skipped, 3 failed (the known baseline), 17:34; min free commit 7.47 GB |
| Rendered browser, Chromium 149 headless | final tree | 71 passed, 0 failed, 0 console errors |
| Upgrade path on a copy of the desktop snapshot | final tree | 19 passed, 0 failed; content fingerprints identical; integrity ok; no non-loopback attempt |
| Repo browser tests (`test_smoke`, `test_capture_updates`, `test_doi_review`, `test_browser_preview`) | final tree | 21 passed |
| Focused (`test_modernization_status`, `test_frontend_assembly`) | final tree | 118 passed |

The final-tree full-suite receipt is recorded after this commit, because it has to run on the committed tree.

## Manual verification script
1. `python .local\validation-621\browser_acceptance.py` with `CALLOSUM_DB_URL` overridden; read `browser\result.json`.
2. `python .local\validation-621\upgrade_path.py` (copies the snapshot; the original is only read).
3. By hand: open Settings on a complete library, import a paper in another window, watch the panel change within about
   15 s and the Status badge reappear, with no reload.

## Not run
Packaged first run, a real low-disk volume, real Arctic indexing, two real app processes with a browser attached, the
panel at mobile width, the 0.6.0 notice under a real version bump (it was observed with a simulated version).

## Security
No new endpoint, fetch, write path or dependency, so the audit gate is not triggered. Self-assessment only. The harness
app read the machine's real OS-keychain set/not-set status while rendering Settings; no key value was read or displayed
and nothing left the machine. No independent review exists for incs 616-621.
