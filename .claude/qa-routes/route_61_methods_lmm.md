<!-- qa-coverage
api: /papers/{paper_id}/lmm
fe: 08f_methods_lmm.jsx
-->

# ROUTE 61 - Methods: LMM-reporting completeness auditor

**Tier:** 1 local-stateful
**Goal:** Exhaust the per-paper LMM-reporting auditor (the statcheck sibling for linear mixed models) while
preserving FLAG-not-ADJUDICATE + no-accusation framing. It reads a mixed-model paper's extracted text and flags
whether it *reports* seven things a careful reader needs — random-effects structure, df/inference method, convergence/
singular fit, estimation (REML/ML), ICC, marginal/conditional R², and (for longitudinal designs with dropout) a
missing-data sensitivity analysis. Each check is `present` / `not-found` / `not-applicable`. **It never runs a model,
an imputation, or a sensitivity analysis, and never ingests raw data.** Local, deterministic, no AI, no egress.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (the auditor is local/no-LLM — assert no
genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The auditor is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **FLAG-not-ADJUDICATE / no accusation (Critical if violated).** No composite score, no rank, no pass/fail verdict,
  no "this analysis is wrong". Statuses are present / not-found / not-applicable only; a fired flag carries a
  **grounded, cited recommendation**, never an accusation of the authors.
- **Silence ≠ certificate.** "not found" is worded **"not detected in the extracted text — check the paper"**, NEVER
  "missing" (Critical if it reads as a verdict). The honest-scope caveat ("reporting completeness, not analysis
  correctness") is stated.
- **Precondition scoping.** ICC shows **n/a** unless a clustering/multilevel structure is claimed; the missing-data
  sensitivity check shows **n/a** unless the paper is longitudinal with evident dropout. A flag that fires on every
  LMM is the failure mode.
- **Coordinate honesty.** A present check's evidence link opens its page at **region** precision (page-open), never a
  fabricated exact highlight.
- **Credit-the-lineage.** Each check names its source in-context (`basis`); the panel offers the methods sources to
  the library via a working **＋ add methods sources to library**.

## Adversarial checklist

- select a metadata-only paper (no chunks) -> "Process a PDF first" (never a crash / never a fabricated result)
- select a non-LMM paper -> "doesn't appear to use a linear mixed model" (no checklist)
- `GET /papers/999999/lmm` -> 404-class, no crash
- confirm a `present` row (green ✓) AND a `not-found` row (muted, "check the paper") AND an `n/a` row all render, and
  the not-found row is NOT worded as an error/accusation
- resize to `375x812`, no horizontal overflow

## Steps

1. Open the **METHODS** pane -> **Mixed-model reporting** section. Confirm the intro (audit reporting; local/no-AI;
   "flags what's not reported, with a grounded recommendation — never a verdict").
2. Select a paper whose text uses a mixed model. The section auto-runs `GET /papers/{id}/lmm` (or click **Audit
   reporting**). Confirm the **Reporting checklist** renders per-check rows.
3. Confirm a `present` row shows `✓ present` + the always-on explainer + the in-context `basis`, and (when found) an
   evidence snippet; a `not-found` row shows the muted status + a grounded recommendation worded "not detected in the
   extracted text — check the paper".
4. Confirm **ICC** is `n/a` on a paper with no clustering claim, and the **missing-data sensitivity** check is `n/a`
   unless the paper is longitudinal with dropout (the precondition scoping — no flag on every LMM).
5. Click a present check's evidence snippet -> the PDF opens at that page at **region** precision (no exact rect).
6. Confirm the honest-scope caveat ("reporting completeness, not analysis correctness; never a verdict, never a
   score, never an accusation").
7. Confirm the **credit** block (Barr/Matuschek/Luke/Bates/Nakagawa & Schielzeth/FDA E9(R1)/Troendle/Cro/
   Moreno-Betancur) + a working **＋ add methods sources to library**.
8. Adversarial: a metadata-only paper -> "Process a PDF first"; a non-LMM paper -> "doesn't appear to use a linear
   mixed model"; 999999 -> 404-class.

## Pass criteria

- The auditor flags reporting presence/absence across the 7 checks, each with a grounded/cited recommendation, and
  routes present-check evidence to its page at region precision.
- 0 console/page errors; **0 genai-host requests** (local).
- No verdict/score/rank/accusation; ICC + missing-data are precondition-scoped (n/a when not applicable);
  "not found" ≠ "missing".
- No-chunks / non-LMM / unknown-id fail closed honestly; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_61_methods_lmm.md` + `screenshots/` (see `_TEMPLATE.md`).
