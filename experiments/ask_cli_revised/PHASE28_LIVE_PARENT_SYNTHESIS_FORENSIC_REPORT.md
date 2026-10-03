# Phase 28 — Live Parent Synthesis: Forensic Report

**This run failed 49.4 seconds in, before any pipeline stage produced a single candidate paper,
proposition, or model call. There is no answer to trace a biography for.** This report exists anyway,
in the same spirit the governing instruction set out: the one-shot's actual outcome is the result,
preserved and diagnosed rather than hidden or silently retried. What follows is an honest, narrow
account of exactly how far the run got, what stopped it, and the precise mechanism behind the stop —
established afterward by a safe, read-only, offline diagnostic that touched no Ollama endpoint, made no
second live/model call, and mutated nothing.

## Legend

- W = retrieval/search · R = responsiveness review · C = sealing/claim construction · U = semantic
  sufficiency mapping · P = recovery planning · S1 = child synthesis · S2 = parent synthesis.
- "stage X" means a pipeline stage name above; "ctx N" (not used in this report — no semantic request
  contexts were ever reached) would mean a local semantic request-context identifier.

## What actually ran, in order

1. **Question load.** `run/00_question.json` written: the hierarchical `aib` request, hash
   `6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030`, loaded via the disclosed
   `hc.load_contract(question, pins=None)` seam. This succeeded cleanly — the hierarchy content itself
   (11 children, 13 requirements, the frozen v9 sufficiency contract) is structurally fine; nothing here
   indicates any problem with the hierarchy or the pins.
2. **Request contract built.** `run/01_request_contract.json` written.
3. **Required-model check.** `e2e.require_models(clients, profile)` succeeded: a real HTTP call to
   `GET /api/tags` against the isolated JUNO Ollama (`127.0.0.1:11435`) confirmed `qwen3.5:9b`,
   `phi4:14b`, and `gemma3:12b` are present with the exact digests recorded in the authorization record.
   This is the **only** real network traffic this run ever produced — a metadata listing call, not an
   inference call.
4. **Runtime construction.** `build_runtime(db_path, want_verifier=True, want_qwen=False)` — this
   constructs the local retrieval/embedding and NLI-verifier wrappers. **This step itself completed
   without error** (confirmed independently afterward, see "Root-cause diagnosis" below) — the failure
   is not here, even though it is the most obvious place to suspect a local-model-loading problem.
5. **Graph rescue (Stage 3, disabled by design).** `run/04_graph_rescue.json`:
   `status: "disabled_insufficient_corpus_data"`, `papers_with_references: 5`,
   `total_live_papers: 256`, `coverage_fraction: 0.0195`. This is an existing, documented, expected
   non-issue (citation-convergence rescue needs bulk reference extraction this library copy doesn't
   have) — not something this phase caused or needs to resolve.
6. **W1 — candidate-paper nomination begins.** `execute()` enters its per-subquestion loop
   (`for subquestion in subquestions: ... discovery.nominate_papers(conn, subquestion_text=text,
   model=rt.model, vector_store=rt.vector_store, axis_cache=sink.axis_cache)`). On the **first**
   subquestion, inside `nominate_papers()`, the very first line is
   `subq_vec = model.encode_texts([subquestion_text])[0]` — embedding the subquestion text so it can be
   compared against the library's precomputed paper/chunk vectors.
7. **CRASH.** `model.encode_texts(...)` raised `EndpointRefused: name resolution for 'huggingface.co'
   refused by the endpoint guard`. `run_topology()`'s own exception handler wrote `run/RUN_FAILED.json`
   with exactly that `error_type`/`message` and re-raised; my runner's outer `except` caught it, wrote
   the (empty) recorder report, and returned exit code 3. **No retry occurred.**

No candidate paper was ever scored. No chunk was ever retrieved. No proposition, no verification, no
coverage audit, no recovery round, no per-child Overview, no parent claim, and no S2 call ever happened.

## Why every later stage is SKIPPED, with the exact reason

| Stage | Status | Reason |
|---|---|---|
| R1 (responsiveness review) | SKIPPED | No proposition was ever produced to review |
| C1 (sealing) | SKIPPED | No sealed ledger can exist without at least one source-verified record |
| U1 (initial semantic map) | SKIPPED | Requires a sealed ledger (C1) as input |
| P1 (recovery planning) | SKIPPED | Requires U1's output |
| W2/R2/C2 (recovery round) | SKIPPED | Requires P1 to have authorized a recovery action |
| U2 (final semantic map) | SKIPPED | Requires the recovery round (or its explicit absence) to resolve |
| S1 (any child's Overview) | SKIPPED | Requires U2 and a sealed per-child ledger |
| Parent claim ledger | SKIPPED | `parent_synthesis_ledger.build_claim_ledger` requires a final sufficiency map |
| S2 (parent synthesis) | SKIPPED | `parent_synthesis.realize()` was never called — there was no claim ledger to realize |

This is not a case of "legitimately skipped by architecture" (like a recovery round that correctly
doesn't fire because nothing needed it) — every one of these is skipped **only** because the stage
before it crashed. None of them tell us anything about T5C, the hierarchy, or parent synthesis.

## Root-cause diagnosis (established offline, afterward — not a second live call)

Two separate, safe, read-only diagnostics were run against the **same** production code this run used,
entirely locally, with **no Ollama contact and no library mutation** (the library fingerprint was
reverified byte-identical immediately after each):

**Diagnostic 1** — does `build_runtime(..., want_verifier=True, want_qwen=False)` itself fail under the
same `endpoint_guard.isolated_only()` guard?
```
rt = build_runtime(LIBRARY_COPY_PATH, want_verifier=True, want_qwen=False)
# -> SUCCEEDED cleanly. No huggingface.co contact at construction time.
```
This ruled out the obvious suspect (eager verifier-model construction) and showed the real model
objects are built **lazily**.

**Diagnostic 2** — does the first actual embedding call reproduce the failure?
```
with endpoint_guard.isolated_only():
    rt.model.encode_texts(["Does short-term exposure to anomalies change behavior?"])
# -> FAILED, byte-identical error: EndpointRefused: name resolution for 'huggingface.co' refused
```
with the full traceback captured this time. The call chain, exactly:

```
model.encode_texts(...)
  -> app/backend/model_runtime.py:317 _load_sentence_transformer()
    -> sentence_transformers.SentenceTransformer.__init__
      -> ._load_sbert_model -> Transformer.load -> Transformer.__init__
        -> ._load_config -> transformers.utils.peft_utils.find_adapter_config_file
          -> transformers.utils.hub.cached_file -> huggingface_hub.hf_hub_download
            -> huggingface_hub.file_download.get_hf_file_metadata
              -> requests -> urllib3 -> socket.getaddrinfo('huggingface.co', ...)
                -> experiments/ask_cli_revised/contract_directed/endpoint_guard.py:57
                   raise EndpointRefused(...)
```

**What this means, precisely:** `sentence_transformers.SentenceTransformer`'s loader, on recent
`transformers`/`sentence-transformers` versions, unconditionally checks HuggingFace Hub for a PEFT
adapter config (`adapter_config.json`) whenever a model is loaded from a hub-style identifier —
**regardless of whether the base model files are already fully cached locally.** This is standard
library behavior, not a bug in callosum's own embedding wrapper. It is silent and harmless under two
conditions this phase's prior live runs (Phase 23, the Sept-30 T5C run) both happened to be under:
genuine internet access (the check succeeds near-instantly and changes nothing), or genuine total
absence of a network path (`huggingface_hub`'s own request wrapper catches ordinary
`requests`/`urllib3` connection errors and falls back to the cached files). **It is not silent under
this phase's own `endpoint_guard.isolated_only()`**, which raises a custom `EndpointRefused` exception
at the `socket.getaddrinfo` level — a type `huggingface_hub`'s offline-fallback logic was never written
to catch, so it propagates as a hard, uncaught failure instead of a graceful cache fallback.

**This is a design flaw in this phase's own scratch harness** (`phase28_runner.py`): wrapping the
*entire* `run_topology()` call — including local embedding-model construction, which has nothing to do
with which Ollama endpoint is reached — in a network guard that no prior live phase ever used. It is
**not** a defect in the Phase 27b production pipeline, the T5C profile, the hierarchy contract, or
parent synthesis. None of those were ever exercised long enough to say anything about them.

## Sentence-level parent provenance table

Not applicable. No parent answer — grounded, fallback, or otherwise — exists. There is no final text to
trace.

## Known-tracer analysis (c8/c12, Phase 23A)

Not applicable, and stated plainly rather than silently omitted: this run never produced a sealed
ledger, U2 nomination, or parent claim, so **it supplies zero evidence, in either direction, about
whether the Phase 23A c8/c12 scientific concerns recur under T5C or under parent synthesis.** That
question is exactly as open now as it was before Phase 28 began.

## Evaluating S2 and S1 on their own job

Not possible. Neither was ever called. The architecture's "S2 ≤ 1 call" invariant holds only
vacuously (0 ≤ 1) — this is not evidence that the invariant holds *under load*, only that it was never
tested.

## Parent-synthesis / child-synthesis stage-local verdict

**UNKNOWN / NOT_RUN** — not NO_ERROR, not a pass. The governing earliest-error taxonomy's categories
(RETRIEVAL_ERROR through RENDERING_ERROR) all presuppose the pipeline produced *some* observable
content to misjudge. This failure precedes all of them: it is a harness/infrastructure failure in the
scratch runner that wraps the production call, not a finding about any pipeline stage's semantic
correctness.

## Did Phase 28 fulfill its stated empirical purpose?

**Not for the purpose it was designed for** — observing the real, live, hierarchical pipeline through
parent synthesis for the first time under T5C, and localizing any downstream error to its earliest
responsible stage. Nothing downstream of "the request loaded correctly" was ever exercised.

**It did fulfill a different, genuine purpose**: it is a real, live-authorized, one-shot attempt that
surfaced an actual, previously-undiscovered, now precisely-diagnosed infrastructure hazard — not a
contrived test case, not a guess, but something that only showed up because a real authorized run was
actually attempted. That is itself the kind of evidence this governing methodology exists to produce,
even when the content of the evidence is "the harness has a bug," not "the pipeline has a bug."

## Recommendation for the next phase

Reopen with a **Phase 28 retry** under a fresh, separate authorization (this one is consumed and closed
as FAILED — not reused, not patched-in-place). The scratch runner for that retry should drop
`endpoint_guard.isolated_only()` entirely around the live call (matching the precedent every prior live
phase already set — none of them used a network guard, relying on the production code's own configured
endpoints instead) or, if an active guard is still wanted, set `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1`
in the process environment before constructing the runtime, exactly as `contract_directed/
offline_pytest.py` already does for its own (test-only) use of the same guard mechanism. Either fix
touches only the scratch harness, never any tracked pipeline module.
