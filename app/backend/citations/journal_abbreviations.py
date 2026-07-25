"""Bounded journal-title abbreviation selection for citation rendering.

The user's embedded CSL records remain immutable. Each render operates on copies and
can retain library-provided short titles, prefer the bundled NLM MEDLINE catalog, or
remove short-title hints so citeproc falls back to the full journal title.
"""

from __future__ import annotations

import gzip
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any

MODES = ("library", "medline", "full")
DEFAULT_MODE = "library"
MAX_UNKNOWN_TITLES = 20
MAX_TITLE_LENGTH = 500
MAX_ABBREVIATION_LENGTH = 300
MAX_INDEX_COMPRESSED_BYTES = 2_000_000
MAX_INDEX_JSON_BYTES = 8_000_000
_DATA_FILE = Path(__file__).with_name("data") / "medline_journals.json.gz"
_CSL_NS = "{http://purl.org/net/xbiblio/csl}"
_ISSN_PATTERN = re.compile(r"\b[0-9]{4}-?[0-9]{3}[0-9Xx]\b")


def normalize_mode(value: str | None) -> str:
    mode = str(value or DEFAULT_MODE).strip().lower()
    if mode not in MODES:
        raise ValueError(f"journal abbreviation mode must be one of {', '.join(MODES)}")
    return mode


def _plain(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > limit or any(ord(char) < 32 for char in cleaned):
        return ""
    return cleaned


def _title_key(value: Any) -> str:
    title = _plain(value, MAX_TITLE_LENGTH)
    normalized = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", normalized).split())


def _issn_keys(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [
        match.replace("-", "").upper()
        for entry in values
        if isinstance(entry, str)
        for match in _ISSN_PATTERN.findall(entry)
    ]


@lru_cache(maxsize=1)
def medline_catalog() -> dict[str, Any]:
    if not _DATA_FILE.is_file() or _DATA_FILE.stat().st_size > MAX_INDEX_COMPRESSED_BYTES:
        raise RuntimeError("The bundled MEDLINE journal-abbreviation index is missing or invalid.")
    with gzip.open(_DATA_FILE, "rb") as stream:
        raw = stream.read(MAX_INDEX_JSON_BYTES + 1)
    if len(raw) > MAX_INDEX_JSON_BYTES:
        raise RuntimeError("The bundled MEDLINE journal-abbreviation index exceeds its safety bound.")
    data = json.loads(raw)
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("by_title"), dict)
        or not isinstance(data.get("by_issn"), dict)
    ):
        raise RuntimeError("The bundled MEDLINE journal-abbreviation index has an invalid shape.")
    return data


def _library_abbreviation(item: dict[str, Any]) -> str:
    return _plain(item.get("container-title-short"), MAX_ABBREVIATION_LENGTH) or _plain(
        item.get("journalAbbreviation"), MAX_ABBREVIATION_LENGTH
    )


def _medline_abbreviation(item: dict[str, Any], catalog: dict[str, Any]) -> str:
    by_issn = catalog["by_issn"]
    for issn in _issn_keys(item.get("ISSN")):
        if abbreviation := _plain(by_issn.get(issn), MAX_ABBREVIATION_LENGTH):
            return abbreviation
    return _plain(catalog["by_title"].get(_title_key(item.get("container-title"))), MAX_ABBREVIATION_LENGTH)


def style_requests_short_journal_titles(style_xml: str) -> bool:
    """Whether a CSL style contains a journal-title short-form request."""
    try:
        root = ET.fromstring(style_xml)
    except ET.ParseError:
        return False
    for node in root.iter(f"{_CSL_NS}text"):
        variables = set(str(node.get("variable") or "").split())
        if "container-title-short" in variables:
            return True
        if "container-title" in variables and node.get("form") == "short":
            return True
    return False


def apply_journal_abbreviations(
    items: list[dict[str, Any]],
    mode: str | None,
    *,
    style_xml: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return copied CSL items and an honest, bounded source/coverage summary."""
    selected = normalize_mode(mode)
    catalog = medline_catalog() if selected == "medline" else None
    transformed: list[dict[str, Any]] = []
    seen: set[str] = set()
    summary: dict[str, Any] = {
        "mode": selected,
        "style_requests_short_titles": style_requests_short_journal_titles(style_xml),
        "journal_count": 0,
        "abbreviated_count": 0,
        "medline_count": 0,
        "library_count": 0,
        "full_title_count": 0,
        "unknown_count": 0,
        "unknown_titles": [],
        "medline_last_modified": catalog.get("last_modified") if catalog is not None else None,
    }
    for original in items:
        item = dict(original)
        title = _plain(item.get("container-title"), MAX_TITLE_LENGTH)
        item_id = str(item.get("id") or "")
        count_item = bool(title) and item_id not in seen
        if item_id:
            seen.add(item_id)
        library = _library_abbreviation(item)
        abbreviation = ""
        source = ""
        if selected == "full":
            item.pop("container-title-short", None)
            item.pop("journalAbbreviation", None)
            if count_item:
                summary["full_title_count"] += 1
        else:
            if selected == "medline" and catalog is not None:
                abbreviation = _medline_abbreviation(item, catalog)
                source = "medline" if abbreviation else ""
            if not abbreviation and library:
                abbreviation = library
                source = "library"
            if abbreviation:
                item["container-title-short"] = abbreviation
                if count_item:
                    summary["abbreviated_count"] += 1
                    summary[f"{source}_count"] += 1
            else:
                item.pop("container-title-short", None)
                item.pop("journalAbbreviation", None)
                if count_item:
                    summary["unknown_count"] += 1
                    if len(summary["unknown_titles"]) < MAX_UNKNOWN_TITLES:
                        summary["unknown_titles"].append(title)
        if count_item:
            summary["journal_count"] += 1
        transformed.append(item)
    return transformed, summary
