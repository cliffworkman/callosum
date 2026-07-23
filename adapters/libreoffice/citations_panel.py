"""callosum — "Citations in this document" panel (P1 item #12, backlog #33/#34).

A read-only overview of every unique work cited in the current document: occurrence count, missing/orphaned
status, retraction status, and click-to-navigate — modeled on RefWorks' "My Citations" view. A **snapshot at
open time**, not a live-refreshing panel: every dialog in this codebase (composer.py, callosum_cite.py's own
`_input_box`/`_msgbox`) is modal (`.execute()`), and nothing here has ever built a non-modal/"stays open while
you keep editing" UNO window — the `.oxt` dispatcher (`callosum_addon.py`) is a stateless per-click invocation
with no persistent object between actions, so a real always-open panel needs new lifecycle plumbing (an
`XModifyListener`, something holding a reference so it isn't garbage-collected) with zero precedent here.
Shipping the modal version first (reopen after editing to refresh) delivers the value without that risk; the
always-open version is a deliberate, named later phase, not a silent scope cut.

Kept in its own module (mirrors the `composer.py` split): dialog CONSTRUCTION is a distinct concern from the
document-scanning logic (`callosum_cite.py::list_document_citations`), which the caller already ran before
opening this — this module only renders already-fetched data and returns a navigation choice, no network calls
and no `import callosum_cite` needed.

NOTE: like `composer.py`, this is only ever exercised interactively (`dialog.execute()` blocks on real UI
input) — no headless spike for the dialog itself, only for the pure data-gathering side
(`list_document_citations`, tested via `selftest_uno.py`). The dialog's actual behavior needs a manual check
in real Writer, same as the composer.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callosum_cite as cc  # noqa: E402  (after sys.path injection, matching composer.py's own convention)


def _format_row(entry: dict) -> str:
    tag = f"  [{entry['retraction_label']}]" if entry.get("retraction_label") else ""
    return f"{entry['row']}  ({entry['count']}×){tag}"


def run_citations_panel(entries: list[dict]):
    """Show the panel over the already-fetched `entries` (`callosum_cite.py::list_document_citations`'
    output). Returns the chosen entry's ReferenceMark if the user selected one and clicked "Go to", else None.
    The caller (not this module) does the actual navigation — mirrors `composer.py::run_composer_dialog`
    returning assembled items for its caller to insert, rather than mutating the document itself."""
    import unohelper
    from com.sun.star.awt import XActionListener, XTextListener

    ctx = cc._component_ctx()
    smgr = ctx.ServiceManager

    class _TextChangeListener(unohelper.Base, XTextListener):
        def __init__(self, callback):
            self._callback = callback

        def textChanged(self, event):
            self._callback()

        def disposing(self, event):
            pass

    class _ActionListener(unohelper.Base, XActionListener):
        def __init__(self, callback):
            self._callback = callback

        def actionPerformed(self, event):
            self._callback()

        def disposing(self, event):
            pass

    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 380, 280, "Citations in this document"

    def _label(name, x, y, w, h, text):
        lbl = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lbl.PositionX, lbl.PositionY, lbl.Width, lbl.Height, lbl.Label = x, y, w, h, text
        dm.insertByName(name, lbl)
        return lbl

    _label("filter_lbl", 6, 6, 60, 12, "Filter:")
    filter_box = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    filter_box.PositionX, filter_box.PositionY, filter_box.Width, filter_box.Height, filter_box.Text = (
        70,
        4,
        304,
        14,
        "",
    )
    dm.insertByName("filter", filter_box)

    _label("count_lbl", 6, 22, 368, 12, f"{len(entries)} cited work(s):")

    results = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    results.PositionX, results.PositionY, results.Width, results.Height = 6, 36, 368, 200
    dm.insertByName("results", results)

    goto_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    goto_btn.PositionX, goto_btn.PositionY, goto_btn.Width, goto_btn.Height = 214, 244, 74, 18
    goto_btn.Label, goto_btn.PushButtonType = "Go to", 1
    dm.insertByName("goto", goto_btn)

    close_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    close_btn.PositionX, close_btn.PositionY, close_btn.Width, close_btn.Height = 294, 244, 80, 18
    close_btn.Label, close_btn.PushButtonType = "Close", 2
    dm.insertByName("close", close_btn)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)

    filter_ctrl = dialog.getControl("filter")
    results_ctrl = dialog.getControl("results")
    count_lbl_ctrl = dialog.getControl("count_lbl")

    # `state["visible"]` mirrors what's on screen after the current filter, so `do_filter`'s selection index
    # maps back to the right full-list entry regardless of how the filter has narrowed the list.
    state = {"visible": list(entries)}

    def _refresh_listbox():
        results_ctrl.getModel().StringItemList = tuple(_format_row(e) for e in state["visible"])
        count_lbl_ctrl.getModel().Label = f"{len(state['visible'])} of {len(entries)} cited work(s):"

    def do_filter():
        needle = filter_ctrl.getModel().Text.strip().lower()
        state["visible"] = list(entries) if not needle else [e for e in entries if needle in _format_row(e).lower()]
        _refresh_listbox()

    _refresh_listbox()
    filter_ctrl.addTextListener(_TextChangeListener(do_filter))

    result = dialog.execute()  # 1 == Go to (PushButtonType), 0/2 == Close
    chosen = None
    if result == 1:
        pos = results_ctrl.getSelectedItemPos()
        if pos is not None and 0 <= pos < len(state["visible"]):
            chosen = state["visible"][pos]["mark"]
    dialog.dispose()
    return chosen
