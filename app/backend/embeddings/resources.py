"""Memory headroom for local index builds: real OS measurements and a policy derived from this machine.

The earlier standalone guard approximated free commit as ``total RAM + swap - used RAM - used swap``. On Windows
that is wrong in both directions: the commit limit is RAM plus *every* paging file (which can grow), and commit
charge includes reserved-but-unpaged allocations that never appear as used RAM. ``GlobalMemoryStatusEx`` reports
the commit limit (``ullTotalPageFile``) and available commit (``ullAvailPageFile``) directly, so it is used there.
Linux reads ``MemAvailable`` from ``/proc/meminfo`` and macOS counts free + inactive + speculative pages from
``vm_stat``; with overcommit there is no hard commit limit to exhaust, so available physical memory binds.
Standard library only: the packaged runtime does not ship psutil.

No threshold assumes a 16 GB machine: every floor is the larger of a small absolute minimum and a fraction of this
machine's total memory, plus the measured (or, before the first load, estimated) working set of the worker.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess  # nosec B404 -- fixed /usr/bin/vm_stat argv on macOS only
import sys
from dataclasses import dataclass

MB = 1024 * 1024


@dataclass(frozen=True)
class ResourceSnapshot:
    total_physical_mb: int
    available_physical_mb: int
    commit_limit_mb: int | None  # None where the OS has no hard commit limit to report
    available_commit_mb: int | None
    source: str  # "GlobalMemoryStatusEx", "/proc/meminfo" or "vm_stat"

    def as_dict(self) -> dict:
        return {
            "total_physical_mb": self.total_physical_mb,
            "available_physical_mb": self.available_physical_mb,
            "commit_limit_mb": self.commit_limit_mb,
            "available_commit_mb": self.available_commit_mb,
            "source": self.source,
        }


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _windows_snapshot() -> ResourceSnapshot | None:
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
        return None
    return ResourceSnapshot(
        total_physical_mb=int(status.ullTotalPhys // MB),
        available_physical_mb=int(status.ullAvailPhys // MB),
        commit_limit_mb=int(status.ullTotalPageFile // MB),
        available_commit_mb=int(status.ullAvailPageFile // MB),
        source="GlobalMemoryStatusEx",
    )


def _linux_snapshot() -> ResourceSnapshot:
    fields: dict[str, int] = {}
    with open("/proc/meminfo", encoding="ascii") as handle:
        for line in handle:
            key, _, rest = line.partition(":")
            fields[key] = int(rest.split()[0])  # kB
    return ResourceSnapshot(
        total_physical_mb=fields["MemTotal"] // 1024,
        available_physical_mb=fields.get("MemAvailable", fields.get("MemFree", 0)) // 1024,
        commit_limit_mb=None,
        available_commit_mb=None,
        source="/proc/meminfo",
    )


def _macos_snapshot() -> ResourceSnapshot:
    total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    out = subprocess.run(["/usr/bin/vm_stat"], capture_output=True, text=True, timeout=5, check=True).stdout  # noqa: S603  # nosec B603
    page = int(re.search(r"page size of (\d+) bytes", out).group(1))  # type: ignore[union-attr]
    pages = {m.group(1): int(m.group(2)) for m in re.finditer(r"^Pages ([\w ]+):\s+(\d+)\.", out, re.M)}
    free = sum(pages.get(k, 0) for k in ("free", "inactive", "speculative"))
    return ResourceSnapshot(int(total // MB), int(free * page // MB), None, None, "vm_stat")


def measure() -> ResourceSnapshot:
    if sys.platform == "win32":
        snapshot = _windows_snapshot()
        if snapshot is not None:
            return snapshot
    if sys.platform == "darwin":
        return _macos_snapshot()
    return _linux_snapshot()


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def process_rss_mb(pid: int | None = None) -> int | None:
    """Current working set of ``pid`` (default: this process), or None if it cannot be read."""
    pid = pid or os.getpid()
    try:
        if sys.platform == "win32":
            kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi  # type: ignore[attr-defined]
            kernel32.OpenProcess.restype = ctypes.c_void_p
            handle = kernel32.OpenProcess(0x1000 | 0x0010, False, int(pid))  # QUERY_LIMITED_INFORMATION | VM_READ
            if not handle:
                return None
            try:
                counters = _ProcessMemoryCounters()
                counters.cb = ctypes.sizeof(counters)
                ok = psapi.GetProcessMemoryInfo(ctypes.c_void_p(handle), ctypes.byref(counters), counters.cb)
                return int(counters.WorkingSetSize // MB) if ok else None
            finally:
                kernel32.CloseHandle(ctypes.c_void_p(handle))
        if sys.platform.startswith("linux"):
            with open(f"/proc/{int(pid)}/statm", encoding="ascii") as handle:
                return int(handle.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") // MB
        if pid == os.getpid():
            import resource

            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // MB)  # macOS: bytes, peak
    except (OSError, ValueError, IndexError):
        return None
    return None


# Before the first measured load: Arctic S weights (~130 MB fp32) plus torch/tokenizer runtime and one 512-token
# batch. Replaced by the observed peak worker working set as soon as one attempt has run.
DEFAULT_WORKER_ESTIMATE_MB = 1200


@dataclass(frozen=True)
class ResourcePolicy:
    """Three floors on free memory, all relative to this machine.

    * ``start``: enough headroom to load the model and run one batch while leaving a reserve for the user's apps.
    * ``pause``: the worker finishes its batch, commits and exits so memory is returned (checked between batches).
    * ``stop``: the supervisor terminates its own worker immediately (backstop for a batch that spikes).
    """

    reserve_mb: int
    stop_mb: int

    @classmethod
    def for_machine(cls, snapshot: ResourceSnapshot) -> ResourcePolicy:
        total = snapshot.total_physical_mb
        return cls(reserve_mb=max(512, total // 20), stop_mb=max(256, total // 40))

    @property
    def pause_mb(self) -> int:
        return (self.reserve_mb + self.stop_mb) // 2

    def start_floor_mb(self, worker_need_mb: int) -> int:
        return worker_need_mb + self.reserve_mb

    def _free(self, snapshot: ResourceSnapshot) -> int:
        free = snapshot.available_physical_mb
        if snapshot.available_commit_mb is not None:
            free = min(free, snapshot.available_commit_mb)
        return free

    def can_start(self, snapshot: ResourceSnapshot, worker_need_mb: int) -> bool:
        return self._free(snapshot) >= self.start_floor_mb(worker_need_mb)

    def should_pause(self, snapshot: ResourceSnapshot) -> bool:
        """Checked by a running worker, whose own memory is already excluded from the free figures."""
        return self._free(snapshot) < self.pause_mb

    def must_stop(self, snapshot: ResourceSnapshot) -> bool:
        return self._free(snapshot) < self.stop_mb

    def as_dict(self) -> dict:
        return {"reserve_mb": self.reserve_mb, "pause_mb": self.pause_mb, "stop_mb": self.stop_mb}
