# Increment 523 — Word custom bibliography category order

**Date:** 2026-08-28
**Scope:** Word P1 bibliography item #11, third bounded slice: explicit document-local precedence for active named groups.

## User behavior

After the document-citations panel finds at least two active named categories, **Category order…** opens a staged
editor. Every row has explicitly labelled Move-up and Move-down buttons; **Reset alphabetical**, **Save order**,
and **Cancel** complete the interaction without requiring drag-and-drop.

Configured active groups lead in the saved order. A category created later—or otherwise absent from the saved
precedence—follows configured groups alphabetically until the author saves another order. **Other references** is
generated from unassigned/mixed entries, never appears as an orderable row, and remains last.

Reset stages the alphabetical list; Reset plus Save removes the custom-order setting and restores inc 521's exact
default behavior. Cancel and Escape discard the draft without touching document metadata or content.

## Metadata and rendering contract

`callosumBibliographyCategoryOrder` is a separate Word document setting: a JSON array bounded to 50 unique valid
category labels and 8,192 serialized characters. Read-time corruption, duplicates, reserved/blank labels, and
oversized values degrade to the alphabetical default. Write-time drafts validate strictly.

The editor lists active categories from the freshly scanned cited-work panel, not every stale assignment remaining
in saved metadata. Rendering applies configured precedence only to currently produced named groups; stale order
labels are harmless and new/unranked groups fall back alphabetically. Citeproc's existing entry text and order stay
unchanged inside each group.

Save persists once and invokes the existing whole-document Refresh once. If persistence or rendering fails, Word
restores the exact prior raw order setting—including a corrupt value—rather than normalizing history during
rollback. Flatten's optional citation-settings cleanup now removes both membership and precedence metadata.

## Product boundaries

- Group order is explicit author organization, not importance, recommendation, or quality; the Principles gate is
  non-triggering.
- No endpoint, provider, prompt, citeproc, scientific validation, egress, permission, dependency, or migration
  changes.
- Category membership remains inc 521/522 metadata. This increment adds no inferred membership, uncited works,
  links, heading detection, or section bibliography.

## Experience pass

Local deadline-author walkthrough (delegation is disabled): each movement is explicit and immediately visible,
boundary buttons disable rather than silently wrap, reset is staged/cancellable, the Other group is correctly
absent, and the editor stays unavailable until two active groups exist. The cheap correctness fix was deriving the
list from the current panel rather than stale saved assignments.

## Automated verification

Final automated gates passed:

- Word pure logic: **50/50** (`node --test adapters/word/taskpane_core.test.js`).
- Focused Word/access/citation/help pytest: **96 passed** in 116.40s.
- Full repository suite: **2563 passed, 3 skipped** in 960.77s (16m00.77s;
  `pytest -n auto -q --tb=short`).
- JavaScript syntax checks passed for `taskpane.js` and `taskpane_core.js`.
- Scoped Ruff check/format, Bandit, Tach, 569-file line-budget, QA surface map, website coverage, and
  `git diff --check` passed.

The pure suite covers bounded fail-soft reads, strict writes, duplicate/reserved/excessive rejection, configured
precedence, stale/new alphabetical fallback, custom render order, per-group stability, and Other-last. Static
wiring covers active-only editor controls, reset/save/cancel, one Refresh, and exact rollback.

## Honest verification boundary

No available agent can drive real Word. Move/reset/cancel interaction, save/reopen persistence, current-group
derivation, layout, failure rollback, desktop Word, and Word-on-the-web behavior are **not yet live-verified**.
Per the maintainer's request, these checks will be consolidated with incs 519-522 into the arc-level manual
verification checklist after the remaining Word work is complete.

## Manual Word verification owed

1. Create at least three active named groups and open **Category order…**.
2. Move the last group to the first position; confirm boundary buttons disable and Save changes headings only.
3. Confirm citeproc entry order/text inside each group and **Other references** last remain unchanged.
4. Save/reopen and Refresh; confirm custom order survives in both in-text and note-style documents.
5. Add a new category; confirm it follows configured groups alphabetically until explicitly positioned.
6. Remove every cited work from one configured category; confirm the stale label disappears from the editor/render.
7. Stage moves then Cancel/Escape; confirm metadata and layout remain unchanged.
8. Reset alphabetical then Save; confirm the custom order setting is removed and alphabetical layout returns.
9. Force Refresh failure after Save; confirm the exact prior raw setting and rendered order remain/restores.
10. Repeat the core path in Word on the web.

## Next

Implement heading-scoped bibliography blocks as the remaining bibliography item #11 architecture increment.
