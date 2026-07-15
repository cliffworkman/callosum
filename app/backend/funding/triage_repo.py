"""Persistence helpers for Funding Discovery AI-fit annotations."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import Connection, delete, insert, select

from app.backend.persistence.schema import funding_llm_triage_annotations
from app.backend.persistence.sqlite_retry import retry_sqlite_locked

SECTION_KINDS = {
    "open_opportunities": "opportunity",
    "recurring_schemes": "scheme",
    "funding_prospects": "prospect",
}


def persist_llm_triage_annotations(
    conn: Connection, run_id: int, report: dict[str, Any], status: dict[str, Any]
) -> int:
    retry_sqlite_locked(
        lambda: conn.execute(
            delete(funding_llm_triage_annotations).where(funding_llm_triage_annotations.c.run_id == run_id)
        )
    )
    provider_id = str(status.get("provider_id") or "configured-llm")
    prompt_version = str(status.get("prompt_version") or "") or None
    inserted = 0
    for section, item_kind in SECTION_KINDS.items():
        for item in report.get(section) or []:
            if not isinstance(item, dict) or not isinstance(item.get("llm_evaluation"), dict):
                continue
            evaluation = item["llm_evaluation"]
            canonical_item_id = item.get("id")
            if canonical_item_id is None:
                continue
            retry_sqlite_locked(
                lambda item=item,
                evaluation=evaluation,
                item_kind=item_kind,
                canonical_item_id=canonical_item_id: conn.execute(
                    insert(funding_llm_triage_annotations).values(
                        run_id=run_id,
                        item_kind=item_kind,
                        canonical_item_id=int(canonical_item_id),
                        label=str(evaluation.get("label") or "not_assessed"),
                        show_in_triage=1 if evaluation.get("show_in_triage") else 0,
                        rationale=evaluation.get("rationale"),
                        fit_dimensions_json=_json_list(evaluation.get("fit_dimensions")),
                        concerns_json=_json_list(evaluation.get("concerns")),
                        basis=evaluation.get("basis"),
                        provider_id=provider_id,
                        prompt_version=prompt_version,
                        evidence_fingerprint=funding_llm_triage_fingerprint(item),
                        status="current",
                    )
                )
            )
            inserted += 1
    return inserted


def load_llm_triage_annotations(conn: Connection, run_id: int) -> dict[str, dict[str, Any]]:
    records = (
        conn.execute(select(funding_llm_triage_annotations).where(funding_llm_triage_annotations.c.run_id == run_id))
        .mappings()
        .all()
    )
    return {
        _key(row["item_kind"], row["canonical_item_id"]): {
            "label": row["label"],
            "show_in_triage": bool(row["show_in_triage"]),
            "rationale": row["rationale"],
            "fit_dimensions": row["fit_dimensions_json"] or [],
            "concerns": row["concerns_json"] or [],
            "basis": row["basis"],
            "provider_id": row["provider_id"],
            "prompt_version": row["prompt_version"],
            "status": row["status"],
            "evidence_fingerprint": row["evidence_fingerprint"],
        }
        for row in records
    }


def attach_llm_triage_annotations(report: dict[str, Any], annotations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for section, item_kind in SECTION_KINDS.items():
        for item in report.get(section) or []:
            if isinstance(item, dict) and item.get("id") is not None:
                evaluation = llm_triage_annotation_for_item(annotations, item_kind, item)
                if evaluation:
                    item["llm_evaluation"] = evaluation
    return report


def llm_triage_annotation_for_item(
    annotations: dict[str, dict[str, Any]], item_kind: str, item: dict[str, Any]
) -> dict[str, Any] | None:
    if item.get("id") is None:
        return None
    annotation = annotations.get(_key(item_kind, item["id"]))
    if not annotation:
        return None
    evaluation = dict(annotation)
    stored = evaluation.pop("evidence_fingerprint", None)
    current = funding_llm_triage_fingerprint(item)
    if stored and current != stored:
        evaluation["status"] = "stale"
        evaluation["stale_reason"] = "AI-fit label is based on earlier run evidence."
    return evaluation


def _key(item_kind: str, canonical_item_id: Any) -> str:
    return f"{item_kind}:{int(canonical_item_id)}"


def _json_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def funding_llm_triage_fingerprint(item: dict[str, Any]) -> str:
    evidence = {
        "id": item.get("id"),
        "status": item.get("status"),
        "deadlines": item.get("deadlines"),
        "signals": item.get("signals"),
        "organization_name": item.get("organization_name"),
        "scheme_name": item.get("scheme_name"),
        "source_url": item.get("source_url"),
    }
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode("utf-8")).hexdigest()
