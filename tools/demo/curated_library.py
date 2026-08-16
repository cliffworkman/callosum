"""Public, allowlisted inputs for the three-paper anomalous-is-bad demo library."""

from __future__ import annotations

import sqlite3
from typing import Any

CURATED_ON = "2026-08-13"

CORPUS: dict[int, dict[str, Any]] = {
    42: {
        "title": "What is good is beautiful (and what isn’t, isn’t): How moral character affects perceived facial attractiveness.",
        "authors": ["Dexian He", "Clifford I. Workman", "Xianyou He", "Anjan Chatterjee"],
        "csl_authors": [
            {"given": "Dexian", "family": "He"},
            {"given": "Clifford I.", "family": "Workman"},
            {"given": "Xianyou", "family": "He"},
            {"given": "Anjan", "family": "Chatterjee"},
        ],
        "year": 2024,
        "publication_date": "2024-08",
        "doi": "10.1037/aca0000454",
        "venue": "Psychology of Aesthetics, Creativity, and the Arts",
        "publisher": "American Psychological Association (APA)",
        "volume": "18",
        "issue": "4",
        "page": "633-641",
        "issn": ["1931-390X", "1931-3896"],
        "filename": "he-2021-good-beautiful-preprint.pdf",
        "license_name": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "redistribution_basis": (
            "The PsyArXiv preprint record applies CC BY 4.0 to its primary file; the bundled PDF matches "
            "the OSF file record's SHA-256 checksum."
        ),
        "canonical_url": "https://osf.io/preprints/psyarxiv/yj8ps",
        "article_url": "https://doi.org/10.1037/aca0000454",
        "verified_via": "OSF Preprints API license 563c1cf88c5e4a3877f9e96a and primary file 616d9a9d4154dc00f18b4b76",
        "notice": (
            "Bundled material is the 2021 PsyArXiv preprint, distributed with attribution under CC BY 4.0; "
            "the bibliographic record describes the final 2024 journal article."
        ),
        "automatic_topics": [
            "Psychology of Moral and Emotional Judgment",
            "Social Perception and Impression Formation",
            "Face Recognition and Perception",
        ],
    },
    67: {
        "title": "Morality is in the eye of the beholder: the neurocognitive basis of the ‘anomalous-is-bad’ stereotype",
        "authors": [
            "Clifford I. Workman",
            "Stacey Humphries",
            "Franziska Hartung",
            "Geoffrey K. Aguirre",
            "Joseph W. Kable",
            "Anjan Chatterjee",
        ],
        "csl_authors": [
            {"given": "Clifford I.", "family": "Workman"},
            {"given": "Stacey", "family": "Humphries"},
            {"given": "Franziska", "family": "Hartung"},
            {"given": "Geoffrey K.", "family": "Aguirre"},
            {"given": "Joseph W.", "family": "Kable"},
            {"given": "Anjan", "family": "Chatterjee"},
        ],
        "year": 2021,
        "publication_date": "2021-02-09",
        "doi": "10.1111/nyas.14575",
        "venue": "Annals of the New York Academy of Sciences",
        "publisher": "Wiley",
        "volume": "1494",
        "issue": "1",
        "page": "3-17",
        "issn": ["0077-8923", "1749-6632"],
        "filename": "workman-2021-morality-eye-beholder.pdf",
        "license_name": "Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)",
        "license_url": "https://creativecommons.org/licenses/by-nc/4.0/",
        "redistribution_basis": "The NCBI PMC Open Access API lists PMC8247878 in the OA subset under CC BY-NC.",
        "canonical_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC8247878/",
        "verified_via": "NCBI PMC Open Access API record for PMC8247878",
        "notice": "Distributed for this noncommercial public demonstration with attribution under CC BY-NC 4.0.",
        "automatic_topics": [
            "Psychology of Moral and Emotional Judgment",
            "Evolutionary Psychology and Human Behavior",
            "Face Recognition and Perception",
        ],
    },
    88: {
        "title": "Only human after all? a pre-registered study on gaze behavior and humanity attributions to people with facial difference",
        "authors": ["Pauline Rasset", "Benoît Montalan", "Jessica Mange"],
        "csl_authors": [
            {"given": "Pauline", "family": "Rasset"},
            {"given": "Benoît", "family": "Montalan"},
            {"given": "Jessica", "family": "Mange"},
        ],
        "year": 2023,
        "publication_date": "2023-12-12",
        "doi": "10.1371/journal.pone.0295617",
        "venue": "PLOS ONE",
        "publisher": "Public Library of Science (PLoS)",
        "volume": "18",
        "issue": "12",
        "page": "e0295617",
        "issn": ["1932-6203"],
        "filename": "rasset-2023-only-human.pdf",
        "license_name": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "redistribution_basis": "The PLOS article and PMC record identify the work as distributed under CC BY 4.0.",
        "canonical_url": "https://doi.org/10.1371/journal.pone.0295617",
        "verified_via": "PLOS ONE article license statement and NCBI PMC record PMC10715648",
        "notice": "Distributed with attribution under CC BY 4.0; preregistration: https://osf.io/grytk.",
        "automatic_topics": [
            "Psychology of Moral and Emotional Judgment",
            "Evolutionary Psychology and Human Behavior",
            "Face Recognition and Perception",
        ],
    },
}


def curated_abstract(con: sqlite3.Connection, paper_id: int) -> str | None:
    """Recover the article abstract from the deliberately curated documents, never a working library."""

    if paper_id == 42:
        row = con.execute(
            "SELECT text FROM chunks WHERE paper_id = ? AND text LIKE '%A well-documented%beauty%good%' ORDER BY id LIMIT 1",
            (paper_id,),
        ).fetchone()
        if row:
            text = str(row[0]).replace("\u00ad", "")
            start = text.find("A well-documented")
            end = text.find("Keywords:", start)
            return text[start:end].strip() if start >= 0 and end > start else text
        return None
    if paper_id == 67:
        row = con.execute(
            "SELECT text FROM chunks WHERE paper_id = ? AND text LIKE 'Are people with flawed faces%' ORDER BY id LIMIT 1",
            (paper_id,),
        ).fetchone()
        return str(row[0]).replace("\u00ad", "") if row else None
    for row in con.execute("SELECT text FROM chunks WHERE paper_id = ? ORDER BY id", (paper_id,)):
        text = str(row[0])
        if "\nAbstract\n" in text and "\nIntroduction\n" in text:
            return text.split("\nAbstract\n", 1)[1].split("\nIntroduction\n", 1)[0].strip()
    return None
