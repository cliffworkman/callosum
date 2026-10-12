# Phase 34 -- Referential-context NLI experiment

**Conclusion: TRADEOFF UNRESOLVED.**

Both repairs recover real supported claims, including the two Q1 false negatives. Neither yields a
safe automatic policy on the evidence available:

- **Context restoration** recovers the most (7 supported pairs under B2) but also admits 2 claims
  the adjudicator labelled contradicted, and raises scores for true and false claims at about the
  same rate.
- **Source-faithful reformulation** recovers 3 supported pairs with no new false admission, but
  only by hand, only for one paper, and only because the existing contradiction veto happened to
  catch every wrong-subject control.

Nothing was implemented. No live run and no remote model call was made; only the pinned local NLI
cross-encoder ran.

## 1. Scope and inputs

- Start: `7c80d22d72d6c57f6e74d1e83ece01085d18f0d6`, worktree clean. Tracked changes: this report and
  the lineage entry.
- Inputs: the bakeoff's 99 blinded-adjudicated items (67 natural, 32 synthetic controls), their
  quotes and source chunks. The label file hash matches the bakeoff receipt (`d75e3086...`).
- Working files (gitignored): `.local/phase34-referential-context-20261012/`.
- The baseline score was recomputed for all 99 pairs and reproduces the stored value in every case.

**Labels.** One blinded ChatGPT adjudication pass, not human validation. Class counts follow the
bakeoff's rules: 59 supported, 3 "meta" statements (set aside as in the bakeoff; never admitted
under any condition here), 5 partial, 27 negative (unsupported or contradicted), 5 unresolved.
**Every negative in the packet is a synthetic control.** There are no natural unsupported pairs, so
false-admission behaviour is measured on constructed errors only.

**Disclosures.** The bakeoff's baseline scores and aggregate results were already known. The first
nine labels were displayed while inspecting file formats, before the cohort was defined. The two Q1
cases had been probed by hand in the previous increment.

## 2. Frozen cohort

Frozen by hash before any B or C score was computed and before labels were joined.

**Detector (no model call).** A pair is "referential" when the quote contains a deictic expression
(we / our / this X / it / they ...) **and** the claim, after the bakeoff's mechanical frame strip,
contains a content word that is absent from the quote but present in the sentence immediately
before the quote in its chunk. It fires on 14 of 99 pairs.

**Cohort = detector pairs plus every control of the requested types**: 40 pairs.

| | Supported | Partial | Negative | Unresolved |
|---|---|---|---|---|
| Cohort (40) | 9 | 2 | 26 | 3 |
| Remainder (59) | 50 (+3 meta) | 3 | 1 | 2 |

Controls in the cohort by type: reversed relationship or negation 10, missing qualification 6,
incorrect population 5, referent swap 4, overstated or fabricated relationship 3, attribution 1,
magnitude 1 (detector-selected). Both Q1 cases are in the cohort through the detector, as are
supported pairs from five other papers. The detector was not tuned after freezing; it is noisy
(four of its 14 hits fire on an incidental shared word).

All 99 pairs were scored, so the remainder shows what each repair does outside the cohort.

## 3. Representations

- **A** -- original claim against the exact quote.
- **B** -- original claim against the sentence immediately preceding the quote plus the quote,
  verbatim from the same chunk. One fixed rule. Not applicable for 24 pairs whose quote opens its
  chunk; there B equals A.
- **C** -- the claim with its grammatical subject replaced by the quote's own expression in the
  same grammatical role. Written by hand in one pass under a five-point protocol, frozen before
  scoring. The rule is role-matched and deliberately never asks whether the two expressions name
  the same entity, since that question is the verification judgment itself. Applicable to 17 of the
  40 cohort pairs.

C is not an algorithm. No existing local mechanism produces it.

**Decision rule.** Exact quote and the contradiction veto apply throughout. "Rescue" means the
repair is consulted only when A fails, and a pair that A vetoes as contradicted stays vetoed. Under
C the thing admitted is the original claim, so a passing rewrite of a false claim is a false
admission.

## 4. Paired comparison

Admitted / total. "Current" is similarity >= 0.70 and NLI >= 0.55; B2 is NLI >= 0.90 with no
similarity gate.

**Cohort (40 pairs)**

| Policy | Representation | Supported | Negative | Recovered | New negatives |
|---|---|---|---|---|---|
| Current | A | 1/9 | 4/26 | -- | -- |
| Current | rescue-B | 3/9 | 4/26 | E010, E099 | none (1 unresolved: E080) |
| Current | rescue-C | 1/9 | 4/26 | none | none |
| B2 | A | 3/9 | 5/26 | -- | -- |
| B2 | rescue-B | 7/9 | **7/26** | E010, E083, E090, E099 | **E056, E088** |
| B2 | rescue-C | 6/9 | 5/26 | E021, E083, E090 | none |
| B2 | rescue-B or C | 8/9 | 7/26 | the five above | E056, E088 |

**All 99 pairs**

| Policy | Representation | Supported | Negative | Recovered | Lost |
|---|---|---|---|---|---|
| Current | A | 15/59 | 5/27 | -- | -- |
| Current | rescue-B | 18/59 | 5/27 | 3 | 0 |
| B2 | A | 38/59 | 5/27 | -- | -- |
| B2 | rescue-B | 45/59 | 7/27 | 7 | 0 |
| B2 | rescue-C | 41/59 | 5/27 | 3 | 0 |
| B2 | replace with B | 38/59 | 6/27 | 7 | **7** |

Partial pairs: no change under any condition (all five are already admitted by B2).

**Unique scientific findings recovered** (distinct source quotes, B2): rescue-B 7, rescue-C 2 (E021
and E083 share a quote).

**Overlap.** B and C both recover the two Q1 cases. C alone recovers E021 (context gave 0.846,
under the 0.90 bar). B alone recovers E010 and E099 in the cohort and three pairs outside it.

### The Q1 false negatives

| | A | B | C |
|---|---|---|---|
| E083 "as much as a two-fold reduction" | 0.009 | 0.953 | 0.993 |
| E090 "1.5-2x fewer samples" | 0.062 | 0.972 | 0.985 |

Both are recovered by either repair **under B2 only**. Under the current verifier they stay
rejected, because their claim-to-chunk similarity is 0.22 and 0.67, below the 0.70 gate.

## 5. Newly admitted negatives: complete inventory

**Context restoration, B2 (2 new, both labelled contradicted):**

| Item | Type | A | B | Claim vs source |
|---|---|---|---|---|
| E056 | reversed relationship | 0.691 | 0.959 | Claim: regions recruited "for nonmoral over moral facts". Source: "for moral over nonmoral facts". |
| E088 | missing qualification | 0.888 | 0.924 | Claim: a 2x gain "in all cases". Source: "does not give a substantial gain in all cases". |

In neither case does the added sentence bear on the error. It simply lifts an already-high score
over the bar.

**One near miss that matters.** E006 is the twin of Q1 case E090 with "on all mice and all
datasets" substituted. Context moves it from 0.099 to **0.879**, against 0.972 for the true claim.
It escapes B2 by 0.02. A 0.55 bar without the similarity gate would admit it.

**Context restoration, current verifier:** no new negative. One unresolved item (E080, an
aim-stated-as-finding control the adjudicator called supported) is newly admitted.

**Reformulation:** no new negative under rescue. Three controls pass at 0.99 once their subject is
replaced: E001 ("in vivo experimental results" for "the simulation results"), E071 ("left TPJ" for
"right TPJ") and E095 ("several of the control regions" for "none"). Each is blocked only because
the original claim scores as a contradiction (0.96-1.00) and the existing veto fires. The rewrite
erases the error; the safeguard that catches it is the baseline pair, not the rewrite.

**High-confidence false admissions already present under A** (unchanged by either repair): three
referent swaps (E064, E078, E092) and two fabricated or overstated relationships (E004, E009) pass
B2 at baseline.

## 6. Does context discriminate?

Among pairs where B applies:

| | Score raised by > 0.1 | Score lowered by > 0.1 |
|---|---|---|
| Supported (47) | 10 (21%) | 6 (13%) |
| Negative (21) | 4 (19%) | 2 (10%) |

Context raises supported and unsupported claims at about the same rate. It also lowers some
supported claims: using B in place of A, instead of as a rescue, loses 7 supported pairs under B2,
which reproduces the bakeoff's finding that added context dilutes entailment.

## 7. Cost

Measured locally on CPU, one batch per representation.

| | Pairs | ms per pair | Mean tokens |
|---|---|---|---|
| A | 99 | 123 | 73 |
| B | 75 | 174 | 114 (max 235 of 512) |
| C | 17 | 129 | -- |

Extra NLI calls per 99 pairs for context restoration under B2:

| Scope | Calls | Supported recovered | Negatives admitted |
|---|---|---|---|
| Every pair | 75 | 7 | 2 |
| Only pairs A rejects | 36 | 7 | 2 |
| Only detector pairs A rejects | 11 | 4 | 1 |

Rescue adds roughly 6 seconds per 99 pairs on this machine; detector-gated rescue about 2 seconds.
C's NLI cost is small (13 calls), but its real cost is the rewrite, which has no measured cost
because no mechanism exists to produce it.

## 8. Is selective use justified?

1. **Can the need be detected without a model call?** Partly. The detector caught 4 of the 7
   context recoveries, including both Q1 cases, and cut calls by about 70%. It missed three, and it
   did not screen out a false admission (E088 is a detector hit).
2. **Does minimal context discriminate supported from unsupported?** No. See section 6.
3. **Does reformulation add unique value?** One pair (E021), from the same paper as the Q1 cases.
   Its three recoveries are all the single "our approach" renaming in one source. No generality is
   demonstrated.
4. **Do the improvements survive the negative controls?** Context does not under B2 (two
   contradicted claims admitted, one near miss on the Q1 twin). It does under the current verifier,
   where it also recovers less and does not recover Q1. Reformulation survives only through the
   baseline contradiction veto.
5. **Would selective use reduce inference?** Yes, materially, but it reduces cost without reducing
   the false-admission problem.

No safe automatic identification is demonstrated, so no escalation policy is proposed.

## 9. Generalisation beyond Q1

- **Context:** five of its seven recoveries are not the Q1 cases. Four of those come from two other
  papers, one in each library; the fifth is from the Q1 paper. Two are the same referential mechanism (E010, E099). One is a
  different mechanism altogether: E023's quote is a sentence fragment and the preceding text
  completes it. Two are near misses nudged over the bar (E028, E041). So the effect is real beyond
  Q1, but it is not one mechanism.
- **Reformulation:** not shown to generalise.

## 10. What this leaves

Against the predeclared reading rule (no additional contradicted pair in the cohort), context
restoration fails under B2 and passes under the current verifier; reformulation passes numerically
but cannot be run. The useful combination, recovering Q1's findings without new false admissions,
is not available from either repair as tested.

Two observations may be worth more than either repair:

- The two contradicted claims context lets through were already at 0.69 and 0.89 without it, and
  five negatives pass B2 with no repair at all. The model's weakness on reversed relationships,
  dropped qualifiers and referent swaps is the limiting factor, and neither repair addresses it.
- Reformulation's clean result rests on one asymmetry: a claim with a *wrong* subject scored as a
  contradiction against its quote, while a claim with a *renamed* subject scored neutral. That held
  for all three controls here. Three controls is far too few to rely on, and the constructed
  role-reversal case from the previous increment (neutral at baseline, 0.805 once the subject
  matched) shows the asymmetry is not guaranteed.

## Limits

- 99 labelled pairs; 9 supported pairs in the cohort; conclusions rest on single-digit counts.
- All negatives are synthetic. The packet has no reversed-relationship or causal-overstatement
  control built on a referential pair, so the combination most likely to fail is under-tested.
- Labels come from one model adjudicator.
- Representation C was built by one author by hand. A different rewriter could differ.
- The detector's stop list and stemming were written once and not validated.
