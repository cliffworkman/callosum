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
`_decode_and_reject_doctype` refuses any document that has one BEFORE handing it to ElementTree -- a DOCTYPE is
the only vector for both XXE and entity-expansion attacks, so rejecting it outright is a complete, auditable
defense that needs no new dependency (`defusedxml` was considered and declined: a good library, but an unneeded
second dependency when a small guard closes the exact same gap for this specific, narrow use case).

An earlier version of this guard did a raw ASCII byte-substring check (`b"<!DOCTYPE" in tei_xml.upper()`)
directly on the undecoded bytes. A code review caught a real bypass: ElementTree auto-detects encoding from
the document's own `<?xml ... encoding="..."?>` declaration (or a BOM), so a non-UTF-8-encoded payload has no
contiguous `<!DOCTYPE` ASCII byte sequence for that check to find, yet ElementTree still parses it -- and
still expands internal entities. Requiring strict UTF-8 decoding up front (GROBID always emits UTF-8) closes
the BOM'd cases for free: every UTF-16/UTF-32 byte-order mark starts with a byte (0xFF, 0xFE, or a leading
0x00 followed by one) that is never a valid UTF-8 lead byte, so `bytes.decode("utf-8", strict)` already fails
on any of them. But a *bare* UTF-16/UTF-32 payload with NO BOM was verified to survive strict UTF-8 decoding:
each ASCII byte of the original document is interleaved with literal 0x00 bytes, and 0x00 (NUL, U+0000) is a
perfectly valid single-byte UTF-8 codepoint on its own -- so the "decode" succeeds, just producing text with a
NUL wedged between every character, which no longer contains "<!DOCTYPE" as a contiguous substring. Worse,
this was empirically confirmed to still parse via `ET.fromstring()` with the internal entity fully expanded
(CPython's pyexpat re-encodes a `str` argument to UTF-8 before handing it to the underlying C parser, and the
embedded NULs don't stop it from reconstructing the original tag/entity structure). Since NUL is not a legal
XML character under the spec (real GROBID output -- or any well-formed XML -- never contains one), rejecting
any decoded text containing `"\x00"` closes this second, deeper bypass; combined with the DOCTYPE substring
check running against the *decoded* text (not raw bytes) and `ET.fromstring()` being called on that same
already-decoded `str` (removing ElementTree's own byte-level encoding autodetection from the trust boundary
entirely), this closes both the reported bypass and the related no-BOM variant found while fixing it."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

_TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


class GrobidParseError(Exception):
    """The TEI-XML response could not be parsed. Fails closed -- callers must not proceed with partial data."""


def _decode_and_reject_doctype(tei_xml: bytes) -> str:
    """Strictly decode `tei_xml` as UTF-8 (GROBID's only real encoding) and refuse any document containing a
    DOCTYPE declaration or an embedded NUL character -- see the module docstring for why both checks are
    necessary and must run against the *decoded text*, not the raw bytes. Returns the decoded text so callers
    hand ElementTree an already-decoded `str`, never raw bytes it could re-interpret under a different
    encoding."""
    try:
        text = tei_xml.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GrobidParseError(f"TEI-XML is not valid UTF-8 (GROBID only emits UTF-8): {exc}") from exc
    if "\x00" in text:
        raise GrobidParseError(
            "refusing to parse TEI-XML containing an embedded NUL character (not legal XML, not expected from GROBID)"
        )
    if "<!DOCTYPE" in text.upper():
        raise GrobidParseError("refusing to parse TEI-XML containing a DOCTYPE declaration (not expected from GROBID)")
    return text


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
    text = _decode_and_reject_doctype(tei_xml)
    try:
        root = ET.fromstring(text)
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
