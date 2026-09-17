"""Explicitly authorized, offline three-file projection; never inference or freeze.

Unselected values are scanned for boundaries, not decoded. No source content is
printed. Archive paths are fixed; no recursive discovery or old script imports.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import canonical, digest, require, sha

OUTPUT_ARCHIVE = Path(
    "C:/Users/cliff/AppData/Local/Temp/callosum-claim-representation-isolation-resume-20260909-190527"
)
SOURCE_ARCHIVE = Path("C:/Users/cliff/AppData/Local/Temp/callosum-claim-representation-isolation-20260909-184828")
SOURCE_FIELDS = ("quote", "paper_id", "span", "grown_context", "source_unit_context")
OUTPUT_FIELDS = (
    "raw_text",
    "produced_representation",
    "provider_ok",
    "failure_reason",
    "finish_reason",
    "truncated",
    "whole_response_parse_success",
    "schema_valid",
    "malformed_response",
    "mechanically_complete",
    "empty_response",
    "explicit_null_claim",
    "wrapper_fallback",
    "prompt_sha256",
)


def ws(data, pos):
    while pos < len(data) and data[pos] in b" \r\n\t":
        pos += 1
    return pos


def end_value(data, start):
    """Find raw value boundary without decoding scientific strings/lineage."""
    start = ws(data, start)
    require(start < len(data), "JSON_BOUNDARY")
    in_string = False
    escaped = False
    stack = []
    for i in range(start, len(data)):
        char = data[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                in_string = False
                if not stack:
                    return i + 1
        elif char == 34:
            in_string = True
        elif char in (91, 123):
            stack.append(char)
        elif char in (93, 125):
            if not stack:
                return i
            require(stack.pop() == (91 if char == 93 else 123), "JSON_BOUNDARY")
            if not stack:
                return i + 1
        elif not stack and char in b", \r\n\t":
            return i
    require(not in_string and not stack, "JSON_BOUNDARY")
    return len(data)


def object_fields(data):
    pos = ws(data, 0)
    require(data[pos : pos + 1] == b"{", "EXPECTED_OBJECT")
    pos += 1
    seen = set()
    while True:
        pos = ws(data, pos)
        if data[pos : pos + 1] == b"}":
            require(ws(data, pos + 1) == len(data), "JSON_TRAILING_DATA")
            return
        require(data[pos : pos + 1] == b'"', "JSON_KEY")
        end = end_value(data, pos)
        key = json.loads(data[pos:end])
        require(key not in seen, "DUPLICATE_JSON_KEY")
        seen.add(key)
        pos = ws(data, end)
        require(data[pos : pos + 1] == b":", "JSON_COLON")
        start = ws(data, pos + 1)
        end = end_value(data, start)
        yield key, start, end
        pos = ws(data, end)
        require(data[pos : pos + 1] in (b",", b"}"), "JSON_SEPARATOR")
        if data[pos : pos + 1] == b",":
            pos += 1


def project(data, fields):
    wanted = set(fields)
    result = {key: json.loads(data[start:end]) for key, start, end in object_fields(data) if key in wanted}
    require(set(result) == wanted, "REQUIRED_FIELD_MISSING")
    return result


def array_records(data):
    pos = ws(data, 0)
    require(data[pos : pos + 1] == b"[", "EXPECTED_INVENTORY_ARRAY")
    pos += 1
    while True:
        pos = ws(data, pos)
        if data[pos : pos + 1] == b"]":
            require(ws(data, pos + 1) == len(data), "JSON_TRAILING_DATA")
            return
        end = end_value(data, pos)
        yield data[pos:end]
        pos = ws(data, end)
        require(data[pos : pos + 1] in (b",", b"]"), "JSON_SEPARATOR")
        if data[pos : pos + 1] == b",":
            pos += 1


def bounded_read(path):
    require(not path.is_symlink(), "ARCHIVE_SYMLINK_FORBIDDEN")
    require(path.stat().st_size <= 128 * 1024 * 1024, "ARCHIVE_READ_BOUND")
    return path.read_bytes()


def construct_projection():
    # Supporting metadata projects only authorized entries; never follows paths.
    hashes = project(
        bounded_read(OUTPUT_ARCHIVE / "artifact_hashes.json"),
        ("arm1_outputs.jsonl", "arm2_outputs.jsonl", "execution_freeze_manifest.v2.json"),
    )
    manifest = bounded_read(OUTPUT_ARCHIVE / "execution_freeze_manifest.v2.json")
    require(sha(manifest) == hashes["execution_freeze_manifest.v2.json"], "EXECUTION_MANIFEST_HASH_MISMATCH")
    sidecar = bounded_read(OUTPUT_ARCHIVE / "execution_freeze_manifest.v2.sha256")
    require(sidecar.decode("ascii").split()[0] == sha(manifest), "EXECUTION_SIDECAR_HASH_MISMATCH")
    file_span = [(a, z) for k, a, z in object_fields(manifest) if k == "files"]
    require(len(file_span) == 1, "EXECUTION_FILES_MISSING")
    nested = manifest[file_span[0][0] : file_span[0][1]]
    target = str(SOURCE_ARCHIVE / "experimental_units.json").replace("\\", "/").lower()
    inventory_hashes = [
        json.loads(nested[a:z]) for k, a, z in object_fields(nested) if k.replace("\\", "/").lower() == target
    ]
    require(len(inventory_hashes) == 1, "INVENTORY_PROVENANCE_UNAVAILABLE")
    inv = bounded_read(SOURCE_ARCHIVE / "experimental_units.json")
    require(sha(inv) == inventory_hashes[0], "INVENTORY_HASH_MISMATCH")
    sources, inventory_ids, exclusions = {}, set(), []
    for raw in array_records(inv):
        identity = project(raw, ("unit_id", "qid"))
        uid = identity["unit_id"]
        require(isinstance(uid, str) and uid not in inventory_ids, "DUPLICATE_OR_INVALID_SOURCE_ID")
        inventory_ids.add(uid)
        if identity["qid"] != "q_aib":
            exclusions.append({"unit_id": uid, "reason": "OUTSIDE_Q_AIB"})
            continue
        sources[uid] = {**identity, **project(raw, SOURCE_FIELDS), "record_sha256": sha(raw)}
    require(len(sources) == 39 and len(inventory_ids) == 164, "INVENTORY_COUNT_MISMATCH")
    archive_hashes = {"inventory": sha(inv), "execution_manifest": sha(manifest)}
    observations = []
    for arm in (1, 2):
        data = bounded_read(OUTPUT_ARCHIVE / f"arm{arm}_outputs.jsonl")
        require(sha(data) == hashes[f"arm{arm}_outputs.jsonl"], "OUTPUT_HASH_MISMATCH")
        archive_hashes[f"arm{arm}"] = sha(data)
        seen = set()
        for raw in data.splitlines():
            if not raw.strip():
                continue
            identity = project(raw, ("unit_id", "arm"))
            uid = identity["unit_id"]
            require(identity["arm"] == arm and uid not in seen and uid in inventory_ids, "OUTPUT_IDENTITY_MISMATCH")
            seen.add(uid)
            if uid not in sources:
                continue
            observations.append({**identity, **project(raw, OUTPUT_FIELDS), "record_sha256": sha(raw)})
        require(seen == inventory_ids, "OUTPUT_MEMBERSHIP_MISMATCH")
    objects, identities = [], []
    for row in observations:
        src = sources[row["unit_id"]]
        representation = row["produced_representation"]
        if row["arm"] == 2:
            anchor = representation["canonical_evidence"]
            require(
                anchor["quote"] == src["quote"]
                and anchor["paper_id"] == src["paper_id"]
                and anchor["span"] == src["span"],
                "ARM2_SOURCE_BINDING_MISMATCH",
            )
        cid = "c-" + digest(
            {
                "domain": "callosum-study1-freeze-a-v1",
                "archive": archive_hashes,
                "unit_id": row["unit_id"],
                "arm": row["arm"],
            }
        )
        scientific = {
            "candidate_id": cid,
            "source": {
                "source_unit_id": src["unit_id"],
                "paper_id": src["paper_id"],
                "source_span": src["span"],
                "exact_excerpt": src["quote"],
                "grown_context": src["grown_context"],
                "source_unit_and_obligation_context": src["source_unit_context"],
            },
            "raw_output": row["raw_text"],
            "effective_representation": representation,
        }
        objects.append(scientific)
        identities.append(
            {
                "candidate_id": cid,
                "unit_id": row["unit_id"],
                "configuration": row["arm"],
                "source_record_sha256": src["record_sha256"],
                "output_record_sha256": row["record_sha256"],
                "projected_output_sha256": digest(row),
                "scientific_object_sha256": digest(scientific),
                "source_sha256": digest(scientific["source"]),
                "excerpt_sha256": digest(src["quote"]),
                "context_sha256": digest({"grown": src["grown_context"], "task": src["source_unit_context"]}),
                "representation_sha256": digest(representation),
                "original_prompt_sha256": row["prompt_sha256"],
                "mechanical": {
                    k: row[k]
                    for k in OUTPUT_FIELDS
                    if k not in ("raw_text", "produced_representation", "prompt_sha256")
                },
            }
        )
    require(len(objects) == 78 and len({x["candidate_id"] for x in objects}) == 78, "CORPUS_IDENTITY_COLLISION")
    sizes = [len(canonical(x)) for x in objects]
    report = {
        "status": "PROJECTED_NOT_FROZEN",
        "inventory_units": len(inventory_ids),
        "q_aib_units": len(sources),
        "configuration_counts": {str(a): sum(x["configuration"] == a for x in identities) for a in (1, 2)},
        "scientific_objects": len(objects),
        "outside_question_units": len(exclusions),
        "semantic_quality_exclusions": 0,
        "mechanical_incomplete_retained": sum(not x["mechanical"]["mechanically_complete"] for x in identities),
        "object_min_bytes": min(sizes),
        "object_max_bytes": max(sizes),
        "objects_exceeding_14698": sum(n > 14698 for n in sizes),
        "corpus_sha256": digest(objects),
        "archive_hashes": archive_hashes,
        "sealed_mapping_accessed": False,
        "semantic_inference_calls": 0,
        "source_identity_and_arm2_anchor_checks": "PASS",
    }
    return {
        "corpus.json": canonical(objects),
        "private_identities.json": canonical(identities),
        "exclusions.json": canonical(exclusions),
        "projection_receipt.json": canonical(report),
    }, report


def main():
    # This entrypoint does not construct a Freeze-A manifest or send any request.
    root = Path(tempfile.mkdtemp(prefix="callosum-freeze-a-private-"))
    os.chmod(root, 0o700)
    try:
        files, report = construct_projection()
        artifacts = {}
        for name, data in files.items():
            with (root / name).open("xb") as handle:
                handle.write(data)
            artifacts[name] = {"sha256": sha(data), "bytes": len(data)}
        (root / "projection_artifacts.json").write_bytes(
            canonical(
                {
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "origin": "REAL_CORPUS_AUTHORIZED_PROJECTION",
                    "freeze_a_executed": False,
                    "artifacts": artifacts,
                }
            )
        )
        print(json.dumps({"private_root": str(root), **report}))
    except Exception as error:
        code = str(error) if re.fullmatch(r"[A-Z][A-Z0-9_]+", str(error)) else "PROJECTION_STRUCTURE_OR_IO_ERROR"
        (root / "blocked.json").write_bytes(canonical({"status": "BLOCKED", "code": code, "freeze_a_executed": False}))
        print(json.dumps({"private_root": str(root), "status": "BLOCKED", "code": code, "freeze_a_executed": False}))


if __name__ == "__main__":
    main()
