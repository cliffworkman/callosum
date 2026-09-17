"""Expanded synthetic receipt syntax; v1 remains in receipt_adapter.py unchanged."""

import re

from .reason_envelope import MAX_REASON_BYTES


def exact_receipts_in_prose_v2(raw: bytes, expected: bytes) -> str:
    """V1 rejection logic with only expanded ID/label/reason contract recognition.

    Obtain expected from the verified ReasonEnvelope fixture/manifest, never
    from a model answer. This is not a semantic-response normalizer.
    """
    try:
        text = raw.decode("utf-8").replace("\r\n", "\n")
        contract = expected.decode("utf-8").replace("\r\n", "\n").rstrip("\n").split("\n")
    except UnicodeError:
        return "FAIL_ENCODING"
    pattern = r"s-[0-9a-f]{78} \| UNCERTAIN \| [^|\r\n]+"
    if not contract or any(not re.fullmatch(pattern, row) for row in contract):
        return "FAIL_CONTRACT"
    if any(len(row.split(" | ", 2)[2].encode("utf-8")) > MAX_REASON_BYTES for row in contract):
        return "FAIL_CONTRACT"
    ids = [row.split(" | ")[0] for row in contract]
    if len(set(ids)) != len(ids):
        return "FAIL_CONTRACT"
    # Same fragment and competing-row rejection logic as v1.
    fragments = {row[i : i + 16] for row in contract for i in range(len(row) - 15)}
    found = []
    for line in text.split("\n"):
        if line in contract:
            found.append(line)
        elif (
            "\r" in line
            or "|" in line
            or re.search(
                r"\bCOPY[_ ]OK\b|\b(?:FLAG|UNCERTAIN|NO_FLAG)\b|\bs-[a-z0-9]|[0-9a-fA-F]{16,}", line, re.IGNORECASE
            )
            or any(identifier in line for identifier in ids)
            or any(line[i : i + 16] in fragments for i in range(len(line) - 15))
        ):
            return "FAIL_AMBIGUOUS_RECEIPT"
    return "PASS" if found == contract else "FAIL_ROWS"
