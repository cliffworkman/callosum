from __future__ import annotations

from app.backend.summarization.chunk_filtering import (
    exclude_repeated_boilerplate_chunks,
    is_front_matter_chunk,
    repeated_boilerplate_keys,
)
from app.backend.summarization.generators import SourceChunk

# The masthead/front-matter strings are the actual degenerate "sentences" from validation summary #7
# (papers scope) — see .claude/docs/specs/2026-06-25-synthesis-overview-design.md §0.
FRONT_MATTER = [
    "Original Manuscript",
    "Social Psychological and Personality Science 1-10 © The Author(s) 2021 Article reuse guidelines: "
    "sagepub.com/journals-permissions DOI: 10.1177/19485506211031722 journals.sagepub.com/home/spp",
    "r Human Brain Mapping 38:3391–3401 (2017) r",
    "Frederick S. Barrett ,1* Clifford I. Workman,1 Haris I. Sair,2",
    "Journal of Affective Disorders Reports 10 (2022) 100380 Contents lists available at ScienceDirect",
    "",
    "   ",
    # inc 125: real front matter that leaked into the verified claims of a LIVE papers-scope synthesis
    # (.local/visual/drive_inc124_live.py over papers 1-3) — the inc-123 classifier missed all of these.
    "Typical is Trustworthy - Evidence for a Generalized Heuristic",  # paper title
    "Hans Alves1 , Pinar Uğurlar2, and Christian Unkelbach3",  # author line (digit-after-name superscripts)
    "Association Between Serotonin Denervation and Resting-State Functional Connectivity in Mild Cognitive Impairment",  # title
    "Journal of Affective Disorders Reports 10 (2022) 100380",  # journal running header
    "Journal of Affective Disorders Reports",  # journal running header (bare)
    "Contract grant sponsor: National Institute of Health; Contract grant numbers: AG038893, AG041633, "
    "UL1 TR 001079, T32 DA007209 (to F.S.B.), and R03 DA042336 (to",  # funding / acknowledgment
    "1Department of Psychiatry and Behavioral Sciences, Johns Hopkins University School of Medicine, "
    "Baltimore, Maryland 2Department of Radiology and Radiological Sc",  # affiliation block (digit-prefix)
]

CONTENT = [
    "We found that people with facial anomalies are associated with negative characteristics.",
    "Paper A chunk 1 discusses cortex.",
    "Paper B chunk 1 discusses cortex.",
    "Anomalous faces were rated more negatively in terms of warmth and competence than typical faces.",
    "Participants completed a trust game in which they allocated money to partners shown as faces.",
    # inc 125: real body text that correctly got selected in the LIVE run — must stay CONTENT (don't over-flag).
    "Abstract When judging whether someone is trustworthy, people rely on the perceptual typicality of a "
    "person's face. We tested whether a more general typical-is-trustworthy heuristic governs these judgments.",
    "regarding the distance between the eyes or a certain nose shape. Typicality is also determined by frequency "
    "of instantiation, as a typical exemplar is one that resembles many other category members.",
    "Abstract: Resting-state functional connectivity alterations have been demonstrated in Alzheimer's disease "
    "and mild cognitive impairment before the onset of significant cognitive decline.",
]


def test_front_matter_strings_are_flagged() -> None:
    for s in FRONT_MATTER:
        assert is_front_matter_chunk(s) is True, f"expected front-matter: {s!r}"


def test_body_sentences_are_content() -> None:
    for s in CONTENT:
        assert is_front_matter_chunk(s) is False, f"expected content: {s!r}"


def _chunk(chunk_id: int, paper_id: int, page: int, text: str) -> SourceChunk:
    return SourceChunk(
        chunk_id=chunk_id,
        paper_id=paper_id,
        attachment_id=1,
        text=text,
        page_start=page,
        page_end=page,
        chunk_version="v1",
    )


# 2026-08-26: a real synthesis run against an unscoped ("all sections") query surfaced repeated per-page running
# headers as if they were substantive Discussion-section evidence -- the paper's own short-title line, repeated
# on every page, is a near-perfect textual match for a query about that same title. is_front_matter_chunk misses
# this (it's content-pattern-based; a plain title-case running header has no DOI/superscript/volume fingerprint),
# so this is a separate, repetition-based signal. See backlog #58.
HEADER_TEXT = "Workman et al. The “anomalous-is-bad” stereotype"


def test_repeated_short_header_is_excluded() -> None:
    chunks = [_chunk(i, paper_id=1, page=i, text=HEADER_TEXT) for i in range(1, 6)]
    chunks.append(_chunk(6, paper_id=1, page=3, text="Participants rated anomalous faces as less trustworthy."))
    result = exclude_repeated_boilerplate_chunks(chunks)
    assert [c.chunk_id for c in result] == [6]


def test_text_under_the_page_floor_is_kept() -> None:
    # Recurs on only 2 pages -- below REPEATED_BOILERPLATE_MIN_PAGE_COUNT (3), so it's kept.
    chunks = [_chunk(1, paper_id=1, page=1, text=HEADER_TEXT), _chunk(2, paper_id=1, page=2, text=HEADER_TEXT)]
    result = exclude_repeated_boilerplate_chunks(chunks)
    assert {c.chunk_id for c in result} == {1, 2}


def test_repetition_is_scoped_per_paper_not_cross_paper() -> None:
    # HEADER_TEXT repeats 3x in paper 1 (excluded there, leaving its one real content chunk) but appears only
    # once in paper 2, where it's kept -- one paper's repetition must not affect another paper's candidacy.
    chunks = [
        _chunk(1, paper_id=1, page=1, text=HEADER_TEXT),
        _chunk(2, paper_id=1, page=2, text=HEADER_TEXT),
        _chunk(3, paper_id=1, page=3, text=HEADER_TEXT),
        _chunk(4, paper_id=1, page=2, text="Anomalous faces were rated as less trustworthy than typical faces."),
        _chunk(5, paper_id=2, page=1, text=HEADER_TEXT),
    ]
    result = exclude_repeated_boilerplate_chunks(chunks)
    assert {c.chunk_id for c in result} == {4, 5}


def test_long_repeated_passage_is_not_excluded() -> None:
    long_text = " ".join(["word"] * 30)  # over REPEATED_BOILERPLATE_MAX_WORDS (25)
    chunks = [_chunk(i, paper_id=1, page=i, text=long_text) for i in range(1, 5)]
    result = exclude_repeated_boilerplate_chunks(chunks)
    assert {c.chunk_id for c in result} == {1, 2, 3, 4}


def test_repeated_header_with_a_varying_trailing_page_number_is_excluded() -> None:
    # Live regression (2026-08-26): a paper's Supplementary Materials running header embedded a different
    # trailing page number on every page ("...STEREOTYPE (SOM) 14", "...STEREOTYPE (SOM) 9", ...), which made
    # every occurrence's exact-normalized text unique and defeated repetition detection entirely -- confirmed
    # live, the fix without this had 7 of 8 retrieved chunks be this exact header. Fixed by stripping one
    # trailing numeric token before comparing.
    chunks = [
        _chunk(1, paper_id=1, page=24, text="THE “ANOMALOUS-IS-BAD” STEREOTYPE (SOM) 9"),
        _chunk(2, paper_id=1, page=25, text="THE “ANOMALOUS-IS-BAD” STEREOTYPE (SOM) 10"),
        _chunk(3, paper_id=1, page=26, text="THE “ANOMALOUS-IS-BAD” STEREOTYPE (SOM) 11"),
        _chunk(4, paper_id=1, page=27, text="THE “ANOMALOUS-IS-BAD” STEREOTYPE (SOM) 12"),
        _chunk(5, paper_id=1, page=2, text="An “anomalous-is-bad” stereotype is expressed in negative attitudes."),
    ]
    result = exclude_repeated_boilerplate_chunks(chunks)
    assert {c.chunk_id for c in result} == {5}


def test_a_paper_is_never_left_with_zero_chunks() -> None:
    # Every chunk in this paper "qualifies" as repeated boilerplate -- the safety valve keeps them all rather
    # than silencing the paper entirely.
    chunks = [_chunk(i, paper_id=1, page=i, text=HEADER_TEXT) for i in range(1, 4)]
    result = exclude_repeated_boilerplate_chunks(chunks)
    assert {c.chunk_id for c in result} == {1, 2, 3}


def test_detection_is_independent_of_a_section_filtered_candidate_list() -> None:
    """inc 577: DETECTION must see the whole paper; the section filter narrows only what is returned.

    Before the split, the two were fused, so the verdict depended on which candidate list happened to
    be handed in. Measured on the real library, a sections=['methods'] synthesis kept 112
    running-head chunks that whole-paper scope removes -- a header on five pages survived into too
    few of the selected-section chunks to reach the three-page floor.
    """
    whole_paper = [
        _chunk(1, paper_id=1, page=1, text=HEADER_TEXT),
        _chunk(2, paper_id=1, page=2, text=HEADER_TEXT),
        _chunk(3, paper_id=1, page=3, text=HEADER_TEXT),
        _chunk(4, paper_id=1, page=3, text="Anomalous faces were rated as less trustworthy than typical faces."),
    ]
    # The 'methods' section contributes only ONE of the header's occurrences.
    section_scoped = [whole_paper[0], whole_paper[3]]

    # Fused (old) behaviour: one occurrence never reaches the floor, so the header survives.
    assert {c.chunk_id for c in exclude_repeated_boilerplate_chunks(section_scoped)} == {1, 4}

    # Split (new) behaviour: keys come from the whole paper, so the header is excluded even though
    # the candidate list contains it only once.
    keys = repeated_boilerplate_keys(whole_paper)
    assert {c.chunk_id for c in exclude_repeated_boilerplate_chunks(section_scoped, keys=keys)} == {4}


def test_precomputed_keys_still_never_empty_a_paper() -> None:
    """The safety valve survives the split: a paper is never left with zero chunks."""
    whole_paper = [_chunk(i, paper_id=1, page=i, text=HEADER_TEXT) for i in range(1, 4)]
    keys = repeated_boilerplate_keys(whole_paper)
    result = exclude_repeated_boilerplate_chunks([whole_paper[0]], keys=keys)
    assert {c.chunk_id for c in result} == {1}


def test_omitting_keys_reproduces_the_previous_behaviour_exactly() -> None:
    chunks = [_chunk(i, paper_id=1, page=i, text=HEADER_TEXT) for i in range(1, 4)]
    chunks.append(_chunk(9, paper_id=1, page=3, text="Real content that should always survive."))
    assert {c.chunk_id for c in exclude_repeated_boilerplate_chunks(chunks)} == {
        c.chunk_id for c in exclude_repeated_boilerplate_chunks(chunks, keys=repeated_boilerplate_keys(chunks))
    }
