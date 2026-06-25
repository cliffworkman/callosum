<!-- qa-coverage
api: /methods/pcurve*
fe: 29_pcurve.jsx
-->

# ROUTE 36 - Methods: p-curve (collection-level evidential value)

**Tier:** 1 local-stateful
**Goal:** Exhaust the p-curve flow over a selected set of papers while preserving signal-not-verdict +
no-accusation language. p-curve is **collection-level only, never per-paper, never "p-hacked."**

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (p-curve is local/no-LLM — assert it
makes no genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** p-curve is local; ANY request to a `generativelanguage`/Gemini/genai host during a p-curve run
  is **Critical**.
- **Signal not verdict.** No composite "evidential value score", no rank, no per-paper or per-author judgment, and
  the word "p-hacked"/"p-hacking" must NOT appear as a label applied to any paper or person. The curve is
  presented for the user to interpret.
- **Inspectability.** The included tests are listed and each opens its page (region precision — page-open, no fake
  exact highlight).

## Adversarial checklist

- run p-curve on a selection with no significant inline NHST tests -> honest empty state + coverage note (no crash)
- run on a single paper -> still framed collection-level; no per-paper verdict
- navigate away / close the modal mid-job; rapid re-open
- deep-link / direct GET a non-existent p-curve job id -> 404
- POST an empty paper_ids selection -> 422-class; resize to `375x812`, no horizontal overflow

## Steps

1. In the library (selecting mode), check several papers -> the bulk bar shows a **p-curve** action.
2. Click **p-curve** (`POST /methods/pcurve/run`); poll the modal (`GET /methods/pcurve/run/{job_id}`). Confirm
   the **framing** states it is collection-level and "not a verdict … never describes any single paper or author."
3. Confirm the result: the selection/coverage **note** ("N significant of M extracted across K papers"), the
   **SVG curve** (bars at .01-.05 + the dashed 20% null line), the **right-skew** (Z, p) + **binomial** statistics
   phrased descriptively (consistent-with-evidential-value vs not — never "good/bad paper").
4. Expand the **included tests**; click one -> it opens that paper's page (region precision). Assert no fake exact
   highlight.
5. Confirm the **coverage caveat** (inline-NHST only; can't pick the focal test; small-k unreliable;
   rounds-to-0 dropped) and the **credit** block (Simonsohn, Nelson & Simmons 2014) with a working
   **＋ add to library** (idempotent).
6. Adversarial: select papers with no parseable stats -> honest empty; fake job id -> 404; empty selection -> 422.

## Pass criteria

- The p-curve flow completes; the modal shows the curve + statistics + included tests + coverage + credit.
- 0 console/page errors; **0 genai-host requests** (local).
- No per-paper or per-author judgment; no "p-hacked" label; no composite score/rank.
- Empty/low-k/error states are honest; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_36_methods_pcurve.md` + `screenshots/` (see `_TEMPLATE.md`).
