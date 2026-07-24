"""Searchable CSL style catalog, local preferences, and deterministic previews.

The bundled CSL files remain the source of truth. Metadata is parsed with ElementTree rather than duplicated in
UI code; favorites, recents, and the application default are local non-secret preferences in app-settings.json.
No network or LLM is involved.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

from app.backend import app_settings
from app.backend.citations import style_provenance, style_store
from app.backend.citations.render import (
    DEFAULT_LOCALE,
    DEFAULT_STYLE,
    LOCALES,
    STYLES,
    render_document,
    validate_style_xml,
)
from app.backend.citations.style_validator import validate_csl_schema

_CSL_NS = style_store.CSL_NS
_MAX_RECENTS = 8
MAX_STYLE_QUERY = 120
MAX_CSL_BYTES = style_store.MAX_CSL_BYTES
_MAX_CSL_ELEMENTS = 20_000
_MAX_CSL_DEPTH = 100

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


class StyleUpdateRequired(ValueError):
    def __init__(self, style_id: str, title: str) -> None:
        super().__init__(f"{title} is already installed with different CSL content")
        self.style_id = style_id
        self.title = title


class StyleRemovalRefused(ValueError):
    pass


def _style_metadata(
    style_id: str,
    path,
    *,
    custom: bool,
    manifest: dict[str, str] | None = None,
) -> dict[str, Any]:
    root = style_store.style_root(path)
    info = root.find("csl:info", _CSL_NS)
    categories = info.findall("csl:category", _CSL_NS) if info is not None else []
    fields = sorted({category.get("field", "") for category in categories if category.get("field")})
    citation_format = next(
        (category.get("citation-format", "") for category in categories if category.get("citation-format")),
        "",
    )
    parent_canonical = next(
        (
            (link.get("href") or "").strip()
            for link in (info.findall("csl:link", _CSL_NS) if info is not None else [])
            if link.get("rel") == "independent-parent"
        ),
        None,
    )
    parent_match = style_store.canonical_index().get(parent_canonical) if parent_canonical else None
    parent = parent_match[0] if parent_match else (parent_canonical or "").rsplit("/", 1)[-1] or None
    parent_root = style_store.style_root(parent_match[1]) if parent_match else None
    parent_info = parent_root.find("csl:info", _CSL_NS) if parent_root is not None else None
    parent_categories = parent_info.findall("csl:category", _CSL_NS) if parent_info is not None else []
    parent_format = next(
        (category.get("citation-format", "") for category in parent_categories if category.get("citation-format")),
        "",
    )
    title = _text(info, "title") or (manifest or {}).get("title") or style_id
    short_title = _text(info, "title-short")
    summary = _text(info, "summary")
    canonical = _text(info, "id")
    style_class = parent_root.get("class") if parent_root is not None else root.get("class")
    family = (
        "note"
        if style_class == "note"
        else (manifest or {}).get("family") or citation_format or parent_format or "in-text"
    )
    searchable = " ".join(
        [
            style_id,
            (manifest or {}).get("title", ""),
            title,
            short_title,
            summary,
            citation_format,
            *fields,
            *(field.replace("_", " ") for field in fields),
        ]
    ).casefold()
    provenance = (style_provenance.provenance_for(style_id) if custom else {"source_type": "bundled"}) or {
        "source_type": "personal"
    }
    return {
        "id": style_id,
        "title": (manifest or {}).get("title") or title,
        "family": family,
        "full_title": title,
        "short_title": short_title,
        "summary": summary,
        "citation_format": citation_format or parent_format or family,
        "fields": fields,
        "independent": parent is None,
        "parent_style": parent,
        "default_locale": root.get("default-locale") or "",
        "installed": True,
        "custom": custom,
        "source": "custom" if custom else "bundled",
        "provenance": provenance,
        "canonical_id": canonical,
        "updated": _text(info, "updated"),
        "_searchable": searchable,
    }


def _catalog() -> tuple[dict[str, Any], ...]:
    manifests = {manifest["id"]: manifest for manifest in STYLES}
    rows = []
    for style_id, path, custom in style_store.installed_style_paths():
        try:
            rows.append(_style_metadata(style_id, path, custom=custom, manifest=manifests.get(style_id)))
        except (OSError, ET.ParseError, ValueError):
            continue
    return tuple(rows)


def _installed_ids() -> set[str]:
    return {style["id"] for style in _catalog()}


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
    installed = _installed_ids()
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item in installed and item not in out:
            out.append(item)
            if limit is not None and len(out) >= limit:
                break
    return out


def style_preferences() -> dict[str, Any]:
    data = app_settings.load_settings()
    installed = _installed_ids()
    default_style = data.get("citation_default_style")
    default_locale = data.get("citation_default_locale")
    return {
        "default_style": default_style if default_style in installed else DEFAULT_STYLE,
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
    if style_id not in _installed_ids():
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
    if style_id not in _installed_ids():
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


def _parse_candidate(
    filename: str,
    xml: str,
    *,
    available_parent_canonicals: frozenset[str] = frozenset(),
    allow_uninstalled_parent: bool = False,
) -> tuple[ET.Element, str, str, str | None, str, str | None]:
    clean_name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if not clean_name.casefold().endswith(".csl"):
        raise ValueError("Choose a .csl citation style file")
    if not isinstance(xml, str) or not xml.strip():
        raise ValueError("The CSL file is empty")
    xml, preferred_id = style_store.strip_portable_marker(xml)
    if len(xml.encode("utf-8")) > MAX_CSL_BYTES:
        raise ValueError(f"The CSL file is too large (max {MAX_CSL_BYTES // 1000} KB)")
    folded = xml.casefold()
    if "<!doctype" in folded or "<!entity" in folded:
        raise ValueError("CSL files may not contain DTD or entity declarations")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML: {exc}") from exc
    count = 0
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > _MAX_CSL_ELEMENTS:
            raise ValueError(f"The CSL file has too many XML elements (max {_MAX_CSL_ELEMENTS})")
        if depth > _MAX_CSL_DEPTH:
            raise ValueError(f"The CSL XML is nested too deeply (max {_MAX_CSL_DEPTH} levels)")
        stack.extend((child, depth + 1) for child in node)
    if root.tag != f"{{{style_store.CSL_NAMESPACE}}}style":
        raise ValueError("The root element must be a CSL <style> in the CSL namespace")
    style_class = root.get("class")
    version = (root.get("version") or "").strip()
    if not version.startswith("1.0"):
        raise ValueError("The CSL style version must be CSL 1.0.x")
    info = root.find("csl:info", _CSL_NS)
    title = _text(info, "title")
    canonical = _text(info, "id")
    if not title:
        raise ValueError("The CSL <info> section needs a title")
    if len(title) > 300:
        raise ValueError("The CSL title is too long (max 300 characters)")
    parsed = urlparse(canonical)
    if len(canonical) > 500 or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The CSL <info> id must be an http(s) URL")
    parent = next(
        (
            (link.get("href") or "").strip()
            for link in (info.findall("csl:link", _CSL_NS) if info is not None else [])
            if link.get("rel") == "independent-parent"
        ),
        None,
    )
    if parent:
        if style_class not in {None, "in-text", "note"}:
            raise ValueError("The CSL style class must be in-text or note")
        if (
            not allow_uninstalled_parent
            and parent not in style_store.canonical_index()
            and parent not in available_parent_canonicals
        ):
            raise ValueError(f"This dependent CSL style requires an uninstalled parent: {parent}")
    else:
        if style_class not in {"in-text", "note"}:
            raise ValueError("The CSL style class must be in-text or note")
        citation = root.find("csl:citation", _CSL_NS)
        if citation is None or citation.find("csl:layout", _CSL_NS) is None:
            raise ValueError("An independent CSL style needs a citation layout")
    validate_csl_schema(xml)
    if not parent:
        validate_style_xml(xml)
    return root, title, canonical, parent, xml, preferred_id


def candidate_source_metadata(filename: str, xml: str) -> dict[str, str | None]:
    """Validate one fetched candidate and expose only the identity needed to resolve its parent chain."""
    root, title, canonical, parent, normalized_xml, _ = _parse_candidate(
        filename,
        xml,
        allow_uninstalled_parent=True,
    )
    info = root.find("csl:info", _CSL_NS)
    return {
        "title": title,
        "canonical_id": canonical,
        "parent_canonical_id": parent,
        "updated": _text(info, "updated") or None,
        "csl": normalized_xml,
    }


def _inspect_candidate(
    filename: str,
    xml: str,
    *,
    available_parent_canonicals: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], str]:
    _, title, canonical, _, normalized_xml, preferred_id = _parse_candidate(
        filename,
        xml,
        available_parent_canonicals=available_parent_canonicals,
    )
    existing = style_store.canonical_index().get(canonical)
    if existing is not None:
        style_id, path, custom = existing
        if not custom:
            raise ValueError(f"{title} duplicates a bundled style and cannot replace it")
        try:
            current = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError("The installed CSL style could not be read") from exc
        current, _ = style_store.strip_portable_marker(current)
        if current == normalized_xml:
            action = "already_installed"
        else:
            action = "update_available"
    else:
        style_id = style_store.custom_style_id(canonical, preferred_id)
        action = "ready"
    return {
        "action": action,
        "style": {
            "id": style_id,
            "full_title": title,
            "canonical_id": canonical,
        },
    }, normalized_xml


def inspect_style_install(
    filename: str,
    xml: str,
    *,
    available_parent_canonicals: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Validate a candidate and report the non-mutating install action it would require."""
    inspection, _ = _inspect_candidate(
        filename,
        xml,
        available_parent_canonicals=available_parent_canonicals,
    )
    return inspection


def install_style(
    filename: str,
    xml: str,
    *,
    replace: bool = False,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and atomically install or update one local CSL file."""
    inspection, normalized_xml = _inspect_candidate(filename, xml)
    action = inspection["action"]
    style_id = inspection["style"]["id"]
    title = inspection["style"]["full_title"]
    if action == "update_available" and not replace:
        raise StyleUpdateRequired(style_id, title)
    prior_xml: str | None = None
    if action == "update_available":
        prior_path = style_store.style_path(style_id)
        prior_xml = prior_path.read_text(encoding="utf-8") if prior_path else None
    if action in {"ready", "update_available"}:
        style_store.write_custom_style(style_id, normalized_xml)
        final_action = "installed" if action == "ready" else "updated"
        if provenance:
            try:
                style_provenance.record_install(style_id, **provenance)
            except Exception:
                if prior_xml is None:
                    try:
                        style_store.remove_custom_style(style_id)
                    except (FileNotFoundError, OSError, ValueError):
                        pass
                else:
                    style_store.write_custom_style(style_id, prior_xml)
                raise
        action = final_action
    style = next((row for row in list_catalog_styles() if row["id"] == style_id), None)
    if style is None:
        raise RuntimeError("The CSL style was written but could not be reopened")
    return {"action": action, "style": style}


def export_style(style_id: str) -> str:
    """Export one personal style with its portable Callosum id marker."""
    return style_store.export_style_xml(style_id)


def remove_style(style_id: str) -> dict[str, Any]:
    """Remove one non-default personal style without orphaning installed dependents."""
    path = style_store.style_path(style_id)
    if path is None:
        raise FileNotFoundError(f"unknown citation style: {style_id}")
    if style_id in style_store.BUILTIN_STYLE_IDS:
        raise StyleRemovalRefused("Bundled citation styles cannot be removed")
    prefs = style_preferences()
    if prefs["default_style"] == style_id:
        raise StyleRemovalRefused("Choose another application default before removing this personal style")
    canonical = style_store.canonical_id(path)
    dependents: list[str] = []
    for candidate_id, candidate_path, _ in style_store.installed_style_paths():
        if candidate_id == style_id:
            continue
        try:
            if style_store.parent_canonical_id(candidate_path) == canonical:
                dependents.append(candidate_id)
        except (OSError, ET.ParseError, ValueError):
            continue
    if dependents:
        raise StyleRemovalRefused("Remove dependent citation styles first: " + ", ".join(sorted(dependents)))
    data = app_settings.load_settings()
    original = dict(data)
    preferences_changed = False
    for key in ("citation_favorite_styles", "citation_recent_styles"):
        values = data.get(key)
        if isinstance(values, list):
            cleaned = [item for item in values if item != style_id]
            if cleaned != values:
                data[key] = cleaned
                preferences_changed = True
    if preferences_changed:
        app_settings.save_settings(data)
    try:
        style_store.remove_custom_style(style_id)
    except (OSError, ValueError):
        if preferences_changed:
            try:
                app_settings.save_settings(original)
            except OSError:
                pass
        raise
    try:
        style_provenance.remove_provenance(style_id)
    except OSError:
        pass
    return catalog_response()
