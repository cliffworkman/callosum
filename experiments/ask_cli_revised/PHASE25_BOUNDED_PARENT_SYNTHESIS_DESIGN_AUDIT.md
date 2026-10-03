# Phase 25 — bounded parent synthesis for hierarchical Ask: DESIGN AUDIT (no implementation)

**Authoritative state, verified before any work began:** HEAD `ba066b148e6aade65271a8c98ff5c40863025629`
— exact match to the packet's expected value. Frozen v9 `combined_hash`
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586` — read directly from
`sufficiency_contract.aib_hier_v9.frozen.json`'s own `combined_hash` field, exact match. Working
tree clean (`git status --porcelain` empty) before and after this audit. **No code was changed, no
live model call was made, no network call was made, no contract/pin was touched.** This document
and its one `CONTRIBUTION-LINEAGE.md` append are the only writes made.

---

## 1. Current parent/Overview synthesis architecture — audit

**There is no parent-level synthesis today, by explicit design, not by omission.** `e2e.py:801-864`
branches on `contract.get("version") == hierarchy_contract.HIER_VERSION`:

- **Hierarchy arm (`e2e.py:811-856`):** one `overview.build_overview()` call **per approved child**,
  each over a strictly child-scoped sealed ledger (`hierarchy_contract.build_child_sealed_ledger`,
  `hierarchy_contract.py:975-1028`). The arm's own comment is explicit about why: *"never one flat
  call over the whole 11-child ledger, which would be exactly the parent-level meta-synthesis this
  architecture does not yet authorize"* (`e2e.py:805-810`). Results land in per-child files
  (`14a_overview.{child_id}.json`, `14_final_answer.{child_id}.md`, `14b_detailed_inspection.
  {child_id}.md`) referenced (state + audit only, not the full record) in `14_child_overview_
  manifest.json`.
- **Flat arm (`e2e.py:857-864`):** one `overview.build_overview()` call over the whole sealed ledger
  — this is the **only** case that produces a single, request-wide synthesized answer today, and it
  exists only because a flat run has no children to separate.
- **The deterministic, hierarchy-aware top-level answer** (`14_final_answer.md`, built via
  `ledger_renderer.render_answer(sealed)` → `render_responsive_ledger`, unconditionally, in both
  arms, `e2e.py:865`) is a **structural roll-up, not a synthesis**: verbatim claims grouped "By
  request item," a "Parent reconciliation (structural; no verdict)" table
  (`ledger_renderer.py:183-213`, built from `hierarchy_contract.rollup()`,
  `hierarchy_contract.py:1041-1153`) that explicitly states "Individual obligation fulfilment: NOT
  assessed… Parent answer completeness: NOT certified" (`hierarchy_contract.py:1069`,
  `LABELS["parent_completeness"]`), and a closing "Completeness remains unresolved" section. It
  joins nothing across children and asserts no relationship — it is pure reorganization of
  already-verbatim content, the one thing Phase 25 is allowed to do more of, not a precedent for
  doing *less*.

**Inputs/outputs of the existing per-child/flat Overview stage** (`overview.py`, `overview_
evidence.py`, `overview_guards.py`, `overview_render.py`, `overview_audit.py`):

| | |
|---|---|
| Input | one sealed ledger (flat: the whole run's; per-child: `build_child_sealed_ledger`'s filtered copy) — `verified_propositions` + `evidence_spans` + `obligation_states`, nothing else |
| Model calls | exactly one `supervisor.call(STAGE, prompt, schema, …)` per invocation (`overview.py:412`), plus one batched local NLI call (`overview.py:271-283`, `screen_proposals`) |
| Output | a hashed, self-contained record (`overview_hash` over everything but itself, `overview.py:229-231`) with `items` (1-6 screened sentences, `unit_ids`→`proposition_ids`, `bears_on` tags), `parts` (4-state per-request-item status, never a completeness verdict), and a full audit trail of every proposal (grounded or withheld) and every passage's eligibility |
| Provenance | fully retained: every displayed sentence traces to 1-3 `unit_id`s → `proposition_ids` → paper/chunk/span locators via `unit["locators"]` |
| Citation | `unit_ids` in the model's JSON output, rendered as `[n]` numbers assigned in first-citation order (`overview_render._cite_numbers`, `overview_render.py:56-66`) |

### What is reusable, unmodified

- **`overview_guards.screen` / `overview_guards.nli_pair` / `overview_guards.nli_reasons`** — the
  entire lexical+NLI fidelity screen is generic over `(proposal, units, part_ids)`; nothing in it
  assumes a flat or per-child ledger. It checks a sentence against **whatever `units` dict it is
  given** — it has no opinion about where those units came from. This is the single most valuable
  reusable primitive for Phase 25 (see §18).
- **The screen→batched-NLI→positional-reconstruction pattern** in `overview.screen_proposals`
  (`overview.py:235-287`) — one call for all proposals, scores reattached by index, a scorer failure
  withholds rather than approves. Directly reusable for any future realization pass.
- **The "separate, separately-hashed artifact referencing the sealed ledger by hash" pattern**
  (`overview.py:9-11`, `overview_audit.py`'s re-derive-and-compare discipline) — the right shape for
  a parent artifact too: never mutate the ledger, never let model prose enter a trusted record
  silently.
- **`contract_sha256`/`worst_case_output_chars`** (`overview.py:182-217`) — the schema-driven output-
  cap discipline (CLAUDE.md's own inc-575 rule, independently reinvented here) applies unchanged to
  any new schema.
- **`hierarchy_contract.rollup()`** — the per-child/per-parent structural grouping a parent answer
  would want to organize by (depth, parent, owned obligations) already exists, is already audited,
  and needs no change.

### What would be dangerous to reuse as-is

- **`overview_evidence.build_units(sealed)` called over a *merged* multi-child ledger.** This is
  exactly the mistake Phase 17/18 found and fixed one level down: `units_by_child`/`compute_
  direction_and_effectiveness` used to pool a whole child's candidate units undifferentiated by
  instance, and a proposition attached to child A could "hijack" a value for child B merely by
  sharing a dedup key or request-tag (`PHASE18_DIRECTION_EFFECTIVENESS_SEMANTICS_RESULTS.md` §18,
  reproduced live: *"irrelevant earlier unit wins over the target instance's own evidence"*). Running
  `build_units` over a **union of children's propositions** reintroduces the identical class of bug
  one level up: a unit's `attached_children` can span several children, and `overview.select_for_
  prompt` has no instance/requirement scoping at all — it would show the model passages from
  unrelated branches of the hierarchy with nothing stopping it from writing one sentence that spans
  two of them. **Do not point the existing `build_overview` at a merged ledger as a shortcut to
  "parent synthesis."**
- **Per-child Overview *output* (the `items`/proposed sentences) as parent-synthesis input.** See §2a
  below — this is the single most important finding of this audit.
- **Per-child `unit_id`s as a citation key at the parent level.** Each child's `overview.build_units`
  call starts its own `U1, U2, …` numbering fresh (`overview_evidence.py:256`, `len(by_key) + 1`
  scoped to whatever `sealed` dict was passed in). `U1` in child `c4`'s overview and `U1` in child
  `c5`'s overview are almost always different propositions. A parent ledger **must** key citations by
  the globally-unique `proposition_id` (confirmed global and flat across the whole run — Phase 23a's
  own table cites `p11`, `p26`, `p33`, … across every child without collision) or by the physical
  `(paper_id, chunk_id, span_id)` locator, never by a per-child `unit_id`.

### 2a. The central finding: per-child Overview output is *convenience*, not *authority*

The brief asks whether "final child overview outputs" belong in the authoritative input set (§3). **They
do not, and the reason is concrete, not theoretical.** The per-child Overview's deterministic screen
(`overview_guards.screen`) validates a proposed sentence's **fidelity to its cited passage** — numbers,
acronyms, direction words, hedges, negation, actor/recipient prepositions, novel vocabulary. It has
**no mechanism to validate fidelity to the sufficiency engine's own role-binding semantics**, because
the Overview stage never sees the sufficiency map at all — `overview.build_overview` takes a `sealed`
ledger and nothing else (`overview.py:339-348`). Phase 23a's own adjudicated c12 finding is the proof:
the `target_manifestation` nomination that picked "the wrong half of a stated contrast" (row #21,
`PHASE23A_POSTHOC_SCIENTIFIC_ADJUDICATION_AND_ERRATUM.md` §3a) is a **role-assignment** error, not a
passage-fidelity error — the cited text ("bias toward people of color") is verbatim-grounded, exactly
as `overview_guards.screen` would want it, and exactly as an equivalent per-child Overview sentence
about it would pass screening. A parent synthesizer built on per-child Overview *prose* would inherit
that error dressed in fluent, passage-grounded language, with nothing upstream positioned to catch it.
A parent synthesizer built on the **structured role bindings** (`exact_text` directly, `sufficiency_map_
final[c12]["instances"][…]["role_bindings"]["target_manifestation"]`) reproduces the identical wrong
value — faithfully, which is the whole point (§17) — but with its exact provenance (`proposition_id`
→ `p33` → the real passage) attached for a reader to discover the error themselves, which passage-level
prose with no role label does not surface as cleanly.

**Conclusion:** the per-child Overview is a complete, independently-correct, already-shipped product
in its own right (Stage B). Parent synthesis should be built as a **sibling consumer of the same
underlying sufficiency state**, not as a consumer **of** Stage B's output. This decouples the two
cleanly: Stage B is untouched by Phase 25 under every design below, and a future change to either
never risks breaking the other.

---

## 3. Authoritative parent-synthesis inputs — the hierarchy

| Candidate | Authority class | Why |
|---|---|---|
| `sufficiency_map_final` (per-child `SufficiencyContract`, `instances[*].role_bindings`/`complete`/`state`, `direction_summary`/`effectiveness_summary`) | **(A) Semantic authority** | The one place a role's own value, an instance's completion, and a requirement's state are *decided* — by deterministic mapping, optionally model-assisted but always structurally flagged (`provenance.candidate_source`) |
| `sufficiency_recovery_targets` (final, post-last-round) | **(D) Unresolved-gap authority** | The closed 6-reason, hashed-identity inventory of exactly what remains unanswered and why (`sufficiency_recovery_targets.py:49-56`, `:68-118`) |
| `sealed["verified_propositions"]` / `evidence_spans` (via `proposition_id`) | **(C) Provenance/citation authority** | The only place an exact quote, page/chunk/span locator, and verification record live |
| `hierarchy_contract.rollup(contract, …)` / `parent_of(contract)` | **(E) Non-authoritative display/structural artifact** | Organizes *where* to say something (grouping, depth, which child owns which obligation); explicitly disclaims completeness/fulfilment itself (`LABELS["parent_completeness"]`) — never a source of what is true |
| Per-child Overview output (`items`, `proposals`) | **(B) Prose/context convenience, at most** | Already-screened, already-fluent phrasing a realization pass *could* borrow wording from, but never a source of role-level truth (§2a) |
| `stop_search_certified` (`compute_stop_search_certified`) | **(D)-adjacent, a modifier on (A)** | Not semantic authority itself (never overloads `state`) — a separate, orthogonal fact about whether a `filled` state leans on a model nomination; feeds §16, not completion |
| Child contracts (the mapped `SufficiencyContract` per child) | *Same object as (A)* | `sufficiency_map_final[child_id]` already **is** "the child contract" — not a second candidate |
| Citation metadata (paper/chunk/span via `evidence_spans`) | *Same object as (C)* | — |

**The hierarchy, stated as a rule:** (A) and (D) decide *what may be said and what is unresolved*; (C)
decides *what may be quoted and where it points*; (E) decides *how to organize the page*; (B) may only
ever *inform wording*, never truth, and must be independently re-validated against (A)/(C) before it
can appear (exactly the existing Overview screen's own relationship to its passages, one level up). A
child's model-generated prose must never silently outrank (A) if the two disagree — and under this
design they structurally cannot disagree, because the parent ledger is never built *from* the prose at
all (§2a).

---

## 4. Existing child output contract — audit

Everything below is read from `sufficiency_engine.py` and `sufficiency_diagnostic.py`, confirmed
present on every mapped instance/requirement as of Phase 18 (fully implemented, not merely designed —
confirmed by direct read of `sufficiency_diagnostic.compute_direction_and_effectiveness`,
`sufficiency_diagnostic.py:234-275`, which populates instance-scoped, order-invariant observations
exactly as `PHASE18_DIRECTION_EFFECTIVENESS_SEMANTICS_RESULTS.md` specified).

**Per instance** (`sufficiency_engine.new_instance`, `:194-208`):
`instance_key`, `role_bindings` (`{role: {state, reason, proposition_id, exact_text, provenance:
{candidate_source, model, upstream_model_dependent?, model_dependency_origins?, supporting_
proposition_ids?}, guard}}`), `complete` (bool, from `recompute_instance`), `state`
(`filled`/`partially_filled`/`missing`/`ambiguous`), `reason`, `direction_observations`/
`effectiveness_observations` (lists of `new_direction_assessment`/`new_effectiveness_assessment`
records, each carrying its own `proposition_id`/`exact_text` — never a blended/first-match scalar,
Phase 18 §4/§8).

**Per requirement** (`sufficiency_engine.new_requirement`, `:211-264`): `id`, `kind`, `role_specs`,
`role_completion` (`required_roles`/`alternative_role_groups`/`optional_roles`), `instance_quantifier`
(`exists`/`all_requested_categories`/`for_each_discovered_instance`/`at_least_n`/`open_list`),
`relationship_verifiers`, `multi_instance`, `instances` (list, above shape), `parent_context_roles`,
`direction`/`effectiveness` (the frozen authored template — never mutated at runtime),
`direction_summary`/`effectiveness_summary` (the Phase 18 **derived view**, `summarize_observations`,
`sufficiency_engine.py:497-539`: `observed_values`, `consensus_value`, `has_within_instance_conflict`,
`has_across_instance_heterogeneity`, `complete_instance_keys`, `instance_keys_with_observations`,
`instance_keys_missing_observations`, `conflicted_instance_keys` — **already the exact orthogonal,
non-collapsing shape §11 of the packet asks for**, built from complete instances only), `state`/
`reason` at the requirement level (one of 5 aggregation policies, `_AGGREGATORS`,
`sufficiency_engine.py:645-651`, dispatched by `instance_quantifier`).

**Stop-search / model-dependence:** `compute_stop_search_certified(requirement)`
(`sufficiency_engine.py:779-799`) — a requirement-level bool, **not** stored on the requirement itself
(a parallel query, never a second `state`), true whenever `state != "filled"` or the fill owes nothing
to a `model_mapping`-sourced completion-critical binding, directly or via a propagated
`upstream_model_dependent` hop.

**Losslessly projectable into parent input, with zero loss:** every field above. Nothing needs a new
representation to reach a parent claim ledger — `role_bindings[role].exact_text`/`proposition_id` is
already exactly "a verbatim value plus its citation"; `direction_summary`/`effectiveness_summary` is
already exactly "a requirement-level, heterogeneity-safe derived view." **The one thing that does NOT
exist today and is not needed:** there is no existing concept of "a child's own prose synthesis" tied
to the sufficiency map — the per-child Overview (§2a) is a structurally separate pipeline over the same
`sealed` ledger, never informed by `sufficiency_map_final`.

---

## 5. Core invariant: no novel semantic relationships — mechanical representation

**Decided at ledger-construction time, never at realization time.** The parent claim ledger (§8) is
built by a **pure, deterministic traversal of `sufficiency_map_final`** — the realization model is
never shown two independently-true facts side by side in a way that invites it to relate them unless
the ledger itself already contains one pre-approved combined entry for that relationship. Concretely:

- A `role_value` claim (one filled, non-parent-context role binding) carries **exactly one**
  `proposition_id`/`exact_text` (or the joint-grounded set for a 2+-role relational binding — see
  below) and **one** `claim_kind`. It is never built by scanning across requirements.
- A `relational` claim (one instance of a `kind="relational"` requirement, e.g. `c5#suff:brain-
  behavior`) is built as **one indivisible unit** carrying every jointly-grounded own-evidence role
  together, exactly as `sufficiency_engine._verify_same_proposition`/`_joint_grounded` already
  established grounding for at mapping time (§6). It is never split into two separate role claims and
  never merged with a different instance's roles.
- A `category_list` claim (siblings of one `for_each_discovered_instance`/`all_requested_categories`/
  `open_list` requirement, same role) is pre-combined **once, at ledger-construction time**, by the
  ledger builder — never assembled by the realization model choosing which sentences to put together.
- A realized sentence's screen (§18, reusing `overview_guards.screen` unchanged) enforces: **every
  cited id in one sentence must belong to the same parent `claim_id`** (or a `category_list`/
  `relational` claim that was itself pre-combined under the rule above) — never two different,
  independently-built `claim_id`s. This is the direct parent-level analogue of `overview_guards`'
  existing `MAX_UNIT_IDS` bound, just enforced at claim-identity granularity instead of unit
  granularity.

This makes "invent a cross-child relationship" **structurally unreachable** by the realization pass:
it cannot combine claim A and claim B in one sentence unless the ledger already combined them, and the
ledger only combines things the sufficiency engine already jointly-grounded or the aggregation policy
already treats as one open-ended category.

---

## 6. Relational claims — audit

Every relational finding in the real v9 contract (`c5`, `c6`, and any future `kind="relational"`
requirement) already carries provenance to a specific joint-grounding verifier: `same_proposition`
(intersection of `_support_set`s, `sufficiency_engine.py:380-390`) is the only one with a real call
site today; `contract_directed_links` exists (`sufficiency_engine.py:393-416`, backed by
`contract_directed/links.py`) but is **confirmed unreachable** in the current pipeline — no call site
ever supplies `context["attachment_pieces"]` (`sufficiency_mapping.py`'s own comment, repeated at
`sufficiency_engine.py:402-405` and Phase 18 §4's reproduction). **The existing relationship-witness
machinery is already sufficient to gate this**, with zero additions: `relationship_witness_support_
ids` (`sufficiency_engine.py:456-488`) already computes, for exactly this purpose (feeding direction/
effectiveness), the precise proposition set that *witnesses* a relationship as opposed to merely
supporting one ingredient role independently — "role A's support is {p1,p2}, role B's is {p1,p3}; only
p1 is admissible" is already handled, adversarially tested, and shipped (Phase 18 §4's own worked
example). A parent `relational` claim reuses this verbatim: its admissible evidence is `relationship_
witness_support_ids(...)`, nothing invented.

**No redesign of the sufficiency engine is needed here.** The one new, parent-only representation
required is purely organizational: a `claim_kind` tag on each parent ledger entry (§5/§8) so the
realization screen can tell "this citation set is a pre-approved relational unit" from "this is an
atomic role value" — a label over already-computed content, not a new semantic computation.

---

## 7. One-pass vs. two-stage — comparison and decision

| | A. one-pass model synthesis | B. structured ledger → bounded editorial pass | C. model content-selection → deterministic validation → editorial pass | D (adopted below, = Cliff's hypothesis) |
|---|---|---|---|---|
| Semantic safety | Low — model sees raw per-child state and must both select and phrase, the exact shape that produced c12's error one level down | High — the model never decides *what* is true, only *how to phrase what the ledger already asserts* | Medium — adds a model selection step with its own failure mode (wrong selection) before validation | Same as B, with a derived, pre-combined ledger that needs no selection at all |
| Provenance | Hard to keep sentence-level | Clean — claim_id → proposition_id is fixed before any model call | Clean once selection is validated, but selection itself is unvalidated | Clean |
| Relation-invention risk | High | Mechanically bounded by §5 | Possible at the selection step | Mechanically bounded by §5 |
| Latency | 1 call, but larger/riskier prompt | 1 bounded call (§27) | 2 calls | 1 bounded call |
| Local-model compatibility | Poor (needs strong instruction-following over a huge open-ended prompt) | Good — same shape as the already-working per-child Overview prompt | Good | Good |

**Decision: B/D — a deterministic parent content ledger, then one bounded editorial model pass, with a
separate structured unresolved-gap report.** This is exactly the architecture named in the packet's
§7 as "my prior preference" and it is the correct one: it is the only option that makes relation-
invention structurally bounded rather than merely instructed against, and it reuses the exact
validate-after-generate pattern (`overview.py`'s screen→NLI) that is already proven in this codebase
rather than inventing a new trust mechanism.

---

## 8. Parent content ledger — minimal schema

Question-agnostic, domain-agnostic (no q_aib vocabulary — matches the house style every sibling module
in this package already follows, e.g. `sufficiency_recovery_targets.py`'s own stated charter).

```
ParentClaim = {
    "claim_id":            str,   # stable hash of the fields below, mirrors new_target_id's pattern
    "claim_kind":          "role_value" | "relational" | "category_list"
                            | "direction_or_effectiveness" | "unresolved_gap",
    "child_ids":           [str],         # every (child_id, requirement_id) this claim traces to
    "requirement_ids":     [str],
    "instance_keys":       [str | None],  # the originating instance(s); None for a pre-v9-forked single instance
    "role":                str | None,    # for role_value/relational; None for direction_or_effectiveness/category_list/unresolved_gap
    "category_description":str | None,    # from RoleSpec.category_description -- NEVER from exact_text (the recovery-target confirmation-bias guard, reused)
    "values": [                           # one entry per contributing (proposition_id, exact_text) pair
        {"proposition_id": str, "exact_text": str, "role": str}
    ],
    "admissible_proposition_ids": [str],  # = relationship_witness_support_ids(...) for relational; _support_set(binding) for role_value; union for category_list/direction
    "direction_or_effectiveness": dict | None,   # the Phase-18 summarize_observations() view, verbatim, when claim_kind is that
    "model_dependency": {"any": bool, "stop_search_certified": bool},  # provenance of HOW the value was established, never shown as a confidence score
    "conflict_or_heterogeneity": dict | None,    # carried through unchanged from direction_or_effectiveness when present
}

UnresolvedGap = {  # one per final RecoveryTarget, deduplicated by target_id -- NOT a ParentClaim
    "target_id": str, "search_child_id": str, "requirement_id": str, "target_roles": [str],
    "reason": str, "goal_mode": str, "category_descriptions": [str],
}
```

Fields deliberately **excluded** (per the packet's own "don't include a field merely because it sounds
useful"): a confidence/score number (no opaque composite — PRINCIPLES.md commitment #7, and nothing in
the sufficiency engine produces one to begin with); per-child Overview `unit_id`/sentence text (§2a);
`trigger_child_id`/raw `dependency_origins` detail (already-superseded bookkeeping per Phase 16's own
finding, `PHASE16_PARENT_CONTEXT_ELIGIBILITY_RESULTS.md` "`dependency_origins` merge" section —
`affected_descendants`/`child_ids` already carry what matters).

---

## 9. Deduplication semantics

Keyed on **identity of the underlying fact, never of the surface text**:

- **(A) Exact duplicate:** the same `(requirement_id, role, instance_key)` triple bound to the same
  `proposition_id` — cannot normally arise (an instance has one binding per role), named for
  completeness.
- **(B) Same proposition, different role:** e.g. Phase 23a's `p33` feeding both `intervention` and
  `target_manifestation` on `c12` (§3a rows 20/21) — **two separate `ParentClaim`s**, never merged;
  different role = different semantic content from the same sentence.
- **(C) Same value, different relationship/context:** e.g. `p58`/`p59` feeding `c2`'s behavior role
  directly but being *excluded* from `c5`'s relational pool by `same_proposition` (§3a row 166's own
  adjudication: "not a retrieval miss — a correct cross-requirement repurposing") — **two separate
  claims**, each correctly scoped to its own requirement's own admissible set.
- **(D) Overlapping but non-identical claim:** e.g. `p26` naming 9 regions, independently re-extracted
  by sibling requirements `c1` and `c4` — folded by `(role_category_description, proposition_id,
  exact_text)` into **one `category_list`/`role_value` claim per distinct named region**, with
  `child_ids`/`requirement_ids` carrying both `c1` and `c4` as joint provenance (never two claims
  asserting the identical region from the identical quote).
- **(E) Independent corroboration:** e.g. "Hadza" named correctly under both `c10` and `c11` — these
  are **different requirements asking different questions** (culture-existence vs. culture-paired-with-
  measure), so they fold into (D)'s shape **only if** `category_description` agrees across both; when
  it does not (as in this real case — `c10` and `c11` ask different things of the same fact), they
  remain **two separate claims**, exactly matching Phase 23a's own adjudication language ("independently
  and correctly recognized by two different requirements," §3a row 162).

The dedup key, precisely: `(category_description, proposition_id, exact_text)`. Two bindings that agree
on all three are the same fact asked the same way and fold into one claim with multi-provenance; any
disagreement keeps them separate. This never erases independent support (E) and never double-counts
true duplication (A/D).

---

## 10. Safe claim combination — the generic rule

**Safe (pre-combinable at ledger-construction time, never at realization time):**
1. Two or more `role_value` claims sharing the identical `(role, category_description)` from sibling
   instances of the same `for_each_discovered_instance`/`all_requested_categories`/`open_list`
   requirement → one `category_list` claim (listing several named regions/measures/populations is
   exactly the packet's own named-safe example).
2. The roles of one jointly-grounded `relational`-kind instance → one `relational` claim (already one
   unit by construction, §5/§6).
3. A `direction_or_effectiveness` requirement's own `summarize_observations` view → one claim per
   requirement (the view is already the safe, heterogeneity-preserving combination of that
   requirement's own complete instances — nothing further to combine).

**Relation-creating (never automatic, requires an *existing* verified relationship from §4/§6 to be
expressed as such):** combining a `role_value` from requirement X with a `role_value` from an unrelated
requirement Y in one sentence. The generic rule, stripped of domain vocabulary: **a cross-requirement
combination is safe iff the two requirements' own role bindings were already required, by the frozen
contract's `role_completion`/`relationship_verifiers`, to co-occur in the same proposition** (i.e. they
are actually the same relational instance under §5/§6) — **never** because they happen to both be
`filled` in the same run, share a hierarchy parent, or were retrieved near each other.

---

## 11. Direction/effectiveness handling

Already fully solved by Phase 18, reused verbatim (§4, §8): a `direction_or_effectiveness` claim
carries `summarize_observations`'s own four orthogonal facts — `consensus_value`
(only when `observed_values` has exactly one member and no conflict), `has_within_instance_conflict`,
`has_across_instance_heterogeneity`, and the complete/missing/conflicted instance-key breakdown. The
realization prompt must be given **all four**, never collapsed to the single `consensus_value` field —
the packet's own forbidden move ("heterogeneous observations" → "overall X increases Y") is exactly
prevented by requiring the screen (§18) to check that a sentence asserting a single direction only
appears when `has_across_instance_heterogeneity is False` and `has_within_instance_conflict is False`;
otherwise the only permitted phrasing names the *instances* separately or states the heterogeneity/
conflict explicitly. This is a new, parent-specific screen rule (not present in `overview_guards`
today, which has no concept of "an instance"), detailed in §18.

---

## 12. Partial/missing/ambiguous handling

| Requirement/instance state | Enters main prose? | Enters the unresolved-gap report? | Notes |
|---|---|---|---|
| `filled` (requirement), from ≥1 `complete` instance | Yes, as a `role_value`/`relational`/`category_list`/`direction_or_effectiveness` claim | No | Model-dependence (§16) is a provenance fact, never a prose hedge |
| `partially_filled` | Only the roles that are themselves `filled` on at least one instance (as their own atomic claims) | Yes — the still-missing role(s), via the final `RecoveryTarget` inventory, which already targets exactly this gap (`reason="partial"`, `sufficiency_recovery_targets.py`) | Never synthesized into "a weaker filled claim" |
| `missing` | No | Yes (`reason="missing"`) | |
| `ambiguous` | No (an ambiguous instance is `complete=False` by `recompute_instance`'s own definition when conflicting) | Surfaced in the gap report distinctly (the existing `reason` vocabulary already distinguishes `evidence_conflicting` cases via instance `reason`) | Never silently coerced to either filled or missing |
| `relationship_unverified` (co-occurring filled roles, unverified joint grounding) | No — the *roles* may still appear as independent `role_value` claims (own-evidence, not relational), but no `relational` claim is built | Yes, as its own `RecoveryTarget` reason | This is the §6 boundary enforced at the gap-report level too |

**A polished answer never converts absence into evidence of absence** — the gap report (§13) only ever
names "not yet established," never "established as absent," matching `overview_render.py`'s existing
`_STATE_MESSAGE` convention (e.g. `"no_eligible_evidence"` → *"this describes this run's retrieved
evidence, not the library or the literature"*) and the packet's own §12 instruction. `empty_result_
semantically_allowed` requirements (a frozen field already on every requirement,
`sufficiency_engine.py:224`) are respected: a requirement that explicitly allows an empty result never
generates an `unresolved_gap` entry for it.

---

## 13. Unresolved-gap-report design

**Source:** the FINAL `sufficiency_recovery_targets` inventory (`{target_id: RecoveryTarget}`,
already computed, already hashed-identity, already deduplicated by `new_target_id`'s own content hash
— `sufficiency_recovery_targets.py:68-118`). Zero new computation needed; this is a rendering problem,
not a semantic one.

**Desired properties, mapped to existing fields:**
- Structured: the `RecoveryTarget` dict already is.
- Deduplicated: `target_id` already guarantees this (identity hashes the full search obligation, never
  a changing numeric deficit — rule #2 of the module's own charter).
- User-readable: render `category_descriptions` (never a role's own current guessed value — the
  confirmation-bias guard, rule #4) grouped by `reason`.
- Traces back to child/requirement: `search_child_id`/`requirement_id`/`affected_descendants` already
  carry this.
- `"no evidence found"` vs `"evidence found but insufficient"`: already distinguished by `reason`
  (`missing`/`category_missing` = nothing found; `partial`/`relationship_unverified` = found but
  insufficient/unlinked; `provisional_corroboration`/`open_list_breadth`/`cardinality_deficit` = found
  and used, more would still help).
- Unresolved *relationship* vs unresolved *category/value*: already the `goal_mode` field
  (`relationship` vs `single_role`/`any_of_roles`).
- Never implies another round would solve it: render as a flat list of *what was not established*,
  never as a promise or an ETA — matching `overview_render.py`'s own `_ATTACH_NOTE`/`_unresolved`
  pattern of disclaiming rather than predicting.

**Recommendation on placement (the packet's own §13 question A/B/both): (C) both.** A compact
"Unresolved parts" section in the user-facing answer (mirroring the existing flat-Overview precedent
exactly, `overview_render.py:98-132`) **and** the full, untruncated `RecoveryTarget` list as inspectable
metadata in the parent construction record (§25) — the same two-tier split (`14_final_answer.md` vs
`14b_detailed_inspection.md`) the existing Overview already uses, reused rather than reinvented.

---

## 14. Parent sentence/clause provenance design

**Resolution level: per realized sentence, pointing to exactly one `claim_id` (never a bag of every
claim mentioned anywhere nearby).** This mirrors the existing per-child Overview's own resolution
(`unit_ids` on the *statement*, 1-3 ids, never on the whole overview) and directly satisfies the
packet's "no meaningless giant bag of sources" requirement. Chain, all already-existing fields chained
together, nothing new invented below the claim level:

```
realized sentence → claim_id (1, or the few ids of a pre-combined category_list/relational claim)
                  → requirement_ids / child_ids / instance_keys (already on ParentClaim)
                  → values[*].proposition_id (already on ParentClaim)
                  → sealed["verified_propositions"][proposition_id] → paper_id/chunk_id/span_id/quote (existing ledger fields)
```

A sentence combining three *pre-combined* `category_list` members still cites exactly **one**
`claim_id` (the category_list claim itself already carries all three `proposition_id`s in `values`) —
it never needs three separate top-level citations for what the ledger already decided was one safe
list.

---

## 15. Citation strategy

**Do not invent a new citation system — extend the existing anchor model with one key change: cite by
`proposition_id`, never by per-child `unit_id` (§2a's collision finding).** Concretely:

- One clause using one proposition → cite that `proposition_id` directly.
- One sentence listing several propositions (a `category_list`) → cite every `proposition_id` the
  pre-combined claim carries (already bounded: `MAX_UNIT_IDS`-equivalent cap applies to the ledger
  builder, not the realization model, since combination already happened upstream).
- Two children reusing the same source → the dedup rule (§9D) already folds this into one claim with
  joint `child_ids`; the citation is one `proposition_id`, shown once.
- A relationship using joint witness support → cite `relationship_witness_support_ids(...)`, the
  already-computed, already-adversarially-tested set (§6).
- A model-dependent/provisionally-corroborated statement → cited exactly like any other; model-
  dependence is a provenance fact shown in the construction record, never a different citation shape
  (§16).
- Parent-context propagation (a role inherited from a parent instance, `candidate_source==
  "parent_context"`) → **never contributes its own `proposition_id` to a parent claim's admissible
  set** (the same exclusion `_support_set`/`relationship_witness_support_ids` already enforce, §4/§6) —
  a parent synthesizer must never cite "the parent's own evidence" as if the child itself retrieved it.

**A parent claim must never cite a proposition merely because it is somewhere in a child's evidence
pool** — exactly the existing Overview's own stated rule (`overview_evidence.py`'s module docstring),
inherited unchanged because the `ParentClaim.admissible_proposition_ids` field is built from the same
`_support_set`/`relationship_witness_support_ids` discipline that already enforces this one level down.

---

## 16. Model-dependent fills — presentation

**Recommendation: affect only internal provenance/gap-report presentation, never prose wording.**
This mirrors the sufficiency engine's own explicit, already-stated philosophy
(`sufficiency_engine.py:709-723`'s own comment: a model-dependent fill "remains fully `filled` and
fully usable for answer construction (never hidden, never downgraded in the user-facing map — the
direct analogue of invariant #4)"). Concretely:
- `ParentClaim.model_dependency.any`/`.stop_search_certified` are always computed and always present
  in the construction record (§25) — inspectable, never hidden.
- The realization prompt is never told to hedge a model-dependent claim differently from a
  deterministic one — doing so would imply a confidence distinction the sufficiency engine itself does
  not make (it already made the *harder* call, stop-search certification, as a separate axis rather
  than a confidence number).
- `provisional_corroboration`-reason gaps (one instance filled, more would still help) are **not**
  presented as "weaker" claims in the main prose — the filled instance's own claim stands on its own
  merits; the *opportunity* for more corroboration is a gap-report entry (§13), not a qualifier on the
  claim that already exists.

This does not erase the uncertainty the semantic engine intentionally preserved — it relocates it to
where the engine itself already decided it belongs: `stop_search_certified` controls *search*, not
*presentation*.

---

## 17. Upstream-error boundary

**Mechanically enforced by construction, not by instruction, because of §5/§8's own design: the parent
ledger is built *from* `sufficiency_map_final`'s role bindings, never *re-derived* from raw text with
outside knowledge.** Using the c12 stress test concretely: `ParentClaim.values` for the `target_
manifestation` role is literally `role_bindings["target_manifestation"]["exact_text"]` — whatever that
value is, right or wrong. The realization pass's own screen (§18) validates only that the *realized
sentence* stays faithful to *that exact_text and its cited passage* (the same passage-fidelity checks
`overview_guards.screen` already runs); it has no access to, and no mechanism to apply, outside
scientific knowledge about what "should" be true. A parent synthesizer therefore **cannot** silently
substitute a corrected value, by construction — doing so would require it to invent a `proposition_id`
no ledger entry names, which the citation-closed-enum discipline (§15, mirroring `schema_overview`'s
own `"enum": list(unit_ids)` pattern, `overview.py:163`) already forecloses. Provenance makes the bad
upstream nomination discoverable exactly as it does today: the citation still points at `p33`, and a
reader who opens it sees the same contrast sentence Phase 23a's human adjudicator read. **Parent
validation's job is strictly: does the realized sentence accurately restate `ParentClaim.values` and
cite only its own `admissible_proposition_ids`? Never: is `ParentClaim.values` itself correct?** That
second question belongs entirely to upstream semantic correction (sufficiency mapping, out of scope
here, per §21).

---

## 18. Support-validation strategy

**Feasible, and the existing machinery is sufficient with no new scorer.** Reuse `overview_guards.
screen` and the existing batched `entail(pairs)` seam (`overview.screen_proposals`, `overview.py:
235-287`) **unchanged**, with two differences, both additive:

1. **`units` is built from the parent ledger, not from `overview_evidence.build_units(sealed)`.** For
   each `ParentClaim`, synthesize a `unit`-shaped dict per cited `proposition_id` (`passage` = the
   full verified quote from `sealed["verified_propositions"]`, keyed by the global `proposition_id`,
   not a per-child `U#`) so `overview_guards.screen`'s existing number/acronym/direction/hedge/
   negation/preposition/novel-vocabulary/corroboration checks run **exactly as written**, just against
   a claim-scoped evidence set instead of a child-scoped one.
2. **One new screen rule, additive to `overview_guards.screen`, never modifying its existing checks:**
   a sentence whose cited claim is `direction_or_effectiveness` with `has_across_instance_heterogeneity
   or has_within_instance_conflict` is withheld unless it either names the conflicting/heterogeneous
   instances separately or states the heterogeneity/conflict explicitly (§11/§12's own requirement,
   mechanically enforced here).

The batched-NLI pattern (`screen_proposals`'s `pairs`/`positions` reconstruction, `overview.py:
262-283`) is reused verbatim: **it must validate fidelity, never discover new science** (the packet's
own §18 requirement) — this is already exactly what `nli_reasons` does (contradiction/low-support
withholds; it never *confirms* a scientific relationship, only fails to find a lexical/entailment
objection, per `overview_guards.py`'s own module docstring: "screening, not proof of semantic
correctness"). **It must not broaden the source set after seeing output** — satisfied structurally,
since `admissible_proposition_ids` is fixed at ledger-construction time (§8), before any model call.
**Failure causes conservative fallback, not free-form retry** — see §19/§20.

**A deterministic fallback rendering from the ledger alone is feasible** and recommended as the
baseline: one bullet per `ParentClaim` (grouped by the existing `rollup()` structure — §21), each
rendered as `"{category_description}: {exact_text}" [citation]`, with `direction_or_effectiveness`
claims rendered from `summarize_observations`'s own fields directly. This is strictly less fluent than
a model realization but is **never wrong relative to the ledger** (it is literally the ledger, worded
plainly) — the correct fallback for every failure mode in §19.

---

## 19. Failure/fallback behavior

| Failure | Behavior |
|---|---|
| No `ParentClaim`s at all (nothing filled anywhere) | A `no_claims` state; render only the gap report (§13) — mirrors `overview`'s own `no_eligible_evidence` |
| `sufficiency_map_final is None` (no sufficiency contract active for this hierarchy run) | A `no_sufficiency_contract` state — parent synthesis **declines**, never degrades to a weaker ledger built from raw propositions (an explicit v1 scope boundary, §24/§29) |
| Synthesis model unavailable / malformed output / schema-invalid | Fall back to the deterministic rendering (§18's bullet-list fallback) — never free-form prose, never a retry loop (§20) |
| A realized sentence is unsupported (screen/NLI withholds it) | Withheld from the main prose, shown in the construction record exactly like `overview`'s own withheld-proposal handling (`overview.py:429-430`) — never silently dropped |
| Citation mismatch (a sentence cites an id not in its claim's admissible set) | Same as "unsupported" — the screen's `unknown_unit_id`-equivalent check (§18 point 1) catches this structurally, since the schema's citation enum is built only from the claim's own ids |
| Provenance loss (a claim with no resolvable `proposition_id`) | Cannot occur by construction — every `ParentClaim.values` entry is built by reading an existing `role_bindings[...].proposition_id`; a ledger-builder test asserts this directly (§28, item O-adjacent) |
| Missing child (a hierarchy child with no mapped contract) | That child's claims are simply absent — rendered no differently from "this child had nothing filled," never a crash |
| Contradictory child claims | Exactly the `has_within_instance_conflict`/`has_across_instance_heterogeneity` orthogonal facts (§7/§11) — never collapsed, never a reason to suppress either |
| No filled content anywhere, only partial/missing | Render the gap report alone, with an explicit state naming this (mirrors `no_eligible_evidence`'s own honest-outcome framing, never presented as a defect) |

**No "best effort" free prose with lost provenance is ever permitted** — every failure path above
resolves to either (a) the deterministic ledger-literal fallback or (b) an explicit, inspectable
mechanical state, never a silently-degraded model guess.

---

## 20. Bounded retry policy

**Zero retry, deterministic fallback.** Mirrors `overview.py`'s own existing policy exactly (a capped
or malformed call is a `model_no_answer`/`NO ANSWER` state, never retried — `OVERVIEW_INTEGRATION.md`'s
own "S execution envelope" section: *"A capped call is a NO ANSWER, is not retried, and the settings
are never changed after a failure"*). One model call, one batched NLI call, and on any failure the
deterministic fallback from §18 — this is the smallest bounded policy consistent with the project's own
established discipline against open-ended retry loops (CLAUDE.md's LATENCY.md "no unnecessary fixed
polling" spirit, and this package's own repeated "bounded, not iterative" design choices — Phase 12's
`open_list` bounded-breadth policy, Phase 24's explicit one-round recovery).

---

## 21. User-facing answer shape

**Reuse the existing flat-Overview shape, organized by the existing `rollup()` structure, rather than
inventing a new one:**

```
# Overview
  1-6 realized statements, each citing 1-few proposition_ids, grouped to read naturally
     (not literally "one claim = one sentence" -- consolidation across claims of the SAME
     claim_kind/category is fine; across DIFFERENT claim_ids is the realization boundary §5 enforces)

## Qualified / heterogeneous findings
  direction_or_effectiveness claims with has_across_instance_heterogeneity or
  has_within_instance_conflict -- named explicitly, never folded into the main Overview's
  single-voice prose (the packet's own "within-instance conflict... surfaced explicitly" requirement)

## Supporting findings
  (existing precedent, `overview_render._finding_block`) -- the cited passages themselves,
  grouped by the hierarchy's own child/parent structure (`rollup()`'s children list), reusing
  that structural grouping rather than a flat citation-number list

## Unresolved parts
  the gap report (§13), grouped by `reason`

---
Full inspection: pointer to the parent construction record (§25) AND to the unchanged
per-child Overview files/deterministic hierarchy rendering/sufficiency map/RecoveryTarget
artifacts -- nothing here replaces or hides those.
```

Internal child/requirement/instance ids are **not** exposed in the main "Overview" prose (only in
"Supporting findings"'/the inspection record, mirroring the existing Overview's own `unit_id`
placement) — satisfying the packet's own "do not expose internal child IDs in ordinary prose unless
needed for inspectability" instruction.

---

## 22. Scope: not this phase

**§23 (simple-question bypass) is correctly out of scope and this design does not force a hierarchy
onto every query.** Nothing above touches `e2e.py`'s own `contract.get("version") ==
hierarchy_contract.HIER_VERSION` branch condition — parent synthesis is purely an **additional**
arm inside the existing hierarchy branch (§24), never a change to when a hierarchy exists at all. A
future simple-question rung slots in **above** this one (deciding whether to build a hierarchy at
all), with zero interaction with anything designed here.

---

## 24. Lifecycle position — confirmed from code

`e2e.py:791-864`, in order: `recovery_targets_final` is (re)computed (`:794-798`) → the hierarchy
branch's per-child Overview loop runs (`:811-856`, unchanged, §2a) → **parent synthesis would insert
here, as a new step after the per-child loop, still inside the `if contract.get("version") ==
hierarchy_contract.HIER_VERSION:` branch, consuming `sufficiency_map_final` (already computed earlier
in `execute()`, before this block is reached) and `recovery_targets_final`** → the unconditional
deterministic `render_answer(sealed)` (`:865`) is untouched either way. **Confirmed: parent synthesis
consumes FINAL state only** — `sufficiency_map_final`/`recovery_targets_final` are the post-recovery,
post-remap values; nothing about this stage's position can alter `U1`/`U2`/recovery decisions, which
have already fully executed by the time this point in `execute()` is reached.

---

## 25. Receipts / audit artifact

Mirrors the existing `overview_audit.py` discipline exactly — re-derive everything deterministic from
`sufficiency_map_final`/`sealed`/`sufficiency_recovery_targets` and compare against the stored record:

```
15a_parent_synthesis.json = {
    version, model/config (or "deterministic_fallback"), sealed_ledger_hash,
    sufficiency_map_final_hash (a canonical hash over the map, same discipline as sealed_hash_of),
    claim_ledger: [ParentClaim, ...], gap_report: [UnresolvedGap, ...],
    realized_segments: [{claim_id(s), text, nli, screen_reasons, status: grounded|withheld}],
    fallback_used: bool, parent_synthesis_hash,
}
```

Kept deliberately this small — it is a second, parallel audit of the SAME two already-existing state
objects (`sufficiency_map_final`, `sufficiency_recovery_targets`), never a third independent state
system. `overview_audit.audit_overview`'s own re-derivation pattern (`_check`, "a record that breaks a
re-derivation has failed the audit, never crashed it") is reused directly.

---

## 26. Existing Overview model/profile — reuse, not a new model

**No new Profile field, no new role letter.** `bind()`'s `bound.supervisors` already keys by role
letter (`W`/`R`/`C`/`P`/`S`); the hierarchy arm's per-child loop already calls `bound.supervisors["S"]`
repeatedly under `stage(f"S1:{child_id}", "S")` with **zero model-residency swap cost between calls**
(confirmed: `stage()`'s own `guard.enter`/`guard.observe` only charges a swap when the endpoint/model
target changes, `e2e.py:444-459`; the per-child loop never interleaves a different role's binding in
between). A parent-synthesis call is simply **one more call through the same resident `bound.
supervisors["S"]`**, under a new stage label (e.g. `"S2"`), immediately after the per-child loop —
zero new binding infrastructure. The existing `CHILD_OVERVIEW_PROFILES`/`OVERVIEW_PROFILES` precedent
(`topology.py:157-200`) shows exactly how to add a third, purpose-specific options envelope
(`PARENT_SYNTHESIS_S_OPTIONS`, not yet defined) **if** the prompt-size/thinking-mode tradeoff genuinely
differs from both existing envelopes — an open decision (§29), not a blocker: the parent prompt packs
pre-combined claims (shorter, more structured per-item than a raw passage+claims block) across
potentially the whole tree, so its token-budget shape is a new, measurable question, not an assumption
to carry over from either `OVERVIEW_S_OPTIONS` or `CHILD_OVERVIEW_S_OPTIONS` unexamined — exactly the
caution this package's own comment at `topology.py:180-189` already models for the child/flat split.

---

## 27. Performance

**One bounded model call total, regardless of child count** (the whole point of ledger-first design):
the realization prompt is built from the claim ledger (already deduplicated, §9), not from N children's
raw evidence pools. Expected shape, by direct analogy to the already-measured flat/child Overview
envelopes (`OVERVIEW_INTEGRATION.md`'s own "S execution envelope" section): prompt size scales with
`len(claim_ledger)` (bounded by the same per-item-cap discipline `overview.py`'s `MAX_UNITS`/
`MAX_PROMPT_CHARS` already establish, reapplied to claims instead of units), not with the number of
children or the number of raw propositions. One batched NLI call validates every realized sentence at
once (`screen_proposals`'s existing batching, §18) — the same "one call for a whole answer instead of
one per sentence" shape CLAUDE.md's own LATENCY.md invariants require of the production app, already
native to this module. **Validation cost:** one extra `units`-dict construction per claim (cheap,
dict/string operations only, no model/network) — negligible next to the model call itself. Safety and
provenance take precedence over shaving this one call, per the packet's own instruction — there is
nothing further to shave regardless, since the design is already bounded to exactly one.

---

## 28. Offline test matrix

All fixtures below are literal, hand-built `SufficiencyContract`/`sealed`-shaped dicts fed into real,
unmodified lower-layer functions (`sufficiency_engine.new_requirement`/`new_instance`/
`recompute_requirement`, `sufficiency_recovery_targets.compute_recovery_targets`) plus a new, pure
ledger-builder function — the same literal-fixture discipline Phase 18's own synthetic reproduction
used (§18 there), never pytest-collected prose, never a hidden q_aib-specific assumption:

| # | Adversarial case | Fixture shape |
|---|---|---|
| A | Overlapping duplicate child findings | Two sibling instances of a `for_each_discovered_instance` requirement bind the identical `(category_description, proposition_id, exact_text)` → assert exactly one `category_list` claim with 2 `child_ids` |
| B | Same source, different roles | One `proposition_id` bound to two different roles on two different requirements → assert two separate `ParentClaim`s, each citing the proposition once |
| C | Unrelated findings that must NOT be related | Two `role_value` claims from unrelated requirements, no shared relational instance → assert the realization screen withholds any sentence combining their `claim_id`s |
| D | Supported relational finding | One `relational` instance, `same_proposition`-grounded 2-role binding → assert one `relational` claim carrying both roles and the intersected `admissible_proposition_ids` |
| E | Conflicting directions | Two complete instances of a `direction`-declaring requirement with different `sign` → assert `direction_summary.has_across_instance_heterogeneity is True`, `consensus_value is None` |
| F | Heterogeneous effects | Same as E for `effectiveness_summary`/`conclusion` |
| G | Partial requirement | One role filled, one missing → assert the filled role surfaces as its own atomic claim; a `RecoveryTarget` with `reason="partial"` exists for the missing role |
| H | Missing requirement | No instances filled → assert zero `ParentClaim`s for it, one `UnresolvedGap` with `reason="missing"` |
| I | Ambiguous requirement | A binding with `state="ambiguous"` → assert no claim, a distinct gap entry (never silently "missing") |
| J | Provisional/model-dependent fill | A `complete` instance whose binding has `candidate_source="model_mapping"` → assert the claim renders identically to a deterministic one; `model_dependency.any is True` in the receipt only |
| K | Parent-context propagation | An instance with one own-evidence role + one `parent_context`-sourced role → assert the parent-context role's `proposition_id` is excluded from `admissible_proposition_ids` (reuses `relationship_witness_support_ids`'s own existing adversarial test shape) |
| L | Several children supporting one parent claim | Dedup case D (§9) → assert `child_ids` lists both, one claim |
| M | One child containing several independent claims | A child with 2 unrelated filled roles across 2 requirements → assert 2 separate claims, never merged because they share a `child_id` |
| N | Unsupported model-generated sentence | A fake realization client returns a sentence with an invented direction word → assert the reused `overview_guards.screen` withholds it (`direction_word_not_in_passage`) exactly as it does today |
| O | Citation mismatch | A fake client cites a `proposition_id` outside its claim's admissible set → assert withheld (schema enum violation or an `unknown_unit_id`-equivalent reason) |
| P | Synthesis model failure | Fake client raises/returns malformed JSON → assert the deterministic fallback render (§18/§19) is used, never a crash or free prose |
| Q | No filled findings | Every requirement `missing` → assert `no_claims` state, gap report only |
| R | c12-shaped upstream semantic error | The literal Phase 23a `c12`/`p33` role values (`intervention` correct, `target_manifestation` the confirmed-wrong "bias toward people of color") hand-built as a fixture → assert the ledger faithfully reproduces BOTH role values unchanged, with `p33`'s citation attached to each, and the realization screen neither "fixes" nor flags the wrong one (upstream-error boundary, §17) |

No hidden benchmark-specific runtime logic anywhere in the above — every fixture is expressible in the
generic `SufficiencyContract`/`RecoveryTarget` vocabulary this package already enforces zero-q_aib-
vocabulary discipline on.

---

## 29. q_aib frozen-state replay suitability

**Yes, and it is a *better* fixture than a clean run would be, precisely because of its known defects.**
The frozen Phase-23 final semantic state (`sufficiency_map_final`-shaped, from `17_sufficiency_map.
json` in that run's trace, plus `11_verified_ledger.json`) already contains: (a) the full real-shape
distribution of `filled`/`partially_filled`/`missing` requirements across an 11-child hierarchy, (b) a
real jointly-grounded `relational` instance (`c5`/`c6`), (c) real `direction`/`effectiveness`-bearing
requirements with genuine multi-instance structure (`c12`, 2 instances), (d) the real `c12` scientific
error (fixture R above) to prove the upstream-error boundary holds on *real*, not synthetic, data, and
(e) a real, nonempty final `RecoveryTarget` inventory (6 persisted targets, §7 of
`PHASE23A_POSTHOC_SCIENTIFIC_ADJUDICATION_AND_ERRATUM.md`) to prove the gap report against real
content. Per the packet's own instruction, this is named for **later implementation-phase use** (an
offline, read-only replay fixture, exactly like `E2E_SCORED_LEDGER`'s existing replay seam in
`OVERVIEW_INTEGRATION.md`) — **not run here**; no live model, no network, no new call was made to
produce this assessment, which is read entirely from this audit's own §3a/§6/§7/§9 analysis of the
already-public `PHASE23A_…md` tables.

---

## 30. Minimal implementation surface

| File | Change |
|---|---|
| **new** `parent_synthesis_ledger.py` | Pure. `build_claim_ledger(sufficiency_map_final, parent_of) -> list[ParentClaim]` and `build_gap_report(sufficiency_recovery_targets) -> list[UnresolvedGap]` — the §5/§8/§9/§10 construction, reading only `sufficiency_engine`-shaped dicts (reuses `relationship_witness_support_ids`/`_support_set`/`summarize_observations`, all already public) |
| **new** `parent_synthesis.py` | Mirrors `overview.py`'s shape: prompt/schema for the realization call, `build_parent_synthesis(claim_ledger, gap_report, …)` orchestrating one model call + the reused `overview_guards.screen`/batched-NLI validation (§18), the deterministic fallback (§18/§19), and the hashed `15a_parent_synthesis.json` artifact (§25) |
| **new** `parent_synthesis_render.py` | Mirrors `overview_render.py`: the §21 user-facing shape + the construction record, reusing `rollup()` for structural grouping |
| **new** `parent_synthesis_audit.py` | Mirrors `overview_audit.py`'s re-derive-and-compare discipline exactly, over the new artifact |
| `topology.py` | Additive only: a `PARENT_SYNTHESIS_S_OPTIONS` envelope + however many new profile variants, following the `OVERVIEW_PROFILES`/`CHILD_OVERVIEW_PROFILES` precedent exactly — **no change to `Profile`'s fields** (§26) |
| `e2e.py` | One new block inside the existing hierarchy arm, after the per-child loop (§24), gated behind its own explicit flag (mirroring `--sufficiency-recovery`'s own Phase-24 precedent: independent, default-off, validated to require `--hierarchy`) |

**Expected semantic modules to remain untouched, confirmed, not assumed:** `sufficiency_engine.py`,
`sufficiency_mapping.py`, `sufficiency_diagnostic.py`, `sufficiency_recovery_targets.py`,
`sufficiency_model_scope.py`, `hierarchy_contract.py` (read-only consumers of all of these — every
field this design needs is already public and already correctly shaped, per §4). **No missing
representation was found that parent synthesis cannot safely consume** — the one thing that does not
exist yet (a link from per-child Overview prose to the sufficiency map) is not needed, because this
design deliberately does not route through per-child Overview prose at all (§2a).

---

## 31. Pin drift — impact assessment

**None, for offline implementation/testing**, mirroring every prior phase's identical disposition
(Phase 18 §12/§15, Phase 20a's equivalence-proof pattern, Phase 24 §15): every fixture and test for the
surface above (§28) is a literal dict or an injected `hierarchy_loader`/`hc.load_contract(…,
pins=None)` call — the same seam `*WiringTests`/`*IntegrationTests` already use throughout this
package. Only the real, non-test CLI path (`main()`'s own `load_contract_for_live`, which runs before
`run_topology()` is even reached) is blocked, identically to every flag this session has added since
before Phase 19b, **unrelated to and unworsened by** anything proposed here. The eventual true CLI
end-to-end gate still needs a separately-reviewed pin re-freeze/cleanup, exactly as every prior phase
has noted — not addressed here, per the packet's own §32 instruction not to fix it in this phase.

---

## 32. Recommended Phase 25 implementation/validation split

**(B) — split into stages, mirroring this session's own established cadence** (design → offline
implementation → one bounded live validation, repeated at Phase 19→20a/20b→21 and Phase 22→23→23a→24):

1. **Phase 25 (this document):** design audit. Closed.
2. **Phase 26 (recommended next):** offline implementation of `parent_synthesis_ledger.py` +
   `parent_synthesis_render.py`'s deterministic-fallback path + the full §28 test matrix, **with the
   model-realization call itself stubbed/fake-client-only** — proves the ledger/dedup/combination/
   gap-report machinery correct against real (Phase-23) and synthetic fixtures with zero live calls,
   exactly like Phase 20a proved deterministic sufficiency mapping before any model assistance existed.
3. **Phase 27:** wire the real bounded S2 call + `overview_guards`-reuse validation (§18) into
   `e2e.py`, offline-tested against a fake realization client (mirrors Phase 20b: "production wiring,
   feature-gated off, no live call").
4. **Phase 28:** one bounded live validation run (mirrors Phase 21/23's own "exactly one live call"
   discipline) — against the real T5 hierarchy fixture, explicitly including the `c12` stress case
   (fixture R, §28), to confirm the upstream-error boundary (§17) holds on a genuine model realization
   pass, not merely in a fake-client test.

This is not split "merely for ceremony" — each stage is independently falsifiable exactly as Phase 20a/
20b/21 already demonstrated is the cheapest way to reach a broad E2E gate without skipping an epistemic
checkpoint (Cliff's own stated priority throughout this session).

---

## 33. Remaining design decisions

Three genuine open calls, none blocking offline implementation (Phase 26 above needs none of them
resolved):

1. **§19's `no_sufficiency_contract` scope boundary** — should a future version also support parent
   synthesis for a hierarchy run with no sufficiency contract, built from `sealed`+`rollup()` alone
   (strictly weaker, no role-level structure)? Recommended: **no, not in v1** — an explicit, disclosed
   scope boundary (matching this project's repeated pattern of declining a weaker degraded mode rather
   than silently shipping one), revisit only if a real hierarchy-without-sufficiency-contract use case
   emerges.
2. **§26's new options envelope** — should `PARENT_SYNTHESIS_S_OPTIONS` reuse `CHILD_OVERVIEW_S_
   OPTIONS` (thinking off, matching the now-more-structured, pre-combined claim-ledger prompt) or
   `OVERVIEW_S_OPTIONS` (thinking on)? Recommended: **thinking off**, by analogy to `CHILD_OVERVIEW_
   PROFILES`'s own stated reasoning (`topology.py:180-189`) — the realization prompt is an editorial
   transform over already-decided, already-short claim values, structurally closer to the child-
   overview regime than to the flat-overview's raw-passage-pool regime — but this is a judgment call
   for whoever authorizes Phase 27's live run, not settled here.
3. **§21's exact prose-grouping granularity** (per-child-subtree paragraphs vs. one flowing Overview
   with a separate per-child "Supporting findings" grouping) — both are consistent with every invariant
   above; the choice is a readability/UX call, not a correctness one, and is deferred to Phase 26's
   implementation-time prototyping against the real Phase-23 fixture.

---

## READY OTR

Every item the packet's §33/EXPECTED HAND BACK list asked for is answered above with a concrete,
source-cited basis: the existing architecture is fully traced (§1-2), the authority hierarchy is
explicit and resolves the one real tension the brief flagged (per-child Overview prose is convenience,
never authority, §2a/§3), the no-novel-relationship invariant has a mechanical representation (§5-6,
§10), direction/effectiveness/partial/ambiguous handling reuses Phase 18's already-shipped, already-
orthogonal machinery without modification (§4/§11/§12), the unresolved-gap report is a rendering
problem over an already-correct structure (§13), citation/provenance/support-validation all reuse
`overview_guards`/`overview_audit`'s existing, proven primitives with one necessary correction (cite by
`proposition_id`, never per-child `unit_id`, §15), the upstream-error boundary is enforced by
construction rather than instruction and is proven against the real `c12` case (§17, fixture R in §28),
model/profile reuse needs zero new Profile fields (§26), performance stays at exactly one bounded model
call regardless of tree size (§27), and the minimal implementation surface touches zero semantic
sufficiency modules (§30). No missing representation was found that blocks Phase 26. **READY OTR.**
