from __future__ import annotations

import json
from pathlib import Path

from tools.qualification.overview_battery import (
    PROFILE_DIR,
    freeze_manifest,
    make_packet,
    score_response,
    validate_controls,
)


def test_canned_mechanical_controls_match_preregistration() -> None:
    result = validate_controls()
    assert result["all_mechanical_controls_matched"] is True
    assert len(result["controls"]) == 9


def test_mechanical_score_uses_production_parser_and_reference_contract() -> None:
    valid = score_response(
        '[{"text":"Supported.","claim_indices":[0]},{"text":"Also supported.","claim_indices":[1]}]', 2
    )
    invalid = score_response('[{"text":"Unsupported reference.","claim_indices":[2]}]', 2)
    assert valid.gate_pass is True
    assert valid.requested_sentence_count_met is True
    assert invalid.gate_pass is False
    assert "structural_references" in invalid.errors


def test_bool_references_and_empty_reference_lists_fail() -> None:
    boolean = score_response('[{"text":"No.","claim_indices":[true]}]', 1)
    empty = score_response('[{"text":"No.","claim_indices":[]}]', 1)
    assert boolean.schema_valid is False
    assert empty.schema_valid is False


def test_suspected_truncation_requires_parse_failure_at_output_cap() -> None:
    capped = score_response('[{"text":"cut off"', 1, completion_tokens=256)
    uncapped = score_response('[{"text":"cut off"', 1, completion_tokens=20)
    assert capped.suspected_output_truncation is True
    assert uncapped.suspected_output_truncation is False


def test_fixture_partitions_and_maximal_context_are_frozen_shape() -> None:
    fixtures = json.loads((PROFILE_DIR / "fixtures.json").read_text(encoding="utf-8"))["fixtures"]
    assert sum(item["partition"] == "calibration" for item in fixtures) == 4
    assert sum(item["partition"] == "qualification" for item in fixtures) == 24
    assert sum(item["partition"] == "holdout" for item in fixtures) == 8
    stage_1 = [item for item in fixtures if item.get("stage_1")]
    assert len(stage_1) == 12
    maximal = next(item for item in fixtures if item["fixture_id"] == "Q24")
    assert len(maximal["claims"]) == 40


def test_candidate_landscape_is_bounded_diverse_and_exact() -> None:
    candidates = json.loads((PROFILE_DIR / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    assert len(candidates) == 8
    assert len({item["family"] for item in candidates}) >= 3
    assert all(len(item["revision"]) == 40 and item["filename"].endswith(".gguf") for item in candidates)


def test_freeze_manifest_covers_production_contract_and_assay() -> None:
    frozen = freeze_manifest("a" * 40)
    assert frozen["starting_head"] == "a" * 40
    assert "integrations/gemini/overview.py" in frozen["files"]
    assert "app/backend/summarization/overview_lifecycle.py" in frozen["files"]
    assert len(frozen["aggregate_sha256"]) == 64


def test_blinded_packet_excludes_candidate_and_operational_identity(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "candidate": {"candidate_code": "C99"},
                "records": [
                    {
                        "fixture_id": "Q01",
                        "repetition": 1,
                        "raw_sha256": "a" * 64,
                        "raw_text": '[{"text":"X.","claim_indices":[0]}]',
                        "parsed_sentences": [{"text": "X.", "claim_indices": [0]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    packet = tmp_path / "packet.json"
    mapping = tmp_path / "mapping.json"
    key = tmp_path / "key"
    make_packet([source], packet, mapping, key)
    packet_text = packet.read_text(encoding="utf-8")
    assert "C99" not in packet_text
    assert "latency" not in packet_text
    assert "artifact" not in packet_text
    assert "C99" in mapping.read_text(encoding="utf-8")


def test_receipt_index_withholds_qualification_and_contains_no_private_paths() -> None:
    receipts = json.loads((PROFILE_DIR / "receipt-index.json").read_text(encoding="utf-8"))
    encoded = json.dumps(receipts).lower()
    assert receipts["result"] == "no_qualified_artifact"
    assert len(receipts["results"]) == 8
    assert {item["result"] for item in receipts["results"]} == {
        "not_qualified",
        "runtime_incompatible",
    }
    assert "c:\\users" not in encoded
    assert "/home/" not in encoded
    assert "/tmp/" not in encoded
    assert "credential" not in encoded
    assert "bearer" not in encoded
