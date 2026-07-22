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
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

# ── constants ──────────────────────────────────────────────────────────────────────────────────────────
MARK_PREFIX = "CALLOSUM_CITATION"  # ReferenceMark name prefix → identifies our live fields
BIB_BOOKMARK = "CALLOSUM_BIBLIOGRAPHY"  # bookmark marking the START of the managed bibliography block
# The END of the managed range (P0 phase 7, backlog #33/#34) — a bookmark PAIR bounds the block so a rebuild
# never touches text.getEnd(), replacing the old "bookmark to document end" design that could silently destroy
# any user text placed after the bibliography.
BIB_BOOKMARK_END = "CALLOSUM_BIBLIOGRAPHY_END"
PREF_BIB_AUTO = "CallosumBibAuto"  # document user-property: "0" pauses bibliography rebuilds on refresh (P0 phase 7)
# Mark-payload schema version (inc TBD, P0 phase 1 of the LibreOffice-adapter rework — backlog #33/#34). v1 is the
# original shape (no "v" key, always exactly one item, no per-instance fields) and is still read losslessly; v2
# adds optional per-occurrence citeproc-cite properties (locator/label/prefix/suffix/suppress-author/author-only)
# to each item, alongside the item's own CSL-JSON fields — never written into the paper's own library record.
SCHEMA_VERSION = 2
SUPPORTED_VERSIONS = {1, 2}
# Per-item keys `_normalize_item` guarantees are present on every decoded item, defaulted when absent. Named after
# citeproc-js's own citationItems properties (not the roadmap's parallel vocabulary) so there is zero translation
# layer between what a mark stores and what the backend/citeproc actually consumes.
_ITEM_DEFAULTS = {
    "locator": None,
    "label": None,
    "prefix": None,
    "suffix": None,
    "suppress-author": False,
    "author-only": False,
    "custom_override": None,  # adapter-side only; never sent to the backend (see build_render_request)
}
# The exact CSL locator-label vocabulary the backend validates against (P0 phase 5b, backlog #33/#34) — MUST
# match `CSL_LOCATOR_LABELS` in `app/backend/api/routers/citations.py` exactly. Duplicated rather than imported:
# this adapter runs under LibreOffice's own bundled Python, a separate process/environment with no access to
# the backend's Python package — this is a fixed CSL-spec vocabulary, not something that drifts independently.
CSL_LOCATOR_LABELS = (
    "book",
    "chapter",
    "column",
    "figure",
    "folio",
    "issue",
    "line",
    "note",
    "opus",
    "page",
    "paragraph",
    "part",
    "scene",
    "section",
    "sub-verbo",
    "supplement",
    "table",
    "verse",
    "volume",
)
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

    Always stamps the current ``SCHEMA_VERSION`` — so every mark any code rewrites from here forward (a normal
    refresh, an insert, anything later) silently upgrades to the current schema; no explicit document migration
    is ever needed. A caller's own ``"v"`` key (if any) is overwritten, not merged — this function is the single
    place that decides what version is being written.
    """
    stamped = {**payload, "v": SCHEMA_VERSION}
    blob = base64.b64encode(json.dumps(stamped, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return f"{MARK_PREFIX} {blob} {rnd}"


def _normalize_item(it: dict) -> dict:
    """Fill in the v2 per-occurrence keys a decoded item is missing, defaulted (see ``_ITEM_DEFAULTS``). Pure —
    no UNO. Lets every caller (refresh, scan, a future composer) see one consistent item shape regardless of
    whether the mark that produced it was written as v1 (none of these keys present) or v2 (some/all present)."""
    out = dict(it)
    for key, default in _ITEM_DEFAULTS.items():
        out.setdefault(key, default)
    return out


def decode_mark_name(name: str) -> dict | None:
    """Inverse of :func:`encode_mark_name`. Returns ``{"rnd", "v", "items", "sort"}`` or None if not ours /
    malformed. ``items`` is None (with ``"unsupported": True``) for a schema version we don't recognize — ours,
    but from a future adapter version; never guessed at, never treated as foreign.

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
    v = payload.get("v", 1)  # absent "v" key == the original (v1) shape
    if v not in SUPPORTED_VERSIONS:
        return {"rnd": rnd, "v": v, "items": None, "unsupported": True}
    return {"rnd": rnd, "v": v, "items": [_normalize_item(it) for it in items], "sort": payload.get("sort", "auto")}


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
    """Fetch a library paper's canonical CSL-JSON via the inc-70 export endpoint; returns one CSL record.

    Raises ``ValueError`` if the paper doesn't exist. The endpoint 422s on an all-missing/trashed result
    rather than returning 200 with an empty list (`routers/papers.py::export_citations`) — confirmed
    empirically by the phase-9 diagnostics spike, which found this function's own former "empty rows" check
    was dead code: a genuinely missing paper always raises `HTTPError` first, never reaches it.
    """
    try:
        rows = _post_json(f"{base}/papers/export", {"paper_ids": [int(paper_id)], "format": "csl-json"})
    except urllib.error.HTTPError as exc:
        if exc.code == 422:  # this endpoint's only 422 is "no existing (non-trashed) papers to export"
            raise ValueError(f"No paper with id {paper_id} in the library.") from exc
        raise
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


def bib_auto_enabled(doc) -> bool:
    """Whether the bibliography auto-rebuilds on refresh (P0 phase 7). Default True — only an explicit "0"
    (set via `set_bib_auto`) pauses it, so a fresh/never-touched document keeps today's behavior unchanged."""
    props = doc.getDocumentProperties().getUserDefinedProperties()
    return _user_prop(props, PREF_BIB_AUTO) != "0"


def set_bib_auto(doc, enabled: bool) -> None:
    from com.sun.star.beans.PropertyAttribute import REMOVABLE

    props = doc.getDocumentProperties().getUserDefinedProperties()
    value = "1" if enabled else "0"
    if props.getPropertySetInfo().hasPropertyByName(PREF_BIB_AUTO):
        props.setPropertyValue(PREF_BIB_AUTO, value)
    else:
        props.addProperty(PREF_BIB_AUTO, REMOVABLE, value)


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


def insert_citation_items(doc, items: list[dict], base: str = DEFAULT_BASE, cursor=None) -> str:
    """Insert a live citation ReferenceMark wrapping ONE OR MORE works at the cursor, then re-render the
    document (Phase 5a/5b, backlog #33/#34 — generalizes the original single-item `insert_citation`, now a thin
    wrapper over this). Each `items` entry is ``{"paper_id": ..., **optional per-occurrence overrides}`` —
    locator/label/prefix/suffix/suppress-author/author-only (Phase 5b); any key besides `paper_id` that's
    omitted defaults via `_normalize_item`, exactly like a decoded v1 mark's items would. Item order becomes
    the citation's initial order — subject to whatever the chosen CSL style's own `<citation><sort>` does at
    render time regardless (4 of the 7 bundled styles define one; confirmed in Phase 3 that a composer preview
    must always be a real round-trip, never simulated, for exactly this reason).

    Returns the new mark's `rnd` tag. (UNO; the macro entry point / composer supplies the dialog + current doc.)
    """
    records = []
    for it in items:
        paper_id = it["paper_id"]
        record = stamp_item_id(fetch_csl(base, paper_id), paper_id)
        overrides = {k: v for k, v in it.items() if k != "paper_id"}
        record.update(_normalize_item(overrides))
        records.append(record)
    rnd = _new_rnd(doc)
    payload = {"items": records}
    text = doc.getText()
    if cursor is None:
        cursor = _insertion_cursor(doc)
    cursor.setString(PLACEHOLDER)  # transient visible text; the mark absorbs this range
    mark = doc.createInstance("com.sun.star.text.ReferenceMark")
    mark.Name = encode_mark_name(payload, rnd)
    text.insertTextContent(cursor, mark, True)  # absorb=True → the mark wraps the placeholder range
    refresh(doc, base)
    return rnd


def insert_citation(doc, paper_id, base: str = DEFAULT_BASE, cursor=None) -> str:
    """Insert a live citation ReferenceMark for a SINGLE paper_id, no per-occurrence overrides — a thin wrapper
    over `insert_citation_items` (the common case; every existing caller keeps working unchanged)."""
    return insert_citation_items(doc, [{"paper_id": paper_id}], base, cursor)


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
        if decoded is None or decoded.get("unsupported"):
            continue  # ours but a schema version this adapter doesn't understand — leave untouched, never guess
        fields.append({"citationID": decoded["rnd"], "items": decoded["items"], "_mark": mark})

    def _compare(a, b) -> int:
        return text.compareRegionStarts(a["_mark"].getAnchor(), b["_mark"].getAnchor())

    return order_by_comparator(fields, _compare)


def mark_at_cursor(doc) -> dict | None:
    """Find the citation whose ReferenceMark anchor contains the current view-cursor position (the start of the
    current selection, or the collapsed caret) — the shared primitive Edit Citation / Delete Citation / merge /
    split all need (P0 phase 4, backlog #33/#34) to resolve "which EXISTING citation is this action about."
    Every action before this one either inserts a brand-new mark or operates over ALL marks; this is the first
    "which ONE mark is the user pointing at" lookup.

    Returns the same shape a `scan_citations_in_order` field has (``{"citationID", "items", "_mark"}``), so a
    caller can treat "the mark at the cursor" and "a mark from the full scan" identically. Returns None if the
    cursor isn't inside any recognized citation mark (including a foreign/malformed one, or one from an
    unsupported future schema version — `scan_citations_in_order` already excludes both, so reusing it here
    means this function never needs its own decode/skip logic to drift out of sync with that one).
    """
    text = doc.getText()
    try:
        cursor_range = doc.getCurrentController().getViewCursor().getStart()
    except Exception:
        return None
    for field in scan_citations_in_order(doc):
        anchor = field["_mark"].getAnchor()
        if (
            text.compareRegionStarts(anchor.getStart(), cursor_range) >= 0
            and text.compareRegionStarts(cursor_range, anchor.getEnd()) >= 0
        ):
            return field
    return None


def refresh(doc, base: str = DEFAULT_BASE, bib_cursor=None) -> dict:
    """The live-field loop: scan → render-document → write back in-text + bibliography. Returns the response.

    The write-back (per-mark text replace + bibliography rebuild) is wrapped in an UndoManager-grouped
    transaction (P0 phase 2, backlog #33/#34): if a UNO failure hits partway through — e.g. a concurrent edit
    invalidating a mark's range — the whole group is undone in a single call and verified against a
    pre-mutation snapshot, so the document never ends up mixed (some marks updated, the bibliography stale or
    missing). The render HTTP call itself already happens safely-ordered *before* any mutation begins — a
    network failure there was always a no-op — this only adds a rollback for failures during the mutation itself.

    `bib_cursor`, if given, moves (or creates) the bibliography at that position instead of its existing location
    — "Insert bibliography here" (P0 phase 7). An explicit `bib_cursor` request always writes, even when
    automatic rebuilding is otherwise paused (`bib_auto_enabled(doc)` is False) — pausing the passive
    every-refresh rebuild shouldn't silently swallow a deliberate "put it here" action.
    """
    style, locale = _get_pref(doc)
    fields = scan_citations_in_order(doc)
    if not fields:
        _transactional_apply(doc, [], [], bib_cursor=bib_cursor)
        return {"citations": [], "bibliography_text": ""}
    response = render_document(base, build_render_request(fields, style, locale))
    rendered = {c["citationID"]: c.get("text", "") for c in response.get("citations", [])}
    # Capture (mark name, new text) BEFORE any edit. Recreating a mark mutates the ReferenceMarks collection and
    # invalidates other held mark references, so we keep only immutable names here and re-fetch each mark fresh.
    plan = [
        (field["_mark"].Name, rendered[field["citationID"]]) for field in fields if rendered.get(field["citationID"])
    ]
    _transactional_apply(doc, plan, response.get("bibliography_text", "").splitlines(), bib_cursor=bib_cursor)
    return response


def _snapshot_marks(doc, names: list[str]) -> dict[str, str]:
    """Each named mark's CURRENT anchor text, keyed by name. Used only as the post-rollback verification oracle
    (never the rollback mechanism itself — that's the UndoManager): after an undo(), every name here must map
    back to the same text, proving the rollback actually restored the pre-mutation state rather than merely
    reverting *something*. A name no longer present after undo (e.g. a mark that was never touched because the
    failure hit before it) is simply absent from both snapshots and compares equal."""
    marks = doc.getReferenceMarks()
    return {name: marks.getByName(name).getAnchor().getString() for name in names if marks.hasByName(name)}


def _transactional_apply(doc, plan: list[tuple[str, str]], bib_entries: list[str], bib_cursor=None) -> None:
    """Apply the per-mark write-back + bibliography rebuild as one UndoManager-grouped unit (P0 phase 2).

    On success: the whole group commits as one entry on the document's own Undo stack (a user's Ctrl+Z after a
    refresh reverts the *whole* refresh in one step, not citation-by-citation). On any exception partway
    through: the group is closed, `undo()` reverts it in a single call, and the result is checked against a
    pre-mutation snapshot — the roadmap's own "verify expected marks still exist" step. If the rollback didn't
    fully restore the prior state (an UndoManager failure, not just a mutation failure), that is surfaced as its
    own distinct error rather than silently re-raising the original one, since it means the document may now be
    in a state neither the caller nor the user expected.

    The bibliography rebuild is skipped when `bib_auto_enabled(doc)` is False (P0 phase 7) UNLESS `bib_cursor`
    is given — an explicit "put it here" request always writes, even while passive every-refresh rebuilding is
    paused; citations still update either way, the bibliography just stays frozen otherwise.
    """
    names = [name for name, _ in plan]
    before = _snapshot_marks(doc, names)
    undo = doc.getUndoManager()
    undo.enterUndoContext("Callosum refresh")
    try:
        for name, text_out in plan:
            mark = doc.getReferenceMarks().getByName(name)  # fresh handle each time (never a stale ref)
            _replace_mark_text(doc, mark, text_out)
        if bib_cursor is not None or bib_auto_enabled(doc):
            _write_bibliography(doc, bib_entries, cursor=bib_cursor)
    except Exception as exc:
        undo.leaveUndoContext()
        undo.undo()
        after = _snapshot_marks(doc, names)
        if after != before:
            raise RuntimeError(
                "callosum refresh failed partway through, and the automatic rollback did not fully restore the "
                "document. Please review it carefully (or close without saving and reopen)."
            ) from exc
        raise
    else:
        undo.leaveUndoContext()


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


def _write_bibliography(doc, entries: list[str], cursor=None) -> None:
    """(Re)build the BOUNDED managed bibliography block — a `BIB_BOOKMARK` (start) / `BIB_BOOKMARK_END` (end)
    bookmark PAIR delimits the exact managed range (P0 phase 7, backlog #33/#34). Clearing + rebuilding NEVER
    touches `text.getEnd()` — the verified data-loss fix for the old "bookmark to document end" design: any
    text a user placed after the bibliography now survives untouched.

    A `TextSection` was prototyped first (Phase 0) and found NOT to bound a rebuild safely (its own rebuild
    destroyed text outside the section) — a bookmark PAIR is the fallback this phase actually ships. Placing the
    END bookmark only AFTER the new content is written (never both bookmarks at the same collapsed position
    up front) sidesteps any "which side does a zero-width bookmark stick to" ambiguity — there's nothing to
    stick to yet when each bookmark is placed.

    `cursor`, if given, is where to (re)build the bibliography (P0 phase 7's "insert at cursor" / "move");
    otherwise the block rebuilds in place at its own existing bookmarks, or at the document end for a brand-new
    bibliography (unchanged first-run behavior).
    """
    text = doc.getText()
    bookmarks = doc.getBookmarks()
    has_start = bookmarks.hasByName(BIB_BOOKMARK)
    has_end = bookmarks.hasByName(BIB_BOOKMARK_END)
    if cursor is not None:
        if has_start:
            text.removeTextContent(bookmarks.getByName(BIB_BOOKMARK))
        if doc.getBookmarks().hasByName(BIB_BOOKMARK_END):
            text.removeTextContent(doc.getBookmarks().getByName(BIB_BOOKMARK_END))
    elif has_start and has_end:
        start = bookmarks.getByName(BIB_BOOKMARK).getAnchor().getStart()
        end = bookmarks.getByName(BIB_BOOKMARK_END).getAnchor().getEnd()
        cursor = text.createTextCursorByRange(start)
        cursor.gotoRange(end, True)  # select exactly [start, end] — bounded, never extends past the end bookmark
        cursor.setString("")  # deletes only the managed block + both bookmarks
    elif has_start:
        # A damaged/legacy document (a start bookmark survived without its end) — rebuild fresh at the start
        # bookmark's own position rather than guessing where "the end" might be. A user-facing repair/diagnostics
        # command (Phase 9) reports this state explicitly; this is just the safe fallback so it never crashes.
        start = bookmarks.getByName(BIB_BOOKMARK).getAnchor().getStart()
        text.removeTextContent(bookmarks.getByName(BIB_BOOKMARK))
        cursor = text.createTextCursorByRange(start)
    else:
        cursor = text.createTextCursorByRange(text.getEnd())
        if _has_text(text):
            text.insertControlCharacter(cursor, _PARAGRAH_BREAK(), False)

    start_mark = doc.createInstance("com.sun.star.text.Bookmark")
    start_mark.Name = BIB_BOOKMARK
    text.insertTextContent(cursor, start_mark, False)  # zero-width; cursor stays put
    if entries:
        text.insertString(cursor, BIB_HEADING + "\n", False)
        text.insertString(cursor, "\n".join(entries) + "\n", False)
    end_mark = doc.createInstance("com.sun.star.text.Bookmark")
    end_mark.Name = BIB_BOOKMARK_END
    text.insertTextContent(cursor, end_mark, False)  # placed AFTER the content — no bookmark-gravity ambiguity


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
    """Convert live fields → static text: remove every CALLOSUM ReferenceMark + the bibliography bookmark pair.

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
    for bookmark_name in (BIB_BOOKMARK, BIB_BOOKMARK_END):  # P0 phase 7: now a start/end PAIR, not just a start
        if bookmarks.hasByName(bookmark_name):
            text.removeTextContent(bookmarks.getByName(bookmark_name))  # zero-width bookmark only; bib text stays
    return len(names)


def delete_citation(doc, field: dict) -> None:
    """Delete a citation entirely — both the live field AND its rendered text (P0 phase 6, backlog #33/#34).
    Unlike `flatten` (which keeps the rendered text as static), nothing survives. Caller should `refresh()`
    afterward so the bibliography drops any now-unused entry.

    `cursor.setString("")` runs unconditionally after `removeTextContent` regardless of whether the mark's text
    already vanished with it — `flatten`'s own comment and this file's other rewrap helpers describe that as
    happening sometimes and not other times depending on the exact call shape, so clearing explicitly is the
    one path that is correct either way.
    """
    text = doc.getText()
    mark = field["_mark"]
    cursor = text.createTextCursorByRange(mark.getAnchor())
    text.removeTextContent(mark)
    cursor.setString("")


def _rewrap_mark_payload(doc, mark, payload: dict, rnd: str) -> None:
    """Replace `mark` with a fresh mark (new rnd + payload) wrapping a transient PLACEHOLDER at the same
    position — used when a citation's ITEM SET changes (merge/split), as opposed to `_replace_mark_text` (same
    payload, new rendered text). Caller must `refresh()` afterward to render real text into the placeholder."""
    text = doc.getText()
    cursor = text.createTextCursorByRange(mark.getAnchor())
    text.removeTextContent(mark)
    cursor.setString(PLACEHOLDER)
    fresh = doc.createInstance("com.sun.star.text.ReferenceMark")
    fresh.Name = encode_mark_name(payload, rnd)
    text.insertTextContent(cursor, fresh, True)


def merge_citations(doc, earlier: dict, later: dict) -> None:
    """Combine two citations into one grouped citation at `earlier`'s position (P0 phase 6) — e.g. two separate
    (Smith, 2020) (Jones, 2021) become one (Smith, 2020; Jones, 2021). `later` MUST be the field that comes
    AFTER `earlier` in document order — deleting it first leaves `earlier`'s own anchor range untouched. Caller
    should `refresh()` afterward.

    Known v1 limitation: any text/punctuation BETWEEN the two original citations (e.g. ", " or " and ") is left
    in place, not cleaned up — there's no composer yet (Phase 5) to know what the user wants done with it.
    """
    delete_citation(doc, later)
    combined_items = earlier["items"] + later["items"]
    fresh_mark = doc.getReferenceMarks().getByName(earlier["_mark"].Name)  # re-fetch: the collection mutated
    _rewrap_mark_payload(doc, fresh_mark, {"items": combined_items}, _new_rnd(doc))


def split_citation(doc, field: dict) -> None:
    """Split one grouped citation (multiple items) back into that many single-item citations, in the same item
    order, separated by "; " (P0 phase 6). Caller should `refresh()` afterward.

    Known v1 limitation: a fixed separator is used — there's no composer yet (Phase 5) to let the user choose.
    """
    text = doc.getText()
    mark = field["_mark"]
    cursor = text.createTextCursorByRange(mark.getAnchor())
    text.removeTextContent(mark)
    cursor.setString("")
    cursor.collapseToEnd()
    for i, item in enumerate(field["items"]):
        if i > 0:
            text.insertString(cursor, "; ", False)
            cursor.collapseToEnd()
        cursor.setString(PLACEHOLDER)
        fresh = doc.createInstance("com.sun.star.text.ReferenceMark")
        fresh.Name = encode_mark_name({"items": [item]}, _new_rnd(doc))
        text.insertTextContent(cursor, fresh, True)
        cursor.collapseToEnd()


def open_in_callosum(doc, base: str) -> None:
    """Open the cited work's paper in the callosum web app for the citation at the cursor (P0 phase 6) — a
    plain browser deep link, `{base}/?open_paper=<id>` (read by the frontend's own mount effect). Local-only:
    the base is the user's own configured callosum server.

    Known v1 limitation: for a grouped (multi-item) citation, only the FIRST item's paper opens — there's no
    composer yet (Phase 5) to let the user pick a specific one among several.
    """
    field = mark_at_cursor(doc)
    if field is None:
        _msgbox("Place your cursor inside a citation to open it in callosum.")
        return
    item_id = str((field["items"][0] or {}).get("id") or "")
    paper_id = item_id[len("callosum-") :] if item_id.startswith("callosum-") else ""
    if not paper_id.isdigit():
        _msgbox("Could not determine which paper this citation refers to.")
        return
    webbrowser.open(f"{base}/?open_paper={paper_id}")


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
    """Add a citation via the live-search composer (Phase 5a/5b, backlog #33/#34): search-as-you-type, assemble
    one or more sources (each optionally carrying a locator/prefix/suffix/suppress-author override) with a real
    rendered preview, then insert as one (possibly grouped) citation. Replaces the original one-shot
    search+single-select flow. Returns the mark rnd, or None if nothing was assembled/inserted."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import composer

    items = composer.run_composer_dialog(doc, base)
    if not items:
        return None
    return insert_citation_items(doc, items, base, cursor=_insertion_cursor(doc))


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


def _default_submission_copy_name(doc) -> str:
    url = doc.getURL()
    if url:
        path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
        base_name = os.path.splitext(os.path.basename(path))[0]
        if base_name:
            return f"{base_name}-submission-copy.odt"
    return "submission-copy.odt"


def _submission_copy_url(doc, filename: str) -> str:
    """A file:// URL for `filename` — next to the current document if it's already saved, else the user's
    home directory (P0 phase 8). Purely a local Save-As-style path choice; the filename is the user's own input
    on their own machine (the same trust boundary LibreOffice's native Save As already has), not untrusted
    external input, so no path-traversal handling applies here."""
    import uno

    doc_url = doc.getURL()
    if doc_url:
        directory_url = doc_url.rsplit("/", 1)[0]
        return f"{directory_url}/{urllib.parse.quote(filename)}"
    return uno.systemPathToFileUrl(os.path.join(os.path.expanduser("~"), filename))


def verify_flatten_integrity(before_text: str, after_text: str, doc) -> bool:
    """The post-flatten integrity check (P0 phase 8, backlog #33/#34): `flatten` only ever removes invisible
    mark/bookmark structure and re-inserts the SAME rendered text — the document's plain-text content must be
    byte-identical before and after, and zero CALLOSUM marks may remain."""
    if before_text != after_text:
        return False
    return not any(decode_mark_name(n) is not None for n in doc.getReferenceMarks().getElementNames())


def prepare_submission_copy(doc, filename: str) -> tuple[int, str]:
    """Flatten into a SEPARATE saved copy, never the live document (P0 phase 8) — the safe replacement for a
    bare, immediate `flatten()`. Sequence: group the flatten as one undo step, verify nothing but the invisible
    field/bookmark structure changed (`verify_flatten_integrity`), save the flattened result to `filename`, then
    undo the flatten in the live document so it is never actually left mutated — the copy on disk is the
    reversible artifact, the same role a merge_operations snapshot or a soft-delete husk plays elsewhere in this
    codebase, adapted to a document that isn't a database row.

    Known v1 limitation: always saves ODF (`writer8`) — LibreOffice's per-format filter names are numerous and
    format-specific enough that guessing the right one for every possible original document type without being
    able to verify each is worse than shipping one honestly-documented, verified format.

    Returns (flattened_count, save_url). Raises on integrity failure or a save error — the live document is
    always restored (via undo) before either is raised.
    """
    text = doc.getText()
    before_text = text.getString()
    undo = doc.getUndoManager()
    undo.enterUndoContext("Prepare submission copy")
    count = flatten(doc)
    undo.leaveUndoContext()
    after_text = text.getString()
    if not verify_flatten_integrity(before_text, after_text, doc):
        undo.undo()
        raise RuntimeError(
            "the flatten did not verify cleanly (visible text changed, or a live citation mark remained) — "
            "your document was not changed"
        )
    save_url = _submission_copy_url(doc, filename)
    try:
        from com.sun.star.beans import PropertyValue

        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeToURL(save_url, (filt,))
    except Exception:
        undo.undo()
        raise
    undo.undo()  # restore the live document — it was never actually left flattened
    return count, save_url


def prepare_submission_copy_interactive(doc) -> None:
    citation_count = len(scan_citations_in_order(doc))
    has_bib = doc.getBookmarks().hasByName(BIB_BOOKMARK) and doc.getBookmarks().hasByName(BIB_BOOKMARK_END)
    if citation_count == 0 and not has_bib:
        _msgbox("No live citations or bibliography to flatten in this document.")
        return
    prompt = (
        f"This document has {citation_count} live citation(s)"
        + (" and a bibliography" if has_bib else "")
        + ". This saves a SEPARATE copy with citations converted to static text — your open document is never "
        "changed. Save the copy as (in the same folder, or your home folder if unsaved):"
    )
    filename = _input_box(doc, "Prepare submission copy", prompt, _default_submission_copy_name(doc))
    if not filename or not filename.strip():
        return
    try:
        count, save_url = prepare_submission_copy(doc, filename.strip())
    except Exception as exc:
        _msgbox(f"Could not prepare the submission copy: {exc}\n\nYour open document was not changed.")
        return
    _msgbox(
        f"Saved a submission copy with {count} citation(s) flattened.\n\nYour open document is unchanged.\n{save_url}"
    )


def delete_citation_interactive(doc, base: str) -> None:
    field = mark_at_cursor(doc)
    if field is None:
        _msgbox("Place your cursor inside a citation to delete it.")
        return
    delete_citation(doc, field)
    refresh(doc, base)


def _merge_adjacent_interactive(doc, base: str, direction: str) -> None:
    current = mark_at_cursor(doc)
    if current is None:
        _msgbox("Place your cursor inside a citation to merge it.")
        return
    fields = scan_citations_in_order(doc)
    idx = next((i for i, f in enumerate(fields) if f["_mark"].Name == current["_mark"].Name), None)
    if idx is None:
        return
    other_idx = idx + 1 if direction == "next" else idx - 1
    if other_idx < 0 or other_idx >= len(fields):
        _msgbox(f"No {direction} citation to merge with.")
        return
    earlier, later = (fields[idx], fields[other_idx]) if direction == "next" else (fields[other_idx], fields[idx])
    merge_citations(doc, earlier, later)
    refresh(doc, base)


def merge_with_next_interactive(doc, base: str) -> None:
    _merge_adjacent_interactive(doc, base, "next")


def merge_with_previous_interactive(doc, base: str) -> None:
    _merge_adjacent_interactive(doc, base, "previous")


def split_citation_interactive(doc, base: str) -> None:
    field = mark_at_cursor(doc)
    if field is None:
        _msgbox("Place your cursor inside a citation to split it.")
        return
    if len(field["items"]) < 2:
        _msgbox("This citation has only one source — nothing to split.")
        return
    split_citation(doc, field)
    refresh(doc, base)


def insert_bibliography_here_interactive(doc, base: str) -> None:
    """Move (or, if none exists yet, create) the bibliography at the cursor (P0 phase 7)."""
    refresh(doc, base, bib_cursor=_insertion_cursor(doc))


def toggle_bib_auto_interactive(doc, base: str) -> None:
    """Flip whether the bibliography auto-rebuilds on refresh (P0 phase 7) — citations still update either way;
    this only pauses/resumes the bibliography block itself."""
    enabled = not bib_auto_enabled(doc)
    set_bib_auto(doc, enabled)
    _msgbox(
        f"Automatic bibliography rebuilding is now {'ON' if enabled else 'OFF'}."
        + (
            ""
            if enabled
            else " Citations still update on refresh; the bibliography stays as-is until you turn this back on."
        )
    )


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


def diagnose_document(doc, base: str = DEFAULT_BASE) -> dict:
    """Read-only health check across every recognized citation mark + the bibliography bookmarks (P0 phase 9,
    backlog #33/#34 — the last of the smaller phases). Every state it reports is one this adapter already knows
    how to describe or safely fix (a damaged bibliography self-heals on the next `refresh()`/"Insert bibliography
    here" — see `_write_bibliography`'s own damaged-document branch); this just surfaces it instead of the user
    discovering it by accident.

    Never mutates the document. Makes at most one `fetch_csl` HTTP call per distinct cited paper id (cached), to
    check whether its source paper is still in the library — reusing the same helper `insert_citation` already
    trusts to raise `ValueError` on a missing paper, rather than parsing `/papers/export`'s batched shape anew.
    Any OTHER exception (e.g. the server being unreachable) is deliberately NOT caught here — it propagates like
    every other action in this file, rather than being misreported as "these citations are orphaned."

    Returns ``{"malformed": [name, ...], "unsupported_version": [rnd, ...], "duplicate_ids": [rnd, ...],
    "orphaned": [paper_id, ...], "bibliography": "ok" | "damaged" | "not_built" | "n/a"}``.
    """
    malformed = []
    unsupported = []
    rnd_seen: dict[str, int] = {}
    ids_checked: dict[str, bool] = {}
    orphaned = []
    for name in doc.getReferenceMarks().getElementNames():
        if not (isinstance(name, str) and name.startswith(MARK_PREFIX + " ")):
            continue  # not one of ours — irrelevant to this diagnostic
        decoded = decode_mark_name(name)
        if decoded is None:
            malformed.append(name)
            continue
        if decoded.get("unsupported"):
            unsupported.append(decoded["rnd"])
            continue
        rnd_seen[decoded["rnd"]] = rnd_seen.get(decoded["rnd"], 0) + 1
        for item in decoded["items"]:
            item_id = str(item.get("id") or "")
            paper_id = item_id[len("callosum-") :] if item_id.startswith("callosum-") else ""
            if not paper_id.isdigit() or paper_id in ids_checked:
                continue
            try:
                fetch_csl(base, paper_id)
                ids_checked[paper_id] = True
            except ValueError:
                ids_checked[paper_id] = False
                orphaned.append(paper_id)
    duplicate_ids = [rnd for rnd, count in rnd_seen.items() if count > 1]

    bookmarks = doc.getBookmarks()
    has_start, has_end = bookmarks.hasByName(BIB_BOOKMARK), bookmarks.hasByName(BIB_BOOKMARK_END)
    if has_start and has_end:
        bib_state = "ok"
    elif has_start or has_end:
        bib_state = "damaged"
    elif rnd_seen:
        bib_state = "not_built"
    else:
        bib_state = "n/a"

    return {
        "malformed": malformed,
        "unsupported_version": unsupported,
        "duplicate_ids": duplicate_ids,
        "orphaned": orphaned,
        "bibliography": bib_state,
    }


def document_diagnostics_interactive(doc, base: str) -> None:
    report = diagnose_document(doc, base)
    lines = []
    if report["malformed"]:
        lines.append(
            f"{len(report['malformed'])} malformed citation field(s) — corrupted beyond repair; "
            "delete and re-insert them."
        )
    if report["unsupported_version"]:
        lines.append(
            f"{len(report['unsupported_version'])} citation(s) were written by a newer callosum than this "
            "plugin understands — left untouched; update the plugin to edit them."
        )
    if report["duplicate_ids"]:
        lines.append(
            f"{len(report['duplicate_ids'])} citation ID collision(s) — a refresh may render them "
            "identically; delete and re-insert one of each pair."
        )
    if report["orphaned"]:
        lines.append(
            f"{len(report['orphaned'])} citation(s) reference a paper no longer in your library — they still "
            "render from their saved snapshot, but won't reflect future edits and 'Open in callosum' won't "
            "find them."
        )
    if report["bibliography"] == "damaged":
        lines.append(
            "The bibliography block is damaged (a start or end marker is missing) — hit Refresh to safely rebuild it."
        )
    elif report["bibliography"] == "not_built":
        lines.append(
            "You have live citations but no bibliography yet — Refresh or 'Insert bibliography here' to build one."
        )
    _msgbox("\n\n".join(lines) if lines else "No issues found.", title="callosum — document diagnostics")


# Action registry — the single source of truth for what each Callosum command does. Keyed by the action name the
# .oxt Addons.xcu menu/toolbar dispatches (`service:com.callosum.cite.Dispatcher?<action>`). Each value takes
# (doc, base); flatten/setServerUrl ignore base. `add_citation_by_search` (search-to-cite) is added in SP2.
# deleteCitation/mergeWithNext/mergeWithPrevious/splitCitation/openInCallosum are P0 phase 6 (backlog #33/#34) —
# all resolve "which existing citation" via mark_at_cursor (phase 4).
_ACTIONS = {
    "addCitation": add_citation_by_search,
    "insert": insert_citation_interactive,
    "suggest": suggest_and_insert,
    "refresh": refresh,
    "setStyle": set_style_interactive,
    "flatten": lambda doc, base: flatten_interactive(doc),
    "prepareSubmissionCopy": lambda doc, base: prepare_submission_copy_interactive(doc),
    "insertStatement": insert_statement,
    "setServerUrl": lambda doc, base: set_server_url_interactive(doc),
    "deleteCitation": delete_citation_interactive,
    "mergeWithNext": merge_with_next_interactive,
    "mergeWithPrevious": merge_with_previous_interactive,
    "splitCitation": split_citation_interactive,
    "openInCallosum": open_in_callosum,
    "insertBibliographyHere": insert_bibliography_here_interactive,
    "toggleBibAuto": toggle_bib_auto_interactive,
    "diagnostics": document_diagnostics_interactive,
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


def CallosumDeleteCitation(*_args):
    _macro("deleteCitation")


def CallosumMergeWithNext(*_args):
    _macro("mergeWithNext")


def CallosumMergeWithPrevious(*_args):
    _macro("mergeWithPrevious")


def CallosumSplitCitation(*_args):
    _macro("splitCitation")


def CallosumOpenInCallosum(*_args):
    _macro("openInCallosum")


def CallosumInsertBibliographyHere(*_args):
    _macro("insertBibliographyHere")


def CallosumToggleBibAuto(*_args):
    _macro("toggleBibAuto")


def CallosumPrepareSubmissionCopy(*_args):
    _macro("prepareSubmissionCopy")


def CallosumDiagnostics(*_args):
    _macro("diagnostics")


g_exportedScripts = (
    CallosumAddCitation,
    CallosumInsertCitation,
    CallosumSuggestCitations,
    CallosumRefresh,
    CallosumSetStyle,
    CallosumFlatten,
    CallosumInsertStatement,
    CallosumSetServerUrl,
    CallosumDeleteCitation,
    CallosumMergeWithNext,
    CallosumMergeWithPrevious,
    CallosumSplitCitation,
    CallosumOpenInCallosum,
    CallosumInsertBibliographyHere,
    CallosumToggleBibAuto,
    CallosumPrepareSubmissionCopy,
    CallosumDiagnostics,
)
