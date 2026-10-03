# Phase 27a — parent realization: per-claim fallback and surface dedup (offline only)

**Status: Phase 27a implemented and verified offline.** No live model call, no network, no sufficiency or recovery
change, no contract or pin change, no c12/c8 scientific correction.

**Phase 27: ready to close on your acceptance of 27a.** I have not marked Phase 27 closed; that is your decision.
**The empty-result corrective: not started, not part of 27a, and not yet scoped.** Disposition B from Phase 27 still
stands: Phase 28 readiness is FALSE until that separate, approved fix lands.

---

## 1. Starting state

| Item | Value |
|---|---|
| Starting HEAD | `15d4a99f9fe198b647426fa6aedc3c47a66727ea` (Phase 27) |
| Tree at start | clean; Phase-27 commit present |
| Frozen v9 `combined_hash` | `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`, unchanged |
| Live artifacts | none written; the frozen Phase-23 state was read only |

## 2. Exact cause of the whole-call collapse

The supervisor validates the **whole** answer against the schema (`execution_policy._classify`, a `jsonschema`
Draft 2020-12 check). Any violation returns `answer = None`, which is NO ANSWER for every claim. Three distinct HEAD
schema constraints produced whole-answer failures. Each was reproduced with the HEAD schema and the exact validator
message:

| Trigger | HEAD schema constraint | Validator message | Effect |
|---|---|---|---|
| One too-short statement (`"explicit"`) | `statement.minLength = 15` | `'explicit' is too short` | every claim falls back |
| An unknown claim id (`"ghost"`) | `claim_id.enum = [claim ids]` | `'ghost' is not one of [...]` | every claim falls back |
| A duplicated claim id (4 items for 3 claims) | `items.maxItems = N` | `[...] is too long` | every claim falls back |

Replay evidence on the frozen 24-claim state, measured on HEAD `15d4a99f` with the same fakes:

| Scenario | HEAD: state / whole-call status | Grounded / fallback |
|---|---|---|
| Padded faithful restatement | `mixed_model_and_fallback` / `ok` | 20 / 4 |
| Unpadded faithful restatement (3 bare values) | `deterministic_fallback` / `model_no_answer` | **0 / 24** |
| One too-short item among 24 | `deterministic_fallback` / `model_no_answer` | **0 / 24** |

The one-short case is the brief's defect reproduced exactly: one item collapsed twenty-four claims.

## 3. Exact schema correction

| Element | HEAD (Phase 27) | Phase 27a | Layer after 27a |
|---|---|---|---|
| Top level, closed object, `items` required | yes | yes (unchanged) | whole answer (structure) |
| `item` object closed, `claim_id` + `statement` required | yes | yes (unchanged) | whole answer (structure) |
| `claim_id` type | string with `enum` of the ids | string, `maxLength` 256, **no enum** | per item (identity) |
| `statement` `minLength` | 15 | **removed** | per item (editorial) |
| `statement` `maxLength` | 400 | **800** (structural runaway cap) | whole answer only above 800 |
| `items` `maxItems` | N (claim count) | **2N** (runaway cap) | whole answer only above 2N |

Editorial bounds moved to the parent layer as `ps.MIN_STATEMENT_CHARS` (15) and `ps.MAX_STATEMENT_CHARS` (400), applied per
item by `ps.item_reasons`.

**Two deliberate departures from the brief's §3 wording, each forced by its own requirement:**

1. **The `claim_id` enum is removed.** The brief keeps the enum in §3 but requires in §6 and test D that an unknown id
   be recorded and discarded without contaminating siblings. An enum makes an unknown id a whole-answer schema failure, so
   the two requirements cannot both hold. The model's ids are still checked, per item, against the ledger's ids. An
   unknown id cannot reach rendering.
2. **`maxItems` is 2N, not N.** A duplicate, or an unknown id, adds one item beyond the claim count. The output budget
   prices the legitimate shape only: at 400-character statements and this ledger's 44-character ids, N+1 is the most that
   fits the 12,288-character budget, and 2N does not. So the budget guards the legitimate shape (one item per claim, each
   at the editorial maximum), and a runaway above 2N is bounded by the completion cap. Exceeding that cap is truncation,
   which the supervisor already reports as NO ANSWER.

The schema is the model-facing contract. Its change is recorded here, and `contract_sha256` changes with it. Nothing
pinned changed: the frozen v9 contract is unchanged.

## 4. The whole-call versus per-item failure boundary

**WHOLE-CALL failure** (forces every claim to fall back, `whole_call_status` set): the response cannot be safely
recovered as an identifiable item list.

- transport or model exception;
- no usable answer: non-JSON, truncated at the completion cap, or any structural violation the supervisor reports as
  NO ANSWER;
- top-level value that is not an object carrying an `items` list;
- an item that is not a closed `{claim_id: str, statement: str}` object (an extra key, a missing key, or a non-string);
- a runaway: more than 2N items, a `statement` over 800 characters, or a `claim_id` over 256 characters.

**PER-ITEM failure** (only the affected claim falls back; every sibling is judged on its own):

- a too-short statement (`statement_too_short`, under 15 characters after stripping);
- a too-long statement (`statement_too_long`, over 400, within the 800 runaway cap);
- a statement with fewer than two alphabetic words (`statement_not_prose`);
- a duplicated `claim_id` (both copies distrusted; that claim falls back exactly once);
- a missing `claim_id` (that claim falls back);
- an unknown `claim_id` (recorded in `unknown_claim_ids`; never rendered);
- every Phase-27 screen: claim-value fidelity, source-passage fidelity, heterogeneity collapse, and NLI.

A structurally sound answer is never rejected as a whole for its content. A runaway is the one case that is.

## 5. Per-item behaviour, duplicate, unknown, and missing handling

Each claim gets exactly one segment, in ledger order, with a status: `grounded`, `withheld`, `invalid_item`,
`duplicate`, or `missing`. Unknown ids live only in `unknown_claim_ids` and `item_diagnostics`.

- **Duplicate:** both copies are discarded. That claim falls back once. Neither copy is rendered twice, and its siblings
  are unaffected.
- **Unknown:** discarded and recorded. Known claims are unaffected.
- **Missing:** that claim alone falls back.
- **Invalid item:** that claim alone falls back. Its rejected text and re-derived reasons are kept in the record
  (`rejected_text`, `item_reasons`). It is never rendered as a proposed statement.

The record carries `item_diagnostics` (items received, unknown, duplicate, missing, and invalid claim ids). The audit
re-derives it against the segments.

## 6. Surface dedup rule (display only)

**Rule.** Identical surface strings, after whitespace normalization, are shown once, first occurrence kept. The match is
exact, never fuzzy. `"Hadza"` and `"Hadza "` are one value. `"right amygdala"` and `"bilateral amygdala"` stay distinct, and
so do `"implicit bias"` and `"explicit bias"`.

**Applied at** (the only places a value list is presented):

- `parent_synthesis_render.distinct_surface`, used by the deterministic literal for category lists and by the observed
  values of direction/effectiveness summaries;
- `parent_synthesis.authorized_claim_text`, the model-facing envelope for the same two claim kinds. This removes the
  duplicate `- Hadza` line the model would otherwise be shown. The envelope is the screen premise, but dedup changes no
  token set, so every screen is unchanged.

**Not applied to** (the rule is presentation-only, and these are evidence):

- the ledger: every `values` entry, every `proposition_id`, and every `admissible_proposition_ids` entry is retained;
- citations: `format_citations` still names every admissible proposition;
- model-written prose: the renderer never edits a statement the model wrote.

## 7. Evidence-preservation verdict

**Preserved.** On the real state, the Hadza claims (`c10`, `c11`) carry two values and two supports, `p36` and `p69`.
The literal displays `"a named culture or population: Hadza."`. The citation is `[p36, p69]`. The ledger is unchanged.
Surface dedup changes what is printed and nothing else. The audit re-derives every citation against the ledger.

## 8. Frozen replay: before and after

Read-only over `phase23_result.json` and `run/11_verified_ledger.json`, with a fake S2 client. One call per run.

| Scenario | HEAD (27) | 27a | Audit | Notes |
|---|---|---|---|---|
| Padded faithful restatement | 20 / 4 | **20 / 4** | ok | unchanged: the baseline is stable under the new contract |
| Unpadded faithful restatement | 0 / 24 (`model_no_answer`) | **19 / 5** | ok | 3 `invalid_item`: `explicit`, and the two `Hadza` items; `whole_call_status = ok` |
| One too-short item among 24 | 0 / 24 (`model_no_answer`) | **19 / 5** | ok | exactly one `invalid_item`, and exactly one fallback more than the padded baseline |

- **24 claims and 33 gaps** in every run. **One call** in every run. No retry.
- The one-short case's `invalid_item` carries `statement_too_short` and `statement_not_prose`. Its fallback text is
  the Phase-26 literal.
- The padded baseline's four fallbacks are the same screen outcomes as in Phase 27: direction `c12` (`negation_introduced`)
  and the `c8`, `c10`, and `c11` category lists (`hedge_dropped`). They are not new.

## 9. The c12 invariant and the upstream items

- **c12 wrong target.** The faithful realization still grounds the relational statement, and it still carries
  `bias toward people of color`. The ledger value is unchanged, and no c12 logic was added. This is the Phase-27 finding,
  now re-verified: `c12_faithful = grounded, wrong_value_present = true`.
- **c12 adversarial correction.** Still withheld, on the `intervention` and `target_manifestation` slots, with the
  deterministic literal carrying the ledger's value (`test_N`, and the Phase-27 replay test).
- **c8 item #29.** The `c8` trait category list still contains Phase 23a's adjudicated-incorrect `undesirable behaviors`
  item. Its fallback literal states it, unchanged. This is upstream debt and is intentionally not corrected here.

## 10. Focused tests

| Suite | Count | Result |
|---|---|---|
| Phase-26 ledger / render / audit (unchanged) | 52 | pass |
| `test_parent_synthesis.py` (Phase-27 matrix; updated to the corrected contract) | 43 | pass |
| `test_parent_synthesis_wiring.py` (Phase-27 wiring; fakes read ids from the prompt) | 15 | pass |
| `test_parent_synthesis_replay.py` (frozen state; +4 per-item real-state, +3 per-item tamper) | 20 | pass |
| `test_parent_synthesis_per_item.py` (new: the brief's A–O, plus the structural boundaries) | 21 | pass |
| **Focused total** | **151** | **pass** |

The new matrix maps to the brief as follows. **A:** valid, too-short, valid. **B:** 24 claims with one too-short item,
exactly one fallback. **C:** duplicate, siblings survive. **D:** unknown, siblings survive. **E:** missing. **F:** malformed
top level and non-object items are whole-call. **G:** exception is whole-call. **H, I, J:** claim-value, source-passage, and
heterogeneity failures are per claim. **K:** Hadza displays once, both supports kept. **L:** near-but-not-identical values
both display. **M:** rendering never mutates the ledger. **N:** c12 adversarial still withheld. **O:** one call, zero retry.

Two existing matrix tests were updated because they encoded the old contract, and the update is recorded here. The
schema test was rewritten to assert the structural-only shape. The duplicate and unknown-id tests were rewritten to assert
per-item behaviour through the real supervisor, not a raw double that bypassed the schema. The raw double was then deleted
as dead code.

**Two test fakes were changed:** the wiring and replay fakes took claim ids from the schema enum. They now read them from the
prompt's `[claim_id]` headers, which is how a real model reads them.

## 11. Full regression

Run through the same scratch-only, socket-refusing launcher as Phase 27: it refuses the shared Ollama port (11434), the
isolated JUNO port (11435), and any non-loopback host before a byte is sent. `test_live_command.py` (4 tests) is excluded
for the same reason as in Phase 27.

**Result:** **2497 passed, 11 skipped, 3 failed** (470 s). Phase-27 baseline was 2469 passed, so the increase is exactly the 28 new Phase-27a tests (21 per-item, 4 real-state replay, 3 tamper). The three failures are exactly the known baseline set, with unchanged causes: the loopback refusal (now produced by the launcher) and the pin-drift `AssertionError: 3 != 0`. **No new failure.**

Known baseline failures, not fixed: the two pin-drift failures (`test_hierarchy_e2e.py::MainOrderingTests…` and
`test_hierarchy_contract.py::RealPinsTests…`) and the environment-dependent loopback-Ollama failure
(`test_e2e_run.py::RunTopologyGuardTests…`).

## 12. v9 hash and scope

- Frozen v9 `combined_hash`: `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586`, unchanged.
- Not modified: `parent_synthesis_ledger.py`, `sufficiency_engine.py`, `sufficiency_mapping.py`,
  `sufficiency_diagnostic.py`, `sufficiency_recovery_targets.py`, `hierarchy_contract.py`, recovery and search logic, the
  frozen contract, pins, `overview.py`, `overview_guards.py`, `overview_evidence.py`.
- Modified: `parent_synthesis.py`, `parent_synthesis_render.py`, `parent_synthesis_audit.py`,
  `parent_synthesis_test_support.py` (the prompt-id helper), the three Phase-27 test files, and the new per-item test file.
  This document, the Phase-27 supersession note, and the lineage are docs.

## 13. Newly discovered issues

1. **A duplicate-only answer also collapsed on HEAD.** It did so through `maxItems`, not `enum`, which the brief's §5
   did not anticipate. Fixed by the 2N cap.
2. **The budget cannot fit 2N items at the full editorial length.** The cap is therefore a runaway guard only. A
   runaway that exceeds the completion cap is truncation, reported as NO ANSWER. This is an accepted residual risk.
3. **A statement between 401 and 800 characters is per item, but over 800 is a whole answer.** The 800 cap is a
   judgment, recorded in §3. It is not tuned to any claim.
4. **`Hadza` is duplicated in the ledger's category lists** because two corroborating propositions carry the same
   surface value. This is a presentation issue, handled at display. The ledger still holds both.
5. **The c8 `undesirable behaviors` item and the c12 wrong target** are still upstream errors, unchanged, as the brief
   requires.
6. **The model's envelope now shows each distinct value once.** This changes the prompt, and therefore the contract hash
   for the parent stage. It is the intended, documented change.

## 14. Phase status and readiness

- **Phase 27a:** complete, offline, verified.
- **Phase 27:** ready to close on your acceptance of 27a. Not marked closed by me.
- **Empty-result corrective (`empty_result_semantically_allowed`):** not started. It needs its own scoping and
  authorization. Phase 28 readiness remains FALSE until it lands.
- **Next step, requiring explicit authorization:** a Phase-28 live parent-synthesis run. Nothing in Phase 27a runs a model,
  and this document does not authorize one.
