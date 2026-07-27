<!-- qa-coverage
api: GET /papers/{paper_id}/statcheck, GET /papers/{paper_id}/statcheck/cached, POST /papers/{paper_id}/statcheck/rescan, /methods/statcheck*
fe: 00_lib.jsx, 06_methods_statcheck.jsx
-->

# ROUTE 33 - Methods and statcheck

**Tier:** 1 local-stateful
**Goal:** Exhaust per-paper and library-wide statcheck surfaces, including conservative table-aware extraction
from supported attachments — consolidated in the METHODS pane "Statistics" section (inc 122; relabeled from
"Statistics check" 2026-07-21) — while preserving provenance and signal-not-verdict language.

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

1. Open the **METHODS pane → "Statistics"** section. **Inc 400: selecting a paper shows its CACHED result
   immediately (`GET /papers/{paper_id}/statcheck/cached`) — confirm this never fires a live recompute.** For a
   never-checked paper, run its per-paper check ("This paper" → Check statistics → `POST .../rescan`); the
   control **stays visible permanently** afterward, now labeled "Rescan," alongside an "as of &lt;date&gt;" line.
   Switch to a different paper and back — confirm the same cached result reappears instantly with no spinner.
2. Confirm each prose row shows the reported statistic (verbatim `raw`), recomputed p value, match status, and
   counts. With a PDF/JATS/XML/HTML/DOCX/ODT fixture containing a clearly headed result table, confirm a
   **TABLE N · ROW N** source badge appears, the reconstructed `header | row` evidence remains visible, and the
   coverage line reports attachments/pages/tables/rows/table results. Unlabeled or ambiguous columns must not
   produce a result.
   **inc 257: the page is now surfaced INLINE on each row** as a **`p. N`** locator (mono, indigo — it was
   tooltip-only before); a test with no attributed page shows a muted **`p. —`** (`.statcheck-page-none`), never a
   fabricated page. Confirm the bounded source/context quote uses the shared `EvidenceQuote` primitive (`00_lib.jsx`):
   precision is visible before the jump, the quote stays inside the row, and any clickable evidence opens source
   evidence rather than acting as a verdict. Assert there is no composite score and no accusation.
3. Click each row with a location. Confirm coordinate honesty: prose opens at its existing exact/region/null
   precision. A PDF table row opens at **region** precision using its retained table-row bbox; it never becomes
   an exact quote match. A non-PDF table row with no page shows `p. —` and has no page action. An approximate or
   absent location must never draw a fake exact highlight. In a multi-PDF paper whose result came from the
   secondary PDF, confirm the source request includes `?attachment_id=<secondary id>` and opens that PDF rather
   than the primary.
4. In the same section's "Whole library" block, start library statcheck (Check all papers; `POST /methods/statcheck/run`) and poll (`GET /methods/statcheck/run/{job_id}`). Navigate away mid-run and return.
5. After completion confirm the summary (`GET /methods/statcheck/summary`) drives the "N with inconsistencies" count and the library "⚠ N flagged" header chip; aggregate counts are transparent filters, not ranks. Click the **"⚠ N flagged" chip** (inc 141) → the library filters to flagged papers, the METHODS **Statistics** section opens, the **top flagged paper is auto-selected**, and its per-test rows **auto-show** (no manual "Check statistics" click) — the citer lands on the specific inconsistent result, not just "which papers". **Inc 400: this now works because the batch run warms the per-paper cache for every paper it touches (flagged and clean alike) — confirm the auto-shown rows come from that cache (an "as of" line matching the batch's run time), not a fresh recompute fired by opening the section.**
6. **Inc 400 staleness hint.** After a per-paper check, reprocess that paper's PDF (Detail pane). Reopen
   Statistics for it — confirm an amber "may be stale — paper reprocessed since" hint appears **beside** the
   still-displayed OLD result (never blocking it, never auto-refreshing). Click Rescan → hint clears, "as of"
   updates, and the newly recomputed rows display. Confirm the stale hint never appears for a paper that hasn't
   changed since its last check.
7. Directly visit a fake job id and papers with (a) no parseable methods text, (b) an ambiguous/multi-p-value or
   incomplete table, (c) a malformed supported attachment, and (d) more than eight supported attachments.
   Confirm clean empty/error states, prose results survive an attachment failure, skipped/truncated coverage is
   explicit, and work remains bounded. Confirm statcheck no longer appears in Settings or the Details pane.

## Pass criteria

- Per-paper and library statcheck flows complete.
- Clearly headed table evidence is attributable; ambiguous rows fail closed; scan caps are visible.
- Located prose/table evidence from a secondary PDF opens that exact attachment.
- 0 console/page errors and 0 genai-host requests.
- Counts and caveats remain non-accusatory; no hidden composite score.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_33_methods_statcheck.md` + `screenshots/` (see `_TEMPLATE.md`).
