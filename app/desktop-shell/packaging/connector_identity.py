"""Pure validation helpers for `connector/identity.json` (#61 Phase 1 store-readiness).

One definition of "a valid browser-capture identity", shared by the NSIS generator, the extension package
builder and the tests, so none of them carries its own copy of the rules. No I/O beyond `load_identity`, and
nothing here decides *release policy* (that lives in check_capture_release.py);
this only says whether the identity that IS configured is well-formed.

The rules mirror what the browsers and the connector actually enforce:

* an extension ID is exactly 32 characters from `a`-`p` (Chromium derives it from a SHA-256 prefix, mapping each
  hex nibble onto `a`-`p`), so uppercase, digits and other lengths can never be a real ID;
* `allowed_origins` entries are exact IDs (the browsers accept no wildcards), and the connector host compares
  them by exact match too, so a duplicate is harmless but is rejected here anyway to keep the generated manifest
  free of accidental repetition;
* the dev extension ID is quarantined: it must never appear in the production list.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

EXTENSION_ID_LENGTH = 32
EXTENSION_ID_ALPHABET = "abcdefghijklmnop"

_EXTENSION_ID_RE = re.compile(rf"^[{EXTENSION_ID_ALPHABET}]{{{EXTENSION_ID_LENGTH}}}$")
# Chromium's native-messaging host-name rule: lowercase alphanumerics, underscores and single dots, never a
# leading/trailing dot and never two dots in a row.
_HOST_NAME_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")


def load_identity(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_valid_extension_id(value: object) -> bool:
    return isinstance(value, str) and _EXTENSION_ID_RE.fullmatch(value) is not None


def is_valid_host_name(value: object) -> bool:
    return isinstance(value, str) and _HOST_NAME_RE.fullmatch(value) is not None


def allowed_origins(extension_ids: list[str]) -> list[str]:
    """The exact `allowed_origins` strings for these IDs, in the configured order."""
    return [f"chrome-extension://{extension_id}/" for extension_id in extension_ids]


def validate_identity(identity: dict[str, Any]) -> list[str]:
    """Every problem with this identity, as human-readable strings; an empty list means it is well-formed.

    An empty `production_extension_ids` is *valid* here: whether a given build may ship with none is release
    policy, decided elsewhere.
    """
    problems: list[str] = []

    if not isinstance(identity.get("protocol_version"), int):
        problems.append("protocol_version must be an integer")

    host = identity.get("native_host_name")
    dev_host = identity.get("dev_native_host_name")
    for label, name in (("native_host_name", host), ("dev_native_host_name", dev_host)):
        if not is_valid_host_name(name):
            problems.append(f"{label} {name!r} is not a valid native-messaging host name")
    if host == dev_host:
        problems.append("native_host_name and dev_native_host_name must differ")

    dev_id = identity.get("dev_extension_id")
    if not is_valid_extension_id(dev_id):
        problems.append(f"dev_extension_id {dev_id!r} is not a valid {EXTENSION_ID_LENGTH}-char extension id")

    production = identity.get("production_extension_ids")
    if not isinstance(production, list):
        problems.append("production_extension_ids must be a list")
        return problems

    seen: set[str] = set()
    for extension_id in production:
        if not is_valid_extension_id(extension_id):
            problems.append(
                f"{extension_id!r} is not a valid {EXTENSION_ID_LENGTH}-char extension id "
                f"({EXTENSION_ID_LENGTH} lowercase letters a-p)"
            )
            continue
        if extension_id in seen:
            problems.append(f"duplicate production extension id {extension_id!r}")
        seen.add(extension_id)
        if extension_id == dev_id:
            problems.append("the dev extension id must never appear in production_extension_ids")

    preview = identity.get("preview_extension_id")
    if preview is not None:
        try:
            public = base64.b64decode(identity["preview_extension_public_key_base64"], validate=True)
            derived = "".join(chr(97 + int(c, 16)) for c in hashlib.sha256(public).hexdigest()[:32])
            if preview != derived or preview == dev_id or preview in production:
                problems.append("preview identity must derive from its own public key, separate from dev/store")
        except (KeyError, ValueError, TypeError):
            problems.append("preview public key is invalid")
    return problems
