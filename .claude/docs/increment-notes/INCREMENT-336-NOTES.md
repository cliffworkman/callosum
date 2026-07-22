# Increment 336 — Backlog #23 (1/3): LMM auditor gets F1 chip + F4 persistence + F2 footer fix

## Context
First of three checkers in the cross-method auditor consolidation (LMM, then meta-analysis, then Bayesian — each
its own commit so the pattern is proven and reviewable before repeating it). Research before building found the
backlog's own framing needed two corrections: F2 ("uniform footer suppression across all four") doesn't apply to
statcheck (no `is_x`-style gate exists there — see the design note below); and "like gap-finder" pointed to a
mismatched pattern (gap-finder's cache is per-axis with no chip; the real precedent for a per-paper chip is
statcheck/retraction's `open_science_signals` table). Presented both findings plus the resulting architecture
fork to Cliff before building: **F1 → full statcheck-style library chip** (not the cheaper per-paper badge);
**F4 → persist on ad-hoc view** (not gated behind a batch run first).

## Implemented
- `app/backend/persistence/signals_repo.py`: `LMM_SIGNAL`/`LMM_SOURCE` + `store_lmm`/`count_lmm_flagged`/
  `get_lmm_summary`, mirroring the statcheck/retraction trio. `store_lmm` DELETEs (not "not-applicable"-flags)
  any prior row when `is_lmm` is False — a non-mixed-model paper isn't a fact worth persisting library-wide.
- `app/backend/methods/lmm.py`: `apply_lmm(conn, paper_id, report)` — one function, callable from both the
  ad-hoc per-paper GET and the new batch job (the `apply_retraction` precedent), so both paths stay in
  lockstep. Writes the signal always; writes a `paper_findings` **candidate** (never a fact — a reporting gap
  is a prompt to look) only when the checklist is incomplete; clears it otherwise.
- `app/backend/api/routers/lmm.py`: `GET /papers/{id}/lmm` now also calls `apply_lmm` via `run_write` as a side
  effect (F4) — viewing a paper's panel is enough to seed the chip/candidate, no batch run required. New
  `POST /methods/lmm/run` (async batch, mirrors `_run_statcheck_all_job`), `GET /methods/lmm/run/{job_id}`,
  `GET /methods/lmm/summary`.
- `app/backend/persistence/paper_query_repo.py`: `SIGNAL_FILTERS["lmm-incomplete"]`.
- `app/backend/api/app.py`: `api.state.lmm_jobs = JobStore()`.
- Frontend: `app/frontend/js/03_library.jsx` (chip state/refresh/filter, mirrors statcheck/retraction),
  `40_app.jsx` (paneCtx wiring for `onShowLmmFlagged`/`onLmmRan`), `10_pdf_layer.jsx` (the `🔗 LMM · N` header
  chip, amber like statcheck — a completeness signal, not a fact), `styles.css` (`.lmm-chip`).
  `08f_methods_lmm.jsx`: new `LmmLibrary` (mirrors `TransparencyLibrary` — the closer precedent, since both are
  Checklists-tab-nested rather than their own top-level section) with a "Whole library" batch button + progress
  + summary + a review link. **F2 fix:** `<LmmCredit/>` moved from `LmmSection` (unconditional) into `LmmPaper`'s
  own render, now gated on `d.is_lmm` — it no longer shows for a non-mixed-model paper or before the audit runs.

## Key technical detail
Two producer constants (in the #9 sense) aren't reused here, but a parallel design question came up: should
`store_lmm` write a `"not-applicable"` row for every non-mixed-model paper (matching transparency's per-check
n/a rows), or write nothing? Chose nothing — transparency's n/a rows exist because ITS gate is per-CHECK within
an always-run report; LMM's gate is over the WHOLE report (`is_lmm`), so writing n/a for the ~95% of a general
library that isn't mixed-model papers would be pure noise with zero filter/count value, and the codebase has no
"papers that don't use an LMM" audience. Chose lean-persistence (only write when actually applicable) over
copying transparency's shape reflexively.

## Principles/A-A gate (rule #9)
The chip/candidate additions are read-derived signals, not new judgments — same PRINCIPLES posture as the
existing checklist. The one live tension: F4's "persist on ad-hoc GET" is an unusual mutation-on-read pattern.
Mitigated by making the write idempotent (OR-REPLACE + content-hash-keyed candidate) and narrowly scoped (only
the two already-audited signal/findings tables, never anything user-authored) — documented explicitly in the
new security-audit doc rather than treated as a routine GET. F2's fix directly serves PRINCIPLES' "every claim
carries its evidence": crediting a method before confirming it even applies to the paper on screen would be
attributing something that didn't happen.

## Tests
- `tests/test_lmm.py` (+8): `apply_lmm` for incomplete/complete/not-applicable/un-gating/idempotency; the ad-hoc
  GET's persistence side effect; the batch endpoint + summary + library filter end-to-end.
- Sibling regression check: `test_statcheck.py`/`test_bayes.py`/`test_metaanalysis.py`/`test_transparency.py`/
  `test_retraction.py` all green (99 passed) — confirms the shared `signals_repo.py` edit (`delete` import) and
  `apply_retraction`-adjacent patterns didn't disturb the other producers.
- `tests/test_frontend_assembly.py`: 46 passed after the new chip/whole-library-button JSX landed.

## Manual verification script
See the extended `.claude/qa-routes/route_61_methods_lmm.md` steps 9-11 (whole-library batch → chip → filter;
credit suppression on a non-LMM paper; a Critique candidate seeded purely by an ad-hoc view).

## Gates
- **Security audit:** new `.claude/security-audits/2026-07-22_cross-method-auditor-consolidation.md` — PASS for
  LMM; the doc stays open to extend for meta-analysis/Bayesian rather than opening 3 near-identical files.
- **QA coverage:** `tools/qa/build_surface_map.py check` — 254/254 API surfaces covered (added the 3 new
  endpoints to `route_61_methods_lmm.md`'s frontmatter); 0 regressions.

## Next
Meta-analysis is next (same pattern, `is_meta_analysis` gate); Bayesian last (a slightly different shape — two
independent flag sources, the BF-reproduction results AND the completeness checklist, need a combined "worth
reviewing" definition). Backlog #23 stays open until all three land.
