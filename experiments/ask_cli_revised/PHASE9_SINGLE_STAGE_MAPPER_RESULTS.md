# Phase 9 — single-stage minimal-referent mapper + provisional stop-search policy (2026-09-30)

**Scope:** implement Phase 8's forensic recommendation as a bounded mapper/recovery-safety
redesign. No live model calls anywhere in this phase. No contract version change — v9 remains
byte-identical throughout. Recovery stays OFF. This is implementation + offline validation only.

## Commits

Not yet committed at the time this report was drafted — committed together with this report and
the lineage append at the end of this phase's hand-back (see the final commit list in the reply).

## Final HEAD

See the final commit in the reply (this report is committed in the same commit as the code).

## Files changed

| File | Change |
|---|---|
| `qwen.py` | Reformulated `nomination_prompt` (minimal-referent extraction); deleted `specificity_prompt`/`specificity_schema`/`_validate_specificity_decisions`/`_SPECIFICITY_*` constants/`QwenTasks.verify_specific_instances` |
| `sufficiency_mapping.py` | Deleted `confirm_specific_instances`; `_bind_role_candidates`'s model branch reverted to single-stage (nomination → grounding/admissibility → RoleBinding) |
| `sufficiency_engine.py` | Added `_instance_completion_is_model_dependent`, `_STOP_SEARCH_AGGREGATORS`, `compute_stop_search_certified`; `compute_recovery_needed` now consults it within its `filled` branch |
| `sufficiency_model_nomination_diagnostic.py` | Removed dead `verify_specific_instances` from `_NullModelClient`/`_LiveQwenModelClient` |
| `sufficiency_phase2_replay.py` | Removed dead `verify_specific_instances` from `RecordedNominationClient` |
| `sufficiency_phase5_replay.py` | Redesigned `_Phase5AdjudicationValidator` to filter inline inside `nominate_sufficiency_role` (self-contained; no longer depends on the retired gate code); docstrings updated |
| `test_sufficiency_diagnostic.py`, `test_sufficiency_mapping.py` | Removed dead `verify_specific_instances` fakes |
| `test_sufficiency_engine.py` | Added `StopSearchCertificationTests` (8 tests, Part F) |
| `test_sufficiency_leakage.py` | Removed `SpecificityPromptLeakageTests` (tested deleted code); added `ReformulatedNominationPromptLeakageTests` (2 tests, Part I) |
| `test_sufficiency_specificity_gate.py` | **Deleted** — tested code that no longer exists; its 21 tests' forensic value is preserved in git history (`8bf203b2`) and the Phase 6/7 markdown reports |
| `sufficiency_phase9_counterfactual_replay.py` | **New** — the Part H counterfactual scripted fixture |
| `test_sufficiency_phase9_counterfactual_replay.py` | **New** — 10 tests locking in its result |

## A. Disposition of `confirm_specific_instances` and the Phase 6/7 gate

**Fully retired from the active mapping path, not merely disabled.** `qwen.specificity_prompt`,
`qwen.specificity_schema`, `qwen._validate_specificity_decisions`, `qwen.QwenTasks.
verify_specific_instances`, and `sufficiency_mapping.confirm_specific_instances` are **deleted**
from the live tree — there is no flag, kwarg, or conditional branch anywhere that can reach them;
"conditionally active" was explicitly ruled out by the authorization, so a retained-but-flagged
design was rejected in favor of outright deletion. `_bind_role_candidates`'s model branch is now:

```python
nominations = nominate_with_model(role_spec, units, model_client)
bindings = []
for nomination in nominations:
    ...  # build a RoleBinding directly, no second call
```

**Historical reproducibility is preserved without any live dependency on the deleted code.**
`sufficiency_phase5_replay.py`'s scripted validator was redesigned to apply Cliff's own frozen
Phase 6 adjudication *inline*, inside its own `nominate_sufficiency_role` — filtering the inner
recorded client's raw nominations before returning them, rather than via a second
`verify_specific_instances` call. From today's single-stage engine's perspective this is
indistinguishable from any other model client returning a shorter list; `test_sufficiency_phase5_
replay.py`'s 5 tests (none of which ever asserted on the now-removed `specificity_validated_
instance_text`/`specificity_model` provenance keys) pass unchanged, proving the historical finding
(Phase 6 Part F: c2 drops from Phase 5's `filled`/3 to `partially_filled`/2) still reproduces
byte-for-byte through the new architecture.

The exact retired specification (prompt text, schema, fail-closed rules) remains fully preserved
in git history (`f0814716`, `8bf203b2`) and verbatim-quoted in `PHASE6_SPECIFICITY_GATE_RESULTS.md`
/`PHASE7_LIVE_TWO_KEY_DIAGNOSTIC_RESULTS.md`, which are **not rewritten**.

## B. Old vs. new nomination prompt

**Old** (Phase 2–7, now deleted):
> Does any excerpt below name a SPECIFIC instance of {category_description}, as opposed to a
> generic/unspecified reference to {category_description}?
>
> For each excerpt that names one, return its id and the exact supporting substring copied
> verbatim from that excerpt. ...

**New** (Phase 9, active):
> For each excerpt below, extract the SHORTEST exact span that itself identifies WHICH specific
> instance of {category_description} is present.
>
> If an excerpt only says or implies that some instance of that category exists, occurred, was
> measured, had an effect, or was associated with something -- without identifying which instance
> -- do not return a nomination for it. The returned span itself must contain the identifying
> information; do not return a larger clause merely because that clause supports the existence or
> effect of the category.
>
> The identifying span does not need to be a proper noun or capitalized, and it does not need to
> be a bare noun phrase -- a specific action or task can be identifying too.
>
> For example: "adolescents in Japan" identifies a specific population; "a population was studied"
> does not. "mindfulness training" identifies a specific intervention; "an intervention reduced
> symptoms" does not. "participants donated less money" identifies a specific behavior; "a
> behavioral effect occurred" does not. A named measurement method or modality identifies a
> specific measurement; "neural activity was measured" does not. "trait anxiety" identifies a
> specific trait; "individual differences predicted the outcome" does not.
>
> An excerpt may identify more than one distinct instance -- return each separately. Do not
> paraphrase. Do not invent an excerpt id. If none qualify, return an empty list.
>
> Return only JSON: {"nominations":[{"proposition_id":"...","exact_text":"..."}]}

**Schema: unchanged.** `nomination_schema`/`_validate_nominations`/`_NOMINATION_OUTPUT_TOKENS`
(256)/`_NOMINATION_EXACT_TEXT_MAX_LEN` (300)/`_NOMINATION_MAX_ITEMS` (8) are all byte-identical to
before — the reformulation is purely instructional, not a schema or output-cap change. One call
per role per candidate batch, exactly as before (never merged across roles).

## C. Deterministic safeguards — unchanged

Confirmed by direct inspection, not merely assumed: `is_admissible`, `canonical_text_contains`
grounding, `nominate_with_model`'s anchor-based dedup/`supporting_proposition_ids` provenance,
`_fork_instances_over_role`/`_rederive_keys_if_forked` instance forking, `_support_set`/
`_verify_same_proposition` joint grounding, `map_paired_requirement` parent propagation, every
`instance_quantifier` aggregator, and `recompute_instance`/`recompute_requirement` final-state
computation are **all textually unmodified** in this phase. The model's only remaining
contribution is a `{proposition_id, exact_text}` pair; it cannot create proposition identity,
decide admissibility, or compute a final state.

## D. Redundancy smell-test — omitted, not implemented

Per instruction, explicitly **not** turned into a hard veto. Considered whether a narrow,
non-authoritative diagnostic signal ("this identification role's `exact_text` is wholly contained
in a sibling evidence role's own `exact_text`") could be safely recorded as metadata only. Declined
to implement even that: defining "sibling evidence role" generically requires knowing which other
role in `completion_roles` is the "occurrence" role for ANY contract shape (not declared anywhere
in the current `RoleSpec`/`RoleCompletion` vocabulary), and the containment check itself needs
canonicalization choices (case, whitespace, punctuation) that cannot be validated without a live
re-test this phase doesn't permit. **Omitted entirely**, per the instruction's own explicit
fallback ("If no robust diagnostic can be defined without brittle heuristics, omit it entirely and
report that decision") — this is that report.

## E. The provisional stop-search rule

`sufficiency_engine.compute_stop_search_certified(requirement) -> bool`:

- Returns `True` (certified, meaningless) whenever `requirement["state"] != "filled"` — only
  consulted within `compute_recovery_needed`'s existing `filled` branch.
- When `state == "filled"`: re-aggregates the SAME instance set `_AGGREGATORS` already computed
  `state` from, but against "is this instance `complete` AND none of its own-evidence completion-
  critical bindings are `candidate_source == "model_mapping"`" instead of "is this instance
  `complete`" — using the identical per-`instance_quantifier` dispatch shape (`exists`: any clean
  complete instance certifies; `all_requested_categories`/`for_each_discovered_instance`: every
  complete instance must be clean; `at_least_n`: at least `n` clean complete instances must exist;
  `open_list`: never applicable, since `_aggregate_open_list` never returns `"filled"`).
- `compute_recovery_needed`'s `filled` branch becomes:
  ```python
  if requirement["state"] == "filled":
      if compute_stop_search_certified(requirement):
          return False
      if search_status.get("breadth_pass_used"):
          return False
      return not budget_spent
  ```
  reusing `open_list`'s own already-existing bounded-breadth `SearchStatus` fields
  (`breadth_pass_used`/`recovery_budget_exhausted`/`scoped_search_completed_no_additional_support`)
  — **no new SearchStatus field was added.**

### How required vs. optional model bindings affect the rule

Only roles in `completion_roles(role_completion)` (required + alternative-group members) are
inspected — `optional_roles` are structurally excluded, exactly as they already are from
`recompute_instance`'s own completeness/joint-grounding logic. A `model_mapping`-sourced binding on
an `optional` role can never make an otherwise-clean deterministic completion provisional
(`test_optional_model_binding_does_not_taint_an_otherwise_deterministic_completion`, passing). A
`parent_context`-sourced binding is also never flagged (by construction its `candidate_source` is
never `model_mapping`), consistent with it being trusted background from an already-computed
parent requirement, not this instance's own search result.

`state` is **never overloaded or written to** by this mechanism — `compute_stop_search_certified`
is a pure, read-only, separately-named query over an already-recomputed requirement; it mutates
nothing and is not part of `frozen_view`/`contract_hash`'s hashed content (proven directly:
`test_search_policy_never_mutates_the_frozen_contract_or_its_hash`).

## F. Provisional stop-search tests (`StopSearchCertificationTests`, 8 tests, all passing)

| Test | Proves |
|---|---|
| `test_deterministic_filled_is_stop_search_certified` | deterministic `filled` → certified, `compute_recovery_needed` → False |
| `test_model_only_filled_is_provisional_for_stop_search` | model-only `filled` → semantic state stays `filled`, but `compute_stop_search_certified` → False; bounded one-attempt recovery, then honest termination |
| `test_mixed_completion_is_provisional_when_the_model_binding_is_required` | a required model-sourced role, jointly grounded with a deterministic one → still provisional |
| `test_optional_model_binding_does_not_taint_an_otherwise_deterministic_completion` | an optional model-sourced role never taints a sufficient deterministic completion |
| `test_missing_and_partially_filled_behavior_is_unchanged` | `compute_recovery_needed`'s pre-existing missing/partial logic is untouched |
| `test_search_policy_never_mutates_the_frozen_contract_or_its_hash` | querying stop-search status, under varying `SearchStatus` values, never changes `contract_hash` |
| `test_answer_rendering_can_still_consume_provisional_filled_content` | a provisional fill's `state`/`exact_text`/`role_bindings` remain fully intact and readable |
| `test_compute_functions_are_pure_and_never_mutate_their_input` | both new functions are side-effect-free |

## G. Reformulated-nominator representability tests (11 tests, all passing)

`ReformulatedNominationRepresentabilityTests` in `test_sufficiency_mapping.py` proves the plumbing
(grounding, schema shape, `map_requirement`'s accept/decline handling) can carry every example from
the authorization's own list, via hand-scripted fake clients:

| Domain | ACCEPT | DECLINE |
|---|---|---|
| Population | "adolescents in Japan" | "A population was studied across several sites." |
| Intervention | "mindfulness training" | "An intervention reduced symptoms significantly." |
| Behavior (clause-shaped) | "participants donated less money" | "A behavioral manifestation occurred." |
| Measurement | "Functional MRI" | "Neural activity was measured." |
| Trait | "trait anxiety" | "Individual differences predicted the outcome." |
| Lowercase common noun | "amygdala" | — |

**Explicitly stated, per instruction: the engine cannot prove the model semantically obeys the
instruction — these are plumbing/schema/grounding tests, not claims about live Qwen performance.**
A real bug was caught while writing these (not a plumbing defect): the "Functional MRI" fixture's
exact_text initially didn't case-match its own passage, silently failing grounding — fixed, and
left as a reminder that `canonical_text_contains` is case-sensitive.

## H. Counterfactual scripted replay (Part H)

`sufficiency_phase9_counterfactual_replay.py` is explicitly labeled, in its own module docstring,
as **NOT a replay of any real model trace and NOT evidence of live Qwen behavior** — a hand-scripted
fixture over the REAL preserved q_aib evidence, keyed by `(category_description, frozenset(full
candidate pool))` (the same collision-safe keying `RecordedNominationClient` already uses, for the
same reason — several real role-calls share identical `category_description` text over different
candidate pools).

**A real collision bug was caught and fixed while building this fixture, not silently avoided**: an
early per-proposition-only keying scheme let a scripted nomination intended for c2's own call leak
into c5's distinct call (which shares both c2's behavior category text and 2 of its 10 propositions
over a larger 16-proposition pool), spuriously completing c5. Documented in the module's own
docstring as a design lesson, matching exactly the shape of Phase 3's own historically-discovered
Finding 2.

### Per-child/state/count outcome (deterministic-only vs. counterfactual)

| Child | Requirement | Det-only | Counterfactual | vs. Phase 5/7's own correct result |
|---|---|---|---|---|
| c1 | neural-manifestation | `partially_filled`, 1 | **`filled`, 1** | Matches (via minimal "amygdala") |
| c2 | behavioral-manifestation | `partially_filled`, 1 | **`partially_filled`, 2** | **No false fill** — circular text never nominated at all |
| c3 | attitude-manifestation | `filled`, 1 | `filled`, 1 | Unchanged |
| c3 | implicit-explicit-coverage | `partially_filled`, 2 | `partially_filled`, 2 | Unchanged |
| c4 | specific-region | `partially_filled`, 1 | **`filled`, 1** | Matches |
| c5 | brain-behavior | `missing`, 1 | `partially_filled`, 1 | Matches (true-negative decline preserved) |
| c6 | brain-attitude | `missing`, 1 | **`filled`, 2** | Matches |
| c6 | implicit-explicit-coverage | `partially_filled`, 2 | `partially_filled`, 2 | Unchanged |
| c8 | trait-construct | `missing`, 1 | **`partially_filled`, 4** | Matches |
| c9 | trait-scale-pairing | `missing`, 0 | **`partially_filled`, 4** | Matches — propagation survives |
| c10 | culture-existence | `missing`, 1 | `missing`, 1 | Unchanged |
| c11 | culture-operationalization-pairing | `missing`, 0 | `missing`, 0 | Unchanged |
| c12 | intervention-effectiveness | `partially_filled`, 2 | `partially_filled`, 2 | Unchanged |

**Every genuinely correct Phase 5/7 finding is reproduced (c1, c4, c6, c8, c8→c9 propagation);
the one false finding (c2) is not** — because the circular text was never even nominated under
the new framing, not because anything vetoed it afterward. `same_proposition` joint grounding
still correctly denies full completion to c2's own surviving (genuine) instances (confirmed:
`inst["complete"] is False` for both), proving Phase 4's fix is untouched, not merely coincidentally
unexercised. Anchor-dedup still collapses c8's duplicate p20/p9 propositions to exactly 4 instances,
never 8.

10 tests in `test_sufficiency_phase9_counterfactual_replay.py`, all passing, lock in this result.

## I. Leakage

`ReformulatedNominationPromptLeakageTests` (2 new tests) proves the reformulated prompt's 5 fixed
cross-domain examples carry no hidden benchmark term, provenance token, or "networks" mention, and
pins the literal "does not need to be a proper noun or capitalized"/"does not need to be a bare
noun phrase" instruction text as a direct regression test for the Phase 8 forensic finding.
`NominationPromptLeakageTests` (pre-existing, now exercising the reformulated prompt) passes
unchanged — the same "Excerpts:\n" split marker survived the reformulation intact.
`SpecificityPromptLeakageTests` (tested deleted code) was removed. v9 is unaffected throughout.

## J. Regression

| Suite | Result |
|---|---|
| Targeted sufficiency suite (11 files incl. all new/changed) | **214 passed** |
| `experiments/ask_cli_revised/contract_directed/` (full) | **619 passed** |
| `experiments/ask_cli_revised/` (full tree, 112 test files) | **2047 passed, 11 skipped, 2 failed — the same 2 pre-existing, unrelated `hierarchy_contract.py` pin-drift failures Phase 6's own full-tree run reported, reproduced unchanged** (confirmed: `git diff HEAD -- experiments/ask_cli_revised/hierarchy_contract.py` is empty — this phase never touched that file). Net count change from Phase 6's 2040: +8 (`StopSearchCertificationTests`) +11 (`ReformulatedNominationRepresentabilityTests`) +10 (counterfactual replay) +2 (`ReformulatedNominationPromptLeakageTests`) −3 (`SpecificityPromptLeakageTests` removed) −21 (`test_sufficiency_specificity_gate.py` deleted) = **+7**, exactly matching 2047. |

## v9 byte-identity confirmation

```
git diff HEAD -- experiments/ask_cli_revised/sufficiency_contract.aib_hier_v9.frozen.json
```
→ empty, both before and after every change in this phase. `combined_hash`:
`9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586` — unchanged. No v10 created.

## Newly discovered issue

A real (test-fixture, not production-code) bug was caught and fixed during construction of Part H's
counterfactual replay: naive per-proposition-only keying in a scripted client can leak a
nomination intended for one child's call into a different child's call that happens to share both
category-description text and some (not all) of the same propositions. This is not a new
production defect (`nominate_with_model`/`_bind_role_candidates` were never affected — they always
received candidates from a real, correctly-scoped call), but a reminder for any FUTURE fixture
author: key a scripted model client by `(category_description, frozenset(full candidate pool))`,
never by proposition_id alone, whenever more than one role-call might share a category description.

## Answers to the three questions

**1. Is the single-stage minimal-referent mapper mechanically ready for ONE separately authorized
live v9 diagnostic?**

Yes, mechanically. The core plumbing (prompt, schema, grounding, forking, propagation, instance-
key derivation) is implemented and tested at 214 targeted + 619 `contract_directed` tests, all
passing, with zero live calls used anywhere in this phase. v9 is unchanged. As with every prior
phase's "mechanically ready" answer, this is NOT a claim that the live model will actually produce
the hoped-for extractions — only that the architecture will correctly carry whatever it returns
through to a correct `RoleBinding` or correctly decline. That question can only be answered by an
actual live run.

**2. Is stop-search authority now safely separated from answer sufficiency?**

Yes, structurally. `state == "filled"` and `compute_stop_search_certified(requirement)` are two
independently computed, independently testable predicates; a model-dependent fill can never by
itself suppress all further search (it earns exactly one bounded recovery opportunity, mirroring
`open_list`'s own already-proven bounded-breadth shape), while remaining fully `filled` and fully
usable for answer construction. This directly addresses Phase 7's own catastrophic-failure concern
(a false fill silently certifying "stop searching") independent of whether the minimal-referent
reformulation itself turns out to be well-calibrated live.

**3. Is there any remaining structural blocker before that live diagnostic?**

None found. The one thing this phase cannot answer — because every test here is either a pure
plumbing proof or a hand-scripted counterfactual, never a live call — is whether `qwen3.5:9b`
actually produces well-formed minimal-referent extractions reliably under the new prompt. That is
exactly what a live diagnostic is for, and per instruction, **it was not run in this phase.**
