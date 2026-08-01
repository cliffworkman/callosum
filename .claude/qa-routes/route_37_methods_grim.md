<!-- qa-coverage
api: /methods/grim, GET /papers/{paper_id}/grim-checks, POST /papers/{paper_id}/grim-checks, DELETE /papers/{paper_id}/grim-checks/{check_id}
fe: 07_methods_grim.jsx
-->

# ROUTE 37 - Methods: GRIM + GRIMMER (data-consistency calculator)

**Tier:** 1 local-stateful
**Goal:** Exhaust the assisted GRIM/GRIMMER calculator while preserving signal-not-verdict + no-accusation framing.
It is **user-driven, per-value** (the user types a reported value) — it never scans, ranks, or labels papers.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (GRIM is local/no-LLM — assert no
genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** GRIM is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Signal not verdict / no accusation.** No score, no rank, no per-paper or per-author judgment; "impossible" is
  framed as "a prompt to look, not a verdict" with the integer-scale assumption stated; the **nearest possible**
  values are shown so the result is inspectable.

## Adversarial checklist

- enter a non-numeric mean / SD; n = 0 or negative; absurdly large n -> 422-class / clean handling, no crash
- enter only a mean (no SD) -> GRIM only, no GRIMMER row
- items > 1 with an SD -> GRIM runs; GRIMMER says multi-item unsupported (honest), not a crash
- a mean where N is large for the precision -> the no-power caveat appears
- resize to `375x812`, no horizontal overflow

## Steps

1. Open the **METHODS** pane -> **Data** section (relabeled from "Data consistency (GRIM)" 2026-07-21 when the
   pane was regrouped into Details/Data/Statistics/Checklists; same section id/content). Confirm the form (mean,
   SD, N, items) + the integer-scale intro.
2. Enter an impossible mean (e.g. mean **3.48**, N **20**) -> **Check** (`POST /methods/grim`). Confirm GRIM
   **impossible** + **nearest possible 3.45 / 3.50** + the non-accusatory caveat.
3. Enter a consistent mean + SD (e.g. **5.23 / 2.55 / 31**) -> GRIM **consistent** and GRIMMER **consistent**.
4. Enter a large-N case -> the **no-power** caveat appears (GRIM consistent but uninformative).
5. Confirm the **credit** block (Brown & Heathers 2017; GRIMMER Anaya/Allard) + a working **＋ add to library**.
6. Adversarial: n=0 / non-numeric -> 422-class, no crash; items>1 + SD -> GRIMMER "not supported", GRIM still runs.
7. **Inc 401 saved checks (paper-aware now — `ctx.selectedPaper`, previously not threaded in at all).** With a
   paper selected, run a Check, then click **"Save this check"** (`POST /papers/{paper_id}/grim-checks` —
   confirm the server RE-COMPUTES the verdict from the raw mean/SD/N/items rather than trusting whatever the
   live "Check" already showed). Confirm the saved entry appears in a list below the form with its label (or a
   default "mean/SD/N" description), consistent/impossible pill, and date. Switch to a different paper and back
   — confirm the saved list is correctly scoped (empty for the new paper, the same entries reappear for the
   original). Delete a saved entry (×) — confirm it's removed and stays removed after a hard refresh
   (`DELETE /papers/{paper_id}/grim-checks/{check_id}`). Running "Check" WITHOUT clicking Save must never add
   anything to the saved list (scratch values stay scratch). Confirm the whole Data section — saved list
   included — is absent under `CALLOSUM_READ_ONLY=1` (unchanged `hideInReadOnly`).

## Pass criteria

- The calculator computes GRIM (+ GRIMMER when SD given) with nearest-possible + caveats + credit.
- 0 console/page errors; **0 genai-host requests** (local).
- No per-paper/per-author judgment, no score/rank; "impossible" is a prompt, not a verdict.
- Bad inputs fail closed (422-class); mobile viewport has no horizontal overflow.
- Saved checks are correctly paper-scoped, survive a refresh, and are removable; a saved verdict always matches
  a fresh server-side recomputation of the same inputs (never a trusted client-side value).

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_37_methods_grim.md` + `screenshots/` (see `_TEMPLATE.md`).
