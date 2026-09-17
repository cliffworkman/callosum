"""Exclusive observation claims, durable append-only journals and hash-linked artifacts."""

import json
import os
from pathlib import Path

from .contracts import ContractError
from .hashing import canonical, digest, file_hash, read_json, write_json
from .validation import validate

PERFORMANCE_KEYS = {
    "thermal_state",
    "latency_seconds",
    "prompt_tokens",
    "completion_tokens",
    "peak_vram_bytes",
    "peak_rss_bytes",
    "actual_context",
    "kv_k",
    "kv_v",
    "host_state_hash",
    "cache_state",
    "startup_seconds",
    "measurement_status",
    "service_latency_seconds",
}


def performance_only(values):
    if set(values) - PERFORMANCE_KEYS:
        raise ContractError("PERFORMANCE_PRIVACY_FIELD_REJECTED")
    numeric = {
        "latency_seconds",
        "prompt_tokens",
        "completion_tokens",
        "peak_vram_bytes",
        "peak_rss_bytes",
        "actual_context",
        "startup_seconds",
        "service_latency_seconds",
    }
    enums = {
        "thermal_state": {"cold", "warm", "unknown"},
        "kv_k": {"f16", "q8_0", "q4_0", "not_applicable"},
        "kv_v": {"f16", "q8_0", "q4_0", "not_applicable"},
        "cache_state": {"cached", "uncached", "unknown", "not_applicable"},
        "measurement_status": {"MEASURED", "UNAVAILABLE", "NOT_RUN", "NOT_APPLICABLE", "SYNTHETIC"},
    }
    for key, value in values.items():
        if value is None:
            continue
        if key in numeric and (type(value) not in (int, float) or value < 0):
            raise ContractError("INVALID_PERFORMANCE_MEASUREMENT")
        if key in enums and value not in enums[key]:
            raise ContractError("PERFORMANCE_PRIVACY_VALUE_REJECTED")
        if key == "host_state_hash" and (
            not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ContractError("INVALID_HOST_REFERENCE")
    canonical(values)  # rejects NaN/infinity
    return {k: values.get(k) for k in sorted(PERFORMANCE_KEYS)}


class ObservationStore:
    def __init__(self, root):
        self.root = Path(root)

    def claim(self, cell_id, identity):
        if len(cell_id) != 64 or any(c not in "0123456789abcdef" for c in cell_id) or digest(identity) != cell_id:
            raise ContractError("INVALID_CELL_IDENTITY")
        self.root.mkdir(parents=True, exist_ok=True)
        folder = self.root / cell_id
        try:
            folder.mkdir()  # exclusive across process restarts; never reclaim automatically
        except FileExistsError as exc:
            raise ContractError("OBSERVATION_ALREADY_CLAIMED_NO_RETRY") from exc
        write_json(folder / "identity.json", identity, exclusive=True)
        self.event(cell_id, "CLAIMED", {"identity_sha256": digest(identity)})

    def event(self, cell_id, event, payload):
        path = self.root / cell_id / "journal.jsonl"
        previous = "0" * 64
        sequence = 0
        if path.exists():
            rows = self.journal(cell_id)
            sequence = len(rows)
            previous = rows[-1]["event_hash"] if rows else previous
        entry = {"sequence": sequence, "previous": previous, "event": event, "payload": payload}
        entry["event_hash"] = digest(entry)
        with path.open("ab") as handle:
            handle.write(canonical(entry) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def journal(self, cell_id):
        path = self.root / cell_id / "journal.jsonl"
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        previous = "0" * 64
        for index, row in enumerate(rows):
            content = {k: v for k, v in row.items() if k != "event_hash"}
            if row["sequence"] != index or row["previous"] != previous or digest(content) != row["event_hash"]:
                raise ContractError("OBSERVATION_JOURNAL_INTEGRITY_FAILURE")
            previous = row["event_hash"]
        return rows

    def artifact(self, cell_id, name, content):
        if Path(name).name != name:
            raise ContractError("ARTIFACT_NAME_MUST_BE_LOCAL")
        path = self.root / cell_id / name
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return {"artifact": name, "sha256": file_hash(path)}

    def finish(self, cell_id, receipt):
        folder = self.root / cell_id
        validate(receipt, read_json(Path(__file__).parent / "schemas/cell_receipt.schema.json"))
        write_json(folder / "receipt.json", receipt, exclusive=True)
        self.event(cell_id, "FINALIZED", {"receipt_sha256": file_hash(folder / "receipt.json")})

    def inspect(self, cell_id):
        folder = self.root / cell_id
        if not folder.exists():
            return {"status": "MISSING", "success": False}
        try:
            rows = self.journal(cell_id)
            if not rows or rows[-1]["event"] != "FINALIZED":
                return {"status": "INDETERMINATE_NO_RETRY", "success": False}
            receipt = read_json(folder / "receipt.json")
            if digest(receipt["identity"]) != cell_id or read_json(folder / "identity.json") != receipt["identity"]:
                raise ContractError("CELL_IDENTITY_RECEIPT_MISMATCH")
            if file_hash(folder / "receipt.json") != rows[-1]["payload"]["receipt_sha256"]:
                raise ContractError("RECEIPT_HASH_MISMATCH")
            for ref in receipt["artifacts"]:
                if (
                    Path(ref["artifact"]).name != ref["artifact"]
                    or file_hash(folder / ref["artifact"]) != ref["sha256"]
                ):
                    raise ContractError("ARTIFACT_HASH_MISMATCH")
            return {"status": receipt["status"], "success": receipt["status"] == "SUCCESS", "receipt": receipt}
        except (OSError, ValueError, KeyError):
            return {"status": "CORRUPT_OR_INCOMPLETE", "success": False}
