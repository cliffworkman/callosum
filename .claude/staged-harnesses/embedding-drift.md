# Staged harness: embedding/vector-drift harness

**Checks:** that switching the embedding model (currently `all-MiniLM-L6-v2`, with `bge-base-en-v1.5` also
supported) doesn't silently produce a library full of vectors from two incompatible spaces, and that there's
a real re-index path rather than a manual one-off script when a model change happens.

**Why deferred:** callosum has partial *text*-versioning (chunk text is tracked so re-extraction is
detectable) but no *model*-migration coverage — nobody has changed the default embedding model yet, so a
harness here would be exercising a code path that doesn't exist. Building it speculatively risks guessing
wrong about what the real migration needs.

**Activation trigger:** **before changing the embedding model** — i.e. this is a precondition for that
change, not an independent background check. If a future increment proposes switching the default model (or
adding a third option), this harness's design becomes part of that increment's plan, not an afterthought.

## Draft design (sketch — flesh out when the trigger fires)

- A `vectors` metadata row (or a column on the existing vector table) recording which model produced each
  embedding — `embedding_model` + `embedding_dim`, so a mixed-model library is *detectable*, not silently
  wrong.
- A migration/backfill script (`tools/reembed_library.py`-shaped) that re-embeds every chunk under the new
  model and swaps the `sqlite-vec` index atomically (never leaves a half-migrated, half-old-model library
  queryable in between).
- A CI/test check: `test_vector_dimensions_match_configured_model` — asserts every stored vector's dimension
  matches the currently configured model's known output dimension (catches a mismatched read of an
  old-model vector as if it were new-model).

## Activation steps
1. When a model change is proposed, write out the full design above as a real plan (this sketch is
   intentionally incomplete — it names the shape of the problem, not the solution).
2. Add the `embedding_model`/`embedding_dim` provenance columns via a migration.
3. Build + test the re-index script against a real library before flipping the default.
4. Update this registry's status to `active` (or superseded by the shipped migration tooling) once done.
