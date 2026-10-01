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
