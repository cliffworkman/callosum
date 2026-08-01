from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.backend.registration_comparison.domain import ComparisonProposal
from app.backend.registration_comparison.timing import compare_timing
from app.backend.registration_retrieval.domain import CommitmentRetrieval, PublicationEvidenceHit
from app.backend.registration_retrieval.retriever import MIN_SIMILARITY

COMPARISON_VERSION = "registration-crosswalk-v1"

_UNCERTAINTY = (
    "Inspect both sources. A surfaced difference may reflect reporting compression, amendments, underspecification, "
    "a legitimate deviation, extraction failure, or an incorrect registration match."
)
_NUMBER = re.compile(r"\b([1-9][0-9]{1,6})\b")
_VAGUE = ("to be determined", "as appropriate", "standard methods", "if necessary", "may be", "not specified")
_DEVIATION = ("deviat", "changed from", "change from", "not preregistered", "not pre-registered", "amend")
_MODEL_FAMILIES = (
    "logistic regression",
    "linear regression",
    "mixed-effects",
    "mixed effects",
    "anova",
    "ancova",
    "t-test",
    "t test",
    "cox regression",
    "structural equation",
)
_STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "was",
    "will",
    "be",
    "of",
    "to",
    "and",
    "or",
    "as",
    "our",
    "we",
    "primary",
    "secondary",
    "outcome",
    "measure",
    "participants",
    "reported",
}


def compare_registration_to_publication(
    commitments: Sequence[Mapping],
    retrievals: Sequence[CommitmentRetrieval],
    publication_chunks: Sequence[Mapping],
    *,
    attachment_checksums: Mapping[int, str | None],
    registration_version_id: int,
    registration_content_hash: str,
    registration_attachment_id: int | None = None,
) -> list[ComparisonProposal]:
    if not commitments:
        return [
            _empty_extraction_proposal(
                registration_version_id,
                registration_content_hash,
                registration_attachment_id,
            )
        ]
    retrieval_by_commitment = {item.commitment_id: item for item in retrievals}
    proposals = []
    for commitment in commitments:
        retrieval = retrieval_by_commitment[int(commitment["id"])]
        proposals.append(
            _compare_commitment(
                commitment,
                retrieval,
                publication_chunks,
                attachment_checksums=attachment_checksums,
            )
        )
    proposals.extend(
        _reported_items_without_registration(
            commitments,
            publication_chunks,
            attachment_checksums=attachment_checksums,
            registration_version_id=registration_version_id,
            registration_content_hash=registration_content_hash,
        )
    )
    return proposals


def _empty_extraction_proposal(
    registration_version_id: int,
    registration_content_hash: str,
    registration_attachment_id: int | None,
) -> ComparisonProposal:
    return ComparisonProposal(
        commitment_id=None,
        field_type="registration-document",
        registration_value=None,
        registration_evidence_text=None,
        registration_source_locator={
            "attachment_id": registration_attachment_id,
            "registration_version_id": registration_version_id,
            "registration_content_hash": registration_content_hash,
        },
        publication_value=None,
        publication_evidence_text=None,
        publication_source_locator=None,
        comparison_status="extraction-uncertain",
        timing_status=None,
        explanation=(
            "No canonical commitments were extracted from this registration version, so Callosum did not classify "
            "publication alignment. Inspect the stored registration and extraction basis."
        ),
        uncertainty=(
            "An empty extraction is not evidence that the registration contained no commitments. It may reflect "
            "underspecification, an unsupported form, or extraction failure."
        ),
        search_scope={
            "registration_extraction": "no-canonical-commitments",
            "publication_search_performed": False,
            "non_detection_note": "No comparison search was run; this is not a positive certificate.",
            "publication_sources": [],
        },
        publication_attachment_id=None,
        publication_attachment_checksum=None,
    )


def _compare_commitment(
    commitment: Mapping,
    retrieval: CommitmentRetrieval,
    publication_chunks: Sequence[Mapping],
    *,
    attachment_checksums: Mapping[int, str | None],
) -> ComparisonProposal:
    registration_text = str(commitment["evidence_text"])
    registration_value = dict(commitment["structured_value_json"] or {})
    hit = _usable_hit(retrieval.hits)
    publication_text = hit.text if hit else None
    publication_value = {"text": publication_text} if publication_text else None
    status: str
    timing_status = None
    explanation: str

    if retrieval.study_mapping == "ambiguous":
        status = "ambiguous-study-mapping"
        explanation = "The registration commitment could not be bounded to one reported study; inspect the study match."
    elif commitment["extraction_confidence"] == "low":
        status = "extraction-uncertain"
        explanation = "The registration field mapping is uncertain, so Callosum did not classify document alignment."
    elif commitment["field_type"] == "registration-timing":
        searched_ids = set(retrieval.searched_chunk_ids)
        searched_chunks = [row for row in publication_chunks if int(row["id"]) in searched_ids]
        status, timing_status, explanation, hit = compare_timing(registration_value, searched_chunks)
        publication_text = hit.text if hit else None
        publication_value = {"text": publication_text} if publication_text else None
    elif hit is None:
        status = "planned-item-not-located-in-publication"
        explanation = (
            "This planned item was not located in the publication scope searched. Non-detection is not absence."
        )
    elif any(marker in publication_text.casefold() for marker in _DEVIATION):
        status = "disclosed-deviation"
        explanation = "The publication passage appears to disclose a change or deviation; inspect the stated rationale."
    elif _is_vague(registration_text):
        status = "underspecified-in-registration"
        explanation = "The registration wording does not provide enough detail for a bounded deterministic comparison."
    elif _is_vague(publication_text):
        status = "underspecified-in-publication"
        explanation = "The publication wording does not provide enough detail for a bounded deterministic comparison."
    else:
        status, explanation, normalized = _compare_values(
            str(commitment["field_type"]), registration_value, registration_text, publication_text
        )
        if normalized:
            publication_value |= normalized

    source = _publication_locator(hit) if hit else None
    attachment_id = hit.attachment_id if hit else None
    return ComparisonProposal(
        commitment_id=int(commitment["id"]),
        field_type=str(commitment["field_type"]),
        registration_value=registration_value,
        registration_evidence_text=registration_text,
        registration_source_locator=dict(commitment["source_locator_json"] or {}),
        publication_value=publication_value,
        publication_evidence_text=publication_text,
        publication_source_locator=source,
        comparison_status=status,
        timing_status=timing_status,
        explanation=explanation,
        uncertainty=_UNCERTAINTY,
        search_scope=_search_scope(retrieval, attachment_checksums),
        publication_attachment_id=attachment_id,
        publication_attachment_checksum=attachment_checksums.get(attachment_id) if attachment_id else None,
    )


def _compare_values(
    field_type: str,
    registration_value: dict[str, Any],
    registration_text: str,
    publication_text: str,
) -> tuple[str, str, dict[str, Any]]:
    if field_type == "sample-size-target":
        planned = registration_value.get("target_n") or _first_number(registration_text)
        reported = _sample_number(publication_text)
        values = {"reported_n": reported} if reported is not None else {}
        if planned is None or reported is None:
            return (
                "underspecified-in-publication",
                "A comparable reported sample-size number was not located in the selected passage.",
                values,
            )
        if int(planned) == int(reported):
            return "aligned", f"The planned and reported sample-size values are both {planned}.", values
        return (
            "potentially-changed",
            f"The registration gives {planned}; the selected publication passage reports {reported}. Inspect context.",
            values,
        )
    if field_type in {"primary-outcome", "secondary-outcome"}:
        overlap = _token_overlap(registration_text, publication_text)
        if overlap >= 0.5:
            return (
                "aligned",
                "The named outcome terms substantially overlap in the two passages.",
                {"term_overlap": overlap},
            )
        return (
            "potentially-changed",
            "The named outcome terms differ in the selected passages; inspect whether they denote the same construct.",
            {"term_overlap": overlap},
        )
    if field_type == "exclusion-criterion":
        registered_logic = _logical_threshold(registration_text)
        reported_logic = _logical_threshold(publication_text)
        values = {"reported_logical_threshold": reported_logic} if reported_logic else {}
        if registered_logic and reported_logic and registered_logic != reported_logic:
            return (
                "potentially-changed",
                f"The logical threshold appears different: {registered_logic} versus {reported_logic}.",
                values,
            )
    if field_type == "stopping-rule":
        registered_stop = _stopping_signature(registration_text)
        reported_stop = _stopping_signature(publication_text)
        values = {"reported_stopping_rule": reported_stop} if reported_stop else {}
        if registered_stop and reported_stop:
            if registered_stop == reported_stop:
                return "aligned", "Both passages state the same explicit stopping-rule trigger.", values
            return (
                "potentially-changed",
                "The explicit stopping-rule triggers differ between the selected passages.",
                values,
            )
    if field_type == "covariate":
        registered_covariates = _named_covariates(registration_text)
        reported_covariates = _named_covariates(publication_text)
        values = {"reported_covariates": sorted(reported_covariates)} if reported_covariates else {}
        if registered_covariates and reported_covariates:
            if registered_covariates == reported_covariates:
                return "aligned", "Both passages name the same covariate set.", values
            return (
                "potentially-changed",
                "The named covariate sets differ between the selected passages.",
                values,
            )
    if field_type == "statistical-model":
        registered_model = _model_family(registration_text)
        reported_model = _model_family(publication_text)
        values = {"reported_model_family": reported_model} if reported_model else {}
        if registered_model and reported_model:
            if registered_model == reported_model:
                return "aligned", f"Both passages name {registered_model}.", values
            return (
                "potentially-changed",
                f"The named model families differ: {registered_model} versus {reported_model}.",
                values,
            )
    if field_type == "hypothesis":
        registered_direction = _directional(registration_text)
        reported_direction = _directional(publication_text)
        if registered_direction and not reported_direction:
            return (
                "potentially-changed",
                "The registration appears directional while the selected report passage does not state that direction.",
                {"reported_directional": False},
            )
    overlap = _token_overlap(registration_text, publication_text)
    if overlap >= 0.72:
        return "aligned", "The specific terms substantially overlap in the two passages.", {"term_overlap": overlap}
    return (
        "not-comparable",
        "The selected passages require human semantic interpretation; no deterministic difference was assigned.",
        {"term_overlap": overlap},
    )


def _reported_items_without_registration(
    commitments: Sequence[Mapping],
    chunks: Sequence[Mapping],
    *,
    attachment_checksums: Mapping[int, str | None],
    registration_version_id: int,
    registration_content_hash: str,
) -> list[ComparisonProposal]:
    planned_types = {str(row["field_type"]) for row in commitments}
    patterns = {
        "primary-outcome": re.compile(r"\bprimary\s+(?:outcome|endpoint|dependent variable)\b", re.I),
        "secondary-outcome": re.compile(r"\bsecondary\s+(?:outcome|endpoint|dependent variable)\b", re.I),
        "covariate": re.compile(r"\b(?:covariate|adjusted?\s+for|controlling\s+for)\b", re.I),
    }
    result = []
    for field_type, pattern in patterns.items():
        if field_type in planned_types:
            continue
        chunk = next((row for row in chunks if pattern.search(str(row.get("text") or ""))), None)
        if chunk is None:
            continue
        attachment_id = int(chunk["attachment_id"])
        text = str(chunk["text"])
        result.append(
            ComparisonProposal(
                commitment_id=None,
                field_type=field_type,
                registration_value=None,
                registration_evidence_text=None,
                registration_source_locator={
                    "registration_version_id": registration_version_id,
                    "registration_content_hash": registration_content_hash,
                    "searched_canonical_field": field_type,
                },
                publication_value={"text": text},
                publication_evidence_text=text,
                publication_source_locator=_chunk_locator(chunk),
                comparison_status="reported-item-not-located-in-registration",
                timing_status=None,
                explanation=(
                    f"The publication explicitly labels a {field_type.replace('-', ' ')}, but no extracted "
                    "registration commitment of that field was located. Extraction non-detection is not absence."
                ),
                uncertainty=_UNCERTAINTY,
                search_scope={
                    "registration_fields_searched": sorted(planned_types),
                    "publication_scope": "article" if chunk.get("document_role") != "supplement" else "supplement",
                },
                publication_attachment_id=attachment_id,
                publication_attachment_checksum=attachment_checksums.get(attachment_id),
            )
        )
    return result


def _usable_hit(hits: Sequence[PublicationEvidenceHit]) -> PublicationEvidenceHit | None:
    return hits[0] if hits and hits[0].similarity >= MIN_SIMILARITY else None


def _publication_locator(hit: PublicationEvidenceHit) -> dict[str, Any]:
    return {
        "attachment_id": hit.attachment_id,
        "chunk_id": hit.chunk_id,
        "page_start": hit.page_start,
        "page_end": hit.page_end,
        "bbox": hit.bbox,
        "section": hit.section,
        "section_family": hit.section_family,
        "search_phase": hit.search_phase,
    }


def _chunk_locator(chunk: Mapping) -> dict[str, Any]:
    return {
        "attachment_id": int(chunk["attachment_id"]),
        "chunk_id": int(chunk["id"]),
        "page_start": int(chunk["page_start"]),
        "page_end": int(chunk["page_end"]),
        "bbox": chunk.get("bbox_json"),
        "section": chunk.get("section"),
    }


def _search_scope(retrieval: CommitmentRetrieval, attachment_checksums: Mapping[int, str | None]) -> dict[str, Any]:
    return {
        "expected_section_families": list(retrieval.expected_section_families),
        "sections_searched": list(retrieval.sections_searched),
        "whole_article_expanded": retrieval.whole_article_expanded,
        "supplements_searched": retrieval.supplements_searched,
        "searched_chunk_ids": list(retrieval.searched_chunk_ids),
        "publication_sources": [
            {"attachment_id": attachment_id, "checksum": attachment_checksums.get(attachment_id)}
            for attachment_id in retrieval.searched_attachment_ids
        ],
        "study_mapping": retrieval.study_mapping,
        "study_labels_found": list(retrieval.study_labels_found),
        "non_detection_note": "Not located is not proof of non-reporting.",
    }


def _is_vague(text: str) -> bool:
    lowered = text.casefold().strip()
    return len(lowered.split()) < 4 or any(value in lowered for value in _VAGUE)


def _first_number(text: str) -> int | None:
    match = _NUMBER.search(text.replace(",", ""))
    return int(match.group(1)) if match else None


def _sample_number(text: str) -> int | None:
    patterns = (
        r"\b(?:final\s+)?sample\s+(?:size\s+)?(?:of\s+)?(?:was\s+)?([1-9][0-9]{1,6})\b",
        r"\b(?:n\s*[=:]\s*)([1-9][0-9]{1,6})\b",
        r"\brecruited\s+(?:a\s+final\s+sample\s+of\s+)?([1-9][0-9]{1,6})\b",
    )
    normalized = text.replace(",", "")
    for pattern in patterns:
        match = re.search(pattern, normalized, re.I)
        if match:
            return int(match.group(1))
    return None


def _logical_threshold(text: str) -> str | None:
    lowered = text.casefold()
    if "either" in lowered:
        return "either"
    if "both" in lowered:
        return "both"
    if "any" in lowered:
        return "any"
    if "all" in lowered:
        return "all"
    return None


def _stopping_signature(text: str) -> dict[str, Any] | None:
    lowered = text.casefold()
    number = _sample_number(text) or _first_number(text)
    if number is not None and any(term in lowered for term in ("stop", "until", "target", "collect", "recruit")):
        return {"kind": "sample-target", "value": number}
    if any(term in lowered for term in ("end of the semester", "end of semester", "funding expires")):
        return {"kind": "calendar-or-resource-trigger"}
    if "precision" in lowered:
        return {"kind": "precision-trigger"}
    return None


def _named_covariates(text: str) -> set[str]:
    lowered = " ".join(text.casefold().split())
    candidates: list[str] = []
    patterns = (
        r"\b([a-z][a-z0-9_-]{1,30})\s+(?:will\s+be\s+|was\s+|were\s+)?included\s+as\s+(?:a\s+)?covariate\b",
        r"\binclude\s+([a-z][a-z0-9 ,/-]{1,80}?)\s+as\s+covariates?\b",
        r"\b(?:adjusted?|controlling)\s+for\s+([a-z][a-z0-9 ,/-]{1,80})",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        candidates.extend(re.split(r"\s*(?:,|/|\band\b)\s*", match.group(1)))
    noise = {"included", "include", "used", "use", "the", "a", "an"}
    return {
        value.strip(" .")
        for value in candidates
        if value.strip(" .") and value.strip(" .") not in noise and len(value.strip(" .").split()) <= 5
    }


def _model_family(text: str) -> str | None:
    lowered = text.casefold()
    return next((family for family in _MODEL_FAMILIES if family in lowered), None)


def _directional(text: str) -> bool:
    lowered = text.casefold()
    return any(word in lowered for word in ("higher", "lower", "greater", "less", "increase", "decrease", "more"))


def _token_overlap(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(left_tokens | right_tokens), 6)


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.casefold()) if len(token) > 2 and token not in _STOPWORDS}
