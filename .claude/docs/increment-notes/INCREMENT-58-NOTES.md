# Increment 58 Notes — Provider-agnostic egress gate at the DI seam

Data-egress enforcement (invariant #3) used to live **inside each Gemini provider, by convention**. The
dependency-injection seam had a hole: `_summary_generator` pre-checked egress **only** in the fallback
branch that builds the default Gemini — a generator injected via `create_app(summary_generator=…)` was
returned **unchecked**, and `_axis_term_suggester` / `_axis_cluster_labeler` had no factory-level check
at all. The only thing then protecting source text for an injected provider was the provider self-gating.
This increment moves enforcement to a **provider-neutral gate applied at the factory seam**, covering the
injected instance AND the default, for all three injectable Gemini providers.

## Implemented
- **New `app/backend/llm/egress.py`** (+`__init__.py`) — the **canonical home** of
  `DataEgressDisabledError` plus three egress-gating wrappers conforming to the existing protocols:
  `EgressGatedSummaryGenerator` (`SummaryGenerator`), `EgressGatedAxisTermSuggester`
  (`AxisTermSuggester`), `EgressGatedAxisClusterLabeler` (`AxisClusterLabeler`). Each holds
  `{ inner, data_egress_enabled }`, raises `DataEgressDisabledError` when egress is disabled, else
  delegates unchanged. The summary wrapper exposes `name` (delegating to `inner.name`) so persisted
  generator identity is preserved.
- **`integrations/gemini/generator.py`** — replaced the local `class DataEgressDisabledError` with
  `from app.backend.llm.egress import DataEgressDisabledError` (+ `__all__` re-export). Every existing
  import path resolves to the same class (identity-verified). Provider self-checks **kept** as
  defense-in-depth.
- **`routers/summaries.py::_summary_generator`** + **`routers/axes.py::_axis_term_suggester` /
  `_axis_cluster_labeler`** — each now resolves `inner` (injected or default Gemini) and returns it
  **wrapped** with the egress flag from `GeminiConfig.from_environment().data_egress_enabled`. The
  default-summary branch keeps its `RuntimeError` pre-checks (the actionable "…CALLOSUM_ALLOW_DATA_EGRESS=true
  and a Gemini API key" message + the API-key check the gate doesn't do).
- **`tests/conftest.py`** — an autouse fixture sets `CALLOSUM_ALLOW_DATA_EGRESS=1` by default (models
  "consent given"), so happy-path tests that inject a fake provider exercise generation through the gate
  with no per-test edits; egress-OFF tests already `monkeypatch.delenv(…)`, which composes.
- Removed 25 stray `*.tmp.26380.*` atomic-write orphans left across the tree by an earlier crashed
  process (rule #5 / file-containment).

## Key technical detail
`app/backend/llm/egress.py` must NOT runtime-import `integrations.gemini.*`: `generator.py` re-exports
`DataEgressDisabledError` from it, so a runtime import back would be circular. The module runtime-imports
only `app.backend.summarization.generators` (pure) and references the `AxisTermSuggester` /
`AxisClusterLabeler` protocols under `TYPE_CHECKING`. Net effect at the seam: injected + egress-off →
the wrapper raises **before** `inner` runs → summaries job marks `error` ("DataEgressDisabledError: …");
`/axes/suggest-terms` → **503** (existing handler); the labeler → `apply_labels`'s catch-all → **local
fallback** (suggest-optimal-axes still never 503s). Egress-on → wrappers pass through, identical to today.

## "PR description" (callosum is not a git repo — recorded here per the request)
**Enforcement points that moved:** the canonical `DataEgressDisabledError` (→ `app/backend/llm/egress.py`)
and the authoritative egress check (→ the three router factories `_summary_generator`,
`_axis_term_suggester`, `_axis_cluster_labeler`, via wrappers). **Why the existing Gemini path is
unaffected:** the wrappers read the same `GeminiConfig.from_environment().data_egress_enabled` flag and,
when egress is on, delegate straight to the unchanged Gemini provider (whose own internal check also still
passes). The default-summary RuntimeError guards are retained verbatim. No prompt/parse/pipeline/
verification/persistence/API-shape code was touched; no routes added.

## Manual verification script
Backend-only (no frontend) — the hole-closed pytest IS the negative-path proof:
1. `pytest` → **203 passed**.
2. Re-export identity: `python -c "from app.backend.llm.egress import DataEgressDisabledError as A; from
   integrations.gemini import DataEgressDisabledError as B; from integrations.gemini.generator import
   DataEgressDisabledError as C; assert A is B is C"` → no error.
3. (Optional live) with `CALLOSUM_ALLOW_DATA_EGRESS` unset, `POST /axes/suggest-terms` → 503; `POST
   /summarize` with a configured-but-injected provider → job `error` mentioning DataEgressDisabledError.

## Verification
- **pytest: 203** (+4: two summaries [hole-closed + behavior-preserved], two axes [suggester + labeler
  hole-closed]). Route-surface invariant (`test_health.py`) green — no new routes.
- Audit: `.claude/security-audits/2026-06-19_egress-gate-seam.md` — **PASS**.
- 600-line cap: `egress.py` 88, `summaries.py` 392, `axes.py` 586 (watch — approaching), `generator.py`
  99 (shrank). All < 600.
- No `callosum-app.html` rebuild (backend-only); no live E2E needed.

## Backlog
Queued (unchanged): library **merge** (last, destructive); terms-as-first-class; DESIGN.md `.btn-*` DRY;
embedding-text JATS cleanup; permanent-delete/empty-trash; persistent dedup-dismiss.
