"""Generate saved Critique and Meta-Preregistration state for the public demo.

The generator reads only the dedicated three-paper database. Critique uses the already
exported method records, while Meta-Preregistration is read through Callosum's real API
models from the completed comparison against the bundled CC BY PsyArXiv manuscript.
No acquisition, comparison, AI call, or ordinary working database is used here.
"""

# ruff: noqa: E402 -- direct execution needs the repository root on sys.path before app imports.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.api import create_app
from app.backend.api.routers.critical_review import (
    CandidateListResponse,
    CriticalReadJobResponse,
    MethodSignalResponse,
    ScrutinyBackboneResponse,
)
from app.backend.api.routers.registration_acquisition import RegistrationVersionOut
from app.backend.api.routers.registration_comparisons import ComparisonRunDetail, ComparisonRunSummary
from app.backend.api.routers.registration_discovery import RegistrationLinkOut
from app.backend.demo_snapshot import DemoSnapshot
from app.backend.demo_synthesis_state import DemoRegistrationLicenseAudit, DemoSynthesisState
from tools.demo.curated_library import CORPUS

FIXTURE = PROJECT_ROOT / "tools" / "demo" / "fixtures" / "good-beautiful-registration-public.json"
PREREG_PAPER_ID = 42


def _critical_read(paper: dict[str, Any]) -> CriticalReadJobResponse:
    methods = paper["methods"]
    statcheck = methods["statcheck"]
    signals = [
        MethodSignalResponse(
            kind="statcheck",
            label="Statistical consistency (statcheck)",
            detail=(
                f"{statcheck['checked']} checked, {statcheck['inconsistent']} inconsistent, "
                f"{statcheck['decision_errors']} decision errors"
            ),
        )
    ]
    transparency = methods["transparency"]["checks"]
    present = sum(item["status"] == "present" for item in transparency)
    missing = sum(item["status"] == "not-found" for item in transparency)
    signals.append(
        MethodSignalResponse(
            kind="transparency",
            label="Transparency disclosures",
            detail=f"{present} detected, {missing} not detected across {len(transparency)} checks",
        )
    )
    for key, kind, label in (
        ("lmm", "lmm", "Mixed-model reporting"),
        ("bayes", "bayes", "Bayesian reporting"),
        ("meta_analysis", "meta-analysis", "Meta-analysis reporting"),
    ):
        result = methods[key]
        applies = result.get("is_lmm", result.get("is_bayesian", result.get("is_meta_analysis", False)))
        if not applies:
            continue
        checks = result.get("checks") or result.get("completeness", {}).get("items") or []
        surfaced = sum(item.get("status") in {"not-found", "coherence-flag"} for item in checks)
        signals.append(
            MethodSignalResponse(
                kind=kind,
                label=label,
                detail=f"{surfaced} review prompt{'s' if surfaced != 1 else ''} across {len(checks)} checks",
            )
        )
    paper_id = int(paper["list_item"]["id"])
    return CriticalReadJobResponse(
        job_id=f"saved-demo-critical-{paper_id}",
        status="done",
        backbone=ScrutinyBackboneResponse(method_signals=signals, citation_signal=None, contested_claims=[]),
    )


def _get(client: TestClient, path: str) -> Any:
    response = client.get(path)
    if response.status_code >= 400:
        raise ValueError(f"{path} failed ({response.status_code}): {response.text[:500]}")
    return response.json()


def _registration_state(
    source_db: Path,
) -> tuple[
    RegistrationLinkOut, RegistrationVersionOut, ComparisonRunSummary, ComparisonRunDetail, DemoRegistrationLicenseAudit
]:
    db_url = f"sqlite:///{source_db.resolve().as_posix()}"
    with TestClient(create_app(db_url=db_url)) as client:
        links = _get(client, f"/papers/{PREREG_PAPER_ID}/registration-links")
        versions = _get(client, f"/papers/{PREREG_PAPER_ID}/registration-versions")
        runs = _get(client, f"/papers/{PREREG_PAPER_ID}/registration-comparisons")
        if len(links) != 1 or len(versions) != 1 or len(runs) != 1:
            raise ValueError("dedicated demo source must contain exactly one saved Meta-Preregistration run")
        detail = _get(
            client,
            f"/papers/{PREREG_PAPER_ID}/registration-comparisons/{runs[0]['id']}",
        )
    link = RegistrationLinkOut.model_validate(links[0])
    version = RegistrationVersionOut.model_validate(versions[0])
    run = ComparisonRunSummary.model_validate(runs[0])
    comparison = ComparisonRunDetail.model_validate(detail)
    if run.status != "completed" or comparison.status != "completed" or comparison.stale_reasons:
        raise ValueError("saved Meta-Preregistration run is stale; regenerate it against the bundled preprint")
    if len(comparison.rows) != 12:
        raise ValueError("saved Meta-Preregistration run no longer has the reviewed 12-row contract")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    audit = DemoRegistrationLicenseAudit.model_validate(fixture["license_audit"])
    return link, version, run, comparison, audit


def generate_synthesis_state(source_db: Path, snapshot_path: Path, output: Path) -> DemoSynthesisState:
    raw_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    DemoSnapshot.model_validate(raw_snapshot)
    link, version, run, detail, audit = _registration_state(source_db)
    papers = {str(int(item["list_item"]["id"])): item for item in raw_snapshot["api"]["papers"]}
    if set(map(int, papers)) != set(CORPUS):
        raise ValueError("saved demo snapshot does not contain exactly the curated corpus")
    prereg_key = str(PREREG_PAPER_ID)
    state = DemoSynthesisState(
        critical_reads={paper_id: _critical_read(paper) for paper_id, paper in papers.items()},
        critical_candidates={paper_id: CandidateListResponse(candidates=[]) for paper_id in papers},
        registration_links={paper_id: ([link] if paper_id == prereg_key else []) for paper_id in papers},
        registration_versions={paper_id: ([version] if paper_id == prereg_key else []) for paper_id in papers},
        registration_comparison_runs={paper_id: ([run] if paper_id == prereg_key else []) for paper_id in papers},
        registration_comparison_details={str(run.id): detail},
        registration_license_audits=[audit],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(state.model_dump(mode="json", exclude_none=True), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=PROJECT_ROOT / "demo" / "snapshot-v1.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "demo" / "synthesis-state-v1.json")
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source:
        parser.error("--confirm-public-demo-source is required; never read an ordinary working library")
    generate_synthesis_state(args.source_db, args.snapshot, args.output)
    print(f"generated saved Synthesize state: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
