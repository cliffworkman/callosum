# Increment 521 — Word categorized bibliographies

**Date:** 2026-08-28
**Scope:** Word P1 bibliography item #11, first bounded slice: one document-local category per cited work.

## User behavior

**Citations in this document…** now gives every resolvable cited work a **Set category…** action. The compact
inline editor accepts a new label or reuses labels already saved in the Word document; blank or **Remove
category** clears the assignment. The panel shows the current category and its search box matches category names.

Once at least one visible bibliography entry is categorized:

- named groups sort alphabetically;
- citeproc's existing order remains unchanged inside each group;
- unassigned or ambiguously multi-source entries remain visible under **Other references**;
- removing the final visible assignment restores citeproc's exact ordinary bibliography text.

Assignments persist through Word document settings and refresh/save/reopen. This slice intentionally covers cited
works only; Word does not yet expose LibreOffice's include-uncited/exclude-cited controls.

## Rendering and identity contract

The backend was already complete. `/citations/render-document` returns aligned `bibliography_text` and
`bibliography_entry_ids`; the Word adapter groups those already-rendered entries without changing their text or
re-rendering individual works. A rendered entry is categorized only when every item id in that entry resolves to
the same explicit document assignment. Missing or misaligned entry identity fails closed instead of guessing.

The map is keyed only by the existing `callosum-<paperId>` stamp—never the unreliable source CSL id. It is bounded
to 1,000 assignments, 50 case-insensitive labels, 80 characters per label, and 131,072 serialized characters.
Control characters and the reserved **Other references** label are rejected. Corrupt or excessive saved metadata
degrades to no categories; a failed refresh restores the previous saved map.

## Product boundaries

- Categories are explicit author organization, not an inferred importance, ranking, or recommendation; the
  Principles gate is non-triggering.
- No endpoint, provider, prompt, citeproc logic, scientific verification, egress, dependency, migration, or
  permission changes.
- QA route 35 continues to own the served Word assets/zero-egress contract and records the category surface's
  static Node guard; actual Word-host interaction remains manual.
- No chapter/section bibliography, batch assignment, custom category order, uncited-work membership, heading
  control, or links are added here. Those remain separate increments.
- Clearing Callosum citation settings during Flatten also clears category metadata; ordinary Flatten retains it.

## Experience pass

Local deadline-author walkthrough (delegation is disabled): the action lives beside the work in the existing
document-citations panel, existing labels are suggested, current membership is visible, and removal is explicit.
The user never sees paper ids or entry-id alignment. The cheap fix applied in this increment was making category
names searchable in the panel. Batch assignment is the first material remaining friction and stays the next
increment rather than being hidden inside this slice.

## Automated verification

Final automated gates passed:

- Word pure logic: **47/47** (`node --test adapters/word/taskpane_core.test.js`).
- Focused Word/access/citation/help pytest: **96 passed** in 91.56s.
- Full repository suite: **2563 passed, 3 skipped** in 962.76s (16m02.76s;
  `pytest -n auto -q --tb=short`).
- JavaScript syntax checks passed for `taskpane.js` and `taskpane_core.js`.
- Scoped Ruff check/format, Bandit, Tach, 569-file line-budget, QA surface map, website coverage, and
  `git diff --check` passed.

The pure suite covers validation/bounds, deterministic storage, case canonicalization, immutable update/removal,
grouped rendering order, **Other references**, multi-id ambiguity, exact ordinary-layout restoration, misaligned
identity refusal, panel annotation, and static UI wiring.

## Honest verification boundary

No available agent can drive real Word. Document-setting persistence, category editor interaction, rendered
Content Control layout, save/reopen, desktop Word, and Word-on-the-web behavior are **not yet live-verified**.
Per the maintainer's request, these checks are recorded now and will be consolidated into the arc-level manual
verification checklist after the remaining Word work is complete.

## Manual Word verification owed

1. Cite three works, build a bibliography, and open **Citations in this document…**.
2. Assign `Methods` to two works and `Theory` to one; confirm alphabetical headings and citeproc order within
   Methods.
3. Leave another work unassigned and confirm it remains under **Other references**.
4. Reopen the panel; confirm badges and category-name search, then reuse an existing label from the suggestions.
5. Save/reopen and Refresh; confirm assignments and layout persist in both an in-text and a note-style document.
6. Remove every assignment; confirm the exact ordinary bibliography layout returns.
7. Try a multiline, 81-character, and `Other references` label; confirm each refuses without changing the prior
   assignment or bibliography.
8. Flatten a copy with and without **Also clear Callosum's saved citation settings**; confirm category metadata
   follows that choice.
9. Repeat the core path in Word on the web.

## Next

Add bounded batch category assignment, then explicit category ordering, before heading-scoped bibliography blocks.
