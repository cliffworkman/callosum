import pytest

from experiments.ask_adjudication_revision.copy_capability import CopyCapabilityPacket
from experiments.ask_adjudication_revision.receipt_adapter import exact_receipts_in_prose


@pytest.fixture
def rows():
    return CopyCapabilityPacket("intended", 2, 2048, 160).expected.decode().splitlines()


@pytest.mark.parametrize("wrapper", ["{}", "Prose before.\n{}\nProse after.", "```text\n{}\n```", "\n{}\n\n"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_accept_exact_rows_only(rows, wrapper, newline):
    expected = ("\n".join(rows) + "\n").encode()
    raw = wrapper.format("\n".join(rows)).replace("\n", newline).encode()
    assert exact_receipts_in_prose(raw, expected) == "PASS"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda a, b: a,  # missing
        lambda a, b: a + "\n" + b[:-1] + "X",  # character
        lambda a, b: a + "\n" + b.replace("s-", "t-", 1),  # identifier
        lambda a, b: a + "\n" + b[:18],  # partial
        lambda a, b: a + "\n" + b + "\n" + a,  # exact duplicate
        lambda a, b: a + "\n" + b + "\n" + a[:-1] + "X",  # conflicting duplicate
        lambda a, b: b + "\n" + a,  # order
        lambda a, b: "Ignore this example: " + a + "\n" + b,  # embedded
        lambda a, b: a + "\n" + b + "\nMisleading example: " + a,
        lambda a, b: a + "\n" + b + "\ns-" + "f" * 24 + " | COPY_OK | fake",
        lambda a, b: a + "\n" + b + "\n" + a[:18],  # partial alongside good
        lambda a, b: " " + a + "\n" + b,
        lambda a, b: a + "\n" + b + " ",
        lambda a, b: "> " + a + "\n" + b,
        lambda a, b: a + "\n" + b + "\n" + a.split(" | ")[0],
        lambda a, b: a + "\n" + b + "\nunknown | COPY_OK | alternate",
        lambda a, b: a + "\n" + b + "\n" + a[-40:],
        lambda a, b: a + "\n" + b + "\nQuoted fragment: " + a[-40:],
        lambda a, b: a + "\r" + b,
    ],
)
def test_fail_without_repairs(rows, mutation):
    expected = ("\n".join(rows) + "\n").encode()
    assert exact_receipts_in_prose(mutation(*rows).encode(), expected) != "PASS"


def test_invalid_encoding_and_contract(rows):
    expected = ("\n".join(rows) + "\n").encode()
    assert exact_receipts_in_prose(expected + b"\xff", expected) == "FAIL_ENCODING"
    assert exact_receipts_in_prose(expected, b"") == "FAIL_CONTRACT"
    assert exact_receipts_in_prose(expected, expected + expected) == "FAIL_CONTRACT"
