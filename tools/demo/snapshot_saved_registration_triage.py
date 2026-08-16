"""Snapshot exact saved Meta-Preregistration AI annotations from a named local Callosum run.

This is an explicit public-demo curation command. It reads one user-selected localhost API run,
whitelists only the reversible row annotations and their provider provenance, maps them to the
already-curated twelve-row demo crosswalk by stable ordinal/field contract, and records hashes of
the source and demo bounded evidence bases. It never exports complete documents, source paths,
credentials, notes, or review state.
"""

# ruff: noqa: E402 -- direct execution needs the repository root on sys.path before app imports.

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.demo_synthesis_state import DemoSynthesisState
from app.backend.registration_comparison.llm_triage import _bounded_items

SCHEMA_VERSION = 1
EXPECTED_DOI = "10.1037/aca0000454"
EXPECTED_TITLE_PREFIX = "What is good is beautiful"
EXPECTED_ROW_COUNT = 12
EXPECTED_ANNOTATION_KEYS = {
    "label",
    "show_in_triage",
    "rationale",
    "concerns",
    "basis",
    "provider_id",
    "model_id",
    "prompt_version",
    "status",
    "stale_reasons",
}
FORBIDDEN = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)"),
    re.compile(r"(?i)(?:[a-z]:\\|/users/|/home/|127\.0\.0\.1|localhost)"),
)
PUBLIC_BASIS_WARNING = (
    "These are the exact saved AI-triage annotations from the reviewed Callosum comparison against the "
    "published article. The static demo bundles a redistributable preprint, so its displayed publication "
    "passages and source locations can differ from that saved run."
)


def _get_json(base_url: str, path: str) -> Any:
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 -- explicitly confirmed loopback source
        return json.load(response)


def _validate_loopback(base_url: str) -> None:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("source URL must be an explicit local Callosum HTTP endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("source URL cannot contain credentials, query parameters, or a fragment")


def _basis_hash(row: dict[str, Any]) -> str:
    items, truncated = _bounded_items([row])
    if truncated or len(items) != 1:
        raise ValueError("could not construct the complete bounded triage basis for one row")
    item = dict(items[0])
    item.pop("row_id", None)
    return hashlib.sha256(
        json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def apply_saved_triage(
    *,
    source_paper: dict[str, Any],
    source_detail: dict[str, Any],
    synthesis_raw: dict[str, Any],
) -> tuple[DemoSynthesisState, dict[str, Any]]:
    doi = str(source_paper.get("doi") or "").casefold()
    title = str(source_paper.get("title") or "")
    if doi != EXPECTED_DOI or not title.startswith(EXPECTED_TITLE_PREFIX):
        raise ValueError("the selected source paper is not the curated Good-is-Beautiful article")
    source_rows = source_detail.get("rows")
    if not isinstance(source_rows, list) or len(source_rows) != EXPECTED_ROW_COUNT:
        raise ValueError("the selected source run does not contain the expected twelve-row comparison")
    source_status = source_detail.get("llm_triage_status")
    if not isinstance(source_status, dict) or source_status.get("status") != "success":
        raise ValueError("the selected source run has no successful saved AI triage")
    if int(source_status.get("annotated_count") or 0) != EXPECTED_ROW_COUNT:
        raise ValueError("the selected source run does not have twelve saved AI annotations")

    raw = deepcopy(synthesis_raw)
    details = raw.get("registration_comparison_details")
    if not isinstance(details, dict) or len(details) != 1:
        raise ValueError("the demo must contain exactly one Meta-Preregistration comparison")
    detail = next(iter(details.values()))
    demo_rows = detail.get("rows")
    if not isinstance(demo_rows, list) or len(demo_rows) != EXPECTED_ROW_COUNT:
        raise ValueError("the demo comparison no longer has the expected twelve-row contract")

    annotations: list[dict[str, Any]] = []
    occurrences: dict[str, int] = {}
    for ordinal, (source_row, demo_row) in enumerate(zip(source_rows, demo_rows, strict=True)):
        source_field = str(source_row.get("field_type") or "")
        demo_field = str(demo_row.get("field_type") or "")
        if source_field != demo_field:
            raise ValueError(f"row {ordinal} field drift: source={source_field!r}, demo={demo_field!r}")
        annotation = source_row.get("llm_triage")
        if not isinstance(annotation, dict) or set(annotation) != EXPECTED_ANNOTATION_KEYS:
            raise ValueError(f"row {ordinal} AI annotation has an unexpected field contract")
        if annotation.get("status") != "current" or annotation.get("stale_reasons"):
            raise ValueError(f"row {ordinal} AI annotation is not current in the selected source run")
        exact_annotation = deepcopy(annotation)
        demo_row["llm_triage"] = exact_annotation
        occurrence = occurrences.get(source_field, 0)
        occurrences[source_field] = occurrence + 1
        source_hash = _basis_hash(source_row)
        demo_hash = _basis_hash(demo_row)
        annotations.append(
            {
                "ordinal": ordinal,
                "field_type": source_field,
                "field_occurrence": occurrence,
                "source_basis_sha256": source_hash,
                "demo_basis_sha256": demo_hash,
                "basis_matches_demo": source_hash == demo_hash,
                "llm_triage": exact_annotation,
            }
        )

    provider_id = str(source_status.get("provider_id") or "")
    model_id = str(source_status.get("model_id") or "")
    prompt_version = str(source_status.get("prompt_version") or "")
    if not provider_id or not model_id or not prompt_version:
        raise ValueError("the selected source run is missing AI provider provenance")
    provenance = {
        "provider_id": provider_id,
        "model_id": model_id,
        "prompt_version": prompt_version,
    }
    detail["llm_triage_status"] = {
        **deepcopy(source_status),
        "warning": PUBLIC_BASIS_WARNING if any(not item["basis_matches_demo"] for item in annotations) else None,
    }
    detail.setdefault("model_versions", {})["llm_triage"] = provenance
    for runs in raw.get("registration_comparison_runs", {}).values():
        for run in runs:
            if int(run.get("id")) == int(detail.get("id")):
                run.setdefault("model_versions", {})["llm_triage"] = provenance

    state = DemoSynthesisState.model_validate(raw)
    fixture = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "paper_id": int(source_paper["id"]),
            "paper_title": title,
            "paper_doi": str(source_paper["doi"]),
            "comparison_run_id": int(source_detail["id"]),
            "comparison_created_at": source_detail.get("created_at"),
            "curation_note": (
                "Explicit whitelist snapshot of exact saved AI-triage annotations. Complete documents, working "
                "paths, credentials, notes, and review state are not included."
            ),
        },
        "demo_mapping": {
            "comparison_run_id": int(detail["id"]),
            "row_mapping": "stable ordinal plus field type and repeated-field occurrence",
        },
        "triage_status": deepcopy(source_status),
        "public_basis_warning": detail["llm_triage_status"]["warning"],
        "annotations": annotations,
    }
    encoded = json.dumps(fixture, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    for pattern in FORBIDDEN:
        if pattern.search(encoded):
            raise ValueError(f"public triage fixture rejected by forbidden-data pattern: {pattern.pattern}")
    return state, fixture


def snapshot_saved_triage(
    *,
    source_url: str,
    source_paper_id: int,
    source_run_id: int,
    synthesis_path: Path,
    fixture_path: Path,
) -> DemoSynthesisState:
    _validate_loopback(source_url)
    source_paper = _get_json(source_url, f"/papers/{source_paper_id}")
    source_detail = _get_json(
        source_url,
        f"/papers/{source_paper_id}/registration-comparisons/{source_run_id}",
    )
    synthesis_raw = json.loads(synthesis_path.read_text(encoding="utf-8"))
    state, fixture = apply_saved_triage(
        source_paper=source_paper,
        source_detail=source_detail,
        synthesis_raw=synthesis_raw,
    )
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        json.dumps(fixture, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    synthesis_path.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-paper-id", type=int, required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--synthesis-state", type=Path, default=ROOT / "demo" / "synthesis-state-v1.json")
    parser.add_argument(
        "--output-fixture",
        type=Path,
        default=ROOT / "tools" / "demo" / "fixtures" / "good-beautiful-registration-triage-run2.json",
    )
    parser.add_argument("--confirm-working-source-intermediate", action="store_true")
    parser.add_argument("--confirm-public-fields", action="store_true")
    args = parser.parse_args()
    if not args.confirm_working_source_intermediate or not args.confirm_public_fields:
        parser.error("both explicit source/public-field confirmations are required")
    state = snapshot_saved_triage(
        source_url=args.source_url,
        source_paper_id=args.source_paper_id,
        source_run_id=args.source_run_id,
        synthesis_path=args.synthesis_state,
        fixture_path=args.output_fixture,
    )
    detail = next(iter(state.registration_comparison_details.values()))
    print(
        "snapshotted exact saved Meta-Preregistration triage: "
        f"{detail.llm_triage_status.get('annotated_count')} rows from run {args.source_run_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
