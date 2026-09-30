# Phase 3 — bounded fixes from the Phase 2 diagnostic (2026-09-30)

No live model calls, no new E2E, no recovery, no retrieval, no Overview regeneration, no parent
synthesis anywhere in this increment. Starting HEAD `593e834c` (verified before any change).

## Commits (`593e834c..HEAD`)

| Commit | What |
|---|---|
| `95921f5e` | A: `derive_instance_key` (Finding 1) + B: anchor-based dedup (Finding 2) |
| `40f45622` | C: tightened c1/c2/c5 role semantics + D: v9 candidate contract |
| `8a16f86d` | Synthetic benchmark-neutral semantic-exclusion tests (Finding C) |
| `bd61ea53` | E: offline replay of Phase 2's recorded outputs through the corrected mapper |
| *(this commit)* | Lineage append + this report |

**Files changed:** `sufficiency_engine.py`, `sufficiency_mapping.py`, `sufficiency_diagnostic.py`,
`sufficiency_authoring.py`, `test_sufficiency_mapping.py`, `test_sufficiency_authoring.py`,
`test_sufficiency_freeze.py`, new `sufficiency_contract.aib_hier_v9.frozen.json`, new
`sufficiency_phase2_replay.py` + `test_sufficiency_phase2_replay.py`, `CONTRIBUTION-LINEAGE.md`.
**Never touched:** `sufficiency_contract.aib_hier_v8.frozen.json`,
`sufficiency_contract.aib_hier_v8.review.json`,
`sufficiency_model_nomination_authorization.json`, `MODEL_NOMINATION_DIAGNOSTIC_RESULTS.md`,
`hierarchy_contract.py`, or any hierarchy pin (all confirmed byte-identical via `git diff`).

## A — the exact instance-key fix

`sufficiency_engine.derive_instance_key(role_bindings, *, root_key=None)`: a deterministic,
content-derived key — canonical-json (sorted) of each role's `{state, proposition_id, exact_text}`,
sha256, first 16 hex chars, prefixed by the instance's pre-fork `root_key` (a multi-instance
base's `unit_id`, or `None`). Applied **once**, by the caller (`map_requirement`/
`map_paired_requirement`), **only when forking actually produced more than one result** — the
overwhelmingly common case (`len(forks) <= 1`, always true when `model_client` is omitted) leaves
the original key completely untouched. `_fork_instances_over_role` itself no longer assigns any
key during forking (the positional `f"{parent_key}#{index}"` scheme that caused the collision is
gone entirely). Proven adversarially: two independently-forking roles × 2 values each → 4 uniquely
keyed instances, stable across replay (`InstanceKeyCollisionTests`).

## B — the exact deduplication rule

In `nominate_with_model`: grounded nominations sharing **both** the same normalized `exact_text`
**and** the same physical evidence anchor (`(paper_id, chunk_id, span_id)`, read from
`units_by_child`'s new `proposition_anchor` field — the codebase's own already-existing
`build_units`/locator identity, never a parallel notion) collapse into one nomination. A
proposition with **no known anchor** (e.g. a hand-built fixture) is **never** collapsed with
anything — conservative default, matches every pre-Finding-2 test exactly. Distinct exact-text
values from the same anchor stay distinct; genuinely different anchors are never merged even on
identical text. Proven adversarially (`AnchorDedupTests`, 6 tests): same-anchor duplicates
collapse; distinct anchors don't; distinct values within one anchor still fork; grounding survives
dedup.

## How supporting-proposition provenance is preserved

Each collapsed nomination keeps one **deterministic primary** `proposition_id` (lexicographically
lowest of the group) plus a new `supporting_proposition_ids` list (every contributing id, sorted,
never discarded), threaded into the role binding's `provenance` dict
(`provenance["supporting_proposition_ids"]`) alongside the existing `candidate_source`/`detail`/
`model` fields. Nothing is ever silently dropped.

## Structural replay — before (Phase 2 actual) vs after (corrected mapper, Phase 2's recorded outputs)

`sufficiency_phase2_replay.py` runs the CORRECTED mapper over Phase 2's own recorded raw model
outputs (`.local/sufficiency-nomination-diagnostic-20260930/qwen_calls.jsonl`) — zero live calls.
**This tests A/B structural accounting only — Phase 2's prompts used v8 wording, so a clean replay
is NOT evidence that v9's semantics (Finding C) solve anything.**

| Child | Requirement | Phase 2 state | Phase 2 #instances | Corrected state | Corrected #instances |
|---|---|---|---|---|---|
| c1 | neural-manifestation | `filled` | 4 | **`partially_filled`** | **1** |
| c2 | behavioral-manifestation | `partially_filled` | 1 | `partially_filled` | 1 |
| c3 | attitude-manifestation | `filled` | 1 | `filled` | 1 |
| c3 | implicit-explicit-coverage | `partially_filled` | 2 | `partially_filled` | 2 |
| c4 | specific-region | `filled` | 2 | `filled` | **1** |
| c5 | brain-behavior | `filled` | 5 | `filled` | **2** |
| c6 | brain-attitude | `filled` | 5 | `filled` | **2** |
| c6 | implicit-explicit-coverage | `partially_filled` | 2 | `partially_filled` | 2 |
| c8 | trait-construct | `partially_filled` | 8 | `partially_filled` | **4** |
| c9 | trait-scale-pairing | `partially_filled` | 8 | `partially_filled` | **4** |
| c10 | culture-existence | `missing` | 1 | `missing` | 1 |
| c11 | culture-operationalization-pairing | `missing` | 0 | `missing` | 0 |
| c12 | intervention-effectiveness | `partially_filled` | 2 | `partially_filled` | 2 |

**c8→c9 propagation under dedup, inspected directly:** c8 now correctly reports 4 distinct traits
(down from 8 — the p9/p20 duplicate-anchor artifact is gone), each with `supporting_proposition_
ids` naming both original propositions. c9's pairing sees exactly those 4 corrected parent
instances and produces exactly 4 paired instances (down from 8), each still honestly
`named_scale_or_instrument: missing` (no scale named in c9's own scope — unchanged, correctly
evidence-limited). The 2:1 propagation ratio (8→4 parent, 8→4 child) held exactly, confirming B's
fix propagates through the parent-context chain with no extra distortion.

## Did any state change *solely* from the accounting corrections?

**Instance counts:** yes, for every affected requirement (c1, c4, c5, c6, c8, c9) — all reductions,
never increases, exactly as intended.

**Aggregate `state`:** unchanged for c4, c5, c6, c8, c9. **c1 is the one exception** —
`filled` → `partially_filled` — and this is a **genuinely new, non-obvious finding**, not a simple
count reduction:

### Newly discovered issue (reported, not fixed — out of this increment's authorized scope)

c1's two model-nominated roles both collapse, post-dedup, to the SAME primary proposition
(`p11`, the lexicographically-lower of the anchor-duplicate pair `{p2, p11}`). c1's THIRD,
deterministically-filled role (`neural_manifestation_evidence`) independently resolves to `p2` —
because the deterministic path picks `unit["proposition_ids"][0]` under `units_by_child`'s own
**"responsive-to-this-child-first"** ordering, a completely different selection rule from B's
**"lexicographically lowest"** primary-id choice. `p2` and `p11` are the *identical physical
evidence* (same chunk/span, confirmed in Phase 2's own audit) — but the existing `same_proposition`
joint-grounding check compares proposition_id **strings**, not physical anchors, so it now
(correctly, per its own literal rule) judges the instance incomplete. c4 has the identical
duplicate-proposition shape but happens not to regress, because its own per-child unit ordering
coincidentally already put `p11` first.

This is not a Finding 1/2/C regression — every individual binding is still correctly, literally
grounded. It is a **second-order interaction** between B's fix and the pre-existing
`same_proposition` check, and it is the same underlying gap Finding 2 named (proposition-identity
vs. physical-anchor-identity not fully reconciled everywhere), now visible in the joint-grounding
check rather than the instance-count accounting. **Not fixed here** — extending the relational
verifier to treat same-anchor propositions as interchangeable would itself be a form of
cross-proposition entity resolution, which the explicit HARD SCOPE says not to introduce in this
increment. Flagged as a concrete candidate for a future, separately-authorized increment.

## Synthetic semantic-exclusion test results (Finding C)

No live model call exists in this increment, so these tests prove the **bounded, honest claim**:
the tightened v9 wording (a) contains the intended exclusion language, (b) names no
benchmark-specific modality/instrument, and (c) correctly reaches the model-facing prompt
alongside a confusable **synthetic** excerpt (hippocampus / self-report prejudice scale — never
amygdala/EBQ/q_aib wording). All 5 tests pass (`SemanticExclusionTests`). **This is not evidence a
model would actually comply** — that needs a separately-authorized live rerun.

## v8 → v9 hashes and exact diff

```
v8 combined_hash (reviewed, unchanged):
  9de276b19d2e5afee5f532d64c6a678de6e59a9f41f37198fa00409c5f3094ac
v9 combined_hash (UNREVIEWED_CANDIDATE):
  9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586
```

Programmatically diffed, leaf by leaf, across the full `per_child` structure. **Exactly 3 leaf
diffs**, all `category_description` strings, plus their 3 mechanically-consequent per-child
hashes:

- `c1.neural_measure_or_modality`: `"a neural measure or imaging modality"` →
  `"the method or modality used to measure neural activity or structure (not the anatomical
  region itself, and not the observed neural response or finding)"`
- `c2.behavior_or_behavioral_measure`: `"a named behavior or behavioral measure"` →
  `"an observed behavior, behavioral choice or action, or a task or measure of behavior (not a
  self-report attitude, belief, or prejudice questionnaire)"`
- `c5.behavior_or_behavioral_measure`: same change as c2

All 8 other children (c3, c4, c6, c8, c9, c10, c11, c12) are **byte-identical** between v8 and v9.
`supersessions` and `status` text unchanged. **No unintended contract-visible change.**

## Any newly discovered issue

Documented above (the `same_proposition`/anchor-dedup-primary-id interaction). No other issue
found.

## Full regression results

- Full targeted sufficiency suite (9 files): **173 passed**.
- `contract_directed/` suite: **619 passed**.
- Full `experiments/ask_cli_revised` tree: **2006 passed, 11 skipped, 2 failed** — the same 2
  pre-existing `hierarchy_contract.py` pin-drift failures, reproduced unchanged and confirmed
  unrelated (identical failure at the exact starting HEAD `593e834c`, reconfirmed again here; no
  hierarchy pin touched or installed in this increment).

## Recommendation on v9 readiness

**v9 is ready for your review of its hash and the 3-string diff above.** It is **not** yet ready
for a live model-nomination rerun until you separately authorize one — that rerun is the only way
to test whether Finding C's tightened wording actually changes model behavior (this increment's
replay cannot, by its own stated limitation). Before authorizing that rerun, you may also want to
weigh the newly-discovered `same_proposition`/anchor-primary-id interaction above — it doesn't
block a v9 rerun (every affected role name is unchanged; the interaction is orthogonal to Finding
C), but it does mean a future rerun's OWN c1 result may come back `partially_filled` even when
individually correct, which is worth knowing going in rather than re-discovering live.

Stopping here, per instruction.
