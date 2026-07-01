# Security audit — Bayesian auditor SP1 (`GET /papers/{id}/bayes`), inc 241

**Feature.** A deterministic, local, no-LLM METHODS producer (the statcheck sibling for Bayesian t-tests). For a
paper, it scans the extracted chunk text for inline `t(df) = …, BF10 = …`, recomputes the default JZS Bayes factor
(Rouder et al. 2009) from the reported `t` + `df` via `scipy.integrate.quad`, and reports where the reported and
recomputed values disagree. New: `app/backend/methods/bayes.py` (pure), a `GET /papers/{paper_id}/bayes` endpoint
(`routers/methods.py`, sync, read-only), and a METHODS panel (`08d_methods_bayes.jsx`).

**Audit trigger.** Gate item #1 — a new API endpoint (a read-only GET with no request body).

## Threat review

- **Input validation (rule #4).** The only input is `paper_id` (a path int; FastAPI coerces / 422 on a non-int) and
  the paper's own extracted chunk text (already validated at ingest). The BF regexes are anchored and bounded
  (`MAX_RESULTS = 500`); every numeric parse is wrapped (`try/except → skip`). A degenerate stat (`df <= 0`, a
  non-finite integral) yields `None` and the result is skipped, never a crash.
- **Injection / SQL (rule #3).** No SQL is written; the endpoint reads via the existing `get_chunks_for_paper` /
  `get_paper` (bound-param) and computes in pure Python. No user/external string reaches SQL text.
- **Output encoding.** The response is JSON (Pydantic `BayesResponse`); the frontend renders `raw`/numbers as plain
  React text (no `dangerouslySetInnerHTML`), so the verbatim matched string cannot inject markup.
- **SSRF / external calls / egress.** NONE. Fully local — no network, no LLM, not the Gemini gate. Same posture as
  statcheck / p-curve / GRIM.
- **Secret handling.** None involved.
- **Resource caps.** `MAX_RESULTS = 500` bounds the per-paper work on a huge/adversarial text; `scipy.integrate.quad`
  over `[0, ∞)` is a bounded 1-D quadrature per matched result. No unbounded loops.
- **File-path safety.** No filesystem access.
- **Supply-chain.** No new dependency — `scipy` is already an explicit dep (statcheck uses `scipy.stats`; this uses
  `scipy.integrate.quad`).
- **Coordinate honesty (#2).** Each per-BF row opens its page at `precision:"region"` (page-open, never a fabricated
  exact rect) — the same honest anchor statcheck's rows use.

## Principles posture (recorded; the gate ran in the design)

Signal-not-verdict (#2), no composite score (#7), evidence shown (#4 — the verbatim matched string + the recomputed
value + the assumed prior + the page), silence-≠-certificate (#6 — inline-only coverage is stated; a paper we can't
recompute isn't "fine"), no-accusation (A-A veto — a mismatch is framed "couldn't reproduce under the default prior",
never "wrong" or "p-hacked"; no per-author aggregate). It also errs toward "reproduced" (matches EITHER the paired or
two-sample interpretation, a generous log-scale tolerance) — the conservative, non-accusatory direction.

## Negative-path checks

- Non-int `paper_id` → **422** (FastAPI). Unknown `paper_id` → **404** (`get_paper` → `NoResultFound`).
- A metadata-only paper (no chunks) → `checked: 0`, an honest "no extractable text" — never an error.
- Malformed / oversized text: the regexes match nothing or are capped at 500; no crash.
- Egress while disabled: N/A — the endpoint makes no outbound call under any setting.

## Verification

pytest `tests/test_bayes.py` (hermetic — the JZS math against the pingouin anchor + sanity monotonicity; extraction +
design-both-interpretations reproduce-or-flag; the endpoint 404 / no-chunks-checked-0). No network / no model needed.

**Security Audit: PASS.** Local, read-only, bounded, no egress, no new dependency; coordinate honesty preserved.
