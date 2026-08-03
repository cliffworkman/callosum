"""Persist exact-snapshot meta-analysis reporting runs for WIP manuscripts."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy import Connection, insert

from app.backend.methods.metaanalysis import META_ANALYSIS_VERSION, MetaReport
from app.backend.persistence.schema import tool_runs, wip_findings, wip_tool_runs
from app.backend.persistence.wip_checks_repo import _callosum_version, get_tool_run
from app.backend.persistence.wip_provenance_repo import PreparedSnapshot
from app.backend.persistence.wip_repo import add_activity

META_ANALYSIS_COVERAGE = (
    "Seven text-detection checks cover the effect-size metric, pooling model, heterogeneity, publication-bias "
    "assessment, sensitivity or influence analysis, study count, and search and selection reporting. The search "
    "check is not applicable to a detected within-study mini-meta-analysis. Tables and figures are not fully read, "
    "and 'not detected' is never proof of omission. The auditor never pools, models, recomputes, scores, or judges "
    "the analysis."
)


def store_meta_analysis_run(
    conn: Connection,
    prepared: PreparedSnapshot,
    snapshot_id: int,
    report: MetaReport,
) -> dict:
    present = sum(check.status == "present" for check in report.checks)
    not_found = [check for check in report.checks if check.status == "not-found"]
    not_applicable = sum(check.status == "not-applicable" for check in report.checks)
    if report.is_meta_analysis:
        summary = (
            f"Meta-analysis language detected; {present} reported, {len(not_found)} not detected, "
            f"and {not_applicable} not applicable across {len(report.checks)} checks."
        )
    else:
        summary = "Meta-analysis language was not detected in the primary manuscript; no checklist was applied."
    has_real_pages = Path(prepared.relative_path).suffix.casefold() == ".pdf"
    checks = [
        check.to_dict()
        | {
            "page": check.page if has_real_pages else None,
            "coordinate_precision": "region" if has_real_pages and check.page is not None else None,
        }
        for check in report.checks
    ]
    run_result = conn.execute(
        insert(tool_runs).values(
            uid=str(uuid4()),
            tool_id="meta-analysis",
            tool_version=META_ANALYSIS_VERSION,
            callosum_version=_callosum_version(),
            parameters_json={},
            result_summary=summary,
            structured_result_json={
                "is_meta_analysis": report.is_meta_analysis,
                "present": present,
                "not_found": len(not_found),
                "not_applicable": not_applicable,
                "checks": checks,
            },
            coverage=META_ANALYSIS_COVERAGE,
            status="complete",
        )
    )
    tool_run_id = int(run_result.inserted_primary_key[0])
    conn.execute(
        insert(wip_tool_runs).values(
            tool_run_id=tool_run_id,
            manuscript_id=prepared.manuscript_id,
            file_id=prepared.file_id,
            snapshot_id=snapshot_id,
            relevant_content_hash=prepared.identity.extracted_text_hash,
        )
    )
    checks_by_key = {check["key"]: check for check in checks}
    for check in not_found:
        stored_check = checks_by_key[check.key]
        conn.execute(
            insert(wip_findings).values(
                uid=str(uuid4()),
                tool_run_id=tool_run_id,
                manuscript_id=prepared.manuscript_id,
                file_id=prepared.file_id,
                kind="candidate",
                finding_type=f"meta-analysis-{check.key}-not-detected",
                severity="info",
                summary=f"Review {check.label.lower()} reporting",
                details_json=stored_check,
                quote=None,
                context=check.note or check.explainer,
                coordinate_precision=None,
                disposition="open",
            )
        )
    add_activity(
        conn,
        prepared.manuscript_id,
        "tool-run-completed",
        summary,
        metadata={
            "tool_id": "meta-analysis",
            "tool_version": META_ANALYSIS_VERSION,
            "snapshot_id": snapshot_id,
        },
        related_entity_type="tool-run",
        related_entity_id=str(tool_run_id),
    )
    return get_tool_run(conn, tool_run_id) or {}
