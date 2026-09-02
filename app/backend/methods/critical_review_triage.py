"""Optional evidence-bounded LLM triage for critical-review items (backlog: critique triage).

Mirrors `app/backend/registration_comparison/llm_triage.py`'s exact shape (bounded evaluator, closed
label taxonomy, fail-open on any unlabeled item). One evaluator serves BOTH the ephemeral Tier-1
contested claims and the persisted Tier-2 candidates -- their content shape is identical (a paper's
own claim/concern text + a contrasting/anchor passage + a stance + a confidence). This module can
only add a display annotation that helps a reader focus their inspection; it never changes a
contested claim, a candidate's status, or any evidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.backend.llm.prompt_budget import select_total_chars
from app.backend.llm.providers import complete

TRIAGE_PROMPT_VERSION = "critical-review-triage-v1"
MAX_TRIAGE_ITEMS = 50
MAX_TOTAL_INPUT_CHARS = 40000
# The managed Local AI preview's ~10,240-token input budget is a fraction of the cloud-sized cap above
# (measured worst-case real input against the cloud cap: 39,879 chars, near-certain overflow on the
# managed target's much smaller window). See app/backend/llm/prompt_budget.py.
MAX_TOTAL_INPUT_CHARS_MANAGED_LOCAL = 8000
MAX_CLAIM_CHARS = 500
MAX_EVIDENCE_CHARS = 900
TRIAGE_LABELS = {"prioritize", "uncertain", "likely_noise"}
TRIAGE_FOCUS_LABELS = {"prioritize", "uncertain"}


class CompletionFn(Protocol):
    def __call__(self, config: Any, prompt: str) -> Any: ...


@dataclass(frozen=True)
class CriticalReviewTriageEvaluator:
    config: Any
    complete_fn: CompletionFn = complete

    def evaluate(self, *, items: list[dict[str, Any]]) -> dict[str, Any]:
        total_chars = select_total_chars(
            getattr(self.config, "provider", None),
            cloud_default=MAX_TOTAL_INPUT_CHARS,
            managed_local_budget=MAX_TOTAL_INPUT_CHARS_MANAGED_LOCAL,
        )
        bounded, truncated = _bounded_items(items, total_chars=total_chars)
        if not bounded:
            return {
                "status": _status(self.config, "not_searched", "No critique items were available."),
                "annotations": {},
            }
        result = self.complete_fn(self.config, _prompt(bounded))
        parsed = _parse_response(getattr(result, "text", "") or "")
        allowed_ids = {int(item["item_id"]) for item in bounded}
        annotations = _annotations(parsed, allowed_ids)
        missing_ids = allowed_ids - annotations.keys()
        for item_id in missing_ids:
            annotations[item_id] = {
                "label": "uncertain",
                "show_in_triage": True,
                "rationale": "The model returned no valid label for this item; it remains visible for inspection.",
                "concerns": ["No valid model annotation was returned."],
                "basis": "LLM triage over one bounded critique item and its paired evidence.",
            }
        warnings = []
        if truncated:
            warnings.append(f"Only {len(bounded)} bounded item(s) were sent; unevaluated items remain visible.")
        if missing_ids:
            warnings.append(f"The model did not label {len(missing_ids)} evaluated item(s); those remain visible.")
        return {
            "status": _status(
                self.config,
                "success",
                " ".join(warnings) or None,
                evaluated_count=len(bounded),
                annotated_count=len(annotations),
                focused_count=sum(bool(a["show_in_triage"]) for a in annotations.values()),
            ),
            "annotations": annotations,
        }


def _bounded_items(
    items: list[dict[str, Any]], *, total_chars: int = MAX_TOTAL_INPUT_CHARS
) -> tuple[list[dict[str, Any]], bool]:
    bounded: list[dict[str, Any]] = []
    used = 0
    truncated = False
    for raw in items:
        if len(bounded) >= MAX_TRIAGE_ITEMS:
            truncated = True
            break
        item = {
            "item_id": int(raw["item_id"]),
            "claim": _clip(raw.get("claim"), MAX_CLAIM_CHARS),
            "evidence": _clip(raw.get("evidence"), MAX_EVIDENCE_CHARS),
            "stance": raw.get("stance"),
            "confidence": raw.get("confidence"),
        }
        size = len(json.dumps(item, ensure_ascii=False, default=str))
        if bounded and used + size > total_chars:
            truncated = True
            break
        bounded.append(item)
        used += size
    if len(bounded) < len(items):
        truncated = True
    return bounded, truncated


def _prompt(items: list[dict[str, Any]]) -> str:
    return (
        "You are triaging automatically-surfaced Callosum critical-review items for human inspection: each is "
        "either a claim contested by another passage, or an AI-suggested critique concern anchored to a verbatim "
        "quote.\n"
        "The claim/concern and its evidence are authoritative and already verified; your labels are only a "
        "reversible display aid to reduce apparent noise -- you cannot alter them.\n\n"
        "Rules:\n"
        "- Never judge the authors, decide correctness, or resolve which side of a disagreement is right.\n"
        "- Prioritize an item when the evidence plausibly names a specific, substantive distinction worth a human "
        "reading closely.\n"
        "- Use uncertain when the connection between the claim and its evidence is unclear or could go either way.\n"
        "- Use likely_noise only when the evidence looks unrelated to the claim, is boilerplate/incidental text "
        "(e.g. a citation list, a shared stock phrase, generic wording), or the contrast is not apparent from the "
        "supplied text. This is not dismissal.\n"
        "- Base every rationale only on the supplied text. Return JSON only.\n\n"
        "Return this schema:\n"
        '{"items":[{"item_id":1,"label":"prioritize|uncertain|likely_noise",'
        '"show_in_triage":true|false,"rationale":"short evidence-bound reason",'
        '"concerns":["short caveat"]}]}\n\n'
        f"Input JSON:\n{json.dumps({'critique_items': items}, ensure_ascii=False)}"
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
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        try:
            item_id = int(raw.get("item_id"))
        except (TypeError, ValueError):
            continue
        label = str(raw.get("label") or "uncertain")
        if item_id not in allowed_ids or label not in TRIAGE_LABELS:
            continue
        annotations[item_id] = {
            "label": label,
            "show_in_triage": label in TRIAGE_FOCUS_LABELS,
            "rationale": str(raw.get("rationale") or "")[:800],
            "concerns": _string_list(raw.get("concerns"), limit=5, width=180),
            "basis": "LLM triage over one bounded critique item and its paired evidence.",
        }
    return annotations


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
