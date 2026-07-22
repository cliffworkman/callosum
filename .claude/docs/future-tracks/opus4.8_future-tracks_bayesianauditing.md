# Auditing and Interpreting Bayesian Statistics in Published Research: A Conceptual Map for the Skeptical Non-Expert (and a Design Brief for "Callosum")

## TL;DR
- **Only a narrow slice of a reported Bayesian analysis is deterministically recomputable from text/tables with no raw data** — essentially default ("JZS"/Cauchy) Bayes factors for canonical t-test/ANOVA/correlation/regression designs, recoverable from t/F/r and N via the BayesFactor package's closed-form/quadrature methods (the genuine statcheck-analogue). Most of the terrain is either a **completeness/coherence audit** (did they report the prior, convergence diagnostics, a sensitivity analysis?) or **irreducibly expert judgment** (is this prior defensible? is this model adequate?). For Callosum, that maps cleanly to FLAG-not-ADJUDICATE.
- **The single most useful thing such a tool can do is surface what is *missing or internally inconsistent*, not what is *right or wrong*.** Reporting guidelines already exist (Kruschke's BARG, the Depaoli–van de Schoot WAMBS checklist, the van Doorn et al. JASP guidelines) and define the completeness checklist; computational diagnostics (R-hat, ESS, divergences, Pareto-k) have published thresholds whose *absence* is itself a flag. No automated "Bayesian statcheck" currently exists.
- **The central design risk for a user-facing aid is teaching NHST readers to hunt for a pass/fail verdict** — the exact binary habit Bayesian reasoning should break. The literature documents that 89.2% (Tendeiro et al. 2024, N=167) to 92% (Wong et al. 2022, N=73) of applied papers using Bayes factors contain at least one questionable reporting/interpreting practice, the most common being treating the BF as posterior odds and as absolute (rather than relative, model-comparative) evidence. A good tool builds familiar rungs (BF↔p, credible↔confidence interval) while explicitly flagging where those intuitions mislead.

---

## Key Findings

**1. The checkability tiering is the whole ballgame.** Every auditable element of a Bayesian report falls into one of three tiers, and which tier it is determines what Callosum can build under a verify-everything constraint:
- **Tier 1 — Deterministic/recomputable** from reported summary statistics with no raw data. Narrow but real: default Bayes factors for canonical designs; arithmetic relationships (e.g., BF₁₀ = 1/BF₀₁; posterior odds = BF × prior odds); whether a reported HDI is internally consistent with a reported point estimate.
- **Tier 2 — Completeness/coherence-auditable**: presence/absence of required elements (prior specification, convergence diagnostics, sensitivity analysis, model description), and coherence between claims and reported numbers (e.g., "strong evidence" asserted next to a BF of 2; "the chains converged" with no R-hat reported; a credible interval excluding a value the text says is supported).
- **Tier 3 — Expert-judgment-only**: is the prior substantively defensible? is the likelihood/model adequate? is the ROPE scientifically meaningful? is the BF's prior-sensitivity fatal here? AI can advisory-annotate but never adjudicate.

**2. Existing standards converge on a completeness checklist.** BARG (Kruschke 2021, *Nature Human Behaviour*), WAMBS (Depaoli & van de Schoot 2017, *Psychological Methods*; 10-point checklist), and the JASP guidelines (van Doorn et al. 2021, *Psychonomic Bulletin & Review*) collectively specify: justify and report the prior; report the software and computation method; report MCMC convergence (R-hat) and effective sample size; conduct and report a prior sensitivity/robustness analysis; report posterior summaries with interval type; and make code/data available. The empirical motivation for these guidelines is stark. Kruschke's BARG cites a ROBUST-checklist review of Bayesian medical-device articles in which "only 24% of 17 articles fully reported the prior, only 18% reported a sensitivity analysis, only 35% explained the model, and only 59% reported credible intervals," and a review of 70 Bayesian epidemiology articles in which "33 did not specify what prior was used, and 66 did not report a sensitivity analysis." Depaoli & van de Schoot (2017) found that "31.1% of the articles did not even discuss the priors implemented." These omissions are exactly the Tier-2 flags.

**3. Bayes factors are the most checkable and the most misused element.** The default Bayesian t-test (Rouder, Speckman, Sun, Morey & Iverson 2009) places a Cauchy prior with scale r = √2/2 ≈ 0.707 on effect size δ (the "JZS" prior), and yields a closed-form/quadrature BF computable from t and N alone — this is the Tier-1 core. But Bayes factors are sensitive to prior width (the Jeffreys–Lindley and Bartlett's paradoxes: arbitrarily wide priors drive the BF toward the null), and the conventional Jeffreys/Lee–Wagenmakers verbal labels ("anecdotal/moderate/strong") smuggle in exactly the binary cutoffs Bayesian inference is meant to avoid. Empirically, Tendeiro, Kiers, Hoekstra, Wong & Morey (2024, N=167) found "149 articles (89.2%) displayed at least one QRIP, and 104 articles (62.3%) displayed at least two QRIPs," while Wong, Kiers & Tendeiro (2022, N=73) found "92% of articles demonstrating at least one misconception of Bayes Factors."

**4. Computational diagnostics have published numeric thresholds, so their absence or violation is a clean flag.** Modern practice (Vehtari, Gelman, Simpson, Carpenter & Bürkner 2021, *Bayesian Analysis*) uses rank-normalized split-R̂ < 1.01, bulk-ESS and tail-ESS > 400, plus zero divergent transitions (in Stan/HMC/NUTS) and good Pareto-k (< 0.7) for LOO-CV. A report claiming convergence while omitting these, or reporting values that breach the thresholds, is auditable at Tier 2.

**5. No automated "Bayesian statcheck" exists** — confirmed across the literature. The closest deterministic building blocks are Faulkenberry's Pearson Bayes factor (recompute a BF from reported t/F and df) and JASP's Summary Stats module (manual recomputation from published summaries). The principal technical barrier is that the BF depends on a prior that is frequently unreported (Depaoli & van de Schoot's 31.1% figure). This is precisely why a recompute-and-flag tool must declare its prior assumption and frame a mismatch as "could not reproduce under the stated default," not "error." By contrast, statcheck's success rests on the fact that p-value inconsistencies are both common and deterministically detectable: Nuijten et al. (2016) found "≈50% of the articles with statistical results contained at least one p value that did not match its accompanying test statistic and degrees of freedom," and ≈12.5% contained at least one decision inconsistency.

---

## Details

### Part 1 — The full conceptual terrain of what is auditable

#### 1.1 Priors

**What it is / why it matters.** The prior is the distribution over parameters (or over models/hypotheses) before seeing data. There is a crucial distinction the skeptical reader must hold: **priors on parameters** (e.g., a prior on an effect size δ within a model) versus **priors on models/hypotheses** (the prior model odds that multiply a Bayes factor to give posterior odds). Conflating them is one of the most common errors (see 1.2).

Types:
- **Informative**: encodes substantive prior knowledge; should be justified by citation or elicitation.
- **Weakly-informative**: regularizing, rules out absurd values without strongly committing (Gelman's recommended default for estimation).
- **Flat/improper**: no proper density (integrates to ∞). Tolerable for *estimation* of a well-identified parameter but **catastrophic for Bayes factors** — an improper prior makes the marginal likelihood, and hence the BF, undefined/arbitrary (the Jeffreys–Lindley–Bartlett issue; bayestestR documentation explicitly warns that brms uses flat priors by default and that these must never be used for BF computation: "a model with completely flat priors is infinitely less favorable than a point null model").
- **Default/reference priors** (JZS/Cauchy for t-tests, the Rouder et al. 2012 g-priors for ANOVA, the Ly/Jeffreys prior for correlation): chosen for desirable mathematical properties when little prior information is asserted.

**Good vs. under-specified report.** Good: states the prior family, its hyperparameters (e.g., "Cauchy on δ with scale r = 0.707"), the justification, and a sensitivity analysis. Under-specified: "we used default priors" with no scale, no family, no software version.

**Failure modes / red flags.** Prior-data conflict (the prior concentrates mass where the likelihood is low — Evans & Moshonov 2006 give a formal tail-probability diagnostic: a prior-data conflict arises when the observed value of the minimal sufficient statistic lies in the tails of the prior-predictive distribution); undisclosed informative priors that drive the result; flat priors used for hypothesis testing; reporting a prior on δ but silence on the model prior odds.

**How the NHST reader should think.** Treat the prior like a model assumption you'd interrogate in any analysis — but recognize that, unlike the (usually invisible) assumptions of a t-test, the Bayesian prior is *explicit and auditable*. The skeptical move is not "priors are subjective therefore suspect" but "is the prior stated, justified, and shown to not be driving the conclusion?"

*Tiering*: presence/specification of prior = **Tier 2**; defensibility of an informative prior = **Tier 3**; whether an improper prior renders a reported BF undefined = **Tier 1/2** (detectable from text if the prior is named).

#### 1.2 Bayes factors specifically

**What they are / aren't.** A Bayes factor is the ratio of marginal likelihoods of two models — the relative predictive performance of model A vs. model B for the observed data. It is **relative** (always about two specified models), **not** the posterior probability that a hypothesis is true, and **not** an effect size. Posterior odds = BF × prior odds; only if prior model odds = 1 does the BF equal the posterior odds.

**Interpretation scales and their dangers.** Jeffreys' scheme, as relabeled by Lee & Wagenmakers (2013): BF 1–3 "anecdotal," 3–10 "moderate," 10–30 "strong," 30–100 "very strong," >100 "extreme." (Kass & Raftery's natural-log scheme differs, with "strong" starting at BF > 20.) Schönbrodt & Wagenmakers and others warn explicitly that these labels reintroduce cutoff thinking — "Hey, the BF jumped over the boundary of 3. It's not anecdotal any more, it's moderate evidence!" — recreating what one widely-cited discussion calls "another sacred .05 criterion." The strength of the BF is precisely its non-binary, continuous nature.

**Sensitivity to prior width.** The Jeffreys–Lindley paradox: as the alternative's prior is made wider (more diffuse), the BF increasingly favors the null, even for data that a frequentist test finds highly significant — because the Bayes factor penalizes a model for "wasting" prior mass on large effect sizes that predict poorly (an automatic Occam's razor). Bartlett's paradox is the same phenomenon driven by prior variance: prior variance can be tuned to make the posterior probability of the null arbitrarily high. A 2025 arXiv preprint (the "Bayes factor reversal paradox") proves that for any two-sided significant result at the .05 level there exist prior variances giving opposite BF conclusions — and, unlike Jeffreys–Lindley, "occurs with realistic sample sizes." There is a genuine, live scholarly disagreement here: Wagenmakers and colleagues argue (Bayesian Spectacles, "Concerns About the Default Cauchy Are Often Exaggerated") that in practice the default Cauchy's width has modest impact — "removing the most extreme 50% of the prior mass can at best double the Bayes factor against the null hypothesis." The honest framing for a non-expert: prior width *can* matter a lot in principle, *often* matters modestly for canonical t-test defaults, and the only way to know for a given paper is a reported robustness curve.

**Default vs. tuned priors.** JASP and the R BayesFactor package default to r = 0.707 for t-tests; tuned/informative priors require justification. A robustness check (BF as a function of prior scale) is the gold standard and its absence is a Tier-2 flag.

**Relationship to components.** A BF is a ratio of two marginal likelihoods; a reported BF₁₀ and BF₀₁ must be reciprocals; a reported posterior odds, prior odds, and BF must satisfy posterior = BF × prior. These arithmetic relationships are **Tier 1**.

#### 1.3 Posterior estimation and summaries

- **Credible intervals**: HPD/HDI (highest-density — every point inside has higher density than any point outside; the shortest interval containing the mass) vs. equal-tailed (ETI — symmetric tail probabilities). For skewed posteriors these differ; reporting which one was used matters. bayestestR offers `hdi()`, `eti()`, `spi()`.
- **Point estimates**: posterior mean/median/mode (MAP). Median is robust; MAP can be unstable.
- **ROPE** (region of practical equivalence; Kruschke): a band around the null deemed practically negligible (default for standardized effects ±0.1 per Cohen; for linear models `0 ± 0.1·SD(y)`). The HDI+ROPE decision rule: reject the null value if the 95% HDI falls entirely outside the ROPE; accept if entirely inside; otherwise undecided. (bayestestR defaults to the 89% HDI as "considered more stable.") **Contested**: an NSF-archived paper argues the HDI+ROPE rule is "logically incoherent" because the HDI is not transformation-invariant, so "the ultimate inferential decision depends on statistically arbitrary and scientifically irrelevant properties of the statistical model"; bayestestR documentation itself warns ROPE is invalidated by collinearity and is highly scale-sensitive (rescaling a predictor can flip the in-ROPE percentage).
- **Posterior predictive checks**: simulate data from the fitted model and compare to observed; the principled Bayesian analogue of residual/goodness-of-fit checking. Their presence is Tier 2; their adequacy is Tier 3.

#### 1.4 MCMC / HMC computational diagnostics

These tell you whether the *computation* (not the model) can be trusted:
- **R-hat / potential scale reduction factor**: compares between- to within-chain variance; should be ≈1. Modern rank-normalized split-R̂ (Vehtari et al. 2021) threshold < 1.01 (older literature used 1.1).
- **ESS (bulk and tail)**: bulk-ESS for central summaries (posterior means), tail-ESS for interval/quantile estimates (the minimum of the ESS for the 5% and 95% quantiles); recommended > 400 (for 4 chains × 1000 post-warmup draws).
- **Divergent transitions** (Stan/HMC/NUTS): a divergence signals the sampler's simulated Hamiltonian trajectory departed from the true one due to pathological curvature (e.g., a hierarchical "funnel"); even a few after warmup "cannot be safely ignored if completely reliable inference is desired" (Stan docs). Distinct from max-treedepth warnings, which are efficiency not validity concerns.
- **Trace plots** (should look like well-mixed "fuzzy caterpillars"), chains/iterations/warmup counts, and **Monte Carlo standard error** (MCSE — the simulation noise in a reported posterior summary).

**What SHOULD be reported and what absence implies.** BARG and WAMBS require R-hat and ESS at minimum; Stan-based work should report divergences. Absence of any convergence diagnostic while asserting "the model converged" is a Tier-2 flag. Reported values that breach thresholds (R-hat 1.05, ESS 50, "120 divergent transitions") are Tier-2 coherence flags — the numbers contradict a "fine" narrative.

#### 1.5 Model comparison and selection

- **WAIC** (widely applicable information criterion) and **LOO-CV** (leave-one-out cross-validation via Pareto-smoothed importance sampling, PSIS; Vehtari, Gelman & Gabry 2017, *Statistics and Computing*): estimate out-of-sample predictive accuracy. LOO is preferred because PSIS yields a diagnostic: the **Pareto-k** shape parameter, with k > 0.7 (sample-size-dependent in the 2024 update) flagging unreliable estimates for that observation. The authors note "if k is greater than the diagnostic threshold then WAIC is also likely to fail, but WAIC lacks as accurate diagnostic."
- **DIC** (deviance information criterion): older, **deprecated** in modern workflows because it is not fully Bayesian (point-estimate based), can produce a negative effective number of parameters, and lacks PSIS-style diagnostics.
- **Marginal likelihood / bridge sampling** (Gronau, Singmann & Wagenmakers 2020, the `bridgesampling` package): the route to Bayes factors for general models (e.g., brms with `save_pars = save_pars(all = TRUE)`); requires proper priors and far more posterior draws than estimation (brms documentation gives a "10-fold" rule of thumb — the default 4000 samples "may not be enough").
- **Estimation-focused vs. hypothesis-testing-focused workflows.** This is the deepest fault line in applied Bayesian practice. The Kruschke camp favors estimation (posterior + HDI + ROPE); the Wagenmakers/Rouder camp favors Bayes-factor hypothesis testing; Tendeiro & Kiers (2019, 2023) argue posterior model probabilities and estimation should be emphasized over Bayes factors, while van Ravenzwaaij & Wagenmakers (2022) reply that several of Tendeiro & Kiers's "issues" are in fact "advantages masquerading as issues." A skeptical reader should first ask: *which question is this paper answering — "how big is the effect?" (estimation) or "which model predicts better?" (testing)?* — because the right diagnostics differ.

#### 1.6 Sensitivity and robustness

- **Prior sensitivity analysis**: re-run under alternative priors; report whether conclusions change.
- **Robustness Bayes-factor curves**: plot BF against prior scale r (JASP produces these automatically across its default range of prior widths). A result that flips the sign of its conclusion across the default range is fragile.
- **Multiverse / specification reasoning** (Steegen, Tuerlinckx, Gelman & Vanpaemel 2016, *Perspectives on Psychological Science*; Simonsohn's specification curve): run all reasonable data-processing and model specifications and display the distribution of results. Explicitly *not* a formal test of QRPs and *not* a single evidential summary — and beware the "illusion of probability" (results returned more frequently by the multiverse are not thereby more likely to be true).

#### 1.7 Researcher degrees of freedom in a Bayesian context

- **Prior-hacking**: choosing the prior to get the desired BF/posterior.
- **Optional stopping / BF-stopping.** This is genuinely nuanced and contested. Rouder (2014, "Optional stopping: no problem for Bayesians") showed by simulation that the *interpretation* of posterior odds is invariant to the stopping rule for purely subjective priors — "the interpretation of Bayesian quantities does not depend on the stopping rule." But de Heide & Grünwald and the de Heide et al. analysis show that for the *default/pragmatic* priors actually used in practice, calibration breaks down: "as soon as the parameters of interest are equipped with default or pragmatic priors—which means, in most practical applications of Bayes factor hypothesis testing—resilience to optional stopping can break down." Simonsohn's blunt version: "when a researcher p-hacks, she also Bayes-factor-hacks." The accurate non-expert takeaway: **Bayesian inference is less harmed by optional stopping than NHST, but it is not immune**, especially with default priors and especially for effect-size estimation (Type-M/magnitude bias).
- **Garden of forking paths in model space**: the multiplicity of model/prior/likelihood choices is the Bayesian analogue of the forking-paths problem; pre-registration and multiverse reporting are the mitigations.

### Part 2 — Existing standards, guidelines, and tools

| Tool/guideline | What it checks | Deterministic or judgment | What leaning on it means |
|---|---|---|---|
| **BARG** (Kruschke 2021) | Comprehensive reporting checklist: prior, model, computation, convergence (R-hat, ESS), posterior summaries, sensitivity, code availability | Completeness (Tier 2); items themselves are judgment | The authoritative "what should be present" reference for a completeness audit |
| **WAMBS** (Depaoli & van de Schoot 2017) | 10 points across before/after estimation, prior influence, post-interpretation; convergence, prior-posterior overlap | Completeness + judgment | Process checklist; some items (convergence) map to Tier-2 numeric flags |
| **JASP guidelines** (van Doorn et al. 2021) | Plan/execute/interpret/report stages; robustness checks, prior justification | Completeness + judgment | Strong for JASP-style canonical analyses |
| **statcheck** (Nuijten & Epskamp) | Recomputes NHST p-values from t/F/r/χ²/Z + df in APA format; flags inconsistencies and "decision errors" | **Deterministic** (Tier 1) | The NHST analogue and proof-of-concept; Nuijten et al. (2017) report overall accuracy "96.2% to 99.9%" (contested by Schmidt 2017, who computes sensitivity ≈.52); but it explicitly does NOT handle Bayes factors, can't read tables, requires APA format |
| **BayesFactor package / JASP Summary Stats** | Computes default JZS BFs from summary stats | Deterministic given prior | The recompute engine for the Tier-1 core |
| **bayestestR / easystats** | Posterior description: HDI/ETI, pd, ROPE%, BF; reports R-hat/ESS | Deterministic computation; interpretation is judgment | Defines the standard output vocabulary a parser would target |
| **loo / Pareto-k** (Vehtari et al.) | LOO-CV with k diagnostic | Deterministic diagnostic | Threshold-based Tier-2 flags |
| **Faulkenberry Pearson BF** | Recompute BF from t/F + df | Deterministic (Tier 1) | Closest published building block for a "Bayesian statcheck" |
| **bridgesampling** (Gronau et al.) | Marginal likelihoods/BF for general models | Deterministic given fitted model + proper priors | Not a paper-auditing tool |

**Crucial finding:** there is no automated tool that scrapes Bayes factors from papers and verifies them the way statcheck does for p-values. The Tendeiro/Wong literature studies were done by *manual human coding* of 73 and 167 articles — underscoring the gap. Method-*validation* tools exist (Sekulovski, Marsman & Wagenmakers 2024, "A Good check on the Bayes factor," *Behavior Research Methods*, via Turing/Good simulation-based calibration; Schad et al. 2022 workflow techniques) but they check whether a *computation method* is correct, not whether a *published value* is internally consistent. No GRIM/SPRITE-style granularity test has been adapted to Bayesian quantities.

### Part 3 — The recomputable core (the statcheck-like analogue)

**Where genuine deterministic, no-raw-data recomputation is possible:** default Bayes factors for canonical designs, recoverable from reported test statistics and N.

- **One-sample / paired t-test**: the JZS BF is a closed-form expression in t, N (and df = N−1) and the Cauchy scale r. Rouder et al. (2009) give the explicit integral B₀₁ as a one-dimensional quadrature over g; with the default r = 0.707 it requires only t and N.
- **Two-sample t-test**: same form, with effective N and df = N₁+N₂−2.
- **ANOVA**: Rouder, Morey, Speckman & Province (2012) default g-priors; computable from F and df.
- **Correlation**: Ly, Verhagen & Wagenmakers (2016) Jeffreys prior on ρ; BF from r and N.
- **Regression**: Liang et al. (2008) / Rouder & Morey g-priors; from R², number of predictors, N.

**Inputs required**: test statistic (t/F/r), sample size(s)/df, the prior family and scale. **The check**: recompute the BF under the stated (or default) prior and compare to the reported BF, exactly as statcheck recomputes p from t and df. Internal-consistency checks that need *no* prior assumption at all: BF₁₀ = 1/BF₀₁; posterior odds = BF × prior odds; a verbal label matching its numeric BF.

**Where recomputability ends — sharply:**
- Any analysis with MCMC-estimated posteriors (brms/Stan/PyMC hierarchical models) — the BF/posterior depends on the full data and sampler, not on summary stats.
- Bridge-sampling BFs for general models.
- Any non-default/informative prior whose scale isn't reported.
- Anything where the prior is unstated (Depaoli & van de Schoot's 31.1%) — you can recompute *under an assumed default* and report "could not reproduce under the JZS default (r = 0.707); the paper does not state its prior," which is a flag, not an adjudication.

### Part 4 — The interpretive-scaffolding design problem (Tool A)

**The core risk.** statcheck-style framing trains users to seek a binary "pass/fail." That is the precise habit Bayesian thinking should dissolve. A literacy aid that renders a green check / red X over a Bayesian result would actively *miseducate* — it would teach an NHST reader to treat BF > 3 like p < .05.

**Known pedagogical bridges (familiar rungs):**
- Posterior odds = prior odds × BF mirrors the diagnostic-testing intuition many clinicians already have (sensitivity/specificity → likelihood ratio → updated odds).
- A credible interval *can* be introduced as "what people wrongly wish a confidence interval meant" — the 95% credible interval genuinely has a 95% probability of containing the parameter given the model and prior, which is the interpretation NHST users mistakenly attach to CIs (Kruschke & Liddell 2018, "The Bayesian New Statistics").
- The probability of direction (pd) in bayestestR is numerically close to the one-sided p-value (p ≈ 1−pd; a pd of 97.5% ≈ two-sided p ≈ .05), an explicit, honest translation bridge — though bayestestR cautions pd indexes *existence/direction*, not *magnitude/significance*.

**Known traps (where NHST intuition misleads), with the documented misinterpretations from Tendeiro et al. (2024) and Wong et al. (2022):**
- **BF read as a p-value / as significance**: treating BF thresholds as α-style cutoffs (QRIP10, "interpreting ranges of BF values only"; QRIP5, "absolute statements," in 35.3% of articles).
- **BF read as posterior odds / as P(H₀|data)**: the single most common error — Tendeiro et al. QRIP1 (describing BF as posterior odds, 13.2%) plus QRIP6 (using BF as posterior odds, 20.4%). Wong et al. conclude "interpreting the Bayes Factor as posterior odds and not acknowledging the notion of relative evidence in the Bayes Factor are arguably the most concerning ones."
- **BF read as effect size**: a large BF means strong *evidence*, not a large *effect* (QRIP7, 4.2%).
- **BF read as absolute rather than relative evidence**: failing to acknowledge the BF compares two specified models — Tendeiro et al.'s most prevalent flag (QRIP4, 62.3% of articles).
- **Credible interval read as confidence interval** (and vice versa): a confidence interval has *no* distributional information — values in its middle are not "more probable" (Kruschke & Liddell); a credible interval does.
- **"The posterior probability the null is true"** stated from a BF without prior odds.
- **Absence of evidence treated as evidence of absence**: concluding "no effect" from an inconclusive BF ≈ 1 (QRIP9; Wong et al.'s most common "other" QRIP, basing conclusions on an inconclusive BF, n = 16).

**Design guidance.** Build rungs that are familiar but annotate every rung with the precise place the frequentist intuition breaks. Present continuous evidence (the BF value, the full posterior) rather than verdicts. Where a verbal label is shown, show the whole scale and the cutoff fragility simultaneously. Frame everything as "here is what this number can and cannot tell you," never "this result is valid/invalid."

### Part 5 — Advisory-annotations layer and a planted-error calibration sandbox

**What advisory annotations look like.** AI-generated interpretive flags that are explicitly exploratory and non-authoritative: e.g., "This paper reports BF₁₀ = 14 but does not state the prior scale; under the JASP default r = 0.707 and the reported t(38) = 2.1, N = 40, we recompute BF₁₀ ≈ [value]. If these differ, inspect the original." Every annotation points at the source location and invites verification; none asserts a conclusion. Annotations should carry a confidence/tier tag (Tier 1 recompute mismatch = high-confidence flag; Tier 2 completeness gap = medium; Tier 3 = "advisory only, requires expert").

**A failure-mode taxonomy of plantable Bayesian errors** for a private calibration sandbox (a researcher seeds analyses with known intentional focal errors to test detection). For each: detectable-from-text vs. requires-data.

| Planted error class | Description | Detection from reported text alone? |
|---|---|---|
| **Prior-data conflict** | Informative prior placed far from where data point | Partially — only if prior and posterior/data summaries both reported; full check (Evans–Moshonov tail probability) needs data/draws |
| **BF/component mismatch** | Reported BF₁₀ ≠ 1/BF₀₁; posterior odds ≠ BF×prior odds; BF inconsistent with reported t/F/N under stated prior | **Yes — Tier 1**, deterministic arithmetic/recompute |
| **Undisclosed multiplicity / optional stopping** | Sequential peeking, many comparisons, no correction or disclosure | Only as a completeness flag (was a sampling plan/stopping rule stated?); the bias itself needs design info |
| **Non-convergence reported as fine / omitted diagnostics** | "Chains converged" but no R-hat/ESS; or reported R-hat 1.08 | **Yes — Tier 2** coherence/completeness |
| **Hidden prior sensitivity** | No robustness curve; conclusion fragile to prior width | Completeness flag (no sensitivity analysis reported); fragility itself needs recomputation/data |
| **Mislabeled credible vs. confidence interval** | Text calls a Bayesian interval a "confidence interval" or interprets a CI as a probability statement | **Yes — Tier 2** textual/coherence |
| **Wrong BF interpretation direction** | BF₀₁ described as evidence for the alternative, or label inverted | **Yes — Tier 1/2**, label-vs-value coherence |
| **Improper prior yielding undefined BF** | Flat/improper prior used for a reported Bayes factor | **Yes — Tier 2** if prior is named (improper prior ⇒ BF undefined) |
| **BF as effect size / as posterior probability** | Text infers effect magnitude or P(H|data) from BF alone | **Yes — Tier 2** textual |

Framing matters: this sandbox is a **private, not-generally-released calibration/learning instrument** — a way for a skeptical researcher to measure the tool's true-positive/false-negative profile against known errors before trusting any flag. It is explicitly not a public "fraud detector," and the planted errors are the researcher's own focal test cases, not accusations about real papers.

### Part 6 — Honest-limitations framing

A tool in this space should tell users, plainly:
- **What it stands behind (Tier 1):** "We recomputed this default Bayes factor / checked this arithmetic relationship and it does/does not reconcile under the stated assumptions." This is a reproducibility statement, not a correctness verdict.
- **What it can only flag (Tier 2):** "This element (prior / convergence diagnostic / sensitivity analysis) appears to be missing or internally inconsistent with the text. A human should inspect."
- **What it cannot judge (Tier 3):** "Whether this prior/model/ROPE is appropriate is a matter of domain and statistical expertise. We surface the relevant passage; we do not evaluate it."
- The overarching message: **it is an interpretive aid that points you at evidence in the source, not an authority that adjudicates.** Every flag is a hypothesis to be checked against the paper, consistent with Callosum's governing principle that AI may FLAG-as-inspectable-evidence but never ADJUDICATE.

---

## Recommendations

**Stage 1 — Build the Tier-1 recompute core first (highest trust, narrowest scope).** Implement default-BF recomputation for the canonical designs (one/two-sample/paired t, ANOVA, correlation, regression) from t/F/r and N using the BayesFactor package's methods (or Faulkenberry's closed forms), plus the assumption-free arithmetic checks (reciprocal BFs, posterior = BF × prior, label↔value). Always declare the assumed prior and frame any mismatch as "not reproduced under stated/assumed default," never "error." *Benchmark to advance:* on a planted-error sandbox, ≥95% true-positive on arithmetic/recompute mismatches with a quantified false-positive rate from rounding (mirror statcheck's rounding tolerance, which treats a reported t of 2.35 as consistent with any true value in 2.345–2.354).

**Stage 2 — Add the Tier-2 completeness/coherence auditor.** Parse for presence of: named prior + scale; convergence diagnostics (R-hat, bulk/tail ESS) and whether reported values breach Vehtari thresholds (R-hat < 1.01, ESS > 400); divergent-transition reporting; a prior sensitivity/robustness analysis; interval type (HDI vs ETI); credible-vs-confidence terminology. Output checklist-style flags keyed to BARG/WAMBS/JASP items, each linked to the source passage. *Benchmark:* high recall against the human-coded QRIP categories from Tendeiro et al. on a labeled corpus — the prevalence base rates (QRIP4 at 62.3%, prior-reporting failures at 77.8% combined) suggest where flags will fire most.

**Stage 3 — Layer advisory (Tier-3) annotations, clearly demarcated.** Exploratory interpretive notes (possible prior-data conflict, fragile-looking BF) tagged "advisory — requires expert judgment," never mixed visually with Tier-1/Tier-2 flags.

**Stage 4 — Ship the literacy scaffolding around, not instead of, the flags.** For each flagged element, provide the NHST→Bayesian bridge *and* the trap (e.g., "BF is not P(H₀|data); here's the difference"). Never render a verdict UI.

**Thresholds that would change the plan:** If a validated automated Bayesian-statcheck emerges in the literature, adopt/integrate it rather than rebuilding. If empirical testing shows users systematically read Tier-2 flags as verdicts despite framing, retreat to advisory-only language. If parsing accuracy for priors/diagnostics from PDF text proves low (a known statcheck limitation — it can't read tables and requires strict formatting), gate Tier-2 claims behind a confidence threshold and prefer false negatives over false positives.

## Caveats

- **The estimation-vs-testing and default-prior debates are genuinely unresolved.** The report presents both sides (Rouder/Wagenmakers/van Ravenzwaaij vs. Tendeiro/Kiers; "Cauchy width matters" vs. "concerns exaggerated") rather than flattening them; a tool must not implicitly take a side by, e.g., privileging Bayes factors over posterior estimation.
- **"No automated Bayesian statcheck exists" is an inference from absence** across the literature as of mid-2026; a niche or unpublished tool could exist, but none surfaced in reputable literature or repositories.
- **Some thresholds are conventions, not laws** (R-hat < 1.01, ESS > 400, Pareto-k < 0.7, ROPE ±0.1): they are widely used defaults, and a tool should cite them as such, not as hard truths. The HDI+ROPE rule in particular has a published coherence critique (non-transformation-invariance).
- **statcheck's own accuracy is contested**: Nuijten et al. (2017) report 96.2–99.9% overall accuracy, but Schmidt (2017) recomputes sensitivity near .52 and notes statcheck detected only ~61% of tests. Any Tier-1 Bayesian recompute claim should be validated and reported with the same scrutiny.
- **PDF parsing is the practical bottleneck.** statcheck's limitations (APA-format only, can't read tables, needs complete reporting) will be worse for Bayesian work, which has no single canonical reporting format. Several quoted numeric thresholds and prevalence figures here come from documentation and secondary discussion and should be verified against primary sources before being surfaced as tool copy.
