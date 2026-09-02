"""Optional evidence-bounded LLM triage for registration comparison rows.

The persisted deterministic crosswalk remains the source of truth. This module can only add display annotations that
help a reader focus their inspection; it cannot change statuses, evidence, review state, or source documents.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.backend.llm.prompt_budget import select_total_chars
from app.backend.llm.providers import complete

TRIAGE_PROMPT_VERSION = "registration-comparison-triage-v1"
MAX_TRIAGE_ROWS = 50
MAX_TOTAL_INPUT_CHARS = 60000
# The managed Local AI preview's ~10,240-token input budget is a fraction of the cloud-sized cap above
# (measured worst-case real input against the cloud cap: 58,209 chars, near-certain overflow on the
# managed target's much smaller window). See app/backend/llm/prompt_budget.py.
MAX_TOTAL_INPUT_CHARS_MANAGED_LOCAL = 8000
MAX_EVIDENCE_CHARS = 900
TRIAGE_LABELS = {"prioritize", "uncertain", "likely_noise"}
TRIAGE_FOCUS_LABELS = {"prioritize", "uncertain"}


class CompletionFn(Protocol):
    def __call__(self, config: Any, prompt: str) -> Any: ...


@dataclass(frozen=True)
class RegistrationComparisonTriageEvaluator:
    config: Any
    complete_fn: CompletionFn = complete

    def evaluate(self, *, rows: list[dict[str, Any]]) -> dict[str, Any]:
        total_chars = select_total_chars(
            getattr(self.config, "provider", None),
            cloud_default=MAX_TOTAL_INPUT_CHARS,
            managed_local_budget=MAX_TOTAL_INPUT_CHARS_MANAGED_LOCAL,
        )
        items, truncated = _bounded_items(rows, total_chars=total_chars)
        if not items:
            return {
                "status": _status(self.config, "not_searched", "No comparison rows were available."),
                "annotations": {},
            }
        result = self.complete_fn(self.config, _prompt(items))
        parsed = _parse_response(getattr(result, "text", "") or "")
        allowed_ids = {int(item["row_id"]) for item in items}
        annotations = _annotations(parsed, allowed_ids)
        missing_ids = allowed_ids - annotations.keys()
        for row_id in missing_ids:
            annotations[row_id] = {
                "label": "uncertain",
                "show_in_triage": True,
                "rationale": "The model returned no valid label for this row; it remains visible for inspection.",
                "concerns": ["No valid model annotation was returned."],
                "basis": "LLM triage over one bounded comparison row and its paired evidence.",
            }
        missing = len(missing_ids)
        warnings = []
        if truncated:
            warnings.append(f"Only {len(items)} bounded row(s) were sent; unevaluated rows remain visible.")
        if missing:
            warnings.append(f"The model did not label {missing} evaluated row(s); those rows remain visible.")
        return {
            "status": _status(
                self.config,
                "success",
                " ".join(warnings) or None,
                evaluated_count=len(items),
                annotated_count=len(annotations),
                focused_count=sum(bool(item["show_in_triage"]) for item in annotations.values()),
            ),
            "annotations": annotations,
        }


def _bounded_items(
    rows: list[dict[str, Any]], *, total_chars: int = MAX_TOTAL_INPUT_CHARS
) -> tuple[list[dict[str, Any]], bool]:
    items: list[dict[str, Any]] = []
    used = 0
    truncated = False
    for row in rows:
        if len(items) >= MAX_TRIAGE_ROWS:
            truncated = True
            break
        item = {
            "row_id": int(row["id"]),
            "field_type": str(row.get("field_type") or ""),
            "comparison_status": str(row.get("comparison_status") or ""),
            "timing_status": row.get("timing_status"),
            "registration_evidence": _clip(row.get("registration_evidence_text"), MAX_EVIDENCE_CHARS),
            "publication_evidence": _clip(row.get("publication_evidence_text"), MAX_EVIDENCE_CHARS),
            "why_surfaced": _clip(row.get("explanation"), 700),
            "uncertainty": _clip(row.get("uncertainty"), 500),
            "search_scope": _scope(row.get("search_scope_json") or row.get("search_scope") or {}),
        }
        size = len(json.dumps(item, ensure_ascii=False, default=str))
        if items and used + size > total_chars:
            truncated = True
            break
        items.append(item)
        used += size
    if len(items) < len(rows):
        truncated = True
    return items, truncated


def _prompt(items: list[dict[str, Any]]) -> str:
    return (
        "You are triaging Callosum registration-versus-publication comparison rows for human inspection.\n"
        "The deterministic crosswalk and its evidence are authoritative; your labels are only a reversible display "
        "aid to reduce apparent noise.\n\n"
        "Rules:\n"
        "- Never decide compliance, integrity, misconduct, author intent, or whether a paper followed a registration.\n"
        "- Never rewrite a comparison status or claim that an unlocated item is absent.\n"
        "- Prioritize a row when its paired evidence suggests a specific, potentially material distinction worth "
        "reading, including timing, primary outcomes, stopping, exclusions, or analysis choices.\n"
        "- Use uncertain when evidence is one-sided, study mapping is ambiguous, extraction is uncertain, or the "
        "distinction cannot be resolved from the supplied passages. Keep uncertain rows in the focused view.\n"
        "- Use likely_noise only when the row appears low-information or plausibly explained by wording variation, "
        "reporting compression, duplicate/redundant evidence, or a weak retrieval match. This is not dismissal.\n"
        "- Base every rationale only on the supplied row. Preserve both-document uncertainty.\n"
        "- Return JSON only.\n\n"
        "Return this schema:\n"
        '{"rows":[{"row_id":1,"label":"prioritize|uncertain|likely_noise",'
        '"show_in_triage":true|false,"rationale":"short evidence-bound reason",'
        '"concerns":["short caveat"]}]}\n\n'
        f"Input JSON:\n{json.dumps({'comparison_rows': items}, ensure_ascii=False)}"
    )


def _parse_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    if not cleaned.startswith("{"):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    return data if isinstance(data, dict) else {}


def _annotations(data: dict[str, Any], allowed_ids: set[int]) -> dict[int, dict[str, Any]]:
    annotations: dict[int, dict[str, Any]] = {}
    for raw in data.get("rows") or []:
        if not isinstance(raw, dict):
            continue
        try:
            row_id = int(raw.get("row_id"))
        except (TypeError, ValueError):
            continue
        label = str(raw.get("label") or "uncertain")
        if row_id not in allowed_ids or label not in TRIAGE_LABELS:
            continue
        annotations[row_id] = {
            "label": label,
            "show_in_triage": label in TRIAGE_FOCUS_LABELS,
            "rationale": str(raw.get("rationale") or "")[:800],
            "concerns": _string_list(raw.get("concerns"), limit=5, width=180),
            "basis": "LLM triage over one bounded comparison row and its paired evidence.",
        }
    return annotations


def _scope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    sections = value.get("sections_searched")
    if not isinstance(sections, list):
        sections = []
    return {
        "sections_searched": [str(item)[:100] for item in sections[:20]],
        "whole_article_expanded": bool(value.get("whole_article_expanded")),
        "supplements_searched": bool(value.get("supplements_searched")),
        "study_mapping": _clip(value.get("study_mapping"), 300),
    }


def _clip(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).split())[:limit]


def _string_list(value: Any, *, limit: int, width: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:width] for item in value[:limit]]


def _status(
    config: Any,
    status: str,
    warning: str | None,
    *,
    evaluated_count: int = 0,
    annotated_count: int = 0,
    focused_count: int = 0,
) -> dict[str, Any]:
    return {
        "provider_id": str(getattr(config, "provider", None) or "configured-llm"),
        "model_id": str(getattr(config, "model", None) or "configured-model"),
        "status": status,
        "evaluated_count": evaluated_count,
        "annotated_count": annotated_count,
        "focused_count": focused_count,
        "warning": warning,
        "prompt_version": TRIAGE_PROMPT_VERSION,
    }
