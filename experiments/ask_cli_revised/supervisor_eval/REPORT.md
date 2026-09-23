# Ask 0.7 supervisor bakeoff — first tranche: **no candidate qualified**

Date: 2026-09-23. All four frozen candidates ran the frozen 19-call battery once each, on CUDA, under one
uniform envelope. **No candidate cleared all hard gates**, so there is no winner and no performance ranking
(performance is reported descriptively in §7). This report replaces the earlier "paused before any scored
observation" interim; every "no candidate has been run" caveat in it is superseded.

## 1. Bottom line

| Candidate | G1 mech | G2 ids | G3 positives | G4 negatives | G5 order | G6 coverage | G7 recovery | G8 absence | **Qualified** |
|---|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | **FAIL** | PASS | **FAIL** | PASS | **FAIL** | **FAIL** | **FAIL** | PASS | **no** |
| `gemma3:12b` | PASS | PASS | PASS | **FAIL** | PASS | **FAIL** | PASS | PASS | **no** |
| `phi4:14b` | PASS | PASS | **FAIL** | **FAIL** | **FAIL** | PASS | **FAIL** | PASS | **no** |
| `gpt-oss:20b` | PASS | PASS | **FAIL** | PASS | PASS | **FAIL** | PASS | PASS | **no** |

- **Recommendation: none qualified.** Do not promote any of the four to supervisor. Section 8 states which
  capability failed and whether the evidence supports moving up one tier. Nothing larger was run.
- No candidate passes both G3 (recall on clear positives) and G4 (silence on generic neuroscience). The four
  fail in *opposite directions*: `gemma3:12b` recalls every positive but maps dmPFC to a nearby obligation;
  `gpt-oss:20b` refuses the dmPFC trap but returns nothing for two clear positives.
- Discipline held: one observation per case (19/19 per model, attempt 1, no technical retries), frozen files
  byte-identical to the freeze commit (`build_battery verify` → "freeze intact"), no Vulkan-backend result
  is used anywhere, and the battery, prompts, schemas, gates, envelope and candidate list were not changed.

## 2. Candidate identities (from Ollama `/api/show`)

| Tag | Family | Params | Quant | Ctx cap | Capabilities | License (head) | Reasoning setting used |
|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | qwen35 | 9.7B | Q4_K_M | 262,144 | completion, vision, tools, thinking | Apache | `think: true` (default) |
| `gemma3:12b` | gemma3 | 12.2B | Q4_K_M | 131,072 | completion, vision | **Gemma Terms of Use** (not OSI) | n/a (no thinking capability) |
| `phi4:14b` | phi3 | 14.7B | Q4_K_M | 16,384 | completion | Microsoft (license text head only; terms not otherwise verified here) | n/a |
| `gpt-oss:20b` | gptoss | 20.9B (MoE) | MXFP4 | 131,072 | completion, tools, thinking | Apache | `think: "medium"` (default) |

Distribution note for Callosum (AGPL): the Gemma Terms of Use carry use restrictions that flow downstream. If a
Gemma-family model ever becomes a finalist, licensing is a maintainer decision before it is a technical one.

## 3. Stage 0 — runtime and hardware (measured)

**Runtime (identical for all four):** isolated user-level Ollama **v0.34.3** on JUNO (upstream release tarball,
sha256 verified; binary sha256 `825106b5…bcca`), `127.0.0.1:11435`, store
`/media/brain/JUNO/ollama-models/ask-070-bakeoff`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`.
**GPU backend: CUDA** (`library=CUDA compute=8.6 name=CUDA0 libdirs=ollama,cuda_v13 driver=13.0`, read from the
server's own log; the harness refuses to run any pull/stage0/battery unless the live log says CUDA). NVIDIA
driver **580.178.04** (open kernel modules). RTX 3050 8 GB (Ollama sees 7.7 GiB total / 7.5 GiB free),
i7-8700, 15.9 GB RAM, Debian 12.15. The shared Ollama (0.12.3, port 11434) and its four models were untouched.

**Infrastructure change (approved by Cliff, receipt `receipts/infrastructure.json`):** driver 535.309.01
(Debian, proprietary DKMS) → 580.178.04 (NVIDIA repo, R580 LTS, open modules, branch-pinned) + reboot, because
current Ollama needs driver ≥ 550 for CUDA and otherwise falls back to Vulkan, which was ruled out. This
removed 13 Debian CUDA-11.8 *developer-toolkit* packages (`nvidia-cuda-toolkit`/`nvcc`, `nvidia-cuda-dev`, 11
`libnpp*`) that conflict with NVIDIA's packaging; they were deliberately **not** restored. Apt transaction: 17
installed, 33 upgraded, 26 removed; OS disk free 7.6 → 9.8 GB. A CUDA smoke test on a non-candidate model ran
before any candidate was pulled.

**Stage-0 outcomes (uniform 12,288-token context, temperature 0, seed 42; neutral ask_070 fixtures):**

| Candidate | Verdict | Enum enforced under reasoning | Padded call (target ≈ 8,064) | GPU-resident | Weights in memory | Cold load |
|---|---|---|---|---|---|---|
| `qwen3.5:9b` | ok | yes | 7,924 tokens, in band | **100%** | 5.77 GB | 65.5 s |
| `gemma3:12b` | ok | yes | 7,926 tokens, in band | 62% | 8.97 GB | 56.8 s |
| `phi4:14b` | ok | yes | 7,961 tokens, in band | 58% | 11.83 GB | 60.5 s |
| `gpt-oss:20b` | ok | yes | 7,949 tokens, in band | 47% | 14.06 GB | 96.1 s |

No candidate was eliminated at Stage 0 (no load/OOM failure, every compact trial produced valid JSON, no
timeouts). Two observations that predicted Stage-1 outcomes and were recorded rather than acted on:
`qwen3.5:9b` spent **1,599 thinking tokens on a 99-token prompt**, and its padded call ran to the 4,096-token
cap with invalid JSON; the padded call still proved the 12,288 allocation (its purpose), and verbosity alone is
not a Stage-0 elimination rule.

## 4. The frozen battery (unchanged since the freeze commit `3d12610d`)

19 calls per model, built from the real run9 artifacts (question `q_aib`, six real obligations `s1-o1…s6-o1`,
the real verified ledger `p1…p6`). Every prompt shows the user's original request. Public files hold claim/
obligation text, expected judgments and hashes; verbatim source quotes, rendered prompts and raw outputs stay in
gitignored `.local/`.

- **Task A — claim → obligation (15 calls):** A1 attitudes → s1; A2 cross-cultural → s4; A7 "EBQ measures explicit
  bias" → s3; **A3 dmPFC, A4 mentalizing, A5 years-of-school → no obligation**; A6 diagnostic. A1/A2/A3/A7 each in
  three orderings (original / reversed / rotate-by-3).
- **Task B — coverage audit (2 calls):** p3 supports s1; p5/p6 support nothing; p1/p2 not on s3–s6; s4/s6 stay
  unresolved. Original and reversed proposition order.
- **Task C — bounded recovery (2 calls):** s4 → NOMINATE; s5 → PRESERVE_UNRESOLVED; no closure on s3–s6; no repeat of
  an already-performed action on s3–s5. Original and reversed menu. (s4's state is a disclosed reconstruction.)
- **Gates G1–G8, no weighted score;** G8 flags corpus-absence wording for human adjudication (0 hits for all four,
  so no adjudication was needed).

## 5. Per-candidate results by family

✓ pass · ✗ semantic fail · ⊘ unusable (output hit the 4,096-token cap; not retried). Orderings are original /
reversed / rotated; B and C are original / reversed.

| Case | `qwen3.5:9b` | `gemma3:12b` | `phi4:14b` | `gpt-oss:20b` |
|---|---|---|---|---|
| A1 attitudes → s1 | ⊘ ✗ ✗ | ✓ ✓ ✓ | ✓ ✗ ✓ | ✗ ✗ ✗ |
| A2 cross-cultural → s4 | ✓ ✓ ✓ | ✓ ✓ ✓ | ✓ ✓ ✓ | ✓ ✓ ✓ |
| A7 EBQ → s3 | ⊘ ⊘ ✓ | ✓ ✓ ✓ | ✓ ✓ ✗ | ✗ ✗ ✗ |
| A3 dmPFC → none | ✓ ✓ ✓ | ✗ ✗ ✗ (→ s2) | ✗ ✗ ✗ (→ s2; rotated also s1) | ✓ ✓ ✓ |
| A4 mentalizing → none | ✓ | ✓ | ✓ | ✓ |
| A5 years-of-school → none | ✓ | ✓ | ✓ | ✓ |
| B coverage audit | ⊘ ⊘ | ✗ ✗ (p5 → s3; reversed also p1, p2 → s3) | ✓ ✓ | ✗ ✗ (p5, p6 → s2) |
| C recovery | ⊘ ⊘ | ✓ ✓ | ✓ ✗ (reversed menu closed s3 with `MARK_COVERED:p2`) | ✓ ✓ |

Family summaries:

- **A2 and A4/A5 are solved at this tier** (all four, every call). Lexically obvious positives and generic-topic
  negatives are not what separates these models.
- **A3 (dmPFC) is the discriminator.** `gemma3:12b` and `phi4:14b` pick the nearest-category obligation (s2, brain
  areas ↔ behavior) on every ordering; `qwen3.5:9b` and `gpt-oss:20b` correctly select nothing.
- **A1/A7 recall separates the models the other way.** Only `gemma3:12b` recalls all six. `gpt-oss:20b` returns an
  empty selection for both required positives on *all six* calls (stable, not order noise). `phi4:14b` misses
  one ordering each of A1 and A7. `qwen3.5:9b`'s two *completed* A1 calls both returned `[]`.
- **Task B:** only `phi4:14b` passes both orderings. `gemma3:12b` attaches the dmPFC proposition to "which scales"
  (s3) — the exact "valid science, wrong obligation" error the battery exists to catch — and `gpt-oss:20b` attaches
  both p5 and p6 to s2.
- **Task C:** `gemma3:12b` and `gpt-oss:20b` pass both menus; `phi4:14b` is menu-order sensitive.
- **G2 (invented ids) passed everywhere** — enum-constrained ids held, including under reasoning.

## 6. What failed, per candidate

- **`qwen3.5:9b`** — **7 of 19 calls ran into the 4,096-token cap while thinking** (A1.original, A7.original,
  A7.reversed, both B, both C) → G1 fails and G6/G7 are unevaluable (those gates fail because their only cases are
  unusable, not because a wrong answer was observed). Its 12 completed calls contain the cleanest negative behavior
  in the tranche (A3/A4/A5 all correct) but two genuine recall misses on A1, so G3/G5 fail on completed output too.
  Lifting the cap alone would therefore not be expected to qualify it.
- **`gemma3:12b`** — perfect recall (A1/A2/A7) and recovery, but a stable nearest-category false positive on dmPFC
  (G4) and a coverage audit that attaches valid-but-off-topic propositions (G6).
- **`phi4:14b`** — order-dependent recall (G3/G5), the same dmPFC → s2 error, and a menu-order-dependent closure of
  s3 (G7). Passes the coverage audit.
- **`gpt-oss:20b`** — conservative to the point of missing the clearest positives (G3), and over-attaches p5/p6 in the
  coverage audit (G6). Passes negatives, order-robustness and recovery.

**Label-sensitivity note (descriptive, not a re-score; the frozen gates stand).** Three different families
place dmPFC/mentalizing on s2 ("specific brain areas ↔ behaviors/attitudes") at least once, and s2 is the nearest
real category. The gate follows Cliff's label (generic neuroscience maps to no obligation). Reading the receipts
under a hypothetical tolerance for s2 on A3/B changes **no** qualification outcome: `gemma3:12b` still fails G6
(p5 → s3), `phi4:14b` still fails G3/G5/G7, `gpt-oss:20b` still fails G3, and `qwen3.5:9b` still fails G1. The
"nothing qualifies" conclusion does not depend on how strict that one label is.

## 7. Performance — descriptive only (no survivors, so no selection among survivors)

Measured from each battery's own warm calls in one warm process, one model at a time (`num_thread 6`,
`num_batch 512`, `num_ctx 12288`); first-call load reported separately. Not a ranking: none of these models
cleared semantic trust, which is the prerequisite for latency to matter.

| | GPU-resident | Battery wall | Warm latency med (min–max) | tok/s (median) | Generated tokens | Peak VRAM (MiB) | Peak RAM used (MiB) | Peak swap (MiB) |
|---|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 100% | 27.6 min | 79.0 s (36.7–124.3) | 33.3 | 54,866 | 6,700 | 8,910 | 67 |
| `gemma3:12b` | 62% | 4.4 min | 8.6 s (6.1–40.4) | 9.2 | 1,953 | 6,920 | 7,100 | 180 |
| `phi4:14b` | 58% | 6.3 min | 13.5 s (11.5–48.0) | 6.7 | 2,260 | 6,758 | 5,167 | 285 |
| `gpt-oss:20b` | 47% | 8.7 min | 19.9 s (10.5–50.1) | 22.6 | 10,132 | 6,820 | 3,256 | 850 |

(Peak VRAM is whole-GPU use of the 8,192 MiB card, so it includes the desktop session and is not attributable to
the model alone.)

Reading it honestly: `qwen3.5:9b` is the fastest generator by far (fully GPU-resident) and the slowest in
wall time because native reasoning generates roughly 24–28× the tokens of the two non-thinking models (and 5× the
other reasoning model). Residency is the
dominant speed variable on this 8 GB card: the two dense models that only partly fit run at 7–9 tok/s, while the
MoE `gpt-oss:20b` runs at 23 tok/s at 47% residency. All four stayed within the 12,288 context (longest real
prompt 1,797 tokens; padded Stage-0 calls ≈ 7.9k). `gpt-oss:20b` used the most swap (850 MiB) while using the least
RAM — noted as a stability observation, not a failure.

## 8. Recommendation

**None qualified. Capabilities that failed:**

1. **Claim → obligation discrimination that is simultaneously high-recall and high-precision (G3 ∧ G4).** Every
   candidate got one side and lost the other. This is the exact capability Qwen2.5-1.5B was retired for.
2. **Coverage audit without wrong-obligation attachment (G6):** three of four attach a real, verified proposition
   to an obligation it does not answer (or, for `qwen3.5:9b`, could not be evaluated).
3. **Order-robustness (G5):** `phi4:14b` and `qwen3.5:9b` change answers when only presentation order changes.
4. **Operational (G1, one model):** `qwen3.5:9b` under native reasoning does not fit a 4,096-token output cap.

**Does the evidence support moving up one tier (~24–27B)? Weakly-to-moderately yes — and it is the next step I
would take, but the tranche cannot isolate model size, so I would not present it as established.**

- *For:* no 9–20B model passed both G3 and G4; the failures are opposite-signed across models, which looks like a
  discrimination-capacity shortfall rather than a prompt or format bug (schemas, enum enforcement, and G2 all held);
  the simple cases (A2/A4/A5) are already saturated, so the remaining headroom is exactly the hard-discrimination
  cases where added capacity is most plausibly useful. `gemma3:12b` is the best-informed anchor: perfect recall and
  recovery, with only nearest-category false positives left.
- *Against / confounds:* the four differ in family, reasoning mode, MoE vs dense, quantization and context-cap
  behavior; each ran once at temperature 0 on a 19-call battery, so a per-case result is one draw. Two failures are
  operational, not semantic (Qwen's cap; partial GPU residency). A ~27B model on this card would be far less
  GPU-resident than anything tested here (a Q4 27B is roughly 17 GB against 8 GB VRAM), so expect it to be
  materially slower than the 7–23 tok/s above — an *estimate*, not a measurement.

**Smallest next tests, each needing your decision (nothing below was run):**

1. **One same-battery tier-up arm**, under the identical frozen envelope, with a **same-family contrast** as the
   cleanest scale test (`gemma3:27b` against `gemma3:12b`), and record latency as measured rather than assumed.
2. **Separately**, if you want `qwen3.5:9b` to remain in play, that is an *envelope* question the frozen protocol
   excluded (a larger output cap or non-thinking mode for reasoning models) and would need its own pre-registered
   arm. Its completed-call recall misses suggest it would not clear G3 on the cap change alone.
3. Whether the model tier should be chosen per-*subtask* (recall vs. precision) is a design question, not a
   bakeoff result, and is not evaluated here.

## 9. Disclosed judgment calls and limits

- The pre-freeze judgment calls stand as documented in the freeze commit and `README.md`: original request shown in
  every prompt; A7 added as a "which scales?" positive; Task C's s4 state is a disclosed reconstruction; prompts name
  the JSON fields; every schema has an unscored `rationale` first.
- One run per candidate per case at temperature 0, seed 42. The order-robustness gate exists because single draws
  can flip with presentation order (`phi4:14b` does).
- `qwen3.5:9b`'s G6/G7 verdicts reflect unusable calls, not observed wrong answers; read them that way.
- Earlier Vulkan-era Stage-0 records were archived under `.local/` and are not used anywhere in this report.
- The battery is one question's worth of real obligations (`q_aib`); it qualifies a model for *this kind* of
  supervisory judgment, not in general.

## 10. Reproduce / repository state

```powershell
python -m experiments.ask_cli_revised.supervisor_eval.build_battery verify   # "freeze intact"
python -m experiments.ask_cli_revised.supervisor_eval.run_eval preflight       # log must say library=CUDA
python -m experiments.ask_cli_revised.supervisor_eval.run_eval stage0  <key>   # qwen3.5-9b gemma3-12b phi4-14b gpt-oss-20b
python -m experiments.ask_cli_revised.supervisor_eval.run_eval battery <key>
python -m experiments.ask_cli_revised.supervisor_eval.run_eval score   <key>
python -m experiments.ask_cli_revised.supervisor_eval.run_eval report
```

Public artifacts: this report, `README.md`, `FREEZE.txt` (`freeze_sha256 5848f8c4…697e`),
`battery_manifest.json`, `receipts/{key}.json` (text-free: identity, timings, residency, per-case verdicts as ids,
gate results), and `receipts/infrastructure.json`. Private (gitignored, `.local/ask-070-supervisor-bakeoff/`): the
battery with verbatim quotes, and per-model raw outputs, thinking text, resource CSVs. 247 offline tests pass; ruff
is clean on the package. The freeze commit is `3d12610d`; the results commit follows it and is not pushed.
