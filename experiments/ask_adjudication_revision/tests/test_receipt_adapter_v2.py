import hashlib
from pathlib import Path

import pytest

from experiments.ask_adjudication_revision.copy_capability import CopyCapabilityPacket
from experiments.ask_adjudication_revision.reason_envelope import ReasonEnvelope
from experiments.ask_adjudication_revision.receipt_adapter import exact_receipts_in_prose
from experiments.ask_adjudication_revision.receipt_adapter_v2 import exact_receipts_in_prose_v2


@pytest.fixture
def expected():
    return ReasonEnvelope().expected


def test_preserved_v1_and_packet_identity(expected):
    source = Path(__file__).parents[1] / "receipt_adapter.py"
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == "d29cca948e992412ed2178050982d82b7a7beec442f4f47e550d507a0aaf3789"
    )
    packet = ReasonEnvelope()
    assert (
        hashlib.sha256(packet.payload).hexdigest() == "409179459b78cabf944aa98a4cb3bafa77eb177cab86888de76f26fbe2f41cc2"
    )
    assert hashlib.sha256(expected).hexdigest() == "b10f3d07afccbc463c2c2a3325c5d5c96d9b78b06a65b42f2002dcc393a74ef0"
    old = CopyCapabilityPacket("intended", 2, 2048, 160).expected
    assert exact_receipts_in_prose(old, old) == "PASS"
    assert exact_receipts_in_prose(expected, expected) == "FAIL_CONTRACT"
    assert exact_receipts_in_prose_v2(old, old) == "FAIL_CONTRACT"


@pytest.mark.parametrize("wrapper", ["{}", "Prose before.\n{}\nProse after.", "```text\n{}\n```", "\n{}\n\n"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_exact_expanded_with_permitted_wrapping(expected, wrapper, newline):
    raw = wrapper.format(expected.decode().rstrip("\n")).replace("\n", newline).encode()
    assert exact_receipts_in_prose_v2(raw, expected) == "PASS"


@pytest.mark.parametrize("size", [79, 80, 81])
def test_id_contract_boundaries(size):
    raw = ("s-" + "a" * (size - 2) + " | UNCERTAIN | bounded reason\n").encode()
    assert exact_receipts_in_prose_v2(raw, raw) == ("PASS" if size == 80 else "FAIL_CONTRACT")


@pytest.mark.parametrize("reason", ["a" * 511, "a" * 512, "a" * 513, "Ω" * 256, "Ω" * 257, ""])
def test_reason_contract_byte_boundaries(reason):
    raw = ("s-" + "a" * 78 + " | UNCERTAIN | " + reason + "\n").encode()
    assert exact_receipts_in_prose_v2(raw, raw) == ("PASS" if 0 < len(reason.encode()) <= 512 else "FAIL_CONTRACT")


@pytest.mark.parametrize("label", ["FLAG", "NO_FLAG", "COPY_OK", "uncertain"])
def test_wrong_contract_label(label, expected):
    raw = expected.replace(b"UNCERTAIN", label.encode())
    assert exact_receipts_in_prose_v2(raw, raw) == "FAIL_CONTRACT"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda a, b: a,  # missing
        lambda a, b: a.replace("s-", "t-", 1) + "\n" + b,
        lambda a, b: a[:79] + a[80:] + "\n" + b,  # 79-character ID
        lambda a, b: a[:80] + "a" + a[80:] + "\n" + b,  # 81-character ID
        lambda a, b: a.replace("UNCERTAIN", "FLAG") + "\n" + b,
        lambda a, b: a[:-1] + "X\n" + b,  # changed reason
        lambda a, b: a + "X\n" + b,  # over-budget reason
        lambda a, b: a + "\n" + b + "\n" + a,
        lambda a, b: a + "\n" + b + "\n" + a[:-1] + "X",
        lambda a, b: b + "\n" + a,
        lambda a, b: a + "\n" + b[:100],
        lambda a, b: a + "\n" + b + "\n" + b[:100],
        lambda a, b: a + "\n" + b + "\ns-" + "f" * 78 + " | UNCERTAIN | fake",
        lambda a, b: "Ignore this example: " + a + "\n" + b,
        lambda a, b: a + "\n" + b + "\nMisleading example: " + a,
        lambda a, b: a + "\n" + b + "\n" + a[-40:],
        lambda a, b: a + "\n" + b + "\nQuoted fragment: " + a[-40:],
        lambda a, b: " " + a + "\n" + b,
        lambda a, b: a + "\n" + b + " ",
        lambda a, b: "> " + a + "\n" + b,
        lambda a, b: a + "\r" + b,
        lambda a, b: a + "\n" + b + "\n" + a.split(" | ")[0],
    ],
)
def test_reject_without_repair(expected, mutation):
    assert exact_receipts_in_prose_v2(mutation(*expected.decode().splitlines()).encode(), expected) != "PASS"


def test_invalid_encoding_empty_or_duplicate_contract(expected):
    assert exact_receipts_in_prose_v2(expected + b"\xff", expected) == "FAIL_ENCODING"
    assert exact_receipts_in_prose_v2(expected, b"") == "FAIL_CONTRACT"
    assert exact_receipts_in_prose_v2(expected, expected + expected) == "FAIL_CONTRACT"
