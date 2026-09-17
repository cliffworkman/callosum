from experiments.ask_adjudication_revision.reason_envelope import (
    MAX_INPUT_BYTES,
    MAX_RESPONSE_BYTES,
    PROMPT_RESERVE,
    WRAPPER,
    ReasonEnvelope,
)


def test_bounds_and_exact_contract():
    packet = ReasonEnvelope()
    receipt = packet.receipt()
    assert len(packet.payload) + len(WRAPPER.encode()) <= MAX_INPUT_BYTES
    assert len(packet.expected) == MAX_RESPONSE_BYTES
    assert receipt["current_shared_prompt_all_roles_bytes"] <= PROMPT_RESERVE
    assert packet.payload.count(b"RECEIPT_TO_COPY\n") == 2
    for row in packet.expected.decode().splitlines():
        identifier, label, reason = row.split(" | ")
        assert len(identifier) == 80 and label == "UNCERTAIN" and len(reason.encode()) == 512
        assert packet.payload.count(row.encode()) == 1
    assert packet.check_response(packet.expected) == "PASS"
    assert packet.check_response(packet.expected.replace(b"\n", b"\r\n")) == "PASS"


def test_no_favorable_partial_response_or_repair():
    packet = ReasonEnvelope()
    for raw in (
        packet.expected[:-5],
        packet.expected.replace(b"END", b"BAD", 1),
        packet.expected + packet.expected,
        packet.expected.replace(b"UNCERTAIN", b"FLAG", 1),
        b"\n".join(reversed(packet.expected.splitlines())),
        b"Prose\n" + packet.expected,
    ):
        assert packet.check_response(raw, empty_lines=True) != "PASS"
    blank = packet.expected.replace(b"\n", b"\n\n")
    assert packet.check_response(blank) != "PASS"
    assert packet.check_response(blank, empty_lines=True) == "PASS"
    assert packet.check_response(packet.expected.replace(b"\n", b"\n \n"), empty_lines=True) != "PASS"
