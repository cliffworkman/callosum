# Increment 557 Notes — Local AI reliability audit + Wave 1/2 remediation

## Outcome

Ahead of a lab-meeting demo, two live bugs (Synthesize/Ask, single-paper Critical Review) were found and
fixed the same session: an unhandled `ManagedLocalTargetError` crash and a cloud-sized prompt cap that could
silently overflow the managed Local AI preview's ~10,240-token input budget (commits `35fe406`, `555627b`,
`479fa85`). Those two fixes motivated a thorough, independent-then-combined read-only audit of every place
callosum's backend contacts a local or cloud LLM provider — one pass from this session (6 parallel forks
covering shared plumbing + 5 feature-area groups) and one independent pass from Codex, merged into
`.claude/docs/research/2026-09-01_llm-provider-integration-audit.md`. This increment is the "first crack" fix
pass against that combined audit's Wave 1 (end-user-visible blockers) and Wave 2 (privacy/consistency) items,
in full. Wave 3 (DB-transaction/CAS redesign, Local-AI cache-identity redesign, auxiliary-model preflight,
cross-provider output-cap standardization) is deliberately deferred to a Codex handoff — the audit's own
report warns the DB-transaction fix needs snapshot/version/CAS semantics, not a naive reorder.

## Implemented

**Wave 1 — end-user-visible blockers:**
- **Frontend Local-AI gating fixed** (`08n_methods_analytic_flexibility.jsx`, `08x_methods_critical.jsx`,
  `08y_critical_set.jsx`, `20_synthesis.jsx`): all four read `data_egress_enabled` from `GET /settings` to
  decide whether AI is "ready" — false by design for `managed_local` (no egress needed), so a fully-working
  Local AI setup still presented these panels as gated off. Swapped to `generation_provider_available`
  (already correct at `45_workbench.jsx`).
- **Comprehensive `ManagedLocalTargetError` crash-site sweep.** Every `resolve_llm_config()` call site in the
  codebase (16 files) was directly inspected. Fixed the unguarded ones with the established template — catch
  `ManagedLocalTargetError` specifically, convert to `HTTPException(422, "Local AI is not ready (<code>). Check
  Settings → AI features.")` for a sync endpoint, or a classified job-error string for a background job:
  `app/backend/api/routers/analytic_flexibility.py`, `wip_checks.py` (Library + WIP analytic-flexibility),
  `workbench.py` (`_extraction_assistant`'s one caller), `summary_overview.py` (Overview retry),
  `critical_review.py` (both the single-paper path, already partly fixed, and a newly-found gap in
  `_run_set_tier2`, the Set Critical Review Tier-2 path — job-based, degrades to a friendly
  `llm_status.unavailable` instead of an opaque job error), `axes.py` (`suggest_axis_terms`, ride-along), and
  `my_publications.py`/`help.py` (ride-along, their existing broad `except Exception` already prevented a
  crash but showed a cryptic bare-exception message).
- **`axes.py`'s axis-cluster-label path gets a different fix shape.** Confirmed by direct read that
  `_run_axis_suggest_job` wraps its entire body in one `except Exception`, so a config-resolution failure was
  never a raw 500 — it failed the *whole job* (losing every cluster suggestion) instead of just the optional
  labeler polish `apply_labels(labeler=None)` already promises to degrade gracefully from. Fixed by catching
  `ManagedLocalTargetError` around just the labeler construction and passing `labeler=None` on failure,
  restoring the "egress-gated polish; local fallback" comment's own promise.
- **`critical_review_triage.py`'s three orchestration paths** (`triage_contested`, `triage_contested_dicts`,
  `triage_and_persist_candidates`) previously had zero exception handling around `triage_evaluator()` +
  `evaluator.evaluate()` — unlike the sibling funding/registration triage routers, which both already wrap
  their evaluate call in one broad `except Exception` returning a safe degraded status. Brought Critical
  Review triage to the same parity: `ManagedLocalTargetError` gets the friendly message, anything else
  (including a malformed/non-JSON model response — `app/backend/methods/critical_review_triage.py`'s bare
  `json.loads()`, previously undefended) degrades to `status: "failed"` with the existing findings still shown
  untriaged. This also transitively fixed `critical_review.py:302`'s optional `{"triage": true}` sub-step,
  which called into the now-safe `triage_and_persist_candidates`.
- **New shared `app/backend/llm/prompt_budget.py`** generalizes the truncate-never-drop pattern already
  shipped for Synthesize/Ask and single-paper Critical Review: `is_managed_local`, `per_item_char_budget`,
  `truncate_items`, `truncate_text`, `select_total_chars`. Applied at all 8 measured-overflow sites from the
  audit (each gets its own conservative `_MANAGED_LOCAL` budget constant, well under the ~10,240-token
  ceiling):
  - `app/backend/funding/llm_triage.py` — had **no** total-character cap at all before this fix (only an
    80-item count cap); added a `_bounded_items` cumulative-size-and-drop mechanism (mirroring the sibling
    evaluators) plus a `summary` field clip, since real measured worst-case input was 641,896 characters.
  - `app/backend/registration_comparison/llm_triage.py`, `app/backend/methods/critical_review_triage.py` —
    both already had a cloud-sized `MAX_TOTAL_INPUT_CHARS`; swapped in a managed_local-aware budget via
    `select_total_chars`.
  - `integrations/gemini/help_assistant.py` — the corpus already had a managed_local-aware cap; conversation
    history did not (up to 80,000 chars alone across 20 turns × 4,000 chars). Added
    `MAX_HISTORY_TURNS_MANAGED_LOCAL`/`MAX_TURN_LEN_MANAGED_LOCAL`.
  - `integrations/gemini/research_summary.py` — reduced `MAX_DOCUMENTS`/`MAX_ABSTRACT_CHARS` for managed_local.
  - `app/backend/workbench_assist.py` (`MAX_TEXT_CHARS_MANAGED_LOCAL`, wired from `workbench.py`'s
    `propose_row`) + `integrations/gemini/extraction_assistant.py` (a defense-in-depth cap at its own layer,
    since it previously had none and relied entirely on the caller).
  - `integrations/gemini/critical_review_set.py` — already had the per-paper truncate-never-drop shape;
    tightened the total budget for managed_local.
  - `app/backend/citations/section_scope.py`'s `paper_methods_text` + `app/backend/wip/
    analytic_flexibility_text.py`'s `wip_methods_text` — both already accepted a `max_chars` override; wired a
    managed_local-aware value from both callers (`app/backend/analytic_flexibility.py`, `wip_checks.py`).

**Wave 2 — privacy/consistency:**
- **`app/backend/llm/providers.py`**: `complete()`'s dispatch to `provider_runtime.run_http` now forces
  `trust_env=False` whenever the resolved `base_url` is loopback, regardless of the config's own
  `http_trust_env` value — closing the gap where a manually-configured "local"/custom loopback provider
  (which inherits `LLMConfig`'s `http_trust_env=True` default) would otherwise honor an ambient
  `HTTP_PROXY`/`HTTPS_PROXY`, silently routing "local, no egress" traffic through a proxy. The managed Qwen
  target already set this explicitly and is unaffected.
- `_LOOPBACK_HOSTS` no longer includes `0.0.0.0` (a bind-all address, not a client-reachable loopback target)
  — only affects manual/custom provider egress classification; the managed target is separately hard-pinned
  to a literal `127.0.0.1`.
- **`app/backend/providers_store.py`**'s `_norm_base` and **`app/backend/api/routers/settings.py`**'s
  `local_base_url` path both now reject a base URL carrying embedded userinfo (`https://user:pass@host`) —
  the key is already collected and stored separately, so a URL never needs to carry one.
- Fixed all 3 hardcoded `GOOGLE_API_KEY`-specific error messages (`help.py`, `axes.py`, `my_publications.py`)
  to name Settings generically rather than one specific cloud provider's env var, regardless of which
  provider is actually active. `help.py`'s message also stopped pointing at
  `CALLOSUM_HELP_ASSISTANT_ENABLED=1` (an env var) in favor of the real Settings UI toggle that already
  exists for it.
- Added `POST /critical-read/candidates/triage` to `TRACKED_AI_REQUESTS` (`04c_status.jsx`) — it was
  previously untracked in the Status popover (invariant #5).

## Key technical detail

The single root cause behind the crash-site sweep: `app/backend/api/dependencies.py::resolve_llm_config()`
has no exception handling of its own, and nothing enforces that a caller catches `ManagedLocalTargetError` —
every one of the ~13 call sites had to be independently checked and, where unguarded, fixed with the same
template. Two distinct existing degrade patterns exist in the codebase for provider failures: (1) a
synchronous endpoint converts to a clean `HTTPException(422, ...)`; (2) a job-based or non-endpoint helper
degrades to a status dict / job-error string without raising. Each fix in this increment matches whichever
shape its call site already used, rather than forcing one shape everywhere.

## Verification

- Targeted, per-touched-area: `pytest tests/test_providers.py tests/test_providers_roster.py
  tests/test_managed_local_ai.py tests/test_summarization.py tests/test_axes.py tests/test_workbench.py
  tests/test_workbench_assist.py tests/test_critical_review.py tests/test_critical_review_set.py
  tests/test_critical_review_triage.py tests/test_funding_discovery.py tests/test_registration_comparisons.py
  tests/test_help.py tests/test_my_publications.py tests/test_analytic_flexibility.py
  tests/test_wip_analytic_flexibility_checks.py tests/test_wip_analytic_flexibility_text.py
  tests/test_prompt_budget.py tests/test_settings.py tests/test_frontend_assembly.py -q` — 400+ passed, zero
  failures.
- `python tools/check_line_budget.py` — clean (578 files, none of the touched files near the cap).
- `ruff format` + `ruff check` on every touched Python file — clean.
- `python -m tach check` — clean.
- `python tools/build_frontend.py` — rebuilt `callosum-app.html` from the 5 touched `.jsx` files.
- `python tools/qa/check_website_coverage.py --refresh --note "..."` — reviewed and refreshed (no showcase
  claim/visual change needed; these are internal readiness-detection/tracking fixes).
- Full parallel suite (`pytest -n auto -q`) was started but exceeded this session's 10-minute background-task
  ceiling before completing — the ~29% observed before the timeout showed zero failures across many unrelated
  test modules. Per this project's own verification protocol ("CI also runs `pytest -n auto -q`, so you can
  lean on CI for the full gate"), the full-suite gate is completed by CI on push, not re-run to completion
  locally.

## Manual verification script (deferred)

Not run live this session (no interactive desktop session available mid-fix-pass): with a real managed Local
AI setup, exercise the analytic-flexibility check, single-paper Critical Review, and Set Critical Review UIs
to confirm they now show available instead of gated off (the A1 frontend fix), and confirm a large funding
triage / Help conversation / research-summary run against Local AI no longer silently overflows.

## Revert

Revert this increment's commit. No database migration or data mutation is involved — every change is either
exception-handling, a prompt-size budget, or a frontend field read.
