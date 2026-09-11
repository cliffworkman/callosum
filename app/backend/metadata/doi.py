"""Conservative DOI extraction from PDF metadata and visible text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import fitz

DOI_PATTERN = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.IGNORECASE)
TRAILING_DOI_PUNCTUATION = ".,;:"


@dataclass(frozen=True)
class DoiCandidate:
    doi: str
    source: str


def find_doi_in_pdf(pdf_path: str | Path) -> DoiCandidate | None:
    path = Path(pdf_path)
    with fitz.open(path) as document:
        metadata_text = " ".join(str(value) for value in document.metadata.values() if value)
        metadata_doi = find_doi_in_text(metadata_text)
        if metadata_doi is not None:
            return DoiCandidate(doi=metadata_doi, source="pdf-metadata")

        page_texts = []
        if document.page_count:
            page_texts.append(document[0].get_text("text"))
            if document.page_count > 1:
                page_texts.append(document[document.page_count - 1].get_text("text"))
        text_doi = find_doi_in_text("\n".join(page_texts))
        if text_doi is not None:
            return DoiCandidate(doi=text_doi, source="pdf-text")
    return None


def find_doi_in_text(text: str) -> str | None:
    for match in DOI_PATTERN.finditer(text):
        doi = _clean_doi(match.group(1))
        if doi:
            return doi
    return None


def _clean_doi(raw: str) -> str:
    doi = raw.strip().rstrip(TRAILING_DOI_PUNCTUATION)
    while doi and doi[-1] in ")]}" and _has_unbalanced_closing(doi, doi[-1]):
        doi = doi[:-1].rstrip(TRAILING_DOI_PUNCTUATION)
    return doi.lower()


def _has_unbalanced_closing(value: str, closing: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    opening = pairs[closing]
    return value.count(closing) > value.count(opening)


# --- canonical user-input DOI normalization (backlog #58) ---------------------------------------------------
# Ordered so a longer prefix is stripped before a shorter one it contains.
_DOI_URL_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def normalize_doi(raw: str | None) -> str | None:
    """A pasted DOI in any common form — a bare DOI, a ``doi:`` prefix, or a ``https://doi.org/…`` /
    ``dx.doi.org`` URL — → the canonical bare, lower-cased DOI, or ``None`` if it does not look like a DOI
    at all (so callers fail honestly rather than resolving garbage). This is the ONE place every DOI-*add*
    path normalizes user input, so the agent and the Library "Add with DOI…" endpoint behave identically
    (backlog #58). It sits in front of the Crossref adapter's own bare-DOI cache-key normalizer.

    A DOI must start with the ``10.`` registrant prefix and contain a ``/`` — the liberal check the DOI
    spec implies (real identifiers are too varied for a strict regex to be safe)."""
    if not raw:
        return None
    text = raw.strip()
    low = text.lower()
    for prefix in _DOI_URL_PREFIXES:
        if low.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.strip().rstrip("/").strip().lower()
    if not text.startswith("10.") or "/" not in text:
        return None
    return text
