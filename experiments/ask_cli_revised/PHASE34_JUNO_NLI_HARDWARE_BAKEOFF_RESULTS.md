# Phase 34 -- JUNO NLI hardware bakeoff

This file holds two increments. **Increment 2** (the controlled retry) is new and comes first.
**Increment 1** (the interrupted attempt and laptop-only close-out) follows unchanged, under its own
heading. Where the two differ, Increment 2 is the later evidence; Increment 1's account of the
incident stands as written.

**Correction.** Commit `e0203580` was meant to add Increment 1 but committed this file empty, because
of a line-ending step that truncated it before reading it. The lineage entry in that commit was
intact. Increment 1 is restored below, byte for byte, from the text as originally written.

---

# Increment 2 -- Controlled retry on JUNO

**Disposition: HARDWARE TRADEOFF UNRESOLVED.**

JUNO did not reset. Both models ran on its CPU and reproduced the frozen scores exactly. The
comparison is incomplete because the CPU ran hot: the benchmark's temperature guard ended three
runs, so DeBERTa at four threads, the Ollama coexistence test, and a like-for-like MiniLM rerun were
not measured.

What the completed measurements show:

- **Speed and memory are not the obstacle.** At two threads JUNO is 2.2 to 2.5 times faster than the
  laptop at four. DeBERTa's 1.5 GB peak sat inside 10 GB of free memory with no swap use.
- **JUNO's CPU temperature is.** One thread of either model takes the package to 81-88 C within
  seconds to tens of seconds. This is independent of which model is chosen.

No reset, kernel error, thermal-throttle event or swap use occurred during the retry. Nothing was
implemented. No GPU was used and no generative model was called.

## 1. Starting HEAD and preservation state

- Start: `e02035808e47ab2476998c17a9f3c8693a9eab25`, worktree clean, branch in sync.
- Tracked changes: this report and the lineage entry. 204 preserved input files, including every
  artifact of Increment 1, hashed before and after; none changed.
- New raw results: `.local/phase34-juno-nli-retry-20261012/` (scripts, predeclaration with two
  amendments, per-run logs and JSON, analysis log). Earlier artifacts are untouched.
- Authorisation: the retry was explicitly authorised, superseding the prohibition in Increment 1.

## 2. Reset diagnosis and uncertainty

Read-only, from preserved logs, the scripts, and JUNO's existing system records. Reading the kernel
journal and hardware identity used passwordless sudo; nothing was changed by it.

**Sequence before the reset (15:09:01-15:09:02 EDT, 12 October).**

1. A short preamble process imported PyTorch (CUDA build), called `torch.cuda.is_available()` and
   asked for the device name. It printed "True, NVIDIA GeForce RTX 3050" and exited.
2. The benchmark process started. Before importing anything heavy it ran `nvidia-smi` once, then
   flushed and dropped the MiniLM files from the page cache.
3. It would then import PyTorch, load MiniLM and run six threads. Nothing was logged from this
   process, so how far it got is unknown.

**Was CUDA initialised?** Yes, in step 1: returning a device name requires initialising the CUDA
runtime against the driver. It completed normally. The benchmark itself was a CPU run, but its
PyTorch build carried the CUDA libraries.

**Was hardware detection unnecessary?** Yes. Neither the CUDA query nor the `nvidia-smi` call was
needed for a CPU benchmark. Both are removed in the retry.

**Memory, swap, CPU contention.** Unlikely as a direct cause: 12.7 GB was available and MiniLM needs
under 1 GB. One related fact is new. In that boot, swap included a partition on a USB disk (`sdg5`),
ranked ahead of the internal swap partition, and 3.6 GB of swap was in use. That same USB disk
dropping off the bus ended an earlier boot on 23 September with swap read errors, and it logged two
USB resets shortly after the following boot. It is not a swap device in the current boot. Whether it
played any part on 12 October cannot be told from the records.

**Power, thermal, kernel, hardware, driver records.** None for the reset: no machine-check, no
panic, no thermal event, no driver error, empty crash store, and the journal simply stops. The
board is an ASUS PRIME H310-PLUS (BIOS 0402); it exposes no fan or voltage sensors to the OS.

**New evidence from the retry.** The CPU heats very quickly under this workload (section 8). Six
threads from idle would have heated it faster than anything run in the retry. That fits a thermal or
power-delivery explanation. It does not prove one: no thermal record exists for the reset, the
retry never reproduced it, and the retry never ran six threads.

**Leftovers.** The SSH polling loop from Increment 1 was still running on JUNO (one `bash` loop and
its `sleep`). It was experiment-owned and was terminated. No benchmark process remained. The task
folder was intact and all 14 model files re-verified by hash, so the environment was reusable.

**Conclusion.** The root cause is not determined. Candidates remain CPU thermal or power stress,
GPU driver initialisation, storage or swap on the USB disk, and coincidence. Temporal proximity is
the only link to the benchmark.

## 3. Changes to the benchmark procedure

| | Interrupted attempt | Retry |
|---|---|---|
| PyTorch | 2.6.0 CUDA build | 2.6.0 CPU-only build in a second isolated environment (no CUDA libraries present) |
| GPU | CUDA queried; `nvidia-smi` called | GPU hidden from the process; no GPU query of any kind |
| Page cache | model files evicted before load | not touched |
| Threads | 6 from the start | 1, then 2, then 4; 6 never run |
| Placement | unrestricted | pinned to named physical cores, low priority |
| Limits | none | 4 GB memory cap with no swap, in an unprivileged scope; hard timeout per process |
| Guards | none | in-process abort on temperature or swap growth |
| Lifetime | detached job plus a polling loop | each stage is one foreground SSH command that ends with the benchmark |
| Logging | at the end | line by line; partial results saved after each batch size |

These reduce ordinary contention and remove the GPU and cache steps as variables. They do not
protect against a hardware or kernel failure.

**Deviations from the predeclared plan, both written into the predeclaration file before acting.**

- *Amendment 1.* The plan said to stop if the package exceeded 85 C. MiniLM at four threads reached
  87 C. Instead of stopping, the procedure was tightened: abort at 85 C, cool to 55 C before every
  pass, save partial results.
- *Amendment 2.* The first DeBERTa attempt then aborted at 85 C before running any inference,
  from session setup and the library import alone. The abort line was moved to 88 C, one degree
  above the highest reading already seen, a cooldown was added before the import, and that attempt
  was repeated once. This loosened the original stop line.

After Amendment 2 every abort was treated as final.

## 4. Minimal smoke test

MiniLM, one thread, first four pairs: completed in under a second of inference, exit clean, scores
equal to the frozen ones to seven decimal places, 578 MB peak, no swap, GPU not involved (the
process reported no CUDA build and no device). Package temperature went from 53 C to 71 C during it.

## 5. JUNO MiniLM performance

Continuous passes (no cooldown), 99 pairs, three measured passes each, medians. Time per pair.

| Threads | Batch 1 | Batch 4 | Batch 8 | Batch 16 | Peak memory | Peak temperature |
|---|---|---|---|---|---|---|
| 1 | 65 ms | 74 ms | 83 ms | -- | 732 MB | 81 C |
| 2 | 36 ms | 40 ms | 45 ms | -- | 694 MB | 82 C |
| 4 | **23 ms** | 23 ms | 26 ms | 30 ms | 787 MB | 87 C |

Repeats agreed within 2%. Mean and p90 per pair at batch 1: 66 / 87 ms (1 thread), 36 / 48 ms (2),
23 / 30 ms (4). Batching does not help MiniLM on this CPU; single pairs are fastest.

A rerun of MiniLM under the cooled protocol, for exact parity with DeBERTa's procedure, aborted at
88 C four seconds into its one-thread warm pass. It was not repeated.

## 6. JUNO DeBERTa performance

Cooled protocol (package at or below 55 C before each pass), 99 pairs, three measured passes.

| Threads | Batch 1 | Batch 4 | Batch 8 | Peak memory | Peak temperature | Status |
|---|---|---|---|---|---|---|
| 1 | 264 ms | **202 ms** | 214 ms | 1,519 MB | 87 C | complete |
| 2 | 149 ms | **112 ms** | not measured | not recorded | 88 C | aborted on temperature during batch 8 |
| 4 | -- | -- | -- | -- | -- | not run |

Repeats agreed within 1%. Mean and p90 per pair at batch 1: 264 / 312 ms (1 thread), 149 / 174 ms
(2). DeBERTa is about 3.1 times MiniLM's time per pair at one and at two threads, each at its best
batch size.

The two models were therefore timed under slightly different conditions: MiniLM in continuous
passes, DeBERTa starting each pass cool. If that matters it favours DeBERTa slightly.

## 7. Laptop versus JUNO

Best batch size per cell. Laptop figures are from Increment 1.

| | Laptop, 4 threads | JUNO, 1 thread | JUNO, 2 threads | JUNO, 4 threads |
|---|---|---|---|---|
| MiniLM, per pair | 92 ms | 65 ms | 36 ms | 23 ms |
| DeBERTa-v3, per pair | 241 ms | 202 ms | 112 ms | not measured |
| MiniLM peak memory | 695 MB | 732 MB | 694 MB | 787 MB |
| DeBERTa-v3 peak memory | 1,547 MB | 1,519 MB | not recorded (1,161 MB after load) | -- |
| Library import | 12-17 s | 1.8 s | 1.8 s | 1.8 s |
| Model load, files cached (MiniLM / DeBERTa) | 0.3 / 0.7 s | 0.06 / 0.22 s | 0.05 / 0.17 s | 0.05 s / -- |

JUNO at one thread already beats the laptop at four. The memory cost is the same on both machines,
as expected; what differs is that JUNO had about 10 GB free while the laptop had 1-3 GB.

## 8. Memory and system resources

- Available memory never fell below 10.0 GB (DeBERTa) or 10.9 GB (MiniLM). Swap use stayed at zero.
  Memory pressure indicators stayed at zero.
- Process CPU use matched the thread count (1.0, 2.0, 4.0 cores). System-wide CPU averaged 9%, 17%
  and 33%.
- Residency cost: about 340-400 MB for MiniLM and 1,160 MB for DeBERTa after load.
- **Temperature.** Idle package temperature was 45-53 C. Under load:

| Load | Package temperature |
|---|---|
| Library import and model load only | up to 85 C |
| MiniLM, 1 thread, about 75 s continuous | 81 C |
| MiniLM, 2 threads, about 40 s | 82 C |
| MiniLM, 4 threads, about 30 s | 87 C |
| DeBERTa, 1 thread, 20-26 s passes from 55 C | 77-85 C at the end of each pass, 87 C peak |
| DeBERTa, 2 threads, 11-15 s passes from 55 C | 80-86 C, then 88 C |
| MiniLM, 1 thread, 4 s, late in the session | 88 C |

  It fell back to about 55 C within one to four seconds each time. The kernel's thermal-throttle
  counters stayed at zero and the critical threshold is 100 C, so the processor was never throttled.
  The pattern (very fast rise, very fast fall, and a one-thread load reaching 88 C late in the
  session) is a cooling concern worth Cody's attention in its own right. No cause is asserted.

## 9. Ollama coexistence

**Not measured.** Stage D was conditional on Stages A-C completing normally with adequate headroom.
Memory headroom was ample; thermal headroom was not, and adding a generation that uses six CPU
threads would have added heat. The isolated Ollama on port 11435 was not started. It is still not
running. The shared service on 11434 was not touched.

So there is no measurement of whether the verifier slows Qwen or the reverse.

## 10. Scientific checkpoint parity

- Files: all 14 model files matched their laptop hashes again before the retry.
- Label orders read from each checkpoint: MiniLM contradiction, entailment, neutral; DeBERTa-v3
  entailment, neutral, contradiction. Same as the frozen bakeoff.
- Scores: every JUNO run, at every thread count, matched the laptop bakeoff within 3e-6 on all 99
  pairs (tolerance set in advance: 1e-3). No admission decision changes at MiniLM 0.90 or DeBERTa
  0.50 or 0.90. The scientific comparison (38 supported and 5 negatives against 45 and 2; neither
  recovers the Q1 findings) carries over to JUNO unchanged.

## 11. Estimated impact on Ask latency

Projections from the measured warm per-pair rates above, not measured Ask runs.

| | Pairs | MiniLM, 2 threads | DeBERTa, 2 threads | MiniLM, 1 thread | DeBERTa, 1 thread |
|---|---|---|---|---|---|
| Q1 | 9 | 0.3 s | 1.0 s | 0.6 s | 1.8 s |
| Q3 | 20 | 0.7 s | 2.2 s | 1.3 s | 4.0 s |
| Larger question | 230 | 8 s | 26 s | 15 s | 46 s |

- Against the live Q1 and Q3 runs (389 s and 348 s, 28 and 38 generative calls), DeBERTa on JUNO
  would add about 0.7 s and 1.5 s at two threads: 0.2% and 0.4%. The verifier is not what makes Ask
  take minutes, on either machine or with either model.
- Cold start on JUNO is small: 1.8 s import, under 0.3 s load with files cached, under 0.3 s first
  call. A first load from disk was not measured.
- The 230-pair DeBERTa projection is where the temperature finding bites: 26 s of continuous
  two-thread load is longer than the passes that reached 88 C.
- **Architecture.** These numbers describe JUNO as a machine. Callosum's verifier runs in the desktop
  application's own process today. Using JUNO for verification would need a new service boundary and
  network transfer of claims and quotes. None exists and none was built or designed here.

## 12. Operational concerns and remaining uncertainty

- **No second reset.** About ten minutes of intermittent CPU load at one to four threads completed
  without one.
- **The cause of the 12 October reset is still unknown**, and six threads was deliberately not run.
- **CPU temperature** limits sustained CPU inference on JUNO for either model until it is understood.
- **Coexistence with generation is unmeasured.**
- **DeBERTa at four threads is unmeasured**; the three-times ratio is established at one and two
  threads only.
- **Left on JUNO:** the task folder, now 7.2 GB (the second, CPU-only environment added 1.1 GB).
  Nothing of this experiment is running. No service, package, mount, swap or security setting was
  changed. The USB disk that was a swap device in the previous boot is noted for Cody.
- One short session; temperatures depend on room and case conditions not recorded.

## 13. Recommended next decision

1. **The case for a DeBERTa qualification is unchanged, and slightly clearer.** Runtime and memory do
   not argue against it on JUNO or the laptop. The open question remains scientific: natural
   negatives and independent labels, as set out in the scientific bakeoff.
2. **Do not treat JUNO's CPU as a verification host yet.** That is a hardware question for Cody
   (cooling first), not a model question, and it applies equally to MiniLM.
3. **The coexistence test should wait** for that, since it is the measurement most likely to run the
   CPU hard for longer.
4. No verifier change, threshold change or deployment work is recommended from this increment.

---

# Increment 1 -- Interrupted attempt and laptop-only close-out (preserved as written)

**Disposition: HARDWARE TRADEOFF UNRESOLVED -- PRODUCTION INCIDENT.**

**Exit: MODEL DECISION DEFERRED, with LOCAL EVALUATION CONTINUES** for work that needs no new
hardware.

No valid JUNO inference-time comparison was completed. JUNO hard-reset within seconds of the first
benchmark starting, which took production websites down. JUNO is now a protected production host.
Everything after the incident in this report was done on the development laptop from local files
only.

Nothing was implemented. No production source, model default, threshold, semantic version,
historical baseline or frozen evidence changed. No generative model was called.

## 1. Interrupted benchmark and incident timeline

All times EDT, 12 October 2026. Sources: the local incident record and command output captured at
the time (`.local/phase34-juno-nli-hw-20261012/INCIDENT.md`, `incident_followup.log`).

| Time | Event |
|---|---|
| 15:04-15:08 | Read-only preflight. An isolated Python environment was created in a user-owned folder on JUNO's data disk and PyTorch 2.6.0 installed into it. Both checkpoints, the 99-pair file and the script were copied over; all 14 model files hash-verified. |
| 15:09:01 | Benchmark script started. Its preamble completed: PyTorch reported the NVIDIA RTX 3050 as available; neither Ollama service had a model resident. |
| 15:09:01 onward | First intended benchmark began: MiniLM, CPU, six threads. It produced no output file. |
| 15:09:02 | Last event in the previous boot's journal. |
| 15:09:47 | Next boot. Previous uptime: 18 days 23 hours. |
| 15:11:29 | `juno-web-candidate.service` reached its start limit and stayed failed. |
| about 15:28 | Reset noticed. Benchmarking stopped; nothing was retried. |
| later | clffwrkmn.net and its subdomains were found unreachable. Cody restored the web stack. |

**Production impact.** The public sites route through a Cloudflare tunnel to a container stack that
did not come back after the reboot. Shared Ollama, Plex, Jellyfin, the tunnel client, Tailscale,
authentik and the sync server restarted by themselves.

## 2. Verified starting and ending state

- Start: `28d288e972de33409bd5aacac353d5cfd9f06194`, worktree clean, branch in sync.
- End: tracked changes are this report and the lineage entry. 188 preserved input files hashed
  before and after; none changed.
- Execution after the incident was confirmed local before anything ran: Windows host, local working
  and output directories, CPU-only PyTorch, and a copy of the script with its one GPU query removed.
  The script has no network or remote path.
- One leftover was found and closed during that check: a background SSH session of this experiment,
  a wait loop polling the benchmark log, had been connected since 15:18. It was closed from the
  laptop. Whether its remote shell loop ended with the connection is not known and was not checked.

**Left on JUNO, untouched:** the 6.1 GB task folder
`/media/brain/JUNO/callosum-ask-exp/nli-hw-20261012` (Python environment, two checkpoints, script).
The isolated Ollama on port 11435, a user process rather than a service, was not running after the
reboot. No system package was installed.

**Disclosure.** After the reset, four SSH sessions were used to diagnose it, and one read the
system journal through passwordless sudo. They changed nothing, but they were activity on a host
that had just failed.

## 3. Measurements completed before the incident

- JUNO description from the preflight: Intel Core i7-8700 (6 cores, 12 threads, AVX2), 15.9 GB RAM
  with about 12.5 GB available and 3.5 GB of swap already in use, Debian 12, RTX 3050 8 GB on driver
  580.178.04, no PyTorch installed system-wide, nothing resident in either Ollama.
- Checkpoint parity: MiniLM `b95119ce93d3e065de6214e38cd4a97b0f2f2c6d` and DeBERTa-v3
  `6f5cf0a2b59cabb106aca4c287eed12e357e90eb`, the same files as the scientific bakeoff, transferred
  and hash-verified. Neither completed a benchmark on JUNO.

## 4. Measurements not completed

Every JUNO measurement: CPU timing at any thread count, score parity on JUNO, GPU timing, memory
and residency, and all three Ollama coexistence conditions. No partial result exists.

## 5. Known and unknown causes

**Observed.** The benchmark began immediately before an abrupt reset. The journal ends without a
shutdown sequence. No kernel panic or machine-check record was found, and the crash store was
empty. Temperatures read normal about twenty minutes later.

**Plausible hypotheses.** CPU or power stress from the six-thread load; something in driver or GPU
initialisation when PyTorch queried the card; an existing hardware instability; or an unrelated
failure that happened to coincide.

**Not established.** Which of these, if any, caused the reset. The timing makes this experiment the
leading suspect. It does not identify a mechanism, and nothing here should be read as attributing
the reset to PyTorch, the NVIDIA driver, CPU load, thermals or power delivery. JUNO has previously
run long six-thread Ollama workloads without incident, which neither clears nor implicates this
one.

No stress test is proposed. The investigation belongs to Cody.

## 6. Laptop-only comparison

Laptop: Intel Core i7-8565U (4 cores, 8 threads), 16 GB RAM, Windows 11, PyTorch 2.6.0 CPU build.
Same script, files and data as planned for JUNO; one fresh process per model; one unmeasured warm
pass, then three measured passes per batch size; medians shown. Scores are identical to the
scientific bakeoff's (maximum difference 0.0; no admission decision changes).

| | MiniLM, 4 threads | DeBERTa-v3, 4 threads | MiniLM, 2 threads | DeBERTa-v3, 2 threads |
|---|---|---|---|---|
| One pair at a time, mean / p90 | 92 / 124 ms | 374 / 467 ms | 102 / 140 ms | 392 / 479 ms |
| Batch 4, per pair | 99 ms | 258 ms | 108 ms | 292 ms |
| Batch 8, per pair | **93 ms** | **241 ms** | 117 ms | 316 ms |
| Batch 16, per pair | 99 ms | 283 ms | 129 ms | 321 ms |
| Model load (files cached) | 0.3 s | 0.7 s | 0.5 s | 2.5 s |
| Memory after load | 375 MB | 1,148 MB | -- | -- |
| Peak memory | **695 MB** | **1,547 MB** | 693 MB | 1,542 MB |
| Lowest system memory available during run | 2.6 GB | 1.5 GB | 1.4 GB | 0.8 GB |

- These are laptop measurements. They are not JUNO estimates, and nothing here says whether JUNO
  would be faster or slower.
- The four-thread figures reproduce the earlier reference (91 ms and 243 ms per pair).
- The two-thread run was the one measurement added after the incident. Halving threads cost little
  (about 10-30%), so this laptop is not making good use of four threads. That is a property of this
  machine; it should not be generalised.
- The laptop was short of memory throughout: 2-3 GB available and about 11-12 GB already in its page
  file before any model loaded. DeBERTa's extra 850 MB took available memory under 1 GB in one run.
- Library import took 12-17 s and is the same for both models.

## 7. Practical NLI model tradeoffs

**Q1. Does the speed difference matter to Ask end to end?** No, on this evidence. Projected from
the laptop's batch-8 rate:

| | Pairs | MiniLM | DeBERTa-v3 | Extra | Share of the live run |
|---|---|---|---|---|---|
| Q1 | 9 | 0.8 s | 2.2 s | +1.3 s | +0.3% of 389 s |
| Q3 | 20 | 1.9 s | 4.8 s | +3.0 s | +0.9% of 348 s |
| Larger question | 230 | 21 s | 55 s | +34 s | not measured live |

These are projections from warm per-pair rates, not measured Ask runs. In the live runs
verification was already a small fraction of the total; 28 and 38 generative calls account for
nearly all of it. Changing the verifier neither causes nor cures the multi-minute response time. The
230-pair case is the only one where the difference would be noticeable, and it is illustrative.

**Q2. Is the accuracy worth the memory and CPU on a typical desktop?** Not yet decidable. Time is
not the obstacle. Memory is: DeBERTa holds about 770 MB more while resident, and on a 16 GB machine
that is already under pressure that showed. The benefit side rests on 3 of 27 synthetic controls
and 7 net supported pairs, and does not touch the Q1 failure. One machine, already memory-starved,
is also not a sample of typical desktops.

**Q3. Is a smaller NLI-fine-tuned DeBERTa worth comparing?** Yes, as one bounded comparison, at
lower priority than labels. Smaller DeBERTa-v3 NLI checkpoints are published (small and extra-small
variants). None is on this machine, so comparing one needs a download and was not done. The open
question is scientific, not speed: the published small variants were, as far as known without
checking, trained on less varied data than the base model tested here, and that extra data may be
where its advantage comes from. Identity, licence and training data would need the same
qualification as before.

**Q4. Are more measurements needed first?** Not for the latency question; the existing figures
settle it. Not for a replacement decision either, because what is missing there is labels, not
timing. A JUNO timing would add nothing to the scientific case.

**Q5. What labels would justify a future replacement?**

- Natural negatives: real unsupported and contradicted claim/quote pairs from Ask runs. The current
  negatives are all edits of claims MiniLM had already verified.
- A fresh set assembled without sight of either model's scores, with a human adjudicating at least a
  sample alongside the model adjudicator.
- More cases of the two errors both models still pass: correlation stated as cause, and near-synonym
  substitution.
- A threshold chosen on one part and confirmed on another.
- An explicit statement that the referential-context failure behind Q1 is out of scope for a
  verifier swap.

## 8. Safeguards for future experiments

Three layers, weakest to strongest. None of these was changed in this increment.

**Instruction-level controls.** Written rules: JUNO is production; no agent activity there without
explicit, current authorisation naming the activity; earlier go-aheads do not carry over. Instructions
state intent and make a violation obvious in review. They cannot technically stop an agent from
running a command it has the means to run.

**Access-level controls.** Remove the means. This is what actually prevents a repeat by accident.

**Infrastructure isolation.** Run experimental CPU, GPU and heavyweight inference work on a machine
that hosts nothing else. This is the strongest safeguard and the only one that covers failures no
one predicted. Containers, process priority, CPU limits and memory limits do not provide it: they
bound what a process may consume, and they share the host's kernel, drivers, power supply and
cooling. A reset of the kind seen here takes everything on the box with it regardless.

**Smallest practical changes Cody could make later:**

1. Add the production-host rule to the repository's agent guidance, including that prior
   authorisations for JUNO are void.
2. On the laptop, add deny rules for `ssh`, `scp` and tunnel commands targeting JUNO in the agent's
   permission settings, so such a command is refused or prompts instead of running.
3. Keep the key that reaches JUNO out of the agent's reach, for example a separate
   passphrase-protected key for production administration that is not loaded into the agent's
   session.
4. On JUNO, if agents ever need access again, a separate unprivileged account without sudo. The
   account used here has passwordless sudo.
5. Decide where experimental inference lives. Note the consequence in section 10: Ask's live
   generation has been running on JUNO too.

Access that production recovery depends on should stay as it is until Cody replaces it deliberately.

## 9. Is any further local experiment warranted?

- **No more timing runs.** The latency question is answered for the laptop, and more numbers would
  not change it.
- **Worth doing locally, with no new hardware:** assembling the natural-negative labelled set from
  preserved Ask runs. It needs no model download and no inference beyond the two local classifiers.
- **Needs separate approval (a download):** one smaller NLI-fine-tuned DeBERTa-v3 checkpoint,
  qualified and scored on the same 99 pairs.

## 10. Recommendation for resuming scientific Ask development

1. Treat the verifier model as a deferred decision. MiniLM stays; B2 stays opt-in and experimental;
   DeBERTa-v3 remains a promising candidate with no deployment case yet.
2. Do not spend more effort on verifier speed. It is about 1% of a live run.
3. The scientific gap that mattered in Q1 and Q3, referential context and result recognition, is
   untouched by any model tested and remains the more valuable target.
4. **A dependency to decide before any further live Ask run:** the reviewed live runs used an
   isolated Ollama on JUNO for generation. That is production-host activity and is not authorised.
   Until there is a decision on where generation runs, Ask development is limited to offline work on
   preserved runs.

## Measurement limitations

- No JUNO data. Every number in sections 6 and 7 is from one laptop in one session.
- The laptop was memory-constrained, which may have affected timing and certainly affected the
  available-memory figures.
- Projections assume warm, resident models and linear scaling with pair count.
- The incident timeline is reconstructed from output captured at the time; no further evidence was
  retrieved.
- The scientific limits of the 99-pair set carry over unchanged: small, previously inspected, one
  model adjudicator, synthetic negatives.
