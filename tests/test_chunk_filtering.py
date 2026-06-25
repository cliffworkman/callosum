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
