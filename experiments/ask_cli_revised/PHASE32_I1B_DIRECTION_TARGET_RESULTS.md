# Phase 32 — I1b: answer-layer direction target guard (results)

**Status: implemented and verified offline. Commit under the gates in §10.**

## 0. Starting and final HEAD

- Starting HEAD: `3af0f323e6d95f79c554fcff75cc56afecf9fd0c` (I1a commit).
- The I1b commit hash is given in the handback, not in this file (a file cannot contain the hash of the commit that adds it).

## 1. Files changed

| file | change |
|---|---|
| `experiments/ask_cli_revised/answer_plan/direction_target.py` | new: pure, deterministic direction-target classifier (relation / operand / unknown / none) |
| `experiments/ask_cli_revised/answer_plan/classify.py` | `_evaluate_direction` rewritten: relation attachment requires a witness sentence classified as a relation target; operand valence uses the classified operand as its subject; every other case fails closed with an explicit reason; one import added, one unused import removed |
| `experiments/ask_cli_revised/answer_plan/plan.py` | `direction_target` copied into direction-claim audit records only; `PLAN_VERSION` bumped `answer-plan-step2-v1` → `answer-plan-step2-v2` |
| `experiments/ask_cli_revised/test_direction_target.py` | new: 18 tests (eight specified classifier cases, further classifier behaviour, four integration cases, preserved-run check) |
| `experiments/ask_cli_revised/test_answer_plan.py` | the witnessed-direction test now asserts the fail-closed outcome (it previously asserted the I1a over-attachment); renamed accordingly |
| `experiments/ask_cli_revised/PHASE32_I1B_DIRECTION_TARGET_RESULTS.md` | new (this file) |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | one appended Phase 32 I1b section; earlier entries byte-identical |

Not changed: `relation_witness.py`, the witness semantics, the all-inherited guard, c8 and c5/c6 witness results, projection parity, the direction summaries upstream, the sufficiency semantics, frozen contracts, nomination authorizations, pins, `app/frontend/`.

## 2. The latent failure I1a exposed

Under I1a the section-7 witness is correct, so a relation can be witnessed while a direction word in the same evidence describes
an operand's valence. The old classifier then attached the direction to the witnessed relation whenever the witnessed unit's
witness proposition shared a proposition with the direction observation. Attachment was unconditional on the sentence.

Synthetic example: the inherited referent is realised in the child's passage "Explicit negative attitudes toward alpha were found
with the beta questionnaire." The relation is witnessed, so the sign "negative" was attached to the relation. The sign describes
the attitude toward `alpha`, not the relation. The old witness rule had refused the relation, so the over-attachment was
hidden. I1a removed that accidental protection.

## 3. Relation direction versus operand valence

Three things are kept separate:

- **A. `relation_witnessed`:** the evidence establishes that X and Y are related. This does not imply C.
- **B. Operand valence:** the evidence describes Y as negative, positive, more or less. Example: "X was associated with negative attitudes toward Y."
- **C. Relation direction:** the evidence establishes that X is positively or negatively associated with Y, or higher or lower with respect to Y.

A witnessed relation does not turn a sign into a relation direction. A sign near a witnessed relation is only a relation direction when
the sentence itself targets the relational predicate.

## 4. Exact target rule (`answer_plan/direction_target.py`)

Per sentence, given the operand surfaces it contains (role → verbatim text) and the consensus sign. Operand occurrences are matched
case-insensitively. Direction words are the existing `overview_evidence` direction stems. The relational cue is the existing
correlational pattern (`overview_evidence._CORRELATIONAL`). The only additions are generic grammatical sets: copulas, comparatives and
clause boundaries. No domain vocabulary.

1. **Conflicting signs.** Literal positive and negative direction words both present → `unknown` (`conflicting_signs`).
2. **No requested direction word** → `none`.
3. **Per direction word**, in order:
   - a comparative directly in front of an operand: a comparative *pair* across two operands with a relational cue between them
     is a `relation`; a lone comparative is that operand's magnitude (`operand`);
   - a direction word directly next to a relational cue ("negatively associated", "correlated negatively") is `relation`-bound;
   - a direction word directly in front of an operand ("negative beta evaluations", "negative alpha") is `operand` valence of that operand;
   - a direction word directly after a copula, with an operand earlier in the same clause ("beta scores were negative") is `operand` valence;
   - anything else is `unresolved`.
4. **Aggregate.**
   - Any `relation`-bound word: a `relation` requires two operands present and a relational cue between their first and last
     occurrence. Otherwise `unknown` (`mixed_targets`, `relation_without_two_operands`, `relation_cue_not_between_operands`).
   - Otherwise, operand-attributed words: exactly one operand role and no unresolved word → `operand`; otherwise `unknown`.
   - Otherwise, all words unresolved: if exactly one operand is realised in the sentence, `operand` for that operand
     (`single_operand_sentence`); if two or more, `unknown` (`unbound_direction_word`).

**Fail-closed rule.** A `relation` target attaches only when the sentence is in a witness proposition of a witnessed unit. An
unwitnessed or unattachable relation target is never rendered as operand valence. An `unknown` target is suppressed. No direction is
attached to a relation by proximity.

## 5. Answer-layer integration (`classify._evaluate_direction`)

1. **Attachment.** A witnessed unit attaches its direction only if a sentence in one of its witness propositions classifies as `relation`.
   The record gets `role="attached_to_relation"`, `direction_target="relation"`.
2. **Operand valence.** Otherwise, sentences classified as `operand` render a value-level valence whose subject is the classified
   operand's verbatim surface, provided that surface occurs in the sentence (the subject is now the classified operand, not any own
   operand that happens to occur). `direction_target="operand"`.
3. **Otherwise** the record is suppressed with a reason:
   - `direction_relation_not_attachable`, if a relation target was seen but could not attach;
   - `direction_target_unresolved`, if an unknown target was seen;
   - the existing reasons otherwise. `direction_target` is `relation`, `unknown`, `operand` or `none` accordingly.

`direction_target` is added to the audit record of direction claims only. Other claim records are unchanged.

## 6. Synthetic results

Expected values are hand-written from the specification. Generic alpha/beta fixtures. Sign is "negative" unless stated.

| # | sentence | expected | observed |
|---|---|---|---|
| 1 | "Alpha was negatively associated with beta." | relation | relation |
| 2 | "Higher alpha predicted lower beta." (sign unconstrained) | relation | relation (comparative pair across the predicate) |
| 3 | "Alpha was associated with negative beta evaluations." | operand beta; not relation | operand `measure_y` |
| 4 | "Alpha was associated with beta, and beta scores were negative." | operand beta; relation unknown | operand `measure_y` |
| 5 | "Negative alpha was associated with beta." | operand alpha; relation unknown | operand `entity_x` |
| 6 | witnessed relation; a negative word not tied to it ("…and negative results were reported…") | unknown; not relation | unknown (`unbound_direction_word`) |
| 7 | relation sentence, relation NOT witnessed | no relation attachment | `direction_relation_not_attachable`, suppressed |
| 8 | "Alpha was positively associated with beta, and negatively with beta." | unknown (ambiguous) | unknown (`conflicting_signs`) |

Further classifier tests: no requested direction word → `none`; a single realised operand keeps its attribution (`single_operand_sentence`);
a relation word after the operands without an adjacent direction word is not a relation; case-insensitive operand matching; deterministic output
with only `target`, `role`, `reason` keys (no score); no valence sentence ever classifies as a relation.

Integration (claim records): witnessed relation with a relation sentence → `attached_to_relation`, `relation`; witnessed relation with an operand valence
sentence → `value_level`, `operand`, valence subject `beta`; witnessed relation with an unresolved negative word → suppressed,
`direction_target_unresolved`; relation sentence on an unwitnessed relation → suppressed, `direction_relation_not_attachable`.

## 7. Preserved-run parity

Replay on the preserved map with I1 fields, baseline (I1a commit) versus post-I1b (final code):

| artifact | result |
|---|---|
| `deterministic_layer1.md` (Layer 1) | **byte-identical** |
| `deterministic_layer2.md` (Layer 2) | **byte-identical** |
| `deterministic_layer3.md` (Layer 3) | differs only in `plan_sha256` and `plan_version` (identity, justified in §8) |
| `answer_plan.json` | differs only in `plan_version`, `plan_sha256`, and `direction_target` added to the single direction claim (c6) |
| `answer_plan_audit.json` | differs only in `plan_sha256` and the plan-hash detail of `replay_plan_deterministic` |
| `replay_decomposition_authorization.json` | **byte-identical** |
| `comparison_against_phase29_hand_audit.md` | **byte-identical** |

Structural checks on the final output: node states equal; claim roles equal apart from the single added `direction_target` field;
relation units equal; ParentClaim ids equal; the c6 direction claim is still `value_level` with `direction_target="operand"`, and its
valence subject is still "Explicit Bias Questionnaire".

Witness parity (unchanged from I1a): witnessed `c4 b140…` (`p11`) and `c8` ×5 (`p41`); unwitnessed engine-complete `c5` ×2, `c6` ×2;
36 relational instances. Pipeline projection, ParentClaims, recovery and stop-search: unchanged (harness re-run).

## 8. PLAN_VERSION decision

**Bumped.** `PLAN_VERSION` identifies the semantics of the answer plan. Repository precedent: it was introduced at Step 1 as
`answer-plan-step1-v1` and changed to `answer-plan-step2-v1` when Step-2 semantics changed. I1b changes the direction attachment and
operand-valence semantics, so the identity bumps to `answer-plan-step2-v2`.

Expected hash changes (reported, not parity failures):

| identity | before (I1a commit) | after I1b |
|---|---|---|
| `plan_version` | `answer-plan-step2-v1` | `answer-plan-step2-v2` |
| `plan_sha256` | `43474527ae40623ea609da98b0effb3b9c7a0376513f845baaede8d9a6bed234` | `7e990ae2d34487e8ebb7f75315cfa3c6fe8879b6765e1e77d651ebe3b1bf0d0a` |
| `replay_decomposition_authorization` | `replay_authorization_sha256` unchanged | byte-identical (the authorization does not embed the plan hash) |

**Process gap, recorded.** I1a changed the witness semantics without a `PLAN_VERSION` bump. Its output was byte-identical, so no
identity change was visible, but the identity string did not describe the semantics that shipped in I1a. The v2 bump applies to the
cumulative change since v1 (I1a and I1b). Going forward the convention is: bump `PLAN_VERSION` whenever answer-plan semantics change,
including semantics that do not alter the preserved output.

## 9. Recorded limits (decisions, not hidden)

- **Single-operand sentences keep their existing attribution.** When a direction word is unresolved but exactly one operand is realised in
  the sentence, the classifier attributes it to that operand. This is what keeps the preserved c6 statement ("negative explicit attitudes…
  Explicit Bias Questionnaire") unchanged. The sign's grammatical object ("attitudes") is not verified against the operand, because doing so
  would need a lexicon of attitude nouns, which is domain vocabulary. The residual risk: a sentence with one realised operand and a sign
  describing something else would still be attributed to that operand. I recommend deciding this together with I3, before I2.
- **Case-sensitive referent containment (existing I1 rule, unchanged here).** The inherited-referent containment uses the canonical rule,
  which is case-sensitive. A referent that begins a sentence ("Alpha was…") fails to match "alpha", so a witness can be missed when the
  operand starts the sentence. Because it is the I1 rule, it is recorded, not changed. A fixture with a sentence-initial referent is
  therefore not witnessed. The integration fixtures place operands mid-sentence.
- **Direction target identity is answer-layer only.** Upstream direction summaries are unchanged. Full I3 decides the representation
  under versioned sufficiency semantics.

## 10. Tests and gates

| gate | result |
|---|---|
| I1b module | **18 passed** |
| I1 / I1a witness tests, answer-plan tests, sufficiency tests (targeted) | **607 passed** |
| preserved replay | Layer 1 and Layer 2 **byte-identical**; Layer 3 differs only in identity lines (§8) |
| witness agreement (preserved) | **36/36 unchanged** |
| ParentClaims, recovery, stop-search | **unchanged** |
| frozen contracts, nomination authorizations, pins, frontend | **untouched** |
| broader `ask_cli_revised` offline suite under network refusal | **3 failed, 2688 passed, 11 skipped** (in 199 s) |
| failure set versus pre-change baseline | **identical** (the same three test ids) |

Count arithmetic: 2616 (pre-change baseline) + 32 (I1) + 21 (I1a) + 1 (I1a direction-case split) + 18 (I1b) = 2688.

Pre-existing failures (present at HEAD before any Phase-32 change; unrelated to I1b):
- `test_e2e_run.py::RunTopologyGuardTests::test_an_unscored_smoke_run_may_start_from_a_dirty_tree_and_is_marked_unscored`
- `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_candidate_verifies_the_preserved_artifacts` (pin drift)
- `test_hierarchy_e2e.py::MainOrderingTests::test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`

Lint and format: ruff check and ruff format clean on every changed Python file.

## 11. Scientific gain on the preserved run

**Zero.** Layer 1 and Layer 2 are byte-identical. No witness, node, facet, claim or ParentClaim changed. The c6 valence statement is unchanged.
The guard closes the over-attachment that I1a exposed, and it prevents future aligned witnesses from attaching direction by proximity. It does
not produce a new scientific answer on the preserved run.

## 12. READY / NOT READY for semantic-version plumbing

- **Commit I1b: READY** under the gates in §10, with the limits in §9 recorded.
- **Semantic-version plumbing (`SUFFICIENCY_SEMANTICS_VERSION`, audit §17): READY to design, NOT READY to implement** until two decisions are made:
  1. whether the single-operand attribution limit (§9) is accepted as is, or must be closed by full I3 first;
  2. whether the case-sensitive referent containment (§9) is accepted as the I1 rule, since a sentence-initial referent is then not witnessed.
- I2 remains NOT READY. It needs the semantic-version plumbing and the direction-target decision above.
