# Phase 34 -- Scientific NLI model bakeoff

**Conclusion: CHALLENGER PROMISING** (the DeBERTa-v3 general NLI model), with two limits that
matter as much as the headline:

- It does **not** recover either Q1 finding. A stronger NLI model does not fix that failure.
- Replacing MiniLM is **not** justified by this evidence alone. A separate bounded qualification
  would be needed first.

The SciFact-fine-tuned SciBERT classifier is **unusable as a standalone verifier**: it calls nearly
every related quote/claim pair SUPPORT, including 25 of the 27 negative controls.

Nothing was implemented. No production code, threshold, semantic version or default changed. No
live run and no generative model call was made. Three local classifiers ran offline on CPU.

## 1. Scope and inputs

- Start: `2dcfa65c5ee5b6d645b1dca28ed706cdaf9e078d`, worktree clean, branch in sync. Tracked
  changes: this report and the lineage entry.
- Evaluation set: the bakeoff's 99 blinded-adjudicated pairs, exact preserved quote and claim text,
  label file hash `d75e3086...` (unchanged). 67 natural pairs, 32 synthetic controls.
- Classes, as in the bakeoff: 59 supported, 3 meta statements (set aside), 5 partial, 27 negative
  (20 contradicted, 7 unsupported), 5 unresolved. **Every negative is a synthetic control.**
- Working files (gitignored): `.local/phase34-nli-model-bakeoff-20261012/`. Model files:
  `C:\Users\cliff\callosum-data\nli-bakeoff-models-20261012\`, outside the repository and outside the
  application's model cache. 163 preserved input files were hashed before and after; none changed.
- A predeclaration (scoring rule, threshold grid, split, reading rule) was written and hashed before
  either challenger was downloaded.

**Labels.** One blinded ChatGPT adjudication pass, not human validation. The set has been inspected
in three earlier increments.

**A bias to keep in mind.** The synthetic controls were built as minimal edits of claims MiniLM
had verified. That makes the supported pool lean towards claims MiniLM accepts, and makes the
negatives lean towards wording MiniLM finds persuasive. The second effect favours any challenger.

## 2. Candidate qualification

| | MiniLM (baseline) | DeBERTa-v3 | SciFact SciBERT |
|---|---|---|---|
| Checkpoint | `cross-encoder/nli-MiniLM2-L6-H768` @ `b95119ce` | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` @ `6f5cf0a2` | AllenAI `label_scibert_scifact.tar.gz`, sha256 `2e2345ec...`, dated 2021-01-26 |
| Architecture | RoBERTa-style, 6 layers, hidden 768 | DeBERTa-v2/v3, 12 layers, hidden 768 | BERT (SciBERT uncased vocabulary), 12 layers, hidden 768 |
| Head | 3-way sequence classification | 3-way sequence classification | 3-way sequence classification |
| Labels (index order) | contradiction, entailment, neutral | entailment, neutral, contradiction | CONTRADICT, NOT_ENOUGH_INFO, SUPPORT |
| Label source | checkpoint config | checkpoint config | **AllenAI code only**; config says `LABEL_0..2` |
| Training data | SNLI + MultiNLI | MultiNLI + FEVER-NLI + ANLI | SciFact claims and abstract rationales |
| Licence | Apache-2.0 | MIT | code Apache-2.0, data CC BY 4.0; **no licence stated for the weights** |
| Parameters | 82.1 M | 184.4 M | 109.9 M |
| Weight file | 328 MB | 369 MB (stored half-precision; loads to 32-bit) | 440 MB (408 MB tarball) |

The label orders differ in all three, so indices were resolved per model, never assumed.

**SciFact as a standalone verifier.** Mechanically it works: AllenAI's own inference script feeds
the classifier a (rationale, claim) pair and takes a softmax, so retrieval and rationale selection
are not needed. No pipeline was rebuilt. Two integration cautions remain: the label order is not
recorded in the checkpoint, and the weights are an unlicensed 2021 pickle file.

**Fidelity check (added after seeing its scores, not predeclared).** Because the model's output on
our pairs looked degenerate, it was run on SciFact's own development set with gold rationales. It
loaded with no missing or mismatched weights and scored 67% label accuracy, in line with a working
checkpoint. On that same set it called 34 of 71 human-labelled CONTRADICT pairs SUPPORT. The
behaviour below is the model's, not a wiring fault.

## 3. Scientific correctness

One rule for all models: admit when the model's own support probability is at least *t*. MiniLM at
0.90 is the reference point (the opt-in B2 policy). Above 0.5 the contradiction veto can never
fire, so there is a single knob.

### Across thresholds (supported admitted of 59 / negatives admitted of 27)

| *t* | MiniLM | DeBERTa-v3 | SciFact SciBERT |
|---|---|---|---|
| 0.50 | 42 / 8 | 45 / 2 | 56 / 25 |
| 0.70 | 40 / 6 | 45 / 2 | 55 / 25 |
| 0.80 | 40 / 6 | 45 / 2 | 55 / 25 |
| 0.90 | **38 / 5** | 42 / 2 | 55 / 25 |
| 0.95 | 34 / 5 | 40 / 1 | 53 / 25 |
| 0.98 | 29 / 1 | 31 / 1 | 50 / 24 |
| 0.99 | 14 / 0 | 23 / 0 | 50 / 24 |

- No MiniLM threshold reaches DeBERTa's profile. To get down to one admitted negative MiniLM
  keeps 29 supported; DeBERTa keeps 40.
- DeBERTa is flat from 0.50 to 0.80, so its result does not hinge on a tuned threshold.
- SciFact cannot be given a threshold: negatives score as high as supported claims at every level.
  Its ranking of supported above negative pairs is worse than chance (0.44, against 0.81 for MiniLM
  and 0.89 for DeBERTa).

### Development selection, then held-out

Threshold chosen on the development split as the lowest grid value admitting no more development
negatives than MiniLM at 0.90, then scored once on held-out (40 supported, 16 negative; includes
every live Q1/Q3 pair).

| | Chosen *t* | Dev supported | Dev negatives | Held-out supported | Held-out negatives |
|---|---|---|---|---|---|
| MiniLM, reference 0.90 | -- | 14/19 | 2/11 | 24/40 | 3/16 |
| MiniLM, selected | 0.70 | 15/19 | 2/11 | 25/40 | 4/16 |
| DeBERTa-v3, selected | 0.50 | 15/19 | 0/11 | 30/40 | 2/16 |
| SciFact SciBERT | none qualifies | -- | 11/11 at every *t* | -- | -- |

Among the 25 live supported pairs: MiniLM at 0.90 admits 16, DeBERTa at 0.50 admits 19.

### Contradiction recognition (20 contradicted controls, top label)

| | Contradiction | Neutral | Entailment |
|---|---|---|---|
| MiniLM | 13 | 2 | 5 |
| DeBERTa-v3 | 18 | 1 | 1 |
| SciFact SciBERT | 2 | 0 | 18 |

By control type, negatives the model's top label calls entailment:

| Type (n) | MiniLM | DeBERTa-v3 | SciFact |
|---|---|---|---|
| Negation or reversed relationship (10) | 1 | 0 | 8 |
| Referent swap (4) | 3 | 1 | 4 |
| Fabricated or causal overstatement (3) | 2 | 2 | 3 |
| Incorrect population (5) | 0 | 0 | 5 |
| Omitted qualification (2) | 1 | 0 | 2 |
| Magnitude (1), attribution (1), aim as finding (1) | 1 | 0 | 3 |

### Paired inventory: DeBERTa at 0.50 against MiniLM at 0.90

**Negatives MiniLM admits and DeBERTa rejects (3):**

| Item | Error | MiniLM | DeBERTa |
|---|---|---|---|
| E078 | reversed comparison ("relative to anomalous faces, typical faces increased...") | 0.980 | 0.037, contradiction 0.952 |
| E092 | swapped term ("affective" for "cognitive" empathy) | 0.971 | 0.015, contradiction 0.970 |
| E004 | added outcome ("...and against people of color") | 0.969 | 0.412, contradiction 0.276 |

E004 is a narrow escape: entailment is still DeBERTa's top label, it just falls below 0.50.

**Negatives both admit (2):**

| Item | Error | MiniLM | DeBERTa |
|---|---|---|---|
| E009 | correlation stated as cause | 0.981 | 0.907 |
| E064 | "more trustworthy" for "more trusting" | 0.962 | 0.989 |

**Negatives DeBERTa admits that MiniLM rejects: none**, at any threshold from 0.50 up.

**Supported recovered (8):** E005, E028, E041, E047, E052, E065, E070, E082. Four are findings
(E041 and E065 are near-verbatim claims MiniLM stumbled on, apparently over hyphenation left by
PDF line breaks; E005; E028). Four are framing or background (a title, two statements of what the
paper presents or develops, one summary of prior studies).

**Supported lost (1):** E050, a statement of the study's aim.

**Other classes.** All 5 partial pairs are admitted by both, so qualification loss is not improved.
DeBERTa at 0.50-0.90 admits one meta statement that MiniLM at 0.90 rejects (E036, "the excerpt does
not support a claim regarding...", 0.926). One unresolved pair (E035) is admitted by both.

**Requiring both models to agree** gives 37 supported and the same 2 negatives: no better than
DeBERTa alone, at the cost of both.

### Supplementary check on human-labelled pairs (post hoc)

The fidelity check produced a second, independent comparison at no extra download: SciFact's 209
development pairs (138 SUPPORT, 71 CONTRADICT) carry human labels and natural contradictions, and
neither NLI model was trained on them. This was not predeclared.

| *t* | MiniLM supported / contradicted admitted | DeBERTa-v3 |
|---|---|---|
| 0.50 | 35 / 3 | 64 / 5 |
| 0.70 | 28 / 2 | 56 / 4 |
| 0.90 | 16 / 0 | 41 / 2 |
| 0.95 | 6 / 0 | 32 / 1 |
| 0.98 | 4 / 0 | 22 / 0 |

DeBERTa admits more supported claims at every matched count of admitted contradictions (for
example 22 against 16 at zero, 41 against 28 at two). It also shows that at a fixed threshold
DeBERTa lets through more natural contradictions than MiniLM, so a threshold cannot be carried
across. Both models reject most of these supported claims, which need more domain inference than
Callosum's near-paraphrase pairs.

## 4. Resource costs

Same machine, CPU only, 4 threads, 32-bit weights, one fresh process per model, files already on
local disk. Batched figures are the faster of two passes over the 99 pairs.

| | MiniLM | DeBERTa-v3 | SciFact SciBERT |
|---|---|---|---|
| Parameters | 82.1 M | 184.4 M | 109.9 M |
| Weights on disk | 328 MB | 369 MB | 440 MB |
| Model load | 0.7 s | 1.1 s | 0.7 s |
| Memory after load | 373 MB | 1,147 MB | 791 MB |
| Peak memory | 679 MB | 1,528 MB | 929 MB |
| Warm latency per pair (one at a time), mean / p90 | 99 / 135 ms | 368 / 452 ms | 201 / 297 ms |
| 99 pairs, one at a time | 9.8 s | 36.4 s | 19.9 s |
| 99 pairs, batches of 4 | 9.0 s (11.0 pairs/s) | 24.3 s (4.1 pairs/s) | 17.3 s (5.7 pairs/s) |
| 99 pairs, batches of 8 | 9.3 s | 24.1 s | 17.7 s |
| 99 pairs, batches of 16 | 9.9 s | 26.9 s | 19.6 s |
| Tokens per pair, mean / max | 73 / 160 | 68 / 157 | 69 / 158 |
| Token limit / pairs truncated | 512 / 0 | 512 / 0 | 512 / 0 |

- DeBERTa costs about 3.7 times MiniLM per pair singly and 2.7 times batched, with 2.3 times the
  peak memory. Library import (about 12-14 s, identical for all three) is excluded from load time.
- Tokenisers differ but produce similar lengths here; none of the comparison is affected by
  truncation.
- Batching beyond 4 does not help any of them on this CPU.
- Single machine, single session, small sample: treat ratios as indicative.

**What that means for Ask.** At batched rates, the 9 pairs of the live Q1 run go from about 0.8 s
to about 2.2 s, Q3's 20 pairs from about 1.8 s to about 4.9 s, and a 230-quote question from about
21 s to about 56 s. That is small next to the generation stages in those runs, but it is paid on
every verification, and the extra 850 MB of resident memory matters on a desktop install. Download
size is nearly the same.

## 5. The six questions

1. **Does either model recover the two Q1 findings?** DeBERTa: no (E083 0.024, E090 0.007; MiniLM
   0.009 and 0.062). SciFact scores both 0.998, but it scores the "all mice and all datasets" twin
   (E006) 0.999 as well, so that is not recovery. The Q1 failure is the "our approach" renaming, and
   a better entailment model still, correctly by its own lights, declines to assume the referent.
2. **Does either improve on the five negatives B2 admits?** DeBERTa rejects three (E004 narrowly,
   E078, E092) and still admits two (E009, E064). SciFact admits all five and twenty more.
3. **Do new, scientifically serious errors appear?** DeBERTa: none among the negative controls at
   any threshold of 0.50 or above; one newly admitted meta statement (E036). SciFact: twenty new
   admitted negatives, eight of them negations or reversals.
4. **Is there a useful accuracy/speed tradeoff?** For DeBERTa, plausibly: fewer false admissions
   and more supported claims for roughly three times the verification time and about 850 MB more
   memory. No smaller or faster candidate was tested, so this is not shown to be the smallest model
   that would do it.
5. **Is replacing MiniLM justified now?** No. The benefit rests on 3 of 27 synthetic controls and 7
   net supported pairs, on a set built around MiniLM's behaviour, and it leaves Q1, causal
   overstatement and qualification loss where they were.
6. **What independent validation would be needed?** See section 7.

## 6. Decision table

| | Supported (59) | Negatives (27) | Q1 recovered | New serious errors | Per pair, batched | Peak memory | Usable |
|---|---|---|---|---|---|---|---|
| MiniLM @ 0.90 | 38 | 5 | 0 of 2 | -- | 91 ms | 679 MB | yes (baseline) |
| DeBERTa-v3 @ 0.50 | 45 | 2 | 0 of 2 | 0 | 243 ms | 1,528 MB | yes |
| SciFact SciBERT | 55-56 | 24-25 | not meaningful | 20 | 174 ms | 929 MB | no |

Against the predeclared reading rule, DeBERTa-v3 qualifies as promising: fewer negatives with more
supported claims on held-out at the development-selected point and on the whole set, and no new
high-confidence negative. SciFact fails it outright.

## 7. What a qualification would need

- **Natural negatives.** Real unsupported and contradicted claim/quote pairs from Ask runs, not
  edits of MiniLM-verified claims. This is the largest gap.
- **A fresh, uninspected labelled set**, built without reference to either model's scores, with
  human adjudication of at least a sample.
- **More controls of the kinds both models still pass**: correlation stated as cause, and
  near-synonym substitutions such as trusting/trustworthy. Three and four controls are too few.
- **Threshold chosen on one set and confirmed on another.** The supplementary table shows DeBERTa
  at a given threshold admits more natural contradictions than MiniLM, so 0.50 here is not a
  recommendation.
- **A smaller candidate in the same family** (for example a DeBERTa-v3-small or -xsmall NLI
  checkpoint), since the stated aim is the smallest model that works and only one size was tested.
- **Cost on the target machines**, including cold start and memory alongside the embedding model.
- **An explicit decision that Q1 is out of scope for this change**, since no NLI model tested
  addresses it.

## Limits

- 99 pairs, previously inspected; single-digit counts decide every comparison. No calibration and
  no generalisation is claimed.
- All negatives in the main set are synthetic and derived from MiniLM-verified claims.
- Labels come from one model adjudicator.
- Two analyses were added after scores were seen and are marked as such: the SciFact fidelity check
  and the supplementary table.
- Timing is from one machine in one session.
- "Both models agree" and the per-type table are descriptive, not predeclared.
