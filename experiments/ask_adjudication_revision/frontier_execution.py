"""Private append-only execution receipts and frozen parsing; no model dispatcher."""

import importlib.util
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import canonical, require, sha

FREEZE = Path("C:/Users/cliff/AppData/Local/Temp/callosum-freeze-a-final-private-mskudgm3")
FREEZE_HASH = "1836253a4c8632e36cabdab5f3c4c17168a33af4cfb1a0ca529a4d6b1a425437"
AUTH = Path("C:/Users/cliff/.codex/attachments/bfb38196-ba3f-4c06-9998-3c79b935b802/pasted-text.txt")


def initialize():
    require(sha((FREEZE / "freeze_a_manifest.json").read_bytes()) == FREEZE_HASH, "FREEZE_HASH")
    manifest = json.loads((FREEZE / "freeze_a_manifest.json").read_bytes())
    for name, info in manifest["artifacts"].items():
        require(sha((FREEZE / name).read_bytes()) == info["sha256"], "FROZEN_ARTIFACT_HASH")
    root = Path(tempfile.mkdtemp(prefix="callosum-frontier-study-private-"))
    os.chmod(root, 0o700)
    (root / "relay").mkdir()
    (root / "records").mkdir()
    (root / "journal").mkdir()
    (root / "authorization.txt").write_bytes(AUTH.read_bytes())
    (root / "execution.json").write_bytes(
        canonical(
            {
                "kind": "REAL_FRONTIER_STUDY_EXECUTION",
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "freeze_root": str(FREEZE),
                "freeze_sha256": FREEZE_HASH,
                "planned_packets": 273,
                "planned_cells": 546,
                "authorized_by_sha256": sha(AUTH.read_bytes()),
                "no_study2": True,
                "no_automatic_retry": True,
                "blinding": "standing user-approved dedicated minimized Chrome; private DOM capture; no clipboard/response echo",
            }
        )
    )
    return root


def verify_journal(root):
    previous = None
    events = []
    for i, path in enumerate(sorted((root / "journal").glob("*.json"))):
        event = json.loads(path.read_bytes())
        require(path.name == f"{i:06d}.json", "JOURNAL_SEQUENCE")
        digest = event.pop("event_sha256")
        require(sha(canonical(event)) == digest and event["previous"] == previous, "JOURNAL_CHAIN")
        for name, expected in event["artifacts"].items():
            require(Path(name).name == name, "RECORD_PATH")
            require(sha((root / "records" / name).read_bytes()) == expected, "RECORD_HASH")
        previous = digest
        events.append({**event, "event_sha256": digest})
    return events


def select_capture(directory, key, packet_hash):
    """Accept an append-only recovery of an empty, premature DOM capture only."""
    original_path = directory / (key + ".completion.json")
    meta = json.loads(original_path.read_bytes())
    require(meta["packet_sha256"] == packet_hash, "CAPTURE_PACKET_HASH")
    raw_name = key + ".raw"
    recovery_path = directory / (key + ".capture_recovery.json")
    if recovery_path.exists():
        recovery = json.loads(recovery_path.read_bytes())
        original_raw = (directory / raw_name).read_bytes()
        require(original_raw == b"", "RECOVERY_REQUIRES_EMPTY_ORIGINAL")
        require(recovery["original_raw_sha256"] == sha(original_raw), "RECOVERY_ORIGINAL_RAW")
        require(recovery["original_completion_sha256"] == sha(original_path.read_bytes()), "RECOVERY_ORIGINAL_META")
        require(recovery["packet_sha256"] == packet_hash, "RECOVERY_PACKET_HASH")
        require(recovery["url"] == meta["url"], "RECOVERY_CONVERSATION")
        require(recovery["sendInvocations"] == meta["sendInvocations"], "RECOVERY_NO_NEW_SEND")
        require(recovery["status"] == "RESPONSE_CAPTURED", "RECOVERY_STATUS")
        require(recovery["finalBodyOnly"] and recovery["stopAbsent"], "RECOVERY_FINAL_BOUNDARY")
        raw_name = key + ".recovered.raw"
        raw = (directory / raw_name).read_bytes()
        require(bool(raw) and sha(raw) == recovery["raw_sha256"], "RECOVERY_RAW_HASH")
        require(len(raw) == recovery["bytes"], "RECOVERY_RAW_BYTES")
        meta = recovery
    return meta, raw_name


def ingest(root):
    root = Path(root)
    require(
        root.parent == Path(tempfile.gettempdir()) and root.name.startswith("callosum-frontier-study-private-"),
        "PRIVATE_ROOT",
    )
    require(json.loads((root / "execution.json").read_bytes())["freeze_sha256"] == FREEZE_HASH, "EXECUTION_IDENTITY")
    require(sha((FREEZE / "freeze_a_manifest.json").read_bytes()) == FREEZE_HASH, "FREEZE_HASH")
    manifest = json.loads((FREEZE / "freeze_a_manifest.json").read_bytes())
    for name in ("bound_core.py", "bound_frontier_contract.py", "packet_index.json", "surfaces.json"):
        require(sha((FREEZE / name).read_bytes()) == manifest["artifacts"][name]["sha256"], "PARSER_BINDING_HASH")
    require(
        sha(Path(__file__).with_name("core.py").read_bytes()) == manifest["artifacts"]["bound_core.py"]["sha256"],
        "CORE_DEPENDENCY_HASH",
    )
    spec = importlib.util.spec_from_file_location(
        "experiments.ask_adjudication_revision._execution_frozen_parser", FREEZE / "bound_frontier_contract.py"
    )
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    index = json.loads((FREEZE / "packet_index.json").read_bytes())
    events = verify_journal(root)
    done = {e["packet"] for e in events}
    for packet in index:
        key = packet["artifact"].removesuffix(".txt")
        completion = root / "relay" / (key + ".completion.json")
        if key in done or not completion.exists():
            continue
        meta, raw_name = select_capture(root / "relay", key, packet["packet_sha256"])
        artifact_hashes = {}
        for suffix in (
            ".gate.json", ".intent.json", ".raw", ".completion.json", ".error.txt",
            ".recovered.raw", ".capture_recovery.json", ".capture_boundary_check.json",
        ):
            source = root / "relay" / (key + suffix)
            if source.exists():
                data = source.read_bytes()
                with (root / "records" / source.name).open("xb") as handle:
                    handle.write(data)
                artifact_hashes[source.name] = sha(data)
        if meta["status"] == "RESPONSE_CAPTURED":
            raw = (root / "records" / raw_name).read_bytes()
            result = parser.parse_response(
                raw,
                packet["candidate_ids"],
                copilot_empty_lines=packet["surface"] == "copilot",
                truncated=meta.get("truncated", False),
            )
        else:
            result = {"technical_status": meta["status"], "rows": [], "raw_sha256": artifact_hashes.get(raw_name)}
        data = canonical(result)
        name = key + ".normalized.json"
        with (root / "records" / name).open("xb") as handle:
            handle.write(data)
        artifact_hashes[name] = sha(data)
        event = {
            "packet": key,
            "surface": packet["surface"],
            "cells": len(packet["candidate_ids"]),
            "technical_status": result["technical_status"],
            "selected_raw_artifact": raw_name,
            "artifacts": artifact_hashes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous": events[-1]["event_sha256"] if events else None,
        }
        event["event_sha256"] = sha(canonical(event))
        with (root / "journal" / f"{len(events):06d}.json").open("xb") as handle:
            handle.write(canonical(event))
        events.append(event)
    verify_journal(root)
    return {
        "planned_packets": 273,
        "completed_packets": len(events),
        "planned_cells": 546,
        "completed_cells": sum(e["cells"] for e in events),
        "technical_missing_cells": sum(e["cells"] for e in events if e["technical_status"] != "VALID"),
        "integrity": "PASS",
        "study_closed": False,
    }
