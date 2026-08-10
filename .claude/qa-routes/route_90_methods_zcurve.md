<!-- qa-coverage
api: /methods/zcurve*
fe: 29b_zcurve.jsx
-->

# ROUTE 90 - Methods: z-curve (collection-level expected replication/discovery rate)

**Tier:** 1 local-stateful
**Goal:** Exhaust the z-curve flow over a selected set of papers while preserving signal-not-verdict +
no-accusation language. z-curve is **collection-level only, never per-paper, never per-author.** Sibling to
p-curve (route 36) — same shape, but EDR/ERR are quantitative RATE estimates (more tempting to misread as
describing the specific selected studies), so this route additionally asserts the reliability warning and the
always-shown confidence intervals.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (z-curve is local/no-LLM — assert it
makes no genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** z-curve is local; ANY request to a `generativelanguage`/Gemini/genai host during a z-curve run
  is **Critical**.
- **Signal not verdict.** No composite "replicability score," no per-paper or per-author rank/label, and neither
  EDR nor ERR is ever attributed to a specific paper or author in the UI — only to the assembled selection.
- **Reliability disclosure.** Any run with k_significant < 300 shows the hard reliability warning (not a
  dismissible aside) BEFORE the EDR/ERR numbers; its absence at k < 300 is a bug.
- **Uncertainty always shown.** EDR and ERR never render without their CI beside them.
- **Inspectability.** The included tests are listed and each opens its page (region precision — page-open, no fake
  exact highlight).

## Adversarial checklist

- run z-curve on a selection with no significant inline NHST tests -> honest empty state + coverage note (no crash)
- run on a single paper -> still framed collection-level; reliability warning present; no per-paper verdict
- navigate away / close the modal mid-job; rapid re-open
- deep-link / direct GET a non-existent z-curve job id -> 404
- POST an empty paper_ids selection -> 422-class; resize to `375x812`, no horizontal overflow
- a realistically-sized selection (k_significant well under 300, the expected case at library scale) still
  renders EDR/ERR + CIs, not a blocked/refused state — the warning is a caveat, not a gate

## Steps

1. In the library (selecting mode), check several papers -> the bulk bar shows a **z-curve** action next to
   **p-curve**.
2. Click **z-curve** (`POST /methods/zcurve/run`); poll the modal (`GET /methods/zcurve/run/{job_id}`). Confirm
   the **framing** states it is collection-level and "never a score for these specific papers or their authors."
3. Confirm the result: the selection/coverage **note** ("N significant of M extracted across K papers"), the
   **reliability warning** if k_significant < 300, **EDR** (with its CI + the observed discovery rate for
   comparison) and **ERR** (with its CI), and the **null-component share**.
4. Expand the **included tests**; click one -> it opens that paper's page (region precision). Assert no fake
   exact highlight.
5. Confirm the **coverage caveat** (inline-NHST only; every significant test included rather than a chosen focal
   statistic) and the **credit** block (Bartoš & Schimmack 2022) with a working **＋ add to library** (idempotent;
   confirm via `POST /library/credit/status` before/after).
6. Adversarial: select papers with no parseable stats -> honest empty; fake job id -> 404; empty selection -> 422.

## Pass criteria

- The z-curve flow completes; the modal shows EDR/ERR + CIs + the reliability warning (when applicable) +
  included tests + coverage + credit.
- 0 console/page errors; **0 genai-host requests** (local).
- No per-paper or per-author judgment; no composite score/rank; CIs never omitted when EDR/ERR are shown.
- Empty/low-k/error states are honest; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_90_methods_zcurve.md` + `screenshots/` (see `_TEMPLATE.md`).
