"""``CaptureEnvelope`` v1 — Callosum's own bounded browser-capture DTO (#61 Phase 1).

This is deliberately **Callosum-owned and versioned from the first commit**. Zotero item JSON is never
the wire format: a future translator-backed producer adapts *into* this envelope behind a boundary, so
the browser API never becomes a second reference-manager data model. Other future front ends
(clipboard, share sheet, highlighted-reference, camera/OCR — backlog #25) can produce the same shape
and converge on the same identity path.

Size discipline, per the boundary rule (rule #4): every string is length-capped AND every list is
cardinality-capped. Field caps alone are not a request-size boundary — ten thousand one-character
authors would pass every per-field check — and neither is enough on its own, because Pydantic only
sees the body *after* it has been read and parsed. The streaming total-body cap in the router is the
actual first line of defense; these are the second.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CAPTURE_ENVELOPE_VERSION = 1

# Cardinality caps. Generous for real scholarly records (a 500-author physics paper is real), bounded
# far below anything that could be used to make parsing or storage expensive.
MAX_CREATORS = 500
MAX_PROVENANCE_ENTRIES = 40
MAX_IDENTIFIER_LEN = 300
MAX_URL_LEN = 2000
MAX_TITLE_LEN = 2000
MAX_ABSTRACT_LEN = 20000


class CaptureCreator(BaseModel):
    """One author/creator as the page exposed it. Deliberately not parsed into a name model here —
    ``family``/``given`` when the page gave them separately, ``literal`` when it gave one string."""

    model_config = {"extra": "forbid"}

    family: str | None = Field(default=None, max_length=200)
    given: str | None = Field(default=None, max_length=200)
    literal: str | None = Field(default=None, max_length=400)


class CaptureIdentifiers(BaseModel):
    """Stable scholarly identifiers observed on the page. Absent is meaningfully different from empty."""

    model_config = {"extra": "forbid"}

    doi: str | None = Field(default=None, max_length=MAX_IDENTIFIER_LEN)
    pmid: str | None = Field(default=None, max_length=40)
    pmcid: str | None = Field(default=None, max_length=40)
    arxiv: str | None = Field(default=None, max_length=60)
    isbn: str | None = Field(default=None, max_length=40)
    issn: str | None = Field(default=None, max_length=40)


class CaptureEnvelope(BaseModel):
    """What the extension observed on one page, in Callosum's own vocabulary.

    ``envelope_version`` is pinned rather than defaulted-and-ignored: a future producer sending v2 must
    be refused explicitly rather than silently reinterpreted as v1.
    """

    model_config = {"extra": "forbid"}

    envelope_version: Literal[1]

    # --- capture context -------------------------------------------------------------------------
    source_url: str = Field(max_length=MAX_URL_LEN)
    captured_at: str = Field(max_length=64)  # ISO-8601 from the browser; display/provenance only
    # How this envelope was produced. Phase 1 ships "generic" and "direct-pdf"; "zotero-translator" is
    # reserved so a later producer does not need a new field.
    producer_kind: Literal["generic", "direct-pdf", "zotero-translator"] = "generic"
    producer_label: str | None = Field(default=None, max_length=200)

    # --- the record ------------------------------------------------------------------------------
    item_type: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=MAX_TITLE_LEN)
    creators: list[CaptureCreator] = Field(default_factory=list, max_length=MAX_CREATORS)
    container_title: str | None = Field(default=None, max_length=600)
    publisher: str | None = Field(default=None, max_length=400)
    year: int | None = Field(default=None, ge=1000, le=2100)
    publication_date: str | None = Field(default=None, max_length=40)
    volume: str | None = Field(default=None, max_length=40)
    issue: str | None = Field(default=None, max_length=40)
    pages: str | None = Field(default=None, max_length=60)
    language: str | None = Field(default=None, max_length=40)
    abstract: str | None = Field(default=None, max_length=MAX_ABSTRACT_LEN)
    identifiers: CaptureIdentifiers = Field(default_factory=CaptureIdentifiers)

    # --- provenance --------------------------------------------------------------------------------
    # Which page signal each field came from, e.g. {"doi": "citation_doi", "title": "json-ld"}. Lets
    # Callosum answer "how was this record obtained" at field granularity, which `imported_source`
    # alone cannot. Bounded like every other client-supplied map.
    field_provenance: dict[str, str] = Field(default_factory=dict, max_length=MAX_PROVENANCE_ENTRIES)

    # --- attachment intent ------------------------------------------------------------------------
    # Whether the ACTIVE BROWSER TAB itself supplied PDF bytes the user had already opened. This is
    # never a URL for Callosum to fetch: a URL is not an accessible PDF, and turning one into a
    # backend fetch is exactly the acquisition behavior issue #61 forbids by construction.
    pdf_bytes_from_active_tab: bool = False

    def first_author_family(self) -> str | None:
        """The first creator's family name, for the title/year/author identity tuple."""
        for creator in self.creators:
            if creator.family and creator.family.strip():
                return creator.family.strip()
            if creator.literal and creator.literal.strip():
                # "Family, Given" is the shape discovery already normalizes; fall back to the last word.
                literal = creator.literal.strip()
                return literal.split(",", 1)[0].strip() if "," in literal else literal.rsplit(" ", 1)[-1]
        return None

    def author_strings(self) -> list[str]:
        """Creators as the "Family, Given" strings the existing admission helpers accept."""
        out: list[str] = []
        for creator in self.creators:
            if creator.family:
                out.append(f"{creator.family}, {creator.given}" if creator.given else creator.family)
            elif creator.literal:
                out.append(creator.literal)
        return out
