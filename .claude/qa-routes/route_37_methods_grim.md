<!-- qa-coverage
api: /methods/grim, GET /papers/{paper_id}/grim-checks, POST /papers/{paper_id}/grim-checks, DELETE /papers/{paper_id}/grim-checks/{check_id}, /methods/debit, GET /papers/{paper_id}/debit-checks, POST /papers/{paper_id}/debit-checks, DELETE /papers/{paper_id}/debit-checks/{check_id}, /methods/duplicate-values, GET /papers/{paper_id}/duplicate-value-checks, POST /papers/{paper_id}/duplicate-value-checks, DELETE /papers/{paper_id}/duplicate-value-checks/{check_id}
fe: 07_methods_grim.jsx
-->

# ROUTE 37 - Methods: GRIM + GRIMMER + DEBIT + repeated-values (data-consistency calculators)

**Tier:** 1 local-stateful
**Goal:** Exhaust the assisted GRIM/GRIMMER/DEBIT/repeated-values calculators while preserving
signal-not-verdict + no-accusation framing. All four are **user-driven, per-value** (the user types/pastes a
reported value) — none scan, rank, or label papers.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (all three are local/no-LLM — assert no
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
8. **Inc 467 DEBIT (a second, separate mini-form below GRIM/GRIMMER in the same Data section).** Enter a
   DEBIT-consistent binary case (mean **0.500**, SD **0.527**, N **10**) -> **Check** (`POST /methods/debit`) ->
   confirm **consistent**. Enter an inconsistent SD (e.g. SD **0.999** for the same mean/N) -> confirm
   **impossible** with the binary-data caveat, never a verdict on the paper/author. Confirm the credit block
   (Heathers & Brown 2019) links to the OSF page (no fabricated DOI) and offers **＋ add to library**. Repeat the
   save/list/delete/paper-switch checks from step 7 against `/papers/{paper_id}/debit-checks` — confirm the same
   paperId-reset behavior (no stale form/result bleeding across a paper switch) since this is new code, not a
   copy that inherited the inc-401 fix for free.
9. **Inc 469 repeated-values (a third block below DEBIT, deliberately weaker framing).** Paste values with a
   repeat (e.g. `3.45`, `3.45`, `3.45`, `2.10`, `5.00`, one per line or comma-separated) -> **Check**
   (`POST /methods/duplicate-values`) -> confirm a **plain list** `3.45 x 3` — **critically, no `cite-status`
   verified/flagged pill anywhere in this block** (unlike GRIM/GRIMMER/DEBIT above) and the note explicitly
   states this is "a blunt heuristic with no peer-reviewed method behind it, unlike GRIM/GRIMMER/DEBIT." Paste
   values with no repeats -> confirm "No exact value repeats more than once." Confirm the credit line is
   **text-only** — no `MethodCreditButton`/"add to library" affordance anywhere in this block (there is no
   citable paper, only a software reference to `scrutiny`) — while the section's own shared `LakensCredit`
   block (now at the very end of Data, after all three sub-tools) still renders its own button correctly.
   Repeat the save/list/delete/paper-switch checks from step 7 against
   `/papers/{paper_id}/duplicate-value-checks`. Adversarial: empty input, 501+ values, an oversized label ->
   422-class, no crash.

## Pass criteria

- All calculators compute correctly: GRIM (+ GRIMMER when SD given), DEBIT, and repeated-values, each with
  their own caveats + credit.
- 0 console/page errors; **0 genai-host requests** (local).
- No per-paper/per-author judgment, no score/rank; "impossible" is a prompt, not a verdict. The repeated-values
  block in particular renders **no pill/verdict at all**, only a plain frequency list — its own credit line is
  text-only, never an "add to library" button (no citable paper exists for it).
- Bad inputs fail closed (422-class); mobile viewport has no horizontal overflow.
- Saved checks (GRIM/GRIMMER, DEBIT, and repeated-values) are correctly paper-scoped, survive a refresh, and
  are removable; a saved verdict always matches a fresh server-side recomputation of the same inputs (never a
  trusted client-side value).

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_37_methods_grim.md` + `screenshots/` (see `_TEMPLATE.md`).
