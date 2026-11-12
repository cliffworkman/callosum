# P1b predeclaration, version 3 (inc 639), frozen before the third hosted P1b run

Version 3 amends `P1B_PREDECLARATION.md` (version 1, SHA-256 `6a5a2d85…e063`) and `P1B_PREDECLARATION_V2.md`
(version 2, SHA-256 `cd04c73a…d030`). Both stay in the tree unchanged, and everything in them still applies except
where a section below adds to it. The driver pins all three files by SHA-256 and refuses to run if any differs.
Nothing here is revised after the third run's measurements.

This is a new experiment. Nothing measured in the first or second attempt is counted here, including the second
attempt's concurrent-condition results: the third run must establish its own complete evidence for every condition.

## 1. Prior attempts and why a revision

| Attempt | Run | Commit | Verdict | Cause |
|---|---|---|---|---|
| 1 | 41948518913 | `7998ea63f329792dd5105a0e33d6885b83377a04` | INCONCLUSIVE | driver defect (`$name`/`$Name`); DeBERTa loaded in float16 |
| 2 | 43102297504 | `29a4a446433785a301372c33cf79dc2a2d3f0bd4` | INCONCLUSIVE | `deberta_solo` slot 1 discarded twice by the noise rule |

Both verdicts stand.

**What the second attempt established (recorded, not counted here).**
- The precision stage passed. All 202 DeBERTa parameters were float32, there were no floating-point buffers, and P1
  parity was 1.19 × 10⁻⁷ against the 0.001 limit, with the four statuses unchanged.
- The concurrent condition's three process medians were 5.359, 5.298 and 5.411 s (largest 5.411 s, limit 8.8 s).
  All three overlapped genuinely with Arctic indexing.
- Concurrent peak working set was 1,829 MB and peak commit 2,202 MB.
- Offline enforcement, integrity and cleanup all passed.

**Why the solo condition was not measurable.**
- `deberta_solo_1` lasted 44.0 s. During it, one `svchost` (pid 6820) used 25.53 CPU-s (0.580 per wall-second), and
  all foreign processes together used 0.641 per wall-second.
- Its one permitted repeat lasted 41.9 s. The same `svchost` used 12.03 CPU-s (0.287), and the aggregate was 0.349.
- Under v1 §7 two discards in a row made the condition INCONCLUSIVE, so slots 2 and 3 never ran. The 6-process memory
  statistic was then incomplete as well.
- The activity faded: during the MiniLM2 solo processes that followed, foreign CPU was 0.05–0.06.
- The two discarded medians, 3.448 s and 3.154 s, are well under 7.2 s. They are not acceptance evidence, and nothing
  in this revision counts them.

The hosted VM's own background work, not the code under test, decided that attempt. Version 3 adds a measurement
quality control (§3). It is not a performance change, and it gives no process a second chance beyond v1 §7.

## 2. Noise-rule implementation reconciled with v1 §7 (correction, not a new standard)

v1 §7 says a measured process is discarded if "a process outside the harness … used at least 0.25 CPU-seconds per
wall-second", and that "foreign CPU is the per-process difference of total CPU time". That is a rule about each
individual foreign process.

The driver used in attempts 1 and 2 summed every foreign process's CPU and compared the **sum** with 0.25. No
document, comment or commit records that difference as intended. Version 3 corrects the implementation to the text:

- **Rule (unchanged standard).** A measured process is discarded when any single foreign process used at least
  0.25 CPU-s per wall-second during it, or when available physical memory fell below the reserve.
- **Diagnostics.** Every measured process records:
  - the busiest foreign process (pid, name, CPU-s, ratio);
  - the five busiest;
  - the aggregate, kept as the diagnostic field `foreign_cpu_ratio` (the value attempts 1 and 2 compared).
- **Counters.** CPU time is read with .NET (`Process.TotalProcessorTime`) as before. The old driver silently
  dropped any process whose counter could not be read. Now a counter .NET cannot read is taken from `Win32_Process`
  (`KernelModeTime + UserModeTime`; the WMI provider runs as SYSTEM). Locally, as a standard user, .NET could not
  read 191 service processes, and WMI agreed with .NET to within 0.11 s where both could.
- **Fail-closed accounting.**
  - A foreign process whose name or CPU counter neither source can read makes the measurement invalid, and an
    invalid measurement is discarded.
  - So do a failed WMI query, an empty snapshot and a non-positive or non-finite wall time.
  - A process that disappears between the .NET read and the WMI read is listed as exited.
- **PID reuse.** A process is the same one only if its PID, its name and, when both are known, its start time (to
  within 1 s, because the two sources differ in precision) agree. Otherwise all of its CPU time counts as foreign. A
  counter that decreases is treated the same way. Over-counting can only discard, never pass.
- **Exclusions (unchanged).** The harness exclusions are those of v1 §7.
- **Exited processes.** A foreign process that exits during the interval is listed as exited. Its CPU after the
  start snapshot cannot be observed, the same limitation as v1.
- **History.** Both discarded attempt-2 processes are discarded under either reading (individual 0.580 and 0.287;
  aggregate 0.641 and 0.349). The correction therefore changes no prior verdict.

## 3. Idle settling before each solo measured process (new)

Before every solo measured process, DeBERTa and MiniLM2 alike and including the one permitted noise repeat, the driver
waits for the VM to be quiet. The concurrent conditions are unchanged and have no settling.

| Parameter | Value |
|---|---|
| Window | 10 s, measured on a monotonic clock (`Stopwatch`); windows are contiguous and do not overlap |
| Quiet window | the window's measurement is valid (§2), lasted at least 10 s, and no individual foreign process used 0.20 CPU-s per wall-second or more |
| Required | 3 consecutive quiet windows (30 s); a noisy or invalid window resets the count to zero |
| Attempt budget | 180 s per settling attempt; no window starts that could end after it |
| Run budget | 600 s of settling in total for the whole hosted run, shared by every attempt |
| Foreign processes | the definitions and exclusions of v1 §7 and §2 above; the driver itself is excluded |
| Recorded per window | start, duration, quiet, consecutive count, validity, the busiest foreign process, the aggregate, the five busiest, unreadable and exited processes |

**What settling is.**
- It is a pre-measurement screen. The 0.20 threshold leaves headroom below the 0.25 post-measurement rule, which it
  does not replace.
- Settling time is not part of any cold or warm latency measurement: the measured process starts after settling ends.
- The memory prerequisites are unchanged: the v1 §7 reserve rule and the 1.5 GiB stop floor still apply to every
  measured process.

**Outcomes.**
- If either budget runs out, or the settling measurement itself fails, the driver records the failed infrastructure
  check `<process>_idle_settled`. The condition stops INCONCLUSIVE and its remaining slots are not run.
- A successful settling check does not count a process. The v1 §7 post-measurement rule still decides every measured
  process.
- A discarded process is still repeated exactly once, after its own settling check. Two discards in a row still make
  the condition INCONCLUSIVE.
- A settling failure is not a discard and grants no attempt. No additional measurement attempt of any kind is
  authorised.

**What settling never does.**
- It never kills, suspends, reprioritises or disables any process or service.
- It never chooses among past intervals.
- Its thresholds and durations are fixed here, before any third-run measurement.

## 4. Unchanged

Everything not named above is unchanged from v1 and v2:
- the code under test (v2 §2, the same pinned trees) and the precision stage (v2 §3);
- the fixture `fixtures/p1b-pairs-v1.json` (SHA-256 `acd2723c…9920`) and the indexing corpus;
- the `verify_many` operation, the thread settings, batching and timeouts;
- the resource definitions and the requirement of genuine indexing overlap;
- three fresh counted DeBERTa processes per condition, each with 1 cold call and 8 warm repetitions;
- the largest process median as the acceptance statistic, and the single noise repeat;
- the PASS / FAIL / INCONCLUSIVE classification (v1 §8).

| Criterion | Statistic | Limit |
|---|---|---|
| Warm, DeBERTa alone | the **largest** of the 3 per-process medians | ≤ 7.2 s |
| Warm, DeBERTa with Arctic indexing | the **largest** of the 3 per-process medians | ≤ 8.8 s |
| Peak working set | over the 6 measured DeBERTa processes | ≤ 2,520 MB |
| Peak commit | over the 6 measured DeBERTa processes | ≤ 2,870 MB |

## 5. Scope (adds to v1 §10 and v2 §6)

A PASS needs the third run's own complete evidence: three counted solo and three counted concurrent DeBERTa
processes, the 6-process memory statistic, the precision stage, isolation, integrity and cleanup.

It does not show:
- G1 parity for the float32 loader (the private 308-pair evaluation stays a separate requirement);
- results on other platforms;
- release-gate arming. `DEBERTA_RELEASE_GATES.packaged_runtime_acceptance` stays unarmed, and automatic DeBERTa
  preference stays disabled.
