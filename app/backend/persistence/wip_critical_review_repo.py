"""Persist exact-snapshot local critical-read receipts for WIP manuscripts."""

from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import Connection, insert, select

from app.backend.methods.critical_review import (
    CRITICAL_REVIEW_VERSION,
    CRITIQUE_CONTRADICTION_THRESHOLD,
    CRITIQUE_TOP_K,
    MAX_CRITIQUE_CLAIMS,
    ClaimSentence,
    ContestedSearchReport,
)
from app.backend.persistence.schema import tool_runs, wip_findings, wip_tool_runs
from app.backend.persistence.wip_checks_repo import _callosum_version, get_tool_run
from app.backend.persistence.wip_provenance_repo import PreparedSnapshot
from app.backend.persistence.wip_repo import add_activity

CRITICAL_REVIEW_COVERAGE = (
    "Up to 12 bounded sentences from the exact primary-manuscript checkpoint are embedded transiently and compared "
    "only with matching-model, article-fulltext embeddings from live Library papers. Up to five nearby passages per "
    "claim receive local NLI stance classification; only high-confidence contrast is surfaced with paired verbatim "
    "evidence. Current-hash WIP method-run receipts are summarized separately. No draft embedding is persisted, no "
    "provider is called, and no silence is a clean bill of health or correctness verdict."
)

_METHOD_TOOLS = (
    ("statcheck", "Statistical consistency"),
    ("transparency", "Transparency disclosures"),
    ("lmm", "Mixed-model reporting"),
    ("bayes", "Bayesian reporting"),
    ("meta-analysis", "Meta-analysis reporting"),
)
_OPEN_DISPOSITIONS = {"open", "acknowledged", "deferred"}


def store_critical_review_run(
    conn: Connection,
    prepared: PreparedSnapshot,
    snapshot_id: int,
    *,
    claims: list[ClaimSentence],
    search: ContestedSearchReport,
    model_provenance: dict,
) -> dict:
    method_signals = _current_method_signals(conn, prepared)
    available_methods = sum(item["status"] == "available" for item in method_signals)
    contested = [
        asdict(item)
        | {
            "claim_coordinate_precision": "region" if item.claim_page is not None else None,
            "other_coordinate_precision": "region" if item.page is not None else None,
        }
        for item in search.contested_claims
    ]
    summary = (
        f"Local critical read considered {len(claims)} bounded claim sentence"
        f"{'s' if len(claims) != 1 else ''}, surfaced {len(contested)} contrasting Library passage"
        f"{'s' if len(contested) != 1 else ''}, and found {available_methods} current method receipt"
        f"{'s' if available_methods != 1 else ''}."
    )
    result = conn.execute(
        insert(tool_runs).values(
            uid=str(uuid4()),
            tool_id="critical-read",
            tool_version=CRITICAL_REVIEW_VERSION,
            callosum_version=_callosum_version(),
            parameters_json={
                "max_claims": MAX_CRITIQUE_CLAIMS,
                "top_k_per_claim": CRITIQUE_TOP_K,
                "contradiction_threshold": CRITIQUE_CONTRADICTION_THRESHOLD,
                **model_provenance,
            },
            result_summary=summary,
            structured_result_json={
                "claims": [asdict(claim) for claim in claims],
                "method_signals": method_signals,
                "contested_claims": contested,
                "retrieval": {
                    "status": search.retrieval_status,
                    "claims_considered": search.claims_considered,
                    "eligible_chunk_embeddings": search.eligible_chunk_embeddings,
                    "retrieved_passages": search.retrieved_passages,
                    "classified_passages": search.classified_passages,
                },
            },
            coverage=CRITICAL_REVIEW_COVERAGE,
            status="complete",
        )
    )
    tool_run_id = int(result.inserted_primary_key[0])
    conn.execute(
        insert(wip_tool_runs).values(
            tool_run_id=tool_run_id,
            manuscript_id=prepared.manuscript_id,
            file_id=prepared.file_id,
            snapshot_id=snapshot_id,
            relevant_content_hash=prepared.identity.extracted_text_hash,
        )
    )
    add_activity(
        conn,
        prepared.manuscript_id,
        "tool-run-completed",
        summary,
        metadata={
            "tool_id": "critical-read",
            "tool_version": CRITICAL_REVIEW_VERSION,
            "snapshot_id": snapshot_id,
        },
        related_entity_type="tool-run",
        related_entity_id=str(tool_run_id),
    )
    return get_tool_run(conn, tool_run_id) or {}


def _current_method_signals(conn: Connection, prepared: PreparedSnapshot) -> list[dict]:
    rows = list(
        conn.execute(
            select(
                tool_runs.c.id,
                tool_runs.c.tool_id,
                tool_runs.c.tool_version,
                tool_runs.c.result_summary,
                wip_tool_runs.c.snapshot_id,
                wip_tool_runs.c.relevant_content_hash,
            )
            .join(wip_tool_runs, wip_tool_runs.c.tool_run_id == tool_runs.c.id)
            .where(
                wip_tool_runs.c.manuscript_id == prepared.manuscript_id,
                tool_runs.c.tool_id.in_([tool_id for tool_id, _ in _METHOD_TOOLS]),
            )
            .order_by(tool_runs.c.id.desc())
        ).mappings()
    )
    findings_by_run: dict[int, tuple[int, int]] = {}
    for finding in conn.execute(
        select(wip_findings.c.tool_run_id, wip_findings.c.kind, wip_findings.c.disposition).where(
            wip_findings.c.manuscript_id == prepared.manuscript_id
        )
    ).mappings():
        total, unresolved = findings_by_run.get(int(finding["tool_run_id"]), (0, 0))
        if finding["kind"] == "candidate":
            total += 1
            unresolved += int(finding["disposition"] in _OPEN_DISPOSITIONS)
        findings_by_run[int(finding["tool_run_id"])] = (total, unresolved)
    receipts: list[dict] = []
    for tool_id, label in _METHOD_TOOLS:
        tool_rows = [row for row in rows if row["tool_id"] == tool_id]
        current = next(
            (row for row in tool_rows if row["relevant_content_hash"] == prepared.identity.extracted_text_hash),
            None,
        )
        if current is None:
            receipts.append(
                {
                    "tool_id": tool_id,
                    "label": label,
                    "status": "unavailable",
                    "detail": (
                        "No run matches this exact manuscript text; an older receipt exists."
                        if tool_rows
                        else "Not run for this exact manuscript text."
                    ),
                }
            )
            continue
        candidate_count, unresolved_count = findings_by_run.get(int(current["id"]), (0, 0))
        receipts.append(
            {
                "tool_id": tool_id,
                "label": label,
                "status": "available",
                "tool_run_id": int(current["id"]),
                "tool_version": current["tool_version"],
                "snapshot_id": int(current["snapshot_id"]),
                "result_summary": current["result_summary"],
                "candidate_count": candidate_count,
                "unresolved_candidate_count": unresolved_count,
            }
        )
    return receipts
