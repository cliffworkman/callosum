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
from collections.abc import Mapping, Sequence
from html.parser import HTMLParser
from typing import Any

from app.backend.api.startup import PROJECT_ROOT

_RUNNER = PROJECT_ROOT / "app" / "backend" / "citations" / "citeproc_runner.js"
_CITEPROC = PROJECT_ROOT / "node_modules" / "citeproc"

# Curated bundled styles — each `id` matches `csl/styles/<id>.csl`. The id set is an ALLOWLIST (rule #3/#4):
# only these ids reach the sidecar / filesystem. Add a style = add the .csl file + an entry here.
STYLES: list[dict[str, str]] = [
    {"id": "apa", "title": "APA (7th edition)", "family": "author-date"},
    {"id": "modern-language-association", "title": "MLA (9th edition)", "family": "author-date"},
    {"id": "chicago-author-date", "title": "Chicago (author-date, 18th)", "family": "author-date"},
    {"id": "chicago-notes-bibliography", "title": "Chicago (notes & bibliography, 18th)", "family": "note"},
    {"id": "harvard-cite-them-right", "title": "Harvard — Cite Them Right (12th)", "family": "author-date"},
    {"id": "ieee", "title": "IEEE", "family": "numeric"},
    {"id": "nature", "title": "Nature", "family": "numeric"},
]
STYLE_IDS = {s["id"] for s in STYLES}
LOCALES = ("en-US", "en-GB")
DEFAULT_STYLE = "apa"
DEFAULT_LOCALE = "en-US"
MAX_ITEMS = 5000  # bound a render request (rule #4)
MAX_CLUSTERS = 5000  # document-render: max citation clusters per request
MAX_ITEMS_PER_CLUSTER = 50  # document-render: max items in one citation cluster

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


# ── the engine call ───────────────────────────────────────────────────────────────────────────────────


def _run(request: dict[str, Any]) -> dict[str, Any]:
    """Run the citeproc sidecar with a full request dict (per-item OR document mode); fail-closed."""
    node = shutil.which("node")
    if node is None or not _CITEPROC.is_dir() or not _RUNNER.is_file():
        raise CitationEngineUnavailable(
            "Formatted-citation rendering needs Node + citeproc. Run `npm install` at the project root."
        )
    result = subprocess.run(
        [node, str(_RUNNER)],
        input=json.dumps(request),
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
    if style not in STYLE_IDS:
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
    uncited_items: Sequence[Mapping[str, Any]] = (),
    bibliography_exclude_ids: Sequence[str] = (),
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
    if style not in STYLE_IDS:
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

    data = _run(
        {
            "mode": "document",
            "style": style,
            "locale": locale,
            "citations": clusters,
            "uncited_items": out_uncited,
            "bibliography_exclude_ids": exclude_ids,
        }
    )

    out_citations: list[dict[str, Any]] = []
    for c in data.get("citations", []):
        html = c.get("html", "") or ""
        out_citations.append(
            {"citationID": str(c.get("citationID", "")), "text": _to_text(html), "html": _safe_html(html)}
        )
    bib = data.get("bibliography", []) or []
    return {
        "style": style,
        "locale": locale,
        "citations": out_citations,
        "bibliography_text": "\n".join(_to_text(e) for e in bib),
        "bibliography_html": [_safe_html(e) for e in bib],
    }
