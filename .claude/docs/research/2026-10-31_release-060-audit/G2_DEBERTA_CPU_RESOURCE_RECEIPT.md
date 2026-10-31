# G2: DeBERTa CPU latency and memory receipt

> *Publication note (2026-10-31, inc 616 documentation commit): absolute local paths were rewritten to `%USERPROFILE%` form and a session-scratchpad path was replaced by a description before committing. No finding, number or status was changed.*

**Date:** 2026-10-31.
**Authority:** the "Increment 614 and Bounded DeBERTa Qualification" instruction, §3.
**Bounds:** existing fixture data only (the 99 Phase 34 chunks and claims), local pinned models, serial fresh
processes, disposable DB copies, offline. Not run: full-library benchmark, policy change, interference with other
workloads.

**Recommendation for the G2 component: CONDITIONAL GO.**
- It fits within the inc-610 memory policy on this 16 GB machine.
- It adds about 3 s to a typical synthesis's verification stage.
- No ordinary-use responsiveness degradation was observed.
- Conditions: §6.

Speed says nothing about scientific correctness (see G1).

## 1. Conditions
| | |
|---|---|
| Machine | Windows 11 Pro 26200, Intel64 Family 6 Model 142 (8 logical CPUs), 16,197 MB RAM, commit limit 26,437 MB |
| Machine state | **Not idle:** the user's other applications held ≈10–12 GB. Free physical memory 3.6–6.0 GB during the runs |
| Runtime | Python 3.12.7, torch 2.6.0+cpu, 4 torch threads (default), fp32. This is the dev environment, not the packaged runtime (torch 2.13 / transformers 5.14); the packaged runtime was not measured |
| Models | `nli-MiniLM2-L6-H768` @ `b95119ce…`; `DeBERTa-v3-base-mnli-fever-anli` @ `6f5cf0a2…`; embeddings `all-MiniLM-L6-v2` @ `1110a243…`; concurrency load `snowflake-arctic-embed-s` @ `e596f507…` |
| Path | The same app path as G1: `resolve_support_scorer(app, nli_profile=…)` → `LocalCitationVerifier.verify_many` on a disposable copy of the G1 DB. Each process loads the MiniLM embedding model too, as the app does |
| Safety gate | Every run checked free memory against the inc-610 `ResourcePolicy` first: estimated need + 809 MB reserve; concurrent runs also counted the 1,200 MB index-worker estimate. All runs cleared it; none was forced |
| Concurrency | One measurement process at a time. In "concurrent" runs, one Arctic encoding process shaped like the inc-610 worker ran alongside: same loader, 4 threads, batch 8, `BELOW_NORMAL_PRIORITY_CLASS` |

**Raw receipts:**
- `.local/inc614-g2/G2_RECEIPT_RAW.json`: latency, 2 solo runs per model plus 1 concurrent run.
- `.local/inc614-g2/G2_MEMORY_RAW.json`: memory. The first pass's `GetProcessMemoryInfo` call was mistyped and
  returned zeros, so memory was re-measured in fresh processes with a typed call.
- Harness: `<session scratchpad, not retained>\inc614\` (`g2_run.py`, `g2_child.py`, `g2_mem.py`, `arctic_load.py`).

## 2. Latency (medians; the range across independent fresh-process runs)
| Measure | MiniLM2 (current) | DeBERTa | DeBERTa − MiniLM2 |
|---|---|---|---|
| Cold: model load + first pair (files in OS cache) | 0.44–1.00 s | 0.97–2.41 s | ≈ +0.5–1.4 s, once per app session |
| Warm single pair | 98–170 ms | 368–385 ms | ≈ 2.3–3.8× |
| **Representative Ask verification: 21 pairs** (7 claims × 3 citations, the primary-synthesis schema maximum; the whole `verify_many` stage including embedding, retrieval and quote checks) | 2.2–5.8 s (stable runs 2.2 / 2.9) | 5.4–7.2 s | **≈ +3 s per synthesis** |
| Broad run: 63 pairs | 7.9–15.1 s (stable 7.9 / 10.9) | 20.0–22.8 s | ≈ +10–12 s |

- The first MiniLM2 process's 77 s import was a cold disk cache and does not depend on the model. Later imports took
  10–25 s for both.
- MiniLM2's first-run figures (5.8 s and 15.1 s) carry that cold-start noise; the stable figures are the second runs.

## 3. Memory: whole verification process
Includes Python, torch, the MiniLM embedding model and app imports.

| Stage | MiniLM2 process | DeBERTa process |
|---|---|---|
| After imports | 328 MB | 328 MB |
| After loading the embedding model | 540 MB | 539 MB |
| After loading the NLI model (peak working set) | 721 MB | 1,601 MB |
| **Peak working set over the whole run** | **958 MB** | **2,016 MB** |
| Peak commit | 1,334 MB | 2,298 MB |

**DeBERTa costs ≈ +1.06 GB peak working set and ≈ +0.96 GB peak commit** over MiniLM2 in the same process.
- In the app, MiniLM2 stays resident for stance features, Suggest and Critical Read (Scope §7). If DeBERTa becomes
  the synthesis verifier, both NLI runtimes can be resident at once, so the increment is additive: about 1 GB more
  than today.
- The bakeoff's standalone figure (1,528 MB peak) is consistent: it excluded the embedding model and app.

## 4. Concurrent indexing pressure
| | MiniLM2 + Arctic worker | DeBERTa + Arctic worker |
|---|---|---|
| Free memory with the worker loaded, before the verifier | — | 5,332 MB |
| Free memory after | 4,873 MB | 3,851–3,901 MB |
| Arctic worker peak working set | — | 623 MB (commit 696 MB) |
| Verifier, warm single pair | 132 ms | 554 ms (+44–50 % vs solo) |
| Verifier, 21 pairs | 3.6 s | 7.2–8.8 s (+25–45 % vs solo) |
| Verifier, 63 pairs | 12.0 s | 28.3–28.9 s |
| Arctic throughput meanwhile | 2.86 passages/s | 1.11–2.37 passages/s |

- On this machine both fit together with ≈3.9 GB free afterwards, above the policy's pause (606 MB) and stop
  (404 MB) floors.
- The worker yields as designed (below-normal priority), so Arctic indexing slows while a DeBERTa verification runs.

## 5. Ordinary-use responsiveness
An ordinary Library-style read (a 50-paper page plus a chunk count) ran on a separate connection every 25 ms during
verification.

| | Idle median / max | During verification median / p90 / max |
|---|---|---|
| MiniLM2 | 0.5–0.8 / 1.4–3.8 ms | 0.9–1.3 / 1.3–3.7 / 68–197 ms |
| DeBERTa | 0.5–0.9 / 1.4–1.8 ms | 0.8–0.9 / 1.0–1.3 / 79–128 ms |

No degradation attributable to DeBERTa: medians stay below 1 ms, and the occasional 70–200 ms spikes appear under
both models.

**Not measured:** UI rendering and PDF viewing. Those are browser-side work and do not share the backend thread pool's
CPU in the same way.

## 6. Recommendation for the deployment gate: CONDITIONAL GO
**Supports activation:**
- Memory fits the existing inc-610 policy on a 16 GB machine, even alongside an index build.
- No observed responsiveness regression.
- The latency cost (≈ +3 s on a 21-citation synthesis, ≈2.5× the verification stage) is incurred inside an
  already-long, Status-tracked background job.

**Conditions** (none needs a new experiment):
1. **The per-operation memory precheck (F19) is required.** Use DeBERTa only when the policy's free memory covers
   ≈1.1 GB extra plus the reserve. Otherwise record `insufficient_memory` and use MiniLM2. On 8 GB machines this will
   often fall back, which is the honest outcome.
2. **ETA honesty (invariant #5).** If any synthesis ETA or calibration assumes MiniLM2's verification duration, key
   it by the effective verifier. It must not under-promise by ≈2.5× on that stage.
3. **LATENCY.md disclosure.** Activation is an intentional, measured latency change for a scientific reason. Record
   these figures there when it is implemented (rule #12 item 8).
4. **Packaged-runtime re-check.** These are dev-environment numbers (torch 2.6). Confirm one cold and warm 21-pair
   measurement on the packaged runtime (torch 2.13) in the release validation step (sequence step 10). It need not be
   a new study.

**Incomplete:**
- macOS and Linux;
- 8 GB hardware;
- the packaged runtime;
- whole-synthesis wall-clock time including generation (that depends on the provider).
