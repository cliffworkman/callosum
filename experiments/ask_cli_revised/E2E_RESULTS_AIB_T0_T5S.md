# Ask 0.7 E2E — first two scored AIB runs: T0 and T5* (aggregates only)

Substrate: SHA `6d863121`, tag **`e2e-substrate-v2`** (`e2e-substrate-v1` still `c58faff6`, unmoved). Both runs: `scored: true`, clean tree, same SHA, frozen contracts intact,
library copy identical before and after (sha256 prefix `4f2e98a5`), technical validity **true**, every mechanical check ok, gate NO ANSWER 0 (0/144 and 0/69).
Private run dirs: `.local/e2e-runs/scored/{T0-aib,T5star-aib}` (library text; never committed). No library text, claim text, quotations or answers appear in this file.

## Identity — read before comparing

- **T0** = repaired common-base Q2.5 baseline: W Qwen2.5-1.5B · R Qwen2.5 · C deterministic · P legacy (deepen-then-nominate). **Not** run9 and not the historical pipeline.
- **T5\*** (CLI key `T5`, manifest `profile.name = "T5*"`) = role-specialist topology: W Qwen3.5:9b `think:false` · R off · C phi4:14b · P gemma3:12b. **Not** an upper bound.
- T0 vs T5\* differs in worker, R/C architecture, planner and recovery budget at once. It is a **system-level contrast**, not a causal estimate for Phi4, Gemma12, Qwen3.5 or heterogeneity.

## Side by side

| | T0 | T5* |
|---|---|---|
| wall (s) | 145.8 (W1 77, W2 61) | 332.5 (W1 220, C1 106) |
| retrieved hits / gate calls | 138 / 144 | 48 / 69 |
| gate actions | discard 118, accept 25, after 1 | accept 19, before 21, discard 23, after 6 |
| claims formed (select / form calls) | 15 (15 / 15) | 40 (19 / 40) |
| verification | 0 verified, 2 weak, 13 unverified | **14 verified**, 23 weak, 3 unverified |
| ledger (source-verified) | **0** | 14 claims; 13 distinct texts; 11 distinct evidence anchors; 5 papers |
| items judged responsive (final) | 0 / 6 | 6 / 6 (by phi4 alone; R off) |
| attachments | 0 | 15 (s1 x6, s2 x4, s3 x1, s4 x1, s5 x1, s6 x2) |
| unresolved items | 6 / 6 | 0 |
| recovery | legacy on 6 items: 46 existing + 44 new hits, **0 new verified** | **not run** (P skipped: no unresolved items; gemma never called) |
| frozen-label matches / violations | 0 / 0 | 0 / 0 (no claim text matched a frozen AIB claim) |
| unsupported final claims; render exact | 0; yes | 0; yes |
| final answer | 0 claims: grounded, answers nothing | 14 grounded claims across all 6 items; responsiveness pending adjudication |
| mechanical NO ANSWER | 0 of 180 calls | 0 of 129 calls |
| generated tokens | not recorded for managed-local W calls (output chars 6.2K) | gate 414, select 216, claim 1,302, C 270 |
| model load / unload | none (Q2.5 resident) / 0 | qwen3.5 42 s + phi4 56 s load (~30% of wall) / 0.2 s unload |
| peak GPU / host RAM used / swap used (JUNO sampler) | 1.8 GiB / 2.8 GiB / 1.7 GiB | 6.6 GiB / 4.4 GiB / 1.8 GiB |
| after-phase resident VRAM | Q2.5 2.0 GiB | qwen3.5 5.4 GiB, phi4 6.4 GiB |

## Findings

1. **Repaired Q2.5 worker: 0 usable source-verified evidence at full AIB scale.** The gate is not the whole story: every one of the 15 formed claims had an exact source quote (quote 1.0) but essentially no NLI support
   (max 0.11) — several restate the question or assert things the passage does not; the verifier correctly kept all of them out (invariant 1 held). T0's downstream stages had nothing to judge.
2. **Qwen3.5 produced enough evidence for a meaningful downstream test** (14 source-verified claims, 11 anchors, 5 papers), though clustered (papers 67 and 61 carry most claims).
3. **Phi4 as C judged every item responsive and left nothing unresolved.** **Preliminary, unadjudicated reading (analyst's, identifiers only):** where the claim is specific (scales, cross-cultural) the attachment looks sound; several items rest on tangential claims:
   `p7, p8, p10 -> s2` (attitude / intervention-flavored claims for a brain-areas item), `p12 -> s5` (a claim that names no culture or measure), `p13, p14 -> s6` (no effectiveness evidence). These come from C alone (R was off); source verification is not responsiveness.
   **Provenance anchoring is plausible:** all 14 claims were attached to the item they were *retrieved for* (13 of 14 only there), and identical claim text retrieved for two items (p3/p9; p11/p12) followed its retrieved-for item. The frozen C prompt shows that line. This is measured, not yet shown to be an error; a 15-item blinded sheet is in the private dir.
   This is not a Phi4 semantic failure claim: the evidence was adequate, but whether the coverage is right needs adjudication.
4. **Gemma12 recovery was not exercised** in T5\* (phi4 left no gaps, so P skipped). T0's legacy recovery found 0 new verified evidence. Whether any planner yields genuinely new responsive evidence is still unanswered.
5. C2 (phi4 after recovery) and the phi4 -> gemma -> Qwen3.5 swap chain in a scored run were also not reached.

## Cost

Both runs are cheap: 2.4 and 5.5 minutes. Model loading is the main T5\* overhead (phi4 56 s, qwen3.5 42 s); switching itself is ~free. Peak GPU 6.6 GiB fits the 8 GB card at `num_ctx` 12,288.

## What T3 or T4 would resolve (held; not run)

They share T5\*'s worker, so they should see nearly the same source-verified ledger (Qwen3.5 `think:false` at temperature 0 reproduced identical claim text across runs; to be verified by claim-set comparison) and differ only in R/C/P.
That isolates: (a) whether R-attachment with deterministic coverage is as generous as phi4's C on the same evidence, (b) whether any arm leaves unresolved items so P/recovery is exercised at all, and (c) whether recovery finds new anchors.
