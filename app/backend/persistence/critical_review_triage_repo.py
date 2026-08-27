"""Persistence and staleness helpers for optional critical-review candidate LLM triage.

Mirrors `registration_triage_repo.py` exactly, keyed by candidate_id (a candidate has no "run"
grouping concept the way a registration comparison row does).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from sqlalchemy import Connection, delete, insert, select

from app.backend.persistence.schema_critical_review import critical_review_candidate_triage

TRIAGE_LABELS = {"prioritize", "uncertain", "likely_noise"}
TRIAGE_FOCUS_LABELS = {"prioritize", "uncertain"}


def persist_candidate_triage(
    conn: Connection,
    *,
    candidates: list[Mapping[str, Any]],
    result: dict[str, Any],
) -> int:
    status = result.get("status") if isinstance(result, dict) else None
    if not isinstance(status, dict) or status.get("status") != "success":
        return 0
    allowed = {int(c["id"]): c for c in candidates}
    raw_annotations = result.get("annotations") if isinstance(result.get("annotations"), dict) else {}
    if allowed:
        conn.execute(
            delete(critical_review_candidate_triage).where(
                critical_review_candidate_triage.c.candidate_id.in_(allowed.keys())
            )
        )
    inserted = 0
    for raw_candidate_id, annotation in raw_annotations.items():
        if not isinstance(annotation, dict):
            continue
        try:
            candidate_id = int(raw_candidate_id)
        except (TypeError, ValueError):
            continue
        label = str(annotation.get("label") or "")
        candidate = allowed.get(candidate_id)
        if candidate is None or label not in TRIAGE_LABELS:
            continue
        conn.execute(
            insert(critical_review_candidate_triage).values(
                candidate_id=candidate_id,
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
                evidence_fingerprint=candidate_triage_fingerprint(candidate),
            )
        )
        inserted += 1
    return inserted


def load_candidate_triage(conn: Connection, candidate_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not candidate_ids:
        return {}
    rows = (
        conn.execute(
            select(critical_review_candidate_triage).where(
                critical_review_candidate_triage.c.candidate_id.in_(candidate_ids)
            )
        )
        .mappings()
        .all()
    )
    return {
        int(row["candidate_id"]): {
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


def attach_candidate_triage(
    candidates: list[Mapping[str, Any]],
    annotations: dict[int, dict[str, Any]],
    *,
    current_prompt_version: str,
) -> dict[int, dict[str, Any]]:
    attached: dict[int, dict[str, Any]] = {}
    for candidate in candidates:
        candidate_id = int(candidate["id"])
        stored = annotations.get(candidate_id)
        if not stored:
            continue
        item = dict(stored)
        reasons = []
        if item.get("prompt_version") != current_prompt_version:
            reasons.append("triage-prompt-version-changed")
        if item.pop("evidence_fingerprint", None) != candidate_triage_fingerprint(candidate):
            reasons.append("candidate-evidence-changed")
        item["status"] = "stale" if reasons else "current"
        item["stale_reasons"] = reasons
        attached[candidate_id] = item
    return attached


def candidate_triage_fingerprint(candidate: Mapping[str, Any]) -> str:
    evidence = {
        "id": candidate.get("id"),
        "concern": candidate.get("concern"),
        "anchor_quote": candidate.get("anchor_quote"),
        "stance": candidate.get("stance"),
        "confidence": candidate.get("confidence"),
        "page": candidate.get("page"),
    }
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode("utf-8")).hexdigest()
