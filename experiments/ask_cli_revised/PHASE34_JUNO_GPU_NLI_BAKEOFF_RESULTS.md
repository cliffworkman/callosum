# Phase 34 -- JUNO GPU NLI bakeoff

Date: 2026-10-12. Branch `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, starting HEAD
`9bf631c14e2e07bf457554395f7a4b91ec05dc3c`.

**Disposition: GPU FAVORS DEBERTA** (a hardware conclusion only). On JUNO's RTX 3050 both models
reproduce their frozen scores and every admission decision, DeBERTa-v3-base verifies a pair in about
7 ms end to end, uses about 1.1-1.3 GB of GPU memory, and the whole experiment stayed far inside every
guard. This does not select DeBERTa scientifically: the labels are still one blinded model adjudication,
and neither model recovers the two central Q1 findings.

No production code, default, threshold or device-selection logic was changed. Nothing was installed on
JUNO. No reset occurred.

## 1. Starting state and preservation

- Worktree clean at `9bf631c1`, in sync with its upstream.
- 227 preserved files under ten earlier experiment folders (including both prior JUNO folders) were
  hashed before and after; see section 14 for the result.
- On JUNO, the existing task folder `/media/brain/JUNO/callosum-ask-exp/nli-hw-20261012` already held
  the CUDA-enabled environment (`venv`: torch 2.6.0+cu124, transformers 4.48.3, tokenizers 0.21.4) and
  both checkpoints. All 14 checkpoint files and `pairs.jsonl` passed their recorded SHA-256 sums. No
  download and no installation was needed.
- New files on JUNO: `j_gpu.py`, `run_gpu.sh` and an `out_gpu/` folder of logs. The folder is still 7.2 GB.

## 2. GPU preflight (read-only, before any CUDA initialisation)

| Item | Observation |
|---|---|
| GPU | NVIDIA GeForce RTX 3050, 8,192 MiB, driver 580.178.04 |
| GPU idle state | 42 C, 0% utilisation, fan 0%, power state P8 |
| GPU memory | 120 MiB in use (Xorg, 98 MiB), 7,718 MiB free |
| GPU compute processes | none |
| Driver-reported limits | target 83 C, max operating 92 C, slowdown 94 C, shutdown 97 C |
| Driver slowdown flags | hardware, thermal and power-brake slowdown all "Not Active" |
| CPU package | 39 C |
| Memory | 11.3 GB available of 15.9 GB; swap 0 of 20.4 GB used |
| Pressure | CPU and memory 0.00; IO 0.18 (10 s average) |
| Load average | 0.00 |
| Shared Ollama (:11434) | listening, no resident model |
| Isolated Ollama (:11435) | not running (unchanged since the reset) |
| Disk | 374 GB free on the experiment volume |
| Uptime | 2 h 41 min since the 15:09 reset; kernel log without warnings |

No user workload was on the GPU, so nothing could be evicted by loading the models. The launcher
re-checked the shared Ollama's resident-model list and the GPU's process list before every stage and
would have refused to start otherwise; it never had to.

## 3. Runtime and device compatibility

CUDA initialisation was run by itself first (stage A0): import, initialise, move a one-element tensor
to the GPU and back, synchronise, exit. It completed normally in 0.52 s (0.14 s in later processes),
PyTorch reported `NVIDIA GeForce RTX 3050`, compute capability 8.6, CUDA 12.4 build against the
driver's CUDA 13.0, and the GPU returned to 120 MiB afterwards. TF32 matrix multiplication was off
(the PyTorch default), so FP32 means true single precision.

CUDA was initialised in nine separate processes during this experiment, with a streaming `nvidia-smi`
monitor running throughout, and nothing abnormal happened. That makes the GPU driver a less likely
cause of the earlier reset, without excluding it.

## 4. Predeclared safety guards

Written to `.local/phase34-juno-gpu-nli-20261012/PREDECLARATION.md` before stage A0 and not changed
afterwards.

| Quantity | Warning | Abort |
|---|---|---|
| CPU package temperature | 85 C | 88 C |
| GPU temperature | 75 C | 80 C |
| Swap growth | -- | 500 MB |
| Host memory of the benchmark | -- | 6 GB, no swap |
| GPU memory of the benchmark | -- | half the card (about 4 GB) |
| Temperature monitoring lost or stale for 5 s | -- | abort |
| Wall time per process | -- | 120 s / 240 s / 600 s |

Enforcement was doubled: a sampler thread inside the benchmark (every 0.5 s, started before PyTorch
was imported) and an independent shell watchdog (every 1 s) able to kill the whole process scope.
Cooldown to 50 C (CPU) and 60 C (GPU) before each phase was part of the declared procedure.

**No guard fired and no warning was logged.** Highest readings anywhere: GPU 58 C, CPU 65 C. No
threshold was altered.

## 5. Smoke tests (stage A)

| | MiniLM | DeBERTa |
|---|---|---|
| Model on GPU (PyTorch allocated) | 315 MB | 705 MB |
| First pair, including one-time GPU library start-up | 1.18 s | 0.81 s |
| Score difference from frozen CPU reference, first pair | 4e-08 | 1e-07 |
| PyTorch memory after unload | 8 MB allocated, 20 MB reserved | same |
| GPU memory after the process exited | 120 MiB (baseline) | 120 MiB (baseline) |
| Peak CPU / GPU temperature | 56 C / 46 C | 55 C / 47 C |

Models were loaded one at a time, each in its own process.

## 6. Frozen scientific-score parity

Reference: the laptop CPU scores from the scientific bakeoff. Tolerance predeclared at 1e-3.

| Model, precision | Largest probability difference | Pairs over 1e-3 | Supported admitted | Negatives admitted | Decision flips |
|---|---|---|---|---|---|
| MiniLM FP32 (t = 0.90) | 6e-06 | 0 | 38 of 59 | 5 of 27 | 0 |
| DeBERTa FP32 (t = 0.50) | 8e-06 | 0 | 45 of 59 | 2 of 27 | 0 |
| DeBERTa FP32 (t = 0.90) | 8e-06 | 0 | 42 of 59 | 2 of 27 | 0 |

These hold at every batch size (1, 4, 8, 16), and the three repetitions of each configuration returned
identical numbers. The pairs closest to a threshold (MiniLM E034 0.9056, E065 0.8813, E088 0.8884;
DeBERTa E009 0.9073 against 0.90; none within 0.02 of DeBERTa's 0.50) are unchanged to four decimals.
The two central Q1 findings stay unrecovered on the GPU exactly as on the CPU: E083 scores 0.009
(MiniLM) and 0.024 (DeBERTa); E090 scores 0.063 and 0.008.

## 7. GPU FP32 performance (stage B)

99 pairs, one unmeasured warm pass, then three measured passes per batch size. Every boundary is
synchronised with `torch.cuda.synchronize()`. "End to end" is tokenisation + transfer to the GPU +
forward pass + copy back; "GPU forward" is the synchronised forward pass and softmax alone. One CPU
thread.

**MiniLM**

| Batch | End to end, ms/pair | Pairs/s | GPU forward, ms/pair | Tokenise, ms/pair | Per-call latency mean / median / p90, ms | Peak allocated / reserved, MB |
|---|---|---|---|---|---|---|
| 1 | 3.60 | 278 | 3.33 | 0.23 | 3.6 / 3.6 / 4.3 | 328 / 410 |
| 4 | 2.52 | 396 | 2.34 | 0.17 | 10.0 / 10.2 / 13.7 | 344 / 410 |
| 8 | 2.56 | 391 | 2.38 | 0.16 | 19.5 / 19.0 / 26.9 | 365 / 410 |
| 16 | 2.81 | 356 | 2.66 | 0.15 | 39.8 / 36.2 / 63.5 | 407 / 534 |

**DeBERTa-v3-base**

| Batch | End to end, ms/pair | Pairs/s | GPU forward, ms/pair | Tokenise, ms/pair | Per-call latency mean / median / p90, ms | Peak allocated / reserved, MB |
|---|---|---|---|---|---|---|
| 1 | 13.66 | 73 | 13.30 | 0.26 | 13.6 / 13.4 / 14.1 | 738 / 962 |
| 4 | 7.20 | 139 | 6.99 | 0.19 | 28.6 / 27.6 / 39.5 | 792 / 962 |
| 8 | 7.12 | 141 | 6.89 | 0.21 | 54.2 / 51.8 / 76.5 | 865 / 962 |
| 16 | 7.75 | 129 | 7.55 | 0.22 | 110.0 / 105.5 / 174.8 | 1,008 / 1,162 |

- Transfer to the GPU and copy back together cost under 0.1 ms per pair. End-to-end time is 93-97% GPU
  forward pass; pure GPU time and user-visible time are nearly the same here.
- At FP32 the card is saturated by batch 4. Batch 16 is slightly slower than batch 8 for both models,
  because pairs are padded to the longest in each batch and the input order was not sorted by length.
- DeBERTa costs 2.8 times MiniLM per pair, against 3.1 times on JUNO's CPU.

**Start-up, measured separately from warm inference** (fresh process each time):

| Step | MiniLM | DeBERTa |
|---|---|---|
| Import PyTorch (libraries in page cache) | 0.93 s | 0.93 s |
| Import PyTorch, first process of the session (libraries read from disk) | 7.6 s | -- |
| CUDA initialisation | 0.15 s | 0.15 s |
| Tokenizer load | 0.09-0.23 s | 0.16-0.25 s |
| Model load to host memory, file in page cache | 0.06-0.37 s | 0.22-0.40 s |
| Model transfer to GPU, file in page cache | 0.07 s | 0.13 s |
| First inference call | 0.12-1.18 s | 0.20-0.81 s |
| Model load + transfer, checkpoint file dropped from page cache (stage E) | 2.7 s | 3.2 s |

So a process that already has PyTorch imported needs roughly 0.5-2 s to make either model usable on
the GPU when the file is cached, and about 3 s more from JUNO's spinning disk when it is not. The
import of the `transformers` library was not timed on its own.

## 8. Optional FP16 (stage C)

Run because FP32 finished with the GPU under 60 C and under 1.4 GB. Batch 1 and 16 only.

| | MiniLM FP32 | MiniLM FP16 | DeBERTa FP32 | DeBERTa FP16 |
|---|---|---|---|---|
| Model on GPU | 315 MB | 161 MB | 705 MB | 359 MB |
| Batch 1, end to end ms/pair | 3.60 | 3.29 | 13.66 | 14.10 |
| Batch 16, end to end ms/pair | 2.81 | 0.99 | 7.75 | 3.13 |
| Peak allocated at batch 16 | 407 MB | 212 MB | 1,008 MB | 518 MB |
| Largest probability difference from reference | 6e-06 | 1.7e-03 | 8e-06 | 1.5e-03 |
| Pairs over the 1e-3 tolerance | 0 | 2-3 | 0 | 1 |
| Decision flips | 0 | 0 | 0 | 0 |
| Non-finite outputs | none | none | none | none |

FP16 halves memory and is 2.5-2.8 times faster at batch 16, with no gain at batch 1. It **exceeds the
predeclared 1e-3 tolerance** on one to three pairs per configuration, although no admission decision
changed on these 99 pairs and the admitted counts are identical. It is therefore not score-equivalent
to the reference and would need its own qualification before use; FP32 remains the scientific
reference. FP32 is already fast enough that FP16 is not needed for the verifier's cost to be negligible.

## 9. GPU versus CPU

Best tested batch size for each row. CPU rows are the preserved measurements, taken earlier the same
day under different conditions (CPU-only PyTorch build, cooldown pauses, temperature aborts on JUNO);
they were not rerun.

| Configuration | MiniLM, ms/pair | DeBERTa, ms/pair |
|---|---|---|
| Laptop CPU, 4 threads | 92 | 241 |
| JUNO CPU, 2 threads | 36 | 112 |
| JUNO GPU, FP32 | 2.5 | 7.1 |
| JUNO GPU, FP16 (batch 16) | 1.0 | 3.1 |

JUNO's GPU at FP32 is about 14 times (MiniLM) and 16 times (DeBERTa) faster than JUNO's CPU at two
threads, and about 35 times faster than the laptop. **DeBERTa on the GPU is five times faster than
MiniLM on JUNO's CPU.**

## 10. Memory, temperature and resource observations

| | MiniLM FP32 | DeBERTa FP32 | MiniLM FP16 | DeBERTa FP16 |
|---|---|---|---|---|
| GPU memory of the process, batch up to 8 (`nvidia-smi`, baseline removed) | 519 MiB | 1,071 MiB | 337 MiB | 595 MiB |
| GPU memory of the process, batch 16 | 643 MiB | 1,271 MiB | 353 MiB | 697 MiB |
| Peak GPU temperature | 58 C | 56 C | 46 C | 49 C |
| Peak CPU package temperature | 57 C | 60 C | 61 C | 65 C |
| Peak GPU utilisation sampled | 93% | 98% | 35% | 34% |
| Host memory of the process (peak resident) | 1.0 GB | 1.5 GB | 1.2 GB | 1.4 GB |
| Lowest system memory available | 10.5 GB | 9.9 GB | 10.3 GB | 10.1 GB |
| Swap growth | 0 | 0 | 0 | 0 |

- The CUDA context itself takes about 100 MiB; the rest is weights plus working memory.
- Host memory is about the same as on the CPU path, so the GPU path does not save system RAM.
- The CPU peaks fell in the import, load and pause phases; during measured passes the package read
  52-57 C. The CPU problem that ended the CPU bakeoff (81-88 C under one to four threads) does not
  arise here because each CPU burst lasts about a second.
- Cooldown waits were 0-3 s, with one of 20 s. The GPU fan went from 0% to 32%.
- Kernel log after the runs: no NVRM/Xid message, no machine-check, no thermal-throttle event
  (throttle counters 0). Uptime continuous since 15:09. GPU back to 120 MiB and 34 C.
- No power draw is available from this card's driver interface.

## 11. Expected Ask verification latency

Projections from the measured warm rates above, not measured Ask runs. They assume the model is
already resident.

| Workload | MiniLM, JUNO GPU FP32 | DeBERTa, JUNO GPU FP32 | DeBERTa, JUNO CPU 2 threads | DeBERTa, laptop CPU 4 threads |
|---|---|---|---|---|
| Q1, 9 comparisons | 0.02 s | 0.06 s | 1.0 s | 2.2 s |
| Q3, 20 comparisons | 0.05 s | 0.14 s | 2.2 s | 4.8 s |
| 230 comparisons | 0.6 s | 1.6 s | 26 s | 55 s |

Q1 and Q3 took about 389 s and 348 s in the live pilot, almost all of it generative inference. The
verifier was already under half a percent of that on the CPU. **GPU verification does not shorten
those multi-minute answers.** What it changes is the large-batch case (230 comparisons: 26-55 s down to
under 2 s) and the verifier's share of CPU heat on a machine like JUNO.

If the model is not resident, add the start-up in section 7. For a nine-pair job, loading a model onto
the GPU costs more than running the job on a CPU model that is already loaded.

These numbers describe a verifier running on JUNO. Callosum's reviewed verifier runs inside the desktop
application on the user's machine. Running it on JUNO instead would need a new service boundary that
does not exist and was not built; running it on a user's own GPU depends on that user's hardware and
on the packaged runtime (section 13).

## 12. GPU and Ollama coexistence (observation and arithmetic only)

No Qwen workload was launched, the isolated Ollama was not started, and nothing was sent to the shared
Ollama except its read-only resident-model listing (eleven requests).

Preserved evidence from the live pilot (isolated Ollama, same card, at that pilot's context settings):

| Generator | Resident size | On the GPU |
|---|---|---|
| qwen3.5:9b | 5.77 GB | 5.77 GB (entirely) |
| phi4:14b | 11.8 GB | 6.88 GB (partly; the rest in system RAM) |
| gemma3:12b | 8.96 GB | 5.31 GB (partly; the rest in system RAM) |

- **Qwen3.5-9B does use the GPU, fully**, at about 5,500 MiB. With Xorg's 120 MiB that leaves roughly
  2,570 MiB.
- DeBERTa FP32 needs 1,071-1,271 MiB and MiniLM 519-643 MiB. **On paper either verifier fits beside a
  resident Qwen3.5-9B with over 1 GB to spare.** This was not tested.
- It does not fit beside phi4:14b or gemma3:12b without cost: those are already split between the GPU and system RAM, and
  Ollama sizes its GPU share from the memory free at load time. A resident verifier would push more of
  such a model onto the CPU, which slows generation, the dominant cost. Loading the verifier after
  such a model is resident could fail to allocate.
- Memory fitting says nothing about speed when both run at once. The two would share one GPU's compute,
  and the Ask pipeline as run so far verifies after generating, not during it.
- Practical reading: with Qwen as the generator, simultaneous residency looks feasible; with larger
  generators the verifier should be sequenced (load, verify, unload, about 0.5-2 s of overhead) or left
  on the CPU so the GPU stays reserved for generation.

A brief controlled coexistence run is worth doing only if verification on JUNO becomes a real design
option. It is not needed to decide anything about the desktop application.

## 13. GPU-first, CPU-fallback: recommendation

**GPU-first is a reasonable default orientation**, as a preference that is checked at run time and not
as a requirement. On this card the verifier is 14-35 times faster than on the CPUs measured, gives the
same scores at FP32, and runs cool.

Recommended shape of a future policy (nothing implemented here):

- **Prefer a GPU** when a supported backend is present, initialisation succeeds, and free GPU memory
  exceeds the model's measured need plus a margin (measured need here: about 0.65 GB MiniLM, 1.3 GB
  DeBERTa at FP32, batch 16).
- **Fall back to the CPU** when: no compatible GPU or runtime exists; free GPU memory is below the
  need; a generative model is using or about to need the memory, since generation is the dominant cost
  and should keep the GPU; initialisation or a first call fails (fall back once, record why, do not
  retry in a loop); or the job is small and the GPU model is not already loaded while a CPU model is.
- **Keep the scientific contract device-independent.** FP32 on both devices gave identical decisions
  here. Any reduced-precision or compiled variant is a different verifier for qualification purposes.
- **Record the device** used for each verification, so results stay inspectable.
- **Batch moderately.** Batch 4-8 was the plateau at FP32; larger batches only added padding and memory.
- **Backends differ by platform.** CUDA is one case. Apple Silicon (Metal), Windows machines with AMD
  or Intel GPUs, and Linux without NVIDIA drivers would each need their own check and their own parity
  test. Only CUDA on one card was measured here.

Two constraints from the project's own briefing that bear on this (not re-verified in code for this
report): the packaged desktop application ships a CPU-only PyTorch to limit size, so GPU-first on the
desktop is first a packaging question. The CUDA environment used here is 5.5 GB against 1.1 GB for the
CPU-only one. And the application's model registry already keys runtimes by device, and its managed
local generator already claims GPU memory on a user's machine, so the "generation has priority" rule
applies on the desktop as well as on JUNO.

## 14. Limitations and incomplete measurements

- One card, one driver, one day. Each measured pass lasted 0.1-1.4 s and the whole GPU load lasted
  under a minute per model. **Sustained-load thermal behaviour was not measured.**
- Coexistence with a resident generator is arithmetic from preserved sizes, not a measurement.
- CPU and GPU rows were measured under different conditions and builds; the ratios are large enough
  that this does not change the reading.
- FP16 was tested at two batch sizes only.
- GPU utilisation comes from a 250 ms `nvidia-smi` stream and is coarse for passes this short; the
  per-phase temperature attribution in the raw samples is approximate for the same reason.
- Disk-cold load dropped one checkpoint file from the page cache per model; libraries and tokenizer
  files stayed cached. JUNO's disk is not representative of a user's machine.
- The 99 pairs and their labels are unchanged: one blinded model adjudication, not human validation.
- The cause of the earlier reset remains unknown. Six CPU threads has still never been rerun.
- Operational notes: passwordless sudo was used once, read-only, to read the kernel log. Preserved
  artifacts: 227 files hashed before and after, 0 changed.

## 15. Recommended next step

- **No further hardware benchmark is needed to choose between the two models.** Cost does not separate
  them on a GPU, and did not on the CPUs either.
- The open question is scientific: independent labels and natural negative controls for DeBERTa, plus
  the Q1 quantitative findings that neither model admits.
- For architecture, decide first where verification is meant to run. If on the user's desktop, the next
  work is a packaging and backend-detection study, not another JUNO run. If on JUNO, one short
  coexistence run with Qwen resident would be the remaining measurement.
- JUNO's CPU cooling is still worth Cody's attention independently of this result.

Raw logs, scripts, the predeclaration and the analysis are in
`.local/phase34-juno-gpu-nli-20261012/` (gitignored).
