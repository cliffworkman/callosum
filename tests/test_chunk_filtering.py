from __future__ import annotations

from app.backend.summarization.chunk_filtering import is_front_matter_chunk

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
]

CONTENT = [
    "We found that people with facial anomalies are associated with negative characteristics.",
    "Paper A chunk 1 discusses cortex.",
    "Paper B chunk 1 discusses cortex.",
    "Anomalous faces were rated more negatively in terms of warmth and competence than typical faces.",
    "Participants completed a trust game in which they allocated money to partners shown as faces.",
]


def test_front_matter_strings_are_flagged() -> None:
    for s in FRONT_MATTER:
        assert is_front_matter_chunk(s) is True, f"expected front-matter: {s!r}"


def test_body_sentences_are_content() -> None:
    for s in CONTENT:
        assert is_front_matter_chunk(s) is False, f"expected content: {s!r}"
