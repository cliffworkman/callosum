# PHASE 34 / I4-1g — support_policy + candidate-support schema primitives (results)

**Status: pure, schema-only, unwired.** No `support_policy` gating of any binding, no all-support collection in
`_bind_role_candidates`, no `achieved_outcome_span` consumption, no `assertion_authority` consumption by
production mapping, no `aggregation` consumption by production mapping, no satisfaction/recovery/relation/
direction/effectiveness/AnswerPlan change, no `sufficiency_semantics_version` bump, no `PLAN_VERSION` bump. No
model, network, live search, or live end-to-end run.

- Starting HEAD: `8fe436fc6f3a0bb85ab8558a64cd89e3ec0ea5dd` (I4-1f).
- Branch `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z`, worktree
  `.claude/worktrees/ask-060-hier11-recpm3-citefix-20260929T212442Z`.
- Final HEAD: the commit that carries this increment (see the handback).

---

## 1. Files changed

| File | Change |
|---|---|
| `experiments/ask_cli_revised/sufficiency_engine.py` | Modified (244 insertions, 1 deletion). One new optional `support_policy` keyword on `new_role_spec` (§4); a new, clearly-delimited I4-1g block adding `new_support_policy`/`_canonical_support_policy`, `new_candidate_support`/`new_candidate_supports`, and the two reference-only helpers `reference_future_role_state`/`reference_future_requested_terms_disambiguation` (§3, §6–§10). `new_role_binding`, `new_requirement`, and `new_instance` are **not touched at all** (§2 below). |
| `experiments/ask_cli_revised/test_sufficiency_support_schema.py` | New. The byte-parity gate, every new builder's tests, the §14/§15 directive examples frozen as cases, and the static zero-production-consumption guards. |
| `experiments/ask_cli_revised/PHASE34_I4_1G_SUPPORT_SCHEMA_RESULTS.md` | New: this report. |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | Appended (prior entries unchanged). |

Nothing else changed — confirmed by `git status --porcelain`, which lists exactly these files. `sufficiency_
authoring.py`, `sufficiency_mapping.py`, `sufficiency_recovery_targets.py`, `e2e.py`, and every `answer_plan/`
file are **untouched**: the `requested_category_terms` generalization (§11 of the directive) needed no code
change anywhere, because no existing code restricts that field's presence by `mapping_strategy` in the first
place (confirmed by direct reading — see §9 below).

---

## 2. Backward-compatibility: what was, and was not, touched

**Only `new_role_spec` gained new behavior.** `new_role_binding`, `new_requirement`, and `new_instance` are
**not modified in this increment at all** — a deliberate design decision, not an oversight. The directive's §9
("if an optional future field is added to `new_role_binding`, it must be omitted when not explicitly supplied")
is a conditional constraint; the simplest way to make it unconditionally true is to not add that field yet.
`candidate_supports` is introduced as a **wholly independent schema object** (`new_candidate_support`/
`new_candidate_supports`), not yet attached to `RoleBinding` or `Instance` via any new field — attaching it is
better deferred to the same increment that actually wires it in (I4-2), rather than shipping an unused field that
sits on every instance in the interim. This is confirmed directly by `test_role_binding_and_requirement_are_
entirely_untouched`.

`new_role_spec` itself keeps its historical seven-key shape **exactly** when `support_policy` is omitted — the
key is never materialized as a `None`/empty placeholder (`test_role_spec_without_support_policy_has_exactly_the_
historical_seven_keys`). When explicitly supplied, it is validated and canonicalized via the same logic
`new_support_policy` itself uses, then included as an eighth key.

---

## 3. `support_policy` schema (section 3/14)

```
new_support_policy(
    *,
    allowed_assertion_relations=("current_document", "attributed_external", "unresolved"),
    aggregation_requirement="any",
    allowed_assertion_kinds=("result",),
) -> dict
```

Deterministic, JSON-safe, canonicalizes ordering (both list inputs are deduplicated and sorted — two policies
built from differently-ordered but equal inputs always serialize identically), rejects any value outside the
three closed vocabularies (`SUPPORT_ASSERTION_RELATIONS`, `AGGREGATION_REQUIREMENTS`, `SUPPORT_ASSERTION_KINDS`),
and rejects an empty relation or kind set (a policy admitting nothing is nonsensical, never a legitimate authored
choice). Makes no inference from question text and contains no q_aib/domain vocabulary anywhere. The function's
own keyword defaults double as a usable, question-agnostic schema example — not the future I4-2 default-
admissibility predicate itself, which is confirmed to execute nowhere (§13's static guards).

All four directive-named examples (general empirical; current-document-only; definitional; literature-synthesis)
are frozen as test cases (`test_new_support_policy_examples_from_the_directive_section_14`) and construct cleanly.

**No evaluator was added beyond the two explicitly-authorized reference helpers** (§6/§10's `reference_future_
role_state`, which reads a candidate-support list's `admissible`/`inadmissibility_reason` fields, not a
`support_policy` directly) — no function in this increment takes `(support_policy, assertion_relation,
aggregation, assertion_kind)` and returns an admissibility boolean, because the directive's §3 only authorizes
that "if needed purely to validate the schema," and the schema validates fully without one.

---

## 4. `RoleSpec` optional field (section 4)

`new_role_spec` gained one new keyword, `support_policy: dict | None = None`. Omitted (every pre-existing call
site, and the overwhelming majority of future ones): the historical shape, byte-for-byte. Explicitly supplied: it
is re-validated and canonicalized via `new_support_policy`'s own logic (`_canonical_support_policy`), whether the
caller passed the direct output of `new_support_policy(...)` or a hand-authored dict of the same shape — both
paths are tested (`test_role_spec_accepts_an_explicit_validated_support_policy`,
`test_role_spec_canonicalizes_a_hand_authored_support_policy_dict`). A malformed dict (wrong keys, invalid
vocabulary) raises (`test_role_spec_rejects_a_malformed_support_policy`).

**No existing q_aib role is authored with a `support_policy` in this increment** —
`test_no_existing_q_aib_role_is_authored_with_a_support_policy` rebuilds every `_BUILDERS` entry
(`sufficiency_authoring.py`) from stub wording and asserts none carries the new key. The default admissibility
predicate (§5 of the directive) is confirmed to execute nowhere: it is not implemented at all, by design — the
directive's conceptual sketch ("empirical result-kind support is admissible except ordinary unresolved/non-
synthetic support, with unresolved + explicit literature_synthesis allowed") is recorded here as a design
reference, not as code; no function in this module reads `support_policy` to decide anything.

---

## 5. Candidate-support record + collection (sections 6–9, 15)

```
new_candidate_support(
    *, proposition_id, exact_text, assertion_relation, aggregation, assertion_kind, admissible,
    assertion_span=None, predicate_span=None, content_span=None, support_label=None,
    authority_veto=None, is_caption=False, attachment_ambiguous=False, inadmissibility_reason=None,
) -> dict
```

A pure data contract: it validates and serializes already-computed values, and performs none of the acts the
directive explicitly forbids (classify text, call any I4-1 classifier, decide admissibility, mutate requirement
state, choose a representative) — confirmed by direct reading: the function body is exactly nine closed-
vocabulary membership checks, two cross-field consistency checks (`admissible` and `inadmissibility_reason` must
disagree in presence, never both set or both absent), and a literal dict construction. No `finding_authority`
`authoritative`/`candidate` vocabulary is serialized anywhere on this record, per I4-1e revision 2's own
recommendation that a downstream consumer need not re-expose that coarse, collision-prone field;
`authority_veto`/`is_caption` are retained as properties of the specific (assertion, target) binding attempt they
describe.

All seven directive-named examples (direct primary/synthetic, attributed primary/synthetic, unresolved
synthetic, policy-excluded-but-retained, attachment-ambiguous-but-retained) are frozen as test cases
(`test_candidate_support_examples_from_section_15`) and construct cleanly, each with the full fourteen-key shape.
Seven invalid/inconsistent-input cases are confirmed to raise.

```
new_candidate_supports(records: list[dict]) -> list[dict]
```

A thin, order-preserving validator: it returns a **fresh** list (never aliasing the caller's own), in the
caller's own traversal order, after confirming every record has exactly `new_candidate_support`'s own shape.
Nothing is dropped, reordered, ranked, or filtered — `test_candidate_supports_collection_preserves_order_and_
drops_nothing` constructs two records in one order and confirms the returned list matches that exact order, not
a canonicalized or re-sorted one. List position is documented as never semantically meaningful.

---

## 6. Future role-state aggregation contract, frozen as a reference helper (section 10)

```
reference_future_role_state(candidate_supports: list[dict]) -> tuple[str, str | None]
```

**REFERENCE ONLY.** Implements exactly the three-way rule the directive specifies: `"filled"` iff at least one
candidate is admissible (checked unconditionally first, regardless of what else the list contains — so one
ambiguous candidate never poisons a separate, unambiguous admissible support); `"ambiguous"` iff no candidate is
admissible **and** at least one relevant candidate's `inadmissibility_reason` is specifically `"assertion_
attachment_ambiguous"`; `"missing"` otherwise — confirmed directly: policy-excluded evidence alone (no
attachment-ambiguous candidate present) aggregates to `"missing"`, never `"ambiguous"`
(`test_reference_future_role_state_policy_excluded_alone_is_missing_not_ambiguous`). Two independent static
guards (§13) prove this helper is not called by `recompute_instance`/`recompute_requirement`/
`is_category_requirement`/`category_goal_satisfied` (same-file AST scan) nor by any other function in the module
(a second AST scan covering every function definition), and a third guard proves no production file outside this
module references it by name at all.

---

## 7. `requested_category_terms` generalized contract (sections 11–13)

**No rename.** The field keeps its historical name — judged not strictly necessary to change, per the
directive's own preferred outcome. Its documented contract in `new_role_spec`'s own docstring is generalized:
"verbatim requested target terms/phrases, optionally supplied by ANY strategy that supports target-aware local
disambiguation — today that is also `achieved_outcome_predicate`... never to broaden what counts as a match,
establish relevance, or establish authority."

**No code change was needed anywhere else, because none was required to enable this.** Direct reading of
`sufficiency_mapping.py` confirms `requested_category_terms` is read in exactly two places, both scoped entirely
to the `all_requested_categories`/`explicit_category_terms` cardinality-mapping path (`map_cardinality_
requirement` and its model-nomination-scoping guard) — neither restricts the field's mere *presence* on a
RoleSpec by `mapping_strategy` at construction time, and `new_role_spec` itself never has. An `achieved_outcome_
predicate` role could already carry a non-empty `requested_category_terms` list before this increment; nothing
read it. This increment documents that the field may now be meaningfully populated for that strategy too and
freezes the future matching contract as a reference helper:

```
reference_future_requested_terms_disambiguation(candidates: list[dict], requested_terms: list[str]) -> dict | None
```

**REFERENCE ONLY**, not called by production mapping. Literal substring containment only — no fuzzy matching, no
embeddings, no model call, no synonym expansion, no stemming — deliberately not reusing `sufficiency_mapping.py`'s
own `canonical_text_contains` discipline by import, since doing so would cross the I4-1 classifier family's own
unwired boundary even for a test-only reference (this module imports nothing from that family at all, confirmed
by the same static guard in §9 of I4-1f's own report). The four required cases (A: empty terms → no
disambiguation; B: exactly one candidate's `exact_text` contains a term → that candidate; C: zero candidates
contain a term → no disambiguation; D: more than one candidate contains terms → no disambiguation) are frozen as
parametrized test cases, plus an explicit "never first-match" case (`test_reference_disambiguation_never_first_
match_fallback`) confirming two equally-matching candidates resolve to `None`, not the first one.

---

## 8. A real, self-inflicted guard trip found and fixed before it shipped

**The first implementation draft's own explanatory comments literally contained the strings `"assertion_
authority"` and `"achieved_outcome_span"`** — written to document *why* this module imports neither. The
existing static unwired guards in `test_assertion_authority.py`, `test_achieved_outcome_span.py`, and I4-1f's own
`test_assertion_authority_i4_1f.py` all do a plain substring scan of every production `.py` file's *text* for
those two module names, with no distinction between an actual `import` and a comment mentioning the name in
prose. The first full regression run caught this immediately: three pre-existing, otherwise-unrelated guard tests
failed, each correctly reporting `sufficiency_engine.py` as a new offender. This is confirmed to be exactly what
it looks like — prose, not an import (`git diff` shows no `import`/`from` line referencing either module) — and
was fixed by rewriting the four comments/docstrings to describe the I4-1 classifier family descriptively, without
ever spelling out its two filenames. **No guard test was weakened, relaxed, or edited to accommodate this** — the
existing guards' own strictness is exactly what caught the problem, and they are confirmed unchanged
(`git diff --stat` touches no test file from the I4-1/I4-1b/I4-1c/I4-1f family). Re-run after the fix:
all three previously-failing guards pass again, with zero other change.

---

## 9. Byte-parity gate (sections 2/17)

Eleven representative pre-change serializations were captured (via `json.dumps(obj, sort_keys=True,
ensure_ascii=False)` + SHA-256, the same canonicalization `contract_hash`/`freeze` already use in this file) from
the **unmodified** module, before any edit: three `new_role_spec` shapes (minimal; every optional field
populated; a category role), three `new_role_binding` states (minimal/missing; filled with custom provenance and
guard; ambiguous), three `new_requirement` shapes (minimal atomic; with direction+effectiveness+multi_instance;
a cardinality requirement), and a full stub q_aib contract set run through `sufficiency_authoring.build_qaib_
contract`/`freeze` (eleven children, stub wording — shape-representative, not real q_aib content).

| Fixture | Frozen (pre-I4-1g) SHA-256 |
|---|---|
| `role_spec_minimal` | `15dc036ef1b6c33ed142f82c53affb73ed5f405d165ce276d7e09d58135baa17` |
| `role_spec_full` | `edfc981578b751e0c8a62d3292f8bd137cdb2fae0070684bbedc273e9ffc9ce8` |
| `role_spec_category` | `30c9679d9099e9cfacf9b1fce41a2f3a5a85eabe3d4694ee3e9685aaf9cd1105` |
| `role_binding_minimal` | `2b2a97e743257b8f8de8af09c57b8241650589e70cea6b8bc3e874289d17c095` |
| `role_binding_filled` | `8fbcc6c20323f8453d0e90455b6b7d24d641c439cc62e7507781d54b4adb6afb` |
| `role_binding_ambiguous` | `47b186963d1277ebaaa4728811cefabe91e74bbc66551a4efd65981f95255fb3` |
| `requirement_atomic_minimal` | `0d6d16fef0841374ef9d3596fd9359f809646b750b83cb6b6366ab8314777127` |
| `requirement_with_direction_effectiveness` | `bbb61aff6f38af5ea46f7030d12638fecca50f7ae3bfa2af14a0b948dd1148c3` |
| `requirement_cardinality` | `d446c3056aa02eda790c14395d395c60e7401fd976f3abfc968db2b720b5c377` |
| `qaib_stub_contracts` | `73aea355a4ae28bc82a1387a7e52041ba23d1320a9650451345b0df631147936` |
| `qaib_stub_frozen` (incl. its own `combined_hash`) | `74b6f5be255368b4edb81212ecef1be1a27b6386a2e54733545ef2f8c2c84f5b` |

`test_byte_parity_every_unmodified_constructor_call_is_unchanged` rebuilds all eleven from the **finished**
implementation and asserts every hash is identical, plus the stub contract's own `combined_hash`
(`2696958197f006df28f6b65ff6364f1b36930b18dfbcabe46e13534aa608d553`) separately. **All eleven matched on the
first implementation run that fixed the guard-trip in §8** — byte parity held throughout; nothing needed
relaxing, and the gate was never waived.

---

## 10. Static schema-purity guards (section 16)

Beyond the byte-parity gate and the two reference-helper call guards (§6), `test_sufficiency_support_schema.py`
scans `sufficiency_mapping.py`, `sufficiency_recovery_targets.py`, `sufficiency_diagnostic.py`,
`sufficiency_model_scope.py`, `e2e.py`, and every file in `answer_plan/` for the literal names `support_policy`,
`candidate_supports`, `new_support_policy`, `new_candidate_support`, `new_candidate_supports`,
`reference_future_role_state`, and `reference_future_requested_terms_disambiguation` — none appear anywhere in
any of those files. Combined with §4's confirmation that no existing q_aib role carries a `support_policy`, this
is the full, concrete proof that nothing shipped in I4-1g is consumed by any production path.

---

## 11. Test counts

- **New file** (`test_sufficiency_support_schema.py`): **44 passed**.
- **I4-1 classifier family + I4-1g together** (`test_assertion_authority.py`, `test_assertion_authority_i4_1b.py`,
  `test_assertion_authority_i4_1c.py`, `test_achieved_outcome_span.py`, `test_assertion_authority_i4_1f.py`,
  `test_sufficiency_support_schema.py`, plus `test_sufficiency_mapping.py`, `test_sufficiency_v4_category_
  satisfaction.py`, `test_sufficiency_semantics_version.py`, `test_sufficiency_semantics_threading.py`,
  `test_sufficiency_leakage.py`): **718 passed, 9 xfailed** (the 9 xfails are I4-1b's own pre-existing,
  unaffected supersessions).
- **Full sufficiency/engine/mapping/authoring/replay/direction/relation/parent-synthesis/AnswerPlan sweep**
  (`test_sufficiency_*.py`, `test_answer_plan*.py`, `test_relation_witness.py`, `test_direction_target*.py`,
  `test_parent_synthesis*.py`, `test_hierarchy_subquestions.py`): **927 passed**, zero failures.
- **Full offline `experiments/` suite** (`pytest experiments/ -n auto`): **3695 passed, 5 failed, 12 skipped, 9
  xfailed.** The five failures are the **exact same pre-existing/environment-artifact set** every prior I4-1x
  report already names (the `hierarchy_contract.py` pin-drift and its downstream exit-code effect, the
  live-Ollama-dependent unscored-smoke-run case, and two missing-fixture `FileNotFoundError`s in the unrelated
  `experiments/ask_070/` subtree). **Zero new failures.**

`ruff format`/`ruff check` pass on both touched/new Python files.

---

## 12. The preserved 54-quote / v4-artifact gate, carried forward explicitly (section 19)

I4-1f could not perform the full preserved-54-quote sweep or the reconstructed-v4-map descriptor view because the
prior session's gitignored scratch fixtures (`frozen_54_inputs.json`, any `final_v4*.json`) are not present in
this worktree. **I4-1g did not need them and did not attempt to reconstruct them** — this increment classifies
nothing and gates nothing, so there is no evidence-corpus question for it to answer. This is **not** resolved by
I4-1g, and is restated here as the hard gate it is:

> **I4-2 MUST NOT START** until the preserved 54-quote inputs and the reconstructed v4 map are either recovered
> from wherever the originating session kept them, or deterministically reconstructed from preserved,
> already-committed/stamped artifacts with their hashes independently verified. Fabricating substitute data is
> not an acceptable substitute for either path, and this gate is not satisfied by any amount of schema-level work
> in I4-1f/I4-1g.

---

## 13. Recommendation

**READY for I4-2 planning/review** — not for I4-2 implementation itself. I4-1g delivers exactly its own bounded
scope: `support_policy`'s schema and its one optional `RoleSpec` field, the candidate-support record and
collection schema, and the two reference-only contracts (role-state aggregation; `requested_category_terms`
disambiguation) — all pure, all backward-compatible (an eleven-fixture byte-parity gate held through the finished
implementation), and all confirmed unconsumed by any production path via static guard. I4-2 itself remains
explicitly not started: no binding has ever been gated by a `support_policy`, no role state has ever been
computed from a `candidate_supports` list, and the hard preserved-corpus gate in §12 stands between this
increment and that one, independent of anything I4-1g itself could have done to shorten it.
