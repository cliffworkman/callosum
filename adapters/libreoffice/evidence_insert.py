"""callosum — LibreOffice "Insert evidence" (Citavi-style saved-highlight insertion), backlog #33/#34 P2 item
#20 (inc 461).

Browse a paper's already-saved PDF highlights/annotations (`GET /papers/{id}/annotations` — an existing
endpoint this adapter had never called before this increment), optionally check a typed claim's stance against
the picked passage (`POST /citations/classify-stance`, a new sibling backend endpoint built for exactly this),
and insert it in one of four formats alongside a live citation.

Kept in its own module (not `callosum_cite.py`, already 6000+ lines) — the same "dialog CONSTRUCTION is a
distinct concern from the action logic" discipline `composer.py`'s own docstring established, applied here to a
brand-new three-step UNO interaction (paper picker, highlight picker, configure) rather than another extension
of an existing dialog.

Genuinely new here: this is the first place the adapter inserts free-form body text AND a citation mark
together as one user action (`insert_evidence`) — `insert_statement` inserts text with no citation, and
`insert_citation_items` inserts a citation with no free text; this chains both, reusing each unmodified.

NOTE: like `composer.py`, the dialogs here are only ever exercised interactively — no way to spike-test a real
`dialog.execute()` headlessly. Only the pure helpers (row formatting, locator/evidence-field derivation, format
body text, and the two-step insertion sequence itself with insertString/insert_citation_items monkeypatched)
are unit tested; the real dialogs need `run_roundtrip.py`'s selftest spike + a manual check in real Writer.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callosum_cite as cc  # noqa: E402  (after sys.path injection, matching composer.py's own convention)

ROW_QUOTE_MAX = 70  # truncate a quote preview in the highlight-picker listbox
ROW_NOTE_MAX = 40  # truncate a note preview alongside it

FORMAT_QUOTE_ONLY = "quote_only"
FORMAT_QUOTE_CITE = "quote_cite"
FORMAT_PARAPHRASE_CITE = "paraphrase_cite"
FORMAT_CARD = "card"
# (internal value, menu label) -- order is the order offered in the configure dialog's format dropdown.
FORMATS = (
    (FORMAT_QUOTE_ONLY, "Quote only (no citation)"),
    (FORMAT_QUOTE_CITE, "Quote + citation"),
    (FORMAT_PARAPHRASE_CITE, "Paraphrase (your note) + citation"),
    (FORMAT_CARD, "Structured card (quote + note + citation)"),
)
DEFAULT_FORMAT = FORMAT_QUOTE_CITE


# ── pure helpers (no UNO, no HTTP -- unit tested directly) ───────────────────────────────────────────────────


def _quote_body(annotation: dict) -> str:
    quote = " ".join(str(annotation.get("anchor_text") or "").split())
    return f"“{quote}”" if quote else ""


def _note_body(annotation: dict) -> str:
    return " ".join(str(annotation.get("note") or "").split())


def format_body_text(annotation: dict, fmt: str) -> str:
    """The free-form text to insert BEFORE the citation mark. "Quote only"/"Quote + citation" both use the
    verbatim quote; "Paraphrase + citation" uses the saved note, falling back to the quote if no note was ever
    saved for this highlight (never silently inserting nothing); "Structured card" joins both when a note
    exists. Pure — no UNO, no HTTP."""
    quote = _quote_body(annotation)
    note = _note_body(annotation)
    if fmt in (FORMAT_QUOTE_ONLY, FORMAT_QUOTE_CITE):
        return quote
    if fmt == FORMAT_PARAPHRASE_CITE:
        return note or quote
    if fmt == FORMAT_CARD:
        return f"{quote} — {note}" if note else quote
    raise ValueError(f"Unknown evidence format: {fmt}")


def _annotation_locator(annotation: dict) -> str | None:
    """A page locator pre-filled from the annotation's own single `page` field — the highlight analog of
    `callosum_cite.py`'s own `_auto_locator` (which reads a suggestion's page_start/page_end)."""
    page = annotation.get("page")
    return str(page) if page else None


def _evidence_annotation_fields(annotation: dict) -> dict:
    """The compact evidence-audit locator for a highlight-sourced insert — the annotation analog of
    `callosum_cite.py`'s own `_evidence_fields` (chunk_id/page_start/page_end + a hard-truncated snippet), keyed
    on `evidence_annotation_id` since a saved highlight has no `chunk_id`."""
    snippet = " ".join(str(annotation.get("anchor_text") or "").split())
    if len(snippet) > cc.EVIDENCE_SNIPPET_MAX:
        snippet = snippet[: cc.EVIDENCE_SNIPPET_MAX].rstrip() + "…"
    page = annotation.get("page")
    return {
        "evidence_annotation_id": annotation.get("id"),
        "evidence_page_start": page,
        "evidence_page_end": page,
        "evidence_snippet": snippet or None,
    }


def _annotation_row(annotation: dict) -> str:
    quote = " ".join(str(annotation.get("anchor_text") or "").split())
    if len(quote) > ROW_QUOTE_MAX:
        quote = quote[:ROW_QUOTE_MAX].rstrip() + "…"
    page = annotation.get("page")
    page_text = f"p.{page}" if page else "p.?"
    note = " ".join(str(annotation.get("note") or "").split())
    if not note:
        return f'{page_text} — "{quote}"'
    if len(note) > ROW_NOTE_MAX:
        note = note[:ROW_NOTE_MAX].rstrip() + "…"
    return f'{page_text} — "{quote}"  [note: {note}]'


def annotation_rows(annotations: list[dict]) -> list[str]:
    """One pick-list row per saved highlight. Pure (no UNO)."""
    return [_annotation_row(a) for a in annotations]


def check_stance(base: str, claim: str, annotation: dict) -> dict | None:
    """POST /citations/classify-stance for the typed claim against the highlight's saved quote — None (no call
    made) when either side is blank, matching the endpoint's own "never a guessed verdict" contract for an
    unavailable model."""
    passage = str(annotation.get("anchor_text") or "").strip()
    sentence = (claim or "").strip()
    if not sentence or not passage:
        return None
    return cc._post_json(f"{base}/citations/classify-stance", {"sentence": sentence, "passage": passage})


def insert_evidence(doc, base: str, paper_id, annotation: dict, fmt: str, locator: str | None) -> str | None:
    """The two-step insertion core (genuinely new: first free body text, then a live citation mark) — kept
    separate from the dialogs so it's unit-testable with insertString/insert_citation_items monkeypatched.

    Inserts `format_body_text`'s body at the cursor (the `insert_statement` precedent:
    ``text.insertString(cursor, body + "\\n", False)``, which UNO leaves collapsed right after the inserted
    text), then — unless the format is "quote only" — reuses that SAME cursor object to place the citation mark
    via the existing, unmodified `insert_citation_items`, so the mark lands immediately after the body it
    belongs to. Returns the new mark's rnd, or None when nothing citable was inserted (quote-only format)."""
    cursor = cc._insertion_cursor(doc)
    body = format_body_text(annotation, fmt)
    if body:
        doc.getText().insertString(cursor, body + "\n", False)
    if fmt == FORMAT_QUOTE_ONLY:
        return None
    entry = {"paper_id": paper_id, **_evidence_annotation_fields(annotation)}
    if locator:
        entry["locator"] = locator
        entry["label"] = "page"
    return cc.insert_citation_items(doc, [entry], base, cursor=cursor)


# ── dialogs (UNO only -- exercised interactively; see selftest_uno.py's spike_insert_evidence) ────────────────


def _paper_search_dialog(ctx, base: str) -> dict | None:
    """Live search-as-you-type single-select paper picker — the SAME empirically-proven-safe XTextListener
    wiring `composer.py::run_composer_dialog` already uses for its own search box, reused verbatim (not
    reinvented) for a single pick instead of a multi-item assembly. Returns the chosen search-result dict
    (``{"id", ...}``) or None on cancel/nothing picked."""
    import unohelper
    from a11y import focus_first, labeled_field, set_tab_order
    from com.sun.star.awt import XTextListener

    smgr = ctx.ServiceManager
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 360, 190, "Insert evidence — find a paper"

    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height = 6, 6, 348, 14
    label.Label = "Search your library for the paper whose saved highlights you want to draw from."
    label.TabIndex = 0
    label.Tabstop = False
    dm.insertByName("lbl", label)

    query = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    query.PositionX, query.PositionY, query.Width, query.Height, query.Text = 60, 24, 294, 14, ""
    labeled_field(dm, "query_lbl", "query", 6, 26, 50, 12, "Search:", query, 1)

    results = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    results.PositionX, results.PositionY, results.Width, results.Height = 6, 56, 348, 94
    results.MultiSelection = False
    labeled_field(dm, "results_lbl", "results", 6, 42, 100, 12, "Results:", results, 3)

    ok = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.PositionX, ok.PositionY, ok.Width, ok.Height, ok.Label, ok.PushButtonType = 262, 156, 44, 18, "Next", 1
    dm.insertByName("ok", ok)
    cancel = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.PositionX, cancel.PositionY, cancel.Width, cancel.Height, cancel.Label, cancel.PushButtonType = (
        310,
        156,
        44,
        18,
        "Cancel",
        2,
    )
    dm.insertByName("cancel", cancel)
    set_tab_order(dm, ["ok", "cancel"], start=4)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    focus_first(dialog, "query")

    query_ctrl = dialog.getControl("query")
    results_ctrl = dialog.getControl("results")
    state = {"hits": []}

    def do_search():
        q = query_ctrl.getModel().Text
        hits = cc.search_library(base, q) if q.strip() else []
        state["hits"] = hits
        results_ctrl.getModel().StringItemList = tuple(cc.build_search_rows(hits))

    class _TextChangeListener(unohelper.Base, XTextListener):
        def textChanged(self, event):
            do_search()

        def disposing(self, event):
            pass

    query_ctrl.addTextListener(_TextChangeListener())

    result = dialog.execute()  # 1 == Next
    pos = results_ctrl.getSelectedItemPos() if result == 1 else -1
    dialog.dispose()
    return state["hits"][pos] if 0 <= pos < len(state["hits"]) else None


def _annotation_list_dialog(ctx, paper_row: dict, annotations: list[dict]) -> dict | None:
    """Single-select list of a paper's saved highlights. Returns the chosen annotation dict, or None on
    cancel/nothing picked."""
    from a11y import focus_first, set_tab_order

    smgr = ctx.ServiceManager
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 380, 220, "Insert evidence — pick a highlight"

    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height = 6, 6, 368, 14
    label.Label = str(paper_row.get("title") or "This paper")[:90]
    label.TabIndex = 0
    label.Tabstop = False
    dm.insertByName("lbl", label)

    lst = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    lst.PositionX, lst.PositionY, lst.Width, lst.Height = 6, 24, 368, 150
    lst.MultiSelection = False
    lst.StringItemList = tuple(annotation_rows(annotations))
    lst.TabIndex = 1
    dm.insertByName("list", lst)

    ok = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.PositionX, ok.PositionY, ok.Width, ok.Height, ok.Label, ok.PushButtonType = 292, 182, 40, 18, "Next", 1
    dm.insertByName("ok", ok)
    cancel = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.PositionX, cancel.PositionY, cancel.Width, cancel.Height, cancel.Label, cancel.PushButtonType = (
        336,
        182,
        38,
        18,
        "Cancel",
        2,
    )
    dm.insertByName("cancel", cancel)
    set_tab_order(dm, ["ok", "cancel"], start=2)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    focus_first(dialog, "list")

    list_ctrl = dialog.getControl("list")
    result = dialog.execute()
    pos = list_ctrl.getSelectedItemPos() if result == 1 else -1
    dialog.dispose()
    return annotations[pos] if 0 <= pos < len(annotations) else None


def _annotation_configure_dialog(ctx, base: str, annotation: dict) -> tuple[str, str | None] | None:
    """The Details/configure step: full quote + note, an editable Claim field with an explicit "Check stance"
    button (deliberately not live-per-keystroke — NLI inference is a real model call, not a fast SQLite query,
    matching Suggest-citation/citation-integrity-preflight's own explicit-action convention), a format choice,
    and an editable pre-filled locator. Returns ``(format, locator)`` on Insert, else None."""
    import unohelper
    from a11y import focus_first, labeled_field, set_tab_order
    from com.sun.star.awt import XActionListener

    smgr = ctx.ServiceManager
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 380, 320, "Insert evidence — configure"

    def _label(name, x, y, w, h, text):
        lbl = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lbl.PositionX, lbl.PositionY, lbl.Width, lbl.Height, lbl.Label = x, y, w, h, text
        lbl.MultiLine = h > 14
        dm.insertByName(name, lbl)
        return lbl

    page = annotation.get("page")
    subtitle = _label("subtitle", 6, 6, 368, 12, f"Page {page}" if page else "Page unknown")
    subtitle.TabIndex = 0
    subtitle.Tabstop = False

    quote_box = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    quote_box.PositionX, quote_box.PositionY, quote_box.Width, quote_box.Height = 6, 30, 368, 36
    quote_box.MultiLine, quote_box.ReadOnly, quote_box.Tabstop = True, True, False
    quote_box.Text = str(annotation.get("anchor_text") or "")
    labeled_field(dm, "quote_lbl", "quote", 6, 20, 60, 9, "Quote:", quote_box, 1)

    note_box = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    note_box.PositionX, note_box.PositionY, note_box.Width, note_box.Height = 6, 80, 368, 22
    note_box.MultiLine, note_box.ReadOnly, note_box.Tabstop = True, True, False
    note_box.Text = str(annotation.get("note") or "") or "(no note saved for this highlight)"
    labeled_field(dm, "note_lbl", "note", 6, 70, 60, 9, "Note:", note_box, 3)

    claim_edit = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    claim_edit.PositionX, claim_edit.PositionY, claim_edit.Width, claim_edit.Height = 6, 120, 280, 14
    claim_edit.Text = ""
    labeled_field(dm, "claim_lbl", "claim", 6, 106, 280, 12, "Claim to check (optional):", claim_edit, 5)

    check_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    check_btn.PositionX, check_btn.PositionY, check_btn.Width, check_btn.Height = 292, 118, 82, 18
    check_btn.Label = "Check stance"
    check_btn.TabIndex = 7
    dm.insertByName("check", check_btn)

    stance = _label("stance", 6, 138, 368, 14, "")
    stance.TabIndex = 8
    stance.Tabstop = False

    format_box = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    format_box.PositionX, format_box.PositionY, format_box.Width, format_box.Height = 100, 156, 274, 60
    format_box.Dropdown = True
    format_box.StringItemList = tuple(label for _value, label in FORMATS)
    labeled_field(dm, "format_lbl", "format", 6, 158, 90, 12, "Insert as:", format_box, 9)

    locator_edit = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    locator_edit.PositionX, locator_edit.PositionY, locator_edit.Width, locator_edit.Height = 100, 176, 274, 14
    locator_edit.Text = _annotation_locator(annotation) or ""
    labeled_field(dm, "locator_lbl", "locator", 6, 178, 90, 12, "Page locator:", locator_edit, 11)

    insert_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    insert_btn.PositionX, insert_btn.PositionY, insert_btn.Width, insert_btn.Height = 226, 294, 70, 18
    insert_btn.Label, insert_btn.PushButtonType = "Insert", 1
    dm.insertByName("insert", insert_btn)

    cancel_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel_btn.PositionX, cancel_btn.PositionY, cancel_btn.Width, cancel_btn.Height = 302, 294, 72, 18
    cancel_btn.Label, cancel_btn.PushButtonType = "Cancel", 2
    dm.insertByName("cancel", cancel_btn)
    set_tab_order(dm, ["insert", "cancel"], start=13)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    focus_first(dialog, "claim")

    format_ctrl = dialog.getControl("format")
    default_pos = next((i for i, (value, _label) in enumerate(FORMATS) if value == DEFAULT_FORMAT), 0)
    format_ctrl.selectItemPos(default_pos, True)

    claim_ctrl = dialog.getControl("claim")
    stance_ctrl = dialog.getControl("stance")
    locator_ctrl = dialog.getControl("locator")

    class _CheckStanceListener(unohelper.Base, XActionListener):
        def actionPerformed(self, event):
            claim = claim_ctrl.getModel().Text.strip()
            if not claim:
                stance_ctrl.getModel().Label = "Type a claim first."
                return
            try:
                stance = check_stance(base, claim, annotation)
            except Exception as exc:  # noqa: BLE001 -- a down/slow backend must not crash the dialog
                stance_ctrl.getModel().Label = f"Stance check unavailable: {exc}"
                return
            stance_ctrl.getModel().Label = (
                cc._stance_breakdown_text(stance) if stance else "No stance signal for this passage."
            )

        def disposing(self, event):
            pass

    dialog.getControl("check").addActionListener(_CheckStanceListener())

    result = dialog.execute()  # 1 == Insert
    dialog.dispose()
    if result != 1:
        return None
    fmt = FORMATS[format_ctrl.getSelectedItemPos()][0]
    locator = locator_ctrl.getModel().Text.strip() or None
    return fmt, locator


def run_insert_evidence(doc, base: str) -> str | None:
    """Top-level orchestrator (roadmap #20, Citavi-style evidence insertion): find a paper, pick one of its
    saved highlights, optionally check a typed claim's stance against it, choose an insertion format, and
    insert. Returns the new mark's rnd, or None if cancelled/nothing inserted at any step."""
    ctx = cc._component_ctx()
    paper = _paper_search_dialog(ctx, base)
    if paper is None:
        return None
    paper_id = paper.get("id")
    annotations = cc.list_paper_annotations(base, paper_id)
    if not annotations:
        cc._msgbox("This paper has no saved highlights yet. Highlight passages in the PDF viewer first.")
        return None
    annotation = _annotation_list_dialog(ctx, paper, annotations)
    if annotation is None:
        return None
    configured = _annotation_configure_dialog(ctx, base, annotation)
    if configured is None:
        return None
    fmt, locator = configured
    return insert_evidence(doc, base, paper_id, annotation, fmt, locator)
