"""callosum — shared dialog-accessibility helpers (backlog #33/#34, round-3 accessibility pass).

Every one of this adapter's ~14 UNO dialog-construction functions built a `FixedText` label next to its field
but never gave LibreOffice's own OS-level accessibility bridge (what Windows Narrator / Linux Orca read from)
anything to announce for most fields, never set an explicit tab order, and never set initial focus on open —
even though a sighted user sees a label right there. This module is the one place that's fixed, reused
everywhere instead of re-derived per dialog (mirrors `composer.py`'s own "dialog construction is a distinct
concern" split).

**Empirically verified against the real installed LibreOffice, not assumed** (`.claude/backups/
probe_uno_label*.py`, run via LibreOffice's own bundled Python against a live UNO socket): plain AWT dialog
control models (`UnoControlEditModel`, `UnoControlListBoxModel`, ...) have **no `LabelControl` property at
all** — that property exists only on the *forms* API (`com.sun.star.form.component.*`, e.g. a Writer document
form's `DatabaseTextField`), a different control family from the `UnoControlDialogModel` every dialog in this
adapter builds. Setting `field_model.LabelControl = label` on these raises `AttributeError` at the first real
`dialog.createPeer()` — caught by `selftest_uno.py::spike_dialog_accessibility_wiring`'s real-UNO run, not by
any pytest (this codebase never fakes real UNO control behavior in pytest, see CLAUDE.md's verification
protocol). The REAL mechanism VCL uses (confirmed via `getAccessibleContext().getAccessibleName()` and the
`LABELED_BY` `AccessibleRelation` it produces): a `FixedText` with `Tabstop = False` sitting immediately before
a field in **TabIndex order** is automatically read as that field's accessible name — no property to set on
the field side at all. `labeled_field` below relies on exactly that adjacency; nothing else is needed.
"""

from __future__ import annotations


def labeled_field(
    dm, label_name: str, field_name: str, x: int, y: int, w: int, h: int, label_text: str, field_model, tab_index: int
):
    """Create a `FixedText` label at (x, y, w, h) with `label_text`, immediately before `field_model` in
    TabIndex order and marked `Tabstop = False` — the pairing VCL's own accessibility bridge auto-detects as
    "this field is labeled by that text" (see the module docstring; verified against real LibreOffice, not the
    nonexistent `LabelControl` property). Returns the label model, since a few dialogs update their label's
    text later (e.g. a live "N items" count)."""
    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height, label.Label = x, y, w, h, label_text
    label.TabIndex = tab_index
    label.Tabstop = False
    dm.insertByName(label_name, label)
    field_model.TabIndex = tab_index + 1
    dm.insertByName(field_name, field_model)
    return label


def set_tab_order(dm, ordered_names: list[str], start: int = 0) -> None:
    """Assign sequential `TabIndex` values (starting at `start`) to already-inserted controls in
    `ordered_names` — for button groups and other controls that don't have a single owning label (so
    `labeled_field` doesn't apply). Pass `start` one past the highest index any prior `labeled_field`/
    `set_tab_order` call in the same dialog already used, so indices never collide."""
    for i, name in enumerate(ordered_names):
        dm.getByName(name).TabIndex = start + i


def focus_first(dialog, name: str) -> None:
    """Set initial keyboard focus to `name` right before `dialog.execute()`, so a keyboard user can start
    typing/navigating immediately instead of needing an extra Tab to reach the dialog's primary control."""
    dialog.getControl(name).setFocus()


def enter_activates(control, on_enter) -> None:
    """Fire `on_enter()` when Return/Enter is pressed while `control` has focus — the first `XKeyListener` in
    this codebase (mirrors how `XTextListener` was new territory for the live-search box; spiked headlessly the
    same way, see `selftest_uno.py::spike_dialog_accessibility_wiring`). Used for composer.py's results→Add and
    assembly→Remove shortcuts (Zotero's documented "a second Enter inserts the citation" pattern) — reuses
    whatever callback the equivalent button already calls, never a second code path."""
    import unohelper
    from com.sun.star.awt import Key, XKeyListener

    class _EnterListener(unohelper.Base, XKeyListener):
        def keyPressed(self, event):
            if event.KeyCode == Key.RETURN:
                on_enter()

        def keyReleased(self, event):
            pass

        def disposing(self, event):
            pass

    listener = _EnterListener()
    control.addKeyListener(listener)
    return listener
