"""Citation export — render stored paper metadata as BibTeX, RIS, or CSL-JSON (inc 70).

Pure functions over paper RowMappings (each carries the canonical `csl_json` plus the scalar projection
columns used as fallbacks). callosum is a reference manager you import INTO; this is the path back OUT.
Entirely local — it formats the user's own stored metadata, no egress. The renderers escape their output
format so a paper's own text can't break the structure.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.backend.metadata.abstract_display import abstract_plain_text

EXPORT_FORMATS = ("bibtex", "ris", "csl-json")

# CSL `type` → BibTeX entry type / RIS reference type.
_BIBTEX_ENTRY_TYPES = {
    "article-journal": "article",
    "article": "article",
    "paper-conference": "inproceedings",
    "book": "book",
    "chapter": "incollection",
    "thesis": "phdthesis",
    "report": "techreport",
}
_RIS_TYPES = {
    "article-journal": "JOUR",
    "article": "JOUR",
    "paper-conference": "CONF",
    "book": "BOOK",
    "chapter": "CHAP",
    "thesis": "THES",
    "report": "RPRT",
}


def render_citations(papers: Sequence[Mapping[str, Any]], fmt: str) -> tuple[str, str, str]:
    """Return (text, media_type, file_extension) for the chosen format. Raises ValueError on a bad format."""
    if fmt == "bibtex":
        return to_bibtex(papers), "application/x-bibtex; charset=utf-8", "bib"
    if fmt == "ris":
        return to_ris(papers), "application/x-research-info-systems; charset=utf-8", "ris"
    if fmt == "csl-json":
        return to_csl_json(papers), "application/json; charset=utf-8", "json"
    raise ValueError(f"Unknown export format: {fmt!r}")


# ── shared helpers ───────────────────────────────────────────────────────────


def _csl(paper: Mapping[str, Any]) -> dict:
    raw = paper.get("csl_json")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _year(paper: Mapping[str, Any], csl: Mapping[str, Any]) -> str | None:
    issued = csl.get("issued")
    if isinstance(issued, Mapping):
        parts = issued.get("date-parts")
        if isinstance(parts, Sequence) and parts and isinstance(parts[0], Sequence) and parts[0]:
            return str(parts[0][0])
    year = paper.get("year")
    return str(year) if year else None


def _authors(csl: Mapping[str, Any]) -> list[str]:
    """Each author as "Family, Given" (literal/organisation names kept verbatim)."""
    out: list[str] = []
    for entry in csl.get("author", []) or []:
        if not isinstance(entry, Mapping):
            continue
        literal = entry.get("literal")
        if literal:
            out.append(str(literal).strip())
            continue
        family, given = str(entry.get("family", "")).strip(), str(entry.get("given", "")).strip()
        if family and given:
            out.append(f"{family}, {given}")
        elif family or given:
            out.append(family or given)
    return out


def _field(paper: Mapping[str, Any], csl: Mapping[str, Any], csl_key: str, column: str | None = None) -> str | None:
    value = csl.get(csl_key)
    if value in (None, "") and column:
        value = paper.get(column)
    if value in (None, ""):
        return None
    return str(value).strip()


def _abstract(csl: Mapping[str, Any], paper: Mapping[str, Any]) -> str | None:
    raw = csl.get("abstract") or paper.get("abstract")
    return abstract_plain_text(raw) if raw else None


# ── BibTeX ───────────────────────────────────────────────────────────────────

_BIBTEX_ESCAPE = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}


def _bibtex_escape(text: str) -> str:
    return "".join(_BIBTEX_ESCAPE.get(ch, ch) for ch in text)


def _bibtex_key(paper: Mapping[str, Any], csl: Mapping[str, Any], used: set[str]) -> str:
    base = paper.get("citation_key")
    if not base:
        family = str(paper.get("first_author_family_name") or "").strip()
        if not family:
            authors = _authors(csl)
            family = authors[0].split(",")[0] if authors else "anon"
        base = f"{family}{_year(paper, csl) or ''}"
    key = re.sub(r"[^A-Za-z0-9]", "", str(base)) or "ref"
    candidate, suffix = key, ord("a")
    while candidate in used:  # dedupe collisions: key, keya, keyb, …
        candidate = f"{key}{chr(suffix)}"
        suffix += 1
    used.add(candidate)
    return candidate


def _bibtex_pages(page: str) -> str:
    return re.sub(r"\s*-+\s*", "--", page.strip())


def to_bibtex(papers: Sequence[Mapping[str, Any]]) -> str:
    used: set[str] = set()
    entries: list[str] = []
    for paper in papers:
        csl = _csl(paper)
        entry_type = _BIBTEX_ENTRY_TYPES.get(str(csl.get("type") or paper.get("item_type") or ""), "misc")
        key = _bibtex_key(paper, csl, used)
        fields: list[tuple[str, str]] = []
        authors = _authors(csl)
        if authors:
            fields.append(("author", " and ".join(authors)))
        title = _field(paper, csl, "title", "title")
        if title:
            fields.append(("title", "{" + _bibtex_escape(title) + "}"))  # extra braces preserve title case
        journal = _field(paper, csl, "container-title", "venue")
        if journal:
            fields.append(("journal", _bibtex_escape(journal)))
        year = _year(paper, csl)
        if year:
            fields.append(("year", year))
        for csl_key, bib_key, col in (
            ("volume", "volume", None),
            ("issue", "number", None),
            ("publisher", "publisher", None),
            ("DOI", "doi", "doi"),
            ("URL", "url", None),
            ("ISSN", "issn", None),
            ("ISBN", "isbn", None),
        ):
            value = _field(paper, csl, csl_key, col)
            if value:
                fields.append((bib_key, _bibtex_escape(value)))
        page = _field(paper, csl, "page")
        if page:
            fields.append(("pages", _bibtex_pages(page)))
        abstract = _abstract(csl, paper)
        if abstract:
            fields.append(("abstract", _bibtex_escape(abstract)))
        body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields)
        entries.append(f"@{entry_type}{{{key},\n{body}\n}}")
    return "\n\n".join(entries) + ("\n" if entries else "")


# ── RIS ──────────────────────────────────────────────────────────────────────


def _ris_line(tag: str, value: str) -> str:
    return f"{tag}  - {value}"


def to_ris(papers: Sequence[Mapping[str, Any]]) -> str:
    records: list[str] = []
    for paper in papers:
        csl = _csl(paper)
        lines = [_ris_line("TY", _RIS_TYPES.get(str(csl.get("type") or paper.get("item_type") or ""), "GEN"))]
        for author in _authors(csl):
            lines.append(_ris_line("AU", author))
        title = _field(paper, csl, "title", "title")
        if title:
            lines.append(_ris_line("TI", title))
        year = _year(paper, csl)
        if year:
            lines.append(_ris_line("PY", year))
        journal = _field(paper, csl, "container-title", "venue")
        if journal:
            lines.append(_ris_line("T2", journal))
        for csl_key, tag, col in (
            ("volume", "VL", None),
            ("issue", "IS", None),
            ("publisher", "PB", None),
            ("DOI", "DO", "doi"),
            ("URL", "UR", None),
            ("ISSN", "SN", None),
            ("ISBN", "SN", None),
        ):
            value = _field(paper, csl, csl_key, col)
            if value:
                lines.append(_ris_line(tag, value))
        page = _field(paper, csl, "page")
        if page:
            bounds = re.split(r"\s*-+\s*", page.strip(), maxsplit=1)
            lines.append(_ris_line("SP", bounds[0]))
            if len(bounds) > 1 and bounds[1]:
                lines.append(_ris_line("EP", bounds[1]))
        abstract = _abstract(csl, paper)
        if abstract:
            lines.append(_ris_line("AB", abstract.replace("\n", " ")))
        lines.append("ER  - ")
        records.append("\n".join(lines))
    return "\n\n".join(records) + ("\n" if records else "")


# ── CSL-JSON ─────────────────────────────────────────────────────────────────


def to_csl_json(papers: Sequence[Mapping[str, Any]]) -> str:
    """The canonical stored records verbatim — lossless and re-importable into CSL-aware tools."""
    return json.dumps([_csl(paper) for paper in papers], indent=2, ensure_ascii=False) + "\n"
