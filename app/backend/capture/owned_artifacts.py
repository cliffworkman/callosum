"""The server-owned allowlist seam for Import Queue operations (#61).

A route parameter is a CLAIM about which artifact the user means. It is not filesystem authority. This module turns the claim
into authority the only way the design allows: by finding the same identifier among the artifacts Callosum itself owns and
currently holds in the Import Queue, and returning **the stored value -- never the request string**.

    request string      = lookup claim (syntax-checked, then only ever compared)
    stored active ID    = filesystem authority (returned; used for every later DB, path and sidecar step of the action)

The allowlist is the set of active (non-promoted) artifacts, matching the capability being exercised: promoted artifacts
remain in persistence as provenance but are no longer queue operands. Once an action has resolved an owned ID it must keep
using that ID -- never switch back to the route string.
"""

from __future__ import annotations

import contextlib

from sqlalchemy import Connection

from app.backend.capture.trusted_paths import is_canonical_id
from app.backend.persistence import provisional_artifacts_repo


def resolve_owned_queue_artifact_id(conn: Connection, requested_id: str) -> str | None:
    """The stored identifier of the active Import Queue artifact the caller named, or ``None``.

    ``requested_id`` must already be canonical (``uuid4().hex``); anything else is answered exactly like an unknown artifact.
    The scan streams the allowlist cursor and stops at the first match.
    """
    if not is_canonical_id(requested_id):
        return None
    with contextlib.closing(provisional_artifacts_repo.iter_active_ids(conn)) as active_ids:
        for stored_id in active_ids:
            if stored_id == requested_id:
                return stored_id
    return None
