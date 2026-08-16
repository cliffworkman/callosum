"""Capture every published-paper Meta-Reference outcome for the public demo.

This explicit curation command creates a fresh three-paper sandbox and drives the
production reference-integrity, citation-concentration, overlooked-work, and both
citation-context workflows. It performs public metadata egress to OpenAlex,
Semantic Scholar, and Crossref; no ordinary Callosum database is read.
"""

# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api import create_app
from app.backend.api.routers.citation_context import CitationContextReportModel
from app.backend.api.routers.citation_equity import EquityReportModel, OverlookedReportModel
from app.backend.api.routers.reference_integrity import ReferenceOverviewItem, ReferenceReportModel
from app.backend.demo_extended_state import DemoExtendedState
from tools.demo.capture_demo_extended_state import _seed_papers
from tools.demo.curated_library import CORPUS


def _must(response: Any, label: str) -> Any:
    if response.status_code >= 400:
        raise ValueError(f"{label} failed ({response.status_code}): {response.text[:800]}")
    return response.json() if response.content else None


def _job(
    client: TestClient,
    start_path: str,
    poll_path: str,
    body: dict[str, Any],
    *,
    attempts: int = 900,
) -> dict[str, Any]:
    started = _must(client.post(start_path, json=body), start_path)
    for _ in range(attempts):
        result = _must(client.get(f"{poll_path}/{started['job_id']}"), poll_path)
        if result.get("status") == "done":
            report = result.get("report")
            if report is None:
                raise ValueError(f"{start_path} completed without a report")
            return report
        if result.get("status") == "error":
            raise ValueError(f"{start_path} failed: {result.get('detail')}")
        time.sleep(0.25)
    raise ValueError(f"timed out waiting for {start_path}")


def capture(output: Path) -> DemoExtendedState:
    raw = json.loads(output.read_text(encoding="utf-8"))
    raw.setdefault("work", {}).setdefault(
        "overlooked_work",
        {str(paper_id): {"candidates": [], "pool_size": 0, "considered": 0, "shown": 0} for paper_id in sorted(CORPUS)},
    )
    current = DemoExtendedState.model_validate(raw)
    references: dict[str, ReferenceReportModel] = {}
    equity: dict[str, EquityReportModel] = {}
    overlooked: dict[str, OverlookedReportModel] = {}
    incoming: dict[str, CitationContextReportModel] = {}
    outgoing: dict[str, CitationContextReportModel] = {}

    with tempfile.TemporaryDirectory(prefix="callosum-demo-meta-reference-") as temporary:
        database = Path(temporary) / "sandbox.sqlite"
        db_url = f"sqlite:///{database.as_posix()}"
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(config, "head")
        _seed_papers(db_url)
        with TestClient(create_app(db_url=db_url)) as client:
            for paper_id in sorted(CORPUS):
                key = str(paper_id)
                references[key] = ReferenceReportModel.model_validate(
                    _job(
                        client,
                        f"/papers/{paper_id}/reference-integrity/run",
                        "/reference-integrity/run",
                        {},
                    )
                )
                equity[key] = EquityReportModel.model_validate(
                    _job(
                        client,
                        "/methods/citation-equity/run",
                        "/methods/citation-equity/run",
                        {"paper_id": paper_id},
                    )
                )
                overlooked[key] = OverlookedReportModel.model_validate(
                    _job(
                        client,
                        "/methods/citation-equity/overlooked",
                        "/methods/citation-equity/overlooked",
                        {"paper_id": paper_id},
                    )
                )
                incoming[key] = CitationContextReportModel.model_validate(
                    _job(
                        client,
                        "/papers/citation-context/run",
                        "/papers/citation-context/run",
                        {"paper_id": paper_id, "direction": "citations"},
                    )
                )
                outgoing[key] = CitationContextReportModel.model_validate(
                    _job(
                        client,
                        "/papers/citation-context/run",
                        "/papers/citation-context/run",
                        {"paper_id": paper_id, "direction": "references"},
                    )
                )
                print(
                    f"captured paper {paper_id}: refs={references[key].checked_count}; "
                    f"equity={equity[key].references_resolved}/{equity[key].references_total}; "
                    f"overlooked={overlooked[key].shown}/{overlooked[key].considered}; "
                    f"context={incoming[key].classified}/{incoming[key].total_citations} incoming, "
                    f"{outgoing[key].classified}/{outgoing[key].total_citations} outgoing",
                    flush=True,
                )

    if any(report.checked_count <= 0 for report in references.values()):
        raise ValueError("a curated paper returned no linked reference-integrity coverage")
    if any(report.references_total <= 0 or not report.signals for report in equity.values()):
        raise ValueError("a curated paper returned no citation-concentration outcome")
    if any(report.considered <= 0 for report in overlooked.values()):
        raise ValueError("a curated paper returned no overlooked-work candidate coverage")
    if any(incoming[key].total_citations + outgoing[key].total_citations <= 0 for key in incoming):
        raise ValueError("a curated paper returned no citation-context graph coverage in either direction")
    if not any(report.classified > 0 for report in (*incoming.values(), *outgoing.values())):
        raise ValueError("citation-context capture returned no classifiable sentence in the curated corpus")

    work = current.work.model_copy(
        update={
            "reference_integrity": references,
            "reference_overview": [
                ReferenceOverviewItem(
                    paper_id=int(paper_id),
                    active_count=report.active_count,
                    unreviewed_count=sum(item.review_state == "unreviewed" for item in report.items),
                    confirmed_count=sum(item.review_state == "confirmed_problem" for item in report.items),
                )
                for paper_id, report in references.items()
                if report.active_count
            ],
            "citation_equity": equity,
            "overlooked_work": overlooked,
            "citation_context_incoming": incoming,
            "citation_context_outgoing": outgoing,
        }
    )
    generated_with = dict(current.generated_with)
    generated_with["meta_reference"] = (
        "fresh dedicated three-paper sandbox; production OpenAlex, Semantic Scholar, Crossref, local SPECTER, "
        "and local NLI workflows"
    )
    state = DemoExtendedState.model_validate(
        current.model_copy(update={"work": work, "generated_with": generated_with}).model_dump(mode="json")
    )
    output.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "demo" / "extended-state-v1.json")
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    parser.add_argument("--confirm-metadata-egress", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source or not args.confirm_metadata_egress:
        parser.error("both --confirm-public-demo-source and --confirm-metadata-egress are required")
    state = capture(args.output)
    print(f"saved complete Meta-Reference snapshots for {len(state.work.citation_equity)} papers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
