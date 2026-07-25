"""callosum — "Citations in this document" panel (P1 item #12; bibliography editing P1 item #11, both
backlog #33/#34).

A read-only overview of every unique work cited in the document — occurrence count, missing/orphaned status,
retraction status, a live filter, and click-to-navigate — modeled on RefWorks' "My Citations" view. **Also the
management surface for bibliography editing** (P1 item #11): excluding a cited work from the bibliography
(e.g. a personal communication — still cited in text, conventionally omitted from the reference list) and
adding an uncited "further reading" work. This is the natural, already-built home for "manage what's in my
bibliography" (matching how Zotero/EndNote unify this), rather than a separate new dialog — a deliberate
architecture shift from read-only to read-write, flagged here rather than silently absorbed.

Increment 377 also assigns or removes one document-local category for the selected work. Categories group the
single managed bibliography without changing CSL records or citation text. Increment 378 makes that control
multi-select and reuses existing category labels, so a manuscript-scale batch needs one transactional refresh.

A **snapshot at open time, re-fetched after each edit** — not a live-refreshing panel that tracks ongoing
document edits made outside it: every dialog in this codebase is modal (`.execute()`), and nothing here has
ever built a non-modal/"stays open while you keep editing" UNO window — the `.oxt` dispatcher
(`callosum_addon.py`) is a stateless per-click invocation with no persistent object between actions, so a real
always-open panel would need new, unproven UNO lifecycle plumbing (an `XModifyListener`, something to keep the
window from being garbage-collected). Shipping the modal version keeps the value without that risk; a real
always-open panel is a deliberately deferred later phase.

Kept in its own module (mirrors the `composer.py` split): dialog CONSTRUCTION is a distinct concern from the
document-scanning logic (`callosum_cite.py::list_document_citations`). Reuses `composer.run_composer_dialog`
verbatim for "Add uncited work(s)…" — the exact same search/assemble UI already built, just repurposed to add
bibliography-only entries instead of a citation mark.

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

_CHOOSE_CATEGORY = "\nchoose"
_CREATE_CATEGORY = "\ncreate"
_REMOVE_CATEGORY = "\nremove"


def _format_row(entry: dict) -> str:
    tags = []
    if entry.get("uncited"):
        tags.append("further reading")
    else:
        tags.append(f"{entry['count']}×")
    if entry.get("excluded"):
        tags.append("excluded from bibliography")
    if entry.get("category"):
        tags.append(f"category: {entry['category']}")
    if entry.get("retraction_label"):
        tags.append(entry["retraction_label"])
    return f"{entry['row']}  ({', '.join(tags)})"


def _selected_entries(control, visible: list[dict]) -> list[dict]:
    """Map the UNO listbox's bounded multi-selection back to the filtered entry snapshot."""
    positions = tuple(control.getSelectedItemsPos())
    return [visible[position] for position in positions if 0 <= position < len(visible)]


def _category_picker_options(
    selected: list[dict],
    assignments: dict[str, str],
) -> tuple[tuple[tuple[str, str], ...], str]:
    """Build deterministic reusable-label choices and a safe default for the current selection."""
    canonical: dict[str, str] = {}
    for category in assignments.values():
        canonical.setdefault(category.casefold(), category)
    categories = sorted(canonical.values(), key=str.casefold)
    selected_categories = {entry.get("category") for entry in selected}
    options: list[tuple[str, str]] = []
    if len(selected_categories) > 1:
        options.append(("Choose a category…", _CHOOSE_CATEGORY))
        current = _CHOOSE_CATEGORY
    elif selected_categories == {None}:
        current = _CREATE_CATEGORY
    else:
        current = next(iter(selected_categories), _CREATE_CATEGORY)
    options.extend((category, category) for category in categories)
    options.extend(
        (
            ("Create new category…", _CREATE_CATEGORY),
            ("Remove category", _REMOVE_CATEGORY),
        )
    )
    return tuple(options), current


def run_citations_panel(doc, base: str):
    """Show the panel: fetches `list_document_citations(doc, base)` itself (and again after any edit, so the
    displayed list/flags never go stale within the same dialog session). Returns the chosen entry's
    ReferenceMark if the user selected a cited work and clicked "Go to", else None — the caller (not this
    module) does the actual navigation, mirroring `composer.py::run_composer_dialog`'s own contract."""
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
    dm.Width, dm.Height, dm.Title = 420, 312, "Citations in this document"

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
        344,
        14,
        "",
    )
    dm.insertByName("filter", filter_box)

    _label("count_lbl", 6, 22, 408, 12, "")

    results = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    results.PositionX, results.PositionY, results.Width, results.Height = 6, 36, 408, 200
    results.MultiSelection = True
    dm.insertByName("results", results)

    goto_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    goto_btn.PositionX, goto_btn.PositionY, goto_btn.Width, goto_btn.Height = 6, 244, 80, 18
    goto_btn.Label = "Go to"
    dm.insertByName("goto", goto_btn)

    exclude_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    exclude_btn.PositionX, exclude_btn.PositionY, exclude_btn.Width, exclude_btn.Height = 90, 244, 130, 18
    exclude_btn.Label = "Toggle bibliography exclude"
    dm.insertByName("exclude", exclude_btn)

    category_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    category_btn.PositionX, category_btn.PositionY, category_btn.Width, category_btn.Height = 224, 244, 112, 18
    category_btn.Label = "Set category…"
    dm.insertByName("category", category_btn)

    add_uncited_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    add_uncited_btn.PositionX, add_uncited_btn.PositionY, add_uncited_btn.Width, add_uncited_btn.Height = (
        6,
        266,
        130,
        18,
    )
    add_uncited_btn.Label = "Add uncited work(s)…"
    dm.insertByName("add_uncited", add_uncited_btn)

    close_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    close_btn.PositionX, close_btn.PositionY, close_btn.Width, close_btn.Height = 340, 266, 74, 18
    close_btn.Label, close_btn.PushButtonType = "Close", 2
    dm.insertByName("close", close_btn)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)

    filter_ctrl = dialog.getControl("filter")
    results_ctrl = dialog.getControl("results")
    count_lbl_ctrl = dialog.getControl("count_lbl")

    # state["entries"]: the full, current list from the backend (re-fetched after every edit).
    # state["visible"]: entries after the current filter text — what's actually on screen, so a selected
    # listbox index maps back to the right full-list entry regardless of how the filter has narrowed the list.
    state = {"entries": cc.list_document_citations(doc, base), "visible": [], "chosen": None}

    def _apply_filter():
        needle = filter_ctrl.getModel().Text.strip().lower()
        entries = state["entries"]
        state["visible"] = list(entries) if not needle else [e for e in entries if needle in _format_row(e).lower()]
        results_ctrl.getModel().StringItemList = tuple(_format_row(e) for e in state["visible"])
        count_lbl_ctrl.getModel().Label = (
            f"{len(state['visible'])} of {len(entries)} document work(s) — Ctrl/Shift-select to categorize:"
        )

    def _reload():
        state["entries"] = cc.list_document_citations(doc, base)
        _apply_filter()

    def do_toggle_exclude():
        selected = _selected_entries(results_ctrl, state["visible"])
        if len(selected) != 1:
            cc._msgbox("Select exactly one cited work to change its bibliography exclusion.")
            return
        entry = selected[0]
        if entry.get("uncited"):
            cc._msgbox(
                "Only cited works can be excluded. This uncited work is already included explicitly as further reading."
            )
            return
        exclude_ids = set(cc._get_id_list(doc, cc.PREF_BIB_EXCLUDE))
        if entry["paper_id"] in exclude_ids:
            exclude_ids.discard(entry["paper_id"])
        else:
            exclude_ids.add(entry["paper_id"])
        cc._set_id_list(doc, cc.PREF_BIB_EXCLUDE, sorted(exclude_ids))
        try:
            cc.refresh_bibliography(doc, base)
        except Exception:
            cc.set_dirty_state(doc, bibliography=True)
            raise
        _reload()

    def do_add_uncited():
        import composer

        items = composer.run_composer_dialog(doc, base)
        if not items:
            return
        uncited_ids = set(cc._get_id_list(doc, cc.PREF_BIB_UNCITED))
        for it in items:
            uncited_ids.add(str(it["paper_id"]))
        cc._set_id_list(doc, cc.PREF_BIB_UNCITED, sorted(uncited_ids))
        try:
            cc.refresh_bibliography(doc, base)
        except Exception:
            cc.set_dirty_state(doc, bibliography=True)
            raise
        _reload()

    def do_set_category():
        selected = _selected_entries(results_ctrl, state["visible"])
        if not selected:
            return
        options, current = _category_picker_options(selected, cc.bibliography_categories(doc))
        value = cc._choice_box(
            doc,
            "Bibliography category",
            f"Category for {len(selected)} selected work(s):",
            options,
            current,
        )
        if value is None or value == _CHOOSE_CATEGORY:
            return
        if value == _CREATE_CATEGORY:
            value = cc._input_box(doc, "New bibliography category", "Category name:")
            if value is None:
                return
            if not value.strip():
                cc._msgbox("Enter a category name, or choose Remove category.", "Bibliography category")
                return
        elif value == _REMOVE_CATEGORY:
            value = None
        try:
            cc.set_bibliography_categories(doc, [entry["paper_id"] for entry in selected], value, base)
        except ValueError as exc:
            cc._msgbox(str(exc), "Invalid bibliography category")
            return
        except Exception:
            cc.set_dirty_state(doc, bibliography=True)
            raise
        _reload()

    def do_goto():
        selected = _selected_entries(results_ctrl, state["visible"])
        if len(selected) != 1:
            cc._msgbox("Select exactly one cited work to go to its first occurrence.")
            return
        if selected[0]["mark"] is None:
            cc._msgbox("This uncited further-reading work has no citation location in the document.")
            return
        state["chosen"] = selected[0]["mark"]
        dialog.endExecute()

    _apply_filter()
    filter_ctrl.addTextListener(_TextChangeListener(_apply_filter))
    dialog.getControl("goto").addActionListener(_ActionListener(do_goto))
    dialog.getControl("exclude").addActionListener(_ActionListener(do_toggle_exclude))
    dialog.getControl("category").addActionListener(_ActionListener(do_set_category))
    dialog.getControl("add_uncited").addActionListener(_ActionListener(do_add_uncited))

    dialog.execute()
    chosen = state["chosen"]
    dialog.dispose()
    return chosen
