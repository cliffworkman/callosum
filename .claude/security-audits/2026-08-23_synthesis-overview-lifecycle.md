# Security audit — synthesis primary/Overview lifecycle split (inc 494)

**Date:** 2026-08-23
**Feature:** decouples the token-expensive, supplementary synthesis "Overview" narration from the primary,
verified-claim synthesis so a slow/failing Overview provider call can never delay or corrupt the already-durable
primary trust spine. **Gate trigger:** a new API endpoint (`POST /summaries/{summary_id}/overview/retry`) + a new
database migration (`0075_summary_overview_lifecycle`) + a net-new feature spanning well over 3 files (18 files
touched, ~941 added lines per `git show --stat 6528109`). This audit was never written at the time the work
landed (commit `6528109`, 2026-08-23); it is a delayed formalization written against the real, currently-shipped
code, not a transcription of the increment notes.

## Surface added

- `app/backend/api/routers/summary_overview.py` (new, 83 lines) — `POST /summaries/{summary_id}/overview/retry`,
  mounted as a sibling router on `summaries.router` (`router.include_router(overview_router)`). Also hosts
  `resolve_overview_generator`, the egress-gated Overview generator factory shared by both the primary
  synthesize flow and this new retry route.
- `app/backend/summarization/overview_lifecycle.py` (new, 199 lines) — `acquire_overview` (atomic
  compare-and-swap state transition), `load_overview_input` (rereads only committed verified claims),
  `generate_overview` (runs the provider call with no DB connection held), `_persist_overview` (a second CAS
  write), `overview_status_for_row` (legacy-compatible status interpretation).
- `alembic/versions/0075_summary_overview_lifecycle.py` — two additive nullable columns on `summaries`:
  `overview_status` (`String(32)`) and `overview_updated_at` (`DateTime`).
- `app/backend/api/routers/summaries.py` — `_run_summarize_job` restructured into two phases (see Threat review).
- `app/backend/persistence/schema_summaries.py` — the two new columns added to the `summaries` table definition.
- `app/backend/llm/cache.py` (inc 493, shipped immediately before this increment on the same branch) —
  `GenerationCacheIdentity` hardens the synthesis generation-cache key to include a credential fingerprint; not
  new surface added by inc 494 itself, but its credential-handling property is verified below since the finding
  that triggered this audit named it as adjacent, already-reviewed work.
- Frontend: `19b_synthesis_overview.jsx` (new) renders the four Overview lifecycle states and calls the new
  retry endpoint with an empty POST body (`apiPost('/summaries/${summaryId}/overview/retry', {})`) — no
  user-supplied text reaches this endpoint beyond the summary id already embedded in the URL path.

## Threat review

**Input validation.** `summary_id` is a path parameter FastAPI types as `int`; there is no free-text or JSON body
input to this endpoint at all (the frontend posts `{}`). `get_summary(conn, summary_id)` raises `NoResultFound`
for an unknown id, caught and turned into a clean `404` rather than a raw traceback.

**State-gating (the retry endpoint cannot coerce an ineligible row into a provider call).** Verified directly
against the code, not just asserted:

- The egress gate is the *first* thing evaluated, before any database read: `resolve_overview_generator(request.app)`
  runs before `engine.begin()`. If the active provider needs egress and the app lacks consent + a resolved key,
  it returns `None` and the endpoint 409s ("Overview generation is not currently available") without ever
  touching the database — the refusal wins even over a would-be 404 for a bad `summary_id`, the same ordering
  invariant other egress-gated endpoints in this codebase already follow.
- If `overview_status_for_row(summary) == "complete"`, the endpoint returns `accepted=False` immediately and
  never calls `acquire_overview` — a completed Overview cannot be silently regenerated/overwritten by a retry.
- `acquire_overview(conn, summary_id, allow_pending=True, allow_failed=True)` builds its `WHERE` clause as an
  `or_()` over exactly three raw-column conditions: `overview_status == "pending"`, `overview_status == "failed"`,
  or (`overview_status == "running"` AND `overview_updated_at` older than the 5-minute staleness window). A row
  whose raw `overview_status` is `"not_requested"`, or `NULL` (a legacy pre-lifecycle row, whether it reads as
  `"complete"` or `"not_requested"` through `overview_status_for_row`'s compatibility mapping), matches none of
  these three conditions — the `UPDATE`'s `rowcount` is `0`, `acquired` is `False`, and the endpoint 409s. A
  legacy or not-requested row is therefore **structurally** ineligible for the retry path, not just
  documented as such: there is no code path from "row was never requested" to "provider call happens."
- `acquire_overview` is a single atomic `UPDATE … WHERE …` inside one transaction — the state transition to
  `"running"` and the eligibility check are the same database operation, so two concurrent retry calls cannot
  both believe they acquired the same row. Proven empirically, not just by inspection:
  `tests/test_summary_overview_lifecycle.py::test_concurrent_retry_cas_runs_one_provider_call` fires two real
  threads at a `threading.Barrier`-synchronized `acquire_overview` call against the same summary and asserts
  `sorted(acquired) == [False, True]` — exactly one contender wins.

**Migration safety.** `0075_summary_overview_lifecycle.py` only adds two nullable columns (`overview_status`,
`overview_updated_at`) to the existing `summaries` table; there is no `DROP`, `ALTER … NOT NULL`, data
migration, or index change. It is idempotent (`if "overview_status" not in columns:` / same for the second
column) and guards a fixture edge case (a regression fixture that models only the immediately-preceding
migration's table has nothing for this one to touch, so it returns early rather than raising `KeyError` on a
missing `summaries` table). `down_revision = "0074_paper_sections"` correctly chains onto the real prior head
(`0074_paper_sections`, confirmed against `alembic/versions/`); `downgrade()` is a documented no-op, consistent
with this project's stated "no down-migrations by design" convention. `revision`/`down_revision` are unique,
single-parent, non-branching.

**Credential handling in the generation-cache identity (inc 493, adjacent).** `app/backend/llm/cache.py`'s
`GenerationCacheIdentity.from_config` computes `credential_identity=canonical_hash({"credential": resolved_key
or ""})`, where `canonical_hash` is `hashlib.sha256(...).hexdigest()` over a canonical JSON encoding. The raw
resolved API key is read once (`config.resolved_api_key()`) purely to feed the hash function and is never
assigned to any field of the frozen `GenerationCacheIdentity` dataclass, never included in the `signature`
property's output beyond its hashed form, and never passed to logging. `endpoint_identity` and
`provider_environment_identity` follow the identical hash-not-store pattern. Grepped directly: no raw
`resolved_api_key()`/`api_key`/`base_url` value is written into the `llm_cache` table or any log call in
`app/backend/llm/cache.py` — only the three `canonical_hash(...)` digests and non-secret labels
(`generator_name`, `provider`, `model`, `wire_mode`, `generation_parameters`) are persisted or hashed into the
final `signature`.

**Concurrency / failure-mode isolation (the core design property of this increment).**

- *Phase A (primary synthesis) is unaffected by Phase B (Overview).* `_run_summarize_job`
  (`app/backend/api/routers/summaries.py`) commits the entire verified synthesis — generation, local NLI/
  embedding verification, sentence order, citation mappings, evidence quotes — inside one `engine.begin()`
  block, exits that transaction, **rereads the committed graph through a fresh connection**
  (`engine.connect()`), and only then calls `jobs.mark_done(...)`. Nothing about Overview generation runs
  inside that transaction or before that `mark_done()` call. `generate_overview` is invoked strictly *after*,
  in its own `try/except Exception` that swallows every provider/parse/write failure, logs only the summary id
  and exception *type* name (`type(exc).__name__`, never the raw exception text — so a provider error body
  that might embed a credential or prompt fragment is never logged verbatim), flips the row to `"failed"`, and
  returns a status rather than raising. `tests/test_summary_overview_lifecycle.py::
  test_overview_failure_never_rolls_back_primary` and `::test_phase_a_failure_rolls_back_entire_primary` cover
  both halves of this isolation directly.
- *No database connection is held during the provider call.* `generate_overview` closes its read connection
  (`with engine.connect() as conn: overview_input = load_overview_input(conn, summary_id)`) before calling
  `generator.generate(...)`, and only opens a new short `engine.begin()` block afterward to persist the result.
  `test_primary_is_committed_and_job_done_while_overview_is_blocked` exercises this by blocking the fake
  Overview generator and asserting the primary summary is already visible from an independent connection while
  it blocks — confirmed by reading the test, not merely trusting its name.
- *First-success-wins with no clobber window.* `_persist_overview`'s `UPDATE` only succeeds when
  `overview_status == "running"` **and** `overview_json IS NULL`, checked via `rowcount == 1`; combined with
  `acquire_overview`'s own atomic acquisition (above), two racing attempts to write a result for the same
  summary cannot both "win" — the loser's write silently no-ops (`rowcount == 0`) rather than overwriting the
  winner's already-persisted `overview_json`.
- *Stale-`running` recovery is manual, not automatic.* A `running` row older than
  `OVERVIEW_STALE_AFTER` (5 minutes) becomes retry-eligible only through an explicit user action hitting the
  retry endpoint — nothing runs this on app startup or page load, so a crashed/killed process cannot cause
  unconsented provider egress on the next launch. `test_stale_running_is_manually_reclaimable_but_reload_causes_no_egress`
  names this property directly.

**No SQL injection / no raw string interpolation.** Every query in `overview_lifecycle.py` and
`summary_overview.py` is built with SQLAlchemy Core's `select`/`update` expression API against typed `Table`
objects (`summaries`, `summary_sentences`, `citation_mappings` from `persistence.schema`); no f-string or
`%`-formatted SQL text appears anywhere in either file.

**No new egress path.** The retry endpoint reuses the exact same `resolve_overview_generator` →
`EgressGatedOverviewGenerator` chain the primary synthesize flow already used before this increment
(`app/backend/llm/egress.py`'s pre-existing `EgressGatedOverviewGenerator`, inc 124) — this increment adds no
new provider client, no new credential source, and no new non-loopback call site. The only network call
Overview generation ever makes is the same Gemini/OpenAI/Anthropic/local-compatible `complete()`-seam call every
other LLM feature in this codebase already makes, gated by the same `CALLOSUM_ALLOW_DATA_EGRESS`/Settings
consent posture (invariant #3).

**No new dependency.** `git diff` for this commit touches no `pyproject.toml`/`requirements*.txt`/`uv.lock` —
confirmed against the `git show --stat` file list above, which lists only application, migration, test, and
doc files.

## Negative-path checks (recorded, from `tests/test_summary_overview_lifecycle.py`)

- **Phase A failure rolls back the entire primary** — `test_phase_a_failure_rolls_back_entire_primary` forces a
  mid-transaction exception and asserts no partial summary/sentence/citation row survives. ✓
- **Overview failure never rolls back the primary** — `test_overview_failure_never_rolls_back_primary` (see
  Threat review). ✓
- **A DB write failure during Overview persistence is isolated and retryable** —
  `test_overview_db_write_failure_isolated_and_retryable`. ✓
- **A completed Overview is immutable under retry; a failed one can be retried against the same summary** —
  `test_failed_overview_retries_same_summary_and_complete_is_immutable`. ✓
- **Concurrent acquisition races to exactly one winner** —
  `test_concurrent_retry_cas_runs_one_provider_call` (see Threat review). ✓
- **A stale `running` row is reclaimable only manually; reload/startup causes no egress** —
  `test_stale_running_is_manually_reclaimable_but_reload_causes_no_egress`. ✓
- **Legacy pre-lifecycle rows read as a safe non-pending status** —
  `test_legacy_rows_have_safe_non_pending_compatibility`. ✓
- **Unknown summary id → 404, not a crash** — covered by the router's `except NoResultFound` branch (mirrors
  the same pattern audited elsewhere in this codebase, e.g. the Zotero import job-id lookup).

The increment notes additionally report the full parallel root suite passing 2427 tests (3 skipped) with ruff
format/check, Bandit, Tach, the line-budget gate, generated-frontend equality, and migration-drift checks all
green at the time of landing; this audit did not re-run the full suite (out of scope for a documentation-only
audit backfill) but did directly re-read every test named above to confirm each assertion actually exercises
the property it is credited with, rather than trusting the name alone.

## Residual risk / known scope boundaries

- This audit covers the backend lifecycle/migration/cache-identity surface only. Frontend UX issues in the
  Overview retry flow (a separate concurrent fix-wave's scope) are not security-relevant and are not assessed
  here.
- Overview generation, like every other LLM feature in this codebase, is probabilistic narration of already
  locally-verified claims (Principle #1) — this increment does not change what is sent to a provider or what
  trust the narrated Overview carries; it only changes *when* and *how atomically* that supplementary step is
  attempted relative to the durable primary synthesis.

## Result

**Security Audit: PASS.** The new endpoint is gated by the pre-existing egress consent check before any
database access, cannot be coerced into acting on a complete/not-requested/legacy row (verified structurally,
not just documented), and its acquisition/persistence pair is a genuine atomic compare-and-swap with an
empirically-proven no-clobber property under real concurrent threads. The migration is additive, nullable,
idempotent, and correctly chained. The adjacent generation-cache credential hardening hashes rather than
persists or logs any raw credential value. No new dependency, no new egress path, no raw SQL, and no
regression in the primary synthesis's durability guarantees were found.
