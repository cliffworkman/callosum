# LMM-reporting completeness auditor — design (backlog #23, inc 247)

**Status:** approved (maintainer, 2026-07-02). Scope forks (AskUserQuestion): **all 7 checks** + **"also 'what this
means' for present items"** (a grounded recommendation per fired flag *plus* an always-on literacy explainer).

## One line

A METHODS panel that reads a mixed-model paper's **reported** methods/results and flags — with inspectable evidence
and grounded, cited recommendations, **never verdicts** — whether it reports the seven things a careful reader needs
to evaluate it. It reads reported text only; **it never runs a model, an imputation, or a sensitivity analysis, and
never ingests raw data.** Structurally a twin of the Bayesian SP2 completeness checklist (inc 242).

## Principles alignment gate (rule #9) — run, clears

- **Principles touched:** #2 signal-not-verdict · #4 deterministic substrate · #6 silence-is-not-a-certificate ·
  #7 no-opaque-score · #8 inspectability; the APPROACH-AVOIDANCE **no-accusation** veto.
- **Worked example:** PRINCIPLES Example 3 (a per-paper deterministic signal carrying its evidence) — and its built
  sibling, the Bayesian SP2 completeness checklist (`methods/bayes.py::audit_completeness`, inc 242), which this
  mirrors.
- **Misaligned easy path (declined on purpose):** an "LMM reporting-quality **score**" or a pass/fail "this paper's
  mixed-model reporting is inadequate" **verdict** (a composite masquerading as judgment — #7/#2); a flag that
  **fires on every LMM** (noise, and the inverse of silence≠certificate); or **running the model / ingesting raw
  data** (crossing the identity boundary — Callosum would become a stats environment wrapping lme4/mice).
- **Aligned design (= the future-track doc):** FLAG-not-ADJUDICATE presence/absence checks, **each
  precondition-scoped**, each carrying its inspectable evidence + a grounded, cited recommendation; "not found"
  worded *"not detected in the extracted text — check the paper"* (never "missing"); **no composite/score**; reads
  reported text only. The future-track doc (`opus4.8_future-tracks_lmmreportingauditor.md`) is the gate output.

## Architecture — deterministic, local, no LLM/egress, no migration

Three new files + one-line app wiring; ephemeral (like statcheck/GRIM/p-curve/bayes — no persistence).

### 1. `app/backend/methods/lmm.py` (pure, no I/O, no LLM)

- **The gate** `_LMM` — a paper is "detectably a mixed-model paper" if the extracted text matches any of: `linear
  mixed(-|\s)?(effects?)? model`, `mixed(-|\s)?effects? (model|regression)`, `multilevel model`, `hierarchical
  linear model` / `\bHLM\b`, `lmer\s*\(`, `\blme4\b`, `\bnlme\b`, `\bglmer\s*\(` (generalized — still a mixed
  model), `MixedLM` (statsmodels), or `random(-|\s)?(intercepts?|slopes?|effects?)` co-occurring with `model`. If no
  match → `LmmReport(is_lmm=False, checks=[])` (a non-LMM paper cannot "fail" a checklist it isn't subject to).
- **Text helpers (self-contained, mirroring bayes.py per the per-module convention):** `_chunk_rows(chunks) →
  [(text, page)]`, `_snippet(text, start, end, pad=60)`, `_first(pattern, rows) → (snippet, page) | None`,
  `_has(pattern, rows) → bool`.
- **Contract:**
  ```
  @dataclass(frozen=True)
  class LmmCheck:
      key: str          # random_effects | df_method | convergence | estimation | icc | r2 | missing_data
      label: str
      status: str       # present | not-found | not-applicable
      evidence: str | None   # the matched snippet (present → what was found)
      page: int | None
      note: str | None       # status-specific: the grounded recommendation when not-found; a short confirmation when present
      explainer: str         # always-on "what this is / why it matters" literacy note
      basis: str             # the cited methodological source (in-context attribution)
  @dataclass(frozen=True)
  class LmmReport:
      is_lmm: bool
      checks: list  # list[LmmCheck]
  def audit_lmm(chunks) -> LmmReport: ...
  ```
  `to_dict()` on both (the endpoint returns `report.to_dict()`).

### 2. `app/backend/api/routers/lmm.py` (NEW — `methods.py` is 583/600)

`GET /papers/{paper_id}/lmm` — sync, read-only; reuses `get_paper` (404 unknown) + `get_chunks_for_paper`; no chunks
→ `is_lmm:false` honest-empty. Mirrors `/papers/{id}/bayes` / `/papers/{id}/statcheck`. Wired in `app.py`
(`include_router(lmm.router)`; a sub-path GET, so include order is irrelevant — no `/papers/{id}` collision).

### 3. `app/frontend/js/08f_methods_lmm.jsx`

`registerPaneSection({id:"lmm", label:"Mixed-model reporting", paneId:"methods", order:33, hideInReadOnly:true})` —
between Bayesian (32) and Where-to-submit (34). Auto-runs when its section is the open one (the statcheck/bayes
pattern; self-fetches `GET /papers/{id}/lmm` for the selected paper). Renders:
- an intro + the **honest-scope caveat** ("audits reporting *completeness*, not analysis *correctness* — a paper can
  report everything and still model badly, or omit an item and be fine; this flags what a careful reader should
  check, not what's wrong");
- per-check rows: label + a status pill (`present` ✓ / `not-found` / `not-applicable` n/a) + the **evidence snippet**
  (present → opens its page at **region precision**, the page-open, never a fabricated exact rect) + the `note`
  (grounded recommendation when not-found) + the always-on `explainer` + the in-context `basis` citation;
- not-applicable rows shown muted (with why the precondition didn't hold);
- a **credit block** (the lineage manifest) with a one-click **＋ add methods sources to library** (inc-93
  `/library/import`, CSL-JSON) — the credit-the-lineage requirement.
- `.lmm-*` CSS (tokens only; mirrors `.bayes-check-*`). Read DESIGN.md before writing.

## The seven checks

Each fires only when its precondition holds; the two conditional checks (ICC, missing-data) report `not-applicable`
(with the reason) when theirs doesn't — a flag that fires on every LMM is the failure mode.

1. **Random-effects structure** — precondition: always. `present` if the text specifies the structure: lme4/nlme
   formula syntax `\(\s*[^)]*\|\s*[^)]+\)` (e.g. `(1 | subject)`, `(condition | item)`), or "random
   intercept(s)/slope(s)", "random effect(s) of/for", "by-(subject|item|participant) random". `not-found` else.
   Basis: **Barr et al. 2013** (keep-it-maximal) + **Matuschek et al. 2017** (Type-I/power balance). Note (not-found):
   "the random-effects structure (which grouping factors carry random intercepts/slopes) isn't stated — a reader
   needs it to evaluate the model; the field debates maximal vs parsimonious, so the *choice* matters." Explainer:
   what random intercepts/slopes are + the maximal-vs-parsimonious debate. **Flag absence; never adjudicate the
   choice.**
2. **df / inference method** — precondition: always. `present` if any of: Satterthwaite, Kenward[-–\s]Roger,
   `lmerTest`, `pbkrtest`, "likelihood[-\s]ratio test" / `\bLRT\b`, "asymptotic", "Wald", "degrees of freedom" near a
   test statistic. Basis: **Luke 2017**. Note: "the df/inference method (Satterthwaite / Kenward-Roger / Wald / LRT)
   isn't reported — it materially changes the p-values."
3. **Convergence / singular fit** — precondition: always. `present` if: "converge(d|nce)", "singular", "isSingular",
   "boundary \(singular\) fit", "failed to converge", "did not converge". Basis: **Bates et al. 2015 (lme4)**. Note:
   "whether the model converged / the fit was singular isn't mentioned."
4. **Estimation method** — precondition: always. `present` if: REML / "restricted maximum likelihood" / "maximum
   likelihood" / "ML estimation" (require the phrase, not a bare "ML"). Basis: **Bates et al. 2015 (lme4)**. Note:
   "REML vs ML isn't stated — it matters for likelihood-ratio tests on fixed effects."
5. **ICC** — precondition: **a clustering/multilevel claim** ("multilevel", "nested", "clustered", "hierarchical",
   "level[-\s]?[12]", "within (schools|clusters|groups|clinics)"). If the precondition doesn't hold →
   `not-applicable` (a single-grouping repeated-measures LMM needn't report an ICC). If it holds: `present` if "ICC"
   / "intraclass correlation", else `not-found`. Basis: multilevel-modelling literature. Note.
6. **Marginal vs conditional R²** — precondition: always. `present` if: "marginal R²" / "conditional R²" / `R2m` /
   `R2c` / "Nakagawa" / "variance explained" (with an R² nearby). Basis: **Nakagawa & Schielzeth 2013**. Note: "the
   variance explained (marginal vs conditional R²) isn't reported."
7. **Missing-data sensitivity (the Troendle-grounded flag)** — precondition: **longitudinal/repeated-measures design
   AND evident dropout/missingness**. Longitudinal cues: "longitudinal", "repeated measures", "over time", "waves",
   "time points", "follow[-\s]?up", "visits", "baseline and". Dropout/missing cues: "dropout", "attrition", "missing
   data", "lost to follow[-\s]?up", "withdrew", "incomplete cases". BOTH must hold → else `not-applicable`. If it
   holds: `present` if a sensitivity analysis is reported ("sensitivity analysis" (near "missing"), "multiple
   imputation" / `\bMI\b`, "pattern[-\s]mixture", "reference[-\s]based", "tipping[-\s]point", "controlled
   imputation", "delta[-\s]adjusted", "\bMNAR\b", "jump to reference"), else `not-found`. Basis: **FDA ICH E9(R1)** +
   **Troendle et al. 2025**, **Cro et al. 2020**, **Moreno-Betancur & Chavance 2016**. Note (regulatory
   recommendation, not accusation): "a longitudinal LMM with dropout, but no missing-data sensitivity analysis
   detected — FDA ICH E9(R1) recommends assessing robustness to the missing-at-random assumption (controlled/delta
   imputation, pattern-mixture, reference-based, tipping-point). Not a claim the analysis is wrong."

## Credit-the-lineage (in-context attribution + one-click add)

Each check names its methodological source **in-context** (the `basis` field, shown on the row). A **credit block**
at the panel foot offers the whole lineage manifest to the library in one click (inc-93 `POST /library/import`,
CSL-JSON — the Bayesian-credit pattern). Manifest (CSL-JSON built in the panel; **omit any DOI not confidently
known — a missing DOI over a wrong one**; the import dedups on title+year+author when DOI is absent):

- Barr, Levy, Scheepers & Tily (2013), *Keep it maximal*, J. Memory & Language 68(3):255–278 — DOI
  10.1016/j.jml.2012.11.001
- Matuschek, Kliegl, Vasishth, Baayen & Bates (2017), *Balancing Type I error and power in LMMs*, J. Memory &
  Language 94:305–315 — DOI 10.1016/j.jml.2017.01.001
- Luke (2017), *Evaluating significance in linear mixed-effects models in R*, Behavior Research Methods
  49(4):1494–1502 — DOI 10.3758/s13428-016-0809-y
- Bates, Mächler, Bolker & Walker (2015), *Fitting Linear Mixed-Effects Models Using lme4*, J. Statistical Software
  67(1):1–48 — DOI 10.18637/jss.v067.i01
- Nakagawa & Schielzeth (2013), *A general and simple method for obtaining R² from GLMMs*, Methods in Ecology &
  Evolution 4(2):133–142 — DOI 10.1111/j.2041-210x.2012.00261.x
- FDA / ICH **E9(R1)** addendum, *Estimands and Sensitivity Analysis in Clinical Trials* (2019/2021) — a guideline
  (no journal DOI; title + issuer).
- Troendle et al. (2025), *(missing-data sensitivity analysis for longitudinal LMMs)* — the future-track doc notes
  OA/public-domain; include title + authors + year, **DOI only if confidently known at build time, else omitted**.
- Cro, Morris, Kenward & Carpenter (2020), *Sensitivity analysis for clinical trials with missing continuous outcome
  data using controlled multiple imputation*, Statistics in Medicine — DOI included only if confidently confirmed at
  build time, else omitted.
- Moreno-Betancur & Chavance (2016), *Sensitivity analysis of incomplete longitudinal data via pattern-mixture
  models*, Statistical Methods in Medical Research 25(4):1471–1489 — DOI included only if confidently confirmed.

(Any entry whose exact DOI can't be confirmed at build time ships with title+authors+year+container and no DOI — never
a fabricated identifier. This is the same no-fabrication discipline as the Bayesian ANOVA decline + the agent-write
DOI-verify.)

## Honesty controls (structural + test-pinned)

- **FLAG-not-ADJUDICATE:** statuses are `present`/`not-found`/`not-applicable` — never pass/fail; **no aggregate,
  count-summary-as-grade, or score**.
- **Precondition scoping:** ICC + missing-data are `not-applicable` (with the reason) when their precondition fails.
- **"not found" ≠ "missing":** worded "not detected in the extracted text — check the paper" (tables aren't fully
  parsed; silence≠certificate both ways, #6).
- **Inspectable evidence:** a present check shows the passage it found (region-precision page-open); the reader
  verifies. No fabricated exact rect (#2/coordinate honesty).
- **Grounded, cited recommendation** on a fired flag + the in-context `basis`; **never** an assertion the analysis is
  wrong (A-A no-accusation).
- **Reads reported text only; never runs a model / imputation / sensitivity analysis; never ingests raw data.** There
  is no code path that does — asserted structurally by test (the module imports no modelling/stats-fitting library;
  its only input is the paper's extracted chunk text).

## Files & rule-#1

- NEW `app/backend/methods/lmm.py` (~well under 600), `app/backend/api/routers/lmm.py` (~120),
  `app/frontend/js/08f_methods_lmm.jsx` (~180); + `app.py` (one import + one `include_router`) + `styles.css`
  (`.lmm-*`). No existing file pushed over (the endpoint's own router avoids growing `methods.py` at 583/600).
- **No migration, no new dependency, no egress, no LLM.**

## Testing (hermetic — no network/model; the test_bayes.py pattern), `tests/test_lmm.py`

- The gate: a non-LMM paper → `is_lmm:false`, empty checks.
- Each check `present` from fake chunks that report it; `not-found` from chunks that don't.
- **Precondition scoping:** missing-data → `not-applicable` on a non-longitudinal LMM; ICC → `not-applicable` absent a
  clustering claim; both → the proper `present`/`not-found` when their precondition holds.
- "not-found" wording contains "check the paper" (not "missing").
- A present check carries an evidence snippet + page.
- The endpoint: 404 unknown paper; no-chunks → `is_lmm:false`; a seeded LMM paper → the checklist.
- The identity boundary: `methods/lmm.py` imports no model-fitting library (a static assertion — no `lme4`/`mice`/
  `statsmodels`/`scipy.optimize`-style fitting; the module's surface is regex over text).

## Gates

- **Security audit** `.claude/security-audits/2026-07-02_lmm-auditor.md` — light (reads the paper-in-hand via the
  audited repo; no new external fetch / data path / egress / LLM / migration / dependency; the never-runs-a-model
  boundary is structural). End PASS.
- **QA (rule #10):** new `route_61_methods_lmm.md` (the `GET /papers/{id}/lmm` endpoint + `fe: 08f_methods_lmm.jsx`;
  the flag-not-verdict / precondition-scoping / no-composite / evidence-shown assertions). Keep `check` 0-uncovered.
- **help corpus:** an "Auditing mixed-model reporting" section (move `HELP-DOCS-SYNCED` forward).
- **THIRD-PARTY-NOTICES.md:** credit the methods lineage (the manifest above).
- **Experience pass (rule #11):** a "deadline citer vetting a mixed-model paper" persona check after the build; fix
  cheap findings in-increment, else backlog.

## Acceptance criteria (from the future-track doc)

- The tool **never** ingests raw data or runs a model/imputation/sensitivity analysis (asserted by test).
- Each check fires **only when its precondition holds** (missing-data not on a non-longitudinal LMM; ICC not absent a
  clustering claim).
- Every flag shows **inspectable evidence** + a **grounded, cited recommendation**; none is a pass/fail verdict; no
  composite score.
- Each check **credits its lineage** in-context and the panel offers the source papers to the library (one-click).
- The honest-scope caveat ("reporting completeness, not analysis correctness") is shown.

## Deferred (documented, not this increment)

- LLM-assisted detection for fuzzier reporting (consent-gated) — SP1 is deterministic-regex only.
- Richer interpretation scaffolding beyond the per-check explainer.
- Any producer-side capability (running models / imputations) — **permanently out** (the identity boundary).
