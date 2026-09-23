# Ask 0.7 supervisor bakeoff — Qwen3.5 reasoning-budget sensitivity (4,096 → 8,192 generated tokens)

**This is a post-hoc, predeclared execution-envelope sensitivity arm, run after the first tranche's results were observed. It is not part of
the frozen first tranche and it does not re-score it.** The 4K result stands unchanged and authoritative for the frozen envelope
([`REPORT.md`](REPORT.md), freeze `3d12610d`, results `87e3d7c3`), as does the separate scale test ([`GEMMA27_EXTENSION.md`](GEMMA27_EXTENSION.md)).

- **Question:** of the seven frozen calls where `qwen3.5:9b` hit the 4,096-token ceiling *while still reasoning*, what happens if the identical
  calls may run to 8,192 tokens? Does the 4K cap merely hide capability, or does Qwen3.5 still fail once allowed to finish?
- **One variable changed:** `num_predict` 4,096 → 8,192. Everything else identical: same `qwen3.5:9b` artifact (digest `6488c96f…`, pulled before
  the original run), same Ollama v0.34.3 on CUDA (driver 580.178.04), `num_ctx 12288`, prompts, schemas, orderings, temperature 0, seed 42,
  `think: true`, thread/batch options, frozen watchdog. One observation per case, no retries, **no gates and no Qualified flag** (seven reruns
  cannot make a battery-level result; verdicts are per-case, through the frozen case judges).
- **Cases (confirmed against the original raw results before running):** exactly the seven `done_reason=length` calls — A1.original, A7.original,
  A7.reversed, B1.original, B1.reversed, C1.original, C1.reversed. Completed semantic failures (A1.reversed, A1.rotated, both `[]`) were **not** rerun.
- Artifacts: this file and `receipts/qwen3.5-9b-8k-sensitivity.json` (text-free). Raw reasoning/output stay in gitignored `.local/`. Frozen files, every
  first-tranche and Gemma27 receipt, and the original Qwen raw results are byte-identical before and after (23 hashes compared).

## 1. Bottom line

| | |
|---|---|
| **Mechanical** | **4 of 7 completed** at 8K (A1.original, A7.original, C1.original, C1.reversed). **3 of 7 hit the 8,192 cap again** (A7.reversed, B1.original, B1.reversed). |
| **Semantic** | Of the 4 that completed: **3 correct** (A7.original, C1.original, C1.reversed), **1 wrong** (A1.original returned an empty selection). |
| **By capability** | **Bounded recovery: observed and correct (2/2)** — needed 6.1–7.1K tokens. **Whole-ledger coverage: still unobserved** — both audits capped again. **Claim→obligation: A1 is a budget-independent miss** (`[]` on all three orderings); A7 is right when it finishes but ordering-dependent in cost. |

Reading, per the rules fixed before the run: **recovered = completes *and* correct.** A7.original, C1.original, C1.reversed are recovered. A1.original
completed but is wrong — *not* recovered: the cap was a mechanical problem but not the explanation for that miss. A7.reversed, B1.original,
B1.reversed show continuing reasoning-budget pressure; **no further escalation was attempted** and they come back as a decision point (§7).

**Qwen3.5 still cannot qualify on the original battery from this arm**: the already-completed A1.reversed and A1.rotated `[]` misses stand, and
A1.original now adds a third. This arm can only reveal previously censored behavior.

## 2. The seven calls

| Case | 4K outcome | 8K mechanical outcome | 8K semantic outcome | Tokens used (total; ≈reasoning) |
|---|---|---|---|---|
| A1.original | unusable (length @ 4,096) | completed | **wrong** — selected nothing; s1 required | 5,519; ≈5,415 |
| A7.original | unusable | completed | **correct** — s3 | 6,185; ≈6,100 |
| A7.reversed | unusable | **hit 8,192 cap** | unusable (no output) | 8,192; ≈8,192 |
| B1.original | unusable | **hit 8,192 cap** | unusable (no output) | 8,192; ≈8,192 |
| B1.reversed | unusable | **hit 8,192 cap** | unusable (no output) | 8,192; ≈8,192 |
| C1.original | unusable | completed | **correct** — recovery plan below | 6,082; ≈5,897 |
| C1.reversed | unusable | completed | **correct** — recovery plan below | 7,073; ≈6,918 |

"≈reasoning" is an approximate character-proportion split of `eval_count`, which is the authoritative total (Ollama reports no per-phase count). The
final structured JSON is ~85–190 tokens; the budget question is entirely about reasoning. Structured output was valid and used no invented ids in
all four completed calls.

## 3. The four calls the original battery could not observe at all

### Coverage audit (B1) — both still capped
B1.original and B1.reversed each ran to **8,192 tokens without producing an answer** (prompt 1,060 tokens; 246 s each). Whole-ledger coverage
assignment therefore remains **unobserved for Qwen3.5**: the 8K arm produced neither a correct nor a wrong mapping. Nothing about p3 → s1, the
p5/p6 traps, or s4/s6 staying unresolved can be said. (More budget did not fix execution here; whether it eventually would is unknown, and
extending the ladder was explicitly out of scope.)

### Bounded recovery (C1) — completed and correct on both menus
| Obligation | C1.original | C1.reversed | Expected |
|---|---|---|---|
| s1 | MARK_COVERED p3 | MARK_COVERED p3 | diagnostic (p3 is the verified s1 support) |
| s2 | MARK_COVERED p1 | MARK_COVERED p4 | diagnostic |
| s3 | PRESERVE_UNRESOLVED | PRESERVE_UNRESOLVED | no closure, no repeat |
| **s4** | **NOMINATE** | **NOMINATE** | **NOMINATE** |
| **s5** | **PRESERVE_UNRESOLVED** | **PRESERVE_UNRESOLVED** | **PRESERVE_UNRESOLVED** |
| s6 | PRESERVE_UNRESOLVED | PRESERVE_UNRESOLVED | no closure |

Both plans satisfy every frozen recovery rule: s4 nominates new papers, s5 preserves rather than closing on generic-related evidence, nothing in s3–s6
is closed, and no already-performed action is repeated. s1/s2 are closed with propositions the ledger retrieved for them (p3 for s1; p1/p4 for s2), which the gate permits. The reasoning cost was
6.1–7.1K tokens — above the old cap by ~49–73% — so **these two calls were censored capability, not a semantic limitation.**

## 4. A1 / A7: completion is not recovery

- **A7 ("EBQ measures explicit bias" → s3):** A7.original finished correct at 6,185 tokens. A7.rotated had already finished correct at 3,204 under the 4K cap,
  and A7.reversed is *still* capped at 8,192. Same claim, three presentation orders: **≈3.2K, ≈6.2K, >8.2K tokens** — a spread of more than 2.5× from
  order alone. The extra budget mostly re-confirmed an answer already obtainable cheaply in one ordering.
- **A1 (attitudes → s1):** now `[]` on all three orderings — A1.reversed and A1.rotated at 4K (completed), A1.original at 8K after 5.5K tokens of reasoning. More
  thinking did not change the answer. This is a stable semantic miss, independent of budget, that alone keeps `qwen3.5:9b` from qualifying.

## 5. Budget evidence

| Group | Tokens |
|---|---|
| 12 calls that completed under the 4K cap (all Task A) | 1,191–3,939, median 2,130 |
| 4 calls that completed only at 8K | 5,519 · 6,082 · 6,185 · 7,073 (median 6,134) |
| 3 calls still capped at 8K | > 8,192 |

- Completions used **67–86%** of the 8,192 allowance, so headroom is thin (C1.reversed at 86%); n = 2 per stage is too small to bound a stage's need.
- Speed was steady at 32–34 tok/s, 189–248 s per call, 100% GPU-resident, peak swap 1.3 GB (baseline 1.27 GB); the arm took ~26 min. At this speed an 8K call costs ~4 min.
- **Context accounting (actual returned counts, not the pre-run estimate):** prompt + generated ≤ **9,252** of 12,288 in every call (min headroom 3,036); no context change was needed or made.
- **Determinism diagnostic (descriptive, not proof):** in all seven calls the 8K run's reasoning text begins with the entire stored 4K reasoning, character for character
  (100% prefix agreement). The 8K runs behave as continuations of the 4K runs here; a divergence would have been reported, not treated as invalidating.

## 6. Answers to the handoff questions

1. **Completed at 8K:** 4 of 7.
2. **Semantically correct among those:** 3 of 4 (A7.original, C1.original, C1.reversed); A1.original completed but wrong.
3. **Both coverage audits:** both hit the 8,192 cap with no output; no mapping was produced, so coverage is unobserved.
4. **Both recovery cases:** completed and correct — s4 → NOMINATE, s5 → PRESERVE_UNRESOLVED, s3/s6 preserved, s1/s2 closed with p3/(p1|p4).
5. **Reasoning tokens the recovered calls required (≈):** A7.original ≈6.1K, C1.original ≈5.9K, C1.reversed ≈6.9K (all above 4K; 74–86% of 8K).
6. **Does this justify dynamic / stage-aware budgets before E2E?** Yes for the capabilities that demonstrably need it, no as a universal rule — see §7.
7. **Smallest supported runtime policy:** see §7.

## 7. What policy, if any, do these observations support? (recommended from the data; nothing built)

The evidence is **stage-dependent, not uniform**, which argues against a single Qwen cap and against simply raising it:

- **Bounded recovery (C):** needs roughly **6–7K** and is correct when given it (2/2). The smallest supported change is a per-call allowance of **8K for
  recovery-planning calls**, because at 4K these produce no usable answer at all. Headroom is thin (74–86% used), so this is a floor of evidence, not a safe bound.
- **Claim→obligation (A):** 12 of 15 A calls finish **≤ 3.9K**; the 3 that overflow gave one wrong answer (A1), one correct-but-redundant answer (A7.original) and one still capped
  (A7.reversed). The added budget mostly buys cost, and the cost varies >2.5× with presentation order for the same claim. The data does **not** support
  raising the A-stage allowance; treating an overflow as "no answer" for this stage is the evidence-proportional default.
- **Whole-ledger coverage (B):** **no allowance up to 8K produced an output**, so there is no evidence about what it takes or whether Qwen3.5 does it well. Do **not**
  extrapolate to 12K: a 1,060-token B prompt plus a 12K allowance would also exceed the 12,288 context, i.e. it would need a context increase you have not approved.
- **Net:** the observations support a **stage-aware budget** (allowance chosen by task family) over a universal cap, and a **completion-aware** treatment of
  truncation (a capped call is "no answer", never a semantic result). They do not support a universal 8K, and 3 of 7 calls show pressure beyond it.

**Decision points back to you (none started):** (a) whether Task B belongs to Qwen3.5 at all, or needs a separate, explicitly approved larger-budget-and-context arm; (b) whether
recovery planning at ~4 min/call is an acceptable supervisor cost for a rare stage; (c) whether to pursue the A-stage ordering-dependence (≈3.2K vs >8.2K for one claim), which is a
stability question more than a budget one.

## 8. Limits

Single draw per case at temperature 0, n = 7, one model. Token phase split is approximate (total `eval_count` is authoritative). The 8K observations cannot be merged into a battery-level
result and were not. Two recovery cases and zero coverage cases are thin evidence for stage-level claims. No matched controls were run.

## 9. Reproduce

```powershell
python -m experiments.ask_cli_revised.supervisor_eval.build_battery verify        # "freeze intact"
python -m experiments.ask_cli_revised.supervisor_eval.run_eval sensitivity         # the seven censored calls only, num_predict 8192
python -m experiments.ask_cli_revised.supervisor_eval.run_eval sensitivity-report  # writes receipts/qwen3.5-9b-8k-sensitivity.json only
```

Private (gitignored): `.local/ask-070-supervisor-bakeoff/qwen3.5-9b-8k-sensitivity/` (raw calls, arm metadata, resource CSV). The frozen 4K results are in `.local/…/qwen3.5-9b/` and were not touched.
