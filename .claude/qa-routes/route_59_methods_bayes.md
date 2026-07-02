<!-- qa-coverage
api: /papers/{paper_id}/bayes
fe: 08d_methods_bayes.jsx
-->

# ROUTE 59 - Methods: Bayesian auditor (default JZS Bayes-factor recompute + Tier-2 reporting checklist)

**Tier:** 1 local-stateful
**Goal:** Exhaust the per-paper Bayesian auditor (the statcheck sibling for Bayesian Bayes factors) while preserving
signal-not-verdict + no-accusation framing. **SP1:** recompute a paper's reported **default JZS** Bayes factors
(Rouder et al. 2009) from inline `t(df) = …, BF10 = …` and flag where they don't reproduce under the default prior.
**SP2:** a **Tier-2 completeness checklist** (BARG/WAMBS/JASP) — presence/absence of the prior, convergence
diagnostics, and a sensitivity analysis, plus a coherence flag when a *reported* diagnostic breaches a convention.
**SP3 (inc 243):** the **correlation** recompute — inline `r(df) = …, BF10 = …` recomputed under the default
correlation prior (Ly et al. 2016). **SP4 (inc 244):** Tier-3 **advisory** prompts (credible-vs-confidence mislabel;
BF-direction) — clearly demarcated, exploratory, requires-expert-judgment, never a flag. Local, deterministic, no AI.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (the auditor is local/no-LLM — assert no
genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The auditor is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Signal not verdict / no accusation (Critical if violated).** No composite score, no rank, no per-paper or
  per-author judgment; a mismatch is framed "couldn't reproduce **under the default prior**", never "wrong" or
  "p-hacked"; the recomputed value + the assumed prior scale are shown so the result is inspectable.
- **Silence ≠ certificate.** The inline-only coverage caveat is stated (a clean result isn't a clean bill; a BF with
  no adjacent t-stat is invisible, not "fine").
- **Coordinate honesty.** A per-BF / per-checklist-item evidence link opens its page at **region** precision
  (page-open), never a fabricated exact highlight.
- **Checklist honesty (SP2).** The completeness checklist runs **only** on a paper detectably doing Bayesian analysis
  (else no checklist). "not found" is worded **"not detected in the extracted text — check the paper"**, NEVER
  "missing" / an accusation (Critical if it reads as a verdict). Convergence is **n/a** when no MCMC is reported (a
  closed-form BF has no chains — not "missing"). Thresholds (R-hat < 1.1, ESS > 400) are cited as **conventions**.

## Adversarial checklist

- select a metadata-only paper (no chunks) -> "Process a PDF first" (never a crash / never a fabricated result)
- select a paper with no inline t-test BFs -> honest "No inline t-test Bayes factors found"
- `GET /papers/999999/bayes` -> 404-class, no crash
- confirm a **reproduces** row (green) AND a **couldn't reproduce** row (amber) both show the recomputed value +
  the assumed prior; the amber row is NOT worded as an error/accusation
- resize to `375x812`, no horizontal overflow

## Steps

1. Open the **METHODS** pane -> **Bayesian statistics** section. Confirm the intro (default-Bayes-factor recompute,
   local/no-AI, "a prompt to look, never a verdict").
2. Select a paper whose text has an inline `t(df) = …, BF10 = …`. The section auto-runs `GET /papers/{id}/bayes`
   (or click **Check Bayes factors**). Confirm the counts line ("N checked · M couldn't reproduce under the default
   prior") + per-BF rows.
3. Confirm a **reproduces** row shows `reported BF₁₀ = …` + `recomputed … (paired|two-sample|correlation)` + a green
   pill; a **couldn't reproduce** row shows the amber pill + the recomputed candidate(s). A **correlation** `r(df)`
   BF has a single recomputed value (`(correlation)`), no paired/two-sample fork.
4. Click a per-BF row -> the PDF opens at that page at **region** precision (no exact rect).
5. Confirm the **default-prior caveat** (r ≈ 0.71; a different prior → an expected mismatch; inline-only coverage;
   "not a verdict or an accusation").
6. **SP2 — Reporting checklist.** For a Bayesian paper, confirm the **Reporting checklist** below the recompute: rows
   for **Prior stated**, **Convergence diagnostics**, **Prior sensitivity/robustness**, each `✓ present` / `not found`
   / `n/a` / `⚠ check` (coherence). A present/coherence row shows the **matched evidence snippet** (opens its page at
   region precision). Confirm the guidelines-credit (BARG/WAMBS/JASP) + the "not detected in the text, not a verdict"
   caveat. Confirm convergence is **n/a** for a closed-form BF paper (no MCMC).
   - **SP4 — Advisory notes (if present).** A Bayesian paper that mentions a "confidence interval" (with no "credible
     interval"), or a BF₀₁ near "support for the alternative", shows an **Advisory** block — clearly demarcated from
     the checklist (neutral tint, NOT amber), headed "requires expert judgment", worded as an exploratory prompt
     ("verify…", "a common conflation"), **never a flag/verdict** (Critical if it reads as a verdict). It runs only on
     a Bayesian paper.
7. Confirm the **credit** block (Rouder, Speckman, Sun, Morey & Iverson 2009) + a working **＋ add to library**.
8. Adversarial: a metadata-only paper -> "Process a PDF first"; a non-Bayesian paper -> "doesn't appear to report a
   Bayesian analysis"; 999999 -> 404-class.

## Pass criteria

- The auditor recomputes reported default BFs, shows reproduce/couldn't-reproduce with the recomputed value + prior,
  and routes each row to its page at region precision.
- 0 console/page errors; **0 genai-host requests** (local).
- No per-paper/per-author judgment, no score/rank; a mismatch is "couldn't reproduce under the default prior".
- No-chunks / no-BF / unknown-id fail closed honestly; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_59_methods_bayes.md` + `screenshots/` (see `_TEMPLATE.md`).
