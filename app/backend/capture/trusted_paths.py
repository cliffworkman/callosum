"""Explicit filesystem trust boundaries for browser capture (#61).

Two rules, each stated once here instead of being re-derived at every call site:

1. **Network strings are syntax, not authority.** Callosum mints capture and provisional-artifact identifiers as
   ``uuid4().hex`` (32 lowercase hex characters). A route parameter is only ever a *lookup key*: it must first be
   syntactically a Callosum ID (:func:`is_canonical_id`), and the filesystem name of anything Callosum writes is
   derived from the server-minted ID held in server-owned state -- never from the route text
   (:func:`managed_capture_pdf_path`).
2. **A stored path is trusted only after it is resolved.** A queued PDF may be served only if, after following
   symlinks, it is a real file directly under the resolved Import Queue directory (:func:`resolve_queued_pdf`); a
   database value that points elsewhere, or a symlink inside the queue that targets elsewhere, is refused.

This module is a leaf: it imports nothing from the capture package.
"""

from __future__ import annotations

import re
from pathlib import Path

_CANONICAL_ID = re.compile(r"[0-9a-f]{32}")


def is_canonical_id(value: object) -> bool:
    """True only for a syntactically valid Callosum-minted identifier (``uuid4().hex``)."""
    return isinstance(value, str) and _CANONICAL_ID.fullmatch(value) is not None


def managed_capture_pdf_path(managed_root: Path, server_capture_id: str) -> Path:
    """The managed-library filename for an attached capture, derived from the SERVER-MINTED capture ID.

    Raises ``ValueError`` if the ID is not canonical -- which can only mean a programming error, because the value
    comes from server-owned state, not from a request.
    """
    if not is_canonical_id(server_capture_id):
        raise ValueError("a managed capture filename must derive from a server-minted capture ID")
    return managed_root / f"capture-{server_capture_id}.pdf"


def resolve_queued_pdf(stored_path: object, queue_root: Path) -> Path | None:
    """The queued PDF to serve, or ``None`` if it may not be served.

    Permitted only when the stored path, RESOLVED (symlinks followed), is a real file whose parent is the RESOLVED
    ``queue_root``. The caller serves the returned, resolved path -- never the raw stored value.
    """
    try:
        root = queue_root.resolve(strict=True)
        candidate = Path(str(stored_path)).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    if candidate.is_file() and candidate.parent == root:
        return candidate
    return None
