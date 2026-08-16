"""Merge audited Meta-Reference results after a curated paper replacement.

Unchanged papers retain their previously deployed public reports. The replacement paper
uses newly returned production API reports; genuine provider-empty outcomes remain empty
and retain their provider status rather than borrowing another paper's evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api.routers.citation_context import CitationContextReportModel  # noqa: E402
from app.backend.api.routers.citation_equity import EquityReportModel, OverlookedReportModel  # noqa: E402
from app.backend.api.routers.reference_integrity import (  # noqa: E402
    ReferenceOverviewItem,
    ReferenceReportModel,
)
from app.backend.demo_extended_state import DemoExtendedState  # noqa: E402

REPLACEMENT_DEMO_ID = 42
UNCHANGED_IDS = (67, 88)


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _prior_reference_report(payload: dict) -> ReferenceReportModel:
    """Remove propagation edges whose source paper left the curated library."""

    cleaned_items = []
    for original_item in payload["items"]:
        item = dict(original_item)
        cleaned_signals = []
        for original_signal in item["signals"]:
            signal = dict(original_signal)
            if signal.get("detector_kind") != "own_library_propagation":
                cleaned_signals.append(signal)
                continue
            evidence = dict(signal.get("evidence") or {})
            sources = [
                source
                for source in evidence.get("source_instances", [])
                if int(source.get("citing_paper_id") or 0) != REPLACEMENT_DEMO_ID
            ]
            if sources:
                signal["evidence"] = evidence | {"source_instances": sources}
                cleaned_signals.append(signal)
        if cleaned_signals:
            item["signals"] = cleaned_signals
            cleaned_items.append(item)
    return ReferenceReportModel.model_validate(
        dict(payload) | {"active_count": len(cleaned_items), "items": cleaned_items}
    )


def merge(previous_snapshot: Path, output: Path, local_dir: Path) -> DemoExtendedState:
    prior = _read(previous_snapshot)["api"]["extended"]["work"]
    current = DemoExtendedState.model_validate_json(output.read_bytes())
    reference = _read(local_dir / "demo-paper25-reference.json")
    reference["paper_id"] = REPLACEMENT_DEMO_ID
    references = {
        "42": ReferenceReportModel.model_validate(reference),
        **{str(pid): _prior_reference_report(prior["reference_integrity"][str(pid)]) for pid in UNCHANGED_IDS},
    }
    equity = {
        "42": EquityReportModel.model_validate(_read(local_dir / "demo-paper25-equity.json")),
        **{str(pid): EquityReportModel.model_validate(prior["citation_equity"][str(pid)]) for pid in UNCHANGED_IDS},
    }
    incoming = {
        "42": CitationContextReportModel.model_validate(_read(local_dir / "demo-paper25-incoming.json")),
        **{
            str(pid): CitationContextReportModel.model_validate(prior["citation_context_incoming"][str(pid)])
            for pid in UNCHANGED_IDS
        },
    }
    outgoing = {
        "42": CitationContextReportModel.model_validate(_read(local_dir / "demo-paper25-outgoing.json")),
        **{
            str(pid): CitationContextReportModel.model_validate(prior["citation_context_outgoing"][str(pid)])
            for pid in UNCHANGED_IDS
        },
    }
    overlooked = {
        "42": OverlookedReportModel.model_validate({"candidates": [], "pool_size": 0, "considered": 0, "shown": 0}),
        **{str(pid): OverlookedReportModel.model_validate(prior["overlooked_work"][str(pid)]) for pid in UNCHANGED_IDS},
    }
    work = current.work.model_copy(
        update={
            "reference_integrity": references,
            "reference_overview": [
                ReferenceOverviewItem(
                    paper_id=int(pid),
                    active_count=report.active_count,
                    unreviewed_count=sum(item.review_state == "unreviewed" for item in report.items),
                    confirmed_count=sum(item.review_state == "confirmed_problem" for item in report.items),
                )
                for pid, report in references.items()
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
        "paper 42: fresh production API capture; providers returned no linked reference/citation records, "
        "with citation-concentration field calibration retained; papers 67/88: prior deployed public reports"
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
    parser.add_argument("--previous-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "demo" / "extended-state-v1.json")
    parser.add_argument("--local-dir", type=Path, default=ROOT / ".local")
    parser.add_argument("--confirm-public-reports", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_reports:
        parser.error("--confirm-public-reports is required")
    state = merge(args.previous_snapshot, args.output, args.local_dir)
    print(f"merged Meta-Reference results for {len(state.work.citation_equity)} curated papers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
