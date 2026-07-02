# Security audit — LMM-reporting completeness auditor (backlog #23, inc 247)

**Scope:** `app/backend/methods/lmm.py` (pure regex-over-text auditor), `app/backend/api/routers/lmm.py`
(`GET /papers/{id}/lmm`), `app.py` wiring, `08f_methods_lmm.jsx` (panel). A light audit — a new read-only endpoint,
no new external fetch / data path / egress / migration / dependency.

## Threat review

- **Input validation / injection:** the only inputs are a path integer (`paper_id`, FastAPI-coerced) and the paper's
  own extracted chunk text (read via the audited `get_chunks_for_paper`). No SQL is written by the feature — it reads
  through the repository (bound-param, rule #3). The regexes are literal/anchored alternations with no catastrophic
  backtracking; run over bounded chunk text.
- **Output encoding:** the response is JSON via Pydantic; the panel renders `evidence`/`note`/`explainer`/`basis` as
  React text nodes (no `dangerouslySetInnerHTML`). Evidence is a snippet of the paper's own text; page-open is at
  **region** precision (no fabricated exact rect — coordinate honesty #2).
- **SSRF / external calls:** none. The auditor reads local text only; there is no fetch. The credit block's
  add-to-library reuses the audited `POST /library/import` (CSL-JSON, local, no PDF).
- **Secret handling / data egress:** none. No LLM, no network — the auditor is fully local (like statcheck / GRIM /
  the Bayesian recompute). Not behind and not touching the Gemini gate.
- **Resource caps:** the checklist is a fixed 7 checks; `_first`/`_has` scan the paper's chunks once each. No unbounded
  growth. No new job/state.
- **File-path safety:** none touched.
- **Supply-chain:** no new dependency (stdlib `re` + dataclasses).
- **The identity boundary (the load-bearing one):** the tool **reads reported text and never runs a model, an
  imputation, or a sensitivity analysis, and never ingests raw data.** Enforced structurally — there is no
  model-fitting code path — and pinned by `test_no_model_fitting_import` (the module source contains no
  `lme4`/`mice`/`statsmodels`/`scipy.optimize`/`numpy` import).

## Negative-path checks (run)

- A non-LMM paper → `is_lmm:false`, empty checks (a paper it isn't subject to cannot "fail" the checklist).
- ICC / missing-data → `not-applicable` (with the reason) when their precondition doesn't hold — a flag that fires on
  every LMM is the failure mode; verified they don't.
- "not found" is worded "not detected in the extracted text — check the paper", never "missing" (silence≠certificate).
- `GET /papers/99999/lmm` → 404; a paper with no chunks → 200 `is_lmm:false` (honest-empty).
- No `*score*` / pass-fail / verdict field in the response (FLAG-not-ADJUDICATE); no author-facing accusation
  (A-A veto) — statuses are present / not-found / not-applicable only.

## Result

**Security Audit: PASS** — local read-only auditor over the paper-in-hand; no external fetch / egress / LLM /
migration / dependency; the never-runs-a-model boundary is structural + test-pinned; the flag-not-adjudicate /
precondition-scoped / not-found-≠-missing controls uphold the no-accusation boundary.
