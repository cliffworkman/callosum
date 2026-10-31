"""Inc 611: scientific prose is not demoted or excluded as bibliography; genuine references still are.

Two mechanisms used to lose cited Discussion prose. (1) Inside an inferred reference region the prose veto capped
``biblio_score`` at 1.5, which a paragraph's own in-text citations exceed ("et al." + years = 1.8), so the
paragraph was labelled ``ref_region.member``. (2) A heading-based SQL filter excluded every chunk labelled
``references`` before retrieval, including mislabelled conclusions. Each fixture below is a SYNTHETIC paraphrase
of the shape that failed in the development pilot (chunk ids named only for traceability) -- no chunk id, paper,
DOI or title is special-cased by the code, and the case set is development evidence, not held-out validation.
"""

from __future__ import annotations

import pytest

from app.backend.pdf_processing.chunk_structure import (
    BIBLIOGRAPHIC,
    BODY_PROSE,
    REFERENCE_ENTRY,
    SCIENTIFIC,
    UNKNOWN,
    ChunkInput,
    biblio_score,
    classify_paper,
)
from app.backend.pdf_processing.source_role import (
    FRAGMENT,
    MIXED,
    NOT_PROSE,
    SUBSTANTIVE,
    assess_prose,
    strip_citations,
)
from app.backend.summarization.chunk_filtering import rescued_from_reference_label

# --- shapes of the known pilot failures (synthetic paraphrases) ---------------------------------

CONCLUSION_WITH_CITATIONS = (  # 5399-shape: conclusion carrying author-year citations (score 1.8)
    "Overall, several screening methods can identify careless responders in survey data. Removing these "
    "responders has been shown to reduce error and to yield more valid estimates (Curran, 2016; Huang et al., "
    "2015; Maniaci & Rogge, 2014), and we recommend that researchers apply these checks routinely."
)
ORPHAN_CITATION_TAIL = (  # 56894-shape: chunk begins mid-citation, then a clinical interpretation
    "al., 2004; Tucker et al., 2006; Nelson et al., 2007). Serotonergic agents could potentially be used to "
    "prevent cognitive decline, while further investigation is needed to understand the mechanisms involved."
)
SPLIT_SENTENCE_TAIL = "such studies are critical to developing imaging biomarkers of treatment response."  # 56618
CONCLUSION_IN_REFERENCES = (  # 58052-shape: a conclusion the section tracker labelled `references`
    "In conclusion, reduced transporter availability was observed in patients relative to controls, which may "
    "reflect an early stage of degeneration. The results also support a role for occupancy in the response of "
    "depressive symptoms to treatment (Smith et al., 2017)."
)
SUPERSCRIPT_CITED = (  # 67832-shape: Vancouver superscripts flattened into the text
    "Prior studies have used drawn images,31 and digitally altered full-color images.47-49 Given the design of the "
    "study, we needed more than 700 unique photographs, and the only reasonable solution was to alter the images of "
    "typical faces."
)
NULL_RESULT = (
    "Contrary to our hypothesis, we found no reliable difference between groups in recall accuracy (Smith et "
    "al., 2019; Jones, 2020; Okafor, 2021), and the effect did not approach significance in any of the sensitivity analyses."
)
LIMITATION = (
    "Several limitations should be noted. The sample was drawn from a single site (see Brown et al., 2018), "
    "so the findings may not generalise, and the cross-sectional design cannot establish the direction of effect."
)
QUALIFICATION = (
    "These estimates should be interpreted cautiously because the confidence intervals were wide (Lee & Park, "
    "2021), and the observed association may reflect unmeasured confounding rather than a causal pathway."
)

# --- genuine bibliography ------------------------------------------------------------------------

APA_ENTRY = (
    "Smith, J. A., & Jones, B. C. (2019). A study of things. Journal of Results, 12(3), 145-160. doi:10.1000/xyz"
)
CONSECUTIVE_ENTRIES = (
    "Brown, K. L. (2014). Memory and attention in older adults. Psychology and Aging, 29(2), 210-222. "
    "Garcia, M., & Lee, S. (2016). Attention training in later life. Neuropsychology, 30(4), 401-415."
)
SCIENTIFIC_SOUNDING_TITLE = (
    "Nguyen, T. H. (2018). Decreased transporter availability is associated with poorer treatment response in "
    "late-life depression. Journal of Affective Disorders, 41(2), 120-131."
)
TITLE_THEN_VANCOUVER_SOURCE = (  # a reference title alone reads like a finding; the source line betrays it
    "Activation of the receptor is induced by antidepressant drugs and is required for antidepressant-induced "
    "behavioral effects. J Neurosci 23: 349-357. Sackeim HA, Freeman J, McElhiney M, Coleman E, Prudic J,"
)
CROSS_PAGE_ENTRY_START = (  # an entry split across a page: the tail of one, the head of the next
    "C. A. (2008). Social influence in human face preference: Men and women are influenced more for long-term "
    "than short-term decisions. Evolution and Human Behavior, 29(2), 140-146."
)
VANCOUVER_NUMBERED = "12. Smith GS, Kramer E, Ma Y. The neuroanatomy of geriatric depression. Int J Psychiatry 2009."
DOI_ONLY_FRAGMENT = "https://doi.org/10.1016/j.bodyim.2018.10.002"
TITLE_FRAGMENT = (
    "is there for the use of art therapy in adults with cancer? a systematic review. Psychooncology 20, 135-145."
)
PROSE_THEN_ENTRIES = (
    "The effect persisted across every model we estimated in this sample. Our data therefore suggest that the "
    "manipulation was robust to the analytic choices we considered. Smith, J. A. (2019). A study of things. "
    "Journal of Results, 12(3), 145-160."
)


def _chunk(chunk_id: int, text: str, **kw) -> ChunkInput:  # type: ignore[no-untyped-def]
    return ChunkInput(chunk_id=chunk_id, paper_id=1, text=text, **kw)


def _in_region(text: str):  # type: ignore[no-untyped-def]
    return classify_paper([_chunk(1, text)], reference_region={1}, reference_region_source="anchored")[0]


# --- the pure assessment ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        CONCLUSION_WITH_CITATIONS,
        ORPHAN_CITATION_TAIL,
        CONCLUSION_IN_REFERENCES,
        SUPERSCRIPT_CITED,
        NULL_RESULT,
        LIMITATION,
        QUALIFICATION,
    ],
)
def test_cited_scientific_prose_is_substantive(text: str) -> None:
    assert assess_prose(text).outcome == SUBSTANTIVE


@pytest.mark.parametrize(
    "text",
    [
        APA_ENTRY,
        CONSECUTIVE_ENTRIES,
        SCIENTIFIC_SOUNDING_TITLE,
        TITLE_THEN_VANCOUVER_SOURCE,
        CROSS_PAGE_ENTRY_START,
        VANCOUVER_NUMBERED,
        DOI_ONLY_FRAGMENT,
        TITLE_FRAGMENT,
    ],
)
def test_genuine_references_are_never_substantive_prose(text: str) -> None:
    assert assess_prose(text).outcome != SUBSTANTIVE


def test_split_sentence_tail_is_an_ambiguous_fragment_not_substantive() -> None:
    assert assess_prose(SPLIT_SENTENCE_TAIL).outcome == FRAGMENT


def test_prose_followed_by_entries_is_mixed() -> None:
    assert assess_prose(PROSE_THEN_ENTRIES).outcome == MIXED


def test_a_single_title_like_sentence_before_a_source_is_not_mixed() -> None:
    """One leading "sentence" in a bibliography is almost always a title's tail, so MIXED needs two."""
    assert assess_prose(TITLE_THEN_VANCOUVER_SOURCE).outcome == NOT_PROSE


def test_citation_strip_removes_apparatus_but_keeps_the_claim() -> None:
    residual = strip_citations(CONCLUSION_WITH_CITATIONS)
    assert "Huang" not in residual and "2015" not in residual
    assert "reduce error" in residual


# --- the classifier ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [CONCLUSION_WITH_CITATIONS, ORPHAN_CITATION_TAIL, SUPERSCRIPT_CITED, NULL_RESULT, LIMITATION, QUALIFICATION],
)
def test_cited_prose_inside_a_reference_region_is_scientific_with_a_recorded_reason(text: str) -> None:
    result = _in_region(text)
    assert (result.chunk_type, result.evidence_role) == (BODY_PROSE, SCIENTIFIC)
    assert result.reason_codes[-1] in ("ref_region.prose_veto", "ref_region.prose_veto.citations_stripped")
    assert result.reference_region is True  # the anchored provenance is preserved, only overridden


@pytest.mark.parametrize("text", [CONCLUSION_WITH_CITATIONS, ORPHAN_CITATION_TAIL, NULL_RESULT])
def test_the_new_veto_catches_what_the_old_score_cap_demoted(text: str) -> None:
    """These carry enough in-text citation apparatus to exceed the old 1.5 cap -- the actual defect."""
    assert biblio_score(text) >= 1.5
    assert _in_region(text).reason_codes[-1] == "ref_region.prose_veto.citations_stripped"


def test_split_sentence_tail_in_a_region_is_unknown_never_bibliographic() -> None:
    result = _in_region(SPLIT_SENTENCE_TAIL)
    assert result.chunk_type == UNKNOWN and result.evidence_role != BIBLIOGRAPHIC
    assert result.reason_codes[-1] == "ref_region.ambiguous.prose_fragment"


def test_prose_then_entries_in_a_region_is_unknown_not_forced() -> None:
    result = _in_region(PROSE_THEN_ENTRIES)
    assert result.chunk_type == UNKNOWN
    assert result.reason_codes[-1] == "ref_region.ambiguous.mixed_prose_and_entries"


@pytest.mark.parametrize(
    "text", [APA_ENTRY, CONSECUTIVE_ENTRIES, SCIENTIFIC_SOUNDING_TITLE, TITLE_THEN_VANCOUVER_SOURCE, TITLE_FRAGMENT]
)
def test_anchored_genuine_references_stay_reference_entries(text: str) -> None:
    result = _in_region(text)
    assert (result.chunk_type, result.evidence_role) == (REFERENCE_ENTRY, BIBLIOGRAPHIC)
    assert result.reason_codes[-1] == "ref_region.member"


@pytest.mark.parametrize("text", [APA_ENTRY, CONSECUTIVE_ENTRIES, SCIENTIFIC_SOUNDING_TITLE])
def test_shape_only_genuine_references_stay_reference_entries(text: str) -> None:
    result = classify_paper([_chunk(1, text)])[0]
    assert result.chunk_type == REFERENCE_ENTRY
    assert result.reason_codes[-1] == "shape.biblio_score"


def test_cited_prose_outside_any_region_is_scientific() -> None:
    result = classify_paper([_chunk(1, CONCLUSION_WITH_CITATIONS)])[0]
    assert result.evidence_role == SCIENTIFIC


def test_caption_inside_a_region_is_not_promoted_to_body_prose() -> None:
    caption = (
        "Figure 2. Mean recall accuracy was lower in the older group than in the younger group (Smith et al., "
        "2019), and the difference remained after adjustment for education and baseline vocabulary."
    )
    assert _in_region(caption).chunk_type != BODY_PROSE


# --- the heading-label rescue (pre-retrieval) ----------------------------------------------------


@pytest.mark.parametrize("text", [CONCLUSION_IN_REFERENCES, LIMITATION, NULL_RESULT, SPLIT_SENTENCE_TAIL])
def test_mislabelled_prose_is_rescued_from_a_references_label(text: str) -> None:
    assert rescued_from_reference_label(text)


@pytest.mark.parametrize(
    "text",
    [
        APA_ENTRY,
        CONSECUTIVE_ENTRIES,
        SCIENTIFIC_SOUNDING_TITLE,
        TITLE_THEN_VANCOUVER_SOURCE,
        CROSS_PAGE_ENTRY_START,
        VANCOUVER_NUMBERED,
        DOI_ONLY_FRAGMENT,
        TITLE_FRAGMENT,
        "body",
        "",
    ],
)
def test_genuine_references_stay_excluded_by_the_references_label(text: str) -> None:
    assert not rescued_from_reference_label(text)


def test_publisher_notices_are_not_rescued_even_though_they_read_as_prose() -> None:
    notice = (
        "This is an open-access article distributed under the terms of the Creative Commons Attribution License, "
        "and use in other forums is permitted provided the original authors are credited."
    )
    assert assess_prose(notice).outcome == SUBSTANTIVE
    assert not rescued_from_reference_label(notice)


def test_rescue_memo_is_keyed_by_the_text_it_decides() -> None:
    """The decision depends only on the text, so the memo is keyed by a text fingerprint (inc 612)."""
    from app.backend.summarization.reference_rescue import rescue_decision

    assert rescue_decision(CONCLUSION_IN_REFERENCES) is True
    assert rescue_decision(APA_ENTRY) is False
    assert rescue_decision(CONCLUSION_IN_REFERENCES) is True  # a repeat is served the same, correct answer
    assert rescue_decision("") is False
