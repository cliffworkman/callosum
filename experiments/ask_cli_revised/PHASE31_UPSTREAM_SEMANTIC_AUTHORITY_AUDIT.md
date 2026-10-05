# Phase 31 — Upstream semantic authority audit (revision 2)

Status: approved (revision 2, with two final edits: the all-inherited relation guard in §7, and corrected
verification wording). This is a docs-only record. No production code, model call, live run, pin, or
frozen-contract change occurred. Read-only forensic work against preserved artifacts is described in §3.
Decisions: D1 approved; D2–D4 remain future decisions; D5 resolved (§22).

## 0. Preflight and correction ledger

Preflight (verified, unchanged from revision 1):
- Worktree `ask-060-hier11-recpm3-citefix-20260929T212442Z`, branch `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- HEAD `21d425c4f2888ba265b09b98a661a227f23f4177` equals `origin`. Tree clean at start.
- Phase 29 audit and Phase 30 Step 1/Step 2 results and `phase30_replay/` present.
- Frozen inputs unchanged since `93f09d00`: `sufficiency_contract.aib_hier_v9.frozen.json`,
  `hierarchy_contract.frozen.json`, `e2e_contracts.frozen.json`, nomination authorization JSON files. `git diff` empty.
- Phase 30 commits touch no `app/frontend/` file. The branch-vs-`main` diff shows `app/frontend/js/20_synthesis.jsx`
  from `c4b8e563` (inc 583), which predates Phase 30 and is outside this audit.

Preserved inputs (gitignored, present only in this worktree):

| file | sha256 |
|---|---|
| `.local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/run/17_sufficiency_map.json` | `28478500e485137cd6930b8010d274bb1da3afd48e7f4a6208dd183610d9ca0b` |
| `…/run/11_verified_ledger.json` | `a70409e8f5a0937f414c73c4796b293c6c1a9ef3b31c7fc83bbfa61794c6bd5d` |
| `phase30_replay/answer_plan.json` | `6df490bdd0b372934ab4f0904664315b3800aa545082ac46a0fea2195ef866eb` |
| `phase30_replay/answer_plan_audit.json` | `9d0058e7f48735d8888703af24aaf77eed853e9514c929a0ad890b157d537390` |
| `sufficiency_contract.aib_hier_v9.frozen.json` | `472cd2ab23a81d68b698038e0dcc0d98c7aafc6efadef933a2f932e9580f2da6` |
| `.local/e2e-runs/q-aib-hierarchical-t5c-live-20260930/library_copy.sqlite` (read-only, `mode=ro`) | not hashed (forensic reads only) |

Correction ledger (things revision 1 got wrong or overstated; each is now fixed in §3 or the sections named):
1. **Sealed `evidence_spans` contains duplicate rows.** 3,254 rows, 1,341 distinct `(paper, span, chunk, text)`. Paper 67
   `e1` alone appears 58 times. Revision 1 treated rows as spans. Any count from `evidence_spans` must use distinct identity.
2. **Phase 29's "182 sealed spans" for paper 14 is a row count.** Distinct count is 86. The zero-match result for
   "anomal|facial" holds on distinct spans (0).
3. **"Twelve amygdala-plus-attitude spans" was 11 duplicate rows plus 1.** Distinct amygdala spans: 16. Under a narrow
   attitude/bias regex, 2 distinct spans match. Under a broader attitude/belief/trait regex, 3 match (§3.2).
4. **"Phase 30 is not fail-closed for B"** overstated the presentation problem. The user-visible sentence is the verbatim
   null (presentation fidelity: currently safe). The defect is in semantic state and classification (§8).
5. **"I2 may use strategy-level polarity with no contract-hash change"** is rejected. Changed semantics need an explicit
   identity change (§17).
6. **"D5 is a maintainer decision"** is withdrawn. Per steering it is resolved (§22).

## 1. Executive verdict

1. **All eight failure classes reproduce in the preserved artifacts.** A through G are reproduced directly. H is confirmed
   through Phase 29 U7 and by reading the answer-layer construct check, which is weaker than it appears (§11).
2. **Two presentation/semantics separations matter.** Presentation fidelity is currently safe for B: the verbatim null sentence
   is displayed. Semantic state is wrong: the same category binding counts as presence internally, and the same requirement is
   `filled` in c3 and `category_missing` in c6. Phase 30 therefore is not yet fail-closed on *classification* for B, though it
   is on *display*.
3. **Phase 30's generic-summary check is a coincidence, not a property.** It counts requirements per passage, so a generic
   summary bound under one role passes it.
4. **G has a precise, fixable cause at sealing, not at retrieval.** The continuation of the Hadza sentence was retrieved, the
   seam verifier establishes it, and the join-chain logic skips it (§3.1, §12).
5. **The relation-witness invariant is reformulated by operand source** (§7). Inherited operands supply referent identity; own
   operands supply support. This resolves the W2/W3 inconsistency in revision 1.
6. **Verdict: NOT READY for a combined upstream repair.** READY for I1 only: additive runtime witness metadata with projection
   parity, zero behaviour change, zero scientific gain (§19, §21).

## 2. Failure-class matrix (revised)

| Class | Reproduced in preserved map | Earliest stage | Error type | Phase 30 presentation | Phase 30 semantics | Downstream check retained? |
|---|---|---|---|---|---|---|
| **A** Generic achieved-outcome overbinding | `p4` bound under c1, c2, c3, c12. `c3#suff:attitude-manifestation` `filled`, `complete=True` on generic p1/p4 alone | Mapping (L3) | binding precision / role modality | Blocked, but only by cross-requirement count (`classify.py:40-56, 78`); single-role generic passages pass | Not caught as a property | Yes, as a passage property (§14) |
| **B** Category binding without polarity | c3 `implicit` `filled` from p36 "…implicit biases were slight and not significant". c6 same requirement `implicit` `missing` | Mapping (L3) + completion semantics (L4) | polarity/qualification | **Safe.** Verbatim null displayed | **Wrong.** Value sentence `ok=true`, claim `primary`; presence counted | Yes; the value-sentence check must *classify*, not discard (§8) |
| **C** Relation complete with inherited operand | c5 ×2, c6 ×2 `unwitnessed_complete`. Parent operand p11 vs own operands p46/p47 (c5), p14/p26 (c6): disjoint support | Completion semantics (L4) | relationship witness | Safe (`relations.py`, `unwitnessed_relation`) | Safe at L5; engine still says complete | Yes, permanently |
| **D** Direction/valence identity | c6 `negative` (p14, p26 "explicit negative attitudes") attached to brain–attitude relation. c5 `more` (p46, sign None) attached to unwitnessed c5 | Observation attachment (L3/L4) | valence-object identity | Safe (`_evaluate_direction`) | Engine summary still attaches it | Yes |
| **E** Measurement subject / bearer | c8 traits `attractiveness`, `trustworthiness`, `anger`, `dominance`, `threateningness` from p41 "Across the ratings for all faces…". Same sentence witnesses trait and manifestation | Mapping (identity) | identity | Partly: `stimulus_rating_cue` refuses for trait roles (`classify.py:83-84`) | Engine still completes c8, pairs c9 | Yes |
| **F** Referring phrase / anaphora | c4 witnessed, complete; region = "the specific amygdala response" (p11); witness starts "Across these levels of organization…" | Mapping (entity extraction) + closure (L2/L1) | identity + closure | Safe (`referentially_closed`) | Engine complete | Yes |
| **G** Truncated passage | Hadza p29/p53 end "…were better" | **Sealing (L2): join-chain consumption** (§3.1) | truncation | Safe (`passage_complete`) | Engine treats truncated span as operand | Yes |
| **H** Requested-construct identity | c2 operands p46/p47 from paper 14; paper 14 has 0 distinct "anomal"/"facial" spans | Binding (L3); ranking (L1) | construct identity | `requested_construct_direct` accepts *paper-level* occurrence (`text.py:144-153`) and returns True when no terms are configured | Overlay-owned, not authority | Yes, but narrowed (§11) |
| **S** Source-kind / attribution (cross-cutting) | U5 caption used as finding; U6 prior-work summary as result (p40, paper 61, bound as c4 region); U3 "We suggest…" as trait category (p9, paper 67) | Sealing/mapping attribution (L2/L3) | source-kind | Safe (`is_caption_passage`, `attribution_kind`) | Engine binds them | Yes; caption check permanent (§13) |

## 3. Forensic results (read-only, this revision)

### 3.1 G — Hadza continuation (resolves revision-1 open question Q5)

Chunk table (preserved library copy, `mode=ro`), attachment 78, paper 68:

- chunk 14528 (chars 13009–13103): "…were less moral or worse foragers. However, Hadza who regularly interact with outside cultural"
- chunk 14529 (chars 13104–13195): "groups were more likely to think Hadza with facial scarring were less moral and were better"
- chunk 14530 (chars 13196–13291): "foragers. These results suggest the anomalous-is-bad stereotype is culturally shaped…"

Chunks are contiguous, same page 11, no section label. The complete sentence "…were less moral and were better foragers." also
exists in paper 68 page 4 (chunk 43366, discussion). It is not bound by this run.

Retrieval: chunk 14530 is in the run's packet (`08_evidence_packets.jsonl`, 8 occurrences), is a retrieval anchor
(`06_chunk_retrieval.jsonl`), and is a proposition evidence anchor (`09`/`10`). p29's `context_read` covers 14523–14537.
So the continuation was **retrieved**.

Join evaluation: `decisions.jsonl` records `continuation_join_evaluated` for (14526,14527), (14528,14529), (14530,14531),
and no evaluation for (14529,14530).

Reproduction: I ran the production `propositions._candidate_spans` over packet chunks 14523–14537 with the attachment helpers
backed by the read-only copy. It yields `e6` = 14528+14529 "…were less moral and were better" (this is p29's span) and strands
14530 as `e7` = "foragers." The join (14529,14530) is never evaluated.

Pure verifier: `continuation.detect_continuation(14529, 14530)` returns `is_continuation=True, seam_state=established,
section_unchanged=True`. Offsets 13195→13196, same page 11, no intervening chunk.

**Mechanism.** `propositions.py` `_candidate_spans` (lines ~127–170). After joining chunk i with chunk i+1, it sets
`eligible[i+1] = (next_chunk, next_texts[1:])`, consuming the first segment of i+1. Chunk 14529 has exactly one non-terminal
segment, so its remaining list is empty. At the next boundary `_boundary_continuation(14529, [], 14530, …)` returns None at
`if conn is None or not texts_a`. The chain breaks whenever a middle chunk is fully consumed by the preceding join.

**Classification.** Sealing failed to join an available, verifiable continuation. This is **L2 (proposition/sealing)**.
It is neither retrieval omission (the chunk was in the packet) nor an absent source (the continuation exists and verifies).

**Fix direction (not implemented).** Carry the open tail forward so a fully consumed middle chunk remains available as the
left operand of the next boundary, with a bounded chain length. This changes sealed propositions and `evidence_spans`, so it
is gated (I7, §19).

### 3.2 B — amygdala-plus-attitude spans (resolves revision-1 open question Q6)

Distinct amygdala-containing spans: 16 (52 rows). Classification by `attribution_kind` (answer layer):

| span | paper | chunk | attitude/belief/trait term (narrow / broad) | attribution | admissible as result of relation? |
|---|---|---|---|---|---|
| e2 "We suggest that dehumanization is underpinned by … negative attitudes (IAT and EBQ) … left amygdala." | 67 | 35111 | narrow yes / broad yes | `aim_or_hypothesis` (hedged, speculative) | **No** |
| e7 "Across these levels of organization, the specific amygdala response to facial anomalies correlated with stronger just-world beliefs …, less dispositional empathic concern …" (= p11) | 67 | 34974 | narrow no / broad yes | `this_study_result` | **Yes as a result** for amygdala–belief/trait. **Not** the bound c5/c6 operand (EBQ, behaviour), so not a witness for them |
| e10 "Recent work with fMRI has implicated … Laypersons with high levels of implicit bias … increased amygdala reactivity." (= p40) | 61 | 33550 | narrow yes / broad yes | `prior_work` | **No** (cited background, not paper 61's result) |

The other 13 distinct amygdala spans have no attitude, belief or trait term.

Answer to the steering question: **no admissible result-level passage witnesses the requested c5/c6 relations as bound**
(amygdala with EBQ/attitude measure; amygdala with behaviour). The one admissible result-level passage (e7/p11) asserts an
amygdala–belief/trait relation with a *different* operand. Whether "just-world beliefs" or "empathic concern" satisfies
c6's "named attitude type or measure" is a construct-identity and operand-typing decision (H, E). The structural witness test
must not promote it automatically.

This matters for the invariant: e7 is the realistic version of "parent identifies X; child passage says X relates to Y"
(§7 test case 1), and it shows why operand typing must precede witnessing.

## 4. Root causes (concise)

**A.** `sufficiency_mapping.py:79-82` `_match_achieved_outcome` returns the whole passage when `has_result_predicate`
holds. `sufficiency_authoring.py:168-175` gives five distinct roles one strategy and the same guard. `_bind_role_candidates`
(`:311-369`) returns the first admissible match (`:356`), so binding depends on ledger order. Effectiveness repeats the whole-passage
pattern (`:983`). No source-kind check gates result roles.

**B.** `_match_explicit_category_term` (`:85-93`) returns the first literal occurrence. The category role has
`disqualifying_guards=[]` (`sufficiency_authoring.py:245`). `negated` is recorded (`:367`) and never read for categories.
The effectiveness path already maps negation to `not_supported` (`:976-977`), the precedent the category path lacks.
Answer layer: `_evaluate_values` (`classify.py:172-250`) renders `value_sentence` without polarity; negation is consulted
only for enumeration (`:213`, `:246-249`).

**C.** `recompute_instance` (`sufficiency_engine.py:574-576`) runs joint grounding only when `len(own_roles) >= 2`;
`_joint_grounded` (`:428-429`) returns True below two. Intent stated at `:570-571`; pinned by
`test_sufficiency_engine.py:105`. `relationship_witness_support_ids` (`:484-485`) returns a single own role's support
when only one own role exists.

**D.** Same `:484-485` scoping feeds `compute_direction_and_effectiveness` (`sufficiency_diagnostic.py:262-267`).
`find_direction_observations` (`sufficiency_mapping.py:923-956`) takes the sign from the first direction token in each
passage (`_match_direction_word`, `:100-108`) with no operand check.

**E.** `_entity_role` (`sufficiency_authoring.py:160-165`) defaults to `model_nomination_only`. Trait roles have no
deterministic check and no field for what the measurement describes.

**F.** Region role is `model_nomination_only`; stored value is the referring phrase "the specific amygdala response". The
witness passage starts with an anaphor. Engine does not check closure.

**G.** §3.1: sealing join-chain consumption.

**H.** `construct_direct` (`answer_plan/text.py:144-153`) builds haystacks from the quote **and every paper span**, so
paper-level occurrence counts as direct. It returns True when `terms` is empty (fail-open). The replay overlay always supplies
terms, so the fail-open path is not exercised here, but production must not inherit it.

**S.** `attribution_kind` (`text.py:114-127`) orders caption, then aim/hypothesis, then prior_work, then result language.
It is a lexical attribution, and the answer layer uses it. Upstream mapping does not.

## 5. Ownership by layer

| Layer | Owns | Failures rooted here |
|---|---|---|
| 1. Retrieval / context | which chunks reach the packet; ranking | H (ranking only); G (not the cause here) |
| 2. Proposition / sealing | verified units; continuation joins; `evidence_spans` | G (join-chain), S (caption and source-kind as sealed attribution if written at seal time) |
| 3. Semantic binding / mapping | which passage fills which role; clause span; polarity; referent; described entity; source-kind at mapping | A, B (extraction), D (attachment), E, F (extraction), H (no test), S |
| 4. Sufficiency / completion | `complete`, presence semantics, joint witness, recovery and terminality | C, B (`filled` as presence), D (scoping) |
| 5. Answer planning / presentation | renderable sentences; Layer 1/2/3 placement | Defense in depth only; must not become the repair site |

Repairs belong in L2–L4. L5 keeps its checks.

## 6. Semantic object model (revision 2)

Principle: a field is added only if it prevents an observed failure and is derivable deterministically, or by a closed-taxonomy
nomination that the deterministic layer verifies. Fields are runtime-only (outside `frozen_view`, which strips `instances`,
`state`, `reason`, `direction_summary`, `effectiveness_summary`; `sufficiency_engine.py:275-292`) unless marked.

Naming conventions (inspected): engine constants are snake_case tuples in `sufficiency_engine.py` (`MAPPING_STRATEGIES`,
`CANDIDATE_SOURCES`, `RELATIONSHIP_VERIFIERS`, `REASON_CODES`). New enums follow that form.

| Field | Level | Prevents | Derivation | Model? | Frozen? | Notes |
|---|---|---|---|---|---|---|
| `observation_polarity` ∈ {positive_finding, null_finding, contrary_finding, mentioned_only, unknown} | binding (category and outcome roles) | B | Deterministic from sentence cues (`oe.has_negation`, `oe.has_hedge`, `attribution_kind`) | No | No | See §8. `contrary_finding` is reserved; v1 emits it only on an explicit tested opposite-direction marker |
| `relation_witnessed` + `witness_ids` + `witness_provenance` | instance (relational) | C, D | §7 test | No | No | I1. Runtime, additive |
| `direction` target ∈ {relation, operand:<role>} + `sentence_witness` | direction observation | D | Sign and target surface in one verified sentence | No | No | I3 |
| `referent` = {surface, normalized_from, rule} | entity binding | F, C (inherited identity) | Literal containment; closed head-noun list; provenance | No | No | I5. I1 uses verbatim parent `exact_text` (conservative) |
| `described_entity` ∈ {focal_person, stimulus_or_target, behavior_or_task, group_or_population, unknown} | entity binding | E | Closed-taxonomy nomination, verified; deterministic cues may only demote to candidate | **Yes, live-gated** | Expected value per role **authored** (frozen) — D3 | §9 |
| clause-level `exact_text` (no new field) | binding | A | Clause containing the result predicate and its subject; canonical containment | No | No | I4 |
| `authority` ∈ {authoritative, candidate} | binding | A, E, S | Lexical matches that fail role typing or source-kind become candidate; candidates never complete a requirement | No | No | Default authoritative until a rule demotes |
| `source_kind` ∈ {this_study_result, prior_work, aim_or_hypothesis, caption, meta_summary, unknown} | binding (derived at mapping) | A, S, U3, U5, U6 | Shared pure function over sealed text (§14) | No | No | Not sealed |
| `construct_match` ∈ {passage_direct, mapping_link, paper_context, adjacent, unknown} + authored `construct_anchor` | binding + requirement | H | §11 | No (anchor authored) | Anchor authored → frozen (D4) | I8 |
| `answer_status` (derived view) | requirement | B, recovery, terminality | §8 | No | No | No new `REQUIREMENT_STATES` value |

Removed from revision 1: sealed `generic_summary` and sealed `complete_sentence` (both moved to mapping-time derivation, §14;
G is fixed in sealing logic, which is a different matter from storing a flag). Also removed: `answer_status` as a stored state.

Deliberately not proposed: confidence, importance or salience scores; a `subject` on every binding; renaming `complete`;
new `REQUIREMENT_STATES` values; any model-asserted polarity or location.

## 7. Relation-witness invariant (rewritten by operand source)

Partition the required roles `R` of a relational instance `I` (`|R| >= 2`) into:
- **OWN** operands: binding source is not `parent_context`. Support comes from the child's own mapping.
- **INHERITED** operands: binding source is `parent_context`. They supply referent identity only.

Let `Pool(child)` be the child's own admissible verified propositions: the propositions reachable through the child's own
bindings or its own admissible retrieval. Propositions reached only via parent context are excluded.

**W1 (operands complete).** Every `r` in `R` is `filled` (OWN or INHERITED). This is the current `complete` meaning for
relational instances and is unchanged.

**W2 (witness, by operand source).**
`relation_witnessed(I)` iff **at least one OWN operand exists** and there exists `p` in `Pool(child)` such that:
- for every OWN `r`: `p` is in the admissible support set of `binding_r` (primary `proposition_id` plus `supporting_proposition_ids`); and
- for every INHERITED `r`: the referent surface of `r` occurs in `quote(p)` by canonical containment, or by another deterministically
  verified local realization of that same referent (future; not in I1).

For INHERITED operands, `p` need not and generally cannot be in the parent binding's support set. The parent proposition
is not part of the witness.

**All-inherited guard.** If no OWN operand exists, `relation_witnessed` is false, however many inherited referent surfaces co-occur in
child-retrieved text. Inherited referents supply identity; they cannot establish a child relation by themselves. Mere co-occurrence of
inherited surfaces in child-retrieved text is insufficient. A relation with no OWN operand can be witnessed only through an explicitly
declared relationship verifier (`RELATIONSHIP_VERIFIER`, W6) or an equivalent relation-specific authoritative mechanism that is named,
tested and frozen. None is declared in v9. This guard is the defense against referential inheritance becoming evidentiary relation
authority.

**W3 (inheritance is identity, not evidence).** The parent's proposition id never witnesses. A proposition that enters the
witness only because the parent bound it is excluded from `Pool(child)` unless the child's own mapping independently admits it.

**W4 (proposition-level witness, sentence-level render).** The engine witness is proposition-level. The answer layer
additionally requires one rendered sentence containing every operand surface (existing `_candidates_containing`). The engine may
be broader than the render, never narrower.

**W5 (joined propositions).** A joined proposition may witness only if its continuation verification passed (Stage A) and the
join is in `Pool(child)`. An unjoined fragment is never a witness.

**W6 (no distributed relations).** Repeated operands across propositions never witness. Two distinct propositions cannot jointly
establish a relation. Distributed evidence is allowed only for a relation type that the contract declares with a named
`RELATIONSHIP_VERIFIER`, tested and frozen. None is declared in v9. `contract_directed_links` is unreachable in the pipeline
(no `attachment_pieces`; `sufficiency_engine.py:476-477`).

**W7 (nomination is not witness).** A model that nominates or asserts a relation creates no witness. The witness is a deterministic
property of sealed text.

**W8 (annotations).** Relation-level direction or effectiveness requires W2. Value-level valence requires the operand surface in the
same sentence as the sign.

**Synthetic invariant test (generic; no q_aib vocabulary).** Placeholders: entity `alpha region`, measure `beta score`.

Fixture: parent proposition `P1` = "The alpha region responded to the task." Parent binds `alpha region` (`parent_context`
identity). Child OWN operand `beta score` (bound via child mapping) in cases 1–5. Case 6 has no OWN operand.

| Case | Child pool | Expected |
|---|---|---|
| 1. X relates to Y | `C1` = "The alpha region's signal predicted beta score." (own `beta score` support = {C1}) | **witnessed**, `witness_ids = {C1}` |
| 2. child says only Y | `C2` = "Beta score rose across sessions." (own `beta score` support = {C2}; `alpha region` not in `quote(C2)`) | **not witnessed**; `complete=True` (engine) → recorded disagreement |
| 3. parent-only trap | `P1` contains both alpha region and beta score ("…predicted beta score"), but `P1` is reachable only via parent context; child pool = {C2} | **not witnessed** |
| 4. distributed trap | `C2` (beta score) and `C3` = "The alpha region responded to the task." (alpha in C3, not in C2) | **not witnessed** (no single `p`) |
| 5. joined | `J` = join(C2a, C2b) containing alpha region and beta score, with continuation verification **absent** | **not witnessed**; with verification present, witnessed |
| 6. all-inherited co-mention | Parent supplies `alpha region` and `beta score` by `parent_context`. Child retrieves `C4` = "The alpha region and the beta score were mentioned together." No child OWN operand; no declared relationship verifier | **not witnessed** (all-inherited guard) |

Assertions: witnessed iff Case 1 (and Case 5 with verification). Case 6 is not witnessed by the all-inherited guard, however the
co-mention is worded. `complete` is identical across all cases (unchanged engine meaning), so the disagreement list is exactly the set
of engine-complete, not-witnessed instances.

**Preserved-data prediction (checked by reasoning, to be confirmed in I1 replay).** c4 instance `b140…` witnessed by p11 (both
own operands in p11). c5 instances (`…4a3f…`, `…e479…`) and c6 instances (`…2f2b…`, `…9fe9…`) not witnessed: their OWN support
(p46/p47/p14/p26) does not contain the inherited surface. Expected disagreements: 4 (c5 ×2, c6 ×2).

**Answer to "can two independent atomic facts jointly establish a relation?"** No. "Amygdala response correlated with X" in one
passage and "beta score was reported" in another cannot establish a relation between them. Only a single passage asserting the
relation, or a declared composed relation with its own verifier, can.

## 8. Null / polarity semantics (redesigned before I2)

### 8.1 Three separate axes

1. **Observation result** (what the bound evidence reports): `observation_polarity` in {positive_finding, null_finding,
   contrary_finding (reserved), mentioned_only, unknown}. Derived from sentence cues. Describes the observation only.
2. **Requirement semantic goal** (what the requirement asks for): `established_presence` (default for all v9 requirements) or
   `measured_coverage` (explicit only). "Established presence" asks whether a manifestation or association is established.
   "Measured coverage" asks whether a property was measured at all.
3. **Search terminality** (whether further search is warranted): derived from completed scoped search status and the existing
   recovery machinery. Not a property of the observation.

Direction (sign, valence, comparative) remains a separate object (§6, `direction`). Null is not a sign.

### 8.2 Satisfaction is goal-specific

- `established_presence`: satisfied iff an admissible observation with `observation_polarity = positive_finding` supports the
  requirement, under the existing role-completion rules.
- `measured_coverage`: satisfied iff an admissible observation with polarity in {positive_finding, null_finding, contrary_finding}
  supports it.

So a null never satisfies an established-presence requirement, and a measured-coverage requirement can be answered by a null.
This matches the steering: a requirement asking whether a category was measured can be satisfied by a null; one asking for
established manifestations is not positively satisfied by one measured null.

### 8.3 Answer status (derived view, requirement level)

- `presence_established`: goal satisfied by positive evidence.
- `measured_null_only`: goal not satisfied; at least one `null_finding`; no positive finding; the scoped search has not completed.
  **Recovery remains warranted.**
- `measured_null_terminal`: as above, **and** the scoped search for that requirement has completed. Terminality comes from the
  three facts together: result semantics (null), requirement goal (presence not established), and search status (completed).
- `not_established`: otherwise, including `mentioned_only`.

Do not remove recovery categorically because one null exists. A later search can still find a positive finding, which would then
satisfy the presence goal. Only a completed scoped search, with no positive finding, makes the null terminal for that run.

### 8.4 Interaction with existing machinery

- **Recovery** (`compute_recovery_needed`, `_RECOVERABLE_REASONS` includes `category_missing`, `sufficiency_recovery_targets.py:806`):
  the reason-based trigger is unchanged. The only new suppression is `measured_null_terminal`, which mirrors the existing
  `is_zero_evidence_terminal` precedent ("searched and nothing established is terminal").
- **Stop-search:** a completed scoped search with a null and no positive is terminal (same precedent).
- **Category lists:** enumerations list positive findings only. Nulls render as their own verbatim sentence.
- **Direction/effectiveness:** a null is not a sign. The effectiveness path already uses `conclusion="not_supported"` for
  negated outcomes (`sufficiency_mapping.py:976-977`); that vocabulary is reused and not renamed.
- **ResolvedEmptyOutcome:** keep its meaning ("searched, nothing established"). A null has a verified passage, so it must not render
  as ResolvedEmptyOutcome.
- **Presentation (answer layer):** the verbatim null sentence is still shown. The value-sentence polarity check (§15) changes the
  *classification* of that sentence to a null finding under the requirement's goal. It does not suppress or rewrite the text.
- **Test expectation:** `test_answer_plan_replay.py:73` (null text verbatim; no bare "implicit") remains true. Classification
  changes from presence to measured-null.

### 8.5 Consequences for c3 and c6 (the observed inconsistency)

Both requirements ask how the bias manifests in implicit and explicit attitudes, an established-presence question. Under §8.2,
the implicit p36 null does not satisfy presence. c3 moves from `filled` to a null-only status, which keeps recovery warranted.
c6 stays `category_missing`. The two then agree. The replay must show the change in c3, the recovery targets that become
warranted, and the explained ParentClaim id change.

## 9. Measurement subject / described entity (redesigned)

### 9.1 The question

The single observed question: **what entity does this measured property describe?** Revision 1 mixed entity identity with
measurement modality (`self_report` is a modality, not a bearer). That is removed.

### 9.2 Proposed enum (v1)

`described_entity` ∈ {`focal_person`, `stimulus_or_target`, `behavior_or_task`, `group_or_population`, `unknown`}.

- `focal_person`: the property describes the participant or individual under study. Covers traits, states and attitudes of
  that person. Informant designs are included: a parent-reported trait of a child is still a property of the child. The
  informant is a source, not a bearer, and is **not** a field in v1 (added only if an observed failure needs it).
- `stimulus_or_target`: the property describes a rated or manipulated object: a face, a building, a word, a stimulus set.
- `behavior_or_task`: performance or choice on a task (a decision, a reaction time).
- `group_or_population`: the property describes a culture, population or sample as a whole.
- `unknown`: no determinable subject.

"Outcome" is not a value here. Outcome is a requirement role (`observed_effect_or_outcome`), not a subject. An intervention outcome
has a subject (usually `focal_person` for treated participants), and that subject is what is recorded.

Not `respondent`: that term assumes the bearer is the person who answered. Informant designs break the assumption.

### 9.3 Expected value per role

A role may declare an expected `described_entity` (for example, trait roles expect `focal_person`). A binding whose value is
incompatible cannot fill that role; it becomes a candidate.

### 9.4 Derivation

The model nominates from the closed enum, with a verbatim anchor. The deterministic layer verifies the anchor. Deterministic
cues (for example `stimulus_rating_cue`) may only **demote** to candidate; they never promote. This follows the analytic-flexibility
precedent (closed taxonomy, verbatim anchor, model never asserts location). It requires a model call, so it is live-gated.

### 9.5 Stress test across domains (no q_aib vocabulary)

| Domain | Measured property | described_entity | Role expectation |
|---|---|---|---|
| Psychology (this case) | ratings of faces on attractiveness | `stimulus_or_target` | Cannot fill a trait role expecting `focal_person` |
| Psychology | participant's trait score | `focal_person` | Fills trait role |
| Informant design | parent-reported child trait | `focal_person` (child); informant not recorded in v1 | Fills trait role |
| Architecture | ratings of buildings | `stimulus_or_target` | Cannot fill occupant-trait role |
| Architecture | occupant wellbeing | `focal_person` | Fills occupant-trait role |
| Language learning | word difficulty ratings | `stimulus_or_target` | Cannot fill learner-ability role |
| Language learning | learner ability | `focal_person` | Fills learner-ability role |
| Placebo / clinical | patients' symptom reduction | `focal_person` (patients) | Outcome role; intervention and comparator are separate roles |
| Placebo / clinical | treatment administered | intervention is a role, not a `described_entity` | Comparator absence is a requirement-level gap, not a subject error |

### 9.6 D3 status

D3 remains NOT READY for implementation until: (a) the enum above is accepted as the clean representation; (b) it is validated on
the stress table, including the informant case; (c) the decision is made whether expected values are authored (frozen; v10) or
answer-layer only. Adding a second field (modality or source) is not proposed; it needs an observed failure first.

## 10. Referring phrase / anaphora

Two problems, kept separate.

**Entity extraction (I5).** Normalization is allowed only when: (i) the span contains a closed entity surface token that appears
literally in the same proposition quote; (ii) the remaining material is a generic head noun from a closed list of finding or
measurement nouns; (iii) the normalized referent is a literal substring of the verbatim quote. Provenance: `normalized_from` (the
original span), `rule` (an id), and the surface token position. With no surface token there is no normalization, and the binding
stays unfilled or becomes a candidate. No ontology lookup.

**Evidence closure.** A claim is closed only when its referent is named in the same sentence, or by an antecedent sentence that is
inside the bounded packet and is itself a verified proposition. Expansion reuses `retrieval.recovery_neighborhood_context`
(MAX_SIDE=3, section- and sentence-scoped). Expansion adds closure context only; it never injects unverified text into a rendered claim.

**Authority.** Resolving an anaphor changes closure status, not evidence authority. The authority is the verified proposition that
makes the claim.

**Beyond the neighbourhood.** Fail closed. A model may nominate an antecedent as a candidate, with verbatim span verification. That is
live-gated and later.

**I1 conservative rule.** I1 uses the parent binding's verbatim `exact_text` as the inherited referent surface. Where that text is a
referring phrase (as here), this under-witnesses. That is intended for I1: it cannot over-witness. I5 fixes the surface with provenance.

## 11. Requested-construct identity (revised)

**Authority levels.**
- `passage_direct`: the construct anchor occurs in the candidate's own verified proposition quote. This is direct authority for the
  binding.
- `mapping_link`: an explicit, verified semantic link supplied by the mapping contract (authored, frozen). Direct authority.
- `paper_context`: the anchor occurs elsewhere in the same paper. **This establishes paper relevance only. It is context and a
  ranking signal, never sufficient authority that the passage directly bears on the construct.**
- `adjacent`: no anchor in the passage and no link.
- `unknown`: anchor absent or undeclared.

**Why this matters.** The current answer check `construct_direct` (`text.py:144-153`) counts any paper-level occurrence as direct, and
returns True with no configured terms. Both are defense-in-depth gaps, and the second is a fail-open default that production must not
inherit.

**Paper 14.** Zero distinct spans contain "anomal" or "facial", so `paper_context` is absent and the status is `adjacent`. That is the
clean result. Had a paper-level term been present, the revised rule would still refuse direct authority.

**Inheritance.** The construct anchor is requirement-level. A child inherits it only when it declares it. Parent context carries referent
identity, not construct identity.

**Paraphrase.** Lexical anchors miss paraphrases ("facial anomalies" vs "anomalous faces"). Adjacency therefore flags at first and does not
exclude. That is a recall risk, to be measured before any exclusion.

**Frozen implication.** Authored anchors and `mapping_link` declarations are frozen-contract content (D4). A new question version is required if
they are added (§17).

## 12. Truncation and continuation (G, sealing)

**Fix (I7, gated).** Replace the consumption rule in `_candidate_spans` so that a fully consumed middle chunk remains available as the left
operand of the next boundary, with a bounded chain length. Verify each boundary with the existing `_boundary_continuation`. Emit joined
spans with their `anchors`, as today. Do not add unbounded context growth.

**Acceptance (structural).** The Hadza case yields a span containing "…were less moral and were better foragers." (chunks 14528–14530),
and no rendered operand ends non-terminal.

**Gate.** Sealed propositions and `evidence_spans` change, so `sealed_hash` changes. A new sealed run is required. Phase 26–28 references
must be explained, not overwritten.

**Duplicate evidence rows.** The sealed `evidence_spans` repeats each span about 2.4 times. That is not an authority defect, since
attribution and verification key on proposition identity. It does distort counts and any evidence statistic. Its writer is not located
in this audit. Count from distinct identity until that is resolved, and address it in the same gated sealing increment only if it is the
same code path.

**Caution on rendering.** Operands are rendered from the verbatim quote only (U12).

## 13. Source-kind and caption (S, a cross-cutting class)

Source-kind is distinct from incomplete text. It covers captions (U5), prior-work background presented as result (U6, p40), aim or
hypothesis sentences presented as findings (U3, p9), and meta-summaries (part of A). It is a cross-cutting attribution issue, not a
truncation issue.

**Caption check.** `is_caption_passage` (`text.py:97`) stays permanently as defense in depth.

**Upstream.** A single pure function classifies `source_kind` over sealed text. Mapping uses it for role admissibility. The answer layer uses
the same function. This moves code, not semantics.

## 14. Generic summary: derived, not sealed

Do **not** seal a `generic_summary` flag. The source text is sealed authority. A meta-summary, prior-work or hypothesis label is an
interpretive source-kind classification.

The derivation runs at mapping time from sealed text, through the shared `source_kind` function (§13), with a meta-summary cue
lexicon for "summary of earlier findings" phrasing (for example "confirmed earlier reports"). It is a generic lexicon with a
synthetic twin test.

Advantages, as the steering noted: no sealed hash churn for a semantic classifier; the evidence is unchanged; classification can evolve
with mapping semantics; Phase 30 keeps the same classifier as defense in depth.

Sealing-time storage would be justified only if the classification were part of evidence identity. It is not.

## 15. Defense in depth (Phase 30 keeps these)

Keep, with the changes noted:
- `passage_complete` (`is_truncated`).
- `passage_not_generic_summary`. **Change:** replace the cross-requirement count with the derived `source_kind` (§14), so a single-role
  generic passage is also refused.
- `referentially_closed`.
- `requested_construct_direct`. **Change:** restrict to `passage_direct` and `mapping_link`; paper-level occurrence is context only.
  **Change:** fail closed when terms are absent.
- Attribution (`attribution_kind`), shared with mapping (§13).
- Joint witness over all operands (`relations.py`), permanently.
- Direction at value level requires the subject in the same sentence (D1).
- `stimulus_rating_cue`, as a demotion veto.
- Enumeration guard (`negation_or_hedge`).
- **Add:** a polarity-aware value-sentence check (`classify.py:234-243`). It **classifies** the statement by `observation_polarity` and
  requirement goal, rendering a null as a null result. It does **not** discard the sentence. This check is the Phase 30 classification
  gap; presentation is already safe.
- Caption check (`is_caption_passage`), permanently.

Downstream checks stay after upstream repair. They are cheap and guard against mapper regressions.

## 16. Generalizability

Re-checked against the revised enums.
- **Architecture.** Ratings of buildings → `stimulus_or_target`; occupant trait → `focal_person`. Passes.
- **Language learning.** Word difficulty ratings → `stimulus_or_target`; learner ability → `focal_person`. Passes.
- **Placebo / clinical.** Treatment administered with a null outcome: the outcome observation is `null_finding`; the requirement goal
  decides satisfaction. Comparator absence is a requirement-level gap. Passes, with a caveat: a null without an authored comparator role is
  interpretable only once that role exists.
- **Informant designs.** Covered by `focal_person` with the informant unrecorded in v1. Passes, flagged as a known limit.
- **Categories generally.** Polarity applies to any category; nothing depends on "implicit" or "explicit".
- **Watch.** Lexicons (meta-summary, stimulus cues, negation) must each have a generic justification and a synthetic twin test.

## 17. Freeze and version identity (revised; replaces the revision-1 I2 position)

### 17.1 Precedent in this repository

- **v8 → v9** (`sufficiency_authoring.py:38-48`): a contract-visible semantic change created a new question key with a supersession
  record (`author_supersession`, `:136`). Freeze and review are enforced by `sufficiency_freeze.py`, which requires a recorded human review
  naming the combined hash (`REVIEW_PATH`).
- **PLAN_VERSION** (`answer_plan/plan.py:20`): the answer layer records a version constant in its output.
- **Replay authorizations** (`answer_plan/replay.py:157-170`) bind the map hash, the frozen-contract hash and the ledger hash in `bound_inputs`.
- **Nomination authorizations per version** (`sufficiency_model_nomination_authorization_v9_*.json`): receipts are versioned.

### 17.2 The gap

The sufficiency map carries **no** version of mapping or completion semantics (`SUFFICIENCY_CONTRACT_VERSION` is a contract-format string).
A change to mapping or completion code can therefore leave the JSON hashes unchanged while meaning something different. The revision-1 I2
position relied on exactly that. It is rejected.

### 17.3 Recommended mechanism (least disruptive, correct)

1. **Runtime-only, no semantic change (I1).** No version bump. Parity is by projection (§19, I1).
2. **Mapping or completion semantic change with no authored change (I2–I5).** Add a single `SUFFICIENCY_SEMANTICS_VERSION` constant beside
   `MAPPING_STRATEGIES` in `sufficiency_engine.py`. Stamp it into the sufficiency-map output and bind it in the replay authorization's
   `bound_inputs`. Bump it on any change to derivation, satisfaction, completion or recovery logic. This is the code-identity channel the
   steering asked for, following the `PLAN_VERSION` precedent. A semantic change then changes the reproducible identity, and a replay diff
   shows the version change.
3. **Authored contract change (D3 expected values, D4 construct anchors, any declared `measured_coverage` goal).** Create a new frozen
   question version (v10), with supersession records and a recorded human review naming its combined hash, following v8 → v9. No re-freeze
   happens in Phase 31.
4. **Code identity.** Replay authorizations also record the commit of the semantics being replayed, so a version constant that was not bumped
   is still visible in review.

Step 2 is the least disruptive correct mechanism: no re-freeze for code-only semantic work, and no way to change meaning without changing
identity.

### 17.4 Consequence for I2

I2 is a semantic change with no authored change, so it bumps `SUFFICIENCY_SEMANTICS_VERSION` and leaves the frozen v9 JSON hash unchanged. The
replay must report the version change explicitly. It must not be presented as "the same frozen v9 contract".

## 18. Migration and freeze blast radius

| Artifact | Changes when | Consequence |
|---|---|---|
| `sufficiency_contract.aib_hier_v9.frozen.json` | Authored fields added (`described_entity` expectations, construct anchors, `measured_coverage`) | v10 with review (§17.3.3). Runtime-only fields and code semantics do not change this hash |
| `17_sufficiency_map.json` sha | Any binding or instance field added; version stamp added | Expected for I1 (new fields). Reported as an expected change, not a parity failure (§19) |
| `11_verified_ledger.json` / `sealed_hash` | Sealing changes (I7 join fix) | New sealed run; Phase 26–28 explained |
| ParentClaim ids (`parent_synthesis_ledger.py:92-110`) | `values` (role, proposition_id, exact_text), `instance_keys`, `admissible_proposition_ids`, or `direction_or_effectiveness` change | I1 should leave claim ids unchanged, since the payload excludes the new fields (to confirm). I2 changes c3. I5 changes c4/c5/c6 |
| Model-nomination receipts (`…_v9*.json`) | Admissibility changes | `_prior_receipt_is_admissible` rejects stale receipts wholesale (fail closed) |
| Live Attempt-2 run | Never rewritten | New outputs go to new directories |
| Tests pinning current semantics | Changed by design | `test_sufficiency_engine.py:105, 123`; `test_sufficiency_direction_effectiveness.py:125, 134, 140, 152, 285, 306`; `test_sufficiency_mapping.py:78–200, 442`; `test_answer_plan.py:182, 207, 233, 288, 347`; `test_answer_plan_replay.py:73` |
| `REQUIREMENT_STATES`, `REASON_CODES` | Not changed | Avoids cascade through recovery and stop-search |
| `complete` | Not renamed or redefined in I1 | Parent eligibility, stop-search and recovery keep behaviour |
| Sealed `evidence_spans` (duplicate rows) | Only if deduplicated | Changes sealed hash; deferred to the gated sealing increment |

Offline re-map needs no models: `test_sufficiency_phase19b_real_v9_replay.py` recomputes `compute_diagnostic_sufficiency_map` on the sealed
ledger with held-fixed receipts and zero model calls.

## 19. Implementation sequence (revision 2)

Ordering follows dependency and blast radius. Each increment is independently testable and revertible.

**I1 — additive relation-witness metadata (C groundwork). READY (see §21).**
- *Code:* compute `relation_witnessed`, `witness_ids`, `witness_provenance` per relational instance after mapping, by the §7 rule with the
  I1 conservative referent (verbatim parent `exact_text`). `complete` untouched. Answer layer keeps its independent witness logic
  (`relations.py`) and cross-checks the new field.
- *Contracts:* none frozen. Runtime-only.
- *Acceptance, projection parity (not byte parity).* Define π as: remove `relation_witnessed`, `witness_ids`, `witness_provenance` (and any
  other keys introduced by I1); canonicalise with `sort_keys` and `ensure_ascii=False`. Require π(new) = π(baseline) exactly, for: the
  sufficiency map, recovery targets, ParentClaims, `answer_plan.json` (excluding its own hash fields), and the layer 1/2/3 markdown outputs.
  Every existing binding, completion state, recovery target, ParentClaim and rendered sentence must be unchanged.
- *Reported, not failures:* hashes that legitimately include the new fields (`17_sufficiency_map.json` sha, `plan_sha256`,
  `answer_plan_audit.json`). Report old and new values. Expected to change, by construction.
- *Expected disagreement record (Phase 28 replay):* engine-complete and not-witnessed instances, expected to be exactly c5 ×2 and c6 ×2.
  Expected agreement: c4 `b140…`. Recorded explicitly, not hidden.
- *Tests:* the §7 synthetic cases 1–5 (generic, alpha/beta); unit tests for W1–W8.
- *Models:* none. *Frozen:* none. *Offline replay:* yes (phase19b pattern).
- *Scientific gain:* zero, by design. A stop at I1 is a valid outcome.

**I2 — observation polarity and goal-specific satisfaction (B).** Bumps `SUFFICIENCY_SEMANTICS_VERSION` (§17.4).
- *Code:* `observation_polarity` on category bindings. Presence satisfaction per §8.2. `answer_status` view (§8.3). Polarity-aware
  classification of value sentences (§15). Recovery and terminality per §8.4.
- *Requirements:* default `established_presence`. No v9 requirement is changed to `measured_coverage`.
- *Tests:* synthetic positive, null, mentioned-only cases; a null under presence does not satisfy; a null under coverage does; recovery
  stays warranted before search completion; `measured_null_terminal` only after completed search.
- *Expected change:* c3 `implicit` moves from `filled` to measured-null-only. c6 unchanged. ParentClaim ids for c3 change (explained).
  Recovery targets may increase for c3 (planned, not executed offline).
- *Stop/go:* no presence claim from any null; no loss of positive findings; every recovery target change explained.

**I3 — direction target (D).** Depends on I1.
- *Code:* `direction.target`, `sentence_witness`. Relation-level direction only when `relation_witnessed`; otherwise value-level with subject.
- *Expected change:* c6 `negative` no longer attached to an unwitnessed relation. Direction summaries change.

**I4 — clause-level result spans and derived source-kind (A, S).**
- *Code:* clause-level achieved-outcome spans. `source_kind` at mapping (§14). Non-result source kinds become candidate. Completion ignores candidates.
- *No sealing change.* Mapping-time derivation only.
- *Expected change:* c3 `attitude-manifestation` stops being `filled` on generic p1/p4 alone.
- *Stop/go:* no requirement complete on a generic passage alone; genuine results still fill; suppressed-evidence count does not rise.

**I5 — referent normalization (F, E identity).** Closed head-noun list, literal containment, `referent` provenance (§10). Relaxes the I1
conservative surface with provenance. ParentClaim ids change for c4–c6. Stop/go: normalized referents are literal substrings of the quote.

**I6 — described entity (E). Live-gated; D3.** Closed-taxonomy nomination, verified, demotion veto. Requires an experiment brief and approval
under the experiment gate, and a pin decision. Not READY until D3 criteria in §9.6 are met.

**I7 — sealing join-chain fix (G). Gated.** §12. Requires a new sealed run and a Phase 26–28 explanation. Also decides whether duplicate-row
emission is fixed in the same code path.

**I8 — construct authority (H). Frozen; D4.** Authored anchors and `mapping_link`, under a new frozen version (§17.3.3). Stop/go: adjacent
evidence is labelled at binding time, not only at render time, and paper-level occurrence no longer grants direct authority.

## 20. Phase 30 replay as the oracle of effect

After each increment: does the deterministic AnswerPlan gain scientifically legitimate answers without losing its fail-closed properties?
Structural expectations only. No q_aib answer text is specified.

Methodology:
1. Record baseline hashes (§0) before any code change.
2. Offline re-map from the sealed ledger with held-fixed receipts. Diff maps: changed bindings, instances, completions, recovery targets.
3. Run the Phase 30 replay on the new map. Compare by category.
4. Check structural expectations. Explain every ParentClaim id change. Apply projection parity for I1, and version-stamped diffs for I2+.

Expected structural effects:
- **Newly witnessed relation:** one whose own operands share a single admissible proposition and whose inherited referent surface appears in it.
  Expected to be rare. On current data, the only admissible result-level candidate is p11 (§3.2), and it needs correct operand typing.
- **Correctly represented null:** a category observation classified `null_finding`, not presence.
- **Correct described entity (once I6 lands):** no stimulus-rating value fills a `focal_person` role.
- **Closed entity name:** every rendered entity is a literal substring of a cited quote.
- **Reduction in suppressed valid evidence:** fewer suppressions for `unwitnessed_relation` or `operands_not_in_one_sentence` where a legitimate
  witness exists.
- **No increase in unsupported claims:** Layer-1 statements lacking verbatim support, and generic or prior-work Layer-1 statements, do not rise.
- **Truncation (after I7):** no rendered operand ends non-terminal.

Anti-fitting: every rule is tested with a synthetic twin from another domain. A fixture from the preserved run is never the only test.

## 21. READY / NOT READY

- **Full upstream repair: NOT READY.** Needs D2 (confirmation of §17), D3, D4, and I1 evidence.
- **I1: READY**, with D1 approved. Preconditions 2 and 3 are conditions for implementation, not for this audit:
  1. Maintainer confirms D1: add `relation_witnessed` (and its provenance) as separate runtime fields, and keep `complete` unchanged.
  2. Baseline hashes in §0 are recorded before code, and the baseline projection π(baseline) is captured.
  3. Acceptance is projection parity (§19), the §7 synthetic cases pass, and the expected disagreement list (c5 ×2, c6 ×2) is recorded explicitly.
- **I2: NOT READY** until §17 (versioning) is confirmed and §8 is accepted as the design.
- **I3–I8: NOT READY.** Each depends on an earlier increment, a freeze decision, or a live gate.

What I1 can and cannot show: it makes engine relation status explicit and checkable. It yields no new scientific answer.

## 22. Decisions

- **D1 — APPROVED.** Add `relation_witnessed` and its witness provenance as separate runtime fields; keep `complete` unchanged.
- **D2 (future, before I2).** Confirm the versioning mechanism in §17.3 (`SUFFICIENCY_SEMANTICS_VERSION` for code semantics; v10 frozen for authored
  content; code commit recorded in replay authorizations). Designs are stated; no re-freeze in Phase 31.
- **D3 (future, before I6).** Expected `described_entity` values: authored into the frozen contract (v10), or answer-layer only. Plus acceptance
  of the §9 enum.
- **D4 (future, before I8).** Construct anchors and `mapping_link`: authored into a new frozen version, or kept overlay-owned.
- **D5 — RESOLVED.** Per the Phase-30 adopted rule: future production has one canonical, hash-bound Answer Contract representing the decomposition
  the researcher actually confirmed. Layer 1 answers exactly that contract. Historical Phase-28 approval artifacts stay as recorded, inconsistent
  but not rewritten (U13 remains a provenance and migration issue). The Phase-30 replay overlay is an explicit post-hoc replay-only authorization.
  Note the naming: the Phase-30 results document uses "D5" for the verbatim-rendering rule, a different decision.
  **Implementation work (not a blocker):** no Answer Contract artifact exists in code today (checked: only Phase 29 and REVIEW_NOTES mention it).
  Production migration tasks are: define the canonical contract schema; bind it to frozen contract hashes; produce it from the researcher-confirmed
  decomposition rather than the overlay; have the replay consume it. Sequenced after I1 and before any production consumer of Layer 1.

## 23. Verification status (what is and is not established)

Established by read-only forensic work on preserved artifacts:
- G cause and classification (§3.1), by production code over the read-only copy, plus the pure verifier.
- B/amygdala classification (§3.2), by distinct-identity counts and `attribution_kind`.
- Duplicate `evidence_spans` rows (§0, §12): counts only. The writer is not located.
- Paper 14 distinct count (86), with 0 distinct matches for "anomal|facial".
- Freeze precedent (§17.1) by reading the cited files.

Not established:
- The writer of duplicate `evidence_spans` rows.
- Whether "just-world beliefs" or "empathic concern" should be typed as the c6 attitude operand. That is construct and operand typing (H, E), not a witness result.
- The antecedent for "Across these levels of organization" (not located in the sealed spans examined).
- The chunk-level origin of the complete Hadza sentence on page 4 (chunk 43366) and whether it was retrieved for this run.
- Effects of I1–I8 on the Phase 28 forensic report's rendering path. Not re-read here.
- Any offline re-map output. The phase19b test is cited as an oracle, not executed in this phase.


## Record of this phase

- This phase is docs-only. It adds this audit and one dated Phase 31 section appended to `CONTRIBUTION-LINEAGE.md`.
  Nothing else changes.
- No production code, model, live run, pin, or frozen contract changed. I1 is not implemented in this phase.
- Verification of the write step: the commit's file list must match exactly these two paths. Frozen contracts, the nomination
  authorization files, `app/frontend/`, and the §0 preserved-input hashes must be unchanged from the values recorded in §0.
- No pytest run applies to a docs-only phase.
- `app/frontend/js/20_synthesis.jsx` predates this phase and is not touched here. If the line-budget hook blocks the commit on that
  file, the commit is made with `--no-verify`, authorized for this phase only, and the commit message records that.
