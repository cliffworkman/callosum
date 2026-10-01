# Phase 8 — forensic/planning pass over Phase 5 + Phase 7 (2026-09-30)

**No code changes. No live model calls. No recovery. No retrieval. No E2E. No contract changes. v9
untouched throughout — confirmed byte-identical, hash `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.**
This is a read-only analysis of artifacts already on disk: Phase 7's `qwen_calls.jsonl`/`result.json`,
Phase 5's own already-frozen adjudication, `11_verified_ledger.json`, and the v9 frozen contract.

## 1. Forensic reconstruction of all Phase 7 validator decisions

All 5 specificity calls, all 11 candidates, reconstructed verbatim from the frozen trace. `v9
category_description` and the raw prompt/output are quoted exactly as recorded — no summarization.

| Call | Child/Role | v9 `category_description` | Nominated `exact_text` | Proposition passage (verbatim, truncated where noted) | Parsed decision | Manual truth | Classification |
|---|---|---|---|---|---|---|---|
| 2 | c1 `brain_region_or_network` | `a specific named brain area` | `the specific amygdala response` | "Across these levels of organization, the specific amygdala response to facial anomalies correlated with stronger just-world beliefs (i.e., people get what they deserve), less dispositional empathic concern, and less prosociality toward people with facial anomalies." | `specific=false, instance_text=""` | Correct (amygdala is a specific named region) | **INCORRECT VETO** |
| 11 | c4 `named_brain_region_or_network` | `a specific NAMED brain area` | `the specific amygdala response` | *(identical passage, re-discovered independently)* | `specific=false, instance_text=""` | Correct | **INCORRECT VETO** |
| 9 | c2 `behavior_or_behavioral_measure` | `an observed behavior, behavioral choice or action, or a task or measure of behavior (not a self-report attitude, belief, or prejudice questionnaire)` | `described a behavioral manifestation of the "anomalous-is-bad" stereotype affecting prosociality` | "This research confirmed earlier reports that people with anomalous faces are imbued with negative personality characteristics, detected explicit biases against people with facial anomalies, and described a behavioral manifestation of the "anomalous-is-bad" stereotype affecting prosociality." | `specific=true, instance_text=<same text>` | **Incorrect** (vague/circular — no referent named) | **INCORRECT ACCEPT** |
| 9 | c2 `behavior_or_behavioral_measure` | *(same)* | `visual attention toward people with facial anomalies` | "Despite these limitations, this study characterized relations between biases and social dispositions with visual attention toward people with facial anomalies and characterized the way biases and social dispositions influence visual attention when looking at faces with anomalous anatomy." | `specific=true, instance_text=<same text>` | Correct | **CORRECT ACCEPT** |
| 9 | c2 `behavior_or_behavioral_measure` | *(same)* | `influence visual attention when looking at faces with anomalous anatomy` | *(same passage as above)* | `specific=true, instance_text=<same text>` | Correct | **CORRECT ACCEPT** |
| 13 | c8 `individual_difference_trait_or_construct` | `a named individual-difference trait or construct` | `negative attitudes (IAT and EBQ)` | "We suggest that dehumanization is underpinned by a suite of negative attitudes (IAT and EBQ), social cognitive biases (just-world beliefs), emotional dispositions (affective empathy), and undesirable behaviors (less generosity in the DG)—all factors associated with the functioning of the left amygdala." | `specific=false, instance_text=""` | Correct | **INCORRECT VETO** |
| 13 | c8 `individual_difference_trait_or_construct` | *(same)* | `social cognitive biases (just-world beliefs)` | *(same passage)* | `specific=false, instance_text=""` | Correct | **INCORRECT VETO** |
| 13 | c8 `individual_difference_trait_or_construct` | *(same)* | `emotional dispositions (affective empathy)` | *(same passage)* | `specific=false, instance_text=""` | Correct | **INCORRECT VETO** |
| 13 | c8 `individual_difference_trait_or_construct` | *(same)* | `undesirable behaviors (less generosity in the DG)` | *(same passage)* | `specific=false, instance_text=""` | Correct | **INCORRECT VETO** |
| 18 | c6 `attitude_type_or_measure` | `a named attitude type or measure` | `Explicit Bias Questionnaire` (anchor group 1) | "Nevertheless, we found evidence for the "anomalous-is-bad" stereotype in explicit negative attitudes about people with facial anomalies both as individuals (i.e., character inferences) and as a group (i.e., scores on the Explicit Bias Questionnaire)." | `specific=false, instance_text=""` | Correct | **INCORRECT VETO** |
| 18 | c6 `attitude_type_or_measure` | *(same)* | `Explicit Bias Questionnaire` (anchor group 2, identical text/context) | *(identical passage)* | `specific=false, instance_text=""` | Correct | **INCORRECT VETO** |

**Totals: 11 candidates. 2 correct accepts, 1 incorrect accept, 0 correct vetoes, 8 incorrect vetoes.**

### Do the 8 incorrect vetoes share a concrete, observable characteristic?

**Observation (directly readable from the table, not inferred):** 7 of the 8 incorrect vetoes
(amygdala ×2, c8's 4 traits) share a specific syntactic shape in their `exact_text`: **the
grammatical head of the nominated noun phrase is an abstract category or occurrence noun, and the
actual specific identifier is syntactically subordinate** — either a trailing modified head
("the specific amygdala**↳response**", head = *response*, an occurrence/effect noun, "amygdala"
only modifies it) or a parenthetical aside ("negative attitudes **(IAT and EBQ)**", head =
*attitudes*, an abstract category noun; the real identifiers are bracketed off, not the head).
Cliff's own prompt examples ("adolescents in Japan," "mindfulness training") have the OPPOSITE
shape — the specific content IS the head of the phrase, nothing abstract or occurrence-shaped
dominates it.

**Observation:** the 8th incorrect veto (both EBQ candidates) does **not** fit this pattern —
"Explicit Bias Questionnaire" is a bare proper-noun-shaped compound with no abstract head or
parenthetical structure, structurally identical in shape to Cliff's own "mindfulness training"
positive example. No syntactic-shape explanation accounts for its rejection.

**Observation:** the one incorrect accept ("described a behavioral manifestation...") is the
longest, most clause-like nominated text of any candidate in the batch (a verb phrase with no
nameable referent at all — no noun names a specific entity, trait, instrument, or action beyond
restating that "a manifestation...was described").

**Hypothesis (not proven from the trace alone, offered with the above two observations as its
basis):** the validator may be judging specificity by a surface/lexical heuristic sensitive to
whether the phrase's dominant word is itself an occurrence/effect/category noun ("response,"
"attitudes," "manifestation") rather than genuinely parsing "does ANY part of this span name a
specific referent." Under this reading, "amygdala response" and "attitudes (IAT and EBQ)" are
read as fundamentally ABOUT an occurrence/category and get rejected on that dominant cue despite
containing a real identifier; "a behavioral manifestation...affecting prosociality" happens to
contain the literal word "behavioral" which may read as topically on-point for a `behavior_or_
behavioral_measure` role regardless of the fact that the sentence never names which behavior.
**This is a plausible, not confirmed, model-internal explanation** — no model internals were
inspected, consistent with Phase 5's own identical disclaimer about its analogous hypothesis.

**Open/unexplained:** EBQ's rejection has no syntactic-shape explanation. Two candidate
hypotheses, neither confirmed:
(a) **context-level cue bleed** — the surrounding passage reads "...scores on the Explicit Bias
Questionnaire," and "scores" (a measurement-outcome noun) sits immediately before the instrument
name; the validator may be reacting to passage-level occurrence language rather than the
nominated span itself (weaker evidence than the syntactic-shape hypothesis above, since the
circular c2 candidate's passage is comparably occurrence-heavy yet THAT one was accepted, not
rejected — the directions don't consistently align).
(b) **duplicate-candidate batch effect** — call 18 is the only specificity call in this run with
two candidates sharing byte-identical `exact_text` AND `context` (two separate anchor groups
quoting the same physical sentence). This is a genuine structural anomaly worth flagging
separately from any semantic hypothesis (see §2).

## 2. No hidden implementation/schema explanation found

Every sub-check re-verified directly against the frozen artifacts and code, with no code changed:

| Check | Result |
|---|---|
| `candidate_id` → decision mapping | **Correct.** Every decision's `candidate_id` in all 5 raw outputs exactly matches an offered id (`cand0..candN`); none invented, none mismatched. |
| `specific` true/false interpretation | **Correct.** `json.loads` maps JSON `false`/`true` to real Python `False`/`True`; `confirm_specific_instances`'s `decision.get("specific") is not True` correctly drops every `false` decision — confirmed by direct inspection of the code path, not assumed. |
| `instance_text` requirement causing an otherwise-good candidate to fail | **Not a factor.** Every one of the 8 incorrectly-vetoed candidates already carried `specific=false` with an empty `instance_text` **from the model's own output** — the host-side grounding check (`canonical_text_contains`) never had a chance to reject anything, because the model's own `specific` flag was already false. The failure is unambiguously upstream of any host-side logic. |
| Output truncation / schema constraints | **Not a factor.** `generated_tokens` for the 5 calls were 45, 147, 45, 66, 36 — all well under the 384-token `output_cap`; `done_reason="stop"` on every call (natural completion, never a cap-induced cutoff). |
| Interaction/order effects across candidates in one call | **Not ruled out; flagged as open.** Cannot be proven or disproven from a single recorded trace without an ablation (one-candidate-per-call vs. batched) — explicitly out of scope for a no-live-call phase. The EBQ duplicate-candidate call (§1) is the one concrete site where such an effect is plausible; the c8 call's uniform 4-for-4 rejection is also consistent with either a shared genuine cause OR a batch-anchoring artifact, and the trace alone cannot distinguish them. |
| Validator saw the intended passage for every candidate | **Confirmed correct**, directly cross-checked: every candidate's `context` field in the specificity prompt matches its own proposition's `quote` in `11_verified_ledger.json` exactly (all 11 candidates checked programmatically). No cross-candidate passage contamination. |
| `category_description` exactly the v9 text | **Confirmed exact**, cross-checked against `sufficiency_contract.aib_hier_v9.frozen.json` directly: all 5 prompts' category lines match the frozen contract's own `role_specs[...]["category_description"]` strings byte-for-byte. |
| A candidate accidentally evaluated against another candidate's context | **Not a bug where it occurs.** Several candidates legitimately share an identical `context` (c8's 4 candidates all come from the one sentence enumerating all 4 constructs; c6's 2 candidates are duplicate propositions over one physical anchor) — this is a correct, expected feature of how evidence is structured (one sentence naming several things), not cross-contamination. Distinguished explicitly from the *interaction-effect* question above, which is about whether judgment bleeds across candidates in the same call regardless of whether their contexts are legitimately identical. |

**Conclusion of §2: the failure is genuinely semantic/model-level, not a plumbing, schema, or
mapping defect** — consistent with and reinforcing Phase 7's own finding, now independently
re-verified from the artifacts rather than taken on faith.

## 3. Analysis of the Phase 5 false fill itself

### The structural mechanism (generalized, not c2-specific)

c2's `behavioral-manifestation` requirement has two required roles: `behavior_or_behavioral_measure`
(model-sourced, identification) and `behavioral_manifestation_evidence` (deterministic,
`achieved_outcome_predicate` — binds to the **entire passage** of whichever admissible unit's text
satisfies `attr.has_result_predicate`, confirmed by reading `_match_achieved_outcome`'s own
docstring: "Returns the whole passage... not one token"). For proposition **p1**, that deterministic
match IS the full sentence containing the word "behavioral manifestation." When the model's
`behavior_or_behavioral_measure` nomination is **also** drawn from p1 (the circular candidate), its
`exact_text` is a literal substring of the SAME sentence `behavioral_manifestation_evidence` already
claimed whole. `same_proposition` (Phase 4's own joint-grounding check) only tests proposition-id-set
intersection — it has no notion of "did this role contribute anything beyond what the other role
already captured." Two propositions that are literally the same sentence satisfy it trivially.

**Critical cross-check — does this mechanism ALSO explain Phase 5's correctly-accepted c1/c4
amygdala finding, which this planning pass must not inadvertently condemn?** Yes, structurally
identically: c1's `brain_region_or_network` ("the specific amygdala response") and its own evidence
role (`neural_manifestation_evidence`) are **also** both bound to the same proposition (p2/p11).
**A naive rule that simply forbids an identification role from sharing a proposition with its
sibling evidence role would incorrectly reject c1/c4's genuinely-correct finding along with c2's
false one.** This is the single most important finding of this forensic pass — see §4.C.

### What actually distinguishes the two cases, side by side

| | c1/c4 amygdala (correct) | c2 circular (incorrect) |
|---|---|---|
| Shares a proposition with the sibling evidence role? | Yes | Yes |
| Does the nominated `exact_text` name a specific referent (an entity) not otherwise isolated by the evidence role? | **Yes — "amygdala,"** a named brain structure | **No** — no noun in the span names any entity; it restates that *a* manifestation occurred |
| Would the information be lost if this role were dropped entirely? | Yes — "amygdala" is the only place the SPECIFIC region is ever named | No — `behavioral_manifestation_evidence` already fully captures everything in this text; the identification role adds nothing new |

**The generic, mechanically-grounded answer to the pre-registered key question:** there is **not**
a cleanly engine-enforceable distinction from proposition/anchor identity alone (§4.C expands this).
There **is** a real, defensible distinction at the level of "does the nominated span itself contain
an extractable referent, as opposed to being wholly a restatement of occurrence" — but that
distinction is semantic, not structural, and is exactly what the first-stage nomination task (not a
second validator) is best positioned to enforce directly, by being asked to *extract* a referent
rather than *judge* a whole span after the fact (§4.A).

### c1/c4/c6/c8 comparison, requested explicitly

| Candidate | `proposition_id`(s) | Shares proposition with a sibling required role? | Names a referent? | Redundant with sibling role's own text? |
|---|---|---|---|---|
| c1/c4 "the specific amygdala response" | p2/p11 (collapsed) | Yes (with the evidence role) | Yes — "amygdala" | No — amygdala's identity is new information |
| c2 circular "described a behavioral manifestation..." | p1 | Yes (with `behavioral_manifestation_evidence`) | **No** | **Yes — adds nothing `behavioral_manifestation_evidence`'s own full-passage text doesn't already say** |
| c2 "visual attention toward people with facial anomalies" | p5/p15 | No (different proposition than p1) | Yes | n/a — doesn't share a proposition with the sibling role at all |
| c8's 4 traits | p20/p9 | No sibling evidence role on this requirement (c8's completion only requires the one identification role + `relationship_to_bias_manifestation`, itself `missing` in this run) | Yes — each names a distinct construct | n/a |
| c6 EBQ ×2 | p3/p7/p14/p17/p26 | No sibling evidence role sharing this proposition | Yes — "Explicit Bias Questionnaire" | n/a |

## 4. Alternatives evaluated

### A. Remove the second validator; strengthen first-stage extraction

Reframe the nomination task from "does ANY excerpt name a SPECIFIC instance... return the exact
supporting substring" (the current prompt, which allows an over-broad "supporting substring" and
has, across all three live phases, consistently extracted the entire circular clause rather than
nothing) to: **extract the SHORTEST exact span that itself names WHICH instance; if the excerpt
only asserts that some instance of the category exists/occurred/was measured, with no nameable
referent, return nothing for it.** The two already-battle-tested cross-domain examples from the
Phase 6 prompt ("adolescents in Japan"/"a population was studied"; "mindfulness training"/"an
intervention reduced symptoms") transplant directly into this reframed nomination prompt — no new
vocabulary needed.

**Assessment:** this directly targets the ROOT shown in §3 — c2's problem is that the nominator
extracted an over-broad span with no referent in the first place, not that a second judge failed to
catch it afterward. A minimal-span framing would plausibly have extracted **nothing** for c2's
circular sentence (there is no referent to extract), while for c1/c4 it would plausibly extract
just **"amygdala"** rather than "the specific amygdala response" — which also *sidesteps* the
syntactic-shape confusion §1 found (a head-noun of "response" no longer appears in the nominated
span at all, since a true minimal extraction would stop at the entity name). This is strong
circumstantial support, not a live-tested confirmation — a reformulated prompt has not been run.
**Promising; the most generalizable and lowest-overhead candidate** (zero additional model calls
versus the current single-nomination pass, since it replaces rather than adds to the existing call).

### B. Deterministic identification-shape guard

Evaluated with explicit skepticism, as instructed, and **rejected as a standalone mechanism**: a
capitalization/POS/named-entity heuristic cannot be made robust in a benchmark-neutral way, proven
directly against Cliff's own canonical positive examples — "mindfulness training" and "adolescents
in Japan" are **not** proper-noun-shaped (no capitalization, no NER-recognizable entity type), yet
both are the exact standard for "specific" the whole gate is built around. A regex/POS rule would
either reject these canonically-correct cases or admit arbitrary lowercase noun phrases
indiscriminately — there is no light heuristic threading that needle. The underlying idea (role
metadata such as `requires_named_instance`) could survive as a **non-enforcing annotation** read by
a human-authored or model-facing extraction prompt (telling it which roles need "which X" framing),
but not as an automatic deterministic gate.

### C. Cross-role non-redundancy / information gain

**The naive version of this (forbid any identification role from sharing a proposition with
another required role) is demonstrably unsafe** — §3's side-by-side comparison shows it would
reject c1/c4's genuinely-correct amygdala finding along with c2's false one, since both share a
proposition with their sibling evidence role. A safe version would need a notion of "the
identification role's `exact_text` adds a referent the sibling role's own `exact_text` doesn't
already isolate" — which is not mechanically decidable from spans/proposition identity alone
without re-introducing a semantic "does this name something new" judgment, the exact kind of call
the live validator failed at in Phase 7. **Not viable as a clean, purely-structural standalone
mechanism** — but a cheap, narrow, best-effort DETERMINISTIC safety net is still defensible as a
secondary layer under Option A: e.g., reject a model nomination whose `exact_text` equals or is a
near-total superset-overlap of a sibling required role's own `exact_text` (a crude redundancy
smell-test, not a specificity judge) — this would have correctly flagged c2's circular case (its
`exact_text` is wholly contained within `behavioral_manifestation_evidence`'s own full-passage
text with no non-overlapping content) while leaving c1/c4 untouched (amygdala's "identity" is not
contained in — nor removable from — the evidence role's own binding). Framed this way, it is a
**complement to A, not a replacement.**

### D. Requirement-aware / contrastive nomination

Essentially the authoring-time half of Option A's same idea: give `RoleSpec.category_description`
an explicit, benchmark-neutral contrastive exclusion — "this is NOT satisfied merely by text
asserting that some instance of this category occurred, exists, or had an effect; it must name
which one." The precedent already exists in this exact contract: c2's own `category_description`
already carries a parenthetical exclusion ("not a self-report attitude, belief, or prejudice
questionnaire"). Extending the same authoring pattern with an occurrence-vs-identification
exclusion costs nothing structurally (no schema change, no new call) and is strictly more
generalizable than a second model call, since it is enforced by the SAME model, in the SAME call,
against the SAME passage it already has in context — rather than asking a second model to re-judge
an already-extracted, potentially-already-corrupted span after the fact. **D and A are best
understood as one unified redesign of the single nomination step, not two separate mechanisms.**

### E. Different model / ensemble

**Not justified by current evidence**, per the instruction's own framing. §2 established the Phase
7 failure is genuinely semantic, not a plumbing defect — but §1/§3 also show the failure is highly
consistent with a *specific, nameable task-formulation weakness* (holistic post-hoc judgment of an
already-broad, ambiguously-headed span, with zero chain-of-thought space under thinking-OFF) rather
than a demonstrated ceiling on what this model can do at the underlying task. The evidence that
would justify a model change: a reformulated, minimal-span-extraction nomination prompt (Option
A/D) is live-tested with `qwen3.5:9b` and STILL shows a comparable or worse error rate on genuinely
clean cases. That test has not been run. Recommending a model swap now would repeat exactly the
mistake Cliff's own framing warns against ("blindly tuning... do not assume the answer is 'improve
the validator prompt'" generalizes to "do not assume the answer is 'swap the model'" either, absent
evidence the task itself, not the model, was given a fair formulation).

### F. Recovery-side asymmetric treatment (fail-safe, not fail-perfect)

**The most architecturally robust complement, independent of whichever mapping fix is eventually
chosen.** Treat a model-assisted `filled` state as **provisional** for STOP-SEARCH purposes — i.e.,
a recovery controller would not treat `candidate_source="model_mapping"` the same as a fully
corroborated, multi-source, or deterministic `filled` state when deciding whether to suppress
further search — while the binding remains fully usable for answer construction and display (never
hidden, never downgraded in the user-facing map; see invariant #4, "never hide a low-confidence or
flagged claim" — this is a direct architectural analogue at the sufficiency-engine layer). This
does **not** require the mapper to achieve anything close to perfect precision to be safe for
recovery: even a mapper with Phase 7's own demonstrated error rate could not, under this scheme,
cause the catastrophic "recovery stops searching on a false claim" failure Phase 5/7 are both
fundamentally worried about — because a model-sourced `filled` would never by itself be read as a
stop-search certificate. This is a **generic, reusable property of the recovery CONTROLLER**, not
specific to c2/behavior at all, and composes cleanly with Options A/D (which reduce how often this
provisional flag would even need to matter) rather than substituting for them.

## 5. Generalization test (benchmark-neutral domains)

The combined mechanism evaluated here is **A+D** (minimal-span extraction, explicit null-on-no-
referent, authoring-time contrastive exclusion), with **C's narrow redundancy smell-test** as a
cheap secondary net and **F** as the recovery-side backstop — reasoned through, not implemented:

| Domain | Generic assertion (should extract nothing) | Specific instance (should extract the minimal referent) | Mechanism holds? |
|---|---|---|---|
| Population | "a population was studied" — no referent | "adolescents in Japan" — referent is the whole phrase, extracted verbatim | Yes |
| Intervention | "an intervention reduced symptoms" — no referent | "eight weeks of mindfulness training" — minimal referent "mindfulness training" extractable from within the longer clause | Yes |
| Measurement | "neural activity was measured" — no referent | "functional MRI" — a named modality, directly extractable | Yes |
| Behavior | "a behavioral effect occurred" — no referent | "participants donated less money" — names the specific action/measure (a clause, not a bare noun — confirms the mechanism's test is "does this answer WHICH," not "is this a noun phrase," consistent with how the task is already framed) | Yes |
| Trait | "individual differences predicted the outcome" — no referent | "trait anxiety" — directly extractable | Yes |

A **re-run of this exact Phase 7 case** under the proposed reframing, reasoned through (not
executed): c1/c4 minimal extraction → "amygdala" (sidesteps the head-noun-is-"response" confusion
entirely, since "response" would no longer be part of the nominated span); c8's four → minimal
extraction of the bracketed identifiers ("IAT and EBQ," "just-world beliefs," "affective empathy,"
"the DG" or similar) rather than their abstract head nouns; c6 EBQ → unaffected either way, since it
was already minimal (its Phase 7 veto came from the SECOND-pass validator, which A+D removes
entirely — so EBQ would simply be accepted by the single reframed nomination call, with no second
judge able to re-reject it); c2 circular → no referent exists anywhere in the sentence to extract,
so a faithful minimal-span nominator should return nothing for it. **The mechanism is not
q_aib-specific anywhere in this reasoning** — every domain pair and every Phase 7 candidate is
handled by the same single rule: extract the minimal referent, or decline.

## 6. Recommendation — exactly one path

**Redesign the single first-stage nomination task (Options A+D combined) to extract a minimal,
referent-naming span with an explicit null-on-no-referent instruction and an authoring-time
contrastive exclusion, layered with Option C's narrow redundancy smell-test as a cheap deterministic
secondary net, and Option F's provisional-fill treatment at the recovery-controller layer as a
structural backstop independent of mapping accuracy.**

Scored against the stated priorities:

1. **Generalizability** — highest for A+D (reasoned through 5 benchmark-neutral domain pairs with
   no q_aib-specific vocabulary needed anywhere); C only works as a narrow secondary net, not alone
   (§4.C); F is domain-independent by construction (it never inspects content).
2. **False-positive safety for recovery** — F provides this independent of whether A+D perfectly
   solves the semantic problem; this is the layer that actually eliminates the *catastrophic*
   failure mode Phase 5/7 both worry about, since even a residual false fill can no longer silently
   certify "stop searching."
3. **Preserving Phase 5's otherwise-strong mapping recall** — A+D is reasoned, not proven, to
   preserve or improve recall (it doesn't add a second filter that can only subtract, as Phase 7's
   gate did; it reshapes what gets proposed in the first place). This needs a live test before
   trusting it, which this phase does not authorize.
4. **Minimal model complexity/call overhead** — A+D is a **net call reduction** versus Phase 6/7 (one
   nomination call instead of nomination+specificity); C adds zero calls (host-side string check); F
   adds zero calls (controller-side policy).
5. **Inspectability/provenance** — unaffected or improved: A+D's null-on-no-referent instruction is
   at least as inspectable as the current two-stage scheme, and F explicitly makes provenance
   (`candidate_source="model_mapping"`) load-bearing for a real downstream decision, rather than a
   label nobody acts on.
6. **Avoiding endless prompt tuning** — A+D is **one** reformulation informed by concrete, artifact-
   grounded forensic evidence (§1–§3), not an iterative tuning loop; F reduces the STAKES of future
   prompt imperfection, which directly reduces pressure toward endless tuning.

### Explicit disposition of the Phase 6 specificity-confirmation gate

**Redesigned** — more precisely, **retired in its current second-pass-judgment form and folded
into a reformulated single nomination step (A+D), with its two role-specific worked examples and
schema discipline (closed `candidate_id` enum, fail-closed rules) carried forward as design
precedent for the reformulated extraction prompt rather than discarded.** Not simply "removed"
(the underlying intent — catch occurrence-only assertions — is validated as a real, recurring
problem by Phase 5's own original finding), and not "retained but disabled" (leaving dead,
untested code around that already has one demonstrated catastrophic failure mode invites exactly
the "blind re-enablement" risk the forensic pass exists to prevent). The concrete mechanism
(`confirm_specific_instances`, `specificity_prompt`, the whole second-call architecture) should be
treated as **superseded pending a new design**, not quietly left live.

### v9

**Must remain unchanged.** Nothing in this forensic pass found or implies a defect in v9's own
`category_description` text, role shapes, or completion logic — every finding traces to the
*nomination/validation task formulation* layered on top of v9, never to v9 itself. v9's hash stays
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`.

**No implementation of this recommendation has been done in this phase**, per instruction.

## 7. Credit the lineage

Appended to `CONTRIBUTION-LINEAGE.md` (Phase 8 section; Phases 1–7 unchanged).
