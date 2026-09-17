import copy

import pytest

from experiments.ask_adjudication_revision.capability import suite
from experiments.ask_adjudication_revision.copy_capability import copy_suite, packet_from_receipt
from experiments.ask_adjudication_revision.core import sha


def test_archived_v1_identity_is_unchanged_and_both_versions_round_trip():
    old = suite()[0]
    assert sha(old.payload) == "f5f86dd636e8dc9d43f752f2bd5c579c2a48793a597208e22296271701b247f2"
    for packet in (old, *copy_suite()):
        restored = packet_from_receipt(packet.receipt())
        assert restored.payload == packet.payload
        assert restored.check_response(packet.expected) == "PASS"


def test_literal_fixture_supplies_every_response_and_rejects_missing_duplicate_or_mutated_rows():
    packet = copy_suite()[0]
    rows = packet.expected.splitlines()
    assert len(rows) == 8
    assert all(row in packet.payload for row in rows)
    assert len(packet.payload) > 37000
    assert 1600 <= len(packet.expected) < 1800
    for raw in (b"\n".join(rows[:-1]), b"\n".join(rows + rows[:1]), packet.expected.replace(b"END", b"EN", 1)):
        assert packet.check_response(raw) == "MECHANICAL_FAILURE"
    damaged = copy.deepcopy(packet.receipt())
    damaged["fixture_version"] = 3
    with pytest.raises(ValueError, match="UNKNOWN_FIXTURE_VERSION"):
        packet_from_receipt(damaged)
