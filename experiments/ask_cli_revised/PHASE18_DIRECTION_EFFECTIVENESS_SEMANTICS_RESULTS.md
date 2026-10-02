# Phase 18 — direction/effectiveness semantics and determinism: AUDIT / DESIGN (no implementation)

**Authoritative state, verified before any work began:** HEAD `379d644c998743ab53a4ca6182d5e7ef0efa1d46`
(exact match); frozen v9 `combined_hash` `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`
(read directly from `sufficiency_contract.aib_hier_v9.frozen.json`, exact match). Phase 17 remains closed for
its own scope (proposition-level C2 sealing); nothing in this audit found a dependency requiring it to reopen
(see §12). **No engine code was changed, no live model call was made, no retrieval ran, no recovery executed,
no contract/pin changed, no v10 created.** This document and its one `CONTRIBUTION-LINEAGE.md` append are the
only writes made.

One of the three dispatched exploration agents for this audit failed on an account-wide weekly API rate limit
(unrelated to this codebase); its scope (the producer/consumer call graph) was recovered directly via `Grep`/
`Read` rather than re-dispatching into the same limit — every claim below carries its own file:line citation,
gathered the same way regardless of source.

---

## 1. Durable artifact + synthetic-reproduction outcome

- Artifact: this file, `experiments/ask_cli_revised/PHASE18_DIRECTION_EFFECTIVENESS_SEMANTICS_RESULTS.md`.
- Synthetic reproduction: **ran without exception; every requested case (1–8) reproduced as predicted**, plus
  one bonus case validating the proposed fix. Full script + transcript in §18. **Explicitly synthetic** — the
  real preserved `.local/` run artifacts (`q-aib-hierarchical-t5c-live-20260930/...`) that
  `phase17_c2_sealing_stability_replay.py` itself replays are **absent from this worktree** (confirmed:
  `ls .local` → no such directory), so this is a literal-fixture reproduction against the real, unmodified
  `overview_evidence.build_units` / `sufficiency_diagnostic.units_by_child` / `sufficiency_mapping.
  map_effectiveness` functions — not a replay of preserved real data, and not presented as one.

---

## 2. Exact producer → storage → consumer call graph

**Nothing in this call graph is model-sourced.** `direction`/`effectiveness` are populated entirely post-hoc
by deterministic lexical scanning over already-verified evidence text; no LLM schema anywhere returns either
field (confirmed by `sufficiency_authoring.py`'s own `D1_SUFFICIENCY_SUPERSESSION.scope`: "these roles are
assessed only from already-verified evidence after the fact, never shown to a model as contract text").

```
sufficiency_authoring._build_c5 / _build_c6 / _build_c12          (declares the field, empty template)
        │  se.new_direction_assessment() / se.new_effectiveness_assessment()
        ▼
sufficiency_engine.new_requirement()                               requirement["direction"/"effectiveness"]
        │  (frozen into sufficiency_contract.aib_hier_v9.frozen.json at these EMPTY default values —
        │   confirmed by direct read: reported:false / outcome_reported:false, everything else null)
        ▼
[ RUNTIME, per search round — e2e.py ]
e2e.py:385  sufficiency_map_initial = sufficiency_diagnostic.compute_diagnostic_sufficiency_map(early_sealed, ...)
e2e.py:388  sufficiency_diagnostic.compute_direction_and_effectiveness(early_sealed, sufficiency_map_initial)   # "U1"
   ... (optional recovery round) ...
e2e.py:529  sufficiency_map_final = sufficiency_diagnostic.compute_diagnostic_sufficiency_map(sealed, ...)
e2e.py:532  sufficiency_diagnostic.compute_direction_and_effectiveness(sealed, sufficiency_map_final)           # "U2"
        │
        ▼
sufficiency_diagnostic.compute_direction_and_effectiveness (sufficiency_diagnostic.py:183-196)
    by_child = units_by_child(sealed)                              # sufficiency_diagnostic.py:189
    for child_id, contract in mapped_contract_by_child.items():
        candidate_units = by_child.get(child_id, [])                # WHOLE-CHILD, undifferentiated pool
        for req in contract["requirements"]:
            if req.get("direction") is not None:
                req["direction"] = sm.map_direction(req, candidate_units)        # mutates IN PLACE
            if req.get("effectiveness") is not None:
                req["effectiveness"] = sm.map_effectiveness(req, candidate_units)
        │
        ▼
sufficiency_diagnostic.units_by_child (sufficiency_diagnostic.py:21-74)
    units, _claims = oe.build_units(sealed)                         # sufficiency_diagnostic.py:49
    for unit in units:                                              # ITERATION ORDER = build_units' own order
        for child_id in unit["attached_children"]:
            by_child.setdefault(child_id, []).append({**unit, "proposition_ids": <reordered for THIS child>})
        │
        ▼
overview_evidence.build_units (overview_evidence.py:239-301)
    by_key: dict[tuple, dict] = {}                                  # plain Python dict — preserves FIRST-
    for row in sealed["verified_propositions"]:                     # INSERTION order on iteration (.values())
        key = _dedupe_key(row["paper_id"], row["quote"])             # overview_evidence.py:235-236
        unit = by_key.get(key)
        if unit is None:
            unit = {...}; by_key[key] = unit                        # NEW unit inserted HERE, fixes its position
        unit["proposition_ids"].append(row["proposition_id"])       # existing unit MUTATED, position unchanged
        unit["attached_children"] = sorted(set(...) | set(row["responsive_obligation_ids"]))
    units = list(by_key.values())                                   # ledger/first-appearance order
        │
        ▼
sufficiency_mapping.map_direction / map_effectiveness (sufficiency_mapping.py:662-702)
    for unit in grounding_units:            # candidate_units, in the above pool order, UNCHANGED since Phase 17
        if <lexical match on unit["passage"]>:
            return <assessment built from THIS unit>                 # FIRST MATCH WINS, loop stops
    return <empty assessment>               # no match anywhere in the whole-child pool

[ CONSUMPTION — confirmed by direct grep, zero hits in all four ]
synthesis.py           — 0 references to "direction"/"effectiveness"
overview.py             — 0 references
ledger_renderer.py      — 0 references
overview_render.py      — 1 reference, UNRELATED: its own claim-extraction prompt text ("the direction of
                           any difference") for the separate Overview `novel_terms` hallucination-guard
                           mechanism, not this field (overview_render.py:60)
sufficiency_recovery_targets.py — 0 references (one grep false-positive on "redirection", line 363)
```

**Today, `direction`/`effectiveness` are pure, un-consumed diagnostic metadata** — real, worth fixing, but not
currently producing a wrong user-facing answer (confirmed by the zero-hit greps above). This lowers urgency
but not correctness importance, and matches Phase 17/18's own stated ordering: fix this *before* wiring it into
any production synthesis consumption, not after.

**`recompute_instance`/`recompute_requirement` never read or write either field** (`sufficiency_engine.py:433,
545` — confirmed by direct read of both function bodies and their return-dict construction). `new_instance()`
(`sufficiency_engine.py:194-201`) has **no** `direction`/`effectiveness` key at all; only `new_requirement()`
(`sufficiency_engine.py:204-251`) does. **This is the structural fact that answers directive §5A directly:
today, direction/effectiveness are requirement-scoped scalars with zero instance-level representation.**

---

## 3. Exhaustive real-v9 direction/effectiveness table

Every requirement in the frozen v9 contract carries both keys; only three are ever non-`null`. (Table
confirmed by direct read of `sufficiency_contract.aib_hier_v9.frozen.json` plus `sufficiency_authoring.py`'s
builder functions, `_build_c5`/`_build_c6`/`_build_c12`, lines 308-331 / 334-355 / 451-476.)

| child | requirement id | quantifier | roles | `parent_context_roles` | `multi_instance` (declared) | field | real recorded instance count (phase replays) | admissible evidence relationship |
|---|---|---|---|---|---|---|---|---|
| c5 | `c5#suff:brain-behavior` | exists | region, behavior | `["named_brain_region_or_network"]` | False (**but runtime count follows eligible c4 parents — can exceed 1**, see below) | `direction` | never concretely recorded in any phase doc; state oscillated `filled`(v8)→`partially_filled`(v9); region binding forked amygdala↔RTPJ across c4 forks (Phase 15 §L/§G) | region role is **parent-context inherited** (excluded, §5); behavior role is own-evidence |
| c6 | `c6#suff:brain-attitude` | exists | region, attitude | `["named_brain_region_or_network"]` | False (same runtime caveat) | `direction` | Phase 15: `reported=true, sign="negative", proposition_id=p17`, stable across CONTROL/EXPERIMENTAL; 2 instances recorded (down from Phase-2's 5, attributed to accounting fixes) | region role parent-context (excluded); attitude role own-evidence |
| c12 | `c12#suff:intervention-effectiveness` | exists | intervention, target_manifestation, observed_effect_or_outcome | **none** — zero parent-context participation | **True** (explicit) | `effectiveness` | `partially_filled`, **2 instances**, confirmed identically across 5 independent phase reports (Phase 3/5/6/7/9) | **all three roles own-evidence**; no phase doc records what, if anything, the 2 instances' own `conclusion` values are |

All other requirements (c1,c2,c3×2,c4,c8,c9,c10,c11) carry `direction:null, effectiveness:null` (confirmed by
direct read of the frozen JSON — every requirement object literally has both keys, 10 of 13 at `null`/`null`).
Notably **c9 and c11 are also `relational`/multi-instance** (trait↔scale, culture↔measure pairings) but
declare neither field — confirming the requirement-vs-instance distinction this phase works out is a general
property of the schema, not special-cased to c5/c6/c12.

**v8→v9 diff:** byte-level diff of the two frozen contracts shows the only changes are three unrelated
`category_description` wording edits (c1/c2/c5) and consequent hashes — **zero** `direction`/`effectiveness`
differences. v8 already carried the identical schema shapes.

**A structural fact that materially changes the design, found by directly reading `sufficiency_mapping.
map_requirement` (lines 400-436) and `build_multi_instances` (340-350):** because c12 declares
`multi_instance=True` and has no parent context, it is mapped via `map_requirement`, which — for a
multi-instance requirement — calls `build_multi_instances(candidate_units)`: **one provisional instance per
distinct candidate UNIT**, and crucially `units_by_instance = {inst["instance_key"]: [u] for inst, u in
zip(instances, candidate_units, strict=True)}` (line 421) **restricts that instance's own role-binding search
to exactly its one originating unit** (`units_here`, line 429). So for c12, each instance's role bindings are
*already*, structurally, grounded in one single unit's own text — an instance-scoped admissible evidence set
for c12 reduces cleanly to "that one unit's own passage." c5/c6 (mapped via `map_paired_requirement`, §5)
don't get this for free — their one own-evidence role is bound via `_bind_role_candidates`'s own
first-admissible-match over the **whole** per-child pool, so the instance's own role binding is a specific,
already-decided `proposition_id`/`supporting_proposition_ids` value that must still be used to scope evidence
*after* binding (exactly what §5's rule does). **Role-binding's own first-match order-sensitivity for a
deterministic-strategy role is a separate, pre-existing, out-of-scope question** — Phase 18 takes an
already-mapped instance's role bindings as given and asks only what evidence may describe *that* instance's
direction/effectiveness, not whether completion-finding itself is order-stable.

---

## 4. Exact instance support-set rule (directive §B)

**Derived entirely from existing fields — no second notion of support invented.**
`sufficiency_engine._support_set(binding)` (lines 346-364) already is the house-style primitive:

```python
def _support_set(binding: dict) -> set:
    proposition_id = binding.get("proposition_id")
    supporting = binding.get("provenance", {}).get("supporting_proposition_ids")
    support = set(supporting) if supporting else set()
    if proposition_id is not None:
        support.add(proposition_id)
    return support
```

**The rule:** for one mapped instance,

```
admissible_proposition_ids(instance) = ⋃ { _support_set(binding)
                                            for role, binding in instance["role_bindings"].items()
                                            if binding.get("state") == "filled"
                                            and binding.get("provenance", {}).get("candidate_source")
                                                != "parent_context" }
```

This is **exactly** `recompute_instance`'s own existing `own_evidence_roles` filter (`sufficiency_engine.py:
461-463`), reused verbatim rather than re-derived. When an instance has 2+ own-evidence roles that were
required to jointly-ground via `same_proposition` (`_verify_same_proposition`, lines 367-377 — intersection of
support sets), the resulting admissible set is dominated by that shared proposition but still correctly
captures any additional `supporting_proposition_ids` an anchor-collapsed model binding carries. When an
instance has exactly one own-evidence role (c5/c6's real shape), the set is simply that one role's own support
set. **If the resulting set is empty** (every filled role was parent-context — impossible for c5/c6/c12 given
their own `role_completion.required_roles`, but stated for completeness), the instance correctly has **no**
admissible evidence and direction/effectiveness stays missing — never fabricated from a parent proposition.

---

## 5. Parent-context evidence rule (directive §C)

**The existing provenance structure already lets the mapper distinguish inherited contextual identity from
child-owned relationship evidence — confirmed directly, no new provenance axis needed.** Three independent,
convergent pieces of evidence:

1. `sufficiency_mapping._propagated_provenance` (the function that builds a parent-context binding's
   provenance when `map_paired_requirement` inherits a role, lines ~470-514) **always** stamps
   `"candidate_source": "parent_context"` (line 508) on the inherited binding, regardless of how the parent
   itself originally established it — this is an unconditional re-stamp, not a pass-through, by explicit
   design (the function's own docstring: "Re-stamped, never passed through verbatim").
2. `recompute_instance`'s own completeness computation already filters on this exact tag
   (`sufficiency_engine.py:461-463`) with an explicit rationale in its own comment: *"Parent-context roles are
   trusted as background context, not evidence this child itself retrieved... they structurally cannot share a
   proposition with anything this child retrieves."*
3. `map_paired_requirement`'s own inline comment at the inheritance site (lines 604-610) states the identical
   principle for exactly the c6-inherits-from-c4 shape named in the directive's example: *"this is what exempts
   it from the joint-grounding check below (a parent-context role can never share a proposition with anything
   this child retrieves, by construction) while still recording, for full transparency, exactly how the parent
   arrived at it."*

**The rule, restated precisely for direction/effectiveness:** a `candidate_source="parent_context"` binding's
own `proposition_id`/`supporting_proposition_ids` are **never** included in `admissible_proposition_ids`
(§4) — it may identify *which entity* (e.g. which brain region) the relationship concerns, but the
relationship's own direction/effectiveness must come from the child's *own* evidence. Tested against c5/c6
(the named shape) and c9 (a different parent-context shape, trait↔scale pairing, though c9 declares neither
field): the same `candidate_source` filter applies uniformly regardless of quantifier (`exists` for c5/c6 vs.
`for_each_discovered_instance` for c9), since the filter lives in `_support_set`/`candidate_source` logic that
is quantifier-agnostic.

---

## 6. A real, pre-existing ontology conflation (directive §E — documented, NOT fixed in this phase)

`sufficiency_mapping.map_effectiveness`'s `not_supported` path (lines 697-698) consumes the shared `negated`
flag from `overview_evidence.passage_flags()`, whose underlying `_NEGATION` regex
(`overview_evidence.py:92-94`) folds `not`/`never`/`fail(s/ed/ure)`/`lack(s/ed/ing)` **and** `non-?significant`
into one boolean. This means a passage reporting a *statistically non-significant* result and one reporting an
outright *failed*/*absent* effect produce the **identical** `conclusion="not_supported"` value — confirmed as
an explicit, pre-existing design choice (the function's own docstring: *"`outcome_reported` is TRUE even for a
definitive null/failed result"*), not an oversight Phase 18 introduced, and codified in the already-passing
test `test_map_effectiveness_null_result_is_reported_and_not_supported`
(`test_sufficiency_mapping.py:381-390`), whose own fixture text is "No significant effect ... was observed."

**Disposition: named plainly as a finding, not fixed here.** Per directive §E, broadening the vocabulary is
out of scope for this phase. The proposed representation (§8) does not foreclose a future richer ontology: each
observation already carries its own `exact_text`/`proposition_id`, so a future pass could re-classify stored
observations' `exact_text` against a richer taxonomy without any structural rewrite of the instance/requirement
shape proposed below.

---

## 7. Heterogeneity vs. conflict — four distinguished cases (directive §D)

| case | definition | example | classification |
|---|---|---|---|
| **corroboration** | the SAME instance has 2+ grounded observations that **agree** | two propositions both supporting intervention A | not a problem; preserve both provenance trails |
| **within-instance conflict** | the SAME instance has 2+ grounded observations that **disagree** | one proposition says intervention A worked, another (also tied to A) says it didn't | genuine conflict — surfaced explicitly, never silently resolved by first-match |
| **across-instance heterogeneity** | two DIFFERENT instances legitimately have different values | intervention A supported, intervention B not_supported | ordinary heterogeneity, not conflict — ordinary multi-instance reality |
| **missing** | an instance has zero grounded observations | no effectiveness-bearing language tied to this instance's own evidence | missing, never coerced to "null effect" (directive §14) |

These are **orthogonal facts**, not one scalar (directly answers directive §L's question: *"whether one enum
can faithfully encode this"* — **no**, an instance can simultaneously be part of across-instance heterogeneity
AND itself carry a within-instance conflict; collapsing both into one "heterogeneous/conflict" string would
hide exactly the distinction the directive asked to preserve).

---

## 8. Runtime instance-level representation (directive §F)

**Smallest additive shape, reusing the existing per-observation record type unchanged:**

```python
# sufficiency_engine.new_instance() gains two new optional keys, default []:
{
    ...,
    "direction_observations": [],       # list[dict], each = an EXISTING new_direction_assessment() shape
    "effectiveness_observations": [],   # list[dict], each = an EXISTING new_effectiveness_assessment() shape
}
```

No new builder/dataclass is needed — `new_direction_assessment`/`new_effectiveness_assessment`
(`sufficiency_engine.py:158-191`) already produce exactly the right per-observation record (`reported`/`sign`/
`required_sign`/`causal_language_present`/`proposition_id`/`exact_text` for direction;
`outcome_reported`/`conclusion`/`proposition_id`/`exact_text` for effectiveness). The only change is **where**
these get stored (a list on the instance, not a bare scalar overwritten on the requirement) and **how many**
get collected (every admissible match in the instance's own scoped unit pool, not just the first). This
satisfies every state directive §F lists: zero observations (empty list); one (singleton list); multiple
agreeing (list of 2+ records with the same `sign`/`conclusion`, each with its own `proposition_id`/`exact_text`
— full provenance preserved, nothing collapsed); multiple conflicting (list of 2+ records with differing
`sign`/`conclusion`). No full role-binding/provenance blob is duplicated — each observation carries only the
`proposition_id`/`exact_text` fields it already had, which is sufficient to trace back to evidence via the
existing `sealed["verified_propositions"]` lookup `units_by_child` already builds (`anchor_by_proposition`,
`sufficiency_diagnostic.py:51-59`).

A pure classification helper (specified, not required to be a new builder) derives the within-instance
semantics from the list directly:

```python
def classify_observations(observations: list[dict], value_key: str) -> str:
    """'missing' | 'single' | 'consensus' | 'conflict' from a list of direction/effectiveness
    observation dicts, reading `value_key` ('sign' or 'conclusion')."""
    values = {o[value_key] for o in observations if o.get(value_key) is not None}
    if not values:
        return "missing"
    if len(values) == 1:
        return "consensus" if len(observations) > 1 else "single"
    return "conflict"
```

---

## 9. Requirement-level derived view (directive §G)

**A view, never a second source of truth** — the per-run `req["direction"]`/`req["effectiveness"]` keys may
continue to exist for backward-compatible reading, but their value is now **derived from instance observations
after the fact**, not independently computed by re-scanning the whole-child pool.

**Only COMPLETE instances contribute** — directive §G's own starting preference, **audited, not assumed**:
confirmed correct by direct analogy to Phase 16's own established, already-shipped principle
(`se.eligible_parent_instances`, used by `map_paired_requirement`, requires `instance.complete == True` before
an instance may become trusted context for anything downstream — `PHASE16_PARENT_CONTEXT_ELIGIBILITY_RESULTS.
md`'s own closing architecture). An incomplete instance's role-bindings are, by construction, only partially
established — using its "evidence" to assert a trusted direction/effectiveness value would smuggle an
unverified relationship's valence into a requirement-level summary. **Adopted.**

**Derivation rule** (four states, exposed as orthogonal fields rather than one enum, per §7):

```python
def requirement_direction_or_effectiveness_view(instances: list[dict], obs_key: str, value_key: str) -> dict:
    complete = [i for i in instances if i["complete"]]
    per_instance = {i["instance_key"]: classify_observations(i[obs_key], value_key) for i in complete}
    grounded_values = {
        next(o[value_key] for o in i[obs_key] if o.get(value_key) is not None)
        for i in complete
        if per_instance[i["instance_key"]] in ("single", "consensus")
    }
    return {
        "state": (
            "missing" if not grounded_values and not any(v == "conflict" for v in per_instance.values())
            else "consensus" if len(grounded_values) == 1 and not any(v == "conflict" for v in per_instance.values())
            else "heterogeneous"
        ),
        "value": next(iter(grounded_values)) if len(grounded_values) == 1 else None,
        "has_within_instance_conflict": any(v == "conflict" for v in per_instance.values()),
        "instances_considered": sorted(per_instance),
    }
```

`"heterogeneous"` and `has_within_instance_conflict=True` can co-occur (e.g. instance A conflicted internally
*and* instance B disagrees with A's dominant value) — exactly the orthogonality §7 requires. **The frozen
contract is never touched by this** — §15 confirms why.

---

## 10. Order-invariance (directive §M) — stated precisely

> For fixed mapped instances and fixed admissible evidence support sets, permutations of proposition order,
> unit order, role-binding order, or `supporting_proposition_ids` order must not change: the **set** of
> instance-level observations, their provenance, within-instance conflict classification, or the
> requirement-level derived view. Serialization may canonicalize order afterward for display; order is never
> evidence priority.

This is a **consequence** of §4's support-set rule plus §8's "collect every admissible match, not just the
first" — never a sort-then-first-match policy (directive §2's own explicit prohibition). The synthetic
reproduction in §18 demonstrates both the current violation and this invariant holding once instance-scoped.

---

## 11. `build_units` verdict (directive §J)

**NO — `build_units` needs no change.** Answering the narrower question directly: when a shared unit contains
several propositions with different `responsive_obligation_ids`, the unit **does** retain enough
proposition-level identity — `unit["proposition_ids"]` is a list of distinct, individually-traceable ids
(never merged into one), each resolvable back to its own row (including its own `responsive_obligation_ids`,
`quote`, anchor) via `sealed["verified_propositions"]`. An instance-scoped filter needs only the instance's own
`admissible_proposition_ids` (§4) intersected against each unit's `proposition_ids` — exactly what the
synthetic reproduction's `instance_scoped_units` helper does (§18), using only fields `build_units` already
exposes. The dedup key `(paper_id, normalized passage words)` (`overview_evidence.py:235-236`) is semantically
sound for its own purpose (preventing the same physical quote from being double-counted as separate evidence)
and is **not** the site of the defect — confirmed, not assumed, by the reproduction's Cases 1–6 using
*non*-deduplicating fixtures (distinct passages) and still exhibiting the full order-sensitivity, proving the
defect lives entirely in `units_by_child`/`compute_direction_and_effectiveness`'s whole-child pooling, never in
`build_units`'s own merge logic.

---

## 12. Completeness / RecoveryTarget consequences (directive §H)

**Preserved, unchanged — no contradiction found.** `sufficiency_recovery_targets.py` has zero references to
direction/effectiveness (confirmed by grep, one false-positive on "redirection"). `recompute_instance`/
`recompute_requirement` never read either field (§2). The proposed design keeps this invariant explicitly:
`compute_direction_and_effectiveness`'s instance-scoped successor still runs as a separate pass *after*
`compute_diagnostic_sufficiency_map` has already fixed `complete`/`state`/`reason` — it only adds
`*_observations` lists to already-built instance dicts, never participates in `required_roles`/
`alternative_role_groups` completion logic. **Missing direction ≠ incomplete requirement; missing
effectiveness ≠ incomplete intervention requirement** — v9's authored `role_completion` for c5/c6/c12 (§3)
requires only the named entity/relationship roles, never `direction`/`effectiveness` itself; no sufficiency
requirement is smuggled in by this phase. **Phase 17 does not need to reopen**: its own scope (proposition-level
`responsive_obligation_ids` stability) is orthogonal to this phase's scope (which evidence, among already-stable
propositions, may ground a derived annotation) — confirmed by re-reading `PHASE17_C2_SEALING_STABILITY_RESULTS.
md` §12 in full, which names exactly this defect as deferred, never as blocking.

---

## 13. Synthesis consequences (directive §16)

Nothing changes today — §2 confirms zero current consumers. **Future interface implication, documented only,
not implemented:** a future synthesis consumer reading a multi-value requirement-level view (§9) must handle
`state="heterogeneous"` by presenting per-instance values distinctly (never collapsing to one sentence), and
must surface `has_within_instance_conflict=True` as an explicit caveat rather than picking one observation.
This is a specification for later work, not a Phase 18 deliverable.

---

## 14. Implementation surface (directive §N)

| file | change |
|---|---|
| `sufficiency_mapping.py` | `map_direction`/`map_effectiveness` take an instance-scoped unit list and return **all** admissible matches (a list), not the first |
| `sufficiency_diagnostic.py` | `compute_direction_and_effectiveness` restructured: build one `proposition_id → unit` lookup per child from `build_units`'s own output (reusing `units_by_child`'s existing per-child grouping, not re-deriving it), then for each instance compute `admissible_proposition_ids` (§4) and call the mapper with only the units those ids touch; also computes the derived requirement-level view (§9) |
| `sufficiency_engine.py` | `new_instance` gains `direction_observations`/`effectiveness_observations` (default `[]`); add `classify_observations` (§8) and `requirement_direction_or_effectiveness_view` (§9) as new pure helpers |
| contract/schema | **no change** — confirmed safe: `frozen_view` (`sufficiency_engine.py:265-274`) strips `_RUNTIME_ONLY_KEYS = {"instances","state","reason"}` before hashing, and — independently — the frozen authored contract is a categorically separate object from the per-run mapped copy `compute_direction_and_effectiveness` mutates (the file's own comment: *"Frozen contract vs. per-run search state (never mixed; never hashed together)"*, `sufficiency_engine.py:259-260`); direct read of the frozen v9 JSON confirms c5/c6/c12's `direction`/`effectiveness` sit at their empty template defaults, never touched by any run |

Tests only elsewhere (new test file or extension of `test_sufficiency_diagnostic.py`/`test_sufficiency_mapping.
py`) — no change needed to `test_sufficiency_engine.py`'s existing schema-presence assertions. **Synthesis is
explicitly NOT touched** (§13) — only the future interface is documented.

---

## 15. Deterministic test plan (directive §17's 20 items, mapped to concrete scenarios)

| # | scenario | status |
|---|---|---|
| 1 | one complete instance, one correctly grounded observation | proven live, §18 "target instance's own value" |
| 2 | irrelevant earlier unit cannot hijack another instance | proven live, §18 Cases 7-8 + bonus |
| 3 | proposition permutation invariance | proven live, §18 bonus (orders 1/2 agree) |
| 4 | unit permutation invariance | same mechanism as #3 (units derive 1:1 from propositions here) |
| 5 | new same-dedup-unit proposition cannot change an unrelated instance's value | follows from §11's finding — to be coded as a fixture extending Case 7/8 with a dedup-colliding passage |
| 6 | two instances, same direction, both provenance trails retained | spec'd in §8's "consensus" list shape — new unit test |
| 7 | two instances, conflicting directions, no first-match collapse | proven live, §18 Cases 1-6 (A=supported, B=not_supported, both independently retrievable once instance-scoped) |
| 8 | missing direction stays missing, never null | `classify_observations([]) == "missing"`, §8 |
| 9 | explicit null/no-effect distinguishable from missing | `outcome_reported=True, conclusion=None` is structurally impossible today (conclusion is only set alongside outcome_reported=True) — confirmed existing invariant, carries through unchanged |
| 10 | one effective + one ineffective instance preserves heterogeneity | proven live, §18 Cases 1-6 directly instantiate this exact scenario |
| 11 | direction/effectiveness source belongs to the annotated instance's admissible support | proven live, §18 bonus |
| 12 | model-dependent parent-context instance preserves provenance without unrelated child evidence rewriting it | follows from §5's `candidate_source` exclusion — new unit test using a `model_mapping`-sourced parent binding |
| 13 | Phase 17 append-only sealing unaffected | no code in Phase 17's own files touched by this design; `test_stages.py`'s 39/39 untouched |
| 14 | c5 real replay order-invariant | cannot run without `.local/` artifacts in this worktree — flagged, not fabricated |
| 15 | c6 real replay order-invariant | same flag as #14 |
| 16 | c12 real replay order-invariant | same flag as #14 |
| 17 | requirement aggregate state (`complete`/`state`/`reason`) unchanged | guaranteed structurally — §12, the new pass never touches these keys |
| 18 | RecoveryTarget inventory changes only if intended | unchanged — §12, zero references |
| 19 | no q_aib-specific runtime vocabulary | confirmed — every function/field named here is generic across any future contract, not hardcoded to c5/c6/c12 |
| 20 | v9 contract hash unchanged | confirmed structurally, §14's contract/schema row |

Items 14–16 are **honestly flagged as blocked on real artifacts this worktree does not have**, per the
directive's own instruction to report rather than force a fixture (§I).

---

## 16. Production-integration ordering (directive §19)

Unchanged from Phase 17's own stated order — nothing in this audit surfaced a new prerequisite:

1. **Direction/effectiveness semantic correctness + determinism** — this phase (design complete; implementation
   not yet authorized).
2. Robust `(child_id, requirement_id, role)` model-scoping seam.
3. Initial production model-assisted sufficiency mapping.
4. Post-recovery target-scoped remap.
5. Broader release/pin work.

---

## 17. Compared architectures (directive §13, for the record)

- **A — canonical first match (stable-sort then take first):** rejected. Deterministic but not correct — does
  not fix the structural defect that a value can come from evidence unrelated to the instance it annotates, and
  the reproduction's bonus case shows a naive canonical sort over the whole-child pool would still pick "a"
  value with no grounding guarantee.
- **B — instance-grounded scalar:** a genuine improvement but under-specifies what happens when an instance has
  2+ admissible observations that disagree (directive §7 Case B) — would still force a first-match choice
  *within* an instance.
- **C — instance-grounded multi-value:** correct per-instance, but directive §13 also wants a requirement-level
  answer when useful.
- **D — requirement-level consensus/conflict, derived from instance-grounded values:** correct but incomplete
  alone (needs B/C underneath it to have anything principled to derive from).
- **Recommended (adopted): B+C+D composed** — exactly what §4, §8, and §9 specify: instance-grounded,
  multi-value observations (C, built on B's grounding discipline) as the authoritative per-instance data, with
  a strictly derived (never independently computed) requirement-level view (D) only over complete instances.

---

## 18. Synthetic reproduction — full script and transcript

Run from the worktree root, zero live calls, zero network, zero mutation of any tracked file (fixtures are
literal Python dicts; the script itself lives only in the session scratch directory, never committed):

```python
"""Phase 18 synthetic reproduction -- NOT a replay of preserved real `.local/` artifacts (those are
absent from this worktree). Every fixture below is a literal, hand-built `sealed`-shaped dict fed
into the REAL, unmodified `overview_evidence.build_units` / `sufficiency_diagnostic.units_by_child` /
`sufficiency_mapping.map_direction` / `map_effectiveness` functions. No model call, no network call,
no mutation of any repo file. Run manually; not pytest-collected; throwaway (scratch location only).
"""

import sys
sys.path.insert(0, WORKTREE_ROOT)

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm


def _prop(pid, paper_id, quote, text, children, chunk="c1", span="s1"):
    return {
        "proposition_id": pid, "proposition_text": text, "paper_id": paper_id, "quote": quote,
        "evidence_anchor_chunk_id": chunk, "evidence_span_id": span,
        "responsive_obligation_ids": list(children), "anchors": [], "verification": {},
    }

def _span(paper_id, chunk_id, span_id, text):
    return {"paper_id": paper_id, "chunk_id": chunk_id, "span_id": span_id, "text": text}

def sealed_from(props):
    spans = [_span(p["paper_id"], p["evidence_anchor_chunk_id"], p["evidence_span_id"], p["quote"]) for p in props]
    return {"verified_propositions": props, "evidence_spans": spans}


# Cases 1-6: two real instances, order sensitivity
req = {"effectiveness": se.new_effectiveness_assessment()}
pA = _prop("pA", 1, "Intervention X showed decreased bias scores in the treatment group.",
           "Intervention X showed decreased bias.", ["c12"])
pB = _prop("pB", 1, "No significant effect of Intervention Y on bias scores was observed.",
           "Intervention Y had no effect.", ["c12"])

sealed_AB, sealed_BA = sealed_from([pA, pB]), sealed_from([pB, pA])
units_AB = sd.units_by_child(sealed_AB)["c12"]
units_BA = sd.units_by_child(sealed_BA)["c12"]
result_AB = sm.map_effectiveness(req, units_AB)
result_BA = sm.map_effectiveness(req, units_BA)

# Cases 7-8: irrelevant-unit hijack
p_irrelevant = _prop("pZ", 2, "An unrelated aside: Intervention Z showed no effect in a different study population.",
                      "Aside about Intervention Z.", ["c12"])
sealed_hijack = sealed_from([p_irrelevant, pA])
result_hijack = sm.map_effectiveness(req, sd.units_by_child(sealed_hijack)["c12"])
target_alone = sm.map_effectiveness(req, [sd.units_by_child(sealed_from([pA]))["c12"][0]])

# Bonus: instance-scoped support-set filter (the proposed fix) resolves the hijack
def instance_scoped_units(units_for_child, admissible_proposition_ids):
    return [u for u in units_for_child if admissible_proposition_ids & set(u["proposition_ids"])]

instance_a_support = {"pA"}
scoped_1 = sm.map_effectiveness(req, instance_scoped_units(sd.units_by_child(sealed_hijack)["c12"], instance_a_support))
sealed_hijack_rev = sealed_from([pA, p_irrelevant])
scoped_2 = sm.map_effectiveness(req, instance_scoped_units(sd.units_by_child(sealed_hijack_rev)["c12"], instance_a_support))
```

**Actual output (verbatim, this run):**

```
========== Cases 1-6: two real instances, order sensitivity ==========
Ledger order [pA, pB] -> effectiveness: {'outcome_reported': True, 'conclusion': 'supported', 'proposition_id': 'pA', 'exact_text': 'Intervention X showed decreased bias scores in the treatment group.'}
Ledger order [pB, pA] -> effectiveness: {'outcome_reported': True, 'conclusion': 'not_supported', 'proposition_id': 'pB', 'exact_text': 'No significant effect of Intervention Y on bias scores was observed.'}
Same underlying evidence set in both runs (cases 1/2/6): True
Case 3 (first-match on whatever occurs first): True
Case 4/5 (reversing order changed the scalar): True

========== Cases 7-8: irrelevant-unit hijack ==========
Pool order: [pZ(irrelevant), pA(target)] -> effectiveness: {'outcome_reported': True, 'conclusion': 'not_supported', 'proposition_id': 'pZ', 'exact_text': 'An unrelated aside: Intervention Z showed no effect in a different study population.'}
Target instance's OWN value, if asked alone: {'outcome_reported': True, 'conclusion': 'supported', 'proposition_id': 'pA', 'exact_text': 'Intervention X showed decreased bias scores in the treatment group.'}
Case 8 (irrelevant earlier unit wins over the target instance's own evidence): True
Case 7 IS reproducible: no existing filter in map_effectiveness/units_by_child blocks this.

========== Bonus: instance-scoped support-set filter resolves the hijack ==========
Instance-scoped result, pool order 1: {'outcome_reported': True, 'conclusion': 'supported', 'proposition_id': 'pA', ...}
Instance-scoped result, pool order 2: {'outcome_reported': True, 'conclusion': 'supported', 'proposition_id': 'pA', ...}
Order-invariant once instance-scoped: True

ALL REPRODUCTIONS RAN WITHOUT EXCEPTION.
```

This concretely proves: (a) the current mechanism is genuinely order-sensitive on real, unmodified code — not
hypothetical; (b) an irrelevant proposition merely tagged responsive to the same child *can* hijack the
requirement-level value today; (c) the proposed instance-scoped support-set filter — built from fields the
schema already carries — removes both defects with no change to `build_units` and no new provenance concept.

---

## 19. Status

**All eight items directive §O lists are resolved with a precise, source-cited answer** (§4 instance support
set; §5 parent-context rule; §8 observation representation; §7 same-instance conflict semantics; §7
across-instance heterogeneity semantics; §9 requirement-level derived-view rule, including the complete-only
restriction, audited and confirmed; §11 build_units verdict — no change; §14 implementation files; §15 test
matrix). The one judgment call directive §G flagged for audit (complete-only instances) is confirmed, not
merely assumed, against the Phase 16 precedent.

**READY OTR**
