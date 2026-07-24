"""Installed CSL style paths and render-time resolution.

Bundled styles are immutable project assets. User-installed styles live beside app-settings.json, outside the
repository, and are addressed only by server-generated ids. This module contains no XML installation policy; it
only exposes already-installed files to the catalog and renderer.
"""

from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

from app.backend import app_settings
from app.backend.api.startup import PROJECT_ROOT

CSL_NAMESPACE = "http://purl.org/net/xbiblio/csl"
CSL_NS = {"csl": CSL_NAMESPACE}
MAX_CSL_BYTES = 1_000_000
STYLE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
PORTABLE_MARKER_MAX_BYTES = 180
_PORTABLE_MARKER = re.compile(
    r"\A(?P<prefix>\ufeff?\s*(?:<\?xml[^>]*\?>\s*)?)"
    r"<!-- callosum-style-id: (?P<style_id>custom-[a-z0-9][a-z0-9-]{0,112}) -->\s*"
)

BUILTIN_STYLES: list[dict[str, str]] = [
    {"id": "apa", "title": "APA (7th edition)", "family": "author-date"},
    {"id": "modern-language-association", "title": "MLA (9th edition)", "family": "author-date"},
    {"id": "chicago-author-date", "title": "Chicago (author-date, 18th)", "family": "author-date"},
    {"id": "chicago-notes-bibliography", "title": "Chicago (notes & bibliography, 18th)", "family": "note"},
    {"id": "harvard-cite-them-right", "title": "Harvard — Cite Them Right (12th)", "family": "author-date"},
    {"id": "ieee", "title": "IEEE", "family": "numeric"},
    {"id": "nature", "title": "Nature", "family": "numeric"},
]
BUILTIN_STYLE_IDS = {style["id"] for style in BUILTIN_STYLES}
_BUNDLED_DIR = PROJECT_ROOT / "app" / "backend" / "citations" / "csl" / "styles"


def custom_styles_dir() -> Path:
    """User style directory, colocated with the overridable local settings store."""
    return app_settings.settings_path().parent / "citation-styles"


def _custom_paths() -> list[Path]:
    directory = custom_styles_dir()
    try:
        return sorted(
            path
            for path in directory.glob("custom-*.csl")
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_CSL_BYTES
        )
    except OSError:
        return []


def installed_style_paths() -> list[tuple[str, Path, bool]]:
    rows = [(style["id"], _BUNDLED_DIR / f"{style['id']}.csl", False) for style in BUILTIN_STYLES]
    rows.extend((path.stem, path, True) for path in _custom_paths() if STYLE_ID_PATTERN.fullmatch(path.stem))
    return rows


def style_path(style_id: str) -> Path | None:
    if not STYLE_ID_PATTERN.fullmatch(str(style_id or "")):
        return None
    if style_id in BUILTIN_STYLE_IDS:
        path = _BUNDLED_DIR / f"{style_id}.csl"
    elif style_id.startswith("custom-"):
        path = custom_styles_dir() / f"{style_id}.csl"
        if path.is_symlink():
            return None
    else:
        return None
    try:
        return path if path.is_file() and path.stat().st_size <= MAX_CSL_BYTES else None
    except OSError:
        return None


def style_exists(style_id: str) -> bool:
    return style_path(style_id) is not None


def installed_style_ids() -> set[str]:
    return {style_id for style_id, _, _ in installed_style_paths()}


def style_root(path: Path) -> ET.Element:
    xml = path.read_text(encoding="utf-8")
    if len(xml.encode("utf-8")) > MAX_CSL_BYTES:
        raise ValueError("installed citation style is too large")
    folded = xml.casefold()
    if "<!doctype" in folded or "<!entity" in folded:
        raise ValueError("installed citation style contains a forbidden DTD or entity declaration")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError("installed citation style contains invalid XML") from exc
    if root.tag != f"{{{CSL_NAMESPACE}}}style":
        raise ValueError("installed citation style has an invalid root element")
    return root


def canonical_id(path: Path) -> str:
    info = style_root(path).find("csl:info", CSL_NS)
    node = info.find("csl:id", CSL_NS) if info is not None else None
    return " ".join((node.text or "").split()) if node is not None else ""


def canonical_index() -> dict[str, tuple[str, Path, bool]]:
    out: dict[str, tuple[str, Path, bool]] = {}
    for style_id, path, custom in installed_style_paths():
        try:
            value = canonical_id(path)
        except (OSError, ET.ParseError, ValueError):
            continue
        if value:
            out[value] = (style_id, path, custom)
    return out


def parent_canonical_id(path: Path) -> str | None:
    info = style_root(path).find("csl:info", CSL_NS)
    if info is None:
        return None
    for link in info.findall("csl:link", CSL_NS):
        if link.get("rel") == "independent-parent":
            return (link.get("href") or "").strip() or None
    return None


def render_style_xml(style_id: str) -> str:
    """Return independent CSL XML for an installed style, resolving a dependent style by canonical parent id."""
    path = style_path(style_id)
    if path is None:
        raise ValueError(f"unknown style: {style_id}")
    seen: set[str] = set()
    for _ in range(5):
        canonical = canonical_id(path)
        if canonical in seen:
            raise ValueError("citation style dependency is circular")
        seen.add(canonical)
        parent = parent_canonical_id(path)
        if not parent:
            style_root(path)
            return path.read_text(encoding="utf-8")
        match = canonical_index().get(parent)
        if match is None:
            raise ValueError(f"citation style requires an uninstalled parent: {parent}")
        path = match[1]
    raise ValueError("citation style dependency chain is too deep")


def strip_portable_marker(xml: str) -> tuple[str, str | None]:
    """Remove Callosum's export-only id marker and return its constrained preferred local id."""
    match = _PORTABLE_MARKER.match(xml)
    if match is None:
        if "callosum-style-id:" in xml:
            raise ValueError("The Callosum style-id marker is malformed or misplaced")
        return xml, None
    normalized = match.group("prefix") + xml[match.end() :]
    return normalized, match.group("style_id")


def export_style_xml(style_id: str) -> str:
    """Return a custom style with a portable local-id marker in the XML prolog."""
    path = style_path(style_id)
    if path is None:
        raise FileNotFoundError(f"unknown citation style: {style_id}")
    if style_id in BUILTIN_STYLE_IDS:
        raise ValueError("Bundled citation styles cannot be exported as personal styles")
    xml, _ = strip_portable_marker(path.read_text(encoding="utf-8"))
    declaration = re.match(r"\A(\ufeff?\s*<\?xml[^>]*\?>)(\s*)", xml)
    marker = f"<!-- callosum-style-id: {style_id} -->"
    if declaration is None:
        return f"{marker}\n{xml}"
    return f"{declaration.group(1)}\n{marker}{declaration.group(2)}{xml[declaration.end() :]}"


def custom_style_id(canonical: str, preferred: str | None = None) -> str:
    parsed = urlparse(canonical)
    raw = parsed.path.rstrip("/").rsplit("/", 1)[-1] or parsed.netloc or "style"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.casefold()).strip("-")[:80] or "style"
    used = installed_style_ids()
    if (
        preferred
        and preferred.startswith("custom-")
        and STYLE_ID_PATTERN.fullmatch(preferred)
        and preferred not in used
    ):
        return preferred
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    for length in (8, 12, 16, 24, 32):
        candidate = f"custom-{slug[: 111 - length]}-{digest[:length]}"
        if candidate not in used:
            return candidate
    raise ValueError("Could not allocate a unique custom style id")


def write_custom_style(style_id: str, xml: str) -> Path:
    if not style_id.startswith("custom-") or not STYLE_ID_PATTERN.fullmatch(style_id):
        raise ValueError("invalid custom style id")
    directory = custom_styles_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{style_id}.csl"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(xml, encoding="utf-8")
    os.replace(tmp, path)
    return path


def remove_custom_style(style_id: str) -> None:
    if style_id in BUILTIN_STYLE_IDS:
        raise ValueError("Bundled citation styles cannot be removed")
    path = style_path(style_id)
    if path is None or not style_id.startswith("custom-"):
        raise FileNotFoundError(f"unknown personal citation style: {style_id}")
    path.unlink()
