import copy
import json

import pytest

from experiments.ask_adjudication_revision.capability import (
    HIDDEN_CHECKS,
    CapabilityPacket,
    assess_capability,
    assign_roles,
    capability_template,
    suite,
    synthetic_evidence,
)
from experiments.ask_adjudication_revision.core import ROLES, ROSTER, canonical, semantic_prompt, synthetic_cases
from experiments.ask_adjudication_revision.transport import FORMATS, batches, decode_packet, normalize, render


@pytest.mark.parametrize("format", FORMATS)
def test_lossless_unicode_multiline_and_delimiters(format):
    cases = synthetic_cases(3)
    assert decode_packet(render(cases, format), format) == [c.content() for c in cases]


@pytest.mark.parametrize("format", FORMATS)
def test_batch_envelopes_preserve_whole_objects(format):
    cases = synthetic_cases(5, padding=512)
    result = batches(cases, format=format, max_bytes=3200, max_candidates=2, prompt_bytes=80)
    assert all(len(b) + 80 <= 3200 for b in result)
    decoded = [row for b in result for row in decode_packet(b, format)]
    assert decoded == [c.content() for c in cases]
    with pytest.raises(ValueError, match="OBJECT_EXCEEDS"):
        batches(cases, format=format, max_bytes=50)


def test_cannot_pass_real_content_as_synthetic_case():
    with pytest.raises(ValueError, match="SYNTHETIC_CASES_ONLY"):
        render([{"origin": "SYNTHETIC", "source": "arbitrary external content"}])


def test_capability_packets_are_mechanical_and_size_configurable():
    packets = suite()
    for packet in packets:
        assert packet.check_response(packet.expected) == "PASS"
        assert packet.check_response(packet.expected.replace(b"\n", b"\r\n")) == "PASS"
        assert packet.check_response(packet.expected[:-10]) == "MECHANICAL_FAILURE"
        assert packet.receipt()["expected_response_bytes"] == len(packet.expected)
        assert b"FLAG" not in packet.payload
        assert b"Is there a scientifically" not in packet.payload
    larger = CapabilityPacket("intended", 8, 4096, 320)
    assert len(larger.payload) > len(packets[1].payload)
    assert len(larger.expected) > len(packets[1].expected)
    assert len(packets[2].cases[0].content()["effective_representation"]["annotation"]) == 10


def test_unobserved_surface_never_qualifies():
    packets = suite()
    assert assess_capability(capability_template(*ROSTER[0]), packets) == "UNTESTED"
    record = synthetic_evidence("claude", packets)
    assert assess_capability(record, packets) == "QUALIFIED_SYNTHETIC"
    record["origin"] = "ACTUAL"
    assert assess_capability(record, packets) == "QUALIFIED"
    record["profile_receipts"][0]["status"] = "MECHANICAL_FAILURE"
    assert assess_capability(record, packets) == "TECHNICALLY_UNAVAILABLE"


@pytest.mark.parametrize("surface", HIDDEN_CHECKS)
def test_any_visibility_failure_prevents_blinded_admission(surface):
    record = synthetic_evidence("claude", suite())
    record["hidden_checks"][surface] = False
    assert assess_capability(record, suite()) == "TECHNICALLY_UNAVAILABLE"


def test_role_assignment_occurs_after_qualification_and_preserves_coverage():
    packets = suite()
    records = [synthetic_evidence(sid, packets) for sid, _ in ROSTER]
    records[0]["hidden_checks"]["viewport"] = False
    mapping = assign_roles(list(reversed(records)), packets)
    assert "claude" not in mapping
    assert sorted(role for roles in mapping.values() for role in roles) == sorted(ROLES)
    assert mapping == assign_roles(records, packets)
    assert max(map(len, assign_roles(records[1:4], packets).values())) == 3
    with pytest.raises(ValueError, match="ATTENTIONAL_COVERAGE"):
        assign_roles(records[1:3], packets)
    actual = copy.deepcopy(records)
    for record in actual:
        record["origin"] = "ACTUAL"
    with pytest.raises(ValueError, match="ATTENTIONAL_COVERAGE"):
        assign_roles(actual, packets)
    with pytest.raises(ValueError, match="REAL_STUDY_DISABLED"):
        assign_roles(records, packets, synthetic_only=False)


def test_prompts_share_criterion_and_use_roles_not_model_reputation():
    prompts = [semantic_prompt([role]) for role in ROLES]
    assert len({p.split("Attentional emphasis:")[0] for p in prompts}) == 1
    assert all("NO_FLAG is not certification" in p for p in prompts)


def test_extra_copilot_surface_is_distinct_and_has_a_role():
    packets = suite()
    records = [synthetic_evidence(sid, packets) for sid, _ in ROSTER]
    assignments = assign_roles(records, packets)
    assert "copilot" in assignments and "github_copilot" in assignments
    assert all(assignments.values())
    assert assignments["github_copilot"] == ("skeptical_review",)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"I cannot respond",
        b"unknown | NO_FLAG |",
        b"s1 | NO_FLAG |\ns1 | NO_FLAG |",
        b"s1 | FLAG |",
        b"s1 | YES | ok",
        b"s1 | NO_FLAG | suspicious",
        b"\xff",
        b'[{"candidate_id": "s1", "label": "NO_FLAG"}]',
    ],
)
def test_bad_responses_produce_no_favorable_rows(raw):
    result = normalize(raw, ["s1", "s2"])
    assert result.technical_status != "VALID"
    assert result.rows == ()


def test_missing_and_truncated_are_explicit_and_not_uncertainty_labels():
    assert normalize(b"s1 | NO_FLAG |", ["s1", "s2"]).technical_status == "MISSING_ROWS"
    result = normalize(b"s1 | NO_FLAG |", ["s1"], truncated=True)
    assert result.technical_status == "TRUNCATED" and not result.rows


def test_delimited_and_json_reasons_preserved_without_semantic_repair():
    reason = "fixture | delimiter\nand unicode Ω"
    raw = canonical([{"candidate_id": "s1", "label": "UNCERTAIN", "reason": reason}])
    assert normalize(raw, ["s1"]).rows == (("s1", "UNCERTAIN", reason),)
    plain = b"s1 | FLAG | literal | separator"
    assert normalize(plain, ["s1"]).rows == (("s1", "FLAG", "literal | separator"),)
    fenced = b"```json\n" + raw + b"\n```"
    assert normalize(fenced, ["s1"]).rows == normalize(raw, ["s1"]).rows
    assert json.loads(raw)[0]["reason"] == reason
