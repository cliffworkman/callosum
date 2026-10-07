# PHASE 34 / I4-1e — evidence provenance, directness, and requirement admissibility: design audit

**Status: PLANNING / DESIGN ONLY — revision 2.** Revision 1 (below, superseded in place) was accepted in broad
form; four aspects of its object model are revised here per explicit steering before any further work. No
production code, classifier edit, mapping edit, `RoleSpec` field addition, version bump, I4-1f, I4-2, model call,
live search, or live end-to-end run occurred while producing either revision. Starting HEAD for revision 1:
`321a5d42c8f58c3b21d334f198f4c72dac6f212f`. This revision was made against the same clean worktree state (the
revision-1 write and its `CONTRIBUTION-LINEAGE.md` append were the only prior changes; nothing else moved). Branch
`experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, worktree
`.claude/worktrees/ask-060-hier11-recpm3-citefix-20260929T212442Z`. This file and one further
`CONTRIBUTION-LINEAGE.md` append are the only writes made for this revision.

I4-1 through I4-1d remain treated as implemented, tested, pure, unwired experimental machinery, unchanged by
either revision of this audit.

---

## 0. Correction ledger — what changed from revision 1, and why

**Locked by this steering round, unchanged from revision 1:** indirect evidence is legitimate evidence; the
defect is misattribution, not indirectness; provenance/directness determines HOW evidence counts; requirement
semantics determine WHETHER that support is sufficient; directness is not evidence quality; satisfaction state and
evidence provenance remain orthogonal; review/synthetic evidence may fully satisfy a general literature question;
source-specific questions may require direct current-document evidence; no document-genre inference; Simple Ask
and hierarchical Ask share one evidence-semantic layer; no global direct>indirect>synthetic ranking; no new
satisfaction state merely for indirectness.

**Four corrections, each a real design improvement found by stress-testing revision 1 against concrete
counter-examples, not a cosmetic relabeling:**

1. **Revision 1 added a fourth `assertion_source` value, `synthesis`.** This conflated "who owns/reports this
   assertion" with "is this assertion aggregating a literature." §1 below shows four concrete sentences
   (own-voice synthesis; attributed synthesis; own-voice *computed* synthesis, e.g. a pooled meta-analytic effect;
   attributed non-synthesis) that a single four-valued enum cannot distinguish. `assertion_source` reverts to
   exactly its I4-1 three values; aggregation becomes a second, orthogonal axis.
2. **Revision 1 collapsed provenance and kind into one mutually-exclusive `support_mode` label.** This loses
   exactly the information the correction in (1) was trying to preserve — a meta-analysis's own pooled result is
   simultaneously "this document's own finding" and "synthetic," which one flat enum cell cannot hold. The
   semantic representation becomes an orthogonal triple (`assertion_relation`, `aggregation`, `assertion_kind`);
   the old six-value label survives only as a downstream, lossy, display-only convenience derived from the triple.
3. **Revision 1's default admissibility policy, applied literally to the new triple, would have excluded the
   exact review sentence that motivated the whole design** ("Across multiple studies, regions A, B, and C are
   implicated in X" resolves to `assertion_relation=unresolved` under D-A/D-D, since the sentence has no owner
   phrase at all — only the *new* `aggregation` cue distinguishes it from an ordinary bare unmarked result). §8
   below replaces the flat default with a predicate that reads relation and aggregation jointly, admitting
   `unresolved` only when an aggregation cue is present, closing this self-contradiction without reopening D-A/D-D
   for the ordinary bare-unmarked case (p11, p30 stay excluded, unchanged).
4. **Revision 1's multi-source handling ("first admissible binding wins; the rest ride in `supporting_bindings`")
   still let list order decide which candidate is primary.** §6 below removes that dependency: every relevant
   candidate is now collected and classified before satisfaction is evaluated, satisfaction reads the whole
   admissible set, and a primary/representative candidate (if one is still wanted for legacy-shaped output) is
   chosen only afterward, for display, from among the candidates satisfaction already deemed valid.

A fifth, smaller correction folded in while working through the above: revision 1's `target_wording_span` field is
withdrawn in favor of reusing the existing `requested_category_terms` field for `achieved_outcome_predicate` roles
(§10) — the steering round's own instruction to "avoid duplicating the same semantic target in multiple fields"
applies directly once the existing field's shape is reread.

---

## 1. Revised object model: four concrete contrasts (steering §1)

| Sentence | Who is credited (unchanged `assertion_source`/renamed `assertion_relation`) | Is it aggregating a literature (`aggregation`) |
|---|---|---|
| A. "Across studies, X has been associated with Y." (a review's own sentence, no first-person marker) | no owner phrase at all → `unresolved` | yes — `literature_synthesis` |
| B. "A recent review found that X is associated with Y." (an empirical paper attributing a synthesis to prior work) | a leading external-source noun phrase, owner = "a recent review" → `attributed_external` *(see the lexicon note below)* | yes — the owner noun itself is synthesis-headed → `literature_synthesis` |
| C. "We found a pooled effect of X on Y." (a meta-analysis's own computed result) | owner = "We" → `current_document` | yes — the object content is synthesis-shaped ("pooled effect") → `literature_synthesis` |
| D. "Previous studies found X." (an ordinary prior-work citation, no aggregation signal) | owner = "previous studies" → `attributed_external` | no → `non_synthetic_or_unspecified` |

**A, B, C, and D are four distinct cells of a 3×2 grid (`assertion_relation` × `aggregation`), never four values of
one enum.** This is the structural reason revision 1's `synthesis` provenance value was wrong: C needs
`current_document` AND synthesis simultaneously, which a value set of `{this_study, prior_work, synthesis,
unknown}` cannot express without either losing "We found" ownership or losing "pooled effect" aggregation.

**A concrete lexicon finding, checked against the real I4-1 grammar, not assumed:** case B's owner phrase, "a
recent review," is **not** recognized as prior-work ownership by the classifier as it stands today. I4-1's
prior-ownership rule matches a leading external-source noun phrase only when the head noun is drawn from
`study|studies|work|reports|findings|…` (I4-1 report §5) — "review" is not in that closed set. As built today,
case B's owner resolves to `unknown`/`unresolved`, not `attributed_external`. This is a real, narrow, disclosed
gap for a future increment to close with exactly the minimal-diff precedent I4-1c already set when it added
`provide/provided/provides` to the result-verb lexicon for one directive-required case: add `review`, `systematic
review`, and `meta-analysis`/`meta-analytic review` to the prior-source head-noun set. Not performed in this
audit (no classifier edit); named as a bounded, specific scope item for I4-1f (§12).

---

## 2. The revised, orthogonal triple (replaces revision 1's `support_mode`)

```
assertion_relation  ∈ {current_document, attributed_external, unresolved}
aggregation         ∈ {literature_synthesis, non_synthetic_or_unspecified}
assertion_kind      ∈ {result, method_or_description, aim_or_hypothesis, interpretation, unknown}   (unchanged)
```

**`assertion_relation` is a pure, lossless, 1:1 rename-view of I4-1's own `assertion_source` — never a new
classification:**

| `assertion_source` (I4-1, unchanged, internal) | `assertion_relation` (this design, production-facing) |
|---|---|
| `this_study` | `current_document` |
| `prior_work` | `attributed_external` |
| `unknown` | `unresolved` |

The rename exists for exactly the reason revision 1's own §18 terminology section already argued for
`finding_authority`: the pure classifier's internal vocabulary and its 300+ frozen, hash-pinned cases stay
untouched forever; a production-facing layer gets its own clearly-named fields that read naturally beside the new
`aggregation` axis, translated at one small, explicit boundary function rather than by editing
`assertion_authority.py`.

**`aggregation` is a genuinely new classifier output**, computed from a small, closed surface-cue set, independent
of ownership:
- an adverbial/framing cue on the clause ("across studies", "across multiple studies", "the literature
  indicates/suggests", "meta-analytic evidence shows") — this is what makes case A (§1) representable without an
  owner at all;
- a synthesis-headed owner noun phrase ("a review", "a systematic review", "a meta-analysis") — case B, once the
  lexicon gap above is closed;
- a synthesis-shaped object/content noun governing a `current_document`-owned result ("pooled effect",
  "meta-analytic estimate", "aggregate effect", "combined effect size") — case C.

No cue present → `non_synthetic_or_unspecified`, the conservative default, exactly mirroring D-A/D-D's own
conservatism: absence of a recognized cue is never promoted to a claim either way.

**A convenience, downstream-only label may still be derived, never destructively, for rendering shorthand** — a
pure function of the triple, documented as display sugar and never consulted by admissibility logic (§7):

| `assertion_relation` | `aggregation` | `assertion_kind=result` label |
|---|---|---|
| `current_document` | `non_synthetic_or_unspecified` | `direct_empirical` |
| `current_document` | `literature_synthesis` | `direct_synthetic` |
| `attributed_external` | `non_synthetic_or_unspecified` | `attributed_indirect` |
| `attributed_external` | `literature_synthesis` | `attributed_synthetic` |
| `unresolved` | `non_synthetic_or_unspecified` | `unresolved` |
| `unresolved` | `literature_synthesis` | `unresolved_synthetic` |

`method_or_description` kind labels simply `descriptive`; `interpretation` labels `interpretive`; `aim_or_
hypothesis` derives no label at all (unchanged reasoning from revision 1: a stated intention is not itself offered
as an outcome). The six-cell result table above is strictly more information than revision 1's flat six-value
enum (it recovers `direct_synthetic`/`attributed_synthetic`/`unresolved_synthetic`, all previously unrepresentable),
and nothing downstream may read only the label when the triple is available — the label exists for a quick
display chip, not as the semantic record.

---

## 3. Review/synthesis cues answer one question only (steering §3)

The aggregation cue answers exactly: *"is this assertion explicitly aggregating/synthesizing a literature?"* —
never *"who owns this assertion"* (answered separately by `assertion_relation`, §2) and never *"what kind of
document is this"* (not answered at all, deliberately — see §13, unchanged from revision 1: no document-genre
inference). Ownership, aggregation, and kind are computed by three independent passes over the same sentence and
combined only at the point of use.

**The rendering caveat the steering round raised is a direct, mechanical consequence of keeping relation and
aggregation separate, not an extra rule that needs separate enforcement:** if Paper A (in the library) says "A
systematic review found X" and that review itself is not in the library, the bound evidence's `assertion_relation`
is `attributed_external` (Paper A is attributing the claim to an external review) and its `aggregation` is
`literature_synthesis`. A correct render reads the relation first — *"Paper A reports that a review found X"* —
never *"A review in the library found X,"* because nothing in this design ever asserts that the cited review is
itself a library member; `aggregation` says what kind of claim is being attributed, and `assertion_relation` says
who is making the attribution, and neither field ever claims the attributed source is independently present. This
distinction is exactly why ownership and aggregation must stay orthogonal fields rather than being fused into a
single "this is synthetic evidence" label that would blur who is speaking.

**Do not require the cited review to be present in the library, and do not infer document genre** — both already
locked, both already satisfied by construction: the cue lives on the citing sentence's own surface text, read
once, with no lookup against the library's holdings and no `papers.document_type`-style field anywhere in the
design.

---

## 4. Inadmissible evidence must remain inspectable (steering §4)

**Requirement admissibility gates satisfaction. It must never gate existence in the semantic record.** The
revised instance-level structure, replacing revision 1's `provenance["supporting_bindings"]` sketch, is one list
per role per instance, built **before** any satisfaction decision is made:

```
candidate_supports[role] = [
    {
        "proposition_id": ...,
        "exact_text": ...,
        "assertion_relation": current_document | attributed_external | unresolved,
        "aggregation": literature_synthesis | non_synthetic_or_unspecified,
        "assertion_kind": result | method_or_description | aim_or_hypothesis | interpretation | unknown,
        "support_label": <the §2 downstream convenience string, display-only>,
        "finding_authority_veto": None | negated_result_predicate | absence_of_evidence,   # §9
        "is_caption": bool,
        "admissible": bool,
        "inadmissibility_reason": None | "support_policy_excluded" | "assertion_attachment_ambiguous",
    },
    ...
]
```

This mirrors the already-shipped v4 category precedent directly: `category_observations` already keeps every
observation for an instance, never collapsing to one representative, with `category_goal_satisfied` reading the
full list (`any(... == OBSERVATION_POSITIVE)`) and `_representative_observation` used only for display. The
design above is that exact pattern, generalized past category roles: satisfaction reads
`any(c["admissible"] for c in candidate_supports[role])`; nothing — rendering, audit, a future human reviewer — ever
loses access to an inadmissible-for-this-requirement candidate, because it is still in the list, still carrying
its own relation/aggregation/kind/label and its own disclosed reason for not counting here.

Worked example (steering §4's own): "Did this trial find X?" against a role whose `support_policy` (§7) admits
only `current_document` relation. The library holds no direct result for X in the trial paper itself, but a review
passage offers `attributed_external` + `literature_synthesis` support. That candidate is recorded with
`admissible=False`, `inadmissibility_reason="support_policy_excluded"` — the role stays `missing` (not `filled`),
but the review passage is never discarded: it remains fully inspectable, with its own honest relation/aggregation
metadata, available to a context-aware render ("the trial itself does not report this; a review in the library
does") that is a strict superset of silence, never a fabricated satisfaction.

---

## 5. Definitional and method-description content — boundary preserved (steering §9)

**Unchanged in substance from revision 1, restated to make the boundary explicit and non-negotiable:**
`assertion_kind=method_or_description` is **not** split in this design, and the support/admissibility layer is
**never** the thing deciding whether a descriptive sentence actually answers a target ("X is defined as..."
versus "X was measured using..."). That is a mapping-relevance question — did the retrieval/mapping strategy
decide this passage is topically about the role's target at all — fully upstream of and independent from
provenance classification. The support/admissibility layer only ever classifies evidence that mapping has
*already* judged relevant; it never re-litigates relevance. If a future increment wants `method_or_description` to
distinguish a definitional clause from an operational-measurement clause, that is a mapping-strategy refinement
(a new, narrower strategy, or a sub-rule inside the existing kind classifier) — out of scope here, named, not
decided.

---

## 6. All-support aggregation: no winner determined by list order (steering §5, §6)

**Pipeline, replacing revision 1's first-admissible-wins design:**

1. **Collect.** For a deterministic-strategy role, scan every unit in the searched scope (not stopping at the
   first match) and build one `candidate_supports` entry (§4) per locally-valid assertion that binds to the role's
   target — using I4-1d's span attachment, not the historical whole-passage match, once I4-2 actually wires it.
2. **Classify.** Each candidate gets its own `assertion_relation`/`aggregation`/`assertion_kind`/`finding_
   authority_veto`/`is_caption`, independent of the others.
3. **Admit.** Each candidate's `admissible` flag is computed from two independent gates (§7, §9): the role's
   `support_policy` against (relation, aggregation, kind), **and**, separately, the attachment-ambiguity rule
   below. A candidate that is structurally ambiguous (I4-1d's `ambiguous_with`) is `admissible=False`,
   `inadmissibility_reason="assertion_attachment_ambiguous"` — **it cannot independently satisfy the role**,
   exactly the steering round's own strong hypothesis.
4. **Aggregate role state.** `filled` iff **any** candidate is admissible. `ambiguous` iff **no** candidate is
   admissible **and** at least one relevant candidate carries `assertion_attachment_ambiguous` specifically (as
   opposed to merely `support_policy_excluded`, which aggregates to ordinary `missing`/`not_found` — a role with
   only policy-excluded candidates is not ambiguous, it is cleanly unsatisfied for a disclosed reason).
   `missing`/`not_found` otherwise. This directly implements the steering round's two worked cases: candidate A
   ambiguous + candidate B unambiguous-and-admissible → role fills from B, A's ambiguity still recorded;
   candidate A ambiguous + no other candidate → role is `ambiguous`, reason
   `assertion_attachment_ambiguous`, never silently resolved by picking A anyway.
5. **Select a representative, last, for display only.** If a legacy-shaped single `exact_text`/`proposition_id`
   is still wanted on the binding (for any consumer not yet updated to read `candidate_supports`), it is populated
   **after** step 4, deterministically, from among the *already-admissible* candidates only (e.g., first-admissible
   in list order among survivors) — never from the raw unfiltered list, and never itself deciding `state`. This is
   exactly the "compatibility projection" the steering round explicitly permits: order may still decide which
   equally-valid admissible quote is shown first, but it never again decides whether the role filled at all.

This removes the dependency the steering round flagged: under revision 1, two admissible candidates in different
list positions could never both be seen as co-equal evidence; under this design, both live in `candidate_supports`
regardless of order, and `state` depends on the *set*, never on which happened to be scanned first.

---

## 7. Requirement admissibility: a small predicate over the orthogonal fields (steering §7)

**Rejected again, for the same reason as revision 1: a named-policy enum (`current_study_result_required` /
`empirical_support` / …) is sugar for a fixed set and adds a second vocabulary to keep in sync.** Revised to
operate directly on the orthogonal triple rather than on revision 1's flattened label, per the steering round's
explicit instruction (§7 there, option B):

```
support_policy = {
    "allowed_assertion_relations": frozenset(...) ⊆ {current_document, attributed_external, unresolved},
    "aggregation_requirement": "any" | "require_synthesis" | "exclude_synthesis",
    "allowed_assertion_kinds": frozenset(...) ⊆ {result, method_or_description, aim_or_hypothesis, interpretation},
}
```

Three fields, one small closed vocabulary each — not a large ontology. `aggregation_requirement` is three-valued
rather than a plain boolean specifically so the fourth worked case below ("what does the literature broadly say")
is expressible without inventing a separate mechanism later. Structurally, this is one new optional `RoleSpec`
field (a nested dict, not three more flat kwargs), the same convention `new_requirement` already uses for
`direction`/`effectiveness` (`se.new_effectiveness_assessment()` is the existing, directly-citable precedent for
"compound per-requirement metadata lives in its own small builder-produced dict, not a sprawl of flat kwargs") —
not performed in this audit (no `RoleSpec` field addition).

The four required cases from the steering round, all expressible without a domain branch:

| Ask shape | `allowed_assertion_relations` | `aggregation_requirement` | `allowed_assertion_kinds` |
|---|---|---|---|
| 1. General empirical ask ("has X been found?") | `{current_document, attributed_external, unresolved}` | `any` | `{result}` |
| 2. Current-study-specific ask ("did THIS trial find X?") | `{current_document}` | `any` *(a trial's own meta-analytic/pooled result still counts as its own finding — directness and aggregation are orthogonal, so narrowing relation does not need to also narrow aggregation)* | `{result}` |
| 3. Definitional ask ("what is X?") | `{current_document, attributed_external, unresolved}` | `any` | `{method_or_description}` *(plus `interpretation`, opt-in)* |
| 4. Literature-synthesis ask ("what does the literature say about X overall?") | `{current_document, attributed_external, unresolved}` | `require_synthesis` | `{result}` |

---

## 8. Default policy, corrected, and the compatibility claim rephrased (steering §8)

**Two separate claims, now kept explicitly separate, as instructed:**

- **Schema/authoring compatibility (unchanged, verified in revision 1 and reconfirmed here):** `sufficiency_
  authoring.py`'s real q_aib contract contains zero occurrences of "this study"/"this paper"/"the present study"/
  "current study" in any requirement wording, so no existing `RoleSpec` needs an explicit `support_policy`
  override the moment this ships, and a new optional field defaulting to `None` leaves every pre-existing
  `RoleSpec` byte-identical in shape.
- **Semantic-output parity after wiring is a different claim, and it is false in general.** Once `is_support_
  admissible`-equivalent logic actually gates `_bind_role_candidates`, some candidate-binding *outcomes* change
  for roles that relied on the historical first-admissible-unit-wins behavior admitting everything indiscriminately.
  This is precisely why I4-2 is the increment that must declare and justify a `sufficiency_semantics_version` bump
  — not because the schema moved, but because real outputs may move. This audit does not claim otherwise, and
  revision 1's phrasing that risked reading as "behavior-preserving" is corrected here.

**The default predicate itself, corrected to resolve the self-contradiction named in the correction ledger (§0.3):**

```
default_support_policy(relation, aggregation, kind) :=
    kind == result
    and not (relation == unresolved and aggregation == non_synthetic_or_unspecified)
```

i.e., `allowed_assertion_kinds` defaults to `{result}` (`method_or_description`/`interpretation` need an explicit
opt-in per role, unchanged reasoning from revision 1 — a general empirical-existence role is not automatically a
definitional one), `aggregation_requirement` defaults to `any`, and `allowed_assertion_relations` defaults to all
three **except** that `unresolved` is admitted **only when `aggregation == literature_synthesis`**. This is not
expressible as three independently-defaulted set memberships; it is one small, named, fully-specified predicate,
and an authored `support_policy` on a `RoleSpec` may override any subset of its three fields while leaving the
rest to fall back to this same predicate's corresponding behavior — the exact mechanical split (one hard-coded
function with override hooks, versus three independently-defaultable sub-fields) is an I4-1g/I4-2 implementation
choice, not locked here.

**Quantified counterfactual against the preserved corpus, under the corrected default (supersedes revision 1's
table for these three ids):**

| id | `assertion_relation` | `aggregation` | Admissible under the corrected default? | Changed from revision 1's claim? |
|---|---|---|---|---|
| p11 | `unresolved` | `non_synthetic_or_unspecified` (bare "correlated with", no cue) | **no** | No — revision 1 also excluded it, for the same D-A/D-D reason, now via the compound predicate rather than a flat `unresolved`-exclusion. |
| p30 | `unresolved` | `non_synthetic_or_unspecified` (run-in-heading false negative, no aggregation cue either) | **no** | No — same as p11, for the same disclosed, pre-existing reason (I4-1b's own named extraction artifact). |
| p31 | `unresolved` (subject is the hedged possibility, not the authors) | `non_synthetic_or_unspecified` | **no**, but for a *different* gate than relation/aggregation — `assertion_kind=interpretation` is excluded from `allowed_assertion_kinds`'s default regardless of relation/aggregation | No change in outcome; the exclusion now routes through the kind gate rather than being entangled with the relation gate, which is a clarity improvement, not an output change. |
| §3's worked review sentence ("Across multiple studies, regions A, B, C are implicated") | `unresolved` | `literature_synthesis` | **yes** | **This is the corrected case** — revision 1's flat default would have wrongly excluded this exact sentence (relation=unresolved) despite it being the design's own motivating example; the compound predicate admits it correctly because the aggregation cue is present. |

No regression is introduced for p11/p30/p31; the one case that changes outcome under the correction is the one the
design was built to serve in the first place, which is the intended, measured effect of this revision.

---

## 9. `finding_authority`/`authority_veto` after the revision (steering §11)

**A clarified, narrower role, not a removal.** `assertion_relation`/`aggregation`/`assertion_kind` are properties
of an **assertion in isolation**. `finding_authority`/`authority_veto`/`is_caption` are properties of a specific
**(assertion, proposed target span) pair** — confirmed directly from the real API,
`classify_assertion_authority(text, *, target_start, target_end, ...)`, which has always taken a target, never
operated on a bare assertion alone. These are not redundant axes; they answer a strictly narrower, additional
question once a specific positive target is on the table: does *this* assertion, for *this* target, survive the
caption/negation/absence-of-evidence checks.

**Revised recommendation, sharper than revision 1's "rename at the boundary":** `finding_authority`'s own coarse
`authoritative`/`candidate` value does **not** need to be separately exposed at any future production boundary at
all — once ownership is read honestly through `assertion_relation`, the "who" information `finding_authority`
used to gatekeep is already fully and more legibly carried there, with none of the `"candidate"`-naming-collision
risk revision 1's §18 flagged (nothing downstream is ever literally called `"candidate"` under this design).  What
`authority_veto` and `is_caption` uniquely and non-redundantly contribute — whether a *specific* target-binding
survives negation/absence-of-evidence/caption framing — is retained exactly as designed in revision 1 (§14 there,
unchanged): a veto blocks admissibility only for the specific positive-outcome-shaped role targeting the embedded
claim it negates, while the same vetoed assertion remains fully legitimate, disclosed evidence for an adjacent
"was this tested"/"what null findings exist" role. Both flags ride on each `candidate_supports` entry (§4) exactly
because each entry already is one specific (assertion, role-target) binding attempt.

`assertion_authority.py`'s own module, field names, and all frozen batteries remain **completely untouched** by
this recommendation — it is a statement about what a future production integration chooses to re-expose
downstream, not a change to the pure classifier.

---

## 10. Target-aware seam: reuse, not a new field (steering §10)

**Revision 1's `target_wording_span` is withdrawn.** Re-auditing against the existing `RoleSpec` field inventory
(`category_description`, `requested_category_terms`, `source_wording_span`, the role name/description, the
contract's own wording) finds that `requested_category_terms` already has exactly the needed shape — a list of
verbatim, authored term/phrase strings — and is simply scoped too narrowly today (gated to the
`explicit_category_terms` strategy's v4 category-observation machinery specifically, per the explicit `ValueError`
guard at `sufficiency_mapping.py:350-353`, which is a guard on that one mechanism, not a statement that the field
itself is strategy-exclusive).

**Recommendation: extend `requested_category_terms`'s documented meaning for `achieved_outcome_predicate` roles,
rather than adding a new field that would duplicate it.** Precisely specified, per the steering round's own
checklist:

- **What it contains:** zero or more exact phrase strings, copied verbatim from the original requirement wording —
  never paraphrased, never model-generated, identical authoring discipline to its existing use.
- **Where it comes from:** authored at contract-authoring time, same as today, by a human (or a future `author_
  supersession`-gated proposer).
- **Verbatim:** yes, unchanged from the field's existing contract.
- **Multiple terms:** yes — already a list; "Y" versus "X and Y" are both representable with no new multi-value
  design.
- **Fail-closed, narrowly-scoped matching:** literal containment only (the existing `canonical_text_contains`
  belt-and-suspenders check, `sufficiency_mapping.py:356`), and used **only to disambiguate among already-locally-
  valid candidates sharing one passage, never to broaden what counts as a match in the first place.** Concretely:
  when a role's `requested_category_terms` is non-empty and exactly one `candidate_supports` entry's matched text
  literally contains a listed term, that one is the non-ambiguous winner; if the list is empty, or none contain a
  listed term, or more than one does, the ordinary ambiguity-preserving aggregation rule (§6) applies unchanged.
  This directly answers the steering round's "do NOT authorize naive substring matching merely because it is easy"
  — the substring check is explicitly non-authoritative, scoped to breaking ties among candidates that have
  *already* independently qualified as locally-valid assertions, never a standalone relevance or admissibility
  gate on its own.
- **Historical roles when empty:** byte-identical, unaffected — every existing `achieved_outcome_predicate` role
  today has an empty `requested_category_terms` and none of this logic activates for them.

This is one new documented use of an existing field, not a new field — directly satisfying the steering round's
"avoid duplicating the same semantic target in multiple fields."

---

## 11. Shared semantics for Simple Ask and hierarchical Ask (unchanged)

Unchanged from revision 1: the triple (§2), the admissibility predicate (§7/§8), and `candidate_supports` (§4/§6)
all operate on raw text and a `RoleSpec`, with zero dependency on hierarchical decomposition. A Simple-Ask question
contract constructs one `RoleSpec` and runs the identical mapping/engine path. Routing itself remains out of scope
for this audit.

---

## 12. Revised generalization matrix (replaces revision 1's; same four domains, now over the triple)

| Domain | Question | `assertion_relation` | `aggregation` | `assertion_kind` | Admissible under corrected default or the role's own narrowing | Rendering |
|---|---|---|---|---|---|---|
| Neuroscience | "What did this study find?" | `current_document` | n/s | `result` | yes (role narrowed to `{current_document}`) | "Paper A found X." |
| Neuroscience | "Has X been found?" (cited prior result) | `attributed_external` | `non_synthetic_or_unspecified` | `result` | yes (default) | "Paper A reports prior evidence that X." |
| Neuroscience | "Has X been found?" (review in the library) | `unresolved` or `attributed_external` (depends on the review's own first-person framing) | `literature_synthesis` | `result` | yes (default, via the §8 compound predicate) | "A review in the library reports that X." |
| Neuroscience | "Has X been found?" (Paper A cites an *uncollected* external review) | `attributed_external` | `literature_synthesis` | `result` | yes (default) | "Paper A reports that a review found X." *(never "a review in the library" — §3)* |
| Clinical | "Did this trial reduce symptoms?" | `current_document` only admissible | n/s | `result` | yes only if `current_document`; a `synthesis`/review candidate is recorded `inadmissible, support_policy_excluded`, still inspectable | "Trial A found a reduction in symptoms." |
| Clinical | Meta-analysis's own pooled result | `current_document` | `literature_synthesis` | `result` | yes, including for a current-study-specific role (relation and aggregation are orthogonal — §7 case 2) | "This meta-analysis found a pooled effect of X." |
| Clinical | Null result ("found no evidence that X") | `current_document` | n/s | `result`, `finding_authority_veto=absence_of_evidence` | admissible for a "was X tested" role; blocked for the positive-outcome role targeting X itself | "Paper A directly tested X and reported no evidence for it." |
| Architecture/built environment | "What is X?" (concept definition) | any | n/s | `method_or_description` | yes (default) | "A paper defines X as..." |
| Language learning | "What does the literature say about X?" | any | `require_synthesis` (role explicitly requires it) | `result` | only `literature_synthesis` candidates admitted | "The literature, per a review in the library, reports X." |

Every cell is produced by the same triple-classification + predicate mechanism; no domain-specific branch anywhere.

---

## 13. No document-genre inference (unchanged, restated once for completeness)

Unchanged from revision 1 (§17/§20 there): the aggregation signal lives on the sentence's own surface wording,
never on a `papers.document_type` field or equivalent, which does not exist in the preserved corpus and would
mislabel a review's own occasional direct computation (§1 case C) or a primary paper's synthesizing background
paragraph in either direction regardless.

---

## 14. Revised decisions R1–R12

| # | Decision |
|---|---|
| **R1** | **No.** `assertion_source`/`assertion_relation` keeps exactly three values (`this_study`/`current_document`, `prior_work`/`attributed_external`, `unknown`/`unresolved`). Synthesis is never an ownership value. |
| **R2** | `aggregation ∈ {literature_synthesis, non_synthetic_or_unspecified}` — one new, orthogonal, pure classifier output, detected from a small closed surface-cue set (adverbial framing, a synthesis-headed owner noun, or a synthesis-shaped object noun), independent of ownership and kind. |
| **R3** | **No**, not as the sole representation. The semantic record is the orthogonal triple (`assertion_relation`, `aggregation`, `assertion_kind`); a six(+)-cell downstream label may still be derived for display, never consulted by admissibility. |
| **R4** | `support_policy = {allowed_assertion_relations, aggregation_requirement ∈ {any, require_synthesis, exclude_synthesis}, allowed_assertion_kinds}` — one new optional nested-dict `RoleSpec` field (not three flat kwargs), mirroring the existing `direction`/`effectiveness` nested-dict convention. |
| **R5** | `candidate_supports[role]`, a list built *before* satisfaction is evaluated, one entry per locally-valid candidate, each carrying its own relation/aggregation/kind/label/veto/caption/admissible/inadmissibility_reason (§4) — the direct generalization of the already-shipped `category_observations` pattern past category roles. |
| **R6** | `filled` iff any candidate admissible; a representative/primary binding, if still needed for legacy-shaped output, is selected *after* that determination, from among already-admissible candidates only, never deciding `state` itself (§6). |
| **R7** | A candidate with structurally ambiguous attachment is itself inadmissible (`assertion_attachment_ambiguous`) and cannot independently satisfy a role; the role becomes `ambiguous` only when no unambiguous admissible candidate exists **and** at least one ambiguous-but-relevant candidate does; it becomes ordinary `missing` when every candidate is merely policy-excluded (§6, step 4). |
| **R8** | Default policy is the one compound predicate in §8 — `kind==result and not(relation==unresolved and aggregation==non_synthetic)` — not three independently-defaulted set memberships. Schema compatibility (no existing `RoleSpec` needs an override) is explicitly distinguished from semantic-output parity (some bindings' admissibility *will* change once wired, justifying I4-2's version bump); the measured counterfactual (§8's table) shows zero regression for p11/p30/p31 and the intended correction for the design's own motivating review example. |
| **R9** | The definitional/method-description boundary is explicitly preserved: the support/admissibility layer never decides topical relevance (whether a descriptive sentence answers the target) — that remains mapping's job, upstream and independent (§5). No classifier-enum split performed. |
| **R10** | No new field. `requested_category_terms`'s existing, documented meaning is extended (not duplicated) to `achieved_outcome_predicate` roles, used only to disambiguate among already-locally-valid candidates sharing one passage, never to broaden admissibility (§10). `target_wording_span` is withdrawn. |
| **R11** | `finding_authority`'s own `authoritative`/`candidate` value need not be re-exposed downstream at all — `assertion_relation` already carries its "who" information without the naming-collision risk. `authority_veto`/`is_caption` remain, as properties of an (assertion, target) pair rather than the assertion alone, riding on each `candidate_supports` entry (§9). No code change. |
| **R12** | I4-1f's exact bounded contract — see §15. |

---

## 15. I4-1f's exact bounded contract (steering §14, "if READY")

**READY for I4-1f**, scoped to exactly the following, and nothing past it:

1. A pure `assertion_relation(assertion_source) -> str` translation function (trivial, exhaustively tested for the
   three-way 1:1 correspondence in §2) — no new classification, a rename only.
2. A pure, new `aggregation(text, assertion_span_or_governing_structure) -> str` classifier output, implemented as
   a small, closed, surface-cue detector per §2/§1, including the review/meta-analysis/systematic-review head-noun
   addition to the existing prior-ownership lexicon named in §1's lexicon finding (the same disclosed, narrow,
   frozen-battery-tested shape every prior I4-1x lexicon addition has used — e.g. I4-1c's `provide/provided/
   provides`). This may live inside `assertion_authority.py` or a new sibling pure module; the choice is an I4-1f
   implementation detail, not locked here.
3. A pure `support_label(relation, aggregation, kind) -> str | None` downstream convenience function implementing
   the table in §2, documented as display-only and never an admissibility input.
4. Frozen synthetic batteries, in the established convention (preregistered + holdout + cross-domain twins),
   covering: the four minimal-pair contrasts in §1 (A–D); the review/meta-analysis lexicon addition; and — **a
   required, specific negative case** — the preserved sealed quote p41 ("Across the ratings for all faces,
   Spearman correlations revealed...") must be included as an explicit non-trigger: "across" alone, without a
   study/literature-denoting complement, must **not** fire the aggregation cue. This is a concrete false-positive
   risk a loose "across \w+" pattern would hit, and the battery must prove the real detector does not.
5. A read-only re-evaluation against the 54 preserved sealed quotes and the real preserved v4 map bindings
   (the same convention every prior I4-1x phase used), reporting every quote's `aggregation` value and every
   lexicon-addition effect on `assertion_relation`, with zero tuning toward a desired outcome.

**Explicitly out of scope for I4-1f** (deferred to I4-1g/I4-2, per the revised staging below): the `support_policy`
`RoleSpec` field; `candidate_supports`; the all-support-collection rewrite of `_bind_role_candidates`; the
role-level ambiguity aggregation rule; the `requested_category_terms` reuse for disambiguation. I4-1f produces
pure, unwired, classifier/descriptor-layer outputs only — no `RoleSpec` field, no mapping edit, no version bump,
matching this revision's own constraints exactly.

**Revised staging (replaces revision 1's §22):**

- I4-1e (this document) — design only, revision 2. Complete.
- **I4-1f** — the bounded contract above. Pure, unwired.
- **I4-1g** — the `support_policy` `RoleSpec` field + its builder, the `candidate_supports` instance-level
  structure, and the `requested_category_terms` reuse for disambiguation — all as pure schema additions with their
  own backward-compatibility tests (every existing call site, unmodified, produces byte-identical output). Still
  no semantic-gating change anywhere a production path executes.
- **I4-2** — production integration: wire `support_policy` evaluation and the all-support-collection pipeline (§6)
  into `_bind_role_candidates`; wire I4-1d's span attachment in to replace whole-passage binding; declare and
  justify the `sufficiency_semantics_version` bump this increment requires (quantifying the real output diff, per
  §8's corrected compatibility claim); re-run the full v4 map reconstruction against q_aib's real preserved data
  and diff it byte-for-byte against the v4-lenient baseline.
- I4-3 (relation/direction/effectiveness integration), conditional on what the I4-2 diff actually shows.
- I4-4 (AnswerPlan/rendering consumes the shared metadata for the honestly-worded templates demonstrated in §3/§12).
- Then resume I2-3, unaffected by and independent of all of the above.

---

## 16. Recommendation

**READY for I4-1f**, bounded exactly as specified in §15. **NOT READY for I4-1g or I4-2** — the pure descriptor
layer I4-1g's schema additions and I4-2's wiring both depend on (`assertion_relation`, `aggregation`,
`support_label`) does not exist as tested code yet, and I4-1d's own standing blocker (the achieved-outcome mapper
still binds the whole passage at the real `_bind_role_candidates` call site) remains unchanged by either revision
of this audit.
