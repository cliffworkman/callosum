"""Exclusive artifacts and hash-linked receipts in a task-owned private directory."""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import ROSTER, canonical, digest, require, sha

PREFIX = "callosum-adjudication-synthetic-"
MARKER = {"origin": "SYNTHETIC", "kind": "CAPABILITY_PREPARATION", "version": 1}


class Store:
    def __init__(self, root):
        require(not Path(root).is_symlink(), "STORE_SYMLINK_FORBIDDEN")
        self.root = Path(root).resolve()
        require(self.root.parent == Path(tempfile.gettempdir()).resolve(), "PRIVATE_TEMP_ROOT_REQUIRED")
        require(self.root.name.startswith(PREFIX), "TASK_OWNED_ROOT_REQUIRED")
        require("dropbox" not in str(self.root).lower(), "SYNCED_STORAGE_FORBIDDEN")
        require(not (self.root / "owner.json").is_symlink(), "OWNER_SYMLINK_FORBIDDEN")
        require(json.loads((self.root / "owner.json").read_text(encoding="utf-8")) == MARKER, "INVALID_STORE_OWNER")
        require((self.root / "journal").resolve() == self.root / "journal", "JOURNAL_PATH_ESCAPE")

    @classmethod
    def create(cls):
        root = Path(tempfile.mkdtemp(prefix=PREFIX))
        os.chmod(root, 0o700)
        (root / "owner.json").write_bytes(canonical(MARKER))
        (root / "journal").mkdir()
        return cls(root)

    def path(self, name):
        require(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_-]+\.[a-z]+", name), "INVALID_ARTIFACT_NAME")
        require(name != "owner.json", "OWNER_IMMUTABLE")
        path = self.root / name
        require(path.resolve().parent == self.root and not path.is_symlink(), "ARTIFACT_PATH_ESCAPE")
        return path

    def read(self, name):
        return self.path(name).read_bytes()

    def events(self):
        events = []
        previous = None
        for index, path in enumerate(sorted((self.root / "journal").glob("*.json"))):
            require(not path.is_symlink(), "JOURNAL_PATH_ESCAPE")
            require(path.name == f"{index:06d}.json", "JOURNAL_SEQUENCE_ERROR")
            event = json.loads(path.read_bytes())
            recorded_hash = event.pop("event_sha256")
            require(recorded_hash == digest(event) and event["previous"] == previous, "JOURNAL_INTEGRITY_ERROR")
            previous = recorded_hash
            events.append({**event, "event_sha256": recorded_hash})
        return events

    def write(self, name, data, *, kind="ARTIFACT", metadata=None):
        path = self.path(name)
        lock = self.root / "write.lock"
        try:
            lock.mkdir()
        except FileExistsError:
            raise ValueError("STORE_BUSY_OR_INDETERMINATE") from None
        try:
            events = self.events()
            self._verify_artifacts(events)
            with path.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            event = {
                "sequence": len(events),
                "previous": events[-1]["event_sha256"] if events else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "name": name,
                "bytes": len(data),
                "sha256": sha(data),
                "metadata": metadata or {},
            }
            event["event_sha256"] = digest(event)
            with (self.root / "journal" / f"{len(events):06d}.json").open("xb") as handle:
                handle.write(canonical(event))
                handle.flush()
                os.fsync(handle.fileno())
            return {"capture_success": True, "bytes": len(data), "sha256": sha(data)}
        finally:
            lock.rmdir()

    def _verify_artifacts(self, events):
        recorded = set()
        for event in events:
            data = self.read(event["name"])
            require(sha(data) == event["sha256"] and len(data) == event["bytes"], "ARTIFACT_INTEGRITY_ERROR")
            require(event["name"] not in recorded, "DUPLICATE_ARTIFACT_EVENT")
            recorded.add(event["name"])
        actual = {p.name for p in self.root.iterdir() if p.is_file() and p.name != "owner.json"}
        require(actual == recorded, "UNJOURNALED_ARTIFACT")

    def verify(self):
        events = self.events()
        self._verify_artifacts(events)
        require(not (self.root / "write.lock").exists(), "STORE_BUSY_OR_INDETERMINATE")
        return {"verified": True, "artifact_count": len(events)}

    def capture(self, packet, raw, *, surface_id, attempt=1, amendment_id=None):
        require(surface_id in dict(ROSTER), "UNREGISTERED_RATER")
        require(type(attempt) is int and attempt in (1, 2), "RETRY_LIMIT")
        require(len(raw) <= 8 * 1024 * 1024, "CAPTURE_SIZE_LIMIT")
        name = f"{surface_id}_{packet.packet_id}_attempt{attempt}.bin"
        if attempt == 2:
            first = f"{surface_id}_{packet.packet_id}_attempt1.bin"
            require(self.path(first).exists(), "FIRST_ATTEMPT_REQUIRED")
            amendments = [e for e in self.events() if e["kind"] == "MECHANICAL_AMENDMENT"]
            require(any(e["sha256"] == amendment_id for e in amendments), "MECHANICAL_AMENDMENT_REQUIRED")
            require(packet.check_response(self.read(first)) != "PASS", "UNNECESSARY_RESUBMISSION")
        return self.write(
            name,
            raw,
            kind="CAPABILITY_CAPTURE",
            metadata={
                "origin": "SYNTHETIC_PACKET_RESPONSE",
                "packet_id": packet.packet_id,
                "surface_id": surface_id,
                "payload_sha256": sha(packet.payload),
                "attempt": attempt,
                "status": packet.check_response(raw),
                "amendment_id": amendment_id,
            },
        )
