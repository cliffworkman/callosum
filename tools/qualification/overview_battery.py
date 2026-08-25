"""Reusable, non-production qualification harness for synthesis Overview.

Candidate execution uses Callosum's production prompt, provider-neutral ``complete()``, parser,
and lifecycle reference filter. Raw model responses and blinded packets stay outside the repo.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import random
import secrets
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PROFILE_DIR = ROOT / ".claude" / "qualification" / "synthesis-overview-v1"
FREEZE_PATH = PROFILE_DIR / "freeze.json"
FROZEN_INPUTS = (
    ".claude/qualification/synthesis-overview-v1/preregistration.json",
    ".claude/qualification/synthesis-overview-v1/codebook.md",
    ".claude/qualification/synthesis-overview-v1/controls.json",
    ".claude/qualification/synthesis-overview-v1/fixtures.json",
    ".claude/qualification/synthesis-overview-v1/candidates.json",
    "integrations/gemini/overview.py",
    "app/backend/summarization/overview.py",
    "app/backend/summarization/overview_lifecycle.py",
    "app/backend/llm/providers.py",
    "tools/qualification/overview_battery.py",
)


@dataclass(frozen=True)
class MechanicalScore:
    json_parse: bool
    array_root: bool
    schema_valid: bool
    structural_references_valid: bool
    parser_success: bool
    usable_after_reference_filter: bool
    sentence_count: int
    requested_sentence_count_met: bool
    suspected_output_truncation: bool
    errors: tuple[str, ...]

    @property
    def gate_pass(self) -> bool:
        return all(
            (
                self.json_parse,
                self.array_root,
                self.schema_valid,
                self.structural_references_valid,
                self.parser_success,
                self.usable_after_reference_filter,
                not self.suspected_output_truncation,
            )
        )


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def freeze_manifest(starting_head: str) -> dict[str, object]:
    files = {relative: _sha256(ROOT / relative) for relative in FROZEN_INPUTS}
    return {
        "schema_version": 1,
        "qualification_profile": "synthesis-overview-v1",
        "starting_head": starting_head,
        "files": files,
        "aggregate_sha256": _canonical_sha256(files),
    }


def verify_freeze() -> dict[str, object]:
    if not FREEZE_PATH.is_file():
        raise RuntimeError("qualification battery has not been frozen")
    frozen = _json(FREEZE_PATH)
    expected = frozen.get("files")
    if not isinstance(expected, dict):
        raise RuntimeError("invalid qualification freeze manifest")
    actual = {relative: _sha256(ROOT / relative) for relative in expected}
    if actual != expected or _canonical_sha256(actual) != frozen.get("aggregate_sha256"):
        raise RuntimeError("qualification battery differs from its frozen manifest")
    return frozen


def _strip_code_fence(text: str) -> str:
    from integrations.gemini.overview import _strip_code_fence as production_strip

    return production_strip(text)


def score_response(raw_text: str, claim_count: int, completion_tokens: int | None = None) -> MechanicalScore:
    from app.backend.summarization.overview import validated_overview_items
    from integrations.gemini.overview import _parse_overview_response

    errors: list[str] = []
    payload: object = None
    try:
        payload = json.loads(_strip_code_fence(raw_text))
        json_parse = True
    except (json.JSONDecodeError, TypeError, ValueError):
        json_parse = False
        errors.append("json_parse")
    array_root = isinstance(payload, list)
    if json_parse and not array_root:
        errors.append("array_root")

    schema_valid = array_root
    structural_refs = array_root
    if isinstance(payload, list):
        for item in payload:
            valid_item = isinstance(item, dict) and isinstance(item.get("text"), str) and bool(item["text"].strip())
            refs = item.get("claim_indices") if isinstance(item, dict) else None
            valid_refs_shape = (
                isinstance(refs, list)
                and bool(refs)
                and all(isinstance(value, int) and not isinstance(value, bool) for value in refs)
            )
            if not valid_item or not valid_refs_shape:
                schema_valid = False
            if not valid_refs_shape or not all(0 <= value < claim_count for value in refs):
                structural_refs = False
    if not schema_valid:
        errors.append("schema")
    if not structural_refs:
        errors.append("structural_references")

    parsed = []
    try:
        parsed = _parse_overview_response(raw_text)
        parser_success = True
    except (json.JSONDecodeError, TypeError, ValueError):
        parser_success = False
        errors.append("production_parser")
    usable = bool(validated_overview_items(parsed, list(range(claim_count)))) if parser_success else False
    if not usable:
        errors.append("no_usable_items")
    sentence_count = len(payload) if isinstance(payload, list) else 0
    requested_count = 2 <= sentence_count <= 4
    suspected_truncation = not json_parse and completion_tokens is not None and completion_tokens >= 250
    if suspected_truncation:
        errors.append("suspected_output_truncation")
    return MechanicalScore(
        json_parse=json_parse,
        array_root=array_root,
        schema_valid=schema_valid,
        structural_references_valid=structural_refs,
        parser_success=parser_success,
        usable_after_reference_filter=usable,
        sentence_count=sentence_count,
        requested_sentence_count_met=requested_count,
        suspected_output_truncation=suspected_truncation,
        errors=tuple(dict.fromkeys(errors)),
    )


def validate_controls() -> dict[str, object]:
    controls = _json(PROFILE_DIR / "controls.json")["controls"]
    results = []
    for control in controls:
        score = score_response(control["raw_output"], len(control["claims"]))
        expected = control["expected_mechanical"] == "pass"
        results.append(
            {
                "control_id": control["control_id"],
                "expected": expected,
                "actual": score.gate_pass,
                "matched": expected == score.gate_pass,
                "semantic_expected": control["expected_semantic"],
            }
        )
    if not all(item["matched"] for item in results):
        raise RuntimeError("mechanical controls did not behave as preregistered")
    return {"controls": results, "all_mechanical_controls_matched": True}


def _fixtures_for_stage(stage: str) -> list[dict[str, object]]:
    fixtures = _json(PROFILE_DIR / "fixtures.json")["fixtures"]
    if stage == "stage1":
        return [fixture for fixture in fixtures if fixture.get("partition") == "qualification" and fixture["stage_1"]]
    partition = {"stage2": "qualification", "holdout": "holdout", "calibration": "calibration"}[stage]
    return [fixture for fixture in fixtures if fixture.get("partition") == partition]


def _candidate(code: str) -> dict[str, object]:
    for candidate in _json(PROFILE_DIR / "candidates.json")["candidates"]:
        if candidate["candidate_code"] == code:
            return candidate
    raise RuntimeError(f"unknown candidate code: {code}")


def _usage_value(meta: object, name: str) -> int | None:
    value = getattr(meta, name, None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def execute(candidate_code: str, stage: str, repetitions: int, output: Path) -> None:
    from app.backend.llm.managed_local import load_target_from_environment
    from app.backend.llm.providers import complete
    from app.backend.provider_runtime import ProviderClientRuntime
    from app.backend.summarization.overview import validated_overview_items
    from integrations.gemini.overview import _parse_overview_response, _prompt

    frozen = verify_freeze()
    candidate = _candidate(candidate_code)
    target = load_target_from_environment()
    if target.model_artifact_digest != candidate.get("artifact_sha256"):
        raise RuntimeError("managed descriptor model digest does not match frozen candidate identity")
    records: list[dict[str, object]] = []
    runtime = ProviderClientRuntime()
    config = target.config(runtime)
    try:
        for fixture in _fixtures_for_stage(stage):
            claims = fixture["claims"]
            for repetition in range(1, repetitions + 1):
                started = time.perf_counter()
                error_type: str | None = None
                raw_text = ""
                usage = None
                try:
                    result = complete(config, _prompt(claims))
                    raw_text = str(result.text or "")
                    usage = result.usage_metadata
                except Exception as exc:  # noqa: BLE001 - errors are measured, not hidden
                    error_type = type(exc).__name__
                elapsed = time.perf_counter() - started
                completion_tokens = _usage_value(usage, "candidates_token_count")
                score = score_response(raw_text, len(claims), completion_tokens) if error_type is None else None
                parsed = []
                validated = []
                if score is not None and score.parser_success:
                    parsed = _parse_overview_response(raw_text)
                    validated = validated_overview_items(parsed, list(range(len(claims))))
                records.append(
                    {
                        "fixture_id": fixture["fixture_id"],
                        "repetition": repetition,
                        "http_success": error_type is None,
                        "error_type": error_type,
                        "elapsed_seconds": elapsed,
                        "usage": {
                            "prompt_tokens": _usage_value(usage, "prompt_token_count"),
                            "completion_tokens": completion_tokens,
                            "total_tokens": _usage_value(usage, "total_token_count"),
                        },
                        "raw_text": raw_text,
                        "raw_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
                        "mechanical": asdict(score) if score is not None else None,
                        "parsed_sentences": [asdict(item) for item in parsed],
                        "validated_items": validated,
                    }
                )
    finally:
        runtime.close()

    payload = {
        "schema_version": 1,
        "qualification_profile": "synthesis-overview-v1",
        "battery_aggregate_sha256": frozen["aggregate_sha256"],
        "candidate": candidate,
        "stage": stage,
        "repetitions": repetitions,
        "runtime": {
            "family": target.runtime_family,
            "version": target.runtime_version,
            "launcher_sha256": target.runtime_binary_digest,
            "bundle_manifest_sha256": target.runtime_bundle_manifest_digest,
            "declared_build_backend": target.declared_build_backend,
        },
        "execution": {
            "requested": asdict(target.requested_execution),
            "observed": asdict(target.observed_execution),
        },
        "model": {
            "artifact_sha256": target.model_artifact_digest,
            "chat_template_sha256": target.chat_template_digest,
        },
        "generation": {
            "context_tokens": target.context_tokens,
            "max_output_tokens": target.max_output_tokens,
            "temperature": target.temperature,
            "seed": target.seed,
        },
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    temporary.replace(output)


def summarize(paths: list[Path]) -> dict[str, object]:
    rows = []
    for path in paths:
        payload = _json(path)
        records = payload["records"]
        usable = [
            row for row in records if row.get("mechanical") and row["mechanical"]["usable_after_reference_filter"]
        ]
        gate_pass = [row for row in records if row.get("mechanical") and _score_dict_gate(row["mechanical"])]
        latencies = [row["elapsed_seconds"] for row in records if row["http_success"]]
        rows.append(
            {
                "candidate_code": payload["candidate"]["candidate_code"],
                "stage": payload["stage"],
                "n": len(records),
                "http_success": sum(bool(row["http_success"]) for row in records),
                "mechanical_gate_pass": len(gate_pass),
                "usable": len(usable),
                "structural_reference_failures": sum(
                    bool(row.get("mechanical")) and not row["mechanical"]["structural_references_valid"]
                    for row in records
                ),
                "requested_sentence_count": sum(
                    bool(row.get("mechanical")) and row["mechanical"]["requested_sentence_count_met"] for row in records
                ),
                "median_latency_seconds": statistics.median(latencies) if latencies else None,
            }
        )
    return {"results": rows}


def _score_dict_gate(score: dict[str, object]) -> bool:
    return all(
        bool(score[key])
        for key in (
            "json_parse",
            "array_root",
            "schema_valid",
            "structural_references_valid",
            "parser_success",
            "usable_after_reference_filter",
        )
    ) and not bool(score["suspected_output_truncation"])


def make_packet(paths: list[Path], packet: Path, mapping: Path, key_file: Path) -> None:
    fixtures = {item["fixture_id"]: item for item in _json(PROFILE_DIR / "fixtures.json")["fixtures"]}
    if key_file.exists():
        key = key_file.read_text(encoding="ascii").strip()
    else:
        key = secrets.token_hex(32)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key, encoding="ascii")
        try:
            key_file.chmod(0o600)
        except OSError:
            pass
    entries = []
    identities = {}
    for path in paths:
        payload = _json(path)
        candidate_code = payload["candidate"]["candidate_code"]
        for record in payload["records"]:
            identity = f"{candidate_code}|{record['fixture_id']}|{record['repetition']}|{record['raw_sha256']}"
            response_id = hmac.new(key.encode("ascii"), identity.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
            fixture = fixtures[record["fixture_id"]]
            entries.append(
                {
                    "response_id": response_id,
                    "verified_claims": [
                        {"index": index, "claim": claim} for index, claim in enumerate(fixture["claims"])
                    ],
                    "raw_overview": record["raw_text"],
                    "parsed_sentences": record["parsed_sentences"],
                    "adjudication": {
                        "supported_factual_content": None,
                        "semantic_reference_adequacy": None,
                        "unsupported_fact": None,
                        "unsupported_fact_category": [],
                        "inferential_upgrade": None,
                        "inferential_upgrade_category": [],
                        "critical_omission": None,
                        "framing_distortion": None,
                        "notes": "",
                        "overall_scientific_integrity": None,
                    },
                }
            )
            identities[response_id] = {
                "candidate_code": candidate_code,
                "fixture_id": record["fixture_id"],
                "repetition": record["repetition"],
            }
    random.Random(hashlib.sha256(key.encode("ascii")).digest()).shuffle(entries)
    packet.parent.mkdir(parents=True, exist_ok=True)
    packet.write_text(json.dumps({"schema_version": 1, "responses": entries}, indent=2), encoding="utf-8")
    mapping.write_text(json.dumps({"schema_version": 1, "identities": identities}, indent=2), encoding="utf-8")


def _paths(values: list[str]) -> list[Path]:
    return [Path(value).resolve() for value in values]


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--starting-head", required=True)
    commands.add_parser("validate-controls")
    execute_parser = commands.add_parser("execute")
    execute_parser.add_argument("--candidate", required=True)
    execute_parser.add_argument("--stage", choices=("calibration", "stage1", "stage2", "holdout"), required=True)
    execute_parser.add_argument("--repetitions", type=int, required=True)
    execute_parser.add_argument("--output", type=Path, required=True)
    summary_parser = commands.add_parser("summarize")
    summary_parser.add_argument("inputs", nargs="+")
    packet_parser = commands.add_parser("packet")
    packet_parser.add_argument("--packet", type=Path, required=True)
    packet_parser.add_argument("--mapping", type=Path, required=True)
    packet_parser.add_argument("--key-file", type=Path, required=True)
    packet_parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()
    if args.command == "freeze":
        FREEZE_PATH.write_text(json.dumps(freeze_manifest(args.starting_head), indent=2) + "\n", encoding="utf-8")
    elif args.command == "validate-controls":
        print(json.dumps(validate_controls(), indent=2))
    elif args.command == "execute":
        if not 1 <= args.repetitions <= 10:
            raise SystemExit("repetitions must be between 1 and 10")
        execute(args.candidate, args.stage, args.repetitions, args.output.resolve())
    elif args.command == "summarize":
        print(json.dumps(summarize(_paths(args.inputs)), indent=2))
    elif args.command == "packet":
        make_packet(_paths(args.inputs), args.packet.resolve(), args.mapping.resolve(), args.key_file.resolve())


if __name__ == "__main__":
    main()
