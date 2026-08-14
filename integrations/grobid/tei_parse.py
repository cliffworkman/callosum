"""Parses GROBID's TEI-XML output into section spans with verbatim titles and bounding boxes. No normalization
here -- this is the ground-truth layer; canonical-family classification is section_classify.py's job.

Verified against a real GROBID 0.8.x response (`tests/fixtures/grobid/sample_fulltext.tei.xml`, generated with
`teiCoordinates=div,head,p`): body sections are flat `<text><body><div>` children (no nesting even for
numbered subsections like "2.2.3") each carrying a `<head>` title child; `@coords` never appears on the `<div>`
element itself, only on `<head>` and `<p>` -- so a section's bounding boxes are gathered from its head plus
every direct `<p>` child. `<back>` (references/acknowledgements/funding/availability) is a `<text>` sibling of
`<body>` with structurally identical `<div>` elements and must be excluded -- only `<text><body>` divs are real
document sections.

Uses stdlib xml.etree.ElementTree -- deliberately NOT relying on its default entity-handling alone (a genuine
security tool flagged this during plan-writing: ElementTree blocks EXTERNAL entity fetches by default in modern
Python, but has no built-in defense against internal entity-expansion ("billion laughs") denial-of-service).
Since this parses a response from a network service and legitimate GROBID TEI output never contains a DOCTYPE,
`_reject_doctype` refuses any document that has one BEFORE handing it to ElementTree -- a DOCTYPE is the only
vector for both XXE and entity-expansion attacks, so rejecting it outright is a complete, auditable defense
that needs no new dependency (`defusedxml` was considered and declined: a good library, but an unneeded second
dependency when a three-line guard closes the exact same gap for this specific, narrow use case)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

_TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


class GrobidParseError(Exception):
    """The TEI-XML response could not be parsed. Fails closed -- callers must not proceed with partial data."""


def _reject_doctype(tei_xml: bytes) -> None:
    """Refuse any document containing a DOCTYPE declaration -- legitimate GROBID TEI output never has one, and
    a DOCTYPE is required for both XXE and billion-laughs attacks. Checked on the raw bytes, before ElementTree
    ever sees them."""
    if b"<!DOCTYPE" in tei_xml.upper():
        raise GrobidParseError("refusing to parse TEI-XML containing a DOCTYPE declaration (not expected from GROBID)")


@dataclass(frozen=True)
class SectionSpan:
    title: str
    page_start: int
    page_end: int
    bboxes: list[tuple[int, float, float, float, float]] = field(default_factory=list)


def _parse_coords(coords_attr: str | None) -> list[tuple[int, float, float, float, float]]:
    """Parse a GROBID `@coords` attribute: `"page,x,y,w,h"`, semicolon-separated for multi-region (multi-line)
    spans -- confirmed against the real fixture, e.g. `"1,44.45,209.32,514.12,9.16;1,44.45,221.28,..."`."""
    if not coords_attr:
        return []
    out = []
    for region in coords_attr.split(";"):
        parts = region.strip().split(",")
        if len(parts) != 5:
            continue
        try:
            page, x, y, w, h = int(float(parts[0])), *(float(p) for p in parts[1:])
        except ValueError:
            continue
        out.append((page, x, y, w, h))
    return out


def parse_tei(tei_xml: bytes) -> list[SectionSpan]:
    """Extract section spans from GROBID TEI-XML body divs. A div is skipped (never yielded as a span) if it
    has no verbatim `<head>` title, or if neither its head nor any of its paragraphs carry `@coords` data --
    a section with no location data can't be mapped to a page/chunk anyway, and reporting it as a zero-bbox
    span would look like a real (but empty) location result rather than an absence."""
    _reject_doctype(tei_xml)
    try:
        root = ET.fromstring(tei_xml)
    except ET.ParseError as exc:
        raise GrobidParseError(f"malformed TEI-XML: {exc}") from exc

    spans: list[SectionSpan] = []
    for div in root.findall(".//tei:text/tei:body/tei:div", _TEI_NS):
        head = div.find("tei:head", _TEI_NS)
        title = "".join(head.itertext()).strip() if head is not None else ""
        if not title:
            continue

        bboxes: list[tuple[int, float, float, float, float]] = []
        if head is not None:
            bboxes.extend(_parse_coords(head.get("coords")))
        for p in div.findall("tei:p", _TEI_NS):
            bboxes.extend(_parse_coords(p.get("coords")))
        if not bboxes:
            continue

        pages = sorted({b[0] for b in bboxes})
        spans.append(SectionSpan(title=title, page_start=pages[0], page_end=pages[-1], bboxes=bboxes))
    return spans
