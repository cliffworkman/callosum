# Model-nomination diagnostic — live replay results (2026-09-30)

**Experiment:** `q_aib_sufficiency_model_nomination_diagnostic_v1` · **Model:** `qwen3.5:9b` · **Thinking:** OFF
**Authorized by:** Cliff, `2026-09-30T16:38:30-04:00` · **Frozen contract hash:** `9de276b19d2e5afee5f532d64c6a678de6e59a9f41f37198fa00409c5f3094ac`
**Authorized executions:** 1 · **Actual live executions:** 1 (zero retries — every call completed mechanically clean)

This is the frozen experiment output. Per the authorization's own terms, nothing below has been
silently repaired after inspection — findings that look like bugs are reported as findings, not
fixed and re-run.

---

## 1. Execution summary

| | |
|---|---|
| Live model calls | 15 |
| Mechanical failures | 0 (every call: `provider_ok`/`parse_ok`/`validation_ok` = True, `done_reason="stop"`, `outcome="usable"`) |
| Retries | 0 |
| Total wall time | 68.89 s (44.83 s one-time cold model load on the first call + 24.06 s across the remaining 14) |
| `thinking_chars` | 0 on every call (thinking OFF genuinely held throughout) |
| Total prompt tokens | 6,213 |
| Total generated tokens | 576 |
| Endpoint | `http://127.0.0.1:11435` (isolated, JUNO SSH forward) |
| **Effective model options** (actual, not just tag+thinking) | `{"num_ctx": 12288, "num_predict": 256, "temperature": 0, "seed": 42, "num_thread": 6, "num_batch": 512}`, `keep_alive="30m"`, `wall_timeout=1200.0s` — identical to `topology.SUPERVISOR_BASE_OPTIONS` except `num_predict`, which the worker-task output cap (256) overrides per call, exactly as every other `QwenTasks` worker method already behaves |

**Artifacts (local, gitignored per `.local/` convention):**

| Artifact | Path | sha256 |
|---|---|---|
| Full result (both maps) | `.local/sufficiency-nomination-diagnostic-20260930/result.json` | `61e7ca72835282463724072a05d07655f190059626426e1b6725c498c548cc49` |
| Full call trace | `.local/sufficiency-nomination-diagnostic-20260930/qwen_calls.jsonl` | `ed4cc3aff967c5e84da5c50c84c19f733a7528d849a7baa1ba1f5baee289026e` |

Committed artifacts: `sufficiency_contract.aib_hier_v8.review.json`, `sufficiency_model_nomination_authorization.json` (both `experiments/ask_cli_revised/`).

---

## 2. Per-child comparison (all 11 children)

| Child | Det. state | Model state | Newly filled | Remaining missing/partial | Limited by | What recovery would target |
|---|---|---|---|---|---|---|
| c1 | `partially_filled` | **`filled`** | `brain_region_or_network` (amygdala) completes the alt-group | — | — | n/a (now filled) |
| c2 | `partially_filled` | `partially_filled` (unchanged) | none (model declined on its own 10 candidates) | `behavior_or_behavioral_measure` | evidence-limited (candidates were summary sentences, no specific measure named) | a named behavioral measure for the dehumanization/prosociality outcome |
| c3 (manifestation) | `filled` | `filled` (unchanged) | — | — | — | n/a |
| c3 (cardinality) | `partially_filled` | `partially_filled` (unchanged) | none (no model-nominated role on this requirement) | `explicit` category evidence | evidence-limited | explicit-attitude category evidence |
| c4 | `partially_filled` | **`filled`** | `named_brain_region_or_network` (amygdala) | — | — | n/a (now filled) |
| c5 | `missing` | **`filled`** | `behavior_or_behavioral_measure` (EBQ — **adjudicated ambiguous**, see §3) | — | — | n/a, but see finding re: category fit |
| c6 | `missing` | **`filled`** | `attitude_type_or_measure` (EBQ — correct) | — | — | n/a (now filled) |
| c8 | `missing` | **`partially_filled`** | 4 distinct traits identified (IAT/EBQ negative attitudes, just-world beliefs, affective empathy, DG generosity) | `relationship_to_bias_manifestation` per trait | mapper/evidence mixed — see §4 finding on instance inflation | a manifestation link per named trait |
| c9 | `missing` (0 instances) | **`partially_filled`** (8 instances) | Trait identity propagated from c8 (parent-context) into 8 paired instances | `named_scale_or_instrument` on every instance | **evidence-limited** — no candidate unit in c9's own scope names a scale/instrument for these traits | a named scale/instrument for any of the 4 traits |
| c10 | `missing` | `missing` (unchanged) | none (model correctly declined — candidates only assert universality, name no specific culture/population) | `named_culture_or_population` | evidence-limited (own-scope candidates are generic, honestly declined) | a specific named culture/population |
| c11 | `missing` (0 instances) | `missing` (0 instances, unchanged) | none (c11 has no `parent_context_roles` — confirmed in Phase 1 design review; it never inherits from c10 at the sufficiency layer) | both roles | evidence-limited (candidate_units empty/non-matching) | culture+operationalization pairing evidence |
| c12 | `partially_filled` | `partially_filled` (unchanged) | none (model correctly declined on both roles across both candidate units — summary/implication sentences, no described intervention) | `intervention`, `target_manifestation` | **evidence-limited** — this paper is observational, not an intervention trial; a genuine "no" | an actual intervention description |

**Headline result: 5 of 11 children changed state** (c1, c4, c5, c6: `missing`/`partial` → `filled`; c8, c9: `missing` → `partially_filled`, with c9 specifically proving the parent-propagation fix live — c8's model-discovered trait instances were visible to c9's pairing logic in the same computation, exactly as designed).

---

## 3. Manual adjudication — every accepted model-sourced binding

Deduplicated to distinct **(child, role, exact_text)** semantic claims (28 raw binding-rows across
forked instances collapse to these; proposition-id duplication is itself Finding 2, §4).

| Child | Requirement | Role | Proposition(s) | Exact text | Adjudication | Note |
|---|---|---|---|---|---|---|
| c1 | neural-manifestation | `brain_region_or_network` | p2, p11 | "the specific amygdala response" | **Correct** | Amygdala is unambiguously a specific named region; span includes "response" (part of the finding, not just the name) |
| c1 | neural-manifestation | `neural_measure_or_modality` | p2, p11 | "specific amygdala response" | **Incorrect** | "Amygdala response" is a *finding*, not an imaging modality/measure (fMRI etc. is never named in this span). The model answered both "is this a brain region" and "is this a measure/modality" prompts with the same salient phrase, not distinguishing the two categories. Harmless here only because c1's role-completion is an alt-group and `brain_region_or_network` alone already satisfies it. |
| c4 | specific-region | `named_brain_region_or_network` | p2, p11 | "the specific amygdala response" | **Correct** | Same region, independently re-discovered for a different child (no cross-child caching, as designed) |
| c5 | brain-behavior | `behavior_or_behavioral_measure` | p14, p3, p7, p17, p26 | "scores on the Explicit Bias Questionnaire" | **Ambiguous** | A self-report attitude questionnaire is a stretch for "a named *behavior or behavioral measure*" (contrast with the genuine behavioral measure named elsewhere in the same paper — "less generosity in the DG" — which was never offered to c5's own candidate scope). Within what c5 was actually shown, this may be the best available candidate, or the model over-reached the category boundary. |
| c6 | brain-attitude | `attitude_type_or_measure` | p17, p3, p7, p14, p26 | "Explicit Bias Questionnaire" | **Correct** | Textbook fit for "a named attitude type or measure" |
| c8 | trait-construct | `individual_difference_trait_or_construct` | p20, p9 (×4 each) | "negative attitudes (IAT and EBQ)" / "social cognitive biases (just-world beliefs)" / "emotional dispositions (affective empathy)" / "undesirable behaviors (less generosity in the DG)" | **Correct** (all 4) | Clean, literal extraction of exactly the four constructs the source sentence itself enumerates, including their parenthetical sub-labels |

**Totals:** 6 distinct semantic claims judged; **5 correct, 1 ambiguous, 0 outright incorrect at the region/instrument level** (c1's `neural_measure_or_modality` binding is the one **incorrect** categorization, noted above — 7 distinct claims total, 5 correct / 1 ambiguous / 1 incorrect).

**Rejected nominations:** zero. Every schema-valid raw model nomination also passed
`canonical_text_contains` grounding — no false negatives from the grounding gate itself. Separately,
the model **declined outright** on 8 of 15 calls (c2, c10, both c12 roles × both its units) — manually
reviewed every one (§ below): all 8 are genuine, correct declines (the offered candidates were
summary/implication sentences naming no specific culture, intervention, or behavioral measure — see
the literal quotes in the handback). **No evidence of a false negative** — the model did not miss an
available, nameable candidate within what it was actually shown.

**Benchmark isolation check:** "EBQ", "IAT", and "DG" — three of the six literal hidden-benchmark
terms from `_HIDDEN_BENCHMARK_TERMS` — appear in *accepted, correct* nominations above, because
they are genuine instrument/task names in the real retrieved evidence (paper 67's own text). This is
the explicitly-intended behavior (§ BENCHMARK ISOLATION in the authorization): these terms were never
constructed by the prompt/contract, only read from already-verified evidence, and were correctly not
filtered.

---

## 4. Two architectural findings (mapper-limited, not evidence-limited)

### Finding 1 — `instance_key` collision when 2+ roles in one requirement both fork

c1 has two independently model-nominated roles (`neural_measure_or_modality`,
`brain_region_or_network`), each returning 2 grounded candidates from the same 2-proposition pool.
`_fork_instances_over_role` forks sequentially per role, producing **4 instances**, two of which
(both by construction of the naming scheme `f"{parent_key}#{index}"`) collide on the literal string
`"None#1"` — confirmed distinct instances with different role-binding content sharing one key:

```
None:      neural_measure=p2,  brain_region=p2
'None#1':  neural_measure=p2,  brain_region=p11
'None#1':  neural_measure=p11, brain_region=p2      <- SAME KEY as the row above, different content
'None#1#1': neural_measure=p11, brain_region=p11
```

This is **not** a grounding/correctness bug — every individual binding is independently, literally
grounded, and c1's own requirement-level `state` is correctly `filled`. It is a **non-uniqueness bug
in fork instance-key generation**: any future consumer keying by `instance_key` (a report, a UI, a
downstream join) cannot distinguish the two colliding instances. Confirmed isolated to this one
shape (a non-multi-instance requirement with 2+ independently model-nominated roles) — no other
child in this run triggered it. **Not fixed here**, per the authorization's explicit scope.

### Finding 2 — duplicate verified propositions inflate reported instance/discovery counts

Rigorously confirmed (exact `evidence_anchor_chunk_id`/`evidence_span_id` comparison, not just
matching quote text): **every** group of "multiple proposition_ids" behind an accepted nomination
in this run shares the **identical physical evidence anchor**:

| Group | Proposition ids | Shared anchor (chunk, span) |
|---|---|---|
| c1/c4 amygdala | p2, p11 | (34974, e7) |
| c8 traits | p9, p20 | (35111, e2) |
| c5/c6 EBQ | p14, p3, p7, p17 | (35068, e4) |
| c5/c6 EBQ | p26 | (35068, e8) |

`units_by_child`'s own existing docstring already explains *why* a unit can carry several
proposition_ids (independent per-child responsiveness tagging over the same deduplicated passage).
The **deterministic** path absorbs this silently — `proposition_ids[0]` always picks one and moves
on. Correction #4 deliberately removed that silent collapsing for the model path (a closed
proposition-id enum, never an index), which is **structurally correct** per its own mandate — but
the side effect, demonstrated live here, is that `nominate_with_model`'s "return ALL grounded
nominations" design (correction #5) creates one grounded binding **per duplicate proposition_id**,
not one per distinct physical finding. Net effect on this run's reported instance counts:

- c8: **4 real distinct traits reported as 8 instances** (2× inflation)
- c5/c6: **1 real finding reported as 5 instances each** (5× inflation)
- c1/c4: contributes to Finding 1's 4-instance fan-out (2× from this cause alone)

This is the dominant cause of the apparent "over-flagging" a naive read of instance *counts* would
suggest — it is not the model hallucinating or the engine mis-grounding; every individual binding is
correct. It is an interaction between a pre-existing evidence-layer property (duplicate
propositions per physical anchor) and the new path's correct-per-its-own-spec refusal to collapse
distinct proposition identities. **Recommended future direction** (not built here): deduplicate the
*reported* instance/discovery count by evidence anchor (chunk_id + span_id) while still preserving
per-proposition citability in the underlying data — a display/aggregation-layer fix, not a grounding
or nomination-logic change.

A smaller, related **efficiency** observation: forking re-issues an identical `nominate_with_model`
call once per existing fork even when `units_here` hasn't changed (c1's `brain_region_or_network`
role was queried twice — calls 1 and 2 — with byte-identical input, returning the same 2
nominations both times). Harmless to correctness, but a small avoidable cost.

---

## 5. Global statistics

| | |
|---|---|
| Model calls | 15 |
| Wall time | 68.89 s |
| Raw model-reported nominations (sum across calls) | 26 |
| Grounding-rejected | 0 |
| Distinct (role, proposition_id, exact_text) tuples | 24 (2 less than 26 — the c1 duplicate-call efficiency note above) |
| Distinct real-world semantic claims (collapsing duplicate-anchor propositions) | 7 |
| Manual adjudication | 5 correct / 1 ambiguous / 1 incorrect |
| Children with a changed state | 5 of 11 (c1, c4, c5, c6: → `filled`; c8: → `partially_filled`; c9: `missing`(0) → `partially_filled`(8)) |
| Model declines (0 nominations) | 8 of 15 calls — all 8 manually reviewed, all genuine correct declines, zero false negatives found |
| Over-flagging reduced? | **Yes, at the binding level** — every accepted binding is individually literally grounded, and the model correctly declined 8/15 times rather than forcing a fit. **At the reported-instance-count level, no** — Finding 2 shows counts can be inflated 2–5× by duplicate-anchor propositions, which is a real residual over-flagging risk if instance *count* (rather than binding correctness) were ever read as a calibration signal. |
| Evidence of under-flagging / false completion | None found. Every `filled` state traces to a genuinely correct or at worst ambiguous (never fabricated) binding; no requirement was marked complete on a hallucinated or ungrounded candidate. |

---

## 6. Readiness decision — evaluated, NOT activated

**Criterion 1 (reasonably calibrated, not systematically over-flagging):** **Not yet met.**
Individual binding correctness is strong (5/6 distinct claims correct or defensible), but Finding 2
demonstrates the *reported instance/discovery count* is not yet a trustworthy signal on its own —
it can overstate distinct findings by 2–5× purely from duplicate-anchor propositions, independent of
any model error. A recovery-gating decision keyed off "how many instances are still missing" would
be acting on an inflated denominator.

**Criterion 2 (accurate under exhaustive manual inspection):** **Partially met.** 5 of 6 distinct
semantic claims are correct; one (c1's `neural_measure_or_modality`) is a real category-confusion
error (though harmless to the actual requirement outcome via the alt-group), and one (c5's EBQ
binding) is a genuine category-boundary ambiguity. Zero false negatives found among declines. This
is a small, single-run sample (6 distinct claims) — not enough to certify accuracy at the confidence
a recovery-gating decision should require.

**Recommendation: NOT READY for a separately-authorized recovery-gating experiment**, with two
concrete, fixable failure modes to close first:
1. Fix Finding 1 (instance_key uniqueness across multi-role forks).
2. Add an evidence-anchor-based dedup to the reported instance/discovery count (Finding 2) so
   "instances found" reflects distinct physical findings, not distinct proposition rows.

Neither finding was repaired in this run, per the authorization's explicit scope. Recovery gating
remains OFF; no code in this diagnostic or its call path was changed after observing these results.

---

## 7. Contribution lineage (append-only)

| Date | Role | Contributor(s) |
|---|---|---|
| 2026-09-30 | Phase 2 experimental authorization | Cliff Workman |
| 2026-09-30 | Phase 2 live-client wiring, execution, manual adjudication, and analysis | Claude |

No external scholarly method or tool is implemented by this experiment (unchanged from Phase 1's
assessment in `CONTRIBUTION-LINEAGE.md`, which this entry does not alter — see that file for the
architecture's own origin/elaboration/implementation lineage).
