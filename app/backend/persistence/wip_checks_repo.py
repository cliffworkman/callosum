"""Persist WIP tool runs, findings, dispositions, and derived validity."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from sqlalchemy import Connection, func, insert, select, update

from app.backend.methods.statcheck import STATCHECK_VERSION, StatcheckReport
from app.backend.persistence.schema import tool_runs, wip_findings, wip_tool_runs
from app.backend.persistence.wip_provenance_repo import PreparedSnapshot, list_snapshots
from app.backend.persistence.wip_repo import add_activity

STATCHECK_COVERAGE = (
    "Inline APA-style t, F, r, chi-square, and z results in extracted running text only. "
    "Tables, Bayesian results, confidence intervals, and unsupported reporting styles are not checked. "
    "No surfaced inconsistency never means the manuscript is clean."
)
OPEN_DISPOSITIONS = {"open", "acknowledged", "deferred"}
FINDING_DISPOSITIONS = OPEN_DISPOSITIONS | {
    "resolved",
    "dismissed",
    "false-positive",
    "superseded",
}


def store_statcheck_run(
    conn: Connection,
    prepared: PreparedSnapshot,
    snapshot_id: int,
    report: StatcheckReport,
) -> dict:
    flagged = [result for result in report.results if result.consistency != "consistent"]
    summary = (
        f"Checked {report.checked} inline NHST result{'s' if report.checked != 1 else ''}; "
        f"surfaced {len(flagged)} possible reporting inconsistenc{'ies' if len(flagged) != 1 else 'y'}."
    )
    run_result = conn.execute(
        insert(tool_runs).values(
            uid=str(uuid4()),
            tool_id="statcheck",
            tool_version=STATCHECK_VERSION,
            callosum_version=_callosum_version(),
            parameters_json={},
            result_summary=summary,
            structured_result_json={
                "checked": report.checked,
                "inconsistent": report.inconsistent,
                "decision_errors": report.decision_errors,
                "results": [asdict(result) for result in report.results],
            },
            coverage=STATCHECK_COVERAGE,
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
    for result in flagged:
        conn.execute(
            insert(wip_findings).values(
                uid=str(uuid4()),
                tool_run_id=tool_run_id,
                manuscript_id=prepared.manuscript_id,
                file_id=prepared.file_id,
                kind="candidate",
                finding_type=f"statcheck-{result.consistency}",
                severity="high" if result.consistency == "decision-error" else "warning",
                summary="Possible statistical reporting inconsistency",
                details_json={
                    "test_type": result.test_type,
                    "reported_p": result.reported_p,
                    "computed_p": result.computed_p,
                    "consistency": result.consistency,
                    "page": result.page,
                    "page_end": result.page_end,
                    "section": result.section,
                },
                quote=result.raw,
                context=result.context,
                coordinate_precision=None,
                disposition="open",
            )
        )
    add_activity(
        conn,
        prepared.manuscript_id,
        "tool-run-completed",
        summary,
        metadata={"tool_id": "statcheck", "tool_version": STATCHECK_VERSION, "snapshot_id": snapshot_id},
        related_entity_type="tool-run",
        related_entity_id=str(tool_run_id),
    )
    return get_tool_run(conn, tool_run_id) or {}


def list_tool_runs(conn: Connection, manuscript_id: int) -> list[dict]:
    rows = conn.execute(
        select(tool_runs, wip_tool_runs.c.manuscript_id, wip_tool_runs.c.file_id, wip_tool_runs.c.snapshot_id)
        .join(wip_tool_runs, wip_tool_runs.c.tool_run_id == tool_runs.c.id)
        .where(wip_tool_runs.c.manuscript_id == manuscript_id)
        .order_by(tool_runs.c.executed_at.desc(), tool_runs.c.id.desc())
    ).mappings()
    snapshot_status = {row["id"]: row["identity_status"] for row in list_snapshots(conn, manuscript_id)}
    return [_run_dict(conn, row, snapshot_status.get(row["snapshot_id"], "stale")) for row in rows]


def get_tool_run(conn: Connection, tool_run_id: int) -> dict | None:
    row = (
        conn.execute(
            select(tool_runs, wip_tool_runs.c.manuscript_id, wip_tool_runs.c.file_id, wip_tool_runs.c.snapshot_id)
            .join(wip_tool_runs, wip_tool_runs.c.tool_run_id == tool_runs.c.id)
            .where(tool_runs.c.id == tool_run_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    statuses = {item["id"]: item["identity_status"] for item in list_snapshots(conn, int(row["manuscript_id"]))}
    return _run_dict(conn, row, statuses.get(row["snapshot_id"], "stale"))


def update_finding_disposition(
    conn: Connection,
    finding_id: int,
    *,
    disposition: str,
    notes: str | None,
) -> dict | None:
    if disposition not in FINDING_DISPOSITIONS:
        raise ValueError("Invalid finding disposition")
    row = conn.execute(select(wip_findings).where(wip_findings.c.id == finding_id)).mappings().first()
    if row is None:
        return None
    conn.execute(
        update(wip_findings)
        .where(wip_findings.c.id == finding_id)
        .values(disposition=disposition, resolution_notes=notes, updated_at=func.current_timestamp())
    )
    add_activity(
        conn,
        int(row["manuscript_id"]),
        "finding-status-changed",
        f"Statcheck finding marked {disposition.replace('-', ' ')}",
        related_entity_type="finding",
        related_entity_id=str(finding_id),
    )
    updated = conn.execute(select(wip_findings).where(wip_findings.c.id == finding_id)).mappings().one()
    return _finding_dict(updated)


def _run_dict(conn: Connection, row, snapshot_status: str) -> dict:
    findings = [
        _finding_dict(item)
        for item in conn.execute(
            select(wip_findings).where(wip_findings.c.tool_run_id == row["id"]).order_by(wip_findings.c.id)
        ).mappings()
    ]
    unresolved = sum(1 for finding in findings if finding["disposition"] in OPEN_DISPOSITIONS)
    validity = "current-with-findings" if snapshot_status == "current" and unresolved else snapshot_status
    data = dict(row)
    if isinstance(data.get("executed_at"), datetime):
        data["executed_at"] = data["executed_at"].isoformat()
    data.update(validity=validity, unresolved_findings=unresolved, findings=findings)
    return data


def _finding_dict(row) -> dict:
    data = dict(row)
    for key in ("created_at", "updated_at"):
        if isinstance(data.get(key), datetime):
            data[key] = data[key].isoformat()
    return data


def _callosum_version() -> str:
    try:
        return version("callosum")
    except PackageNotFoundError:
        return "dev"
