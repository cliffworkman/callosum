"""Explicit remote update checks and independent personal-style duplication."""

from __future__ import annotations

import copy
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from app.backend.citations import style_provenance, style_store
from app.backend.citations.style_manager import install_style, list_catalog_styles
from app.backend.citations.style_repository import prepare_repository_style, prepare_style_from_url

_NS = style_store.CSL_NAMESPACE
_Q = f"{{{_NS}}}"


def check_style_update(style_id: str) -> dict[str, Any]:
    if style_store.style_path(style_id) is None:
        raise FileNotFoundError(f"unknown citation style: {style_id}")
    provenance = style_provenance.provenance_for(style_id)
    if provenance is None or provenance["source_type"] not in {"repository", "url"}:
        raise ValueError("This citation style has no remote source to check")
    if provenance["source_type"] == "repository":
        source = provenance.get("repository_id")
        if not source:
            raise ValueError("This citation style's repository source is incomplete")
        prepared = prepare_repository_style(source, refresh_installed_parents=True)
        install_path = "/citations/styles/repository/install"
        install_body = {"repository_id": source}
    else:
        source = provenance.get("source_url")
        if not source:
            raise ValueError("This citation style's URL source is incomplete")
        prepared = prepare_style_from_url(source, refresh_installed_parents=True)
        install_path = "/citations/styles/url/install"
        install_body = {"url": source}
    if prepared["style"]["id"] != style_id:
        raise ValueError("The remote citation style identity no longer matches the installed style")
    checked = style_provenance.record_check(
        style_id,
        upstream_updated=prepared.get("upstream_updated"),
    )
    update_available = prepared["action"] == "update_available"
    return {
        "status": "update_available" if update_available else "current",
        "style_id": style_id,
        "checked_at": checked["last_checked_at"],
        "upstream_updated": prepared.get("upstream_updated"),
        "source": checked,
        "install": (
            {
                "path": install_path,
                "body": install_body,
                "preflight_token": prepared["token"],
            }
            if update_available
            else None
        ),
    }


def _source_info(style_id: str) -> tuple[ET.Element, str, str]:
    path = style_store.style_path(style_id)
    if path is None:
        raise FileNotFoundError(f"unknown citation style: {style_id}")
    source_root = style_store.style_root(path)
    source_info = source_root.find("csl:info", style_store.CSL_NS)
    if source_info is None:
        raise ValueError("The citation style has no CSL info section")
    metadata = next((row for row in list_catalog_styles() if row["id"] == style_id), None)
    if metadata is None:
        raise ValueError("The citation style metadata could not be read")
    return source_info, metadata["full_title"], metadata["canonical_id"]


def _copy_info(source_info: ET.Element, title: str, canonical: str, template: str) -> ET.Element:
    info = copy.deepcopy(source_info)
    for link in list(info.findall("csl:link", style_store.CSL_NS)):
        if link.get("rel") in {"self", "independent-parent"}:
            info.remove(link)
    title_node = info.find("csl:title", style_store.CSL_NS)
    id_node = info.find("csl:id", style_store.CSL_NS)
    updated_node = info.find("csl:updated", style_store.CSL_NS)
    if title_node is None or id_node is None or updated_node is None:
        raise ValueError("The citation style info section is incomplete")
    title_node.text = title
    id_node.text = canonical
    updated_node.text = datetime.now(timezone.utc).isoformat(timespec="seconds")
    short_title = info.find("csl:title-short", style_store.CSL_NS)
    if short_title is not None:
        short_title.text = title
    self_link = ET.Element(f"{_Q}link", {"href": canonical, "rel": "self"})
    info.insert(list(info).index(id_node) + 1, self_link)
    if template:
        template_link = ET.Element(f"{_Q}link", {"href": template, "rel": "template"})
        info.insert(list(info).index(self_link) + 1, template_link)
    return info


def duplicate_style(style_id: str, title: str | None = None) -> dict[str, Any]:
    source_info, source_title, source_canonical = _source_info(style_id)
    duplicate_title = " ".join(str(title or "").split()) or f"{source_title[:293]} - Copy"
    if len(duplicate_title) > 300:
        raise ValueError("The citation style title is too long (max 300 characters)")
    canonical = f"https://callosum.local/styles/{uuid.uuid4()}"
    effective_root = ET.fromstring(style_store.render_style_xml(style_id))
    effective_info = effective_root.find("csl:info", style_store.CSL_NS)
    if effective_info is None:
        raise ValueError("The effective citation style has no CSL info section")
    index = list(effective_root).index(effective_info)
    effective_root.remove(effective_info)
    effective_root.insert(index, _copy_info(source_info, duplicate_title, canonical, source_canonical))
    ET.register_namespace("", _NS)
    xml = ET.tostring(effective_root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    result = install_style(
        f"{duplicate_title}.csl",
        xml,
        provenance={
            "source_type": "duplicate",
            "source_style_id": style_id,
            "source_canonical_id": source_canonical,
        },
    )
    if result["action"] != "installed":
        raise RuntimeError("The personal citation-style copy was not created")
    return result
