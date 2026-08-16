"""Add explicitly requested, evidence-bounded LLM triage to saved public-demo state.

This is a curation command, never an ordinary build step. It sends only the bounded
funding cards and registration/publication evidence already selected for the public
demo through Callosum's production triage evaluators, then validates the shared API
response models before replacing the two saved-state fixtures.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api.routers.summaries import SummarizeJobResponse
from app.backend.demo_ask_overview import DemoAskOverviewState, verified_claims_sha256
from app.backend.demo_extended_state import DemoExtendedState
from app.backend.demo_synthesis_state import DemoSynthesisState
from app.backend.funding.llm_triage import FundingLlmTriageEvaluator
from app.backend.llm.providers import requires_egress
from app.backend.registration_comparison.llm_triage import RegistrationComparisonTriageEvaluator
from integrations.gemini import GeminiConfig
from integrations.gemini.overview import OVERVIEW_PROMPT_VERSION, GeminiOverviewGenerator


def _write_validated(path: Path, model: Any) -> None:
    path.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _funding_context(snapshot: dict[str, Any], paper_id: int) -> str:
    paper = next(item for item in snapshot["api"]["papers"] if int(item["list_item"]["id"]) == paper_id)
    title = str(paper["detail"].get("title") or "").strip()
    abstract = str(paper["detail"].get("abstract") or "").strip()
    return "\n\n".join(part for part in (title, abstract) if part)


def triage(
    snapshot_path: Path,
    extended_path: Path,
    synthesis_path: Path,
    ask_overview_path: Path,
) -> tuple[DemoExtendedState, DemoSynthesisState, DemoAskOverviewState]:
    config = GeminiConfig.from_environment()
    if requires_egress(config) and not config.data_egress_enabled:
        raise ValueError("AI egress consent is disabled; refusing public-demo triage")
    if requires_egress(config) and not config.resolved_api_key():
        raise ValueError("the configured AI provider has no credential")

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    extended_raw = json.loads(extended_path.read_text(encoding="utf-8"))
    synthesis_raw = json.loads(synthesis_path.read_text(encoding="utf-8"))
    DemoExtendedState.model_validate(extended_raw)
    DemoSynthesisState.model_validate(synthesis_raw)

    funding_reports = extended_raw["discover"]["funding_reports"]
    if len(funding_reports) != 1:
        raise ValueError("the curated demo must contain exactly one Funding report")
    report = next(iter(funding_reports.values()))
    source_id = int(report["profile"]["source_id"])
    funding_status = FundingLlmTriageEvaluator(config=config).evaluate(
        report=report,
        research_context=_funding_context(snapshot, source_id),
    )
    if funding_status.get("status") != "success" or not funding_status.get("annotated_count"):
        raise ValueError(f"Funding LLM triage did not produce saved annotations: {funding_status}")
    funding_status["provider_id"] = str(config.provider)
    funding_status["model_id"] = str(config.model)
    report["llm_triage_status"] = funding_status
    for summary in extended_raw["discover"]["funding_runs"]:
        if int(summary["run_id"]) == int(report["run_id"]):
            summary["llm_annotated_count"] = int(funding_status["annotated_count"])
    extended_raw["generated_with"]["llm_triage"] = f"{config.provider}/{config.model}; funding-triage-v1"

    details = synthesis_raw["registration_comparison_details"]
    if len(details) != 1:
        raise ValueError("the curated demo must contain exactly one Meta-Preregistration comparison")
    detail = next(iter(details.values()))
    registration_result = RegistrationComparisonTriageEvaluator(config=config).evaluate(rows=detail["rows"])
    registration_status = registration_result.get("status") or {}
    if registration_status.get("status") != "success" or not registration_result.get("annotations"):
        raise ValueError(f"Meta-Preregistration LLM triage did not produce annotations: {registration_status}")
    registration_status["stale_reasons"] = []
    annotations = {int(key): value for key, value in registration_result["annotations"].items()}
    for row in detail["rows"]:
        annotation = dict(annotations[int(row["id"])])
        annotation.update(
            {
                "provider_id": str(config.provider),
                "model_id": str(config.model),
                "prompt_version": registration_status["prompt_version"],
                "status": "current",
                "stale_reasons": [],
            }
        )
        row["llm_triage"] = annotation
    detail["llm_triage_status"] = registration_status
    provenance = {
        "provider_id": str(config.provider),
        "model_id": str(config.model),
        "prompt_version": registration_status["prompt_version"],
    }
    detail["model_versions"]["llm_triage"] = provenance
    for runs in synthesis_raw["registration_comparison_runs"].values():
        for run in runs:
            if int(run["id"]) == int(detail["id"]):
                run["model_versions"]["llm_triage"] = provenance

    manifest = snapshot.get("manifest") or {}
    summary_id = int(manifest["initial_summary_id"])
    summary = SummarizeJobResponse.model_validate(snapshot["api"]["summaries"][str(summary_id)])
    verified = [sentence for sentence in summary.sentences or [] if not sentence.flagged]
    if not verified:
        raise ValueError("the curated synthesis has no verified claims to narrate")
    generated = GeminiOverviewGenerator(config=config).generate(
        verified_claims=[sentence.text for sentence in verified],
        scope_ref={
            "paper_ids": None,
            "cluster_node_id": None,
            "query": str(manifest["question"]),
            "sections": summary.section_filter,
        },
    )
    overview = []
    for item in generated:
        ordinals = sorted({verified[index].ordinal for index in item.claim_indices if 0 <= index < len(verified)})
        if item.text.strip() and ordinals:
            overview.append({"text": item.text.strip(), "claim_ordinals": ordinals})
    if not overview:
        raise ValueError("the production Overview generator returned no traceable sentences")
    ask_overview = DemoAskOverviewState(
        summary_id=summary_id,
        overview=overview,
        verified_claim_count=len(verified),
        verified_claims_sha256=verified_claims_sha256(summary),
        provider_id=str(config.provider),
        model_id=str(config.model),
        prompt_version=OVERVIEW_PROMPT_VERSION,
    )

    extended = DemoExtendedState.model_validate(extended_raw)
    synthesis = DemoSynthesisState.model_validate(synthesis_raw)
    _write_validated(extended_path, extended)
    _write_validated(synthesis_path, synthesis)
    _write_validated(ask_overview_path, ask_overview)
    return extended, synthesis, ask_overview


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=ROOT / "demo" / "snapshot-v1.json")
    parser.add_argument("--extended-state", type=Path, default=ROOT / "demo" / "extended-state-v1.json")
    parser.add_argument("--synthesis-state", type=Path, default=ROOT / "demo" / "synthesis-state-v1.json")
    parser.add_argument("--ask-overview", type=Path, default=ROOT / "demo" / "ask-overview-v1.json")
    parser.add_argument("--confirm-public-demo-source", action="store_true")
    parser.add_argument("--confirm-ai-egress", action="store_true")
    args = parser.parse_args()
    if not args.confirm_public_demo_source or not args.confirm_ai_egress:
        parser.error("both --confirm-public-demo-source and --confirm-ai-egress are required")
    extended, synthesis, ask_overview = triage(
        args.snapshot,
        args.extended_state,
        args.synthesis_state,
        args.ask_overview,
    )
    funding = next(iter(extended.discover.funding_reports.values()))
    comparison = next(iter(synthesis.registration_comparison_details.values()))
    print(
        "saved public-demo LLM triage: "
        f"funding={funding.llm_triage_status.get('annotated_count')} items; "
        f"meta-preregistration={comparison.llm_triage_status.get('annotated_count')} rows; "
        f"synthesis-overview={len(ask_overview.overview)} sentences"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
