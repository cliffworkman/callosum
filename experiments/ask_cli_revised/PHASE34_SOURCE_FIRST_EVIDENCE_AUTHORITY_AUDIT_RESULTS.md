# Phase 34 -- Source-first evidence authority audit

**Disposition: SOURCE-FIRST INCONCLUSIVE. Recommendation: no-go on implementation now.**

The suspected misallocation is real. On the reviewed route the model-written claim holds the veto
over a quotation, yet nothing that decides scientific content reads the claim. Replacing every claim
with its own quote leaves the v8 scientific map unchanged.

That does not make a source-first pathway worth building yet, for three reasons the preserved
evidence establishes:

1. **No benefit under current semantics.** Handing every exact quote from the Q1 and Q3 runs to the
   unmodified v8 mapper leaves both requirements `missing / not_found`, exactly as live. Q1 fills
   only when source-first is combined with the vocabulary variant that was declined for its false
   admissions.
2. **The claim check does incidental work that nothing downstream replaces.** It currently keeps out
   truncated quotes whose claims were completed from context. Several of those become admissible
   "findings" once the claim check is removed.
3. **The existing architecture cannot express "eligible but not claim-verified".** Nine places
   require `status == "verified"`, one of them in byte-pinned code. An unverified row is refused at
   Layer C, so no displayed answer could be tested without relabelling it.

No case was found in which a false claim gained scientific authority through a source-first path.
The safety case is incomplete rather than failed.

Nothing was implemented. No live run, no model generation, no retrieval. One offline call set to the
pinned local NLI model (section 9). Tracked changes: this report and the lineage entry.

## 1. Starting checkpoint and inspected evidence

| Check | Result |
|---|---|
| Worktree / branch | `ask-060-hier11-recpm3-citefix-20260929T212442Z` / `experiment/ask-060-...` |
| HEAD at start | `0fa578fd28002b9f82508f3f99d38756fe4f55bd`, worktree clean |
| CI | the only workflow on this branch (CodeQL) succeeded for that commit |
| Preserved inputs | 153 files hashed before and after (pilot runs, pilot library, reviewed inputs, bakeoff, the three later Phase 34 work directories): 0 changed |
| Wiring | the audit's reconstruction of each live ledger equals the sealed rows; its ownership index equals the recorded one; the v8 map computed from each ledger file equals the live `17_sufficiency_map.json` exactly |

Read: the five Phase 34 result reports named in the brief, `CREDIT-THE-LINEAGE.md`, and the code
cited by file and line below. Evidence used: the B2 pilot's Q1 and Q3 runs (all 9 and 20 formed
claims, sealed or not), the bakeoff's 99 adjudicated pairs and its frozen table of 288 unique scored
pairs (230 unique quotes), and the Phase 28 q_aib sufficiency map.

**Labels.** One blinded ChatGPT adjudication pass, not independent human review. Every negative is a
synthetic control: a wrong claim written against a real quote.

Working files (gitignored): `.local/phase34-source-first-20261012/`.

## 2. The existing authority pathway

| Stage | Code | Reads the claim | Reads the quote |
|---|---|---|---|
| Retrieval, context growth | `retrieval.py` | -- | chunks |
| Span exposure | `propositions._candidate_spans` | -- | exact sentence-split substrings; bibliographic and structural chunk types dropped |
| Span selection | `qwen.select_evidence` | -- | yes (model picks span ids) |
| Claim formation | `qwen.form_claim` (`qwen.py:508`) | writes it, from the span plus surrounding context | yes |
| Verification | `LocalCitationVerifier.verify_many` | embedding against the chunk; NLI hypothesis | exact-substring check; NLI premise |
| Ledger membership | `stages.source_verified` (`stages.py:109`) | through the status only | -- |
| Coverage attachment | `stages.run_responsiveness`, `run_coverage_audit` | yes | coverage audit only |
| Recovery planning | `stages.run_recovery_plan` | yes | -- |
| Ownership context | `ownership_context.build_context_index` | -- | yes |
| Units for mapping | `overview_evidence.build_units`, `sufficiency_diagnostic` | -- | yes; a unit is the passage, scoped to children by attachment |
| v8 mapping, support policy | `sufficiency_mapping` | -- | yes |
| Relation witness | `relation_witness`, `compatible_witness` | -- | yes |
| Layer C projection and display | `layerc_projection`, `_layerc_*`, `layerc_presentation` | -- | yes |
| Plan and rendering | `answer_plan/*` | one guard that the claim is *not* what is printed (`render.py:347`) | yes |

What happens when verification fails: the record stays in the run's proposition and verification
logs and is excluded from the ledger. Its quote remains in `evidence_spans`, which lists every
exposed span, but no later stage looks there for evidence.

**Observed, not assumed.** The mapper's independence from the claim was tested: a ledger with each
`proposition_text` replaced by its quote gives a map identical to the original apart from input
hashes, for Q1 and Q3, under current and experimental recognition.

## 3. Where the generated claim has veto or routing influence

| Influence | Where | Kind |
|---|---|---|
| The model returns an empty claim and the span is dropped | `propositions.py:241` | veto (model abstention) |
| Claim-to-chunk similarity and claim-against-quote NLI set the status | `verification.py`, consumed at `stages.py:114` | veto |
| Per-claim responsiveness: the model sees the claim alone | `stages.py:187` | routing |
| Coverage audit: the model sees the claim, then the quote, under the heading "Verified propositions" | `supervisor_prompts.py:32` | routing; decides which child's mapper ever sees the passage |
| Recovery planning sees claims only | `supervisor_prompts.py:49` | routing (search effort) |
| Record identity and de-duplication use the claim text | `stages.py:133`, `propositions.py:250` | bookkeeping |
| The non-reviewed renderers print the claim as the answer | `ledger_renderer.py:74`, overview path | **content** |

The last row matters. Only the reviewed route replaces the ledger rendering with Layer C output
(`e2e.py:1011-1013`). On the other routes the claim is the displayed text and the verifier is the
only semantic check on it. Anything said below about claim text being inert applies to the reviewed
route alone.

**Does the NLI check supply protection not enforced downstream?** Three things, on the reviewed
route:

- It limits which claims the coverage model reads. A false claim that passes can still steer
  attachment; a false claim that fails cannot. This protection is partial already: three
  referent-swap controls pass B2 and the default rule.
- It filters quotes whose claim says more than the quote does. That includes truncated spans
  (section 6).
- It bounds ledger size (section 9).

It does not protect answer wording, relationships or citations on that route. Those are decided
from the quote.

## 4. The three candidate models

| | A. Claim-first (today) | B. Source-eligible, claim kept | C. Source-grounded proposition |
|---|---|---|---|
| What enters the ledger | quotes whose claim verifies | every exact quote, with its unverified claim | every exact quote, with the quote as its own proposition |
| Expressible today | yes | no. Nine status checks (`stages.py:114`, `relation_witness.py:81`, `layerc_projection.py:149`, `_layerc_validation.py:310`, `_layerc_values.py:54`, `ledger_renderer.py:28`, `e2e_checks.py:283`, `coverage.py:14`, `request_contract.py:124`) | partly. A precedent exists: `contract_directed/overview_bridge.py` builds rows with `proposition_text` equal to the quote and `nli_entailment_checked: False`, and needed its own renderer because the ledger gate demands `verified` |
| Claim influence on routing | verified claims only | grows: unverified claims shown to the coverage model as "Verified propositions" | removed by construction |
| Claim reaches answer text | no (reviewed route); yes (other routes) | no / yes, unverified | no on any route; the "claim" is source text |
| Loses | supported findings whose claim renames the subject | the claim check entirely, while still displaying claims | the paraphrase's resolved referents, which the coverage model may need to judge relevance |
| New inference | -- | none | none; claim formation and NLI could be dropped for these rows |

B is not viable as stated. It keeps the unverified claim in every place a model or a non-reviewed
renderer reads it. Removing the claim from those places turns B into C.

C cannot simply be routed through the unchanged verifier either. Scoring each of the 230 unique
quotes as a claim against itself, 206 reach 0.90 and 224 reach 0.55; the lowest is 0.011
(statistics-dense sentences). The default rule would add a similarity failure, since a single
sentence is rarely close to its whole chunk. A verbatim proposition is true by construction, so it
needs an admission class of its own, and that class meets the same status checks as B.

A simpler alternative surfaced from the code: keep claim-first and have claim formation retain the
source's own referring expressions. The previous experiment's reformulation arm is the evidence for
it (three recoveries, no new false admission, protected only by the contradiction veto). It changes
a generation prompt, which is out of bounds here.

## 5. Results on supported source evidence

All rows below are **hypothetical offline counterfactuals** at the mapper boundary. No status was
rewritten; rows the verifier called `weak` stayed `weak`.

**Q1** (9 formed claims; 5 sealed under B2; 4 excluded, all exact quotes):

| Excluded quote (paper 83) | NLI | Current v8 | With the declined vocabulary variant |
|---|---|---|---|
| "We demonstrate our approach on both real and synthetic data, obtaining in some cases as much as a two-fold reduction ..." | 0.009 | not recognised | admissible; this-study result; **fills the requirement** |
| "In particular, on Mouse 1 and both datasets for Mouse 3, we observe a gain of between 1.5-2x over baselines ..." | 0.062 | not recognised | admissible; this-study result |
| "... our active learning approach yields a non-trivial gain over both baseline approaches." | 0.394 | not recognised | not recognised ("yields" is in neither list) |
| "This demonstrates the effectiveness of our active learning procedure ..." | 0.020 | not recognised | recognised; excluded, owner unresolved |

Requirement state: `missing / not_found` under current v8 with all nine quotes; `filled` with the
variant.

**Q3** (20 claim events; 12 unique sealed; 5 more exact quotes): current v8 stays `missing`. With
the variant it is `partially_filled` by the sentence already known from the mapping audit plus the
two-fold sentence. The other four additions (a sentence fragment, "This section presents a practical
framework ...", "By leveraging this alternating scheme ...", "Here, we develop methods ...") form no
candidate under either vocabulary.

**The q_aib history** (unit-level binder, free `finding` role; an indicator, not the q_aib map):

| Quotes | Count | Admissible, current v8 | Admissible, variant |
|---|---|---|---|
| Admitted by B2 | 114 | 9 | 12 |
| Exact but not admitted | 116 | 7 | 12 |

So under *current* semantics, source-first would expose seven more result sentences on q_aib. Four
are complete this-study results (for example "we observed a spatial and functional dissociation
...", "Spearman correlations revealed greater proportionality was associated with attractiveness
..."). Two are truncated and one reports prior research (section 6). In the Phase 28 map, three of the seven were
retrieved for a child whose requirement is already filled, two for a child with one filled and one
partially filled requirement, and two for a child that is only partially filled. The q_aib map itself was not recomputed, because its roles use recorded model
nominations.

**The 99 adjudicated pairs.** The quote of 2 pairs labelled supported is admissible under current v8,
and of no negative. With the variant: 7 supported, 3 negative, 1 unresolved (section 6).

## 6. Results on unsupported and contradictory controls

A control is a false claim on a real quote. Under a source-first design the false claim is not what
would be admitted, so the right question is what the mapper does with the quote.

| Control | Error in the claim | Verifier | Mapper on the quote (current v8) |
|---|---|---|---|
| E009 | "cause" for "correlated with" | default rejects, B2 admits | recognised as a result; excluded, owner unresolved. With source context the pilot found it fills a role value, gets no relation witness and is not displayed |
| E004 | added population | both admit | recognised; excluded, owner unresolved |
| E078 | referent swap | both admit | recognised; excluded, owner unresolved |
| E064, E092 | referent swaps | both admit | not recognised |
| E056, E088 | reversed relationship; dropped qualifier | both reject | not recognised |
| E006 | "all mice and all datasets" | both reject | not recognised. Variant: admissible, and correctly so; the quote says "Mouse 1 and both datasets for Mouse 3" |
| E080 | aim stated as finding | both reject | not recognised |

No control's false wording reached the map, in any condition. That follows from section 2 and was
confirmed by the identical-map test.

What the counterfactual did expose is in the quotes, not the claims:

- **Truncated quotes become findings.** "Our results showed that the amplification of emotional
  contagion was correlated with the involvement of bilateral" and "We found increased activation
  restricted to the bilateral fusiform gyri and left amygdala (Table S12A, online only), and no
  areas of" are both admissible under current v8. Each was excluded today because the model's claim
  completed the sentence from context ("bilateral brain regions") and NLI rejected the completion.
  With the variant, two more: "... is largely absent among Hadza without exposure to" and "This
  study provides evidence against the hypothesis that the anomalous-is-bad stereotype is a".
- **Malformed spans are over-represented among the excluded quotes.** By the project's own passage
  flags, 14 of 116 are fragments and 20 start mid-sentence, against 8 and 6 of the 114 that B2
  admits.
- **Prior work is admissible as a finding.** "Prior research has found that interfering with
  activity in RTPJ can impair mental state reasoning ..." passes the default policy as
  attributed-external under current v8.
- **A degenerate span under the variant.** For E064 and E091 the admissible "finding" is the three
  words "This analysis shows that". This is a defect of the variant, already not promoted.

Why the 116 were excluded: for 72 the best claim scored under 0.10; 15 scored 0.10-0.55; 15 scored
0.55-0.90; 14 were vetoed as contradicted.

## 7. Scientific authority and citation risks

**1. Fabricated relationships.** A generated causal claim cannot make a correlational quote satisfy
a relationship requirement: the witness reads the quote, and E009 was not witnessed. The separate
weakness stands unchanged under every model: the contract vocabulary has no causal relation type, so
a causally worded question can be answered with an associational quote.

**2. Referential substitution.** Yes, an erroneous referent can influence obligation attachment
today while the quote stays correct. The responsiveness role reads the claim alone and the coverage
audit reads it first. This path has never been exercised with a live model and a false claim. Model
B widens it; model C closes it.

**3. Qualification preservation.** This is the most concrete risk found. The display envelope is the
matched clause, not the sentence. Observed in the mapping audit's route probe: the Q3 sentence was
displayed without its opening "Using neural population responses to photostimulation in mouse motor
cortex,". For Q1's 1.5-2x sentence the candidate span starts at "we observe", so the scope "on Mouse
1 and both datasets for Mouse 3" would be dropped. That is the E006 error, produced by omission from
authentic text. It is a prediction from the candidate span, not a rendered result. The two-fold
sentence keeps "in some cases". This weakness is independent of source-first, but Q1's benefit would
flow straight through it.

**4. Attribution.** A result with an unresolved owner is excluded by the default policy, and that
rule did its job on every recognised control. A result explicitly attributed to others is admitted
as attributed-external. Under the variant, one sub-span ("implicated specific neuroanatomic
structures ...") is admissible without its attributing subject "Recent studies have".

**5. Irrelevant authentic quotations.** The `finding` role carries no target terms, so relevance
rests entirely on coverage attachment, which reads the claim. In Q1 and Q3 every non-finding
addition was kept out, but only because the result vocabulary did not match it. No relevance check
on the quote itself exists.

**6. Legitimate evidence recovery.** Theoretical availability: yes, both Q1 findings would reach the
mapper. Recognition by the current mapper: no. Recognition with the variant: yes, both, and the
requirement fills. Displayed, cited answer: untested, and not authentically testable, because Layer
C refuses the ledger (`ProjectionIntegrityError: unverified sealed proposition`) and the relation
witness returns inadmissible for each added row.

## 8. Would Q1 and Q3 actually benefit

| | Current v8 | With the declined variant |
|---|---|---|
| Q1 | no change (demonstrated at the mapper) | requirement fills from the two-fold sentence, qualified "in some cases" (hypothetical) |
| Q3 | no change (demonstrated at the mapper) | one more sentence from paper 83; still no finding from paper 82, so no two-study synthesis (hypothetical) |

Source-first on its own improves candidate counts and nothing else for these two questions. The
binding constraint for Q1 is the pair: admission and recognition. Either alone leaves it empty.

## 9. Incremental runtime and engineering cost

| | B | C |
|---|---|---|
| New inference calls | none | none |
| Calls that could be removed | none | claim formation (9 calls, 15.5 s in Q1; 20 calls, 31.5 s in Q3) and the NLI pass, if propositions are verbatim |
| Ledger size | Q1 5 to 9; Q3 12 to 17; q_aib unique quotes 114 to 230 (64 under the default rule) | same |
| Knock-on cost | coverage prompts grow with the ledger (2.8-5.3k characters now; a prompt that would not fit is refused, not truncated) | same; the mapper and ownership work are deterministic |
| Code boundaries | admission in `propositions.py` / `stages.py`; nine status checks | the same, plus the coverage prompt wording |
| Tests | negative controls for truncation, attribution and scope before any admission | the same, plus a live-model attachment check |

The analysis itself cost one offline batch of 230 NLI pairs.

## 10. Historical and versioning implications

- No semantics version change is implied: the mapper would be unchanged and reads the same field.
- Recorded runs, replays and qualifications are keyed to their sealed inputs and are unaffected. New
  runs would produce different ledgers and so different sealed hashes.
- `relation_witness.py`, `overview_evidence.py`, `sufficiency_diagnostic.py`,
  `sufficiency_mapping.py`, `ownership_context.py` and `support_policy.py` are byte-pinned in the
  producer code manifest. A distinct "eligible" status would have to pass
  `relation_witness.is_admissible`, which means editing pinned code and re-enrolling the producer.
- The alternative, labelling a verbatim row `verified`, avoids the pinned edit but changes what the
  word means in the ledger. That is a decision, not an implementation detail.
- Either way there would be two admission classes feeding one ledger. That is one authority path
  with two entrances, not a second authority system, but it needs to be visible in every row.

## 11. Smallest defensible change

None is recommended now.

If this is pursued later, the smallest form consistent with the findings is a verbatim-proposition
fallback, opt-in like B2 and confined to the reviewed route: a quote whose claim fails is carried as
its own proposition, marked as such in provenance, with the claim discarded. It should not be built
before these exist, in this order:

1. A decision on result recognition. Without it the fallback changes no answer to Q1 or Q3.
2. A guard that keeps truncated and mid-sentence spans out of result roles. NLI does this today by
   accident.
3. A display rule that keeps scope-setting phrases with the clause they qualify.
4. One bounded check, needing a handful of live coverage-model calls and so separate authorization,
   of whether verbatim propositions are still attached to the right obligation without the
   paraphrase.

## 12. Decision table

| Criterion for a favourable recommendation | Finding | Basis |
|---|---|---|
| Makes supported evidence available that is excluded unnecessarily | yes | observed: 4 Q1 quotes, 5 Q3 quotes, 116 q_aib quotes; 7 admissible result sentences under current v8 |
| Does not treat quote validity as scientific authority | yes in the mapper | observed: maps identical with claims replaced; non-findings excluded |
| Defensible mechanism against unsupported relationships, attribution errors, misleading qualifications | **incomplete** | relationships held (observed); truncation and prior-work admission observed; scope loss predicted |
| Ownership, witnessing and citation protections stay enforceable | only by relabelling or editing pinned code | observed: Layer C and the witness refuse unverified rows |
| Improves research-question coverage, not just counts | **not shown** | observed: Q1 and Q3 unchanged under current v8; hypothetical gain only with the declined variant; q_aib map not recomputed |
| Cost proportionate | yes if the above held | no new inference; ledger roughly doubles |

Two of six criteria are unmet on the preserved evidence, and one more is met only by a labelling
decision. Hence INCONCLUSIVE and no-go.

## Limits

- Everything past the mapper is static reading or carried over from earlier probes; no unverified
  row was pushed through Layer C, by design.
- Attachment was scripted to tag every row responsive, as the live runs did. Whether a coverage
  model would attach the added quotes is unknown.
- The q_aib figures are unit-level with a free result role, not that question's own contract.
- "Complete result", "truncated" and "prior research" for the q_aib sentences are the auditor's
  reading, not adjudicated labels.
- Bakeoff labels are one model adjudication. All negatives are synthetic.
- Two papers for Q1/Q3; one question on a second library.
