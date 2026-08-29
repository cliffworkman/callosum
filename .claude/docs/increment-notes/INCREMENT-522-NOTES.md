# Increment 522 — Word batch bibliography categories

**Date:** 2026-08-28
**Scope:** Word P1 bibliography item #11, second bounded slice: assign or remove one category across selected cited works.

## User behavior

After **Citations in this document…** scans the document, every resolvable cited work has a real checkbox. The
compact batch bar reports the independent selection and provides:

- **Select visible** — add every resolvable work in the current search result;
- **Clear** — reset the selection;
- **Set selected category…** — open the existing category editor for the selected works.

Filtering changes what is visible, not which works remain selected. One save applies or removes one category across
the whole selection, refreshes once, clears a successful batch selection, and updates the panel badges. Individual
**Set category…** actions remain unchanged and use the same transaction underneath.

## Transaction and safety contract

The pure batch helper accepts numeric `callosum-<paperId>` identities only, deduplicates them, and caps a batch at
1,000 works. It canonicalizes an existing label case-insensitively, produces one new immutable assignment map,
persists once, and invokes the existing Refresh once. A persistence or rendering failure restores the whole prior
map; there is no repeated single-work save/refresh loop and no partial-success state.

If selected works have different current categories, the editor begins with no implied value. An untouched blank
cannot erase the selection: the user must type/choose a label or click the explicit **Remove category** action.
Single-work and uniform-batch blank-removes behavior from inc 521 remains intact.

## Product boundaries

- Explicit checkbox selection is author intent, not inferred classification, recommendation, or ranking; the
  Principles gate is non-triggering.
- No endpoint, provider, prompt, citation rendering, verification, egress, permission, dependency, or migration
  changes.
- Selection is process-local UI state only. The category map remains the sole saved document metadata, and Word's
  authoritative citation controls remain the source of the panel on every scan.
- Custom category order, chapter/section bibliography blocks, uncited membership, and category links remain later
  increments.

## Experience pass

Local deadline-author walkthrough (delegation is disabled): checkbox selection makes batch membership visible,
Select-visible composes with search rather than inventing a second filter model, the count remains visible when
selected rows are filtered away, and one editor prevents repeated naming. The cheap safety fix was requiring a
positive choice for mixed selections instead of letting the blank initial field silently remove categories.

## Automated verification

Final automated gates passed:

- Word pure logic: **48/48** (`node --test adapters/word/taskpane_core.test.js`).
- Focused Word/access/citation/help pytest: **96 passed** in 111.21s.
- Full repository suite: **2563 passed, 3 skipped** in 966.30s (16m06.30s;
  `pytest -n auto -q --tb=short`).
- JavaScript syntax checks passed for `taskpane.js` and `taskpane_core.js`.
- Scoped Ruff check/format, Bandit, Tach, 569-file line-budget, QA surface map, website coverage, and
  `git diff --check` passed.

The pure suite covers batch deduplication, canonicalization, immutable application and removal, empty selection,
invalid identity rejection, the 1,000-work cap, unchanged single-work delegation, static checkbox/batch-control
wiring, the mixed-selection guard, and the shared one-refresh path.

## Honest verification boundary

No available agent can drive real Word. Checkbox interaction, search plus Select-visible, mixed/uniform editor
state, one-refresh behavior, failure rollback, save/reopen, and desktop/web layout are **not yet live-verified**.
Per the maintainer's request, these are recorded now and will be consolidated with inc 521 and the rest of the arc
into one manual verification checklist after the Word work is complete.

## Manual Word verification owed

1. Scan a document with at least five resolvable cited works; select individual rows and confirm the count.
2. Filter to a subset, choose **Select visible**, clear the filter, and confirm prior plus newly visible selection.
3. Batch-assign one existing label; confirm one refresh, updated badges, cleared selection, and grouped bibliography.
4. Select works with different categories; confirm Save starts disabled until a label is entered, while explicit
   **Remove category** remains available.
5. Batch-remove a uniform category and confirm only selected works move to **Other references**.
6. Change the search while selection exists; confirm hidden selections remain counted and **Clear** resets all.
7. Force a refresh failure and confirm the complete prior category map and rendered layout remain/restores.
8. Repeat the core path with note-style citations and in Word on the web.

## Next

Add explicit document-local category ordering, then heading-scoped bibliography blocks.
