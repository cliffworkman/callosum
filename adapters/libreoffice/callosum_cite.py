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
import os
import urllib.parse
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
# Where the extension persists the (optional) server URL — outside LibreOffice's read-only extension package, in the
# OS user home (the same `~/.callosum/` callosum uses for app-settings). Lets the .oxt point at a non-default port
# without editing source. Pure file I/O (no UNO), so it's unit-testable with a temp path.
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".callosum", "libreoffice.json")

# Set by the .oxt dispatcher (callosum_addon.py) so the dialog helpers can find a component context when this code
# runs inside a UNO component (where the macro-only `XSCRIPTCONTEXT` global does NOT exist). None ⇒ macro mode.
_DISPATCH_CTX = None


def get_server_url(path: str = CONFIG_PATH) -> str:
    """The configured callosum server base URL (sidecar JSON), or DEFAULT_BASE. Pure — no UNO."""
    try:
        with open(path, encoding="utf-8") as f:
            url = json.load(f).get("base")
        if isinstance(url, str) and url.strip():
            return url.strip().rstrip("/")
    except Exception:
        pass
    return DEFAULT_BASE


def set_server_url(url: str, path: str = CONFIG_PATH) -> None:
    """Persist the server base URL to the sidecar JSON (blank ⇒ reset to DEFAULT_BASE). Pure — no UNO."""
    cleaned = (url or "").strip().rstrip("/") or DEFAULT_BASE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"base": cleaned}, f)


def _base() -> str:
    return get_server_url()


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


SUGGEST_QUOTE_MAX = 90  # truncate the matched-passage preview in a pick-list row


def build_suggest_rows(suggestions: list[dict]) -> list[str]:
    """One display row per suggestion for the pick-list: stance + author/year + match + a quote preview.

    The quote is the *reason* (the honesty surface) — a truncated preview so the writer can judge fit before
    inserting. Pure (no UNO); parallel to `suggestions` (row index → suggestion → paper_id).
    """
    rows = []
    for s in suggestions:
        stance = s.get("stance")
        label = stance.get("label") if isinstance(stance, dict) else None
        tag = label or "no stance"
        author = str(s.get("author") or "").strip()
        year = s.get("year")
        who = " ".join(p for p in (author, str(year) if year else "") if p)
        if not who:
            who = str(s.get("title") or f"paper {s.get('paper_id')}")
        try:
            match = f"{float(s.get('match_score', 0)):.2f}"
        except (TypeError, ValueError):
            match = "?"
        quote = " ".join(str(s.get("quote") or "").split())
        if len(quote) > SUGGEST_QUOTE_MAX:
            quote = quote[:SUGGEST_QUOTE_MAX].rstrip() + "…"
        rows.append(f'[{tag}] {who} · match {match} — "{quote}"')
    return rows


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


SUGGEST_TIMEOUT = 90  # suggest does local ML work (embed + NLI); the first call loads the models — give it room


def fetch_suggestions(base: str, text: str, top_k: int = 5) -> list[dict]:
    """Citation suggestions for a draft sentence via the inc-156 endpoint; returns the suggestions list.

    Local-only (127.0.0.1); the engine ranks the library by relevance + evaluates each candidate's stance. The
    first call loads the embedding + NLI models server-side, so it uses a longer timeout than render/export.
    Defensive on shape — a malformed/empty response yields [].
    """
    data = _post_json(
        f"{base}/citations/suggest", {"text": text, "top_k": top_k, "evaluate": True}, timeout=SUGGEST_TIMEOUT
    )
    suggestions = data.get("suggestions") if isinstance(data, dict) else None
    return suggestions if isinstance(suggestions, list) else []


SEARCH_TITLE_MAX = 90  # truncate the title in a pick-list row


def search_library(base: str, query: str, limit: int = 20) -> list[dict]:
    """Search the library for papers matching `query` (author / title / year / venue …) via the inc-89 endpoint.
    Returns a list of paper rows ({id, title, authors, year, venue, …}); [] on a blank query / malformed shape.
    This is the familiar 'type to find a paper' cite path (vs suggest-from-the-sentence)."""
    q = (query or "").strip()
    if not q:
        return []
    url = f"{base}/papers?q={urllib.parse.quote(q)}&limit={int(limit)}"
    data = _get_json(url)
    return data if isinstance(data, list) else []


def build_search_rows(papers: list[dict]) -> list[str]:
    """One pick-list row per search hit: ``Author [et al.] Year — Title`` (title truncated). Pure (no UNO)."""
    rows = []
    for p in papers:
        authors = p.get("authors") or []
        who = authors[0] if authors else "—"
        if len(authors) > 1:
            who += " et al."
        year = p.get("year") or "n.d."
        title = (p.get("title") or "Untitled").strip()
        if len(title) > SEARCH_TITLE_MAX:
            title = title[:SEARCH_TITLE_MAX] + "…"
        rows.append(f"{who} {year} — {title}")
    return rows


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


def _insertion_cursor_at_end(doc):
    """A collapsed cursor at the END of the current selection — so a suggested cite lands AFTER the highlighted
    sentence (for a collapsed caret, end == the caret). Falls back to the plain insertion point."""
    text = doc.getText()
    try:
        view = doc.getCurrentController().getViewCursor()
        return text.createTextCursorByRange(view.getEnd())
    except Exception:
        return _insertion_cursor(doc)


def current_query_text(doc) -> str:
    """The text to suggest citations for: the current SELECTION if non-empty (highlight-to-suggest), else the
    paragraph around the caret. Returns "" if neither yields text."""
    try:
        view = doc.getCurrentController().getViewCursor()
    except Exception:
        return ""
    selected = str(view.getString() or "").strip()
    if selected:
        return selected
    try:
        para = doc.getText().createTextCursorByRange(view.getStart())
        para.gotoStartOfParagraph(False)
        para.gotoEndOfParagraph(True)
    except Exception:
        return ""
    return str(para.getString() or "").strip()


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


_SUGGEST_CAVEAT = "Pick a paper to cite for the selected text — ranked by relevance; verify the source. You decide."


def _suggest_listbox(
    doc, rows: list[str], title: str = "Suggest citations", caveat: str = _SUGGEST_CAVEAT
) -> int | None:
    """A modal pick-list (mirrors _input_box, with a ListBox). Returns the chosen row index, or None if
    cancelled / nothing selected. Shared by Suggest (stance + quote rows) and Add-citation (search rows);
    the writer reads each row and picks — nothing auto-inserts."""
    smgr = _component_ctx().ServiceManager
    ctx = _component_ctx()
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 320, 172, title
    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height = 6, 6, 308, 22
    label.Label = caveat
    label.MultiLine = True
    dm.insertByName("lbl", label)
    lst = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    lst.PositionX, lst.PositionY, lst.Width, lst.Height = 6, 32, 308, 110
    lst.Dropdown = False
    lst.MultiSelection = False
    lst.StringItemList = tuple(rows)
    dm.insertByName("list", lst)
    ok = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.PositionX, ok.PositionY, ok.Width, ok.Height, ok.Label, ok.PushButtonType = 222, 150, 44, 16, "Insert", 1
    dm.insertByName("ok", ok)
    cancel = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.PositionX, cancel.PositionY, cancel.Width, cancel.Height, cancel.Label, cancel.PushButtonType = (
        270,
        150,
        44,
        16,
        "Cancel",
        2,
    )
    dm.insertByName("cancel", cancel)
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    result = dialog.execute()  # 1 == OK (Insert)
    pos = dialog.getControl("list").getSelectedItemPos() if result == 1 else -1
    dialog.dispose()
    if result != 1 or pos is None or pos < 0 or pos >= len(rows):
        return None
    return int(pos)


def _component_ctx():
    # Component mode (.oxt dispatcher) sets _DISPATCH_CTX; macro mode uses the injected XSCRIPTCONTEXT global.
    if _DISPATCH_CTX is not None:
        return _DISPATCH_CTX
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


def suggest_and_insert(doc, base: str = DEFAULT_BASE) -> str | None:
    """Suggest library papers to cite for the current sentence, let the user pick one, and insert it.

    Returns the new mark's `rnd` tag, or None if nothing was inserted (no text / no suggestions / cancelled).
    The suggestion + stance signal is the backend's (inc 156); this only presents the evidence + inserts the
    chosen cite via the existing insert_citation flow.
    """
    text = current_query_text(doc)
    if not text:
        _msgbox("Select a sentence (or place the cursor in one) to suggest citations for.")
        return None
    suggestions = fetch_suggestions(base, text)
    if not suggestions:
        _msgbox("No related papers in your library for that sentence.")
        return None
    idx = _suggest_listbox(doc, build_suggest_rows(suggestions))
    if idx is None:
        return None
    return insert_citation(doc, suggestions[idx].get("paper_id"), base, cursor=_insertion_cursor_at_end(doc))


def add_citation_by_search(doc, base: str) -> str | None:
    """Add a citation by SEARCHING the library: prompt for a query, show matching papers, insert the chosen one.
    The familiar 'type to find a paper' cite flow (vs suggest-from-the-sentence). Returns the mark rnd or None."""
    query = _input_box(doc, "Add citation", "Search your library (author / title / year):")
    if not query or not query.strip():
        return None
    papers = search_library(base, query.strip())
    if not papers:
        _msgbox("No matching papers in your library.")
        return None
    idx = _suggest_listbox(doc, build_search_rows(papers), "Add citation", "Pick a paper from your library to cite.")
    if idx is None:
        return None
    return insert_citation(doc, papers[idx]["id"], base, cursor=_insertion_cursor(doc))


# ── interactive flows (the prompt+act bodies; shared by the macro entry points AND the .oxt dispatcher) ─────


def insert_citation_interactive(doc, base: str) -> None:
    """Prompt for a paper id and insert it (the by-id path; the search path is add_citation_by_search)."""
    paper_id = _input_box(doc, "Insert citation", "callosum paper id:")
    if not paper_id:
        return
    insert_citation(doc, paper_id.strip(), base)


def set_style_interactive(doc, base: str) -> None:
    style, locale = _get_pref(doc)
    chosen = _input_box(doc, "Citation style", "CSL style id (e.g. apa, ieee, nature):", style)
    if not chosen:
        return
    loc = _input_box(doc, "Locale", "Locale (en-US / en-GB):", locale) or DEFAULT_LOCALE
    set_style(doc, chosen.strip(), loc.strip(), base)


def flatten_interactive(doc) -> None:
    n = flatten(doc)
    _msgbox(f"Flattened {n} citation(s) to static text. Live updating is now off for this document.")


def insert_statement(doc, base: str) -> None:
    """Insert the CRediT contribution statement the user built + staged in the callosum web UI at the cursor.

    The role grid lives in the web app; this macro can only reach the server over HTTP, so the UI stages the built
    text (`POST /credit/pending`) and this pulls it (`GET /credit/pending`). Plain static text — a contributorship
    statement is prose the author asserts, not a live citation field, so no ReferenceMark wrapper. Local, no egress.
    """
    resp = _get_json(f"{base}/credit/pending")
    text = str((resp or {}).get("text") or "").strip()
    if not text:
        _msgbox(
            "No staged CRediT statement — in callosum open Theory → CRediT statement, build one, and click "
            '"Send to LibreOffice" first.'
        )
        return
    doc.getText().insertString(_insertion_cursor(doc), text + "\n", False)


def set_server_url_interactive(doc) -> None:
    url = _input_box(doc, "callosum server URL", "Server URL (e.g. http://127.0.0.1:8080):", get_server_url())
    if url is None:
        return
    set_server_url(url.strip())
    _msgbox(f"callosum server URL set to {get_server_url()}.")


# Action registry — the single source of truth for what each Callosum command does. Keyed by the action name the
# .oxt Addons.xcu menu/toolbar dispatches (`service:com.callosum.cite.Dispatcher?<action>`). Each value takes
# (doc, base); flatten/setServerUrl ignore base. `add_citation_by_search` (search-to-cite) is added in SP2.
_ACTIONS = {
    "addCitation": add_citation_by_search,
    "insert": insert_citation_interactive,
    "suggest": suggest_and_insert,
    "refresh": refresh,
    "setStyle": set_style_interactive,
    "flatten": lambda doc, base: flatten_interactive(doc),
    "insertStatement": insert_statement,
    "setServerUrl": lambda doc, base: set_server_url_interactive(doc),
}


def dispatch(action: str, doc, base: str) -> None:
    """Run a named action against `doc`. Shared by the macro entry points (macro mode) and the .oxt dispatcher
    (component mode); the caller resolves doc + base and wraps errors."""
    _ACTIONS[action](doc, base)


def _macro(action: str) -> None:
    """Macro-mode entry point body: resolve the doc + base from the script context, run the action, surface errors."""
    try:
        dispatch(action, _current_doc(), _base())
    except Exception as exc:  # surface, never crash Writer
        _msgbox(f"{action}: {exc}")


# ── macro entry points (Tools → Macros → Organize Macros → Python; also bundled in the .oxt) ───────────────


def CallosumAddCitation(*_args):
    _macro("addCitation")


def CallosumInsertCitation(*_args):
    _macro("insert")


def CallosumSuggestCitations(*_args):
    _macro("suggest")


def CallosumRefresh(*_args):
    _macro("refresh")


def CallosumSetStyle(*_args):
    _macro("setStyle")


def CallosumFlatten(*_args):
    _macro("flatten")


def CallosumInsertStatement(*_args):
    _macro("insertStatement")


def CallosumSetServerUrl(*_args):
    _macro("setServerUrl")


g_exportedScripts = (
    CallosumAddCitation,
    CallosumInsertCitation,
    CallosumSuggestCitations,
    CallosumRefresh,
    CallosumSetStyle,
    CallosumFlatten,
    CallosumInsertStatement,
    CallosumSetServerUrl,
)
