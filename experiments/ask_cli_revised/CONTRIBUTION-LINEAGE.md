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
