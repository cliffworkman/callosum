# Increment 491 — app-scoped embedding and NLI runtime reuse

## Implemented

- `app/backend/model_runtime.py` introduces one explicit `ModelRuntimeRegistry` per FastAPI application. It keys
  underlying runtimes by family, model name, revision, device, `local_files_only`, and backend. Wrapper settings
  such as embedding version, normalization, and batch size remain separate cache keys while compatible wrappers
  can share identical weights.
- Each runtime has an independent first-load lock and inference lock. A constructor result is published only after
  success, so simultaneous first users receive one object and a failed construction remains retryable. Ordinary
  inference never holds the registry lock, and unrelated identities do not block each other.
- `SentenceTransformerEmbeddingModel`, `NLISupportScorer`, and `NLIStanceScorer` accept a managed runtime while
  retaining their standalone lazy-loader and fake-injection seams. Support and stance scorers share CrossEncoder
  weights but retain unchanged probability interpretation, fallback, and classification behavior.
- `create_app()` owns the registry in `app.state` and closes it during lifespan shutdown. Central dependency
  resolvers honor explicit embedding/support/stance injections first. Synthesis, Critical Read, WIP Critical Read,
  citation context/suggestion, and all router embedding fallbacks now use those resolvers.

## Identity and safety decisions

`local_files_only=True` is deliberately a distinct identity from the normal default because offline behavior is a
material construction setting. Different model names, revisions, devices, and backends also stay distinct.
Normalization and batching affect an embedding wrapper's preprocessing/inference request, not the loaded weight
object; those wrappers are distinct but may share the compatible runtime.

Shared local inference is conservatively serialized per runtime identity because repository/server behavior does
not establish concurrent SentenceTransformer/CrossEncoder inference safety. Loading and inference locks are
separate; neither covers database access, retrieval, parsing, provider calls, or persistence. Different identities
can infer concurrently. Critical Read's ordered batching remains exactly one embedding call and one NLI call for
the ordinary single/set/WIP paths.

## Measured proof

- Real CPU, cached models, full temporary-DB synthesis with a deterministic fake generator and no provider egress:
  run 1 **2.558 s**, run 2 **0.0625 s**, run 3 **0.0595 s**. Run 1 loaded `all-MiniLM-L6-v2` once (**1.872 s**) and
  `cross-encoder/nli-MiniLM2-L6-H768` once (**0.571 s**); runs 2–3 loaded neither and retained the same object ids.
- Real CPU Critical Read search, 12 claims/5 hits each/60 NLI pairs: run 1 **3.497 s**, run 2 **1.282 s**, repeated
  same input **1.314 s**. The first run loaded embedding once (**1.601 s**) and NLI once (**0.681 s**); later runs
  loaded neither. Every run made one embedding call and one NLI call. Warm embedding inference was 0.044–0.056 s
  and warm NLI inference 1.232–1.252 s.
- RSS process observation: baseline **199,622,656 B**; first embedding feature **560,410,624 B**; a second
  compatible embedding feature **560,431,104 B** (+20,480 B, no load); first NLI support use **750,473,216 B**;
  an additional compatible stance feature **750,473,216 B** (+0 B, no load). Import/framework allocations make
  the first embedding delta unsuitable as pure weight size, but compatible-feature duplicate growth is absent.

## Verification

- Registry unit suite: **10 passed**. It covers one load, cross-feature runtime identity, distinct identities,
  explicit-injection precedence, simultaneous first use, failed-load retry, same-identity inference serialization,
  unrelated-identity overlap, app isolation, shutdown cleanup, and exact fake-model output equivalence.
- Synthesis/Critical Read/WIP/citation focused suite: **103 passed**. All touched-router suites: **261 passed**.
- Full suite: **2359 passed, 3 skipped in 2861.85 s (0:47:41)**.
- Ruff format/check, Tach module boundaries, and the **554-file** line budget passed. Bandit was unavailable in the
  environment (`bandit` command absent; `python -m bandit` reported no installed module), so no Bandit result is
  claimed. No security-audit trigger was introduced: no endpoint, dependency, schema, input, egress, auth, file,
  provider, or deployment boundary changed.

## Boundaries

No provider HTTP/Gemini client reuse, synthesis-overview split, output cap, task-specific routing, persistent
inference cache, local inference concurrency, model/threshold/top-k change, retrieval change, API/frontend change,
or schema migration is included. Help documentation was reviewed and intentionally left unchanged because model
lifetime is invisible to users. Benchmarks used temporary databases, cached local models, and fake/local inference;
they made no paid/network provider call and wrote no persistent user data.
