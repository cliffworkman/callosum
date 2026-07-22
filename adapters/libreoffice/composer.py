"""callosum — LibreOffice citation composer (Phase 5a, backlog #33/#34).

The live-search, multi-item citation-building dialog that replaces the original one-shot search+single-select
flow (`callosum_cite.py`'s old `add_citation_by_search`). Building this needed the FIRST UNO event-listener
implementations in this codebase beyond the .oxt dispatcher itself (see `spike_live_search_listener` in
`selftest_uno.py`, which empirically confirmed a programmatic `setText()` reliably fires
`XTextListener.textChanged`, and that a synchronous local search-and-refresh from inside the callback has no
observed reentrancy problem — the local search round-trip took ~26ms in that spike, fast enough that no async
debounce timer was needed for a "live" feel).

Kept in its own module (not `callosum_cite.py`, already 1300+ lines) since dialog CONSTRUCTION is a distinct
concern from the action logic every other function in that file implements.

NOTE: like `callosum_cite.py`'s own dialog helpers (`_input_box`, `_suggest_listbox`), this module is only ever
exercised interactively — a real human driving `dialog.execute()`, which blocks waiting for real UI input, so
there is no way to spike-test the assembled dialog headlessly. Only the pure wiring mechanism (the text
listener) was de-risked via spike; the dialog's actual behavior needs a manual check in real Writer.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callosum_cite as cc  # noqa: E402  (after sys.path injection, matching selftest_uno.py's own convention)

PREVIEW_MAX = 400  # cap the rendered-preview text length shown in the dialog


def run_composer_dialog(doc, base: str) -> list | None:
    """Show the composer: live search + a persistent multi-item assembly + a real rendered preview. Returns the
    assembled paper ids (in the order added) if the user clicked Insert with at least one item, else None."""
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
    dm.Width, dm.Height, dm.Title = 380, 300, "Add citation"

    def _label(name, x, y, w, h, text, multiline=False):
        lbl = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lbl.PositionX, lbl.PositionY, lbl.Width, lbl.Height, lbl.Label = x, y, w, h, text
        if multiline:
            lbl.MultiLine = True
        dm.insertByName(name, lbl)
        return lbl

    _label(
        "caveat",
        6,
        6,
        368,
        16,
        "Search your library, add one or more sources below, then Insert. Nothing is added until you click Insert.",
        multiline=True,
    )

    query = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    query.PositionX, query.PositionY, query.Width, query.Height, query.Text = 6, 26, 368, 14, ""
    dm.insertByName("query", query)

    _label("results_lbl", 6, 44, 300, 12, "Search results:")
    results = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    results.PositionX, results.PositionY, results.Width, results.Height = 6, 56, 368, 58
    dm.insertByName("results", results)

    add_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    add_btn.PositionX, add_btn.PositionY, add_btn.Width, add_btn.Height, add_btn.Label = 6, 118, 110, 16, "Add →"
    dm.insertByName("add", add_btn)

    remove_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    remove_btn.PositionX, remove_btn.PositionY, remove_btn.Width, remove_btn.Height, remove_btn.Label = (
        122,
        118,
        110,
        16,
        "← Remove",
    )
    dm.insertByName("remove", remove_btn)

    _label("assembly_lbl", 6, 138, 300, 12, "Citing (0):")
    assembly = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    assembly.PositionX, assembly.PositionY, assembly.Width, assembly.Height = 6, 150, 368, 58
    dm.insertByName("assembly", assembly)

    _label("preview_lbl", 6, 212, 300, 12, "Preview (as it will render):")
    preview = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    preview.PositionX, preview.PositionY, preview.Width, preview.Height = 6, 224, 368, 40
    preview.MultiLine, preview.ReadOnly = True, True
    dm.insertByName("preview", preview)

    insert_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    insert_btn.PositionX, insert_btn.PositionY, insert_btn.Width, insert_btn.Height = 214, 270, 74, 18
    insert_btn.Label, insert_btn.PushButtonType = "Insert", 1
    dm.insertByName("insert", insert_btn)

    cancel_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel_btn.PositionX, cancel_btn.PositionY, cancel_btn.Width, cancel_btn.Height = 294, 270, 80, 18
    cancel_btn.Label, cancel_btn.PushButtonType = "Cancel", 2
    dm.insertByName("cancel", cancel_btn)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)

    query_ctrl = dialog.getControl("query")
    results_ctrl = dialog.getControl("results")
    assembly_ctrl = dialog.getControl("assembly")
    preview_ctrl = dialog.getControl("preview")
    assembly_lbl_ctrl = dialog.getControl("assembly_lbl")

    # state["assembly"]: ordered list of (paper_id, display_row, stamped_csl_record) — the record is fetched
    # once on Add and reused for every preview render, never re-fetched.
    state = {"hits": [], "assembly": []}

    def do_search():
        q = query_ctrl.getModel().Text
        hits = cc.search_library(base, q) if q.strip() else []
        state["hits"] = hits
        results_ctrl.getModel().StringItemList = tuple(cc.build_search_rows(hits))

    def refresh_preview():
        records = [rec for _pid, _row, rec in state["assembly"]]
        if not records:
            preview_ctrl.getModel().Text = ""
            return
        style, locale = cc._get_pref(doc)
        req = cc.build_render_request([{"citationID": "preview", "items": records}], style, locale)
        try:
            resp = cc.render_document(base, req)
            cites = resp.get("citations", [])
            text = cites[0].get("text", "") if cites else ""
        except Exception as exc:
            text = f"(preview unavailable: {exc})"
        preview_ctrl.getModel().Text = text[:PREVIEW_MAX]

    def do_add():
        pos = results_ctrl.getSelectedItemPos()
        if pos is None or pos < 0 or pos >= len(state["hits"]):
            return
        hit = state["hits"][pos]
        paper_id = hit["id"]
        if any(pid == paper_id for pid, _row, _rec in state["assembly"]):
            return  # already added -- no duplicate items in one citation
        record = cc.stamp_item_id(cc.fetch_csl(base, paper_id), paper_id)
        row = cc.build_search_rows([hit])[0]
        state["assembly"].append((paper_id, row, record))
        assembly_ctrl.getModel().StringItemList = tuple(r for _p, r, _rec in state["assembly"])
        assembly_lbl_ctrl.getModel().Label = f"Citing ({len(state['assembly'])}):"
        refresh_preview()

    def do_remove():
        pos = assembly_ctrl.getSelectedItemPos()
        if pos is None or pos < 0 or pos >= len(state["assembly"]):
            return
        state["assembly"].pop(pos)
        assembly_ctrl.getModel().StringItemList = tuple(r for _p, r, _rec in state["assembly"])
        assembly_lbl_ctrl.getModel().Label = f"Citing ({len(state['assembly'])}):"
        refresh_preview()

    query_ctrl.addTextListener(_TextChangeListener(do_search))
    dialog.getControl("add").addActionListener(_ActionListener(do_add))
    dialog.getControl("remove").addActionListener(_ActionListener(do_remove))

    result = dialog.execute()  # 1 == Insert (PushButtonType), 0/2 == Cancel
    paper_ids = [pid for pid, _row, _rec in state["assembly"]] if result == 1 else []
    dialog.dispose()
    return paper_ids or None
