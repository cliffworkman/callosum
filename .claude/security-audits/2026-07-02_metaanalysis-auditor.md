# Security audit — Meta-analysis reporting auditor (inc 249, backlog #36 consumer-side)

**Date:** 2026-07-02
**Feature:** `methods/metaanalysis.py` (pure regex auditor) + `GET /papers/{id}/meta-analysis`
(`routers/metaanalysis.py`) + the `08g_methods_metaanalysis.jsx` METHODS panel. Reads a published meta-analysis's
extracted text and flags whether it *reports* 7 key methodological choices — present / not-found / not-applicable.
Near-exact clone of the inc-247 LMM auditor (`2026-07-02_lmm-auditor.md`).

**Audit-gate trigger:** #1 (a new API endpoint) + #5 (a net-new feature spanning 3 files). Light review — the feature
is local, read-only over the paper already in the library, with no external fetch / egress / LLM / migration / new
dependency.

## Threat review

- **Input validation / boundary (rule #4):** the only endpoint input is `paper_id` (a path int, coerced by FastAPI)
  + the paper's own extracted chunk text (already ingested + validated at import; untrusted-content posture unchanged).
  The regexes are literal / anchored token patterns with no catastrophic backtracking (bounded alternations, `\b`
  anchors, character classes), run over each chunk's text; no user-supplied pattern reaches `re`.
- **Injection / SQL (rule #3):** the router writes no SQL — it reads via the audited repo helpers `get_paper` +
  `get_chunks_for_paper` (SQLAlchemy Core bound parameters). No string-built SQL.
- **Output encoding:** the response is a Pydantic `MetaResponse` (JSON); the panel renders `label`/`note`/`explainer`/
  `basis`/`evidence` as React text nodes (no `dangerouslySetInnerHTML`) — no XSS surface. Evidence snippets are
  whitespace-collapsed + length-capped (200 chars) in `_snippet`.
- **SSRF / external calls:** NONE. The auditor makes no network call; it reads only the local DB. Not the Gemini
  egress gate (no library text leaves the machine).
- **Data egress:** NONE. Fully local — no LLM, no external fetch. The egress invariant (#3) is untouched.
- **Resource caps:** the auditor is O(chunks × patterns) over a single paper's already-bounded chunk set; each check
  short-circuits on the first match (`_first`/`_has`). No unbounded loop / recompute. (No explicit MAX_RESULTS is
  needed — unlike statcheck/bayes it emits a fixed 7-check list, not a per-match list.)
- **File-path safety:** no filesystem access.
- **Secret handling:** none involved.
- **Supply-chain:** no new dependency (stdlib `re` + dataclasses; the credit ＋add reuses the existing inc-93
  `/library/import`).

## The identity boundary (the load-bearing security-relevant property)

The auditor **reads reported text only** — it NEVER pools, models heterogeneity, meta-regresses, computes an effect
size, or does bias inference (metafor/JASP/RevMan territory). This is enforced **structurally** (there is no
statistical-computation code path — no numeric aggregation of study data) and **test-pinned**:
`test_no_statistical_computation_import` asserts the module source imports none of `numpy`, `scipy`, `statsmodels`,
`sklearn`, `pandas`.

## Honesty / no-accusation controls (verified)

- **FLAG-not-ADJUDICATE:** statuses are only `present` / `not-found` / `not-applicable`; there is no `score`/`grade`/
  rank field (`test_no_verdict_no_score`). The panel tally is a factual status count, explicitly "not a score".
- **Precondition-scoping:** check 7 (search & selection) → `not-applicable` for a within-study mini-meta (no
  systematic search) — a flag firing on every meta-analysis would be the failure mode.
- **"not found" wording:** always "not detected in the extracted text — check the paper", never "missing" (tables/
  figures aren't fully read — silence≠certificate cuts both ways).
- **No accusation** of the authors (A-A veto): a fired flag is a reader's prompt with a cited recommendation, never
  "this meta-analysis is flawed"; no per-author aggregate.

## Negative-path checks (run)

- Non-meta paper (RCT that merely mentions "a recent meta-analysis") → `is_meta_analysis:false`, no checks (gate off).
- A within-study mini-meta with no systematic search → search check `n/a` (not a false "not found").
- 404 on an unknown paper id; a paper with no extracted chunks → 200 `is_meta_analysis:false`, honest-empty (not a crash).
- No `score`/`grade`/verdict field anywhere in the report.
- The identity-boundary static import assert passes (no numpy/scipy/statsmodels/sklearn/pandas import).

All covered by `tests/test_metaanalysis.py` (12 tests, hermetic; no network/model).

## Conclusion

Local, read-only over the paper in hand; no external fetch / egress / LLM / migration / dependency; the
never-computes-statistics identity boundary is structural + test-pinned; the flag-not-adjudicate / precondition-scoped
/ not-found-≠-missing controls uphold the no-accusation boundary.

**Security Audit: PASS**
