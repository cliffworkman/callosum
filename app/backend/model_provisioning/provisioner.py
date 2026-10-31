"""One restart-safe provisioning track: detect, download, verify and record one pinned checkpoint (inc 615).

Design rules:

* **Status is local and cheap.** ``status()`` reads a small JSON state file and ``stat``s the manifest files. It never
  touches the network, never hashes, never loads a model. A ``verified`` receipt is trusted only while its manifest
  digest and every file's size and modification time still match; anything else drops back to a re-verify.
* **One owner per track across processes.** An OS-level lock (the inc-610 ``WorkerLock``) is held for the whole
  attempt, so two Callosum instances sharing a cache never download the same checkpoint twice. The OS frees the lock
  when a process dies, which is how a killed download is recognised as ``interrupted`` on the next start.
* **The Hub cache does the transfer.** Files are fetched one at a time through ``huggingface_hub`` into the ordinary
  shared cache, which resumes its own ``.incomplete`` files. Callosum never deletes cache entries; an explicit retry of
  a corrupt file re-fetches it with ``force_download``.
* **Transient is not terminal.** Network trouble, missing disk space and unknown interruptions are retried with a
  bounded backoff schedule, indefinitely. An integrity or contract failure, or a pinned revision the Hub no longer
  serves, is terminal until an explicit ``provision_once(force=True)``; it is never retried automatically.
* **Nothing private leaves.** A request names only the manifest's repository, revision and filename.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import socket
import time
from collections.abc import Callable
from pathlib import Path

from app.backend.embeddings.index_lock import WorkerLock
from app.backend.model_provisioning.manifests import (
    ArtifactFile,
    ContractMismatch,
    ModelManifest,
    check_static_contract,
)

ABSENT = "absent"
DOWNLOADING = "downloading"
WAITING_FOR_NETWORK = "waiting_for_network"
INTERRUPTED = "interrupted"
PRESENT_UNVERIFIED = "present_unverified"
VERIFIED = "verified"
INVALID = "invalid"
INSUFFICIENT_RESOURCES = "insufficient_resources"
STATES = (
    ABSENT,
    DOWNLOADING,
    WAITING_FOR_NETWORK,
    INTERRUPTED,
    PRESENT_UNVERIFIED,
    VERIFIED,
    INVALID,
    INSUFFICIENT_RESOURCES,
)
RETRYABLE = frozenset({WAITING_FOR_NETWORK, INTERRUPTED, INSUFFICIENT_RESOURCES})
TERMINAL = frozenset({VERIFIED, INVALID})

BACKOFF_SECONDS: tuple[float, ...] = (30.0, 120.0, 600.0, 1800.0)  # the last value repeats: bounded, never terminal
DISK_MARGIN_BYTES = 64 * 1024 * 1024
_HASH_CHUNK = 1024 * 1024

Fetcher = Callable[[str, str, str, Path, bool], object]  # (repo_id, revision, filename, cache_dir, force) -> path


def hub_fetch(repo_id: str, revision: str, filename: str, cache_dir: Path, force: bool) -> object:
    """Download one file at the pinned revision into the shared Hub cache (resumes its own partial files)."""
    from huggingface_hub import hf_hub_download

    return hf_hub_download(
        repo_id=repo_id, filename=filename, revision=revision, cache_dir=str(cache_dir), force_download=force
    )


def default_cache_dir() -> Path:
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def hub_offline() -> bool:
    return os.environ.get("HF_HUB_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}


# Exception classes are matched by name across the MRO so classification does not depend on whether the installed
# huggingface_hub speaks requests (0.x) or httpx (1.x).
_NETWORK_NAMES = {
    "LocalEntryNotFoundError",  # raised by the Hub client when it cannot reach the server and has no local copy
    "ConnectionError",
    "ConnectTimeout",
    "ReadTimeout",
    "Timeout",
    "TimeoutException",
    "ConnectError",
    "ReadError",
    "NetworkError",
    "RemoteProtocolError",
    "ProxyError",
    "SSLError",
    "ChunkedEncodingError",
    "ProtocolError",
    "IncompleteRead",
    "RemoteDisconnected",
}
_UNAVAILABLE_NAMES = {
    "RepositoryNotFoundError",
    "RevisionNotFoundError",
    "EntryNotFoundError",
    "RemoteEntryNotFoundError",
    "GatedRepoError",
    "DisabledRepoError",
}


def classify(exc: BaseException) -> tuple[str, str]:
    """(state, error_kind) for an exception raised while fetching."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    if "LocalEntryNotFoundError" in names:  # subclasses EntryNotFoundError in 0.x: check it first
        return WAITING_FOR_NETWORK, "network"
    if names & _UNAVAILABLE_NAMES:
        return INVALID, "pinned_revision_unavailable"
    if isinstance(exc, OSError) and exc.errno in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)}:
        return INSUFFICIENT_RESOURCES, "disk_full"
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        if status in (401, 403, 404, 410):
            return INVALID, "pinned_revision_unavailable"
        if status in (408, 429) or status >= 500:
            return WAITING_FOR_NETWORK, "network"
    if names & _NETWORK_NAMES or isinstance(exc, (TimeoutError, socket.gaierror, socket.timeout)):
        return WAITING_FOR_NETWORK, "network"
    if isinstance(exc, ConnectionError):
        return WAITING_FOR_NETWORK, "network"
    return INTERRUPTED, "unexpected"


def _scrub(text: str) -> str:
    return " ".join(str(text).split())[:400]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _free_bytes(path: Path) -> int:
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return shutil.disk_usage(probe).free


class Provisioner:
    def __init__(
        self,
        manifest: ModelManifest,
        *,
        cache_dir: Path,
        state_dir: Path,
        fetcher: Fetcher = hub_fetch,
        free_bytes: Callable[[Path], int] = _free_bytes,
        memory_ok: Callable[[], bool] | None = None,
        offline: Callable[[], bool] = hub_offline,
        clock: Callable[[], float] = time.time,
        backoff: tuple[float, ...] = BACKOFF_SECONDS,
    ) -> None:
        self.manifest = manifest
        self.cache_dir = Path(cache_dir)
        self.state_dir = Path(state_dir)
        self._fetch = fetcher
        self._free_bytes = free_bytes
        self._memory_ok = memory_ok or _memory_ok
        self._offline = offline
        self._clock = clock
        self._backoff = backoff
        self._lock = WorkerLock(self.state_dir / f"{manifest.track}.lock")
        self._holding = False

    # --- paths and persisted state -------------------------------------------------------------------------------
    @property
    def snapshot_root(self) -> Path:
        folder = "models--" + self.manifest.repo_id.replace("/", "--")
        return self.cache_dir / folder / "snapshots" / self.manifest.revision

    @property
    def state_path(self) -> Path:
        return self.state_dir / f"{self.manifest.track}.json"

    def _read(self) -> dict:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if data.get("manifest_digest") != self.manifest.digest:
            return {}  # a state written for another manifest says nothing about this one
        return data if data.get("state") in STATES else {}

    def _write(self, **fields: object) -> dict:
        data = {k: v for k, v in self._read().items() if k in {"attempts", "failures"}}
        data.update(
            track=self.manifest.track,
            repo_id=self.manifest.repo_id,
            revision=self.manifest.revision,
            manifest_digest=self.manifest.digest,
            updated_at=self._clock(),
        )
        data.update(fields)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_name(f"{self.state_path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.state_path)  # atomic: a crash leaves the old state or the new one, never half of either
        return data

    def _stat(self, f: ArtifactFile) -> os.stat_result | None:
        try:
            return (self.snapshot_root / f.path).stat()
        except OSError:
            return None

    def _receipt_matches(self, data: dict) -> bool:
        files = data.get("verified_files")
        if data.get("state") != VERIFIED or not isinstance(files, dict):
            return False
        for f in self.manifest.files:
            st = self._stat(f)
            if st is None or files.get(f.path) != [st.st_size, st.st_mtime_ns] or st.st_size != f.size:
                return False
        return True

    def _owned_elsewhere(self) -> bool:
        if self._holding:
            return False
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self._lock.acquire():
            self._lock.release()
            return False
        return True

    # --- status (local, no network, no hashing) -----------------------------------------------------------------
    def status(self) -> dict:
        data = self._read()
        present = [f for f in self.manifest.files if (st := self._stat(f)) is not None and st.st_size == f.size]
        if self._receipt_matches(data):
            state = VERIFIED
        elif self._owned_elsewhere():
            state = data.get("state") if data.get("state") in RETRYABLE | {DOWNLOADING} else DOWNLOADING
        elif data.get("state") in {INVALID, INSUFFICIENT_RESOURCES, WAITING_FOR_NETWORK}:
            state = data["state"]
        elif data.get("state") in {DOWNLOADING, INTERRUPTED}:
            state = INTERRUPTED  # the owner is gone: killed, crashed or shut down mid-transfer
        elif len(present) == len(self.manifest.files):
            state = PRESENT_UNVERIFIED
        else:
            state = ABSENT
        return {
            "track": self.manifest.track,
            "repo_id": self.manifest.repo_id,
            "revision": self.manifest.revision,
            "state": state,
            "bytes_total": self.manifest.total_bytes,
            "files_present": len(present),
            "files_total": len(self.manifest.files),
            "error_kind": data.get("error_kind") if state not in {VERIFIED, ABSENT, PRESENT_UNVERIFIED} else None,
            "diagnostic": data.get("diagnostic") if state not in {VERIFIED, ABSENT, PRESENT_UNVERIFIED} else None,
            "next_attempt_at": data.get("next_attempt_at") if state in RETRYABLE else None,
            "attempts": int(data.get("attempts") or 0),
            "verified_at": data.get("verified_at") if state == VERIFIED else None,
            "owned_elsewhere": state == DOWNLOADING and not self._holding,
        }

    def is_verified(self) -> bool:
        return self._receipt_matches(self._read())

    # --- one attempt ---------------------------------------------------------------------------------------------
    def _verify(self) -> tuple[list[str], list[str]]:
        """(missing_or_short, corrupt) files, by streaming hash. Called only while holding the track lock."""
        missing, corrupt = [], []
        for f in self.manifest.files:
            st = self._stat(f)
            if st is None or st.st_size != f.size:
                missing.append(f.path)
            elif _sha256(self.snapshot_root / f.path) != f.sha256:
                corrupt.append(f.path)
        return missing, corrupt

    def _fail(self, state: str, kind: str, diagnostic: str) -> dict:
        data = self._read()
        failures = int(data.get("failures") or 0) + 1 if state in RETRYABLE else 0
        delay = self._backoff[min(failures, len(self._backoff)) - 1] if state in RETRYABLE else None
        return self._write(
            state=state,
            error_kind=kind,
            diagnostic=_scrub(diagnostic),
            failures=failures,
            next_attempt_at=(self._clock() + delay) if delay is not None else None,
        )

    def _settle(self) -> dict:
        missing, corrupt = self._verify()
        if missing or corrupt:
            detail = ", ".join(f"{p} (incomplete)" for p in missing) or ", ".join(
                f"{p} (hash mismatch)" for p in corrupt
            )
            return self._fail(INVALID, "integrity", f"Checkpoint files do not match the pinned manifest: {detail}")
        try:
            check_static_contract(self.manifest, self.snapshot_root)
        except ContractMismatch as exc:
            return self._fail(INVALID, "contract", f"Checkpoint contract mismatch: {exc}")
        stats = {f.path: [s.st_size, s.st_mtime_ns] for f in self.manifest.files if (s := self._stat(f))}
        return self._write(
            state=VERIFIED,
            error_kind=None,
            diagnostic=None,
            failures=0,
            next_attempt_at=None,
            verified_at=self._clock(),
            verified_files=stats,
        )

    def provision_once(self, *, force: bool = False) -> dict:
        """One bounded attempt. Returns ``status()`` afterwards. ``force`` is the explicit user retry: it clears a
        terminal state and re-fetches files whose bytes failed verification."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if not self._lock.acquire():
            return self.status()  # another instance owns this track; it will finish or release on exit
        self._holding = True
        try:
            data = self._read()
            if self._receipt_matches(data) and not force:
                return self.status()
            if data.get("state") == INVALID and not force:
                return self.status()  # terminal: never retried automatically
            self._write(attempts=int(data.get("attempts") or 0) + 1, state=data.get("state") or ABSENT)
            missing, corrupt = self._verify()
            if corrupt and not force:
                self._fail(
                    INVALID, "integrity", f"Cached checkpoint files fail their pinned hashes: {', '.join(corrupt)}"
                )
                return self.status()
            fetch = [f for f in self.manifest.files if f.path in missing or f.path in corrupt]
            if fetch:
                needed = sum(f.size for f in fetch) + DISK_MARGIN_BYTES
                if self._free_bytes(self.cache_dir) < needed:
                    self._fail(
                        INSUFFICIENT_RESOURCES, "disk_space", f"Needs about {needed // 2**20} MB free disk space"
                    )
                    return self.status()
                if not self._memory_ok():
                    self._fail(INSUFFICIENT_RESOURCES, "memory", "System memory is below the safe floor; deferred")
                    return self.status()
                if self._offline():
                    self._fail(WAITING_FOR_NETWORK, "offline", "Offline mode is set (HF_HUB_OFFLINE); waiting")
                    return self.status()
                self._write(state=DOWNLOADING, error_kind=None, diagnostic=None, next_attempt_at=None)
                for f in fetch:
                    try:
                        self._fetch(
                            self.manifest.repo_id, self.manifest.revision, f.path, self.cache_dir, f.path in corrupt
                        )
                    except Exception as exc:  # noqa: BLE001 -- every failure is classified and recorded, never swallowed
                        state, kind = classify(exc)
                        self._fail(state, kind, f"{f.path}: {type(exc).__name__}: {exc}")
                        return self.status()
            self._settle()
            return self.status()
        finally:
            self._holding = False
            self._lock.release()


def _memory_ok() -> bool:
    """Downloads load no model, but they should not start while the machine is already below the inc-610 pause
    floor. An unavailable probe never blocks provisioning."""
    try:
        from app.backend.embeddings.resources import ResourcePolicy, measure

        snapshot = measure()
        return not ResourcePolicy.for_machine(snapshot).should_pause(snapshot)
    except Exception:  # noqa: BLE001  # nosec B110 -- a missing probe must not block provisioning
        return True
