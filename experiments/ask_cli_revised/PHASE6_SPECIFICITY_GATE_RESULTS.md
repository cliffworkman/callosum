# Phase 6 — generic specific-instance confirmation gate (2026-09-30)

**Scope:** add a second, VETO-ONLY nomination key to model-assisted sufficiency mapping, targeting
Phase 5's own newly-discovered weakness (c2's circular/self-referential nomination). No live model
call anywhere in this phase. No contract version change — v9 remains byte-identical throughout.
Recovery stays OFF. **The live diagnostic was explicitly NOT run in this phase**, per instruction.

## Commits

| Commit | Contents |
|---|---|
| `f0814716` | Core: `qwen.specificity_prompt`/`specificity_schema`/`QwenTasks.verify_specific_instances`; `sufficiency_mapping.confirm_specific_instances`; wired into `_bind_role_candidates`; always-approve fakes added to every pre-existing test client (178 tests passing, zero behavior change to any prior assertion) |
| `8bf203b2` | Part E: explicit `isinstance(raw, list)` fail-closed guard in `confirm_specific_instances`; new `test_sufficiency_specificity_gate.py` (21 synthetic tests) |
| `9a3493c8` | Parts F+G: `sufficiency_phase5_replay.py` (the scripted recorded-output replay) + `test_sufficiency_phase5_replay.py` (5 tests); `SpecificityPromptLeakageTests` added to `test_sufficiency_leakage.py` (3 tests) |

**Final HEAD (pending this report + Part H's lineage append, already committed separately):**
`9a3493c8` plus the uncommitted `CONTRIBUTION-LINEAGE.md` append and this file, committed together
at the end of this hand-back.

## Files changed this phase

- `experiments/ask_cli_revised/qwen.py` — `_SPECIFICITY_OUTPUT_TOKENS`/`_SPECIFICITY_INSTANCE_TEXT_MAX_LEN`/`_SPECIFICITY_MAX_ITEMS` constants; `specificity_prompt`; `specificity_schema`; `_validate_specificity_decisions`; `QwenTasks.verify_specific_instances`
- `experiments/ask_cli_revised/sufficiency_mapping.py` — `confirm_specific_instances` (new); `_bind_role_candidates`'s model branch now calls it between `nominate_with_model` and binding construction
- `experiments/ask_cli_revised/sufficiency_model_nomination_diagnostic.py` — `_NullModelClient`/`_LiveQwenModelClient` gained `verify_specific_instances`
- `experiments/ask_cli_revised/sufficiency_phase2_replay.py` — `RecordedNominationClient` gained an always-approve `verify_specific_instances` (Phase 2's trace predates this gate — nothing to replay there)
- `experiments/ask_cli_revised/test_sufficiency_mapping.py`, `test_sufficiency_diagnostic.py` — always-approve `verify_specific_instances` added to existing fakes
- `experiments/ask_cli_revised/test_sufficiency_specificity_gate.py` (new, 21 tests)
- `experiments/ask_cli_revised/sufficiency_phase5_replay.py` (new)
- `experiments/ask_cli_revised/test_sufficiency_phase5_replay.py` (new, 5 tests)
- `experiments/ask_cli_revised/test_sufficiency_leakage.py` — `SpecificityPromptLeakageTests` (new, 3 tests)
- `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` — Phase 6 section appended

## A. The specificity-validation task

`qwen.specificity_prompt(*, category_description, candidates)` — one call per role-call's full
nomination batch (never per-candidate). Exact prompt:

```
Each candidate below claims to identify a SPECIFIC instance of {category_description}.

Does the nominated text actually identify WHICH specific instance is present, rather
than merely saying or implying that some instance of that category exists, occurred,
was measured, or had an effect? A useful test: if a reader were shown only the
nominated text, could they answer 'which one?'

For example: "adolescents in Japan" identifies a specific population; "a population
was studied" does not. "mindfulness training" identifies a specific intervention; "an
intervention reduced symptoms" does not.

When uncertain, mark the candidate NOT specific.

For each candidate, return whether it is specific, and if so, the exact substring
(copied verbatim from its nominated text or context) that names the specific instance.
Do not invent a candidate id.

Return only JSON: {"decisions":[{"candidate_id":"...","specific":true|false,"instance_text":"..."}]}

Candidates:
[cand0] nominated text: '...'
context: ...

[cand1] nominated text: '...'
context: ...
```

Output cap 384 tokens (`_SPECIFICITY_OUTPUT_TOKENS`), ≤8 candidates/call (`_SPECIFICITY_MAX_ITEMS`),
`instance_text` capped at 300 chars (`_SPECIFICITY_INSTANCE_TEXT_MAX_LEN`). `QwenTasks.verify_
specific_instances` mirrors every other task method's `_call`/`_extract_json`/`_record` pattern
exactly (stage `"18_sufficiency_specificity"`, task `"verify_specific_instances"`) — same model,
same `topology.SUPERVISOR_BASE_OPTIONS` envelope, same isolated endpoint, unchanged for whenever
this is eventually run live.

## B. Schema and fail-closed rules

```json
{
  "type": "object", "required": ["decisions"], "additionalProperties": false,
  "properties": {
    "decisions": {
      "type": "array", "maxItems": 8,
      "items": {
        "type": "object", "required": ["candidate_id", "specific", "instance_text"],
        "additionalProperties": false,
        "properties": {
          "candidate_id": {"type": "string", "enum": ["<host-generated, closed per call>"]},
          "specific": {"type": "boolean"},
          "instance_text": {"type": "string", "maxLength": 300}
        }
      }
    }
  }
}
```

`candidate_id` is host-generated (`f"cand{i}"` per nomination, freshly enumerated every call) —
never a `proposition_id`; the validator structurally cannot introduce or rename proposition
identity, because its schema has no field that could carry one.

Exact fail-closed rules implemented in `confirm_specific_instances`:

1. A non-list `verify_specific_instances` response (any shape) is replaced with `[]` before any
   further processing (`isinstance(raw, list)` guard) — malformed output fails closed.
2. A decision whose `candidate_id` was never offered this call is silently absent from the
   `candidate_by_id` lookup used for iteration, so it can never produce a binding — the validator
   cannot create a candidate.
3. A candidate the validator's response never mentions (no decision at all) is dropped — omission
   fails closed, never defaults to approved.
4. `specific is not True` (explicit `False`, or any non-boolean value) drops the candidate.
5. `specific=True` with a missing, non-string, or empty/whitespace-only `instance_text` drops the
   candidate.
6. `specific=True` with a non-empty `instance_text` that is NOT a literal substring (via
   `canonical_text_contains`) of either the nomination's own `exact_text` or its proposition's
   verified passage is dropped — a fabricated `instance_text` fails closed.
7. `confirm_specific_instances` is called only when `nominations` is non-empty — an already-declined
   nomination call never invokes the validator at all.

The function can only **subtract** from `nominations`; nothing in its control flow can append,
duplicate, or mutate a nomination's own `proposition_id`/`exact_text`.

## C. Provenance preservation

A surviving candidate's returned dict is `{**nomination, "specificity_validated_instance_text":
instance_text, "specificity_model": model_name}` — every original nomination field (`proposition_id`,
`exact_text`, `proposed_role`, `supporting_proposition_ids`) is carried through completely
unchanged. `_bind_role_candidates` records both the original nomination provenance AND the new
validation provenance on the same binding, as additions:

```python
provenance={
    "candidate_source": "model_mapping",
    "detail": "model_nomination_only",
    "model": model_name,                                            # original nomination model
    "supporting_proposition_ids": nomination["supporting_proposition_ids"],  # original (Phase 3)
    "specificity_validated_instance_text": nomination["specificity_validated_instance_text"],  # new
    "specificity_model": nomination["specificity_model"],            # new
}
```

No existing provenance key is overwritten, renamed, or removed.

## D. Contract version — unchanged

No v10 was created. v9's frozen file (`sufficiency_contract.aib_hier_v9.frozen.json`) has an
**empty diff** against its state at the Phase 5 commit (`f7be3175`), and its `combined_hash` is
still exactly:

```
9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586
```

No `category_description` string was touched. The gate's implementation needed no contract-visible
change — it is purely a new mapping-layer function and a new prompt/schema, confirming the original
design boundary held.

## E. Synthetic tests (21 tests, `test_sufficiency_specificity_gate.py`)

**Domain ACCEPT/REJECT pairs** (`SpecificityGateDomainTests`, 10 tests) — all through
`confirm_specific_instances` directly, with a scripted single-decision validator:

| Domain | ACCEPT | REJECT |
|---|---|---|
| Behavior | "participants donated less money" | "a behavioral manifestation occurred" |
| Population | "adolescents in Japan" | "a population was studied" |
| Intervention | "mindfulness training" | "an intervention reduced symptoms" |
| Neural region | "amygdala" | "a neural response was observed" |
| Neural modality | "functional MRI" | "a neural response was observed" |

**Mechanical proofs** (`SpecificityGateMechanicalTests`, 9 tests): validator cannot create a
candidate; validator cannot swap `proposition_id`; malformed (non-list) output fails closed;
ungrounded `instance_text` fails closed; an omitted decision fails closed; an empty nomination list
never invokes the validator; a rejected nomination cannot fill a role (`map_requirement`); an
approved nomination still can; the deterministic-only path (`model_client` omitted) is provably
unaffected.

**Parent propagation** (`SpecificityGateParentPropagationTests`, 2 tests): the c8→c9-shaped fixture
proves propagation proceeds when a nomination survives validation, and does NOT occur when the
same evidence's nomination is vetoed instead.

All 21 use hand-written fake clients — no live model call.

## F. Recorded Phase 5 replay (`sufficiency_phase5_replay.py`, 5 tests)

Replays `.local/sufficiency-nomination-diagnostic-v9-20260930/qwen_calls.jsonl` (Phase 5's own
recorded live trace) through `confirm_specific_instances`, wrapped by a validator scripted to
Cliff's own frozen manual adjudication in `PHASE5_V9_LIVE_RERUN_RESULTS.md` — vetoing **exactly**
one nomination text (extracted byte-for-byte from the trace via `.encode("unicode_escape")`, not
retyped by hand):

```
described a behavioral manifestation of the "anomalous-is- bad" stereotype affecting prosociality
```

(U+201C/U+201D curly quotes, ordinary space before "bad".) Every other nomination Phase 5 actually
produced is approved verbatim. No new adjudication — this script is a mechanical restatement of a
judgment Cliff had already made.

### Per-child/state/count result

| Child | Requirement | Phase 5 (v9, live, ungated) | Phase 6 replay (gated) | Changed? |
|---|---|---|---|---|
| c1 | `c1#suff:neural-manifestation` | `filled`, 1 | `filled`, 1 | No |
| c2 | `c2#suff:behavioral-manifestation` | **`filled`, 3** | **`partially_filled`, 2** | **Yes — this is the fix** |
| c3 | `c3#suff:attitude-manifestation` | `filled`, 1 | `filled`, 1 | No |
| c3 | `c3#suff:implicit-explicit-coverage` | `partially_filled`, 2 | `partially_filled`, 2 | No |
| c4 | `c4#suff:specific-region` | `filled`, 1 | `filled`, 1 | No |
| c5 | `c5#suff:brain-behavior` | `partially_filled`, 1 | `partially_filled`, 1 | No |
| c6 | `c6#suff:brain-attitude` | `filled`, 2 | `filled`, 2 | No |
| c6 | `c6#suff:implicit-explicit-coverage` | `partially_filled`, 2 | `partially_filled`, 2 | No |
| c8 | `c8#suff:trait-construct` | `partially_filled`, 4 | `partially_filled`, 4 | No |
| c9 | `c9#suff:trait-scale-pairing` | `partially_filled`, 4 | `partially_filled`, 4 | No |
| c10 | `c10#suff:culture-existence` | `missing`, 1 | `missing`, 1 | No |
| c11 | `c11#suff:culture-operationalization-pairing` | `missing`, 0 | `missing`, 0 | No |
| c12 | `c12#suff:intervention-effectiveness` | `partially_filled`, 2 | `partially_filled`, 2 | No |

**Only c2 changed.** Every other claim Phase 5's own adjudication called correct (8 of 9 distinct
claims) survives the gate byte-identically — same state, same instance count.

### Why c2 is `partially_filled` rather than simply losing one instance

The two surviving c2 instances are the genuine "visual attention" findings (`visual attention
toward people with facial anomalies` / `influence visual attention when looking at faces with
anomalous anatomy`), confirmed by direct inspection of their `role_bindings`. Both individually
show `behavior_or_behavioral_measure: filled` AND `behavioral_manifestation_evidence: filled` — the
gate did not blank either role. The requirement's overall state is `partially_filled` rather than
`filled` because of a **pre-existing** check, Phase 4's `same_proposition` joint-grounding verifier:
the surviving nominations' own propositions (p15/p5) never share a proposition with
`behavioral_manifestation_evidence`'s own binding (p1), so `_joint_grounded` correctly returns
`False` for both instances. The vetoed nomination was uniquely able to reach `filled` only because
it happened to share proposition p1 with the manifestation-evidence role itself (the exact
self-referential mechanism Phase 5's adjudication described). Removing it does not just drop a
wrong candidate — it reveals that **no** remaining candidate was ever jointly grounded with the
manifestation evidence, so `partially_filled` is the architecturally honest state, not an artifact
of the gate.

## G. Leakage extension + regression

`SpecificityPromptLeakageTests` (3 tests) mirrors `NominationPromptLeakageTests` exactly over
`qwen.specificity_prompt`: every role's `category_description`, and the prompt's two fixed
cross-domain worked examples, carry no hidden benchmark term / provenance token / "networks"
mention; a fixture proves real evidence text containing a hidden-benchmark-shaped word is still
allowed through verbatim (the assertions are about question construction, never evidence content).

### Regression results

| Suite | Result |
|---|---|
| `test_sufficiency_mapping.py` + `test_sufficiency_diagnostic.py` + `test_sufficiency_phase2_replay.py` + `test_sufficiency_replay_real.py` + `test_sufficiency_model_nomination_diagnostic.py` + `test_sufficiency_specificity_gate.py` | **120 passed** |
| `test_sufficiency_phase5_replay.py` | **5 passed** |
| `test_sufficiency_leakage.py` | **17 passed** |
| `experiments/ask_cli_revised/contract_directed/` (full) | **619 passed** |
| `experiments/ask_cli_revised/` (full tree, 111 test files) | **2040 passed, 11 skipped, 2 failed — both pre-existing, unrelated** |

**The 2 failures** are `test_hierarchy_contract.py::RealPinsTests::test_the_generated_pin_
candidate_verifies_the_preserved_artifacts` and `test_hierarchy_e2e.py::MainOrderingTests::
test_preflight_only_reports_readiness_and_the_model_facing_text_with_no_side_effects`, both raising
`HierarchyRejected: hierarchy rejected: pin drift: code input hierarchy_contract.py changed since
the pins were generated`. Confirmed pre-existing and unrelated to this phase: `hierarchy_contract.py`
last changed in commit `d075fa36`, predating every Phase 6 commit, and `git diff f7be3175 HEAD --
hierarchy_contract.py` (Phase 5's commit → this phase's HEAD) is **empty** — Phase 6 never touched
this file. The pin-staleness is a pre-existing artifact of earlier hierarchy work in this same
experiment tree, not something this phase introduced or could fix without regenerating pins outside
this phase's authorized scope.

## v9 byte-identity confirmation

```
git diff f7be3175 HEAD -- experiments/ask_cli_revised/sufficiency_contract.aib_hier_v9.frozen.json
```

→ **empty**. `combined_hash` read directly from the file: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586` — unchanged from Phase 5's approved hash.

## Newly discovered issue

None. The replay's result matched the expectation derivable from Phase 4's `same_proposition`
mechanics once the circular nomination is removed — this was verified empirically (by inspecting
the surviving instances' actual role bindings), not assumed in advance, and no further
architectural gap was found.

## H. Lineage

Appended to `experiments/ask_cli_revised/CONTRIBUTION-LINEAGE.md` (Phase 6 section, does not alter
any prior row).

---

## Answers to the three questions

**1. Is the specificity-confirmation architecture mechanically ready for ONE separately authorized
live v9 mapping rerun?**

Yes, mechanically. The core plumbing is implemented, wired, and tested at 142 tests (120 + 5 + 17)
plus 619 in `contract_directed` — all passing, no live call used anywhere in this phase. The
fail-closed rules are explicit and independently tested (malformed/omitted/ungrounded/hallucinated
candidate_id all proven to drop, never silently pass). v9 is unchanged. Readiness here is purely
mechanical — it answers "would the plumbing work," not "would the live model's actual specificity
judgments be reliable," which only a live run itself can establish.

**2. Did the recorded-output replay remove the c2 false fill without damaging unrelated correct
mappings?**

Yes, confirmed directly: c2 moved from Phase 5's `filled`/3-instances to `partially_filled`/
2-instances, and all 8 other distinct claims Phase 5's adjudication judged correct (c1, c3 ×2, c4,
c5, c6 ×2, c8, and c9's propagated pairing) match Phase 5's own live result exactly — same state,
same instance count, in every one of the 12 other requirement rows checked.

**3. Is there any remaining structural blocker before that live diagnostic?**

None found. The one open question Phase 6 cannot answer from a recorded-output replay — because a
scripted validator is not a live one — is whether the actual `qwen3.5:9b` specificity judge will
reliably reproduce Cliff's own ACCEPT/REJECT distinctions on real, previously-unseen nominations
(including candidates from roles whose declines Phase 5 never exercised with this gate). That is
precisely what a live diagnostic is for, and per instruction, **it was not run in this phase.**
