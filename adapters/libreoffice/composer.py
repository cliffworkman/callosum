"""callosum — LibreOffice citation composer (Phase 5a/5b/5c, backlog #33/#34).

The live-search, multi-item citation-building dialog that replaces the original one-shot search+single-select
flow (`callosum_cite.py`'s old `add_citation_by_search`). Building this needed the FIRST UNO event-listener
implementations in this codebase beyond the .oxt dispatcher itself (see `spike_live_search_listener` in
`selftest_uno.py`, which empirically confirmed a programmatic `setText()` reliably fires
`XTextListener.textChanged`, and that a synchronous local search-and-refresh from inside the callback has no
observed reentrancy problem — the local search round-trip took ~26ms in that spike, fast enough that no async
debounce timer was needed for a "live" feel).

Phase 5b added per-item options (locator/label/prefix/suffix/suppress-author/author-only) via a small
"Options…" sub-dialog. Phase 5c adds **Edit Citation** (the same composer, reopened pre-populated from an
existing citation's items via `existing_items`) and manual reordering (Move ↑/↓) of assembled items.

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
from a11y import enter_activates, focus_first, labeled_field, set_tab_order  # noqa: E402

PREVIEW_MAX = 400  # cap the rendered-preview text length shown in the dialog


def _item_overrides(item: dict) -> dict:
    """The per-occurrence fields on an assembly item, ready to merge into `insert_citation_items`' payload."""
    return {k: item[k] for k in cc._ITEM_DEFAULTS if k != "custom_override" and item.get(k) not in (None, False)}


def _format_assembly_row(item: dict) -> str:
    """The base search-result row, plus a compact `[...]` summary of any active per-occurrence override, so the
    user can see at a glance which assembled items carry one without opening Options."""
    tags = []
    if item.get("locator"):
        tags.append(f"{item.get('label') or 'loc.'} {item['locator']}")
    if item.get("prefix"):
        tags.append(f'prefix "{item["prefix"]}"')
    if item.get("suffix"):
        tags.append(f'suffix "{item["suffix"]}"')
    if item.get("suppress-author"):
        tags.append("no author")
    if item.get("author-only"):
        tags.append("author only")
    return f"{item['row']}  [{', '.join(tags)}]" if tags else item["row"]


def _assembly_item_from_decoded(record: dict) -> dict:
    """Rebuild a composer assembly-item dict from an EXISTING citation's already-decoded item (Phase 5c, Edit
    Citation) — separates the per-occurrence override keys back out from the bare CSL record, so an edited
    citation's assembly items have the identical shape a fresh `do_add()` produces (both feed the same
    `refresh_preview`/final-insert code unchanged)."""
    item_id = str(record.get("id") or "")
    paper_id = item_id[len("callosum-") :] if item_id.startswith("callosum-") else item_id
    bare_record = {k: v for k, v in record.items() if k not in cc._ITEM_DEFAULTS}
    item = {"paper_id": paper_id, "row": cc.csl_record_row(record), "record": bare_record}
    for key, default in cc._ITEM_DEFAULTS.items():
        if key != "custom_override":
            item[key] = record.get(key, default)
    return item


def _edit_item_options(ctx, item: dict) -> dict | None:
    """A small modal dialog editing ONE assembly item's per-occurrence fields in place. Returns the updated
    item dict on OK, or None on Cancel (caller should leave the item unchanged). "Clear" resets the dialog's
    OWN visible fields (not the item) — the user still confirms via OK, so a stray click can't silently drop
    an override without a chance to back out via Cancel."""
    import unohelper
    from com.sun.star.awt import XActionListener, XItemListener

    smgr = ctx.ServiceManager
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 320, 216, "Citation options"

    def _label(name, x, y, w, h, text):
        lbl = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lbl.PositionX, lbl.PositionY, lbl.Width, lbl.Height, lbl.Label = x, y, w, h, text
        lbl.Tabstop = False
        dm.insertByName(name, lbl)

    _label("subtitle", 6, 6, 308, 12, item["row"][:70])

    label_box = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    label_box.PositionX, label_box.PositionY, label_box.Width, label_box.Height = 100, 22, 120, 60
    label_box.Dropdown = True
    label_options = ("(none)", *cc.CSL_LOCATOR_LABELS)
    label_box.StringItemList = label_options
    labeled_field(dm, "label_lbl", "label", 6, 24, 90, 12, "Locator label:", label_box, 0)

    locator_edit = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    locator_edit.PositionX, locator_edit.PositionY, locator_edit.Width, locator_edit.Height = 100, 42, 214, 14
    locator_edit.Text = item.get("locator") or ""
    labeled_field(dm, "locator_lbl", "locator", 6, 44, 90, 12, "Locator value:", locator_edit, 2)

    prefix_edit = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    prefix_edit.PositionX, prefix_edit.PositionY, prefix_edit.Width, prefix_edit.Height = 100, 62, 214, 14
    prefix_edit.Text = item.get("prefix") or ""
    labeled_field(dm, "prefix_lbl", "prefix", 6, 64, 90, 12, "Prefix:", prefix_edit, 4)

    suffix_edit = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    suffix_edit.PositionX, suffix_edit.PositionY, suffix_edit.Width, suffix_edit.Height = 100, 82, 214, 14
    suffix_edit.Text = item.get("suffix") or ""
    labeled_field(dm, "suffix_lbl", "suffix", 6, 84, 90, 12, "Suffix:", suffix_edit, 6)

    suppress_box = dm.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
    suppress_box.PositionX, suppress_box.PositionY, suppress_box.Width, suppress_box.Height = 6, 104, 150, 14
    suppress_box.Label, suppress_box.State = "Suppress author", (1 if item.get("suppress-author") else 0)
    dm.insertByName("suppress_author", suppress_box)

    author_only_box = dm.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
    author_only_box.PositionX, author_only_box.PositionY, author_only_box.Width, author_only_box.Height = (
        160,
        104,
        150,
        14,
    )
    author_only_box.Label, author_only_box.State = "Author only", (1 if item.get("author-only") else 0)
    dm.insertByName("author_only", author_only_box)

    clear_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    clear_btn.PositionX, clear_btn.PositionY, clear_btn.Width, clear_btn.Height, clear_btn.Label = (
        6,
        190,
        74,
        18,
        "Clear",
    )
    dm.insertByName("clear", clear_btn)

    ok_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok_btn.PositionX, ok_btn.PositionY, ok_btn.Width, ok_btn.Height = 154, 190, 74, 18
    ok_btn.Label, ok_btn.PushButtonType = "OK", 1
    dm.insertByName("ok", ok_btn)

    cancel_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel_btn.PositionX, cancel_btn.PositionY, cancel_btn.Width, cancel_btn.Height = 234, 190, 80, 18
    cancel_btn.Label, cancel_btn.PushButtonType = "Cancel", 2
    dm.insertByName("cancel", cancel_btn)

    set_tab_order(dm, ["suppress_author", "author_only", "clear", "ok", "cancel"], start=8)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)

    label_ctrl = dialog.getControl("label")
    current_label = item.get("label")
    label_ctrl.selectItemPos(label_options.index(current_label) if current_label in label_options else 0, True)

    locator_ctrl = dialog.getControl("locator")
    prefix_ctrl = dialog.getControl("prefix")
    suffix_ctrl = dialog.getControl("suffix")
    suppress_ctrl = dialog.getControl("suppress_author")
    author_only_ctrl = dialog.getControl("author_only")

    class _MutexListener(unohelper.Base, XItemListener):
        """Suppress-author and author-only are contradictory CSL concepts (omit vs. show-only the author) —
        checking one unchecks the other rather than letting both be set at once with undefined effect."""

        def __init__(self, this_box, other_box):
            self._this, self._other = this_box, other_box

        def itemStateChanged(self, event):
            if self._this.getState() == 1:
                self._other.setState(0)

        def disposing(self, event):
            pass

    class _ClearListener(unohelper.Base, XActionListener):
        def actionPerformed(self, event):
            label_ctrl.selectItemPos(0, True)
            locator_ctrl.setText("")
            prefix_ctrl.setText("")
            suffix_ctrl.setText("")
            suppress_ctrl.setState(0)
            author_only_ctrl.setState(0)

        def disposing(self, event):
            pass

    suppress_ctrl.addItemListener(_MutexListener(suppress_ctrl, author_only_ctrl))
    author_only_ctrl.addItemListener(_MutexListener(author_only_ctrl, suppress_ctrl))
    dialog.getControl("clear").addActionListener(_ClearListener())

    focus_first(dialog, "label")
    result = dialog.execute()  # 1 == OK
    updated = None
    if result == 1:
        chosen_label = label_options[label_ctrl.getSelectedItemPos()]
        updated = dict(item)
        updated["label"] = None if chosen_label == "(none)" else chosen_label
        updated["locator"] = locator_ctrl.getModel().Text.strip() or None
        updated["prefix"] = prefix_ctrl.getModel().Text.strip() or None
        updated["suffix"] = suffix_ctrl.getModel().Text.strip() or None
        updated["suppress-author"] = suppress_ctrl.getState() == 1
        updated["author-only"] = author_only_ctrl.getState() == 1
    dialog.dispose()
    return updated


def run_composer_dialog(doc, base: str, existing_items: list[dict] | None = None) -> list | None:
    """Show the composer: live search + a persistent multi-item assembly (each item optionally carrying a
    locator/prefix/suffix/suppress-author override, via "Options…", and manually reorderable via Move ↑/↓) +
    a real rendered preview. If `existing_items` is given (Edit Citation, Phase 5c — an existing citation's
    already-decoded items), the assembly starts pre-populated from them instead of empty, and the dialog opens
    in "Edit citation" mode (title + button label change; behavior is otherwise identical to Insert). Returns
    the assembled items (``[{"paper_id": ..., **any set overrides}, ...]``, in the final on-screen order) if
    the user clicked Insert/Update with at least one item, else None."""
    import unohelper
    from com.sun.star.awt import XActionListener, XTextListener

    editing = existing_items is not None
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
    dm.Width, dm.Height, dm.Title = 380, 316, ("Edit citation" if editing else "Add citation")

    def _label(name, x, y, w, h, text, multiline=False):
        lbl = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lbl.PositionX, lbl.PositionY, lbl.Width, lbl.Height, lbl.Label = x, y, w, h, text
        if multiline:
            lbl.MultiLine = True
        lbl.Tabstop = False
        dm.insertByName(name, lbl)
        return lbl

    _label(
        "caveat",
        6,
        6,
        368,
        16,
        "Search your library, add one or more sources below, then "
        + ("Update. " if editing else "Insert. Nothing is added until you click Insert."),
        multiline=True,
    )

    query = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    query.PositionX, query.PositionY, query.Width, query.Height, query.Text = 60, 26, 314, 14, ""
    labeled_field(dm, "query_lbl", "query", 6, 28, 50, 12, "Search:", query, 0)

    results = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    results.PositionX, results.PositionY, results.Width, results.Height = 6, 56, 368, 58
    labeled_field(dm, "results_lbl", "results", 6, 44, 300, 12, "Search results:", results, 2)

    add_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    add_btn.PositionX, add_btn.PositionY, add_btn.Width, add_btn.Height, add_btn.Label = 6, 118, 88, 16, "Add →"
    dm.insertByName("add", add_btn)

    remove_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    remove_btn.PositionX, remove_btn.PositionY, remove_btn.Width, remove_btn.Height, remove_btn.Label = (
        98,
        118,
        88,
        16,
        "← Remove",
    )
    dm.insertByName("remove", remove_btn)

    options_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    options_btn.PositionX, options_btn.PositionY, options_btn.Width, options_btn.Height, options_btn.Label = (
        190,
        118,
        90,
        16,
        "Options…",
    )
    dm.insertByName("options", options_btn)

    up_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    up_btn.PositionX, up_btn.PositionY, up_btn.Width, up_btn.Height, up_btn.Label = 6, 136, 88, 16, "Move ↑"
    dm.insertByName("move_up", up_btn)

    down_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    down_btn.PositionX, down_btn.PositionY, down_btn.Width, down_btn.Height, down_btn.Label = 98, 136, 88, 16, "Move ↓"
    dm.insertByName("move_down", down_btn)

    set_tab_order(dm, ["add", "remove", "options", "move_up", "move_down"], start=4)

    assembly = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    assembly.PositionX, assembly.PositionY, assembly.Width, assembly.Height = 6, 168, 368, 58
    labeled_field(dm, "assembly_lbl", "assembly", 6, 156, 300, 12, "Citing (0):", assembly, 9)

    preview = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    preview.PositionX, preview.PositionY, preview.Width, preview.Height = 6, 242, 368, 40
    preview.MultiLine, preview.ReadOnly, preview.Tabstop = True, True, False
    labeled_field(dm, "preview_lbl", "preview", 6, 230, 300, 12, "Preview (as it will render):", preview, 11)

    insert_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    insert_btn.PositionX, insert_btn.PositionY, insert_btn.Width, insert_btn.Height = 214, 288, 74, 18
    insert_btn.Label, insert_btn.PushButtonType = ("Update" if editing else "Insert"), 1
    dm.insertByName("insert", insert_btn)

    cancel_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel_btn.PositionX, cancel_btn.PositionY, cancel_btn.Width, cancel_btn.Height = 294, 288, 80, 18
    cancel_btn.Label, cancel_btn.PushButtonType = "Cancel", 2
    dm.insertByName("cancel", cancel_btn)

    set_tab_order(dm, ["insert", "cancel"], start=13)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)

    query_ctrl = dialog.getControl("query")
    results_ctrl = dialog.getControl("results")
    assembly_ctrl = dialog.getControl("assembly")
    preview_ctrl = dialog.getControl("preview")
    assembly_lbl_ctrl = dialog.getControl("assembly_lbl")

    # state["assembly"]: ordered list of item dicts — {"paper_id", "row", "record" (bare CSL, fetched once on
    # Add / rebuilt from the decoded item on Edit, never re-fetched), plus the per-occurrence keys from
    # cc._ITEM_DEFAULTS (locator/label/prefix/suffix/suppress-author/author-only), None/False until set.
    state = {"hits": [], "assembly": [_assembly_item_from_decoded(it) for it in (existing_items or [])]}

    def _refresh_assembly_listbox():
        assembly_ctrl.getModel().StringItemList = tuple(_format_assembly_row(it) for it in state["assembly"])
        assembly_lbl_ctrl.getModel().Label = f"Citing ({len(state['assembly'])}):"

    def do_search():
        q = query_ctrl.getModel().Text
        hits = cc.search_library(base, q) if q.strip() else []
        state["hits"] = hits
        results_ctrl.getModel().StringItemList = tuple(cc.build_search_rows(hits))

    def refresh_preview():
        if not state["assembly"]:
            preview_ctrl.getModel().Text = ""
            return
        records = []
        for it in state["assembly"]:
            record = dict(it["record"])
            record.update(_item_overrides(it))
            records.append(record)
        style, locale = cc._get_pref(doc, base)
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
        if any(it["paper_id"] == paper_id for it in state["assembly"]):
            return  # already added -- no duplicate items in one citation
        record = cc.stamp_item_id(cc.fetch_csl(base, paper_id), paper_id)
        row = cc.build_search_rows([hit])[0]
        item = {"paper_id": paper_id, "row": row, "record": record, **cc._ITEM_DEFAULTS}
        del item["custom_override"]  # adapter-internal only; never surfaced or sent from the composer
        state["assembly"].append(item)
        _refresh_assembly_listbox()
        refresh_preview()

    def do_remove():
        pos = assembly_ctrl.getSelectedItemPos()
        if pos is None or pos < 0 or pos >= len(state["assembly"]):
            return
        state["assembly"].pop(pos)
        _refresh_assembly_listbox()
        refresh_preview()

    def do_options():
        pos = assembly_ctrl.getSelectedItemPos()
        if pos is None or pos < 0 or pos >= len(state["assembly"]):
            return
        updated = _edit_item_options(ctx, state["assembly"][pos])
        if updated is not None:
            state["assembly"][pos] = updated
            _refresh_assembly_listbox()
            refresh_preview()

    def do_move(delta: int):
        pos = assembly_ctrl.getSelectedItemPos()
        if pos is None or pos < 0 or pos >= len(state["assembly"]):
            return
        new_pos = pos + delta
        if new_pos < 0 or new_pos >= len(state["assembly"]):
            return
        state["assembly"][pos], state["assembly"][new_pos] = state["assembly"][new_pos], state["assembly"][pos]
        _refresh_assembly_listbox()
        assembly_ctrl.selectItemPos(new_pos, True)  # keep the moved item selected
        refresh_preview()

    query_ctrl.addTextListener(_TextChangeListener(do_search))
    dialog.getControl("add").addActionListener(_ActionListener(do_add))
    dialog.getControl("remove").addActionListener(_ActionListener(do_remove))
    dialog.getControl("options").addActionListener(_ActionListener(do_options))
    dialog.getControl("move_up").addActionListener(_ActionListener(lambda: do_move(-1)))
    dialog.getControl("move_down").addActionListener(_ActionListener(lambda: do_move(1)))

    # Zotero's documented "a second Enter inserts the citation" pattern: Enter while a result/assembly row has
    # focus does what the adjacent Add/Remove button does, without requiring a mouse or an extra Tab.
    enter_activates(results_ctrl, do_add)
    enter_activates(assembly_ctrl, do_remove)

    if editing:
        _refresh_assembly_listbox()
        refresh_preview()

    focus_first(dialog, "query")
    result = dialog.execute()  # 1 == Insert/Update (PushButtonType), 0/2 == Cancel
    items = [{"paper_id": it["paper_id"], **_item_overrides(it)} for it in state["assembly"]] if result == 1 else []
    dialog.dispose()
    return items or None
