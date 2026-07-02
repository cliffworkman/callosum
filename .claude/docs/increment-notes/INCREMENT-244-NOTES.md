# Increment 244 — Bayesian auditor SP4 (Tier-3 textual-coherence advisory prompts; fully closes #24)

The last of the "build all three" threads the maintainer chose to close out future-track #24. The future-track doc's
**Stage 3** — *advisory* interpretive notes, clearly demarcated, requires-expert-judgment, never mixed with the
Tier-1/Tier-2 flags. These are the riskiest thing in the whole auditor (fuzzy prose → false positives), so the
honesty controls are the entire point.

## What it flags

Two conservatively-gated **Tier-3 advisory** prompts on the `completeness` block of the existing
`GET /papers/{id}/bayes` (`methods/bayes.py::_advisory_notes`):

1. **credible-vs-confidence** — a Bayesian paper that mentions a "confidence interval" but **never** a "credible
   interval": *verify whether a credible interval was intended (a common Bayesian/frequentist conflation).*
2. **BF-direction** — a `BF01` reported within ±120 chars of a claim of support for the alternative: *BF₀₁ quantifies
   evidence for the null, so verify the direction or label.*

## The honesty controls (built, not framed)

- **Advisory, never a flag/verdict.** A separate panel block (`BayesAdvisories`), **neutral `--accent-soft` tint —
  NOT the amber flag** used for the Tier-2 coherence flag; headed **"Advisory — requires expert judgment"**; each note
  worded as an exploratory prompt ("verify…", "a common conflation"), with a closing caveat "exploratory prompts, not
  verdicts or flags — the text merely *suggests* a possible mislabel; a human should confirm." Honors #2
  signal-not-verdict + the A-A no-accusation veto.
- **Bayesian-gated.** `_advisory_notes` runs only when `_has(_BAYESIAN, rows)` (the same gate as the checklist) — a
  non-Bayesian paper mentioning a confidence interval is untouched.
- **Conservative (prefer false negatives — the doc's guidance).** credible-vs-confidence is **suppressed** if the
  paper also says "credible interval" (assume it distinguishes them); BF-direction fires only on the *specific*
  `BF01`-near-"alternative-support" co-occurrence (a literal alternation, `[^.]{0,40}\balternative\b`), and returns
  after the first hit (advisory, not an exhaustive scan).

## Surface / gates

- Rides the **existing** `GET /papers/{id}/bayes` additively (an `advisories` list on the `completeness` block) — **no
  new API surface, no migration, no egress, no LLM, no new dependency** (literal/anchored regexes, no catastrophic
  backtracking).
- **Principles (#9) — aligned:** built to the doc's Stage-3 advisory-not-verdict prescription; the maintainer's strong
  no-false-positive stance (cf. the inc-229 citation-equity rework) honored by the conservative gating + prompt-not-
  verdict wording + visual separation from the real flags.
- **Audit — addendum 3 to `2026-07-01_bayes-auditor.md` PASS** (additive read-only field; local/bounded; no
  backtracking; Bayesian-gated / conservative / advisory-not-verdict).
- **QA (#10):** `route_59_methods_bayes.md` extended with the advisory step; surface 174/174 API + 771/771 FE, 0
  uncovered (the block rides the existing endpoint + panel).

## Verification

pytest **909 passed, 1 skipped** (+5 hermetic `tests/test_bayes.py`, no network/model: credible-vs-confidence fires
[confidence, no credible] / **suppressed** when both interval types appear; BF-direction fires [BF01 near "supported
the alternative"]; **none** for a clean Bayesian paper; **none** for a non-Bayesian paper; + the endpoint `advisories`
field). `ruff` + `format` clean; `test_frontend_assembly` 5/5.

**Headed-verified at desktop, 0 errors** (`.local/visual/drive_inc244_advisory.py` — a seeded Bayesian paper with both
triggers: open METHODS → Bayesian statistics → the recompute + checklist render AND an **Advisory** block shows **2**
prompts under **"ADVISORY — REQUIRES EXPERT JUDGMENT"**, worded as prompts ("verify…", "not verdicts"), with a
**neutral left-border, not the amber flag**; 0 console/page errors, 0 genai-host requests).

## This FULLY CLOSES future-track #24

The Bayesian auditor is complete: **SP1** t-test recompute (241) · **SP2** completeness checklist (242) · **SP3**
Pearson-correlation recompute (243) · **SP4** advisory prompts (244). **ANOVA / regression BFs remain a documented
deferral** — not faithfully recomputable/verifiable from F + df alone (inc 243 audit addendum 2), pending a trusted
anchor (R BayesFactor / a validated Rouder-2012 quadrature).

**NEXT (a fresh track — the maintainer's pick):** the standing new-METHODS-auditor candidate is the **LMM-reporting
auditor** (#23); or another future-track (the tree's A-list + B-list + #24/#25 are all done).
