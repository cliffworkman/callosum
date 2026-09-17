"""Process-local offline/archive guard; not an OS security boundary."""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

from .core import BoundaryError

_active = False
_installed = False
_forbidden = (
    "claim-representation-isolation",
    "sealed_arm_key",
    "blinded_adjudication_packet",
    "treatment_inputs.json",
    "arm0_outputs",
    "arm1_outputs",
    "arm2_outputs",
    "arm0_wire",
    "arm1_wire",
    "arm2_wire",
    "source_anchor_audit",
    "field_availability",
)
_modules = ("torch", "transformers", "sentence_transformers", "google.genai", "app.backend")


def _audit(event, args):
    if not _active:
        return
    if event in ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "subprocess.Popen", "os.system"):
        raise BoundaryError("OFFLINE_EXECUTION_ONLY")
    if event == "import" and any(args[0] == m or args[0].startswith(m + ".") for m in _modules):
        raise BoundaryError("MODEL_PRODUCTION_IMPORT_BLOCKED")
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.fsdecode(args[0]).replace("\\", "/").lower()
        if any(token in path for token in _forbidden) or "/sealed/" in path:
            raise BoundaryError("ARCHIVE_ACCESS_BLOCKED")
        # Reject writes to production even if accidental code is added later.
        mode, flags = args[1:3]
        writing = (mode and any(c in mode for c in "wax+")) or (flags and flags & (os.O_WRONLY | os.O_RDWR))
        if writing and "/app/" in str(Path(path).absolute()).replace("\\", "/"):
            raise BoundaryError("PRODUCTION_WRITE_BLOCKED")


@contextmanager
def offline_guard():
    global _active, _installed
    if not _installed:
        sys.addaudithook(_audit)
        _installed = True
    previous = _active
    _active = True
    try:
        yield
    finally:
        _active = previous
