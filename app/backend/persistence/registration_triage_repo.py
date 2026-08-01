"""Persistence and staleness helpers for optional registration-comparison LLM triage."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from sqlalchemy import Connection, delete, insert, select

from app.backend.persistence.registration_schema import registration_comparison_triage_annotations

TRIAGE_LABELS = {"prioritize", "uncertain", "likely_noise"}
TRIAGE_FOCUS_LABELS = {"prioritize", "uncertain"}


def persist_registration_comparison_triage(
    conn: Connection,
    *,
    run_id: int,
    rows: list[Mapping[str, Any]],
    result: dict[str, Any],
) -> int:
    status = result.get("status") if isinstance(result, dict) else None
    if not isinstance(status, dict) or status.get("status") != "success":
        return 0
    allowed = {int(row["id"]): row for row in rows}
    raw_annotations = result.get("annotations") if isinstance(result.get("annotations"), dict) else {}
    conn.execute(
        delete(registration_comparison_triage_annotations).where(
            registration_comparison_triage_annotations.c.run_id == run_id
        )
    )
    inserted = 0
    for raw_row_id, annotation in raw_annotations.items():
        if not isinstance(annotation, dict):
            continue
        try:
            row_id = int(raw_row_id)
        except (TypeError, ValueError):
            continue
        label = str(annotation.get("label") or "")
        row = allowed.get(row_id)
        if row is None or label not in TRIAGE_LABELS:
            continue
        conn.execute(
            insert(registration_comparison_triage_annotations).values(
                run_id=run_id,
                row_id=row_id,
                label=label,
                show_in_triage=1 if label in TRIAGE_FOCUS_LABELS else 0,
                rationale=str(annotation.get("rationale") or "")[:800] or None,
                concerns_json=(
                    [str(value)[:180] for value in annotation["concerns"][:5]]
                    if isinstance(annotation.get("concerns"), list)
                    else []
                ),
                basis=str(annotation.get("basis") or "")[:500] or None,
                provider_id=str(status.get("provider_id") or "configured-llm")[:120],
                model_id=str(status.get("model_id") or "")[:200] or None,
                prompt_version=str(status.get("prompt_version") or "")[:120],
                evidence_fingerprint=registration_comparison_triage_fingerprint(row),
            )
        )
        inserted += 1
    return inserted


def load_registration_comparison_triage(conn: Connection, run_id: int) -> dict[int, dict[str, Any]]:
    rows = (
        conn.execute(
            select(registration_comparison_triage_annotations).where(
                registration_comparison_triage_annotations.c.run_id == run_id
            )
        )
        .mappings()
        .all()
    )
    return {
        int(row["row_id"]): {
            "label": row["label"],
            "show_in_triage": bool(row["show_in_triage"]),
            "rationale": row["rationale"],
            "concerns": list(row["concerns_json"] or []),
            "basis": row["basis"],
            "provider_id": row["provider_id"],
            "model_id": row["model_id"],
            "prompt_version": row["prompt_version"],
            "evidence_fingerprint": row["evidence_fingerprint"],
        }
        for row in rows
    }


def attach_registration_comparison_triage(
    rows: list[Mapping[str, Any]],
    annotations: dict[int, dict[str, Any]],
    *,
    comparison_stale: bool,
    current_prompt_version: str,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    if not annotations:
        return {}, {
            "status": "not_searched",
            "annotated_count": 0,
            "focused_count": 0,
            "warning": "AI triage has not been requested for this comparison.",
        }
    attached: dict[int, dict[str, Any]] = {}
    stale_reasons: set[str] = set()
    for row in rows:
        row_id = int(row["id"])
        stored = annotations.get(row_id)
        if not stored:
            continue
        item = dict(stored)
        reasons = []
        if comparison_stale:
            reasons.append("comparison-stale")
        if item.get("prompt_version") != current_prompt_version:
            reasons.append("triage-prompt-version-changed")
        if item.pop("evidence_fingerprint", None) != registration_comparison_triage_fingerprint(row):
            reasons.append("comparison-row-evidence-changed")
        item["status"] = "stale" if reasons else "current"
        item["stale_reasons"] = reasons
        attached[row_id] = item
        stale_reasons.update(reasons)
    first = next(iter(attached.values()), {})
    current = [item for item in attached.values() if item["status"] == "current"]
    status_name = "stale" if stale_reasons else "success"
    return attached, {
        "status": status_name,
        "annotated_count": len(attached),
        "focused_count": sum(bool(item.get("show_in_triage")) for item in current),
        "provider_id": first.get("provider_id"),
        "model_id": first.get("model_id"),
        "prompt_version": first.get("prompt_version"),
        "stale_reasons": sorted(stale_reasons),
        "warning": (
            "AI triage is based on an earlier comparison or prompt; re-run it before using the focused view."
            if stale_reasons
            else None
        ),
    }


def registration_comparison_triage_fingerprint(row: Mapping[str, Any]) -> str:
    evidence = {
        "id": row.get("id"),
        "field_type": row.get("field_type"),
        "comparison_status": row.get("comparison_status"),
        "timing_status": row.get("timing_status"),
        "registration_evidence_text": row.get("registration_evidence_text"),
        "publication_evidence_text": row.get("publication_evidence_text"),
        "explanation": row.get("explanation"),
        "uncertainty": row.get("uncertainty"),
        "search_scope_json": row.get("search_scope_json"),
        "registration_content_hash": row.get("registration_content_hash"),
        "publication_attachment_checksum": row.get("publication_attachment_checksum"),
    }
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode("utf-8")).hexdigest()
