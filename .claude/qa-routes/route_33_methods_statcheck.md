<!-- qa-coverage
api: GET /papers/{paper_id}/statcheck, /methods/statcheck*
fe: 06_methods_statcheck.jsx
-->

# ROUTE 33 - Methods and statcheck

**Tier:** 1 local-stateful
**Goal:** Exhaust per-paper statcheck and library-wide statcheck summary/run surfaces — now consolidated in the
METHODS pane "Statistics check" section (inc 122) — while preserving signal-not-verdict language.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open the **METHODS pane → "Statistics check"** section. Select a paper, then run its per-paper check ("This paper" → Check statistics; `GET /papers/{paper_id}/statcheck`).
2. Confirm each row shows the reported statistic (verbatim `raw`), recomputed p value, match status, and counts.
   **inc 257: the page is now surfaced INLINE on each row** as a **`p. N`** locator (mono, indigo — it was
   tooltip-only before); a test with no attributed page shows a muted **`p. —`** (`.statcheck-page-none`), never a
   fabricated page. Assert there is no composite score and no accusation.
3. Click each row with a location. Confirm coordinate honesty: the inline `p. N` opens that page at **region**
   precision (page-open, no bbox rect — statcheck has no exact coordinates); a `p. —` row has no page to open. An
   approximate/null location must never draw a fake exact highlight.
4. In the same section's "Whole library" block, start library statcheck (Check all papers; `POST /methods/statcheck/run`) and poll (`GET /methods/statcheck/run/{job_id}`). Navigate away mid-run and return.
5. After completion confirm the summary (`GET /methods/statcheck/summary`) drives the "N with inconsistencies" count and the library "⚠ N flagged" header chip; aggregate counts are transparent filters, not ranks. Click the **"⚠ N flagged" chip** (inc 141) → the library filters to flagged papers, the METHODS **Statistics check** section opens, the **top flagged paper is auto-selected**, and its per-test rows **auto-show** (no manual "Check statistics" click) — the citer lands on the specific inconsistent result, not just "which papers".
6. Directly visit a fake job id and a paper without parseable methods text. Confirm clean empty/error states. Confirm statcheck no longer appears in Settings or the Details pane (it lives only in the METHODS section now).

## Pass criteria

- Per-paper and library statcheck flows complete.
- 0 console/page errors and 0 genai-host requests.
- Counts and caveats remain non-accusatory; no hidden composite score.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_33_methods_statcheck.md` + `screenshots/` (see `_TEMPLATE.md`).

