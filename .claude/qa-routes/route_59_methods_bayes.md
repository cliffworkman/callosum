<!-- qa-coverage
api: /papers/{paper_id}/bayes
fe: 08d_methods_bayes.jsx
-->

# ROUTE 59 - Methods: Bayesian auditor (default JZS Bayes-factor recompute)

**Tier:** 1 local-stateful
**Goal:** Exhaust the per-paper Bayesian auditor (the statcheck sibling for t-test Bayes factors) while preserving
signal-not-verdict + no-accusation framing. It recomputes a paper's reported **default JZS** Bayes factors (Rouder
et al. 2009) from inline `t(df) = …, BF10 = …` and flags where they don't reproduce under the default prior. Local,
deterministic, no AI.

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
- **Coordinate honesty.** A per-BF row opens its page at **region** precision (page-open), never a fabricated exact
  highlight.

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
3. Confirm a **reproduces** row shows `reported BF₁₀ = …` + `recomputed … (paired|two-sample)` + a green pill; a
   **couldn't reproduce** row shows the amber pill + the recomputed candidate(s).
4. Click a per-BF row -> the PDF opens at that page at **region** precision (no exact rect).
5. Confirm the **default-prior caveat** (r ≈ 0.71; a different prior → an expected mismatch; inline-only coverage;
   "not a verdict or an accusation").
6. Confirm the **credit** block (Rouder, Speckman, Sun, Morey & Iverson 2009) + a working **＋ add to library**.
7. Adversarial: a metadata-only paper -> "Process a PDF first"; a no-BF paper -> honest empty; 999999 -> 404-class.

## Pass criteria

- The auditor recomputes reported default BFs, shows reproduce/couldn't-reproduce with the recomputed value + prior,
  and routes each row to its page at region precision.
- 0 console/page errors; **0 genai-host requests** (local).
- No per-paper/per-author judgment, no score/rank; a mismatch is "couldn't reproduce under the default prior".
- No-chunks / no-BF / unknown-id fail closed honestly; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_59_methods_bayes.md` + `screenshots/` (see `_TEMPLATE.md`).
