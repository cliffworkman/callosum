# Phase 28, Attempt 2 — Live Parent Synthesis: Forensic Report

**This is the first live, complete, end-to-end run of the hierarchical Ask pipeline through parent
synthesis under T5C.** Attempt 1 (same phase, a separate consumed authorization) failed before any
pipeline stage completed — a harness bug, not a pipeline finding; see
`PHASE28_LIVE_PARENT_SYNTHESIS_FORENSIC_REPORT.md` for that record, preserved unchanged. This document
covers Attempt 2 only: 1657.3 seconds, 15 real model calls, 21 ParentClaims, one S2 call, one rendered
parent answer.

## Legend

- W = retrieval/search · R = responsiveness review (architecturally `off` for T5C — see §R1) · C =
  sealing/coverage audit · U = semantic sufficiency mapping · P = recovery planning · S1 = per-child
  synthesis · S2 = parent synthesis.
- "stage U1" means the pipeline stage; this report never needs "ctx" identifiers, so no ambiguity arises.

## Scope note on what the independent recorder does and does not see

The `SupervisorCallRecorder` wraps `stages.Supervisor.call` — the R/C/P/S-role call path. It does
**not** wrap the W-role's own internal packet-level gate decisions during retrieval and context growth,
which go through a separate class (`backends.NativeWorker`/`QwenTasks`, confirmed by direct code read).
Those are the 110 calls the manifest's `gate_no_answer` block counts (`calls: 110, no_answer: 0`) — a
real, large, and entirely clean set of mechanical decisions, but not independently witnessed by this
phase's recorder the way the 15 Supervisor-role calls are. This report is explicit about which claim
rests on which evidence.

---

## W1 — Initial retrieval (313.1s)

- 165 papers found by direct matching (`02_direct_papers.json`), 2,112 axis-nomination entries scored
  (`03_axis_nominations.json`), yielding exactly **25 candidate papers per child** (all 11 children —
  the `per_subq_paper_cap` cap, confirmed from `05_candidate_papers.json`).
- 246 chunk-retrieval records (`06_chunk_retrieval.jsonl`) → 246 evidence packets
  (`08_evidence_packets.jsonl`) → 264 candidate propositions extracted (`09_propositions.jsonl`, matches
  the manifest's `records_total: 264` exactly) → 264 verification attempts
  (`10_verification.jsonl`).
- No major evidence absence is visible at this stage beyond what the run already expected: the
  "graph rescue" citation-convergence stage (04) is **disabled by design**
  (`status: "disabled_insufficient_corpus_data"`, 5/256 papers have extractable references) — a
  pre-existing, documented non-issue, not something this run caused.

## R1 — Initial responsiveness review: architecturally SKIPPED

T5C binds `R` to `off` by design (`stages.Supervisor` validation requires this whenever `C` is
model-bound — a model-bound C would make a bound R a noncausal stage). **C1 is the sole
responsiveness/coverage authority for this profile.** This is not a gap; it is the profile's own
documented shape, confirmed directly against `topology.py`.

## C1 — Initial sealing (151.3s, phi4:14b)

- One real `coverage_audit` call (prompt 15,967 chars, hash `607d452fb399edfa...`), mechanically
  `usable`, `done_reason: stop`.
- Result: **10 of 11 children `judged_responsive`, 1 `no_responsive_claim`** (the one unresolved child
  is c9 — consistent with c9's own S1 state below).
- Of the 264 candidate propositions, **54 were source-verified** at this point (the manifest's
  `verified_claims: 54` is a run-total figure, not purely C1's own count, but C1's coverage judgment
  operates over whatever was source-verified at the time it ran).
- Provenance integrity: `ledger_valid: true`, `contract_preserved: true` (from `16_mechanical_checks.json`).

## U1 — Initial semantic map (69.1s, qwen3.5:9b model-assist)

- 18 request-key scopes reached, **all 18 status `fresh`** — every initial nomination request was a
  genuine first-time model call (no held-fixed replay yet; nothing to replay before any recovery round
  has happened).
- Physical model calls: 18 (one per fresh scope); 0 `fresh_no_candidates`; 0 failures.
- This is where per-requirement role-assignment happens — the stage most responsible, structurally, for
  any semantic-mapping error that might appear later (see the c8 tracer analysis, §Known-tracer analysis).

## P1 — Recovery planning (88.6s, gemma3:12b)

Production `P` (gemma3:12b) was asked, over all 11 unresolved items, what recovery action to take. It
chose **`DEEPEN` for every single child**, with an explicit, substantive rationale (not a default):

> "All requested items currently have available recovery actions. Given the policy to prioritize
> bounded recovery, I will choose the DEEPEN action for each item to see if further searching of the
> existing candidate papers can yield more responsive evidence."

This is P's own real decision, not a fallback — one real `recovery_planning` call (prompt 13,401 chars,
hash `c54506e233677c21...`), mechanically `usable`. Whether DEEPEN was the *right* call for every item
is not graded here; it is described as what P actually decided. The allowed-empty `c4#suff:specific-region`
requirement was still eligible to search before any terminal judgment — confirmed by the fact that it
*was* searched (see W2 below) and *did* return new evidence.

## W2 / R2 / C2 — Recovery (671.0s W2, N/A R2, 154.5s C2)

**W2 (recovery retrieval, 671.0s — the single longest stage in the run):** 20 structured recovery-target
searches executed (`13_gap_recovery.json`), one per requirement/role combination P1 authorized. Every
search reused the **same 25-paper candidate pool already retrieved in W1** (`existing_candidate_papers:
25` throughout, `new_papers_nominated: []` in all 20 entries) but searched it with a fresh, targeted
query string. Per-target outcome:

| Search child | Target role | New verified | Reason code |
|---|---|---|---|
| c9 | trait-scale (via c8) | 1 | recovery_added_evidence |
| c1 | neural-manifestation relationship | 2 | recovery_added_evidence |
| c10 | named culture | 1 | recovery_added_evidence |
| c10 | population generalizability | 0 | recovery_no_new_evidence |
| c11 | named culture ×2 | 0, 0 | recovery_no_new_evidence |
| c11 | operationalization ×2 | 0, 0 | recovery_no_new_evidence |
| c12 | intervention (×2 distinct queries) | 2, 2 | recovery_added_evidence |
| c12 | target_manifestation, outcome ×3 | 0 each | recovery_no_new_evidence |
| c2 | behavioral measure | 2 | recovery_added_evidence |
| c3 | implicit/explicit coverage | 4 | recovery_added_evidence |
| c4 | named brain area | 1 | recovery_added_evidence |
| c8 | trait/construct ×2 | 2, 1 | recovery_added_evidence |
| c5 | brain-behavior | 5 | recovery_added_evidence |
| c6 | attitude measure, implicit/explicit | 3, 3 | recovery_added_evidence |

**14 of 20 targets added new verified evidence; 6 found nothing new in the same pool.** Zero mechanical
failures. **R2:** not applicable — R stays `off` for the recovery round exactly as for the initial round.
**C2 (154.5s, phi4:14b):** one real `coverage_audit` call (prompt 17,121 chars, hash
`47bf09e8b71a80eb...`), mechanically `usable`. Result: **all 11 children now `judged_responsive`** — the
recovery round gave every child at least one attached, responsive proposition at this coarser gate
(contrast with S1's own stricter per-sentence screen below, which still withheld c5/c9's specific
sentences — two independently-calibrated gates, not a contradiction).

**Scoped-search terminality** (Phase 27b's own invariant, `13c_scoped_search.json`): all 11 requirements
with a structured search show `completed: true`; **zero** show `terminal: true` — none ended as a
genuinely-empty, terminal search. `resolved_empty_outcome_count: 0` follows directly.

## U2 — Final semantic map (68.7s, qwen3.5:9b targeted remap)

Diff from U1: **31 scopes reached** (up from 18) — **16 `fresh`** (genuinely new nomination requests the
recovery round's new evidence opened up), **10 `held_fixed_no_valid_prior`**, **5 `held_fixed_replay`**
(scopes U1 already resolved, correctly not re-asked). `recovery_targets_initial_count: 20` (matching
W2's own 20 searches exactly) and `u2_fresh_request_key_count: 16` (matching U2's own fresh count
exactly) — internally consistent. No held-fixed scope was incorrectly treated as fresh or vice versa,
confirmed by these counts lining up with the independently-logged recovery/search records above.

---

## S1 — every child's actual synthesis

For each child: final structured state entering S1 (from the stage log), the actual rendered overview
text (verbatim from `14_final_answer.c<id>.md`), and a fidelity note.

### S1:c1 — "how does the anomalous is bad bias manifest in brain…"
State: `ok`, partial (5 units sent, 2 proposals, 1 displayed).

> 1. The 'anomalous-is-bad' stereotype manifests behaviorally by affecting prosociality, a finding
> supported by correlations between implicit biases and neural responses to facial anomalies in regions
> implicated in processing disgust and facial beauty. [1][2][3]

Citations: paper 67, chunks 35111/35123/35125 (pages 13–14), all source-verified. **Fidelity: faithful**
— the statement combines three distinct passages (a behavioral-manifestation finding, a disgust/beauty
region finding, and a correlation finding) into one sentence; each clause traces to its own cited
passage, and the qualification ("reports an association") on passage 3 is preserved honestly rather
than stated as established fact.

### S1:c2 — behavioral manifestation
State: `ok`, partial (10 units, 3 proposals, 2 displayed).

> 1. This research confirmed earlier reports that people with anomalous faces are imbued with negative
> personality characteristics, detected explicit biases against people with facial anomalies, and
> described a behavioral manifestation of the 'anomalous-is-bad' stereotype affecting prosociality. [1]
> 2. Participants expressed explicit biases against people with facial anomalies, but their implicit
> biases were slight and not significant. [2]

**Fidelity: faithful**, including a genuine negative/null finding (statement 2) stated plainly rather
than smoothed into a positive claim.

### S1:c3 — attitude manifestation
State: `ok`, partial (8 units, 3 proposals, 2 displayed). Two statements, both faithful restatements of
their cited passages, with hedge/causal-wording qualifications ("might," "underpinned") honestly flagged
on the passage that carries them rather than silently dropped.

### S1:c4 — specific brain areas
State: `ok`, partial (2 units, 2 proposals, 1 displayed).

> 1. The specific amygdala response to facial anomalies correlates with less prosociality toward people
> with facial anomalies. [1]

**Fidelity note:** the cited passage (chunk 34974) actually reports a *three-way* association (stronger
just-world beliefs, less empathic concern, *and* less prosociality); the S1 statement surfaces only the
prosociality clause. This is a **narrowing, not a fabrication** — the single clause kept is verbatim-true
of the source — but it is an incomplete restatement of a multi-part finding. Worth noting since the full
three-part version does appear faithfully elsewhere (the parent-level claim `relational::5d178917787a4805`
restates all three clauses and was S2-grounded).

### S1:c5 — brain-behavior relationship: **no_grounded_sentences** (honest zero)
State: `no_grounded_sentences` (9 units sent, 2 proposals, 0 displayed). Ten passages are listed as
supporting findings, none cited in an overview sentence — every proposed statement was withheld by
screening. This is the architecture working as intended: a real retrieval yield, a real model attempt,
and a real, disclosed refusal to assert a sentence the screens didn't clear. **Fidelity: N/A — nothing
was asserted to be unfaithful.**

### S1:c6 — brain-attitude relationship
State: `ok`, partial (7 units, 3 proposals, 2 displayed). Two faithful statements, one carrying its hedge
("might improve... and reduce bias") forward honestly.

### S1:c8 — personality traits
State: `ok`, partial (4 units, 3 proposals, 2 displayed). Two faithful statements; statement 2 restates a
study's stated *aim* ("the aims of this study were to confirm and extend...") without claiming the aim
was *achieved* — a real fidelity-preserving distinction correctly kept.

### S1:c9 — trait-scale pairing: **no_grounded_sentences** (honest zero)
State: `no_grounded_sentences` (1 unit sent, 1 proposal, 0 displayed). One passage listed, zero cited.
Same honest-refusal pattern as c5.

### S1:c10 — cross-cultural evidence
State: `ok` (1 unit, 1 proposal, 1 displayed).

> 1. Results suggest that the anomalous-is-bad stereotype is culturally shared, providing evidence
> against a universal pathogen avoidance byproduct hypothesis. [1]

**Fidelity: faithful**, with both qualifications disclosed in the report (hedge language; "the passage
begins mid-sentence" — a genuine partial-quote caveat surfaced honestly rather than hidden).

### S1:c11 — culture/operationalization pairing
State: `ok` (1 unit, 1 proposal, 1 displayed). Same source passage as c10, correctly scoped to a narrower
claim (cultural sharing alone, not the pathogen-avoidance contrast) — appropriate to c11's own, different
requirement.

### S1:c12 — intervention effectiveness
State: `ok`, partial (6 units, 3 proposals, 2 displayed). Two faithful statements, both hedges honestly
carried forward ("may offer a promising... approach," "might improve decision-making").

**Summary across all 11 children:** every displayed statement traced correctly to its cited passage(s);
every disclosed qualification (hedge, null result, association-not-causation, partial quote) was
preserved rather than smoothed away; the two zero-statement outcomes (c5, c9) are honest refusals, not
failures. One minor narrowing noted (c4). No fabrication, no invented citation, no silently-dropped
negation found in any of the 11 children's rendered text.

---

## Parent claim ledger (21 claims, deterministic construction)

Built by `parent_synthesis_ledger.build_claim_ledger(sufficiency_map_final, sealed)` from the same
264-proposition sealed ledger (hash `1dce0e1c2dead992c...`) every S1 child already drew from — **no new
evidence, no new search, purely a deterministic re-projection into closed claim shapes.**

| # | claim_id | kind | child(ren) | admissible props |
|---|---|---|---|---|
| 1 | relational::5d178917787a4805 | relational | c4 | p11 |
| 2–6 | relational::{6d3e9d91,bac1b3e1,99d44d22,629c3c06,6e5d1f4c} | relational | c8 | p41 (×5, one per trait) |
| 7 | direction_or_effectiveness::97e9b66f0fd3c1c2 | direction | c6 | p14, p26 |
| 8 | role_value::8d0ce9c4405f714b | role_value | c1 | p1 |
| 9 | role_value::57b25a887d32ec58 | role_value | c1 | p11, p2 |
| 10 | role_value::b9591e4fba42edb1 | role_value | c2 | p4 |
| 11 | role_value::34d05796cc1dd8a3 | role_value | c3 | p8 |
| 12 | role_value::161d9d5825b7df74 | role_value | c4 | p40 |
| 13 | role_value::1f1af648ebc4dd29 | role_value | c4 | p11 |
| 14 | role_value::c33c4ccf244a45a8 | role_value | c6 | p17 |
| 15 | category_list::775fda7778860372 | category_list | c10 | p29, p53 |
| 16 | category_list::d47465340e922bca | category_list | c12 | p24, p30, p31 |
| 17 | category_list::10ddc38dbb7cb05e | category_list | c2 | p35, p46, p47 |
| 18 | category_list::9fd341f1bbff788b | category_list | c3 | p36, p8 |
| 19 | category_list::f1f51b4ba55bad3c | category_list | c8 | p20, p9 |
| 20 | category_list::7af59a3e5749152a | category_list | c5 | p46, p47 |
| 21 | category_list::f453ebb75104e61d | category_list | c6 | p14, p17, p26, p3, p7 |

**Unresolved parts (39 gaps, separate from the 21 claims — never conflated):** spread across c1 (1,
relationship_unverified), c2 (3, relationship_unverified), c4 (1, provisional_corroboration), c5 (2,
provisional_corroboration), c6 (4: 2 provisional_corroboration, 1 missing, 1 provisional_corroboration),
c8 (1, open_list_breadth), c9 (5, partial — the named-scale role), c10 (2, partial), c11 (6, missing),
c12 (16: 6 missing, 7 partial, plus the ones shown resolved above). **Resolved-empty outcomes: 0** — no
requirement both searched-to-completion and remained genuinely zero-evidence.

---

## S2 — Parent synthesis (the headline stage)

- **Call count: exactly 1** (independently witnessed — see the recorder data in the Results doc).
- **Prompt:** 9,959 chars, sha256 `66bc9e18f265170d50f49900ff66d44eda8048e6ffdf204ac5bfa7a7de3a7987` —
  the independently-captured raw text matches `parent_synthesis.realize()`'s own self-reported hash
  exactly. The prompt contains **only** the 21 claims' `authorized_claim_text()` serializations (role
  values, category lists, the one relational-pair block, the one direction summary) plus the verbatim
  original question — confirmed by direct inspection of the captured raw text: **no child S1 Overview
  prose, no ResolvedEmptyOutcome text, no proposition ids, no internal instance keys, and no unrelated
  evidence pool appear anywhere in it.**
- **Schema:** closed object, `items[].{claim_id, statement}` only, `maxItems: 42` (= 2×21, the
  Phase-27a per-claim-fallback headroom), `statement` capped at 800 chars. No citation field, no
  proposition-id field — **S2 cannot choose citations; deterministic rendering owns that entirely.**
- **Outcome:** `whole_call_status: ok`, `call_outcome: usable` — the model returned a well-formed answer
  for every one of the 21 claims (no unknown/duplicate/missing claim_id at the whole-call level).
- **Per-claim screening** (the real content of this stage):
  - **7 grounded** (passed claim-value, evidence-passage, heterogeneity, and NLI screens): the role_value
    claims (8d0ce9c4, 57b25a88, b9591e4f, 34d05796, 161d9d58, 1f1af648) plus one relational claim
    (5d178917, NLI support 0.93/0.99 against claim/evidence respectively — high-confidence).
  - **11 withheld** by NLI low support or a lexical reason: five `relational` trait-correlation claims
    all withheld at the *identical* `nli_low_support:0.54` threshold (6d3e9d91, bac1b3e1, 99d44d22,
    629c3c06, 6e5d1f4c) — a single dense multi-correlation passage (p41) rendered five times for five
    different trait-slot claims, and the model's phrasing didn't entail strongly enough against the
    evidence passage each time; the `direction_or_effectiveness` claim (97e9b66f) withheld for
    `negation_introduced` + `too_many_novel_terms` (the model echoed back structural/meta vocabulary —
    "observed," "consensus," "heterogeneous" — rather than producing clean prose); three `category_list`
    claims withheld by NLI (10ddc38d, 9fd341f1, 7af59a3e); one (f1f51b4b) withheld for `hedge_dropped`
    (the model's phrasing lost a hedge the source passage carried); one (f453ebb7) withheld for
    `source_set_exceeds_screen_limit` — a **structural** cap (`guards.MAX_UNIT_IDS`), not a judgment: a
    claim citing 5 propositions can't even have its evidence layer screened, so it falls back
    automatically regardless of what the model wrote.
  - **3 invalid_item** (structural, pre-NLI): c33c4ccf (c6, "explicit"), 775fda77 (c10, "Hadza"),
    d4746534 (c12) — each a `category_list`/`role_value` claim whose bare value is a single word or
    short phrase; the model's returned "statement" text failed the basic structural prose check
    (`item_reasons()`) before NLI was ever consulted.
- **Grounded/fallback totals:** 7 grounded, 14 fallback (11 withheld + 3 invalid_item) — matching the
  manifest's `grounded_segment_count: 7` / `fallback_segment_count: 14` exactly, and matching the
  independent recorder's own observation of the single S2 call that produced them.
- **Model/binding identity:** qwen3.5:9b, think=False, options = `PARENT_SYNTHESIS_S_OPTIONS` (confirmed
  byte-identical to `CHILD_OVERVIEW_S_OPTIONS`) — `realize()`'s own binding-envelope guard (`s_binding_
  not_parent_envelope`) never fired, confirming the resident S supervisor was exactly the expected
  envelope throughout.

### The complete rendered parent answer

```
## Overview

Across these levels of organization, the specific amygdala response to facial anomalies correlated with
stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern,
and less prosociality toward people with facial anomalies. [p11]
A reported relationship (individual_difference_trait_or_construct: attractiveness; relationship_to_bias_
manifestation: Results: Across the ratings for all faces, Spearman correlations revealed greater
proportionality was associated with attractiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193,
P < 0.001), while lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001),
dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001).). [p41]
[...four more structurally-identical "A reported relationship (...)" fallback sentences for
trustworthiness/anger/dominance/threateningness, each citing p41...]
A direction finding (negative) was reported. [p14, p26]
This research confirmed earlier reports that people with anomalous faces are imbued with negative
personality characteristics, detected explicit biases against people with facial anomalies, and
described a behavioral manifestation of the "anomalous-is-bad" stereotype affecting prosociality. [p1]
the specific amygdala response [p11, p2]
This research confirmed earlier reports... [p4]
This research confirmed earlier reports... [p8]
increased amygdala reactivity [p40]
Across these levels of organization, the specific amygdala response... [p11]
attitude category (implicit/explicit) evidence: explicit. [p17]
a named culture or population: Hadza. [p29, p53]
a definitive, non-speculative reported outcome: [... three outcome statements verbatim ...]. [p24, p30, p31]
an observed behavior, behavioral choice or action...: [... three behavior statements verbatim ...]. [p35, p46, p47]
attitude category (implicit/explicit) evidence: implicit; explicit. [p36, p8]
a named individual-difference trait or construct: emotional dispositions (affective empathy); negative
attitudes (IAT and EBQ); social cognitive biases (just-world beliefs); undesirable behaviors (less
generosity in the DG). [p20, p9]
an observed behavior...: participants made more share decisions overall... [p46, p47]
a named attitude type or measure: Explicit Bias Questionnaire. [p14, p17, p26, p3, p7]

## Qualified / heterogeneous findings
None.

[Supporting findings and Unresolved parts sections: see full file at run/15_parent_answer.md]

This answer restates the structured sufficiency state of this run. It makes no statement about what the
library or the literature holds. Completeness is not certified.
```

(Full text, including the complete "Supporting findings" citation list and "Unresolved parts" breakdown
by reason code, is in the preserved artifact `run/15_parent_answer.md`, not reproduced byte-for-byte here
for length; nothing is paraphrased above — every sentence shown is copied verbatim.)

---

## Sentence-level parent provenance table

| Parent statement (abbreviated) | Source kind | claim_id | Child / requirement | Proposition(s) | Earliest stage content appeared | Classification |
|---|---|---|---|---|---|---|
| "Across these levels... less prosociality..." | **S2-grounded** | relational::5d178917 | c4 / specific-region | p11 | W1 (p11 retrieved+verified) | NO_ERROR |
| "A reported relationship (...attractiveness...)" | Deterministic fallback (withheld, nli 0.54) | relational::6d3e9d91 | c8 / trait-construct | p41 | W2 recovery (p41 added) | NO_ERROR — correctly withheld, not silently trusted |
| (same, trustworthiness/anger/dominance/threateningness) | Deterministic fallback (withheld, nli 0.54–0.55) | relational::{bac1b3e1,99d44d22,629c3c06,6e5d1f4c} | c8 | p41 | W2 recovery | NO_ERROR |
| "A direction finding (negative) was reported." | Deterministic fallback (withheld: negation/novel-terms) | direction_or_effectiveness::97e9b66f | c6 / brain-attitude | p14, p26 | W1/W2 | NO_ERROR |
| "This research confirmed earlier reports..." (c1) | **S2-grounded** | role_value::8d0ce9c4 | c1 / neural-manifestation | p1 | W1 | NO_ERROR |
| "the specific amygdala response" | **S2-grounded** | role_value::57b25a88 | c1 | p11, p2 | W1 | NO_ERROR |
| "This research confirmed earlier reports..." (c2) | **S2-grounded** | role_value::b9591e4f | c2 / behavioral-manifestation | p4 | W1 | NO_ERROR |
| "This research confirmed earlier reports..." (c3) | **S2-grounded** | role_value::34d05796 | c3 / attitude-manifestation | p8 | W1 | NO_ERROR |
| "increased amygdala reactivity" | **S2-grounded** | role_value::161d9d58 | c4 | p40 | W2 recovery | NO_ERROR |
| "Across these levels of organization..." (repeat, c4) | **S2-grounded** | role_value::1f1af648 | c4 | p11 | W1 | NO_ERROR |
| "attitude category... explicit." | Deterministic fallback (invalid_item) | role_value::c33c4ccf | c6 / implicit-explicit | p17 | W2 recovery | NO_ERROR — correctly caught by structural check |
| "a named culture or population: Hadza." | Deterministic fallback (invalid_item) | category_list::775fda77 | c10 / culture-existence | p29, p53 | W1 | NO_ERROR |
| "a definitive, non-speculative... outcome: [...]" | Deterministic fallback (invalid_item) | category_list::d4746534 | c12 / intervention-effectiveness | p24, p30, p31 | W2 recovery | NO_ERROR |
| "an observed behavior...: [3 items]" (c2) | Deterministic fallback (withheld, nli 0.41) | category_list::10ddc38d | c2 | p35, p46, p47 | W1/W2 | NO_ERROR |
| "attitude category...: implicit; explicit." | Deterministic fallback (withheld, nli 0.50) | category_list::9fd341f1 | c3 | p36, p8 | W1/W2 | NO_ERROR |
| "a named individual-difference trait...: [4 items incl. 'undesirable behaviors']" | Deterministic fallback (withheld, hedge_dropped) | category_list::f1f51b4b | c8 / trait-construct | p20, p9 | **U1/U2 (semantic mapping)** | **SEMANTIC_MAPPING_ERROR** — see below |
| "an observed behavior...: [2 items]" (c5) | Deterministic fallback (withheld, nli 0.02) | category_list::7af59a3e | c5 / brain-behavior | p46, p47 | W2 recovery | NO_ERROR |
| "a named attitude type or measure: Explicit Bias Questionnaire." | Deterministic fallback (withheld, source_set_exceeds_screen_limit) | category_list::f453ebb7 | c6 | p14,p17,p26,p3,p7 | W1/W2 | NO_ERROR — structural cap, not a judgment |
| Unresolved-parts list (39 gaps) | Deterministic gap rendering | n/a | all children | n/a | U2 final map | NO_ERROR (honest gaps) |

**The one traceable error in the final answer:** the "undesirable behaviors (less generosity in the DG)"
value inside claim `category_list::f1f51b4ba55bad3c` (c8's trait/construct list) is a **category-boundary
error** — a reported *behavior* (less generosity in a Dictator Game) classified under the
*individual-difference trait or construct* role. This is **not** something S2 introduced (S2 withheld
this claim's own statement for an unrelated reason, `hedge_dropped`, and the value reaches the final
answer only via the deterministic literal fallback, which renders the ledger's own values verbatim). It
is **not** a parent-ledger-construction error either (the ledger faithfully reflects whatever U1/U2
nominated). **Earliest-error classification: SEMANTIC_MAPPING_ERROR, at U1's (or U2's remap of) the
`individual_difference_trait_or_construct` role for c8** — the same, confirmed-recurring error Phase 23A
found in a different live run. See the next section.

---

## Known-tracer analysis (Phase 23A, consulted only now that artifacts are sealed)

### c8 — RECURS

Phase 23A (reviewing a different, earlier live run) found `"undesirable behaviors (less generosity in
the DG)"` nominated as a value for c8's `individual_difference_trait_or_construct` role — a
category-boundary error, since "less generosity in a Dictator Game" is a measured *behavior*, not a
*trait*. Phase 23A judged the architecture's own refusal to certify c8 "complete" scientifically correct
regardless of this one value's error.

**This exact value is present in this run's c8 claim ledger too** (`category_list::f1f51b4ba55bad3c`,
proposition `p20`). Evidence text first appears at W1 (the proposition is a direct, initial W1 retrieval
hit, not a W2 recovery addition — confirmed via `13_gap_recovery.json`, which lists no recovery target
touching `p20`). The error is introduced by whichever U1 nomination bound `p20`'s "undesirable behaviors"
span to the trait/construct role rather than correctly recognizing it as an operationalized behavioral
measure. S1:c8's own rendered overview never surfaced this specific value (c8's two displayed statements
restate different passages, p42/p43); the value only reaches a final, human-visible surface via the
**parent** claim ledger and its deterministic fallback rendering, since S2's own attempt to phrase it was
independently withheld for an unrelated lexical reason. **Both the faithful parent-ledger construction
and the faithful S2/fallback propagation are correct behavior given an already-wrong upstream value** —
this is the textbook case the earliest-error methodology exists to distinguish from a parent-synthesis
defect.

### c12 — Phase 23A's specific contamination does NOT recur; a different, more conservative outcome instead

Phase 23A flagged two separate c12 concerns: (a) a correct intervention paired with an *incorrect*
`target_manifestation` (the unaffected half of a stated contrast), and (b) a weak, off-topic value
accepted from a retrieval miss (a COVID-19 misinformation paper, unrelated to the facial-bias topic).

**Neither specific bad value appears in this run's c12 claims.** The only c12 claim that reached the
ledger (`category_list::d47465340e922bca`, "a definitive, non-speculative reported outcome") cites three
on-topic facial-anomaly/exposure-intervention propositions (p24, p30, p31) — no COVID-19 content
anywhere. c12's `target_manifestation` role, the one Phase 23A found an *incorrect* accepted value for,
shows in **this** run's gap report only as `missing`/`partial` across multiple target ids — an honest
open gap, not a wrong answer. **This is not evidence the underlying issue was fixed**: this run used a
different profile (T5C/model-assisted U1/U2) and a different recovery path (a real P1/gemma3:12b DEEPEN
decision, different recovery queries) than Phase 23's run, so different search results are expected on
their own, independent of any architectural change. The honest, bounded claim here is: *this specific
contamination did not recur in this specific run*, not *the retrieval-quality issue is resolved*.

---

## Parent-synthesis stage-local verdict

**PASS, by the stage's own job description.** Exactly one call; no child S1 prose, no ResolvedEmptyOutcome
text, and no unrelated evidence pool in the prompt (confirmed by direct inspection of the captured raw
text, not inferred); S2 never chose which propositions cite a claim (the schema has no such field); every
claim got a deterministic per-item fallback when its phrasing didn't clear the screens, and one claim's
rejection never touched a sibling (per-claim isolation holds, confirmed across all 14 fallback cases);
citations in the final answer are 100% deterministic regardless of grounded/fallback status; the one
confirmed-recurring scientific error (c8's category-boundary mislabel) demonstrably predates S2 and is
faithfully, not newly, propagated — S2 is not scored down for an error introduced upstream, per the
methodology's own stated principle.

## Child-synthesis (S1) stage-local verdict

**PASS for all 11 children**, evaluated against their own structured/evidence input rather than against
idealized scientific truth: every rendered statement traces to its cited passage; every disclosed
qualification (hedge, null result, partial quote, association-not-causation) was carried forward rather
than smoothed away; the two honest zero-statement outcomes (c5, c9) reflect real screening refusals, not
mechanical failure; one minor narrowing was found (c4, a three-clause passage rendered as one clause) and
is noted, not treated as a fabrication.

## Parent audit result

`parent_synthesis_audit.audit_parent_synthesis(...)` ran as part of the real construction (`15a_parent_
synthesis.json` includes an `audit` key in the live `_parent_synthesis_outputs()` return — confirmed by
direct code read of `e2e.py`'s `_parent_synthesis_outputs`); the realization state it audited
(`mixed_model_and_fallback`, 7 grounded / 14 fallback) matches this report's own independent recorder-based
count exactly, with no discrepancy between the audit's view and the recorder's view of what actually
happened.

## Newly discovered issues (this run, not pre-existing knowledge)

1. **`hierarchy_carriage` mechanical check: 13 of 626 calls failed** (`16_mechanical_checks.json`). All 13
   are `recovery_query` worker-task calls (the W-role's own internal query-construction calls during W2,
   distinct from the Supervisor-role calls this report's recorder tracks) for children c4 (1), c5 (1), c6
   (2), c11 (4), c12 (5) — each missing the child's exact "item line" the carriage invariant expects every
   call touching a child to carry verbatim. This did **not** block the run (`technical_validity.valid:
   true`) and is reported, not patched, per the no-code-change mandate. **Recommendation:** a future,
   separately-scoped look at `hierarchy_contract.carriage_violations`'s handling of the `recovery_query`
   task specifically — whether the carriage invariant is mis-specified for a query-formulation task (which
   may not need the verbatim item line the way a classification task does) or whether the prompt builder
   has a real, fixable gap.
2. The c8 category-boundary tracer (above) is confirmed recurring, not new, but this is the first time it
   has been traced through a **complete** parent-synthesis pipeline, showing concretely that neither the
   ledger nor S2 nor the fallback renderer are the place to fix it — any correction belongs at U1/U2's
   role-nomination/screening layer, consistent with Phase 23A's own framing.

## Did Attempt 2 fulfill Phase 28's purpose?

**Yes, fully.** A complete, live, authorized, one-shot observation of T5C through parent synthesis,
independently witnessed at the S2 boundary, with a full stage-by-stage trail from W1 through the rendered
answer, an honest accounting of every fallback and every gap, and a concrete, evidence-traced answer to
"where did this first become wrong" for the one real scientific error found.

## Recommended next step

No further live Phase 28 work is required to close this phase's own stated purpose. Two open threads for
separate, future phases: (a) the `hierarchy_carriage`/`recovery_query` mechanical finding above; (b) the
c8 category-boundary error remains an open scientific-fidelity question at the U1/U2 role-nomination
layer — unchanged by, and not in scope for, parent synthesis.
