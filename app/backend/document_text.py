"""DocumentTextProvider adapters for non-PDF scholarly text sources.

This is the buildable infrastructure slice of the transparency / registration-alignment track. It keeps PyMuPDF as
the primary PDF path, but lets JATS/XML, DOCX, ODT, HTML, and bounded plain-text documents feed the same ``chunks``
table used by transparency, statcheck, synthesis, and future registration comparison. The adapters are
deterministic, local, and dependency-free.
"""

from __future__ import annotations

import html
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from xml.etree import ElementTree as ET

from app.backend.pdf_processing.extraction import ChunkDraft, make_chunk_version

TEXT_COORDINATE_SYSTEM = "document-text-offsets"
DEFAULT_TEXT_CHUNKING_STRATEGY = "document-text-block-v1"
EXTRACTION_VERSION = "1"
MAX_PLAIN_TEXT_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class TextSegment:
    text: str
    section: str | None = None
    page_start: int = 1
    page_end: int = 1


@dataclass(frozen=True)
class DocumentTextExtraction:
    source_path: Path
    provider_id: str
    content_type: str
    extraction_version: str
    coordinate_system: str
    segments: tuple[TextSegment, ...]


class DocumentTextProvider(Protocol):
    provider_id: str

    def supports(self, path: Path, content_type: str | None = None) -> bool: ...

    def extract(self, path: Path, content_type: str | None = None) -> DocumentTextExtraction: ...


def extract_text_document(path: str | Path, content_type: str | None = None) -> DocumentTextExtraction:
    source = Path(path)
    for provider in _PROVIDERS:
        if provider.supports(source, content_type):
            return provider.extract(source, content_type)
    raise ValueError(f"No DocumentTextProvider for {source.suffix or content_type or 'unknown document type'}")


def make_text_chunk_drafts(
    extraction: DocumentTextExtraction,
    *,
    source_attachment_checksum: str,
    chunking_strategy: str = DEFAULT_TEXT_CHUNKING_STRATEGY,
) -> list[ChunkDraft]:
    chunk_version = make_chunk_version(
        chunking_strategy=chunking_strategy,
        extraction_tool=extraction.provider_id,
        extraction_version=extraction.extraction_version,
        source_attachment_checksum=source_attachment_checksum,
    )
    drafts: list[ChunkDraft] = []
    cursor = 0
    for segment in extraction.segments:
        text = _normalize_space(segment.text)
        if not text:
            continue
        char_start = cursor
        char_end = cursor + len(text)
        cursor = char_end + 1
        drafts.append(
            ChunkDraft(
                text=text,
                page_start=segment.page_start,
                page_end=segment.page_end,
                char_start=char_start,
                char_end=char_end,
                bbox_json=[],
                bbox_coordinate_system=extraction.coordinate_system,
                extraction_tool=extraction.provider_id,
                extraction_version=extraction.extraction_version,
                chunking_strategy=chunking_strategy,
                chunk_version=chunk_version,
                source_attachment_checksum=source_attachment_checksum,
                section=segment.section,
            )
        )
    return drafts


def content_type_for_document(path: str | Path, content_type: str | None = None) -> str:
    if content_type:
        return content_type
    suffix = Path(path).suffix.lower()
    return {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".odt": "application/vnd.oasis.opendocument.text",
        ".html": "text/html",
        ".htm": "text/html",
        ".xml": "application/xml",
        ".jats": "application/xml",
    }.get(suffix, "text/plain")


def attachment_type_for_document(path: str | Path, content_type: str | None = None) -> str:
    ctype = content_type_for_document(path, content_type).lower()
    if "wordprocessingml" in ctype or Path(path).suffix.lower() == ".docx":
        return "docx"
    if "opendocument.text" in ctype or Path(path).suffix.lower() == ".odt":
        return "odt"
    if "html" in ctype or Path(path).suffix.lower() in {".html", ".htm"}:
        return "html"
    if "xml" in ctype or Path(path).suffix.lower() in {".xml", ".jats"}:
        return "jats-xml"
    return "text"


class JatsXmlTextProvider:
    provider_id = "jats-xml-text"

    def supports(self, path: Path, content_type: str | None = None) -> bool:
        ctype = (content_type or "").lower()
        return path.suffix.lower() in {".xml", ".jats"} or "xml" in ctype

    def extract(self, path: Path, content_type: str | None = None) -> DocumentTextExtraction:
        root = ET.parse(path).getroot()
        segments: list[TextSegment] = []
        for abstract in _children(root, "abstract"):
            _collect_jats_blocks(abstract, "Abstract", segments)
        for body in _children(root, "body"):
            _collect_jats_blocks(body, None, segments)
        if not segments:
            _collect_jats_blocks(root, None, segments)
        return DocumentTextExtraction(
            source_path=path,
            provider_id=self.provider_id,
            content_type=content_type_for_document(path, content_type),
            extraction_version=EXTRACTION_VERSION,
            coordinate_system=TEXT_COORDINATE_SYSTEM,
            segments=tuple(segments),
        )


class DocxTextProvider:
    provider_id = "docx-text"

    def supports(self, path: Path, content_type: str | None = None) -> bool:
        ctype = (content_type or "").lower()
        return path.suffix.lower() == ".docx" or "wordprocessingml" in ctype

    def extract(self, path: Path, content_type: str | None = None) -> DocumentTextExtraction:
        with zipfile.ZipFile(path) as docx:
            document_xml = docx.read("word/document.xml")
        root = ET.fromstring(document_xml)
        segments = [TextSegment(_docx_paragraph_text(p)) for p in root.iter() if _local_name(p.tag) == "p"]
        return DocumentTextExtraction(
            source_path=path,
            provider_id=self.provider_id,
            content_type=content_type_for_document(path, content_type),
            extraction_version=EXTRACTION_VERSION,
            coordinate_system=TEXT_COORDINATE_SYSTEM,
            segments=tuple(s for s in segments if s.text.strip()),
        )


class OdtTextProvider:
    provider_id = "odt-text"

    def supports(self, path: Path, content_type: str | None = None) -> bool:
        ctype = (content_type or "").lower()
        return path.suffix.lower() == ".odt" or "opendocument.text" in ctype

    def extract(self, path: Path, content_type: str | None = None) -> DocumentTextExtraction:
        with zipfile.ZipFile(path) as odt:
            content_xml = odt.read("content.xml")
        root = ET.fromstring(content_xml)
        segments: list[TextSegment] = []
        section: str | None = None
        for node in root.iter():
            name = _local_name(node.tag)
            text = _element_text(node) if name in {"h", "p"} else ""
            if name == "h" and text:
                section = text
            elif name == "p" and text:
                segments.append(TextSegment(text, section))
        return DocumentTextExtraction(
            source_path=path,
            provider_id=self.provider_id,
            content_type=content_type_for_document(path, content_type),
            extraction_version=EXTRACTION_VERSION,
            coordinate_system=TEXT_COORDINATE_SYSTEM,
            segments=tuple(segments),
        )


class HtmlTextProvider:
    provider_id = "html-text"

    def supports(self, path: Path, content_type: str | None = None) -> bool:
        ctype = (content_type or "").lower()
        return path.suffix.lower() in {".html", ".htm"} or "html" in ctype

    def extract(self, path: Path, content_type: str | None = None) -> DocumentTextExtraction:
        parser = _BlockHtmlParser()
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        parser.close()
        return DocumentTextExtraction(
            source_path=path,
            provider_id=self.provider_id,
            content_type=content_type_for_document(path, content_type),
            extraction_version=EXTRACTION_VERSION,
            coordinate_system=TEXT_COORDINATE_SYSTEM,
            segments=tuple(parser.segments),
        )


class PlainTextProvider:
    provider_id = "plain-text"
    _suffixes = {".md", ".txt", ".tex"}

    def supports(self, path: Path, content_type: str | None = None) -> bool:
        return path.suffix.lower() in self._suffixes

    def extract(self, path: Path, content_type: str | None = None) -> DocumentTextExtraction:
        if path.stat().st_size > MAX_PLAIN_TEXT_BYTES:
            raise ValueError(f"Plain-text document exceeds the {MAX_PLAIN_TEXT_BYTES // (1024 * 1024)} MiB limit")
        text = path.read_text(encoding="utf-8", errors="replace")
        segments = tuple(TextSegment(block) for block in text.split("\n\n") if block.strip())
        return DocumentTextExtraction(
            source_path=path,
            provider_id=self.provider_id,
            content_type=content_type_for_document(path, content_type),
            extraction_version=EXTRACTION_VERSION,
            coordinate_system=TEXT_COORDINATE_SYSTEM,
            segments=segments,
        )


def _collect_jats_blocks(element: ET.Element, section: str | None, segments: list[TextSegment]) -> None:
    current_section = section
    if _local_name(element.tag) == "sec":
        title = next((_element_text(child) for child in element if _local_name(child.tag) == "title"), "")
        current_section = title or section
    for child in element:
        name = _local_name(child.tag)
        if name == "p":
            segments.append(TextSegment(_element_text(child), current_section))
        elif name != "title":
            _collect_jats_blocks(child, current_section, segments)


def _children(element: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in element.iter() if _local_name(child.tag) == local_name]


def _element_text(element: ET.Element) -> str:
    return _normalize_space(" ".join(item for item in element.itertext()))


def _docx_paragraph_text(paragraph: ET.Element) -> str:
    pieces: list[str] = []
    for node in paragraph.iter():
        name = _local_name(node.tag)
        if name == "t" and node.text:
            pieces.append(node.text)
        elif name == "tab":
            pieces.append(" ")
        elif name in {"br", "cr"}:
            pieces.append("\n")
    return _normalize_space("".join(pieces))


class _BlockHtmlParser(HTMLParser):
    _block_tags = {"p", "li", "blockquote", "section", "article", "div"}
    _heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.segments: list[TextSegment] = []
        self._pieces: list[str] = []
        self._section: str | None = None
        self._heading: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._block_tags or tag in self._heading_tags:
            self._flush()
        if tag in self._heading_tags:
            self._heading = tag

    def handle_endtag(self, tag: str) -> None:
        if tag in self._heading_tags:
            heading_text = _normalize_space(" ".join(self._pieces))
            if heading_text:
                self._section = heading_text
            self._pieces.clear()
            self._heading = None
            return
        if tag in self._block_tags:
            self._flush()

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._pieces.append(html.unescape(data))

    def close(self) -> None:
        self._flush()
        super().close()

    def _flush(self) -> None:
        text = _normalize_space(" ".join(self._pieces))
        if text and self._heading is None:
            self.segments.append(TextSegment(text, self._section))
        self._pieces.clear()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _normalize_space(text: str) -> str:
    return " ".join(str(text or "").split())


_PROVIDERS: tuple[DocumentTextProvider, ...] = (
    JatsXmlTextProvider(),
    DocxTextProvider(),
    OdtTextProvider(),
    HtmlTextProvider(),
    PlainTextProvider(),
)
