# Increment 515 — closes the Word/Docs parity P0 remainder (bibliography-bounds review + safer Flatten)

## Implemented

Closes the last two P0 items on the Word/Docs parity roadmap (`INCREMENT-BACKLOG.md` #33/#34), both already
named in the backlog text from inc 512's scoping.

**Bibliography-bounds safety review — verified safe, no code change.** The roadmap doc's original critique of
LibreOffice's bibliography implementation: refreshing "selects everything from the bibliography bookmark to
the end of the document and deletes it before rebuilding... any legitimate text placed after the bibliography
can therefore be destroyed" — a real data-loss hazard LibreOffice needed several dedicated increments (374-384)
to earn safety from. Re-read Word's `refreshDocument()` in full: `bibCC.insertText(text, Word.InsertLocation.
replace)` operates on a Word **Content Control**, an inherently bounded range — `insertText(..., replace)`
structurally cannot touch anything outside that control's own range. Word gets this safety property for free
from its data model; there was nothing to fix.

**Safer Flatten.** Scoped the roadmap's full wishlist (item #7) against what Office.js can actually do,
confirmed via research rather than assumed:
- **Not buildable, confirmed**: "save-as-copy by default" and "optional filename suggestion" — Word Add-ins JS
  API has `document.save()` (save in place) but no `saveAs`; an add-in cannot create a new file. "Checkbox to
  retain hyperlinks" doesn't apply to Word at all yet — Word's bibliography has no hyperlink-insertion feature
  (that's LibreOffice-only, and it's Word's own not-yet-started P1 item), so there's nothing to retain.
- **Built**: the first Flatten click now runs a quick read-only scan and shows exactly how many citations (and
  whether the bibliography) will be affected, with an explicit reminder that Callosum can't save a copy or
  undo the action (Word's own Ctrl+Z should still work — expected Office.js behavior, not independently
  verified live this session). A new "Also clear Callosum's saved style setting" checkbox (unchecked by
  default) removes the one piece of add-in-specific document metadata that exists
  (`Office.context.document.settings`'s `callosumStyle` key — grepped, confirmed nothing else is stored).
  After flattening, a post-operation integrity check re-scans the document and confirms zero citation/
  bibliography content controls remain, reporting honestly if any straggler is found rather than assuming
  success.

### Files

- `adapters/word/taskpane.js` — `onFlatten()` is now `async`; its first-click path runs a `Word.run` count
  before arming the confirm (window extended 4s → 8s to give time to read the count and toggle the new
  checkbox). `doFlatten()` adds the settings-clear (gated on the checkbox) and the post-flatten re-scan.
- `adapters/word/taskpane.html` — new `#flattenClearStyle` checkbox, reusing the existing `.checkbox-inline`
  class (no new CSS needed).
- `adapters/word/README.md` — documents the verified bibliography-bounds finding, the enhanced Flatten flow,
  and the honest `saveAs`-doesn't-exist limitation (both in the feature description and the Limitations list).
- `.claude/docs/INCREMENT-BACKLOG.md` — the Word/Docs parity P0 section is now fully closed.

**No `taskpane_core.js` changes** — this is Office.js glue (`Word.run` scans, `document.settings` calls),
neither of which is pure-logic-testable; `node --test` stays at 27/27, unaffected.

## Key technical detail

The post-flatten integrity check deliberately does **not** trust that `cc.delete(true)` calls inside the same
`Word.run` batch all landed — it re-loads `contentControls` fresh, after the delete `ctx.sync()`, and re-scans
for anything still tagged as a citation or bibliography. This mirrors the project's general
signal-not-verdict/no-silent-success posture (PRINCIPLES.md) applied to a local UI operation, not just to
claims about the literature: report what was actually verified, not what was merely attempted.

## Manual verification script

Not yet run live this increment (session's established pattern: build, verify with `node --test`, hand off).
In real Word: click Flatten once with 2+ citations present, confirm the count in the warning message matches
reality; click again, confirm the post-flatten message reports the right count and "verified none remain
live"; toggle the checkbox on a separate run and confirm the style dropdown reverts to the app default on next
load (settings cleared); press Ctrl+Z after a flatten and confirm Word's native undo restores the live
citations (the one claim in this increment that's expected-but-unverified, not assumed proven).

## Pytest / tests

`node --test adapters/word/taskpane_core.test.js` → 27/27 passed (unchanged — no pure-logic changes this
increment). No Python changes.
