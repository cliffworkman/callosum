# Callosum Latency Contract

This document defines performance requirements for Callosum features that use local models, remote model providers, background jobs, or other latency-sensitive backend computation.

It is an architectural contract, not a changelog.

Its canonical repository location is `.claude/LATENCY.md`; `CLAUDE.md` rule #12 makes it a required read for affected work.

New model-backed functionality and modifications to existing model-backed functionality MUST follow these rules unless there is a documented, measured reason not to.

The governing principle is:

> Do not make the user wait for work that Callosum does not need to perform.

Performance changes must preserve scientific correctness, result semantics, provenance, persistence, and reliability.

---

## 1. Measure Before Optimizing

Do not optimize from intuition alone.

Before making a non-trivial latency optimization:

1. Identify the user-visible workflow.
2. Measure its current wall-clock latency.
3. Attribute latency to major stages.
4. Identify the dominant component.
5. Change one meaningful causal factor at a time where practical.
6. Re-measure using comparable workloads.

Do not infer bottlenecks from call counts alone.

A workflow that makes fewer calls may still be slower because individual calls process more work.

Performance work should distinguish:

- model loading
- first inference
- warm inference
- model-runtime queue/inference-lock wait
- provider-client construction
- provider request latency
- tokenization/planning
- retrieval
- persistence
- backend job completion
- frontend completion visibility

---

## 2. Separate Backend Latency From Visibility Latency

A backend result being complete and a user seeing that result are different events.

Where relevant, measure:

- job start
- backend terminal-state time
- client completion-detection time
- authoritative final-result fetch time
- visibility-ready time

Do not hide frontend polling or notification delay inside "backend latency."

For background jobs, prefer notification or bounded waiting where practical.

Fixed polling may remain as a fallback, but should not impose substantial avoidable delay after a job is already complete.

Notification mechanisms must treat persistent or authoritative job state as the source of truth.

A notification is a signal to retrieve state, not the sole copy of the result.

Current live coverage is deliberately narrower than "all jobs": synthesis, single Critical Read, Set Critical Read,
and WIP Critical Read use the shared frontend observer in `app/frontend/js/02b_job_completion.jsx`. The frontend
holds a status request for 20 seconds; the four status endpoints accept `wait_seconds` up to 25 seconds and delegate
to `JobStore.wait_for_update()`. After a retryable held-request failure, the observer waits 1.2 seconds, issues a
non-held status GET, and returns to long polling after a successful non-terminal response. Other job-backed workflows
still contain fixed polling and must not be described as already migrated.

`JobStore` state is process-local and authoritative for an active job; it is not durable across an application
restart. Frontend `sessionStorage` permits reload recovery only while that backend job still exists. Persisted feature
results, where a workflow has them, remain separately authoritative after completion.

Current launch paths use one Uvicorn worker. Because both active-job state and waiter notification are process-local,
a future multi-worker or multi-process deployment must introduce shared job-state/notification infrastructure or
provable request affinity before it may rely on this completion mechanism. A start request and a status request
landing in different workers would otherwise observe different `JobStore` instances.

Stopping or unmounting a frontend observer aborts its held status request; it does not cancel the backend job. Any
future job-cancellation feature must define separate execution, persistence, and multi-observer semantics rather than
treating notification cleanup as computation cancellation.

---

## 3. Reuse Expensive Runtime Objects

Model and provider runtimes should be scoped for reuse.

Do not repeatedly construct or load identical resources during normal warm operation.

This includes:

- local embedding models
- local CrossEncoders
- other local inference runtimes
- HTTP connection pools
- cloud-provider SDK clients

Prefer app-scoped, lazily initialized runtimes where compatible with application architecture.

Runtime reuse must preserve:

- dependency injection
- test isolation
- credential-rotation safety
- endpoint/configuration identity
- shutdown cleanup
- concurrency safety

Avoid module-global singletons when app-scoped state provides clearer lifecycle and isolation.

The live implementation is owned by each `create_app()` instance:

- `ModelRuntimeRegistry` keys local runtimes by model family/name/revision/device/local-files-only/backend.
- `ManagedModelRuntime` guards first load and serializes inference per compatible runtime identity; it does not hold
  that inference lock around retrieval, database, parsing, provider work, or other orchestration.
- Compatible support and stance scorers may retain different scientific interpretation while sharing one underlying
  CrossEncoder runtime.
- `ProviderClientRuntime` owns raw HTTP pools and Gemini clients.
- FastAPI lifespan shutdown closes both registries before disposing the database engine.
- Explicit injected models, scorers, HTTP clients, and app-owned registries remain the test/customization precedence.

---

## 4. Batch Independent Model Work

Do not perform independent local-model inference one item at a time when the model API supports batching.

Collect compatible work and infer in batches.

Examples include:

- embeddings
- NLI pairs
- classification inputs
- other independent transformer examples

A production change MUST NOT reintroduce a per-item inference loop into a path that is currently batched without explicit measurement and justification.

When output order matters, carry explicit positional identity and reconstruct results deterministically.

Do not rely on incidental ordering behavior.

Current batched paths that must not regress include:

- single-paper and WIP Critical Read: all bounded claim embeddings are encoded together, then all retrieved
  claim/passage pairs enter one logical NLI inference phase
- Set Critical Read: claims and resolved pairs across all selected papers are collected before those same two phases
- synthesis citation verification: all generated candidate/citation pairs enter `verify_many()`, which performs one
  batched citation embedding call and one batched support-NLI call for the generated summary

Retrieval may remain per claim because each claim has its own candidate scope and `top_k`; batching the model work
does not imply changing retrieval semantics.

Known live exceptions—not satisfied batching invariants—remain in citation workflows:

- `methods/citation_context.py::classify_citation_contexts()` calls the stance scorer once per available citation
  context (bounded at 500 items)
- `citations/suggest.py::suggest_citations()` calls the stance scorer once per retained local suggestion; that local
  set is capped at 20 before NLI
- the evaluated path in `citations/beyond_library.py` calls the stance scorer for every merged, non-library candidate
  with an abstract before sorting and slicing the response. The returned result set is capped at 20, but the NLI call
  count is not: a controlled multi-provider audit classified 40 candidates and returned 20 results

These paths reuse the app-owned model runtime, but runtime reuse does not make their per-item inference shape batched.
Sequential one-pair inference remains the fastest measured citation-suggestion execution shape overall, so this is a
measured exception rather than an invitation to batch by default. Any future change should preserve item order and
missing/unclassifiable-item semantics while measuring a batch seam. The final response cap does not establish that
pre-slicing before NLI is semantically safe: reducing the evaluated candidate set requires separate measurement and
design because it could change which returned suggestions have stance evidence.

---

## 5. Preserve Scientific Semantics During Performance Work

Execution optimizations must not silently alter scientific meaning.

Unless a task explicitly intends to modify scientific behavior, preserve:

- exact input collection
- premise/hypothesis orientation
- model identity
- tokenizer identity
- truncation policy
- thresholds
- classifications
- evidence selection
- provenance
- persistence
- duplicate handling
- stable tie behavior
- final ordering

For optimizations that can introduce floating-point variation, compare against a reference implementation.

Current default acceptance expectation for numerically equivalent local-model execution:

- maximum absolute probability difference <= 1e-5
- threshold crossings = 0
- classification differences = 0
- evidence-selection differences = 0
- positional reconstruction differences = 0
- final ordering differences = 0

A task may define a stricter tolerance.

Do not loosen tolerance merely to make an optimization pass.

---

## 6. Transformer Workloads Must Be Described by Token Shape

Item count alone is not a sufficient transformer workload descriptor.

For variable-length transformer inputs, benchmarks should report where practical:

- item/pair count
- effective token-length distribution
- raw token-length distribution if truncation matters
- p25
- median
- p75
- p90
- p95
- maximum
- truncation count/rate
- batch size
- input order
- batch-local maximum lengths
- total effective tokens
- total padded tokens
- padding efficiency
- percentage of batches reaching the model maximum
- effective tokens/second
- padded tokens/second

Do not use median sequence length as a proxy for compute when a long tail determines batch width.

Callosum measurements showed that heterogeneous inputs with similar pair counts can differ dramatically in latency because dynamic padding makes short examples pay for long neighbors.

Total padded token volume has proven more informative than pair count alone for Critical Read NLI workloads.

---

## 7. Minimize Padding Waste Without Changing Evidence

When independent transformer examples have heterogeneous lengths, execution order may be changed to reduce padding if and only if:

- every input is preserved exactly
- model/tokenizer/truncation behavior is unchanged
- original positions are explicitly retained
- predictions are reconstructed before downstream interpretation
- scientific-equivalence tests pass

For Critical Read NLI specifically, the current production contract uses stable length buckets for multi-batch workloads:

- <=64
- 65-128
- 129-256
- 257-384
- 385-511
- 512

Pairs retain stable original order within each bucket.

Predictions are restored to exact original pair order before thresholds, evidence selection, persistence, or response construction.

Workloads fitting within one inference batch should bypass length planning because reordering cannot reduce that batch's maximum width.

If the production batch size changes, the bypass threshold and acceptance benchmarks must be reviewed together.

Do not casually change bucket boundaries without measurement.

The concrete production constants live in `app/backend/summarization/stance.py`: batch size 32, maximum effective
length 512, and `truncation="longest_first"` using the default
`cross-encoder/nli-MiniLM2-L6-H768` CrossEncoder's actual tokenizer. The passage is the premise and the claim is the
hypothesis. Workloads of 32 pairs or fewer bypass planning. Compatible production scorers use length planning;
custom/injected scorers that do not expose the production tokenizer contract retain their prior ordered batch seam.
Length-aware execution is scoped to Critical Read rather than silently applied to every NLI consumer.

---

## 8. Avoid Optimization Machinery When It Cannot Help

An optimization is not free merely because its overhead is small.

Use bypass paths when preconditions prove that optimization cannot improve the workload.

Examples:

- one-batch NLI workloads should not perform length-aware planning
- cached resources should not be reconstructed
- completed jobs should not continue polling
- empty work should not invoke models

Prefer explicit fast paths over unnecessary general machinery when correctness remains clear.

---

## 9. Remote Provider Clients Must Reuse Connections

Do not use request patterns that reconstruct transport state for every provider call.

Reuse HTTP clients and connection pools.

Provider integrations should preserve safe identity boundaries for:

- endpoint/base URL
- TLS behavior
- proxy/environment behavior
- credentials where SDK clients bind credentials at construction

Raw credentials must not be stored in runtime-registry keys or logs.

Credential rotation must not accidentally reuse a client whose semantics bind it to obsolete credentials.

In the live `ProviderClientRuntime`:

- raw HTTP pool identity includes an endpoint fingerprint, the 60-second timeout policy, TLS/trust-environment
  behavior, and proxy/certificate environment fingerprints; API keys remain request headers, so raw HTTP credential
  rotation does not require a different transport pool
- Gemini client identity includes a non-reversible credential fingerprint plus relevant Google SDK environment
- explicit `complete(..., http_client=...)` injection wins over the app runtime
- normal `create_app()` dependency resolution attaches the app runtime to provider configuration
- directly constructed configurations retain a legacy per-call fallback and must not be mistaken for the normal
  production path

---

## 10. Remote Calls Belong on the Critical Path Only When Necessary

A remote call should delay user-visible completion only when its result is required for the state being presented.

When a secondary result is optional or supplementary, investigate whether it can occur after the primary durable result.

Do not move work out of the critical path merely by changing response serialization if the underlying transaction still prevents the primary result from becoming durable.

Transaction boundaries must be considered explicitly.

Any change to commit order, durability, or state transitions requires correctness testing before performance benefit is considered.

Current live synthesis boundary: Phase A keeps retrieval, generation-cache access/remote summary generation,
verification, and the complete evidence graph in one primary transaction. Only after that transaction commits does
`_run_summarize_job()` reread authoritative state and mark the primary job done. Phase B then acquires persisted
overview work, closes its database context, calls the overview provider with no transaction/connection held, and uses
a short transaction to persist the result. Overview lifecycle is explicit (`not_requested`, `pending`, `running`,
`complete`, `failed`); a five-minute stale `running` attempt is manually retryable, completed content is immutable
under ordinary retry, and no startup/reload path automatically emits provider traffic. Persisted summary state remains
authoritative; the frontend renders committed claims immediately and performs only a bounded supplementary refetch.

Critical Read Tier-2 paths also retain remote proposal calls inside transaction/connection scope: the single-paper
endpoint commits after proposal, grounding, and insertion, while Set Critical Read keeps proposal, verification, and
persistence inside one `engine.begin()` block. Their generated candidates are required for those Tier-2 responses, but
the transaction lifetime remains a measured future design concern rather than a completed optimization.

---

## 11. Concurrency Requires Measurement and Bounds

Do not parallelize remote or local model work simply because tasks appear independent.

Before adding concurrency, consider:

- provider rate limits
- local CPU contention
- model-runtime serialization
- memory
- request ordering
- failure handling
- deterministic reconstruction

Use bounded concurrency.

Unbounded fan-out is not an acceptable latency optimization.

For cloud-model workflows, compare serial and bounded-concurrent behavior using actual provider limits and representative requests.

Because compatible local inference is currently serialized per runtime identity, concurrent-workflow measurements
should separate time waiting for the inference lock from time spent executing the model. A fast warm inference can
still have high user-visible latency when another workflow owns the shared runtime.

Known live boundary: optional axis-cluster label polishing in
`app/backend/clustering/axis_suggestion.py::apply_labels()` still invokes one remote label call per suggestion
serially. Provider-client reuse removes reconstruction overhead but does not make those independent remote calls
concurrent. Treat concurrency there as a measured future candidate, not a current invariant.

---

## 12. Output Limits Must Be Feature-Specific

Do not impose one universal model-output cap across unrelated features.

Use measured output distributions and feature semantics.

A tighter cap is justified only when:

- the feature's legitimate output is structurally bounded
- truncation risk is understood
- representative outputs remain complete
- the cap provides a meaningful safety or tail-latency benefit

Short structured features may warrant different limits from synthesis or critique.

Input-token volume and output-token volume must be considered separately.

Current provider behavior is not feature-specific: Anthropic Messages uses the shared required 2048-token cap, while
Gemini, OpenAI-compatible Chat Completions, and Responses do not currently receive per-feature output caps from the
provider-neutral seam. Do not claim feature-specific caps have landed; introducing them requires feature-level output
distribution evidence and truncation tests.

---

## 13. Large Prompt Inputs Must Be Justified

Do not repeatedly send an entire large corpus to a provider when only a small subset is likely to be relevant unless coverage requirements justify it.

When prompts become large, measure:

- input-token count
- output-token count
- wall-clock provider latency
- cost where relevant
- retrieval/coverage behavior

Potential prompt-reduction work must preserve answer coverage and correctness.

Do not replace broad context with retrieval merely because retrieval is cheaper without evaluating missed-information risk.

Known live boundary: `integrations/gemini/help_assistant.py` includes the entire public help corpus in every assistant
prompt. This was an intentional coverage-first design when the corpus was small; current corpus size, provider input
tokens, latency, and retrieval miss risk must be measured before replacing it with selective retrieval.

---

## 14. Benchmark Real Heterogeneity

Uniform synthetic workloads are useful for controlled experiments but are not sufficient for production acceptance when real workloads are heterogeneous.

Where privacy allows, use anonymized numeric measurements from realistic local workloads.

Never emit raw scholarly content solely for performance profiling.

Prefer:

- anonymized run IDs
- counts
- token-length statistics
- timing
- memory
- truncation metadata
- batch-shape metadata

Real workload measurements should be privacy-safe and should not expose:

- paper text
- claims
- passages
- titles
- authors
- file paths
- user prompts
- quotes

---

## 15. Control Benchmark Host State

Performance comparisons should preferentially use:

- the same warm process
- interleaved reference and candidate trials
- stable model/runtime state
- identical or explicitly characterized workloads

Record where practical:

- OS
- CPU
- physical/logical core count
- RAM
- Python version
- model library versions
- model identity
- backend
- device
- thread counts
- batch size
- process ID
- CPU utilization/background-load limitations

Do not compare timings from different fixtures or host states as though they were directly interchangeable.

Absolute wall-clock values are often environment-specific.

Within-process ratios are usually more trustworthy.

---

## 16. Separate Correctness Tests From Performance Benchmarks

Unit and integration tests should assert deterministic functional invariants.

Do not make correctness depend on aggressive scheduler-sensitive wall-clock thresholds.

For asynchronous/background work, test state and synchronization directly where practical.

Examples:

- waiter registered
- notification event set
- authoritative terminal state returned
- timeout path taken
- waiter removed
- all observers notified
- no deadlock

Performance expectations such as millisecond completion detection belong in dedicated benchmarks or loose sanity checks, not fragile correctness assertions.

Timing bounds used purely as deadlock guards should be broad and documented as such.

The live long-poll tests follow this distinction: they synchronize on waiter registration, inspect the actual
notification event, assert authoritative terminal/timeout state and cleanup, and keep only broad cross-thread deadlock
guards. Millisecond detection latency is measured separately rather than used as a functional assertion.

---

## 17. Measure Planning Overhead

Latency optimizations that introduce planning, sorting, token counting, reconstruction, caching, or orchestration must include their own overhead in candidate timings.

Do not benchmark only the faster inner operation.

Measure the end-to-end candidate path relevant to the optimization.

A useful optimization reduces total user-relevant work after including its own machinery.

---

## 18. Memory Is Part of Performance

A latency win that creates unacceptable memory pressure may not be a win.

Where model inference shape changes materially, record:

- RSS before
- peak RSS
- RSS after

Watch for:

- duplicate model loads
- large batch allocations
- allocator retention
- monotonic growth
- concurrent model copies

Treat small RSS differences cautiously under PyTorch allocator behavior.

---

## 19. Cache Only With Clear Semantics

Caching must define:

- cache key identity
- invalidation behavior
- model/configuration identity
- source-data dependencies
- persistence lifetime
- concurrency behavior

Never cache scientific results using keys that omit inputs capable of changing those results.

Do not add caching merely because a workflow is slow.

First identify whether the expensive computation is actually repeated.

The live synthesis generation cache uses the versioned `summary-generation-v2` identity. It hashes the generator and
prompt version; provider roster identity; exact model; resolved wire/API mode; normalized endpoint; fixed wire-level
generation parameters; a non-reversible credential fingerprint; Gemini SDK environment identity where applicable;
the ordered prompt-relevant source fields; source version; and scope. Raw credentials and endpoint text are not
persisted in the signature. Equivalent trailing-slash/default endpoint spellings normalize to the same identity.
Credential rotation deliberately misses because an arbitrary custom endpoint may bind credentials to different
tenant/model-deployment semantics. Legacy under-specified rows remain stored but are unreachable under the v2 key.
Local citation verification still runs on every hit.

---

## 20. Performance Acceptance Must Be Explicit

A performance task should define its success threshold before implementation where practical.

For substantial local-model optimizations, a useful default is:

- >=20% median improvement on at least one important smaller workload
- >=20% improvement on an important large workload
- no important regression >5%
- no unacceptable memory increase
- scientific equivalence passes

Smaller improvements may still be justified for very low-complexity changes, but should be described as such.

Do not ship architectural complexity for noise-sized gains.

---

## 21. Preserve Causal Attribution

Prefer the smallest production change supported by measurement.

Do not combine unrelated latency optimizations into one tranche when doing so prevents attribution.

Typical workflow:

1. measure
2. form hypothesis
3. run controlled experiment
4. decide whether evidence clears threshold
5. implement one justified change
6. rerun acceptance benchmark
7. retain or revert
8. move to the next bottleneck

A failed optimization experiment is useful evidence.

Do not force a production change simply because time was spent investigating it.

---

## 22. Performance Regressions Are Contract Violations

When modifying model-backed backend code, explicitly check whether the change reintroduces any previously eliminated behavior, including:

- per-item model inference
- repeated identical model loading
- repeated provider-client construction
- unnecessary fixed polling
- uncontrolled padding waste
- missing positional reconstruction
- unnecessary remote critical-path calls
- unbounded concurrency

If a regression is necessary for correctness or a new requirement, document and measure it.

---

## 23. Current Critical Performance Invariants

Unless deliberately changed and revalidated, Callosum currently relies on these architectural properties:

- Normal production Critical Read embeddings are batched.
- Normal production Critical Read NLI is executed as one logical inference phase over collected pairs.
- Synthesis citation embeddings and support-NLI verification are batched across the generated summary.
- Compatible local models are app-scoped and reused.
- Compatible provider clients are app-scoped and reused.
- Critical Read NLI uses stable length-aware bucketing for multi-batch workloads.
- NLI results are reconstructed into original pair order before interpretation.
- Critical Read NLI workloads of 32 pairs or fewer bypass length planning.
- Synthesis and single/Set/WIP Critical Read completion use 20-second bounded long polling against endpoints capped at
  25 seconds, with immediate-GET plus 1.2-second retry fallback on retryable notification failure.
- Authoritative in-process `JobStore` state remains the source of truth for active-job status; notification payloads
  never replace final status/result retrieval.
- Long-poll correctness tests do not use microbenchmark detection latency as a functional invariant.
- Synthesis generation-cache hits require the versioned provider/model/wire/endpoint/credential/request-semantics
  identity plus the exact ordered prompt inputs; legacy under-specified rows cannot satisfy the current key.
- A synthesis job becomes done only after its summary row, ordered sentences, citation mappings, evidence quotes,
  verification/provenance state, and derived status commit successfully. Optional overview work starts afterward,
  holds no database transaction during provider latency, and cannot roll back or fail the primary job.
- Persisted overview lifecycle state is authoritative. Retry reuses the same summary id, uses guarded acquisition,
  permits manual reclamation of stale work, and never overwrites a completed overview.

Any modification that affects these properties requires explicit review.

---

## 24. Live Implementation Map and Known Boundaries

| Concern | Live implementation |
|---|---|
| App-owned lifecycle | `app/backend/api/app.py` |
| Local runtime identity/load/inference guards | `app/backend/model_runtime.py` |
| Default model/scorer dependency resolution | `app/backend/api/dependencies.py` |
| Critical Read batching and positional pair mapping | `app/backend/methods/critical_review.py` |
| Critical Read tokenizer-length planning and reconstruction | `app/backend/summarization/stance.py` |
| Synthesis citation batching and primary persistence | `app/backend/summarization/pipeline.py` |
| Supplementary overview lifecycle/CAS/provider boundary | `app/backend/summarization/overview_lifecycle.py`, `app/backend/api/routers/summary_overview.py` |
| Synthesis generation-cache identity and source hashing | `app/backend/llm/cache.py`, `integrations/gemini/generator.py` |
| Provider pool/client identity and cleanup | `app/backend/provider_runtime.py` |
| Provider dispatch and explicit-client precedence | `app/backend/llm/providers.py` |
| Long-poll waiter registration/wake/cleanup | `app/backend/api/job_store.py` |
| Long-poll status endpoints | `app/backend/api/routers/summaries.py`, `critical_review.py`, `wip_critical_review.py` |
| Shared frontend completion observer | `app/frontend/js/02b_job_completion.jsx` |

Known current boundaries—not completed optimizations—include:

- synthesis Phase A still includes remote primary generation and local verification in its primary transaction;
  only the supplementary overview has moved outside that transaction/critical path
- Critical Read Tier-2 proposal calls remain inside their request transaction/connection scope
- numerous non-synthesis/non-Critical-Read background workflows still use fixed polling
- feature-specific output caps have not been implemented across provider paths
- optional axis-cluster label calls remain serialized
- citation-context and citation-suggestion stance inference remains per item despite app-scoped model reuse
- the help assistant sends the entire public help corpus on each request
- evidence truncation/window shape and alternative CrossEncoder backends remain unchanged
- provider reuse removes construction/pool setup, not provider network/generation latency
- local model inference is conservatively serialized per compatible runtime identity
- process-local `JobStore` notification assumes the documented single-worker launch topology
- aborting a frontend status observer does not cancel the underlying backend job

When code and this map disagree, inspect the code and update this contract in the same change; do not preserve stale
prose as authority.

---

## 25. Required Review Questions

Before merging a change that adds or modifies local-model or cloud-model backend work, answer:

1. What is the user-visible critical path?
2. What work is local versus remote?
3. Are identical runtimes/clients reused?
4. Is independent model work batched?
5. For variable-length transformer input, what is the padded-token shape?
6. Does output ordering need explicit reconstruction?
7. Is any work performed that cannot affect the result?
8. Does the frontend add completion-visibility delay?
9. Are remote calls serialized unnecessarily?
10. Are transaction boundaries keeping optional work on the critical path?
11. Are correctness tests separated from performance benchmarks?
12. What benchmark demonstrates that this change does not create an important latency regression?
13. What scientific-equivalence checks are required?
14. What memory effect does the change have?
15. Is the complexity justified by the measured benefit?

If these questions cannot be answered for a significant model-backed change, performance review is incomplete.
