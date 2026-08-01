# Increment 432 — inspectable registration comparison UI

**Date:** 2026-07-31
**Status:** implemented

## Outcome

The Transparency panel now carries the complete reader-controlled path from detected reference to candidate choice,
confirmed acquisition, version selection, local comparison, side-by-side evidence inspection, review, correction, and
stale re-run. The surface remains a crosswalk for human inspection and never becomes a paper or author verdict.

## Interaction design

- Panel state is explicit: no link; candidates need choice; linked/not acquired; attached/not compared; comparison
  running; compared/items to inspect; stale; provider unavailable; or incorrect registration match.
- A stored version offers **Compare now**; a saved run offers **Re-run comparison**. The user controls relevant-
  supplement inclusion and whether weak bounded searches may expand beyond expected sections.
- A version selector appears when history contains multiple immutable registrations. The exact hash/date and pipeline
  basis remain visible. The stored OSF rendering can be inspected inline; AsPredicted/manual PDFs can open as their
  own attachment independently of the paper.
- Crosswalk rows use two equal evidence columns on desktop and one stacked column on phone widths. Registration and
  publication passages remain visible together, with source-open actions where anchors exist.
- Each row shows canonical field, bounded status, optional timing detail, why it surfaced, sections searched,
  expansion/supplement/study scope, uncertainty, and actions to mark reviewed, dismiss, or save a private note.
- Stale state names the changed basis and keeps prior evidence/review state visible. An incorrect-match action rejects
  the link, visibly stales saved comparisons, and backend validation refuses new comparisons until another link is
  confirmed.
- When no difference flags surface, the state says to review the crosswalk and explicitly denies a positive
  certificate. Indigo/amber/neutral tokens communicate provenance/inspection; aligned rows do not become a green
  “passed” report card.

## Experience pass

Code/help-grounded walkthrough as a reader checking an outcome before citing it: the path begins where the existing
preregistration disclosure already appears; each state exposes one next action; comparison rows keep both quotes in
view; source actions return to the exact attachment/page; review notes do not alter evidence; stale/incorrect matches
have a recovery route. Fixes made during the pass: raw registration inspection, direct registration-PDF opening,
version selection, per-row save errors, explicit no-certificate empty state, and backend rejection after an incorrect
match. No remaining blocking dead end was found. A larger center workspace can be considered if real-world crosswalks
make the Methods pane too narrow; the responsive stacked view is sufficient for this increment.

## Evaluation and security

- Curated manifest: `tests/fixtures/registration_evaluation_cases.json`.
- Separate dimensions: `.claude/evaluations/registration-workflow.md`; no composite metric.
- End-to-end audit: `.claude/security-audits/2026-07-31_registration-comparison-workflow.md` — **PASS**.

## Verification

- Focused registration/UI suite: **116 passed**.
- Full parallel suite: **1766 passed, 1 skipped**.
- Computed QA surface map: **351/351 API** and **1537/1537 frontend**, zero uncovered.
- Ruff format/check, frontend rebuild, line-budget, and diff-hygiene gates: clean.

## Rollback

Revert Increment 432's frontend/tests/docs changes. No migration was added. Keep Increment 431 data: removing the UI
must not delete saved crosswalk evidence, notes, or review state. Earlier APIs remain independently usable.
