"""ResearchFundingProfile construction.

Baseline extraction is deterministic and facet-based. It does not infer applicant-sensitive facts, and full text is
not used for provider queries by default.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import Connection, select

from app.backend.funding.domain import FundingFacet, ProvenanceRecord, ResearchFundingProfile
from app.backend.metadata.abstract_display import abstract_plain_text
from app.backend.persistence.schema import papers

FACET_KEYS = (
    "subjects",
    "conditionsOrPhenomena",
    "populations",
    "methods",
    "dataModalities",
    "interventionModalities",
    "researchStages",
    "activityTypes",
    "expectedOutputs",
    "supportStrategies",
    "disciplines",
    "geographies",
)

RULES: dict[str, dict[str, list[str]]] = {
    "methods": {
        "neuroimaging": ["fmri", "functional mri", "neuroimaging", "brain imaging"],
        "environmental dna": ["edna", "environmental dna"],
        "computational modeling": ["computational model", "machine learning", "algorithm"],
        "digitization": ["digitization", "digital archive", "imaging manuscripts"],
        "field sampling": ["field sampling", "field survey"],
    },
    "populations": {
        "adolescents": ["adolescent", "youth", "teen"],
        "military-connected people": ["veteran", "military", "service member"],
        "students": ["student", "school", "classroom"],
        "communities": ["community", "communities"],
    },
    "conditionsOrPhenomena": {
        "trauma": ["trauma", "ptsd"],
        "mood": ["mood", "depression", "affective"],
        "brain injury": ["brain injury", "tbi"],
        "freshwater systems": ["freshwater", "river", "watershed"],
        "microbial ecology": ["microbial ecology", "microbiome"],
        "cultural heritage": ["cultural heritage", "manuscript", "archive"],
    },
    "interventionModalities": {
        "creative arts intervention": ["art therapy", "creative arts", "music therapy"],
        "implementation": ["implementation", "translation into practice"],
    },
    "supportStrategies": {
        "pilot": ["pilot", "proof of concept", "seed grant"],
        "data reuse": ["secondary analysis", "data reuse", "existing dataset"],
        "equipment": ["equipment", "instrumentation"],
        "infrastructure": ["infrastructure", "repository", "database", "archive"],
        "training": ["training", "workshop", "curriculum"],
        "career development": ["career development", "early career"],
        "community partnership": ["community partnership", "community-based", "participatory"],
        "implementation": ["implementation", "scale-up"],
        "translation": ["translation", "translational"],
        "dissemination": ["dissemination", "public engagement"],
        "convening": ["convening", "symposium", "conference"],
        "network building": ["network", "consortium"],
        "field work": ["field work", "field sampling"],
        "archival work": ["archive", "archival"],
        "digitization": ["digitization", "digital preservation"],
        "methodology development": ["methodology", "method development"],
    },
    "activityTypes": {
        "research": ["study", "research", "analysis"],
        "training": ["training", "education"],
        "infrastructure": ["infrastructure", "repository"],
        "convening": ["conference", "symposium", "convening"],
    },
    "expectedOutputs": {
        "dataset": ["dataset", "data set", "database"],
        "software": ["software", "toolkit", "package"],
        "archive": ["archive", "collection"],
        "policy evidence": ["policy", "program evaluation"],
    },
    "disciplines": {
        "neuroscience": ["neuroscience", "brain", "neural"],
        "ecology": ["ecology", "environmental", "freshwater"],
        "humanities": ["humanities", "paleography", "cultural heritage"],
        "education policy": ["education policy", "school", "student"],
        "engineering": ["engineering", "computational", "robotics"],
    },
    "geographies": {
        "regional": ["regional", "local", "rural", "urban"],
        "international": ["international", "global"],
    },
}


def profile_from_paper(conn: Connection, paper_id: int) -> ResearchFundingProfile | None:
    row = (
        conn.execute(
            select(papers.c.id, papers.c.title, papers.c.abstract, papers.c.csl_json).where(papers.c.id == paper_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    csl = row["csl_json"] or {}
    keywords = csl.get("keyword") or csl.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords]
    title = str(row["title"] or "").strip()
    abstract = abstract_plain_text(row["abstract"]) or ""
    text = " ".join([title, abstract, " ".join(str(k) for k in keywords)])
    return profile_from_text(text, field="", source_kind="paper", source_id=str(paper_id), title=title)


def profile_from_text(
    text: str,
    *,
    field: str,
    source_kind: str = "manual",
    source_id: str | None = None,
    title: str | None = None,
) -> ResearchFundingProfile:
    now = datetime.now(UTC).isoformat()
    clean = " ".join((text or "").split())[:20000]
    facets = {k: [] for k in FACET_KEYS}
    source = clean + " " + (field or "")
    for key, values in RULES.items():
        for normalized, patterns in values.items():
            match = _first_match(source, patterns)
            if match:
                facets[key].append(
                    FundingFacet(
                        normalized_value=normalized,
                        source_text=match,
                        basis="deterministic_extraction",
                        confidence_basis="Matched a funding-profile phrase rule.",
                    )
                )
    for token in _subject_terms(title or clean, field):
        facets["subjects"].append(
            FundingFacet(token, token, "deterministic_extraction", "Top non-sensitive terms from title/field.")
        )
    if field.strip():
        facets["disciplines"].append(FundingFacet(field.strip().lower(), field.strip(), "user_supplied"))
    return ResearchFundingProfile(
        source_kind=source_kind,
        source_id=source_id,
        title=title,
        facets=facets,
        provenance=[
            ProvenanceRecord(
                provider_id="callosum",
                source_record_id=source_id or "manual",
                retrieved_at=now,
                source_field="title/abstract/field",
                extraction_method="deterministic_parse",
            )
        ],
    )


def facet_values(profile: ResearchFundingProfile) -> set[str]:
    return {f.normalized_value for values in profile.facets.values() for f in values}


def _first_match(text: str, patterns: list[str]) -> str | None:
    lower = text.lower()
    for p in patterns:
        if re.search(r"\b" + re.escape(p.lower()) + r"\b", lower):
            return p
    return None


def _subject_terms(text: str, field: str) -> list[str]:
    stop = {"the", "and", "for", "with", "from", "using", "study", "research", "analysis", "into", "of"}
    words = re.findall(r"[a-z][a-z\-]{3,}", (text + " " + field).lower())
    out: list[str] = []
    for word in words:
        if word not in stop and word not in out:
            out.append(word)
        if len(out) >= 8:
            break
    return out
