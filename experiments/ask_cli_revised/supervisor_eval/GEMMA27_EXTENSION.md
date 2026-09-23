# Ask 0.7 supervisor bakeoff — Gemma3:27B tier-up extension

**This is a post-hoc, predeclared same-family scale extension, run after the first tranche's results were observed.**
`gemma3:27b` was **not** part of the original candidate set. The first-tranche result is unchanged and stands on its own:
[`REPORT.md`](REPORT.md) — *four candidates, none qualified*. Nothing here edits it, its receipts, its freeze or its registry.

- Frozen inputs (unchanged): freeze commit `3d12610d`, `freeze_sha256 5848f8c4…697e`, battery manifest `370ea09c…1985`, private
  battery `037806d3…e4fd`; first-tranche results commit `87e3d7c3`. `build_battery verify` → "freeze intact" before, during and after.
- Same battery, prompts, schemas, expected judgments, gates, scorer and **envelope** as `gemma3:12b` (`num_ctx 12288`,
  `num_predict 4096`, temperature 0, seed 42, schema-constrained output, no thinking channel, one observation per case, no retries,
  frozen watchdogs). Nothing was widened because the model is larger: this is a **scale** test, not an execution-policy test.
- The candidate lives in `extension.py`, outside `models.CANDIDATES` and outside the frozen code, so the original four never read as if
  27B took part prospectively. Date 2026-09-23. Receipt: `receipts/gemma3-27b.json` (text-free).

## 1. Bottom line — three separate results

| | Result |
|---|---|
| **Semantic** | **No improvement on either 12B failure; two new regressions.** A3 (generic dmPFC → s2) still fails on all three orderings, and the coverage audit still attaches p5 → s3 in both orderings. Order-robustness (G5) newly fails and the generic mentalizing claim (A4) newly maps to s2. Recall (9/9) and recovery (2/2) are preserved. Global flag: **not qualified** (G4, G5, G6 fail). |
| **Operational** | Completes the frozen battery (19/19, `done_reason=stop`, no retries, no timeouts) but at **31% GPU residency**, **2.3 tok/s**, **23.8 min** battery (×5.4 vs 12B) and a **5.1 GB peak swap**. No OOM kill; JUNO services stayed active. |
| **E2E implication** | **`gemma3:27b` earns no jurisdiction that `gemma3:12b` does not already hold**, at ~5× the cost and with a worse semantic profile. Do not carry it into the E2E pool as a supervisor. |

Reading the capability-level delta (primary) against the fixed interpretation rules: **both** 12B failures reproduced **plus** new
regressions → "report the trade". It is also the strongest available evidence that, within this range, **scale alone does not fix
Gemma's nearest-category / wrong-obligation pattern**.

## 2. Answers to the seven handoff questions

1. **Claim-level precision improved?** No. A3 → s2 on all three orderings (rotated also adds s1); A4 mentalizing, correct on 12B, now maps to s2. Generic-negative rejection 2/5 → **1/5**.
2. **Whole-ledger coverage improved?** No. p5 → s3 in both orderings again; p2 → s3 in both (12B: reversed only); p6 → s5 added in the original order. Coverage 0/2 → 0/2, with broader over-attachment.
3. **Positive recall preserved?** Yes at the gate: A1/A2/A7 9/9. But selections are broader (s2 added on all three A1 calls and on A2.original), which is what breaks G5.
4. **Recovery preserved?** Yes, 2/2 (G7 pass). Its original-menu plan also closes s1/s2 with p3/p4, which the gate permits and 12B did not do.
5. **Measured JUNO cost?** See §7: 31% GPU-resident (62% for 12B), 162 s cold load, 40.9 s median warm call (8.6 s), 2.3 tok/s generation (9.2), 23.8 min battery (4.4), 5.1 GB peak swap (0.18).
6. **Earns E2E inclusion?** No.
7. **For which roles?** None over 12B (§9).

## 3. Identity (runtime-observed, not documentation)

From `/api/show`, `/api/tags` and measured residency: family `gemma3`, **27.4B** parameters, **Q4_K_M**, context capability 131,072,
capabilities `completion, vision` (no thinking), license head "Gemma Terms of Use" (a separate deployment decision; it did not affect
the test). Artifact digest `a418f583…2203`, **17,396,936,941 bytes** on disk; **18.47 GB** in memory at the 12,288 context, of which
**5.73 GB (31%)** is in VRAM. (A pre-run registry estimate of ~17.4 GB was used only for the store-headroom check and is not model
metadata.) Runtime identical to the first tranche: isolated Ollama v0.34.3 (binary sha256 `825106b5…`), CUDA, driver 580.178.04,
store `/media/brain/JUNO/ollama-models/ask-070-bakeoff`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`. Pre-run baseline:
GPU idle (61 MiB), no compute apps, shared Ollama empty.

## 4. Stage 0 (same neutral procedure as 12B): `ok`

Enum enforcement held; padded 7,926-token call in band, `ok`, 66.0 s (154 tok/s prompt eval); compact trials valid JSON; cold load
162.4 s (12B: 56.8 s). Nothing eliminated it, and nothing about it was accommodated.

## 5. Gates: Gemma3:12B → Gemma3:27B

| Gate | 12B | 27B |
|---|---|---|
| G1 mechanical | PASS | PASS |
| G2 ids | PASS | PASS |
| G3 positives | PASS | PASS |
| G4 negatives | FAIL | FAIL |
| G5 order-robustness | PASS | **FAIL** |
| G6 coverage | FAIL | FAIL |
| G7 recovery | PASS | PASS |
| G8 absence wording | PASS | PASS |
| **Qualified** | no | no |

## 6. Per-case matrix (✓ pass · ✗ fail · · diagnostic; selected obligations after →)

| Case (original / reversed / rotated) | 12B | 27B |
|---|---|---|
| A1 attitudes → s1 | ✓→s1 ✓→s1 ✓→s1 | ✓→s1,s2 ✓→s1,s2 ✓→s1,s2 |
| A2 cross-cultural → s4 | ✓→s4 ✓→s4 ✓→s4 | ✓→s4,s2 ✓→s4 ✓→s4 |
| A7 EBQ → s3 | ✓→s3 ✓→s3 ✓→s3 | ✓→s3 ✓→s3 ✓→s3 |
| A3 generic dmPFC → none | ✗→s2 ✗→s2 ✗→s2 | ✗→s2 ✗→s2 ✗→s1,s2 |
| A4 generic mentalizing → none | ✓ | **✗→s2** |
| A5 years-of-school → none | ✓ | ✓ |
| A6 diagnostic | ·→s2 | ·→s2 |
| B coverage (original / reversed) | ✗ p5→s3 · ✗ p1,p2,p5→s3 | ✗ p2,p5→s3, p6→s5 · ✗ p2,p5→s3 |
| C recovery (original / reversed) | ✓ ✓ | ✓ ✓ |

## 7. Capability-level delta (the primary reading)

| Capability | Gemma12 | Gemma27 | Delta |
|---|---|---|---|
| clear-positive recall (G3; A1/A2/A7, 9 calls) | 9/9, tight (s1 / s4 / s3 only) | 9/9, broader (extra s2 on 4 calls) | **preserved**; selections less exact |
| generic-negative rejection (G4; A3×3, A4, A5) | 2/5 (A3 → s2 ×3) | 1/5 (A3 → s2 ×3; A4 → s2) | **not improved; slightly worse** |
| order robustness (G5) | PASS | FAIL (A2, A3 selections change with order) | **regression** |
| whole-ledger coverage (G6; B ×2) | 0/2 | 0/2, wider (p6 → s5 added, p2 → s3 in both) | **not improved** |
| bounded recovery (G7; C ×2) | 2/2 | 2/2 | **preserved** |
| schema / id discipline (G1, G2) | PASS / PASS | PASS / PASS; 19/19 complete, 0 invented ids | **preserved** |
| operational completion | 19/19 in 4.4 min | 19/19 in 23.8 min, 31% GPU, 5.1 GB peak swap | completes; **×5.4 wall** |

Predeclared reading (fixed before any 27B observation): A3 still fails **and** Task B still fails **and** new regressions appeared →
*reproduces both failures; report the trade explicitly.* Improvement on either dimension would have counted even with the other
broken; neither improved.

## 8. Operational result: what 27B costs on JUNO (measured, same warm-process method as the first tranche)

| Metric | 12B | 27B |
|---|---|---|
| GPU-resident / VRAM-resident | 62% / 5.58 GB | **31%** / 5.73 GB |
| In memory (weights + cache) | 8.97 GB | **18.47 GB** |
| Cold load (Stage 0) / first battery call load | 56.8 s / 6.1 s | **162.4 s / 140.3 s** |
| Warm call wall, median (min–max) | 8.6 s (6.1–40.4) | **40.9 s (33.2–203.3)** |
| Generation tok/s, median | 9.2 | **2.3** |
| Prompt-eval tok/s, median (min–max) | 437 (396–458) | 132 (**16**–135) |
| Generated tokens (19 calls) | 1,953 | 2,180 |
| Battery wall | 4.4 min | **23.8 min** (×5.4) |
| Peak VRAM, whole GPU (MiB) | 6,920 | 6,746 |
| Peak RAM used / min RAM available (MiB) | 7,100 / 8,802 | 5,737 / 10,165 |
| Peak swap (MiB) | 180 | **5,068** |

- VRAM is essentially the same; the extra ~9.5 GB lives in system memory, which is why throughput drops ~4×.
- **Memory-state sensitivity.** The ~500-token A prompts ran steadily (~131 tok/s prompt eval, swap flat near 1.4 GB). On the four longer
  1.1k–1.8k-token B/C calls, prompt-eval fell to 16–44 tok/s while swap grew from ~1.4 GB to ~5.1 GB (RAM available stayed ≥ 10 GB). The
  earlier 7.9k-token Stage-0 call ran at 154 tok/s at ~1.3 GB swap, so the slowdown tracks memory state during those calls rather than
  prompt length alone; the cause is not isolated. Latency on this host is therefore both slow and unpredictable.
- **Host impact.** No OOM kill; plex/jellyfin/docker active after the run; swap 1.33 GB after unload (0.73–0.80 GB before); GPU and both Ollama
  instances idle again. Which processes' pages were swapped is not attributed.

## 9. E2E implications and roles

- **Semantics:** 27B has no stage where it beats 12B on the measured cases: equal on recall and recovery, worse on order-robustness and
  generic-negative rejection, equal-and-broader on coverage. **No role over `gemma3:12b`.**
- **Cost:** ×5.4 battery wall, ×4.8 warm-call latency, ~¼ the generation speed, multi-GB swap. "Rare supervisory stage" does not rescue it here: there is
  no measured semantic advantage to buy with that cost.
- **If a Gemma representative is wanted in the E2E pool,** it is `gemma3:12b` for recall/recovery-type roles (positive claim → obligation
  mapping; bounded recovery-plan choice), with claim-level discrimination and whole-ledger coverage assigned elsewhere.
- **First-tranche context, not new evidence:** the recorded results already show complementary strengths across *families* (`gemma3:12b` recall +
  recovery; `gpt-oss:20b` and `qwen3.5:9b`'s completed calls generic-negative rejection; `phi4:14b` coverage audit). This extension finds no
  Gemma-*scale* route to the capabilities Gemma is missing; that pattern is more consistent with a family/framing trait (nearest-category
  and "which scales?" attraction) than a capacity shortfall in this range.

## 10. Limits

Single draw per case at temperature 0; small n (A2/A4 differences from 12B may be single-draw noise, but the A3 and p5 → s3 failures reproduced
across every ordering). Scale is the intended difference, not a perfectly isolated one (runtime residency, memory pressure and throughput also
differ). The s2 label-sensitivity note in `REPORT.md` applies here too and does not change this result: A3.rotated adds s1, and the coverage
failures are s3/s5, not s2. Not tested: any envelope change, larger models, Qwen's reasoning budget (a separate execution-policy question), or E2E.

## 11. Reproduce

```powershell
python -m experiments.ask_cli_revised.supervisor_eval.build_battery verify        # "freeze intact"
python -m experiments.ask_cli_revised.supervisor_eval.run_eval pull   gemma3-27b
python -m experiments.ask_cli_revised.supervisor_eval.run_eval stage0 gemma3-27b
python -m experiments.ask_cli_revised.supervisor_eval.run_eval battery gemma3-27b
python -m experiments.ask_cli_revised.supervisor_eval.run_eval score  gemma3-27b
python -m experiments.ask_cli_revised.supervisor_eval.run_eval report-extension   # writes receipts/gemma3-27b.json only
```

Private (gitignored, `.local/ask-070-supervisor-bakeoff/gemma3-27b/`): raw outputs, Stage-0 detail, resource CSV. The model remains in the
isolated store.
