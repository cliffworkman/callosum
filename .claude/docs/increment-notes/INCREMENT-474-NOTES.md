# Increment 474 — LibreOffice adapter keyboard/screen-reader accessibility pass (round 3, item #3)

## Implemented

Round 3's item #3 (memory `callosum-next5-backlog-roadmap-round3`): backlog #33/#34's long-open
"comprehensive keyboard/screen-reader accessibility" P1 item, traced to its source
(`chatgpt5.6_future-tracks_wordprocessorpluginscompetitivereview.md`) and scoped to the LibreOffice adapter's
own citation-authoring UI, benchmarked against Zotero/Mendeley's documented word-processor plugin keyboarding.
Read all 13 real UNO dialog-construction sites first (`callosum_cite.py` ×6, `citations_panel.py` ×2,
`composer.py` ×2, `evidence_insert.py` ×3) and found a fully consistent, systemic gap: none associated a
`FixedText` label with its field, none set an explicit `TabIndex`, none set initial focus on open, and
`composer.py::run_composer_dialog`'s results/assembly lists had no Enter-to-add/remove shortcut (Zotero's own
documented "a second Enter inserts the citation" pattern). Cliff confirmed fixing all 13 sites in one pass
(explicitly the broader of two offered scopes), not just the composer.

- **New `adapters/libreoffice/a11y.py`** — `labeled_field()`, `set_tab_order()`, `focus_first()`,
  `enter_activates()`. The one shared place every dialog's wiring goes through, mirroring `composer.py`'s own
  "dialog construction is a distinct concern" split.
- **All 13 dialog-construction functions converted**: `composer.py::_edit_item_options` +
  `run_composer_dialog` (the latter also gains `enter_activates(results_ctrl, do_add)` /
  `enter_activates(assembly_ctrl, do_remove)`); `callosum_cite.py::_suggestion_detail_dialog`,
  `_suggest_dialog`, `_choose_citation_source`, `_input_box`, `_choice_box`,
  `_section_bibliographies_dialog`; `citations_panel.py::run_category_order_dialog`, `run_citations_panel`;
  `evidence_insert.py::_paper_search_dialog`, `_annotation_list_dialog`, `_annotation_configure_dialog`.
- **New `selftest_uno.py::spike_dialog_accessibility_wiring`** (item #30 in the default sequence; also
  reachable standalone via `CALLOSUM_UNO_SPIKE=dialog-accessibility`) — proves `labeled_field`/`set_tab_order`
  against real `AccessibleContext.getAccessibleName()` on a live peer, and `enter_activates` against a real
  registered `XKeyListener` fed a synthetic `Key.RETURN` event.
- **`README.md`** — new "Accessibility" section describing the Tab order/labeling/Enter-shortcut behavior.

## Key technical detail

**A real bug this spike caught before ship, not after**: the first implementation set
`field_model.LabelControl = label` on the field (mirroring what looked like a plausible UNO accessibility
property). Real LibreOffice raised `AttributeError: LabelControl` the moment `spike_dialog_accessibility_wiring`
called `dialog.createPeer()` — `LabelControl` is a *forms*-API property
(`com.sun.star.form.component.*`, e.g. a Writer document form's `DatabaseTextField`), not something
`UnoControlEditModel`/`UnoControlListBoxModel` (the plain AWT dialog controls every dialog in this adapter
builds) expose at all. Confirmed by directly introspecting `getPropertySetInfo().getProperties()` against the
real installed LibreOffice via three one-off probe scripts (run through LibreOffice's own bundled Python
against a live UNO socket, then deleted once the finding was folded into the fix — this codebase never fakes
real UNO control behavior, so a throwaway probe against the real thing was the only way to find the real
mechanism).

**The real mechanism** (same probes, confirmed via `getAccessibleContext().getAccessibleName()` and the
`LABELED_BY` `AccessibleRelation` it produces): VCL auto-associates a `FixedText` with the field immediately
**following it in `TabIndex` order**, as long as the label has `Tabstop = False`. Proven correct for *multiple
distinct label/field pairs in one dialog* (not just a blunt "one label describes everything" false positive) —
two independently-labeled fields each resolved to their own, correct label text. `labeled_field()` in `a11y.py`
was rewritten around this: it sets `TabIndex`/`Tabstop` on the label and `TabIndex = tab_index + 1` on the
field, and sets nothing on the field beyond that. No `dialog.execute()` is ever called (would block on real
input), so this whole mechanism is headless-provable — the same principle `spike_live_search_listener`
established for the `XTextListener` mechanism.

**A second real headless limitation, also caught by the spike rather than assumed**: a genuinely `--headless`
soffice grants real OS/VCL keyboard focus to **no window at all** — not even the dialog itself, let alone a
child control — regardless of `setVisible()`/`toFront()`/`setFocus()` (confirmed via a fourth probe). So
`focus_first()` is only headlessly provable as "doesn't error on a real peer," never as "actually lands
keyboard focus" — that half is left to the manual verification script below, matching the same limit
`spike_live_search_listener`'s own docstring already states for real per-keystroke timing.

## Manual verification script

Needs a real Writer session (not run this increment — flagged as a follow-up, per the verification protocol):

1. Open the composer (**Add citation…**). Tab through every control; confirm a sensible order with nothing
   skipped, and that the search box has focus on open.
2. With Windows Narrator (or Orca on Linux) running, confirm each field announces a real name (e.g. "Search:",
   not silence) as focus moves to it.
3. Type a query, arrow to a result, press **Enter** with no mouse — confirm it's added to the assembly list;
   repeat on the assembly list with **Remove**.
4. Spot-check 2–3 of the other fixed dialogs (Suggest citations, the citations panel, Insert evidence) the
   same way — Tab order sane, labels announced, initial focus lands somewhere sensible.

## Verification

- `CALLOSUM_UNO_SPIKE=dialog-accessibility python adapters/libreoffice/selftest_uno.py http://127.0.0.1:8100
  1 2 2003` (targeted) → `SELFTEST OK`.
- Full `python adapters/libreoffice/selftest_uno.py ...` (all ~30 spikes, including the new one as item #30,
  against a real headless LibreOffice via a persistent `run_roundtrip.py serve` stack) → `SELFTEST OK`. Confirms
  the `LabelControl`→`TabIndex`-adjacency fix didn't regress any of the other 29 real-Writer round-trip proofs.
- `pytest tests/test_libreoffice_adapter.py -q` → 188 passed (the adapter's own pure-logic tests; unaffected,
  as expected — no pure-logic behavior changed).
- `python -m ruff check` / `ruff format` / `python tools/check_line_budget.py` / `python -m tach check` on every
  touched file → clean.

## Housekeeping

- `.claude/docs/INCREMENT-BACKLOG.md`: backlog #33/#34's remaining-open bullet trimmed to just
  "Traveling-library portability" — the accessibility half is closed, logged in `INCREMENT-BACKLOG-DONE.md`.
- Memory `callosum-next5-backlog-roadmap-round3`: item 3 (accessibility pass) now complete. Item 4 (#15 Sync
  SP4 sharing — scope the design) is next.
