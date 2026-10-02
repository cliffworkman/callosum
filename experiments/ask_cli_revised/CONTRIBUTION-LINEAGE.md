# Contribution lineage — semantic answer-sufficiency architecture

Follows [Credit the lineage](../../.claude/CREDIT-THE-LINEAGE.md): this architecture is not an
implementation of an identifiable external scholarly method or tool (`sufficiency_authoring.py`'s
own docstring is explicit that q_aib's contract content is Cliff's own researcher authorship, not
derived from a published method), but it has a real, worth-preserving internal contribution
lineage across a founder, a founder-plus-model design collaboration, and a model-driven
implementation pass. Recorded here rather than collapsed into a generic "AI-assisted" credit line.

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Researcher origin / disposition | Cliff Workman |
| 2026-09-30 | Elaboration / critique | Cliff Workman + ChatGPT |
| 2026-09-30 | Planning / implementation | Claude |

**Researcher origin / disposition (Cliff Workman).** Defined the scientific objective,
generalizability priority, researcher-authorized semantic supersessions, and decisions governing
what sufficiency should mean and when model-assisted recovery may become authoritative.

**Elaboration / critique (Cliff Workman + ChatGPT).** Developed and stress-tested the generic
semantic-sufficiency architecture, including relational binding, semantic-vs-search state,
quantifier/completion semantics, model-signal boundaries, evidence-admissibility distinctions, and
generalization controls.

**Planning / implementation (Claude).** Performed code-grounded planning and implemented the
accepted architecture, including deterministic mapping, replay/testing infrastructure, and the
model-assisted nomination diagnostic seam.

---

## Phase 2 — the live diagnostic replay (appended 2026-09-30; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Phase 2 experimental authorization | Cliff Workman |
| 2026-09-30 | Phase 2 live-client wiring, execution, manual adjudication, and analysis | Claude |

**Phase 2 experimental authorization (Cliff Workman).** Authorized exactly one live
model-assisted nomination replay over the preserved q_aib evidence, its hard scope boundaries, and
the manual-adjudication/readiness-evaluation protocol.

**Phase 2 live-client wiring, execution, manual adjudication, and analysis (Claude).** Wired the
deferred live-client construction, ran the one authorized replay, manually adjudicated every
accepted binding against its verified proposition, and reported the comparison and two
architectural findings in `MODEL_NOMINATION_DIAGNOSTIC_RESULTS.md`. No external scholarly method
or tool is implemented by this experiment, unchanged from the Phase 1 assessment above.

---

## Phase 3 — bounded fixes from the Phase 2 findings (appended 2026-09-30; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Evidence / critique | Phase 2 diagnostic |
| 2026-09-30 | Disposition / refinement | Cliff Workman |
| 2026-09-30 | Implementation | Claude |

**Evidence / critique (Phase 2 diagnostic).** The live model-assisted replay exposed
instance-key collisions under multi-role forking, proposition-driven instance-count inflation
from duplicate same-anchor propositions, and two semantic category-boundary errors
(`neural_measure_or_modality` accepting a neural finding rather than a measurement modality;
`behavior_or_behavioral_measure` accepting a self-report attitude measure as behavior).

**Disposition / refinement (Cliff Workman).** Interpreted those findings as bounded
representation and role-semantics problems rather than a need for architectural redesign, and
specified the fix: preserve the physical-anchor/proposition/semantic-instance distinctions,
derive instance identity from content rather than fork position, and tighten the two role
descriptions with domain-general (never benchmark-specific) exclusion language — plus an offline
replay of Phase 2's own recorded outputs to test the structural fix before any live rerun.

**Implementation (Claude).** Implemented and tested the four fixes
(`sufficiency_engine.derive_instance_key`; `nominate_with_model`'s anchor-based dedup with
preserved `supporting_proposition_ids` provenance; the tightened v9 `category_description` text
for the three affected roles; the `sufficiency_phase2_replay` offline replay harness), versioned
the contract to an unreviewed v9 candidate leaving v8 permanently immutable, and reported the
before/after structural comparison plus one newly-discovered issue (a same_proposition
joint-grounding interaction with the anchor-dedup's primary-id choice, left unfixed and
explicitly out of this increment's authorized scope).

---

## Phase 4 — generic support-set fix for the Phase 3 finding (appended 2026-09-30; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Disposition / refinement | Cliff Workman |
| 2026-09-30 | Implementation | Claude |

**Disposition / refinement (Cliff Workman).** Diagnosed Phase 3's newly-discovered c1 issue as a
generic representation problem (semantic completion depending on which proposition a collapsed
nomination happened to select as primary) and specified a bounded, generic fix: joint-grounding
must consult a binding's full recorded proposition-support set, never the primary id alone, while
explicitly forbidding any loosening to evidence-anchor identity.

**Implementation (Claude).** Verified the exact c1 support sets genuinely intersected (on `p2`)
before implementing, per the instruction to stop and report rather than build a same-anchor
verifier if they did not. Implemented `sufficiency_engine._support_set`/the generalized
`_verify_same_proposition` (intersection of every role's support set), added 5 adversarial tests,
and confirmed the offline replay of Phase 2's own recorded outputs now matches Phase 2's actual
live states exactly, with only instance counts differing.

---

## Phase 5 — v9 live rerun, empirical validation (appended 2026-09-30; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | v9 researcher approval + experimental authorization | Cliff Workman |
| 2026-09-30 | Live experimental execution, manual adjudication, and analysis | Claude |

**v9 researcher approval + experimental authorization (Cliff Workman).** Reviewed and approved
the v9 frozen contract's exact hash after confirming the mechanical review gate (v8/v9
byte-identity, the exact 3-description diff, benchmark-neutral wording), then authorized exactly
one live model-assisted nomination rerun over the same preserved q_aib evidence to determine
empirically whether v9's tightened generic role descriptions changed model behavior.

**Live experimental execution, manual adjudication, and analysis (Claude).** Ran the one
authorized v9 replay (mechanically clean: 14 calls, 0 failures, 0 grounding rejections, thinking
confirmed OFF throughout), manually adjudicated every one of 9 distinct accepted semantic claims
against its verified proposition, manually reviewed every decline for false negatives, and
reported the full comparison against Phase 2 in `PHASE5_V9_LIVE_RERUN_RESULTS.md`. **Empirical
result:** both of Phase 2's originally-identified category-boundary errors disappeared under v9's
wording (confirmed, not assumed — c1's own modality attempt now correctly declines; c5's own
behavior attempt now correctly declines EBQ and c5 honestly reverts to `partially_filled`). A
new, different nomination weakness was found in c2 (a circular/self-referential match, not a
repeat of either original error), informing a **NOT READY** recommendation for
sufficiency-directed recovery experimentation. Recovery was not enabled or run.

---

## Phase 6 — generic specific-instance confirmation gate (appended 2026-09-30; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Evidence / critique | Phase 5 live rerun |
| 2026-09-30 | Disposition / refinement | Cliff Workman |
| 2026-09-30 | Implementation | Claude |

**Evidence / critique (Phase 5 live rerun).** The second live replay found a new, different
nomination weakness: c2's `behavior_or_behavioral_measure` role accepted a vague, self-referential
nomination ("described a behavioral manifestation of the 'anomalous-is-bad' stereotype affecting
prosociality") that restates an already-established manifestation fact rather than independently
naming a specific behavior or measure — flipping c2 from the honest `partially_filled` to a false
`filled` state built on weak grounding.

**Disposition / refinement (Cliff Workman).** Diagnosed this as a generic category-boundary
problem distinct from Phase 3's wording-tightening approach — not "which category does this
belong to" but "does this nomination name a SPECIFIC instance at all, as opposed to merely
asserting one exists" — and specified a bounded, generic fix: a second, VETO-ONLY nomination key
(specific-instance confirmation) that can only drop a candidate the first key already produced,
never create, modify, or broaden one. Required a host-generated closed `candidate_id` enum (never
a `proposition_id`, so the validator cannot rename proposition identity), explicit fail-closed
rules for every malformed/omitted/ungrounded decision, preservation of the original nomination's
own provenance alongside new validation provenance, no contract version change, and an offline
replay of Phase 5's own already-completed manual adjudication (never a new judgment call) before
any further live diagnostic.

**Implementation (Claude).** Implemented `qwen.specificity_prompt`/`specificity_schema`/
`QwenTasks.verify_specific_instances` and `sufficiency_mapping.confirm_specific_instances` (the
second key), wired into `_bind_role_candidates` between nomination and binding. Added 21 synthetic
tests across four benchmark-neutral domains (behavior, population, intervention, neural
region/modality) plus nine mechanical fail-closed/scope-boundary proofs, and a new
`sufficiency_phase5_replay.py` module that replays Phase 5's own recorded v9 outputs through a
validator scripted to Cliff's own frozen adjudication table — vetoing exactly the one nomination
judged "Incorrect — Vague/circular," approving every other nomination Phase 5 actually produced.
**Result (no live model call):** c2 drops from Phase 5's false `filled`/3-instances to the honest
`partially_filled`/2-instances; the two surviving instances are the genuine "visual attention"
findings, which legitimately fail the pre-existing `same_proposition` joint-grounding check
against a different proposition than the manifestation-evidence role's own — confirming the
state change is architecturally correct, not merely the gate suppressing a role. Every other
child/requirement (c1, c3, c4, c5, c6 ×2, c8, c9, c10, c11, c12) matches Phase 5's own live v9
result exactly. Extended the leakage suite with `SpecificityPromptLeakageTests` (3 tests) over the
new prompt. v9 remains byte-identical throughout (hash unchanged); no live diagnostic was run.

---

## Phase 7 — live v9 two-key diagnostic, empirical validation (appended 2026-09-30; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Pre-run gate review + experimental authorization | Cliff Workman |
| 2026-09-30 | Live experimental execution, manual adjudication, and analysis | Claude |

**Pre-run gate review + experimental authorization (Cliff Workman).** Reviewed the Phase 6
two-key architecture and, after confirming an explicit 6-point mechanical pre-run gate (v9
byte-identity, no v10, the nomination-then-confirmation call order, veto-only behavior, recovery
disabled, leakage tests green), authorized exactly one live execution of the v9 model-assisted
nomination diagnostic with the Phase 6 specificity-confirmation gate active — pre-registering
seven numbered success criteria and a two-key manual adjudication protocol (nomination-stage
correctness, validator-decision correctness, post-gate claim correctness, each classified
independently) before any output was inspected.

**Live experimental execution, manual adjudication, and analysis (Claude).** Ran the one
authorized live replay (mechanically clean: 19 calls — 14 nomination + 5 specificity — 0
failures, 0 grounding rejections, thinking confirmed OFF throughout), manually adjudicated all 11
distinct specificity candidates across both stages independently, and reported the full
comparison against Phase 2/Phase 5 in `PHASE7_LIVE_TWO_KEY_DIAGNOSTIC_RESULTS.md`. **Empirical
result: the specificity gate did not fix Phase 5's false-fill case and introduced a severe,
previously-unobserved new failure mode.** It accepted the one nomination it was built to veto
(c2's circular claim — an incorrect accept), while incorrectly vetoing 8 of the remaining 10
genuinely correct candidates across three unrelated roles and three unrelated children (amygdala
×2, all four of c8's named traits, both of c6's EBQ anchor groups) — a systematic false-negative
rate (73%) the authorization's own pre-registered criteria classify as disqualifying for recovery
use. c8→c9 parent propagation collapsed from Phase 5's correct 4→4 to 0→0 as a direct downstream
consequence. No code, prompt, or gate parameter was changed after observing this result, per the
authorization's explicit constraint. Recommended **NOT READY FOR RECOVERY EXPERIMENTATION**, with
the live validator's own directionally-inverted miscalibration flagged as the newly discovered
issue warranting investigation before any further specificity-gate experimentation. Recovery was
not enabled or run.

---

## Phase 8 — forensic/planning pass, no implementation (appended 2026-09-30; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Evidence | Phase 7 live diagnostic |
| 2026-09-30 | Disposition | Cliff Workman + ChatGPT |
| 2026-09-30 | Forensic analysis + architecture evaluation | Claude |

**Evidence (Phase 7 live diagnostic).** The generic Qwen specificity-confirmation gate showed
severe inverted calibration: it retained the known vague false nomination (c2's circular claim)
while vetoing most genuinely specific candidates (8 of the other 10 candidates offered to it).

**Disposition (Cliff Workman + ChatGPT).** Rejected further blind tuning of the second-pass
validator and redirected work toward forensic analysis of the remaining false-fill shape and
recovery-safe alternatives, explicitly instructing against assuming "improve the validator prompt"
was the answer, and requiring the analysis to distinguish observations from hypotheses, verify no
hidden implementation explanation, analyze the Phase 5 false fill generically, evaluate six named
alternative architectures (including one the author explicitly asked to be treated with
skepticism), run a benchmark-neutral generalization test, and recommend exactly one next path
without implementing it.

**Forensic analysis + architecture evaluation (Claude).** Reconstructed all 11 Phase 7 specificity
decisions verbatim from the frozen trace against their exact prompts/passages; found 0 grounding
rejections, 0 schema/mapping defects, 0 truncation — the failure is genuinely semantic, not
structural. Found 7 of 8 incorrect vetoes share a concrete syntactic shape (the nominated span's
grammatical head is an abstract/occurrence noun rather than the referent itself — e.g. "amygdala
**response**," "**attitudes** (IAT and EBQ)"); one incorrect veto (EBQ) and the interaction/order
question are left honestly unexplained rather than forced into the same story. Critically found
that a naive cross-role non-redundancy rule (reject an identification role sharing a proposition
with its sibling evidence role) would incorrectly reject Phase 5's own correctly-accepted c1/c4
amygdala finding alongside c2's false one — both share a proposition with their sibling role, and
the real distinguishing property is whether the nominated span names a referent at all, not
proposition identity. Evaluated all six proposed alternatives (including an explicit, evidence-
grounded rejection of the deterministic POS/capitalization guard, proven unsafe against Cliff's own
canonical "mindfulness training"/"adolescents in Japan" examples) and recommended retiring the
second-pass validator in favor of reformulating the single first-stage nomination task toward
minimal-referent extraction with an explicit null-on-no-referent instruction and an authoring-time
contrastive exclusion, backed by a narrow deterministic redundancy check and a recovery-controller-
side provisional-fill policy that removes the catastrophic failure mode independent of mapping
accuracy. Full detail in `PHASE8_FORENSIC_PLANNING_RESULTS.md`. No code was changed, no live model
call was made, and v9 remains byte-identical (hash unchanged). The recommendation is not
implemented in this phase.

---

## Phase 9 — single-stage minimal-referent mapper + provisional stop-search policy (appended 2026-09-30; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Evidence | Phase 8 forensic analysis |
| 2026-09-30 | Disposition / refinement | Cliff Workman + ChatGPT |
| 2026-09-30 | Implementation | Claude |

**Evidence (Phase 8 forensic analysis).** Established that Phase 7's validator failure was
genuinely semantic/model-level; showed that proposition-sharing cannot distinguish valid
identification from circular occurrence assertions; identified referent extraction as the
meaningful distinction.

**Disposition / refinement (Cliff Workman + ChatGPT).** Accepted retirement of the second-pass
validator, resolved the A+D design as generic minimal-referent extraction at the
`model_nomination_only` task level while preserving v9 unchanged, declined to make the proposed
redundancy smell-test an authoritative veto (explicitly instructing it be omitted rather than
risk a brittle heuristic), and separated semantic answer sufficiency from stop-search authority
so model-only fills remain provisional for recovery control.

**Implementation (Claude).** Retired `confirm_specific_instances`/`specificity_prompt`/
`specificity_schema`/`QwenTasks.verify_specific_instances` from the active mapping path entirely
(`_bind_role_candidates` is back to ONE model operation: nomination -> deterministic grounding/
admissibility -> RoleBinding); their exact specification remains in git history
(commits `f0814716`/`8bf203b2`) and the Phase 6/7 markdown reports, and
`sufficiency_phase5_replay.py` was redesigned to reproduce Phase 6 Part F's historical finding as
a self-contained scripted filter, with zero dependency on the retired code. Reformulated
`qwen.nomination_prompt` toward minimal-referent extraction with an explicit null-on-no-referent
instruction and 5 benchmark-neutral worked examples (population/intervention/behavior/
measurement/trait), explicitly not requiring noun-phrase or capitalized/proper-noun shape (the
exact property Phase 8 found the old live validator's incorrect vetoes clustered on). Added
`sufficiency_engine.compute_stop_search_certified` (a parallel per-`instance_quantifier`
aggregation over "clean completion" rather than "any completion," mirroring `_AGGREGATORS`'s own
dispatch shape) and wired it into `compute_recovery_needed`'s existing `filled` branch, giving a
model-dependent fill the same bounded-breadth single-recovery-opportunity shape `open_list`
already used — `state` itself is never overloaded. Declined to implement the redundancy
smell-test (Part D), per instruction, after confirming no robust version could be defined without
risking exactly the false-positive-veto failure mode Phase 7 already demonstrated. Proved the
reformulated nominator's plumbing can represent all 11 benchmark-neutral ACCEPT/DECLINE examples
via fake clients (explicitly labeled as plumbing proof, not a claim about live model behavior),
and built a hand-scripted COUNTERFACTUAL replay over the real preserved q_aib evidence showing the
proposed minimal-referent nominations remove c2's false fill while every other previously-correct
finding (c1, c4, c6, c8, c8→c9 propagation) survives intact — a real cross-call collision bug in
this fixture's own first draft (c5 spuriously completing) was caught and fixed during
construction, documented in the fixture's own module docstring rather than silently corrected
away. v9 remains byte-identical throughout (hash unchanged); no live model call was made in this
phase. Full detail in `PHASE9_SINGLE_STAGE_MAPPER_RESULTS.md`.

---

## Phase 10 — live v9 single-stage diagnostic + parent_context provenance audit (appended 2026-10-01; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-10-01 | Pre-run gate review + experimental authorization | Cliff Workman |
| 2026-10-01 | Live experimental execution, manual adjudication, code audit, and analysis | Claude |

**Pre-run gate review + experimental authorization (Cliff Workman).** Reviewed Phase 9's
single-stage architecture and, after confirming an explicit 7-point mechanical pre-run gate,
authorized exactly one live execution of the reformulated minimal-referent-extraction mapper over
the same preserved q_aib evidence — pre-registering the adjudication protocol (correct/incorrect/
ambiguous per accepted nomination, false negatives among declines), the primary empirical question
(does Qwen reliably follow the new extraction instruction), and a required code-level audit of
whether model-dependence survives `parent_context` propagation, with an explicit pre-registered
rule: if it does not, recommend a bounded follow-up before recovery regardless of how well the
mapper itself performs.

**Live experimental execution, manual adjudication, code audit, and analysis (Claude).** Ran the
one authorized live replay (mechanically clean except 3 genuine grounding rejections — a first in
this arc, traced to a benign PDF-whitespace artifact, not a model defect), manually adjudicated all
18 distinct accepted nominations against their real source passages, and reported the full
comparison against Phase 5/Phase 7 in `PHASE10_LIVE_SINGLE_STAGE_DIAGNOSTIC_RESULTS.md`.
**Empirical result: a mixed, role-dependent outcome, not a clean win.** The reformulation
dramatically improved c8's extraction (minimal referents instead of abstract-headed phrases,
exactly as intended) but did NOT fix c2's circular-assertion problem — the model extracted a
*different* vague occurrence-assertion span from the same sentence rather than correctly declining
— and introduced new false positives in c5 (a direct violation of the role's own explicit textual
exclusion, accepting a self-report questionnaire for a role that names one as excluded), c10, and
c12 (category-adjacent substitutions), none of which any prior phase ever produced. Precision
regressed sharply: 9 correct / 7 incorrect / 2 ambiguous of 18, versus Phase 5's 8/1/0 of 9.
**Code-level audit, confirmed by a read-only synthetic reproduction of the exact c8→c9 shape (no
file modified): transitive model-dependence IS lost through `parent_context`** —
`_instance_completion_is_model_dependent` checks only the literal `candidate_source` string, which
`map_paired_requirement`'s own re-stamping always sets to `"parent_context"` regardless of the
inherited binding's true origin, preserved only as unparsed free text. This did not cause an
unsafe certification anywhere in this run's own data (every `filled` requirement also carried its
own directly model-sourced role), but the gap is real and would bite the moment a propagated-only
completion occurs. Per the pre-registered rule, recommended **READY FOR A BOUNDED FOLLOW-UP BEFORE
RECOVERY** — two independent sufficient reasons: the mapper's own regressed precision, and the
confirmed provenance gap. No code was changed and no fix was applied in this phase. Recovery was
not enabled or run.

---

## Phase 11 — rollback to the strongest mapper, transitive provenance repair, recovery-targeting audit (appended 2026-10-01; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-10-01 | Evidence | Phase 10 live diagnostic |
| 2026-10-01 | Disposition / refinement | Cliff Workman + ChatGPT |
| 2026-10-01 | Implementation / audit | Claude |

**Evidence (Phase 10 live diagnostic).** The minimal-referent reformulation improved one mapping
shape but sharply reduced overall precision, failed to resolve the original circular false fill,
introduced new semantic substitutions, and confirmed loss of transitive model-dependence through
`parent_context`.

**Disposition / refinement (Cliff Workman + ChatGPT).** Rejected further nomination-prompt
tuning, selected rollback to the empirically strongest Phase 5 v9 mapper (restored from git
history, never reconstructed from memory), retained provenance-aware provisional stop-search as
the safety mechanism while repairing its transitive gap, and identified meaningful recovery
targeting for provisional fills as the remaining prerequisite to recovery experimentation —
explicitly instructing the targeting question be audited, not implemented, unless the fix proved
purely mechanical.

**Implementation / audit (Claude).** Restored `qwen.nomination_prompt` byte-for-byte to the exact
text at commit `f7be3175` (Phase 5's own commit), verified by direct function-output comparison
(not just source diff). Added `sufficiency_mapping._propagated_provenance` — a single shared
helper (de-duplicating two previously-identical inline constructions) that preserves
`candidate_source="parent_context"` as the immediate, never-overloaded source identity while
adding structured `upstream_model_dependent`/`source_lineage` fields that survive arbitrary
propagation depth without ever parsing `provenance["detail"]`'s free text. Updated
`sufficiency_engine._instance_completion_is_model_dependent` to consult the new structured field
alongside the existing immediate-source check. Reproduced Phase 10's own synthetic c8→c9 shape and
confirmed `compute_stop_search_certified` now correctly returns `False` where it previously,
incorrectly, returned `True`. Added 11 adversarial tests covering direct/one-hop/two-hop
propagation, fully-deterministic ancestry, mixed required/optional roles, hash-independence, and
an explicit proof the certification path never reads `detail`'s free text. **Audited (code-traced,
not inferred) the full recovery-targeting path** from `compute_recovery_needed` through actual
query construction (`qwen.recovery_query(subquestion=..., obligation_note=gap.get("display") or
gap.get("note", ""))`) and found `sufficiency_mapping.recovery_hint` has **zero production call
sites** — sufficiency-driven recovery gating operates entirely at child granularity (any
requirement needing recovery triggers that whole child's pre-existing, sufficiency-blind
obligation note), with no role-level targeting and no redirection to an upstream parent child even
when a child's entire provisionality is inherited. Classified this **REDESIGN NEEDED** — the
existing gap representation has no slot for "which role," "direct or transitive," or "which child
truly needs corroboration," which are semantic design choices, not mechanical plumbing — and
reported rather than implemented a fix, per instruction. v9 remains byte-identical throughout
(hash unchanged); no live model call was made in this phase; recovery was not enabled or run. Full
detail in `PHASE11_ROLLBACK_AND_PROVENANCE_REPAIR_RESULTS.md`.

---

## Phase 12 — structured RecoveryTarget architecture, implemented (appended 2026-10-01; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-10-01 | Evidence | Phase 11 recovery-targeting audit |
| 2026-10-01 | Design direction | Cliff Workman + ChatGPT |
| 2026-10-01 | Design (3 review rounds) + implementation | Claude |

**Evidence (Phase 11 recovery-targeting audit).** Established by direct code trace that
sufficiency-driven recovery collapses requirement-level semantic state to a child-level boolean
and a generic obligation query; `recovery_hint` is dead production code; inherited provisionality
cannot be redirected upstream; classified REDESIGN NEEDED.

**Design direction (Cliff Workman + ChatGPT).** Proposed replacing child-level sufficiency
recovery with structured RecoveryTargets that preserve role/reason/ownership, redirect inherited
uncertainty to its originating obligation, avoid feeding untrusted model values back into search
by default, deduplicate shared upstream recovery work, and use a bounded one-attempt policy for
provisional fills. Three subsequent review rounds (not re-narrated here; see the session's own
design record) progressively forced quantifier-, instance-, and alternative-group-aware
granularity; a first-class `relationship_unverified` reason; a confidence-aware relationship-
context rule; a hashed `target_id` carrying a `goal_mode` field; `child_id`-explicit (not
convention-inferred) origin provenance; and an unconditional generic-gap/structured-target
coexistence policy — each correction grounded in a direct re-read of the real engine code, not
assumed.

**Design + implementation (Claude).** Shipped the reviewed architecture, test-driven
(`test_sufficiency_recovery_targets.py`, 38 tests) against the real codebase, with four further
corrections surfaced only by building and running it — none anticipated in the design review
itself:

1. **Provisional corroboration is checked PER INSTANCE, never gated on the requirement's own
   aggregate `state`.** The design review's own `state=="filled"` gate (mirroring
   `compute_stop_search_certified`'s documented scope) turned out to silently defer — potentially
   forever — corroboration for a `for_each_discovered_instance`/`at_least_n`/multi-instance
   `exists` requirement's own already-complete-but-model-dependent instance whenever a SIBLING
   instance was still incomplete (the real c9 shape: one pairing done, three still missing their
   own scale). Fixed by dispatching per instance (`_targets_for_instance`), consulting
   `sufficiency_engine._instance_completion_is_model_dependent` directly rather than the
   whole-requirement aggregate.
2. **Scoping follows the requirement's RUNTIME instance count, never the declared `multi_instance`
   flag.** The real preserved Phase-5 replay surfaces a requirement (`c6#suff:brain-attitude`)
   declared `multi_instance=False` whose own model-nomination forking (`sufficiency_mapping.
   _fork_instances_over_role`) still produced two final, independently model-dependent instances.
   Trusting the declared flag would have collapsed two genuinely distinct corroboration needs into
   one target; fixed by scoping on `len(requirement["instances"])` directly.
3. **Provisional-corroboration origin grouping keys by `(requirement_id, instance_key)`, never
   `requirement_id` alone** — the same c6 shape exposed this: without the instance-key component,
   its two independent nominations would have merged into one target, discarding one.
4. **Relationship-context scaffolding needed a length bound.** The offline inventory (below) was
   the first thing to surface this: `achieved_outcome_predicate`'s own detector deliberately
   returns the WHOLE PASSAGE as `exact_text` ("a stated result is a property of the passage as a
   whole"), which produced an unusably long, non-"short phrase" hint when offered as relationship
   scaffolding (`c12`'s own `observed_effect_or_outcome` role). Fixed with a length bound
   (`_MAX_CONTEXT_EXACT_TEXT_LENGTH = 80`), keyed on length rather than strategy name to stay
   generic over any current or future `mapping_strategy`.

**Shipped:** `sufficiency_recovery_targets.py` (new module: `new_recovery_target`/`new_target_id`
— canonical-JSON SHA-256 identity over `{search_child_id, requirement_id, reason, goal_mode,
target_roles, scope}`, excluding `trigger_child_id`/`affected_descendants`/the `at_least_n`
deficit count by design; quantifier-aware generation for `exists`/`all_requested_categories`/
`for_each_discovered_instance`/`at_least_n`/`open_list`; required-vs-alternative conjunctive/
disjunctive semantics; zero-instance/first-instance discovery, including upstream deferral when a
parent-backed `for_each_discovered_instance` child's parent has no source; the confidence-aware
hint builder, dispatched on `goal_mode`). `sufficiency_diagnostic._stamp_model_dependency_origins`
(new: stamps `{child_id, requirement_id, role, instance_key}` onto a fresh `model_mapping`
binding, called from `compute_diagnostic_sufficiency_map`'s existing per-child loop — never from
`sufficiency_mapping.py`, preserving that module's own child-agnostic charter).
`sufficiency_mapping._propagated_provenance` gained one more carried-forward (never newly minted)
field, `model_dependency_origins`. `compute_recovery_candidates`/`recovery_hint` deleted outright
(confirmed by grep: no consumer outside this file parsed the old key/shape); their call sites and
tests ported to `compute_recovery_targets`/`recovery_query_hint`, including the non-leakage
guarantee. `e2e.py`'s sufficiency-extension block now generates targets via
`compute_recovery_targets`, appends one synthetic `gaps` row per target (`field_id`/
`subquestion_id` = the target's real search-owner child id, never a fresh per-target id; per-target
identity rides an inert `_recovery_target_id` key `cli._recover` never reads) **unconditionally**
— a structured target is never suppressed merely because the generic coverage pass already gapped
the same child, since Phase 11 itself established the generic query is sufficiency-blind. Output
key renamed `sufficiency_recovery_candidates` → `sufficiency_recovery_targets` (shape changed; no
external consumer, confirmed by grep). Zero changes to `_recover`, `qwen.recovery_query`,
`_process_hits`, retrieval, `compute_recovery_needed`, or `compute_stop_search_certified`.

**Offline inventory (no live model call, no retrieval, no recovery execution):** Phase 5's own
frozen recorded nominations (`sufficiency_phase5_replay.replay`, Cliff's already-frozen manual
adjudication, not re-adjudicated) replayed through the current mapper/stamping pipeline
(`sufficiency_recovery_targets_inventory.py`) produced **24 real RecoveryTargets**. Confirms,
against real data rather than synthetic fixtures: `c9` does **not** redirect upstream — its own
four discovered pairings each produce a local `partial` target for their own missing scale role,
never a provisional-fill redirect to `c8` (the concrete doubt Cliff's own review round raised,
confirmed rather than assumed); `c4→c6` **does** genuinely redirect (one merged target,
`affected_descendants=["c4","c6"]`); `c6` independently exercises the real multi-instance-
corroboration shape (two separate targets for two distinct model-nominated attitude measures);
`c2` reproduces its own historically-documented `relationship_unverified` shape (two instances,
each failing joint-grounding against a different proposition than its own manifestation evidence).

**Regression:** `test_sufficiency_recovery_targets.py` 38/38; the full sufficiency-family suite
(10 files) 245/245; the full `experiments/ask_cli_revised/` tree **2097 passed, 11 skipped, 2
failed** — both failures confirmed pre-existing and unrelated by direct comparison against
unmodified HEAD (a `hierarchy_contract.py` pin-drift failure in a file never touched this phase,
and a `--preflight-only` readiness-code mismatch reproduced identically on baseline). v9
`combined_hash` confirmed byte-identical throughout:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`. Recovery gate remained OFF
throughout; no live model call, no retrieval, no recovery execution, no contract or v10 change.

---

## Phase 13 — one live, isolated RecoveryTarget experiment (appended 2026-10-01; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-10-01 | Target selection + falsification criteria | Cliff Workman |
| 2026-10-01 | Pre-run gate review, isolation harness, live execution, adjudication | Claude |

**Target selection + falsification criteria (Cliff Workman).** Selected `target_id
c4::0c3e1a392e7868e4` from Phase 12's own real offline inventory (the c4→c6 redirected provisional-
corroboration target) as the single authorized live experiment, with six pre-registered mechanical
falsification criteria (redirection, confirmation-bias, dedup, target-id, scope, provenance) and
an explicit "no retry for a scientifically valid but disappointing result" constraint.

**Pre-run gate review, isolation harness, live execution, adjudication (Claude).** Found and
disclosed a real, pre-existing, unrelated blocker before any live call (hierarchy pin-drift in
`hierarchy_contract.py`, confirmed via direct hash comparison and git log to predate this work and
to leave the hierarchy data itself unaffected) and obtained Cliff's explicit decision before
proceeding, rather than silently bypassing a safety gate. Built the smallest diagnostic-only
isolation harness (`phase13_c4_recovery_experiment.py`) that changes zero `_recover`/retrieval
semantics, reusing `e2e.seed_pass_from`'s own seeding closure and the unchanged `cli._recover`/
`stages.run_coverage_audit`. Verified all 12 Section-B mechanical gates in dry-run before making
the one live call. Executed exactly one recovery attempt (qwen3.5:9b, `think=False`) plus the
mechanical coverage-sealing step (phi4:14b) the sufficiency recomputation structurally requires —
found one new, verified, but ambiguously-relevant piece of evidence (a theory-of-mind/RTPJ
passage, not a direct bias-manifestation finding). **Found and corrected a real methodological
error in its own first recomputation**: comparing a with-model "before" (Phase 5's replay) against
a deterministic-only "after" (this run's own recomputation, correctly scoped without an
additional, unauthorized model-nomination call) would have shown large, spurious changes across
every unrelated child; verified offline, with no further live call, that every child except c4
reproduces its own deterministic-only baseline exactly, isolating the true, honest result: c4's
state is unchanged by this experiment under a valid apples-to-apples comparison, and whether the
new evidence or the prior amygdala nomination would survive a further model-nomination pass is
genuinely undetermined, not a negative finding. All six pre-registered falsification criteria
passed; architecture judged mechanically valid; recovery usefulness judged "no material change."
Recommended next step: B (mechanically valid, query/retrieval targeting refinement candidate
noted, not validated). No second target, no broader run. v9 `combined_hash` unchanged:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`. Full detail in
`PHASE13_C4_LIVE_RECOVERY_EXPERIMENT_RESULTS.md`.

---

## Phase 14 — post-recovery semantic-consumption audit and design (appended 2026-10-01; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-10-01 | Scope: audit the actual production call graph, design the consumption architecture | Cliff Workman |
| 2026-10-01 | Call-graph trace, architecture comparison, design document | Claude |

**Scope (Cliff Workman).** Asked whether/how recovery evidence can reach model-assisted roles,
and to design (not build or run) the architecture that would close that loop, strictly bounded to
audit + design: no live model call, no retrieval, no contract change, no pin re-freeze.

**Call-graph trace, architecture comparison, design document (Claude).** Traced every call site
(grep, not inference) and found a materially larger fact than the question's own framing assumed:
production `e2e.py`/`__main__.py` perform **zero** model-assisted sufficiency nomination at any
point — initial pass or post-recovery, with or without recovery. Compared three consumption
architectures against the real mapper code: no remap (today's status quo, leaves
`provisional_corroboration` targets permanently unresolved in-run), broad remap (costly,
unattributable — re-attempts every `model_nomination_only` role hierarchy-wide), and
target-scoped remap (recommended — a role-scoped model-client wrapper that forwards only the
target role's exact `category_description` and declines elsewhere, exploiting the fact that every
`model_nomination_only` role already gets a deterministic-or-model attempt independent of whether
a client is supplied). Confirmed the confirmation-bias guarantee the design needed is already
structurally true (`qwen.nomination_prompt` has no slot for a prior answer). Designed the
re-mapping semantics (input map, outcome handling for all five possible nomination results,
provenance as a caller-level snapshot diff, confirmed post-recovery bindings remain provisional
with zero code change) and the smallest next live experiment (one role-scoped nomination call for
c4's `named_brain_region_or_network`), verifying the proposed string-based scoping is safe for
that one case (category-description globally unique in frozen v9) while recommending a robust
`(child_id, requirement_id, role)`-based scoping for any future, more general use. No
implementation, live call, or retrieval performed; v9 unchanged. Full detail in the Plan Mode
record presented and approved before Phase 15's own implementation began.

---

## Phase 15 — one live, target-scoped semantic-consumption experiment (appended 2026-10-01; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-10-01 | Required refinement over Phase 14's sketch; stop-condition review; proceed decision | Cliff Workman |
| 2026-10-01 | Hybrid control/experimental harness, offline preflight, live execution, result analysis | Claude |

**Required refinement, stop-condition review, proceed decision (Cliff Workman).** Required a
CONTROL-map-vs-EXPERIMENTAL-map design (both over the identical post-recovery ledger, every
non-target role held fixed to Phase 5's own recorded history) in place of Phase 14's simpler
deterministic-vs-with-model sketch, to avoid re-creating Phase 13's own comparability problem.
Specified a pre-registered falsification taxonomy (five mechanical outcomes, none ranked), an
explicit candidate-visibility gate, and a named stop condition (Section C: if the control map
shows unrelated semantic drift from the replay/control mechanism itself, stop before the live
call). When that condition genuinely fired during the offline preflight, reviewed the specific
finding presented and made the explicit decision to proceed, rather than the decision being
assumed or defaulted.

**Hybrid harness, offline preflight, live execution, result analysis (Claude).** Built
`phase15_c4_semantic_consumption_experiment.py`, replicating
`compute_diagnostic_sufficiency_map`'s own per-child topological loop (production code
unmodified) to compose a per-child-scoped client — something that function's single shared
`model_client` parameter cannot express. Ran the full offline preflight (50/50 gates): confirmed
the recovered RTPJ evidence (p27) is visible in c4's target candidate pool; dry-ran the full
build with a non-live stand-in, proving mechanically that exactly one call-site would go live;
and found a **real, confirmed** instance of the brief's own named stop condition — the mandatory
C2 re-sealing call (needed to seal the new evidence into one ledger) has a genuine, confirmed
side effect on unrelated propositions' `responsive_obligation_ids`, drifting c5/c6/c12's
`direction`/`effectiveness` fields relative to the Phase-5 baseline. Verified this drift is
confined to those two fields (never requirement state or role bindings) and is structurally
identical between the CONTROL and EXPERIMENTAL maps, so it does not contaminate the actual
comparison — but per the brief's own literal instruction, stopped and presented the finding
rather than deciding unilaterally to proceed or abort. After Cliff's explicit decision to
proceed, executed the one authorized live call (`qwen3.5:9b`, `think=False`, isolated endpoint,
44.1s). Result: **Outcome 4, multiple bindings** — the model recognized the newly recovered RTPJ
passage as an independently specific named brain area distinct from the pre-existing amygdala
finding, and the existing, unmodified instance-forking mechanism (`_fork_instances_over_role`)
surfaced both as separate grounded candidates rather than the model simply re-affirming or
discarding either. c6 inherited the new region via the existing, unmodified single-instance
parent-context fallback with zero new code, exactly as predicted. **Found and fixed a real bug in
its own reporting code while writing up the result** (not a bug in the underlying computation):
the harness's first draft hard-coded the "expected to change" exclusion set as `{c4, c6}` when
checking for unrelated isolation failures, which flagged `c5` as a false "isolation failure" —
investigation (purely offline, replaying the already-recorded live result, no second live call)
found c5 shares c6's exact structural relationship to c4 (both declare
`parent_context_roles=["named_brain_region_or_network"]` with `parent_of` pointing at c4) and is
therefore *also* legitimately expected to change, exactly mirroring c6's own change — not a new
drift class. Fixed to derive the exclusion set structurally from the contract itself; re-verified
offline that with the fix, the true unrelated-isolation-failure set is empty (c1/c2/c3/c8/c9/c10/
c11/c12 all byte-identical between CONTROL and EXPERIMENTAL). Both open questions (Section N)
answered separately: semantic-consumption mechanism **YES** (validated end to end on a real,
non-trivial case); scientific effect **Outcome 4** (reported as a mechanical fact, not ranked
good or bad). Existing sufficiency test suites (129 tests) pass unchanged; zero production code
touched; v9 `combined_hash` unchanged:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`. No second live call, no
recovery search, no contract or pin re-freeze. Full detail in
`PHASE15_C4_SEMANTIC_CONSUMPTION_RESULTS.md`.

---

## Phase 16 — parent-context multiplicity and parent-instance eligibility (appended 2026-10-01; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-10-01 | Evidence | Phase 15 live semantic-consumption experiment |
| 2026-10-01 | Design direction | Cliff Workman + ChatGPT |
| 2026-10-01 | Code trace, verification, implementation | Claude |

**Evidence (Phase 15 live semantic-consumption experiment).** A target-scoped remap produced
multiple parent instances and demonstrated that current positional parent-context propagation
selects only `instances[0]`, allowing an incomplete newly-nominated parent instance to displace a
complete existing parent instance downstream.

**Design direction (Cliff Workman + ChatGPT).** Identified parent-instance eligibility,
multiplicity preservation, and order invariance as prerequisites before production model-assisted
sufficiency integration. Resolved Phase 16's own open design decision (left unresolved in the
plan-mode design pass) as a uniform rule: a parent instance may supply `parent_context` only if
the requested role binding is filled AND the instance itself is `complete`, applied identically
across every quantifier shape (`exists` and `for_each_discovered_instance` alike, no special-
casing for c9) -- `instance.complete` explicitly kept separate from stop-search certification, so
a complete-but-model-dependent parent instance still propagates, with its model-dependence
carried forward unchanged. Required that own-evidence-first never duplicate per eligible parent,
that the existing paired-mapping machinery be generalized rather than forked into a second
parallel implementation (unless it was found to carry quantifier-specific assumptions that made
generalizing it unsafe), that the mixed-instance `exists` RecoveryTarget gap be closed in the
same pass, and that the `dependency_origins` merge gap be fixed defensively without touching
target identity absent a real collision.

**Code trace, verification, implementation (Claude).** Traced every real v9 `parent_context_
roles` use exhaustively (c4->c5, c4->c6, c8->c9 -- confirmed no others exist) and the complete
parent-context call graph before writing any code. Implemented the shared `eligible_parent_
instances` primitive in the domain-agnostic engine layer, used identically by the mapper and the
RecoveryTarget layer so the two can never disagree about whether a usable parent exists. Found
`map_paired_requirement` already fully quantifier-agnostic after instance generation (it never
read `instance_quantifier` at all), so generalized it directly rather than forking a second
implementation -- retiring `_parent_context_binding_for_single_instance` outright (confirmed zero
remaining references anywhere) and collapsing `map_any_requirement`'s two parent-context branches
into one. Proved order-invariance adversarially, not just by design, using the real recorded
Phase-15 nomination output in both list orders: before this fix, reversing the model's own raw
output order flips which region c6 inherits (RTPJ vs. amygdala) on identical underlying evidence;
after, both orders resolve to amygdala only, locked in as a permanent regression test using the
real nominations as a hardcoded literal (no live call, no `.local/` dependency). Found and fixed
three real issues during implementation that the accepted design did not anticipate, each
documented rather than silently absorbed: (1) own-evidence-first, applied unconditionally, breaks
the real Phase 2/5/9 replay fixtures by introducing a genuinely new model-query shape for c9's
own role that contradicts that child's own pre-existing, pre-Phase-16 design commitment to never
independently re-discover traits -- scoped away from the `for_each_discovered_instance` quantifier
specifically, on a domain-agnostic dispatch (the quantifier field), not a q_aib name check; (2) the
accepted plan's own claim that "zero eligible parents means no change from today" was concretely
wrong for the `exists` shape -- a literal zero-instance result silently also stops testing the
requirement's OTHER role(s) against the child's own evidence, caught by the Phase-15 harness's own
byte-identity verification gate, not by inspection, and fixed to build one base instance exactly
as the retired code always did; (3) `trigger_child_id` is a real field that legitimately disagrees
across two generation calls sharing one `target_id` (confirmed against the pre-existing shared-
upstream-dependency test, not hypothetical) -- resolved as a third benign, already-superseded
bookkeeping field rather than a target-identity change. Reproduced the real c8->c9 before/after
(partially_filled/4 instances -> missing/0 instances, the Phase-12 inventory's own target count
dropping from 24 to 20, exactly the four retired c9-owned targets) and the real Phase-15 c4/c5/c6
before/after (c6 now inherits amygdala, not RTPJ, in both list orders) directly against real data,
never assumed. Closed the companion mixed-instance `exists` RecoveryTarget gap and the
`dependency_origins` merge gap in the same pass, both scoped narrowly and regression-tested.
Updated two pre-existing tests' own real-data expectations with explicit, documented rationale
(never silently) where the fix correctly overturned them. Full sufficiency family: 294 passed;
full `experiments/ask_cli_revised/` tree: 2127 passed, 11 skipped, 2 failed (both pre-existing,
reproduced identically against unmodified HEAD, unrelated to this phase). v9 `combined_hash`
unchanged: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`. No live model call,
no retrieval, no recovery execution, no contract or pin change, no production integration. Full
detail in `PHASE16_PARENT_CONTEXT_ELIGIBILITY_RESULTS.md`.

---

## Phase 17 — C2 re-sealing stability / locality (appended 2026-10-01; does not alter the rows above)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-10-01 | Evidence | Phase 15 semantic-consumption preflight |
| 2026-10-01 | Design direction | Cliff Workman + ChatGPT |
| 2026-10-01 | Design / audit | Claude |
| 2026-10-01 | Implementation, verification, real-artifact replay | Claude |

**Evidence (Phase 15 semantic-consumption preflight).** Re-running C2 coverage sealing over a
broadened ledger changed responsive-obligation assignments on unchanged pre-existing
propositions, perturbing unrelated candidate pools and direction/effectiveness metadata.

**Design direction (Cliff Workman + ChatGPT).** Framed recovery sealing as an incremental
evidence-addition problem and established strict append-only old-proposition semantics with
NEW-propositions x FULL-obligations classification.

**Design / audit (Claude).** Traced the exact `run_coverage_audit`/`seal()` call graph (no field
named `responsive_obligation_ids` exists in the coverage-audit wire protocol itself — it is
synthesized once, by `seal()`, by inverting the obligation->proposition map; `seal()` was a pure
function with no "previous ledger" input, rebuilding every proposition's attachment from scratch
on every call). Independently reproduced the same class of drift, including proposition **loss**
(not only gain), in a second, unrelated preserved run (`q-aib-hierarchical-t5c-live-20260930`) --
new evidence this audit surfaced, not previously documented. Separated the Phase-15 direction/
effectiveness drift into two distinct mechanisms (old-proposition reclassification, which this
phase's design closes; unit-level pool-order sensitivity from a genuinely new proposition sharing
a dedup unit with an old one, which it does not) and showed only the first is in scope. Designed
the backward-compatible `classify_pids`/`prior_sealed` extension to the two existing primitives,
confirmed compatible with the frozen Task-B prompt with zero wording changes, requiring no new
persisted schema and no change to any other call site.

**Implementation, verification, real-artifact replay (Claude).** Implemented exactly the accepted
two-primitive design: `run_coverage_audit(..., classify_pids=None)` and `seal(..., prior_sealed=
None)`, both backward-compatible defaults. Resolved the accepted plan's one named STOP condition
(whole-ledger `coverage_assessed`/`obligation_states`/`coverage_authority` truthfulness) by
re-deriving those fields from the merged attachment map rather than inventing new schema, exactly
as the plan's own escape hatch allowed. Added the pre-C2 fail-closed prefix guard
(`verify_stable_prefix_and_new_pids`) and the shared `record_identity` helper, reusing rather than
reinventing the exact tuple `__main__._new_unique_verified` already established for the identical
"two records can share a physical anchor" problem (confirmed by reading the existing code first,
not assumed) -- `__main__.py` now delegates to the one copy. Running the real test suite (not
static inspection) surfaced a real, concrete instance of the hazard the accepted design's own
Section B anticipated, in a previously-passing test whose fixture encoded the pre-fix (full-reseal)
assumption; updated it with explicit, documented rationale (the Phase-16 precedent), verified live
against unmodified HEAD that the change in behavior was this phase's own and not a second,
unrelated bug. Built an offline counterfactual replay (`phase17_c2_sealing_stability_replay.py`)
against the real preserved `q-aib-hierarchical-t5c-live-20260930` C1 artifacts and Phase 13's own
real recovered proposition text, proving byte-for-byte preservation across all 26 real
propositions plus correct new attachment for the recovered one -- disclosed exactly what this
replay does and does not claim to reproduce bit-for-bit against the Phase-15 report's own
narration, rather than overclaiming. Baked the independently-found same-ledger drift instance into
a permanent hardcoded-literal regression fixture (the Phase-16 lineage precedent) rather than a
live `.local/` dependency. `test_stages.py`: 39/39 (21 pre-existing unchanged + 18 new). Full
`experiments/ask_cli_revised/` tree: 2145 passed, 11 skipped, 2 failed (both pre-existing,
reproduced identically against unmodified HEAD via direct `git stash` comparison, unrelated to
this phase -- `MainOrderingTests::test_preflight_only_...` and
`RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts`). `ruff check`
clean on every new/touched line; `ruff format` applied only to the two wholly-new files, leaving
pre-existing unformatted spots elsewhere untouched. v9 `combined_hash` unchanged:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`. No live model call, no
retrieval, no recovery execution, no contract or pin change, no production integration. Full
detail in `PHASE17_C2_SEALING_STABILITY_RESULTS.md`.
