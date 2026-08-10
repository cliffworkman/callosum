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
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser

# ── constants ──────────────────────────────────────────────────────────────────────────────────────────
MARK_PREFIX = "CALLOSUM_CITATION"  # ReferenceMark name prefix → identifies our live fields
BIB_BOOKMARK = "CALLOSUM_BIBLIOGRAPHY"  # bookmark marking the START of the managed bibliography block
# The END of the managed range (P0 phase 7, backlog #33/#34) — a bookmark PAIR bounds the block so a rebuild
# never touches text.getEnd(), replacing the old "bookmark to document end" design that could silently destroy
# any user text placed after the bibliography.
BIB_BOOKMARK_END = "CALLOSUM_BIBLIOGRAPHY_END"
BIB_ENTRY_PREFIX = "CALLOSUM_BIB_ENTRY_"  # stable internal-link targets, one per rendered bibliography item
SECTION_BIB_PREFIX = "CALLOSUM_SECTION_BIBLIOGRAPHY_"
SECTION_BIB_KINDS = ("SCOPE", "START", "END")
MAX_SECTION_BIBLIOGRAPHIES = 50
MAX_CITATION_SOURCE_CHOICES = 50
_SECTION_BIB_NAME = re.compile(rf"^{SECTION_BIB_PREFIX}([0-9a-f]{{32}})_({'|'.join(SECTION_BIB_KINDS)})$")
MAX_BIBLIOGRAPHY_LINKS_PER_ENTRY = 20
MAX_BIBLIOGRAPHY_EXTERNAL_URL = 2048
MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS = 1000
MAX_BIBLIOGRAPHY_CATEGORIES = 50
BIBLIOGRAPHY_CATEGORY_MAX = 80
MAX_BIBLIOGRAPHY_CATEGORY_METADATA = 131_072
MAX_BIBLIOGRAPHY_CATEGORY_ORDER_METADATA = 8_192
MAX_BIBLIOGRAPHY_CATEGORY_PAPER_ID = 20
BIBLIOGRAPHY_UNCATEGORIZED = "Other references"
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
    # inc 460 (evidence-aware Suggest-Citation, backlog #33/#34 P2 #17): the local passage that justified
    # inserting this citation, for later audit via the "Citations in this document" panel. `evidence_snippet`
    # is capped well under the server's own 400-char QUOTE_MAX (see EVIDENCE_SNIPPET_MAX) since the mark-name
    # payload has no enforced size ceiling and a grouped multi-source citation would otherwise multiply quote
    # text across every item. These ride along harmlessly in a render-document request if the citation is later
    # refreshed (CitationItem's `extra="allow"` + citeproc-js already ignores CSL fields it doesn't recognize,
    # same as every other extra field already embedded in the stored CSL record) -- not worth stripping.
    "evidence_chunk_id": None,
    "evidence_page_start": None,
    "evidence_page_end": None,
    "evidence_snippet": None,
    # inc 461 ("Insert evidence", backlog #33/#34 P2 #20): the annotation-sourced analog of `evidence_chunk_id`
    # -- a saved PDF highlight has no chunk_id, so its own persisted-annotation id is the audit anchor instead.
    "evidence_annotation_id": None,
}
EVIDENCE_SNIPPET_MAX = 150
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
PREF_BIB_HEADING = "CallosumBibHeading"  # custom per-document heading; absent/blank means "References"
PREF_BIB_LINKS = "CallosumBibLinks"  # "1" hyperlinks unambiguous one-work citations to their bibliography entry
PREF_BIB_EXTERNAL_LINKS = "CallosumBibExternalLinks"  # "1" links DOI/URL text rendered by the current CSL style
PREF_BIB_CATEGORIES = "CallosumBibCategories"  # JSON object: Callosum paper id -> document-local category label
PREF_BIB_CATEGORY_ORDER = "CallosumBibCategoryOrder"  # JSON list: explicit document-local category precedence
PREF_JOURNAL_ABBREVIATIONS = "CallosumJournalAbbreviations"  # library, MEDLINE-first, or full journal titles
DEFAULT_STYLE = "apa"
DEFAULT_LOCALE = "en-US"
DEFAULT_NOTE_PLACEMENT = "footnote"
NOTE_PLACEMENTS = ("footnote", "endnote")
DEFAULT_JOURNAL_ABBREVIATION_MODE = "library"
JOURNAL_ABBREVIATION_MODES = ("library", "medline", "full")
JOURNAL_ABBREVIATION_OPTIONS = (
    ("Library abbreviations (default)", "library"),
    ("MEDLINE first (library fallback)", "medline"),
    ("Full journal titles", "full"),
)
DEFAULT_BASE = "http://127.0.0.1:8080"
HTTP_TIMEOUT = 20
PROGRESS_MIN_WORK = 20  # roughly ten full-document citation updates; avoid flashing UI for small documents
PLACEHOLDER = "{citation}"  # transient visible text before the first render
BIB_HEADING = "References"
BIB_HEADING_MAX = 120
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
_SECTION_REMOVAL_UNDO_LISTENERS: dict[str, object] = {}
_SECTION_REMOVAL_STATES: dict[str, dict[str, dict]] = {}


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
    journal_abbreviation_mode: str = DEFAULT_JOURNAL_ABBREVIATION_MODE,
) -> dict:
    """Turn ordered citation fields into the `/citations/render-document` body.

    Each field is ``{"citationID": <rnd>, "items": [<CSL-JSON>, …], "noteIndex": <0 or Writer note number>}``
    (in document order). Zero is the established in-text sentinel; note-style fields carry the one-based Writer
    footnote number citeproc needs for first/subsequent/ibid state. `uncited_items`/
    `bibliography_exclude_ids` (P1 item #11, backlog #33/#34) are both optional — omitted entirely, they're empty
    lists, matching the backend's own additive/optional contract. The journal-title preference is document-level
    render input; it never rewrites the embedded CSL records.
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
        "journal_abbreviation_mode": normalize_journal_abbreviation_mode(journal_abbreviation_mode),
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


def save_beyond_library_item_for_later(base: str, item: dict, source_query: str | None = None) -> None:
    """Flag a beyond-library suggestion for a second look later (backlog #30's last open piece, inc 465) via
    `POST /citations/beyond-library/save` -- a sibling to `save_beyond_library_item` above, which instead posts
    to `/discovery/save` and adds the paper outright. This never adds anything to the library; it only persists
    the suggestion (verbatim, same evidence fields already shown) into the reviewable "Saved for later" queue,
    reviewed/added/dismissed from the web app (Discover -> Search -> Saved for later)."""
    _post_json(
        f"{base}/citations/beyond-library/save",
        {
            "dedup_key": item.get("dedup_key"),
            "title": item.get("title") or "Untitled",
            "sources": item.get("sources") or [],
            "doi": item.get("doi"),
            "abstract": item.get("abstract"),
            "authors": item.get("authors") or [],
            "journal": item.get("journal"),
            "year": item.get("year"),
            "url": item.get("url"),
            "reason": item.get("reason"),
            "evidence_text": item.get("evidence_text"),
            "evidence_kind": item.get("evidence_kind"),
            "relationship_kind": item.get("relationship_kind"),
            "relationship_label": item.get("relationship_label"),
            "anchor_paper_id": item.get("anchor_paper_id"),
            "anchor_title": item.get("anchor_title"),
            "source_query": source_query,
        },
    )


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


def list_paper_annotations(base: str, paper_id) -> list[dict]:
    """A paper's saved highlights/annotations (inc 461, "Insert evidence", backlog #33/#34 P2 #20) --
    GET /papers/{id}/annotations, an existing endpoint this adapter has never called before. Already returns
    everything needed (verbatim quote, page, note, color) in one call; [] on a malformed non-list response,
    matching `search_library`'s own convention (a real network/HTTP failure still propagates, caught the same
    way every other action's does -- by `_macro`'s broad except)."""
    data = _get_json(f"{base}/papers/{paper_id}/annotations")
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


def citation_source_choices(items: list[dict], available_ids: set[str] | None = None) -> list[dict[str, str]]:
    """Return bounded, de-duplicated Callosum sources for one citation.

    ``available_ids`` optionally restricts the result to sources that currently have a stable full-bibliography
    target. Foreign/malformed ids fail closed; section bibliographies never create duplicate targets.
    """
    choices = []
    seen = set()
    for item in items[:MAX_CITATION_SOURCE_CHOICES]:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        paper_id = item_id[len("callosum-") :] if item_id.startswith("callosum-") else ""
        if not paper_id.isdigit() or item_id in seen:
            continue
        seen.add(item_id)
        if available_ids is not None and item_id not in available_ids:
            continue
        choices.append({"item_id": item_id, "paper_id": paper_id, "row": csl_record_row(item)})
    return choices


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


def normalize_journal_abbreviation_mode(value: str | None) -> str:
    mode = str(value or DEFAULT_JOURNAL_ABBREVIATION_MODE).strip().lower()
    if mode not in JOURNAL_ABBREVIATION_MODES:
        raise ValueError("Journal abbreviation mode must be library, medline, or full.")
    return mode


def journal_abbreviation_mode(doc) -> str:
    """Document-level journal-title source; corrupt/legacy values retain the current library behavior."""
    try:
        return normalize_journal_abbreviation_mode(_effective_user_prop(doc, PREF_JOURNAL_ABBREVIATIONS))
    except ValueError:
        return DEFAULT_JOURNAL_ABBREVIATION_MODE


def journal_abbreviation_feedback(summary: dict) -> str:
    """Concise post-render validation for the document preference dialog."""
    if not isinstance(summary, dict):
        return "The preference was saved; refresh again after adding citations to validate journal coverage."
    journals = max(0, int(summary.get("journal_count", 0)))
    if not summary.get("style_requests_short_titles"):
        return (
            f"The preference was saved for {journals} journal source{'s' if journals != 1 else ''}. "
            "The current CSL style requests full journal titles, so visible text is unchanged."
        )
    mode = normalize_journal_abbreviation_mode(summary.get("mode"))
    if mode == "full":
        return f"Full titles are active for {journals} journal source{'s' if journals != 1 else ''}."
    medline = max(0, int(summary.get("medline_count", 0)))
    library = max(0, int(summary.get("library_count", 0)))
    unknown = max(0, int(summary.get("unknown_count", 0)))
    detail = f"{medline} MEDLINE, {library} library"
    if unknown:
        titles = [str(title) for title in summary.get("unknown_titles", [])[:3] if str(title)]
        warning = f"; {unknown} unknown"
        if titles:
            warning += f" ({'; '.join(titles)})"
    else:
        warning = "; no unknown journals"
    return f"Validated {journals} journal source{'s' if journals != 1 else ''}: {detail}{warning}."


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


def _bookmark_pair_signature(doc, start_name: str, end_name: str) -> tuple[bool, bool, str]:
    bookmarks = doc.getBookmarks()
    has_start = bookmarks.hasByName(start_name)
    has_end = bookmarks.hasByName(end_name)
    if not (has_start and has_end):
        return has_start, has_end, ""
    text = doc.getText()
    cursor = text.createTextCursorByRange(bookmarks.getByName(start_name).getAnchor().getStart())
    cursor.gotoRange(bookmarks.getByName(end_name).getAnchor().getEnd(), True)
    return True, True, cursor.getString()


def _managed_bibliography_signature(doc) -> tuple[bool, bool, str]:
    return _bookmark_pair_signature(doc, BIB_BOOKMARK, BIB_BOOKMARK_END)


def _section_bibliography_signatures(doc) -> tuple[tuple[str, bool, bool, str], ...]:
    complete, damaged = section_bibliography_records(doc)
    signatures = [(record["id"], *_bookmark_pair_signature(doc, record["start"], record["end"])) for record in complete]
    signatures.extend((identifier, False, False, "damaged") for identifier in damaged)
    return tuple(sorted(signatures))


def _managed_bibliographies_signature(
    doc,
) -> tuple[tuple[bool, bool, str], tuple[tuple[str, bool, bool, str], ...]]:
    """Snapshot the full and every heading-scoped managed bibliography range."""
    return _managed_bibliography_signature(doc), _section_bibliography_signatures(doc)


def document_structure_signature(
    doc,
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[bool, bool, str], tuple[tuple[str, bool, bool, str], ...]]]:
    """Snapshot only the Writer structure that can make rendered citations or bibliography stale."""
    citations = tuple(
        (field["_mark"].Name, field["_mark"].getAnchor().getString()) for field in scan_citations_in_order(doc)
    )
    return citations, _managed_bibliographies_signature(doc)


def structure_change_flags(
    previous: tuple,
    current: tuple,
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


def normalize_bibliography_category(value: str | None) -> str | None:
    """Validate one document-local category label; blank deliberately removes an assignment."""
    raw = str(value or "")
    category = raw.strip()
    if not category:
        return None
    if len(category) > BIBLIOGRAPHY_CATEGORY_MAX:
        raise ValueError(f"Bibliography categories must be {BIBLIOGRAPHY_CATEGORY_MAX} characters or fewer.")
    if not raw.isprintable():
        raise ValueError("Bibliography categories must be a single line without control characters.")
    if category.casefold() == BIBLIOGRAPHY_UNCATEGORIZED.casefold():
        raise ValueError(f"{BIBLIOGRAPHY_UNCATEGORIZED!r} is reserved for entries without a category.")
    return category


def bibliography_categories(doc) -> dict[str, str]:
    """Read the bounded paper-id/category map; corrupt or excessive metadata degrades to no categories."""
    raw = _effective_user_prop(doc, PREF_BIB_CATEGORIES)
    if not raw:
        return {}
    if not isinstance(raw, str) or len(raw) > MAX_BIBLIOGRAPHY_CATEGORY_METADATA:
        return {}
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(decoded, dict) or len(decoded) > MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS:
        return {}
    categories: dict[str, str] = {}
    canonical: dict[str, str] = {}
    for raw_id, raw_category in decoded.items():
        paper_id = str(raw_id)
        if not paper_id.isdigit() or len(paper_id) > MAX_BIBLIOGRAPHY_CATEGORY_PAPER_ID:
            continue
        try:
            category = normalize_bibliography_category(raw_category)
        except ValueError:
            continue
        if category is None:
            continue
        folded = category.casefold()
        if folded not in canonical:
            if len(canonical) >= MAX_BIBLIOGRAPHY_CATEGORIES:
                return {}
            canonical[folded] = category
        categories[paper_id] = canonical[folded]
    return categories


def _set_bibliography_categories(doc, assignments: dict[str, str]) -> None:
    """Persist a validated deterministic category map, or remove the property when empty."""
    if len(assignments) > MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS:
        raise ValueError(f"A document can categorize at most {MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS} works.")
    normalized: dict[str, str] = {}
    canonical: dict[str, str] = {}
    for raw_id, raw_category in assignments.items():
        paper_id = str(raw_id)
        if not paper_id.isdigit() or len(paper_id) > MAX_BIBLIOGRAPHY_CATEGORY_PAPER_ID:
            raise ValueError("Bibliography category assignments require numeric Callosum paper ids.")
        category = normalize_bibliography_category(raw_category)
        if category is None:
            continue
        folded = category.casefold()
        if folded not in canonical:
            if len(canonical) >= MAX_BIBLIOGRAPHY_CATEGORIES:
                raise ValueError(f"A document can use at most {MAX_BIBLIOGRAPHY_CATEGORIES} bibliography categories.")
            canonical[folded] = category
        normalized[paper_id] = canonical[folded]
    value = json.dumps(dict(sorted(normalized.items())), ensure_ascii=False) if normalized else None
    if value is not None and len(value) > MAX_BIBLIOGRAPHY_CATEGORY_METADATA:
        raise ValueError("Bibliography category metadata is too large for one Writer document.")
    _set_user_prop_value(doc, PREF_BIB_CATEGORIES, value)


def bibliography_category_order(doc) -> list[str]:
    """Read one bounded explicit category order; corrupt metadata degrades to the alphabetical default."""
    raw = _effective_user_prop(doc, PREF_BIB_CATEGORY_ORDER)
    if not raw:
        return []
    if not isinstance(raw, str) or len(raw) > MAX_BIBLIOGRAPHY_CATEGORY_ORDER_METADATA:
        return []
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(decoded, list) or len(decoded) > MAX_BIBLIOGRAPHY_CATEGORIES:
        return []
    order: list[str] = []
    seen: set[str] = set()
    for raw_category in decoded:
        if not isinstance(raw_category, str):
            return []
        try:
            category = normalize_bibliography_category(raw_category)
        except ValueError:
            return []
        if category is None or category.casefold() in seen:
            return []
        seen.add(category.casefold())
        order.append(category)
    return order


def _set_bibliography_category_order(doc, categories: list[str] | tuple[str, ...]) -> list[str]:
    """Validate and persist explicit category precedence, removing the property for alphabetical order."""
    if len(categories) > MAX_BIBLIOGRAPHY_CATEGORIES:
        raise ValueError(f"A document can order at most {MAX_BIBLIOGRAPHY_CATEGORIES} bibliography categories.")
    order: list[str] = []
    seen: set[str] = set()
    for raw_category in categories:
        if not isinstance(raw_category, str):
            raise ValueError("Bibliography category order labels must be text.")
        category = normalize_bibliography_category(raw_category)
        if category is None:
            raise ValueError("Bibliography category order cannot contain a blank label.")
        folded = category.casefold()
        if folded in seen:
            raise ValueError("Bibliography category order cannot contain duplicate labels.")
        seen.add(folded)
        order.append(category)
    value = json.dumps(order, ensure_ascii=False) if order else None
    if value is not None and len(value) > MAX_BIBLIOGRAPHY_CATEGORY_ORDER_METADATA:
        raise ValueError("Bibliography category order metadata is too large for one Writer document.")
    _set_user_prop_value(doc, PREF_BIB_CATEGORY_ORDER, value)
    return order


def ordered_bibliography_categories(categories: list[str], configured_order: list[str]) -> list[str]:
    """Order active categories by explicit precedence, then alphabetically for any new/unranked labels."""
    rank = {category.casefold(): index for index, category in enumerate(configured_order)}
    return sorted(
        categories,
        key=lambda category: (rank.get(category.casefold(), len(rank)), category.casefold()),
    )


def section_bibliography_bookmarks(identifier: str) -> dict[str, str]:
    """Return the three reserved bookmark names for one bounded heading-scoped bibliography."""
    value = str(identifier)
    if len(value) != 32 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("Section bibliography identifiers must be 32 lowercase hexadecimal characters.")
    return {kind.lower(): f"{SECTION_BIB_PREFIX}{value}_{kind}" for kind in SECTION_BIB_KINDS}


def decode_section_bibliography_bookmark(name: str) -> tuple[str, str] | None:
    """Decode one exact adapter-owned section-bibliography bookmark name."""
    match = _SECTION_BIB_NAME.fullmatch(name) if isinstance(name, str) else None
    return (match.group(1), match.group(2).lower()) if match else None


def section_bibliography_records(doc) -> tuple[list[dict[str, str]], list[str]]:
    """Inventory complete section bibliography triples and damaged ids without reading arbitrary bookmarks."""
    grouped: dict[str, dict[str, str]] = {}
    for name in doc.getBookmarks().getElementNames():
        decoded = decode_section_bibliography_bookmark(name)
        if decoded is None:
            continue
        identifier, kind = decoded
        grouped.setdefault(identifier, {})[kind] = name
    if len(grouped) > MAX_SECTION_BIBLIOGRAPHIES:
        raise ValueError(f"A Writer document can contain at most {MAX_SECTION_BIBLIOGRAPHIES} section bibliographies.")
    complete = []
    damaged = []
    for identifier, names in sorted(grouped.items()):
        if set(names) == {"scope", "start", "end"}:
            complete.append({"id": identifier, **names})
        else:
            damaged.append(identifier)
    return complete, damaged


def format_section_bibliography_row(label: str, cited_work_count: int) -> str:
    """Format one bounded manager row without exposing bookmark identifiers."""
    count = max(0, int(cited_work_count))
    noun = "work" if count == 1 else "works"
    return f"{label} — {count} cited {noun}"


def filter_bibliography_entries(
    entries: list[str],
    entry_ids: list[list[str]],
    entry_links: list[list[tuple[int, int, str]]],
    entry_categories: list[str | None],
    allowed_item_ids: set[str],
) -> tuple[list[str], list[list[str]], list[list[tuple[int, int, str]]], list[str | None]]:
    """Project one citeproc-sorted bibliography onto the works cited by a heading-defined section."""
    if not (
        len(entry_ids) == len(entries) and len(entry_links) == len(entries) and len(entry_categories) == len(entries)
    ):
        return [], [], [], []
    indexes = [index for index, ids in enumerate(entry_ids) if any(str(item_id) in allowed_item_ids for item_id in ids)]
    return (
        [entries[index] for index in indexes],
        [entry_ids[index] for index in indexes],
        [entry_links[index] for index in indexes],
        [entry_categories[index] for index in indexes],
    )


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
    desired_links: dict[str, str] | None = None,
) -> list[tuple[str, str, str]]:
    """Plan targeted writes whose rendered text or managed bibliography link differs from the desired state."""
    return [
        (
            field["_mark"].Name,
            rendered[field["citationID"]],
            (desired_links or {}).get(field["_mark"].Name, ""),
        )
        for field in fields
        if rendered.get(field["citationID"])
        and (citation_names is None or field["_mark"].Name in citation_names)
        and (
            field["_mark"].getAnchor().getString() != rendered[field["citationID"]]
            or (
                desired_links is not None
                and _mark_hyperlink_url(field["_mark"]) != desired_links.get(field["_mark"].Name, "")
            )
        )
    ]


def normalize_bibliography_heading(value: str | None) -> str:
    """Bound one user-authored Writer heading; blank deliberately restores the default."""
    heading = str(value or "").strip()
    if not heading:
        return BIB_HEADING
    if len(heading) > BIB_HEADING_MAX:
        raise ValueError(f"Bibliography heading must be {BIB_HEADING_MAX} characters or fewer.")
    if not heading.isprintable():
        raise ValueError("Bibliography heading must be a single line without control characters.")
    return heading


def bibliography_heading(doc) -> str:
    """Return the validated per-document heading used for every managed bibliography rebuild."""
    return normalize_bibliography_heading(_effective_user_prop(doc, PREF_BIB_HEADING))


def categorize_bibliography_entries(
    entries: list[str],
    entry_ids: list[list[str]],
    entry_links: list[list[tuple[int, int, str]]],
    assignments: dict[str, str],
    category_order: list[str] | None = None,
) -> tuple[list[str], list[list[str]], list[list[tuple[int, int, str]]], list[str | None]]:
    """Group citeproc-sorted entries by category while preserving citeproc order within every group."""
    if len(entry_ids) != len(entries):
        entry_ids = [[] for _entry in entries]
    if len(entry_links) != len(entries):
        entry_links = [[] for _entry in entries]
    categories: list[str | None] = []
    for ids in entry_ids:
        paper_ids = [_paper_id_from_item({"id": item_id}) for item_id in ids]
        assigned = [assignments.get(paper_id or "") for paper_id in paper_ids]
        categories.append(assigned[0] if assigned and assigned[0] is not None and len(set(assigned)) == 1 else None)
    if not any(categories):
        return entries, entry_ids, entry_links, [None for _entry in entries]
    order = ordered_bibliography_categories(
        list({category for category in categories if category is not None}),
        category_order or [],
    )
    grouped_indexes = [
        index
        for category in [*order, None]
        for index, entry_category in enumerate(categories)
        if entry_category == category
    ]
    visible_categories = [categories[index] or BIBLIOGRAPHY_UNCATEGORIZED for index in grouped_indexes]
    return (
        [entries[index] for index in grouped_indexes],
        [entry_ids[index] for index in grouped_indexes],
        [entry_links[index] for index in grouped_indexes],
        visible_categories,
    )


def bibliography_layout(
    entries: list[str],
    categories: list[str | None] | None = None,
    heading: str = BIB_HEADING,
) -> tuple[str, list[int]]:
    """Return exact managed text plus each entry's offset, including deterministic category headings."""
    if not entries:
        return "", []
    aligned = categories if categories is not None and len(categories) == len(entries) else [None for _ in entries]
    parts = [normalize_bibliography_heading(heading) + "\n"]
    length = len(parts[0])
    offsets = []
    previous_category = None
    for entry, category in zip(entries, aligned, strict=True):
        if category is not None and category != previous_category:
            if previous_category is not None:
                parts.append("\n")
                length += 1
            parts.append(category + "\n")
            length += len(category) + 1
        offsets.append(length)
        parts.append(entry + "\n")
        length += len(entry) + 1
        previous_category = category
    return "".join(parts), offsets


def rendered_bibliography_text(
    entries: list[str],
    heading: str = BIB_HEADING,
    categories: list[str | None] | None = None,
) -> str:
    """The exact plain-text contents `_write_bibliography` places between the managed bookmark pair."""
    return bibliography_layout(entries, categories, heading)[0]


def bibliography_render_is_current(
    doc,
    entries: list[str],
    categories: list[str | None] | None = None,
    *,
    start_name: str = BIB_BOOKMARK,
    end_name: str = BIB_BOOKMARK_END,
) -> bool:
    """Whether an intact managed bibliography already contains the requested rendered plain text."""
    signature = (
        _managed_bibliography_signature(doc)
        if start_name == BIB_BOOKMARK and end_name == BIB_BOOKMARK_END
        else _bookmark_pair_signature(doc, start_name, end_name)
    )
    has_start, has_end, current = signature
    return (
        has_start
        and has_end
        and current
        == rendered_bibliography_text(
            entries,
            bibliography_heading(doc),
            categories,
        )
    )


def bibliography_entry_bookmark(item_id: str) -> str | None:
    """Map an adapter-owned CSL id to a stable, Writer-safe bibliography target name."""
    value = str(item_id)
    prefix = "callosum-"
    suffix = value[len(prefix) :] if value.startswith(prefix) else ""
    return f"{BIB_ENTRY_PREFIX}{suffix}" if suffix.isdigit() else None


def _bibliography_target_names(entry_ids: list[list[str]]) -> set[str]:
    return {name for ids in entry_ids for item_id in ids if (name := bibliography_entry_bookmark(item_id)) is not None}


def _existing_bibliography_target_names(doc) -> set[str]:
    return {name for name in doc.getBookmarks().getElementNames() if name.startswith(BIB_ENTRY_PREFIX)}


def bibliography_targets_are_current(doc, entry_ids: list[list[str]]) -> bool:
    """Whether Writer contains exactly the stable internal-link targets represented by this citeproc render."""
    return _existing_bibliography_target_names(doc) == _bibliography_target_names(entry_ids)


def bibliography_links_enabled(doc) -> bool:
    """Internal citation-to-bibliography links are opt-in and persist with the Writer document."""
    return _effective_user_prop(doc, PREF_BIB_LINKS) == "1"


def bibliography_external_links_enabled(doc) -> bool:
    """Rendered title/DOI/URL text becomes an external web link only after a per-document opt-in."""
    return _effective_user_prop(doc, PREF_BIB_EXTERNAL_LINKS) == "1"


def _validated_bibliography_external_url(value) -> str | None:
    if not isinstance(value, str) or not value or len(value) > MAX_BIBLIOGRAPHY_EXTERNAL_URL:
        return None
    if any(char.isspace() or ord(char) < 32 for char in value):
        return None
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not hostname or parsed.username or parsed.password:
        return None
    return value


def normalize_bibliography_links(entries: list[str], raw_links) -> list[list[tuple[int, int, str]]]:
    """Validate the additive render metadata against its exact entry text; malformed input degrades to plain."""
    if not isinstance(raw_links, list) or len(raw_links) != len(entries):
        return [[] for _entry in entries]
    normalized = []
    for entry, links in zip(entries, raw_links, strict=True):
        accepted = []
        previous_end = 0
        if not isinstance(links, list):
            normalized.append(accepted)
            continue
        for link in links[:MAX_BIBLIOGRAPHY_LINKS_PER_ENTRY]:
            if not isinstance(link, dict):
                continue
            start, length = link.get("start"), link.get("length")
            url = _validated_bibliography_external_url(link.get("url"))
            if (
                not isinstance(start, int)
                or isinstance(start, bool)
                or not isinstance(length, int)
                or isinstance(length, bool)
                or start < previous_end
                or length <= 0
                or start + length > len(entry)
                or url is None
            ):
                continue
            accepted.append((start, length, url))
            previous_end = start + length
        normalized.append(accepted)
    return normalized


def _bibliography_span_url(doc, offset: int, length: int, start_name: str = BIB_BOOKMARK) -> str:
    """Read one expected link range relative to the managed bibliography's start bookmark."""
    bookmarks = doc.getBookmarks()
    if not bookmarks.hasByName(start_name):
        return ""
    text = doc.getText()
    cursor = text.createTextCursorByRange(bookmarks.getByName(start_name).getAnchor().getStart())
    if not cursor.goRight(offset, False) or not cursor.goRight(length, True):
        return ""
    try:
        return str(cursor.getPropertyValue("HyperLinkURL") or "")
    except Exception:
        return ""


def bibliography_external_links_are_current(
    doc,
    entries: list[str],
    entry_links: list[list[tuple[int, int, str]]],
    enabled: bool,
    categories: list[str | None] | None = None,
    *,
    start_name: str = BIB_BOOKMARK,
) -> bool:
    """Compare only backend-declared title/DOI/URL spans; arbitrary prose outside the block is never read."""
    _text, offsets = bibliography_layout(entries, categories, bibliography_heading(doc))
    for offset, links in zip(offsets, entry_links, strict=True):
        for start, length, url in links:
            current = (
                _bibliography_span_url(doc, offset + start, length)
                if start_name == BIB_BOOKMARK
                else _bibliography_span_url(doc, offset + start, length, start_name)
            )
            if current != (url if enabled else ""):
                return False
    return True


def _mark_hyperlink_url(mark) -> str:
    """Read the uniform hyperlink URL over one ReferenceMark anchor; mixed/unreadable formatting is unmanaged."""
    try:
        anchor = mark.getAnchor()
        cursor = anchor.getText().createTextCursorByRange(anchor)
        return str(cursor.getPropertyValue("HyperLinkURL") or "")
    except Exception:
        return ""


def desired_citation_links(fields: list[dict], available_ids: set[str], enabled: bool) -> dict[str, str]:
    """Manage only Callosum internal links; grouped/excluded citations stay plain and external links survive."""
    links = {}
    for field in fields:
        current_url = _mark_hyperlink_url(field["_mark"])
        url = "" if current_url.startswith(f"#{BIB_ENTRY_PREFIX}") else current_url
        items = field.get("items") or []
        if enabled and len(items) == 1:
            item_id = str(items[0].get("id", ""))
            target = bibliography_entry_bookmark(item_id)
            if target is not None and item_id in available_ids:
                url = f"#{target}"
        links[field["_mark"].Name] = url
    return links


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


def _outline_section_bounds_at(doc, position) -> tuple[object, object] | None:
    """Return the heading-defined section containing one main-document position as ``(start, end)``.

    Writer's ``OutlineLevel`` is the semantic authority: 0 is body text and 1..10 are headings. A section starts
    at the nearest preceding heading and includes nested lower-ranked headings until the next heading at the same
    or higher rank. Text before the first heading is a preamble section; a heading-free document is one section.
    """
    text = doc.getText()
    try:
        position = _main_document_position(doc, position)
        if position is None:
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
            if text.compareRegionStarts(start, position) >= 0:
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


def _current_outline_section_bounds(doc) -> tuple[object, object] | None:
    """Return the heading-defined section containing the Writer caret."""
    try:
        position = doc.getCurrentController().getViewCursor().getStart()
    except Exception:
        return None
    return _outline_section_bounds_at(doc, position)


def _field_is_in_outline_bounds(doc, field: dict, start, end) -> bool:
    anchor = field["_note"].getAnchor() if field.get("_note") is not None else field["_mark"].getAnchor()
    text = doc.getText()
    try:
        anchor_start = anchor.getStart()
        return text.compareRegionStarts(start, anchor_start) >= 0 and text.compareRegionStarts(anchor_start, end) > 0
    except Exception:
        return False


def current_section_citation_names(doc) -> set[str] | None:
    """Return recognized citation mark names inside the caret's heading-defined section."""
    bounds = _current_outline_section_bounds(doc)
    if bounds is None:
        return None
    start, end = bounds
    return {
        field["_mark"].Name
        for field in scan_citations_in_order(doc)
        if _field_is_in_outline_bounds(doc, field, start, end)
    }


def _same_outline_bounds(doc, first: tuple[object, object], second: tuple[object, object]) -> bool:
    text = doc.getText()
    try:
        return text.compareRegionStarts(first[0], second[0]) == 0 and text.compareRegionStarts(first[1], second[1]) == 0
    except Exception:
        return first == second


def _section_bibliography_record_at(doc, position) -> dict[str, str] | None:
    wanted = _outline_section_bounds_at(doc, position)
    if wanted is None:
        return None
    bookmarks = doc.getBookmarks()
    for record in section_bibliography_records(doc)[0]:
        scope = bookmarks.getByName(record["scope"]).getAnchor().getStart()
        actual = _outline_section_bounds_at(doc, scope)
        if actual is not None and _same_outline_bounds(doc, wanted, actual):
            return record
    return None


def _section_bibliography_item_ids(doc, fields: list[dict], record: dict[str, str]) -> set[str]:
    bookmarks = doc.getBookmarks()
    if not bookmarks.hasByName(record["scope"]):
        return set()
    bounds = _outline_section_bounds_at(doc, bookmarks.getByName(record["scope"]).getAnchor().getStart())
    if bounds is None:
        return set()
    start, end = bounds
    return {
        str(item.get("id"))
        for field in fields
        if _field_is_in_outline_bounds(doc, field, start, end)
        for item in field["items"]
        if str(item.get("id") or "").startswith("callosum-")
    }


def _section_bibliography_label_at(doc, position) -> str:
    """Return the owning heading text, or an honest preamble/document fallback."""
    text = doc.getText()
    first_heading = None
    try:
        enumeration = text.createEnumeration()
        while enumeration.hasMoreElements():
            paragraph = enumeration.nextElement()
            try:
                start = paragraph.getStart()
                level = int(paragraph.getPropertyValue("OutlineLevel"))
            except Exception:
                continue
            if level <= 0:
                continue
            if first_heading is None:
                first_heading = start
            if text.compareRegionStarts(start, position) == 0:
                value = " ".join(str(paragraph.getString() or "").split())
                if not value:
                    return "Untitled heading"
                return value[:BIB_HEADING_MAX] + ("…" if len(value) > BIB_HEADING_MAX else "")
    except Exception:
        return "Section"
    if first_heading is not None:
        try:
            if text.compareRegionStarts(position, first_heading) > 0:
                return "Preamble"
        except Exception:
            pass
    return "Document"


def section_bibliography_summaries(doc) -> tuple[list[dict], list[str]]:
    """Return complete blocks in document order with owning heading and unique cited-work count."""
    records, damaged = section_bibliography_records(doc)
    bookmarks = doc.getBookmarks()
    text = doc.getText()
    ordered = order_by_comparator(
        records,
        lambda first, second: text.compareRegionStarts(
            bookmarks.getByName(first["scope"]).getAnchor().getStart(),
            bookmarks.getByName(second["scope"]).getAnchor().getStart(),
        ),
    )
    fields = scan_citations_in_order(doc)
    summaries = []
    for record in ordered:
        position = bookmarks.getByName(record["scope"]).getAnchor().getStart()
        label = _section_bibliography_label_at(doc, position)
        count = len(_section_bibliography_item_ids(doc, fields, record))
        summaries.append(
            {**record, "label": label, "cited_work_count": count, "row": format_section_bibliography_row(label, count)}
        )
    return summaries, damaged


def _section_bibliography_plans(
    doc,
    fields: list[dict],
    entries: list[str],
    entry_ids: list[list[str]],
    entry_links: list[list[tuple[int, int, str]]],
    entry_categories: list[str | None],
    external_links: bool,
) -> list[dict]:
    plans = []
    for record in section_bibliography_records(doc)[0]:
        projected = filter_bibliography_entries(
            entries,
            entry_ids,
            entry_links,
            entry_categories,
            _section_bibliography_item_ids(doc, fields, record),
        )
        projected_entries, projected_ids, projected_links, projected_categories = projected
        if bibliography_render_is_current(
            doc,
            projected_entries,
            projected_categories,
            start_name=record["start"],
            end_name=record["end"],
        ) and bibliography_external_links_are_current(
            doc,
            projected_entries,
            projected_links,
            external_links,
            projected_categories,
            start_name=record["start"],
        ):
            continue
        plans.append(
            {
                **record,
                "entries": projected_entries,
                "entry_ids": projected_ids,
                "entry_links": projected_links,
                "entry_categories": projected_categories,
                "external_links": external_links,
            }
        )
    return plans


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
    section_records, damaged_section_bibliographies = section_bibliography_records(doc)
    if write_bibliography and damaged_section_bibliographies:
        raise ValueError(
            "Document diagnostics found damaged section bibliography bookmarks. "
            "Remove their remaining Callosum scope/start/end bookmarks before refreshing."
        )
    section_bibliography_count = len(section_records) if write_bibliography else 0
    target_count = (
        sum(1 for field in fields if citation_names is None or field["_mark"].Name in citation_names)
        if update_citations
        else 0
    )
    progress = _new_refresh_progress(
        doc,
        max(1, len(fields) + target_count + int(write_bibliography) + section_bibliography_count),
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
            section_plans = (
                _section_bibliography_plans(doc, fields, [], [], [], [], bibliography_external_links_enabled(doc))
                if write_bibliography
                else []
            )
            _transactional_apply(
                doc,
                [],
                [],
                bib_cursor=bib_cursor,
                write_bibliography=apply_bibliography,
                section_bibliographies=section_plans,
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
                journal_abbreviation_mode=journal_abbreviation_mode(doc),
            ),
        )
        progress.update(len(fields), "Callosum: checking the live document")
        if render_input_signature(scan_citations_in_order(doc)) != expected_signature:
            raise RuntimeError(
                "Citation fields changed while Callosum was formatting them; no rendered changes were applied. "
                "Run Refresh again."
            )
        rendered = {c["citationID"]: c.get("text", "") for c in response.get("citations", [])}
        bibliography_entries = response.get("bibliography_text", "").splitlines()
        bibliography_entry_ids = response.get("bibliography_entry_ids", [])
        if len(bibliography_entry_ids) != len(bibliography_entries):
            bibliography_entry_ids = [[] for _entry in bibliography_entries]
        bibliography_entry_links = normalize_bibliography_links(
            bibliography_entries,
            response.get("bibliography_links", []),
        )
        bibliography_entries, bibliography_entry_ids, bibliography_entry_links, bibliography_entry_categories = (
            categorize_bibliography_entries(
                bibliography_entries,
                bibliography_entry_ids,
                bibliography_entry_links,
                bibliography_categories(doc),
                bibliography_category_order(doc),
            )
        )
        external_links_enabled = bibliography_external_links_enabled(doc)
        section_plans = (
            _section_bibliography_plans(
                doc,
                fields,
                bibliography_entries,
                bibliography_entry_ids,
                bibliography_entry_links,
                bibliography_entry_categories,
                external_links_enabled,
            )
            if write_bibliography
            else []
        )
        apply_bibliography = write_bibliography and (
            bib_cursor is not None
            or not bibliography_render_is_current(doc, bibliography_entries, bibliography_entry_categories)
            or not bibliography_targets_are_current(doc, bibliography_entry_ids)
            or not bibliography_external_links_are_current(
                doc,
                bibliography_entries,
                bibliography_entry_links,
                external_links_enabled,
                bibliography_entry_categories,
            )
        )
        available_ids = {
            str(item_id)
            for ids in bibliography_entry_ids
            for item_id in ids
            if apply_bibliography or doc.getBookmarks().hasByName(bibliography_entry_bookmark(item_id) or "\0")
        }
        links = desired_citation_links(fields, available_ids, bibliography_links_enabled(doc))
        # Capture immutable names only for fields whose visible render or managed link changed. Recreating one
        # mark invalidates other held mark references, so `_transactional_apply` re-fetches every name fresh.
        plan = incremental_citation_plan(fields, rendered, citation_names, links) if update_citations else []
        _transactional_apply(
            doc,
            plan,
            bibliography_entries,
            bib_entry_ids=bibliography_entry_ids,
            bib_entry_links=bibliography_entry_links,
            bib_entry_categories=bibliography_entry_categories,
            bib_external_links=external_links_enabled,
            bib_cursor=bib_cursor,
            write_bibliography=apply_bibliography,
            section_bibliographies=section_plans,
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


def insert_section_bibliography(doc, base: str = DEFAULT_BASE) -> str | None:
    """Insert one bounded live bibliography for the caret's heading subtree, alongside the full bibliography."""
    try:
        view_position = doc.getCurrentController().getViewCursor().getStart()
    except Exception:
        _msgbox("Place your cursor in the main document text where the section bibliography should appear.")
        return None
    if not _range_belongs_to_text(doc.getText(), view_position):
        _msgbox("Section bibliographies must be inserted in the main document text, not inside a note.")
        return None
    bounds = _outline_section_bounds_at(doc, view_position)
    if bounds is None:
        _msgbox("Callosum could not determine the heading-defined section at the cursor.")
        return None
    if _section_bibliography_record_at(doc, view_position) is not None:
        _msgbox("This heading-defined section already has a Callosum bibliography.")
        return None
    complete, damaged = section_bibliography_records(doc)
    if damaged:
        raise ValueError("Repair or remove damaged section bibliography bookmarks before inserting another.")
    if len(complete) >= MAX_SECTION_BIBLIOGRAPHIES:
        raise ValueError(f"A Writer document can contain at most {MAX_SECTION_BIBLIOGRAPHIES} section bibliographies.")

    fields = scan_citations_in_order(doc)
    start, end = bounds
    allowed_ids = {
        str(item.get("id"))
        for field in fields
        if _field_is_in_outline_bounds(doc, field, start, end)
        for item in field["items"]
        if str(item.get("id") or "").startswith("callosum-")
    }
    if not allowed_ids:
        _msgbox("No live Callosum citations were found in the current heading-defined section.")
        return None

    response = refresh(doc, base, update_citations=False, update_bibliography=False)
    entries = response.get("bibliography_text", "").splitlines()
    entry_ids = response.get("bibliography_entry_ids", [])
    if len(entry_ids) != len(entries):
        entry_ids = [[] for _entry in entries]
    entry_links = normalize_bibliography_links(entries, response.get("bibliography_links", []))
    entries, entry_ids, entry_links, entry_categories = categorize_bibliography_entries(
        entries,
        entry_ids,
        entry_links,
        bibliography_categories(doc),
        bibliography_category_order(doc),
    )
    entries, entry_ids, entry_links, entry_categories = filter_bibliography_entries(
        entries,
        entry_ids,
        entry_links,
        entry_categories,
        allowed_ids,
    )

    identifier = uuid.uuid4().hex
    names = section_bibliography_bookmarks(identifier)
    insertion = doc.getText().createTextCursorByRange(view_position)
    undo = doc.getUndoManager()
    undo.enterUndoContext("Insert Callosum section bibliography")
    try:
        scope = doc.createInstance("com.sun.star.text.Bookmark")
        scope.Name = names["scope"]
        doc.getText().insertTextContent(start, scope, False)
        _write_bibliography(
            doc,
            entries,
            entry_ids=entry_ids,
            entry_links=entry_links,
            entry_categories=entry_categories,
            external_links=bibliography_external_links_enabled(doc),
            cursor=insertion,
            start_name=names["start"],
            end_name=names["end"],
            manage_targets=False,
        )
    except Exception as exc:
        undo.leaveUndoContext()
        undo.undo()
        current = doc.getBookmarks()
        if any(current.hasByName(name) for name in names.values()):
            raise RuntimeError(
                "Writer could not fully roll back the failed section-bibliography insertion. "
                "Close without saving and reopen the document."
            ) from exc
        raise
    else:
        undo.leaveUndoContext()
    return identifier


def _section_removal_key(doc) -> tuple[str, ...]:
    """Identify the currently present strict section-bibliography ids, including damaged triples."""
    return tuple(
        sorted(
            {
                decoded[0]
                for name in doc.getBookmarks().getElementNames()
                if (decoded := decode_section_bibliography_bookmark(name)) is not None
            }
        )
    )


def _section_removal_snapshots(doc, records: list[dict[str, str]], base: str) -> list[dict]:
    """Capture exact text plus an optional current render plan for link-preserving Undo restoration."""
    snapshots = [
        {
            "record": dict(record),
            "contents": _bookmark_pair_signature(doc, record["start"], record["end"])[2],
            "plan": None,
        }
        for record in records
    ]
    try:
        fields = scan_citations_in_order(doc)
        response = refresh(doc, base, update_citations=False, update_bibliography=False)
        entries = response.get("bibliography_text", "").splitlines()
        entry_ids = response.get("bibliography_entry_ids", [])
        if len(entry_ids) != len(entries):
            entry_ids = [[] for _entry in entries]
        entry_links = normalize_bibliography_links(entries, response.get("bibliography_links", []))
        source = categorize_bibliography_entries(
            entries,
            entry_ids,
            entry_links,
            bibliography_categories(doc),
            bibliography_category_order(doc),
        )
        external_links = bibliography_external_links_enabled(doc)
        heading = bibliography_heading(doc)
        for snapshot in snapshots:
            record = snapshot["record"]
            projected = filter_bibliography_entries(
                *source,
                _section_bibliography_item_ids(doc, fields, record),
            )
            projected_entries, projected_ids, projected_links, projected_categories = projected
            if rendered_bibliography_text(projected_entries, heading, projected_categories) == snapshot["contents"]:
                snapshot["plan"] = {
                    "entries": projected_entries,
                    "entry_ids": projected_ids,
                    "entry_links": projected_links,
                    "entry_categories": projected_categories,
                    "external_links": external_links,
                }
    except Exception:
        # Removal stays available offline. Native Undo can still restore the exact text/bookmarks; if Writer needs
        # the listener fallback, it restores plain text and marks bibliography formatting pending.
        pass
    return snapshots


def _restore_section_removal_snapshot(doc, snapshot: dict) -> bool:
    """Restore one block after Writer Undo; return whether only plain-text recovery was available."""
    record = snapshot["record"]
    bookmarks = doc.getBookmarks()
    if not all(bookmarks.hasByName(record[kind]) for kind in ("scope", "start", "end")):
        raise RuntimeError("Writer Undo did not restore a removed section bibliography's bookmark triple.")
    if _bookmark_pair_signature(doc, record["start"], record["end"])[2] == snapshot["contents"]:
        return False
    text = doc.getText()
    cursor = text.createTextCursorByRange(bookmarks.getByName(record["start"]).getAnchor().getStart())
    plan = snapshot.get("plan")
    if plan is not None:
        _write_bibliography(
            doc,
            plan["entries"],
            entry_ids=plan["entry_ids"],
            entry_links=plan["entry_links"],
            entry_categories=plan["entry_categories"],
            external_links=plan["external_links"],
            cursor=cursor,
            start_name=record["start"],
            end_name=record["end"],
            manage_targets=False,
        )
        return False

    for kind in ("start", "end"):
        current = doc.getBookmarks()
        if current.hasByName(record[kind]):
            text.removeTextContent(current.getByName(record[kind]))
    start_mark = doc.createInstance("com.sun.star.text.Bookmark")
    start_mark.Name = record["start"]
    text.insertTextContent(cursor, start_mark, False)
    cursor.setPropertyValue("HyperLinkURL", "")
    text.insertString(cursor, snapshot["contents"], False)
    end_mark = doc.createInstance("com.sun.star.text.Bookmark")
    end_mark.Name = record["end"]
    text.insertTextContent(cursor, end_mark, False)
    return True


def _ensure_section_removal_undo_listener(doc):
    uid = _document_uid(doc)
    if uid in _SECTION_REMOVAL_UNDO_LISTENERS:
        return _SECTION_REMOVAL_UNDO_LISTENERS[uid]

    import unohelper
    from com.sun.star.document import XUndoManagerListener

    undo = doc.getUndoManager()

    class SectionRemovalUndoListener(unohelper.Base, XUndoManagerListener):
        def _restore(self, event):
            title = getattr(event, "UndoActionTitle", "")
            if title not in {
                "Remove Callosum section bibliography",
                "Remove all Callosum section bibliographies",
            }:
                return
            state = _SECTION_REMOVAL_STATES.get(uid, {})
            refs = state.get("states", {}).get(_section_removal_key(doc))
            if refs is None:
                return
            snapshots = [state["snapshots"][ref] for ref in refs]
            undo.lock()
            try:
                with suspend_document_observation(doc):
                    plain_recovery = False
                    for snapshot in snapshots:
                        plain_recovery = _restore_section_removal_snapshot(doc, snapshot) or plain_recovery
                    if plain_recovery:
                        set_dirty_state(doc, bibliography=True)
            finally:
                undo.unlock()

        def actionUndone(self, event):
            self._restore(event)

        def actionRedone(self, event):
            self._restore(event)

        def undoActionAdded(self, _event):
            pass

        def allActionsCleared(self, _event):
            _SECTION_REMOVAL_STATES.pop(uid, None)

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
            _SECTION_REMOVAL_STATES.pop(uid, None)

        def disposing(self, _event):
            _SECTION_REMOVAL_UNDO_LISTENERS.pop(uid, None)
            _SECTION_REMOVAL_STATES.pop(uid, None)

    listener = SectionRemovalUndoListener()
    undo.addUndoManagerListener(listener)
    _SECTION_REMOVAL_UNDO_LISTENERS[uid] = listener
    return listener


def _register_section_removal_states(
    doc,
    before_key: tuple[str, ...],
    before: list[dict],
    after_key: tuple[str, ...],
    after: list[dict],
) -> None:
    _ensure_section_removal_undo_listener(doc)
    state = _SECTION_REMOVAL_STATES.setdefault(_document_uid(doc), {"snapshots": {}, "states": {}})

    def intern(snapshots: list[dict]) -> tuple[tuple[str, str], ...]:
        refs = []
        for snapshot in snapshots:
            ref = (snapshot["record"]["id"], snapshot["contents"])
            state["snapshots"].setdefault(ref, snapshot)
            refs.append(ref)
        return tuple(refs)

    state["states"][before_key] = intern(before)
    state["states"][after_key] = intern(after)


def _delete_section_bibliography_record(doc, record: dict[str, str]) -> None:
    """Delete one already-validated section block inside the caller's Undo context."""
    text = doc.getText()
    bookmarks = doc.getBookmarks()
    cursor = text.createTextCursorByRange(bookmarks.getByName(record["start"]).getAnchor().getStart())
    cursor.gotoRange(bookmarks.getByName(record["end"]).getAnchor().getEnd(), True)
    text.insertString(cursor, "", True)
    for name in (record["scope"], record["start"], record["end"]):
        current = doc.getBookmarks()
        if current.hasByName(name):
            text.removeTextContent(current.getByName(name))


def _remove_section_bibliography_records(
    doc,
    records: list[dict[str, str]],
    undo_title: str,
    base: str,
) -> list[str]:
    """Remove validated blocks atomically and verify Writer's rollback if any deletion fails."""
    if not records:
        return []
    current_records = {record["id"]: record for record in section_bibliography_records(doc)[0]}
    selected = []
    for requested in records:
        current = current_records.get(requested["id"])
        if current is None:
            raise ValueError("A selected section bibliography is no longer available.")
        selected.append(current)
    all_records = list(current_records.values())
    snapshots = _section_removal_snapshots(doc, all_records, base)
    selected_ids = {record["id"] for record in selected}
    before_key = _section_removal_key(doc)
    after_key = tuple(identifier for identifier in before_key if identifier not in selected_ids)
    after_snapshots = [snapshot for snapshot in snapshots if snapshot["record"]["id"] not in selected_ids]
    _register_section_removal_states(doc, before_key, snapshots, after_key, after_snapshots)
    before = {record["id"]: _bookmark_pair_signature(doc, record["start"], record["end"]) for record in selected}
    undo = doc.getUndoManager()
    undo.enterUndoContext(undo_title)
    try:
        for record in reversed(selected):
            _delete_section_bibliography_record(doc, record)
    except Exception as exc:
        undo.leaveUndoContext()
        undo.undo()
        current = doc.getBookmarks()
        rollback_failed = any(
            not all(current.hasByName(record[kind]) for kind in ("scope", "start", "end"))
            or _bookmark_pair_signature(doc, record["start"], record["end"]) != before[record["id"]]
            for record in selected
        )
        if rollback_failed:
            raise RuntimeError(
                "Writer could not fully roll back the failed section-bibliography removal transaction. "
                "Close without saving and reopen the document."
            ) from exc
        raise
    else:
        undo.leaveUndoContext()
    return [record["id"] for record in selected]


def remove_section_bibliography_by_id(doc, identifier: str, base: str = DEFAULT_BASE) -> str:
    """Remove one complete section bibliography by its strict adapter-owned identifier."""
    records = {record["id"]: record for record in section_bibliography_records(doc)[0]}
    record = records.get(str(identifier))
    if record is None:
        raise ValueError("That section bibliography is no longer available.")
    return _remove_section_bibliography_records(doc, [record], "Remove Callosum section bibliography", base)[0]


def remove_all_section_bibliographies(doc, base: str = DEFAULT_BASE) -> list[str]:
    """Remove every complete section block in one Writer Undo step; damaged triples fail closed."""
    records, damaged = section_bibliography_records(doc)
    if damaged:
        raise ValueError("Repair damaged section bibliography bookmarks before removing all section bibliographies.")
    return _remove_section_bibliography_records(doc, records, "Remove all Callosum section bibliographies", base)


def go_to_section_bibliography(doc, identifier: str) -> bool:
    """Move the Writer view cursor to one section bibliography's managed start marker."""
    records = {record["id"]: record for record in section_bibliography_records(doc)[0]}
    record = records.get(str(identifier))
    if record is None:
        return False
    try:
        target = doc.getBookmarks().getByName(record["start"]).getAnchor().getStart()
        doc.getCurrentController().getViewCursor().gotoRange(target, False)
    except Exception:
        return False
    return True


def remove_section_bibliography(doc, base: str = DEFAULT_BASE) -> str | None:
    """Delete the managed bibliography for the caret's heading subtree without touching the full bibliography."""
    try:
        position = doc.getCurrentController().getViewCursor().getStart()
    except Exception:
        position = None
    if position is None:
        _msgbox("Place your cursor in the heading-defined section whose bibliography should be removed.")
        return None
    record = _section_bibliography_record_at(doc, position)
    if record is None:
        _msgbox("No Callosum section bibliography was found in the current heading-defined section.")
        return None
    return remove_section_bibliography_by_id(doc, record["id"], base)


def set_bibliography_heading(doc, heading: str | None, base: str = DEFAULT_BASE) -> str:
    """Persist and immediately apply one per-document bibliography heading, restoring state on failure."""
    normalized = normalize_bibliography_heading(heading)
    previous = _effective_user_prop(doc, PREF_BIB_HEADING)
    _set_user_prop_value(doc, PREF_BIB_HEADING, None if normalized == BIB_HEADING else normalized)
    try:
        refresh_bibliography(doc, base)
    except Exception:
        _set_user_prop_value(doc, PREF_BIB_HEADING, previous)
        raise
    return normalized


def set_journal_abbreviation_mode(doc, mode: str, base: str = DEFAULT_BASE) -> tuple[str, dict]:
    """Persist one render-only journal-title source and refresh atomically, restoring the preference on failure."""
    normalized = normalize_journal_abbreviation_mode(mode)
    previous = _effective_user_prop(doc, PREF_JOURNAL_ABBREVIATIONS)
    stored = None if normalized == DEFAULT_JOURNAL_ABBREVIATION_MODE else normalized
    _set_user_prop_value(doc, PREF_JOURNAL_ABBREVIATIONS, stored)
    try:
        response = refresh(doc, base, update_citations=True, update_bibliography=True)
    except Exception:
        _set_user_prop_value(doc, PREF_JOURNAL_ABBREVIATIONS, previous)
        raise
    summary = response.get("journal_abbreviations", {}) if isinstance(response, dict) else {}
    return normalized, summary


def set_bibliography_links(doc, enabled: bool, base: str = DEFAULT_BASE) -> bool:
    """Persist and immediately apply citation-to-bibliography links, restoring the preference on failure."""
    previous = _effective_user_prop(doc, PREF_BIB_LINKS)
    _set_user_prop_value(doc, PREF_BIB_LINKS, "1" if enabled else None)
    try:
        refresh(doc, base, update_citations=True, update_bibliography=True)
    except Exception:
        _set_user_prop_value(doc, PREF_BIB_LINKS, previous)
        raise
    return enabled


def set_bibliography_external_links(doc, enabled: bool, base: str = DEFAULT_BASE) -> tuple[bool, int]:
    """Persist/rebuild title/DOI/URL links and report how many validated spans were rendered."""
    previous = _effective_user_prop(doc, PREF_BIB_EXTERNAL_LINKS)
    _set_user_prop_value(doc, PREF_BIB_EXTERNAL_LINKS, "1" if enabled else None)
    try:
        response = refresh_bibliography(doc, base)
    except Exception:
        _set_user_prop_value(doc, PREF_BIB_EXTERNAL_LINKS, previous)
        raise
    link_count = 0
    if enabled and isinstance(response, dict):
        entries = str(response.get("bibliography_text", "")).splitlines()
        link_count = sum(
            len(links) for links in normalize_bibliography_links(entries, response.get("bibliography_links"))
        )
    return enabled, link_count


def set_bibliography_categories(
    doc,
    paper_ids: list[str] | tuple[str, ...],
    category: str | None,
    base: str = DEFAULT_BASE,
) -> dict[str, str | None]:
    """Assign/remove a category for one bounded work batch, with one refresh and whole-map rollback."""
    normalized_ids = list(dict.fromkeys(str(paper_id) for paper_id in paper_ids))
    if not normalized_ids:
        return {}
    if len(normalized_ids) > MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS:
        raise ValueError(
            f"A category can be assigned to at most {MAX_BIBLIOGRAPHY_CATEGORY_ASSIGNMENTS} works at once."
        )
    if any(not paper_id.isdigit() or len(paper_id) > MAX_BIBLIOGRAPHY_CATEGORY_PAPER_ID for paper_id in normalized_ids):
        raise ValueError("Bibliography category assignments require numeric Callosum paper ids.")
    normalized = normalize_bibliography_category(category)
    previous = bibliography_categories(doc)
    updated = dict(previous)
    canonical = (
        next(
            (existing for existing in updated.values() if existing.casefold() == normalized.casefold()),
            normalized,
        )
        if normalized is not None
        else None
    )
    for paper_id in normalized_ids:
        if canonical is None:
            updated.pop(paper_id, None)
        else:
            updated[paper_id] = canonical
    _set_bibliography_categories(doc, updated)
    try:
        refresh_bibliography(doc, base)
    except Exception:
        _set_bibliography_categories(doc, previous)
        raise
    return {paper_id: updated.get(paper_id) for paper_id in normalized_ids}


def set_bibliography_category(
    doc,
    paper_id: str,
    category: str | None,
    base: str = DEFAULT_BASE,
) -> str | None:
    """Backward-compatible single-work wrapper around the transactional batch category setter."""
    return set_bibliography_categories(doc, [paper_id], category, base)[str(paper_id)]


def set_bibliography_category_order(
    doc,
    categories: list[str] | tuple[str, ...],
    base: str = DEFAULT_BASE,
) -> list[str]:
    """Persist category precedence and rebuild once, restoring the exact previous property on failure."""
    previous = _effective_user_prop(doc, PREF_BIB_CATEGORY_ORDER)
    order = _set_bibliography_category_order(doc, categories)
    try:
        refresh_bibliography(doc, base)
    except Exception:
        _set_user_prop_value(doc, PREF_BIB_CATEGORY_ORDER, previous)
        raise
    return order


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


def _snapshot_mark_states(doc, names: list[str]) -> dict[str, tuple[str, str]]:
    """Rollback oracle for both visible citation text and the managed internal hyperlink."""
    marks = doc.getReferenceMarks()
    return {
        name: (marks.getByName(name).getAnchor().getString(), _mark_hyperlink_url(marks.getByName(name)))
        for name in names
        if marks.hasByName(name)
    }


def _transactional_apply(
    doc,
    plan: list[tuple[str, str, str]],
    bib_entries: list[str],
    bib_cursor=None,
    *,
    bib_entry_ids: list[list[str]] | None = None,
    bib_entry_links: list[list[tuple[int, int, str]]] | None = None,
    bib_entry_categories: list[str | None] | None = None,
    bib_external_links: bool = False,
    write_bibliography: bool | None = None,
    section_bibliographies: list[dict] | None = None,
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
    section_plans = section_bibliographies or []
    if not plan and not should_write_bibliography and not section_plans:
        return
    names = [name for name, _text, _url in plan]
    before = _snapshot_mark_states(doc, names)
    before_bibliographies = (
        (_managed_bibliography_signature(doc), _section_bibliography_signatures(doc))
        if should_write_bibliography or section_plans
        else None
    )
    undo = doc.getUndoManager()
    if progress is not None:
        progress.update(progress_offset, "Callosum: applying citation formatting")
    undo.enterUndoContext("Callosum refresh")
    try:
        for index, (name, text_out, hyperlink_url) in enumerate(plan, 1):
            marks = doc.getReferenceMarks()
            if not marks.hasByName(name):
                remaining = [candidate for candidate in names[index - 1 :] if marks.hasByName(candidate)]
                raise RuntimeError(
                    f"Citation mark disappeared before update {index} of {len(plan)}; "
                    f"{len(remaining)} planned mark(s) remain available."
                )
            mark = marks.getByName(name)  # fresh handle each time (never a stale ref)
            if mark.getAnchor().getString() != text_out:
                _replace_mark_text(doc, mark, text_out)
                mark = doc.getReferenceMarks().getByName(name)
            _set_mark_hyperlink(mark, hyperlink_url)
            if progress is not None:
                progress.update(
                    progress_offset + index,
                    f"Callosum: updated citation {index} of {len(plan)}",
                )
        if should_write_bibliography:
            if progress is not None:
                progress.update(progress_offset + len(plan), "Callosum: updating the bibliography")
            _write_bibliography(
                doc,
                bib_entries,
                entry_ids=bib_entry_ids,
                entry_links=bib_entry_links,
                entry_categories=bib_entry_categories,
                external_links=bib_external_links,
                cursor=bib_cursor,
            )
            if progress is not None:
                progress.update(progress_offset + len(plan) + 1, "Callosum: refresh complete")
        for section_index, section in enumerate(section_plans, 1):
            if progress is not None:
                progress.update(
                    progress_offset + len(plan) + int(should_write_bibliography) + section_index - 1,
                    f"Callosum: updating section bibliography {section_index} of {len(section_plans)}",
                )
            _write_bibliography(
                doc,
                section["entries"],
                entry_ids=section["entry_ids"],
                entry_links=section["entry_links"],
                entry_categories=section["entry_categories"],
                external_links=section["external_links"],
                start_name=section["start"],
                end_name=section["end"],
                manage_targets=False,
            )
            if progress is not None:
                progress.update(
                    progress_offset + len(plan) + int(should_write_bibliography) + section_index,
                    f"Callosum: updated section bibliography {section_index} of {len(section_plans)}",
                )
    except Exception as exc:
        undo.leaveUndoContext()
        undo.undo()
        after = _snapshot_mark_states(doc, names)
        after_bibliographies = (
            (_managed_bibliography_signature(doc), _section_bibliography_signatures(doc))
            if before_bibliographies is not None
            else None
        )
        if after != before or after_bibliographies != before_bibliographies:
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


def _set_mark_hyperlink(mark, hyperlink_url: str) -> None:
    """Apply or remove Callosum's internal link over the whole live citation anchor."""
    anchor = mark.getAnchor()
    cursor = anchor.getText().createTextCursorByRange(anchor)
    cursor.setPropertyValue("HyperLinkURL", hyperlink_url)


def _set_bibliography_span_url(
    doc,
    offset: int,
    length: int,
    url: str,
    start_name: str = BIB_BOOKMARK,
) -> None:
    """Apply one validated link to an existing range inside the bounded bibliography."""
    text = doc.getText()
    start = doc.getBookmarks().getByName(start_name).getAnchor().getStart()
    cursor = text.createTextCursorByRange(start)
    if (offset and not cursor.goRight(offset, False)) or not cursor.goRight(length, True):
        raise RuntimeError("Writer could not select a rendered bibliography link.")
    cursor.setPropertyValue("HyperLinkURL", url)


def _write_bibliography(
    doc,
    entries: list[str],
    entry_ids: list[list[str]] | None = None,
    entry_links: list[list[tuple[int, int, str]]] | None = None,
    entry_categories: list[str | None] | None = None,
    external_links: bool = False,
    cursor=None,
    *,
    start_name: str = BIB_BOOKMARK,
    end_name: str = BIB_BOOKMARK_END,
    manage_targets: bool = True,
) -> None:
    """(Re)build one BOUNDED managed bibliography block; `start_name` / `end_name` delimit its exact range.
    The defaults are the full-document `BIB_BOOKMARK` pair; section blocks pass their own strict names and disable
    global entry-target ownership. Clearing + rebuilding NEVER
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
    if manage_targets:
        for target_name in _existing_bibliography_target_names(doc):
            current = doc.getBookmarks()
            if current.hasByName(target_name):
                text.removeTextContent(current.getByName(target_name))
    has_start = bookmarks.hasByName(start_name)
    has_end = bookmarks.hasByName(end_name)
    if cursor is not None:
        if has_start:
            text.removeTextContent(bookmarks.getByName(start_name))
        if doc.getBookmarks().hasByName(end_name):
            text.removeTextContent(doc.getBookmarks().getByName(end_name))
    elif has_start and has_end:
        start = bookmarks.getByName(start_name).getAnchor().getStart()
        end = bookmarks.getByName(end_name).getAnchor().getEnd()
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
        if fresh_bookmarks.hasByName(start_name):
            text.removeTextContent(fresh_bookmarks.getByName(start_name))
        if fresh_bookmarks.hasByName(end_name):
            text.removeTextContent(fresh_bookmarks.getByName(end_name))
    elif has_start:
        # A damaged/legacy document (a start bookmark survived without its end) — rebuild fresh at the start
        # bookmark's own position rather than guessing where "the end" might be. A user-facing repair/diagnostics
        # command (Phase 9) reports this state explicitly; this is just the safe fallback so it never crashes.
        start = bookmarks.getByName(start_name).getAnchor().getStart()
        text.removeTextContent(bookmarks.getByName(start_name))
        cursor = text.createTextCursorByRange(start)
    else:
        cursor = text.createTextCursorByRange(text.getEnd())
        if _has_text(text):
            text.insertControlCharacter(cursor, _PARAGRAH_BREAK(), False)

    start_mark = doc.createInstance("com.sun.star.text.Bookmark")
    start_mark.Name = start_name
    text.insertTextContent(cursor, start_mark, False)  # zero-width; cursor stays put
    if entries:
        cursor.setPropertyValue("HyperLinkURL", "")
        text.insertString(cursor, bibliography_heading(doc) + "\n", False)
        aligned_ids = entry_ids if entry_ids is not None and len(entry_ids) == len(entries) else [[] for _ in entries]
        aligned_links = (
            entry_links if entry_links is not None and len(entry_links) == len(entries) else [[] for _ in entries]
        )
        aligned_categories = (
            entry_categories
            if entry_categories is not None and len(entry_categories) == len(entries)
            else [None for _ in entries]
        )
        previous_category = None
        for entry, ids, _links, category in zip(
            entries,
            aligned_ids,
            aligned_links,
            aligned_categories,
            strict=True,
        ):
            if category is not None and category != previous_category:
                if previous_category is not None:
                    text.insertString(cursor, "\n", False)
                text.insertString(cursor, category + "\n", False)
            if manage_targets:
                for item_id in ids:
                    target_name = bibliography_entry_bookmark(item_id)
                    if target_name is None:
                        continue
                    target = doc.createInstance("com.sun.star.text.Bookmark")
                    target.Name = target_name
                    text.insertTextContent(cursor, target, False)
            cursor.setPropertyValue("HyperLinkURL", "")
            text.insertString(cursor, entry + "\n", False)
            previous_category = category
    end_mark = doc.createInstance("com.sun.star.text.Bookmark")
    end_mark.Name = end_name
    text.insertTextContent(cursor, end_mark, False)  # placed AFTER the content — no bookmark-gravity ambiguity
    if entries and external_links:
        _layout, offsets = bibliography_layout(entries, aligned_categories, bibliography_heading(doc))
        for offset, links in zip(offsets, aligned_links, strict=True):
            for start, length, url in links:
                _set_bibliography_span_url(doc, offset + start, length, url, start_name)


def _bibliography_in_place_compatible(
    doc,
    entries: list[str],
    entry_categories: list[str | None],
    start_name: str,
    end_name: str,
) -> bool:
    """Whether old/new text share two safe boundary characters that conversion can leave untouched."""
    bookmarks = doc.getBookmarks()
    if not bookmarks.hasByName(start_name) or not bookmarks.hasByName(end_name):
        return False
    current = _bookmark_pair_signature(doc, start_name, end_name)[2]
    target = bibliography_layout(entries, entry_categories, bibliography_heading(doc))[0]
    return len(current) >= 2 and len(target) >= 2 and current[0] == target[0] and current[-1] == target[-1]


def _rewrite_bibliography_in_place(
    doc,
    entries: list[str],
    entry_ids: list[list[str]],
    entry_links: list[list[tuple[int, int, str]]],
    entry_categories: list[str | None],
    external_links: bool,
    *,
    start_name: str = BIB_BOOKMARK,
    end_name: str = BIB_BOOKMARK_END,
    manage_targets: bool = True,
) -> None:
    """Replace a bounded bibliography's interior while retaining its native boundary objects for Undo."""
    text = doc.getText()
    bookmarks = doc.getBookmarks()
    if not bookmarks.hasByName(start_name) or not bookmarks.hasByName(end_name):
        raise RuntimeError("Writer lost a managed bibliography boundary before conversion.")
    if manage_targets:
        for target_name in _existing_bibliography_target_names(doc):
            current = doc.getBookmarks()
            if current.hasByName(target_name):
                text.removeTextContent(current.getByName(target_name))

    layout, offsets = bibliography_layout(entries, entry_categories, bibliography_heading(doc))
    start = bookmarks.getByName(start_name).getAnchor().getStart()
    end = bookmarks.getByName(end_name).getAnchor().getEnd()
    if not _bibliography_in_place_compatible(doc, entries, entry_categories, start_name, end_name):
        raise RuntimeError("Conversion cannot safely retain the boundaries of an empty managed bibliography.")
    interior_start = text.createTextCursorByRange(start)
    interior_end = text.createTextCursorByRange(end)
    if not interior_start.goRight(1, False) or not interior_end.goLeft(1, False):
        raise RuntimeError("Writer could not select the interior of a managed bibliography.")
    interior_start.gotoRange(interior_end, True)
    interior_start.setString(layout[1:-1])

    current = doc.getBookmarks()
    if not current.hasByName(start_name) or not current.hasByName(end_name):
        raise RuntimeError("Writer removed a managed bibliography boundary during conversion.")
    if _bookmark_pair_signature(doc, start_name, end_name)[2] != layout:
        raise RuntimeError("Writer did not keep managed bibliography boundaries around the converted text.")
    formatted = text.createTextCursorByRange(current.getByName(start_name).getAnchor().getStart())
    formatted.gotoRange(current.getByName(end_name).getAnchor().getEnd(), True)
    formatted.setPropertyValue("HyperLinkURL", "")

    if manage_targets:
        for offset, ids in zip(offsets, entry_ids, strict=True):
            for item_id in ids:
                target_name = bibliography_entry_bookmark(item_id)
                if target_name is None:
                    continue
                target_cursor = text.createTextCursorByRange(
                    doc.getBookmarks().getByName(start_name).getAnchor().getStart()
                )
                if offset and not target_cursor.goRight(offset, False):
                    raise RuntimeError("Writer could not locate a converted bibliography entry target.")
                target = doc.createInstance("com.sun.star.text.Bookmark")
                target.Name = target_name
                text.insertTextContent(target_cursor, target, False)
    if external_links:
        for offset, links in zip(offsets, entry_links, strict=True):
            for start, length, url in links:
                _set_bibliography_span_url(doc, offset + start, length, url, start_name)


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


def _redline_items(doc) -> list:
    """Materialize Writer redlines through their guaranteed XEnumerationAccess contract."""
    redlines = doc.getRedlines()
    if hasattr(redlines, "createEnumeration"):
        enumeration = redlines.createEnumeration()
        items = []
        while enumeration.hasMoreElements():
            items.append(enumeration.nextElement())
        return items
    return _collection_items(redlines)


def _redline_ranges(doc) -> list[dict]:
    """Return validated Writer-owned start/end ranges for every tracked change."""
    records = []
    for redline in _redline_items(doc):
        try:
            start = redline.getPropertyValue("RedlineStart")
            end = redline.getPropertyValue("RedlineEnd")
            text = start.getText()
            if not _range_belongs_to_text(text, end):
                raise ValueError("redline endpoints use different Writer text containers")
        except Exception as exc:
            raise ValueError("Writer did not expose a comparable range for every tracked change.") from exc
        records.append({"redline": redline, "text": text, "start": start, "end": end})
    return records


def _ordered_ranges_overlap(compare, first_start, first_end, second_start, second_end) -> bool:
    """Compare half-open Writer spans; a collapsed point conflicts when it touches the other span."""
    first_collapsed = compare(first_start, first_end) == 0
    second_collapsed = compare(second_start, second_end) == 0
    left_order = compare(first_start, second_end)
    right_order = compare(second_start, first_end)
    if first_collapsed or second_collapsed:
        return left_order >= 0 and right_order >= 0
    return left_order > 0 and right_order > 0


def _conversion_managed_ranges(doc, fields: list[dict]) -> list[tuple[object, object, object, str]]:
    """Text spans/points that placement conversion can remove, replace, or insert into."""
    main_text = doc.getText()
    ranges = []
    for field in fields:
        mark = field["_mark"]
        if field["placement"] == "inline":
            anchor = mark.getAnchor()
            ranges.append((main_text, anchor.getStart(), anchor.getEnd(), "a live citation"))
            continue
        note = field["_note"]
        ranges.append((note, note.getStart(), note.getEnd(), "a source citation note"))
        note_anchor = note.getAnchor()
        ranges.append((main_text, note_anchor.getStart(), note_anchor.getEnd(), "a source citation note anchor"))

    state_marks = _conversion_state_marks(doc)
    state_anchor = state_marks[0].getAnchor() if state_marks else main_text.getStart()
    ranges.append((main_text, state_anchor.getStart(), state_anchor.getEnd(), "Callosum conversion state"))

    if bib_auto_enabled(doc):
        bookmarks = doc.getBookmarks()
        if bookmarks.hasByName(BIB_BOOKMARK) and bookmarks.hasByName(BIB_BOOKMARK_END):
            start = bookmarks.getByName(BIB_BOOKMARK).getAnchor().getStart()
            end = bookmarks.getByName(BIB_BOOKMARK_END).getAnchor().getEnd()
        else:
            start = end = main_text.getEnd()
        ranges.append((main_text, start, end, "the managed bibliography"))
        for record in section_bibliography_records(doc)[0]:
            start = bookmarks.getByName(record["start"]).getAnchor().getStart()
            end = bookmarks.getByName(record["end"]).getAnchor().getEnd()
            ranges.append((main_text, start, end, "a managed section bibliography"))
    return ranges


def _tracked_change_conversion_error(doc, fields: list[dict]) -> str | None:
    try:
        redlines = _redline_ranges(doc)
    except Exception:
        return (
            "Callosum could not locate every tracked change safely. Accept or reject tracked changes before "
            "converting citation placement."
        )
    if not redlines:
        return None
    for record in redlines:
        text = record["text"]
        for _managed_text, start, end, label in _conversion_managed_ranges(doc, fields):
            if not _range_belongs_to_text(text, start) or not _range_belongs_to_text(text, end):
                continue
            try:
                overlaps = _ordered_ranges_overlap(
                    text.compareRegionStarts,
                    record["start"],
                    record["end"],
                    start,
                    end,
                )
            except Exception:
                return (
                    "Callosum could not compare every tracked change safely. Accept or reject tracked changes "
                    "before converting citation placement."
                )
            if overlaps:
                return f"Accept or reject tracked changes that overlap {label} before converting citation placement."
    return None


def _redline_property(redline, name: str) -> str:
    try:
        value = redline.getPropertyValue(name)
    except Exception:
        return ""
    return "" if value is None else str(value)


def _redline_container_label(doc, range_) -> str:
    if _range_belongs_to_text(doc.getText(), range_):
        return "main"
    for note in _note_containers(doc):
        if _range_belongs_to_text(note["_note"], range_):
            return note["placement"]
    return "other"


def _tracked_changes_signature(doc) -> tuple:
    """Stable semantic signature used to prove conversion did not alter unrelated redlines."""
    rows = []
    for record in _redline_ranges(doc):
        cursor = record["text"].createTextCursorByRange(record["start"])
        cursor.gotoRange(record["end"], True)
        redline = record["redline"]
        rows.append(
            (
                _redline_property(redline, "RedlineIdentifier"),
                _redline_property(redline, "RedlineType"),
                _redline_property(redline, "RedlineAuthor"),
                _redline_property(redline, "RedlineComment"),
                _redline_property(redline, "RedlineDescription"),
                _redline_container_label(doc, record["start"]),
                cursor.getString(),
            )
        )
    return tuple(sorted(rows))


def _suspend_record_changes(doc) -> bool:
    """Disable recording for one atomic Callosum conversion; return the original state."""
    try:
        enabled = bool(doc.RecordChanges)
    except Exception as exc:
        raise RuntimeError(
            "Writer did not expose the Track Changes recording state; the document was not changed."
        ) from exc
    if enabled:
        try:
            doc.RecordChanges = False
        except Exception as exc:
            raise RuntimeError("Writer would not pause Track Changes; the document was not changed.") from exc
        if bool(doc.RecordChanges):
            raise RuntimeError("Writer would not pause Track Changes; the document was not changed.")
    return enabled


def _restore_record_changes(doc, enabled: bool) -> None:
    if not enabled:
        return
    try:
        doc.RecordChanges = True
    except Exception as exc:
        raise RuntimeError("Writer did not restore Track Changes after citation conversion.") from exc
    if not bool(doc.RecordChanges):
        raise RuntimeError("Writer did not restore Track Changes after citation conversion.")


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
    try:
        _section_bibliographies, damaged_section_bibliographies = section_bibliography_records(doc)
    except ValueError as exc:
        return str(exc)
    if damaged_section_bibliographies:
        return "Repair damaged section bibliography bookmarks before converting citation placement."

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
    return _tracked_change_conversion_error(doc, fields)


def _conversion_user_props(doc) -> dict[str, str | None]:
    return {name: _effective_user_prop(doc, name) for name in _CONVERSION_PREFS}


def _conversion_state_cursor(doc):
    """Choose a bounded main-text point outside every managed TextContent range/anchor."""
    text = doc.getText()
    occupied = []
    for name in doc.getBookmarks().getElementNames():
        anchor = doc.getBookmarks().getByName(name).getAnchor()
        if _range_belongs_to_text(text, anchor):
            occupied.append((anchor.getStart(), anchor.getEnd()))
    for name in doc.getReferenceMarks().getElementNames():
        if isinstance(name, str) and name.startswith(CONVERSION_STATE_PREFIX + " "):
            continue
        anchor = doc.getReferenceMarks().getByName(name).getAnchor()
        if _range_belongs_to_text(text, anchor):
            occupied.append((anchor.getStart(), anchor.getEnd()))
    for note in _note_containers(doc):
        anchor = note["_note"].getAnchor()
        occupied.append((anchor.getStart(), anchor.getEnd()))

    cursor = text.createTextCursorByRange(text.getStart())
    cursor.collapseToStart()
    for _offset in range(4097):
        if not any(
            _ordered_ranges_overlap(text.compareRegionStarts, cursor, cursor, start, end) for start, end in occupied
        ):
            return cursor
        if not cursor.goRight(1, False):
            break
    raise RuntimeError("Writer has no safe bounded main-text position for Callosum conversion state.")


def _replace_conversion_state(doc, values: dict[str, str | None]) -> None:
    """Replace the zero-width state mark; Writer natively includes the change in its current Undo context."""
    text = doc.getText()
    cursor = _conversion_state_cursor(doc)
    for mark in _conversion_state_marks(doc):
        mark.getAnchor().getText().removeTextContent(mark)
    marker = doc.createInstance("com.sun.star.text.ReferenceMark")
    marker.Name = _conversion_state_name(values)
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
                _mark_hyperlink_url(field["_mark"]),
            )
            for field in fields
        ),
        tuple(note.getString() for note in _collection_items(doc.getFootnotes())),
        tuple(note.getString() for note in _collection_items(doc.getEndnotes())),
        _managed_bibliographies_signature(doc),
        tuple(_conversion_user_props(doc).items()),
        tuple(mark.Name for mark in _conversion_state_marks(doc)),
        _tracked_changes_signature(doc),
    )


def _conversion_snapshot_differences(before: tuple, after: tuple) -> str:
    labels = (
        "main text",
        "citation fields",
        "footnotes",
        "endnotes",
        "bibliographies",
        "preferences",
        "state mark",
        "tracked changes",
    )
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
            journal_abbreviation_mode=journal_abbreviation_mode(doc),
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
    section_bibliographies, damaged_section_bibliographies = section_bibliography_records(doc)
    if damaged_section_bibliographies:
        raise ValueError("Repair damaged section bibliography bookmarks before converting citation placement.")
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
    bibliography_entry_ids = response.get("bibliography_entry_ids", [])
    if len(bibliography_entry_ids) != len(bibliography_entries):
        bibliography_entry_ids = [[] for _entry in bibliography_entries]
    bibliography_entry_links = normalize_bibliography_links(
        bibliography_entries,
        response.get("bibliography_links", []),
    )
    bibliography_entries, bibliography_entry_ids, bibliography_entry_links, bibliography_entry_categories = (
        categorize_bibliography_entries(
            bibliography_entries,
            bibliography_entry_ids,
            bibliography_entry_links,
            bibliography_categories(doc),
            bibliography_category_order(doc),
        )
    )
    external_links_enabled = bibliography_external_links_enabled(doc)
    write_bibliography = bib_auto_enabled(doc)
    section_plans = (
        _section_bibliography_plans(
            doc,
            fields,
            bibliography_entries,
            bibliography_entry_ids,
            bibliography_entry_links,
            bibliography_entry_categories,
            external_links_enabled,
        )
        if write_bibliography
        else []
    )
    incompatible_sections = [
        section["id"]
        for section in section_plans
        if not _bibliography_in_place_compatible(
            doc,
            section["entries"],
            section["entry_categories"],
            section["start"],
            section["end"],
        )
    ]
    if incompatible_sections:
        raise ValueError(
            "Remove or refresh empty section bibliographies before converting citation placement; "
            "Writer cannot preserve their boundaries through one-step Undo."
        )
    before_snapshot = _conversion_snapshot(doc)
    before_state_key = _conversion_state_key(doc)
    before_bibliography = before_snapshot[4][0]
    before_redlines = before_snapshot[7]
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
    tracking_was_enabled = _suspend_record_changes(doc)
    transaction_scope = contextlib.ExitStack()
    transaction_scope.enter_context(suspend_document_observation(doc))
    try:
        undo.enterUndoContext("Convert Callosum citation placement")
    except Exception:
        transaction_scope.close()
        _restore_record_changes(doc, tracking_was_enabled)
        raise
    try:
        _replace_conversion_state(doc, after_props)
        for name, citation_id in reversed(relocation_plan):
            _relocate_mark(doc, name, rendered[citation_id], target_placement)
        if write_bibliography:
            if _bibliography_in_place_compatible(
                doc,
                bibliography_entries,
                bibliography_entry_categories,
                BIB_BOOKMARK,
                BIB_BOOKMARK_END,
            ):
                _rewrite_bibliography_in_place(
                    doc,
                    bibliography_entries,
                    bibliography_entry_ids,
                    bibliography_entry_links,
                    bibliography_entry_categories,
                    external_links_enabled,
                )
            else:
                _write_bibliography(
                    doc,
                    bibliography_entries,
                    bibliography_entry_ids,
                    bibliography_entry_links,
                    bibliography_entry_categories,
                    external_links_enabled,
                )
            for section in section_plans:
                _rewrite_bibliography_in_place(
                    doc,
                    section["entries"],
                    section["entry_ids"],
                    section["entry_links"],
                    section["entry_categories"],
                    section["external_links"],
                    start_name=section["start"],
                    end_name=section["end"],
                    manage_targets=False,
                )
        available_ids = {
            str(item_id)
            for ids in bibliography_entry_ids
            for item_id in ids
            if write_bibliography or doc.getBookmarks().hasByName(bibliography_entry_bookmark(item_id) or "\0")
        }
        converted_fields = scan_citations_in_order(doc)
        converted_links = desired_citation_links(
            converted_fields,
            available_ids,
            bibliography_links_enabled(doc),
        )
        for field in converted_fields:
            _set_mark_hyperlink(field["_mark"], converted_links[field["_mark"].Name])

        # A document observer loaded through LibreOffice's installed extension can run from a separate Python
        # module instance, outside this module's in-memory suppression map. Reassert the committed current-state
        # overlay after every structural edit so that callback cannot leave a successful conversion marked dirty.
        _replace_conversion_state(doc, after_props)
        converted = converted_fields
        expected_indexes = list(range(1, len(fields) + 1)) if target_placement in NOTE_PLACEMENTS else [0] * len(fields)
        verification_failures = []
        if [field["_mark"].Name for field in converted] != expected_names:
            verification_failures.append("citation identities")
        if [field["placement"] for field in converted] != [target_placement] * len(fields):
            verification_failures.append("citation placements")
        if [field["noteIndex"] for field in converted] != expected_indexes:
            verification_failures.append("note order")
        if any(field["_mark"].getAnchor().getString() != rendered[field["citationID"]] for field in converted):
            verification_failures.append("rendered citation text")
        actual_props = _conversion_user_props(doc)
        if actual_props != after_props:
            mismatched_props = ", ".join(
                f"{name}={actual_props.get(name)!r} (expected {after_props.get(name)!r})"
                for name in _CONVERSION_PREFS
                if actual_props.get(name) != after_props.get(name)
            )
            verification_failures.append(f"document preferences ({mismatched_props})")
        if write_bibliography and not bibliography_render_is_current(
            doc,
            bibliography_entries,
            bibliography_entry_categories,
        ):
            verification_failures.append("bibliography")
        if write_bibliography and not bibliography_external_links_are_current(
            doc,
            bibliography_entries,
            bibliography_entry_links,
            external_links_enabled,
            bibliography_entry_categories,
        ):
            verification_failures.append("bibliography DOI/URL links")
        if write_bibliography and _section_bibliography_plans(
            doc,
            converted,
            bibliography_entries,
            bibliography_entry_ids,
            bibliography_entry_links,
            bibliography_entry_categories,
            external_links_enabled,
        ):
            verification_failures.append("section bibliographies")
        if _tracked_changes_signature(doc) != before_redlines:
            verification_failures.append("tracked changes")
        if verification_failures:
            raise RuntimeError("Post-conversion verification failed: " + ", ".join(verification_failures) + ".")
        _restore_record_changes(doc, tracking_was_enabled)
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
        finally:
            _restore_record_changes(doc, tracking_was_enabled)
            transaction_scope.close()
        rollback_snapshot = _conversion_snapshot(doc)
        if rollback_snapshot != before_snapshot:
            differences = _conversion_snapshot_differences(before_snapshot, rollback_snapshot)
            raise RuntimeError(
                "Citation conversion failed and automatic rollback did not fully restore the document. "
                f"Close without saving and reopen it. Unrestored: {differences}."
            ) from exc
        raise
    else:
        try:
            undo.leaveUndoContext()
        finally:
            transaction_scope.close()
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
        "tracked_changes_preserved": len(before_redlines),
        "section_bibliographies": len(section_bibliographies),
    }


def flatten(doc) -> int:
    """Convert live fields → static text: remove every CALLOSUM ReferenceMark + all managed bibliography bookmarks.

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
    managed_bookmarks = [BIB_BOOKMARK, BIB_BOOKMARK_END]
    managed_bookmarks.extend(
        name for name in bookmarks.getElementNames() if decode_section_bibliography_bookmark(name) is not None
    )
    for bookmark_name in managed_bookmarks:
        current = doc.getBookmarks()
        if current.hasByName(bookmark_name):
            text.removeTextContent(current.getByName(bookmark_name))  # zero-width bookmark only; bib text stays
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


def _choose_citation_source(
    choices: list[dict[str, str]],
    *,
    title: str,
    prompt: str,
    action_label: str,
) -> dict[str, str] | None:
    """Show a bounded single-select source list; return the chosen source or None when cancelled."""
    if not choices:
        return None
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from a11y import focus_first, set_tab_order

    smgr = _component_ctx().ServiceManager
    ctx = _component_ctx()
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 360, 174, title
    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height, label.Label = 6, 6, 348, 24, prompt
    label.MultiLine = True
    label.TabIndex = 0
    label.Tabstop = False
    dm.insertByName("lbl", label)
    source_list = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    source_list.PositionX, source_list.PositionY, source_list.Width, source_list.Height = 6, 34, 348, 108
    source_list.Dropdown = False
    source_list.MultiSelection = False
    source_list.StringItemList = tuple(choice["row"] for choice in choices)
    source_list.TabIndex = 1
    dm.insertByName("sources", source_list)
    ok = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.PositionX, ok.PositionY, ok.Width, ok.Height, ok.Label, ok.PushButtonType = (
        250,
        150,
        56,
        16,
        action_label,
        1,
    )
    dm.insertByName("ok", ok)
    cancel = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.PositionX, cancel.PositionY, cancel.Width, cancel.Height, cancel.Label, cancel.PushButtonType = (
        310,
        150,
        44,
        16,
        "Cancel",
        2,
    )
    dm.insertByName("cancel", cancel)
    set_tab_order(dm, ["ok", "cancel"], start=2)
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    control = dialog.getControl("sources")
    control.selectItemPos(0, True)
    focus_first(dialog, "sources")
    result = dialog.execute()
    position = control.getSelectedItemPos() if result == 1 else -1
    dialog.dispose()
    return choices[position] if 0 <= position < len(choices) else None


def go_to_bibliography_item(doc, item_id: str) -> bool:
    """Move the Writer view cursor to one stable full-bibliography target, if it currently exists."""
    target_name = bibliography_entry_bookmark(item_id)
    bookmarks = doc.getBookmarks()
    if target_name is None or not bookmarks.hasByName(target_name):
        return False
    try:
        target = bookmarks.getByName(target_name).getAnchor().getStart()
        doc.getCurrentController().getViewCursor().gotoRange(target, False)
    except Exception:
        return False
    return True


def go_to_bibliography_entry_interactive(doc, _base: str) -> None:
    """Jump from the citation at the cursor to a selected source's deterministic full-bibliography target."""
    field = mark_at_cursor(doc)
    if field is None:
        _msgbox("Place your cursor inside a citation to go to its bibliography entry.")
        return
    all_choices = citation_source_choices(field["items"])
    bookmark_names = set(doc.getBookmarks().getElementNames())
    available_ids = {
        choice["item_id"] for choice in all_choices if bibliography_entry_bookmark(choice["item_id"]) in bookmark_names
    }
    choices = citation_source_choices(field["items"], available_ids)
    if not choices:
        _msgbox(
            "No full-bibliography entry is available for this citation. "
            "Build or refresh the full bibliography first; excluded works have no entry."
        )
        return
    choice = choices[0]
    if len(all_choices) > 1:
        choice = _choose_citation_source(
            choices,
            title="Go to bibliography entry",
            prompt="Choose a cited source that is present in the full bibliography.",
            action_label="Go",
        )
        if choice is None:
            return
    if not go_to_bibliography_item(doc, choice["item_id"]):
        _msgbox("That bibliography entry is no longer available. Refresh the bibliography and try again.")


def open_in_callosum(doc, base: str) -> None:
    """Open a selected cited work in the user's configured local Callosum app."""
    field = mark_at_cursor(doc)
    if field is None:
        _msgbox("Place your cursor inside a citation to open it in callosum.")
        return
    choices = citation_source_choices(field["items"])
    if not choices:
        _msgbox("Could not determine which paper this citation refers to.")
        return
    choice = choices[0]
    if len(choices) > 1:
        choice = _choose_citation_source(
            choices,
            title="Open cited work in callosum",
            prompt="Choose which source in this grouped citation to open.",
            action_label="Open",
        )
        if choice is None:
            return
    webbrowser.open(f"{base}/?open_paper={choice['paper_id']}")


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
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from a11y import focus_first, labeled_field, set_tab_order

    smgr = _component_ctx().ServiceManager
    ctx = _component_ctx()
    dialog_model = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dialog_model.Width, dialog_model.Height, dialog_model.Title = 200, 70, title
    edit = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
    edit.PositionX, edit.PositionY, edit.Width, edit.Height, edit.Text = 6, 28, 188, 14, default
    labeled_field(dialog_model, "lbl", "edit", 6, 6, 188, 20, prompt, edit, 0)
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
    set_tab_order(dialog_model, ["ok", "cancel"], start=2)
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dialog_model)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    focus_first(dialog, "edit")
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
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from a11y import focus_first, labeled_field, set_tab_order

    smgr = _component_ctx().ServiceManager
    ctx = _component_ctx()
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 220, 72, title
    choices = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    choices.PositionX, choices.PositionY, choices.Width, choices.Height = 6, 26, 208, 28
    choices.Dropdown = True
    choices.StringItemList = tuple(option[0] for option in options)
    labeled_field(dm, "lbl", "choices", 6, 6, 208, 18, prompt, choices, 0)
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
    set_tab_order(dm, ["ok", "cancel"], start=2)
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    control = dialog.getControl("choices")
    selected = next((index for index, option in enumerate(options) if option[1] == current_value), 0)
    control.selectItemPos(selected, True)
    focus_first(dialog, "choices")
    result = dialog.execute()
    position = control.getSelectedItemPos() if result == 1 else -1
    dialog.dispose()
    return options[position][1] if 0 <= position < len(options) else None


def _confirm_box(message: str, title: str = "callosum") -> bool:
    """Ask an explicit yes/no question with No as the safe default."""
    smgr = _component_ctx().ServiceManager
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", _component_ctx())
    # QUERYBOX=4; BUTTONS_YES_NO=3; DEFAULT_BUTTON_2=512; MessageBoxResults.YES=2.
    box = toolkit.createMessageBox(None, 4, 3 | 512, title, message)
    result = box.execute()
    box.dispose()
    return result == 2


def _section_bibliographies_dialog(
    summaries: list[dict],
    damaged_count: int,
) -> tuple[str, str | None] | None:
    """Return ``(go|remove|remove_all, id)`` from the bounded section-bibliography manager."""
    import sys

    import unohelper
    from com.sun.star.awt import XActionListener

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from a11y import focus_first, set_tab_order

    if not summaries:
        return None
    ctx = _component_ctx()
    smgr = ctx.ServiceManager

    class _ActionListener(unohelper.Base, XActionListener):
        def __init__(self, callback):
            self._callback = callback

        def actionPerformed(self, event):
            self._callback()

        def disposing(self, event):
            pass

    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 420, 186, "Section bibliographies"
    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height = 6, 6, 408, 24
    noun = "bibliography" if len(summaries) == 1 else "bibliographies"
    label.Label = f"{len(summaries)} live section {noun}." + (
        f" {damaged_count} damaged block(s) are not listed; use Document diagnostics."
        if damaged_count
        else " Select one to jump to or remove."
    )
    label.MultiLine = True
    label.TabIndex = 0
    label.Tabstop = False
    dm.insertByName("label", label)
    section_list = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    section_list.PositionX, section_list.PositionY, section_list.Width, section_list.Height = 6, 34, 408, 116
    section_list.MultiSelection = False
    section_list.StringItemList = tuple(summary["row"] for summary in summaries)
    section_list.TabIndex = 1
    dm.insertByName("sections", section_list)

    for name, x, width, text in (
        ("goto", 6, 60, "Go to"),
        ("remove", 70, 92, "Remove selected"),
        ("remove_all", 166, 78, "Remove all"),
    ):
        button = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
        button.PositionX, button.PositionY, button.Width, button.Height, button.Label = x, 160, width, 18, text
        dm.insertByName(name, button)
    close = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    close.PositionX, close.PositionY, close.Width, close.Height = 340, 160, 74, 18
    close.Label, close.PushButtonType = "Close", 2
    dm.insertByName("close", close)
    set_tab_order(dm, ["goto", "remove", "remove_all", "close"], start=2)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)
    list_control = dialog.getControl("sections")
    list_control.selectItemPos(0, True)
    focus_first(dialog, "sections")
    state = {"action": None, "identifier": None}

    def choose(action: str) -> None:
        position = list_control.getSelectedItemPos()
        if action != "remove_all" and not 0 <= position < len(summaries):
            _msgbox("Select one section bibliography first.", "Section bibliographies")
            return
        state["action"] = action
        state["identifier"] = summaries[position]["id"] if action != "remove_all" else None
        dialog.endExecute()

    listeners = (
        _ActionListener(lambda: choose("go")),
        _ActionListener(lambda: choose("remove")),
        _ActionListener(lambda: choose("remove_all")),
    )
    for control_name, listener in zip(("goto", "remove", "remove_all"), listeners, strict=True):
        dialog.getControl(control_name).addActionListener(listener)
    dialog.execute()
    dialog.dispose()
    return (str(state["action"]), state["identifier"]) if state["action"] in {"go", "remove", "remove_all"} else None


_SUGGEST_CAVEAT = "Pick a paper to cite for the selected text — ranked by relevance; verify the source. You decide."

# inc 460: the SAME thresholds invariant #1 already uses (app/backend/summarization/verification.py's
# VerificationConfig defaults: retrieval_threshold=0.7, support_threshold=0.55) -- reused here, not
# reinvented, so "weak evidence" means the same thing everywhere in callosum.
_SUGGEST_RETRIEVAL_THRESHOLD = 0.7
_SUGGEST_SUPPORT_THRESHOLD = 0.55


def _is_weak_evidence(match_score, stance: dict | None) -> bool:
    """True when neither the retrieval match nor the stance's support probability clears its threshold --
    mirrors VerificationConfig's own "unverified" tier (neither signal strong), never a new bar."""
    try:
        score = float(match_score)
    except (TypeError, ValueError):
        score = 0.0
    support = 0.0
    if isinstance(stance, dict):
        probs = stance.get("probs")
        if isinstance(probs, dict):
            try:
                support = float(probs.get("support") or 0.0)
            except (TypeError, ValueError):
                support = 0.0
    return not (score >= _SUGGEST_RETRIEVAL_THRESHOLD or support >= _SUGGEST_SUPPORT_THRESHOLD)


def _stance_breakdown_text(stance: dict | None) -> str:
    """The full 3-way support/contrast/mention breakdown (roadmap #17: "compare supporting, contrasting, and
    merely mentioning evidence") -- not just the single winning label the compact row already shows."""
    if not isinstance(stance, dict):
        return "No stance signal for this passage."
    probs = stance.get("probs") if isinstance(stance.get("probs"), dict) else {}

    def pct(key: str) -> int:
        try:
            return round(float(probs.get(key) or 0.0) * 100)
        except (TypeError, ValueError):
            return 0

    return f"Stance: {pct('support')}% support · {pct('mention')}% mention · {pct('contrast')}% contrast"


def _why_retrieved_text(match_score) -> str:
    """Roadmap #17: "explain why a source was retrieved" -- names the mechanism, not just a bare number."""
    try:
        pct = round(float(match_score) * 100)
    except (TypeError, ValueError):
        pct = 0
    return f"Retrieved by local semantic similarity — approximately {pct}% match to your selected text."


def _auto_locator(item: dict) -> str | None:
    """A page/page-range locator string pre-filled from the suggestion's own page_start/page_end -- the
    "insert automatically" half of roadmap #17's locator bullet; the "confirmation" half is that this is only
    ever a pre-fill, editable/removable in the Details dialog before the one Insert click that commits it."""
    start, end = item.get("page_start"), item.get("page_end")
    if not start:
        return None
    if end and end != start:
        return f"{start}-{end}"
    return str(start)


def _evidence_fields(item: dict) -> dict:
    """The compact evidence-audit locator persisted per inserted item (see `_ITEM_DEFAULTS`) -- chunk_id/page
    plus a hard-truncated snippet, never the full quote."""
    snippet = " ".join(str(item.get("quote") or "").split())
    if len(snippet) > EVIDENCE_SNIPPET_MAX:
        snippet = snippet[:EVIDENCE_SNIPPET_MAX].rstrip() + "…"
    return {
        "evidence_chunk_id": item.get("chunk_id"),
        "evidence_page_start": item.get("page_start"),
        "evidence_page_end": item.get("page_end"),
        "evidence_snippet": snippet or None,
    }


def _suggestion_detail_dialog(base: str, item: dict, current_locator: str | None) -> tuple[bool, str | None]:
    """A modal showing everything roadmap #17 wants surfaced for ONE selected library suggestion: the full
    quote, page/section, the 3-way stance breakdown, a weak-evidence warning, an editable pre-filled locator,
    and an Open-in-PDF button. Mirrors `composer.py::_edit_item_options`'s exact "returns on OK, discard on
    Cancel" contract. Returns ``(changed, locator)`` -- `changed` is True only on OK, so the caller can leave
    any existing override untouched on Cancel/close."""
    import sys

    import unohelper
    from com.sun.star.awt import XActionListener

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from a11y import focus_first, labeled_field, set_tab_order

    ctx = _component_ctx()
    smgr = ctx.ServiceManager
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 360, 258, "Suggestion details"

    def _label(name, x, y, w, h, text):
        lbl = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        lbl.PositionX, lbl.PositionY, lbl.Width, lbl.Height, lbl.Label = x, y, w, h, text
        lbl.MultiLine = h > 14
        lbl.Tabstop = False
        dm.insertByName(name, lbl)

    author = str(item.get("author") or "").strip()
    year = item.get("year")
    who = " ".join(p for p in (author, str(year) if year else "") if p) or str(item.get("title") or "")
    _label("subtitle", 6, 6, 348, 12, who[:80])

    quote_box = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    quote_box.PositionX, quote_box.PositionY, quote_box.Width, quote_box.Height = 6, 30, 348, 50
    quote_box.MultiLine, quote_box.ReadOnly, quote_box.Tabstop = True, True, False
    quote_box.Text = str(item.get("quote") or "")
    labeled_field(dm, "quote_lbl", "quote", 6, 20, 60, 9, "Quote:", quote_box, 0)

    page_start, page_end = item.get("page_start"), item.get("page_end")
    page_text = f"Page {page_start}" if page_start else "Page unknown"
    if page_end and page_end != page_start:
        page_text = f"Pages {page_start}–{page_end}"
    _label("page", 6, 84, 348, 12, page_text)

    _label("stance", 6, 100, 348, 12, _stance_breakdown_text(item.get("stance")))
    _label("why", 6, 116, 348, 22, _why_retrieved_text(item.get("match_score")))

    warning = (
        "⚠ Weak evidence — neither the match nor the stance strongly supports this passage. Verify before citing."
        if _is_weak_evidence(item.get("match_score"), item.get("stance"))
        else ""
    )
    _label("warning", 6, 140, 348, 22, warning)

    locator_edit = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    locator_edit.PositionX, locator_edit.PositionY, locator_edit.Width, locator_edit.Height = 100, 164, 254, 14
    locator_edit.Text = current_locator if current_locator is not None else (_auto_locator(item) or "")
    labeled_field(dm, "locator_lbl", "locator", 6, 166, 90, 12, "Page locator:", locator_edit, 2)

    open_pdf_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    open_pdf_btn.PositionX, open_pdf_btn.PositionY, open_pdf_btn.Width, open_pdf_btn.Height = 6, 186, 100, 18
    open_pdf_btn.Label = "Open in PDF"
    dm.insertByName("open_pdf", open_pdf_btn)

    ok_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok_btn.PositionX, ok_btn.PositionY, ok_btn.Width, ok_btn.Height = 202, 232, 74, 18
    ok_btn.Label, ok_btn.PushButtonType = "OK", 1
    dm.insertByName("ok", ok_btn)

    cancel_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel_btn.PositionX, cancel_btn.PositionY, cancel_btn.Width, cancel_btn.Height = 280, 232, 74, 18
    cancel_btn.Label, cancel_btn.PushButtonType = "Cancel", 2
    dm.insertByName("cancel", cancel_btn)

    set_tab_order(dm, ["open_pdf", "ok", "cancel"], start=4)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)

    locator_ctrl = dialog.getControl("locator")

    class _OpenPdfListener(unohelper.Base, XActionListener):
        def actionPerformed(self, event):
            url = f"{base}/?open_paper={item.get('paper_id')}"
            if page_start:
                precision = item.get("coordinate_precision") or "region"
                url += f"&page={page_start}&precision={precision}"
            webbrowser.open(url)

        def disposing(self, event):
            pass

    dialog.getControl("open_pdf").addActionListener(_OpenPdfListener())

    focus_first(dialog, "locator")
    result = dialog.execute()  # 1 == OK
    dialog.dispose()
    if result != 1:
        return False, None
    return True, (locator_ctrl.getModel().Text.strip() or None)


def _suggest_dialog(doc, base: str, text: str) -> list[tuple[str, dict, str | None]] | None:
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

    inc 460 (roadmap #17): the list is now multi-select (select several sources for the same sentence, inserted
    together as one grouped citation), and a "Details…" button — enabled only for a single selected in-library
    row — opens `_suggestion_detail_dialog` for the full quote/stance/why/weak-evidence-warning/locator/
    open-in-PDF. **v1 boundary**: a multi-select insert must be all-library or all-beyond, never mixed (a
    beyond-library pick needs its own `save_beyond_library_item` round-trip first) — checked after the dialog
    closes, not by disabling Insert live.

    inc 465 (backlog #30's last open piece): a "Save for later" button flags every currently-selected
    beyond-library row into the persistent, dismissible review queue (`save_beyond_library_item_for_later`) —
    a non-closing action, the same pattern as `Details…`, so it can be used before deciding whether to Insert
    or Cancel.

    Returns a list of ``(kind, item, locator_override)`` for every picked row — `kind` is ``"library"`` or
    ``"beyond"``, `locator_override` is whatever was set via Details (or None, meaning "use the auto pre-fill")
    — or None if nothing was picked / the selection was invalid (mixed kinds)."""
    import sys

    import unohelper
    from com.sun.star.awt import XActionListener, XItemListener

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from a11y import focus_first, labeled_field, set_tab_order

    ctx = _component_ctx()
    smgr = ctx.ServiceManager
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 360, 228, "Suggest citations"

    label = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.PositionX, label.PositionY, label.Width, label.Height = 6, 6, 348, 22
    label.Label = _SUGGEST_CAVEAT
    label.MultiLine = True
    label.Tabstop = False
    dm.insertByName("lbl", label)

    lst = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    lst.PositionX, lst.PositionY, lst.Width, lst.Height = 6, 40, 348, 100
    lst.Dropdown = False
    lst.MultiSelection = True
    labeled_field(dm, "list_lbl", "list", 6, 30, 100, 9, "Suggestions:", lst, 0)

    beyond_box = dm.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
    beyond_box.PositionX, beyond_box.PositionY, beyond_box.Width, beyond_box.Height = 6, 144, 320, 14
    beyond_box.Label, beyond_box.State = "Also search beyond my library", 0
    dm.insertByName("beyond", beyond_box)

    details_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    details_btn.PositionX, details_btn.PositionY, details_btn.Width, details_btn.Height = 6, 162, 100, 16
    details_btn.Label = "Details…"
    dm.insertByName("details", details_btn)

    save_later_btn = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    save_later_btn.PositionX, save_later_btn.PositionY, save_later_btn.Width, save_later_btn.Height = 112, 162, 110, 16
    save_later_btn.Label = "Save for later"
    dm.insertByName("saveLater", save_later_btn)

    ok = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.PositionX, ok.PositionY, ok.Width, ok.Height, ok.Label, ok.PushButtonType = 262, 200, 44, 16, "Insert", 1
    dm.insertByName("ok", ok)
    cancel = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.PositionX, cancel.PositionY, cancel.Width, cancel.Height, cancel.Label, cancel.PushButtonType = (
        310,
        200,
        44,
        16,
        "Cancel",
        2,
    )
    dm.insertByName("cancel", cancel)

    set_tab_order(dm, ["beyond", "details", "saveLater", "ok", "cancel"], start=2)

    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)

    list_ctrl = dialog.getControl("list")
    beyond_ctrl = dialog.getControl("beyond")
    # state["rows"]: list of (kind, item), parallel to the listbox's current rows.
    # state["locators"]: row position -> locator override set via Details (absent means "use the auto pre-fill").
    state = {"rows": [], "locators": {}}

    def refresh(include_beyond: bool) -> None:
        result = fetch_suggestions(base, text, include_beyond_library=include_beyond)
        parallel = [("library", s) for s in result["suggestions"]]
        parallel += [("beyond", b) for b in result["beyond_library_suggestions"]]
        rows = build_suggest_rows(result["suggestions"]) + build_beyond_suggest_rows(
            result["beyond_library_suggestions"]
        )
        state["rows"] = parallel
        state["locators"] = {}
        list_ctrl.getModel().StringItemList = tuple(rows)

    refresh(False)  # in-library results load immediately; beyond-library is opt-in only

    class _BeyondListener(unohelper.Base, XItemListener):
        def itemStateChanged(self, event):
            refresh(beyond_ctrl.getState() == 1)

        def disposing(self, event):
            pass

    class _DetailsListener(unohelper.Base, XActionListener):
        def actionPerformed(self, event):
            positions = list(list_ctrl.getSelectedItemsPos())
            if len(positions) != 1 or not (0 <= positions[0] < len(state["rows"])):
                _msgbox("Select exactly one in-library suggestion to see its details.")
                return
            pos = positions[0]
            kind, item = state["rows"][pos]
            if kind != "library":
                _msgbox("Details are only available for in-library suggestions (they carry a quote + stance).")
                return
            changed, locator = _suggestion_detail_dialog(base, item, state["locators"].get(pos))
            if changed:
                state["locators"][pos] = locator

        def disposing(self, event):
            pass

    class _SaveForLaterListener(unohelper.Base, XActionListener):
        """Backlog #30's last open piece (inc 465): flag selected beyond-library rows for later without closing
        the dialog or inserting anything — the exact non-closing-button pattern `Details…` already established.
        Library rows are skipped (nothing to save — they're already in the library); a purely-library selection
        gets an explanatory message rather than silently doing nothing."""

        def actionPerformed(self, event):
            positions = list(list_ctrl.getSelectedItemsPos())
            picks = [state["rows"][pos] for pos in positions if 0 <= pos < len(state["rows"])]
            beyond_picks = [item for kind, item in picks if kind == "beyond"]
            if not picks:
                _msgbox("Select one or more beyond-library suggestions to save for later.")
                return
            if not beyond_picks:
                _msgbox(
                    "Only beyond-library suggestions can be saved for later — in-library results are already in your library."
                )
                return
            for item in beyond_picks:
                save_beyond_library_item_for_later(base, item, text)
            _msgbox(
                f"Saved {len(beyond_picks)} for later — review them anytime from Discover → Search → "
                "Saved for later in the callosum app."
            )

        def disposing(self, event):
            pass

    beyond_ctrl.addItemListener(_BeyondListener())
    dialog.getControl("details").addActionListener(_DetailsListener())
    dialog.getControl("saveLater").addActionListener(_SaveForLaterListener())

    focus_first(dialog, "list")
    result_code = dialog.execute()  # 1 == Insert
    positions = list(list_ctrl.getSelectedItemsPos()) if result_code == 1 else []
    dialog.dispose()
    picks = [(*state["rows"][pos], state["locators"].get(pos)) for pos in positions if 0 <= pos < len(state["rows"])]
    if not picks:
        return None
    if len({kind for kind, _item, _locator in picks}) > 1:
        _msgbox("Select sources of only one kind (library, or beyond-library) to insert together.")
        return None
    return picks


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
    opt-in checkbox (backlog #30) — let the user pick one OR SEVERAL (inc 460, roadmap #17), and insert them.

    Returns the new mark's `rnd` tag, or None if nothing was inserted (no text / cancelled / nothing picked).
    The suggestion + stance signal, and the beyond-library search + reasons, are all the backend's (inc 156,
    271/272); this only presents the evidence and inserts the chosen cite(s). A beyond-library pick is added to
    the library first (`save_beyond_library_item`, the same write path the web app's own "Add to library"
    button uses), then cited — a real user might not have anything relevant in-library yet, so this no longer
    short-circuits on an empty in-library list before the user gets a chance to opt into searching further.

    Multiple picks become one grouped citation (the same `insert_citation_items` mechanism the composer already
    uses for multi-source citations). Each in-library item carries a compact evidence-audit locator
    (`_evidence_fields`) plus a page locator — either edited via Details, or auto-pre-filled from the matched
    passage's own page (`_auto_locator`) — never silently inserted without being visible somewhere first.
    """
    text = current_query_text(doc)
    if not text:
        _msgbox("Select a sentence (or place the cursor in one) to suggest citations for.")
        return None
    picks = _suggest_dialog(doc, base, text)
    if not picks:
        return None
    items = []
    for kind, item, locator_override in picks:
        paper_id = save_beyond_library_item(base, item) if kind == "beyond" else item.get("paper_id")
        entry = {"paper_id": paper_id}
        locator = locator_override if locator_override is not None else _auto_locator(item)
        if locator:
            entry["locator"] = locator
            entry["label"] = "page"
        if kind == "library":
            entry.update(_evidence_fields(item))
        items.append(entry)
    return insert_citation_items(doc, items, base, cursor=_insertion_cursor_at_end(doc))


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
        f"{chosen_style}. Ambiguous notes, user prose, mixed placement, and tracked changes that overlap managed "
        "citation or bibliography content will be refused; unrelated tracked changes will be preserved."
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
            f"Preserved {result['tracked_changes_preserved']} tracked change(s).\n"
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
        f"{result['target_placement']} placement. Preserved {result['tracked_changes_preserved']} tracked change(s). "
        "Use Writer Undo to restore the original document."
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


def insert_section_bibliography_interactive(doc, base: str) -> None:
    """Insert a live bibliography at the caret containing only works cited in its heading subtree."""
    identifier = insert_section_bibliography(doc, base)
    if identifier is not None:
        summaries, _damaged = section_bibliography_summaries(doc)
        summary = next((item for item in summaries if item["id"] == identifier), None)
        detail = summary["row"] if summary is not None else "current section"
        _msgbox(
            f"Section bibliography inserted: {detail}. "
            "Refresh bibliography updates it together with the full bibliography."
        )


def remove_section_bibliography_interactive(doc, base: str) -> None:
    """Remove the live bibliography owned by the caret's heading subtree."""
    summaries, _damaged = section_bibliography_summaries(doc)
    by_id = {summary["id"]: summary for summary in summaries}
    identifier = remove_section_bibliography(doc, base)
    if identifier is not None:
        label = by_id.get(identifier, {}).get("label", "current section")
        _msgbox(f"Section bibliography for “{label}” removed; citations and the full bibliography were not changed.")


def manage_section_bibliographies_interactive(doc, base: str) -> None:
    """List, jump to, remove, or atomically remove all complete section bibliographies."""
    while True:
        summaries, damaged = section_bibliography_summaries(doc)
        if not summaries:
            message = "No complete Callosum section bibliographies were found."
            if damaged:
                message += (
                    f" {len(damaged)} damaged block(s) remain; use Document diagnostics before inserting replacements."
                )
            _msgbox(message, "Section bibliographies")
            return
        choice = _section_bibliographies_dialog(summaries, len(damaged))
        if choice is None:
            return
        action, identifier = choice
        if action == "go":
            if identifier is None or not go_to_section_bibliography(doc, identifier):
                _msgbox("That section bibliography is no longer available.", "Section bibliographies")
            return
        if action == "remove":
            summary = next((item for item in summaries if item["id"] == identifier), None)
            if summary is None:
                _msgbox("That section bibliography is no longer available.", "Section bibliographies")
                continue
            remove_section_bibliography_by_id(doc, summary["id"], base)
            _msgbox(
                f"Section bibliography for “{summary['label']}” removed. "
                "Citations and the full bibliography were not changed.",
                "Section bibliographies",
            )
            continue
        if damaged:
            _msgbox(
                "Remove all is unavailable while damaged section-bibliography bookmarks remain. "
                "Run Document diagnostics first.",
                "Section bibliographies",
            )
            continue
        if not _confirm_box(
            f"Remove all {len(summaries)} section bibliographies in one Writer Undo step?\n\n"
            "Citations and the full bibliography will not change.",
            "Remove all section bibliographies",
        ):
            continue
        removed = remove_all_section_bibliographies(doc, base)
        _msgbox(
            f"Removed {len(removed)} section bibliographies. Citations and the full bibliography were not changed.",
            "Section bibliographies",
        )
        return


def set_bibliography_heading_interactive(doc, base: str) -> None:
    """Prompt for the document's bibliography heading; blank restores the default."""
    try:
        current = bibliography_heading(doc)
    except ValueError:
        current = BIB_HEADING
    value = _input_box(
        doc,
        "Bibliography heading",
        f"Heading ({BIB_HEADING_MAX} characters maximum; blank restores {BIB_HEADING}):",
        current,
    )
    if value is None:
        return
    heading = set_bibliography_heading(doc, value, base)
    _msgbox(f'Bibliography heading is now "{heading}".')


def set_journal_abbreviations_interactive(doc, base: str) -> None:
    """Choose the document's journal-title source, then show citeproc-aware coverage feedback."""
    chosen = _choice_box(
        doc,
        "Journal abbreviations",
        "Journal titles when the CSL style requests a short form:",
        JOURNAL_ABBREVIATION_OPTIONS,
        journal_abbreviation_mode(doc),
    )
    if chosen is None:
        return
    mode, summary = set_journal_abbreviation_mode(doc, chosen, base)
    label = next(label for label, value in JOURNAL_ABBREVIATION_OPTIONS if value == mode)
    _msgbox(f"{label}.\n\n{journal_abbreviation_feedback(summary)}", "Journal abbreviations")


def toggle_bibliography_links_interactive(doc, base: str) -> None:
    """Toggle internal navigation for citation clusters with exactly one bibliography entry."""
    was_enabled = bibliography_links_enabled(doc)
    enabled = set_bibliography_links(doc, not was_enabled, base)
    _msgbox(
        f"Citation-to-bibliography links: {'ON' if was_enabled else 'OFF'} → {'ON' if enabled else 'OFF'}."
        + (
            " Single-work citations now open their bibliography entry; grouped citations remain unlinked."
            if enabled
            else " Citation fields remain live; Callosum's internal links are removed and other hyperlinks are unchanged."
        )
    )


def toggle_bib_auto_interactive(doc, base: str) -> None:
    """Flip whether the bibliography auto-rebuilds on refresh (P0 phase 7) — citations still update either way;
    this only pauses/resumes the bibliography block itself."""
    was_enabled = bib_auto_enabled(doc)
    enabled = not was_enabled
    set_bib_auto(doc, enabled)
    _msgbox(
        f"Automatic bibliography rebuilding: {'ON' if was_enabled else 'OFF'} → {'ON' if enabled else 'OFF'}."
        + (
            ""
            if enabled
            else " Citations still update on refresh; the bibliography stays as-is until you turn this back on."
        )
    )


def toggle_bibliography_external_links_interactive(doc, base: str) -> None:
    """Toggle web links over visible DOI/URL text or a uniquely matched source title fallback."""
    was_enabled = bibliography_external_links_enabled(doc)
    enabled, link_count = set_bibliography_external_links(doc, not was_enabled, base)
    if enabled and link_count:
        detail = f" {link_count} bibliography link{'s are' if link_count != 1 else ' is'} now clickable."
    elif enabled:
        detail = " No safe DOI or URL could be matched to a visible title or identifier."
    else:
        detail = " Managed bibliography web links were removed; the rendered text is unchanged."
    _msgbox(f"Bibliography title/DOI links: {'ON' if was_enabled else 'OFF'} → {'ON' if enabled else 'OFF'}.{detail}")


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


# inc 462 (P2 item #21, backlog #33/#34): open-science statement insertion -- extends the CRediT statement's own
# "build in the web UI -> stage -> LibreOffice pulls & inserts" pattern above to 7 more author-asserted
# manuscript disclosures, generalized to a dict keyed by kind (POST/GET /statements/pending) instead of one bare
# slot, since several statements may be staged at once. Fixed vocabulary duplicated from the backend's own
# STATEMENT_KINDS -- the CSL_LOCATOR_LABELS precedent (this adapter runs under LibreOffice's own bundled Python,
# a separate process with no access to the backend's Python package).
STATEMENT_KIND_LABELS = {
    "data_availability": "Data availability",
    "code_availability": "Code availability",
    "preregistration": "Preregistration",
    "funding": "Funding",
    "conflict_of_interest": "Conflict of interest",
    "ethics": "Ethics",
    "ai_use": "AI use",
}
STATEMENT_PREVIEW_MAX = 60  # truncate a staged statement's text in the picker row


def statements_pending(base: str) -> dict[str, str]:
    """GET /statements/pending -- kind -> currently staged text (only kinds with non-empty staged text).
    {} on a malformed non-dict response, matching `search_library`'s own defensive convention."""
    data = _get_json(f"{base}/statements/pending")
    return data if isinstance(data, dict) else {}


def insert_staged_statement(doc, base: str = DEFAULT_BASE) -> None:
    """Insert whichever staged open-science statement the user picks (roadmap #21). Reuses the existing
    `_choice_box` dropdown picker unchanged -- no new dialog construction needed, unlike inc 461's multi-step
    "Insert evidence" flow, since this is a single pick from a short, already-labeled list. Plain static text —
    a disclosure statement is prose the author asserts, not a live citation field, so no ReferenceMark wrapper,
    matching `insert_statement`'s own CRediT precedent exactly."""
    staged = statements_pending(base)
    if not staged:
        _msgbox(
            "No open-science statements staged yet — in callosum open Work → Statements, build one, and click "
            '"Send to LibreOffice" first.'
        )
        return
    options = tuple(
        (f"{STATEMENT_KIND_LABELS.get(kind, kind)} — {text[:STATEMENT_PREVIEW_MAX]}", kind)
        for kind, text in staged.items()
    )
    chosen = _choice_box(doc, "Insert statement", "Choose which staged statement to insert:", options, options[0][1])
    if chosen is None:
        return
    doc.getText().insertString(_insertion_cursor(doc), staged[chosen] + "\n", False)


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
    "orphaned": [paper_id, ...], "bibliography": "ok" | "damaged" | "not_built" | "n/a", "preferences":
    {"bib_auto", "bibliography_links", "bibliography_external_links"}}``. ``preferences`` is a read-only
    surfacing of the three otherwise state-blind toggles below — this dialog is the one place a user can check
    their current ON/OFF state without side-effecting it by clicking a toggle command.
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
    section_bibliographies, damaged_section_bibliographies = section_bibliography_records(doc)
    citation_dirty, bibliography_dirty = dirty_state(doc)

    return {
        "malformed": malformed,
        "unsupported_version": unsupported,
        "duplicate_ids": duplicate_ids,
        "orphaned": orphaned,
        "bibliography": bib_state,
        "section_bibliographies": {
            "count": len(section_bibliographies),
            "damaged": damaged_section_bibliographies,
        },
        "refresh_pending": {
            "citations": citation_dirty,
            "bibliography": bibliography_dirty,
        },
        "preferences": {
            "bib_auto": bib_auto_enabled(doc),
            "bibliography_links": bibliography_links_enabled(doc),
            "bibliography_external_links": bibliography_external_links_enabled(doc),
        },
    }


def _diagnostics_issue_lines(report: dict) -> list[str]:
    """The mechanics-issue prose lines `diagnose_document`'s report renders to (P0 phase 9), factored out so the
    citation-integrity preflight (inc 459) can reuse the exact same wording rather than duplicating it."""
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
    section_report = report["section_bibliographies"]
    if section_report["damaged"]:
        lines.append(
            f"{len(section_report['damaged'])} section bibliography block(s) have missing scope/start/end markers. "
            "Remove their remaining Callosum bookmarks before inserting replacements."
        )
    return lines


def document_diagnostics_interactive(doc, base: str) -> None:
    report = diagnose_document(doc, base)
    lines = _diagnostics_issue_lines(report)
    issues_text = "\n\n".join(lines) if lines else "No issues found."

    prefs = report["preferences"]
    settings_text = "Current settings:\n" + "\n".join(
        f"- {label}: {'ON' if prefs[key] else 'OFF'}"
        for key, label in (
            ("bib_auto", "Automatic bibliography rebuilding"),
            ("bibliography_links", "Citation-to-bibliography links"),
            ("bibliography_external_links", "Bibliography title/DOI links"),
        )
    )
    _msgbox(f"{issues_text}\n\n{settings_text}", title="callosum — document diagnostics")


_RETRACTION_LABEL = {"retracted": "RETRACTED", "correction": "CORRECTION", "concern": "EXPRESSION OF CONCERN"}


def _paper_id_from_item(item: dict) -> str | None:
    """The ``"callosum-{paper_id}"`` item-id idiom, in one place (P1 item #12, backlog #33/#34) — new call
    sites should use this rather than copy-pasting the strip-the-prefix idiom a 4th time."""
    item_id = str(item.get("id") or "")
    return item_id[len("callosum-") :] if item_id.startswith("callosum-") else None


def _distinct_cited_paper_ids(doc, orphaned: set[str]) -> list[str]:
    """Every distinct, non-orphaned cited paper id in this document, in first-occurrence order (P2 items #19/
    #18, backlog #33/#34) — shared by `citation_integrity_preflight` and `citation_coverage_audit`, both of
    which need "which papers does this document actually cite right now" as their starting point. Untruncated;
    each caller applies its own cap."""
    ids: list[str] = []
    seen: set[str] = set()
    for name in doc.getReferenceMarks().getElementNames():
        if not (isinstance(name, str) and name.startswith(MARK_PREFIX + " ")):
            continue
        decoded = decode_mark_name(name)
        if decoded is None or decoded.get("unsupported"):
            continue
        for item in decoded["items"]:
            paper_id = _paper_id_from_item(item)
            if paper_id is None or paper_id in orphaned or paper_id in seen:
                continue
            seen.add(paper_id)
            ids.append(paper_id)
    return ids


MAX_INTEGRITY_PREFLIGHT_IDS = 100  # mirrors the backend's own POST /methods/retraction/check-selected cap --
# truncated client-side so a manuscript citing more than this still gets a partial re-check rather than one
# oversize request the backend would 422 in full (inc 459)


def citation_integrity_preflight(doc, base: str = DEFAULT_BASE) -> dict:
    """Pre-submission retraction re-check for exactly the papers cited in this document (backlog #33/#34, P2
    item #19 — a reuse-first slice: no new detector, just a fresh, scoped call to the same multi-source
    `detect_retraction()` the whole-library batch and every Meta-Reference audit already share).

    Folds `diagnose_document`'s existing read-only mechanics report (malformed/duplicate/orphaned marks,
    bibliography health) in unchanged, then re-checks retraction status for every distinct, non-orphaned cited
    paper id via ``POST /methods/retraction/check-selected``. This is a genuinely FRESH check right now, not the
    read-only cached ``GET /papers/{id}/retraction`` the "Citations in this document" panel already shows —
    that stored status could be stale if nothing has re-triggered a check since the paper was imported.

    Never mutates the document. Returns `diagnose_document`'s dict plus:
    ``{"retraction_checked": [{"paper_id", "status", "nature", "date", "notice_url", "sources"}, ...],
    "retraction_flagged": [same shape, status not in ("none", "unchecked")], "retraction_check_error": str |
    None}``. A backend/network failure on the retraction re-check is caught and surfaced as
    ``retraction_check_error`` rather than blocking the (already-computed, purely local) mechanics report.
    """
    report = diagnose_document(doc, base)
    orphaned = set(report["orphaned"])
    ids = _distinct_cited_paper_ids(doc, orphaned)[:MAX_INTEGRITY_PREFLIGHT_IDS]

    checked: list[dict] = []
    flagged: list[dict] = []
    error: str | None = None
    if ids:
        try:
            result = _post_json(f"{base}/methods/retraction/check-selected", {"paper_ids": [int(i) for i in ids]})
            checked = result.get("checked") or []
            flagged = [item for item in checked if item.get("status") not in (None, "none", "unchecked")]
        except Exception as exc:  # noqa: BLE001 — a down/slow backend never hides the already-computed mechanics
            error = str(exc)

    return {**report, "retraction_checked": checked, "retraction_flagged": flagged, "retraction_check_error": error}


def citation_integrity_preflight_interactive(doc, base: str) -> None:
    report = citation_integrity_preflight(doc, base)
    lines = _diagnostics_issue_lines(report)
    flagged = report["retraction_flagged"]
    if flagged:
        lines.append(f"{len(flagged)} cited paper(s) carry a retraction/correction signal (see below).")
    for item in flagged:
        label = _RETRACTION_LABEL.get(item.get("status"), str(item.get("status")).upper())
        detail = f"  - Paper {item['paper_id']}: {label}"
        if item.get("date"):
            detail += f" ({item['date']})"
        if item.get("notice_url"):
            detail += f" — {item['notice_url']}"
        lines.append(detail)
    if report["retraction_check_error"]:
        lines.append(f"Retraction re-check unavailable this time: {report['retraction_check_error']}")
    elif not report["retraction_checked"]:
        lines.append("No cited papers to re-check for retraction.")
    else:
        clean = len(report["retraction_checked"]) - len(flagged)
        lines.append(f"Retraction re-check: {clean} of {len(report['retraction_checked'])} cited paper(s) clean.")
    issues_text = "\n\n".join(lines) if lines else "No issues found."
    _msgbox(issues_text, title="callosum — citation integrity preflight")


# inc 463 (P2 item #18, backlog #33/#34): citation coverage audit — a reuse-first slice of the roadmap's much
# larger "manuscript-level citation coverage analysis" checklist. Two pieces: (1) the existing citation-
# concentration engine, scoped to this document's own cited papers; (2) a new, purely structural scan for long
# citation-free stretches of prose. "Claims supported only by retracted/corrected papers" needs no new work
# here — citation_integrity_preflight above already surfaces that. Everything requiring real claim-level
# semantic parsing (evidence relatedness, review-vs-primary preference, secondhand citation) is a deliberate v1
# boundary, matching every other item in this track.

MAX_EQUITY_CHECK_SELECTED = 100  # mirrors the backend's own cap (methods_retraction.py's check-selected precedent)
UNCITED_STRETCH_MIN_PARAGRAPHS = 3  # consecutive substantive paragraphs with no citation to flag a stretch
UNCITED_STRETCH_MIN_WORDS = 15  # a paragraph needs at least this many words to count as "substantive" --
# skips headings/short transitions; a length threshold, never a claim about what needs a citation
UNCITED_STRETCH_PREVIEW_MAX = 150


def _citation_anchor_ranges(doc) -> list:
    """Every one of our own citation marks' MAIN-TEXT anchor position. An inline mark contributes its own
    anchor directly; a note-style mark (footnote/endnote) contributes the NOTE's own main-text anchor instead
    (`XTextContent.getAnchor()` on the footnote/endnote itself, its position in the main document) — the spot a
    reader actually sees the citation reference at. Used by `_uncited_paragraph_stretches` to decide which
    main-text paragraphs count as "cited"."""
    text = doc.getText()
    notes = _note_containers(doc)
    ranges = []
    matched_notes: set[int] = set()
    for name in doc.getReferenceMarks().getElementNames():
        if not (isinstance(name, str) and name.startswith(MARK_PREFIX + " ")):
            continue
        if decode_mark_name(name) is None:
            continue
        mark = doc.getReferenceMarks().getByName(name)
        try:
            anchor = mark.getAnchor()
        except Exception:
            continue
        if _range_belongs_to_text(text, anchor):
            ranges.append(anchor)
            continue
        for index, note in enumerate(notes):
            note_obj = note["_note"]
            if note_obj is None or index in matched_notes:
                continue
            if _range_belongs_to_text(note_obj, anchor):
                try:
                    ranges.append(note_obj.getAnchor())
                except Exception:
                    pass
                matched_notes.add(index)
                break
    return ranges


def _uncited_paragraph_stretches(doc) -> list[dict]:
    """Pure structural scan (no network, no NLI, no claim judgment): walk the main document text's paragraphs
    in order, tracking runs of consecutive substantive paragraphs (>= UNCITED_STRETCH_MIN_WORDS each) that
    contain no citation anchor. A run is reported once it reaches UNCITED_STRETCH_MIN_PARAGRAPHS. This is a
    neutral structural observation ("no citation appeared here") — never a claim that a citation is actually
    needed; the report copy must say so explicitly. Returns ``[{"paragraph_count", "preview"}, ...]``."""
    text = doc.getText()
    anchors = _citation_anchor_ranges(doc)

    def _paragraph_has_citation(para) -> bool:
        # order_by_comparator's own docstring pins the exact convention: compareRegionStarts(a, b) is >0 iff a
        # precedes b, 0 if same start, <0 if a follows b (compareRegionEnds follows the same polarity for ends).
        # Containment of `anchor` within `para` is: para starts at-or-before anchor (para does NOT follow
        # anchor -> compareRegionStarts(para, anchor) >= 0) AND para ends at-or-after anchor (para's end does
        # NOT precede anchor's end -> compareRegionEnds(para, anchor) <= 0).
        for anchor in anchors:
            try:
                if text.compareRegionStarts(para, anchor) >= 0 and text.compareRegionEnds(para, anchor) <= 0:
                    return True
            except Exception:
                continue
        return False

    stretches: list[dict] = []
    run: list[str] = []

    def _flush():
        if len(run) >= UNCITED_STRETCH_MIN_PARAGRAPHS:
            preview = run[0]
            if len(preview) > UNCITED_STRETCH_PREVIEW_MAX:
                preview = preview[:UNCITED_STRETCH_PREVIEW_MAX].rstrip() + "…"
            stretches.append({"paragraph_count": len(run), "preview": preview})

    enum = text.createEnumeration()
    while enum.hasMoreElements():
        para = enum.nextElement()
        if not para.supportsService("com.sun.star.text.Paragraph"):
            continue
        para_text = " ".join(str(para.getString() or "").split())
        substantive = len(para_text.split()) >= UNCITED_STRETCH_MIN_WORDS
        if substantive and not _paragraph_has_citation(para):
            run.append(para_text)
        else:
            _flush()
            run = []
    _flush()
    return stretches


def citation_coverage_audit(doc, base: str = DEFAULT_BASE) -> dict:
    """The two-part coverage audit (P2 item #18): citation-concentration signals for exactly this document's
    own cited papers (via the backend's `POST /methods/citation-equity/check-selected`, reusing
    `audit_reference_list` unchanged with the same honest-degraded author/field path
    `wip_citation_equity.py` already established), plus the local uncited-stretch scan. Never mutates the
    document. Returns ``{"signals", "references_total", "references_resolved", "equity_check_error",
    "uncited_stretches"}``. A backend/network failure on the equity check is caught and surfaced rather than
    blocking the already-computed local scan."""
    # No orphaned-id pre-filter here (unlike citation_integrity_preflight, which needs a fresh diagnose_document
    # scan anyway for its mechanics report) -- an orphaned paper id simply resolves to no DB row and is skipped
    # server-side (check-selected's own per-id skip), so a second document scan just to pre-exclude it would be
    # pure overhead for this audit alone.
    ids = _distinct_cited_paper_ids(doc, orphaned=set())[:MAX_EQUITY_CHECK_SELECTED]
    signals: list[dict] = []
    references_total = 0
    references_resolved = 0
    error: str | None = None
    if ids:
        try:
            result = _post_json(f"{base}/methods/citation-equity/check-selected", {"paper_ids": [int(i) for i in ids]})
            signals = result.get("signals") or []
            references_total = result.get("references_total") or 0
            references_resolved = result.get("references_resolved") or 0
        except Exception as exc:  # noqa: BLE001 — a down/slow backend never hides the local structural scan
            error = str(exc)
    return {
        "signals": signals,
        "references_total": references_total,
        "references_resolved": references_resolved,
        "equity_check_error": error,
        "uncited_stretches": _uncited_paragraph_stretches(doc),
    }


def citation_coverage_audit_interactive(doc, base: str) -> None:
    report = citation_coverage_audit(doc, base)
    lines: list[str] = []
    if report["equity_check_error"]:
        lines.append(f"Citation-concentration check unavailable this time: {report['equity_check_error']}")
    elif not report["signals"]:
        lines.append("No cited papers to audit for citation concentration.")
    else:
        lines.append(
            f"Citation concentration ({report['references_resolved']} of {report['references_total']} "
            "cited paper(s) resolved):"
        )
        for signal in report["signals"]:
            detail = f"  - {signal.get('label')}: {signal.get('summary')}"
            if signal.get("low_coverage"):
                detail += " (⚠ low coverage)"
            lines.append(detail)
    stretches = report["uncited_stretches"]
    if stretches:
        lines.append(
            f"{len(stretches)} stretch(es) of {UNCITED_STRETCH_MIN_PARAGRAPHS}+ consecutive paragraphs with no "
            "citation (a structural note, not a claim that a citation is missing):"
        )
        for stretch in stretches:
            lines.append(f"  - {stretch['paragraph_count']} paragraphs, starting: “{stretch['preview']}”")
    else:
        lines.append("No long uncited stretches found.")
    _msgbox("\n\n".join(lines), title="callosum — citation coverage audit")


# inc 464 (P2 item #22, backlog #33\#34 — the final item in this track): convert Zotero LibreOffice citations
# into live Callosum citations. Format verified from Zotero's own open-source zotero-libreoffice-integration
# (Document.java / ReferenceMark.java) rather than guessed at or reverse-engineered from a sample file (Cliff's
# explicit direction) — see INCREMENT-464-NOTES.md for the citations. v1 is Zotero-only (Mendeley is Word-only;
# EndNote's LibreOffice support is undocumented, per the competitive-review doc) and inline-only: Zotero's
# Bookmark-mode fallback isn't self-contained the way ReferenceMarks are (an unverified internal format,
# declared out of scope), and note-style Zotero citations are detected + reported but not converted (the same
# foreign-mark-inside-a-note risk `citation_placement_error` already guards against for Callosum's own marks).
# This is a faithful format migration, not a claim about the literature — auto-added papers use the exact same
# imported_source="zotero"/processing_tier="metadata-only" trust posture the Zotero *library* importer already
# uses for the same self-asserted metadata.

ZOTERO_MARK_PREFIX = "ZOTERO_"
ZOTERO_ITEM_TAG = "ITEM CSL_CITATION "
ZOTERO_BIBL_TAG = "BIBL "
ZOTERO_BOOKMARK_PREFIX = "ZOTERO_BREF_"
MAX_ZOTERO_DISTINCT_WORKS = 300  # mirrors the backend's own cap (zotero_citations.py)
MAX_ZOTERO_CONVERT_MARKS = 500  # bounds the per-occurrence replace loop (each is its own document refresh)
_ZOTERO_ITEM_OVERRIDE_KEYS = ("locator", "label", "prefix", "suffix", "suppress-author", "author-only")


def _decode_zotero_mark_name(name: str) -> dict | None:
    """Inverse of Zotero's own LibreOffice naming scheme (``PREFIXES[0] + IMPORT_ITEM_PREFIX + json + " RND" +
    random``, verified against zotero-libreoffice-integration's Document.java/ReferenceMark.java). Strips the
    trailing " RND<random>" suffix the same way Zotero's own getCode() does (find the LAST " RND" marker;
    everything after it is the random tag), then requires what remains to start with the item tag and parse as
    the citation.json-shaped payload. Returns the decoded ``{"citationItems": [...], ...}`` dict, or None for
    anything foreign/malformed — defensive like `decode_mark_name`: this is untrusted content pulled from an
    opened document (rule #4) and must never raise.
    """
    if not isinstance(name, str) or not name.startswith(ZOTERO_MARK_PREFIX):
        return None
    without_prefix = name[len(ZOTERO_MARK_PREFIX) :]
    marker = without_prefix.rfind(" RND")
    code = without_prefix[:marker] if marker != -1 and without_prefix[marker + 4 :].isalnum() else without_prefix
    if not code.startswith(ZOTERO_ITEM_TAG):
        return None
    try:
        payload = json.loads(code[len(ZOTERO_ITEM_TAG) :])
    except (ValueError, TypeError):
        return None
    items = payload.get("citationItems") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return None
    return payload


def _zotero_citations_in_order(doc) -> list[dict]:
    """Every Zotero ReferenceMark in the document, decoded, with placement context attached (mirrors
    `scan_citations_in_order`). Each entry: ``{"_mark", "placement", "citationItems": [...]}``. Placement reuses
    `_citation_context`, which is already mark-agnostic — it classifies any ReferenceMark's anchor, not just
    Callosum's own."""
    notes = _note_containers(doc)
    marks = doc.getReferenceMarks()
    out = []
    for name in marks.getElementNames():
        decoded = _decode_zotero_mark_name(name)
        if decoded is None:
            continue
        mark = marks.getByName(name)
        context = _citation_context(doc, mark, notes)
        out.append({"_mark": mark, "citationItems": decoded["citationItems"], **context})
    return out


def _zotero_bookmark_count(doc) -> int:
    """How many Zotero Bookmark-mode citation anchors are present (``ZOTERO_BREF_...``) — detected and
    reported, never parsed: that fallback mode's actual data-storage mechanism isn't self-contained in the
    bookmark name the way ReferenceMarks are, and isn't corroborated from Zotero's public docs/source."""
    return sum(
        1
        for name in doc.getBookmarks().getElementNames()
        if isinstance(name, str) and name.startswith(ZOTERO_BOOKMARK_PREFIX)
    )


def _zotero_bibliography_section(doc):
    """The Zotero-generated bibliography TextSection (``ZOTERO_BIBL ...``), or None. A distinct object type and
    naming scheme from Callosum's own bibliography (a bookmark PAIR, `BIB_BOOKMARK`/`BIB_BOOKMARK_END`) — no
    collision risk."""
    try:
        sections = doc.getTextSections()
    except Exception:
        return None
    for name in sections.getElementNames():
        if isinstance(name, str) and name.startswith(ZOTERO_MARK_PREFIX + ZOTERO_BIBL_TAG):
            return sections.getByName(name)
    return None


def zotero_conversion_scan(doc) -> dict:
    """Read-only. Returns ``{"inline": [...], "note_style_count", "bookmark_count", "bibliography_found",
    "malformed_count"}``. ``inline`` is the list of convertible Zotero citation occurrences
    (`_zotero_citations_in_order`, placement == "inline"); note-style occurrences and Bookmark-mode anchors are
    counted but not returned — a disclosed v1 boundary, never silently dropped. Never mutates the document."""
    fields = _zotero_citations_in_order(doc)
    inline = [f for f in fields if f["placement"] == "inline"]
    note_style_count = sum(1 for f in fields if f["placement"] in NOTE_PLACEMENTS)
    malformed_count = sum(
        1
        for name in doc.getReferenceMarks().getElementNames()
        if isinstance(name, str) and name.startswith(ZOTERO_MARK_PREFIX) and _decode_zotero_mark_name(name) is None
    )
    return {
        "inline": inline,
        "note_style_count": note_style_count,
        "bookmark_count": _zotero_bookmark_count(doc),
        "bibliography_found": _zotero_bibliography_section(doc) is not None,
        "malformed_count": malformed_count,
    }


def convert_zotero_citations_interactive(doc, base: str) -> None:
    """Detect + convert this document's Zotero-authored inline citations into live Callosum citations. Read-only
    scan first, an explicit confirm dialog naming exactly what will happen (including everything left
    unconverted and why) before any mutation, then: resolve every distinct cited work via one
    ``POST /citations/zotero/resolve`` call (matching an existing library paper first, else auto-adding one from
    the citation's own embedded CSL-JSON), replace each inline Zotero mark with a live Callosum one at the same
    position — carrying over locator/label/prefix/suffix/suppress-author/author-only verbatim, since Zotero's
    citation.json schema uses the exact same key names Callosum's own `_ITEM_DEFAULTS` does — and swap Zotero's
    own bibliography TextSection (if found) for a Callosum-managed one at the same position."""
    scan = zotero_conversion_scan(doc)
    inline = scan["inline"][:MAX_ZOTERO_CONVERT_MARKS]
    truncated = len(scan["inline"]) - len(inline)
    if not inline and scan["note_style_count"] == 0 and scan["bookmark_count"] == 0:
        _msgbox("No Zotero citations found in this document.", title="callosum — convert Zotero citations")
        return

    lines: list[str] = []
    if inline:
        lines.append(f"Convert {len(inline)} Zotero citation(s) to live Callosum citations.")
        if truncated:
            lines.append(
                f"({truncated} more were found beyond this run's {MAX_ZOTERO_CONVERT_MARKS}-citation limit — "
                "re-run afterward to continue.)"
            )
    if scan["note_style_count"]:
        lines.append(
            f"{scan['note_style_count']} note-style (footnote/endnote) Zotero citation(s) found — will be left "
            "unconverted (not yet supported)."
        )
    if scan["bookmark_count"]:
        lines.append(
            f"{scan['bookmark_count']} Zotero citation(s) appear to use Bookmark-mode storage — will be left "
            "unconverted (not yet supported)."
        )
    if scan["bibliography_found"]:
        lines.append("Zotero's generated bibliography will be replaced with a Callosum-managed one.")
    if scan["malformed_count"]:
        lines.append(f"{scan['malformed_count']} Zotero-named field(s) could not be read and will be left untouched.")
    if not inline:
        _msgbox("\n".join(lines), title="callosum — convert Zotero citations")
        return
    if not _confirm_box("\n".join(lines) + "\n\nProceed?", title="callosum — convert Zotero citations"):
        return

    fingerprints: dict[str, dict] = {}
    order: list[str] = []
    for field in inline:
        for item in field["citationItems"]:
            item_data = item.get("itemData") or {}
            fingerprint = json.dumps(item_data, sort_keys=True)
            if fingerprint not in fingerprints:
                fingerprints[fingerprint] = {"item_data": item_data, "uris": item.get("uris") or []}
                order.append(fingerprint)
    resolve_items = [fingerprints[fp] for fp in order][:MAX_ZOTERO_DISTINCT_WORKS]
    try:
        resolved = _post_json(f"{base}/citations/zotero/resolve", {"items": resolve_items})
    except Exception as exc:  # noqa: BLE001 — never leaves the document half-edited on a down/slow backend
        _msgbox(
            f"Couldn't resolve Zotero citations against your library: {exc}",
            title="callosum — convert Zotero citations",
        )
        return
    paper_id_by_fingerprint = {order[i]: r["paper_id"] for i, r in enumerate(resolved)}
    created_count = sum(1 for r in resolved if r.get("created"))

    converted = 0
    for field in inline:
        mark = field["_mark"]
        items_payload: list[dict] = []
        for item in field["citationItems"]:
            item_data = item.get("itemData") or {}
            fingerprint = json.dumps(item_data, sort_keys=True)
            paper_id = paper_id_by_fingerprint.get(fingerprint)
            if paper_id is None:
                items_payload = []
                break
            overrides = {k: item[k] for k in _ZOTERO_ITEM_OVERRIDE_KEYS if k in item}
            items_payload.append({"paper_id": paper_id, **overrides})
        if not items_payload:
            continue
        source_text = mark.getAnchor().getText()
        source_cursor = source_text.createTextCursorByRange(mark.getAnchor())
        source_text.removeTextContent(mark)
        source_cursor.setString("")
        insert_citation_items(doc, items_payload, base, cursor=source_cursor)
        converted += 1

    bibliography_swapped = False
    section = _zotero_bibliography_section(doc)
    if section is not None:
        try:
            text = doc.getText()
            cursor = text.createTextCursorByRange(section.getAnchor())
            cursor.setString("")
            text.removeTextContent(section)
            refresh(doc, base, bib_cursor=cursor, update_citations=False, update_bibliography=True)
            bibliography_swapped = True
        except Exception:
            pass

    summary = [
        f"Converted {converted} of {len(inline)} Zotero citation(s) ({len(resolved)} distinct work(s), "
        f"{created_count} newly added to your library)."
    ]
    if scan["note_style_count"]:
        summary.append(f"Left unconverted: {scan['note_style_count']} note-style citation(s) (not yet supported).")
    if scan["bookmark_count"]:
        summary.append(f"Left unconverted: {scan['bookmark_count']} Bookmark-mode citation(s) (not yet supported).")
    if bibliography_swapped:
        summary.append("Zotero's bibliography was replaced with a Callosum-managed one.")
    elif scan["bibliography_found"]:
        summary.append("Zotero's bibliography could not be automatically replaced.")
    _msgbox("\n".join(summary), title="callosum — convert Zotero citations")


def list_document_citations(doc, base: str) -> list[dict]:
    """Read-only rollup of every unique cited work in the document, in first-occurrence order (P1 item #12,
    backlog #33/#34 — the "Citations in this document" panel's data source), PLUS any manually-included
    uncited "further reading" works (P1 item #11) appended after. Never mutates.

    For each unique paper_id: a rendered ``Author Year — Title`` row (`csl_record_row`), the occurrence count
    (a paper cited 3 times counts once here, count=3; an uncited-include entry is always 0), whether it's
    orphaned (no longer in the library — reuses `fetch_csl`'s existing raise-on-missing contract, the same
    signal `diagnose_document` already uses), retraction status (one call per unique paper_id to the
    already-audited, read-only ``GET /papers/{id}/retraction`` — no new endpoint), whether it's currently
    excluded from the bibliography (`PREF_BIB_EXCLUDE`), its optional document-local bibliography category, and
    the FIRST occurrence's mark for navigate-to (``None`` for an uncited-include entry — there's nowhere in the
    document to navigate to).

    Returns ``[{"paper_id", "row", "count", "orphaned", "retraction_label", "excluded", "category", "uncited",
    "mark", "evidence"}, ...]``. ``evidence`` (inc 460, roadmap #17's "record ... for later auditing") is
    ``{"page", "snippet"}`` from the FIRST occurrence's own evidence-audit locator (see `_evidence_fields`),
    or ``None`` when that occurrence carries no evidence (inserted via a path other than Suggest, or a mark
    from before inc 460).
    """
    seen: dict[str, dict] = {}
    order: list[str] = []
    for field in scan_citations_in_order(doc):
        for item in field["items"]:
            paper_id = _paper_id_from_item(item)
            if paper_id is None:
                continue
            if paper_id not in seen:
                seen[paper_id] = {
                    "paper_id": paper_id,
                    "count": 0,
                    "mark": field["_mark"],
                    "evidence": _evidence_from_item(item),
                }
                order.append(paper_id)
            seen[paper_id]["count"] += 1

    exclude_ids = set(_get_id_list(doc, PREF_BIB_EXCLUDE))
    categories = bibliography_categories(doc)
    for paper_id in _get_id_list(doc, PREF_BIB_UNCITED):
        if paper_id not in seen:  # already cited normally -- don't duplicate as a separate uncited row
            seen[paper_id] = {"paper_id": paper_id, "count": 0, "mark": None, "evidence": None}
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
                "category": categories.get(paper_id),
                "uncited": entry["mark"] is None,
                "mark": entry["mark"],
                "evidence": entry["evidence"],
            }
        )
    return results


def _evidence_from_item(item: dict) -> dict | None:
    """The compact evidence-audit locator stored on a decoded item (see `_evidence_fields`/`_ITEM_DEFAULTS`),
    reshaped for display — ``None`` when the item carries no snippet (not inserted via Suggest, or pre-460)."""
    snippet = item.get("evidence_snippet")
    if not snippet:
        return None
    start, end = item.get("evidence_page_start"), item.get("evidence_page_end")
    if start and end and end != start:
        page = f"{start}–{end}"
    else:
        page = start or end
    return {"page": page, "snippet": snippet}


def citations_panel_interactive(doc, base: str) -> None:
    """Open the "Citations in this document" panel (P1 item #12; bibliography editing P1 item #11, both
    backlog #33/#34): every unique cited work, occurrence count, missing/orphaned + retraction flags, a live
    filter, click-to-navigate, and — from the panel itself — toggling a cited work's bibliography exclusion or
    adding an uncited "further reading" work, and assigning/removing a document-local bibliography category.
    A snapshot re-fetched after every edit made from within the panel (the always-open/live-refreshing version
    that also tracks edits made OUTSIDE it is a later, deliberately deferred phase; see `citations_panel.py`'s
    own docstring for why). Opens even with nothing cited yet — that is itself a valid starting point for
    "Add uncited work(s)…" to build a reading list from scratch."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import citations_panel

    mark = citations_panel.run_citations_panel(doc, base)
    if mark is not None:
        doc.getCurrentController().select(mark.getAnchor())


def insert_evidence_interactive(doc, base: str) -> str | None:
    """Citavi-style evidence insertion (P2 item #20, backlog #33/#34, inc 461): find a paper, pick one of its
    saved PDF highlights, optionally check a typed claim's stance against it, and insert it in one of several
    formats alongside a live citation. The dialogs + insertion logic live in `evidence_insert.py` (the
    `composer.py`/`citations_panel.py` sibling-module pattern — new UNO dialog construction, not more action
    logic in this already-large file)."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import evidence_insert

    return evidence_insert.run_insert_evidence(doc, base)


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
    "insertStagedStatement": insert_staged_statement,
    "setServerUrl": lambda doc, base: set_server_url_interactive(doc),
    "deleteCitation": delete_citation_interactive,
    "mergeWithNext": merge_with_next_interactive,
    "mergeWithPrevious": merge_with_previous_interactive,
    "splitCitation": split_citation_interactive,
    "openInCallosum": open_in_callosum,
    "goToBibliographyEntry": go_to_bibliography_entry_interactive,
    "insertBibliographyHere": insert_bibliography_here_interactive,
    "insertSectionBibliography": insert_section_bibliography_interactive,
    "removeSectionBibliography": remove_section_bibliography_interactive,
    "manageSectionBibliographies": manage_section_bibliographies_interactive,
    "setBibliographyHeading": set_bibliography_heading_interactive,
    "setJournalAbbreviations": set_journal_abbreviations_interactive,
    "toggleBibliographyLinks": toggle_bibliography_links_interactive,
    "toggleBibliographyExternalLinks": toggle_bibliography_external_links_interactive,
    "toggleCiteAuto": toggle_cite_auto_interactive,
    "toggleBibAuto": toggle_bib_auto_interactive,
    "diagnostics": document_diagnostics_interactive,
    "editCitation": edit_citation_interactive,
    "citationsPanel": citations_panel_interactive,
    "citationIntegrityPreflight": citation_integrity_preflight_interactive,
    "citationCoverageAudit": citation_coverage_audit_interactive,
    "insertEvidence": insert_evidence_interactive,
    "convertZoteroCitations": convert_zotero_citations_interactive,
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


def CallosumInsertStagedStatement(*_args):
    _macro("insertStagedStatement")


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


def CallosumGoToBibliographyEntry(*_args):
    _macro("goToBibliographyEntry")


def CallosumInsertBibliographyHere(*_args):
    _macro("insertBibliographyHere")


def CallosumInsertSectionBibliography(*_args):
    _macro("insertSectionBibliography")


def CallosumRemoveSectionBibliography(*_args):
    _macro("removeSectionBibliography")


def CallosumManageSectionBibliographies(*_args):
    _macro("manageSectionBibliographies")


def CallosumSetBibliographyHeading(*_args):
    _macro("setBibliographyHeading")


def CallosumSetJournalAbbreviations(*_args):
    _macro("setJournalAbbreviations")


def CallosumToggleBibliographyLinks(*_args):
    _macro("toggleBibliographyLinks")


def CallosumToggleBibliographyExternalLinks(*_args):
    _macro("toggleBibliographyExternalLinks")


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


def CallosumCitationCoverageAudit(*_args):
    _macro("citationCoverageAudit")


def CallosumInsertEvidence(*_args):
    _macro("insertEvidence")


def CallosumConvertZoteroCitations(*_args):
    _macro("convertZoteroCitations")


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
    CallosumGoToBibliographyEntry,
    CallosumInsertBibliographyHere,
    CallosumInsertSectionBibliography,
    CallosumRemoveSectionBibliography,
    CallosumManageSectionBibliographies,
    CallosumSetBibliographyHeading,
    CallosumSetJournalAbbreviations,
    CallosumToggleBibliographyLinks,
    CallosumToggleBibliographyExternalLinks,
    CallosumToggleCiteAuto,
    CallosumToggleBibAuto,
    CallosumPrepareSubmissionCopy,
    CallosumDiagnostics,
    CallosumEditCitation,
    CallosumCitationsPanel,
    CallosumCitationCoverageAudit,
    CallosumInsertEvidence,
    CallosumInsertStagedStatement,
    CallosumConvertZoteroCitations,
)
