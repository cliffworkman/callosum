<!-- qa-coverage
api: /papers/{paper_id}/meta-analysis, /methods/meta-analysis/run, /methods/meta-analysis/run/{job_id}, /methods/meta-analysis/summary
fe: 08g_methods_metaanalysis.jsx
-->

# ROUTE 62 - Methods: Meta-analysis reporting auditor

**Tier:** 1 local-stateful
**Goal:** Exhaust the per-paper meta-analysis-reporting auditor (the statcheck sibling for published meta-analyses)
while preserving FLAG-not-ADJUDICATE + no-accusation framing. It reads a published meta-analysis's extracted text and
flags whether it *reports* seven key methodological choices — effect-size metric, model (fixed vs random-effects),
heterogeneity (I²/τ²/Q), publication-bias assessment, sensitivity/influence analysis, the number of studies (k) +
participants, and (for a systematic review) the search & selection process. Each check is `present` / `not-found` /
`not-applicable`. **It never pools, models, re-computes, scores, or accuses.** Local, deterministic, no AI, no egress.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (the auditor is local/no-LLM — assert no
genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The auditor is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **FLAG-not-ADJUDICATE / no accusation (Critical if violated).** No composite score, no rank, no pass/fail verdict,
  no "this meta-analysis is wrong/low-quality". Statuses are present / not-found / not-applicable only; a fired flag
  carries a **grounded, cited recommendation**, never an accusation of the authors.
- **Never re-computes.** The panel shows no recomputed effect size / pooled estimate / bias-test result — it audits
  *reporting*, not analysis (Critical if it presents a re-analysis).
- **Silence ≠ certificate.** "not found" is worded **"not detected in the extracted text — check the paper"**, NEVER
  "missing" (Critical if it reads as a verdict). The honest-scope caveat ("reporting completeness, not analysis
  correctness") is stated.
- **Precondition scoping.** Search & selection shows **n/a** for a within-study "mini meta-analysis" that isn't a
  systematic review. A flag that fires on every meta-analysis is the failure mode.
- **Coordinate honesty.** A present check's evidence link opens its page at **region** precision (page-open), never a
  fabricated exact highlight.
- **Credit-the-lineage.** Each check names its source in-context (`basis`); the panel offers the methods sources to
  the library via a working **＋ add methods sources to library**.
- **Credit suppression (backlog #23 F2, Critical if violated).** The **Methods:** credit block must render ONLY
  after a paper is confirmed `is_meta_analysis:true` — never while loading, never for a non-meta paper.
- **Library-wide chip is additive, not a new verdict (backlog #23 F1).** The header **∑ Meta · N** chip counts
  papers with an *incomplete* reporting checklist — a completeness gap, never a judgment on the pooling itself.
  Clicking it filters the library (`GET /papers?signal=meta-incomplete`) exactly like the existing statcheck/
  retraction/LMM chips; it must NOT replace or hide those.

## Adversarial checklist

- select a metadata-only paper (no chunks) -> "Process a PDF first" (never a crash / never a fabricated result)
- select a non-meta paper (e.g. a single primary study) -> "doesn't appear to report a meta-analysis" (no checklist)
- `GET /papers/999999/meta-analysis` -> 404-class, no crash
- confirm a `present` row (green ✓) AND a `not-found` row (muted, "check the paper") AND (for a mini-meta) an `n/a`
  search row all render, and the not-found row is NOT worded as an error/accusation
- resize to `375x812`, no horizontal overflow

## Steps

1. Open the **METHODS** pane -> **Checklists** section -> the **Meta-analysis reporting** tab (one of a 2×2 tab
   grid: Transparency / Mixed-model / Bayesian / Meta-analysis — regrouped 2026-07-21 from its own top-level
   section, order 40, bottom-right). Confirm the intro (audit reporting; local/no-AI; "flags what's not reported
   ... never a verdict, and it never pools or re-computes").
2. Select a paper whose text reports a meta-analysis. The tab auto-runs `GET /papers/{id}/meta-analysis` (or click
   **Audit reporting**) **only while it is the selected tab** (`active` now arrives as a real `render(ctx,
   isVisible)` prop from `PaneAccordion`, not derived from `ctx.methodsOpen === "meta"` — switching to another
   Checklists tab and back must not re-trigger a spurious run). Confirm the **Reporting checklist** renders
   per-check rows.
3. Confirm a `present` row shows `✓ present` + the always-on explainer + the in-context `basis`, and (when found) an
   evidence snippet; a `not-found` row shows the muted status + a grounded recommendation worded "not detected in the
   extracted text — check the paper".
4. Confirm the publication-bias not-found note mentions the k≥10 convention (absence may be appropriate for small k),
   and the **search & selection** check is `n/a` for a within-study mini-meta (the precondition scoping — no flag on
   every meta-analysis).
5. Click a present check's evidence snippet -> the PDF opens at that page at **region** precision (no exact rect).
   With a multi-PDF paper whose evidence lives in the secondary PDF, confirm the request includes that PDF's
   `attachment_id` and does not open the primary.
6. Confirm the honest-scope caveat ("reporting completeness, not analysis correctness; never pools/models/re-computes/
   scores/accuses").
7. Confirm the **credit** block (Higgins/Egger/Duval & Tweedie/Sterne/DerSimonian & Laird/IntHout/Viechtbauer/
   Viechtbauer & Cheung/PRISMA 2020/Borenstein) + a working **＋ add methods sources to library**.
8. Adversarial: a metadata-only paper -> "Process a PDF first"; a non-meta paper -> "doesn't appear to report a
   meta-analysis"; 999999 -> 404-class.
9. **Whole-library batch (backlog #23 F1).** Above "This paper", confirm a **"Whole library"** section with an
   **Audit all papers** button. Click it -> a progress bar, then a summary ("N papers checked · M detectably a
   meta-analysis · K incomplete"). If K > 0, click the **"K incomplete"** link -> the library filters to those
   papers and the header **∑ Meta · K** chip now shows the same count.
10. **Credit suppression (F2).** Select a non-meta paper -> confirm NO "Methods:" credit block renders. Select a
   meta-analysis paper -> confirm the credit block renders only once the checklist itself has rendered.
11. **Persist-on-view (F4).** After viewing an incomplete meta-analysis paper's panel, open **Synthesize ->
   Critique** for the same paper and confirm a "meta-analysis reporting" candidate finding is listed — persisted
   from the ad-hoc view alone, no batch run required.

## Pass criteria

- The auditor flags reporting presence/absence across the 7 checks, each with a grounded/cited recommendation, and
  routes present-check evidence to its page at region precision in the evidence-bearing PDF attachment.
- 0 console/page errors; **0 genai-host requests** (local).
- No verdict/score/rank/accusation; no re-analysis shown; search & selection is precondition-scoped (n/a for a
  mini-meta); "not found" ≠ "missing".
- No-chunks / non-meta / unknown-id fail closed honestly; mobile viewport has no horizontal overflow.
- The whole-library batch completes, the chip count matches the batch summary's `incomplete`, and the chip's
  filter click shows the same papers; the credit block never renders before `is_meta_analysis` is confirmed
  true; an ad-hoc per-paper view alone (no batch) is enough to seed a Critique candidate.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_62_methods_metaanalysis.md` + `screenshots/` (see `_TEMPLATE.md`).
