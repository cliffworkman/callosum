"""Locate a verbatim quote in a PDF and return page-aware coordinate rectangles.

The bridge between text and coordinates: it reuses the canonicalization from `extraction.py`
(so hyphenation/ligature/line-break variants still match) and maps the matched character span
back to per-line bounding rectangles. Kept separate from `extraction.py` so the quote→bbox
matching concern can be reviewed on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from app.backend.pdf_processing.extraction import (
    _canonicalize_document_text,
    _normalize_space,
    _rect_to_dict,
    _WordToken,
    canonicalize_faithful_text_variants,
)


@dataclass(frozen=True)
class QuoteMatch:
    found: bool
    quote: str
    page_start: int | None = None
    page_end: int | None = None
    rectangles: tuple[dict[str, Any], ...] = ()


def locate_quote(pdf_path: str | Path, quote: str) -> QuoteMatch:
    """Locate a verbatim quote and return page-aware rectangles.

    Matching is whitespace-normalized across the whole document so line breaks
    and page boundaries do not prevent finding otherwise verbatim text.
    """
    normalized_quotes = canonicalize_faithful_text_variants(quote)
    if not normalized_quotes:
        return QuoteMatch(found=False, quote=quote)

    tokens, document_text = _word_tokens_for_pdf(pdf_path)
    canonical_document, token_map = _canonicalize_document_text(document_text, tokens)
    start = -1
    normalized_quote = ""
    for candidate in normalized_quotes:
        start = canonical_document.find(candidate)
        if start >= 0:
            normalized_quote = candidate
            break
    if start < 0:
        return QuoteMatch(found=False, quote=quote)

    end = start + len(normalized_quote)
    selected_indices = sorted({index for index in token_map[start:end] if index is not None})
    selected = [tokens[index] for index in selected_indices]
    if not selected:
        return QuoteMatch(found=False, quote=quote)

    rectangles = tuple(_line_rectangles(selected))
    return QuoteMatch(
        found=True,
        quote=quote,
        page_start=min(token.page_number for token in selected),
        page_end=max(token.page_number for token in selected),
        rectangles=rectangles,
    )


def _word_tokens_for_pdf(pdf_path: str | Path) -> tuple[list[_WordToken], str]:
    tokens: list[_WordToken] = []
    pieces: list[str] = []
    cursor = 0

    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            words = page.get_text("words", sort=True)
            for word in words:
                text = _normalize_space(str(word[4]))
                if not text:
                    continue
                if pieces:
                    pieces.append(" ")
                    cursor += 1
                start = cursor
                pieces.append(text)
                cursor += len(text)
                tokens.append(
                    _WordToken(
                        text=text,
                        page_number=page_number,
                        block_number=int(word[5]),
                        line_number=int(word[6]),
                        word_number=int(word[7]),
                        bbox=_rect_to_dict(word[:4]),
                        start=start,
                        end=cursor,
                    )
                )

    return tokens, "".join(pieces)


def _line_rectangles(tokens: list[_WordToken]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int, int], list[_WordToken]] = {}
    for token in tokens:
        grouped.setdefault((token.page_number, token.block_number, token.line_number), []).append(token)

    rectangles: list[dict[str, Any]] = []
    for (page_number, block_number, line_number), line_tokens in sorted(grouped.items()):
        x0 = min(token.bbox["x0"] for token in line_tokens)
        y0 = min(token.bbox["y0"] for token in line_tokens)
        x1 = max(token.bbox["x1"] for token in line_tokens)
        y1 = max(token.bbox["y1"] for token in line_tokens)
        rectangles.append(
            {
                "page": page_number,
                "block": block_number,
                "line": line_number,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
            }
        )
    return rectangles
