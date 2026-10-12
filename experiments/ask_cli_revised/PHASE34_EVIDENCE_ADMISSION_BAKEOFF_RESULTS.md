# Phase 34 — Evidence-admission bakeoff

**Disposition: MINIMAL POLICY IDENTIFIED** — with one named open gap.

Drop the chunk-similarity gate and raise the NLI support floor from 0.55 to 0.90, keeping the
exact-quote requirement and the existing contradiction veto (rule **B2** below). On the labelled
set this admits 38 of 59 supported natural pairs instead of 14, and 16 of 25 supported live Q1/Q3
pairs instead of 7, while admitting the same number of known-bad controls as today (5 of 27: 3
contradicted, 2 unsupported — the same counts as the current verifier). It needs no new model
pass; it removes one.

This is an experimental finding only. **No production code, threshold, semantic version, contract,
frozen hash or historical output was changed.** Nothing here is implemented.

What it does not fix: the local NLI model rejects 18 of 59 supported pairs outright, including
Q1's "two-fold reduction" and "1.5-2x fewer samples" findings, and it passes referent-swap controls
at 0.96-0.98. No cheap rule tested repairs either. The LLM recheck intended to probe that gap was
**not run** (JUNO access was refused; see section 9).

Reference labels come from **one blinded ChatGPT adjudication pass. No independent human
scientific validation is claimed.** Every negative example in the labelled set is a synthetic
control written by Claude; the natural sample contained none.

## 1. Starting state

Worktree `...\ask-060-hier11-recpm3-citefix-20260929T212442Z`, branch
`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, HEAD
`fab100c1b10dff245ffcbb5d6888a8e45bd9b92d`, clean at entry and clean after Phase A.
All 17 source files read (two library copies, five runs' proposition/verification/contract files)
re-hash unchanged. Library copies were opened `mode=ro&immutable=1`.

Experiment root (gitignored): `.local/phase34-evidence-admission-bakeoff-20261011/`.

## 2. Historical evidence actually recovered

- **Scored claim-evidence records: 738**, from five preserved runs: q_aib t5c (60), q_aib Phase 23
  (385), q_aib Phase 28 attempt 2 (264), live Q1 (9), live Q3 (20). Live Q2/Q4/Q5/Q6 have none.
- **Unique pairs: 288** (same claim + quote + chunk). The three q_aib runs largely repeat one another;
  262 unique pairs come from 21 q_aib papers and 26 from 2 live papers. No pair changed status across runs.
- **No per-pair reference judgments existed.** Phase 23A adjudicated roles, not claim-evidence pairs.
  `REVIEW_NOTES.md` records a 0.698-vs-0.70 "amygdala" specimen and explicitly leaves the threshold
  alone. No threshold, NLI or alignment correction was ever implemented. Run 0.6b built a
  verifier-replay harness but its baseline run directory is not in this worktree and its live pass
  never ran.
- Existing negative-control fixtures (`assertion_authority_*`, `attribution_i4_2b3_*`,
  `prior_source_review_*`) exercise the sufficiency layer on synthetic sentences and carry no verifier
  scores. They informed the failure types used for controls; none was reused as a scored record.

## 3. Baseline verifier behaviour

`LocalCitationVerifier._status` admits only when similarity >= 0.70, quote = 1.0 and NLI support
>= 0.55, after a contradiction veto (contradiction >= 0.55 and > support). `stages.source_verified`
keeps only `verified`.

- **The two model gates read different text.** "Similarity" is cosine between the claim and the stored
  embedding of the *whole cited chunk*; NLI scores the *isolated quote*. Recomputing both reproduces
  every frozen value to about 1e-6 across all 288 pairs.
- Of 288 unique pairs: 79 verified, 118 weak, 73 unverified, 18 contradicted.
- 73 pairs have an exact quote and NLI >= 0.55 and fail only the similarity gate. 68 of those 73 have
  claim-to-quote similarity >= 0.70.
- Quote confidence is 1.0 on all 288, because extraction already discards non-verbatim quotes. The quote
  gate is therefore never the deciding gate in this data. 39 pairs carry quotes that continue across two
  chunks; production validated those per anchor, and their similarity is measured against the first chunk only.

## 4. Evaluation set and its limits

A blinded packet of **99 items** (21 papers) was built before any label existed, showing claim, exact
quote and surrounding source text only. Rules, split, metric treatment and acceptance criteria were
fixed in `PREDECLARATION.md` first.

| Group | Items | Adjudicated |
|---|---:|---|
| Natural, q_aib | 41 | |
| Natural, live Q1/Q3 (every single-chunk pair) | 26 | |
| **Natural total** | **67** | 62 supported, 3 partial, 2 unresolved, **0 unsupported, 0 contradicted** |
| Synthetic negative controls | 32 | 20 contradicted, 7 unsupported, 2 partial, 3 disagreements |

Handling, as predeclared unless marked:

- `partial` is counted as not supported and shown in its own column. `unresolved` is excluded from rates.
- Three controls where the adjudicator's class differed from the construction intent are treated as
  unresolved. An intended-unsupported control adjudicated as contradicted is not a disagreement; both
  are negatives.
- **Post hoc:** three natural "supported" items are statements about the excerpt ("The excerpt does not
  support a claim about ...") rather than scientific claims. They are separated as `meta` and not counted
  as supported evidence. 19 of the 288 unique pairs are of this kind.
- This leaves **59 supported natural pairs (25 live), 27 negative controls, 5 partial, 5 unresolved, 3 meta**.

Limits that bound every number below:

1. One model adjudicator; 9 of 99 labels at medium confidence, none low.
2. **All negatives are synthetic** minimal edits of real claims. They are near-paraphrases by
   construction, so they cannot show similarity protecting against anything; they do test NLI.
3. The natural sample is stratified toward excluded pairs, so "x of 59" is not a population recall rate.
4. Two libraries, 23 papers, and three of five runs are the same question. Eight additional controls
   were scored but not adjudicated and are reported only as counts.

## 5-8. Comparison

Counts are admitted / available on the labelled set. `inv` is how many of the 288 unique pairs the rule
admits (descriptive, unlabelled). Rules marked * were added after seeing labels and are exploratory.

| Rule | Definition (always: exact quote, not vetoed) | Supported natural | Live Q1/Q3 supported | Negative controls | of which contradicted / unsupported | Partial | inv | Extra cost |
|---|---|---:|---:|---:|---:|---:|---:|---|
| **BASE** | sim_chunk >= .70, nli >= .55 | 14/59 | 7/25 | 5/27 | 3 / 2 | 3/5 | 79 | — |
| A1 | sim_chunk >= .50, nli >= .55 | 33/59 | 15/25 | 8/27 | 5 / 3 | 5/5 | 137 | none |
| A2 | bands: .50-.70 needs nli >= .90 | 31/59 | 14/25 | 6/27 | 4 / 2 | 5/5 | 130 | none |
| B1 | nli >= .55, no similarity | 41/59 | 17/25 | 8/27 | 5 / 3 | 5/5 | 152 | none (one pass fewer) |
| **B2** | **nli >= .90, no similarity** | **38/59** | **16/25** | **5/27** | **3 / 2** | 5/5 | 132 | **none (one pass fewer)** |
| F1 | sim_quote >= .70, nli >= .55 | 40/59 | 16/25 | 8/27 | 5 / 3 | 5/5 | 145 | embed quote |
| F2 | max(sim_chunk, sim_quote) >= .70 | 40/59 | 16/25 | 8/27 | 5 / 3 | 5/5 | 147 | embed quote |
| C1 | BASE + context-NLI rescue | 31/59 | 15/25 | 6/27 | 4 / 2 | 5/5 | 133 | context NLI on discordant pairs |
| C2 | nli >= .55 and context nli >= .55 | 24/59 | 12/25 | 2/27 | 1 / 1 | 4/5 | 104 | context NLI on every pair |
| G1 | B1 with frame-stripped NLI | 42/59 | 18/25 | 8/27 | 5 / 3 | 5/5 | 153 | second NLI pass |
| Q0* | exact quote + veto only | 58/59 | 25/25 | 14/27 | — | 5/5 | 270 | none |
| SQ* | sim_quote >= .70 + veto, no NLI floor | 50/59 | 21/25 | 13/27 | — | 5/5 | 211 | embed quote |

Paper-grouped split (dev = even q_aib paper ids; held-out = odd q_aib paper ids plus the whole live library):

| Rule | Held-out supported | Held-out negatives | Dev supported | Dev negatives |
|---|---:|---:|---:|---:|
| BASE | 10/40 | 2/16 | 4/19 | 3/11 |
| B1 | 26/40 | 4/16 | 15/19 | 4/11 |
| B2 | 24/40 | 3/16 | 14/19 | 2/11 |
| F1 | 25/40 | 4/16 | 15/19 | 4/11 |
| C2 | 16/40 | 1/16 | 8/19 | 1/11 |

### What each hypothesis turned out to be

**A. Similarity bands.** They help only because they loosen a gate that does not discriminate. A1 is
strictly dominated by B1 (B1 adds 8 supported, no negatives). A2 is dominated by B2 (7 more supported,
one fewer negative). Rejected as an intermediate step toward removing the gate.

**B. Multidimensional, noncompensatory rule.** This is where the gain is. With exact quote and the
contradiction veto held as hard requirements, similarity adds nothing: its AUC for separating supported
from negative items is 0.43 against the chunk and 0.62 against the quote, versus 0.81 for NLI support
and 0.87 for (1 - contradiction). On natural pairs the 0.70 gate excluded 27 supported pairs that
B1 admits and zero unsupported ones.

**C. Selective contextual escalation (local NLI).** Not a rescue mechanism. C1 recovers fewer supported
pairs than simply dropping the gate. Adding one neighbouring sentence each side often *lowers* support on
faithful pairs (several fall from about 0.99 to about 0.25), because the longer premise dilutes the
entailment. As a *confirmation* step (C2) it is the only tested rule that cuts negative admissions below
today's (2/27 vs 5/27, catching most referent swaps) while still beating BASE on supported pairs (24 vs
14). It costs a second NLI pass on every pair and gives up 14 supported pairs relative to B2. The LLM
variant was not run.

**D. Relative ranking.** Uninformative here. Among natural labelled pairs grouped by run and
subquestion, the top-ranked pair was supported in 9 of 9 groups and the top three in 22 of 25, against a
base rate of 0.91 — ranking barely beats picking at random because nearly every natural pair is
supported. It was never evaluated as admission. Rejected as adding nothing measurable.

**E. Empirical rule selection.** The dev-selected rule was "nli >= .70, no similarity" (15/19 supported,
2/11 negatives on dev). On held-out it admitted 25/40 supported but 4/16 negatives against BASE's 2/16.
The selected threshold did not transfer. With 30 dev items this is expected, and it is the reason the
recommendation rests on a predeclared rule rather than a fitted one. Calibration claims are not supportable.

**F. Claim-to-quote similarity (sixth hypothesis).** The mechanism is real — 68 of 73 gate-only losses
clear 0.70 once similarity is measured against the quote — but the corrected signal is redundant. F1
recovers no supported pair that B1 misses, B1 recovers one that F1 misses, and they admit identical
negatives. It costs an extra embedding for nothing. Rejected.

**G. Frame-stripped NLI.** Deleting a leading "The study found that" recovers exactly one more supported
pair for a second NLI pass. Rejected as not worth the pass.

### Marginal gain (supported natural pairs / negative controls gained by the first over the second)

| Comparison | Supported | Negatives |
|---|---:|---:|
| B2 over BASE | +24 | 0 net (one swapped) |
| B1 over B2 | +3 | +3 |
| F1 over B1 | 0 | 0 |
| B1 over F1 | +1 | 0 |
| F1 over A1 | +7 | 0 |
| A2 over F1 | 0 | 0 |
| C1 over F1 | +2 | 0 |
| G1 over B1 | +1 | 0 |
| C2 over BASE | +16 | +1 |
| BASE over C2 | +6 | +4 |
| Q0* over B1 | +17 | +6 |

### Error inventory

- **Negatives the current verifier already admits (5):** three referent swaps (cognitive/affective
  empathy; trusting/trustworthy; anomalous/typical face contrast reversed), one fabricated added outcome
  ("...and against people of color"), one aim reported as a finding. NLI support on four of them is
  0.96-0.98. B2 admits the same set except it swaps the aim-as-finding (NLI 0.64) for a fabricated causal
  claim (NLI 0.98, similarity 0.68).
- **Negatives B1 adds and B2 does not (3):** a reversed contrast at NLI 0.69, a dropped "not in all cases"
  at NLI 0.89, and the aim-as-finding at 0.64. This is the whole case for 0.90 over 0.55.
- **Supported pairs no NLI-floor rule recovers (18 at 0.55; 21 at 0.90):** includes live Q1's "as much
  as a two-fold reduction" (NLI 0.009 against a near-verbatim quote), "1.5-2x fewer samples on Mouse 1 and
  both datasets for Mouse 3" (0.06), and "non-trivial gain over both baselines" (0.39).
- **Contradiction veto false positives:** one natural supported pair that restates its quote almost
  verbatim scores contradiction 0.97 and is vetoed by every rule. The other two vetoed natural items are
  `meta` statements, which the veto removes for the wrong reason.
- **Partials (5):** BASE admits 3, C2 admits 4, every other rule admits all 5. Two natural ones turn "we suggest" / "may"
  into a plain assertion. No tested signal detects a dropped hedge.

### What B2 changes for the live cases

It newly admits nine live pairs, including 5591 ("up to a factor of 2x ... not in all cases ... worst
case matches baseline", sim 0.657, NLI 0.994), 5502 (simulation stimulus design, 0.610 / 0.906), 5215
(low-rank model efficacy in mouse motor cortex, 0.693 / 0.986) and 4616 (simulation control result,
0.617 / 0.991). Records reaching the ledger rise from 2 to 5 of 9 on Q1 and from 7 to 14 of 20 on Q3.
Whether that produces a non-empty Q1 or Q3 answer was **not** tested; that depends on mapping and Layer C.

## 9. Measured cost

Local CPU on this machine (torch 2.6 CPU, 288 pairs, one batched call each):

| Pass | ms per pair |
|---|---:|
| Embed claim (needed only for the similarity gate) | 11-13 |
| Embed quote | 17-20 |
| NLI, quote premise (existing) | 125-128 |
| NLI, quote plus neighbouring sentences | 209-222 |
| NLI, frame-stripped claim | 123 |

B2 uses only the existing NLI pass and no longer needs the claim embedding or vector lookup. C2 would
add roughly 1.7x the current NLI cost per pair. Model load was about 12 s, already paid today.

**New model calls in this experiment:** local embedding and NLI passes only. **Zero LLM calls.** The
predeclared LLM recheck (at most 40 pairs) was justified by the results — the NLI false negatives above
are an important unresolved distinction — but the SSH forward to JUNO's isolated Ollama failed with
`Permission denied (publickey,password)` using the configured `juno` host key, and the earlier helper
script is no longer present. No other credential was tried. The attempt is preserved in `tunnel.stderr.log`.

## 10. Recommended minimal policy

**B2: exact quote (unchanged) + contradiction veto (unchanged) + NLI support >= 0.90; no similarity gate.**

Against the predeclared acceptance test: contradicted admissions 3 vs 3; unsupported 2 vs 2; supported
natural 38 vs 14 and live 16 vs 7. It is the cheapest rule that passes. On the held-out split alone it
admits one more negative than BASE (3/16 vs 2/16) and 24 vs 10 supported.

Why not B1: three more supported pairs for three more negatives, two of them contradicted, which fails
criterion 1. Why not C2: safer than today, but it costs a second pass and 14 supported pairs; it is the
right candidate if protection against referent swaps is judged more urgent than recall.

## 11. Alternatives rejected

| Alternative | Reason |
|---|---|
| Similarity bands (A1, A2) | Dominated by dropping the gate |
| Claim-to-quote similarity (F1, F2) | Redundant with NLI; extra pass, no unique gain |
| Context-NLI rescue (C1) | Recovers less than dropping the gate; context dilutes entailment |
| Frame-stripped NLI (G1, G2) | One extra pair for a second pass |
| Ranking (D) | No measurable information; never an admission rule |
| Fitted thresholds (E) | Did not transfer from dev to held-out |
| Quote-only admission (Q0*, Q00*) | Admits 14 and 27 of 27 negatives |
| Any weighted composite | Not tested; nothing suggested a need |

## 12. Remaining uncertainty

1. **NLI false negatives.** A third of supported pairs, including Q1's central quantitative findings,
   stay excluded under any NLI floor. Smallest next comparison: the capped LLM recheck (at most 40
   labelled pairs — NLI-rejected supported vs NLI-rejected negatives) to see whether one bounded call
   separates them.
2. **Referent and hedge errors pass today and under B2.** Only context confirmation (C2) reduced them.
   Exploratory and not validated: B2 plus a context-contradiction check admitted 38 supported and 4
   negatives.
3. **No natural negatives were observed** in 64 resolved natural pairs, so the real rate at which the
   claim-former produces unsupported claims from an exact quote is unmeasured here beyond "rare in this sample".
4. **The 0.90 floor** was one of two predeclared values, not a calibrated optimum.
5. **`meta` statements** (19 of 288) are excluded today by accident of low scores. B2 admitted none of
   them, but nothing guarantees that.
6. Single adjudicator; two libraries; whether more admitted evidence yields correct final answers is untested.

## 13. Smallest justified production change (not made)

In the Ask experimental verifier path only: construct the verifier with a configuration equivalent to
`retrieval_threshold = 0.0, support_threshold = 0.90`, leaving quote and contradiction thresholds as they
are, then re-run live E2E. `VerificationConfig` already exposes both fields, so this is a configuration
choice at the Ask runtime's construction site rather than a change to verifier logic. Applying it to the
application's `/summarize` path is a separate decision: that would touch Core invariant 1's stated
thresholds and needs its own review.

This requires separate authorization. **Stop.**

## Artifacts

`.local/phase34-evidence-admission-bakeoff-20261011/`: `a1`-`a5` and `b1`-`b2` scripts, `signals.py`,
`frozen_raw.jsonl`, `frozen_unique.jsonl`, `signals_unique.jsonl`, `controls.jsonl`, `PREDECLARATION.md`,
`BLINDED_PACKET_for_adjudicator.md`, `PRIVATE_packet_key.json`, `labels.json`
(SHA-256 `d75e3086...48d13faa`), `b1_results.json`, `b2_extras.json`, and the hash/timing receipts.
`python b1_evaluate.py` regenerates the comparison from the frozen signals and labels.
