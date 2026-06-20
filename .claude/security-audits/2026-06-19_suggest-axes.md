# Security audit — Suggest optimal axes (increment 52)

**Date:** 2026-06-19
**Feature:** `POST /axes/suggest` (async job) + `GET /axes/suggest/{job_id}` — cluster the library's
embeddings, propose a diverse set of candidate axes (coverage-with-diversity), label them locally
(c-TF-IDF) with optional egress-gated Gemini polish. Files: `app/backend/clustering/axis_suggestion.py`
(new), `integrations/gemini/axis_cluster_labeler.py` (new), `app/backend/api/routers/axes.py`,
`app/backend/api/app.py`, frontend `17_axes_suggest.jsx` + `15_axes.jsx`.

**Audit triggers:** (1) new API endpoints; (2) a new external fetch (Gemini labeling); (5) a feature
spanning 3+ files. No new file-ingestion path; no new dependency (numpy/sklearn already present); no auth.

## Threat review
- **Input validation.** The endpoint takes **no client free-text** — it operates only on the library's
  own stored papers + axes. `GET /axes/suggest/{job_id}` takes a job id (dict lookup; unknown → 404).
  Clustering params are server constants. Nothing user-supplied reaches SQL or the model.
- **SQL.** Reads via SQLAlchemy Core `select()` (papers, axes); no writes (suggestions are ephemeral —
  the user creates axes via the existing validated `POST /axes`). No string-built SQL.
- **Data egress (invariant #3).** Clustering + local labeling are **fully local**. The ONLY egress is the
  optional Gemini *labeling*, which sends **representative paper titles** (bibliographic metadata, ≤12
  per cluster) — narrower than the existing summary path — and only when `CALLOSUM_ALLOW_DATA_EGRESS=1`.
  The gate is enforced in `GeminiAxisClusterLabeler.label` **before any genai import/call**
  (`DataEgressDisabledError`); `apply_labels` catches it per-cluster and falls back to local labels, so
  **egress-off never touches the network** and the endpoint still returns (never 503). Off by default.
- **Output handling.** Gemini output (label + terms) is defensively parsed (`_parse_label`):
  JSON-only, label length-capped, terms deduped/length-capped/count-capped (untrusted-output discipline,
  mirroring the term suggester). Rendered as React text/input values (auto-escaped) in the modal.
- **Failure modes.** The job runner wraps everything → `mark_error` (never 500). Any Gemini failure
  (network/parse/egress) → local label for that cluster. A library < 6 papers → empty suggestions.
- **Resource use.** Clustering re-encodes the library in-memory once per run (bounded by library size);
  the work runs in a background job (mirrors scoring). Gemini = at most one call per selected cluster
  (≤6). No unbounded loop.
- **Supply chain.** No new dependency — numpy + scikit-learn already ship (sentence-transformers).

## Negative-path checks (run)
- `pytest` (179): suggest returns clusters; **novelty filter** excludes themes an existing axis covers;
  an injected fake labeler polishes labels; a labeler raising `DataEgressDisabledError` → **local labels,
  job done (NOT 503)**; < 6 papers → empty. Route-surface invariant updated.
- Live E2E (`.local/suggest_axes_e2e/`, fake model, **no network**, no labeler → local fallback): ✨ →
  modal → 2 curated cards → Create → axis appears; **0 console errors**.

## Result
**Security Audit: PASS.** No client free-text input; local clustering; the sole egress is title-only,
consent-gated, and degrades to local (off → no network, no 503); untrusted Gemini output defensively
parsed; reads-only (creation goes through the existing validated route); no new dependency.
