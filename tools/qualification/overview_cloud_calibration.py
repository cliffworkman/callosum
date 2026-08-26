"""Developer-only incumbent-cloud calibration for the frozen Overview battery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import secrets
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.qualification import overview_battery  # noqa: E402

PROFILE_DIR = ROOT / ".claude" / "qualification" / "benchmark-calibration-v1"
FREEZE_PATH = PROFILE_DIR / "freeze.json"
PREREG_PATH = PROFILE_DIR / "preregistration.json"
CALIBRATION_INPUTS = (
    ".claude/qualification/benchmark-calibration-v1/preregistration.json",
    ".claude/qualification/benchmark-calibration-v1/protocol-amendment-1.json",
    ".claude/qualification/benchmark-calibration-v1/exploratory-codebook.md",
    ".claude/qualification/benchmark-calibration-v1/cost-receipt.schema.json",
    ".claude/qualification/benchmark-calibration-v1/public-benchmark-card.template.json",
    "tools/qualification/overview_cloud_calibration.py",
)
APPROVED_KEY_NAMES = ("GOOGLE_API_KEY_1", "GOOGLE_API_KEY_2", "GOOGLE_API_KEY_3")
DEFAULT_COST_CEILING_USD = 2.0
MAX_RETRIES = 12
MAX_RETRY_PER_REQUEST = 1
MODEL = "gemini-2.5-flash-lite"
INPUT_PRICE_PER_MILLION = 0.10
OUTPUT_PRICE_PER_MILLION = 0.40
MAX_OUTPUT_TOKENS = 256
MIN_REQUEST_INTERVAL_SECONDS = 6.5


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def freeze_manifest(starting_head: str) -> dict[str, object]:
    base = overview_battery.verify_freeze()
    files = {relative: _sha256(ROOT / relative) for relative in CALIBRATION_INPUTS}
    return {
        "schema_version": 1,
        "calibration_profile": "benchmark-calibration-v1",
        "starting_head": starting_head,
        "frozen_before_provider_output": True,
        "base_battery_aggregate_sha256": base["aggregate_sha256"],
        "files": files,
        "aggregate_sha256": _canonical_sha256(files),
    }


def verify_freeze() -> dict[str, object]:
    base = overview_battery.verify_freeze()
    frozen = _json(FREEZE_PATH)
    expected = frozen.get("files")
    if not isinstance(expected, dict):
        raise RuntimeError("invalid calibration freeze manifest")
    actual = {relative: _sha256(ROOT / relative) for relative in expected}
    if actual != expected or _canonical_sha256(actual) != frozen.get("aggregate_sha256"):
        raise RuntimeError("calibration inputs differ from their frozen manifest")
    if frozen.get("base_battery_aggregate_sha256") != base.get("aggregate_sha256"):
        raise RuntimeError("historical qualification battery identity changed")
    return frozen


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[:1] == value[-1:] and value[0] in "\"'":
            value = value[1:-1]
        values[name.strip()] = value
    return values


def approved_keys(env_path: Path) -> list[str]:
    values = _parse_env(env_path)
    keys = [values.get(name, "").strip() for name in APPROVED_KEY_NAMES]
    if not all(keys):
        raise RuntimeError("all three approved Gemini benchmark credential slots must be populated")
    if len(set(keys)) != len(keys):
        raise RuntimeError("Gemini benchmark credential slots must contain distinct values")
    return keys


def _redacted_error_type(exc: Exception) -> str:
    return type(exc).__name__[:80]


def _is_quota_error(exc: Exception) -> bool:
    lowered = str(exc).lower()
    return any(marker in lowered for marker in ("429", "resource_exhausted", "quota", "rate limit"))


class _KeyPool:
    def __init__(self, keys: list[str], initial_retries: int = 0) -> None:
        self._keys = keys
        self._index = 0
        self.retries = initial_retries
        self.initial_retries = initial_retries
        self._last_request_at: dict[int, float] = {}

    @property
    def current(self) -> str:
        return self._keys[self._index]

    def rotate(self) -> None:
        self._index = (self._index + 1) % len(self._keys)
        self.retries += 1

    def wait_for_slot(self) -> None:
        previous = self._last_request_at.get(self._index)
        if previous is not None:
            remaining = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - previous)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[self._index] = time.monotonic()


def _fixtures(track: str) -> list[dict[str, object]]:
    fixtures = _json(overview_battery.PROFILE_DIR / "fixtures.json")["fixtures"]
    if track == "A":
        return [item for item in fixtures if item.get("partition") == "qualification" and item.get("stage_1")]
    if track == "B":
        return [item for item in fixtures if item.get("partition") == "qualification"]
    raise RuntimeError("calibration runner permits only Track A or Track B; holdout access is forbidden")


def _repetitions(track: str) -> int:
    return 2 if track == "A" else 3


def _generation_config():  # type: ignore[no-untyped-def]
    from google.genai import types

    return types.GenerateContentConfig(
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.0,
        seed=42,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def _usage_value(meta: object, name: str) -> int | None:
    value = getattr(meta, name, None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _usage(meta: object | None) -> dict[str, int | None]:
    return {
        "input_tokens": _usage_value(meta, "prompt_token_count"),
        "output_tokens": _usage_value(meta, "candidates_token_count"),
        "cached_input_tokens": _usage_value(meta, "cached_content_token_count"),
        "reasoning_tokens": _usage_value(meta, "thoughts_token_count"),
        "total_tokens": _usage_value(meta, "total_token_count"),
    }


def _cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * INPUT_PRICE_PER_MILLION + output_tokens * OUTPUT_PRICE_PER_MILLION) / 1_000_000


def active_ceiling() -> float:
    raw = os.getenv("CALLOSUM_BENCHMARK_MAX_USD", "").strip()
    value = float(raw) if raw else DEFAULT_COST_CEILING_USD
    if value <= 0:
        raise RuntimeError("benchmark cost ceiling must be positive")
    return value


def _count_prompt_tokens(client, prompt: str) -> int:  # type: ignore[no-untyped-def]
    response = client.models.count_tokens(model=MODEL, contents=prompt)
    count = getattr(response, "total_tokens", None)
    if not isinstance(count, int) or count < 1:
        raise RuntimeError("Gemini count_tokens returned no usable token count")
    return count


def preflight(env_path: Path, output: Path) -> dict[str, object]:
    from app.backend.provider_runtime import ProviderClientRuntime
    from integrations.gemini.overview import _prompt

    frozen = verify_freeze()
    keys = approved_keys(env_path)
    runtime = ProviderClientRuntime()
    counts: dict[str, int] = {}
    try:
        for fixture in _fixtures("B"):
            prompt = _prompt(fixture["claims"])
            counts[fixture["fixture_id"]] = runtime.run_gemini(
                api_key=keys[0], operation=lambda client, p=prompt: _count_prompt_tokens(client, p)
            )
    finally:
        runtime.close()
    track_a_input = sum(counts[item["fixture_id"]] * 2 for item in _fixtures("A"))
    track_b_input = sum(counts[item["fixture_id"]] * 3 for item in _fixtures("B"))
    planned_input = track_a_input + track_b_input
    planned_output_max = 96 * MAX_OUTPUT_TOKENS
    retry_input_max = max(counts.values()) * MAX_RETRIES
    retry_output_max = MAX_OUTPUT_TOKENS * MAX_RETRIES
    conservative = _cost(planned_input + retry_input_max, planned_output_max + retry_output_max)
    receipt: dict[str, object] = {
        "schema_version": 1,
        "calibration_profile": "benchmark-calibration-v1",
        "calibration_aggregate_sha256": frozen["aggregate_sha256"],
        "provider": "gemini",
        "requested_model": MODEL,
        "token_count_method": "Gemini count_tokens on each frozen production Overview prompt",
        "fixture_input_tokens": counts,
        "track_a_input_tokens": track_a_input,
        "track_b_input_tokens": track_b_input,
        "planned_input_tokens": planned_input,
        "planned_maximum_output_tokens": planned_output_max,
        "planned_requests": 96,
        "maximum_retry_requests": MAX_RETRIES,
        "maximum_requests": 108,
        "conservative_maximum_input_tokens": planned_input + retry_input_max,
        "conservative_maximum_output_tokens": planned_output_max + retry_output_max,
        "input_price_per_million_usd": INPUT_PRICE_PER_MILLION,
        "output_price_per_million_usd": OUTPUT_PRICE_PER_MILLION,
        "conservative_maximum_cost_usd": conservative,
        "active_ceiling_usd": active_ceiling(),
        "allowed": conservative <= active_ceiling(),
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if not receipt["allowed"]:
        raise RuntimeError("COST PREFLIGHT STOP: conservative projected cost exceeds the active ceiling")
    return receipt


def _generate(runtime, pool: _KeyPool, prompt: str) -> tuple[object | None, list[dict[str, object]]]:  # type: ignore[no-untyped-def]
    attempts: list[dict[str, object]] = []
    for attempt in range(MAX_RETRY_PER_REQUEST + 1):
        pool.wait_for_slot()
        started = time.perf_counter()
        try:
            response = runtime.run_gemini(
                api_key=pool.current,
                operation=lambda client: client.models.generate_content(
                    model=MODEL, contents=prompt, config=_generation_config()
                ),
            )
            attempts.append(
                {
                    "success": True,
                    "elapsed_seconds": time.perf_counter() - started,
                    "usage": _usage(getattr(response, "usage_metadata", None)),
                }
            )
            return response, attempts
        except Exception as exc:  # noqa: BLE001 - provider failure is measured, never hidden
            quota = _is_quota_error(exc)
            attempts.append(
                {
                    "success": False,
                    "elapsed_seconds": time.perf_counter() - started,
                    "error_type": _redacted_error_type(exc),
                    "usage": _usage(None),
                }
            )
            if not quota or attempt >= MAX_RETRY_PER_REQUEST or pool.retries >= MAX_RETRIES:
                return None, attempts
            pool.rotate()
    raise AssertionError("bounded generation loop exhausted unexpectedly")


def execute(track: str, env_path: Path, preflight_path: Path, output: Path, track_a_path: Path | None) -> None:
    from app.backend.provider_runtime import ProviderClientRuntime
    from app.backend.summarization.overview import validated_overview_items
    from integrations.gemini.overview import _parse_overview_response, _prompt

    frozen = verify_freeze()
    preflight_receipt = _json(preflight_path)
    if not preflight_receipt.get("allowed") or preflight_receipt.get("calibration_aggregate_sha256") != frozen.get(
        "aggregate_sha256"
    ):
        raise RuntimeError("valid matching cost preflight is required before paid execution")
    if float(preflight_receipt["conservative_maximum_cost_usd"]) > active_ceiling():
        raise RuntimeError("COST PREFLIGHT STOP: active ceiling is below the frozen preflight")
    track_a_sha: str | None = None
    prior_retries = 0
    if track == "B":
        if track_a_path is None or not track_a_path.is_file():
            raise RuntimeError("Track B requires an immutable Track A receipt")
        track_a = _json(track_a_path)
        if track_a.get("track") != "A" or track_a.get("calibration_aggregate_sha256") != frozen.get("aggregate_sha256"):
            raise RuntimeError("Track B received an invalid Track A receipt")
        track_a_sha = _sha256(track_a_path)
        prior_retries = int(track_a.get("study_retry_count", track_a.get("retry_count", 0)))
        if prior_retries > MAX_RETRIES:
            raise RuntimeError("Track A already exceeded the study-wide retry budget")

    keys = approved_keys(env_path)
    pool = _KeyPool(keys, initial_retries=prior_retries)
    runtime = ProviderClientRuntime()
    records: list[dict[str, object]] = []
    try:
        for fixture in _fixtures(track):
            for repetition in range(1, _repetitions(track) + 1):
                prompt = _prompt(fixture["claims"])
                response, attempts = _generate(runtime, pool, prompt)
                raw_text = str(getattr(response, "text", "") or "") if response is not None else ""
                final_usage = attempts[-1]["usage"] if attempts else _usage(None)
                completion_tokens = final_usage.get("output_tokens") if isinstance(final_usage, dict) else None
                score = (
                    overview_battery.score_response(raw_text, len(fixture["claims"]), completion_tokens)
                    if response is not None
                    else None
                )
                parsed = []
                validated = []
                if score is not None and score.parser_success:
                    parsed = _parse_overview_response(raw_text)
                    validated = validated_overview_items(parsed, list(range(len(fixture["claims"]))))
                records.append(
                    {
                        "fixture_id": fixture["fixture_id"],
                        "repetition": repetition,
                        "attempts": attempts,
                        "http_success": response is not None,
                        "provider_returned_model_version": (
                            str(getattr(response, "model_version", "") or "") or None if response is not None else None
                        ),
                        "usage": final_usage,
                        "raw_text": raw_text,
                        "raw_sha256": hashlib.sha256(raw_text.encode()).hexdigest(),
                        "mechanical": asdict(score) if score is not None else None,
                        "parsed_sentences": [asdict(item) for item in parsed],
                        "validated_items": validated,
                    }
                )
                payload = _execution_payload(
                    frozen,
                    track,
                    records,
                    pool.retries,
                    pool.initial_retries,
                    track_a_sha,
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                temporary = output.with_suffix(output.suffix + ".tmp")
                temporary.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
                temporary.replace(output)
    finally:
        runtime.close()


def _execution_payload(
    frozen: dict[str, object],
    track: str,
    records: list[dict[str, object]],
    retries: int,
    prior_retries: int,
    track_a_sha: str | None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "calibration_profile": "benchmark-calibration-v1",
        "calibration_aggregate_sha256": frozen["aggregate_sha256"],
        "battery_aggregate_sha256": frozen["base_battery_aggregate_sha256"],
        "provider": "gemini",
        "requested_model": MODEL,
        "provider_identity_kind": "time_bound_hosted_alias",
        "track": track,
        "evidence_class": "qualification_gate" if track == "A" else "descriptive_calibration",
        "track_a_receipt_sha256": track_a_sha,
        "generation": {
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.0,
            "seed": 42,
            "thinking_budget_tokens": 0,
        },
        "prior_retry_count": prior_retries,
        "retry_count": retries - prior_retries,
        "study_retry_count": retries,
        "records": records,
    }


def _gate_pass(score: dict[str, object] | None) -> bool:
    return (
        bool(score)
        and all(
            bool(score[key])
            for key in (
                "json_parse",
                "array_root",
                "schema_valid",
                "structural_references_valid",
                "parser_success",
                "usable_after_reference_filter",
            )
        )
        and not bool(score["suspected_output_truncation"])
    )


def summarize_track(payload: dict[str, object]) -> dict[str, object]:
    records = payload["records"]
    usable = [row for row in records if row.get("mechanical") and row["mechanical"]["usable_after_reference_filter"]]
    structural_failures = sum(
        bool(row.get("mechanical")) and not row["mechanical"]["structural_references_valid"] for row in records
    )
    sentence_met = sum(
        bool(row.get("mechanical")) and row["mechanical"]["requested_sentence_count_met"] for row in usable
    )
    fixture_usable: dict[str, int] = {}
    for row in records:
        if row in usable:
            fixture_usable[row["fixture_id"]] = fixture_usable.get(row["fixture_id"], 0) + 1
    metrics = {
        "requests": len(records),
        "http_success": sum(bool(row["http_success"]) for row in records),
        "mechanical_gate_pass": sum(_gate_pass(row.get("mechanical")) for row in records),
        "usable": len(usable),
        "structural_reference_failures": structural_failures,
        "sentence_adherence": sentence_met,
        "sentence_adherence_denominator": len(usable),
        "suspected_truncation": sum(
            bool(row.get("mechanical")) and row["mechanical"]["suspected_output_truncation"] for row in records
        ),
    }
    if payload["track"] == "A":
        metrics["passes_frozen_stage1"] = (
            metrics["http_success"] >= 23
            and metrics["usable"] >= 23
            and structural_failures == 0
            and all(fixture_usable.get(item["fixture_id"], 0) >= 1 for item in _fixtures("A"))
            and (sentence_met / len(usable) if usable else 0) >= 0.9
        )
    return metrics


def _token_totals(payloads: list[dict[str, object]]) -> dict[str, object]:
    requests = retries = input_tokens = output_tokens = cached = reasoning = missing = 0
    for payload in payloads:
        for record in payload["records"]:
            requests += 1
            retries += max(0, len(record.get("attempts") or []) - 1)
            for attempt in record.get("attempts") or []:
                usage = attempt.get("usage") or {}
                inp, out = usage.get("input_tokens"), usage.get("output_tokens")
                thought = usage.get("reasoning_tokens")
                if inp is None or out is None:
                    missing += 1
                input_tokens += int(inp or 0)
                output_tokens += int(out or 0)
                cached += int(usage.get("cached_input_tokens") or 0)
                reasoning += int(thought or 0)
    billable_output = output_tokens + reasoning
    return {
        "requests": requests,
        "retries": retries,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached,
        "reasoning_tokens": reasoning,
        "usage_missing_attempts": missing,
        "estimated_cost_usd": _cost(input_tokens, billable_output),
    }


def aggregate(track_a_path: Path, track_b_path: Path, output: Path) -> dict[str, object]:
    frozen = verify_freeze()
    track_a, track_b = _json(track_a_path), _json(track_b_path)
    a_metrics, b_metrics = summarize_track(track_a), summarize_track(track_b)
    if track_b.get("track_a_receipt_sha256") != _sha256(track_a_path):
        raise RuntimeError("Track B is not bound to the supplied Track A receipt")
    model_versions = sorted(
        {
            row["provider_returned_model_version"]
            for payload in (track_a, track_b)
            for row in payload["records"]
            if row.get("provider_returned_model_version")
        }
    )
    receipt: dict[str, object] = {
        "schema_version": 1,
        "calibration_profile": "benchmark-calibration-v1",
        "starting_head": "4cb610eb44d16ce7792f7e169946ebbacc9dbb22",
        "test_timestamp_utc": datetime.now(UTC).isoformat(),
        "battery_aggregate_sha256": frozen["base_battery_aggregate_sha256"],
        "calibration_aggregate_sha256": frozen["aggregate_sha256"],
        "provider": "gemini",
        "requested_model": MODEL,
        "provider_returned_model_versions": model_versions or None,
        "provider_identity_limitation": "Hosted serving identity is time-bound and not equivalent to an artifact digest.",
        "generation": track_a["generation"],
        "track_a": {
            "metrics": a_metrics,
            "verdict": (
                "passes_synthesis_overview_v1_stage1_mechanics"
                if a_metrics["passes_frozen_stage1"]
                else "would_not_qualify_under_synthesis_overview_v1"
            ),
            "raw_receipt_sha256": _sha256(track_a_path),
        },
        "track_b": {
            "metrics": b_metrics,
            "evidence_class": "descriptive_calibration",
            "raw_receipt_sha256": _sha256(track_b_path),
        },
        "token_cost": _token_totals([track_a, track_b]),
        "challenge_holdout": {"opened": False},
        "human_review": {"status": "packet_pending_generation", "authority": "human"},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def _adjudication_fields() -> dict[str, object]:
    return {
        "supported_factual_content": None,
        "semantic_reference_adequacy": None,
        "unsupported_fact": None,
        "unsupported_fact_category": [],
        "inferential_upgrade": None,
        "inferential_upgrade_category": [],
        "critical_omission": None,
        "framing_distortion": None,
        "overall_scientific_integrity": None,
        "worst_severity_0_to_4": None,
        "detectability_A_to_D": None,
        "verification_burden_0_to_4": None,
        "practical_utility": None,
        "notes": "",
    }


def make_packet(gemini_path: Path, local_path: Path, packet_path: Path, decode_path: Path) -> dict[str, object]:
    gemini, local = _json(gemini_path), _json(local_path)
    if gemini.get("track") != "B" or gemini.get("evidence_class") != "descriptive_calibration":
        raise RuntimeError("Gemini packet source must be Track B descriptive calibration")
    if local.get("candidate", {}).get("candidate_code") != "C03" or local.get("stage") != "stage2":
        raise RuntimeError("local comparator must be the legitimate Phase 4 C03 Stage 2 receipt")
    if local.get("battery_aggregate_sha256") != overview_battery.verify_freeze().get("aggregate_sha256"):
        raise RuntimeError("local comparator battery identity differs")

    fixtures = {item["fixture_id"]: item for item in _json(overview_battery.PROFILE_DIR / "fixtures.json")["fixtures"]}
    controls = _json(overview_battery.PROFILE_DIR / "controls.json")["controls"]
    opaque_codes = {"incumbent": f"K-{secrets.token_hex(4)}", "local": f"K-{secrets.token_hex(4)}"}
    while opaque_codes["incumbent"] == opaque_codes["local"]:
        opaque_codes["local"] = f"K-{secrets.token_hex(4)}"
    control_entries = []
    control_decode = {}
    for control in controls:
        opaque = f"S-{secrets.token_hex(6)}"
        control_entries.append(
            {
                "control_response_id": opaque,
                "verified_claims": [{"index": i, "claim": claim} for i, claim in enumerate(control["claims"])],
                "raw_overview": control["raw_output"],
                "adjudication": _adjudication_fields(),
            }
        )
        control_decode[opaque] = {
            "control_id": control["control_id"],
            "expected_semantic": control["expected_semantic"],
        }
    random.SystemRandom().shuffle(control_entries)

    responses = []
    response_decode = {}
    for source_name, payload in (("incumbent", gemini), ("local", local)):
        for record in payload["records"]:
            opaque = f"R-{secrets.token_hex(8)}"
            fixture = fixtures[record["fixture_id"]]
            responses.append(
                {
                    "candidate_code": opaque_codes[source_name],
                    "response_id": opaque,
                    "verified_claims": [{"index": i, "claim": claim} for i, claim in enumerate(fixture["claims"])],
                    "raw_overview": record["raw_text"],
                    "parsed_sentences": record["parsed_sentences"],
                    "adjudication": _adjudication_fields(),
                }
            )
            response_decode[opaque] = {
                "source": source_name,
                "candidate_code": "gemini-incumbent" if source_name == "incumbent" else "C03",
                "fixture_id": record["fixture_id"],
                "repetition": record["repetition"],
                "evidentiary_status": "calibration_only",
            }
    random.SystemRandom().shuffle(responses)
    packet = {
        "schema_version": 1,
        "calibration_profile": "benchmark-calibration-v1",
        "review_order": "Complete semantic_controls before candidate_responses. Do not decode identities first.",
        "semantic_controls": control_entries,
        "candidate_responses": responses,
    }
    decode = {
        "schema_version": 1,
        "keep_separate_from_review_packet": True,
        "candidate_codes": {
            opaque_codes["incumbent"]: "gemini-incumbent-time-bound",
            opaque_codes["local"]: "Phase4-C03-stage2-not-qualified-comparator",
        },
        "controls": control_decode,
        "responses": response_decode,
    }
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    decode_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, ensure_ascii=True, indent=2), encoding="utf-8")
    decode_path.write_text(json.dumps(decode, ensure_ascii=True, indent=2), encoding="utf-8")
    return {
        "candidate_count": 2,
        "response_count": len(responses),
        "semantic_control_count": len(control_entries),
        "packet_sha256": _sha256(packet_path),
        "decode_sha256": _sha256(decode_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--starting-head", required=True)
    commands.add_parser("verify")
    pre = commands.add_parser("preflight")
    pre.add_argument("--env", type=Path, required=True)
    pre.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("execute")
    run.add_argument("--track", choices=("A", "B"), required=True)
    run.add_argument("--env", type=Path, required=True)
    run.add_argument("--preflight", type=Path, required=True)
    run.add_argument("--track-a", type=Path)
    run.add_argument("--output", type=Path, required=True)
    agg = commands.add_parser("aggregate")
    agg.add_argument("--track-a", type=Path, required=True)
    agg.add_argument("--track-b", type=Path, required=True)
    agg.add_argument("--output", type=Path, required=True)
    packet = commands.add_parser("packet")
    packet.add_argument("--gemini", type=Path, required=True)
    packet.add_argument("--local", type=Path, required=True)
    packet.add_argument("--packet", type=Path, required=True)
    packet.add_argument("--decode", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        FREEZE_PATH.write_text(json.dumps(freeze_manifest(args.starting_head), indent=2) + "\n", encoding="utf-8")
    elif args.command == "verify":
        print(json.dumps(verify_freeze(), indent=2))
    elif args.command == "preflight":
        print(json.dumps(preflight(args.env.resolve(), args.output.resolve()), indent=2))
    elif args.command == "execute":
        execute(
            args.track,
            args.env.resolve(),
            args.preflight.resolve(),
            args.output.resolve(),
            args.track_a.resolve() if args.track_a else None,
        )
    elif args.command == "aggregate":
        print(json.dumps(aggregate(args.track_a.resolve(), args.track_b.resolve(), args.output.resolve()), indent=2))
    elif args.command == "packet":
        print(
            json.dumps(
                make_packet(args.gemini.resolve(), args.local.resolve(), args.packet.resolve(), args.decode.resolve()),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
