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
import contextlib
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
PREF_CITE_AUTO = "CallosumCiteAuto"  # document user-property: "0" pauses automatic citation formatting (P1 #13)
PREF_CITE_DIRTY = "CallosumCiteDirty"  # "1" means visible citation text needs an explicit refresh (P1 #13)
PREF_BIB_DIRTY = "CallosumBibDirty"  # "1" means the managed bibliography needs an explicit refresh (P1 #13)
DIRTY_INFOBAR_ID = "callosum-refresh-pending"
DIRTY_REFRESH_URL = "service:com.callosum.cite.Dispatcher?refreshPending"
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
PREF_NOTE_PLACEMENT = "CallosumNotePlacement"  # document user-property: footnote or endnote for note-family styles
CONVERSION_STATE_PREFIX = "CALLOSUM_CONVERSION_STATE"
# P1 item #11 (backlog #33/#34): bibliography editing — each a JSON-encoded list of paper_id strings.
PREF_BIB_EXCLUDE = "CallosumBibExclude"  # cited works omitted from the bibliography (e.g. personal comms)
PREF_BIB_UNCITED = "CallosumBibUncited"  # uncited "further reading" works included in the bibliography
DEFAULT_STYLE = "apa"
DEFAULT_LOCALE = "en-US"
DEFAULT_NOTE_PLACEMENT = "footnote"
NOTE_PLACEMENTS = ("footnote", "endnote")
DEFAULT_BASE = "http://127.0.0.1:8080"
HTTP_TIMEOUT = 20
PROGRESS_MIN_WORK = 20  # roughly ten full-document citation updates; avoid flashing UI for small documents
PLACEHOLDER = "{citation}"  # transient visible text before the first render
BIB_HEADING = "References"
# Where the extension persists the (optional) server URL — outside LibreOffice's read-only extension package, in the
# OS user home (the same `~/.callosum/` callosum uses for app-settings). Lets the .oxt point at a non-default port
# without editing source. Pure file I/O (no UNO), so it's unit-testable with a temp path.
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".callosum", "libreoffice.json")

# Set by the .oxt dispatcher (callosum_addon.py) so the dialog helpers can find a component context when this code
# runs inside a UNO component (where the macro-only `XSCRIPTCONTEXT` global does NOT exist). None ⇒ macro mode.
_DISPATCH_CTX = None
_DOCUMENT_OBSERVERS: dict[str, object] = {}
_OBSERVATION_SUPPRESSIONS: dict[str, int] = {}
_CONVERSION_UNDO_LISTENERS: dict[str, object] = {}
_CONVERSION_BIBLIOGRAPHIES: dict[str, dict[tuple[str, ...], tuple[bool, bool, str]]] = {}


class RefreshCancelled(RuntimeError):
    """The user cooperatively cancelled a refresh before its transaction committed."""


class _RefreshProgress:
    """Small testable wrapper around Writer's status indicator and a temporary Toolkit Escape listener."""

    def __init__(self, total: int):
        self.total = max(1, total)
        self.indicator = None
        self.toolkit = None
        self.listener = None
        self.cancelled = False
        self.started = False

    def start(self) -> None:
        if self.indicator is None:
            return
        self.indicator.start(self._label("Callosum: preparing citation refresh"), self.total)
        self.started = True

    def _label(self, text: str) -> str:
        return f"{text} (Esc cancels)" if self.listener is not None else text

    def update(self, value: int, text: str) -> None:
        if self.cancelled:
            raise RefreshCancelled("Citation refresh cancelled; any partial formatting was rolled back.")
        if self.indicator is not None and self.started:
            self.indicator.setText(self._label(text))
            self.indicator.setValue(max(0, min(value, self.total)))
        if self.toolkit is not None:
            try:
                self.toolkit.reschedule()
            except Exception:
                pass
        if self.cancelled:
            raise RefreshCancelled("Citation refresh cancelled; any partial formatting was rolled back.")

    def close(self) -> None:
        if self.toolkit is not None and self.listener is not None:
            try:
                self.toolkit.removeKeyHandler(self.listener)
            except Exception:
                pass
        if self.indicator is not None and self.started:
            try:
                self.indicator.end()
            except Exception:
                pass
        self.listener = None
        self.started = False


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


def build_render_request(
    fields: list[dict],
    style: str,
    locale: str,
    *,
    uncited_items: list[dict] | None = None,
    bibliography_exclude_ids: list[str] | None = None,
) -> dict:
    """Turn ordered citation fields into the `/citations/render-document` body.

    Each field is ``{"citationID": <rnd>, "items": [<CSL-JSON>, …], "noteIndex": <0 or Writer note number>}``
    (in document order). Zero is the established in-text sentinel; note-style fields carry the one-based Writer
    footnote number citeproc needs for first/subsequent/ibid state. `uncited_items`/
    `bibliography_exclude_ids` (P1 item #11, backlog #33/#34) are both optional — omitted entirely, they're empty
    lists, matching the backend's own additive/optional contract.
    """
    return {
        "style": style,
        "locale": locale,
        "citations": [
            {
                "citationID": f["citationID"],
                "items": f["items"],
                "noteIndex": int(f.get("noteIndex", 0)),
            }
            for f in fields
        ],
        "uncited_items": uncited_items or [],
        "bibliography_exclude_ids": bibliography_exclude_ids or [],
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


def build_beyond_suggest_rows(items: list[dict]) -> list[str]:
    """One pick-list row per beyond-library suggestion (backlog #30): ``Author [et al.] Year — Title — why``.
    Shows the candidate's `relationship_label` (e.g. "Cited by a locally relevant paper: …") when the backend
    surfaced it via OpenAlex graph evidence, else its `reason` (a public-metadata-match sentence) — never a
    bare score. Visually prefixed so these are never confused with an already-in-library suggestion. Pure (no
    UNO); parallel to `items` (row index → item → the fields `save_beyond_library_item` needs)."""
    rows = []
    for it in items:
        authors = it.get("authors") or []
        who = authors[0] if authors else "—"
        if len(authors) > 1:
            who += " et al."
        year = it.get("year") or "n.d."
        title = (it.get("title") or "Untitled").strip()
        if len(title) > SEARCH_TITLE_MAX:
            title = title[:SEARCH_TITLE_MAX] + "…"
        why = " ".join(str(it.get("relationship_label") or it.get("reason") or "public metadata match").split())
        if len(why) > SUGGEST_QUOTE_MAX:
            why = why[:SUGGEST_QUOTE_MAX].rstrip() + "…"
        rows.append(f"[beyond library] {who} {year} — {title} — {why}")
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


def _put_json(url: str, body: dict, timeout: int = HTTP_TIMEOUT):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="PUT")
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
    return {style["id"] for style in list_styles(base)}


def style_catalog(base: str, query: str = "") -> dict:
    """Validated searchable catalog + application preferences from Callosum's local citation engine."""
    url = f"{base}/citations/styles"
    if query.strip():
        url += "?" + urllib.parse.urlencode({"q": query.strip()})
    data = _get_json(url)
    styles = data.get("styles", []) if isinstance(data, dict) else []
    validated = [
        {
            "id": style["id"],
            "family": style["family"],
            "title": str(style.get("title") or style["id"]),
            "citation_format": str(style.get("citation_format") or style["family"]),
            "fields": [str(field) for field in style.get("fields", []) if isinstance(field, str)],
            "favorite": bool(style.get("favorite", False)),
            "recent_rank": style.get("recent_rank") if isinstance(style.get("recent_rank"), int) else None,
            "application_default": bool(style.get("application_default", False)),
        }
        for style in styles
        if isinstance(style, dict) and isinstance(style.get("id"), str) and isinstance(style.get("family"), str)
    ]
    locales = data.get("locales", []) if isinstance(data, dict) else []
    locales = [locale for locale in locales if isinstance(locale, str) and locale]
    return {
        "styles": validated,
        "locales": locales or [DEFAULT_LOCALE],
        "default_style": str(data.get("default_style") or DEFAULT_STYLE) if isinstance(data, dict) else DEFAULT_STYLE,
        "default_locale": str(data.get("default_locale") or DEFAULT_LOCALE)
        if isinstance(data, dict)
        else DEFAULT_LOCALE,
    }


def list_styles(base: str, query: str = "") -> list[dict]:
    return style_catalog(base, query)["styles"]


def preview_style(base: str, style: str, locale: str) -> dict:
    return _post_json(f"{base}/citations/styles/preview", {"style": style, "locale": locale})


def record_style_use(base: str, style: str, locale: str) -> dict:
    return _put_json(
        f"{base}/citations/styles/preferences",
        {"style": style, "locale": locale, "mark_used": True},
    )


def style_family(base: str, style_id: str) -> str:
    """Return the selected style's declared family; fail closed on a missing/malformed manifest entry."""
    for style in list_styles(base):
        if style["id"] == style_id:
            return style["family"]
    raise ValueError(f"Unknown citation style '{style_id}'.")


SUGGEST_TIMEOUT = 90  # suggest does local ML work (embed + NLI); the first call loads the models — give it room


def fetch_suggestions(
    base: str, text: str, top_k: int = 5, include_beyond_library: bool = False, beyond_top_k: int = 5
) -> dict:
    """Citation suggestions for a draft sentence via the inc-156 endpoint, now wired to the already-shipped
    beyond-library path (backlog #30 SP2/Stage-3, `app/backend/citations/beyond_library.py`, inc 271/272) — this
    adapter previously never passed `include_beyond_library` at all. Returns ``{"suggestions": [...in-library],
    "beyond_library_suggestions": [...]}`` — the latter is always ``[]`` unless `include_beyond_library` is
    True, matching the SAME opt-in-each-time consent model the web Cite pane's "Also search beyond my library"
    checkbox already established (`.claude/security-audits/2026-07-11_beyond-library-citation-suggest.md`):
    this must never default to on, or silently persist as a standing setting.

    Local-only when `include_beyond_library` is False (the default): the engine ranks the library by relevance
    + evaluates each candidate's stance. When True, Callosum also sends the bounded draft sentence to public
    metadata providers (Crossref/PubMed/OpenAlex) — metadata-provider egress, not the Gemini/LLM gate, but real
    egress the user is explicitly opting into on this specific call.

    The first call loads the embedding + NLI models server-side, so it uses a longer timeout than render/export.
    Defensive on shape — a malformed/empty response yields empty lists for both.
    """
    data = _post_json(
        f"{base}/citations/suggest",
        {
            "text": text,
            "top_k": top_k,
            "evaluate": True,
            "include_beyond_library": include_beyond_library,
            "beyond_top_k": beyond_top_k,
        },
        timeout=SUGGEST_TIMEOUT,
    )
    if not isinstance(data, dict):
        return {"suggestions": [], "beyond_library_suggestions": []}
    suggestions = data.get("suggestions")
    beyond = data.get("beyond_library_suggestions")
    return {
        "suggestions": suggestions if isinstance(suggestions, list) else [],
        "beyond_library_suggestions": beyond if isinstance(beyond, list) else [],
    }


def save_beyond_library_item(base: str, item: dict) -> int:
    """Add a beyond-library suggestion to the library (backlog #30) via the existing `/discovery/save`
    endpoint — the SAME write path the web Cite pane's "Add to library" button already uses: a metadata-only
    record, no PDF fetch, deduped server-side (safe to call even if the item was already saved). Returns the
    paper_id, ready to hand straight to `insert_citation`."""
    payload = {
        "title": item.get("title") or "Untitled",
        "doi": item.get("doi"),
        "abstract": item.get("abstract"),
        "authors": item.get("authors") or [],
        "journal": item.get("journal"),
        "year": item.get("year"),
        "url": item.get("url"),
    }
    result = _post_json(f"{base}/discovery/save", payload)
    return int(result["paper_id"])


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


def csl_record_row(record: dict) -> str:
    """Same ``Author [et al.] Year — Title`` row shape as `build_search_rows`, but reads a full CSL-JSON record
    (``author: [{family, given}]``, ``issued: {"date-parts": [[year]]}``) rather than a `/papers?q=` search
    hit's flattened shape — used to display an EXISTING citation's already-decoded items when editing (Phase
    5c, backlog #33/#34), where only the CSL record is available, not a fresh search result."""
    authors = record.get("author") or []
    who = (authors[0].get("family") or "—") if authors else "—"
    if len(authors) > 1:
        who += " et al."
    issued = record.get("issued") or {}
    parts = issued.get("date-parts") or []
    year = parts[0][0] if parts and parts[0] else "n.d."
    title = (record.get("title") or "Untitled").strip()
    if len(title) > SEARCH_TITLE_MAX:
        title = title[:SEARCH_TITLE_MAX] + "…"
    return f"{who} {year} — {title}"


# ── UNO layer (lazy `import uno`; driven by the macro entry points + the headless self-test) ───────────────


def _get_pref(doc, base: str | None = None) -> tuple[str, str]:
    style = _effective_user_prop(doc, PREF_STYLE)
    locale = _effective_user_prop(doc, PREF_LOCALE)
    if base is not None and (not style or not locale):
        try:
            catalog = style_catalog(base)
            style = style or catalog["default_style"]
            locale = locale or catalog["default_locale"]
        except Exception:
            pass
    style = style or DEFAULT_STYLE
    locale = locale or DEFAULT_LOCALE
    return style, locale


def _user_prop(props, name: str) -> str | None:
    try:
        return str(props.getPropertyValue(name)) or None
    except Exception:
        return None


def _decode_conversion_state_name(name: str) -> dict[str, str | None] | None:
    prefix = CONVERSION_STATE_PREFIX + " "
    if not isinstance(name, str) or not name.startswith(prefix):
        return None
    try:
        payload = base64.urlsafe_b64decode(name[len(prefix) :].encode("ascii")).decode("utf-8")
        state = json.loads(payload)
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return None
    return state if isinstance(state, dict) else None


def _conversion_state_marks(doc) -> list:
    marks = doc.getReferenceMarks()
    return [
        marks.getByName(name)
        for name in marks.getElementNames()
        if isinstance(name, str) and name.startswith(CONVERSION_STATE_PREFIX + " ")
    ]


def _conversion_state(doc) -> dict[str, str | None] | None:
    marks = _conversion_state_marks(doc)
    return _decode_conversion_state_name(marks[0].Name) if len(marks) == 1 else None


def _conversion_state_name(values: dict[str, str | None]) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return CONVERSION_STATE_PREFIX + " " + base64.urlsafe_b64encode(payload).decode("ascii")


def _effective_user_prop(doc, name: str) -> str | None:
    state = _conversion_state(doc)
    if state is not None and name in state:
        value = state[name]
        return str(value) if value is not None else None
    props = doc.getDocumentProperties().getUserDefinedProperties()
    return _user_prop(props, name)


def _set_user_prop_value(doc, name: str, value: str | None) -> None:
    """Set/remove one document preference, preserving an active undoable conversion-state overlay."""
    state_marks = _conversion_state_marks(doc)
    state = _conversion_state(doc)
    if state is not None and len(state_marks) == 1 and name in _CONVERSION_PREFS:
        state[name] = value
        state_marks[0].Name = _conversion_state_name(state)
        return

    from com.sun.star.beans.PropertyAttribute import REMOVABLE

    props = doc.getDocumentProperties().getUserDefinedProperties()
    exists = props.getPropertySetInfo().hasPropertyByName(name)
    if value is None:
        if exists:
            props.removeProperty(name)
    elif exists:
        props.setPropertyValue(name, value)
    else:
        props.addProperty(name, REMOVABLE, value)


def _set_pref(doc, style: str, locale: str) -> None:
    for name, value in ((PREF_STYLE, style), (PREF_LOCALE, locale)):
        _set_user_prop_value(doc, name, value)


def note_placement(doc) -> str:
    """Document-level placement for newly inserted note-style citations; corrupt/legacy values fail to footnotes."""
    value = (_effective_user_prop(doc, PREF_NOTE_PLACEMENT) or DEFAULT_NOTE_PLACEMENT).strip().lower()
    return value if value in NOTE_PLACEMENTS else DEFAULT_NOTE_PLACEMENT


def normalize_note_placement(value: str) -> str:
    placement = str(value or "").strip().lower()
    if placement not in NOTE_PLACEMENTS:
        raise ValueError("Note placement must be 'footnote' or 'endnote'.")
    return placement


def set_note_placement(doc, placement: str) -> None:
    """Persist the placement for future note citations without silently relocating existing live fields."""
    placement = normalize_note_placement(placement)
    existing = {
        field.get("placement", "inline")
        for field in scan_citations_in_order(doc)
        if field.get("placement", "inline") != "inline"
    }
    if existing and existing != {placement}:
        raise ValueError(
            f"This document already contains live Callosum citations in {', '.join(sorted(existing))}. "
            "Use Convert citation placement to relocate them deliberately."
        )
    _set_user_prop_value(doc, PREF_NOTE_PLACEMENT, placement)


def bib_auto_enabled(doc) -> bool:
    """Whether the bibliography auto-rebuilds on refresh (P0 phase 7). Default True — only an explicit "0"
    (set via `set_bib_auto`) pauses it, so a fresh/never-touched document keeps today's behavior unchanged."""
    props = doc.getDocumentProperties().getUserDefinedProperties()
    return _user_prop(props, PREF_BIB_AUTO) != "0"


def set_bib_auto(doc, enabled: bool) -> None:
    _set_bool_prop(doc, PREF_BIB_AUTO, enabled)


def _set_bool_prop(doc, name: str, enabled: bool) -> None:
    _set_user_prop_value(doc, name, "1" if enabled else "0")


def cite_auto_enabled(doc) -> bool:
    """Whether citation mutations format themselves immediately. Default True for existing and new documents."""
    props = doc.getDocumentProperties().getUserDefinedProperties()
    return _user_prop(props, PREF_CITE_AUTO) != "0"


def set_cite_auto(doc, enabled: bool) -> None:
    _set_bool_prop(doc, PREF_CITE_AUTO, enabled)


def dirty_state(doc) -> tuple[bool, bool]:
    """Return `(citations_pending, bibliography_pending)` from the document-local refresh flags."""
    return _effective_user_prop(doc, PREF_CITE_DIRTY) == "1", _effective_user_prop(doc, PREF_BIB_DIRTY) == "1"


def _document_uid(doc) -> str:
    """Runtime-only document identity used for listener ownership; never persisted or exposed."""
    try:
        return str(doc.RuntimeUID)
    except Exception:
        return str(id(doc))


def _managed_bibliography_signature(doc) -> tuple[bool, bool, str]:
    bookmarks = doc.getBookmarks()
    has_start = bookmarks.hasByName(BIB_BOOKMARK)
    has_end = bookmarks.hasByName(BIB_BOOKMARK_END)
    if not (has_start and has_end):
        return has_start, has_end, ""
    text = doc.getText()
    cursor = text.createTextCursorByRange(bookmarks.getByName(BIB_BOOKMARK).getAnchor().getStart())
    cursor.gotoRange(bookmarks.getByName(BIB_BOOKMARK_END).getAnchor().getEnd(), True)
    return True, True, cursor.getString()


def document_structure_signature(doc) -> tuple[tuple[tuple[str, str], ...], tuple[bool, bool, str]]:
    """Snapshot only the Writer structure that can make rendered citations or bibliography stale."""
    citations = tuple(
        (field["_mark"].Name, field["_mark"].getAnchor().getString()) for field in scan_citations_in_order(doc)
    )
    return citations, _managed_bibliography_signature(doc)


def structure_change_flags(
    previous: tuple[tuple[tuple[str, str], ...], tuple[bool, bool, str]],
    current: tuple[tuple[tuple[str, str], ...], tuple[bool, bool, str]],
) -> tuple[bool, bool]:
    """Map a structured Writer change to `(citations_pending, bibliography_pending)`."""
    citations_changed = previous[0] != current[0]
    bibliography_changed = previous[1] != current[1]
    return citations_changed, citations_changed or bibliography_changed


@contextlib.contextmanager
def suspend_document_observation(doc):
    """Keep the listener's baseline current while a Callosum command performs its own precise state accounting."""
    uid = _document_uid(doc)
    _OBSERVATION_SUPPRESSIONS[uid] = _OBSERVATION_SUPPRESSIONS.get(uid, 0) + 1
    try:
        yield
    finally:
        remaining = _OBSERVATION_SUPPRESSIONS.get(uid, 1) - 1
        if remaining:
            _OBSERVATION_SUPPRESSIONS[uid] = remaining
        else:
            _OBSERVATION_SUPPRESSIONS.pop(uid, None)


def _new_document_observer(doc):
    import unohelper
    from com.sun.star.util import XModifyListener

    uid = _document_uid(doc)

    class DocumentObserver(unohelper.Base, XModifyListener):
        def __init__(self):
            self.signature = document_structure_signature(doc)
            self.busy = False

        def modified(self, _event):
            if self.busy:
                return
            try:
                current = document_structure_signature(doc)
                citations_pending, bibliography_pending = structure_change_flags(self.signature, current)
                self.signature = current
                if uid in _OBSERVATION_SUPPRESSIONS or not (citations_pending or bibliography_pending):
                    return
                self.busy = True
                set_dirty_state(
                    doc,
                    citations=True if citations_pending else None,
                    bibliography=True if bibliography_pending else None,
                )
            except Exception:
                pass
            finally:
                self.busy = False

        def disposing(self, _event):
            if _DOCUMENT_OBSERVERS.get(uid) is self:
                _DOCUMENT_OBSERVERS.pop(uid, None)
            _OBSERVATION_SUPPRESSIONS.pop(uid, None)

    return DocumentObserver()


def observe_document(doc) -> bool:
    """Restore persisted UI state and install one structured-change listener on a Writer document."""
    try:
        if not doc.supportsService("com.sun.star.text.TextDocument"):
            return False
        _sync_dirty_infobar(doc)
        uid = _document_uid(doc)
        if uid not in _DOCUMENT_OBSERVERS:
            listener = _new_document_observer(doc)
            doc.addModifyListener(listener)
            _DOCUMENT_OBSERVERS[uid] = listener
        return True
    except Exception:
        return False


def _new_refresh_progress(doc, total: int) -> _RefreshProgress:
    """Create native Writer progress for a large refresh; degrade to a no-op wrapper if any UI service is absent."""
    progress = _RefreshProgress(total)
    if total < PROGRESS_MIN_WORK:
        return progress
    try:
        progress.indicator = doc.getCurrentController().getFrame().createStatusIndicator()
    except Exception:
        return progress
    try:
        import unohelper
        from com.sun.star.awt import XKeyHandler
        from com.sun.star.awt.Key import ESCAPE

        ctx = _component_ctx()
        progress.toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)

        class EscapeListener(unohelper.Base, XKeyHandler):
            def keyPressed(self, event):
                if event.KeyCode == ESCAPE:
                    progress.cancelled = True
                    return True
                return False

            def keyReleased(self, _event):
                return False

            def disposing(self, _event):
                progress.toolkit = None
                progress.listener = None

        progress.listener = EscapeListener()
        progress.toolkit.addKeyHandler(progress.listener)
    except Exception:
        if progress.toolkit is not None and progress.listener is not None:
            try:
                progress.toolkit.removeKeyHandler(progress.listener)
            except Exception:
                pass
        progress.toolkit = None
        progress.listener = None
    try:
        progress.start()
    except Exception:
        progress.indicator = None
        progress.started = False
    return progress


def _dirty_infobar_copy(citations_pending: bool, bibliography_pending: bool) -> tuple[str, str]:
    if citations_pending and bibliography_pending:
        return "Callosum refresh pending", "Citation formatting and the bibliography are out of date."
    if citations_pending:
        return "Callosum refresh pending", "Citation formatting is out of date."
    return "Callosum refresh pending", "The bibliography is out of date."


def _infobar_refresh_button():
    from com.sun.star.beans import StringPair

    button = StringPair()
    button.First = "Refresh pending"
    button.Second = DIRTY_REFRESH_URL
    return button


def _sync_dirty_infobar(doc) -> bool:
    """Synchronize the non-dismissible Writer Infobar with the persisted dirty flags.

    Returns whether the indicator is visible. Infobar support is best-effort so an older/unusual controller can
    never turn a successful citation mutation into a failure; supported LibreOffice versions are verified by the
    real-UNO harness.
    """
    citations_pending, bibliography_pending = dirty_state(doc)
    try:
        controller = doc.getCurrentController()
        exists = controller.hasInfobar(DIRTY_INFOBAR_ID)
        if not citations_pending and not bibliography_pending:
            if exists:
                controller.removeInfobar(DIRTY_INFOBAR_ID)
            return False
        primary, secondary = _dirty_infobar_copy(citations_pending, bibliography_pending)
        if exists:
            controller.updateInfobar(DIRTY_INFOBAR_ID, primary, secondary, 2)
        else:
            controller.appendInfobar(
                DIRTY_INFOBAR_ID,
                primary,
                secondary,
                2,  # com.sun.star.frame.InfobarType.WARNING
                (_infobar_refresh_button(),),
                False,
            )
        return True
    except Exception:
        return False


def set_dirty_state(doc, *, citations: bool | None = None, bibliography: bool | None = None) -> None:
    """Persist either dirty flag without disturbing the other, then synchronize the visible Writer indicator."""
    if citations is not None:
        _set_bool_prop(doc, PREF_CITE_DIRTY, citations)
    if bibliography is not None:
        _set_bool_prop(doc, PREF_BIB_DIRTY, bibliography)
    _sync_dirty_infobar(doc)


def _get_id_list(doc, name: str) -> list[str]:
    """Read a JSON-encoded list of paper_id strings from a document user-property (P1 item #11, backlog
    #33/#34 — `PREF_BIB_EXCLUDE`/`PREF_BIB_UNCITED`). Defensive against a missing/corrupt property: both return
    an empty list rather than raising, since a bibliography-editing preference is never load-bearing enough to
    break a refresh over."""
    props = doc.getDocumentProperties().getUserDefinedProperties()
    raw = _user_prop(props, name)
    if not raw:
        return []
    try:
        ids = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(x) for x in ids] if isinstance(ids, list) else []


def _set_id_list(doc, name: str, ids: list[str]) -> None:
    from com.sun.star.beans.PropertyAttribute import REMOVABLE

    props = doc.getDocumentProperties().getUserDefinedProperties()
    value = json.dumps(list(ids))
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


def _collection_items(collection) -> list:
    """Materialize a UNO XIndexAccess collection without assuming Python iteration support."""
    return [collection.getByIndex(index) for index in range(collection.getCount())]


def _note_containers(doc) -> list[dict]:
    """Writer footnote/endnote text containers with their one-based index in the respective collection."""
    out = []
    for placement, getter in (("footnote", "getFootnotes"), ("endnote", "getEndnotes")):
        try:
            notes = _collection_items(getattr(doc, getter)())
        except Exception:
            notes = []
        out.extend(
            {
                "placement": placement,
                "noteIndex": index,
                "_note": note,
                "_reference_id": getattr(note, "ReferenceId", None),
            }
            for index, note in enumerate(notes, start=1)
        )
    return out


def _range_belongs_to_text(text, range_) -> bool:
    """Use XText.createTextCursorByRange as Writer's authoritative same-text-context check."""
    try:
        text.createTextCursorByRange(range_)
        return True
    except Exception:
        return False


def _citation_context(doc, mark, notes: list[dict]) -> dict:
    """Classify a citation mark as main-text, footnote, endnote, or an unsupported Writer text context."""
    anchor = mark.getAnchor()
    if not hasattr(anchor, "getText"):
        # Small duck-typed unit fakes predate note support; real UNO XTextRange anchors always expose getText().
        return {"placement": "inline", "noteIndex": 0, "_note": None}
    container = anchor.getText()
    reference_id = getattr(container, "ReferenceId", None)
    candidates = [note for note in notes if reference_id is not None and note["_reference_id"] == reference_id]
    for note in candidates or notes:
        if _range_belongs_to_text(note["_note"], anchor):
            return note
    if _range_belongs_to_text(doc.getText(), anchor):
        return {"placement": "inline", "noteIndex": 0, "_note": None}
    return {"placement": "unsupported", "noteIndex": 0, "_note": None}


def citation_placement_error(
    fields: list[dict],
    family: str,
    expected_note_placement: str = DEFAULT_NOTE_PLACEMENT,
) -> str | None:
    """Explain a style/Writer-context mismatch rather than silently rendering notes inline (or vice versa)."""
    placements = {field.get("placement", "inline") for field in fields}
    if not placements:
        return None
    if family == "note":
        expected_note_placement = normalize_note_placement(expected_note_placement)
        if placements == {expected_note_placement}:
            return None
        return (
            f"This note style is configured to use Writer {expected_note_placement}s, but the existing live "
            f"citations are in {', '.join(sorted(placements))}. Automatic conversion between inline citations, "
            "footnotes, and endnotes is not available yet."
        )
    if placements == {"inline"}:
        return None
    return (
        "This in-text style requires every live Callosum citation to be in the main document text. "
        "Automatic conversion of existing note citations is not available yet."
    )


def _insert_mark(doc, text, cursor, payload: dict, rnd: str) -> None:
    cursor.setString(PLACEHOLDER)  # transient visible text; the mark absorbs this range
    mark = doc.createInstance("com.sun.star.text.ReferenceMark")
    mark.Name = encode_mark_name(payload, rnd)
    text.insertTextContent(cursor, mark, True)  # absorb=True → the mark wraps the placeholder range


def _note_insertion_text(doc, cursor, placement: str):
    """Return the existing configured note at ``cursor``, or None when the cursor is in main text."""
    placement = normalize_note_placement(placement)
    for context in _note_containers(doc):
        note = context["_note"]
        if not _range_belongs_to_text(note, cursor):
            continue
        if context["placement"] != placement:
            raise ValueError(
                f"The cursor is in a Writer {context['placement']}, but this document is configured to use "
                f"{placement}s for note-style citations."
            )
        return note
    if _range_belongs_to_text(doc.getText(), cursor):
        return None
    raise ValueError("Place the cursor in the main document text or an existing configured note.")


def _insert_note_mark(doc, cursor, payload: dict, rnd: str, placement: str) -> None:
    """Insert into an existing configured note at the caret, or create a new note from a main-text caret."""
    placement = normalize_note_placement(placement)
    main_text = doc.getText()
    if cursor is None:
        try:
            cursor = doc.getCurrentController().getViewCursor().getStart()
        except Exception:
            cursor = main_text.getEnd()
    existing_note = _note_insertion_text(doc, cursor, placement)
    if existing_note is not None:
        note_cursor = existing_note.createTextCursorByRange(cursor)
        note_cursor.collapseToStart()
        _insert_mark(doc, existing_note, note_cursor, payload, rnd)
        return
    main_cursor = main_text.createTextCursorByRange(cursor)
    main_cursor.collapseToStart()
    note_service = "com.sun.star.text.Footnote" if placement == "footnote" else "com.sun.star.text.Endnote"
    note = doc.createInstance(note_service)
    main_text.insertTextContent(main_cursor, note, False)
    _insert_mark(doc, note, note.createTextCursor(), payload, rnd)


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
    records = _build_records(items, base)
    rnd = _new_rnd(doc)
    payload = {"items": records}
    style, locale = _get_pref(doc, base)
    if not _effective_user_prop(doc, PREF_STYLE) or not _effective_user_prop(doc, PREF_LOCALE):
        _set_pref(doc, style, locale)
    if style_family(base, style) == "note":
        _insert_note_mark(doc, cursor, payload, rnd, note_placement(doc))
    else:
        text = doc.getText()
        if cursor is None:
            cursor = _insertion_cursor(doc)
        _insert_mark(doc, text, cursor, payload, rnd)
    _auto_refresh(doc, base)
    return rnd


def _build_records(items: list[dict], base: str) -> list[dict]:
    """Shared by `insert_citation_items` and `edit_citation_items`: fetch + stamp each item's CSL record and
    merge in whatever per-occurrence overrides were given (defaulted via `_normalize_item`)."""
    records = []
    for it in items:
        paper_id = it["paper_id"]
        record = stamp_item_id(fetch_csl(base, paper_id), paper_id)
        overrides = {k: v for k, v in it.items() if k != "paper_id"}
        record.update(_normalize_item(overrides))
        records.append(record)
    return records


def insert_citation(doc, paper_id, base: str = DEFAULT_BASE, cursor=None) -> str:
    """Insert a live citation ReferenceMark for a SINGLE paper_id, no per-occurrence overrides — a thin wrapper
    over `insert_citation_items` (the common case; every existing caller keeps working unchanged)."""
    return insert_citation_items(doc, [{"paper_id": paper_id}], base, cursor)


def edit_citation_items(doc, field: dict, items: list[dict], base: str = DEFAULT_BASE) -> None:
    """Replace an EXISTING citation's items in place — same rnd/mark identity, new item set (Phase 5c, backlog
    #33/#34, the composer's Edit-Citation path). Unlike `insert_citation_items`, this never mints a new rnd:
    editing a citation must not change its identity. `field` is the `mark_at_cursor`/`scan_citations_in_order`
    shape (``{"citationID", "items", "_mark"}``). Caller should have already confirmed the user wants to save
    (the composer returning a non-None item list); this always writes and then follows the document's automatic
    refresh preferences."""
    records = _build_records(items, base)
    _rewrap_mark_payload(doc, field["_mark"], {"items": records}, field["citationID"])
    _auto_refresh(doc, base)


def _our_marks(doc) -> list:
    marks = doc.getReferenceMarks()
    return [marks.getByName(n) for n in marks.getElementNames() if decode_mark_name(n) is not None]


def scan_citations_in_order(doc) -> list[dict]:
    """Full-document scan → citation fields in document order.

    Each field includes its Writer placement and citeproc ``noteIndex`` in addition to the live mark. Main-text
    citations are ordered by their anchors as before. Note citations are ordered by Writer's own footnote
    collection, then by anchor within a shared note, so citeproc receives the real note sequence rather than the
    unordered global ReferenceMark collection.
    """
    notes = _note_containers(doc)
    fields = []
    for mark in _our_marks(doc):
        decoded = decode_mark_name(mark.Name)
        if decoded is None or decoded.get("unsupported"):
            continue  # ours but a schema version this adapter doesn't understand — leave untouched, never guess
        context = _citation_context(doc, mark, notes)
        fields.append(
            {
                "citationID": decoded["rnd"],
                "items": decoded["items"],
                "_mark": mark,
                **context,
            }
        )

    def _ordered_in_text(group: list[dict], text) -> list[dict]:
        def _compare(a, b) -> int:
            return text.compareRegionStarts(a["_mark"].getAnchor(), b["_mark"].getAnchor())

        return order_by_comparator(group, _compare)

    ordered = _ordered_in_text([field for field in fields if field["placement"] == "inline"], doc.getText())
    for placement in ("footnote", "endnote"):
        placed = [field for field in fields if field["placement"] == placement]
        for note_index in sorted({field["noteIndex"] for field in placed}):
            group = [field for field in placed if field["noteIndex"] == note_index]
            ordered.extend(_ordered_in_text(group, group[0]["_note"]))
    ordered.extend(
        sorted((field for field in fields if field["placement"] == "unsupported"), key=lambda f: f["_mark"].Name)
    )
    return ordered


def render_input_signature(fields: list[dict]) -> tuple[tuple[str, str, str, str, int], ...]:
    """Identity, order, Writer context, and visible value of the live fields that produced one render request."""
    return tuple(
        (
            field["_mark"].Name,
            field["citationID"],
            field["_mark"].getAnchor().getString(),
            field.get("placement", "inline"),
            int(field.get("noteIndex", 0)),
        )
        for field in fields
    )


def incremental_citation_plan(
    fields: list[dict],
    rendered: dict[str, str],
    citation_names: set[str] | None = None,
) -> list[tuple[str, str]]:
    """Plan writes only for targeted fields whose current visible text differs from citeproc's full render."""
    return [
        (field["_mark"].Name, rendered[field["citationID"]])
        for field in fields
        if rendered.get(field["citationID"])
        and (citation_names is None or field["_mark"].Name in citation_names)
        and field["_mark"].getAnchor().getString() != rendered[field["citationID"]]
    ]


def rendered_bibliography_text(entries: list[str]) -> str:
    """The exact plain-text contents `_write_bibliography` places between the managed bookmark pair."""
    body = "\n".join(entries)
    return f"{BIB_HEADING}\n{body}\n" if entries else ""


def bibliography_render_is_current(doc, entries: list[str]) -> bool:
    """Whether an intact managed bibliography already contains the requested rendered plain text."""
    has_start, has_end, current = _managed_bibliography_signature(doc)
    return has_start and has_end and current == rendered_bibliography_text(entries)


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
    try:
        cursor_range = doc.getCurrentController().getViewCursor().getStart()
    except Exception:
        return None
    for field in scan_citations_in_order(doc):
        anchor = field["_mark"].getAnchor()
        text = anchor.getText()
        if not _range_belongs_to_text(text, cursor_range):
            continue
        if (
            text.compareRegionStarts(anchor.getStart(), cursor_range) >= 0
            and text.compareRegionStarts(cursor_range, anchor.getEnd()) >= 0
        ):
            return field
    return None


def _main_document_position(doc, range_):
    """Map a caret inside a footnote/endnote back to that note's anchor in the main Writer text."""
    if not hasattr(range_, "getText"):
        return range_  # compact outline-unit-test ranges; real UNO XTextRange always exposes getText()
    if _range_belongs_to_text(doc.getText(), range_):
        return range_
    for note in _note_containers(doc):
        if _range_belongs_to_text(note["_note"], range_):
            return note["_note"].getAnchor()
    return None


def _current_outline_section_bounds(doc) -> tuple[object, object] | None:
    """Return the heading-defined section containing the Writer caret as ``(start, end)``.

    Writer's ``OutlineLevel`` is the semantic authority: 0 is body text and 1..10 are headings. A section starts
    at the nearest preceding heading and includes nested lower-ranked headings until the next heading at the same
    or higher rank. Text before the first heading is a preamble section; a heading-free document is one section.
    """
    text = doc.getText()
    try:
        cursor = _main_document_position(doc, doc.getCurrentController().getViewCursor().getStart())
        if cursor is None:
            return None
        enumeration = text.createEnumeration()
    except Exception:
        return None
    headings = []
    while enumeration.hasMoreElements():
        paragraph = enumeration.nextElement()
        try:
            start = paragraph.getStart()
        except Exception:
            continue
        try:
            level = int(paragraph.getPropertyValue("OutlineLevel"))
        except Exception:
            try:
                level = int(paragraph.OutlineLevel)
            except Exception:
                continue
        if level > 0:
            headings.append((start, level))

    current_index = None
    try:
        for index, (start, _level) in enumerate(headings):
            if text.compareRegionStarts(start, cursor) >= 0:
                current_index = index
            else:
                break
    except Exception:
        return None

    if current_index is None:
        return text.getStart(), headings[0][0] if headings else text.getEnd()

    start, level = headings[current_index]
    end = text.getEnd()
    for next_start, next_level in headings[current_index + 1 :]:
        if next_level <= level:
            end = next_start
            break
    return start, end


def current_section_citation_names(doc) -> set[str] | None:
    """Return recognized citation mark names inside the caret's heading-defined section."""
    bounds = _current_outline_section_bounds(doc)
    if bounds is None:
        return None
    start, end = bounds
    text = doc.getText()
    names = set()
    for field in scan_citations_in_order(doc):
        note = field.get("_note")
        anchor_start = note.getAnchor().getStart() if note is not None else field["_mark"].getAnchor().getStart()
        try:
            inside = (
                text.compareRegionStarts(start, anchor_start) >= 0 and text.compareRegionStarts(anchor_start, end) > 0
            )
        except Exception:
            continue
        if inside:
            names.add(field["_mark"].Name)
    return names


def refresh(
    doc,
    base: str = DEFAULT_BASE,
    bib_cursor=None,
    *,
    update_citations: bool = True,
    update_bibliography: bool | None = None,
    citation_names: set[str] | None = None,
) -> dict:
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

    P1 item #13 adds explicit partial refreshes without weakening citeproc's document-wide context:
    `update_citations=False` leaves every citation mark untouched, while `update_bibliography=False` leaves the
    managed bibliography block untouched. The full ordered citation set is still rendered before either write,
    so numeric ordering, disambiguation, and bibliography membership never depend on a partial citeproc input.
    When `update_bibliography` is None (the default), the existing document preference decides whether a passive
    refresh rebuilds it; an explicit True is the deliberate "Refresh bibliography only" command and therefore
    writes even while automatic rebuilding is paused.

    `citation_names`, when provided, narrows citation write-back to those ReferenceMark names while the render
    request still contains every citation. A targeted refresh deliberately does not clear the document-wide
    citation-dirty flag: without per-mark dirty state, updating one citation cannot prove the others are current.

    Large refreshes use Writer's native status indicator. A temporary Escape-key listener cooperatively cancels
    at the next checkpoint; if any write already occurred, `_transactional_apply` rolls the entire UndoManager
    group back. Because yielding to Writer can admit a document event, the exact ordered render input is checked
    again before mutation and a stale response is discarded.

    Incremental rendering still sends the complete ordered document to citeproc, then compares its output with
    the live managed surfaces. Only citation anchors whose visible text changed are recreated; an intact bounded
    bibliography is rebuilt only when its exact plain text changed (or an explicit cursor move was requested).
    An empty delta creates no UndoManager entry.
    """
    style, locale = _get_pref(doc, base)
    fields = scan_citations_in_order(doc)
    placement_error = citation_placement_error(fields, style_family(base, style), note_placement(doc))
    if placement_error:
        raise ValueError(placement_error)
    expected_signature = render_input_signature(fields)
    # P1 item #11 (backlog #33/#34): bibliography editing. Both lists are read-only inputs to this render; the
    # panel (citations_panel.py) is what actually persists them via _set_id_list.
    cited_ids = {_paper_id_from_item(it) for f in fields for it in f["items"]}
    exclude_ids = [f"callosum-{pid}" for pid in _get_id_list(doc, PREF_BIB_EXCLUDE)]
    write_bibliography = (
        update_bibliography if update_bibliography is not None else bib_cursor is not None or bib_auto_enabled(doc)
    )
    target_count = (
        sum(1 for field in fields if citation_names is None or field["_mark"].Name in citation_names)
        if update_citations
        else 0
    )
    progress = _new_refresh_progress(
        doc,
        max(1, len(fields) + target_count + int(write_bibliography)),
    )
    try:
        progress.update(0, "Callosum: preparing citation data")
        uncited_items: list[dict] = []
        for pid in _get_id_list(doc, PREF_BIB_UNCITED):
            if pid in cited_ids:
                continue  # already cited normally -- redundant as a bibliography-only "uncited" entry
            try:
                uncited_items.append(stamp_item_id(fetch_csl(base, pid), pid))
            except ValueError:
                continue  # a manually-included paper no longer in the library -- skip silently, not a hard failure
        if not fields and not uncited_items:
            apply_bibliography = write_bibliography and (
                bib_cursor is not None or not bibliography_render_is_current(doc, [])
            )
            _transactional_apply(
                doc,
                [],
                [],
                bib_cursor=bib_cursor,
                write_bibliography=apply_bibliography,
                progress=progress,
            )
            progress.update(progress.total, "Callosum: refresh complete")
            set_dirty_state(
                doc,
                citations=False if update_citations and citation_names is None else None,
                bibliography=False if write_bibliography else None,
            )
            return {"citations": [], "bibliography_text": ""}
        response = render_document(
            base,
            build_render_request(
                fields,
                style,
                locale,
                uncited_items=uncited_items,
                bibliography_exclude_ids=exclude_ids,
            ),
        )
        progress.update(len(fields), "Callosum: checking the live document")
        if render_input_signature(scan_citations_in_order(doc)) != expected_signature:
            raise RuntimeError(
                "Citation fields changed while Callosum was formatting them; no rendered changes were applied. "
                "Run Refresh again."
            )
        rendered = {c["citationID"]: c.get("text", "") for c in response.get("citations", [])}
        # Capture immutable names only for fields whose visible render changed. Recreating one mark invalidates
        # other held mark references, so `_transactional_apply` re-fetches each planned name fresh.
        plan = incremental_citation_plan(fields, rendered, citation_names) if update_citations else []
        bibliography_entries = response.get("bibliography_text", "").splitlines()
        apply_bibliography = write_bibliography and (
            bib_cursor is not None or not bibliography_render_is_current(doc, bibliography_entries)
        )
        _transactional_apply(
            doc,
            plan,
            bibliography_entries,
            bib_cursor=bib_cursor,
            write_bibliography=apply_bibliography,
            progress=progress,
            progress_offset=len(fields),
        )
        progress.update(progress.total, "Callosum: refresh complete")
        set_dirty_state(
            doc,
            citations=False if update_citations and citation_names is None else None,
            bibliography=False if write_bibliography else None,
        )
        return response
    finally:
        progress.close()


def refresh_citations(doc, base: str = DEFAULT_BASE) -> dict:
    """Re-render citation marks only; leave the managed bibliography byte-for-byte untouched."""
    return refresh(doc, base, update_bibliography=False)


def refresh_selected_citation(doc, base: str = DEFAULT_BASE) -> dict | None:
    """Re-render only the citation at the Writer cursor, using full-document citeproc context."""
    field = mark_at_cursor(doc)
    if field is None:
        _msgbox("Place your cursor inside a citation to refresh it.")
        return None
    return refresh(
        doc,
        base,
        update_bibliography=False,
        citation_names={field["_mark"].Name},
    )


def refresh_current_section(doc, base: str = DEFAULT_BASE) -> dict | None:
    """Re-render citations in the caret's heading-defined section, using full-document citeproc context."""
    names = current_section_citation_names(doc)
    if names is None:
        _msgbox("Place your cursor in the main document text to refresh its current section.")
        return None
    if not names:
        _msgbox("No live Callosum citations were found in the current section.")
        return None
    return refresh(
        doc,
        base,
        update_bibliography=False,
        citation_names=names,
    )


def refresh_bibliography(doc, base: str = DEFAULT_BASE) -> dict:
    """Rebuild the managed bibliography only; leave every citation mark untouched."""
    return refresh(doc, base, update_citations=False, update_bibliography=True)


def refresh_pending(doc, base: str = DEFAULT_BASE) -> dict | None:
    """Refresh exactly the surfaces named by the persisted dirty flags, regardless of automatic-mode settings."""
    citations_pending, bibliography_pending = dirty_state(doc)
    if not citations_pending and not bibliography_pending:
        _sync_dirty_infobar(doc)
        return None
    return refresh(
        doc,
        base,
        update_citations=citations_pending,
        update_bibliography=bibliography_pending,
    )


def _auto_refresh(doc, base: str = DEFAULT_BASE) -> dict | None:
    """Apply only the document surfaces whose automatic-update preferences are enabled.

    Explicit refresh commands call `refresh`/the partial wrappers directly and therefore always override this
    policy. If both surfaces are paused, citation mutations remain structured but perform no render request.
    """
    update_citations = cite_auto_enabled(doc)
    update_bibliography = bib_auto_enabled(doc)
    if not update_citations and not update_bibliography:
        set_dirty_state(doc, citations=True, bibliography=True)
        return None
    pending = {}
    if not update_citations:
        pending["citations"] = True
    if not update_bibliography:
        pending["bibliography"] = True
    if pending:
        set_dirty_state(doc, **pending)
    try:
        return refresh(
            doc,
            base,
            update_citations=update_citations,
            update_bibliography=update_bibliography,
        )
    except Exception:
        set_dirty_state(doc, citations=True, bibliography=True)
        raise


def _snapshot_marks(doc, names: list[str]) -> dict[str, str]:
    """Each named mark's CURRENT anchor text, keyed by name. Used only as the post-rollback verification oracle
    (never the rollback mechanism itself — that's the UndoManager): after an undo(), every name here must map
    back to the same text, proving the rollback actually restored the pre-mutation state rather than merely
    reverting *something*. A name no longer present after undo (e.g. a mark that was never touched because the
    failure hit before it) is simply absent from both snapshots and compares equal."""
    marks = doc.getReferenceMarks()
    return {name: marks.getByName(name).getAnchor().getString() for name in names if marks.hasByName(name)}


def _transactional_apply(
    doc,
    plan: list[tuple[str, str]],
    bib_entries: list[str],
    bib_cursor=None,
    *,
    write_bibliography: bool | None = None,
    progress: _RefreshProgress | None = None,
    progress_offset: int = 0,
) -> None:
    """Apply the per-mark write-back + bibliography rebuild as one UndoManager-grouped unit (P0 phase 2).

    On success: the whole group commits as one entry on the document's own Undo stack (a user's Ctrl+Z after a
    refresh reverts the *whole* refresh in one step, not citation-by-citation). On any exception partway
    through: the group is closed, `undo()` reverts it in a single call, and the result is checked against a
    pre-mutation snapshot — the roadmap's own "verify expected marks still exist" step. If the rollback didn't
    fully restore the prior state (an UndoManager failure, not just a mutation failure), that is surfaced as its
    own distinct error rather than silently re-raising the original one, since it means the document may now be
    in a state neither the caller nor the user expected.

    When `write_bibliography` is None, the bibliography rebuild is skipped if `bib_auto_enabled(doc)` is False
    (P0 phase 7) UNLESS `bib_cursor` is given — an explicit "put it here" request always writes, even while
    passive every-refresh rebuilding is paused. P1 item #13's partial-refresh commands pass an explicit boolean:
    False keeps the bibliography untouched; True deliberately rebuilds it even while auto-rebuild is paused.

    P1 item #13's progress object checks for cooperative cancellation before mutation and after each completed
    unit. Cancellation is an ordinary exception to this transaction, so the same verified rollback path handles
    it rather than maintaining a second recovery mechanism.
    """
    if write_bibliography is None:
        should_write_bibliography = bib_cursor is not None or bib_auto_enabled(doc)
    else:
        should_write_bibliography = write_bibliography
    if not plan and not should_write_bibliography:
        return
    names = [name for name, _ in plan]
    before = _snapshot_marks(doc, names)
    undo = doc.getUndoManager()
    if progress is not None:
        progress.update(progress_offset, "Callosum: applying citation formatting")
    undo.enterUndoContext("Callosum refresh")
    try:
        for index, (name, text_out) in enumerate(plan, 1):
            mark = doc.getReferenceMarks().getByName(name)  # fresh handle each time (never a stale ref)
            _replace_mark_text(doc, mark, text_out)
            if progress is not None:
                progress.update(
                    progress_offset + index,
                    f"Callosum: updated citation {index} of {len(plan)}",
                )
        if should_write_bibliography:
            if progress is not None:
                progress.update(progress_offset + len(plan), "Callosum: updating the bibliography")
            _write_bibliography(doc, bib_entries, cursor=bib_cursor)
            if progress is not None:
                progress.update(progress_offset + len(plan) + 1, "Callosum: refresh complete")
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
    text = mark.getAnchor().getText()
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
        cursor.setString("")  # clears the managed block's TEXT
        # Explicitly remove the bookmark TextContent objects too (P1 item #11, backlog #33/#34 — found via the
        # bibliography-editing spike): a bare setString("") on the enclosing range was observed to sometimes
        # leave the now-zero-width bookmark objects themselves still registered, so the fresh start_mark/
        # end_mark created below collided on name and LibreOffice silently auto-renamed the duplicate
        # ("... Copy 1") instead of erroring — producing an orphaned second bibliography block on the very next
        # refresh. Re-query fresh (not the `bookmarks` snapshot from the top of this function) and remove any
        # survivor before creating the new pair.
        fresh_bookmarks = doc.getBookmarks()
        if fresh_bookmarks.hasByName(BIB_BOOKMARK):
            text.removeTextContent(fresh_bookmarks.getByName(BIB_BOOKMARK))
        if fresh_bookmarks.hasByName(BIB_BOOKMARK_END):
            text.removeTextContent(fresh_bookmarks.getByName(BIB_BOOKMARK_END))
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


def _write_bibliography_for_conversion(doc, entries: list[str]) -> None:
    """Use the proven bounded rebuild; the conversion Undo listener restores its exact before/after snapshot."""
    _write_bibliography(doc, entries)


def _restore_managed_bibliography(doc, signature: tuple[bool, bool, str]) -> None:
    """Re-wrap Writer-restored bibliography text without changing a character."""
    text = doc.getText()
    bookmarks = doc.getBookmarks()
    reserved = [
        name
        for name in bookmarks.getElementNames()
        if name == BIB_BOOKMARK
        or name.startswith(BIB_BOOKMARK + " Copy ")
        or name == BIB_BOOKMARK_END
        or name.startswith(BIB_BOOKMARK_END + " Copy ")
    ]
    fallback = (
        text.createTextCursorByRange(bookmarks.getByName(reserved[0]).getAnchor().getStart())
        if reserved
        else text.createTextCursorByRange(text.getEnd())
    )
    for name in reserved:
        current = doc.getBookmarks()
        if current.hasByName(name):
            text.removeTextContent(current.getByName(name))
    want_start, want_end, contents = signature
    if not (want_start and want_end):
        return

    if contents:
        descriptor = doc.createSearchDescriptor()
        descriptor.SearchString = contents
        found = doc.findFirst(descriptor)
        if found is None or doc.findNext(found.getEnd(), descriptor) is not None:
            raise RuntimeError("Writer restored bibliography text ambiguously; its managed bookmarks were not changed.")
        start_cursor = text.createTextCursorByRange(found.getStart())
        end_cursor = text.createTextCursorByRange(found.getEnd())
    else:
        start_cursor = fallback
        end_cursor = fallback
    start_mark = doc.createInstance("com.sun.star.text.Bookmark")
    start_mark.Name = BIB_BOOKMARK
    text.insertTextContent(start_cursor, start_mark, False)
    end_mark = doc.createInstance("com.sun.star.text.Bookmark")
    end_mark.Name = BIB_BOOKMARK_END
    text.insertTextContent(end_cursor, end_mark, False)


def _conversion_state_key(doc) -> tuple[str, ...]:
    return tuple(mark.Name for mark in _conversion_state_marks(doc))


def _ensure_conversion_undo_listener(doc):
    uid = _document_uid(doc)
    if uid in _CONVERSION_UNDO_LISTENERS:
        return _CONVERSION_UNDO_LISTENERS[uid]

    import unohelper
    from com.sun.star.document import XUndoManagerListener

    undo = doc.getUndoManager()

    class ConversionUndoListener(unohelper.Base, XUndoManagerListener):
        def _restore(self, event):
            if getattr(event, "UndoActionTitle", "") != "Convert Callosum citation placement":
                return
            signature = _CONVERSION_BIBLIOGRAPHIES.get(uid, {}).get(_conversion_state_key(doc))
            if signature is None:
                return
            undo.lock()
            try:
                with suspend_document_observation(doc):
                    _restore_managed_bibliography(doc, signature)
            finally:
                undo.unlock()

        def actionUndone(self, event):
            self._restore(event)

        def actionRedone(self, event):
            self._restore(event)

        def undoActionAdded(self, _event):
            pass

        def allActionsCleared(self, _event):
            _CONVERSION_BIBLIOGRAPHIES.pop(uid, None)

        def redoActionsCleared(self, _event):
            pass

        def enteredContext(self, _event):
            pass

        def enteredHiddenContext(self, _event):
            pass

        def leftContext(self, _event):
            pass

        def leftHiddenContext(self, _event):
            pass

        def cancelledContext(self, _event):
            pass

        def resetAll(self, _event):
            _CONVERSION_BIBLIOGRAPHIES.pop(uid, None)

        def disposing(self, _event):
            _CONVERSION_UNDO_LISTENERS.pop(uid, None)
            _CONVERSION_BIBLIOGRAPHIES.pop(uid, None)

    listener = ConversionUndoListener()
    undo.addUndoManagerListener(listener)
    _CONVERSION_UNDO_LISTENERS[uid] = listener
    return listener


def _register_conversion_bibliographies(
    doc,
    before_key: tuple[str, ...],
    before: tuple[bool, bool, str],
    after_key: tuple[str, ...] | None = None,
    after: tuple[bool, bool, str] | None = None,
) -> None:
    _ensure_conversion_undo_listener(doc)
    states = _CONVERSION_BIBLIOGRAPHIES.setdefault(_document_uid(doc), {})
    states[before_key] = before
    if after_key is not None and after is not None:
        states[after_key] = after


def _has_text(text) -> bool:
    return bool(text.getString().strip())


def _PARAGRAH_BREAK():
    from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK

    return PARAGRAPH_BREAK


def set_style(doc, style: str, locale: str, base: str = DEFAULT_BASE) -> None:
    """Validate and persist the style, then follow the document's automatic refresh preferences."""
    styles = list_styles(base)
    families = {entry["id"]: entry["family"] for entry in styles}
    if style not in families:
        raise ValueError(f"Unknown style '{style}'. Available: {', '.join(sorted(families))}")
    placement_error = citation_placement_error(scan_citations_in_order(doc), families[style], note_placement(doc))
    if placement_error:
        raise ValueError(placement_error)
    _set_pref(doc, style, locale or DEFAULT_LOCALE)
    _auto_refresh(doc, base)
    with contextlib.suppress(Exception):
        record_style_use(base, style, locale or DEFAULT_LOCALE)


_CONVERSION_PREFS = (PREF_STYLE, PREF_LOCALE, PREF_NOTE_PLACEMENT, PREF_CITE_DIRTY, PREF_BIB_DIRTY)


def conversion_target_placement(family: str, requested_note_placement: str = DEFAULT_NOTE_PLACEMENT) -> str:
    """Map a CSL family + bounded note choice to the Writer context the converted fields must occupy."""
    return normalize_note_placement(requested_note_placement) if family == "note" else "inline"


def _document_has_redlines(doc) -> bool:
    try:
        return doc.getRedlines().getCount() > 0
    except Exception:
        return False


def placement_conversion_error(doc, fields: list[dict], target_placement: str) -> str | None:
    """Fail closed on document structures the first conversion slice cannot relocate without guessing."""
    if not fields:
        return "No live Callosum citations were found in this document."
    target_placement = normalize_note_placement(target_placement) if target_placement != "inline" else target_placement
    placements = {field.get("placement", "unsupported") for field in fields}
    if len(placements) != 1 or not placements <= {"inline", *NOTE_PLACEMENTS}:
        return "Citation placement is mixed or unsupported; conversion requires one consistent source placement."
    source_placement = next(iter(placements))
    if source_placement == target_placement:
        return f"All live citations are already in {target_placement} placement."
    state_marks = _conversion_state_marks(doc)
    if len(state_marks) > 1 or (state_marks and _decode_conversion_state_name(state_marks[0].Name) is None):
        return "Repair malformed Callosum conversion state before converting citation placement."
    if _document_has_redlines(doc):
        return "Accept or reject tracked changes before converting citation placement."

    names = doc.getReferenceMarks().getElementNames()
    for name in names:
        if isinstance(name, str) and name.startswith(MARK_PREFIX + " "):
            decoded = decode_mark_name(name)
            if decoded is None or decoded.get("unsupported"):
                return "Repair malformed or newer-schema Callosum citation fields before converting placement."
    citation_ids = [field["citationID"] for field in fields]
    if len(set(citation_ids)) != len(citation_ids):
        return "Repair duplicate Callosum citation IDs before converting placement."

    has_start, has_end, _text = _managed_bibliography_signature(doc)
    if has_start != has_end:
        return "Repair the damaged managed bibliography before converting citation placement."

    if source_placement in NOTE_PLACEMENTS:
        note_keys = [(field["placement"], field["noteIndex"]) for field in fields]
        if len(set(note_keys)) != len(note_keys):
            return "Conversion requires exactly one live citation cluster in each source note."
        all_marks = [doc.getReferenceMarks().getByName(name) for name in names]
        for field in fields:
            note = field.get("_note")
            mark = field["_mark"]
            if note is None or note.getString() != mark.getAnchor().getString():
                return "Conversion cannot move a note that also contains user prose."
            if any(other.Name != mark.Name and _range_belongs_to_text(note, other.getAnchor()) for other in all_marks):
                return "Conversion requires each source note to contain only one Callosum citation field."
    return None


def _conversion_user_props(doc) -> dict[str, str | None]:
    return {name: _effective_user_prop(doc, name) for name in _CONVERSION_PREFS}


def _replace_conversion_state(doc, values: dict[str, str | None]) -> None:
    """Replace the zero-width state mark; Writer natively includes the change in its current Undo context."""
    text = doc.getText()
    for mark in _conversion_state_marks(doc):
        mark.getAnchor().getText().removeTextContent(mark)
    marker = doc.createInstance("com.sun.star.text.ReferenceMark")
    marker.Name = _conversion_state_name(values)
    cursor = text.createTextCursorByRange(text.getStart())
    cursor.collapseToStart()
    text.insertTextContent(cursor, marker, False)


def _conversion_snapshot(doc) -> tuple:
    fields = scan_citations_in_order(doc)
    return (
        doc.getText().getString(),
        tuple(
            (
                field["_mark"].Name,
                field["citationID"],
                field["placement"],
                field["noteIndex"],
                field["_mark"].getAnchor().getString(),
            )
            for field in fields
        ),
        tuple(note.getString() for note in _collection_items(doc.getFootnotes())),
        tuple(note.getString() for note in _collection_items(doc.getEndnotes())),
        _managed_bibliography_signature(doc),
        tuple(_conversion_user_props(doc).items()),
        tuple(mark.Name for mark in _conversion_state_marks(doc)),
    )


def _conversion_snapshot_differences(before: tuple, after: tuple) -> str:
    labels = ("main text", "citation fields", "footnotes", "endnotes", "bibliography", "preferences", "state mark")
    return ", ".join(label for label, old, new in zip(labels, before, after, strict=True) if old != new)


def _insert_named_rendered_mark(doc, text, cursor, name: str, rendered: str) -> None:
    cursor.setString(rendered)
    mark = doc.createInstance("com.sun.star.text.ReferenceMark")
    mark.Name = name
    text.insertTextContent(cursor, mark, True)


def _relocate_mark(doc, name: str, rendered: str, target_placement: str) -> None:
    """Move one isolated live field to main text/a native note while preserving its encoded identity."""
    mark = doc.getReferenceMarks().getByName(name)
    context = _citation_context(doc, mark, _note_containers(doc))
    source_placement = context["placement"]
    main_text = doc.getText()
    if source_placement == "inline":
        source_text = mark.getAnchor().getText()
        source_cursor = source_text.createTextCursorByRange(mark.getAnchor())
        source_text.removeTextContent(mark)
        source_cursor.setString("")
        main_cursor = main_text.createTextCursorByRange(source_cursor)
    elif source_placement in NOTE_PLACEMENTS:
        note = context["_note"]
        main_cursor = main_text.createTextCursorByRange(note.getAnchor())
        main_cursor.collapseToStart()
        main_text.removeTextContent(note)
    else:
        raise ValueError("The citation moved into an unsupported Writer text context during conversion.")
    main_cursor.collapseToStart()

    if target_placement == "inline":
        _insert_named_rendered_mark(doc, main_text, main_cursor, name, rendered)
        return
    target_placement = normalize_note_placement(target_placement)
    service = "com.sun.star.text.Footnote" if target_placement == "footnote" else "com.sun.star.text.Endnote"
    note = doc.createInstance(service)
    main_text.insertTextContent(main_cursor, note, False)
    _insert_named_rendered_mark(doc, note, note.createTextCursor(), name, rendered)


def _conversion_render_response(
    doc,
    fields: list[dict],
    target_style: str,
    locale: str,
    target_placement: str,
    base: str,
) -> dict:
    projected = [
        {
            "citationID": field["citationID"],
            "items": field["items"],
            "noteIndex": index if target_placement in NOTE_PLACEMENTS else 0,
        }
        for index, field in enumerate(fields, start=1)
    ]
    cited_ids = {_paper_id_from_item(item) for field in fields for item in field["items"]}
    uncited_items = []
    for paper_id in _get_id_list(doc, PREF_BIB_UNCITED):
        if paper_id in cited_ids:
            continue
        try:
            uncited_items.append(stamp_item_id(fetch_csl(base, paper_id), paper_id))
        except ValueError:
            continue
    exclude_ids = [f"callosum-{paper_id}" for paper_id in _get_id_list(doc, PREF_BIB_EXCLUDE)]
    return render_document(
        base,
        build_render_request(
            projected,
            target_style,
            locale,
            uncited_items=uncited_items,
            bibliography_exclude_ids=exclude_ids,
        ),
    )


def convert_citation_placement(
    doc,
    target_style: str,
    locale: str,
    target_note_placement: str = DEFAULT_NOTE_PLACEMENT,
    base: str = DEFAULT_BASE,
) -> dict:
    """Explicit, transactional placement/style conversion for the narrow unambiguous Writer subset."""
    styles = list_styles(base)
    families = {entry["id"]: entry["family"] for entry in styles}
    if target_style not in families:
        raise ValueError(f"Unknown style '{target_style}'. Available: {', '.join(sorted(families))}")
    target_placement = conversion_target_placement(families[target_style], target_note_placement)
    fields = scan_citations_in_order(doc)
    current_style, _current_locale = _get_pref(doc, base)
    current_family = next((entry["family"] for entry in styles if entry["id"] == current_style), None)
    if current_family is None:
        raise ValueError(f"Current citation style '{current_style}' is not available.")
    current_error = citation_placement_error(fields, current_family, note_placement(doc))
    if current_error:
        raise ValueError(f"Repair the current citation placement before converting. {current_error}")
    eligibility_error = placement_conversion_error(doc, fields, target_placement)
    if eligibility_error:
        raise ValueError(eligibility_error)

    response = _conversion_render_response(doc, fields, target_style, locale, target_placement, base)
    rendered = {citation["citationID"]: citation.get("text", "") for citation in response.get("citations", [])}
    if any(not rendered.get(field["citationID"]) for field in fields):
        raise RuntimeError("The target style did not render every citation; the document was not changed.")
    bibliography_entries = response.get("bibliography_text", "").splitlines()
    write_bibliography = bib_auto_enabled(doc)
    before_snapshot = _conversion_snapshot(doc)
    before_state_key = _conversion_state_key(doc)
    before_bibliography = before_snapshot[4]
    expected_names = [field["_mark"].Name for field in fields]
    relocation_plan = [(field["_mark"].Name, field["citationID"]) for field in fields]
    before_props = _conversion_user_props(doc)
    after_props = dict(before_props)
    after_props.update(
        {
            PREF_STYLE: target_style,
            PREF_LOCALE: locale or DEFAULT_LOCALE,
            PREF_CITE_DIRTY: "0",
            PREF_BIB_DIRTY: "0" if write_bibliography else "1",
        }
    )
    if target_placement in NOTE_PLACEMENTS:
        after_props[PREF_NOTE_PLACEMENT] = target_placement

    undo = doc.getUndoManager()
    undo.enterUndoContext("Convert Callosum citation placement")
    try:
        _replace_conversion_state(doc, after_props)
        for name, citation_id in reversed(relocation_plan):
            _relocate_mark(doc, name, rendered[citation_id], target_placement)
        if write_bibliography:
            _write_bibliography_for_conversion(doc, bibliography_entries)

        converted = scan_citations_in_order(doc)
        expected_indexes = list(range(1, len(fields) + 1)) if target_placement in NOTE_PLACEMENTS else [0] * len(fields)
        if (
            [field["_mark"].Name for field in converted] != expected_names
            or [field["placement"] for field in converted] != [target_placement] * len(fields)
            or [field["noteIndex"] for field in converted] != expected_indexes
            or any(field["_mark"].getAnchor().getString() != rendered[field["citationID"]] for field in converted)
            or _conversion_user_props(doc) != after_props
            or (write_bibliography and not bibliography_render_is_current(doc, bibliography_entries))
        ):
            raise RuntimeError("Post-conversion identity or structure verification failed.")
    except Exception as exc:
        undo.leaveUndoContext()
        _register_conversion_bibliographies(doc, before_state_key, before_bibliography)
        try:
            undo.undo()
        except Exception as rollback_exc:
            raise RuntimeError(
                "Citation conversion failed and Writer could not undo the conversion. "
                "Close without saving and reopen the document."
            ) from rollback_exc
        rollback_snapshot = _conversion_snapshot(doc)
        if rollback_snapshot != before_snapshot:
            differences = _conversion_snapshot_differences(before_snapshot, rollback_snapshot)
            raise RuntimeError(
                "Citation conversion failed and automatic rollback did not fully restore the document. "
                f"Close without saving and reopen it. Unrestored: {differences}."
            ) from exc
        raise
    else:
        undo.leaveUndoContext()
        _register_conversion_bibliographies(
            doc,
            before_state_key,
            before_bibliography,
            _conversion_state_key(doc),
            _managed_bibliography_signature(doc),
        )
        _sync_dirty_infobar(doc)
    return {
        "count": len(fields),
        "source_placement": fields[0]["placement"],
        "target_placement": target_placement,
        "style": target_style,
    }


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
        mark_text = mark.getAnchor().getText()
        cursor = mark_text.createTextCursorByRange(mark.getAnchor())
        rendered = cursor.getString()
        mark_text.removeTextContent(mark)
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
    mark = field["_mark"]
    text = mark.getAnchor().getText()
    cursor = text.createTextCursorByRange(mark.getAnchor())
    text.removeTextContent(mark)
    cursor.setString("")
    note = field.get("_note")
    if note is not None and not str(note.getString() or "").strip():
        note.getAnchor().getText().removeTextContent(note)


def _rewrap_mark_payload(doc, mark, payload: dict, rnd: str) -> None:
    """Replace `mark` with a fresh mark (new rnd + payload) wrapping a transient PLACEHOLDER at the same
    position — used when a citation's ITEM SET changes (merge/split), as opposed to `_replace_mark_text` (same
    payload, new rendered text). Caller must `refresh()` afterward to render real text into the placeholder."""
    text = mark.getAnchor().getText()
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
    mark = field["_mark"]
    text = mark.getAnchor().getText()
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


def _choice_box(
    doc,
    title: str,
    prompt: str,
    options: tuple[tuple[str, str], ...],
    current_value: str,
) -> str | None:
    """Small modal dropdown for a bounded setting; returns its stable value or None when cancelled."""
    smgr = _component_ctx().ServiceManager
    ctx = _component_ctx()
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 220, 72, title
    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height, label.Label = 6, 6, 208, 18, prompt
    dm.insertByName("lbl", label)
    choices = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    choices.PositionX, choices.PositionY, choices.Width, choices.Height = 6, 26, 208, 28
    choices.Dropdown = True
    choices.StringItemList = tuple(option[0] for option in options)
    dm.insertByName("choices", choices)
    ok = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.PositionX, ok.PositionY, ok.Width, ok.Height, ok.Label, ok.PushButtonType = 130, 52, 40, 14, "OK", 1
    dm.insertByName("ok", ok)
    cancel = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.PositionX, cancel.PositionY, cancel.Width, cancel.Height, cancel.Label, cancel.PushButtonType = (
        174,
        52,
        40,
        14,
        "Cancel",
        2,
    )
    dm.insertByName("cancel", cancel)
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    control = dialog.getControl("choices")
    selected = next((index for index, option in enumerate(options) if option[1] == current_value), 0)
    control.selectItemPos(selected, True)
    result = dialog.execute()
    position = control.getSelectedItemPos() if result == 1 else -1
    dialog.dispose()
    return options[position][1] if 0 <= position < len(options) else None


_SUGGEST_CAVEAT = "Pick a paper to cite for the selected text — ranked by relevance; verify the source. You decide."


def _suggest_dialog(doc, base: str, text: str) -> tuple[str, dict] | None:
    """The Suggest-citation pick list, with an opt-in "Also search beyond my library" checkbox (backlog #30,
    wiring the already-shipped `beyond_library.py` engine into this adapter for the first time). Unchecked by
    default — matching the SAME explicit, opt-in-each-time consent model as the web Cite pane's own checkbox
    (`.claude/security-audits/2026-07-11_beyond-library-citation-suggest.md`). In-library results load
    immediately (local, fast); checking the box triggers a live re-fetch that also queries public metadata
    providers, merging in beyond-library candidates — visually marked, each carrying its own reason/
    relationship label instead of a quote+stance. The checkbox toggle is a synchronous fetch inside the UI
    callback (the same mechanism `spike_live_search_listener` proved safe for the composer's search box), but
    beyond-library search is a multi-provider external fan-out, so expect a noticeably longer pause than the
    local-only path — a real UX characteristic to confirm in the still-owed manual verification pass, not a bug.

    Returns ``(kind, item)`` for the picked row — `kind` is ``"library"`` (item is the in-library suggestion
    dict) or ``"beyond"`` (item is the beyond-library suggestion dict, not yet in the library) — or None if
    nothing was picked."""
    import unohelper
    from com.sun.star.awt import XItemListener

    ctx = _component_ctx()
    smgr = ctx.ServiceManager
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 360, 210, "Suggest citations"

    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height = 6, 6, 348, 22
    label.Label = _SUGGEST_CAVEAT
    label.MultiLine = True
    dm.insertByName("lbl", label)

    lst = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    lst.PositionX, lst.PositionY, lst.Width, lst.Height = 6, 32, 348, 108
    lst.Dropdown = False
    lst.MultiSelection = False
    dm.insertByName("list", lst)

    beyond_box = dm.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
    beyond_box.PositionX, beyond_box.PositionY, beyond_box.Width, beyond_box.Height = 6, 144, 320, 14
    beyond_box.Label, beyond_box.State = "Also search beyond my library", 0
    dm.insertByName("beyond", beyond_box)

    ok = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.PositionX, ok.PositionY, ok.Width, ok.Height, ok.Label, ok.PushButtonType = 262, 182, 44, 16, "Insert", 1
    dm.insertByName("ok", ok)
    cancel = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.PositionX, cancel.PositionY, cancel.Width, cancel.Height, cancel.Label, cancel.PushButtonType = (
        310,
        182,
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

    list_ctrl = dialog.getControl("list")
    beyond_ctrl = dialog.getControl("beyond")
    state = {"rows": []}  # list of (kind, item), parallel to the listbox's current rows

    def refresh(include_beyond: bool) -> None:
        result = fetch_suggestions(base, text, include_beyond_library=include_beyond)
        parallel = [("library", s) for s in result["suggestions"]]
        parallel += [("beyond", b) for b in result["beyond_library_suggestions"]]
        rows = build_suggest_rows(result["suggestions"]) + build_beyond_suggest_rows(
            result["beyond_library_suggestions"]
        )
        state["rows"] = parallel
        list_ctrl.getModel().StringItemList = tuple(rows)

    refresh(False)  # in-library results load immediately; beyond-library is opt-in only

    class _BeyondListener(unohelper.Base, XItemListener):
        def itemStateChanged(self, event):
            refresh(beyond_ctrl.getState() == 1)

        def disposing(self, event):
            pass

    beyond_ctrl.addItemListener(_BeyondListener())

    result_code = dialog.execute()  # 1 == Insert
    pos = list_ctrl.getSelectedItemPos() if result_code == 1 else -1
    dialog.dispose()
    if result_code != 1 or pos is None or pos < 0 or pos >= len(state["rows"]):
        return None
    return state["rows"][pos]


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
    """Suggest papers to cite for the current sentence — from the library by default, or also beyond it via an
    opt-in checkbox (backlog #30) — let the user pick one, and insert it.

    Returns the new mark's `rnd` tag, or None if nothing was inserted (no text / cancelled / nothing picked).
    The suggestion + stance signal, and the beyond-library search + reasons, are all the backend's (inc 156,
    271/272); this only presents the evidence and inserts the chosen cite. A beyond-library pick is added to
    the library first (`save_beyond_library_item`, the same write path the web app's own "Add to library"
    button uses), then cited — a real user might not have anything relevant in-library yet, so this no longer
    short-circuits on an empty in-library list before the user gets a chance to opt into searching further.
    """
    text = current_query_text(doc)
    if not text:
        _msgbox("Select a sentence (or place the cursor in one) to suggest citations for.")
        return None
    picked = _suggest_dialog(doc, base, text)
    if picked is None:
        return None
    kind, item = picked
    paper_id = save_beyond_library_item(base, item) if kind == "beyond" else item.get("paper_id")
    return insert_citation(doc, paper_id, base, cursor=_insertion_cursor_at_end(doc))


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
    catalog = style_catalog(base)
    style, locale = _get_pref(doc, base)
    query = _input_box(
        doc,
        "Citation style",
        "Search by journal, discipline, acronym, or style name (blank shows all):",
    )
    if query is None:
        return
    styles = list_styles(base, query)
    if not styles:
        _msgbox("No installed citation styles match that search.")
        return
    chosen = _choice_box(
        doc,
        "Citation style",
        f"Document style (application default: {catalog['default_style']}):",
        tuple((style_search_row(entry), entry["id"]) for entry in styles),
        style,
    )
    if chosen is None:
        return
    chosen_locale = _choice_box(
        doc,
        "Citation style",
        "Preview and document locale:",
        tuple(
            (
                "English (United States)" if item == "en-US" else "English (United Kingdom)",
                item,
            )
            for item in catalog["locales"]
        ),
        locale,
    )
    if chosen_locale is None:
        return
    preview = preview_style(base, chosen, chosen_locale)
    citations = preview.get("citations", [])
    bibliography = str(preview.get("bibliography_text") or "This style does not produce a bibliography.")
    preview_text = str(citations[0]) if citations else "(No citation preview.)"
    if len(bibliography) > 900:
        bibliography = bibliography[:897].rstrip() + "…"
    _msgbox(
        f"Example citation\n{preview_text}\n\nExample bibliography\n{bibliography}\n\n"
        "These are fictional example references."
    )
    action = _choice_box(
        doc,
        "Citation style",
        "What would you like to do?",
        (
            ("Apply to this document", "apply"),
            ("Open the full style manager in Callosum", "manager"),
        ),
        "apply",
    )
    if action == "manager":
        webbrowser.open(f"{base}/#citation-styles")
    elif action == "apply":
        set_style(doc, chosen, chosen_locale, base)


def style_search_row(style: dict) -> str:
    """Compact Writer pick-list row from one validated catalog entry."""
    star = "★ " if style.get("favorite") else ""
    format_label = "notes" if style.get("family") == "note" else str(style.get("citation_format") or "in-text")
    fields = ", ".join(str(field).replace("_", " ") for field in style.get("fields", [])[:3])
    detail = " · ".join(part for part in (format_label.replace("-", " "), fields) if part)
    return f"{star}{style['title']} — {detail}" if detail else f"{star}{style['title']}"


def set_note_placement_interactive(doc, _base: str) -> None:
    chosen = _choice_box(
        doc,
        "Note placement",
        "Where should new note-style citations appear?",
        (("Footnotes", "footnote"), ("Endnotes", "endnote")),
        note_placement(doc),
    )
    if chosen is None:
        return
    set_note_placement(doc, chosen)
    _msgbox(f"New note-style citations will be inserted as {chosen}s.")


def _default_conversion_copy_name(doc) -> str:
    url = doc.getURL()
    if url:
        path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
        base_name = os.path.splitext(os.path.basename(path))[0]
        if base_name:
            return f"{base_name}-converted.odt"
    return "callosum-converted.odt"


def _store_odt_copy(doc, save_url: str) -> None:
    from com.sun.star.beans import PropertyValue

    filt = PropertyValue()
    filt.Name, filt.Value = "FilterName", "writer8"
    doc.storeToURL(save_url, (filt,))


def save_converted_copy(
    doc,
    filename: str,
    target_style: str,
    locale: str,
    target_note_placement: str = DEFAULT_NOTE_PLACEMENT,
    base: str = DEFAULT_BASE,
) -> tuple[dict, str]:
    """Save an ODF copy with converted live fields, then verified-undo the open document conversion."""
    if not filename or not filename.strip():
        raise ValueError("A filename is required for the converted copy.")
    before = _conversion_snapshot(doc)
    result = convert_citation_placement(doc, target_style, locale, target_note_placement, base)
    save_url = _submission_copy_url(doc, filename.strip())
    try:
        _store_odt_copy(doc, save_url)
    except Exception as save_exc:
        doc.getUndoManager().undo()
        doc.getUndoManager().clearRedo()
        if _conversion_snapshot(doc) != before:
            raise RuntimeError(
                "Saving the converted copy failed and the open document did not fully restore. "
                "Close without saving and reopen it."
            ) from save_exc
        raise
    doc.getUndoManager().undo()
    doc.getUndoManager().clearRedo()
    if _conversion_snapshot(doc) != before:
        raise RuntimeError(
            "The converted copy was saved, but the open document did not fully restore. "
            "Close without saving and reopen it."
        )
    return result, save_url


def convert_citation_placement_interactive(doc, base: str) -> None:
    fields = scan_citations_in_order(doc)
    if not fields:
        _msgbox("No live Callosum citations were found in this document.")
        return
    styles = list_styles(base)
    current_style, current_locale = _get_pref(doc, base)
    chosen_style = _choice_box(
        doc,
        "Convert citation placement",
        "Target citation style:",
        tuple((style["title"], style["id"]) for style in styles),
        current_style,
    )
    if chosen_style is None:
        return
    family = next(style["family"] for style in styles if style["id"] == chosen_style)
    chosen_note_placement = note_placement(doc)
    if family == "note":
        chosen_note_placement = _choice_box(
            doc,
            "Convert citation placement",
            "Place converted note citations in:",
            (("Footnotes", "footnote"), ("Endnotes", "endnote")),
            chosen_note_placement,
        )
        if chosen_note_placement is None:
            return
    target = conversion_target_placement(family, chosen_note_placement)
    source = fields[0]["placement"]
    _msgbox(
        f"Ready to convert {len(fields)} live citation(s) from {source} to {target} placement using "
        f"{chosen_style}. Ambiguous notes, user prose, mixed placement, and tracked changes will be refused."
    )
    mode = _choice_box(
        doc,
        "Convert citation placement",
        "Apply this conversion to:",
        (("This document (one Undo step)", "document"), ("A separate .odt copy", "copy")),
        "document",
    )
    if mode is None:
        return

    if mode == "copy":
        filename = _input_box(
            doc,
            "Save converted copy",
            "Save the converted ODF copy as:",
            _default_conversion_copy_name(doc),
        )
        if not filename or not filename.strip():
            return
        try:
            result, save_url = save_converted_copy(
                doc,
                filename,
                chosen_style,
                current_locale,
                chosen_note_placement,
                base,
            )
        except Exception as exc:
            _msgbox(f"Could not save the converted copy: {exc}")
            return
        _msgbox(
            f"Saved a converted copy with {result['count']} citation(s).\n\n"
            f"Your open document is unchanged.\n{save_url}"
        )
        return
    try:
        result = convert_citation_placement(
            doc,
            chosen_style,
            current_locale,
            chosen_note_placement,
            base,
        )
    except Exception as exc:
        _msgbox(f"Could not convert citation placement: {exc}\n\nThe document was not changed.")
        return
    _msgbox(
        f"Converted {result['count']} citation(s) from {result['source_placement']} to "
        f"{result['target_placement']} placement. Use Writer Undo to restore the original document."
    )


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
    _auto_refresh(doc, base)


def _merge_adjacent_interactive(doc, base: str, direction: str) -> None:
    current = mark_at_cursor(doc)
    if current is None:
        _msgbox("Place your cursor inside a citation to merge it.")
        return
    if current.get("placement") != "inline":
        _msgbox("Use Edit citation to add or reorder multiple sources within a note citation.")
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
    _auto_refresh(doc, base)


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
    if field.get("placement") != "inline":
        _msgbox("Use Edit citation to add or remove sources within a note citation.")
        return
    split_citation(doc, field)
    _auto_refresh(doc, base)


def edit_citation_interactive(doc, base: str) -> None:
    """Reopen the composer on the citation at the cursor, pre-populated with its current items + per-occurrence
    options (Phase 5c, backlog #33/#34) — add/remove/reorder sources, change locators/prefixes/suffixes/
    suppress-author, or clear an item's overrides, then save back to the SAME citation."""
    field = mark_at_cursor(doc)
    if field is None:
        _msgbox("Place your cursor inside a citation to edit it.")
        return
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import composer

    items = composer.run_composer_dialog(doc, base, existing_items=field["items"])
    if items is None:
        return  # cancelled -- the citation is left exactly as it was
    edit_citation_items(doc, field, items, base)


def insert_bibliography_here_interactive(doc, base: str) -> None:
    """Move (or, if none exists yet, create) the bibliography at the cursor (P0 phase 7)."""
    refresh(
        doc,
        base,
        bib_cursor=_insertion_cursor(doc),
        update_citations=False,
        update_bibliography=True,
    )


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


def toggle_cite_auto_interactive(doc, base: str) -> None:
    """Flip automatic citation formatting independently of automatic bibliography rebuilding."""
    enabled = not cite_auto_enabled(doc)
    set_cite_auto(doc, enabled)
    if enabled:
        detail = (
            " Citation changes will format immediately. Existing pending changes are not refreshed automatically; "
            "run Refresh / renumber + bibliography or Refresh citations only once."
        )
    else:
        detail = (
            " Citation changes remain live fields, but their visible text will not update until you run "
            "Refresh / renumber + bibliography or Refresh citations only. Automatic bibliography rebuilding "
            "is controlled separately."
        )
    _msgbox(f"Automatic citation formatting is now {'ON' if enabled else 'OFF'}.{detail}")


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
    citation_dirty, bibliography_dirty = dirty_state(doc)

    return {
        "malformed": malformed,
        "unsupported_version": unsupported,
        "duplicate_ids": duplicate_ids,
        "orphaned": orphaned,
        "bibliography": bib_state,
        "refresh_pending": {
            "citations": citation_dirty,
            "bibliography": bibliography_dirty,
        },
    }


def document_diagnostics_interactive(doc, base: str) -> None:
    report = diagnose_document(doc, base)
    lines = []
    pending = report["refresh_pending"]
    if pending["citations"] or pending["bibliography"]:
        surfaces = (
            "citations and bibliography"
            if all(pending.values())
            else ("citations" if pending["citations"] else "bibliography")
        )
        lines.append(f"Refresh pending for {surfaces} — use the Writer Infobar action or a matching Refresh command.")
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


_RETRACTION_LABEL = {"retracted": "RETRACTED", "correction": "CORRECTION", "concern": "EXPRESSION OF CONCERN"}


def _paper_id_from_item(item: dict) -> str | None:
    """The ``"callosum-{paper_id}"`` item-id idiom, in one place (P1 item #12, backlog #33/#34) — new call
    sites should use this rather than copy-pasting the strip-the-prefix idiom a 4th time."""
    item_id = str(item.get("id") or "")
    return item_id[len("callosum-") :] if item_id.startswith("callosum-") else None


def list_document_citations(doc, base: str) -> list[dict]:
    """Read-only rollup of every unique cited work in the document, in first-occurrence order (P1 item #12,
    backlog #33/#34 — the "Citations in this document" panel's data source), PLUS any manually-included
    uncited "further reading" works (P1 item #11) appended after. Never mutates.

    For each unique paper_id: a rendered ``Author Year — Title`` row (`csl_record_row`), the occurrence count
    (a paper cited 3 times counts once here, count=3; an uncited-include entry is always 0), whether it's
    orphaned (no longer in the library — reuses `fetch_csl`'s existing raise-on-missing contract, the same
    signal `diagnose_document` already uses), retraction status (one call per unique paper_id to the
    already-audited, read-only ``GET /papers/{id}/retraction`` — no new endpoint), whether it's currently
    excluded from the bibliography (`PREF_BIB_EXCLUDE`), and the FIRST occurrence's mark for navigate-to (``None``
    for an uncited-include entry — there's nowhere in the document to navigate to).

    Returns ``[{"paper_id", "row", "count", "orphaned", "retraction_label", "excluded", "uncited", "mark"}, ...]``.
    """
    seen: dict[str, dict] = {}
    order: list[str] = []
    for field in scan_citations_in_order(doc):
        for item in field["items"]:
            paper_id = _paper_id_from_item(item)
            if paper_id is None:
                continue
            if paper_id not in seen:
                seen[paper_id] = {"paper_id": paper_id, "count": 0, "mark": field["_mark"]}
                order.append(paper_id)
            seen[paper_id]["count"] += 1

    exclude_ids = set(_get_id_list(doc, PREF_BIB_EXCLUDE))
    for paper_id in _get_id_list(doc, PREF_BIB_UNCITED):
        if paper_id not in seen:  # already cited normally -- don't duplicate as a separate uncited row
            seen[paper_id] = {"paper_id": paper_id, "count": 0, "mark": None}
            order.append(paper_id)

    results = []
    for paper_id in order:
        entry = seen[paper_id]
        try:
            record = fetch_csl(base, paper_id)
            row = csl_record_row(record)
            orphaned = False
        except ValueError:
            row = f"(missing from library — paper {paper_id})"
            orphaned = True
        retraction_label = None
        if not orphaned:
            try:
                status = _get_json(f"{base}/papers/{paper_id}/retraction").get("status")
                retraction_label = _RETRACTION_LABEL.get(status)
            except Exception:
                retraction_label = None  # never let a retraction-lookup hiccup break the whole panel
        results.append(
            {
                "paper_id": paper_id,
                "row": row,
                "count": entry["count"],
                "orphaned": orphaned,
                "retraction_label": retraction_label,
                "excluded": paper_id in exclude_ids,
                "uncited": entry["mark"] is None,
                "mark": entry["mark"],
            }
        )
    return results


def citations_panel_interactive(doc, base: str) -> None:
    """Open the "Citations in this document" panel (P1 item #12; bibliography editing P1 item #11, both
    backlog #33/#34): every unique cited work, occurrence count, missing/orphaned + retraction flags, a live
    filter, click-to-navigate, and — from the panel itself — toggling a cited work's bibliography exclusion or
    adding an uncited "further reading" work. A snapshot re-fetched after every edit made from within the panel
    (the always-open/live-refreshing version that also tracks edits made OUTSIDE it is a later, deliberately
    deferred phase; see `citations_panel.py`'s own docstring for why). Opens even with nothing cited yet — that
    is itself a valid starting point for "Add uncited work(s)…" to build a reading list from scratch."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import citations_panel

    mark = citations_panel.run_citations_panel(doc, base)
    if mark is not None:
        doc.getCurrentController().select(mark.getAnchor())


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
    "refreshCitations": refresh_citations,
    "refreshSelectedCitation": refresh_selected_citation,
    "refreshCurrentSection": refresh_current_section,
    "refreshBibliography": refresh_bibliography,
    "refreshPending": refresh_pending,
    "setStyle": set_style_interactive,
    "setNotePlacement": set_note_placement_interactive,
    "convertCitationPlacement": convert_citation_placement_interactive,
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
    "toggleCiteAuto": toggle_cite_auto_interactive,
    "toggleBibAuto": toggle_bib_auto_interactive,
    "diagnostics": document_diagnostics_interactive,
    "editCitation": edit_citation_interactive,
    "citationsPanel": citations_panel_interactive,
}


def dispatch(action: str, doc, base: str) -> None:
    """Run a named action against `doc`. Shared by the macro entry points (macro mode) and the .oxt dispatcher
    (component mode); the caller resolves doc + base and wraps errors."""
    before = document_structure_signature(doc)
    try:
        with suspend_document_observation(doc):
            _sync_dirty_infobar(doc)
            _ACTIONS[action](doc, base)
    except Exception:
        after = document_structure_signature(doc)
        if structure_change_flags(before, after) != (False, False):
            set_dirty_state(doc, citations=True, bibliography=True)
        raise
    finally:
        observe_document(doc)


def _macro(action: str) -> None:
    """Macro-mode entry point body: resolve the doc + base from the script context, run the action, surface errors."""
    try:
        dispatch(action, _current_doc(), _base())
    except RefreshCancelled:
        pass
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


def CallosumRefreshCitations(*_args):
    _macro("refreshCitations")


def CallosumRefreshSelectedCitation(*_args):
    _macro("refreshSelectedCitation")


def CallosumRefreshCurrentSection(*_args):
    _macro("refreshCurrentSection")


def CallosumRefreshBibliography(*_args):
    _macro("refreshBibliography")


def CallosumSetStyle(*_args):
    _macro("setStyle")


def CallosumSetNotePlacement(*_args):
    _macro("setNotePlacement")


def CallosumConvertCitationPlacement(*_args):
    _macro("convertCitationPlacement")


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


def CallosumToggleCiteAuto(*_args):
    _macro("toggleCiteAuto")


def CallosumPrepareSubmissionCopy(*_args):
    _macro("prepareSubmissionCopy")


def CallosumDiagnostics(*_args):
    _macro("diagnostics")


def CallosumEditCitation(*_args):
    _macro("editCitation")


def CallosumCitationsPanel(*_args):
    _macro("citationsPanel")


g_exportedScripts = (
    CallosumAddCitation,
    CallosumInsertCitation,
    CallosumSuggestCitations,
    CallosumRefresh,
    CallosumRefreshCitations,
    CallosumRefreshSelectedCitation,
    CallosumRefreshCurrentSection,
    CallosumRefreshBibliography,
    CallosumSetStyle,
    CallosumSetNotePlacement,
    CallosumConvertCitationPlacement,
    CallosumFlatten,
    CallosumInsertStatement,
    CallosumSetServerUrl,
    CallosumDeleteCitation,
    CallosumMergeWithNext,
    CallosumMergeWithPrevious,
    CallosumSplitCitation,
    CallosumOpenInCallosum,
    CallosumInsertBibliographyHere,
    CallosumToggleCiteAuto,
    CallosumToggleBibAuto,
    CallosumPrepareSubmissionCopy,
    CallosumDiagnostics,
    CallosumEditCitation,
    CallosumCitationsPanel,
)
