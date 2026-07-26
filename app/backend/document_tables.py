"""Bounded, local table extraction for evidence-aware Methods checks.

Tables stay separate from ordinary ``chunks`` so row reconstruction cannot silently alter the prose/embedding
corpus.  The extractors retain headers, cells, table/row identity, and PDF row coordinates where available.
They do not decide whether a row contains a statistical result; that belongs to the consuming method.
"""

from __future__ import annotations

import html
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import fitz

MAX_TABLE_FILE_BYTES = 256 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 64 * 1024 * 1024
MAX_PDF_PAGES = 200
MAX_TABLES = 100
MAX_TABLE_ROWS = 1000
MAX_TABLE_COLUMNS = 50
MAX_CELL_CHARS = 2000


@dataclass(frozen=True)
class TableRowEvidence:
    headers: tuple[str, ...]
    cells: tuple[str, ...]
    source_type: str
    table_index: int
    row_index: int
    page: int | None = None
    bbox_json: tuple[dict[str, Any], ...] = ()
    caption: str | None = None
    section: str | None = None
    attachment_id: int | None = None


@dataclass(frozen=True)
class TableExtraction:
    rows: tuple[TableRowEvidence, ...]
    tables_scanned: int
    pages_scanned: int
    truncated: bool = False


def supports_table_extraction(path: str | Path, content_type: str | None = None) -> bool:
    source = Path(path)
    ctype = (content_type or "").lower()
    suffix = source.suffix.lower()
    return suffix in {".pdf", ".xml", ".jats", ".docx", ".odt", ".html", ".htm"} or any(
        marker in ctype for marker in ("pdf", "xml", "wordprocessingml", "opendocument.text", "html")
    )


def extract_document_tables(path: str | Path, content_type: str | None = None) -> TableExtraction:
    source = Path(path)
    stat = source.stat()
    if stat.st_size > MAX_TABLE_FILE_BYTES:
        raise ValueError(f"Document exceeds the {MAX_TABLE_FILE_BYTES // (1024 * 1024)} MiB table-scan limit")
    return _extract_document_tables_cached(
        str(source.resolve()),
        (content_type or "").lower(),
        stat.st_size,
        stat.st_mtime_ns,
    )


@lru_cache(maxsize=64)
def _extract_document_tables_cached(
    resolved_path: str,
    content_type: str,
    _file_size: int,
    _mtime_ns: int,
) -> TableExtraction:
    path = Path(resolved_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf" or "pdf" in content_type:
        return _extract_pdf_tables(path)
    if suffix == ".docx" or "wordprocessingml" in content_type:
        return _extract_docx_tables(path)
    if suffix == ".odt" or "opendocument.text" in content_type:
        return _extract_odt_tables(path)
    if suffix in {".html", ".htm"} or "html" in content_type:
        return _extract_html_tables(path)
    if suffix in {".xml", ".jats"} or "xml" in content_type:
        return _extract_jats_tables(path)
    raise ValueError(f"No table extractor for {suffix or content_type or 'unknown document type'}")


def _extract_pdf_tables(path: Path) -> TableExtraction:
    rows: list[TableRowEvidence] = []
    tables_scanned = 0
    truncated = False
    with fitz.open(path) as document:
        pages_scanned = min(len(document), MAX_PDF_PAGES)
        truncated = len(document) > pages_scanned
        for page_index in range(pages_scanned):
            finder = document[page_index].find_tables()
            for table in finder.tables:
                if tables_scanned >= MAX_TABLES or len(rows) >= MAX_TABLE_ROWS:
                    truncated = True
                    break
                tables_scanned += 1
                extracted = table.extract()
                headers = _bounded_cells(getattr(table.header, "names", ()) or ())
                header_external = bool(getattr(table.header, "external", False))
                for physical_index, raw_cells in enumerate(extracted):
                    cells = _bounded_cells(raw_cells or ())
                    if not cells or not any(cells):
                        continue
                    if not header_external and physical_index == 0 and _same_cells(headers, cells):
                        continue
                    if len(rows) >= MAX_TABLE_ROWS:
                        truncated = True
                        break
                    row_bbox = None
                    table_rows = getattr(table, "rows", ())
                    if physical_index < len(table_rows):
                        row_bbox = getattr(table_rows[physical_index], "bbox", None)
                    bbox_json = ()
                    if row_bbox:
                        bbox_json = (
                            {
                                "page": page_index + 1,
                                "x0": float(row_bbox[0]),
                                "y0": float(row_bbox[1]),
                                "x1": float(row_bbox[2]),
                                "y1": float(row_bbox[3]),
                                "source_kind": "table-row",
                                "table_index": tables_scanned,
                                "row_index": physical_index + 1,
                            },
                        )
                    rows.append(
                        TableRowEvidence(
                            headers=headers,
                            cells=cells,
                            source_type="pdf",
                            table_index=tables_scanned,
                            row_index=physical_index + 1,
                            page=page_index + 1,
                            bbox_json=bbox_json,
                        )
                    )
            if truncated:
                break
    return TableExtraction(tuple(rows), tables_scanned, pages_scanned, truncated)


def _extract_jats_tables(path: Path) -> TableExtraction:
    root = ET.parse(path).getroot()
    tables: list[tuple[list[tuple[list[str], bool]], str | None, str | None]] = []
    _collect_jats_tables(root, None, tables)
    return _rows_from_structured_tables(tables, source_type="jats")


def _collect_jats_tables(
    element: ET.Element,
    section: str | None,
    tables: list[tuple[list[tuple[list[str], bool]], str | None, str | None]],
) -> None:
    name = _local_name(element.tag)
    current_section = section
    if name == "sec":
        title = next((_element_text(child) for child in element if _local_name(child.tag) == "title"), "")
        current_section = title or section
    if name in {"table-wrap", "table"}:
        table_element = element
        if name == "table-wrap":
            table_element = next((child for child in element.iter() if _local_name(child.tag) == "table"), element)
        caption = next(
            (_element_text(child) for child in element.iter() if _local_name(child.tag) in {"caption", "label"}),
            "",
        )
        table_rows = _xml_table_rows(table_element, {"tr"}, {"th", "td"})
        if table_rows:
            tables.append((table_rows, caption or None, current_section))
        return
    for child in element:
        _collect_jats_tables(child, current_section, tables)


def _extract_docx_tables(path: Path) -> TableExtraction:
    root = ET.fromstring(_read_zip_member(path, "word/document.xml"))
    tables = [
        (_xml_table_rows(table, {"tr"}, {"tc"}), None, None) for table in root.iter() if _local_name(table.tag) == "tbl"
    ]
    return _rows_from_structured_tables(tables, source_type="docx")


def _extract_odt_tables(path: Path) -> TableExtraction:
    root = ET.fromstring(_read_zip_member(path, "content.xml"))
    tables = [
        (_xml_table_rows(table, {"table-row"}, {"table-cell"}), None, None)
        for table in root.iter()
        if _local_name(table.tag) == "table"
    ]
    return _rows_from_structured_tables(tables, source_type="odt")


def _extract_html_tables(path: Path) -> TableExtraction:
    parser = _HtmlTableParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()
    return _rows_from_structured_tables(parser.tables, source_type="html")


def _rows_from_structured_tables(
    tables: list[tuple[list[tuple[list[str], bool]], str | None, str | None]],
    *,
    source_type: str,
) -> TableExtraction:
    evidence: list[TableRowEvidence] = []
    truncated = len(tables) > MAX_TABLES
    tables_scanned = min(len(tables), MAX_TABLES)
    for table_index, (raw_rows, caption, section) in enumerate(tables[:MAX_TABLES], start=1):
        if not raw_rows:
            continue
        header_index = next((index for index, (_, explicit_header) in enumerate(raw_rows) if explicit_header), 0)
        headers = _bounded_cells(raw_rows[header_index][0])
        for physical_index, (raw_cells, _) in enumerate(raw_rows):
            if physical_index == header_index:
                continue
            cells = _bounded_cells(raw_cells)
            if not cells or not any(cells):
                continue
            if len(evidence) >= MAX_TABLE_ROWS:
                truncated = True
                break
            evidence.append(
                TableRowEvidence(
                    headers=headers,
                    cells=cells,
                    source_type=source_type,
                    table_index=table_index,
                    row_index=physical_index + 1,
                    caption=_bounded_text(caption),
                    section=_bounded_text(section),
                )
            )
        if truncated:
            break
    return TableExtraction(tuple(evidence), tables_scanned, 0, truncated)


def _xml_table_rows(
    table: ET.Element,
    row_names: set[str],
    cell_names: set[str],
) -> list[tuple[list[str], bool]]:
    rows: list[tuple[list[str], bool]] = []
    for row in table.iter():
        if _local_name(row.tag) not in row_names:
            continue
        cell_elements = [child for child in row if _local_name(child.tag) in cell_names]
        cells = [_element_text(cell) for cell in cell_elements]
        explicit_header = any(_local_name(cell.tag) == "th" for cell in cell_elements)
        if cells:
            rows.append((cells, explicit_header))
    return rows


def _read_zip_member(path: Path, member: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(member)
        if info.file_size > MAX_ZIP_MEMBER_BYTES:
            raise ValueError(f"{member} exceeds the {MAX_ZIP_MEMBER_BYTES // (1024 * 1024)} MiB extraction limit")
        return archive.read(info)


class _HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[tuple[list[tuple[list[str], bool]], str | None, str | None]] = []
        self._section: str | None = None
        self._heading: list[str] | None = None
        self._table_depth = 0
        self._rows: list[tuple[list[str], bool]] = []
        self._cells: list[str] | None = None
        self._cell_pieces: list[str] | None = None
        self._row_header = False
        self._caption: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._table_depth == 0:
            self._heading = []
        elif tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._rows = []
                self._caption = []
        elif self._table_depth == 1 and tag == "tr":
            self._cells = []
            self._row_header = False
        elif self._table_depth == 1 and tag in {"th", "td"} and self._cells is not None:
            self._cell_pieces = []
            self._row_header = self._row_header or tag == "th"

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading is not None:
            self._section = _normalize_space(" ".join(self._heading)) or self._section
            self._heading = None
        elif self._table_depth == 1 and tag in {"th", "td"} and self._cell_pieces is not None:
            if self._cells is not None:
                self._cells.append(_normalize_space(" ".join(self._cell_pieces)))
            self._cell_pieces = None
        elif self._table_depth == 1 and tag == "tr" and self._cells is not None:
            if self._cells:
                self._rows.append((self._cells, self._row_header))
            self._cells = None
        elif tag == "table" and self._table_depth:
            if self._table_depth == 1 and self._rows:
                caption = _normalize_space(" ".join(self._caption or [])) or None
                self.tables.append((self._rows, caption, self._section))
            self._table_depth -= 1
            self._caption = None

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        decoded = html.unescape(data)
        if self._cell_pieces is not None:
            self._cell_pieces.append(decoded)
        elif self._table_depth == 1 and self._caption is not None:
            self._caption.append(decoded)
        elif self._heading is not None:
            self._heading.append(decoded)


def _bounded_cells(values) -> tuple[str, ...]:
    return tuple(_bounded_text(value) or "" for value in list(values)[:MAX_TABLE_COLUMNS])


def _bounded_text(value: Any) -> str | None:
    text = _normalize_space(str(value or ""))
    return text[:MAX_CELL_CHARS] or None


def _same_cells(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return tuple(value.casefold() for value in left) == tuple(value.casefold() for value in right)


def _element_text(element: ET.Element) -> str:
    return _normalize_space(" ".join(item for item in element.itertext()))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _normalize_space(text: str) -> str:
    return " ".join(str(text or "").split())
