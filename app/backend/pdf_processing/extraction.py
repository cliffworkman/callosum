"""PyMuPDF extraction and quote location.

This module is intentionally thin around PyMuPDF so a permissive-license
fallback can later replace the extraction backend without changing callers.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import fitz

from app.backend.pdf_processing.pdf_links import PdfLinkAnnotation, extract_page_link_annotations
from app.backend.pdf_processing.sections import SectionTracker

COORDINATE_SYSTEM = "pdf-points-top-left"
EXTRACTION_TOOL = "pymupdf"
# v2 (inc 283): section labels are now detected per line, so chunk output changed materially; the bump
# makes pre-section chunks read as stale_chunk_version (text-health) instead of masquerading as current.
DEFAULT_CHUNKING_STRATEGY = "pymupdf-block-v2"
SOFT_HYPHEN = "\u00ad"
HYPHEN_BREAK_CHARS = "-\u00ad\u2010\u2011\u2012\u2013\u2014\u2212"
DASH_EQUIVALENTS = {
    "\u2010",
    "\u2011",
    "\u2012",
    "\u2013",
    "\u2014",
    "\u2212",
}
LINE_BREAK_HYPHEN_PREFIXES = {
    "anti",
    "co",
    "ex",
    "inter",
    "intra",
    "multi",
    "non",
    "post",
    "pre",
    "pseudo",
    "quasi",
    "re",
    "self",
    "semi",
    "sub",
    "super",
    "un",
}
LIGATURE_MAP = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "st",
        "\ufb06": "st",
        "\u017f": "s",
    }
)


@dataclass(frozen=True)
class TextSpan:
    page_number: int
    text: str
    bbox: dict[str, float]
    block_number: int
    line_number: int
    span_number: int


@dataclass(frozen=True)
class TextBlock:
    page_number: int
    text: str
    bbox: dict[str, float]
    spans: tuple[TextSpan, ...]


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    width: float
    height: float
    blocks: tuple[TextBlock, ...]


@dataclass(frozen=True)
class ExtractionResult:
    pdf_path: Path
    extraction_tool: str
    extraction_version: str
    coordinate_system: str
    pages: tuple[ExtractedPage, ...]
    links: tuple[PdfLinkAnnotation, ...] = ()


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    bbox_json: list[dict[str, Any]]
    bbox_coordinate_system: str
    extraction_tool: str
    extraction_version: str
    chunking_strategy: str
    chunk_version: str
    source_attachment_checksum: str
    section: str | None = None


@dataclass(frozen=True)
class _WordToken:
    text: str
    page_number: int
    block_number: int
    line_number: int
    word_number: int
    bbox: dict[str, float]
    start: int
    end: int


def extract_pdf(pdf_path: str | Path) -> ExtractionResult:
    path = Path(pdf_path)
    pages: list[ExtractedPage] = []
    links: list[PdfLinkAnnotation] = []

    with fitz.open(path) as document:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            text_dict = page.get_text("dict", sort=True)
            blocks: list[TextBlock] = []

            for block_index, block in enumerate(text_dict.get("blocks", [])):
                if block.get("type") != 0:
                    continue

                spans: list[TextSpan] = []
                line_texts: list[str] = []
                for line_index, line in enumerate(block.get("lines", [])):
                    line_spans: list[dict[str, Any]] = []
                    for span_index, span in enumerate(line.get("spans", [])):
                        text = span.get("text", "")
                        if not text:
                            continue
                        line_spans.append(span)
                        if text.strip():
                            spans.append(
                                TextSpan(
                                    page_number=page_number,
                                    text=text,
                                    bbox=_rect_to_dict(span["bbox"]),
                                    block_number=block_index,
                                    line_number=line_index,
                                    span_number=span_index,
                                )
                            )
                    line_text = _line_text_from_spans(line_spans)
                    if line_text.strip():
                        line_texts.append(line_text)

                block_text = "\n".join(line_texts).strip()
                if not block_text:
                    continue

                blocks.append(
                    TextBlock(
                        page_number=page_number,
                        text=block_text,
                        bbox=_rect_to_dict(block["bbox"]),
                        spans=tuple(spans),
                    )
                )

            pages.append(
                ExtractedPage(
                    page_number=page_number,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    blocks=tuple(blocks),
                )
            )
            links.extend(extract_page_link_annotations(page, page_number, blocks))

    return ExtractionResult(
        pdf_path=path,
        extraction_tool=EXTRACTION_TOOL,
        extraction_version=_pymupdf_version(),
        coordinate_system=COORDINATE_SYSTEM,
        pages=tuple(pages),
        links=tuple(links),
    )


def make_chunk_drafts(
    extraction: ExtractionResult,
    *,
    source_attachment_checksum: str,
    chunking_strategy: str = DEFAULT_CHUNKING_STRATEGY,
) -> list[ChunkDraft]:
    """Create paragraph-like chunks from PyMuPDF text blocks."""
    chunk_version = make_chunk_version(
        chunking_strategy=chunking_strategy,
        extraction_tool=extraction.extraction_tool,
        extraction_version=extraction.extraction_version,
        source_attachment_checksum=source_attachment_checksum,
    )
    drafts: list[ChunkDraft] = []
    cursor = 0
    section_tracker = SectionTracker()

    for page in extraction.pages:
        for block in page.blocks:
            text = _normalize_space(block.text)
            if not text:
                continue
            if section_tracker.observe_block(block.text):
                continue

            char_start = cursor
            char_end = cursor + len(text)
            cursor = char_end + 1
            drafts.append(
                ChunkDraft(
                    text=text,
                    page_start=block.page_number,
                    page_end=block.page_number,
                    char_start=char_start,
                    char_end=char_end,
                    bbox_json=[
                        {
                            "page": span.page_number,
                            "block": span.block_number,
                            "line": span.line_number,
                            "span": span.span_number,
                            **span.bbox,
                        }
                        for span in block.spans
                    ],
                    bbox_coordinate_system=extraction.coordinate_system,
                    extraction_tool=extraction.extraction_tool,
                    extraction_version=extraction.extraction_version,
                    chunking_strategy=chunking_strategy,
                    chunk_version=chunk_version,
                    source_attachment_checksum=source_attachment_checksum,
                    section=section_tracker.current_section,
                )
            )

    return drafts


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_chunk_version(
    *,
    chunking_strategy: str,
    extraction_tool: str,
    extraction_version: str,
    source_attachment_checksum: str,
) -> str:
    return f"{chunking_strategy}:{extraction_tool}-{extraction_version}:{source_attachment_checksum[:16]}"


def canonicalize_quote_text(text: str) -> str:
    """Return the comparison form used for tolerant quote matching."""
    variants = canonicalize_faithful_text_variants(text)
    return variants[0] if variants else ""


def canonicalize_faithful_text_variants(text: str) -> list[str]:
    """Return quote comparison forms, including hyphen-break variants."""
    variants = []
    for mode in ("remove", "keep"):
        canonical, _ = _canonicalize_text(text, hyphen_break_mode=mode)
        if canonical and canonical not in variants:
            variants.append(canonical)
    return variants


def canonical_text_contains(*, needle: str, haystack: str) -> bool:
    haystack_variants = canonicalize_faithful_text_variants(haystack)
    needle_variants = canonicalize_faithful_text_variants(needle)
    return any(
        needle_variant in haystack_variant
        for needle_variant in needle_variants
        for haystack_variant in haystack_variants
    )


def _canonicalize_document_text(
    document_text: str,
    tokens: list[_WordToken],
) -> tuple[str, list[int | None]]:
    if not tokens:
        return _canonicalize_text(document_text)
    return _canonicalize_tokens(tokens)


def _canonicalize_text(
    text: str,
    char_token_indices: list[int | None] | None = None,
    *,
    hyphen_break_mode: str = "remove",
) -> tuple[str, list[int | None]]:
    pieces: list[str] = []
    token_map: list[int | None] = []
    index = 0
    while index < len(text):
        char = text[index]
        token_index = char_token_indices[index] if char_token_indices is not None else None
        if _is_hyphenation_break(text, index, pieces):
            if hyphen_break_mode == "keep" or _string_hyphen_break_forces_keep(text, index, pieces):
                pieces.append("-")
                token_map.append(token_index)
            index = _next_non_whitespace_index(text, index + 1)
            continue
        if char.isspace():
            if pieces and pieces[-1] != " ":
                pieces.append(" ")
                token_map.append(token_index)
            index += 1
            continue
        normalized = _canonical_characters(char)
        for normalized_char in normalized:
            if normalized_char.isspace():
                if pieces and pieces[-1] != " ":
                    pieces.append(" ")
                    token_map.append(token_index)
                continue
            pieces.append(normalized_char)
            token_map.append(token_index)
        index += 1

    while pieces and pieces[-1] == " ":
        pieces.pop()
        token_map.pop()
    return "".join(pieces), token_map


def _canonicalize_tokens(tokens: list[_WordToken]) -> tuple[str, list[int | None]]:
    pieces: list[str] = []
    token_map: list[int | None] = []
    for index, token in enumerate(tokens):
        next_token = tokens[index + 1] if index + 1 < len(tokens) else None
        token_text = token.text
        join_next = False
        if next_token is not None and _token_ends_with_hyphen(token):
            if _is_line_break_between(token, next_token):
                token_text, join_next = _line_break_hyphen_text(token.text, next_token.text)
            elif _is_same_line_hyphen_continuation(token, next_token):
                join_next = True

        _append_canonical_token_text(pieces, token_map, token_text, index)
        if next_token is not None and not join_next:
            _append_space(pieces, token_map)
    while pieces and pieces[-1] == " ":
        pieces.pop()
        token_map.pop()
    return "".join(pieces), token_map


def _append_canonical_token_text(
    pieces: list[str],
    token_map: list[int | None],
    text: str,
    token_index: int,
) -> None:
    canonical, _ = _canonicalize_text(text)
    for char in canonical:
        if char == " ":
            _append_space(pieces, token_map, token_index)
            continue
        pieces.append(char)
        token_map.append(token_index)


def _append_space(
    pieces: list[str],
    token_map: list[int | None],
    token_index: int | None = None,
) -> None:
    if pieces and pieces[-1] != " ":
        pieces.append(" ")
        token_map.append(token_index)


def _token_ends_with_hyphen(token: _WordToken) -> bool:
    return bool(token.text) and token.text[-1] in HYPHEN_BREAK_CHARS


def _is_line_break_between(current: _WordToken, next_token: _WordToken) -> bool:
    return (current.page_number, current.block_number, current.line_number) != (
        next_token.page_number,
        next_token.block_number,
        next_token.line_number,
    )


def _is_same_line_hyphen_continuation(current: _WordToken, next_token: _WordToken) -> bool:
    if _is_line_break_between(current, next_token):
        return False
    gap = next_token.bbox["x0"] - current.bbox["x1"]
    height = max(current.bbox["y1"] - current.bbox["y0"], next_token.bbox["y1"] - next_token.bbox["y0"], 1.0)
    return gap <= height * 0.5


def _line_break_hyphen_text(text: str, next_text: str) -> tuple[str, bool]:
    stripped = text[:-1]
    if _line_break_hyphen_forces_keep(stripped, next_text):
        return text, True
    return stripped, True


def _line_break_hyphen_forces_keep(left_text: str, right_text: str) -> bool:
    left = canonicalize_quote_text(left_text)
    right = canonicalize_quote_text(right_text)
    left_char = _last_alnum(left)
    right_char = _first_alnum(right)
    if (left_char and left_char.isdigit()) or (right_char and right_char.isdigit()):
        return True
    if _prefix_fragment(left) in LINE_BREAK_HYPHEN_PREFIXES:
        return True
    return "-" in left


def _string_hyphen_break_forces_keep(text: str, index: int, pieces: list[str]) -> bool:
    next_index = _next_non_whitespace_index(text, index + 1)
    right_text = text[next_index:] if next_index < len(text) else ""
    left_fragment = "".join(pieces).rsplit(" ", 1)[-1]
    return _line_break_hyphen_forces_keep(left_fragment, right_text)


def _last_alnum(text: str) -> str | None:
    for char in reversed(text):
        if char.isalnum():
            return char
    return None


def _first_alnum(text: str) -> str | None:
    for char in text:
        if char.isalnum():
            return char
    return None


def _prefix_fragment(text: str) -> str:
    return text.strip("-").rsplit("-", 1)[-1].lower()


def _is_hyphenation_break(text: str, index: int, pieces: list[str]) -> bool:
    char = text[index]
    if char not in HYPHEN_BREAK_CHARS:
        return False
    if not pieces or not pieces[-1].isalnum():
        return False
    whitespace_index = index + 1
    if whitespace_index >= len(text) or not text[whitespace_index].isspace():
        return False
    next_index = _next_non_whitespace_index(text, whitespace_index)
    if next_index >= len(text):
        return False
    next_chars = _canonical_characters(text[next_index])
    return bool(next_chars and next_chars[0].isalnum())


def _next_non_whitespace_index(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _canonical_characters(char: str) -> str:
    if char == SOFT_HYPHEN:
        return ""
    translated = char.translate(LIGATURE_MAP)
    normalized = unicodedata.normalize("NFC", translated)
    return "".join("-" if item in DASH_EQUIVALENTS else item for item in normalized if item != SOFT_HYPHEN)


def _rect_to_dict(rect: Any) -> dict[str, float]:
    return {
        "x0": float(rect[0]),
        "y0": float(rect[1]),
        "x1": float(rect[2]),
        "y1": float(rect[3]),
    }


def _line_text_from_spans(spans: list[dict[str, Any]]) -> str:
    pieces: list[str] = []
    previous_span: dict[str, Any] | None = None
    previous_text = ""
    for span in spans:
        text = str(span.get("text", ""))
        if not text:
            continue
        if text.isspace():
            if pieces and not pieces[-1].endswith(" "):
                pieces.append(" ")
            previous_span = span
            previous_text = text
            continue
        if (
            pieces
            and previous_span is not None
            and _needs_space_between_spans(previous_span, span, previous_text, text)
        ):
            pieces.append(" ")
        pieces.append(text)
        previous_span = span
        previous_text = text
    return "".join(pieces)


def _needs_space_between_spans(
    previous_span: dict[str, Any],
    current_span: dict[str, Any],
    previous_text: str,
    current_text: str,
) -> bool:
    if previous_text.endswith((" ", "\t", "\n", "\r")) or current_text.startswith((" ", "\t", "\n", "\r")):
        return False
    previous_bbox = previous_span.get("bbox")
    current_bbox = current_span.get("bbox")
    if previous_bbox is None or current_bbox is None:
        return False
    gap = float(current_bbox[0]) - float(previous_bbox[2])
    if gap <= 0:
        return False
    previous_size = float(previous_span.get("size", 0) or 0)
    current_size = float(current_span.get("size", 0) or 0)
    font_size = (
        min(value for value in (previous_size, current_size) if value > 0) if previous_size or current_size else 12.0
    )
    return gap >= max(1.0, font_size * 0.15)


def _normalize_space(text: str) -> str:
    return " ".join(text.split())


def _pymupdf_version() -> str:
    version = getattr(fitz, "version", None)
    if isinstance(version, tuple) and version:
        return str(version[0])
    return str(getattr(fitz, "__doc__", "unknown")).split()[1] if getattr(fitz, "__doc__", None) else "unknown"
