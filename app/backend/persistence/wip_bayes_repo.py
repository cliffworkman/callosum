"""Persist exact-snapshot Bayesian reporting runs for WIP manuscripts."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Connection, insert

from app.backend.methods.bayes import (
    BAYES_VERSION,
    DEFAULT_KAPPA,
    DEFAULT_R,
    LOG10_TOLERANCE,
    BayesCompleteness,
    BayesReport,
)
from app.backend.persistence.schema import tool_runs, wip_findings, wip_tool_runs
from app.backend.persistence.wip_checks_repo import _callosum_version, get_tool_run
from app.backend.persistence.wip_provenance_repo import PreparedSnapshot
from app.backend.persistence.wip_repo import add_activity

BAYES_COVERAGE = (
    "Inline t-test and Pearson-correlation Bayes factors are recomputed under fixed default-prior assumptions, and "
    "three Bayesian reporting checks cover the prior, MCMC convergence diagnostics when applicable, and prior "
    "sensitivity. BFs in tables, unsupported designs, and results without an adjacent statistic are not checked. "
    "A mismatch commonly reflects a different prior or unreadable design; 'not detected' never proves omission. "
    "Advisories require expert judgment. The auditor never fits a model or produces a correctness verdict or score."
)


def store_bayes_run(
    conn: Connection,
    prepared: PreparedSnapshot,
    snapshot_id: int,
    report: BayesReport,
    completeness: BayesCompleteness,
) -> dict:
    review_items = [item for item in completeness.items if item.status in {"not-found", "coherence-flag"}]
    prompt_count = report.not_reproduced + len(review_items) + len(completeness.advisories)
    if completeness.is_bayesian:
        summary = (
            f"Bayesian language detected; checked {report.checked} inline Bayes factor"
            f"{'s' if report.checked != 1 else ''}, found {report.not_reproduced} not reproduced under the default "
            f"prior, and surfaced {prompt_count} review prompt{'s' if prompt_count != 1 else ''}."
        )
    else:
        summary = "Bayesian analysis language was not detected in the primary manuscript; no checklist was applied."
    has_real_pages = Path(prepared.relative_path).suffix.casefold() == ".pdf"

    def located(payload: dict) -> dict:
        page = payload.get("page") if has_real_pages else None
        return payload | {
            "page": page,
            "coordinate_precision": "region" if page is not None else None,
        }

    results = [located(asdict(result)) for result in report.results]
    items = [located(asdict(item)) for item in completeness.items]
    advisories = [located(asdict(advisory)) for advisory in completeness.advisories]
    run_result = conn.execute(
        insert(tool_runs).values(
            uid=str(uuid4()),
            tool_id="bayes",
            tool_version=BAYES_VERSION,
            callosum_version=_callosum_version(),
            parameters_json={
                "jzs_prior_scale": round(DEFAULT_R, 4),
                "correlation_prior_kappa": DEFAULT_KAPPA,
                "log10_tolerance": LOG10_TOLERANCE,
            },
            result_summary=summary,
            structured_result_json={
                "checked": report.checked,
                "not_reproduced": report.not_reproduced,
                "prior_scale": round(DEFAULT_R, 4),
                "results": results,
                "completeness": {
                    "is_bayesian": completeness.is_bayesian,
                    "items": items,
                    "advisories": advisories,
                },
            },
            coverage=BAYES_COVERAGE,
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
    if completeness.is_bayesian:
        _store_bayes_findings(
            conn,
            prepared,
            tool_run_id,
            results=results,
            items=items,
            advisories=advisories,
        )
    add_activity(
        conn,
        prepared.manuscript_id,
        "tool-run-completed",
        summary,
        metadata={"tool_id": "bayes", "tool_version": BAYES_VERSION, "snapshot_id": snapshot_id},
        related_entity_type="tool-run",
        related_entity_id=str(tool_run_id),
    )
    return get_tool_run(conn, tool_run_id) or {}


def _store_bayes_findings(
    conn: Connection,
    prepared: PreparedSnapshot,
    tool_run_id: int,
    *,
    results: list[dict],
    items: list[dict],
    advisories: list[dict],
) -> None:
    for result in results:
        if result["consistency"] != "not-reproduced":
            continue
        _insert_bayes_candidate(
            conn,
            prepared,
            tool_run_id,
            finding_type="bayes-factor-not-reproduced",
            summary="Review Bayes-factor reproduction under the default prior",
            details=result
            | {
                "jzs_prior_scale": round(DEFAULT_R, 4),
                "correlation_prior_kappa": DEFAULT_KAPPA,
                "log10_tolerance": LOG10_TOLERANCE,
            },
            quote=result["raw"],
            context=(
                "This reported BF10 did not reproduce under Callosum's fixed default-prior assumptions. A different "
                "prior, test definition, or design interpretation commonly explains a mismatch; inspect the source."
            ),
        )
    for item in items:
        if item["status"] not in {"not-found", "coherence-flag"}:
            continue
        _insert_bayes_candidate(
            conn,
            prepared,
            tool_run_id,
            finding_type=f"bayes-{item['key']}-{item['status']}",
            summary=f"Review {item['label'].lower()}",
            details=item,
            quote=item["evidence"],
            context=item["note"] or "Not detected in the extracted primary manuscript; this is not proof of omission.",
        )
    for advisory in advisories:
        _insert_bayes_candidate(
            conn,
            prepared,
            tool_run_id,
            finding_type=f"bayes-advisory-{advisory['key']}",
            summary=f"Expert review: {advisory['label'].lower()}",
            details=advisory,
            quote=advisory["evidence"],
            context=f"Advisory requiring expert judgment: {advisory['note']}.",
        )


def _insert_bayes_candidate(
    conn: Connection,
    prepared: PreparedSnapshot,
    tool_run_id: int,
    *,
    finding_type: str,
    summary: str,
    details: dict,
    quote: str | None,
    context: str,
) -> None:
    conn.execute(
        insert(wip_findings).values(
            uid=str(uuid4()),
            tool_run_id=tool_run_id,
            manuscript_id=prepared.manuscript_id,
            file_id=prepared.file_id,
            kind="candidate",
            finding_type=finding_type,
            severity="info",
            summary=summary,
            details_json=details,
            quote=quote,
            context=context,
            coordinate_precision=details.get("coordinate_precision"),
            disposition="open",
        )
    )
