"""Lossless synthetic packet adapters and strict, deterministic response parsing."""

import csv
import io
import json
import re
from dataclasses import dataclass

from .core import canonical, require, sha, validate_cases

FORMATS = ("txt", "json", "csv", "markdown")


def render(cases, format="txt"):
    validate_cases(cases)
    require(format in FORMATS, "UNSUPPORTED_FORMAT")
    records = [c.content() for c in cases]
    if format == "json":
        return canonical(records)
    if format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["candidate_id", "scientific_object_json"])
        writer.writerows((r["candidate_id"], canonical(r).decode()) for r in records)
        return stream.getvalue().encode("utf-8")
    # JSON-escaped record bodies preserve literal tabs/newlines/delimiters. TXT is
    # ordinary UTF-8 text, requiring neither JSON attachments nor model JSON output.
    prefix = "SYNTHETIC PACKET v1\n" if format == "txt" else "# SYNTHETIC PACKET v1\n"
    return (prefix + "\n".join("CASE " + canonical(r).decode() for r in records) + "\n").encode("utf-8")


def decode_packet(data, format):
    try:
        text = data.decode("utf-8")
        if format == "json":
            return json.loads(text)
        if format == "csv":
            rows = list(csv.DictReader(io.StringIO(text)))
            result = [json.loads(r["scientific_object_json"]) for r in rows]
            require(
                all(r["candidate_id"] == v["candidate_id"] for r, v in zip(rows, result, strict=True)),
                "PACKET_ID_MISMATCH",
            )
            return result
        require(format in ("txt", "markdown"), "UNSUPPORTED_FORMAT")
        return [json.loads(line[5:]) for line in text.splitlines()[1:] if line.startswith("CASE ")]
    except (ValueError, KeyError, UnicodeError):
        raise ValueError("PACKET_PARSE_ERROR") from None


def batches(cases, *, format="txt", max_bytes=32000, max_candidates=8, prompt_bytes=0):
    validate_cases(cases)
    require(max_candidates >= 1 and max_bytes > prompt_bytes >= 0, "INVALID_ENVELOPE")
    result, current = [], []
    for case in cases:
        require(len(render([case], format)) + prompt_bytes <= max_bytes, "OBJECT_EXCEEDS_ENVELOPE")
        proposed = current + [case]
        if current and (len(proposed) > max_candidates or len(render(proposed, format)) + prompt_bytes > max_bytes):
            result.append(render(current, format))
            current = []
        current.append(case)
    if current:
        result.append(render(current, format))
    return tuple(result)


@dataclass(frozen=True)
class Normalized:
    technical_status: str
    rows: tuple
    raw_sha256: str


def normalize(raw, expected_ids, *, truncated=False):
    """A failed batch contributes no favorable partial rows. Raw bytes stay elsewhere."""
    expected = set(expected_ids)
    require(len(expected) == len(expected_ids) and bool(expected), "INVALID_EXPECTED_IDS")
    raw_hash = sha(raw)
    if truncated:
        return Normalized("TRUNCATED", (), raw_hash)
    try:
        text = raw.decode("utf-8").strip()
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1])
        if text.startswith("["):
            objects = json.loads(text)
            require(isinstance(objects, list), "RESPONSE_FORMAT")
            rows = []
            for obj in objects:
                require(isinstance(obj, dict) and set(obj) == {"candidate_id", "label", "reason"}, "RESPONSE_FORMAT")
                rows.append((obj["candidate_id"], obj["label"], obj["reason"]))
        else:
            rows = []
            for line in text.splitlines():
                fields = re.split(r"\t|\|", line, maxsplit=2)
                require(len(fields) == 3, "RESPONSE_FORMAT")
                rows.append(tuple(f.strip() for f in fields))
        seen = set()
        for cid, label, reason in rows:
            require(isinstance(cid, str) and cid in expected and cid not in seen, "RESPONSE_IDS")
            require(label in ("FLAG", "UNCERTAIN", "NO_FLAG") and isinstance(reason, str), "RESPONSE_FORMAT")
            require(
                (label == "NO_FLAG" and not reason) or (label != "NO_FLAG" and bool(reason.strip())), "RESPONSE_REASON"
            )
            seen.add(cid)
        if seen != expected:
            return Normalized("MISSING_ROWS", (), raw_hash)
        return Normalized("VALID", tuple(rows), raw_hash)
    except (ValueError, TypeError, KeyError, UnicodeError):
        return Normalized("INVALID_RESPONSE", (), raw_hash)
