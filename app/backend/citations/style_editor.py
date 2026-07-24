"""Revision-safe source editing for independent personal CSL styles."""

from __future__ import annotations

import hashlib
import threading
from typing import Any

from app.backend.citations import style_provenance, style_store
from app.backend.citations.style_manager import candidate_source_metadata, preview_style_xml

_lock = threading.RLock()


class StyleEditConflict(RuntimeError):
    """The installed source changed after the editor loaded it."""


def _editable_source(style_id: str) -> tuple[Any, str]:
    path = style_store.style_path(style_id)
    if path is None:
        raise FileNotFoundError(f"unknown citation style: {style_id}")
    if style_id in style_store.BUILTIN_STYLE_IDS or not style_id.startswith("custom-"):
        raise ValueError("Duplicate this bundled citation style before editing it")
    if style_store.parent_canonical_id(path):
        raise ValueError("Duplicate this dependent citation style before editing it")
    source, _ = style_store.strip_portable_marker(path.read_text(encoding="utf-8"))
    return path, source


def _revision(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _title(path) -> str:
    info = style_store.style_root(path).find("csl:info", style_store.CSL_NS)
    node = info.find("csl:title", style_store.CSL_NS) if info is not None else None
    return " ".join((node.text or "").split()) if node is not None else ""


def style_source(style_id: str) -> dict[str, Any]:
    """Return exact editable XML and its optimistic-concurrency revision."""
    with _lock:
        path, source = _editable_source(style_id)
        return {
            "style_id": style_id,
            "full_title": _title(path),
            "canonical_id": style_store.canonical_id(path),
            "csl": source,
            "revision": _revision(source),
        }


def _validated_edit(style_id: str, source: str, locale: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    current = style_source(style_id)
    candidate = candidate_source_metadata(f"{style_id}.csl", source)
    if candidate["parent_canonical_id"]:
        raise ValueError("An edited personal style must remain independent")
    if candidate["canonical_id"] != current["canonical_id"]:
        raise ValueError("The CSL id cannot change while editing an installed style")
    normalized = str(candidate["csl"])
    preview = preview_style_xml(normalized, locale)
    return normalized, current, preview


def validate_style_edit(style_id: str, source: str, locale: str) -> dict[str, Any]:
    """Validate and render an unsaved edit without touching the installed file."""
    normalized, current, preview = _validated_edit(style_id, source, locale)
    return {
        "valid": True,
        "revision": current["revision"],
        "normalized_csl": normalized,
        "preview": preview,
    }


def save_style_edit(style_id: str, source: str, expected_revision: str, locale: str) -> dict[str, Any]:
    """Atomically replace one personal style if its exact loaded revision is still current."""
    with _lock:
        _, previous = _editable_source(style_id)
        if _revision(previous) != expected_revision:
            raise StyleEditConflict("The citation style changed after this editor was opened; reload before saving")
        normalized, _, preview = _validated_edit(style_id, source, locale)
        _, latest = _editable_source(style_id)
        if _revision(latest) != expected_revision:
            raise StyleEditConflict("The citation style changed during validation; reload before saving")
        previous = latest
        saved = normalized != previous
        if saved:
            style_store.write_custom_style(style_id, normalized)
            try:
                style_provenance.record_edit(style_id)
            except Exception:
                style_store.write_custom_style(style_id, previous)
                raise
        return {
            "saved": saved,
            "source": style_source(style_id),
            "preview": preview,
        }
