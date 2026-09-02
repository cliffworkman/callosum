# Increment 559 Notes — Local AI cache-identity restart-persistence (Wave 3 item)

## Outcome

Closes the first of the four Wave 3 items deferred from increment 557's Local AI reliability audit: the
managed Local AI target's generation cache never survived a restart, since its cache identity keyed on the
per-launch-ephemeral bearer token and port. Deliberately scoped to touch only `app/backend/llm/cache.py` and
`app/backend/llm/managed_local.py` — **not** `app/backend/llm/providers.py`, which is one of the frozen inputs
to the `synthesis-overview-v1` qualification study (see inc 557/558's own re-freeze episode) — avoiding
another qualification re-freeze cycle for a change that has nothing to do with that study's own frozen request
transport.

## Implemented

- **`app/backend/llm/managed_local.py`**: `ManagedLocalTarget` gains `stable_identity_fingerprint()` — a
  sha256 of everything that determines WHAT a managed target generates (model/runtime/chat-template digests,
  context/output token sizes, temperature, seed), deliberately excluding the per-launch-ephemeral
  `endpoint`/`credential_ref` (security material, re-randomized every Tauri launch) and the
  `requested_execution`/`observed_execution` backend (a performance detail, not output-determining, given
  generation is already fixed-temperature/fixed-seed deterministic). `ManagedProviderConfig` gains a new
  `stable_identity_fingerprint: str = ""` field (default keeps directly-constructed fixtures backward
  compatible), populated by `ManagedLocalTarget.config()`.
- **`app/backend/llm/cache.py`**: `GenerationCacheIdentity.from_config()` now checks for a non-empty
  `stable_identity_fingerprint` on the config (`getattr(..., "")`, so any non-managed config is completely
  unaffected) and, when present, derives both `endpoint_identity` and `credential_identity` from it instead of
  the transport `base_url`/`resolved_api_key()`. A manually-configured "local"/custom loopback provider (no
  such attribute) keeps its existing transport-based identity unchanged.

## Key technical detail

The fingerprint is computed once, at `ManagedLocalTarget.config()` construction time, from the target's own
static descriptor fields — not recomputed per-request. This is safe for the one real caching call site
(`CachedSummaryGenerator` wrapping primary synthesis generation): `max_output_tokens` only varies *between*
the primary-synthesis and Overview `managed_output_contract`s, and Overview generation doesn't use the cache
at all (confirmed by direct read: `integrations/gemini/overview.py`'s own comment says "nothing cached yet"),
so the target-level fingerprint never goes stale relative to what a cached call site actually sends.

## Verification

- `pytest tests/test_llm_cache.py tests/test_managed_local_ai.py tests/test_summarization.py
  tests/test_providers.py -q` — 81 passed.
- `pytest tests/test_overview_qualification.py tests/test_overview_cloud_calibration.py
  tests/test_overview_phase41.py -q` — 24 passed (confirms zero impact on the frozen qualification study, as
  designed).
- `ruff format` + `ruff check` on all 4 touched files — clean.
- `python tools/check_line_budget.py` — clean (578 files).
- `python -m tach check` — clean.
- New regression tests: `test_managed_local_cache_identity_survives_a_restart` and
  `test_manual_local_provider_without_a_fingerprint_still_keys_on_transport` (`tests/test_llm_cache.py`);
  `test_stable_identity_fingerprint_ignores_endpoint_and_credential_but_not_model`
  (`tests/test_managed_local_ai.py`).

## Revert

Revert this increment's commit. No database migration or data mutation involved — existing `llm_cache` rows
are unaffected (their stored `input_hash` values remain valid; this only changes what a *new* managed_local
request's hash resolves to, so old rows simply age out normally, they don't become invalid or need cleanup).
