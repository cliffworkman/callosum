from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.backend.registration_commitments.domain import CommitmentCandidate

EXTRACTION_VERSION = "registration-commitments-v1"

_AS_PREDICTED_FIELDS = {
    "aspredicted-1": "registration-timing",
    "aspredicted-2": "hypothesis",
    "aspredicted-3": "primary-outcome",
    "aspredicted-4": "condition",
    "aspredicted-5": "statistical-model",
    "aspredicted-6": "exclusion-criterion",
    "aspredicted-7": "sample-size-target",
}

# Specific phrases precede broader ones. A match is a proposed canonical placement, never a consistency judgment.
_FIELD_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deviation-amendment-statement", ("amend", "deviation", "change to the registration", "revision")),
    ("confirmatory-exploratory-designation", ("confirmatory", "exploratory", "primary analysis designation")),
    ("multiple-comparison-procedure", ("multiple comparison", "multiple testing", "bonferroni", "false discovery")),
    ("missing-data-procedure", ("missing data", "missingness", "imputation", "complete case")),
    ("robustness-sensitivity-analysis", ("robustness", "sensitivity analysis", "robust check")),
    ("planned-subgroup-analysis", ("subgroup", "moderator analysis", "stratified analysis")),
    ("sample-size-target", ("sample size", "number of participants", "number of observations", "recruit")),
    ("power-analysis", ("power analysis", "statistical power", "effect size used for power")),
    ("stopping-rule", ("stopping rule", "stop collecting", "data collection stop", "termination rule")),
    ("inclusion-criterion", ("inclusion criter", "eligible", "eligibility", "include participants")),
    ("exclusion-criterion", ("exclusion criter", "exclude", "outlier", "attention check")),
    ("primary-outcome", ("primary outcome", "primary dependent", "main outcome", "dependent variable")),
    ("secondary-outcome", ("secondary outcome", "secondary dependent")),
    ("research-question", ("research question", "main question", "question being asked")),
    ("hypothesis", ("hypoth", "prediction")),
    ("randomization", ("randomi", "random assign", "allocation sequence")),
    ("blinding", ("blind", "masking")),
    ("data-transformation", ("transform", "standardiz", "normalize", "log-trans")),
    ("statistical-model", ("statistical model", "analysis plan", "regression", "anova", "t-test", "model")),
    ("covariate", ("covariate", "control variable", "adjust for")),
    ("interaction", ("interaction", "moderation")),
    ("manipulation", ("manipulation", "intervention")),
    ("condition", ("condition", "experimental group", "control group", "treatment arm")),
    ("design", ("study design", "experimental design", "trial design", "within-subject", "between-subject")),
    ("study-identity", ("study name", "study identity", "experiment name", "trial name")),
)

_STUDY_LABEL = re.compile(r"\b(?:study|experiment)\s+[A-Za-z0-9]+\b|\b(?:trial phase|cohort)\s+[A-Za-z0-9-]+\b", re.I)
_TARGET_N = re.compile(
    r"\b(?:n\s*[=:]?\s*|recruit(?:ing)?\s+|sample(?:\s+size)?\s+(?:of\s+)?)([1-9][0-9]{1,6})\b", re.I
)


def extract_commitments(version: Mapping[str, Any], chunks: Sequence[Mapping[str, Any]]) -> list[CommitmentCandidate]:
    structured = dict(version.get("structured_json") or {})
    questions = structured.get("questions") or []
    attachment_id = version.get("attachment_id")
    base_locator = {
        "attachment_id": attachment_id,
        "registration_version_id": version["id"],
        "registration_content_hash": version["content_hash"],
    }
    result: list[CommitmentCandidate] = []
    if structured.get("title"):
        result.append(
            _candidate(
                "study-identity",
                str(structured["title"]),
                "registration-metadata:title",
                "Registration metadata",
                base_locator | {"metadata_field": "title"},
                "structured-registry-metadata",
                "high",
                chunks,
            )
        )
    if structured.get("registered_at"):
        timing = str(structured["registered_at"])
        existing_data = _existing_data_timing(questions)
        updated_at = _latest_response_update(structured.get("response_history") or [])
        timing_value = {
            "registered_at": timing,
            "registration_status": structured.get("registration_status"),
        }
        timing_evidence = timing
        timing_locator = base_locator | {"metadata_field": "registered_at"}
        if updated_at:
            timing_value["updated_at"] = updated_at
        if existing_data:
            timing_value |= {
                "existing_data_collected": existing_data["collected"],
                "existing_data_statement": existing_data["answer"],
            }
            timing_evidence += f"\nExisting-data response: {existing_data['answer']}"
            timing_locator["existing_data_response_key"] = existing_data["response_key"]
        result.append(
            CommitmentCandidate(
                field_type="registration-timing",
                study_label=None,
                structured_value=timing_value,
                evidence_text=timing_evidence,
                source_section="Registration metadata",
                source_key="registration-metadata:registered-at",
                page=None,
                chunk_id=None,
                source_locator=timing_locator,
                extraction_method="structured-registry-metadata",
                extraction_confidence="high",
            )
        )

    if questions:
        for question in questions:
            answer = _answer_text(question.get("answer"))
            if not answer:
                continue
            response_key = str(question.get("response_key") or f"question-{len(result)}")
            if response_key == "aspredicted-1" and structured.get("registered_at"):
                continue
            mapping = _map_field(
                f"{question.get('section') or ''} {question.get('label') or ''}",
                response_key=response_key,
            )
            if mapping is None:
                continue
            field_type, confidence = mapping
            chunk = _find_chunk(chunks, answer)
            locator = base_locator | {
                "response_key": response_key,
                "question_block_id": question.get("question_block_id"),
                "question_group_id": question.get("question_group_id"),
                "answer_order": question.get("answer_order"),
            }
            if chunk is not None:
                locator |= _chunk_locator(chunk)
            result.append(
                CommitmentCandidate(
                    field_type=field_type,
                    study_label=_study_label(f"{question.get('label') or ''} {answer}"),
                    structured_value=_structured_value(field_type, answer, question.get("answer")),
                    evidence_text=answer,
                    source_section=str(question.get("section") or question.get("label") or "Registration response"),
                    source_key=f"question:{response_key}",
                    page=int(chunk["page_start"]) if chunk is not None else None,
                    chunk_id=int(chunk["id"]) if chunk is not None else None,
                    source_locator=locator,
                    extraction_method=f"structured-{structured.get('provider') or version.get('provider')}",
                    extraction_confidence=confidence,
                )
            )
    else:
        result.extend(_extract_from_chunks(chunks, base_locator))

    response_meta = structured.get("response_metadata") or {}
    justification = _answer_text(response_meta.get("revision_justification"))
    updated = response_meta.get("updated_response_keys") or []
    if justification or updated:
        evidence = justification or f"Updated response keys: {', '.join(map(str, updated))}"
        result.append(
            CommitmentCandidate(
                field_type="deviation-amendment-statement",
                study_label=_study_label(evidence),
                structured_value={"text": evidence, "updated_response_keys": list(updated)},
                evidence_text=evidence,
                source_section="Registration revision metadata",
                source_key="registration-metadata:revision",
                page=None,
                chunk_id=None,
                source_locator=base_locator | {"metadata_field": "response_metadata"},
                extraction_method="structured-registry-metadata",
                extraction_confidence="high",
            )
        )
    return [candidate for index, candidate in enumerate(result) if _unique(candidate, result[:index])]


def _extract_from_chunks(
    chunks: Sequence[Mapping[str, Any]], base_locator: dict[str, Any]
) -> list[CommitmentCandidate]:
    result = []
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        paragraphs = [
            item.strip() for item in re.split(r"\n\s*\n|(?<=\.)\s+(?=[A-Z])", text) if len(item.strip()) >= 18
        ]
        for index, evidence in enumerate(paragraphs):
            mapping = _map_field(f"{chunk.get('section') or ''} {evidence}")
            if mapping is None:
                continue
            field_type, confidence = mapping
            result.append(
                CommitmentCandidate(
                    field_type=field_type,
                    study_label=_study_label(evidence),
                    structured_value=_structured_value(field_type, evidence, evidence),
                    evidence_text=evidence,
                    source_section=str(chunk.get("section") or "Registration document"),
                    source_key=f"chunk:{chunk['id']}:{index}",
                    page=int(chunk["page_start"]),
                    chunk_id=int(chunk["id"]),
                    source_locator=base_locator | _chunk_locator(chunk),
                    extraction_method="deterministic-local-text",
                    extraction_confidence="medium" if confidence == "high" else "low",
                )
            )
    return result


def _candidate(
    field_type: str,
    evidence: str,
    source_key: str,
    source_section: str,
    locator: dict[str, Any],
    method: str,
    confidence: str,
    chunks: Sequence[Mapping[str, Any]],
) -> CommitmentCandidate:
    chunk = _find_chunk(chunks, evidence)
    if chunk is not None:
        locator |= _chunk_locator(chunk)
    return CommitmentCandidate(
        field_type=field_type,
        study_label=_study_label(evidence),
        structured_value=_structured_value(field_type, evidence, evidence),
        evidence_text=evidence,
        source_section=source_section,
        source_key=source_key,
        page=int(chunk["page_start"]) if chunk is not None else None,
        chunk_id=int(chunk["id"]) if chunk is not None else None,
        source_locator=locator,
        extraction_method=method,
        extraction_confidence=confidence,
    )


def _map_field(text: str, *, response_key: str | None = None) -> tuple[str, str] | None:
    if response_key in _AS_PREDICTED_FIELDS:
        return _AS_PREDICTED_FIELDS[response_key], "high"
    normalized = text.casefold()
    for field_type, patterns in _FIELD_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            return field_type, "high"
    return None


def _structured_value(field_type: str, evidence: str, raw: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"text": evidence}
    if not isinstance(raw, str):
        result["raw"] = raw
    if field_type == "sample-size-target":
        match = _TARGET_N.search(evidence)
        if match:
            result["target_n"] = int(match.group(1))
    return result


def _answer_text(value: Any) -> str:
    if value in (None, "", []):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _find_chunk(chunks: Sequence[Mapping[str, Any]], evidence: str) -> Mapping[str, Any] | None:
    needle = " ".join(evidence.casefold().split())[:160]
    if not needle:
        return None
    for chunk in chunks:
        haystack = " ".join(str(chunk.get("text") or "").casefold().split())
        if needle in haystack or (len(needle) > 60 and needle[:60] in haystack):
            return chunk
    return None


def _chunk_locator(chunk: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": int(chunk["id"]),
        "page_start": int(chunk["page_start"]),
        "page_end": int(chunk["page_end"]),
        "bbox": chunk.get("bbox_json"),
        "char_start": chunk.get("char_start"),
        "char_end": chunk.get("char_end"),
    }


def _study_label(text: str) -> str | None:
    match = _STUDY_LABEL.search(text)
    return match.group(0) if match else None


def _unique(candidate: CommitmentCandidate, prior: Sequence[CommitmentCandidate]) -> bool:
    return not any(
        item.field_type == candidate.field_type
        and item.source_key == candidate.source_key
        and item.evidence_text == candidate.evidence_text
        for item in prior
    )


def _existing_data_timing(questions: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    question = next((item for item in questions if item.get("response_key") == "aspredicted-1"), None)
    if question is None:
        return None
    answer = _answer_text(question.get("answer"))
    lowered = answer.casefold()
    if not answer:
        collected = None
    elif re.search(r"\b(?:no|none)\b.{0,40}\bdata\b.{0,40}\bcollected\b", lowered):
        collected = False
    elif re.search(r"\b(?:yes|some|all)\b.{0,60}\bdata\b", lowered) or "data have been collected" in lowered:
        collected = True
    else:
        collected = None
    return {"response_key": "aspredicted-1", "answer": answer, "collected": collected}


def _latest_response_update(history: Sequence[Mapping[str, Any]]) -> str | None:
    values = [str(item.get("date_modified") or "") for item in history if item.get("date_modified")]
    return max(values, default=None)
