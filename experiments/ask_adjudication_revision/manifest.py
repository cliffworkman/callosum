"""Hash only this package's implementation, never external experiment artifacts."""

from pathlib import Path

from . import VERSION
from .core import sha


def implementation_manifest():
    root = Path(__file__).resolve().parent
    return {
        "package": "ask_adjudication_revision",
        "version": VERSION,
        "real_study_enabled": False,
        "files": {path.relative_to(root).as_posix(): sha(path.read_bytes()) for path in sorted(root.rglob("*.py"))},
    }
