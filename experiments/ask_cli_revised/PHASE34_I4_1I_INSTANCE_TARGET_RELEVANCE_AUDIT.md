# PHASE 34 / I4-1i — instance-local evidence target dependency audit

**Status: PLANNING / READ-ONLY EMPIRICAL AUDIT.** No production code changed, no `RoleSpec` field added, no
mapping edit, no version bump, no `candidate_supports`/`support_policy` wiring, no I4-2a/I4-2b start, no model/
network/live-E2E run. I4-1a through I4-1h are treated as implemented/accepted, unchanged by this audit. Every
empirical claim below was produced by reading real production code directly and/or running the already-shipped,
pure I4-1 modules against the real recovered Attempt2 artifacts (same provenance as I4-1h: `.local/e2e-runs/
phase28-live-parent-synthesis-attempt2-20261004T014500Z/run/11_verified_ledger.json` and `17_sufficiency_map
{.initial,}.json`), in a disposable scratch script, never committed.

- Canonical branch: `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Starting HEAD: `4f3199aa3ae2b1d712bedc369c422f100ecaac53` — confirmed (`git rev-parse HEAD`). Working tree carries
  only I4-1h's own two uncommitted files (`CONTRIBUTION-LINEAGE.md` append, `PHASE34_I4_1H_…AUDIT.md`), matching
  the directive's own "I4-1h is ACCEPTED" statement — accepted in review, not yet committed as a git commit, which
  changes nothing about this audit's own starting state.

**Headline correction to the directive's own framing, stated up front because it changes the shape of several
answers below:** the directive characterizes c8's defect as the thing this whole track exists to prevent, and
asks whether solving it generically "breaks" c1/c2/c3/c4/c12. Direct code reading (§4/§12) finds the real
picture is **sharper and better than that framing assumes**: the existing `relationship_verifiers=
["same_proposition"]` joint-grounding check, already running on every one of these seven requirements, **already
catches and correctly demotes two of the other real cases (c2, c4) to `partially_filled`/`complete=False`** —
it just cannot see *within* one shared proposition's own multiple assertions, which is exactly what makes c8
uniquely dangerous: it is the one case where the misattribution hides **behind** a passing existing safety
check, not in the absence of one.

---

## 1. Locked principle — restated, not re-derived

`candidate_support` means "this local assertion is candidate support for THIS role in THIS instance," never
merely "this passage contains some result assertion." Confirmed as the correct framing by every real case
examined below: `local assertion attachment` (I4-1d, solved) and `role-instance relevance` (undesigned until
this audit) are genuinely different questions, and no provenance/admissibility machinery (I4-1e–g) can
substitute for the second.

---

## 2. The real c8 defect, reproduced from the recovered map

All five `relationship_to_bias_manifestation` instances bound to p41, read directly from `17_sufficiency_map.json`:

| Instance | `individual_difference_trait_or_construct` | `relationship_to_bias_manifestation` |
|---|---|---|
| `U23::313bd6d8a8225859` | p41 / `"attractiveness"` | p41 / *whole passage* |
| `U23::8c0c360f15addd4a` | p41 / `"trustworthiness"` | p41 / *whole passage* |
| `U23::8cf0ad0452a402ec` | p41 / `"anger"` | p41 / *whole passage* |
| `U23::ca4ec660cdb1a0de` | p41 / `"dominance"` | p41 / *whole passage* |
| `U23::0ae6b077fe124a0e` | p41 / `"threateningness"` | p41 / *whole passage* |

*whole passage* = `"Results: Across the ratings for all faces, Spearman correlations revealed greater
proportionality was associated with attrac- tiveness (ρ=0.292, P<0.001) and trustworthiness (ρ=0.193, P<0.001),
while lesser proportionality was associated with impressions of anger (ρ=0.132, P=0.001), dominance (ρ=0.259,
P<0.001), and threateningness (ρ=0.234, P<0.001)."` — byte-identical on all five bindings.

**`assertion_authority.classify_target_assertions` resolves p41 into exactly two non-overlapping assertions**
(reconfirmed here, not re-read from I4-1h's own text):

```
assertion 1  span=[43,200]   current_document / result / authoritative
  content: "greater proportionality was associated with attrac- tiveness (…) and trustworthiness (…)"
assertion 2  span=[208,372]  unresolved / result / candidate
  content: "with impressions of anger (…), dominance (…), and threateningness (…)"
```

**Which trait occurs in which assertion, tested directly (not assumed):** plain case-insensitive substring
containment correctly, uniquely assigns `trustworthiness→1`, `anger→2`, `dominance→2`, `threateningness→2` —
but finds **zero** matches for `attractiveness` anywhere, because the sealed text has a line-wrap hyphen
(`"attrac- tiveness"`). Applying `contract_directed/attribution.dehyphenate_for_matching` — the **exact, already-
shipped** helper `sufficiency_mapping._match_instrument` already uses for this identical class of artifact —
recovers `attractiveness→1` cleanly, with no other change. Final, verified split:

```
assertion 1 (current_document / authoritative): attractiveness, trustworthiness
assertion 2 (unresolved / candidate):            anger, dominance, threateningness
```

This is exactly the "expected real structure" the directive names, now empirically confirmed term-by-term
rather than asserted.

**Why the current deterministic binder cannot distinguish them, read directly from code
(`sufficiency_mapping.py:81-84`, `:316-377`):** `_match_achieved_outcome(text)` takes **only the unit's whole
passage** and returns that same whole passage back, unconditionally, whenever `attr.has_result_predicate(text)`
is true. `_bind_role_candidates` calls it once per role per fork, with **no per-instance parameter of any kind**
— its own signature is `(role_spec, units, model_client=None, child_id=None, requirement_id=None,
nomination_context=None, request_context=None, semantics_version)`, nothing that could carry "which trait is
this instance about." Five forks of the same instance, over the same `units_here`, necessarily call the same
function with the same arguments and get the same answer back five times. This is not a bug in control flow —
it is the literal absence of an input the function would need.

---

## 3. All seven real `achieved_outcome_predicate` roles, audited

Every requirement that declares an `achieved_outcome_predicate` role was read in full
(`role_specs`, `role_completion`, `instances`) from the real recovered map:

| Child/role | A. What does it bear on? | B. Target source | C. RoleSpec carries it? | D. Instance carries it after sibling binds? | E. Mapping order guarantees sibling-first? | F. Multiple sibling values legitimately constrain it? |
|---|---|---|---|---|---|---|
| c1 `neural_manifestation_evidence` | "an observed neural finding bearing on the bias" | EITHER sibling (`neural_measure_or_modality` OR `brain_region_or_network`, an `alternative_role_group` — not jointly required) | No | Yes, but single-instance (`multi_instance=False`) — no cross-instance disambiguation need even if read | Yes (role_specs dict order: identification roles declared before evidence role) | No — single instance, so at most one sibling value is ever live at once |
| c2 `behavioral_manifestation_evidence` | "an observed behavioral finding bearing on the bias" | sibling `behavior_or_behavioral_measure` (jointly **required**) | No | Yes — 3 real forked instances, each with a *different* sibling value | Yes | No — one sibling per instance, not several |
| c3 `attitude_manifestation_evidence` | "an observed attitude finding bearing on the bias" | **none** — this requirement has no identification role at all | n/a | n/a | n/a | n/a |
| c4 `region_bears_on_bias_evidence` | "evidence that the named region bears on the bias" | sibling `named_brain_region_or_network` (jointly required) | No | Yes — 2 real forked instances, different sibling values | Yes | No |
| c8 `relationship_to_bias_manifestation` | "evidence relating the trait/construct to the bias's manifestation" | sibling `individual_difference_trait_or_construct` (jointly required) | No | Yes — 11 real instances (two outer `request_context` partitions, inner model-nomination forks within each) | Yes | No |
| c10 `bias_evidence_in_population` | "evidence bearing on the bias/generalizability in that population" | sibling `named_culture_or_population` (jointly required) | No | Yes — 2 real instances, same sibling value (`"Hadza"`) from two different propositions | Yes | No |
| c12 `observed_effect_or_outcome` | "a definitive, non-speculative reported outcome" | siblings `intervention` **and** `target_manifestation` (both jointly required) | No | **No** — in every one of the 6 real instances, both siblings are `missing` | n/a (nothing to be sibling-first about — see §4) | Would be **yes in principle** (two siblings), but moot today since neither is ever filled |

**Column B's real shape across all seven roles is uniform except c1/c3:** five of seven depend on exactly one
sibling role's value from the **same instance**; one (c3) has no sibling at all (its target is simply "the
bias," unconditionally); one (c1) has an *alternative* pair rather than a required single sibling, but with no
multi-instance need to exploit it. None depend on a category term, and none depend on anything at the
requirement level that isn't already a role.

---

## 4. Sibling-role dependency — audited, not assumed, with the existing joint-grounding check as the critical variable

Read directly from `17_sufficiency_map.json`'s real instance data for every multi-instance case:

| Child | Sibling values across instances | Evidence binding across instances | `same_proposition` outcome (computed, not guessed) | Real instance `complete`/`state` |
|---|---|---|---|---|
| c2 | p35, p46, p47 (3 **different** propositions) | p4 (same, all 3) | `{p35}∩{p4}=∅`, `{p46}∩{p4}=∅`, `{p47}∩{p4}=∅` — **fails** on all 3 | `partially_filled`/`False` on all 3 — **already correctly demoted** |
| c4 | p11, p40 (2 **different** propositions) | p11 (same, both) | instance 1: `{p11}∩{p11}≠∅` — passes; instance 2: `{p40}∩{p11}=∅` — **fails** | instance 1 `filled`/`True`; instance 2 `partially_filled`/`False` — **already correctly demoted** |
| c8 | p20 (×4), p41 (×5) | **p20 instances: evidence role is `missing` — never bound at all.** p41 instances: evidence = p41 (same, all 5) | p20 instances: `own_evidence_roles` has only 1 filled role (the sibling) — `_joint_grounded` trivially `True` for an *unrelated* reason, same shape as c10/c12. p41 instances: `{p41}∩{p41}≠∅` — **passes on every one of the 5** | p20 instances: `partially_filled`/`False` — correctly incomplete, but because the evidence role was never found, **not** a same_proposition story. **Only the 5 p41 instances are `complete=True`/`state=filled` — not caught**, because the check only sees proposition identity, never that one proposition (p41) contains two different assertions |
| c10 | p29, p53 (2 different propositions, same value `"Hadza"`) | role never filled (see §13) | n/a — one role always missing, so `own_evidence_roles` has <2 entries and `_joint_grounded` is trivially `True` | `partially_filled` for an unrelated reason (the role is simply missing) |
| c12 | always `missing` on both siblings | p24/p30/p31 (3 different `request_context` partitions) | `own_evidence_roles` returns only `["observed_effect_or_outcome"]` (len 1) — trivially `True`, no joint-grounding question arises at all | `partially_filled` for the unrelated reason that 2 required roles are simply missing |

**This is the single most important empirical finding of this audit.** `relationship_verifiers=
["same_proposition"]` (`sufficiency_engine._verify_same_proposition`, `:747-757`) is a real, already-shipped,
already-running dependency check between exactly the sibling pairs the directive is asking about — but it
operates at **proposition granularity**, called **post-hoc** (`_joint_grounded`, invoked from
`recompute_instance` after both roles are already bound, never before/during either role's own candidate
search). It is why **c2 and c4 are already honest** — their instances are correctly marked incomplete, so a
consumer reading the aggregate instance state is not misled, even though the individual role bindings
themselves still carry generic/mismatched text. **c8 passes this exact same check cleanly on every one of its
5 p41-bound instances** (its other 4 non-empty instances, p20-bound, never reach the check at all — their
evidence role is simply `missing`, the same unrelated, correctly-honest shape as c10/c12, confirmed by direct
re-reading of the real map; see the §24-equivalent correction note at the end of this report for the exact
original misstatement this replaces), because `individual_difference_trait_or_construct` and `relationship_to_
bias_manifestation` really do share proposition p41 in every one of those 5 — the check was never designed to
see *inside* a shared proposition's own multiple assertions, and it structurally cannot. **c8 is not a case
where no safety mechanism exists; it is the one case where the existing mechanism's own blind spot is exactly
where the real error lives — narrower than first stated (5 instances, not 9), but real.**

---

## 5. General contract question — which schema form

**Recommendation: D, extended minimally — not a new top-level field.** The existing `relationship_verifiers`
list + `_VERIFIER_FUNCS` registry (`sufficiency_engine.py:786-789`) is already the schema's own answer to "does
evidence role E bear on sibling role R" — it is a declared, per-requirement, named-function dependency check,
reused unmodified by `_joint_grounded`/`recompute_instance` for exactly this question today, just scoped one
level too coarse (proposition, not local assertion) and applied one step too late (verification, not
candidate-search guidance). The natural, minimal, already-precedented extension is a **second verifier function
of the same shape** — e.g. `same_local_assertion` — registered in the same `_VERIFIER_FUNCS` dict, opted into
per-requirement by adding its name to an existing `relationship_verifiers` list (additive, backward-compatible,
exactly how every prior verifier addition in this codebase has shipped). This directly satisfies "prefer the
smallest explicit, question-agnostic representation" and "derive dependency from an existing structure already
present" simultaneously — it is the *same* structure, extended, not a new one. Options A/B/C (a new
`target_role_refs`/`evidence_for_roles` field, or dependency metadata on `RoleCompletionSpec`) were considered
and rejected as a **second** schema expressing the same relationship `relationship_verifiers` already declares
— they would duplicate, not extend, an existing contract-authoring surface. **No q_aib role name is encoded in
either `same_proposition` or the proposed `same_local_assertion` today, and none would be in the new one
either** — both operate purely on `role_bindings`/`roles` (a list of role *names* the requirement itself
declares), never a hardcoded trait/behavior/region vocabulary.

**A second, complementary mechanism is still required and is not the same thing (named here, not conflated):**
the verifier above would let `complete`/`state` correctly reflect the within-proposition mismatch (demoting
c8's 5 p41-bound instances to `partially_filled`, matching c2/c4's current honesty) — but it does **not**, by itself,
make `relationship_to_bias_manifestation`'s own `exact_text` correct for each instance. That requires a second,
genuinely new mechanism — **instance-local target-aware candidate search**, threaded into `_bind_role_
candidates`/`_fork_instances_over_role` itself — which is what §6–§14 below actually design.

---

## 6. Static terms vs. dynamic instance targets

Confirmed and sharpened from I4-1h: `requested_category_terms` is `[]` on all seven real
`achieved_outcome_predicate` roles, and for c8/c2/c4/c10 specifically **it could never be populated statically**
— the needed value is not authored wording at all, it is each instance's own already-bound sibling value,
known only at mapping time, differing per instance of the same role. **Decision: `requested_category_terms`
remains exactly what it is — authored, static, verbatim wording, scoped to disambiguating against a role's own
fixed authored target list (its only real activation case today, per I4-1e/I4-1g, remains hypothetical). A
separate, new mechanism supplies dynamic instance-local target values, sourced from an already-bound sibling
role's own `exact_text` on the SAME fork — never from this field.** No precedence conflict exists between them
because no real role needs both today; if a future role ever did, the dynamic sibling value should win for
disambiguation purposes (it is instance-specific and therefore strictly more relevant than a role-wide static
list), with the static list usable only as an additional, independent narrowing filter — but this is
speculative, not grounded in any real case, and is named only so the field's semantics are never silently
overloaded later.

---

## 7. Mapping order / dependency graph — no two-pass mapper needed, confirmed by direct code reading

Read `sufficiency_mapping.map_requirement` (`:519-604`) and `_fork_instances_over_role` (`:447-502`) directly,
line by line, not inferred:

- **Roles are bound in `role_specs.items()` order** — a plain Python dict, insertion-ordered, authored in
  `sufficiency_authoring.py`. In every one of the seven real roles audited in §3, the identification/sibling
  role is declared **before** the `achieved_outcome_predicate` role in the same `role_specs` dict.
- **Each instance's fork is threaded sequentially through this loop**: `forks` starts as `[instance]` and is
  reassigned after every role (`forks = _fork_instances_over_role(forks, role, spec, …)`), so by the time the
  evidence role's own turn comes, every fork in the list already carries the sibling role's finished binding in
  its own `role_bindings` dict.
- **`_fork_instances_over_role` never reads `forked["role_bindings"]` before calling `_bind_role_candidates`** —
  confirmed directly: the call is `_bind_role_candidates(spec, units_here, model_client=…, …)`, with no
  `forked`/`instance`/sibling argument anywhere in the ten keyword arguments it actually passes. The sibling
  value is sitting one line above in the very same loop body and is simply never read.
- **Answering the directive's specific questions:** roles are **not** bound independently (order is fixed and
  deterministic, by dict order, not by any runtime race); order **does** correspond to the real semantic
  dependency in every authored case examined; a dependent role **can** safely read an already-bound sibling
  today, with zero mapper restructuring, because the data is already in scope at the right time; **a two-pass
  instance mapper is not required** — this is a single-pass, correctly-ordered pipeline with a missing
  parameter, not a missing pass; **dependency cycles cannot occur** under the current authoring convention
  (a linear dict order has no back-edges, and nothing in `sufficiency_authoring.py` lets a role declare "depends
  on a role declared after it" even in principle); and when the sibling/target role is `missing` or forked into
  more than one candidate, this is exactly what §10 below specifies (fail closed to "no target available," never
  guess which fork's sibling to use for a role processed before forking happened — moot here regardless, since
  the sibling role is always processed first).
- **Recommended wiring, stated as a design fact, not implemented:** extend `_fork_instances_over_role`'s own
  signature with one new, optional, backward-compatible parameter (e.g. `sibling_context: dict | None = None`,
  the current fork's own `role_bindings` so far) — the exact additive-optional-parameter convention this same
  function and `map_requirement` have already used twice (`nomination_context`, Phase 19; `request_context`,
  Phase 19b). Every existing call site that omits it stays byte-identical, mirroring I4-1g's own
  backward-compatibility discipline exactly.

---

## 8. What counts as a target match — tested against all real roles, not generalized from c8 alone

| Role | Target values tested | Literal containment alone | With the existing `dehyphenate_for_matching` fallback | Verdict |
|---|---|---|---|---|
| c8 | attractiveness, trustworthiness, anger, dominance, threateningness | 4/5 unique (misses `attractiveness` — hyphen artifact) | **5/5 unique**, zero ambiguity | Clean |
| c2 | `p35`'s/`p46`'s/`p47`'s own nominated behavior phrases, searched within **each sibling's own source proposition** (not the generic p4 binding) | `p47`'s own passage ("…faster to share when playing with the good partner…") self-contains its nominated phrase **and** independently passes `attribution.has_result_predicate` — 1/3 clean, self-sufficient | n/a — not a hyphenation case | `p35`/`p46`'s own source passages do **not** themselves pass `has_result_predicate` (their own verbs, "yielded," "made … decisions," are outside the narrow result-predicate lexicon — the same disclosed I4-1d §6 gap) — **2/3 genuinely have no target-matched achieved-outcome evidence anywhere in scope today**, not a matching-mechanism failure |
| c4 | `named_brain_region_or_network`'s own values, `"the specific amygdala response"` (p11) and `"increased amygdala reactiv-ity"` (p40) | **Both** literally contain the bare word `"amygdala"` — and so does the *other* instance's own bound passage (p11 contains "amygdala" too) | n/a | A single common anatomical noun **over-matches**: literal containment alone cannot discriminate "the specific amygdala finding this instance's sibling actually named" from "any sentence mentioning the amygdala at all" |

**Decision: start with the weakest mechanism (literal/canonical containment, including the existing
dehyphenation fallback), but scope its search FIRST to the sibling's own source proposition/unit, never a free
search across the whole eligible pool.** This single scoping rule (§9) is what makes literal matching safe for
c4's generic-noun case (it correctly finds p40's own result sentence for instance 2, never reaching for p11's
unrelated "amygdala" mention) while still being strong enough for c8 (self-referential, same proposition) and
for c2's one real positive case (p47, also self-referential). c2's negative cases (p35/p46) are not a matching
failure at all — they are an honest "no achieved-outcome-shaped sentence exists in this sibling's own source
passage," which is the correct, disclosed outcome per §10 case C, not a reason to broaden the search or fall
back to a generic passage.

---

## 9. Target value identity vs. text

**Decision: consume the sibling role's own `exact_text` directly — no new schema primitive is required on the
target side.** This is a genuinely different conclusion from I4-1h's finding about the *evidence* side (where
`achieved_outcome_predicate`'s own whole-passage `exact_text` was found to be too coarse, P4 there). The
*sibling/identification* side is different: every `model_nomination_only` binding's `exact_text` is already, by
design, a **minimal, literal referent** — confirmed by reading the Phase 8/9 contribution-lineage history (the
nomination prompt was deliberately reformulated toward "minimal-referent extraction… explicit null-on-no-
referent," specifically to stop the model offering whole-clause, abstract-headed phrases) and confirmed again
empirically here: every one of c8's five trait values (`"attractiveness"`, `"trustworthiness"`, `"anger"`,
`"dominance"`, `"threateningness"`) and c4's/c2's own sibling values are already short, literal, directly
matchable noun phrases — none required any normalization beyond the one already-existing dehyphenation helper.
**If current `RoleBinding` lacked a clean machine-readable value separate from its evidence text, that would
block this design — it does not; `exact_text` on a sibling role already is that clean value.** No additional
schema primitive is needed before I4-2a for the target-representation question specifically (the separate,
already-identified `supporting_proposition_ids`/plural-id question from I4-1h §7/P3 remains outstanding on its
own track, unaffected by this finding).

---

## 10. Multiple target occurrences — design, no first-match behavior

- **A. Unique occurrence** (c8's 4/5 straightforward cases, c2's `p47`): the one containing assertion is the
  unique relevant candidate.
- **B. Multiple occurrences** (not observed in this corpus's real data, but must be designed for): every
  containing assertion is retained as a separate relevant candidate — never collapsed to "the first one."
- **C. Target appears nowhere** (c2's `p35`/`p46`, confirmed empirically in §8): **no target-matched candidate**
  for that instance. This is the correct, honest outcome — not a reason to fall back to a role-wide generic
  passage (today's actual behavior) and not a reason to widen the search beyond the sibling's own scoped
  source.
- **D. Multiple sibling values constraining one evidence role jointly:** **not required by any real role in
  this contract** — every real `achieved_outcome_predicate` role has exactly zero or one sibling identification
  role per instance (§3's column F), never several simultaneously. Not designed further here, per the
  directive's own "define only if the real contract requires this."
- **E. Target reachable only through pronoun/reference/paraphrase:** **fail closed.** No real case in this
  corpus exercises it (every sibling value tested was a literal noun phrase occurring verbatim, modulo the one
  disclosed hyphenation artifact). `contract_directed/links.py`'s existing designator/reference machinery
  (already wired as the `contract_directed_links` relationship verifier, confirmed unreachable in the live
  pipeline today — §4 of `sufficiency_engine.py:760-783`, "no real call site ever supplies
  `context["attachment_pieces"]`") is the only existing referent-resolution machinery in this codebase; it is
  not activated here, and no case in the real data requires it.

---

## 11. Real c8/p41 counterfactual — the ideal target-aware outcome, computed

| Instance target | Target source | Candidate assertion(s) | `assertion_relation` | `aggregation` | `assertion_kind` | Unique? | Relevant? |
|---|---|---|---|---|---|---|---|
| attractiveness | `individual_difference_trait_or_construct` exact_text, p41 | assertion 1 only | `current_document` | `non_synthetic_or_unspecified` | `result` | Yes | Yes |
| trustworthiness | same | assertion 1 only | `current_document` | `non_synthetic_or_unspecified` | `result` | Yes | Yes |
| anger | same | assertion 2 only | `unresolved` | `non_synthetic_or_unspecified` | `result` | Yes | Yes |
| dominance | same | assertion 2 only | `unresolved` | `non_synthetic_or_unspecified` | `result` | Yes | Yes |
| threateningness | same | assertion 2 only | `unresolved` | `non_synthetic_or_unspecified` | `result` | Yes | Yes |

**Relevance is evaluated independently of `support_policy`, per the directive's own instruction.** All five are
relevant (each has exactly one containing local assertion); whether `unresolved`/`non_synthetic` support is
*admissible* for this role is I4-2b's own, deliberately deferred, question (I4-1h §12/§13) — not re-opened here.
This single table, if wired, would also (as a side effect this audit notes but does not pursue) cause all five
instances to pass a future `same_local_assertion` verifier on the attractiveness/trustworthiness pair and the
anger/dominance/threateningness triple respectively, since each pair/triple would then share **both** proposition
*and* local-assertion identity with their own sibling.

---

## 12. Real non-c8 counterfactuals — does solving c8 generically break anything else?

| Role | Real sibling values | Target-aware outcome | vs. historical binding |
|---|---|---|---|
| c1 | single instance, no multi-instance need | unchanged — `neural_manifestation_evidence` stays uniquely relevant (p1, single assertion) | **No change** |
| c2, instance `p47` | "faster to share when playing with the good partner…" | **becomes uniquely relevant to `p47` itself** (self-contained, passes `has_result_predicate` on its own) | **Changes** — from the generic p4 passage to `p47`'s own specific passage; `same_proposition` would now also pass (both roles bound to `p47`) |
| c2, instances `p35`/`p46` | "decisions… share with bad partner…" / "share decisions between partners…" | **becomes target-unmatched** (§8/§10 case C) — no passage anywhere in scope both contains the sibling's phrase and passes `has_result_predicate` | **Changes** — from a false-positive-looking (but already `partially_filled`, per §4) generic p4 binding to an honest `missing`-with-no-candidate |
| c3 | no sibling at all | unchanged — nothing to target against; the role's existing single-instance, no-sibling behavior is untouched by this design | **No change** |
| c4, instance 1 (p11) | "the specific amygdala response" | unchanged — already self-referential, already correct | **No change** |
| c4, instance 2 (p40) | "increased amygdala reactiv-ity" | **becomes uniquely relevant to a sentence inside p40 itself** ("Laypersons… demonstrated increased amygdala reactivity," an `unresolved`/`result` assertion — corrected under I4-1j from this table's own original, imprecise "`attributed_external`"; its subject, "Laypersons with high levels of implicit bias…," is not a recognized owner phrase, so it resolves `unknown`/`unresolved`, distinct from p40's OTHER, genuinely `prior_work`/`attributed_external` sentence, "Recent work… has implicated certain neuroanatomic structures") — scoped-first search finds it before ever reaching p11 | **Changes** — from p11's unrelated passage to p40's own matching sentence; as a direct side effect, `same_proposition` would now also pass (both roles bound to p40), where today it correctly fails |
| c8 | 5 instances, 2 propositions | as computed in §11 | **Changes** — from one shared whole-passage binding to two distinct, correctly-split local-assertion bindings |
| c10 | "Hadza" (×2, different propositions) | no change possible — the one real candidate passage (p29/p53's own text) is excluded by the pre-existing `hedged` guard regardless of target-matching (§13) | **No change in outcome**, but the *reason* for `missing` becomes "found a target match, excluded by an orthogonal guard" rather than "no candidate was ever examined" |
| c12 | always missing, both siblings | no dynamic target exists to apply the mechanism to; all 3 real filled instances (p24/p30/p31) are already each from a distinct top-level `request_context`, so there is no cross-instance sharing to correct in the first place | **No change** |

**Answer to the directive's own central worry: solving c8 generically does not break anything — every other
real role either stays exactly as it is (c1, c3, c12, and c4-instance-1) or is *corrected* in the same direction
c8 is (c2, c4-instance-2), never regressed.** The one place behavior changes most visibly beyond c8 itself is
c2's two negative instances, which go from a misleadingly-specific-looking (but already-flagged-incomplete)
generic passage to an honestly empty one — a strictly more honest outcome, not a loss of information, since
`candidate_supports` (once wired) would still retain the rejected/non-matching passage as inspectable diagnostic
detail per §14 below.

---

## 13. c10 — genuinely absent evidence, confirmed, not an invisible candidate

Checked directly against the real sealed corpus and the real guard-computation code, not assumed:

- **p29/p53** (the propositions that bind `named_culture_or_population` = `"Hadza"`) **do** contain a result
  predicate (`attribution.has_result_predicate` → `True`) — "Hadza who regularly interact with outside cultural
  groups were **more likely to think**… were less moral…" — but `overview_evidence.has_hedge` also returns
  `True` on this exact text (the word **"likely"** matches the existing `_HEDGE` pattern), and
  `bias_evidence_in_population`'s own `disqualifying_guards=["hedged"]` therefore correctly excludes it under
  **today's existing, pre-I4-1 rules** — nothing to do with target relevance at all.
- **p21** (the only other culture/generalizability-themed proposition tagged `subquestion_id="c10"` in the
  whole 54-quote ledger) — `"results suggest the anomalous-is-bad stereotype is culturally shared…"` — fails
  the **prior** gate: `attribution.has_result_predicate` → `False` (`"suggest"` is not in that narrower lexicon;
  `assertion_authority` independently classifies it `unknown`/`interpretation`, `hedged=True`). It was never a
  candidate at all, target-matching or otherwise.
- **No new search was performed** — both checks run the existing production functions directly against the
  already-recorded sealed text.

**Conclusion: c10 genuinely lacks eligible result evidence under today's rules. No target-aware matching could
have exposed a currently-invisible candidate here, because the only two real candidates in scope were already
individually excluded for reasons orthogonal to target relevance** (the `hedged` guard; the result-predicate
lexicon gap). This is a second, independent, concrete illustration of I4-1h's own §16/P12 finding — the
`disqualifying_guards` silent-discard behavior means neither excluded candidate is visible anywhere in the real
map today, which is a genuine inspectability cost even though the *outcome* (`missing`) is correct here. Fixing
that discard-vs-retain asymmetry remains out of scope for this audit (§18), exactly as the directive specifies.

---

## 14. Interaction with all-support collection

**The hypothesized seven-step order (§14 of the directive) is confirmed correct by every real case examined,
with one clarification:** step 2 (existing guard eligibility) must run **before** step 4 (role-instance target
relevance) specifically because it is cheap, orthogonal, and — as §13 shows — can exclude a candidate for a
reason that has nothing to do with which instance it is being considered for; running target-matching first
would waste work discriminating between two instances' worth of a candidate that guard-eligibility was always
going to reject regardless.

**`candidate_supports` should contain only candidates that have already passed role-instance target relevance,
never every result assertion in an eligible passage.** A target-unmatched-but-otherwise-guard-eligible assertion
(c2's p35/p46 case, §12) does **not** belong in `candidate_supports` for `behavioral_manifestation_evidence` —
it genuinely does not bear on this role's instance, and including it would pollute the semantic support set
with assertions the design itself already knows are irrelevant, exactly the outcome §14 warns against. **It
belongs in a separate diagnostic/rejected-candidates record** (not designed here — out of this audit's scope —
but explicitly distinct from `candidate_supports`), preserving the inspectability principle (I4-1e §4) for a
*different reason* than `support_policy`-excluded evidence: a `support_policy`-excluded candidate is relevant
but not admissible; a target-unmatched candidate is not even relevant, and conflating the two would blur a
distinction the directive's own locked principle (§1) depends on.

---

## 15. `candidate_support.proposition_id` schema correction — migration specifics

Carrying I4-1h's P3 decision (`supporting_proposition_ids: [...]`, plural) forward with the specific migration
questions this audit was asked to resolve:

- **Replace the singular field before it is ever consumed.** `new_candidate_support` (I4-1g) is, as of this
  audit, still completely unwired — zero production call sites construct one from real data. This is
  confirmed the cheapest possible moment to correct it: no caller exists yet to migrate.
- **Retain a singular, optional compatibility projection — never require one.** A legacy consumer (if any ever
  exists before full `candidate_supports` adoption) can read `supporting_proposition_ids[0]` or an explicit
  separate `primary_proposition_id` convenience key; the canonical field itself must never collapse back to
  singular.
- **Require a non-empty plural list.** An empty `supporting_proposition_ids` is not meaningfully different from
  a missing proposition identity and should be rejected at construction, mirroring `new_support_policy`'s own
  "reject an empty set as nonsensical" discipline (I4-1g §3).
- **Canonical order: ledger/discovery order, not an artificially canonicalized sort.** Unlike `new_support_
  policy`'s own two *set*-valued fields (where sorting is correct because membership, not order, is the
  semantic content), `supporting_proposition_ids` for a candidate support record is closer to
  `model_mapping`'s own existing `supporting_proposition_ids` provenance field (`17_sufficiency_map.json`'s real
  `c8` bindings: `["p20", "p9"]`, confirmed order-preserving, not sorted) — the real precedent already in
  production data preserves discovery order, and the new schema field should match that precedent exactly
  rather than introduce a second, differently-ordered convention for structurally the same information.
- **How the existing `model_mapping` provenance maps in:** directly — `provenance.supporting_proposition_ids`
  already has the right shape and order; the correction is only to also expose it (or its equivalent) as the
  CANDIDATE'S own primary identity field, not bury it one level deeper inside `provenance` while a separate,
  narrower `proposition_id` sits beside it pretending to be authoritative.

---

## 16. `exact_text` + source-context sufficiency

**`supporting_proposition_ids` + `assertion_span`/`content_span` is sufficient to recover the full sealed
passage deterministically, but only if the span is interpreted against the specific proposition it names, not
against text in isolation.** Confirmed by direct reconstruction: given `proposition_id=p41` and `content_span=
[43,200]`, the full sealed passage is recoverable exactly as `verified_propositions[p41].quote[43:200]`,
byte-identical to assertion 1's content above — no additional field is needed, because the proposition ledger
(already the system of record for the sealed quote) is always addressable by `proposition_id` alone. **One
precise, minimal addition is still required: which `proposition_id`, among a plural `supporting_proposition_
ids` list, the span's offsets are relative to** — for a candidate support spanning more than one
proposition's worth of support (not observed in this corpus, but not ruled out structurally), an unqualified
`[43,200]` is ambiguous without naming its own anchor proposition. **Minimal fix, not a new field: when
`assertion_span`/`content_span` is present, it is always relative to the single proposition most directly
responsible for the matched local assertion — recorded as its own field, e.g. `span_proposition_id` — distinct
from the full `supporting_proposition_ids` list, which remains the honest plural provenance.** Restoring
whole-passage `exact_text` "for convenience" is explicitly rejected, per I4-1h's own P4 and reconfirmed here —
the local span plus this one small anchor field is sufficient and strictly more precise.

---

## 17. p41 / `achieved_outcome_span`'s proper role — the deterministic join, specified

Locking I4-1h's own correction (P7 there): top-level assertion identity comes from `assertion_authority`'s
resolved spans, never from `achieved_outcome_span`'s independently-duplicated boundary grammar. The proper
division of labor, specified precisely:

- **`achieved_outcome_span.find_achieved_outcome_matches`'s job:** *localize* a result-predicate hit and its
  tightest `content_span` within a passage — this is genuinely useful, narrower-grained information
  `assertion_authority` does not itself compute (it only knows assertion-level boundaries, not
  predicate-level ones).
- **`assertion_authority.classify_target_assertions`'s job:** determine the *containing assertion* for any
  given span — ownership, kind, authority, aggregation — exactly what it already does.
- **The deterministic join, proposed:**

  ```
  locate_containing_assertion(text, predicate_or_content_span) -> assertion | FAIL
  ```

  implemented as a thin wrapper over the EXISTING `classify_target_assertions(text, target_start=span[0],
  target_end=span[1])` call (no new parsing logic — this is literally the function signature I4-1h's own §6
  already used to re-derive p41's two assertions, just invoked with a narrower predicate-level span instead of
  the whole-passage span `[0, len(text))`). **Fail-closed rule, exactly as the directive specifies:** if the
  resulting `target_scope` is `no_governing_assertion` (zero containing assertions) or `multi_assertion` (more
  than one — I4-1h's §6 already confirmed p41's own two assertions never jointly cover one predicate span, so
  this case did not arise for p41 itself, but must still be checked generically), the join fails closed and the
  diagnostic detail (which spans, which assertions, why none/multiple matched) is retained, never silently
  resolved by picking one. **This exact join, applied to p41's own `achieved_outcome_span` match for assertion
  1's predicate (`"revealed"`, at content_span start 43) and assertion 2's predicate (the second `"associated"`,
  at content_span start ~208), each independently resolves to `target_scope=within_assertion`, one governing
  assertion each — confirmed directly, not assumed** (re-running `classify_target_assertions` with
  `target_start/target_end` narrowed to each `achieved_outcome_span` match's own `content_span`, rather than the
  whole passage, returns exactly one assertion for each of the three raw predicate hits `achieved_outcome_span`
  found — the SAME two assertions as §2's whole-passage-scoped call, with `revealed` and the first `associated`
  both correctly resolving into assertion 1 despite `achieved_outcome_span`'s own, separate "ambiguous_with"
  flag between them). **This reconfirms, with one more independent check, that p41's false ambiguity lives
  entirely inside `achieved_outcome_span`'s own narrower layer and never reaches `assertion_authority`'s spans
  at all** — the proposed join does not merely avoid reintroducing it; it is structurally incapable of seeing it,
  because it only ever asks `assertion_authority` the question `assertion_authority` is actually built to answer.

---

## 18. `disqualifying_guards` — deferred, ordering recorded only

Not solved here, per the directive. **Ordering for the eventual pipeline: instance-local target relevance must
run AFTER the existing `disqualifying_guards` check, never before** — confirmed necessary by §13's own c10
finding (a target-matched-but-guard-excluded candidate should still end up excluded; running target-relevance
first would not change that outcome, but guard-filtering first avoids wasted per-instance work on a candidate
that was always going to be rejected regardless of which instance is asking). This matches the directive's own
hypothesized order (step 2 before step 4) exactly, now confirmed against a real case rather than left abstract.

---

## 19. `default_support_policy` — deferred, no dependency found

Not solved here, per the directive. No direct dependency was found between instance-local relevance and
`support_policy`'s own admissibility semantics (I4-1h §12/§13) — they are evaluated on genuinely different
questions (does this assertion bear on this role-instance at all, vs. is this kind/relation/aggregation of
support admissible for this requirement) and can be implemented and tested independently, in either order,
without one blocking the other's own correctness. The only interaction worth naming for I4-2b's own future
design: once both exist, `candidate_supports[role]` for one instance should contain only target-relevant
candidates (§14), and `support_policy` admissibility is evaluated **within** that already-filtered set, never
across the unfiltered one.

---

## 20. Generic stress tests — domain-neutral design, not benchmark-specific

No q_aib vocabulary in any of the following; each mirrors p41's own real two-assertion split structurally:

- **Clinical.** Instance target = `depression`. Passage: *"Scores on the depression subscale decreased
  significantly (p<.01), while anxiety subscale scores showed no significant change."* Two local assertions
  (contrast-split at `, while`); target `depression` occurs only in assertion 1 → uniquely relevant to assertion
  1; a sibling instance targeting `anxiety` would uniquely resolve to assertion 2. Neither instance's evidence
  should ever be the other's.
- **Neuroscience.** Instance target = `amygdala`. Passage: *"Amygdala activation predicted threat sensitivity,
  whereas hippocampal volume predicted memory performance."* Same shape: `amygdala`→assertion 1 only,
  `hippocampal`→assertion 2 only — the generic-noun over-matching risk named in §8 does not arise here because
  `amygdala` and `hippocampal` are each still unique within this one passage (the real c4 case's over-matching
  risk was specifically *cross-passage*, not within one passage — worth distinguishing for a future design: the
  scoping-to-sibling's-own-source rule from §8 handles the cross-passage case; a same-passage repeated-generic-
  noun case, not observed in the real corpus, would still need the "preserve as multiple relevant candidates,
  never pick one" rule from §10B).
- **Built environment.** Instance target = `floor area`. Passage: *"Floor area per occupant increased from 2.1
  to 2.8 m², while ceiling height remained unchanged across all three renovation phases."* `floor area`→
  assertion 1, `ceiling height`→assertion 2.
- **Language learning.** Instance target = `vocabulary`. Passage: *"Vocabulary gains were significant (d=0.6),
  though grammatical accuracy showed no reliable improvement."* `vocabulary`→assertion 1, `grammatical
  accuracy`→assertion 2.

In every domain, the evidence role correctly attaches only to the assertion(s) bearing on the current instance's
own target, using the same mechanism validated against the real corpus in §8/§11 — literal/canonical containment
scoped to the sibling's own source, never a free search, never a first-match fallback.

---

## 21. Versioning

**No version bump in this audit; none is required by anything designed here, by the same non-load-bearing-
substrate logic I4-1h applied to I4-1f/g.** A future `same_local_assertion` relationship verifier can ship,
registered in `_VERIFIER_FUNCS`, completely unconsumed (no real requirement's `relationship_verifiers` list
edited to include it) — additive, inert, provably unreachable by the same kind of static guard I4-1f/g's own
reports already use. **The moment any real requirement's `relationship_verifiers` list is actually edited to
add it, that is a real semantic boundary** (c8's own `complete`/`state` would change for real, from `True` to
`False`, on its 5 p41-bound instances) and needs `sufficiency-semantics-v5` (or whatever version I4-2 ultimately claims
it under) exactly as I4-1h's own P15/§21 already specifies for any `state`-changing wiring. The larger
instance-local target-aware candidate search mechanism this audit designs is, likewise, purely additive until
it is actually threaded into `_bind_role_candidates`'s own decision — a pure, unwired, schema-only increment
implementing the join (§17) and the sibling-context-threading parameter (§7) can ship with zero version
consequence, exactly mirroring I4-1g's own precedent.

---

## 22. Next-increment recommendation

**B — one tiny, pure, schema/primitive increment is needed first, not A, and not C.**

- **Not A.** Existing structures do **not** already provide instance-local target identity usable by
  `achieved_outcome_predicate`'s own candidate search — confirmed empirically and at the code level throughout
  §2–§9; `_bind_role_candidates` has no parameter that could carry it, and `requested_category_terms` cannot be
  statically authored to supply it for the one real role family that needs it (c8/c2/c4/c10, §6).
- **Not C.** No larger mapping-architecture revision is required — §7 confirms, by direct code reading, that
  role-binding order already matches the real semantic dependency in every authored case, forking already
  threads each instance's accumulated bindings correctly, and no cycle can occur under the current
  authoring convention. This is a parameter-threading gap, not an architectural one.
- **B, scoped precisely:** a new **I4-1j**, pure and unwired like I4-1d/f/g, delivering exactly three things,
  none of which touches production behavior: (1) `locate_containing_assertion` (§17), the deterministic
  `achieved_outcome_span` → `assertion_authority` join, fail-closed on 0/>1 containing assertions; (2) a pure
  `same_local_assertion(role_bindings, roles)` relationship-verifier function, the same shape as the existing
  `_VERIFIER_FUNCS` entries, registered but not added to any real requirement's `relationship_verifiers` list;
  and (3) the scoped target-matching primitive validated in §8 (literal/canonical containment, with the existing
  `dehyphenate_for_matching` fallback, searched first against the sibling's own source proposition before any
  wider pool) as a pure function taking `(sibling_exact_text, candidate_units) -> matched_span | None`. All
  three are directly testable against the real recovered 54-quote/v4-map baseline (frozen batteries plus a
  read-only re-evaluation against the real c8/c2/c4/c10 cases documented in §11–§13), exactly the I4-1d/f/g
  convention. I4-2a (I4-1h's own split) should consume I4-1j's primitives when it wires `candidate_supports`
  collection, rather than reinventing target-scoping ad hoc inside that larger increment.

---

## 23. Required decisions

**T1.** Role-instance relevance = "this local assertion is the specific assertion, within its own proposition's
passage, that a specific role's own instance-local target (the value already bound to a jointly-required
sibling role on the SAME fork) actually names or describes" — strictly finer than proposition identity, and
independent of admissibility/provenance.

**T2.** Per role (§3): c1 — either-of-two sibling, single instance, not exercised; c2 — sibling `behavior_or_
behavioral_measure`; c3 — no sibling, target is simply "the bias"; c4 — sibling `named_brain_region_or_network`;
c8 — sibling `individual_difference_trait_or_construct`; c10 — sibling `named_culture_or_population`; c12 —
siblings `intervention`+`target_manifestation`, never actually filled in this run.

**T3.** c2, c4, c8, and (structurally, though unexercised today) c10 and c12 require a dynamic, instance-local
sibling value. c1 and c3 do not (no real multi-instance disambiguation need / no sibling at all).

**T4.** Mapping order already guarantees sibling-before-evidence in every real authored case (role_specs dict
order); no two-pass mapper is needed; a safe wiring is one new optional parameter threaded through the existing
single pass (§7).

**T5.** Consume the sibling role's own `exact_text` directly as the target value — already a clean, minimal,
literal referent by the Phase 8/9 nomination-prompt design; no new schema primitive needed on the target side
(§9).

**T6.** Literal/canonical substring containment (reusing the existing `dehyphenate_for_matching` fallback),
scoped first to the sibling's own source proposition/unit before any wider search — validated against all real
cases in §8, including the one real over-matching risk (c4's generic "amygdala") and the one real negative
result (c2's p35/p46).

**T7.** Unique → unique relevance; multiple → preserve all, never pick one; none → honest no-target-match,
never fall back to a generic passage (§10, §12).

**T8.** p41's five instances split cleanly: attractiveness/trustworthiness → assertion 1 (current_document/
authoritative); anger/dominance/threateningness → assertion 2 (unresolved/candidate) (§11).

**T9.** c1/c3/c12 unaffected; c4-instance-1 unaffected (already correct); c2-p47 and c4-instance-2 are corrected
(from a shared/mismatched generic passage to their own self-sufficient passage); c2-p35/p46 become honestly
target-unmatched rather than falsely generic; c10 and c8's own 4 p20-bound instances are unaffected (already,
correctly, `missing`) (§12).

**T10.** `candidate_supports[role]` for an instance contains only target-relevant candidates; a guard-eligible
but target-unmatched assertion belongs in a separate diagnostic/rejected-candidates record, never in
`candidate_supports` itself (§14).

**T11.** Replace the singular `proposition_id` with a required, non-empty, discovery-ordered
`supporting_proposition_ids` list before any production wiring — cheapest now, while fully unconsumed (§15).

**T12.** `supporting_proposition_ids` + a span qualified by its own anchor proposition id (`span_proposition_
id`, a small addition, not a new whole-passage field) is sufficient to deterministically relocate the full
sealed passage (§16).

**T13.** `locate_containing_assertion(text, span) -> assertion | FAIL` — a thin wrapper over the already-existing
`assertion_authority.classify_target_assertions`, fail-closed on `no_governing_assertion`/`multi_assertion`,
confirmed to correctly resolve all three of `achieved_outcome_span`'s own raw p41 predicate hits into the right
two assertions, structurally incapable of reintroducing `achieved_outcome_span`'s own narrower ambiguity (§17).

**T14.** No version bump for any pure/unwired schema addition (a new, unconsumed `_VERIFIER_FUNCS` entry; the
join primitive; the scoped-matching primitive). A version bump is required the moment any real requirement's
`relationship_verifiers` list is edited to consume the new verifier, or the candidate-search mechanism is wired
into `_bind_role_candidates` for real (§21).

**T15.** **B** — one small, pure I4-1j (the join, the verifier function, the scoped-matching primitive), before
I4-2a consumes it. Not A (confirmed no existing structure already supplies this); not C (confirmed no larger
architecture change is needed) (§22).

---

## Correction (made under I4-1j, 2026-10-08) — §4/§5 overstated c8's affected-instance count

**Original conflicting statements.** §4's table and surrounding prose stated that `same_proposition` "passes
on every one of the 9 non-empty instances" of c8 and that "all 9 are `complete=True`/`state=filled` — not
caught." §5 repeated "demoting c8's 9 instances to `partially_filled`." Meanwhile T9 (§23) stated, correctly
but without flagging the contradiction, that "c8's own 4 p20-bound instances are unaffected (already,
correctly, `missing`)."

**Source of truth.** `17_sufficiency_map.json`'s real `c8` requirement, re-read directly and exhaustively
(every one of its 11 instances, not a sample): the 4 `U6::*` (p20-bound) instances have
`relationship_to_bias_manifestation.state == "missing"` — the evidence role was **never bound at all** for
them, not bound-and-matching-the-wrong-assertion. Only the 5 `U23::*` (p41-bound) instances have both roles
`filled`, both sharing proposition p41, both therefore passing `same_proposition` and landing on
`complete=True`/`state=filled`.

**Corrected fact.** `same_proposition` passes, and is blind to the within-proposition split, on **5 of c8's 11
instances (the p41-bound ones), not 9.** The 4 p20-bound instances are correctly `partially_filled` for an
entirely unrelated reason — their evidence role was simply never found — the same honest-absence shape as
c10's and c12's own unfilled roles, not a same_proposition story at all. §4, §5, and §21/§23's own prose above
(and the `/tmp` scratch computation this report was originally drafted from, which conflated "has a non-null
sibling value" with "both required roles are filled" when building the `own_evidence_roles`-eligible instance
set) have been corrected in place to say "5 p41-bound instances," matching T9 exactly.

**Does any T1–T15 decision change?** No. Every decision in §23 was already keyed to the real per-case
behavior (§11's own table already correctly used "5 instances"; T8/T9 were already correct), not to the
now-corrected "9" headline count. The headline count was a prose overstatement of how many instances the blind
spot affects, not a wrong conclusion about what to build — the design (§5's `same_local_assertion` extension,
§7's parameter-threading, §17's join) is unaffected. The one place the correction has real teeth is scale:
the practical blast radius of c8's false-positive `complete=True` is **5 instances**, not 9 — smaller than
originally reported, which is a reason for less urgency, not a reason to revisit the recommendation.

---

## Second correction (made under I4-1j, 2026-10-08) — §12 mislabeled p40's own relevant sentence

**Found while building I4-1j's real c4 battery**, not flagged by the directive but corrected for the same
reason as the first: building a real test battery on a misdescribed fact would compound the error, not just
repeat it.

**Original statement.** §12's non-c8 counterfactual table described c4 instance 2's target-aware correction
as resolving to "an `attributed_external`/`result` assertion already confirmed present in p40 by I4-1h's own
sweep."

**Source of truth.** Running `assertion_authority.classify_target_assertions` directly against p40's own real
sealed text (not re-read from a prior report's prose) shows p40 contains **three** assertions: (1) "certain
neuroanatomic structures when viewing others with facial anomalies" — `prior_work`/`attributed_external`,
subject "Recent work…has implicated"; (2) "increased amygdala reactiv- ity" — `unknown`/`unresolved`, subject
"Laypersons with high levels of implicit bias…," which is **not** a recognized owner phrase; (3) "eye-tracking
to characterize visual attention…" — `prior_work`/`attributed_external`/`method_or_description`.

**Corrected fact.** The sentence that actually becomes the relevant, scoped-to-p40 evidence for c4's instance
2 — "Laypersons… demonstrated increased amygdala reactivity" — is `unresolved`, not `attributed_external`.
§12's table has been corrected in place.

**Does this change any decision?** No. Which sentence is target-relevant, and that scoping-to-p40 finds it
before ever reaching p11's unrelated passage, are both unaffected — only the specific `assertion_relation`
label attached to it in the prose was wrong. (Whether `unresolved`/`result` support would be *admissible* for
this role under a future `support_policy` is, as throughout this track, I4-2b's own deferred question, not
reopened here.)

---

## 24. Deliverable

This file: `experiments/ask_cli_revised/PHASE34_I4_1I_INSTANCE_TARGET_RELEVANCE_AUDIT.md`. Planning/read-only
audit only. A `CONTRIBUTION-LINEAGE.md` append follows. No production `.py` file was modified; no `RoleSpec`,
mapping, version constant, frozen battery, or pin was touched. The scratch script that produced §2/§4/§8/§11–
§13/§17's empirical numbers lives outside the repository and was never committed or imported, per the directive's
own "prefer scratch" instruction and I4-1h's own established convention.

---

## STOP

STOP after this audit, as instructed. Not implemented: I4-1j, I4-2a, I4-2b. No version bump. No wiring of
`candidate_supports`, `support_policy`, a new relationship verifier, or sibling-context threading into any
production path. No model, network, or live end-to-end run occurred anywhere in this audit.
