# Security Audit — Provider-agnostic egress gate at the DI seam (increment 58)

**Date:** 2026-06-19
**Trigger:** Change to data-egress enforcement (invariant #3) — moves the authoritative gate from
provider self-checks (by convention) to the dependency-injection seam. Net ≈90 LOC new + edits across
3 routers/providers. (Audit gate criterion #4-analog: change to the enforcement boundary that protects
library text.)

## What changed (enforcement points that moved)
- **Canonical `DataEgressDisabledError`** now lives in `app/backend/llm/egress.py` (provider-neutral).
  `integrations/gemini/generator.py` imports + re-exports it, so every existing import path
  (`from integrations.gemini import …`, `from integrations.gemini.generator import …`,
  `axis_terms.py`, `axis_cluster_labeler.py`) resolves to the **same class** (verified by an identity
  smoke test).
- **Three egress-gating wrappers** (`EgressGatedSummaryGenerator`, `EgressGatedAxisTermSuggester`,
  `EgressGatedAxisClusterLabeler`) conform to the existing provider protocols; each holds an inner
  instance + the resolved `data_egress_enabled` flag, raises `DataEgressDisabledError` when egress is
  disabled, else delegates unchanged.
- **The wrappers are applied at the three router factories** (`_summary_generator`,
  `_axis_term_suggester`, `_axis_cluster_labeler`), so the gate now covers the **injected** provider AND
  the default — closing the hole where an instance injected via `create_app(...)` was returned
  unchecked. The egress flag is read from `GeminiConfig.from_environment().data_egress_enabled` (the
  same env source as before).
- **Providers keep their internal `if not self.config.data_egress_enabled: raise …` checks** as
  defense-in-depth (not removed — removing them risked a behavior change).

## Threat review
- **Data egress (the core concern):** before this change, an injected provider bypassed the egress
  check entirely; only the provider self-gating by convention protected source text. Now the seam is
  the authoritative boundary: no library text reaches `inner.generate()/suggest()/label()` unless
  `data_egress_enabled` is true at request time. The summarize path sends source chunks; the term
  suggester sends only the user's own axis label/description; the cluster labeler sends only
  representative titles — all three are now gated at the seam.
- **Input validation / output encoding / injection:** unchanged — no prompt/parse code touched, no new
  request schema, no SQL. The wrappers forward the exact keyword arguments unchanged.
- **SSRF / external calls:** unchanged — the wrappers add NO new network calls; they gate the existing
  Gemini calls. With egress disabled the wrapper raises **before** the provider would import/call
  `google.genai`, so egress-off never touches the network (same property as the provider self-checks).
- **Secret handling:** unchanged — `GOOGLE_API_KEY` still read only inside the provider; the default
  summary path keeps its `resolved_api_key()` RuntimeError guard with the actionable message.
- **Resource caps / file paths / supply chain:** unchanged — no new dependency, no file I/O, no caps
  affected.
- **API shape:** unchanged — no new routes (route-surface invariant test green), no response-model
  change. The `routers/axes.py::except DataEgressDisabledError → 503` handler is unchanged and still
  catches the (now seam-raised) error.

## Negative-path checks (results)
Added hole-closed tests that inject a fake provider that does **NOT** self-gate, with egress disabled,
and assert the seam blocks rather than calling the fake:
- `test_summarize_injected_generator_blocked_when_egress_off` → summarize job status `error`, detail
  contains `DataEgressDisabledError`, no summary produced. **PASS.**
- `test_suggest_terms_injected_suggester_blocked_when_egress_off` → `/axes/suggest-terms` returns
  **503**. **PASS.**
- `test_suggest_axes_injected_labeler_blocked_when_egress_off` → suggest-optimal-axes falls back to
  **local** labels (never the injected "Gemini Label"), status `done` (never 503). **PASS.**

Behavior-preserved (egress enabled → injected fake IS called):
- `test_summarize_injected_generator_runs_when_egress_on` (new) + the existing happy-path summarize /
  `test_suggest_terms_returns_curated_list` / `test_suggest_axes_uses_injected_gemini_labeler` (now run
  egress-on via the conftest consent default). **PASS.**

Pre-existing egress-OFF behavior unchanged:
- `test_summarize_real_generator_without_egress_fails_gracefully` (default Gemini, no key) still errors
  with the "CALLOSUM_ALLOW_DATA_EGRESS=true and a Gemini API key" RuntimeError message (the default
  branch's pre-checks are retained). **PASS.**
- `test_suggest_terms_egress_off_returns_503` (default Gemini, egress off) still 503. **PASS.**
- `test_summarization.py` / `test_validation_harness.py` egress-off provider self-checks (explicit
  `GeminiConfig(data_egress_enabled=False)`, not env) unaffected. **PASS.**

Full suite: **203 passed.**

## Residual / not in scope
- `tools/validation_harness.py` constructs `GeminiSummaryGenerator` directly (a manually-run dev tool,
  not the `create_app` seam); it relies on the provider self-check, which is retained. Left as-is.
- Crossref (`/papers/{id}/re-resolve`) intentionally sends only a DOI to a public metadata API and is
  deliberately NOT behind the egress gate (inc-49 decision) — out of scope here.

**Security Audit: PASS.**
