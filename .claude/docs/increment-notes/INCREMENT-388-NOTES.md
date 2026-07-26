# Increment 388 — attachment-aware Methods evidence navigation

**Date:** 2026-07-26
**Status:** implemented; local gates complete

## Outcome

The attachment-awareness follow-up from backlog #5 is closed for every Methods surface that actually carries
page-anchored paper evidence. Statcheck, Bayesian, mixed-model, meta-analysis, and transparency responses now
retain the PDF attachment that supplied their matched evidence. Their shared source-jump target opens that exact
attachment, including a secondary PDF preserved by a paper merge, at the existing exact or region precision.

Non-PDF evidence deliberately omits its attachment id from the PDF target and retains the established
primary-PDF degradation. GRIM/GRIMMER is user-entered and stateless, and reference-integrity rows describe
external reference records rather than page-anchored evidence, so neither has an applicable source attachment.
The in-app Cite pane's separate suggestion object remains a small filed follow-up.

## Architecture and boundaries

- `methods/evidence_anchors.py` owns the common evidence contract. It resolves a bounded set of chunk attachment
  ids in one query and retains only database records typed as PDF.
- `anchor_evidence` returns `attachment_id` alongside page range, precision, and rectangles on every path. A
  located exact quote and a region fallback both keep the same PDF attachment; unmatched/non-PDF evidence does
  not invent one.
- Statcheck retains its table/prose attachment provenance and filters it through the same PDF-type helper.
- Bayesian recompute, Bayesian completeness/advisories, mixed-model, meta-analysis, and transparency response
  models expose the optional id and precompute their paper's PDF id set once.
- `methodEvidenceTarget` is the single frontend bridge into `PdfViewer`; statcheck now uses that bridge instead
  of maintaining a parallel target object.
- `GET /papers/{paper_id}/pdf?attachment_id=` remains the only serving path. It already rejects an attachment
  that is stale, unavailable, non-PDF, or belongs to another paper.
- There is no new endpoint, migration, dependency, persistence, file write, egress, or LLM use.

## User experience

For a merged paper with a primary article and a secondary supplement, clicking Methods evidence now lands in
the document that actually supplied the quote or table row. Exact/region labeling and highlighting behavior are
unchanged; the improvement is choosing the right source document before applying those coordinates.

A skeptical synthesizer's goal-in-the-moment pass asked: “If this result came from the supplement, does Inspect
evidence actually take me to the supplement?” The real-browser statcheck path confirms the click requests the
secondary attachment id, with zero console/page errors. The intended next action—inspect the original
row/passage—is now trustworthy. The viewer tab still names the paper rather than the active attachment, so a
low-priority active-attachment label is filed in backlog #5 rather than expanding this contract change.

## Manual verification

1. Merge or create a paper with distinguishable primary and secondary PDF attachments.
2. Put page-anchored statcheck, Bayesian, mixed-model, meta-analysis, or transparency evidence in the secondary.
3. Open the applicable **METHODS** panel and click the evidence quote/row.
4. Confirm the PDF request includes the secondary `attachment_id` and opens that document.
5. Confirm exact evidence draws its real rectangles; region evidence opens the correct page without a fake rect.
6. Repeat with evidence from a non-PDF attachment and confirm its id is not sent to the PDF route.

## Verification

- Focused Methods/frontend suite: **169 passed**.
- Chromium smoke: **5 passed**, including an actual statcheck evidence click that requests the secondary PDF;
  zero console/page errors.
- Alembic upgrade/model-drift tests: **3 passed**.
- Ruff check/format, 393-file source line budget, frontend build/assembly, help sync, and diff hygiene: pass.
- QA surface map: **312/312 API** and **1378/1399 frontend**; the 21 frontend items remain explicitly
  report-only and every gated surface is claimed.
- Full project suite: **1609 passed, 1 skipped** in 1694.68 seconds.
