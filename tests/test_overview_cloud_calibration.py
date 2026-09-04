from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.qualification import overview_battery
from tools.qualification import overview_cloud_calibration as calibration


def test_historical_battery_remains_frozen() -> None:
    # Re-frozen 2026-09-01 (inc 557): app/backend/llm/providers.py -- one of the battery's frozen inputs --
    # changed for the first time since the 2026-08-25 freeze, as part of an unrelated privacy hardening fix
    # (forcing trust_env=False for loopback destinations; removing 0.0.0.0 from the loopback allowlist).
    # Confirmed behaviorally neutral for what this study tested: managed_local's own http_trust_env was
    # already hardcoded False before and after, and the managed target is hard-pinned to a literal 127.0.0.1,
    # never 0.0.0.0 -- so the qualification's already-recorded null result remains reproducible against the
    # re-frozen code. See .claude/docs/increment-notes/INCREMENT-557-NOTES.md.
    # inc 575: providers.py moved again, fixing a truncated model answer that surfaced to a real user as a
    # raw JSONDecodeError. Confirmed behaviourally neutral for what THIS study tested: the additions read the
    # finish_reason/stop_reason the provider already returned (no request field changes), and the one real
    # generation-setting change (_MAX_TOKENS 2048 -> 4096) governs only the Anthropic `messages` wire, which
    # none of this battery's local GGUF candidates use -- their Overview cap is the unchanged 256. The
    # recorded null result stays reproducible. See INCREMENT-575-NOTES.md and the profile README.
    assert overview_battery.verify_freeze()["aggregate_sha256"] == (
        "3591ed8dcd424fa0dbbc2b8b71f9858adb6da9c81ae90a6996aef1588d6a6bc3"
    )


def test_calibration_manifest_is_deterministic_and_separate() -> None:
    first = calibration.freeze_manifest("a" * 40)
    second = calibration.freeze_manifest("a" * 40)
    assert first == second
    assert first["base_battery_aggregate_sha256"] == overview_battery.verify_freeze()["aggregate_sha256"]
    assert "fixtures.json" not in first["files"]


def test_runner_exposes_only_frozen_qualification_tracks() -> None:
    assert len(calibration._fixtures("A")) == 12
    assert len(calibration._fixtures("B")) == 24
    with pytest.raises(RuntimeError, match="holdout access is forbidden"):
        calibration._fixtures("holdout")


def test_production_prompt_and_parser_drive_mechanical_score() -> None:
    from integrations.gemini.overview import _parse_overview_response, _prompt

    prompt = _prompt(["Verified one.", "Verified two."])
    raw = '[{"text":"One.","claim_indices":[0]},{"text":"Two.","claim_indices":[1]}]'
    assert "NUMBERED claims" in prompt
    assert len(_parse_overview_response(raw)) == 2
    assert overview_battery.score_response(raw, 2).gate_pass is True


def test_track_a_gate_is_literal_and_track_b_has_no_qualification_verdict() -> None:
    good = {
        "json_parse": True,
        "array_root": True,
        "schema_valid": True,
        "structural_references_valid": True,
        "parser_success": True,
        "usable_after_reference_filter": True,
        "sentence_count": 2,
        "requested_sentence_count_met": True,
        "suspected_output_truncation": False,
        "errors": [],
    }
    a_records = [
        {"fixture_id": fixture["fixture_id"], "http_success": True, "mechanical": dict(good)}
        for fixture in calibration._fixtures("A")
        for _ in range(2)
    ]
    a_records[0]["mechanical"]["requested_sentence_count_met"] = False
    a_records[1]["mechanical"]["requested_sentence_count_met"] = False
    a_records[2]["mechanical"]["requested_sentence_count_met"] = False
    assert calibration.summarize_track({"track": "A", "records": a_records})["passes_frozen_stage1"] is False
    b = calibration.summarize_track({"track": "B", "records": a_records})
    assert "passes_frozen_stage1" not in b


def test_cost_ceiling_blocks_before_key_or_provider_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "allowed": True,
                "calibration_aggregate_sha256": calibration.verify_freeze()["aggregate_sha256"],
                "conservative_maximum_cost_usd": 2.01,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CALLOSUM_BENCHMARK_MAX_USD", "2.00")
    with pytest.raises(RuntimeError, match="COST PREFLIGHT STOP"):
        calibration.execute("A", tmp_path / "missing.env", preflight, tmp_path / "out.json", None)
    assert not (tmp_path / "out.json").exists()


def test_approved_env_keys_are_required_but_never_returned(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    values = ["secret-alpha", "secret-beta", "secret-gamma"]
    env.write_text(
        "\n".join(f"{name}={value}" for name, value in zip(calibration.APPROVED_KEY_NAMES, values, strict=True)),
        encoding="utf-8",
    )
    assert calibration.approved_keys(env) == values
    assert all(value not in json.dumps(calibration.freeze_manifest("b" * 40)) for value in values)


def test_token_accounting_includes_retries_and_missing_usage() -> None:
    payload = {
        "records": [
            {
                "attempts": [
                    {"usage": {"input_tokens": None, "output_tokens": None}},
                    {
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 20,
                            "cached_input_tokens": 5,
                            "reasoning_tokens": 3,
                        }
                    },
                ]
            }
        ]
    }
    totals = calibration._token_totals([payload])
    assert totals["requests"] == 1
    assert totals["retries"] == 1
    assert totals["input_tokens"] == 100
    assert totals["output_tokens"] == 20
    assert totals["reasoning_tokens"] == 3
    assert totals["usage_missing_attempts"] == 1


def test_retry_budget_carries_from_track_a_and_pacing_is_per_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = iter((10.0, 11.0, 16.5, 16.5))
    sleeps: list[float] = []
    monkeypatch.setattr(calibration.time, "monotonic", lambda: next(now))
    monkeypatch.setattr(calibration.time, "sleep", sleeps.append)
    pool = calibration._KeyPool(["one", "two"], initial_retries=2)
    pool.wait_for_slot()
    pool.wait_for_slot()
    assert sleeps == [pytest.approx(5.5)]
    pool.rotate()
    pool.wait_for_slot()
    assert pool.initial_retries == 2
    assert pool.retries == 3


def _packet_source(source: str) -> dict:
    record = {
        "fixture_id": "Q01",
        "repetition": 1,
        "raw_text": '[{"text":"Supported.","claim_indices":[0]}]',
        "parsed_sentences": [{"text": "Supported.", "claim_indices": [0]}],
    }
    if source == "gemini":
        return {"track": "B", "evidence_class": "descriptive_calibration", "records": [record]}
    return {
        "candidate": {"candidate_code": "C03"},
        "stage": "stage2",
        "battery_aggregate_sha256": overview_battery.verify_freeze()["aggregate_sha256"],
        "records": [record],
    }


def test_blinded_packet_is_random_opaque_and_decode_is_separate(tmp_path: Path) -> None:
    gemini, local = tmp_path / "gemini.json", tmp_path / "local.json"
    gemini.write_text(json.dumps(_packet_source("gemini")), encoding="utf-8")
    local.write_text(json.dumps(_packet_source("local")), encoding="utf-8")
    packets = []
    for suffix in ("one", "two"):
        packet, decode = tmp_path / f"packet-{suffix}.json", tmp_path / f"decode-{suffix}.json"
        calibration.make_packet(gemini, local, packet, decode)
        packet_text = packet.read_text(encoding="utf-8")
        decode_text = decode.read_text(encoding="utf-8")
        assert "gemini" not in packet_text.lower()
        assert "C03" not in packet_text
        assert "provider" not in packet_text.lower()
        assert "gemini-incumbent" in decode_text
        assert "calibration_only" in decode_text
        packets.append(packet_text)
    assert packets[0] != packets[1]


def test_public_card_has_no_cloud_hardware_claim_or_secret_field() -> None:
    card = json.loads((calibration.PROFILE_DIR / "public-benchmark-card.template.json").read_text(encoding="utf-8"))
    encoded = json.dumps(card).lower()
    assert card["provider_compute"] == "undisclosed/unknown"
    assert "api_key" not in encoded
    assert "credential" not in encoded
    assert "c:\\users" not in encoded
    assert "/home/" not in encoded
