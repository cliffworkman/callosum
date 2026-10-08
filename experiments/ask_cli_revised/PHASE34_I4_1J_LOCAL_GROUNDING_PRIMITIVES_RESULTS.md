# PHASE 34 / I4-1j — pure local assertion grounding primitives (results)

**Status: pure, schema/primitive-only, unwired.** No `support_policy` gating of any binding, no all-support
collection in `_bind_role_candidates`, no sibling-context threading into production mapping, no real
requirement's `relationship_verifiers` list edited, no `sufficiency_semantics_version` bump, no
`PLAN_VERSION` bump, no I4-2a, no I4-2b, no I2-3. No model, network, live search, or live end-to-end run.

- Starting HEAD: `4f3199aa3ae2b1d712bedc369c422f100ecaac53`.
- Docs-only checkpoint (I4-1h accepted + corrected I4-1i, per this increment's own instruction to commit
  that history separately before any code): `5bdf488e` (pushed to `origin/experiment/ask-060-hier11-
  recpm3-citefix-20260929T212442Z`).
- Implementation starting point: `5bdf488e`. Final HEAD: the commit that carries this increment (see the
  handback).

I4-1i is accepted in substance, after one required correction (below) made before any code.

---

## 1. I4-1i factual correction (required before implementation)

**Found exactly as flagged.** §4 of `PHASE34_I4_1I_INSTANCE_TARGET_RELEVANCE_AUDIT.md` stated that
`same_proposition` "passes on every one of the 9 non-empty instances" of c8 and that "all 9 are
`complete=True`/`state=filled`." T9 (§23) stated, correctly, that "c8's own 4 p20-bound instances are
unaffected (already, correctly, `missing`)" — a direct contradiction never flagged as one.

**Re-read `17_sufficiency_map.json`'s real `c8` requirement, exhaustively (all 11 instances, not a sample):**

| Instance group | `individual_difference_trait_or_construct` | `relationship_to_bias_manifestation` | `complete`/`state` |
|---|---|---|---|
| `U6::*` (×4, p20-bound) | `filled` | **`missing`** — never bound at all | `False`/`partially_filled` |
| `U7` | `missing` | `missing` | `False`/`missing` |
| `U23::*` (×5, p41-bound) | `filled` | `filled`, same proposition p41 | `True`/`filled` |
| `U24` | `missing` | `missing` | `False`/`missing` |

**Source of truth: the real map, re-read directly.** **Corrected fact: `same_proposition` passes, and is
blind to the within-proposition split, on 5 of c8's 11 instances — not 9.** The 4 p20-bound instances are
correctly `partially_filled` for an entirely unrelated reason (their evidence role was simply never found),
the same honest-absence shape as c10's/c12's own unfilled roles — never a `same_proposition` story.

**T1–T15 consequence: none.** §11's own counterfactual table already correctly said "5 instances"; T8/T9 were
already correct. The design (the `same_local_assertion` extension, the parameter-threading finding, the join)
is unaffected — only the headline blast-radius count was overstated.

**I4-1i corrected in place:** §4's table, §4's/§5's prose, and §21/§23's "9 real instances" phrasing were all
rewritten to say "5 p41-bound instances," with an explicit correction note appended to the file itself
(matching this same disclosure convention) rather than silently edited. Committed as part of the docs-only
checkpoint, `5bdf488e`.

**A second, related error found while building this increment's own real battery (not flagged by the
directive, corrected for the same reason):** I4-1i §12's counterfactual table described c4 instance 2's
corrected evidence as "an `attributed_external`/`result` assertion." Running `assertion_authority.classify_
target_assertions` directly against p40's real sealed text shows the sentence in question ("Laypersons with
high levels of implicit bias… demonstrated increased amygdala reactiv- ity") is actually `unknown`/
`unresolved` — its subject, "Laypersons with high levels of implicit bias," is not a recognized owner phrase,
unlike p40's *other* sentence ("Recent work… has implicated certain neuroanatomic structures"), which
genuinely is `prior_work`/`attributed_external`. Corrected in place in I4-1i §12, with its own explicit
correction note; no decision changes (which sentence is target-relevant is unaffected — only its label was
wrong).

---

## 2. Files changed

| File | Change |
|---|---|
| `experiments/ask_cli_revised/sufficiency_engine.py` | `new_candidate_support`/`_CANDIDATE_SUPPORT_KEYS` corrected: `proposition_id` → `supporting_proposition_ids` (required, non-empty, duplicate-free, discovery-order) + new `span_proposition_id` (required iff a span is present; must be a member). `new_candidate_supports`, `reference_future_role_state`, `reference_future_requested_terms_disambiguation`, `new_role_binding`, `new_requirement`, `new_instance`, `_VERIFIER_FUNCS` — **untouched**. |
| `experiments/ask_cli_revised/assertion_authority.py` | New function `locate_containing_assertion` — the deterministic join. `RULESET_VERSION` **deliberately left at `"i4-1f.0"`** (§9 below). |
| `experiments/ask_cli_revised/target_relevance.py` | **New file.** `local_assertion_relevance`, `match_target_to_assertions`, `verify_shared_local_assertion` — all pure, importing neither classifier-family module. |
| `experiments/ask_cli_revised/test_sufficiency_support_schema.py` | Updated for the plural schema; 4 new tests (non-empty/duplicate-free/order-preserved identity; `span_proposition_id` required-with-span-and-must-be-member); one deliberate, documented exclusion from the file's own `_NEW_NAMES` guard (§4). |
| `experiments/ask_cli_revised/test_i4_1j_local_grounding.py` | **New file.** 25 tests: the join (synthetic + the real p41 battery), the matcher (synthetic + generic twins + real c8/c4/c2/c10 batteries), the `same_local_assertion` vacuity/non-registration proof, schema-parity cross-check, static unwired guards. |
| `experiments/ask_cli_revised/PHASE34_I4_1I_INSTANCE_TARGET_RELEVANCE_AUDIT.md` | Corrected in place (§1 above). |
| `experiments/ask_cli_revised/PHASE34_I4_1J_LOCAL_GROUNDING_PRIMITIVES_RESULTS.md` | New: this report. |
| `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` | Appended. |

Nothing else changed — confirmed by `git diff --stat` against the implementation starting point
(`5bdf488e`), and by direct listing of every modified/new path above. No `app/`, `integrations/`, frontend,
pin, frozen-contract, or version file was touched.

---

## 3. Candidate-support plural-identity correction

`new_candidate_support` now requires `supporting_proposition_ids: list[str]` (replacing the singular
`proposition_id`) — required, must be non-empty, must contain no duplicates, preserved in **discovery order**
(never sorted — a defensive copy of exactly what the caller supplied). This deliberately mirrors the real,
already-production `model_mapping` provenance shape (`17_sufficiency_map.json`'s own real `c8` bindings:
`"supporting_proposition_ids": ["p20", "p9"]`) rather than inventing a second, differently-ordered convention
for the same kind of information.

**No mandatory singular `primary_proposition_id` was added**, per the directive's own instruction — a future
compatibility projection may derive a display-only first element from the list later, never the reverse.

**A real name collision was found and handled, not silently avoided.** `sufficiency_mapping.py` already,
legitimately, contains the literal string `"supporting_proposition_ids"` — it is Phase 3's own, already-
production `RoleBinding.provenance.supporting_proposition_ids` field (the anchor-dedup provenance key). A
bare substring-scan guard (the exact shape `test_sufficiency_support_schema.py`'s own `_NEW_NAMES` check
uses) cannot distinguish "references the pre-existing Phase-3 field" from "consumes I4-1j's new candidate-
support schema." `supporting_proposition_ids` is therefore **deliberately excluded** from that guard's
`_NEW_NAMES` tuple, with an explicit comment recording why; `span_proposition_id` (genuinely new, zero
pre-existing collisions, confirmed) is included. The genuinely new API surface
(`new_candidate_support`/`new_candidate_supports`) remains in the guard and is what actually proves
non-consumption.

---

## 4. The span-anchor rule

`span_proposition_id: str | None`, required **exactly when** any of `assertion_span`/`predicate_span`/
`content_span` is present, and must itself be a member of `supporting_proposition_ids`. This answers I4-1i's
own §16 question precisely: `supporting_proposition_ids` + a span **qualified by its own anchor proposition**
is sufficient to deterministically relocate the exact sealed passage a span's offsets index into — no new
whole-passage field, and no ambiguity the moment a candidate's support spans more than one proposition
(not observed in the real corpus, but not structurally ruled out either).

---

## 5. The deterministic assertion-localization join

```python
locate_containing_assertion(text, target_start, target_end, *, is_caption=False, structural_context=None, locator=None) -> dict
```

A thin wrapper inside `assertion_authority.py` itself over the module's own, already-existing
`classify_target_assertions` — **zero new parsing, zero new boundary logic.** Added as a new function to
the same module (continuing the exact pattern I4-1b/c/f already established — each adds capability directly
to this file rather than a sibling module that would have to import it, since importing the classifier by
name from anywhere else trips its own unwired static guard).

| `target_scope` | Outcome |
|---|---|
| `within_assertion` or `partial_assertion` | **resolved** — `assertion` is that one assertion's full record |
| `no_governing_assertion` | fails closed, `reason="no_governing_assertion"` |
| `multi_assertion` | fails closed, `reason="multi_assertion"` |

The full, unmodified `classify_target_assertions` result is always returned as `"diagnostic"` — a failed join
never discards the information needed to understand why.

---

## 6. Division of labor, locked and proven, not merely asserted

Confirmed exactly per the directive: a result-predicate-localizing module finds/localizes raw predicate hits
(its own job); `assertion_authority` determines the containing local assertion and its relation/kind/
aggregation/authority metadata (its own, pre-existing job, unchanged). `locate_containing_assertion` is the
one join between them. Neither module imports the other's name — `target_relevance.py` likewise imports
neither, confirmed by a static AST-based guard (`test_target_relevance_module_imports_neither_classifier_
family_module`), not merely a docstring claim.

**The real p41 join test (frozen, section 6):**

```
raw hit 0: content_span=(65, 200)   -> join resolves -> assertion span (43, 200)
raw hit 1: content_span=(102, 200)  -> join resolves -> assertion span (43, 200)   [same assertion as hit 0]
raw hit 2: content_span=(235, 373)  -> join resolves -> assertion span (208, 372)
```

All three resolve; none is `no_governing_assertion`/`multi_assertion`. Hits 0 and 1 are flagged mutually
`ambiguous_with` by the predicate-localizing module's own, separate, narrower boundary grammar — confirmed
present in the frozen test, not hidden — and the join is structurally incapable of reproducing that flag: it
never reads `ambiguous_with` at all, it only asks `assertion_authority` where the span falls, and
`assertion_authority`'s own embedded-content parsing already resolves "revealed [elliptical-that] greater
proportionality was associated with…" as one assertion. Deduplicating the three raw hits by resolved
assertion span (not performed by the join itself — a one-line test-side step, exactly where I4-2a's own
future candidate-collection would do it) collapses them to exactly the two real assertions, with zero
p41-specific code anywhere in `locate_containing_assertion`.

---

## 7. The target-relevance matcher

```python
match_target_to_assertions(*, target_text, candidate_assertions, allowed_proposition_ids=None) -> dict
```

Three cleanly separated layers, per the directive's own A/B/C/D split:

- **Scope (A):** `allowed_proposition_ids`, a plain pre-filter. The matcher never knows or computes why that
  scope exists — it might be `same_proposition`'s own sibling support set, or `None` for an unscoped search.
- **Target text (B):** a caller-supplied literal string — a sibling role's own `exact_text`, confirmed by
  I4-1i to already be a clean, minimal referent; no new value-representation primitive needed.
- **Candidates (C):** a caller-supplied list of `{"proposition_id", "text", ...}` dicts — in this increment's
  own real batteries, each is the **full assertion region text** (`locate_containing_assertion`'s own
  `assertion["assertion"]["text"]`, subject-inclusive), not the narrower `content.text`. This choice is
  load-bearing, not cosmetic: the real c4 instance 1 case needs it — the sibling's own bound value, `"the
  specific amygdala response,"` is drawn from **p11's subject**, which the narrower content span excludes
  entirely (confirmed directly: `content.text` for p11's one assertion is `"with stronger just-world
  beliefs…"`, which does not contain the word at all). Using the full region text is what lets a
  self-referential instance (the sibling's own value drawn from the same passage it is evidence for) match
  itself.
- **Matching (D):** literal, case-insensitive containment, with the existing `dehyphenate_for_matching`
  fallback — the identical two-step discipline `sufficiency_mapping._match_instrument` already uses for this
  exact class of sealed-PDF line-wrap artifact. No stemming, no embeddings, no synonym expansion, no model
  call, no domain lexicon.

Returns `{"relevance": "unmatched" | "unique" | "multiple", "matches": [...]}` — **never a first match.**
Genuine evidence plurality (`"multiple"`) is preserved, never collapsed into an ambiguous state merely
because there is more than one.

---

## 8. Relationship-derived scope

`allowed_proposition_ids` is populated, in every real battery below, from `_support_set` — **the exact,
already-shipped compatibility helper** `sufficiency_engine._verify_same_proposition` itself already uses to
normalize a binding's `proposition_id` into a set (unioned with any already-present plural `provenance.
supporting_proposition_ids`). No new compatibility helper was written; §8's own suggested one already exists.
`target_relevance.py` itself never calls it and never needs to — the scope arrives pre-computed, exactly as
the directive's own "the matcher itself should not know why that scope exists" instructs.

---

## 9. `same_local_assertion` — the pure primitive, deliberately NOT registered

**`verify_shared_local_assertion(*, sibling_target_text, evidence_assertion_text) -> bool`** is implemented —
a thin, correctly-named wrapper over `local_assertion_relevance` with the CORRECT two inputs the semantic
question actually needs: the sibling's target text, and the evidence role's own already-**narrowed** local
assertion text (never a whole passage).

**Registration into `sufficiency_engine._VERIFIER_FUNCS` was evaluated and explicitly declined, with
empirical proof, not merely argued.** The existing `(role_bindings, roles) -> bool` signature every verifier
uses *can* represent this function's real inputs with no hidden global read (`role_bindings[sibling]
["exact_text"]`, `role_bindings[evidence]["exact_text"]` — both already live fields), which satisfies the
directive's own registration test on its face. But for **every real `achieved_outcome_predicate` binding
today**, `exact_text` is still the **whole passage** (I4-1d's own disclosed, unfixed limitation) — and feeding
a whole passage as `evidence_assertion_text` does not fail; it returns a **vacuous, non-discriminating**
answer. Confirmed directly, not assumed (`test_verify_shared_local_assertion_is_vacuous_against_todays_real_
whole_passage_binding`): fed p41's real whole passage, `verify_shared_local_assertion` returns `True` for
**every one of c8's five real trait terms** — attractiveness, trustworthiness, anger, dominance,
threateningness all "pass," because each does occur *somewhere* in the shared passage, regardless of which
of its two real assertions. A verifier that always passes the exact case it exists to catch is **actively
worse than no verifier at all** — it would give false reassurance to anyone who consulted it. **Decision:
the pure primitive ships, fully tested against both the correct-input case (§ the first test) and the
vacuity case (the second); it is not added to `_VERIFIER_FUNCS`, and a static test
(`test_same_local_assertion_is_not_registered_in_verifier_funcs`) proves this. Registration becomes safe the
moment a caller can supply a genuinely narrowed local-assertion text as the second argument — I4-2a's own
future span-narrowing work — with zero further change to this function.**

---

## 10. Real battery results

### c8 (section 16)

All five real trait targets, against the real p41 text, scoped to `["p41"]`:

| Target | Relevance | Resolved assertion span |
|---|---|---|
| `attractiveness` | unique | `(43, 200)` — via the dehyphenation fallback (sealed text: `"attrac- tiveness"`) |
| `trustworthiness` | unique | `(43, 200)` |
| `anger` | unique | `(208, 372)` |
| `dominance` | unique | `(208, 372)` |
| `threateningness` | unique | `(208, 372)` |

Exactly I4-1h's/I4-1i's own predicted split, now produced by the real, composed, end-to-end pipeline
(achieved-outcome localization → the join → the matcher) rather than hand-verified text alone.

### c4 (section 17)

| Instance | Sibling value | Scope | Relevance | Matched proposition |
|---|---|---|---|---|
| 1 | `"the specific amygdala response"` | `["p11"]` | unique | p11 |
| 2 | `"increased amygdala reactiv- ity"` | `["p40"]` | unique | p40 |

**The load-bearing demonstration:** the bare, generic target `"amygdala"` against the **unscoped** pool of
both propositions' own real assertions returns `"multiple"` (both p11 and p40 match) — removing scope
over-matches exactly as predicted. Re-scoping to `["p40"]` alone collapses it back to `"unique"`. Confirmed
by direct test, not asserted.

### c2 (section 18)

| Proposition | `has_result_predicate` | Candidate count | Target | Relevance |
|---|---|---|---|---|
| p35 | `False` | 0 | own sibling phrase | **unmatched** |
| p46 | `False` | 0 | own sibling phrase | **unmatched** |
| p47 | `True` | 1 | own sibling phrase | **unique** |

p35/p46 never produce a candidate at all — confirmed directly against the real `attribution.
has_result_predicate` function, not assumed — so there is nothing for the matcher to find, honestly. **No
widening of the result-predicate lexicon was performed**, per the directive's own explicit instruction (a
separate, known, already-disclosed issue, I4-1d §6).

### c10 (section 19)

Unchanged, confirmed directly: p29/p53's own result-predicate-bearing sentence passes `has_result_predicate`
but is excluded by the **pre-existing** `hedged` guard (the word "likely"); p21 fails the pre-existing
result-predicate lexicon gate outright (`"suggest"` is not a result verb). Neither outcome is a target-
relevance question, and I4-1j changes neither.

### Generic cross-domain twins (section 20)

Seven cases, one per required property (unique; multiple; no match; same lexical target in two propositions
with only one in scope; a hyphenated line-wrap target; a target that appears only in a neighboring assertion
the matcher was never offered as a candidate; a target that occurs in a relevant-but-hedged-looking
assertion), across clinical/neuroscience/built-environment/language-learning domains. A static guard
confirms zero domain vocabulary appears in `target_relevance.py`'s own executable source — the words exist
only as test data.

---

## 11. A real, self-inflicted guard trip — found and fixed before it shipped (section 25's own discipline)

**Two, not one**, mirroring I4-1g's own precedent exactly. (1) `target_relevance.py`'s own first-draft module
docstring, explaining *why* the module imports neither classifier-family sibling, **literally named both of
them** — tripping neither module's own guard directly (since neither guard scans `target_relevance.py` by
name yet) but tripping this increment's **own** new `test_no_domain_vocabulary_in_executable_target_
relevance_logic`-adjacent discipline once "amygdala" was also used as a motivating example in the same
docstring. (2) `locate_containing_assertion`'s own docstring, added inside `assertion_authority.py`, named
the result-predicate-localizing module by name — immediately failing *that* module's own pre-existing
`test_module_is_unwired_static_guard` (a plain text-substring scan, no import/comment distinction, exactly
the mechanism I4-1g's report already documents tripping on). Both fixed by rewriting the prose to describe
the sibling module/domain concept generically, never spelling out the forbidden literal strings — no guard
was weakened or edited to accommodate either mistake; the existing guards' own strictness is exactly what
caught both, immediately, before any battery widened around the error.

---

## 12. Static unwired guards

- No production file (`sufficiency_mapping.py`, `sufficiency_recovery_targets.py`, `sufficiency_diagnostic.py`,
  `sufficiency_model_scope.py`, `sufficiency_authoring.py`, `e2e.py`, every `answer_plan/*.py`) references
  `locate_containing_assertion`, `match_target_to_assertions`, `local_assertion_relevance`, `verify_shared_
  local_assertion`, or the module name `target_relevance` — confirmed by direct substring scan.
- `target_relevance.py` imports neither classifier-family module — confirmed by AST import-name inspection,
  not a substring scan (so a prose mention, if one slipped through, would not falsely pass this one).
- `same_local_assertion` is absent from `sufficiency_engine._VERIFIER_FUNCS` — confirmed directly.
- No real q_aib requirement's `relationship_verifiers` list contains `same_local_assertion` — confirmed by
  rebuilding the real stub contract and checking every requirement; every one is still exactly
  `["same_proposition"]`, byte-identical to every prior phase.
- `assertion_authority.py`'s own pre-existing unwired guard (no non-test module anywhere references the
  module's name) still passes, re-run directly — confirmed unaffected by adding a function to the module
  itself, since that changes nothing about which *other* files reference it by name.

---

## 13. Byte/runtime parity

- `_verify_same_proposition`'s own behavior is reproduced byte-identically over the real c8/c4 shapes
  (`p41`/`p41` → `True`; `p20`/`p41` → `False`; `p11`/`p40` → `False`) with zero code change to that
  function.
- `SUFFICIENCY_SEMANTICS_VERSION`/`PLAN_VERSION` confirmed unchanged.
- `RULESET_VERSION` **deliberately left at `"i4-1f.0"`** — a considered decision, not an oversight. I4-1b/c/f
  each moved it because they changed what an *existing* classification call returns; `locate_containing_
  assertion` is purely additive and changes the output of no existing function (`classify_assertion_
  authority`, `classify_target_assertions`, `aggregation`, `support_label`, `assertion_relation` are all
  confirmed byte-identical by the full regression below). Moving the "ruleset" identity for a change that
  touches no rule would make that identity track file edits rather than classification behavior, which is
  less precise than the existing convention, not more consistent with it.

---

## 14. Test counts

- **New file** (`test_i4_1j_local_grounding.py`): **25 passed**.
- **I4-1 classifier family + I4-1j together** (`test_assertion_authority.py`, `_i4_1b`, `_i4_1c`, `_i4_1f`,
  `test_achieved_outcome_span.py`, `test_sufficiency_support_schema.py`, `test_i4_1j_local_grounding.py`):
  **575 passed, 9 xfailed** (the unaffected pre-existing I4-1b supersessions).
- **Full sufficiency/engine/mapping/relation/direction/replay/AnswerPlan/parent-synthesis sweep**
  (every `test_sufficiency_*.py`, `test_relation_witness.py`, `test_direction_target*.py`,
  `test_answer_plan*.py`, `test_parent_synthesis*.py`, `test_hierarchy_subquestions.py`, parallelized):
  **909 passed**, zero failures.
- **Full offline `experiments/` suite** (`pytest experiments/ -n auto`, no network call needed for this
  increment's own code, mirroring I4-1f's identical choice): **3726 passed, 5 failed, 12 skipped, 9 xfailed.**
  All five failures are the **exact same pre-existing/environment-artifact set** every prior I4-1x report
  already names (the `hierarchy_contract.py` pin-drift and its downstream `test_hierarchy_e2e.py` exit-code
  effect; the live-Ollama-dependent `test_e2e_run.py` case; two missing-fixture `FileNotFoundError`s in the
  unrelated `experiments/ask_070/` subtree) — confirmed by `git diff --stat` showing zero changes anywhere
  near `hierarchy_contract.py` or `ask_070/`. **Zero new failures.**

`ruff format`/`ruff check` pass on all five touched/new Python files.

---

## 15. Recommendation

**READY for I4-2a**, scoped exactly as I4-1i's own §22 bounds it: span attachment + `candidate_supports`
collection + `exact_text` narrowing, with the real `locate_containing_assertion` join and the real
`match_target_to_assertions`/scope-derivation primitives now available, tested, and real-data-validated to
compose correctly end to end (the p41/c4/c2 batteries above). **NOT READY for I4-2b** — unchanged from
I4-1h's own finding: a real `default_support_policy` function still needs to be written (never derived from
`new_support_policy()`'s own, more permissive keyword defaults), and the `disqualifying_guards` retain-vs-
discard asymmetry (I4-1h §16/P12) still needs a deliberate decision. **`same_local_assertion` registration
remains explicitly deferred**, with its own precise, now-proven trigger condition: the first real instance in
which a caller can supply a genuinely narrowed (not whole-passage) local-assertion text for an
`achieved_outcome_predicate` binding — i.e., not before I4-2a's own span-narrowing work actually ships.
