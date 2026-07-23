"""Deterministic, local content identity for WIP manuscript files."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from app.backend.document_text import extract_text_document
from app.backend.pdf_processing.extraction import extract_pdf, file_sha256

SUPPORTED_SUFFIXES = {".docx", ".odt", ".html", ".htm", ".xml", ".jats", ".md", ".txt", ".tex", ".pdf"}
MAX_PRIMARY_FILE_BYTES = 256 * 1024 * 1024
MAX_EVIDENCE_CONTEXTS = 6
MAX_EVIDENCE_CONTEXT_CHARS = 500


class ContentIdentityError(ValueError):
    """Raised when an exact extracted-text identity cannot be produced."""

    def __init__(self, message: str, *, status: str = "error") -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class ContentBlock:
    text: str
    section: str | None
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True)
class ContentIdentity:
    whole_file_hash: str
    extracted_text_hash: str
    extraction_provider: str
    extraction_version: str
    extracted_char_count: int
    section_hashes: dict[str, str]
    evidence_contexts: tuple[str, ...]
    blocks: tuple[ContentBlock, ...]


def extract_content_identity(path: str | Path) -> ContentIdentity:
    """Extract normalized text and return hashes plus bounded inspectable context."""
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ContentIdentityError(
            f"Unsupported primary manuscript format: {suffix or 'no extension'}", status="unsupported"
        )
    try:
        if source.stat().st_size > MAX_PRIMARY_FILE_BYTES:
            raise ContentIdentityError("Primary manuscript exceeds the 256 MiB extraction limit")
        if suffix == ".pdf":
            extraction = extract_pdf(source)
            raw_blocks = [
                (None, block.text, page.page_number, page.page_number)
                for page in extraction.pages
                for block in page.blocks
                if _normalize_text(block.text)
            ]
            provider = extraction.extraction_tool
            version = extraction.extraction_version
        else:
            extraction = extract_text_document(source)
            raw_blocks = [
                (segment.section, segment.text, segment.page_start, segment.page_end)
                for segment in extraction.segments
                if _normalize_text(segment.text)
            ]
            provider = extraction.provider_id
            version = extraction.extraction_version
    except ContentIdentityError:
        raise
    except (OSError, ValueError, KeyError, RuntimeError, SyntaxError) as exc:
        raise ContentIdentityError(f"{type(exc).__name__}: {exc}") from exc
    blocks = tuple(
        ContentBlock(
            text=_normalize_text(text),
            section=_normalize_text(section or "") or None,
            page_start=page_start,
            page_end=page_end,
        )
        for section, text, page_start, page_end in raw_blocks
        if _normalize_text(text)
    )
    if not blocks:
        raise ContentIdentityError("No manuscript text could be extracted")
    text = "\n\n".join(block.text for block in blocks)
    section_text: dict[str, list[str]] = {}
    for block in blocks:
        if block.section:
            section_text.setdefault(block.section, []).append(block.text)
    contexts = tuple(block.text[:MAX_EVIDENCE_CONTEXT_CHARS] for block in blocks[:MAX_EVIDENCE_CONTEXTS])
    return ContentIdentity(
        whole_file_hash=file_sha256(source),
        extracted_text_hash=_text_hash(text),
        extraction_provider=provider,
        extraction_version=version,
        extracted_char_count=len(text),
        section_hashes={name: _text_hash("\n\n".join(parts)) for name, parts in section_text.items()},
        evidence_contexts=contexts,
        blocks=blocks,
    )


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _text_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
