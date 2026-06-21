"""callosum — LibreOffice (UNO) citation adapter (inc 108).

The first word-processor adapter: cite-while-you-write in LibreOffice Writer, riding callosum's backend citation
engine. It is a **thin field-placer** — it never formats citations itself. Its only jobs (per the future-track
spec `…_citationbibliographyengine.md`) are: place/track a live field, read the full ordered citation set out of
the document, and write back the rendered in-text + bibliography that the backend produced.

Live fields are **ReferenceMarks** whose *name* carries the citation's CSL-JSON payload (base64-encoded) — the
Zotero `ADDIN … CSL_CITATION` embedded-CSL-JSON convention reused as a **pattern, not code** (see README /
THIRD-PARTY-NOTICES). The marked text is the rendered citation. On refresh the adapter scans every such mark in
**document order** (a full-document scan, not the unordered name-collection), POSTs the ordered set to
`POST /citations/render-document`, and writes the position-aware result back (numeric renumbering, author-date
disambiguation are all done backend-side by citeproc).

Local-only: it talks solely to a callosum server on 127.0.0.1 (default :8080) over stdlib HTTP — no third-party
dependency (LibreOffice's bundled Python has no pip packages), no egress, never auto-inserts (every action is
user-invoked).

Install: copy this file into your LibreOffice user Scripts/python/ directory, then run the macros from
Tools → Macros → Organize Macros → Python (see README.md).

NOTE: `import uno` is deliberately **lazy** (inside the UNO functions), so the pure helpers (encode/decode/order/
request-build) import + unit-test under ordinary CPython without LibreOffice — see tests/test_libreoffice_adapter.py.
"""

from __future__ import annotations

import base64
import functools
import json
import urllib.request

# ── constants ──────────────────────────────────────────────────────────────────────────────────────────
MARK_PREFIX = "CALLOSUM_CITATION"  # ReferenceMark name prefix → identifies our live fields
BIB_BOOKMARK = "CALLOSUM_BIBLIOGRAPHY"  # bookmark marking the start of the managed bibliography block
PREF_STYLE = "CallosumStyle"  # document user-property: chosen CSL style id
PREF_LOCALE = "CallosumLocale"  # document user-property: chosen locale
DEFAULT_STYLE = "apa"
DEFAULT_LOCALE = "en-US"
DEFAULT_BASE = "http://127.0.0.1:8080"
HTTP_TIMEOUT = 20
PLACEHOLDER = "{citation}"  # transient visible text before the first render
BIB_HEADING = "References"


# ── pure helpers (no UNO — unit-tested) ──────────────────────────────────────────────────────────────────


def encode_mark_name(payload: dict, rnd: str) -> str:
    """A ReferenceMark name encoding the citation payload: ``CALLOSUM_CITATION <base64-json> <rnd>``.

    base64 keeps the JSON's braces/quotes/spaces out of the mark name (which must be a stable, simple token).
    `rnd` makes the name unique within the document (ReferenceMark names must be unique).
    """
    blob = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return f"{MARK_PREFIX} {blob} {rnd}"


def decode_mark_name(name: str) -> dict | None:
    """Inverse of :func:`encode_mark_name`. Returns ``{"rnd", "items"}`` or None if not ours / malformed.

    Defensive: any parse failure → None (a corrupt or foreign mark is skipped, never fatal).
    """
    if not isinstance(name, str) or not name.startswith(MARK_PREFIX + " "):
        return None
    parts = name.split(" ")
    if len(parts) != 3:
        return None
    _, blob, rnd = parts
    try:
        payload = json.loads(base64.b64decode(blob).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return None
    return {"rnd": rnd, "items": items}


def stamp_item_id(record: dict, paper_id: int | str) -> dict:
    """Give a CSL record the stable in-document id the render contract requires (one per cited work)."""
    out = dict(record)
    out["id"] = f"callosum-{paper_id}"
    return out


def build_render_request(fields: list[dict], style: str, locale: str) -> dict:
    """Turn ordered citation fields into the `/citations/render-document` body.

    Each field is ``{"citationID": <rnd>, "items": [<CSL-JSON>, …]}`` (in document order).
    """
    return {
        "style": style,
        "locale": locale,
        "citations": [{"citationID": f["citationID"], "items": f["items"]} for f in fields],
    }


def order_by_comparator(items: list, compare) -> list:
    """Sort `items` into ascending document order.

    `compare(a, b)` follows UNO's `XTextRangeCompare.compareRegionStarts` convention: **>0 iff a precedes b**,
    0 if same start, <0 if a follows b. (We invert it because Python's sort wants negative-when-a-first.)
    """

    def _cmp(a, b) -> int:
        c = compare(a, b)
        return -1 if c > 0 else (1 if c < 0 else 0)

    return sorted(items, key=functools.cmp_to_key(_cmp))


# ── HTTP (no UNO; stdlib only) ───────────────────────────────────────────────────────────────────────────


def _get_json(url: str, timeout: int = HTTP_TIMEOUT):
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (fixed 127.0.0.1 base; local only)
        return json.loads(r.read().decode("utf-8"))


def _post_json(url: str, body: dict, timeout: int = HTTP_TIMEOUT):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed 127.0.0.1 base; local only)
        return json.loads(r.read().decode("utf-8"))


def fetch_csl(base: str, paper_id: int | str) -> dict:
    """Fetch a library paper's canonical CSL-JSON via the inc-70 export endpoint; returns one CSL record."""
    rows = _post_json(f"{base}/papers/export", {"paper_ids": [int(paper_id)], "format": "csl-json"})
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No paper with id {paper_id} in the library.")
    return rows[0]


def render_document(base: str, request: dict) -> dict:
    return _post_json(f"{base}/citations/render-document", request)


def list_style_ids(base: str) -> set[str]:
    data = _get_json(f"{base}/citations/styles")
    return {s["id"] for s in data.get("styles", [])}


# ── UNO layer (lazy `import uno`; driven by the macro entry points + the headless self-test) ───────────────


def _get_pref(doc) -> tuple[str, str]:
    props = doc.getDocumentProperties().getUserDefinedProperties()
    style = _user_prop(props, PREF_STYLE) or DEFAULT_STYLE
    locale = _user_prop(props, PREF_LOCALE) or DEFAULT_LOCALE
    return style, locale


def _user_prop(props, name: str) -> str | None:
    try:
        return str(props.getPropertyValue(name)) or None
    except Exception:
        return None


def _set_pref(doc, style: str, locale: str) -> None:
    from com.sun.star.beans.PropertyAttribute import REMOVABLE

    props = doc.getDocumentProperties().getUserDefinedProperties()
    for name, value in ((PREF_STYLE, style), (PREF_LOCALE, locale)):
        if props.getPropertySetInfo().hasPropertyByName(name):
            props.setPropertyValue(name, value)
        else:
            props.addProperty(name, REMOVABLE, value)


def _insertion_cursor(doc):
    """A text cursor at the current insertion point (view cursor), else the document end."""
    text = doc.getText()
    try:
        view = doc.getCurrentController().getViewCursor()
        return text.createTextCursorByRange(view.getStart())
    except Exception:
        return text.createTextCursorByRange(text.getEnd())


def insert_citation(doc, paper_id, base: str = DEFAULT_BASE, cursor=None) -> str:
    """Insert a live citation ReferenceMark for `paper_id` at the cursor, then re-render the document.

    Returns the new mark's `rnd` tag. (UNO; the macro entry point supplies the dialog + current doc.)
    """
    record = stamp_item_id(fetch_csl(base, paper_id), paper_id)
    rnd = _new_rnd(doc)
    payload = {"items": [record]}
    text = doc.getText()
    if cursor is None:
        cursor = _insertion_cursor(doc)
    cursor.setString(PLACEHOLDER)  # transient visible text; the mark absorbs this range
    mark = doc.createInstance("com.sun.star.text.ReferenceMark")
    mark.Name = encode_mark_name(payload, rnd)
    text.insertTextContent(cursor, mark, True)  # absorb=True → the mark wraps the placeholder range
    refresh(doc, base)
    return rnd


def _our_marks(doc) -> list:
    marks = doc.getReferenceMarks()
    return [marks.getByName(n) for n in marks.getElementNames() if decode_mark_name(n) is not None]


def scan_citations_in_order(doc) -> list[dict]:
    """Full-document scan → citation fields in document order.

    Each field: ``{"citationID": rnd, "items": [...], "_mark": <ReferenceMark>}``. Ordering is by the mark's
    anchor start via `XTextRangeCompare.compareRegionStarts` (not the unordered name collection — the spec's
    full-scan-tolerant contract, so later weak-iterator targets aren't blocked).
    """
    text = doc.getText()
    fields = []
    for mark in _our_marks(doc):
        decoded = decode_mark_name(mark.Name)
        if decoded is None:
            continue
        fields.append({"citationID": decoded["rnd"], "items": decoded["items"], "_mark": mark})

    def _compare(a, b) -> int:
        return text.compareRegionStarts(a["_mark"].getAnchor(), b["_mark"].getAnchor())

    return order_by_comparator(fields, _compare)


def refresh(doc, base: str = DEFAULT_BASE) -> dict:
    """The live-field loop: scan → render-document → write back in-text + bibliography. Returns the response."""
    style, locale = _get_pref(doc)
    fields = scan_citations_in_order(doc)
    if not fields:
        _write_bibliography(doc, [])
        return {"citations": [], "bibliography_text": ""}
    response = render_document(base, build_render_request(fields, style, locale))
    rendered = {c["citationID"]: c.get("text", "") for c in response.get("citations", [])}
    # Capture (mark name, new text) BEFORE any edit. Recreating a mark mutates the ReferenceMarks collection and
    # invalidates other held mark references, so we keep only immutable names here and re-fetch each mark fresh.
    plan = [
        (field["_mark"].Name, rendered[field["citationID"]]) for field in fields if rendered.get(field["citationID"])
    ]
    for name, text_out in plan:
        mark = doc.getReferenceMarks().getByName(name)  # fresh handle each time (never a stale ref)
        _replace_mark_text(doc, mark, text_out)
    _write_bibliography(doc, response.get("bibliography_text", "").splitlines())
    return response


def _replace_mark_text(doc, mark, new_text: str) -> None:
    """Update a citation's rendered text while KEEPING the live field.

    Setting a ReferenceMark anchor's whole string destroys the mark (replacing a mark's entire range removes it).
    So we recreate the mark around the new text: snapshot the range + name, drop the old mark, replace the text in
    place, then re-wrap a fresh same-named mark (the payload/`rnd` is preserved → the citationID stays stable).
    The text is written as **plain text** (`setString`), never an HTML/markup path.
    """
    text = doc.getText()
    name = mark.Name
    cursor = text.createTextCursorByRange(mark.getAnchor())  # spans the marked range
    text.removeTextContent(mark)  # remove the old mark boundary; the text + cursor range survive
    cursor.setString(new_text)  # replace the wrapped text in place
    fresh = doc.createInstance("com.sun.star.text.ReferenceMark")
    fresh.Name = name
    text.insertTextContent(cursor, fresh, True)  # absorb=True → re-wrap the new text


def _write_bibliography(doc, entries: list[str]) -> None:
    """(Re)build the managed bibliography block: everything from the `CALLOSUM_BIBLIOGRAPHY` bookmark to the
    document end. Cleared + rewritten each refresh; an empty `entries` clears it.

    The clear deletes the old block (and the bookmark inside it), so we keep working with the SAME cursor — never
    re-read the now-stale bookmark anchor — then drop a fresh bookmark at that spot.
    """
    text = doc.getText()
    bookmarks = doc.getBookmarks()
    if bookmarks.hasByName(BIB_BOOKMARK):
        start = bookmarks.getByName(BIB_BOOKMARK).getAnchor().getStart()
        cursor = text.createTextCursorByRange(start)
        cursor.gotoEnd(True)  # select bookmark-start … document-end
        cursor.setString("")  # deletes the old bib block + its bookmark; cursor now collapsed at that spot
    else:
        cursor = text.createTextCursorByRange(text.getEnd())
        if _has_text(text):
            text.insertControlCharacter(cursor, _PARAGRAH_BREAK(), False)
    _place_bib_bookmark(doc, cursor)  # fresh bookmark at the (now-empty) bibliography location
    if not entries:
        return
    text.insertString(cursor, BIB_HEADING + "\n", False)
    text.insertString(cursor, "\n".join(entries) + "\n", False)


def _place_bib_bookmark(doc, cursor) -> None:
    text = doc.getText()
    bookmarks = doc.getBookmarks()
    if bookmarks.hasByName(BIB_BOOKMARK):
        text.removeTextContent(bookmarks.getByName(BIB_BOOKMARK))
    mark = doc.createInstance("com.sun.star.text.Bookmark")
    mark.Name = BIB_BOOKMARK
    text.insertTextContent(cursor, mark, False)  # zero-width insert at the cursor; cursor stays put


def _has_text(text) -> bool:
    return bool(text.getString().strip())


def _PARAGRAH_BREAK():
    from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK

    return PARAGRAPH_BREAK


def set_style(doc, style: str, locale: str, base: str = DEFAULT_BASE) -> None:
    """Validate the style against the server's bundled set, persist the preference, re-render."""
    valid = list_style_ids(base)
    if style not in valid:
        raise ValueError(f"Unknown style '{style}'. Available: {', '.join(sorted(valid))}")
    _set_pref(doc, style, locale or DEFAULT_LOCALE)
    refresh(doc, base)


def flatten(doc) -> int:
    """Convert live fields → static text: remove every CALLOSUM ReferenceMark + the bibliography bookmark.

    The rendered text stays in place; only the live-field wrappers are removed. One-way. Returns the count
    of citation marks removed.
    """
    text = doc.getText()
    # Capture names first, then unlink each by a fresh handle — removing a mark mutates the collection and
    # invalidates other held references (the same UNO trap as the write-back). Removing a ReferenceMark also
    # deletes its wrapped text, so we keep the rendered text and re-insert it as plain static text.
    names = [n for n in doc.getReferenceMarks().getElementNames() if decode_mark_name(n) is not None]
    for name in names:
        mark = doc.getReferenceMarks().getByName(name)
        cursor = text.createTextCursorByRange(mark.getAnchor())
        rendered = cursor.getString()
        text.removeTextContent(mark)
        cursor.setString(rendered)  # re-insert the rendered citation as static text (mark is gone)
    bookmarks = doc.getBookmarks()
    if bookmarks.hasByName(BIB_BOOKMARK):
        text.removeTextContent(bookmarks.getByName(BIB_BOOKMARK))  # zero-width bookmark only; bib text stays
    return len(names)


def _new_rnd(doc) -> str:
    """A document-unique short tag for a new mark (counter over existing marks; deterministic, no RNG)."""
    existing = {decode_mark_name(n)["rnd"] for n in doc.getReferenceMarks().getElementNames() if decode_mark_name(n)}
    i = 1
    while f"c{i}" in existing:
        i += 1
    return f"c{i}"


# ── macro entry points (shown in Tools → Macros) ─────────────────────────────────────────────────────────


def _current_doc():
    # XSCRIPTCONTEXT is injected into every LibreOffice Python macro by the script provider (bridge already up).
    return XSCRIPTCONTEXT.getDocument()  # noqa: F821


def _input_box(doc, title: str, prompt: str, default: str = "") -> str | None:
    """A minimal modal text-input dialog (UNO has no native input box). Returns the string, or None if cancelled."""
    smgr = _component_ctx().ServiceManager
    ctx = _component_ctx()
    dialog_model = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dialog_model.Width, dialog_model.Height, dialog_model.Title = 200, 70, title
    label = dialog_model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height, label.Label = 6, 6, 188, 20, prompt
    dialog_model.insertByName("lbl", label)
    edit = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
    edit.PositionX, edit.PositionY, edit.Width, edit.Height, edit.Text = 6, 28, 188, 14, default
    dialog_model.insertByName("edit", edit)
    ok = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.PositionX, ok.PositionY, ok.Width, ok.Height, ok.Label, ok.PushButtonType = 110, 50, 40, 14, "OK", 1
    dialog_model.insertByName("ok", ok)
    cancel = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.PositionX, cancel.PositionY, cancel.Width, cancel.Height, cancel.Label, cancel.PushButtonType = (
        154,
        50,
        40,
        14,
        "Cancel",
        2,
    )
    dialog_model.insertByName("cancel", cancel)
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dialog_model)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    result = dialog.execute()  # 1 == OK
    value = dialog.getControl("edit").getModel().Text if result == 1 else None
    dialog.dispose()
    return value


def _component_ctx():
    return XSCRIPTCONTEXT.getComponentContext()  # noqa: F821


def _msgbox(message: str, title: str = "callosum") -> None:
    smgr = _component_ctx().ServiceManager
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", _component_ctx())
    box = toolkit.createMessageBox(
        None,
        1,
        1,
        title,
        message,  # INFOBOX, BUTTONS_OK
    )
    box.execute()
    box.dispose()


def CallosumInsertCitation(*_args):
    doc = _current_doc()
    paper_id = _input_box(doc, "Insert citation", "callosum paper id:")
    if not paper_id:
        return
    try:
        insert_citation(doc, paper_id.strip(), DEFAULT_BASE)
    except Exception as exc:  # surface, never crash Writer
        _msgbox(f"Insert failed: {exc}")


def CallosumRefresh(*_args):
    try:
        refresh(_current_doc(), DEFAULT_BASE)
    except Exception as exc:
        _msgbox(f"Refresh failed: {exc}")


def CallosumSetStyle(*_args):
    doc = _current_doc()
    style, locale = _get_pref(doc)
    chosen = _input_box(doc, "Citation style", "CSL style id (e.g. apa, ieee, nature):", style)
    if not chosen:
        return
    loc = _input_box(doc, "Locale", "Locale (en-US / en-GB):", locale) or DEFAULT_LOCALE
    try:
        set_style(doc, chosen.strip(), loc.strip(), DEFAULT_BASE)
    except Exception as exc:
        _msgbox(f"Set style failed: {exc}")


def CallosumFlatten(*_args):
    doc = _current_doc()
    n = flatten(doc)
    _msgbox(f"Flattened {n} citation(s) to static text. Live updating is now off for this document.")


g_exportedScripts = (CallosumInsertCitation, CallosumRefresh, CallosumSetStyle, CallosumFlatten)
