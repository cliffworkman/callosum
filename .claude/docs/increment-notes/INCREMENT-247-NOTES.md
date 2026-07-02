# Increment 247 — LMM-reporting completeness auditor (backlog #23)

## Implemented

A METHODS **"Mixed-model reporting"** panel — the statcheck sibling for linear mixed models. It reads a mixed-model
paper's extracted text and flags whether it *reports* seven things a careful reader needs; **it never runs a model, an
imputation, or a sensitivity analysis, and never ingests raw data.** A direct analogue of the Bayesian SP2 completeness
checklist. Scope forks (AskUserQuestion): **all 7 checks** + **"also 'what this means' for present items"** (a grounded
recommendation per fired flag + an always-on literacy explainer).

Files:
- `app/backend/methods/lmm.py` (NEW, pure) — a `_LMM` gate + 7 precondition-scoped checks + `LmmCheck{key,label,
  status,evidence,page,note,explainer,basis}` + `LmmReport{is_lmm,checks}` + `audit_lmm(chunks)`. Regex over the
  paper's chunk text; self-contained `_snippet`/`_first`/`_has` (the bayes.py helpers). No I/O, no LLM.
- `app/backend/api/routers/lmm.py` (NEW) — `GET /papers/{id}/lmm` (sync, read-only; 404 unknown; no chunks →
  `is_lmm:false`). Mirrors `/bayes` / `/statcheck`. Wired in `app.py` (import + `include_router`).
- `app/frontend/js/08f_methods_lmm.jsx` (NEW) — `LmmSection`/`LmmPaper`/`LmmChecklist`/`LmmCredit`
  (`registerPaneSection` order 33, `hideInReadOnly`; auto-runs when its section is open). Per-check rows (status pill
  + note + always-on explainer + in-context basis + evidence snippet → region page-open), the honest-scope caveat, and
  a credit block with a one-click **＋ add methods sources to library** (`LMM_CSL` manifest via `/library/import`).
- `app/frontend/styles.css` (+`.lmm-explainer`/`.lmm-basis`, tokens only; reuses `.bayes-check-*`/`.method-credit`/
  `.statcheck-caveat`).

## The seven checks (each present / not-found / not-applicable)

random-effects structure (Barr 2013; Matuschek 2017) · df/inference method (Luke 2017) · convergence/singular fit
(Bates 2015 lme4) · estimation REML vs ML · **ICC** — n/a unless a clustering/multilevel claim · marginal/conditional
R² (Nakagawa & Schielzeth 2013) · **missing-data sensitivity** — n/a unless longitudinal + evident dropout (FDA ICH
E9(R1); Troendle 2025; Cro 2020; Moreno-Betancur & Chavance 2016).

## Key technical detail

**FLAG-not-ADJUDICATE + precondition-scoped, structurally:** statuses are only `present`/`not-found`/`not-applicable`
— no aggregate, no score, no verdict (a test asserts `not hasattr(rep, "score")`). ICC + missing-data are
`not-applicable` (with the reason) when their precondition fails — a flag that fires on every LMM is the failure mode.
"not found" is worded *"not detected in the extracted text — check the paper"* (never "missing"; silence≠certificate).
**The identity boundary** (reads text, never fits a model) is pinned by `test_no_model_fitting_import` (the module
imports no `lme4`/`mice`/`statsmodels`/`scipy.optimize`/`numpy`).

## Manual verification script

1. `HF_HUB_OFFLINE=1 python .local/visual/drive_inc247_lmm.py` → "PASS": open METHODS → **Mixed-model reporting** on a
   seeded mixed-model paper → a 7-row checklist (Random-effects ✓ present; df method "not found — check the paper";
   ICC + missing-data n/a; the in-context basis + credit); 0 console/page/genai.
2. `python tools/qa/build_surface_map.py check` → API 177/177, FE 796/796, 0 uncovered.
3. Live spot-check (the maintainer's): open a real mixed-model paper → the checklist reflects what it does/doesn't
   report; a present check's evidence opens its page.

## Pytest

924 → **938 passed, 1 skipped** (+14 `tests/test_lmm.py`: the gate off/on; each check present/not-found; ICC +
missing-data precondition scoping [n/a]; "not found ≠ missing" wording; no-verdict/no-score; the identity-boundary
static assert; the endpoint 404 + no-chunks honest-empty). `ruff check` + `ruff format --check` clean; frontend rebuilt
(`test_frontend_assembly` 5/5).

## Gates

- **Security audit** `.claude/security-audits/2026-07-02_lmm-auditor.md` **PASS** (local read-only; no external fetch /
  egress / LLM / migration / dependency; never-runs-a-model boundary structural + test-pinned; flag-not-adjudicate /
  precondition-scoped / not-found-≠-missing uphold the no-accusation boundary).
- **Principles gate (rule #9) — aligned** (PRINCIPLES Example 3 + the Bayesian-SP2 class: a per-paper deterministic
  signal carrying its evidence; #2 signal-not-verdict, #4 evidence-shown, #6 silence-≠-certificate, #7 no-composite;
  the misaligned "reporting-quality score / this paper is inadequate" verdict + running-a-model declined).
- **QA (rule #10)** — new `route_61_methods_lmm.md`; surface 177/177 API + 796/796 FE, 0 uncovered.
- **Experience pass (rule #11)** — a deadline-citer persona agent drove the panel; findings recorded below.
- **Credit-the-lineage** — each check names its source in-context (`basis`) + the panel offers them to the library;
  `THIRD-PARTY-NOTICES.md` credits the manifest.

## No migration, no new dependency, no egress, no LLM.

Notes: spec `.claude/docs/specs/2026-07-02-lmm-auditor-design.md`; plan `.claude/backups/plans/2026-07-02_lmm-auditor.md`.

## Deferred (documented)

- LLM-assisted detection for fuzzier reporting (consent-gated) — SP1 is deterministic-regex only.
- A per-check-precision/recall pass on real mixed-model papers (the maintainer's live spot-check is the first read).
- Any producer-side capability (running models/imputations) — permanently out (the identity boundary).
