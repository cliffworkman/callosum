"""Searchable CSL style catalog, local preferences, and deterministic previews.

The bundled CSL files remain the source of truth. Metadata is parsed with ElementTree rather than duplicated in
UI code; favorites, recents, and the application default are local non-secret preferences in app-settings.json.
No network or LLM is involved.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Any

from app.backend import app_settings
from app.backend.api.startup import PROJECT_ROOT
from app.backend.citations.render import (
    DEFAULT_LOCALE,
    DEFAULT_STYLE,
    LOCALES,
    STYLE_IDS,
    STYLES,
    render_document,
)

_CSL_NS = {"csl": "http://purl.org/net/xbiblio/csl"}
_STYLES_DIR = PROJECT_ROOT / "app" / "backend" / "citations" / "csl" / "styles"
_MAX_RECENTS = 8
MAX_STYLE_QUERY = 120

_PREVIEW_CITATIONS = (
    {
        "citationID": "preview-primary",
        "noteIndex": 1,
        "items": [
            {
                "id": "callosum-preview-article",
                "type": "article-journal",
                "title": "An example study of collaborative writing",
                "author": [
                    {"family": "Rivera", "given": "Maya"},
                    {"family": "Chen", "given": "Alex"},
                ],
                "issued": {"date-parts": [[2024]]},
                "container-title": "Journal of Examples",
                "volume": "12",
                "issue": "3",
                "page": "145-162",
                "DOI": "10.0000/example.2024.001",
            },
            {
                "id": "callosum-preview-book",
                "type": "book",
                "title": "Methods for Working with Sources",
                "author": [{"family": "Okafor", "given": "Nneka"}],
                "issued": {"date-parts": [[2021]]},
                "publisher": "Example Press",
                "publisher-place": "New York",
            },
        ],
    },
    {
        "citationID": "preview-subsequent",
        "noteIndex": 2,
        "items": [
            {
                "id": "callosum-preview-article",
                "type": "article-journal",
                "title": "An example study of collaborative writing",
                "author": [
                    {"family": "Rivera", "given": "Maya"},
                    {"family": "Chen", "given": "Alex"},
                ],
                "issued": {"date-parts": [[2024]]},
                "container-title": "Journal of Examples",
                "volume": "12",
                "issue": "3",
                "page": "145-162",
                "DOI": "10.0000/example.2024.001",
            }
        ],
    },
)


def _text(parent: ET.Element | None, name: str) -> str:
    node = parent.find(f"csl:{name}", _CSL_NS) if parent is not None else None
    return " ".join((node.text or "").split()) if node is not None else ""


def _style_metadata(manifest: dict[str, str]) -> dict[str, Any]:
    path = _STYLES_DIR / f"{manifest['id']}.csl"
    root = ET.parse(path).getroot()
    info = root.find("csl:info", _CSL_NS)
    categories = info.findall("csl:category", _CSL_NS) if info is not None else []
    fields = sorted({category.get("field", "") for category in categories if category.get("field")})
    citation_format = next(
        (category.get("citation-format", "") for category in categories if category.get("citation-format")),
        manifest["family"],
    )
    parent = next(
        (
            link.get("href", "").rsplit("/", 1)[-1]
            for link in (info.findall("csl:link", _CSL_NS) if info is not None else [])
            if link.get("rel") == "independent-parent"
        ),
        None,
    )
    title = _text(info, "title") or manifest["title"]
    short_title = _text(info, "title-short")
    summary = _text(info, "summary")
    searchable = " ".join(
        [
            manifest["id"],
            manifest["title"],
            title,
            short_title,
            summary,
            citation_format,
            *fields,
            *(field.replace("_", " ") for field in fields),
        ]
    ).casefold()
    return {
        **manifest,
        "full_title": title,
        "short_title": short_title,
        "summary": summary,
        "citation_format": citation_format,
        "fields": fields,
        "independent": parent is None,
        "parent_style": parent,
        "default_locale": root.get("default-locale") or "",
        "installed": True,
        "_searchable": searchable,
    }


@lru_cache(maxsize=1)
def _catalog() -> tuple[dict[str, Any], ...]:
    return tuple(_style_metadata(manifest) for manifest in STYLES)


def list_catalog_styles(query: str = "") -> list[dict[str, Any]]:
    """Return installed styles matching every bounded query token, in curated manifest order."""
    query = str(query or "").strip()
    if len(query) > MAX_STYLE_QUERY:
        raise ValueError(f"style search is too long (max {MAX_STYLE_QUERY} characters)")
    tokens = re.findall(r"[\w-]+", query.casefold())
    rows = [style for style in _catalog() if all(token in style["_searchable"] for token in tokens)]
    return [{key: value for key, value in style.items() if key != "_searchable"} for style in rows]


def _valid_ids(value: object, *, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item in STYLE_IDS and item not in out:
            out.append(item)
            if limit is not None and len(out) >= limit:
                break
    return out


def style_preferences() -> dict[str, Any]:
    data = app_settings.load_settings()
    default_style = data.get("citation_default_style")
    default_locale = data.get("citation_default_locale")
    return {
        "default_style": default_style if default_style in STYLE_IDS else DEFAULT_STYLE,
        "default_locale": default_locale if default_locale in LOCALES else DEFAULT_LOCALE,
        "favorite_style_ids": _valid_ids(data.get("citation_favorite_styles")),
        "recent_style_ids": _valid_ids(data.get("citation_recent_styles"), limit=_MAX_RECENTS),
    }


def update_style_preferences(
    style_id: str,
    locale: str,
    *,
    favorite: bool | None = None,
    set_default: bool = False,
    mark_used: bool = False,
) -> dict[str, Any]:
    """Update one style's local state while preserving unrelated settings and bounding list growth."""
    if style_id not in STYLE_IDS:
        raise ValueError(f"unknown style: {style_id}")
    if locale not in LOCALES:
        raise ValueError(f"unknown locale: {locale}")
    data = app_settings.load_settings()
    favorites = _valid_ids(data.get("citation_favorite_styles"))
    recents = _valid_ids(data.get("citation_recent_styles"), limit=_MAX_RECENTS)
    if favorite is True and style_id not in favorites:
        favorites.append(style_id)
    elif favorite is False:
        favorites = [item for item in favorites if item != style_id]
    if mark_used:
        recents = [style_id, *(item for item in recents if item != style_id)][:_MAX_RECENTS]
    if set_default:
        data["citation_default_style"] = style_id
        data["citation_default_locale"] = locale
    data["citation_favorite_styles"] = favorites
    data["citation_recent_styles"] = recents
    app_settings.save_settings(data)
    return style_preferences()


def catalog_response(query: str = "") -> dict[str, Any]:
    prefs = style_preferences()
    favorites = set(prefs["favorite_style_ids"])
    recent_ranks = {style_id: index for index, style_id in enumerate(prefs["recent_style_ids"])}
    styles = []
    for style in list_catalog_styles(query):
        styles.append(
            {
                **style,
                "favorite": style["id"] in favorites,
                "recent_rank": recent_ranks.get(style["id"]),
                "application_default": style["id"] == prefs["default_style"],
            }
        )
    return {
        "styles": styles,
        "locales": list(LOCALES),
        **prefs,
    }


def preview_style(style_id: str, locale: str) -> dict[str, Any]:
    """Render fixed, explicitly fictional examples through the real citeproc engine."""
    if style_id not in STYLE_IDS:
        raise ValueError(f"unknown style: {style_id}")
    if locale not in LOCALES:
        raise ValueError(f"unknown locale: {locale}")
    rendered = render_document(_PREVIEW_CITATIONS, style=style_id, locale=locale)
    return {
        "style": style_id,
        "locale": locale,
        "example_only": True,
        "citations": [item["text"] for item in rendered["citations"]],
        "bibliography_text": rendered["bibliography_text"],
    }
