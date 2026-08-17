"""Persist WIP tool runs, findings, dispositions, and derived validity."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Connection, desc, func, insert, select, update

from app.backend.methods.lmm import LMM_VERSION, LmmReport
from app.backend.methods.statcheck import STATCHECK_VERSION, StatcheckReport
from app.backend.methods.transparency import TRANSPARENCY_VERSION, TransparencyReport
from app.backend.persistence.schema import tool_runs, wip_findings, wip_journal_runs, wip_tool_runs
from app.backend.persistence.wip_provenance_repo import PreparedSnapshot, list_snapshots
from app.backend.persistence.wip_repo import add_activity

STATCHECK_COVERAGE = (
    "Inline APA-style t, F, r, chi-square, and z results in extracted running text only. "
    "Tables, Bayesian results, confidence intervals, and unsupported reporting styles are not checked. "
    "No surfaced inconsistency never means the manuscript is clean."
)
TRANSPARENCY_COVERAGE = (
    "Seven rule-based text checks: data and code availability, conflict of interest, funding, protocol or trial "
    "registration, preregistration, and 'available upon request'. Checks only the extracted primary manuscript; "
    "it does not inspect journal metadata, linked repositories, or files outside that primary source. "
    "'Not detected' never means absent, and no result is a transparency score or judgment."
)
LMM_COVERAGE = (
    "A fixed text gate first checks for linear mixed-model language. When detected, seven reporting checks cover "
    "random-effects structure, df or inference method, convergence, REML or ML estimation, ICC, marginal or "
    "conditional R-squared, and missing-data sensitivity when its longitudinal-dropout precondition holds. "
    "Checks only the extracted primary manuscript; tables are not fully read. 'Not detected' is a review prompt, "
    "not proof of omission. The auditor never runs a model and produces no correctness verdict or score."
)
ANALYTIC_FLEXIBILITY_VERSION = "1"
ANALYTIC_FLEXIBILITY_COVERAGE = (
    "An egress-gated large language model proposes candidate analytic-decision points -- exclusion criteria, "
    "covariate or control choices, statistical test or model selections, outcome or measure choices, and other "
    "reported branch points -- from the methods section of the extracted primary manuscript when section "
    "scoping is available, or the whole manuscript text when it is not. Every proposed quote is anchored "
    "afterward, deterministically and locally -- never by the model. Candidates are a starting point for "
    "reviewer judgment, never a flexibility score, ranking, or verdict."
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


def store_transparency_run(
    conn: Connection,
    prepared: PreparedSnapshot,
    snapshot_id: int,
    report: TransparencyReport,
) -> dict:
    present = [check for check in report.checks if check.status == "present"]
    not_found = sum(check.status == "not-found" for check in report.checks)
    not_applicable = sum(check.status == "not-applicable" for check in report.checks)
    summary = (
        f"Detected {len(present)} reported disclosure{'s' if len(present) != 1 else ''} across "
        f"{len(report.checks)} checks; {not_found} not detected; {not_applicable} not applicable."
    )
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
            tool_id="transparency",
            tool_version=TRANSPARENCY_VERSION,
            callosum_version=_callosum_version(),
            parameters_json={},
            result_summary=summary,
            structured_result_json={
                "present": len(present),
                "not_found": not_found,
                "not_applicable": not_applicable,
                "checks": checks,
            },
            coverage=TRANSPARENCY_COVERAGE,
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
    for check in present:
        stored_check = checks_by_key[check.key]
        conn.execute(
            insert(wip_findings).values(
                uid=str(uuid4()),
                tool_run_id=tool_run_id,
                manuscript_id=prepared.manuscript_id,
                file_id=prepared.file_id,
                kind="fact",
                finding_type=f"transparency-{check.key}-detected",
                severity="info",
                summary=f"{check.label} disclosure detected",
                details_json=stored_check,
                quote=check.evidence,
                context=check.explainer,
                coordinate_precision=stored_check["coordinate_precision"],
                disposition=None,
            )
        )
    add_activity(
        conn,
        prepared.manuscript_id,
        "tool-run-completed",
        summary,
        metadata={
            "tool_id": "transparency",
            "tool_version": TRANSPARENCY_VERSION,
            "snapshot_id": snapshot_id,
        },
        related_entity_type="tool-run",
        related_entity_id=str(tool_run_id),
    )
    return get_tool_run(conn, tool_run_id) or {}


def store_lmm_run(
    conn: Connection,
    prepared: PreparedSnapshot,
    snapshot_id: int,
    report: LmmReport,
) -> dict:
    present = sum(check.status == "present" for check in report.checks)
    not_found = [check for check in report.checks if check.status == "not-found"]
    not_applicable = sum(check.status == "not-applicable" for check in report.checks)
    if report.is_lmm:
        summary = (
            f"Mixed-model language detected; {present} reported, {len(not_found)} not detected, "
            f"and {not_applicable} not applicable across {len(report.checks)} checks."
        )
    else:
        summary = "Mixed-model language was not detected in the primary manuscript; no checklist was applied."
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
            tool_id="lmm",
            tool_version=LMM_VERSION,
            callosum_version=_callosum_version(),
            parameters_json={},
            result_summary=summary,
            structured_result_json={
                "is_lmm": report.is_lmm,
                "present": present,
                "not_found": len(not_found),
                "not_applicable": not_applicable,
                "checks": checks,
            },
            coverage=LMM_COVERAGE,
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
                finding_type=f"lmm-{check.key}-not-detected",
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
        metadata={"tool_id": "lmm", "tool_version": LMM_VERSION, "snapshot_id": snapshot_id},
        related_entity_type="tool-run",
        related_entity_id=str(tool_run_id),
    )
    return get_tool_run(conn, tool_run_id) or {}


def store_analytic_flexibility_run(
    conn: Connection,
    prepared: PreparedSnapshot,
    snapshot_id: int,
    candidates: list[dict],
    *,
    methods_text_found: bool,
    scoped: bool,
) -> dict:
    if not methods_text_found:
        summary = "No manuscript text was found; nothing to surface."
        scope = "none"
    elif scoped:
        summary = (
            f"{len(candidates)} candidate decision point{'s' if len(candidates) != 1 else ''} surfaced "
            "from the methods section."
        )
        scope = "methods-section"
    else:
        summary = (
            f"{len(candidates)} candidate decision point{'s' if len(candidates) != 1 else ''} surfaced "
            "from the whole manuscript text (no per-block section scoping available for this file type)."
        )
        scope = "whole-manuscript"
    run_result = conn.execute(
        insert(tool_runs).values(
            uid=str(uuid4()),
            tool_id="analytic-flexibility",
            tool_version=ANALYTIC_FLEXIBILITY_VERSION,
            callosum_version=_callosum_version(),
            parameters_json={},
            result_summary=summary,
            structured_result_json={
                "methods_text_found": methods_text_found,
                "scoped": scoped,
                "scope": scope,
                "candidate_count": len(candidates),
            },
            coverage=ANALYTIC_FLEXIBILITY_COVERAGE,
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
    for candidate in candidates:
        conn.execute(
            insert(wip_findings).values(
                uid=str(uuid4()),
                tool_run_id=tool_run_id,
                manuscript_id=prepared.manuscript_id,
                file_id=prepared.file_id,
                kind="candidate",
                finding_type=f"analytic-flexibility-{candidate['category']}",
                severity="info",
                summary=f"Possible {candidate['category'].replace('-', ' ')} decision point",
                details_json=candidate,
                quote=candidate["quote"],
                context=None,
                # The CHECK constraint on wip_findings.coordinate_precision permits only NULL/exact/region --
                # "unanchored" (a real anchor_state this feature produces) has no matching literal here, so it
                # maps to NULL. The fuller anchor_state value still lives in details_json for inspection.
                coordinate_precision=(candidate["anchor_state"] if candidate["anchor_state"] != "unanchored" else None),
                disposition="open",
            )
        )
    add_activity(
        conn,
        prepared.manuscript_id,
        "tool-run-completed",
        summary,
        metadata={
            "tool_id": "analytic-flexibility",
            "tool_version": ANALYTIC_FLEXIBILITY_VERSION,
            "snapshot_id": snapshot_id,
        },
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
    if row["kind"] != "candidate":
        raise ValueError("Only candidate findings have a review disposition")
    conn.execute(
        update(wip_findings)
        .where(wip_findings.c.id == finding_id)
        .values(disposition=disposition, resolution_notes=notes, updated_at=func.current_timestamp())
    )
    add_activity(
        conn,
        int(row["manuscript_id"]),
        "finding-status-changed",
        f"Finding marked {disposition.replace('-', ' ')}",
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


def record_journal_run(
    conn: Connection,
    manuscript_id: int,
    *,
    topic_id: str | None,
    weighting: float,
    considered: int,
    shown: int,
) -> None:
    # inc 404: a receipt only (topic/weighting/counts) -- never the ranked profile list itself, matching
    # publishers.py's "ephemeral job result" design for the paper/abstract paths this doesn't touch.
    conn.execute(
        insert(wip_journal_runs).values(
            manuscript_id=manuscript_id,
            topic_id=topic_id,
            weighting=weighting,
            considered=considered,
            shown=shown,
        )
    )


def list_journal_runs(conn: Connection, manuscript_id: int, limit: int = 25) -> list[dict]:
    rows = conn.execute(
        select(wip_journal_runs)
        .where(wip_journal_runs.c.manuscript_id == manuscript_id)
        .order_by(desc(wip_journal_runs.c.id))
        .limit(max(1, min(int(limit), 25)))
    ).mappings()
    result = []
    for row in rows:
        data = dict(row)
        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()
        result.append(data)
    return result
