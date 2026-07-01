# Increment 242 — Bayesian auditor SP2 (Tier-2 BARG/WAMBS/JASP reporting checklist; completes #24)

SP1 (inc 241) shipped the deterministic recompute. SP2 is the **completeness/coherence** half: does a Bayesian paper
*report* the core reporting elements the guidelines require? Via AskUserQuestion the maintainer chose the **BARG/WAMBS
core** (three clean presence/absence items) over the riskier "core + textual-coherence" path — matching the doc's own
guidance to prefer false negatives. The Principles gate ran — the presence/absence-checklist class (PRINCIPLES
Example 3, the statcheck class).

## What it checks

Three items keyed to the published Bayesian reporting guidelines (BARG — Kruschke 2021; WAMBS — Depaoli & van de
Schoot 2017; the JASP guidelines — van Doorn et al. 2021):

1. **Prior stated** — is a prior family/scale named? ("default priors" with no scale → **present-but-under-specified**,
   the specific BARG point.)
2. **Convergence diagnostics** — R-hat / ESS / divergent transitions reported?
3. **Prior sensitivity / robustness analysis** — reported?

Plus a **coherence flag** when a *reported* diagnostic breaches a convention.

## The load-bearing honesty controls (the doc's warnings, made structural)

A completeness checklist is dangerous if it reads as a verdict, so every honesty control is built in, not framed:

- **Gated on the paper being Bayesian.** `audit_completeness` first checks for Bayesian keywords (BF / Bayesian /
  posterior / credible interval / MCMC-Stan-brms-JAGS-NUTS-HMC). If none → `is_bayesian: false`, no items. A
  non-Bayesian paper cannot "fail" the checklist.
- **Convergence is `not-applicable` without MCMC.** A closed-form default Bayes factor has no chains to diagnose, so
  the absence of R-hat/ESS is *not* "missing" — it's n/a. The item is only "present"/"not-found" when a sampler
  (Stan/brms/JAGS/MCMC/posterior sampling) is detected.
- **"not-found" ≠ "missing".** Framed **"not detected in the extracted text — check the paper"**. statcheck can't
  read tables, so silence-≠-certificate cuts both ways: absence in our scan is not absence in the paper. Never an
  accusation (the A-A veto).
- **The coherence flag is conservative** (prefers false negatives, the doc's guidance): it fires only on a *reported*
  R-hat > 1.1 (breaches even the lenient older convention), ESS < 400 (the Vehtari recommendation), or > 0 divergent
  transitions — and the note cites the threshold as a **convention, not a law** (e.g. "exceeds the conventional
  R-hat < 1.1; modern practice uses < 1.01").
- **No composite score** (#7) — three independent items, each carrying its **matched evidence snippet** + page (#4/#8).

## The surface

- **Extends `GET /papers/{paper_id}/bayes`** additively with a `completeness` block (`is_bayesian` + per-item
  `{key, label, status, evidence, page, note}`), computed by `methods/bayes.py::audit_completeness`. One fetch drives
  both the SP1 recompute rows and the checklist (the panel already auto-runs one `/bayes` call on open).
- **Panel `08d_methods_bayes.jsx`** gains a **Reporting checklist** section below the recompute: per-item pills
  (✓ present / not found / n/a / ⚠ check), the matched evidence snippet (opens its page at **region** precision — the
  coordinate-honesty contract), the BARG/WAMBS/JASP credit, and the "presence/absence in the text, never a verdict"
  caveat. A Bayesian paper with no *inline* default BFs still gets the checklist (the recompute part shows a "no
  inline BFs to recompute" note).

**Fully local — no egress, no LLM, no migration, no new dependency** (bounded anchored regexes; no catastrophic
backtracking; `_chunk_rows` factored out of `run_bayes` and reused).

## Gates

- **Principles (#9) — aligned.** The presence/absence-checklist class; declined the "Bayesian reproducibility score /
  failed the checklist" verdict, and deferred the fuzzier **textual-coherence** flags (credible-vs-confidence mislabel,
  BF-direction) per the doc's prefer-false-negatives guidance.
- **Audit — addendum to `2026-07-01_bayes-auditor.md` PASS.** Additive read-only response field; the honesty controls
  (Bayesian-gated / convergence-n/a / not-found-≠-missing / conventions-not-laws) uphold the no-accusation boundary.
- **QA (#10):** `route_59_methods_bayes.md` extended with the checklist step + the honesty assertions; surface
  174/174 API + 769/769 FE, 0 uncovered.
- **Credit-the-lineage:** BARG/WAMBS/JASP credited in the checklist caveat (the SP1 credit already library-adds Rouder).

## Verification

pytest **899 passed, 1 skipped** (+5 hermetic `tests/test_bayes.py`, no network/model: gated-on-Bayesian [a
non-Bayesian paper → `is_bayesian:false`, no items]; a closed-form BF paper → prior present [Cauchy] / convergence
**n/a** [no MCMC] / sensitivity not-found; an MCMC paper with R-hat = 1.21 → convergence **coherence-flag** with the
value + convention in the note + sensitivity present; "default priors" → present-**under-specified**; good MCMC
diagnostics → present; the endpoint returns the `completeness` block + a metadata-only paper → `is_bayesian:false`).
`ruff` + `format` clean; `test_frontend_assembly` 5/5.

**Headed-verified at desktop, 0 errors** (`.local/visual/drive_inc242_bayes_completeness.py` — a seeded Bayesian
paired t-test [Cauchy prior + an inline BF, no MCMC, no sensitivity analysis]: open METHODS → Bayesian statistics →
the section auto-runs → the recompute reproduces AND the **Reporting checklist** shows [**Prior stated → ✓ present**,
**Convergence → n/a**, **Sensitivity → not found**] + the BARG/WAMBS/JASP credit; the prior's evidence snippet opens
its page at region precision; 0 console/page errors, 0 genai-host requests). *(The seed writes a real 6-page PDF so
the evidence page-open serves cleanly.)*

## This completes future-track #24

SP1 (inc 241) recompute + SP2 (inc 242) checklist. **Deferred (own increment if wanted):** correlation / ANOVA
default BFs (Tier-1 recompute for more designs) + the fuzzier **textual-coherence** flags (credible-vs-confidence
mislabel, BF-direction error) as *advisory* (Tier-3) annotations. Other new-auditor candidate: the **LMM-reporting
auditor** (#23). Spec: `.claude/docs/future-tracks/opus4.8_future-tracks_bayesianauditing.md`.
