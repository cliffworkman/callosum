"""Public, allowlisted inputs for the anomalous-is-bad demo library."""

from __future__ import annotations

import sqlite3
from typing import Any

CURATED_ON = "2026-08-13"
CORPUS_GROWN_ON = "2026-08-30"

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
        "bundled_material": "complete-pdf",
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
        "bundled_material": "complete-pdf",
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
        "bundled_material": "complete-pdf",
    },
    90: {
        "title": "Evidence against the “anomalous-is-bad” stereotype in Hadza hunter gatherers",
        "authors": ["Clifford I. Workman", "Kristopher M. Smith", "Coren L. Apicella", "Anjan Chatterjee"],
        "csl_authors": [
            {"given": "Clifford I.", "family": "Workman"},
            {"given": "Kristopher M.", "family": "Smith"},
            {"given": "Coren L.", "family": "Apicella"},
            {"given": "Anjan", "family": "Chatterjee"},
        ],
        "year": 2022,
        "publication_date": "2022-05-24",
        "doi": "10.1038/s41598-022-12440-w",
        "venue": "Scientific Reports",
        "publisher": "Springer Science and Business Media LLC",
        "volume": "12",
        "issue": None,
        "page": "8693",
        "issn": ["2045-2322"],
        "filename": "workman-2022-hadza-anomalous-is-bad.pdf",
        "license_name": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "redistribution_basis": (
            "Scientific Reports is fully Gold Open Access; the Crossref license record and the Europe PMC "
            "record for PMC9130266 both state CC BY 4.0."
        ),
        "canonical_url": "https://doi.org/10.1038/s41598-022-12440-w",
        "verified_via": "Crossref API license record and Europe PMC record for PMC9130266 (license: cc by)",
        "notice": "Distributed with attribution under CC BY 4.0.",
        "abstract": (
            "People have an “anomalous-is-bad” stereotype whereby they make negative inferences about "
            "the moral character of people with craniofacial anomalies like scars. This stereotype is "
            "hypothesized to be a byproduct of adaptations for avoiding pathogens. However, evidence for the "
            "anomalous-is-bad stereotype comes from studies of European and North American populations; the "
            "byproduct hypothesis would predict universality of the stereotype. We presented 123 Hadza across "
            "ten camps pairs of morphed Hadza faces—each with one face altered to include a scar—and "
            "asked who they expected to be more moral and a better forager. Hadza with minimal exposure to "
            "other cultures chose at chance for both questions. Hadza with greater exposure to other cultures, "
            "however, expected the scarred face to be less moral and a better forager. These results suggest "
            "the anomalous-is-bad stereotype may be culturally shared or learned erroneously through "
            "associations with population-level differences, providing evidence against a universal pathogen "
            "avoidance byproduct hypothesis."
        ),
        "openalex_work_id": "W4281398376",
        "openalex_cited_by_count": 20,
        "automatic_topics": [
            "Psychology of Moral and Emotional Judgment",
            "Evolutionary Psychology and Human Behavior",
            "Body Image and Dysmorphia Studies",
        ],
        "bundled_material": "complete-pdf",
    },
    89: {
        "title": "Changing the narrative: stories reduce biases against anomalous faces",
        "authors": [
            "Nadir Bilici",
            "Mariola Paruzel-Czachura",
            "Clifford I. Workman",
            "Stacey Humphries",
            "Roy H. Hamilton",
            "Anjan Chatterjee",
        ],
        "csl_authors": [
            {"given": "Nadir", "family": "Bilici"},
            {"given": "Mariola", "family": "Paruzel-Czachura"},
            {"given": "Clifford I.", "family": "Workman"},
            {"given": "Stacey", "family": "Humphries"},
            {"given": "Roy H.", "family": "Hamilton"},
            {"given": "Anjan", "family": "Chatterjee"},
        ],
        "year": 2026,
        "publication_date": "2026-06-12",
        "doi": "10.1186/s40359-026-04964-x",
        "venue": "BMC Psychology",
        "publisher": "Springer Science and Business Media LLC",
        "volume": "14",
        "issue": "1",
        "page": "1205",
        "issn": ["2050-7283"],
        "filename": None,
        "license_name": "Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)",
        "license_url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
        "redistribution_basis": (
            "The Crossref license record and the Semantic Scholar Graph API (openAccessPdf.license) both state "
            "CC BY-NC-ND 4.0 -- the No-Derivatives clause means full text/chunk redistribution is not permitted "
            "for this work; only standard bibliographic metadata (title/authors/abstract/DOI) is used, per "
            "demo/README.md's own metadata-and-evidence-only fallback."
        ),
        "canonical_url": "https://doi.org/10.1186/s40359-026-04964-x",
        "article_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC13483554/",
        "verified_via": (
            "Crossref API license record and Semantic Scholar Graph API (openAccessPdf.license=CCBYNCND), cross-checked"
        ),
        "notice": (
            "Metadata-and-evidence-only: CC BY-NC-ND 4.0 does not permit redistributing full text/chunks; "
            "only bibliographic metadata is stored. No PDF is bundled."
        ),
        "abstract": (
            "Facial anomalies, such as scars, are often linked to an “anomalous-is-bad” stereotype, "
            "in which people with visible differences are seen as less warm or less moral. We developed the "
            "“Normalizing Anomalies with Mobile Exposure” (NAME) intervention based on the idea that "
            "repeated exposure and narratives can shift automatic evaluations of others. In a between-subjects "
            "design, one group of participants was repeatedly exposed to faces with visible anomalies paired "
            "with narratives describing morally praiseworthy actions, while a second group viewed "
            "phenotypically typical faces of people of color paired with the same type of narratives. Each "
            "group completed two daily sessions for five consecutive days via a mobile application. Across "
            "both versions of the intervention, implicit evaluations of the targeted faces became more "
            "positive over time, with the anomalous faces version showing the clearest target-specific "
            "improvement. Explicit attitudes did not change. These findings suggest that exposure-based "
            "storytelling can alter automatic evaluations of individuals with facial anomalies and may offer a "
            "promising, scalable approach to reducing stigma associated with visible differences, although "
            "further research is needed to test durability and generalizability to other groups."
        ),
        "openalex_work_id": "W7164336181",
        "openalex_cited_by_count": 0,
        "automatic_topics": [
            "Evolutionary Psychology and Human Behavior",
            "Psychology of Moral and Emotional Judgment",
            "Face Recognition and Perception",
        ],
        "bundled_material": "metadata-and-evidence-only",
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
