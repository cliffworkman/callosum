# Increment 560 Notes — pin auxiliary local-model revisions (Wave 3 item, partial)

## Outcome

Starts the third Wave 3 item from increment 557's Local AI reliability audit — "auxiliary embedding/NLI/
SPECTER model layer has a hidden first-use download dependency, unpinned revisions, and no progress/ETA."
This increment closes the **revision-pinning** half only; first-use download progress/ETA UI and a friendlier
failure for `local_files_only=True` paths when the cache isn't warm remain explicitly open (see below).

## Implemented

- **`app/backend/model_runtime.py`** gains `PINNED_MODEL_REVISIONS: dict[str, str]` — the exact Hugging Face
  Hub commit-hash revision this project has actually been developed and tested against for the three models
  referenced by a fixed name anywhere in the codebase: `all-MiniLM-L6-v2` (`DEFAULT_EMBEDDING_MODEL`),
  `cross-encoder/nli-MiniLM2-L6-H768` (`DEFAULT_NLI_MODEL`), and `sentence-transformers/allenai-specter`
  (`citation_equity.py`'s `OVERLOOKED_EMBED_MODEL` / `publishers.py`'s `PUBLISHERS_EMBED_MODEL`). Revisions
  read directly off this machine's already-populated local Hugging Face cache
  (`~/.cache/huggingface/hub/*/refs/main`) rather than guessed or fetched fresh, so the pin reflects what's
  actually been exercised, not necessarily the newest revision available on the Hub today.
- **`app/backend/api/dependencies.py`**'s three resolver functions (`resolve_embedding_model`,
  `resolve_support_scorer`, `resolve_stance_scorer`) now look up a pinned revision by name/model_name when the
  caller doesn't already supply one explicitly — an explicit `revision=` argument (already a parameter on
  `resolve_embedding_model`) still wins, and a name with no known pin (e.g. a user-selected alternate
  embedding model like `bge-base-en-v1.5`, never referenced by a fixed constant in this codebase) resolves
  unpinned exactly as before, never a guessed hash. All the actual plumbing (`ModelRuntimeIdentity.revision`,
  `SentenceTransformer(revision=...)`, `CrossEncoder(revision=...)`) already existed from `revision`-typed
  parameters threaded everywhere; the gap was purely that nothing ever supplied a real value.

## Explicitly NOT done this increment (remaining Wave-3-item-3 scope)

- **First-use download progress/ETA.** A fresh install's first real use of an embedding/NLI/SPECTER feature
  still downloads silently with no Status-popover entry or progress indication (invariant #5 gap). This needs
  hooking into `sentence-transformers`/`huggingface_hub`'s own download progress callbacks and threading them
  through the existing Status system — a meaningfully larger, UI-touching piece of work, not attempted here.
- **A friendlier failure when `local_files_only=True` hits a cold cache.** The three real call sites
  (`registration_comparisons.py:313`, `registration_retrieval.py:93`, `wip_critical_review.py:51/53`) will
  still raise whatever raw exception `sentence-transformers` produces when weights aren't already cached and
  network access is refused — not yet translated into an actionable message pointing the user at warming the
  cache first (e.g. by running an ordinary embedding-producing feature once with network allowed).
- **`bge-base-en-v1.5`** (CLAUDE.md's documented second supported embedding model) is not referenced by any
  fixed constant in the codebase (only selectable via Settings), so no local cache/revision was available to
  pin from — left honestly unpinned rather than guessed.
- `tools/` scripts (`validation_harness.py`, `demo/generate_demo_library_state.py`) construct
  `SentenceTransformerEmbeddingModel` directly, bypassing `dependencies.py`'s resolvers entirely, and are left
  unpinned — dev/validation tooling, not the live end-user-facing app path the audit's finding was about.

## Verification

- `pytest tests/test_model_runtime.py tests/test_citation_equity.py tests/test_publishers.py -q` — 69 passed.
- `pytest tests/test_summarization.py tests/test_critical_review.py tests/test_registration_comparisons.py -q`
  — 55 passed (broader sanity sweep over every real caller of the pinned resolvers).
- New regression test `test_default_models_resolve_with_their_pinned_revision`
  (`tests/test_model_runtime.py`): confirms the two default models resolve with their pinned revision, an
  explicit caller override still wins, and an unknown model name resolves unpinned.
- `ruff format` + `ruff check` on all 3 touched files — clean.
- `python tools/check_line_budget.py` — clean (578 files).
- `python -m tach check` — clean.
- Confirmed neither touched file (`model_runtime.py`, `dependencies.py`) is part of any frozen qualification
  manifest, and neither is inside the demo-experience or website-coverage drift gates' watched globs — both
  stay green with zero refresh needed this time.

## Revert

Revert this increment's commit. No database migration or data mutation involved. Reverting restores the
previous unpinned (`revision=None`) behavior exactly.
