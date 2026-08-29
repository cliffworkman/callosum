# Increment 524 — Word heading-scoped bibliographies

**Date:** 2026-08-28
**Scope:** Word P1 bibliography item #11, fourth bounded slice: live bibliography blocks owned by semantic heading subtrees.

## User behavior

**Insert current-section bibliography here** creates a live block at the cursor for the nearest preceding Word
heading plus its nested lower-level headings, stopping before the next peer or ancestor heading. Up to 50 blocks
can coexist with the ordinary full-document bibliography. **Remove bibliography for current section** removes only
the block owned by that heading; citations, other section blocks, and the full bibliography remain untouched.

Ordinary **Refresh / renumber + bibliography** updates every intact section block from current citation membership.
The same document-local categories and explicit category order apply. Document diagnostics reports complete and
damaged pairs. Flatten removes both scope and block wrappers while retaining the heading and rendered text.

## Persistent identity and outline contract

Microsoft's production Word JavaScript API can enumerate bookmarks, but bookmark creation remains preview-only.
This implementation therefore uses two stable Content Controls sharing one cryptographically random 128-bit,
lowercase-hex identity:

- a hidden scope control wraps the owning heading paragraph;
- a bounded block control owns only generated bibliography text.

The persisted identity never depends on heading text, ordinal position, or Word's session-local paragraph id.
During one WordApi 1.6 batch, paragraph `uniqueLocalId` correlates controls to the current body outline; it is never
stored. A scope that no longer wraps a heading, a missing/duplicate/malformed pair, a pair outside the main story,
or a 51st block fails closed before refresh/insertion. The generated paragraph is explicitly Normal style so
insertion from within a heading cannot create a false outline boundary.

## Rendering and scientific boundary

Callosum still sends the complete ordered manuscript once through the existing production
`/citations/render-document` contract. Each section performs a pure projection over aligned
`bibliography_entry_ids`, retaining entries whose ids intersect live citations in its heading subtree. Categories
and configured order are then applied to that projection without changing citeproc entry text/order.

No endpoint, provider, prompt, parser, citeproc behavior, scientific validation, egress rule, permission,
dependency, migration, or production AI behavior changed. The feature is explicit author structure, not a claim,
signal, ranking, or inferred importance; the Principles gate is non-triggering. The security audit gate is also
non-triggering: no new host, credential, filesystem path, or egress surface exists.

## Deliberate first-slice boundary

Section bibliographies require WordApi 1.6 and an in-text citation style. A native footnote/endnote citation does
not currently expose a proven mapping from its note body back to the owning main-story heading. Note styles are
therefore refused rather than guessed. Placement conversion, a section manager/remove-all flow, bibliography title
links, and grouped-citation per-source navigation remain later independent increments.

## QA and experience pass

QA route 34 now contains the desktop/web manual Word matrix; route 35's static zero-egress surface assertion names
the new controls. The website capability registry was reviewed because the document-adapter fingerprint changed;
no public visual/capability claim required copy or screenshot changes.

Local deadline-author walkthrough (delegation is disabled): the two commands sit beside Refresh/Flatten, use the
same “current section” wording as Writer, explain heading-defined failures, and removal names its narrow effect.
The cheap fix found in this pass was forcing the generated paragraph to Normal style; without it, insertion from a
heading could silently create the next outline boundary. A dedicated manager remains polish rather than a blocker
for the insert/refresh/remove loop.

## Automated verification

- Word pure logic: **58/58** (`node --test adapters/word/taskpane_core.test.js`).
- Focused Word/citation pytest: **113 passed** in 288.47s. The earlier combined Word/citation/Help command reached
  its explicit 300-second harness with no aggregate and is not counted as a pass.
- Focused Help pytest: **14 passed** in 26.26s.
- Full repository suite: **2563 passed, 3 skipped** in 1021.05s (17m01s;
  `pytest -n auto -q --tb=short`).
- JavaScript syntax checks passed for `taskpane.js` and `taskpane_core.js`.
- Scoped Ruff format/check, Bandit, Tach, 569-file line budget, QA surface map (430/430 gated API surfaces),
  website coverage review, targeted pre-commit, and `git diff --check` passed.

Pure tests cover random-id encoding, strict tag decoding, complete/damaged/duplicate pair inventory, the 50-block
cap, nearest-heading/nested-subtree bounds, grouped-citation id membership, full-render projection, category/order
preservation, missing entry-identity refusal, diagnostics, and static insert/remove/refresh/Flatten wiring.

## Honest verification boundary

No available agent can drive real Word. Scope-control creation, paragraph correlation, insert/remove placement,
save/reopen persistence, category rendering, damaged-pair behavior, Flatten, desktop Word, and Word-on-the-web are
**not yet live-verified**. Per the maintainer's request, these steps are recorded here and will be consolidated into
one manual arc checklist after implementation work finishes.

## Manual Word verification owed

1. In APA, create two peer Heading 1 sections plus a nested Heading 2; cite distinct works in each.
2. Insert a section bibliography from body text and from inside a heading; confirm the block is Normal style and
   the heading outline remains unchanged.
3. Confirm parent/nested membership, peer exclusion, full-bibliography coexistence, and category/order behavior.
4. Add, move, group, and remove citations; Refresh and confirm each block repairs without touching prose/peers.
5. Save/reopen; confirm identities and Refresh survive. Insert a second block in one subtree and confirm refusal.
6. Try no preceding heading, a citation-free section, a note body/style, damaged/missing/duplicate controls, and
   over 50 blocks; confirm fail-closed messages and no mutation.
7. Run Document diagnostics; confirm complete/damaged counts. Remove one current-section block and confirm its
   scope only is removed.
8. Flatten; confirm all citation/full/section controls disappear while headings and rendered text remain.
9. Repeat the core insertion/refresh/removal/reopen path in Word on the web.

## Next

Continue the Word parity arc with the smallest remaining independently useful P1/P2 slice; do not expand this
increment into note-anchor inference, placement conversion, a section manager, or bibliography hyperlinks.
