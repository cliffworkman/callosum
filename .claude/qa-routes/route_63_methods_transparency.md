<!-- qa-coverage
api: /papers/{paper_id}/transparency
fe: 08h_methods_transparency.jsx
-->

# ROUTE 63 - Methods: Transparency-signals auditor

**Tier:** 1 local-stateful
**Goal:** Exhaust the per-paper transparency-signals auditor (the statcheck/meta sibling that detects open-science
disclosures) while preserving FLAG-not-ADJUDICATE + the load-bearing no-accusation framing. It reads a paper's
extracted text and detects whether it *discloses* seven open-science artifacts — data availability, code / software
availability, a conflict-of-interest statement, a funding statement, protocol/trial registration, preregistration, and
an "available upon request" weak-signal qualifier. Each check is `present` / `not-found` / `not-applicable`. **It never
scores, ranks, or accuses; "not detected" never means "absent".** ODDPub/rtransparent-derived, local, rule-based, no
AI, no egress.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (the auditor is local/no-LLM — assert no
genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The auditor is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **FLAG-not-ADJUDICATE / no accusation (Critical if violated).** No composite/transparency score, no rank, no
  pass/fail verdict, no "this paper hides its data / has an undisclosed conflict / did no open science". Statuses are
  present / not-found / not-applicable only.
- **Silence ≠ certificate (Critical if it reads as an accusation).** A `not-found` row is worded **"not detected in the
  extracted text — check the paper"**, NEVER "absent" / "missing" / "concealed" / "no open data" / "not shared". The
  honest-scope caveat ("detects reported disclosures, does not judge a paper's openness; a statement can live in an
  appendix / footnote / structured metadata this reader doesn't fully see") is stated.
- **Weak signal, not a flag.** The `upon_request` row (when present) is shown as a legibility note ("a weaker signal
  than an open link, not a concern in itself"), never an accusation.
- **Precondition scoping.** **Registration** shows **n/a** for a non-trial / non-review design (a registration flag on
  every paper is the failure mode). **Available upon request** shows **n/a** when the phrase is absent (never
  "not found").
- **Coordinate honesty.** A present check's evidence link opens its page at **region** precision (page-open), never a
  fabricated exact highlight.
- **Credit-the-lineage.** The detectors name their source in-context (`basis` + the credit block); the panel offers the
  methods sources to the library via a working **＋ add methods sources to library**.

## Adversarial checklist

- select a metadata-only paper (no chunks) -> "Process a PDF first" (never a crash / never a fabricated result)
- `GET /papers/999999/transparency` -> 404-class, no crash
- confirm a `present` row (green ✓ detected) AND a `not-found` row (muted, "not detected ... check the paper") AND (for
  a non-trial paper) an `n/a` registration row all render, and the not-found row is NOT worded as an error/accusation
- resize to `375x812`, no horizontal overflow

## Steps

1. Open the **METHODS** pane -> **Transparency signals** section (order 36, among the real tools). Confirm the intro
   (detect open-science disclosures; local/no-AI; "surfaces what's reported ... never a transparency score, and
   'not detected' never means the artifact is absent").
2. Select a paper whose text has an open-science footer (data/code links, COI, funding, (pre)registration). The section
   auto-runs `GET /papers/{id}/transparency` (or click **Check disclosures**). Confirm the **Open-science disclosures**
   checklist renders 7 rows + a factual tally line ("N disclosed · M not detected · K not applicable · 7 checks" —
   explicitly not a score).
3. Confirm a `present` row shows `✓ detected` + the always-on explainer + the in-context `basis`, and (when found) an
   evidence snippet; a `not-found` row shows the muted status + a note worded "not detected in the extracted text —
   check the paper" (never "missing"/"absent"/an accusation).
4. Confirm **Registration** is `n/a` for a non-trial paper (precondition scoping — no flag on every paper), and
   **Available upon request** is `n/a` when the phrase is absent.
5. Click a present check's evidence snippet -> the PDF opens at that page at **region** precision (no exact rect).
6. Confirm the honest-scope caveat (reported disclosures, not a judgment of openness; "not detected" ≠ "absent";
   never a score/accusation; upon-request = a weaker signal, not a concern).
7. Confirm the **credit** block (ODDPub — Riedel et al. 2020; rtransparent — Serghiou et al. 2021; preregistration —
   Nosek et al. 2018) + a working **＋ add methods sources to library**.
8. Adversarial: a metadata-only paper -> "Process a PDF first"; 999999 -> 404-class.

## Pass criteria

- The auditor detects disclosure presence/absence across the 7 checks, each with the in-context basis, and routes
  present-check evidence to its page at region precision.
- 0 console/page errors; **0 genai-host requests** (local).
- No verdict/score/rank/accusation; "not detected" ≠ "absent"; registration + upon-request are precondition-scoped
  (n/a where inapplicable); the upon-request row reads as a weak signal, not a flag.
- No-chunks / unknown-id fail closed honestly; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_63_methods_transparency.md` + `screenshots/` (see `_TEMPLATE.md`).
