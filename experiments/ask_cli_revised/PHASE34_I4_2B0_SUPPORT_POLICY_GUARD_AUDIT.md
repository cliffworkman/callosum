# Phase 34 / I4-2b0 — Support admissibility and guard semantics audit

**Status:** planning audit accepted in substance, with the user's corrected B9 aggregation contract.
**Implementation readiness:** **NOT READY for I4-2b**; [I4-2b1](PHASE34_I4_2B1_OWNERSHIP_UNCERTAINTY_AUDIT.md)
recommends **B: fix attribution first; do not weaken the conservative support-policy default**.
**Date:** 2026-10-08. **Authoring:** Cody/Codex; architecture and acceptance: Cliff Workman.

This report preserves the original **uncorrected-attribution counterfactual**. It is not a claim that six
real assertions are intrinsically unusable: I4-2b1 establishes recoverable upstream attribution failures
for all six. Both projections are retained so the reason for the changed recommendation is inspectable.

## 1. Frozen scope and evidence

Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
Starting HEAD: `d2f3e1619a820b27479e7e00abb1e1e002fd1882`; clean before materialization.
I4-2a is accepted. This increment writes only this report, I4-2b1, and two entries in
[CONTRIBUTION-LINEAGE.md](CONTRIBUTION-LINEAGE.md). No production code, classifier, support-policy
evaluation, guard behavior, sufficiency version, PLAN_VERSION, relationship registration, ParentClaims,
or AnswerPlan is changed. No retrieval, model calls, external search, or live E2E. No I2-3.

Evidence sources are the committed [I4-2a replay annex](phase34_i4_2a_replay_results.json), accepted
[I4-2a report](PHASE34_I4_2A_LOCAL_GROUNDING_INTEGRATION_RESULTS.md), preserved Attempt2 artifacts,
and the existing offline [replay harness](test_i4_2a_replay.py). The run directory, relative to the
canonical worktree, is `.local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/run`.

| Artifact | SHA-256 |
|---|---|
| Sealed ledger, `11_verified_ledger.json` | `a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d` |
| Initial sufficiency map | `46a213044bc6211702fa89710268e1bfb6c4fc348259727a46cb238ef5bbc14e` |
| Final preserved sufficiency map | `28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b` |
| Accepted repaired v5 replay | `109030de83856b4384d596311dd8e3f6d46d19859c895c4b94b9efb3aa92ae77` |
| Historical v4 replay, both paths | `4154ebd4062d22aa25db43e947aba61abe2c5888d6aa10d8ecd14b60afa65e4a` |

The accepted v5 replay is `.local/i4-2a/current-v5-repaired.json`. Its recorded byte hash uses the saved
Windows newline convention; decoded canonical replay equality is checked as well. These are historical
v5 artifacts, not new v6 artifacts.

## 2. Semantic boundary and evidence model

I4-2a asks whether a local assertion is evidence about this role instance. I4-2b would ask whether that
kind of evidence may satisfy the authored requirement. Do not repair ownership or relevance in the
support-policy evaluator.

The original ten candidates are already grounded and role-instance relevant. Their `admissible=None`
and `inadmissibility_reason=None` mean **not evaluated**. They do not mean rejected or ambiguous.
Relation, aggregation, and kind are independent axes; `support_label` is derived display metadata.
There is no direct > indirect > synthetic quality ranking. Attributed prior evidence is legitimate.
The defect audited here is misattribution, not indirectness.

## 3. B1–B3: default, explicit policy, and API distinction

The proposed absent-policy default for general empirical-result roles remains:

```text
assertion_kind == result
AND NOT (
    assertion_relation == unresolved
    AND aggregation == non_synthetic_or_unspecified
)
```

This admits current-document results, attributed-external results, and unresolved literature-synthesis
results. It rejects unresolved non-synthetic results and every non-result kind. Its application to the
uncorrected real map is recorded below, not treated as proof that those ownership labels are correct.

An explicit policy is the complete authored rule. All three fields are required by
`_canonical_support_policy`; relation membership, kind membership, and the aggregation condition
combine with **AND**:

| `aggregation_requirement` | Condition |
|---|---|
| `any` | Either aggregation value passes this dimension |
| `require_synthesis` | Only `literature_synthesis` |
| `exclude_synthesis` | Only `non_synthetic_or_unspecified` |

An explicit policy **replaces**, rather than layers over, the absent-policy predicate. Thus an authored
policy can deliberately admit an unresolved non-synthetic result or a description. No hidden empirical
default may veto that choice. I4-1h prose about subset overrides must not override the complete schema
and the user's accepted replacement decision.

The distinction is already stated in [sufficiency_engine.py](sufficiency_engine.py):
`new_support_policy()` allows every relation, any aggregation, and result kinds; it is intentionally
more permissive than the absent-policy predicate. `new_role_spec` omits the policy key when absent.
The builder must never stand in for the default.

**Smallest future API clarification:** provide an explicitly named pure absent-policy predicate and a
dispatcher that distinguishes absent policy from a complete authored policy. Document the two branches
beside the RoleSpec schema and pin the counterexample
`unresolved/non_synthetic_or_unspecified/result`: false under absent policy, true under the builder's
explicit defaults. No builder-default change, partial-policy merge, new flattened label, or production
API change is made in this audit.

### Source-specific and definitional authoring

For “What did THIS study find?”, author relations `[current_document]`, kinds `[result]`, and
aggregation `any`. Current-document synthetic results then remain eligible. Use
`exclude_synthesis` only when the requirement actually calls for that restriction. The evaluator does
not parse the question.

For a definition such as “What is the placebo effect?”, a role can author
`[method_or_description, interpretation]` and appropriate relations. The matrix below demonstrates a
complete policy accepting current-document and attributed-external descriptions/interpretations.
This does not change the general empirical default. Future Simple Ask can author such a policy using
the same machinery as hierarchical Ask.

## 4. Complete real v5 candidate inventory

The following ten records are transcribed directly from the committed I4-2a annex, preserving plural
proposition discovery order, exact text, and instance identity. JSON `null` corresponds to Python
`None`; a null instance key is a real unkeyed instance, not omitted evidence.
All ten currently have `attachment_ambiguous=False`. Each proposed outcome below is **before**
the I4-2b1 attribution correction.

### Candidate 1 — c1 / neural_manifestation_evidence

```json
{
  "child": "c1",
  "requirement": "c1#suff:neural-manifestation",
  "role": "neural_manifestation_evidence",
  "instance": null,
  "supporting_proposition_ids": [
    "p2",
    "p11"
  ],
  "span_proposition_id": "p2",
  "assertion_span": [
    37,
    264
  ],
  "exact_text": "the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies",
  "assertion_relation": "unresolved",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "unresolved",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **False**. Excluded: unresolved ownership and non-synthetic/unspecified aggregation; retain as support_policy_excluded.

### Candidate 2 — c2 / behavioral_manifestation_evidence

```json
{
  "child": "c2",
  "requirement": "c2#suff:behavioral-manifestation",
  "role": "behavioral_manifestation_evidence",
  "instance": "i::76d9e54baf790d84",
  "supporting_proposition_ids": [
    "p47"
  ],
  "span_proposition_id": "p47",
  "assertion_span": [
    76,
    251
  ],
  "exact_text": "we observed that participants were faster to share when playing with the good partner compared to the bad (t11 ¼ –3.73, P o 0.005) and neutral partners (t11 ¼ –1.89, P ¼ 0.08)",
  "assertion_relation": "current_document",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "direct_empirical",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **True**. Result kind with current-document ownership.

### Candidate 3 — c3 / attitude_manifestation_evidence

```json
{
  "child": "c3",
  "requirement": "c3#suff:attitude-manifestation",
  "role": "attitude_manifestation_evidence",
  "instance": null,
  "supporting_proposition_ids": [
    "p7",
    "p3",
    "p14",
    "p17",
    "p26"
  ],
  "span_proposition_id": "p7",
  "assertion_span": [
    14,
    251
  ],
  "exact_text": "we found evidence for the “anomalous-is-bad” stereotype in explicit negative attitudes about people with facial anoma- lies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire)",
  "assertion_relation": "current_document",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "direct_empirical",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **True**. Result kind with current-document ownership.

### Candidate 4 — c4 / region_bears_on_bias_evidence

```json
{
  "child": "c4",
  "requirement": "c4#suff:specific-region",
  "role": "region_bears_on_bias_evidence",
  "instance": "i::ac9b72f14d53f532",
  "supporting_proposition_ids": [
    "p11",
    "p2"
  ],
  "span_proposition_id": "p11",
  "assertion_span": [
    37,
    264
  ],
  "exact_text": "the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies",
  "assertion_relation": "unresolved",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "unresolved",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **False**. Excluded: unresolved ownership and non-synthetic/unspecified aggregation; retain as support_policy_excluded.

### Candidate 5 — c4 / region_bears_on_bias_evidence

```json
{
  "child": "c4",
  "requirement": "c4#suff:specific-region",
  "role": "region_bears_on_bias_evidence",
  "instance": "i::a3ab9566580a7fe4",
  "supporting_proposition_ids": [
    "p40"
  ],
  "span_proposition_id": "p40",
  "assertion_span": [
    147,
    273
  ],
  "exact_text": "Laypersons with high levels of implicit bias toward those with facial anomalies demonstrated increased amygdala reactiv- ity.6",
  "assertion_relation": "unresolved",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "unresolved",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **False**. Excluded: unresolved ownership and non-synthetic/unspecified aggregation; retain as support_policy_excluded.

### Candidate 6 — c8 / relationship_to_bias_manifestation

```json
{
  "child": "c8",
  "requirement": "c8#suff:trait-construct",
  "role": "relationship_to_bias_manifestation",
  "instance": "U23::24d132203292cebb",
  "supporting_proposition_ids": [
    "p41"
  ],
  "span_proposition_id": "p41",
  "assertion_span": [
    43,
    200
  ],
  "exact_text": "Spearman correlations revealed greater proportionality was associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193, P < 0.001)",
  "assertion_relation": "current_document",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "direct_empirical",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **True**. Result kind with current-document ownership.

### Candidate 7 — c8 / relationship_to_bias_manifestation

```json
{
  "child": "c8",
  "requirement": "c8#suff:trait-construct",
  "role": "relationship_to_bias_manifestation",
  "instance": "U23::8d7156b76bf6a6f7",
  "supporting_proposition_ids": [
    "p41"
  ],
  "span_proposition_id": "p41",
  "assertion_span": [
    43,
    200
  ],
  "exact_text": "Spearman correlations revealed greater proportionality was associated with attrac- tiveness (ρ = 0.292, P < 0.001) and trustworthiness (ρ = 0.193, P < 0.001)",
  "assertion_relation": "current_document",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "direct_empirical",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **True**. Result kind with current-document ownership.

### Candidate 8 — c8 / relationship_to_bias_manifestation

```json
{
  "child": "c8",
  "requirement": "c8#suff:trait-construct",
  "role": "relationship_to_bias_manifestation",
  "instance": "U23::50b0d4004f2f502f",
  "supporting_proposition_ids": [
    "p41"
  ],
  "span_proposition_id": "p41",
  "assertion_span": [
    208,
    372
  ],
  "exact_text": "lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001)",
  "assertion_relation": "unresolved",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "unresolved",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **False**. Excluded: unresolved ownership and non-synthetic/unspecified aggregation; retain as support_policy_excluded.

### Candidate 9 — c8 / relationship_to_bias_manifestation

```json
{
  "child": "c8",
  "requirement": "c8#suff:trait-construct",
  "role": "relationship_to_bias_manifestation",
  "instance": "U23::f6027eb43b85593c",
  "supporting_proposition_ids": [
    "p41"
  ],
  "span_proposition_id": "p41",
  "assertion_span": [
    208,
    372
  ],
  "exact_text": "lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001)",
  "assertion_relation": "unresolved",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "unresolved",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **False**. Excluded: unresolved ownership and non-synthetic/unspecified aggregation; retain as support_policy_excluded.

### Candidate 10 — c8 / relationship_to_bias_manifestation

```json
{
  "child": "c8",
  "requirement": "c8#suff:trait-construct",
  "role": "relationship_to_bias_manifestation",
  "instance": "U23::910466e6604581fa",
  "supporting_proposition_ids": [
    "p41"
  ],
  "span_proposition_id": "p41",
  "assertion_span": [
    208,
    372
  ],
  "exact_text": "lesser proportionality was associated with impressions of anger (ρ = 0.132, P = 0.001), dominance (ρ = 0.259, P < 0.001), and threateningness (ρ = 0.234, P < 0.001)",
  "assertion_relation": "unresolved",
  "aggregation": "non_synthetic_or_unspecified",
  "assertion_kind": "result",
  "support_label": "unresolved",
  "authority_veto": null,
  "is_caption": false,
  "admissible": null,
  "inadmissibility_reason": null,
  "attachment_ambiguous": false
}
```

Proposed default, uncorrected attribution: **False**. Excluded: unresolved ownership and non-synthetic/unspecified aggregation; retain as support_policy_excluded.


There are **4 True and 6 False** outcomes among the ten original candidates. Every False has the same
specific cause: `unresolved + non_synthetic_or_unspecified + result`; the candidate would be retained
with `inadmissibility_reason=support_policy_excluded`. No original candidate fails for a non-result
kind, authority veto, caption status, or attachment uncertainty.

c1's one candidate fails; c2's p47 candidate and c3's pooled result pass. c4's p11/p2 and p40 candidates
both fail. c8 splits into two passing instances (attractiveness, trustworthiness) and three failing
instances (anger, dominance, threateningness). c10/c12 have no original grounded candidates to evaluate.
Do not infer that lack of a candidate means support policy rejected it.

## 5. B4–B7: vetoes, captions, guards, and hedging

### Authority veto: deferred gating

A current-document result can carry `absence_of_evidence` or `negated_result_predicate` without losing
its ownership or kind. A positive achieved-outcome claim should not be satisfied by a null result, while
a null-finding role could use it. But the current RoleSpec has no structured positive/null claim-goal
field, and existing achieved-outcome behavior/tests admit unhedged null findings as reported evidence.
The user therefore accepted **deferring authority-veto gating until structured claim-goal authoring
exists**. Do not infer a positive goal from the mapping strategy, role name, or question vocabulary.
Do not create a global veto. Preserve the metadata. There are no real vetoed candidates in this inventory.

### Caption status: metadata only

There are no real caption examples here. Do not import I4-1's old finding-authority caption treatment
into support admissibility. A caption result passes the same authored policy as another result, subject
to any independently authored applicable gates. The current v5 binder supplies `is_caption=False`;
unit reconstruction does not carry structural caption context into this call. This is a metadata
transport limitation, not evidence for blanket caption rejection.

### Architecture comparison

| Architecture | Meaning and consequence | Audit decision |
|---|---|---|
| A: keep guard prefilters | Declare guards to be semantic eligibility/relevance exclusions; hard discard is intentional and the evidence is not inspectable in candidate_supports | Rejected for this future integration: history and the actual hedge flag concern admissibility/uncertainty, not necessarily role relevance |
| B: retain and flag after grounding/relevance | A successfully grounded, relevant candidate remains inspectable with independent guard exclusions and policy outcome | **Accepted**, requiring future collection-order/schema/reference-contract changes and a semantic boundary |

Existing `is_admissible` and the guard authoring history (including commit `5bfcf61b`) treat guards as
per-role evidence restrictions. Achieved-outcome roles commonly declare `hedged`; named-entity roles
need not. Existing tests accepting an unhedged null result further demonstrate that “achieved outcome”
is not a structured positive-claim declaration.

The passage-level hedge detector includes words such as may, likely, suggest, appear, and seem.
“X was likely associated with Y” can still be evidence about X/Y with weaker certainty. The real c10
phrase “more likely” also illustrates that the lexical flag is not a calibrated certainty model.
Do not redesign hedge detection in this audit or weaken declared guards.

With guard prefiltering bypassed **only in the in-memory simulation**, normal localization and relevance
still run first. Five additional candidates survive those checks: one c3 interpretation and four c8
interpretations from the p9/p20 assertion beginning “We suggest that dehumanization…”. All five carry the
existing hedge exclusion and independently fail the empirical default because their kind is
`interpretation`. Guard failure is not caused by the kind; these are two separate failed gates.

c10 still emits no candidate: its relevant raw hits do not join to a governing assertion; other units
have no raw hits. Thus retain-and-flag does not automatically make every prefiltered unit inspectable.
The evidence must first ground and match the role. c12 also remains absent after grounding/relevance.
Production guard order and behavior are unchanged.

## 6. B8–B10: candidate evaluation and corrected role aggregation

Evaluate every candidate independently against its applicable authored guards and selected support
policy. Retain the outcomes separately from attachment status. Preserve a policy rejection as
`support_policy_excluded` and preserve guard exclusions independently, including simultaneous failures.
A single legacy reason cannot be semantic authority for the combination.

The user's corrected B9 is authoritative:

- **FILLED:** at least one attachment-resolved candidate passes all applicable guard and support-policy gates.
- **AMBIGUOUS:** no filled candidate exists, and at least one attachment-ambiguous candidate would otherwise
  pass all applicable guard and support-policy gates if attachment were resolved.
- **MISSING:** otherwise.

There is **no semantic precedence attachment > guard > policy**. An independently excluded candidate
does not create ambiguity because its attachment is also uncertain. This retains the three-state intent
of I4-1g but corrects its reference contract for simultaneous failures. The current
`reference_future_role_state` checks admissible flags and then a scalar attachment reason; it does not
express these orthogonal facts adequately and must be revised in a future authorized increment.
It is not modified here.

| Attachment | Guard passes | Policy passes | Single-candidate role state |
|---|---|---|---|
| Resolved | True | True | filled |
| Resolved | True | False | missing |
| Resolved | False | True | missing |
| Resolved | False | False | missing |
| Ambiguous | True | True | ambiguous |
| Ambiguous | True | False | missing |
| Ambiguous | False | True | missing |
| Ambiguous | False | False | missing |

Multiple-candidate examples, with all other applicable gates passing unless stated:

| Candidate set | State |
|---|---|
| Resolved direct + resolved attributed evidence, both admissible | filled |
| Direct policy-excluded + attributed admissible | filled |
| Resolved admissible + attachment-ambiguous otherwise eligible | filled |
| All policy-excluded, including an attachment-ambiguous candidate | missing |
| Multiple synthetic supports, at least one resolved and eligible | filled |
| Only otherwise-eligible attachment-ambiguous support | ambiguous |
| Empty candidate set | missing |

Fourteen in-memory contract checks pass: the eight single-candidate combinations plus six set cases
(filled plus ambiguous; resolved/ambiguous both guard-excluded; ambiguous candidates independently
excluded by policy/guard; eligible ambiguous plus resolved policy-excluded; excluded plus admissible
resolved; empty). These check the aggregation contract, not an implemented new production evaluator.
No provenance-only state such as filled_indirect or partial_indirect is introduced.

## 7. Generic policy matrix and synthetic evidence gap

This matrix assumes resolved attachment and passing guards. True means the sole candidate could fill
the role; False means a sole candidate leaves it missing. Other candidates can independently fill it.

- **E, empirical:** absent-policy predicate.
- **C, current document:** explicit relations `[current_document]`, aggregation `any`, kinds `[result]`.
- **S, synthesis:** explicit all three relations, `require_synthesis`, kinds `[result]`.
- **D, definition:** explicit `[current_document, attributed_external]`, `any`,
  kinds `[method_or_description, interpretation]`.

| Candidate | E | C | S | D | Reason for differences |
|---|---|---|---|---|---|
| Primary current-document result | True | True | False | False | S requires synthesis; D requires a different kind |
| Attributed prior result | True | False | False | False | Legitimate empirical evidence; C requires current ownership |
| Unresolved bare result | False | False | False | False | E rejects unresolved non-synthesis; other authored dimensions fail |
| Unresolved synthesis result | True | False | True | False | Synthesis satisfies E despite unresolved relation |
| Attributed synthesis result | True | False | True | False | C relation fails; D kind fails |
| Current-document synthesis result | True | True | True | False | C does not exclude synthesis |
| Current-document description | False | False | False | True | Non-result kind is authored explicitly by D |
| Current-document interpretation | False | False | False | True | Same; any separate hedge guard still applies |
| Current-document result with authority veto | True | True | False | False | Veto gating deferred, not silently inferred |
| Current-document caption result | True | True | False | False | Caption metadata has no direct policy effect |

There are zero real `literature_synthesis` candidates in the preserved corpus. Preserve these synthetic
cases explicitly; real-map replay cannot validate them:

| Synthetic assertion | Relation | Aggregation | Kind | E |
|---|---|---|---|---|
| “Across studies, X has been associated with Y.” | unresolved | literature_synthesis | result | True |
| “A review found X.” | attributed_external | literature_synthesis | result | True |
| “We found a meta-analytic effect.” | current_document | literature_synthesis | result | True |

A is the critical steering case: unresolved ownership alone must not reject synthesis. The matrix
contains no domain vocabulary used as runtime policy.

## 8. B11–B12: relationship verification and versioning

Support-policy evaluation does not need `same_local_assertion`. Narrowed I4-2a exact_text makes the
primitive meaningful, but registration changes relationship semantics independently. Defer it to I4-3
planning. Do not treat successful support admissibility as a new relationship witness.

The repository's semantic-version precedent explicitly covers mapping, admissibility, satisfaction,
recovery, and witness changes. I4-2a introduced v5 for grounding. The uncorrected projection below changes
states independently of grounding; retain-and-flag also changes inspectability, and synthetic policy
cases change behavior even if attribution corrections eliminate real state losses. Recommend a likely
**sufficiency-semantics-v6** boundary for eventual I4-2b. No version is changed here.
Any earlier attribution repair also needs an explicit compatibility decision: it must not silently
alter historical v5 classification through a globally changed classifier. Preserve exact explicit v5
replay; PLAN_VERSION remains outside this increment.

## 9. B13–B14: original uncorrected-attribution counterfactual

**Historical projection, intentionally preserved.** Apply the default to the original v5 relation
labels, retain/flag grounded guards, and recompute downstream using frozen model nominations.
This is not the revised ownership judgment. All actual attachments are resolved, so correcting B9 does
not alter these historical numerical results.

| Measure | v5 | Uncorrected-attribution projection |
|---|---:|---:|
| Original candidates | 10 unevaluated | 4 passing, 6 policy-excluded |
| Candidates including newly retained guard exclusions | 10 | 15: 4 passing, 6 original policy exclusions, 5 guard-and-policy exclusions |
| Evidence-role instances unchanged | — | 20 of 26: 4 filled, 16 missing |
| filled → missing | — | 6 |
| filled → ambiguous / missing → filled | — | 0 / 0 |
| Requirements with state changes | — | 4 of 13 |
| Total instances | 46 | 39 |
| Total role bindings | 94 (51 filled, 43 missing) | 80 (30 filled, 50 missing) |
| Recovery targets | 48 | 39 |
| ParentClaims | 17 | 13 |
| AnswerPlan nodes | 9 | 9, node statuses unchanged |
| AnswerPlan invariant checks | 33 passing | 33 passing |

Requirement effects:

| Requirement | State change / instance consequence |
|---|---|
| c1 neural manifestation | filled → partially_filled; evidence role missing |
| c4 specific region | filled → partially_filled; both evidence roles missing, complete instances 2 → 0 |
| c5 brain–behavior | filled → partially_filled; instances 4 → 2, complete 4 → 0 |
| c6 brain–attitude | filled → partially_filled; instances 4 → 2, complete 4 → 0 |
| c8 trait construct | remains partially_filled; complete instances 5 → 2 |
| c9 trait–scale pairing | remains partially_filled; inherited instances 5 → 2 |
| All other requirements | states unchanged |

c8 is actually an **atomic open_list**, not an exists/cardinality requirement. Its two surviving
instances do not complete that list. Generally, an exists requirement stays filled if any complete
instance survives; this must not be substituted for c8's actual quantifier.

Recovery has 32 identical retained targets, 16 removed, and 7 added. Added: one c1 evidence target, two
c4 evidence targets, and two missing-region targets each for c5/c6. Removed: thirteen provisional
corroboration targets (c1: 1; c4/c5/c6: 4 each), plus three c9 scale targets. c8 retains its existing
open-list breadth target; it does not automatically acquire one recovery target per excluded trait.

c4 relation witnesses fall 2 → 0; c8 witnesses 5 → 2; c2 is unchanged. c5/c6 relation tests remain false,
but the reason changes from inherited_referent_absent to incomplete_operands. Direction observations
fall c5: 2 → 1 and c6: 4 → 2, all ineligible in either projection; no supported directional consensus
appears. Effectiveness observations remain zero.

ParentClaim kinds change relational 9 → 3, role_value 2 → 3, and category_list 6 → 7. Eight claim IDs
are retained, nine removed, and five added. c1/c4 gain entity-value/category-list expressions. c8's
category-list surface can still contain named traits whose relationship evidence was excluded; a name
alone is not support for the relationship.

The AnswerPlan's nine node statuses stay the same, but disclosures on nodes 1 and 4 and rendered Layer 1
change. All 33 invariants pass. Passing those checks does not mean rendering already explains support
exclusions. Policy-only and retain-and-flag projections have identical targets, claims, and Layer 1 here;
the latter adds candidate inspectability.

## 10. Revised interpretation and answer-layer handoff

[I4-2b1](PHASE34_I4_2B1_OWNERSHIP_UNCERTAINTY_AUDIT.md) finds the six original exclusions recoverable:
p2/p11 current-document ownership (two supports), p40 external attribution (one), and p41 second-clause
current-document ownership (three). Correcting only those relations leaves all ten originals admissible.
All 26 evidence-role states and 13 requirement states then match v5; recovery, ParentClaims, AnswerPlan,
and Layer 1 are identical. This does not erase §9 or implement the correction.

I4-4 must eventually receive each candidate's relation, aggregation, kind, exact assertion and offsets,
plural supporting proposition IDs in discovery order, span anchor, attachment status, policy outcome,
independent guard exclusions, authority_veto, is_caption, role/instance/requirement identity, and the
authored/default policy identity sufficient to explain a rejection. Ownership resolution also needs its
bounded context/provenance proof and semantic/ruleset identity. Preserve excluded candidates as evidence
that exists but does not satisfy this requirement.

These fields enable distinct wording: current source found X; current source reports prior evidence for
X; a review/synthesis reports X; relevant evidence exists but fails the requirement's support rule.
The current ParentClaims/AnswerPlan path does not consume the full candidate list. No repair is made
here, and the legacy representative is display compatibility only.

## 11. Required decision register

| Decision | Accepted audit result |
|---|---|
| B1 | Keep exact empirical predicate in §3; fix upstream ownership before integrating it |
| B2 | Explicit relation membership AND aggregation condition AND kind membership |
| B3 | Complete explicit policy replaces absent default; no dimension merging |
| B4 | Defer authority-veto gating until structured claim-goal authoring |
| B5 | Captions metadata only |
| B6 | Retain and flag declared guards after successful grounding/relevance |
| B7 | Hedging can weaken certainty without destroying relevance; preserve the flag without redesigning detector |
| B8 | Evaluate every candidate's independent applicable gates |
| B9 | Corrected filled/ambiguous/missing contract in §6; no failure precedence |
| B10 | Aggregate the set; representative never decides semantic state |
| B11 | Defer same_local_assertion to I4-3 planning |
| B12 | Likely v6; preserve historical explicit v5; no version change now |
| B13 | Preserve six-exclusion uncorrected projection (§9); revised zero-exclusion interpretation in I4-2b1 |
| B14 | Preserve quantified recovery/downstream consequences and later I4-4 metadata needs |
| B15 | One policy mechanism for hierarchical and Simple Ask; authored policies differ |
| B16 | **NOT READY for bounded I4-2b implementation; B: fix attribution first** |

## 12. Verification and stop

Source artifact hashes and baseline replay equality were checked before counterfactual use.
The earlier read-only audit's focused schema/grounding/version checks recorded 122 passing tests.
Materialization rechecked the projections and 14 aggregation combinations; all 33 downstream invariants
pass in each projection. New ownership rules were not implemented or represented as passing production
tests. Documentation checks confirm exactly the two reports and experiment lineage changed.

The audits are complete; implementation is not authorized by this report. Stop after I4-2b1.
