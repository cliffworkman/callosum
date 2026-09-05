"""Regression coverage for structural chunk classification (inc 577, H1a).

The maintainer-adjudicated fixtures from the evidence-hygiene study are promoted here as explicit
cases. Every input is built from literals: `classify_paper` performs no I/O by design, so a test
never needs a database, a PDF, or a network call.

The load-bearing property these tests protect is NEGATIVE -- classification must not become a way to
lose scientific evidence. Several cases below assert that something is *not* classified as
excludable, and those matter more than the positive ones.
"""

from __future__ import annotations

import json

from app.backend.pdf_processing.chunk_structure import (
    BIBLIOGRAPHIC,
    BODY_PROSE,
    CAPTION,
    CITATION_INSTRUCTION,
    KEYWORD_LINE,
    PUBLICATION_METADATA,
    REFERENCE_ENTRY,
    RUNNING_FOOTER,
    RUNNING_HEAD,
    SCIENTIFIC,
    STRUCTURAL,
    TABLE_CELL_DEBRIS,
    UNKNOWN,
    ChunkInput,
    classify_paper,
)

PROSE = (
    "Participants completed the task while we recorded responses and analysed the resulting data "
    "carefully across every experimental condition in turn, and the effect persisted throughout."
)


def _bbox(x0: float, y0: float, x1: float, y1: float, *, page: int = 1, block: int = 0) -> str:
    return json.dumps([{"page": page, "block": block, "line": 0, "span": 0, "x0": x0, "y0": y0, "x1": x1, "y1": y1}])


def _chunk(chunk_id: int, text: str, **kw) -> ChunkInput:
    return ChunkInput(chunk_id=chunk_id, paper_id=1, text=text, **kw)


def _body_column(n: int = 4) -> list[ChunkInput]:
    """Enough real body prose for `calibrate_column_width` to establish the paper's own column."""
    return [
        _chunk(100 + i, PROSE * 2, page_start=1, bbox_json=_bbox(50, 100 + 20 * i, 300, 115 + 20 * i, block=i))
        for i in range(n)
    ]


def _typed(results) -> dict[int, str]:
    return {r.chunk_id: r.chunk_type for r in results}


# --- maintainer-adjudicated fixtures -----------------------------------------------------------


def test_f44485_caption_stating_a_finding_is_a_caption_and_scientific() -> None:
    """A caption that states a relationship is potentially proposition-bearing (maintainer ruling)."""
    result = classify_paper(
        [
            _chunk(
                1,
                "Table 3 The first component explained 18.3% of the variance "
                "and captured support for neuroessentialist attitudes.",
            )
        ]
    )[0]
    assert result.chunk_type == CAPTION
    assert result.evidence_role == SCIENTIFIC


def test_f39057_caption_reporting_effects_is_a_caption_and_scientific() -> None:
    result = classify_paper(
        [
            _chunk(
                1,
                "Figure 1. Effects of injury severity on global network measures. Comparison among subjects with mTBI.",
            )
        ]
    )[0]
    assert result.chunk_type == CAPTION
    assert result.evidence_role == SCIENTIFIC


def test_f45476_sentence_about_a_table_is_prose_not_a_caption() -> None:
    """Adjudicated FALSE POSITIVE: opens like a caption, but is body prose.

    A caption LABELS its object; this sentence predicates something ABOUT it. Excluding it would
    have removed real evidence, which is exactly the failure this discriminator prevents.
    """
    result = classify_paper(
        [
            _chunk(
                1,
                "Table 4 below shows the number of extracted statistics and "
                "the number of identified errors for both Wicherts et al. "
                "and statcheck in this reanalysis.",
            )
        ]
    )[0]
    assert result.chunk_type != CAPTION
    assert result.evidence_role != STRUCTURAL


def test_f26458_subfigure_label_is_not_publication_metadata() -> None:
    """Adjudicated FALSE POSITIVE: the "(c)" is a sub-figure label, not a copyright mark."""
    result = classify_paper(
        [
            _chunk(
                1,
                "(height), (c) placed onto a plain white background using "
                "the GIMP 2 software package, and then rated by every "
                "participant for attractiveness in a randomized order.",
            )
        ]
    )[0]
    assert result.chunk_type != PUBLICATION_METADATA
    assert result.evidence_role == SCIENTIFIC


def test_f29836_bare_statistic_is_structural_not_scientific() -> None:
    """An orphaned value cannot identify what it is evidence about (maintainer principle)."""
    cells = [
        _chunk(200 + i, t, page_start=2, bbox_json=_bbox(50 + 60 * i, 300, 90 + 60 * i, 310, page=2, block=10 + i))
        for i, t in enumerate(["p = 0.146", "0.42", "12.7", "n = 30"])
    ]
    typed = {r.chunk_id: r for r in classify_paper(_body_column() + cells)}
    assert typed[200].evidence_role == STRUCTURAL


def test_f36125_results_prose_inside_a_reference_region_is_vetoed_back_to_prose() -> None:
    """Region membership is strong structural evidence, NOT final chunk identity."""
    text = (
        "The analysis showed no reliable difference between conditions, and scenarios featuring "
        "negative outcomes contained the same number of words as the other scenarios did."
    )
    result = classify_paper([_chunk(1, text)], reference_region={1}, reference_region_source="anchored")[0]
    assert result.chunk_type == BODY_PROSE
    assert result.reason_codes[-1] == "ref_region.prose_veto"
    assert result.reference_region is True  # the signal is recorded even though it was overridden


# --- the guard that stops classification eating evidence ---------------------------------------


def test_isolated_short_evidence_is_never_table_cell_debris() -> None:
    """A lone narrow chunk is not debris. Debris arrives with grid siblings; a reported effect size
    does not, and `grid_support` is what keeps the two apart."""
    lonely = _chunk(300, "d = 0.42, 95% CI [0.11, 0.73]", page_start=1, bbox_json=_bbox(50, 400, 140, 412))
    result = {r.chunk_id: r for r in classify_paper(_body_column() + [lonely])}[300]
    assert result.chunk_type != TABLE_CELL_DEBRIS


def test_unknown_is_a_real_answer_and_never_bibliographic_or_dropped() -> None:
    result = classify_paper([_chunk(1, "between visits (all p > 0.7).")])[0]
    assert result.chunk_type == UNKNOWN
    assert result.evidence_role not in (BIBLIOGRAPHIC, STRUCTURAL)


def test_classification_never_alters_chunk_text() -> None:
    original = "Text with a ﬁ ligature, a soft­hyphen and a tempo- ral line break."
    chunk = _chunk(1, original)
    classify_paper([chunk])
    assert chunk.text == original


# --- ordinary structural types ------------------------------------------------------------------


def test_reference_entry_typing_and_bibliographic_role() -> None:
    result = classify_paper(
        [
            _chunk(
                1,
                "Smith, J. A., & Jones, B. C. (2019). A study of things. "
                "Journal of Results, 12(3), 145-160. doi:10.1000/xyz",
            )
        ]
    )[0]
    assert result.chunk_type == REFERENCE_ENTRY
    assert result.evidence_role == BIBLIOGRAPHIC


def test_no_doi_reference_still_types_as_a_reference() -> None:
    """Older works often have no printed DOI; shape must carry the case."""
    result = classify_paper(
        [
            _chunk(
                1,
                "Karlins, M., Coffman, T. L., & Walters, G. C. (1969). On the "
                "fading of social stereotypes. Journal of Personality, 13, 1-16.",
            )
        ]
    )[0]
    assert result.chunk_type == REFERENCE_ENTRY


def test_running_head_and_footer_stay_distinct() -> None:
    head = classify_paper([_chunk(1, "FACIAL SCARS: WHAT MATTERS?")], repeated={1: "top"})[0]
    foot = classify_paper([_chunk(2, "Personality Science 2022, Vol. 3")], repeated={2: "bottom"})[0]
    assert head.chunk_type == RUNNING_HEAD
    assert foot.chunk_type == RUNNING_FOOTER
    assert head.repeated_boilerplate is True


def test_keyword_line_and_citation_instruction() -> None:
    kw = classify_paper([_chunk(1, "Keywords: beauty; disfigurement; face perception; culture")])[0]
    ci = classify_paper([_chunk(2, "Please cite this article as: Davies-Jenkins, C. W., et al.")])[0]
    assert kw.chunk_type == KEYWORD_LINE
    assert ci.chunk_type == CITATION_INSTRUCTION
    assert {kw.evidence_role, ci.evidence_role} == {STRUCTURAL}


def test_abstract_prose_is_scientific_and_not_swept_into_front_matter() -> None:
    result = classify_paper([_chunk(1, PROSE, section="abstract")])[0]
    assert result.evidence_role == SCIENTIFIC


def test_every_chunk_gets_a_verdict_with_a_reason_code() -> None:
    chunks = _body_column() + [_chunk(500, ""), _chunk(501, "Methods"), _chunk(502, "= - x")]
    results = classify_paper(chunks)
    assert len(results) == len(chunks)
    assert all(r.reason_codes for r in results)
    assert all(r.derivation_version for r in results)


def test_missing_geometry_degrades_to_text_rules_rather_than_guessing() -> None:
    """No bbox means width rules are skipped, not run against an invented scale."""
    typed = _typed(classify_paper([_chunk(1, "p = 0.146"), _chunk(2, PROSE)]))
    assert typed[1] != TABLE_CELL_DEBRIS
    assert typed[2] == BODY_PROSE
