"""Citation import — parse a BibTeX / RIS / CSL-JSON file into library papers (inc 93).

The inverse of `citation_export` (inc 70): the user exports OUT, this brings a citation file back IN. Parsers are
**hand-rolled, no new dependency** (the project ethos — cf. inc-75's hand-rolled arXiv parser) and **defensive**:
a malformed entry is skipped and counted, never fatal. Each parser produces a **CSL-shaped dict**; one inverse
mapping (`csl_record_to_paper_fields`) turns that into `create_paper` kwargs. Entirely **local — no egress**
(nothing is fetched; the file's metadata is authoritative). Dedup reuses `find_existing_paper_by_identity`.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import Connection

from app.backend.persistence.repository import create_paper, find_existing_paper_by_identity

IMPORT_FORMATS = ("bibtex", "ris", "csl-json")

_log = logging.getLogger("callosum.citation_import")
MAX_IMPORT_BYTES = 5_000_000  # ~5 MB — bound resource use on an untrusted file (rule #4)
MAX_IMPORT_RECORDS = 5000  # bound the number of papers one import can create

# Reverse of citation_export's CSL→BibTeX / CSL→RIS type maps (canonical CSL type per source type).
_BIBTEX_TO_CSL_TYPE = {
    "article": "article-journal",
    "inproceedings": "paper-conference",
    "conference": "paper-conference",
    "book": "book",
    "incollection": "chapter",
    "inbook": "chapter",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "techreport": "report",
}
_RIS_TO_CSL_TYPE = {
    "JOUR": "article-journal",
    "CONF": "paper-conference",
    "CPAPER": "paper-conference",
    "BOOK": "book",
    "CHAP": "chapter",
    "THES": "thesis",
    "RPRT": "report",
}
_BIBTEX_UNESCAPE = (("\\&", "&"), ("\\%", "%"), ("\\$", "$"), ("\\#", "#"), ("\\_", "_"))
_RIS_TAG_RE = re.compile(r"^([A-Z][A-Z0-9])  -\s?(.*)$")


def detect_format(content: str) -> str | None:
    """Sniff the citation format from the content. Returns a member of IMPORT_FORMATS, or None if unrecognised."""
    stripped = content.lstrip()
    if not stripped:
        return None
    if stripped[0] in "[{":
        return "csl-json"
    if stripped[0] == "@":
        return "bibtex"
    for line in content.splitlines():
        if _RIS_TAG_RE.match(line):
            return "ris"
        if line.strip():
            break
    return "bibtex" if "@" in stripped[:200] else None


# ── shared helpers ───────────────────────────────────────────────────────────


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _issued(year: int | None) -> dict | None:
    return {"date-parts": [[year]]} if year else None


def _year_int(raw: Any) -> int | None:
    match = re.search(r"\d{4}", str(raw or ""))
    return int(match.group(0)) if match else None


def _parse_name(raw: str) -> dict[str, str]:
    """A single author name → a CSL author dict. Braced groups = organisation literals; "Family, Given" and
    "Given Family" both handled."""
    name = raw.strip()
    if name.startswith("{") and name.endswith("}"):
        return {"literal": name[1:-1].strip()}
    name = name.replace("{", "").replace("}", "")
    if "," in name:
        family, given = name.split(",", 1)
        return {"family": family.strip(), "given": given.strip()}
    parts = name.split()
    if len(parts) <= 1:
        return {"family": name}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def _split_authors(field: str) -> list[dict[str, str]]:
    names = re.split(r"\s+and\s+", field, flags=re.IGNORECASE)
    return [_parse_name(n) for n in names if n.strip()]


# ── BibTeX ───────────────────────────────────────────────────────────────────


def _strip_outer(raw: str) -> str:
    """Remove one outer {…} or "…" delimiter level, keeping inner braces (author literals need them)."""
    value = raw.strip()
    if len(value) >= 2 and ((value[0] == "{" and value[-1] == "}") or (value[0] == '"' and value[-1] == '"')):
        return value[1:-1].strip()
    return value


def _clean_bibtex_value(raw: str) -> str:
    value = _strip_outer(raw).replace("{", "").replace("}", "")
    for esc, char in _BIBTEX_UNESCAPE:
        value = value.replace(esc, char)
    return re.sub(r"\s+", " ", value).strip()


def _split_bibtex_fields(body: str) -> list[str]:
    """Split an entry body on top-level commas (commas inside {…} or "…" are kept)."""
    segments: list[str] = []
    depth = 0
    in_quote = False
    buf: list[str] = []
    for char in body:
        if char == "{" and not in_quote:
            depth += 1
            buf.append(char)
        elif char == "}" and not in_quote:
            depth = max(0, depth - 1)
            buf.append(char)
        elif char == '"' and depth == 0:
            in_quote = not in_quote
            buf.append(char)
        elif char == "," and depth == 0 and not in_quote:
            segments.append("".join(buf))
            buf = []
        else:
            buf.append(char)
    if "".join(buf).strip():
        segments.append("".join(buf))
    return segments


def _bibtex_entry_to_csl(entry_type: str, body: str) -> dict | None:
    segments = _split_bibtex_fields(body)
    if not segments:
        return None
    rec: dict[str, Any] = {"type": _BIBTEX_TO_CSL_TYPE.get(entry_type, "document")}
    citation_key = segments[0].strip()
    if citation_key and "=" not in citation_key:
        rec["id"] = citation_key
    raw_fields: dict[str, str] = {}
    for segment in segments[1:]:
        if "=" not in segment:
            continue
        name, value = segment.split("=", 1)
        raw_fields[name.strip().lower()] = value.strip()  # RAW (braces intact — author literals need them)
    if "author" in raw_fields:
        rec["author"] = _split_authors(_strip_outer(raw_fields["author"]))
    title = _clean_bibtex_value(raw_fields["title"]) if raw_fields.get("title") else None
    if title:
        rec["title"] = title
    journal_raw = raw_fields.get("journal") or raw_fields.get("booktitle")
    if journal_raw:
        rec["container-title"] = _clean_bibtex_value(journal_raw)
    issued = _issued(_year_int(raw_fields.get("year")))
    if issued:
        rec["issued"] = issued
    for src, dst in (
        ("volume", "volume"),
        ("number", "issue"),
        ("publisher", "publisher"),
        ("doi", "DOI"),
        ("url", "URL"),
        ("issn", "ISSN"),
        ("isbn", "ISBN"),
        ("abstract", "abstract"),
    ):
        if raw_fields.get(src):
            rec[dst] = _clean_bibtex_value(raw_fields[src])
    if raw_fields.get("pages"):
        rec["page"] = re.sub(r"\s*-+\s*", "-", _clean_bibtex_value(raw_fields["pages"]))
    return rec if (rec.get("title") or rec.get("DOI")) else None


def parse_bibtex(text: str) -> tuple[list[dict], int]:
    """→ (CSL records, count of entries dropped for having no title AND no DOI). The skip count lets the import
    report which entries silently vanished at parse (inc 173), instead of only the survivors."""
    records: list[dict] = []
    skipped = 0
    i, n = 0, len(text)
    while i < n:
        at = text.find("@", i)
        if at == -1:
            break
        j = at + 1
        while j < n and text[j].isalnum():
            j += 1
        entry_type = text[at + 1 : j].strip().lower()
        while j < n and text[j].isspace():
            j += 1
        if j >= n or text[j] != "{":  # only brace-delimited entries (the standard exporter form)
            i = at + 1
            continue
        depth, k = 1, j + 1
        while k < n and depth > 0:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        body = text[j + 1 : k - 1]
        i = k
        if entry_type in ("comment", "preamble", "string"):
            continue
        try:
            rec = _bibtex_entry_to_csl(entry_type, body)
        except Exception:
            rec = None
        if rec:
            records.append(rec)
        else:
            skipped += 1  # a real entry (not @comment/@preamble/@string) with no title and no DOI
    return records, skipped


# ── RIS ──────────────────────────────────────────────────────────────────────


def _ris_entry_to_csl(ty: str, authors: list[str], fields: dict[str, str]) -> dict | None:
    rec: dict[str, Any] = {"type": _RIS_TO_CSL_TYPE.get(ty.upper(), "document")}
    if authors:
        rec["author"] = [_parse_name(a) for a in authors]
    # Clarivate's current RIS upload contract accepts these aliases; EndNote
    # desktop itself recommends its RefMan (RIS) Export transfer style.
    title = next((fields.get(tag) for tag in ("TI", "T1", "BT", "CT", "T3", "TT", "ST") if fields.get(tag)), None)
    if title:
        rec["title"] = title
    journal = next((fields.get(tag) for tag in ("T2", "JO", "JF", "J1", "J2") if fields.get(tag)), None)
    if journal:
        rec["container-title"] = journal
    issued = _issued(_year_int(fields.get("PY") or fields.get("Y1") or fields.get("Y2") or fields.get("DA")))
    if issued:
        rec["issued"] = issued
    for src, dst in (
        ("VL", "volume"),
        ("IS", "issue"),
        ("PB", "publisher"),
        ("DO", "DOI"),
        ("UR", "URL"),
        ("SN", "ISSN"),
        ("AB", "abstract"),
    ):
        if fields.get(src):
            rec[dst] = fields[src]
    if fields.get("SP"):
        rec["page"] = f"{fields['SP']}-{fields['EP']}" if fields.get("EP") else fields["SP"]
    return rec if (rec.get("title") or rec.get("DOI")) else None


def parse_ris(text: str) -> tuple[list[dict], int]:
    """→ (CSL records, count of ER-delimited entries dropped for having no title AND no DOI). See parse_bibtex."""
    records: list[dict] = []
    skipped = 0
    ty: str | None = None
    authors: list[str] = []
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = _RIS_TAG_RE.match(line)
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag == "TY":
            ty, authors, fields = value, [], {}
        elif tag == "ER":
            if ty is not None:
                try:
                    rec = _ris_entry_to_csl(ty, authors, fields)
                except Exception:
                    rec = None
                if rec:
                    records.append(rec)
                else:
                    skipped += 1
            ty, authors, fields = None, [], {}
        elif ty is not None:
            if tag in ("AU", "A1", "A2", "A3", "A4"):
                authors.append(value)
            else:
                fields[tag] = value
    return records, skipped


# ── CSL-JSON ───────────────────────────────────────────────────────────────────


def parse_csl_json(text: str) -> tuple[list[dict], int]:
    """→ (CSL records, count of array entries dropped for being non-dict / having no title AND no DOI)."""
    data = json.loads(text)  # may raise — caught by parse_records
    if isinstance(data, dict):
        items = data.get("items")
        data = items if isinstance(items, list) else [data]
    if not isinstance(data, list):
        return [], 0
    records = [r for r in data if isinstance(r, dict) and (_norm(r.get("title")) or _norm(r.get("DOI")))]
    return records, len(data) - len(records)


# ── dispatch + mapping + orchestration ─────────────────────────────────────────


def parse_records(content: str, fmt: str | None) -> tuple[list[dict], str | None, int]:
    """Parse `content` (using `fmt`, or auto-detect when it isn't a known format) → (CSL records, resolved fmt,
    skipped). `skipped` = entries dropped at parse for having no title AND no DOI, **plus** any beyond the
    record cap. Caps the byte size + record count; a parser that throws yields an empty list (never fatal)."""
    if len(content.encode("utf-8", "ignore")) > MAX_IMPORT_BYTES:
        raise ValueError("Citation file too large to import.")
    resolved = fmt if fmt in IMPORT_FORMATS else detect_format(content)
    if resolved is None:
        return [], None, 0
    try:
        if resolved == "csl-json":
            records, skipped = parse_csl_json(content)
        elif resolved == "ris":
            records, skipped = parse_ris(content)
        else:
            records, skipped = parse_bibtex(content)
    except Exception:
        records, skipped = [], 0
    capped = records[:MAX_IMPORT_RECORDS]
    return capped, resolved, skipped + (len(records) - len(capped))


def csl_record_to_paper_fields(rec: dict) -> dict[str, Any]:
    """Map a CSL record → `create_paper` kwargs (the inverse of citation_export). `csl_json` stores the record
    whole (CSL-JSON round-trips losslessly). `item_type` is the CSL type so the inc-91 Type facet labels it."""
    title = _norm(rec.get("title"))
    first_family = None
    for author in rec.get("author") or []:
        if isinstance(author, dict):
            first_family = _norm(author.get("family")) or _norm(author.get("literal"))
            break
    issued = rec.get("issued")
    year = _year_int(issued.get("date-parts", [[None]])[0][0]) if isinstance(issued, dict) else None
    return {
        "title": title or _norm(rec.get("DOI")) or "(untitled import)",
        "csl_json": rec,
        "abstract": _norm(rec.get("abstract")),
        "year": year,
        "doi": _norm(rec.get("DOI")),
        "venue": _norm(rec.get("container-title")),
        "item_type": str(rec.get("type") or "document"),
        "first_author_family_name": first_family,
        "citation_key": _norm(rec.get("id")),
    }


def import_citations(conn: Connection, content: str, fmt: str | None) -> dict[str, Any]:
    """Parse → dedup → create. Each record runs in its own savepoint so a bad one is isolated, not fatal. Dedup
    reuses `find_existing_paper_by_identity` (DOI → title+year+author). No egress; no Crossref/My-Pubs hook (the
    file is authoritative — `<fmt>-import` is deliberately outside enrichment's update allowlist, like user-edits)."""
    records, resolved, skipped = parse_records(content, fmt)
    source = f"{resolved}-import" if resolved else "citation-import"
    created: list[int] = []
    duplicate = 0
    failed = 0
    for rec in records:
        try:
            with conn.begin_nested():
                fields = csl_record_to_paper_fields(rec)
                if not fields["doi"] and fields["title"] == "(untitled import)":
                    failed += 1
                    continue
                existing = find_existing_paper_by_identity(
                    conn,
                    doi=fields["doi"],
                    title=fields["title"],
                    year=fields["year"],
                    first_author_family_name=fields["first_author_family_name"],
                )
                if existing is not None:
                    duplicate += 1
                    continue
                created.append(create_paper(conn, imported_source=source, **fields))
        except Exception as exc:
            _log.warning("citation import: skipped record %r: %s", rec.get("title", "(untitled)"), exc)
            failed += 1
    return {"created": created, "duplicate": duplicate, "failed": failed, "skipped": skipped, "format": resolved}
