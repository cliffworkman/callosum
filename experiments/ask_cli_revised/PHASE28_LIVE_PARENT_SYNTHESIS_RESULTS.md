# Phase 28 — Live Parent Synthesis: Results (compact technical handback)

**Outcome: FAILED before any pipeline stage completed. Not retried, per the standing one-shot mandate.
A real, previously-undiscovered harness/environment interaction bug was found and precisely diagnosed
offline afterward (no second live/model call). Zero scientific content was produced by the live attempt
itself.**

## Starting state

| Field | Value |
|---|---|
| Branch | `experiment/ask-060-hier11-recpm3-citefix-20260929T212442Z` |
| Starting HEAD | `2cc84ec4469d1f6075fabc11ebe4a105cc6a3802` (Phase 27b) |
| Dirty/clean | Clean throughout (confirmed before authorization, before the live call, and after) |
| Remote-presence verification | Pushed to `origin` before any live work; confirmed `git fetch` + 0 ahead/0 behind |
| Run id | `phase28-live-parent-synthesis-20261003T223145Z` |
| Question hash | `6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030` (q_aib / `BENCHMARK_QUESTION`) |
| Profile | resolve key `T5C`, display name `T5*+C` |
| Frozen v9 combined hash | `9c72dc6a0180e95c55e68a009c366843b671684c19c6ae84ed254f3865305586` — verified before and after |
| Library copy | `.local/e2e-runs/q-aib-hierarchical-t5c-live-20260930/library_copy.sqlite`, fingerprint sha256 `4f2e98a54c92790e791d841ef63e2fd60c4b411246f9c29590c19e56da892523` — **verified identical before the live attempt, after the failure, and after the offline diagnostics below** |

## Effective feature flags (the actual live invocation)

```python
e2e.run_topology(
    "T5C", "aib",
    db_path=<Sept-30 copy>, library_frozen=<its fingerprint>,
    out_dir=<run/>, git_root=ROOT, scored=True, hierarchy=True,
    experiment_authorization=<phase28_authorization.json>,
    hierarchy_loader=lambda q: hc.load_contract(q, pins=None),   # the disclosed pin-drift departure
    sufficiency_model_assist=True, sufficiency_recovery_gate=True, parent_synthesis=True,
)
```
wrapped in `endpoint_guard.isolated_only()` (permits only `127.0.0.1:11435`) and the scratch
`SupervisorCallRecorder` (patches `stages.Supervisor.call`, forwards every call unchanged, records
stage/prompt/schema hashes).

## Disclosed departures from the literal CLI path

1. `run_topology()`'s own `hierarchy_loader=` parameter (a pre-existing DI seam) routes around the
   known, pre-existing pin drift instead of `load_contract_for_live`. `authorization_checker` stayed at
   its real default — the genuine `EXPERIMENT_GATE.md` gate ran against the real authorization file.
2. `run_topology()` called directly rather than via the `e2e.main()` CLI entrypoint, because `main()`
   itself calls `load_contract_for_live` unconditionally before `run_topology()` is ever reached.
3. An independent, scratch-only `SupervisorCallRecorder` (not committed, not in tracked code) wrapped
   `stages.Supervisor.call` at the class level for the run's duration — a pure pass-through observer.

## Model identities (confirmed via liveness-only calls, zero inference, both before and after)

| Model | Digest |
|---|---|
| `qwen3.5:9b` | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` |
| `phi4:14b` | `ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba` |
| `gemma3:12b` | `f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a` |

Ollama `0.34.3`, isolated endpoint `127.0.0.1:11435` (reached via a standing SSH port-forward).

## Stage log (as actually executed — nothing pretended)

| Stage | Status | Detail |
|---|---|---|
| Question load (`00_question.json`) | RAN | Written |
| Request contract (`01_request_contract.json`) | RAN | Hierarchical contract built via `pins=None` |
| Required-model check (`require_models`) | RAN | Succeeded — `/api/tags` against the isolated endpoint, no issue |
| Graph rescue (`04_graph_rescue.json`) | RAN (disabled by design) | `status: "disabled_insufficient_corpus_data"` — a pre-existing, documented, expected non-issue (5/256 papers have extractable references; unrelated to this phase) |
| W1 — initial retrieval / candidate-paper nomination | **CRASHED mid-stage** | Failed inside `discovery.nominate_papers()`, during the very first subquestion's embedding call, before any candidate paper, chunk, or proposition was produced |
| R1 / C1 / U1 / P1 / W2 / R2 / C2 / U2 | **NOT RUN** | Never reached — W1 never completed |
| S1 (per-child Overview, any child) | **NOT RUN** | Zero calls |
| Parent claim ledger | **NOT RUN** | No sufficiency map ever existed to build one from |
| S2 (parent synthesis) | **NOT RUN** | Zero calls |

Elapsed time to failure: **49.4 seconds**.

## Call counts (from the independent `SupervisorCallRecorder`, not self-reported by the system under test)

- Total `stages.Supervisor.call` invocations: **0**
- S2 (`parent_synthesis`) calls: **0**
- `phase28_recorder_calls.json`: `{"total_calls": 0, "s2_call_count": 0, "calls_by_stage": {}, "all_calls": [], "s2_calls": []}`

**S2 attempts = 0 ≤ 1. The "exactly one S2 call" architectural requirement is vacuously satisfied** (no
call was ever attempted), not meaningfully tested. This phase supplies no evidence, positive or
negative, about S2's own behavior.

## U1/U2/recovery/search-terminality/resolved-empty accounting

Not applicable — none of these stages were reached. No sufficiency map, no RecoveryTarget, no
`structured_search_outcomes`, no `ResolvedEmptyOutcome` was ever constructed.

## Parent claim / gap / resolved-empty counts

Not applicable — the parent claim ledger was never built (it requires a final sufficiency map, which
requires W1/U1 to have completed at least once).

## The actual failure (production-written artifact, not inferred)

`run/RUN_FAILED.json`:
```json
{
  "error_type": "EndpointRefused",
  "message": "name resolution for 'huggingface.co' refused by the endpoint guard"
}
```

## Root cause (confirmed via a separate, safe, read-only, offline diagnostic — NOT a second live/model
call, no Ollama contact, no library mutation; see the forensic report for the full narrative and exact
traceback)

`app/backend/model_runtime.py`'s `_load_sentence_transformer()` lazily constructs the real
`sentence_transformers.SentenceTransformer` instance on the **first** `model.encode_texts()` call inside
`discovery.nominate_papers()` — not eagerly when `build_runtime()` itself is called (confirmed: a bare
`build_runtime(..., want_verifier=True)` call succeeds cleanly under the same guard; only the first
`encode_texts()` call fails). That construction path unconditionally performs a HuggingFace Hub
**PEFT-adapter-config existence check** (`transformers.utils.peft_utils.find_adapter_config_file` →
`hf_hub_download` → a real outbound metadata request for `adapter_config.json`) regardless of whether the
base model is already fully cached locally. This is normal, standard `sentence-transformers`/
`transformers` library behavior on recent versions, and is harmless and silent under genuine internet
access (as in every prior live phase, none of which used a network guard) or under a genuine
no-internet condition (`huggingface_hub`'s own request wrapper catches ordinary connection errors and
falls back to the local cache). It is **not** harmless under this phase's own
`endpoint_guard.isolated_only()` wrapper: that guard raises a non-standard `EndpointRefused` exception at
`socket.getaddrinfo`, a type `huggingface_hub`'s offline-fallback `except` clauses do not recognize, so
it propagates as a hard crash instead of a graceful cache fallback.

**This is a flaw in this phase's own scratch harness design — wrapping the entire `run_topology()` call
(including local embedding-model construction, which has nothing to do with which Ollama port is used)
in a network guard that was never exercised by any prior live phase — not a defect in the Phase 27b
production pipeline, and not a scientific finding about T5C, parent synthesis, or the hierarchical
pipeline's own behavior.**

## Mechanical/`pytest` baseline

Unaffected — the offline pre-flight gate run before authorization (490 passed, the same 3 pre-existing
baseline failures) is untouched by this live attempt's outcome; no new test was run or needed to explain
this failure (it was reproduced directly against production code, read-only, outside pytest).

## Known-tracer comparison (c8/c12, Phase 23A)

Not applicable. No sealed ledger, no U2 nominations, and no parent claims were ever produced by this
run, so there is nothing to compare against Phase 23A's adjudicated tracer cases. **This phase supplies
zero evidence about whether the c8/c12 scientific concerns recur under T5C/parent-synthesis** — that
question remains exactly as open as it was before this phase.

## Did Phase 28 achieve its empirical purpose?

**No, not for its original intended purpose** (observing the full W1→S2 pipeline with parent synthesis
live, for the first time, under T5C). **It did achieve a different, real, legitimate purpose**: an
actual live-authorized one-shot attempt surfaced a genuine, previously-undiscovered, precisely-diagnosed
infrastructure interaction hazard (network-guard scoping vs. `transformers`' unconditional PEFT-adapter
probe), with a byte-exact reproducible root cause. Per the governing instruction, this is not something
to patch and silently rerun — it is reported as the phase's actual, honest result.

## Recommendation for the next phase

A **Phase 28 retry** (fresh authorization required — this one is fully consumed and closed as FAILED,
not to be reused) with one of these corrected harness designs:

1. **Remove `endpoint_guard.isolated_only()` from the live call entirely**, matching the precedent set
   by every prior live phase (13/15/21/23, the Sept-30 T5C run) — none of them used any network guard
   during their own live call, relying instead on the production code's own configured endpoints. The
   "no accidental shared-Ollama access" property can instead be verified by inspecting
   `phase28_recorder_calls.json`'s `endpoint_kind`/model fields after the run, rather than enforced by a
   live-blocking guard.
2. **Or**, if an active guard during the live call is still wanted, set `HF_HUB_OFFLINE=1` and
   `TRANSFORMERS_OFFLINE=1` in the process environment before constructing the runtime — the exact
   precedent `contract_directed/offline_pytest.py` already establishes for its own (test-only) use of
   this same guard.

Either fix is a harness-only change (the scratch runner, never tracked/production code) and needs no
change to `experiments/ask_cli_revised/`'s own pipeline modules.
