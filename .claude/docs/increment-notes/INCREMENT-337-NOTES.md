# Increment 337 — Backlog #23 (2/3): meta-analysis auditor gets F1 chip + F4 persistence + F2 footer fix

## Context
Second of three checkers, repeating the exact pattern proven for LMM (inc 336) with zero design changes needed —
meta-analysis's `MetaReport{is_meta_analysis, checks}` shape is structurally identical to `LmmReport`, so this
was a mechanical repetition rather than a fresh design pass.

## Implemented
- `app/backend/persistence/signals_repo.py`: `META_SIGNAL`/`META_SOURCE` + `store_meta`/`count_meta_flagged`/
  `get_meta_summary`, byte-for-byte mirroring `store_lmm`'s DELETE-when-not-applicable behavior.
- `app/backend/methods/metaanalysis.py`: `apply_meta_analysis(conn, paper_id, report)`, mirroring `apply_lmm`.
- `app/backend/api/routers/metaanalysis.py`: `GET /papers/{id}/meta-analysis` now persists as a side effect
  (F4); new `POST /methods/meta-analysis/run`, `GET /methods/meta-analysis/run/{job_id}`,
  `GET /methods/meta-analysis/summary`.
- `app/backend/persistence/paper_query_repo.py`: `SIGNAL_FILTERS["meta-incomplete"]`.
- `app/backend/api/app.py`: `api.state.meta_jobs = JobStore()`.
- Frontend: the same three-file chip wiring (`03_library.jsx`/`40_app.jsx`/`10_pdf_layer.jsx`) + `styles.css`
  (`.meta-chip`, same amber `--flag` semantics as `.lmm-chip`). `08g_methods_metaanalysis.jsx`: new
  `MetaLibrary` (whole-library batch button, mirrors `LmmLibrary`); **F2 fix:** `<MetaCredit/>` moved from
  `MetaSection` into `MetaPaper`'s own render, gated on `d.is_meta_analysis`.

## Key technical detail
None new — this increment intentionally introduced no design deviation from LMM's pattern, confirming the
pattern generalizes cleanly to a second checker before the third (Bayesian, which does need a genuine design
decision — two independent flag sources instead of one).

## Tests
- `tests/test_metaanalysis.py` (+6): the same six cases as LMM (incomplete/complete/not-applicable/idempotency/
  ad-hoc-persists/batch+chip+filter), using the file's own existing `_META_TEXT` (full-completeness) and a
  shorter gate-passing-but-incomplete sample already exercised elsewhere in the file.
- Sibling regression: `test_lmm.py`/`test_statcheck.py`/`test_bayes.py`/`test_retraction.py`/
  `test_frontend_assembly.py` all green (141 passed) — confirms no cross-checker interference.
- A full `pytest -n auto -q` run is deferred to after the third checker (Bayesian) lands, per the Verification
  protocol's "don't run everything for every localized change" guidance — the targeted + sibling-regression
  passes above give the same confidence at a fraction of the cost for a mechanically-repeated pattern.

## Manual verification script
Identical shape to `route_61_methods_lmm.md`'s steps 9-11, now in `.claude/qa-routes/route_62_methods_
metaanalysis.md` (whole-library batch → chip → filter; credit suppression on a non-meta paper; a Critique
candidate seeded purely by an ad-hoc view).

## Gates
- **Security audit:** extended `.claude/security-audits/2026-07-22_cross-method-auditor-consolidation.md` —
  PASS for meta-analysis (same threat shape as LMM, re-verified against this checker's own tests).
- **QA coverage:** `tools/qa/build_surface_map.py check` — API surfaces still 100% covered (added the 3 new
  endpoints to `route_62`'s frontmatter).

## Next
Bayesian is last. Its shape differs: `BayesReport.not_reproduced` (a math-reproduction mismatch, statcheck-like)
and `BayesCompleteness` (a reporting-completeness checklist, LMM/meta-like) are two independent signals from the
SAME auditor — the batch/chip/candidate design needs to decide how they combine into one "worth reviewing"
definition before repeating the pattern a third time.
