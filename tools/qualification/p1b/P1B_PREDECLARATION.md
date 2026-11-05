# P1b predeclaration, version 1 (inc 636), frozen before the first hosted P1b run

This document fixes the P1b method before any P1b measurement exists. Its SHA-256 and the fixture's SHA-256 are
pinned in `p1b_qualify.ps1`; the run refuses to measure if either file differs. Nothing here is revised after
measurement. Where it differs from the inc 632A plan (`RELEASE_060_PACKAGED_MODEL_QUALIFICATION_PLAN.md` §8.3), the
difference is listed in §9 with its reason.

## 1. Question

Is DeBERTa (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` at `6f5cf0a2b59cabb106aca4c287eed12e357e90eb`)
operationally acceptable as Callosum's preferred local verifier on the shipped Windows CPU runtime
(`win-x86_64-py3.11-s1-2094b5a287a1dd54`, tree `a51f65b3…f2fc`)? P1b is an operational qualification. It is not
scientific adjudication, threshold calibration, or model selection. It never arms
`DEBERTA_RELEASE_GATES.packaged_runtime_acceptance`; that is a later product decision.

## 2. Code under test

The application tree is pinned by Git tree identity and must equal the integration branch
`integrate/inc607-608-ask` at `da47c81bcbd928da2d7a2ab7f596d0cecc7d54f9`:

| Path | Tree |
|---|---|
| `app` | `39edfb6a1e29eb37155589ce3634287980d77d1e` |
| `integrations` | `f02b9dbad694cceee0f109d454465922380e8fa9` |
| `alembic` | `88d476b99486fe22716b6156437006d4cc31f525` |
| `tests` | `2ab60beeb6d912f7ca30261d984db327ac3ca9b4` |
| `pyproject.toml` | `53edf2b51b86385154bac5ed1840512ca026caca` |
| `uv.lock` | `e5966c320bb5e4f113fd18c58de2ec8ef8e1f74b` |

The qualification branch `qualify/p1b-0.6.0` starts from the qualified P1 commit
`f1d6c4302af3350146676fd79b7c62bacf3495c7` and adds only `tools/qualification/p1b/` and
`.github/workflows/p1b-qualification.yml`. The P1 harness, workflow and evidence are not modified. P1b reuses the P1
runtime-extraction, tree-digest and Minisign scripts unchanged, by path.

## 3. Workload

**Fixture** `fixtures/p1b-pairs-v1.json`: 21 pairs written from scratch for P1b. Every study, number, place and
name is fictional; no private G1 or G2 text is used, and none is uploaded. This is a new fixture. It does not
reproduce the G2 21-pair subset, whose harness and pair list were not retained.

- Each pair is the app's NLI input: premise = the citation quote, hypothesis = the claim sentence
  (`LocalCitationVerifier.verify_many` builds `(citation.quote, sentence)`).
- Quote lengths: 271 to 472 characters (36 to 72 words; median 44). The app caps a quote at 500 characters.
- Sentence lengths: 13 to 27 words (median 19).
- Token lengths under both pinned NLI tokenizers are measured by the `tokenize` stage, before the first timed call,
  and recorded in the receipt. A pair longer than the tokenizer's model maximum fails the stage.
- Each quote sits verbatim in its own chunk (`chunk_text`), so the quote check passes as for a real citation.
- The candidate pool is the 21 cited chunks plus 9 synthetic distractor chunks, i.e. 30 source chunks, the same
  pool for every item, as in a real synthesis.
- `design_relation` (support / contradict / neutral) records only the author's intent, so the workload mixes
  outcomes. No acceptance decision reads it.

**One verification operation** = one `verify_many` call over all 21 items with the 30-chunk pool. Within it the
app makes one MiniLM encode call and one NLI `predict` call for all 21 pairs (inc 418/490 batching, unchanged). No
batching, padding, thread or model setting is changed by the harness.

**Indexing corpus (condition B):** a disposable synthetic library generated deterministically from the fixture
(seed 6360002, 400 papers × 100 chunks × 260 words from a fixed 250-word vocabulary). Its SHA-256 is recorded.

## 4. Application path

- The verifier is chosen by the app's own synthesis resolution, `summaries._verifier` → `verifier_resolution.decide`
  → `resolve_support_scorer` (which runs `verify_nli_checkpoint`), with the preference stored through
  `set_nli_user_preference`. Condition DeBERTa uses an explicit DeBERTa preference; the gates stay disarmed.
  `CALLOSUM_MODEL_PROVISIONING=1` makes the checkpoint provisioner-managed, as in the packaged app.
- The similarity model is `resolve_embedding_model` (MiniLM, the verification-similarity model). The vector store is
  `SQLiteVecVectorStore`. The database is a disposable SQLite file migrated with the app's Alembic chain.
- Checks per measured process:
  - provenance names the expected profile, model and revision, preference `user`, `embedding_fallback` false, and
    fallback reason none for DeBERTa (`user_choice` for the explicit MiniLM2 reference, which is what the app records
    when a user picks the baseline);
  - the DeBERTa scorer has no fallback scorer and loads with `local_files_only`;
  - the loaded runtime's model name and revision are DeBERTa's;
  - thresholds are 0.70 / 1.00 / 0.55 / 0.55;
  - every result carries a support and a contradiction probability;
  - the status of every item is identical across all 9 calls of the process;
  - exactly one NLI cross-encoder is resident in the app's model registry, and it is the expected one.

  The warm-up processes run the same checks, and their failures count like any other.
- **Fail closed** (stage `failclosed`), using the app's own code:
  - an explicit DeBERTa choice with a simulated low-memory snapshot must raise `VerifierUnavailableError`, not
    return MiniLM2;
  - an inference failure injected into the loaded DeBERTa runtime must raise `NLIInferenceError` from `verify_many`,
    with no score from another model, and no other NLI model may be loaded;
  - the loaded checkpoint checked against a profile with a different label order must be refused
    (`NliProfileConfigurationError`);
  - with the gates as committed, `packaged_runtime_acceptance` is false and an automatic (unset) preference resolves
    to MiniLM2 with reason `not_qualified`.

  These are simulations of resource pressure. Real exhaustion is not induced.
- MiniLM2 (`cross-encoder/nli-MiniLM2-L6-H768` at `b95119ce…`) runs the same path with an explicit MiniLM2
  preference. It is reference and dependency evidence only. Its timings are reported separately and never enter
  the DeBERTa decision.

## 5. Conditions, order and repetitions (serial, never parallel jobs)

1. One discarded warm-up process per model (DeBERTa, then MiniLM2). It brings model files into the OS file cache
   and writes the 30 MiniLM chunk vectors, so every measured process starts from the same state.
2. **Condition A, DeBERTa alone:** 3 fresh processes.
3. MiniLM2 alone: 3 fresh processes (reference).
4. Start the real Arctic S worker and wait until its run row is `running`, owned by the launched process, with at
   least 16 committed chunks (2 batches of 8). If that does not happen within 600 s, condition B is not measured
   and the run is INCONCLUSIVE.
5. **Condition B, DeBERTa with Arctic S indexing:** 3 fresh processes.
6. MiniLM2 with Arctic S indexing: 1 process (reference, as in plan §8.3).
7. Ask the worker to pause through its own run row; it must exit between batches with code 3 within 120 s,
   otherwise it is killed and that is recorded as a failed cleanup check.

**Arctic S worker:**
- The production entry `app.backend.embeddings.index_worker.main` loads the provisioned checkpoint with
  `--local-files-only` through `load_profile_model` and indexes with `run_worker`. It uses the real batch commits,
  checkpoints, heartbeat, disk guard and resource policy, on the same database as the verifier, which is how the app
  runs it.
- It is launched as `python.exe -I -B p1b_worker.py`. That shim puts the checkout on `sys.path`, because `-I` drops
  it, and calls `main`. The supervisor's own launcher would run `python -m` without `-I -B`, which writes bytecode
  into the verified runtime.
- Shape as plan §8.3: 4 threads, batch 8, below-normal priority. The supervisor's default on a 4-vCPU machine would
  be 2 threads, so this is the heavier load. The run row is armed the way `IndexSupervisor._maybe_launch` arms it.
- The supervisor's monitoring, retry and restart are not exercised: that is P3.

## 6. Measurement definitions

- **Timer:** `time.perf_counter()` immediately before and after the `verify_many` call. The call runs inside
  `engine.begin()` (as in the summarize pipeline). The transaction is opened before the timer starts and committed
  after it stops.
- **Cold:**
  - from the process creation time (`GetProcessTimes`) to the return of the first `verify_many` call;
  - this includes interpreter start, imports, verifier resolution with DeBERTa load and contract check, MiniLM load
    and the first call;
  - the components are recorded separately;
  - the batch returns all 21 results at once, so "first verified pair" means the end of the first call.
  - Cold is reported, not judged (the plan sets no cold limit).
- **Warm:** the 8 `verify_many` calls that immediately follow the cold call, in the same process. No other warm-up.
- **Threads:** torch defaults, never overridden in verifier processes. `torch.get_num_threads()`,
  `torch.get_num_interop_threads()` and `os.cpu_count()` are recorded. The harness sets no
  `TOKENIZERS_PARALLELISM`, `OMP_NUM_THREADS` or similar variable.
- **Memory:**
  - `K32GetProcessMemoryInfo` on the measured process: `PeakWorkingSetSize` (peak working set) and
    `PeakPagefileUsage` (peak private commit). These are OS peak counters, not samples.
  - Read after imports, after verifier resolution, after the cold call, after each warm call, and at exit.
  - The driver also samples every measured process, the worker and system memory once per second.
- **Units:** acceptance compares bytes / 10^6 with the MB limits, the stricter of the two readings of "MB". MiB is
  also reported.

## 7. Acceptance (from plan §8.3, unchanged numbers)

| Criterion | Statistic | Limit |
|---|---|---|
| Warm, DeBERTa alone | the **largest** of the 3 per-process medians (each the median of that process's 8 warm values) | ≤ 7.2 s |
| Warm, DeBERTa with Arctic indexing | the **largest** of the 3 per-process medians | ≤ 8.8 s |
| Peak working set | the largest `PeakWorkingSetSize` over the 6 measured DeBERTa processes | ≤ 2,520 MB |
| Peak commit | the largest `PeakPagefileUsage` over the 6 measured DeBERTa processes | ≤ 2,870 MB |

The plan names "per-process median, and the range of medians" without fixing which median is compared. This
declaration fixes the least favourable reading: every process's median must meet the limit. The pooled median of
all 24 warm values, the range of medians and every raw value are reported, never used for acceptance. No tolerance
beyond the limits is applied. The 25 % runtime allowance is already inside the memory limits (plan §8.3).

**Concurrency is established for a condition B process only if:**
- the worker process is alive at the start and end of every warm call;
- the worker uses at least 0.10 CPU-seconds per wall-second during every warm call (from `GetProcessTimes`);
- its committed `indexed_chunks` rise between the start of the first and the end of the last warm call.

Condition B is evaluated only when all 3 counted processes are established. Otherwise condition B is INCONCLUSIVE:
missing overlap is never counted as concurrent and never counted as passing.

**Noise rule (plan §8.3):** a measured process is discarded if, during it:
- available physical memory sampled by the driver fell below the app's `ResourcePolicy` reserve; or
- a process outside the harness (and outside the worker in condition B) used at least 0.25 CPU-seconds per
  wall-second.

"The harness" means the measured process and its children, the driver's own PowerShell process, the Arctic worker,
the WMI provider host that answers the driver's process queries (`WmiPrvSE`), `conhost`, and the kernel pseudo-processes
(`Idle`, `System`, `Registry`, `Memory Compression`, `Secure System`). Foreign CPU is the per-process difference of
total CPU time between the start and end of the measured process. The five busiest foreign processes are recorded
for every measured process, discarded or not.

**Timeouts:** a measured process gets 900 s. One that is still running then is killed and recorded as a failed
**performance** check, because 9 calls at the limit plus any plausible cold start fit well inside it. A process
killed because available physical memory fell below 1.5 GiB is recorded as infrastructure, with its sampled working
set, since the worker shares the machine.

A discarded process is repeated once, with both recorded. Two discards in a row make that condition INCONCLUSIVE.
Nothing else is repeated.

## 8. Verdict

- **FAIL:** any failed integrity, contract, scientific, isolation or **performance** check, including a warm median
  or memory peak over its limit. Slowness of the packaged runtime is never re-labelled as infrastructure.
- **INCONCLUSIVE:** otherwise, any failed infrastructure check, unestablished concurrency, two discards in a row, a
  missing measurement or an incomplete stage.
- **PASS:** every stage complete and every check passed.

One run, no automatic rerun. Out-of-range values go to Cliff. Limits are not revised after measurement.

## 9. Differences from plan §8.3, and why

| Plan §8.3 | P1b v1 | Reason |
|---|---|---|
| First 21 Set A items of the private G1 receipt | the new public synthetic fixture above | the brief forbids publishing G1/G2 material to GitHub Actions; the G2 comparison stays envelope-level |
| §8.2 G1 categorical parity (99 + 209 pairs) is part of P1b | **not covered** | same reason; G1 stays CONDITIONAL and the gap is carried to the arming decision |
| Concurrency: one run per model | 3 DeBERTa processes, 1 MiniLM2 | the brief requires 3 processes per condition for DeBERTa |
| "Arctic encoding worker shaped like G2's" | the real `index_worker` entry, same shape | stronger: real indexing, not a load generator |
| Median rule unstated | largest per-process median | least favourable reading, fixed now |
| Memory sampled at load points | OS peak counters plus those samples | peaks cannot be missed between samples |
| Laptop isolation (dedicated local account, ACLs, protected targets) | fresh hosted VM, as P1 | the P1 hosted isolation contract |

## 10. Scope of a PASS

A PASS supports `packaged_runtime_acceptance` for Windows x64 on a 4-vCPU, 16 GB hosted VM. It does not show:
- that the gate should be armed;
- G1 scientific parity on the packaged runtime;
- threshold calibration;
- P2, P3 or P4;
- 8 GB machines, macOS or Linux.
