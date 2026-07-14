"""Optional LLM triage for Funding Discovery results.

The deterministic Funding Discovery pool remains the source of truth. This module asks the configured model to
annotate already-surfaced items for apparent fit against the user's bounded research context; it never creates,
deletes, or verifies opportunities.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.backend.llm.providers import complete

TRIAGE_PROMPT_VERSION = "funding-triage-v1"
MAX_CONTEXT_CHARS = 6000
MAX_TRIAGE_ITEMS = 80
TRIAGE_KEEP_LABELS = {"closer_apparent_fit", "possible_fit"}
TRIAGE_LABELS = TRIAGE_KEEP_LABELS | {"uncertain", "lower_apparent_fit"}


class CompletionFn(Protocol):
    def __call__(self, config: Any, prompt: str) -> Any: ...


@dataclass(frozen=True)
class FundingLlmTriageEvaluator:
    config: Any
    complete_fn: CompletionFn = complete

    def evaluate(self, *, report: dict[str, Any], research_context: str) -> dict[str, Any]:
        items = _triage_items(report)
        if not items:
            return _status("not_searched", "No funding items were available for LLM triage.")
        evaluated = items[:MAX_TRIAGE_ITEMS]
        result = self.complete_fn(self.config, _prompt(research_context, report.get("profile") or {}, evaluated))
        parsed = _parse_response(getattr(result, "text", "") or "")
        annotations = _annotations(parsed, {item["item_key"] for item in evaluated})
        _attach_annotations(report, annotations)
        warning = None
        if len(items) > len(evaluated):
            warning = f"Only the first {len(evaluated)} surfaced item(s) were sent for LLM triage."
        return _status("success", warning, evaluated_count=len(evaluated), annotated_count=len(annotations))


def _triage_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for kind, section in (
        ("opportunity", "open_opportunities"),
        ("scheme", "recurring_schemes"),
        ("prospect", "funding_prospects"),
    ):
        for item in report.get(section) or []:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            if item_id is None:
                continue
            items.append(
                {
                    "item_key": f"{kind}:{item_id}",
                    "item_kind": kind,
                    "title": item.get("title") or item.get("scheme_name") or item.get("organization_name"),
                    "organization_name": item.get("organization_name"),
                    "scheme_name": item.get("scheme_name"),
                    "status": item.get("status") or _status_label(kind),
                    "summary": item.get("summary"),
                    "signals": _signal_summaries(item.get("signals") or []),
                    "eligibility": (item.get("eligibility") or {}).get("label"),
                    "application_route": _surface_summaries(report, item),
                }
            )
    return items


def _prompt(research_context: str, profile: dict[str, Any], items: list[dict[str, Any]]) -> str:
    payload = {
        "research_context": " ".join((research_context or "").split())[:MAX_CONTEXT_CHARS],
        "profile_facets": _facet_payload(profile),
        "funding_items": items,
    }
    return (
        "You are helping triage Callosum Funding Discovery results.\n"
        "Callosum already surfaced these items from deterministic/open-data signals. Your task is only to annotate "
        "apparent substantive fit for human review.\n\n"
        "Rules:\n"
        "- Do not call anything a recommendation, best match, verified, eligible, likely to fund, or open unless the "
        "item data already says it is open.\n"
        "- Do not invent opportunities, deadlines, funder priorities, eligibility, or application routes.\n"
        "- Preserve uncertainty. A low apparent fit is not evidence the funder is irrelevant.\n"
        "- Judge topical, population, method, activity, support-strategy, geography, and application-surface fit "
        "separately when possible.\n"
        "- Return JSON only.\n\n"
        "Return this schema:\n"
        '{"items":[{"item_key":"kind:id","label":"closer_apparent_fit|possible_fit|uncertain|'
        'lower_apparent_fit","show_in_triage":true|false,"rationale":"short reason",'
        '"fit_dimensions":["subject|population|method|support_strategy|activity_type|geography|application_route"],'
        '"concerns":["short uncertainty or mismatch"]}]}\n\n'
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}"
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


def _annotations(data: dict[str, Any], allowed_keys: set[str]) -> dict[str, dict[str, Any]]:
    annotations: dict[str, dict[str, Any]] = {}
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("item_key") or "")
        label = str(raw.get("label") or "uncertain")
        if key not in allowed_keys or label not in TRIAGE_LABELS:
            continue
        show = bool(raw.get("show_in_triage"))
        if label in TRIAGE_KEEP_LABELS and raw.get("show_in_triage") is not False:
            show = True
        annotations[key] = {
            "label": label,
            "show_in_triage": show,
            "rationale": str(raw.get("rationale") or "")[:800],
            "fit_dimensions": [str(x)[:80] for x in (raw.get("fit_dimensions") or [])[:8]],
            "concerns": [str(x)[:160] for x in (raw.get("concerns") or [])[:5]],
            "basis": "LLM triage over bounded research context and surfaced funding evidence.",
            "prompt_version": TRIAGE_PROMPT_VERSION,
        }
    return annotations


def _attach_annotations(report: dict[str, Any], annotations: dict[str, dict[str, Any]]) -> None:
    for kind, section in (
        ("opportunity", "open_opportunities"),
        ("scheme", "recurring_schemes"),
        ("prospect", "funding_prospects"),
    ):
        for item in report.get(section) or []:
            if isinstance(item, dict):
                item["llm_evaluation"] = annotations.get(f"{kind}:{item.get('id')}")


def _facet_payload(profile: dict[str, Any]) -> dict[str, list[str]]:
    facets = profile.get("facets") if isinstance(profile, dict) else {}
    if not isinstance(facets, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key, values in facets.items():
        if isinstance(values, list):
            out[str(key)] = [
                str(v.get("normalized_value")) for v in values if isinstance(v, dict) and v.get("normalized_value")
            ][:12]
    return out


def _signal_summaries(signals: list[Any]) -> list[str]:
    out: list[str] = []
    for signal in signals[:4]:
        if isinstance(signal, dict):
            label = str(signal.get("signal_type") or "signal").replace("_", " ")
            explanation = str(signal.get("explanation") or "").strip()
            out.append(f"{label}: {explanation}" if explanation else label)
    return out


def _surface_summaries(report: dict[str, Any], item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for surface in report.get("application_surfaces") or []:
        if not isinstance(surface, dict) or surface.get("organization_name") != item.get("organization_name"):
            continue
        if (
            item.get("scheme_name")
            and surface.get("scheme_name")
            and item.get("scheme_name") != surface.get("scheme_name")
        ):
            continue
        out.append(
            " · ".join(
                str(x) for x in (surface.get("actionability"), surface.get("access_mode"), surface.get("details")) if x
            )[:500]
        )
    return out[:3]


def _status_label(kind: str) -> str:
    return "current window not verified" if kind == "scheme" else "prospect only" if kind == "prospect" else "unknown"


def _status(status: str, warning: str | None, *, evaluated_count: int = 0, annotated_count: int = 0) -> dict[str, Any]:
    return {
        "provider_id": "configured-llm",
        "status": status,
        "evaluated_count": evaluated_count,
        "annotated_count": annotated_count,
        "warning": warning,
        "prompt_version": TRIAGE_PROMPT_VERSION,
    }
