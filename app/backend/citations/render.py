"""Formatted-citation rendering via citeproc-js (inc 106).

Turns a paper's canonical CSL-JSON (`papers.csl_json`) into formatted in-text citations + bibliography
entries in real CSL styles (APA / MLA / Chicago / IEEE / Nature / Harvard …) by shelling out to the
citeproc-js sidecar (`citeproc_runner.js`) the SAME way the frontend build shells out to esbuild
(`api/frontend.py::_transpile_jsx`): a fixed-arg `node <runner>` subprocess, request JSON on stdin,
result JSON on stdout, fail-closed. Local — no network, no LLM, no egress. Styles + locales are bundled
under `csl/` (CC-BY-SA — see THIRD-PARTY-NOTICES.md). citeproc-js is © Frank Bennett & contributors (AGPL-3.0).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.parse
from collections.abc import Mapping, Sequence
from html.parser import HTMLParser
from typing import Any

from app.backend.api.startup import PROJECT_ROOT
from app.backend.citations import style_store
from app.backend.citations.journal_abbreviations import DEFAULT_MODE as DEFAULT_JOURNAL_ABBREVIATION_MODE
from app.backend.citations.journal_abbreviations import apply_journal_abbreviations

_RUNNER = PROJECT_ROOT / "app" / "backend" / "citations" / "citeproc_runner.js"
_CITEPROC = PROJECT_ROOT / "node_modules" / "citeproc"

# Re-export the bundled manifest for compatibility. Runtime validation uses style_store so local custom styles
# become first-class without turning user input into a path.
STYLES = style_store.BUILTIN_STYLES
STYLE_IDS = {s["id"] for s in STYLES}
LOCALES = ("en-US", "en-GB")
DEFAULT_STYLE = "apa"
DEFAULT_LOCALE = "en-US"
MAX_ITEMS = 5000  # bound a render request (rule #4)
MAX_CLUSTERS = 5000  # document-render: max citation clusters per request
MAX_ITEMS_PER_CLUSTER = 50  # document-render: max items in one citation cluster
MAX_BIBLIOGRAPHY_LINKS_PER_ENTRY = 20
MAX_EXTERNAL_LINK_LENGTH = 2048
MAX_BIBLIOGRAPHY_TITLE_LENGTH = 2000

# citeproc emits only these inline formatting tags in citation text; everything else (div/span/class) is dropped.
_ALLOWED_HTML_TAGS = {"i", "b", "em", "strong", "sup", "sub"}


class CitationEngineUnavailable(RuntimeError):
    """Node and/or the bundled citeproc dependency is not installed."""


def list_styles() -> list[dict[str, str]]:
    """The bundled style manifest (id, human title, family)."""
    return [dict(s) for s in STYLES]


# ── HTML → text / safe-HTML (citeproc returns HTML; we never display it raw) ──────────────────────────


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return " ".join("".join(p.parts).split())


class _Sanitizer(HTMLParser):
    """Keep only allowlisted inline tags; escape all text; drop attributes + every other tag (text kept)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _ALLOWED_HTML_TAGS:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _ALLOWED_HTML_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.out.append(data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _safe_html(html: str) -> str:
    s = _Sanitizer()
    s.feed(html)
    return " ".join("".join(s.out).split())


def _validated_external_url(value: str | None) -> str | None:
    """Accept only bounded web destinations; citeproc output never grants authority to other URI schemes."""
    if not isinstance(value, str) or not value or len(value) > MAX_EXTERNAL_LINK_LENGTH:
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


class _BibliographyLinkExtractor(HTMLParser):
    """Collect citeproc's DOI/URL anchor text without retaining arbitrary HTML or attributes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._anchors: list[dict[str, Any]] = []
        self._active: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a" or self._active is not None:
            return
        href = _validated_external_url(next((value for name, value in attrs if name == "href"), None))
        self._active = {"url": href, "parts": []}

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._active is None:
            return
        if self._active["url"]:
            self._anchors.append(self._active)
        self._active = None

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._active["parts"].append(data)


def _bibliography_link_spans(html: str) -> list[dict[str, Any]]:
    """Return bounded, non-overlapping offsets into the exact normalized plain-text bibliography entry."""
    parser = _BibliographyLinkExtractor()
    parser.feed(html)
    plain_text = _to_text(html)
    spans: list[dict[str, Any]] = []
    search_from = 0
    for anchor in parser._anchors[:MAX_BIBLIOGRAPHY_LINKS_PER_ENTRY]:
        display = " ".join("".join(anchor["parts"]).split())
        if not display:
            continue
        start = plain_text.find(display, search_from)
        if start < 0:
            start = plain_text.find(display)
        end = start + len(display)
        if start < 0 or (spans and start < spans[-1]["start"] + spans[-1]["length"]):
            continue
        spans.append({"start": start, "length": len(display), "url": anchor["url"]})
        search_from = end
    return spans


def _bibliography_title_destination(item: Mapping[str, Any]) -> str | None:
    """Prefer a canonical DOI resolver, then a source URL; malformed metadata stays plain."""
    raw_doi = item.get("DOI")
    if isinstance(raw_doi, str):
        doi = raw_doi.strip()
        lowered = doi.lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:"):
            if lowered.startswith(prefix):
                doi = doi[len(prefix) :].strip()
                break
        if (
            0 < len(doi) <= MAX_EXTERNAL_LINK_LENGTH
            and doi.lower().startswith("10.")
            and "/" in doi
            and not any(char.isspace() or ord(char) < 32 for char in doi)
        ):
            encoded = urllib.parse.quote(doi, safe="/:;()[]-._~!$&'*,=@")
            if destination := _validated_external_url(f"https://doi.org/{encoded}"):
                return destination

    raw_url = item.get("URL")
    return _validated_external_url(raw_url.strip()) if isinstance(raw_url, str) else None


def _bibliography_title_link_span(
    html: str,
    entry_ids: Sequence[str],
    items_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Link one exact/ASCII-case-only unique title; ambiguity or citeproc transformation fails plain."""
    if len(entry_ids) != 1:
        return []
    item = items_by_id.get(str(entry_ids[0]))
    if item is None or (destination := _bibliography_title_destination(item)) is None:
        return []
    raw_title = item.get("title")
    if not isinstance(raw_title, str):
        return []
    title = _to_text(raw_title)
    if not title or len(title) > MAX_BIBLIOGRAPHY_TITLE_LENGTH:
        return []

    plain_text = _to_text(html)
    if plain_text.count(title) == 1:
        start = plain_text.index(title)
    elif plain_text.isascii() and title.isascii() and plain_text.lower().count(title.lower()) == 1:
        start = plain_text.lower().index(title.lower())
    else:
        return []
    return [{"start": start, "length": len(title), "url": destination}]


def _bibliography_links(
    html: str,
    entry_ids: Sequence[str],
    items_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Keep citeproc's visible DOI/URL anchors, otherwise safely fall back to the rendered source title."""
    return _bibliography_link_spans(html) or _bibliography_title_link_span(html, entry_ids, items_by_id)


# ── the engine call ───────────────────────────────────────────────────────────────────────────────────


def _run(request: dict[str, Any]) -> dict[str, Any]:
    """Run the citeproc sidecar with a full request dict (per-item OR document mode); fail-closed."""
    node = shutil.which("node")
    if node is None or not _CITEPROC.is_dir() or not _RUNNER.is_file():
        raise CitationEngineUnavailable(
            "Formatted-citation rendering needs Node + citeproc. Run `npm install` at the project root."
        )
    payload = dict(request)
    if "style_xml" not in payload and payload.get("style"):
        payload["style_xml"] = style_store.render_style_xml(str(payload["style"]))
    result = subprocess.run(
        [node, str(_RUNNER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        detail = (result.stdout or result.stderr or "").strip() or "citeproc failed"
        raise RuntimeError(f"citation render failed: {detail}")
    data = json.loads(result.stdout)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"citation render failed: {data['error']}")
    return data


def render_papers(papers: Sequence[Mapping[str, Any]], *, style: str, locale: str) -> dict[str, Any]:
    """Render the given paper rows (each with `id` + `csl_json`) in the chosen style.

    Returns per-item in-text + reference (plain text + sanitized HTML) and the combined bibliography.
    """
    if not style_store.style_exists(style):
        raise ValueError(f"unknown style: {style}")
    if locale not in LOCALES:
        locale = DEFAULT_LOCALE
    if len(papers) > MAX_ITEMS:
        raise ValueError(f"too many papers to render at once (max {MAX_ITEMS})")

    items: list[dict[str, Any]] = []
    for p in papers:
        csl = p.get("csl_json")
        item = dict(csl) if isinstance(csl, dict) else {}
        item["id"] = str(p["id"])
        item.setdefault("type", "article-journal")  # citeproc requires a type
        items.append(item)

    data = _run({"items": items, "style": style, "locale": locale})
    by_id = {str(it.get("id")): it for it in data.get("items", [])}

    out_items: list[dict[str, Any]] = []
    for p in papers:
        it = by_id.get(str(p["id"]), {})
        ref_html = it.get("reference", "") or ""
        out_items.append(
            {
                "id": int(p["id"]),
                "in_text": _to_text(it.get("inText", "") or ""),
                "reference_text": _to_text(ref_html),
                "reference_html": _safe_html(ref_html),
            }
        )

    bib = data.get("bibliography", []) or []
    return {
        "style": style,
        "locale": locale,
        "items": out_items,
        "bibliography_text": "\n".join(_to_text(e) for e in bib),
        "bibliography_html": [_safe_html(e) for e in bib],
    }


def render_document(
    citations: Sequence[Mapping[str, Any]],
    *,
    style: str,
    locale: str,
    style_xml: str | None = None,
    uncited_items: Sequence[Mapping[str, Any]] = (),
    bibliography_exclude_ids: Sequence[str] = (),
    journal_abbreviation_mode: str = DEFAULT_JOURNAL_ABBREVIATION_MODE,
) -> dict[str, Any]:
    """Position-aware render of a document's ORDERED citation clusters — the word-processor adapter contract.

    Each cluster is ``{"citationID"?: str, "items": [<CSL-JSON dict, each with an `id`>], "noteIndex"?: int}``,
    passed in **document order**. Unlike :func:`render_papers` (isolated per-item), this renders the whole set
    coherently — numeric styles renumber `[1][2][3]` by appearance, author-date styles disambiguate
    (`2020a`/`2020b`), and note styles receive their real one-based Writer note number for first/subsequent/ibid
    position state. In-text callers omit ``noteIndex`` and retain the original zero default. Self-contained: it
    renders from the **passed CSL-JSON payloads** (each document field carries its own), so it needs no library
    lookup. Returns per-cluster in-text (text + sanitized HTML) + the bibliography.

    ``uncited_items`` (P1 item #11, backlog #33/#34) are bibliography-only entries — a "further reading" work
    with no in-text citation mark — via citeproc-js's own ``updateUncitedItems``. ``bibliography_exclude_ids``
    removes specific CITED works from the bibliography (e.g. a personal communication) while their in-text
    citation still renders, via citeproc-js's own ``makeBibliography({exclude: [...]})`` field filter — both are
    real, already-supported citeproc-js mechanisms, just not previously wired through this endpoint.
    """
    if style_xml is None and not style_store.style_exists(style):
        raise ValueError(f"unknown style: {style}")
    if locale not in LOCALES:
        locale = DEFAULT_LOCALE
    if len(citations) > MAX_CLUSTERS:
        raise ValueError(f"too many citations to render at once (max {MAX_CLUSTERS})")
    if len(uncited_items) > MAX_ITEMS_PER_CLUSTER:
        raise ValueError(f"too many uncited items at once (max {MAX_ITEMS_PER_CLUSTER})")
    if len(bibliography_exclude_ids) > MAX_CLUSTERS:
        raise ValueError(f"too many bibliography-exclude ids at once (max {MAX_CLUSTERS})")

    clusters: list[dict[str, Any]] = []
    total_items = 0
    for i, c in enumerate(citations):
        raw_items = c.get("items") if isinstance(c, Mapping) else None
        items_in = raw_items if isinstance(raw_items, list) else []
        if len(items_in) > MAX_ITEMS_PER_CLUSTER:
            raise ValueError(f"too many items in one citation (max {MAX_ITEMS_PER_CLUSTER})")
        out_items: list[dict[str, Any]] = []
        for it in items_in:
            if not isinstance(it, Mapping) or it.get("id") is None:
                raise ValueError("each citation item needs an id")
            item = dict(it)
            item["id"] = str(item["id"])
            item.setdefault("type", "article-journal")  # citeproc requires a type
            out_items.append(item)
            total_items += 1
        raw_note_index = c.get("noteIndex", 0)
        if not isinstance(raw_note_index, int) or isinstance(raw_note_index, bool):
            raise ValueError("citation noteIndex must be an integer")
        if raw_note_index < 0 or raw_note_index > MAX_CLUSTERS:
            raise ValueError(f"citation noteIndex must be between 0 and {MAX_CLUSTERS}")
        clusters.append(
            {
                "citationID": str(c.get("citationID") or f"c{i}"),
                "items": out_items,
                "noteIndex": raw_note_index,
            }
        )
    note_indexes = [cluster["noteIndex"] for cluster in clusters]
    if any(note_indexes) and any(note_index == 0 for note_index in note_indexes):
        raise ValueError("citation noteIndex values must be either all zero or all positive")
    if any(current < previous for previous, current in zip(note_indexes, note_indexes[1:], strict=False)):
        raise ValueError("positive citation noteIndex values must follow document order")
    if total_items > MAX_ITEMS:
        raise ValueError(f"too many items to render at once (max {MAX_ITEMS})")

    out_uncited: list[dict[str, Any]] = []
    for it in uncited_items:
        if not isinstance(it, Mapping) or it.get("id") is None:
            raise ValueError("each uncited item needs an id")
        item = dict(it)
        item["id"] = str(item["id"])
        item.setdefault("type", "article-journal")
        out_uncited.append(item)
    exclude_ids = [str(x) for x in bibliography_exclude_ids]
    effective_style_xml = style_xml if style_xml is not None else style_store.render_style_xml(style)
    flat_items = [item for cluster in clusters for item in cluster["items"]] + out_uncited
    transformed_items, journal_summary = apply_journal_abbreviations(
        flat_items,
        journal_abbreviation_mode,
        style_xml=effective_style_xml,
    )
    transformed = iter(transformed_items)
    for cluster in clusters:
        cluster["items"] = [next(transformed) for _item in cluster["items"]]
    out_uncited = [next(transformed) for _item in out_uncited]

    request = {
        "mode": "document",
        "style": style,
        "locale": locale,
        "style_xml": effective_style_xml,
        "citations": clusters,
        "uncited_items": out_uncited,
        "bibliography_exclude_ids": exclude_ids,
    }
    data = _run(request)

    out_citations: list[dict[str, Any]] = []
    for c in data.get("citations", []):
        html = c.get("html", "") or ""
        out_citations.append(
            {"citationID": str(c.get("citationID", "")), "text": _to_text(html), "html": _safe_html(html)}
        )
    bib = data.get("bibliography", []) or []
    bib_entry_ids = data.get("bibliography_entry_ids", []) or []
    if len(bib_entry_ids) != len(bib) or not all(isinstance(ids, list) for ids in bib_entry_ids):
        bib_entry_ids = [[] for _entry in bib]
    items_by_id = {str(item["id"]): item for cluster in clusters for item in cluster["items"]}
    items_by_id.update({str(item["id"]): item for item in out_uncited})
    return {
        "style": style,
        "locale": locale,
        "citations": out_citations,
        "bibliography_text": "\n".join(_to_text(e) for e in bib),
        "bibliography_html": [_safe_html(e) for e in bib],
        "bibliography_entry_ids": [[str(item_id) for item_id in ids] for ids in bib_entry_ids],
        "bibliography_links": [
            _bibliography_links(entry, entry_ids, items_by_id)
            for entry, entry_ids in zip(bib, bib_entry_ids, strict=True)
        ],
        "journal_abbreviations": journal_summary,
    }


def validate_style_xml(style_xml: str) -> None:
    """Ask the real citeproc engine to instantiate and render an independent candidate style."""
    item = {
        "id": "validation",
        "type": "book",
        "title": "A Citation Style Validation Example",
        "author": [{"family": "Rivera", "given": "Maya"}],
        "issued": {"date-parts": [[2024]]},
        "publisher": "Example Press",
    }
    _run(
        {
            "items": [item],
            "order": ["validation"],
            "style": "custom-validation",
            "locale": DEFAULT_LOCALE,
            "style_xml": style_xml,
        }
    )
