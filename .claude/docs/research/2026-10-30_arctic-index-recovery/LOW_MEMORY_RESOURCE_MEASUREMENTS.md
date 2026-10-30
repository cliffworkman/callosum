# Low-memory resource measurements (inc 610)

Machine: Windows 11 Pro, 16,197 MB physical RAM, commit limit 26,437 MB (`GlobalMemoryStatusEx`). The machine
stayed busy throughout (Codex and other sessions); free physical memory was about 4.6–5.7 GB the whole time. All
numbers below were measured on this machine. None is assumed.

## Policy applied on this machine

`ResourcePolicy.for_machine(16,197 MB)`: reserve **809 MB**, pause **606 MB**, stop **404 MB**. Start floor =
worker need (observed peak, else 1,200 MB) + reserve ≈ **2.0 GB** before the first run and **1.4 GB** once a
629 MB peak was observed. "Free" = min(available physical, available commit). Available commit stayed about 2×
available physical, so physical memory was the binding measure in this run. The floors were never reached:
`waiting_resources` was not triggered for real (it is covered by tests 4–6 in `ARCTIC_FAILURE_AND_RETRY_TESTS.md`).

## Real Arctic S worker (controlled continuation)

| Segment | Passages | Batch | Throughput | Worker RSS max / median | Free physical min–max | Free commit min–max |
|---|---|---|---|---|---|---|
| pre-refactor code | 25,453 → 28,821 | 8 then 4 | 9.0 /s (8), 14.3 /s (4) | 629 / 590 MB | 4,881–5,563 MB | 9,845–10,678 MB |
| final code | 28,857 → 42,044 | 4 then 2 | 12.2 /s (4), 13.0 /s (2) | 616 / 584 MB | 4,611–5,688 MB | 9,541–10,693 MB |

The recorded peak worker RSS is 629 MB, and the minimum free memory the supervisor recorded was 4,593 MB. Batch
shrinking happened only because of the deliberate kills (an unexplained kill halves the batch, conservatively).
Throughput did not suffer: batches of 2–4 ran *faster* than 8 here, and faster than the previous per-paper encode
(about 9.6 passages/s). Small batches pad less, because each forward pass pads to its own longest passage rather than
the longest in a whole paper. Treat this as an observation on this CPU and corpus, not a general law. The 8-batch
segment was short (about 40 s, including model load).

The full continuation of 16,591 passages took about 23 minutes of indexing time (wall clock, excluding the gap
while the driver was stopped for the code change).

## Variable-batch parity and memory (real checkpoint, 24 stored chunks, shortest to longest)

| Batch | Encode time | RSS after | Max abs diff vs stored | Min cosine vs stored |
|---|---|---|---|---|
| 1 | 23.1 s incl. model load | 501 MB | ≤ 9.87e-8 | ≥ 0.99999988 |
| 8 | 3.56 s | 702 MB | 9.87e-8 | 0.99999988 |
| 32 | 7.75 s | 899 MB | 9.87e-8 | 1.0 |

Batch 1 vs 32: 1.06e-7; batch 8 vs 32: 6.7e-8. Dimension 384, norms 1 ± 1.2e-7. Peak process RSS 962 MB, with three
model loads in one process (the guard measured a 899 MB peak for the tree). Memory grows with batch size, roughly
6 MB per extra passage at 512 tokens here. That is why halving the batch is the right first response to memory
pressure, and why one passage per batch (about 500 MB with the model loaded) is the honest floor below which the
build reports `insufficient_memory` instead of retrying.

## What this implies for an ordinary 16 GB laptop

- Minimum practical headroom is about 0.5 GB for the worker at batch 1, plus the reserve (809 MB on 16 GB). Below
  roughly 1.3 GB free, the build waits rather than starting.
- The old guard approximated commit as RAM+swap. On this machine the real commit limit (26.4 GB) and available
  commit (about 10 GB) come straight from the OS, so the policy reacts to true commit pressure, not a guess.
- The previous interruptions were not OS memory exhaustion (no event 2004, no crash events). They were external
  termination of the host shell, which is exactly the case reconciliation now covers.

Raw data: `C:\Users\cliff\callosum-data\experiments\arctic-continuation-20261030\` (`samples.jsonl`,
`samples_final.jsonl`, `samples_summary.json`, `parity_guard.log`, `parity_guard.json`).
