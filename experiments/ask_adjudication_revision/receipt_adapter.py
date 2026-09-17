"""Exact synthetic receipt extraction; never a semantic-response normalizer."""

import re


def exact_receipts_in_prose(raw: bytes, expected: bytes) -> str:
    """Ignore only non-receipt prose. Fail closed on ambiguous receipt syntax.

    Only UTF-8 and CRLF -> LF normalization are accepted. Qualifying rows must
    occupy an entire line. This recognizes syntax, not the meaning of prose.
    The expected contract is supplied by the synthetic fixture, never a model.
    """
    try:
        text = raw.decode("utf-8").replace("\r\n", "\n")
        contract = expected.decode("utf-8").replace("\r\n", "\n").rstrip("\n").split("\n")
    except UnicodeError:
        return "FAIL_ENCODING"
    pattern = r"s-[0-9a-f]{24} \| COPY_OK \| [^|\r\n]+"
    if not contract or any(not re.fullmatch(pattern, row) for row in contract):
        return "FAIL_CONTRACT"
    ids = [row.split(" | ")[0] for row in contract]
    if len(set(ids)) != len(ids):
        return "FAIL_CONTRACT"
    # Long literal fragments also identify orphaned/embedded partial receipts.
    # Short ordinary words alone cannot be distinguished from permitted prose.
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
