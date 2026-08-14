from __future__ import annotations

from pathlib import Path

from integrations.grobid.tei_parse import SectionSpan, parse_tei

FIXTURE = Path(__file__).parent / "fixtures" / "grobid" / "sample_fulltext.tei.xml"


def test_parse_tei_extracts_real_section_spans():
    spans = parse_tei(FIXTURE.read_bytes())
    assert len(spans) > 0
    assert all(isinstance(s, SectionSpan) for s in spans)
    assert all(s.title.strip() for s in spans)  # every span has a real, non-blank verbatim title
    # At least one span should have real bbox data, since the fixture was generated with teiCoordinates set
    assert any(len(s.bboxes) > 0 for s in spans)


def test_parse_tei_real_fixture_has_expected_named_sections():
    """Sanity-checks against the real fixture's known content (a PLOS ONE article with a numbered
    Introduction/Methods/Results/Discussion structure) so a parser that merely returns non-empty garbage
    would still fail."""
    spans = parse_tei(FIXTURE.read_bytes())
    titles = {s.title for s in spans}
    assert "Introduction" in titles
    assert "Discussion" in titles


def test_parse_tei_bboxes_and_pages_are_well_formed():
    spans = parse_tei(FIXTURE.read_bytes())
    intro = next(s for s in spans if s.title == "Introduction")
    assert intro.page_start <= intro.page_end
    assert len(intro.bboxes) > 0
    for page, x, y, w, h in intro.bboxes:
        assert isinstance(page, int)
        assert all(isinstance(v, float) for v in (x, y, w, h))
        assert page >= 1
    assert intro.page_start == min(b[0] for b in intro.bboxes)
    assert intro.page_end == max(b[0] for b in intro.bboxes)


def test_parse_tei_malformed_xml_raises():
    import pytest

    from integrations.grobid.tei_parse import GrobidParseError

    with pytest.raises(GrobidParseError):
        parse_tei(b"not xml at all <<<")


def test_parse_tei_empty_document_returns_empty_list():
    minimal_tei = b'<?xml version="1.0"?><TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body></body></text></TEI>'
    assert parse_tei(minimal_tei) == []


def test_parse_tei_div_without_head_is_skipped():
    """A body div with no <head> child (or a blank one) has no verbatim title to report -- it must be
    skipped rather than surfaced with an empty title."""
    tei = (
        b'<?xml version="1.0"?><TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        b'<div><p coords="1,10.0,10.0,100.0,10.0">orphan paragraph, no head</p></div>'
        b"</body></text></TEI>"
    )
    assert parse_tei(tei) == []


def test_parse_tei_div_with_head_but_no_coords_anywhere_is_skipped():
    """A div whose head/paragraphs carry no @coords at all (teiCoordinates wasn't requested, or GROBID had
    no location data) cannot be mapped back to a page/bbox -- must be skipped, not returned with an empty
    bboxes list standing in for real location data."""
    tei = (
        b'<?xml version="1.0"?><TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        b"<div><head>Untitled Section</head><p>no coordinates here</p></div>"
        b"</body></text></TEI>"
    )
    assert parse_tei(tei) == []


def test_parse_tei_rejects_a_doctype_declaration():
    """GROBID's own TEI output never has a DOCTYPE -- a response that includes one (a malicious/compromised
    GROBID instance, or a MITM on a non-loopback URL) must be refused outright rather than parsed, since a
    DOCTYPE is the only vector for both XXE and billion-laughs entity-expansion attacks. This is a real,
    checkable security requirement (flagged by this project's own security tooling during plan-writing), not
    speculative hardening."""
    import pytest

    from integrations.grobid.tei_parse import GrobidParseError

    malicious = (
        b'<?xml version="1.0"?><!DOCTYPE TEI [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b'<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>&xxe;</body></text></TEI>'
    )
    with pytest.raises(GrobidParseError):
        parse_tei(malicious)


def test_parse_tei_ignores_back_matter_divs():
    """GROBID's <back> element (references, acknowledgements, funding, availability) also contains <div>
    elements structurally identical to body sections. These must never be surfaced as content SectionSpans --
    only <text><body> divs are real document sections."""
    tei = (
        b'<?xml version="1.0"?><TEI xmlns="http://www.tei-c.org/ns/1.0"><text>'
        b'<body><div><head coords="1,1.0,1.0,10.0,10.0">Introduction</head>'
        b'<p coords="1,1.0,20.0,10.0,10.0">real body text</p></div></body>'
        b'<back><div type="references"><head coords="9,1.0,1.0,10.0,10.0">References</head>'
        b'<p coords="9,1.0,20.0,10.0,10.0">Smith, J. (2020)</p></div></back>'
        b"</text></TEI>"
    )
    spans = parse_tei(tei)
    titles = {s.title for s in spans}
    assert titles == {"Introduction"}
