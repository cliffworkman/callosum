# Increment 249 — Meta-analysis reporting auditor (backlog #36, consumer-side slice)

## Implemented

A METHODS **"Meta-analysis reporting"** panel — the direct sibling of the statcheck / Bayesian / LMM auditors — that
reads a *published* meta-analysis's extracted text and flags whether it **reports** 7 key methodological choices, each
`present` / `not-found` / `not-applicable`. **FLAG-not-ADJUDICATE: it never pools, models, re-computes, scores, ranks,
or accuses.** Fully local — no AI, no egress, no migration, no new dependency.

- **`app/backend/methods/metaanalysis.py`** (NEW pure) — a `_META` gate (a meta-analysis WORD cue + an ANALYTIC cue,
  so a paper merely *citing* a meta-analysis doesn't trip) + 7 checks + `MetaCheck`/`MetaReport` + `audit_meta_analysis`.
  Self-contained regex helpers (`_rx`/`_chunk_rows`/`_snippet`/`_first`/`_has`/`_simple`, duplicated from `lmm.py` —
  the established per-module precedent). No I/O, no LLM, no statistical computation.
- **`app/backend/api/routers/metaanalysis.py`** (NEW) — `GET /papers/{paper_id}/meta-analysis` (sync, read-only;
  mirrors `/lmm`/`/bayes`; 404 unknown; no chunks → `is_meta_analysis:false` honest-empty). Wired in `app.py`
  (import after `lmm`, `include_router` after the lmm include).
- **`app/frontend/js/08g_methods_metaanalysis.jsx`** (NEW) — `MetaSection`/`MetaPaper`/`MetaChecklist`/`MetaCredit`;
  `registerPaneSection` id `"meta"`, order **35** (among the real stat auditors, after where-to-submit, before Review),
  `hideInReadOnly`; auto-runs when its section is open (the statcheck pattern). Reuses `.bayes-check-*` /
  `.method-credit` / `.lmm-*` — **no new CSS**.
- **`app/frontend/js/09_placeholders.jsx`** — removed the `id:"meta-analysis"` coming-soon stub (its real feature has
  landed — the inc-163 convention).

**The 7 checks:** (1) effect-size metric; (2) model (fixed vs random-effects + estimator); (3) heterogeneity
(I²/τ²/Q); (4) publication-bias assessment (note mentions the k≥10 convention — Sterne 2011); (5) sensitivity /
influence; (6) number of studies (k) + participants; (7) search & selection reporting — **precondition-scoped** to
`n/a` for a within-study "mini meta-analysis" that isn't a systematic review.

## Key technical detail

- **The identity boundary (load-bearing):** it reads reported text and **NEVER pools, models heterogeneity,
  meta-regresses, computes an effect size, or does bias inference** — metafor/JASP/RevMan territory. Enforced
  **structurally** (no statistical-computation code path — no numeric aggregation of study data) + **test-pinned**
  (`test_no_statistical_computation_import`: the module imports none of numpy/scipy/statsmodels/sklearn/pandas).
- **Precondition-scoping — the mini-meta rule:** check 7 is `n/a` iff `_MINI_META` matches (a within-study
  meta-analysis of the paper's own experiments) AND no `_SEARCH_STRATEGY` vocab appears — so a systematic review that
  merely omits its search reporting is `not-found`, not `n/a`, while a "mini meta-analysis" (no systematic search) is
  correctly `n/a`. A flag that fires on every meta-analysis is the failure mode.
- **FLAG-not-ADJUDICATE:** statuses are only `present`/`not-found`/`not-applicable`; no `score`/`grade` field (test);
  the panel tally is a factual status count, explicitly "not a score"; "not found" = "not detected in the extracted
  text — check the paper", never "missing" (silence≠certificate); never an accusation (A-A veto).

## Manual verification script

`HF_HUB_OFFLINE=1 python .local/visual/drive_inc249_metaanalysis.py` → "PASS":
- Seeds a within-study **mini meta-analysis** (Hedges' g / random-effects / I² / a study count reported; no publication
  bias / no sensitivity analysis; no systematic search). Open METHODS → **Meta-analysis reporting** → the section
  auto-runs → a **7-row checklist**: **Effect-size metric ✓ present** (basis Borenstein), **Publication-bias
  assessment "not found"** (note has the k≥10 caveat + "check the paper", no "missing"), **Search & selection "n/a"**
  (mini-meta). The tally line reads "4 reported · 2 not detected · 1 not applicable · 7 checks"; a present row's
  evidence opens its page; the credit ＋add button renders. **0 console/page errors, 0 genai-host requests.**

## Gates

- **Security audit** `.claude/security-audits/2026-07-02_metaanalysis-auditor.md` **PASS** (local read-only over the
  paper in hand; no external fetch/egress/LLM/migration/dependency; never-computes-statistics structural + test-pinned;
  flag-not-adjudicate / precondition-scoped / not-found-≠-missing uphold no-accusation).
- **Principles gate (rule #9) — aligned** (PRINCIPLES Example 3 / the statcheck-LMM class; the misaligned "meta-analysis
  quality/reproducibility score / this analysis is low-quality" verdict + re-pooling/re-computing declined).
- **QA (rule #10):** new `route_62_methods_metaanalysis.md` (`api: /papers/{paper_id}/meta-analysis` +
  `fe: 08g_methods_metaanalysis.jsx`) + the honesty assertions; surface **178/178 API + 802/802 FE, 0 uncovered**.
- **Experience pass (rule #11, deadline-citer persona agent):** the panel serves the citer (the tally [F2] +
  n/a de-emphasis [F3] from the LMM pass are baked in). Findings filed per the agent's report.
- **Rule #1:** all new files well under cap (`methods/metaanalysis.py` ~290, `routers/metaanalysis.py` ~65,
  `08g_methods_metaanalysis.jsx` ~250). No migration, no new dependency, no egress, no LLM.

## Pytest

**950 passed, 1 skipped** (+12 hermetic `tests/test_metaanalysis.py`: gate off [non-meta / cite-only] / on;
each check present / not-found; publication-bias k≥10 caveat; search precondition scoping [mini-meta → n/a;
systematic-but-unreported → not-found]; not-found-≠-missing wording; no-verdict/no-score; the identity-boundary static
import assert; the endpoint 404 + no-chunks honest-empty). `ruff check` + `ruff format --check` clean; frontend rebuilt
(`test_frontend_assembly` 5/5).

## Notes

`THIRD-PARTY-NOTICES.md` credits the 10-source manifest; help corpus gained "Auditing meta-analysis reporting"
(`HELP-DOCS-SYNCED` → 249). **The live spot-check on a real published meta-analysis is the maintainer's** (the
math-free regex detection + contracts + a seeded round-trip are proven; per-check precision/recall on real papers is
the first live read). **NEXT — the producer-side extraction workbench** (the full #36 future-track: protocol →
screening → LLM-drafted provenance-anchored human-verified extraction → effect-size conversion → export to metafor/
JASP) is the deliberate next increment (its own workspace + spec + heavy Principles/A-A pass).
