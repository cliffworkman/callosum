# Increment 494 — synthesis primary / Overview transaction split

## Implemented

- Phase A keeps generation, local verification, summary status, ordered sentences, citation mappings, evidence
  quotes, and all verification provenance atomic. The router exits `engine.begin()`, rereads that committed graph
  through a fresh connection, and only then marks the primary synthesis job done.
- Phase B uses the committed summary id. It atomically acquires `pending` work as `running`, closes the database
  context, rereads committed verified claims, performs the provider call with no connection/transaction held, then
  uses a short compare-and-swap transaction to write the unchanged `overview_json` representation and `complete`.
- `summaries.overview_status` and `overview_updated_at` are additive nullable columns. New rows explicitly use
  `not_requested`, `pending`, `running`, `complete`, or `failed`. Legacy rows with non-null Overview JSON read as
  complete; legacy null rows read as not requested and never trigger provider egress.
- Manual Overview-only retry reuses the same summary id and never creates or rewrites the primary graph. Pending,
  failed, or five-minute-stale running work can be acquired exactly once; complete is immutable under ordinary retry.
  Startup/reload performs no automatic retry or provider call.
- The UI renders verified/flagged claims in every Overview state. A bounded authoritative refetch observes normal
  completion; failure shows a small retry action. Reload reads the persisted lifecycle and result.

## Measurement receipt

- Controlled fake Overview delays of 0.46, 1, 3, and 5 seconds left primary completion at 0.0200, 0.0174, 0.0181,
  and 0.0206 seconds respectively; final Overview commits arrived at 0.482, 1.018, 3.019, and 5.021 seconds.
- A competing SQLite writer took 0.0132–0.0155 seconds while those providers were sleeping, versus a 0.0211-second
  no-hold baseline. Its wait no longer scales with provider delay (historical one-transaction references were about
  1.08 and 3.11 seconds for 1- and 3-second holds).
- Three permitted real-provider Overview attempts over a synthetic verified claim all returned provider errors in
  the current quota/runtime state. Primary visibility still occurred in 0.017–0.043 seconds and every primary
  survived; no successful real-provider latency comparison is claimed.

## Correctness coverage

- Focused tests cover Phase-A rollback atomicity, commit-before-mark-done, blocked-provider visibility from another
  connection, provider timeout/exception/malformed output, invalid reference postprocessing, Phase-B write failure,
  same-summary retry, concurrent acquisition, complete immutability, stale running recovery, legacy rows, frontend
  states/bounds, authoritative reload, migration/model drift, and unchanged Overview ordinal mapping.
- Existing synthesis readback tests continue to protect sentence order, citation mapping/evidence shape, status,
  quote/retrieval/support confidence, coordinate provenance, generation-cache behavior, and long-poll completion.
- The affected synthesis/cache/long-poll/runtime/frontend/migration set passed 192 tests. The final parallel root
  suite passed **2427 tests with 3 skipped in 978.95 seconds**. Ruff format/check, Bandit, Tach, the 560-file line
  budget, generated-frontend equality, migration drift, and `git diff --check` passed.

## Principles and boundaries

Principles 1, 8, and 10 remain controlling: generated prose is never exposed before evidence is durable; scientific
atomicity ends at the complete primary trust spine; the supplementary narration cannot erase or delay that spine.
Primary generation still occurs inside Phase A's transaction, as do the required local verification and persistence.
Critical Read, provider/model runtimes, generation-cache v2, prompts, token limits, and other latency targets are
unchanged.
