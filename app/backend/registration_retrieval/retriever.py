from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

from app.backend.embeddings.models import EmbeddingModel
from app.backend.registration_retrieval.domain import CommitmentRetrieval, PublicationEvidenceHit

RETRIEVAL_VERSION = "registration-publication-retrieval-v1"
MIN_SIMILARITY = 0.28

_DEFAULT_SECTIONS = ("methods", "results")
_COMPATIBLE_SECTIONS: dict[str, tuple[str, ...]] = {
    "study-identity": ("introduction", "methods", "results"),
    "registration-timing": ("methods", "participants", "procedure"),
    "research-question": ("introduction", "methods", "results"),
    "hypothesis": ("introduction", "methods", "results"),
    "confirmatory-exploratory-designation": ("introduction", "methods", "analysis", "results", "discussion"),
    "design": ("methods", "participants", "procedure"),
    "condition": ("methods", "participants", "procedure", "results"),
    "manipulation": ("methods", "procedure", "results"),
    "primary-outcome": ("methods", "measures", "outcomes", "results"),
    "secondary-outcome": ("methods", "measures", "outcomes", "results"),
    "sample-size-target": ("methods", "participants", "procedure", "power-analysis"),
    "power-analysis": ("methods", "participants", "power-analysis", "analysis"),
    "stopping-rule": ("methods", "participants", "procedure"),
    "inclusion-criterion": ("methods", "participants", "procedure", "results"),
    "exclusion-criterion": ("methods", "participants", "data-preparation", "results"),
    "randomization": ("methods", "procedure"),
    "blinding": ("methods", "procedure"),
    "data-transformation": ("methods", "data-preparation", "analysis", "results"),
    "statistical-model": ("methods", "analysis", "results"),
    "covariate": ("methods", "analysis", "results"),
    "interaction": ("methods", "analysis", "results"),
    "multiple-comparison-procedure": ("methods", "analysis", "results"),
    "missing-data-procedure": ("methods", "data-preparation", "analysis", "results"),
    "robustness-sensitivity-analysis": ("analysis", "results", "supplement", "discussion"),
    "planned-subgroup-analysis": ("analysis", "results", "supplement"),
    "deviation-amendment-statement": ("methods", "analysis", "results", "discussion", "supplement"),
}

_SECTION_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("participants", ("participant", "sample", "subjects", "recruitment")),
    ("power-analysis", ("power analysis", "sample size calculation")),
    ("data-preparation", ("data preparation", "data cleaning", "preprocessing", "exclusion")),
    ("analysis", ("statistical analysis", "analysis plan", "analyses", "analysis")),
    ("measures", ("measure", "instrument")),
    ("outcomes", ("outcome", "endpoint")),
    ("procedure", ("procedure", "protocol")),
    ("introduction", ("introduction", "background", "theory")),
    ("methods", ("materials and methods", "methodology", "methods", "method")),
    ("results", ("results", "findings")),
    ("discussion", ("discussion", "conclusion", "limitations")),
    ("supplement", ("supplement", "supporting information", "appendix")),
)
_STUDY_LABEL_RE = re.compile(
    r"\b(?:study|experiment)\s+[A-Za-z0-9]+\b|\b(?:trial phase|cohort)\s+[A-Za-z0-9-]+\b", re.I
)
_SUPPLEMENT_RELEVANT_FIELDS = {
    "primary-outcome",
    "secondary-outcome",
    "exclusion-criterion",
    "data-transformation",
    "statistical-model",
    "covariate",
    "interaction",
    "multiple-comparison-procedure",
    "missing-data-procedure",
    "robustness-sensitivity-analysis",
    "planned-subgroup-analysis",
    "deviation-amendment-statement",
}


def retrieve_publication_evidence(
    commitments: Sequence[Mapping],
    article_chunks: Sequence[Mapping],
    supplement_chunks: Sequence[Mapping],
    *,
    model: EmbeddingModel,
    include_supplements: bool = False,
    expand_beyond_expected: bool = True,
    top_k: int = 3,
) -> list[CommitmentRetrieval]:
    article = [dict(row) for row in article_chunks]
    supplements = [dict(row) for row in supplement_chunks]
    study_labels = _study_labels(article)
    result = []
    for commitment in commitments:
        expected = _COMPATIBLE_SECTIONS.get(str(commitment["field_type"]), _DEFAULT_SECTIONS)
        study_mapping, scoped_article = _study_scope(article, commitment.get("study_label"), study_labels)
        bounded = [row for row in scoped_article if _section_family(row) in expected]
        searched_rows = list(bounded)
        sections_searched = {_section_family(row) for row in bounded}
        query = _query(commitment)
        hits = _rank(
            query,
            bounded,
            model=model,
            top_k=top_k,
            role="article-fulltext",
            phase="expected-sections",
            context_rows=article,
        )
        expanded = False
        if expand_beyond_expected and not _has_usable_hit(hits):
            expanded = True
            searched_rows = list(scoped_article)
            sections_searched.update(_section_family(row) for row in scoped_article)
            hits = _rank(
                query,
                scoped_article,
                model=model,
                top_k=top_k,
                role="article-fulltext",
                phase="whole-article",
                context_rows=article,
            )
        supplement_hits: list[PublicationEvidenceHit] = []
        search_supplements = include_supplements and str(commitment["field_type"]) in _SUPPLEMENT_RELEVANT_FIELDS
        if search_supplements:
            scoped_supplements = _scope_supplements(supplements, commitment.get("study_label"))
            searched_rows.extend(scoped_supplements)
            sections_searched.update(_section_family(row, supplement=True) for row in scoped_supplements)
            supplement_hits = _rank(
                query,
                scoped_supplements,
                model=model,
                top_k=top_k,
                role="supplement",
                phase="supplement",
                supplement=True,
                context_rows=supplements,
            )
        combined = sorted((*hits, *supplement_hits), key=lambda hit: (-hit.similarity, hit.chunk_id))[:top_k]
        result.append(
            CommitmentRetrieval(
                commitment_id=int(commitment["id"]),
                field_type=str(commitment["field_type"]),
                expected_section_families=tuple(expected),
                sections_searched=tuple(sorted(sections_searched)),
                whole_article_expanded=expanded,
                supplements_searched=search_supplements,
                searched_chunk_ids=tuple(dict.fromkeys(int(row["id"]) for row in searched_rows)),
                searched_attachment_ids=tuple(dict.fromkeys(int(row["attachment_id"]) for row in searched_rows)),
                study_mapping=study_mapping,
                study_labels_found=tuple(study_labels),
                hits=tuple(combined),
            )
        )
    return result


def _rank(
    query: str,
    rows: Sequence[dict],
    *,
    model: EmbeddingModel,
    top_k: int,
    role: str,
    phase: str,
    supplement: bool = False,
    context_rows: Sequence[dict] | None = None,
) -> list[PublicationEvidenceHit]:
    if not rows:
        return []
    vectors = model.encode_texts([query, *(str(row.get("text") or "") for row in rows)])
    query_vector = vectors[0]
    scored = sorted(
        ((_cosine(query_vector, vector), row) for row, vector in zip(rows, vectors[1:], strict=True)),
        key=lambda item: (-item[0], int(item[1]["id"])),
    )
    return [
        PublicationEvidenceHit(
            chunk_id=int(row["id"]),
            attachment_id=int(row["attachment_id"]),
            document_role=role,  # type: ignore[arg-type]
            text=str(row.get("text") or ""),
            context_text=_nearby_context(row, context_rows or rows),
            section=row.get("section"),
            section_family=_section_family(row, supplement=supplement),
            page_start=int(row["page_start"]),
            page_end=int(row["page_end"]),
            bbox=row.get("bbox_json"),
            similarity=round(score, 6),
            search_phase=phase,  # type: ignore[arg-type]
        )
        for score, row in scored[:top_k]
    ]


def _study_scope(chunks: list[dict], requested: str | None, labels: tuple[str, ...]) -> tuple[str, list[dict]]:
    if requested:
        wanted = _normalize_study_label(requested)
        matching = [row for row in chunks if wanted in _chunk_study_labels(row)]
        if matching:
            return "matched", matching
        return "ambiguous", chunks
    if len(labels) > 1:
        return "ambiguous", chunks
    return "unscoped", chunks


def _scope_supplements(chunks: list[dict], requested: str | None) -> list[dict]:
    if not requested:
        return chunks
    wanted = _normalize_study_label(requested)
    matching = [row for row in chunks if wanted in _chunk_study_labels(row)]
    return matching if matching else chunks


def _nearby_context(row: Mapping, rows: Sequence[Mapping]) -> str:
    index = next(index for index, candidate in enumerate(rows) if candidate["id"] == row["id"])
    context = []
    for neighbor_index in range(max(0, index - 1), min(len(rows), index + 2)):
        neighbor = rows[neighbor_index]
        if neighbor["attachment_id"] == row["attachment_id"]:
            context.append(str(neighbor.get("text") or ""))
    return "\n\n".join(context)


def _section_family(row: Mapping, *, supplement: bool = False) -> str:
    if supplement:
        return "supplement"
    section = str(row.get("section") or "").casefold().replace("_", " ")
    lead = str(row.get("text") or "").splitlines()[0].casefold()[:100]
    for family, aliases in _SECTION_ALIASES:
        if any(alias == section.strip() for alias in aliases):
            return family
    for family, aliases in _SECTION_ALIASES:
        if any(alias in lead for alias in aliases):
            return family
    return "unknown"


def _study_labels(chunks: Sequence[Mapping]) -> tuple[str, ...]:
    labels = []
    keys = set()
    for row in chunks:
        for match in _STUDY_LABEL_RE.finditer(f"{row.get('section') or ''} {row.get('text') or ''}"):
            label = " ".join(match.group(0).split())
            key = _normalize_study_label(label)
            if key not in keys:
                labels.append(label)
                keys.add(key)
    return tuple(labels)


def _chunk_study_labels(row: Mapping) -> set[str]:
    return {
        _normalize_study_label(match.group(0))
        for match in _STUDY_LABEL_RE.finditer(f"{row.get('section') or ''} {row.get('text') or ''}")
    }


def _normalize_study_label(value: str) -> str:
    return " ".join(value.casefold().split())


def _query(commitment: Mapping) -> str:
    value = commitment.get("structured_value_json") or commitment.get("structured_value") or {}
    text = value.get("text") if isinstance(value, Mapping) else None
    return f"{str(commitment['field_type']).replace('-', ' ')}\n{text or commitment.get('evidence_text') or ''}"


def _has_usable_hit(hits: Sequence[PublicationEvidenceHit]) -> bool:
    return bool(hits and hits[0].similarity >= MIN_SIMILARITY)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator
