# Meta-analysis reporting auditor — design (backlog #36, consumer-side slice; inc 249)

**Status:** approved (maintainer, 2026-07-02). Single-increment. The producer-side **extraction workbench** (the
full future-track `…_metaanalysisextractionworkbench.md`) is the deliberate NEXT increment, not this one.

## One line

A METHODS **"Meta-analysis reporting"** panel — the direct sibling of the statcheck / Bayesian / LMM auditors
(inc 95 / 241–244 / 247) — that reads a **published** meta-analysis's extracted text and flags whether it *reports*
seven key methodological choices, each `present` / `not-found` / `not-applicable`, with the matched evidence opening
its page at region precision, a grounded cited recommendation, an always-on literacy explainer, and the in-context
`basis`. **FLAG-not-ADJUDICATE: it never pools, models, re-computes, scores, ranks, or accuses.**

## Principles gate (rule #9) — aligned

- **Principle(s) + worked example:** PRINCIPLES Example 3 (the per-paper deterministic-signal class) — identical to
  statcheck / Bayesian-SP2 / LMM. Carries every flag's evidence (#4); signal-not-verdict (#2); silence ≠ certificate
  (#6 — "not detected … — check the paper"); no composite (#7 — a factual status tally, not a grade).
- **Misaligned easy path (declined):** a *"meta-analysis quality / reproducibility score / this meta-analysis is
  low-quality"* verdict; or **re-pooling / re-computing** the meta-analysis (crossing the veto line into inferential
  stats — metafor/JASP territory); or any accusation of the authors (A-A veto).
- **Aligned shape:** reads the *reported* text of a published meta-analysis and flags whether it *reports* the key
  choices — never pools, models, re-computes, scores, or accuses. The identity boundary is the load-bearing line and
  is enforced **structurally** (no statistical-computation code path — the module imports no scipy/numpy/statsmodels)
  + **test-pinned** (`test_no_statistical_computation_import`). This is the extraction-workbench doc's veto line
  ("never pools, models heterogeneity, meta-regresses, or does bias inference") applied to the consumer-side slice.

## Architecture (mirrors inc 247's LMM auditor — 3 new files + 1 wire)

### 1. `app/backend/methods/metaanalysis.py` (NEW, pure)

- `@dataclass(frozen=True) class MetaCheck: key, label, status, evidence, page, note, explainer, basis` + `to_dict()`
  (`asdict`) — **identical shape to `LmmCheck`**.
- `@dataclass(frozen=True) class MetaReport: is_meta_analysis: bool, checks: list` + `to_dict()` →
  `{"is_meta_analysis": bool, "checks": [...]}`.
- Self-contained helpers (duplicated from `lmm.py` — the established per-module precedent; `lmm.py` itself duplicated
  `bayes.py`; keeps the module reviewable in isolation, no cross-coupling): `_rx`, `_chunk_rows`, `_snippet`, `_first`,
  `_has`, `_simple`, `_NOT_DETECTED = "not detected in the extracted text — check the paper"`.
- `audit_meta_analysis(chunks) -> MetaReport` — the `_META` gate → 7 checks. Regex over chunk text; **no I/O, no LLM,
  no statistical computation.**

**The `_META` gate** (detectably a meta-analysis, not a paper merely *citing* one): fires iff a meta-analysis WORD
cue and an ANALYTIC cue both appear.
- `_META_WORD = _rx(r"meta[-\s]?analy(s[ie]s|tic|z[e]?d?|s[e]?d?)")`
- `_ANALYTIC = _rx(r"random[-\s]?effects?|fixed[-\s]?effects?|common[-\s]?effect|forest plot|pooled (effect|estimate|"
  r"odds ratio|risk ratio|OR|RR|mean|prevalence|proportion)|funnel plot|I²|I2\b|I-squared|τ²|tau2\b|tau-squared|"
  r"Hedges'?\s?g|DerSimonian|inverse[-\s]?variance|(standardi[sz]ed )?mean difference|\bSMD\b|effect sizes?")`
- Gate: `_has(_META_WORD, rows) and _has(_ANALYTIC, rows)` → else `MetaReport(is_meta_analysis=False, checks=[])`.

**The 7 checks** (order as listed; each via `_simple` unless noted):

1. **effect_size_metric** — `label="Effect-size metric"`, `basis="Borenstein et al. 2009 (Introduction to
   Meta-Analysis); Viechtbauer 2010 (metafor)"`.
   `_EFFECT = _rx(r"Hedges'?\s?g|Cohen'?s?\s?d\b|(log[-\s]?)?(odds ratio|\bOR\b|risk ratio|\bRR\b|relative risk|`
   `hazard ratio|\bHR\b|rate ratio|incidence rate ratio)|Fisher'?s?\s?z|(standardi[sz]ed )?mean difference|\bSMD\b|`
   `\bWMD\b|raw mean difference|correlation coefficient|pooled (prevalence|proportion)|(log )?response ratio")`.
   missing_note: "the effect-size index (e.g. Hedges' g, log odds ratio, Fisher's z) isn't stated — you can't
   interpret the pooled estimate without it". explainer: what an effect-size metric is + why it must be stated.

2. **model** — `label="Model (fixed vs random-effects)"`, `basis="DerSimonian & Laird 1986; IntHout et al. 2014
   (Hartung-Knapp)"`.
   `_MODEL = _rx(r"fixed[-\s]?effects?\s+(model|meta|analysis)|random[-\s]?effects?\s+(model|meta|analysis)|`
   `DerSimonian[-–\s]?Laird|\bREML\b|restricted maximum likelihood|Hartung[-–\s]?Knapp|Sidik[-–\s]?Jonkman|`
   `Paule[-–\s]?Mandel|inverse[-\s]?variance|Mantel[-–\s]?Haenszel|three[-\s]?level meta|multilevel meta|`
   `common[-\s]?effect model|equal[-\s]?effects? model")`.
   missing_note: "fixed- vs random-effects (and the between-study variance estimator, e.g. DerSimonian-Laird or
   REML) isn't stated — it changes the weights, the CI, and what the pooled estimate generalizes to". explainer.

3. **heterogeneity** — `label="Heterogeneity (I² / τ² / Q)"`, `basis="Higgins, Thompson, Deeks & Altman 2003"`.
   `_HETEROGENEITY = _rx(r"I²|I2\b|I-squared|I\^2|τ²|tau2\b|tau-squared|tau\^2|Cochran'?s?\s?Q|Q[-\s]?statistic|`
   `Q\s*=|\bH2\b|H-statistic|between[-\s]?study (variance|heterogeneity)|heterogeneity (statistic|test|was|were|of|"
   `assess)|prediction interval")`.
   missing_note: "heterogeneity (I² / τ² / Cochran's Q) isn't reported — it tells the reader how much the true
   effects vary across studies, which governs how the pooled estimate should be read". explainer.

4. **publication_bias** — `label="Publication-bias assessment"`, `basis="Egger et al. 1997; Duval & Tweedie 2000
   (trim-and-fill); Sterne et al. 2011"`.
   `_PUBBIAS = _rx(r"funnel plot|Egger'?s?|Begg'?s?|trim[-\s]?and[-\s]?fill|PET[-\s]?PEESE|PET-PEESE|`
   `fail[-\s]?safe (N|number)|Rosenthal'?s?|Orwin|p[-\s]?curve|p[-\s]?uniform|selection model|`
   `small[-\s]?study (effect|bias)|publication bias|Duval (and|&) Tweedie")`.
   missing_note: "no publication-bias assessment (funnel plot, Egger's test, trim-and-fill, PET-PEESE …) is reported.
   For k ≥ 10 studies a funnel-based check is commonly recommended (Sterne et al. 2011); with fewer studies these
   tests are underpowered, so absence may be appropriate — check the paper". explainer.

5. **sensitivity** — `label="Sensitivity / influence analysis"`, `basis="Viechtbauer & Cheung 2010"`.
   `_META_SENSITIVITY = _rx(r"leave[-\s]?one[-\s]?out|leave-1-out|influence (diagnostic|analys[ie]s|case)|Baujat|`
   `\boutlier|sensitivity analys[ie]s|robustness (check|analys[ie]s|test)|jackknife|Cook'?s? distance|`
   `studentized residual|\bGOSH\b|subgroup analys[ie]s)`.
   missing_note: "no sensitivity / influence analysis (leave-one-out, outlier/influence diagnostics, robustness to
   an included study) is reported — it shows whether the pooled result hinges on one study or choice". explainer.

6. **study_count** — `label="Number of studies (k) and participants"`, `basis="PRISMA reporting (Page et al. 2021)"`.
   `_STUDYCOUNT = _rx(r"\bk\s*=\s*\d+|\b\d+\s+(included\s+)?(studies|trials|samples|effect sizes|articles|papers|`
   `comparisons|datasets|cohorts)|(number of|total (number of)?)\s+(studies|trials|effect sizes)|`
   `\b\d+\s+(independent\s+)?effect sizes")`.
   missing_note: "the number of studies (k) — and, ideally, the total participants pooled — isn't clearly stated;
   it's the first thing a reader needs to weigh the meta-analysis". explainer. (Conservative: requires an explicit
   count adjacent to a study noun, so a single study's own N doesn't false-fire.)

7. **search_selection** (PRECONDITION-SCOPED) — `label="Search & selection reporting"`, `basis="PRISMA 2020 (Page et
   al. 2021)"`.
   `_SEARCH_STRATEGY = _rx(r"PRISMA|systematic (review|search|literature search)|databases?\s+(searched|were searched"
   r"|search)|\b(PubMed|MEDLINE|Embase|EMBASE|Web of Science|Scopus|PsycINFO|PsycInfo|Cochrane (Library|CENTRAL)|`
   r"CINAHL|Google Scholar)\b|search (strategy|string|terms)|inclusion (and exclusion )?criteria|eligibility "
   r"criteria|PROSPERO|pre[-\s]?regist(ered|ration)|protocol (was )?regist|study selection|title.{0,6}abstract "
   r"screening)")`
   `_MINI_META = _rx(r"(internal|mini|within[-\s]?(study|paper|subject)|single[-\s]?paper) meta[-\s]?analy(s[ie]s|"
   r"tic)|meta[-\s]?analy(s[ie]s|z[e]?d?|s[e]?d?) (of )?(our|the present|the current|these) (\d+ )?(studies|"
   r"experiments|samples)")`
   Status logic: if `_has(_MINI_META, rows) and not _has(_SEARCH_STRATEGY, rows)` → `not-applicable`
   ("a within-study meta-analysis of the paper's own experiments — not a systematic review, so a systematic
   literature search isn't expected"). Else → `_simple(_SEARCH_STRATEGY, …)` (present/not-found).
   missing_note (not-found branch): "the search & selection process (databases searched, inclusion/eligibility
   criteria, PRISMA flow, or a registered protocol) isn't reported — a reader can't judge what was and wasn't
   included". explainer.

Each check's `explainer` is a one-line "what it is / why a reader cares" note; each `note` on a fired flag is a
grounded recommendation ending with `({_NOT_DETECTED})` on the not-found branch, per the LMM pattern. **No score,
no grade, no aggregate; ICC-style precondition scoping only where genuinely conditional (check 7).**

### 2. `app/backend/api/routers/metaanalysis.py` (NEW)

`GET /papers/{paper_id}/meta-analysis` — sync, read-only; mirrors `routers/lmm.py`:
- `MetaCheckOut(BaseModel)` = the 8 fields; `MetaResponse(BaseModel){is_meta_analysis: bool, checks: list[MetaCheckOut]}`.
- handler `paper_meta_analysis(paper_id, conn=Depends(get_connection))`: `get_paper` → **404** on `NoResultFound`;
  `audit_meta_analysis(get_chunks_for_paper(conn, paper_id))`; no chunks → `is_meta_analysis:false` honest-empty.

### 3. `app/backend/api/app.py` (wire)

Import `metaanalysis` (alphabetical, after `lmm`) + `api.include_router(metaanalysis.router)` right after the `lmm`
include (the methods cluster). 3-segment sub-path (`/papers/{id}/meta-analysis`) — no `/papers/{id}` collision.

### 4. `app/frontend/js/08g_methods_metaanalysis.jsx` (NEW panel)

Clone `08f_methods_lmm.jsx`: `META_CSL` credit manifest + `MetaPaper` (self-fetches title + chunk_count; auto-runs
when `ctx.methodsOpen === "meta"`) + `MetaChecklist` (per-check `✓ present` / `not found` / `n/a` pills + note +
explainer + `basis` + evidence page-open at **region** precision + the factual status tally + the honest-scope
caveat) + `MetaCredit` (`＋ add methods sources to library` via `apiPost("/library/import", {content:
JSON.stringify(META_CSL), format: "csl-json"})`). `registerPaneSection({id:"meta", label:"Meta-analysis reporting",
paneId:"methods", order:35, hideInReadOnly:true, render:(ctx)=><MetaSection ctx={ctx}/>})`. **Reuses `.bayes-check-*`
/ `.method-credit` / `.lmm-*`** (the generic method-checklist styling from inc 247 — no new CSS; DESIGN note that
`.lmm-*` are the shared method-checklist recipe).

### 5. `app/frontend/js/09_placeholders.jsx` (remove the stub)

Remove the `id:"meta-analysis"` coming-soon `registerPaneSection` (order 70) — its real feature has landed (the
inc-163 convention; inc 248 already removed the bayesian + lmm stubs). The statcheck "More checks" tab (#27) stays.

## Credit-the-lineage — `META_CSL` manifest

Bundled CSL-JSON (confident DOIs only; omit any unsure — no fabrication). `THIRD-PARTY-NOTICES.md` gains a
"Meta-analysis reporting auditor" lineage block.
- Higgins, Thompson, Deeks & Altman (2003), *Measuring inconsistency in meta-analyses*, BMJ — I². DOI
  10.1136/bmj.327.7414.557.
- Egger, Davey Smith, Schneider & Minder (1997), *Bias in meta-analysis detected by a simple, graphical test*, BMJ.
  DOI 10.1136/bmj.315.7109.629.
- Duval & Tweedie (2000), *Trim and fill*, Biometrics. DOI 10.1111/j.0006-341X.2000.00455.x.
- Sterne et al. (2011), *Recommendations for examining and interpreting funnel plot asymmetry*, BMJ. DOI
  10.1136/bmj.d4002.
- DerSimonian & Laird (1986), *Meta-analysis in clinical trials*, Controlled Clinical Trials. DOI
  10.1016/0197-2456(86)90046-2.
- IntHout, Ioannidis & Borm (2014), *The Hartung-Knapp-Sidik-Jonkman method*, BMC Med Res Methodol. DOI
  10.1186/1471-2288-14-25.
- Viechtbauer (2010), *Conducting meta-analyses in R with the metafor package*, J Stat Softw. DOI 10.18637/jss.v036.i03.
- Viechtbauer & Cheung (2010), *Outlier and influence diagnostics for meta-analysis*, Res Synth Methods. DOI
  10.1002/jrsm.11.
- Page et al. (2021), *The PRISMA 2020 statement*, BMJ. DOI 10.1136/bmj.n71.
- Borenstein, Hedges, Higgins & Rothstein (2009), *Introduction to Meta-Analysis*, Wiley — book, NO DOI (omit to be
  safe; carried as title+authors+year+publisher; the import dedups on title+year+author).

## Honesty controls (structural + test-pinned)

- **FLAG-not-ADJUDICATE:** statuses are only `present` / `not-found` / `not-applicable`; no `score`/`grade`/rank field
  (a test asserts absence). The panel tally is a factual status count, explicitly "not a score".
- **Precondition-scoped:** check 7 → `n/a` for a within-study mini-meta (a flag on every meta-analysis is the failure
  mode). The other six are always-expected for a meta-analysis (publication-bias's k<10 caveat lives in its note, not
  a suppression — silence≠certificate).
- **"not found" wording:** always "not detected in the extracted text — check the paper", never "missing".
- **Identity boundary (the load-bearing line):** it reads reported text and **NEVER pools, models heterogeneity,
  meta-regresses, computes an effect size, or does bias inference** — there is no statistical-computation code path.
  Pinned by `test_no_statistical_computation_import` (the module source imports none of `numpy`, `scipy`,
  `statsmodels`, `sklearn`, `pandas`).
- **Never an accusation** of the authors (A-A veto): "not found" ≠ "the meta-analysis is flawed"; a fired flag is a
  reader's prompt with a cited recommendation.

## Gates

- **Security audit** `.claude/security-audits/2026-07-02_metaanalysis-auditor.md` (light — local read-only over the
  paper-in-hand; no external fetch / egress / LLM / migration / dependency; the never-computes-statistics boundary is
  structural + test-pinned; flag-not-adjudicate / precondition-scoped / not-found-≠-missing uphold no-accusation).
  End PASS.
- **QA (rule #10):** new `route_62_methods_metaanalysis.md` (`api: /papers/{paper_id}/meta-analysis`, `fe:
  08g_methods_metaanalysis.jsx`) + the honesty assertions. Keep `build_surface_map.py check` at 0-uncovered.
- **Experience pass (rule #11):** dispatch a persona-grounded agent (deadline-citer / skeptical-synthesizer vetting a
  published meta-analysis before relying on it) after the build; fix-cheap in-increment, else backlog.
- **Rule #1:** all new files well under 600. **No migration, no new dependency, no egress, no LLM.**

## Tests / acceptance criteria (`tests/test_metaanalysis.py`, ~14, hermetic)

A `_Chunk` fake (text + page_start) like `test_lmm.py`; no network/model.
- Gate OFF: a non-meta paper (e.g. a primary RCT that merely mentions "a recent meta-analysis") → `is_meta_analysis:
  false`, no checks. Gate ON: a real meta-analysis paper → checks present.
- Each check present / not-found (effect-size metric, model, heterogeneity, publication bias, sensitivity, study
  count, search).
- **search_selection precondition scoping:** a within-study "mini meta-analysis" with no systematic search → search
  check `n/a`; a systematic-review meta-analysis with no search reporting → `not-found`.
- "not found" says "check the paper", never "missing".
- No `score`/`grade`/verdict field anywhere in the report (`test_no_verdict_no_score`).
- **Identity boundary:** `test_no_statistical_computation_import` — the module source contains no
  `import numpy|scipy|statsmodels|sklearn|pandas`.
- Endpoint: `GET /papers/{id}/meta-analysis` → 404 unknown; a paper with no chunks → 200 `is_meta_analysis:false`.

## Verification

- pytest full suite green (~952 = 938 + ~14); `ruff check` + `ruff format --check`; frontend rebuilt
  (`test_frontend_assembly` 5/5); QA `check` 0-uncovered; headed `.local/visual/drive_inc249_metaanalysis.py` (seed a
  meta-analysis paper → open METHODS → Meta-analysis reporting → the section auto-runs → a 7-row checklist with a
  present row, a not-found row [with "check the paper"], and an n/a row [search, for a seeded mini-meta variant]; the
  in-context basis + credit ＋add; the tally; 0 console/page/genai). **The live spot-check on a real published
  meta-analysis is the maintainer's** (regex precision/recall on real papers is the first live read).
- Docs: `INCREMENT-249-NOTES.md`; `changes.md` (+ `HELP-DOCS-SYNCED` → 249 — help corpus gains an "Auditing
  meta-analysis reporting" section); CLAUDE footer + decision-log + count (938→~952) + directory-layout (methods/
  metaanalysis.py + routers/metaanalysis.py + 08g); `THIRD-PARTY-NOTICES.md`. Backlog: mark the consumer-side slice of
  #36 shipped; the extraction workbench is the next increment.

## Deferred (out of this increment)

- The producer-side **extraction workbench** (the full future-track: protocol → screening → LLM-drafted
  provenance-anchored human-verified extraction → effect-size conversion → export) — the NEXT increment, its own
  workspace + spec.
- On-paper discoverability chip ("reports a meta-analysis · report card →", the statcheck-inc-141 pattern) +
  persisting the audit as a findings candidate (inc 130) — the same F1/F4 deferrals the LMM auditor filed; likely
  surfaced again by the experience pass.
- LLM-assisted detection for fuzzier reporting; a per-check precision/recall pass on real meta-analyses.
