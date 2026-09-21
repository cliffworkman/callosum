"""Explicit filesystem authority for browser capture (#61).

The invariant, stated once here instead of re-derived at every call site:

    Managed filesystem paths derive from Callosum-owned identity -- never from request text and never from a
    persisted path string.

Three kinds of value are kept apart:

* **A request string is a lookup CLAIM.** Route parameters are only ever compared against server-owned identifiers
  (``owned_artifacts.resolve_owned_queue_artifact_id``); the request string itself never becomes part of a path.
* **A Callosum-owned identifier is filesystem authority.** Identifiers are ``uuid4().hex`` (32 lowercase hex characters).
  Every constructor below re-checks that shape at the actual filename-construction boundary, so the invariant survives
  future call-site refactors.
* **A directory entry is authority only through its exact canonical name** (:func:`queue_filename_id`), so a recovery
  scan never treats an arbitrary file name as identity.

Two filesystem CAPABILITIES are deliberately separate, because they are not the same permission:

* *entry* paths (:func:`queued_pdf_entry_path`) name a directory entry lexically. They are safe to **unlink** -- removing
  an entry never follows a symlink -- and are NOT safe to read, serve or copy.
* *read* paths (:func:`queued_pdf_read_path`) are safe to **follow**: the entry is a plain regular file (not a symlink)
  whose resolved parent is the resolved queue directory.

The Library root and its subdirectories are Callosum-configured local paths (an intentional filesystem authority owned by
the user), not request input. This module is a leaf: it imports nothing from the capture package.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

_CANONICAL_ID = re.compile(r"[0-9a-f]{32}")
_QUEUE_FILENAME = re.compile(r"([0-9a-f]{32})\.pdf")


def is_canonical_id(value: object) -> bool:
    """True only for a syntactically valid Callosum-minted identifier (``uuid4().hex``)."""
    return isinstance(value, str) and _CANONICAL_ID.fullmatch(value) is not None


def require_canonical_id(value: object) -> str:
    """Return ``value`` if it is a canonical identifier, else raise ``ValueError``.

    Path constructors call this on their own input: reaching it with a non-canonical value is a programming error
    (the value should have come from server-owned state), never a request the caller may retry.
    """
    if not is_canonical_id(value):
        raise ValueError("a managed filename must derive from a Callosum-minted identifier")
    return str(value)


def queue_filename_id(name: str) -> str | None:
    """The artifact identity encoded by an Import Queue directory entry name, or ``None``.

    Only the exact form ``<32 lowercase hex>.pdf`` qualifies. Anything else -- another extension, upper-case hex, extra
    characters, a hidden temp file -- is not an identity and must be ignored (never adopted, followed or deleted).
    """
    match = _QUEUE_FILENAME.fullmatch(name)
    return match.group(1) if match else None


def is_plain_file(path: Path) -> bool:
    """True if ``path`` is itself a regular file: a symlink (even one pointing at a regular file) is not."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def managed_capture_pdf_path(managed_root: Path, server_capture_id: str) -> Path:
    """The managed-library filename for an attached capture, derived from the SERVER-MINTED capture ID."""
    return managed_root / f"capture-{require_canonical_id(server_capture_id)}.pdf"


def queued_pdf_entry_path(queue_root: Path, owned_id: str) -> Path:
    """The lexical direct child ``<queue_root>/<owned_id>.pdf``.

    Safe to UNLINK (``Path.unlink`` removes the entry itself and never follows a symlink). It is NOT safe to read, serve or
    copy -- use :func:`queued_pdf_read_path` for that.
    """
    return queue_root / f"{require_canonical_id(owned_id)}.pdf"


def queued_pdf_read_path(queue_root: Path, owned_id: str) -> Path | None:
    """The queued PDF to read/serve/copy, or ``None`` if it may not be followed.

    Requires the derived entry to be a plain regular file (not a symlink) whose resolved parent is the resolved queue
    directory. The caller uses the returned, resolved path.
    """
    entry = queued_pdf_entry_path(queue_root, owned_id)
    if not is_plain_file(entry):
        return None
    try:
        root = queue_root.resolve(strict=True)
        resolved = entry.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved if resolved.parent == root else None
