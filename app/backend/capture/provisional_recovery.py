"""Startup recovery and permanent deletion of provisional artifacts (#61).

Split out of ``provisional.py`` (rule #1, 600-line cap). Both operate on the durable state the core module writes
(the queue directory, the provenance sidecars and the `provisional_artifacts` rows) and never on identity evidence.

Seam policy: the core module's path helpers are reached through the module (`provisional.queue_dir`), not imported by
name, so replacing one on `app.backend.capture.provisional` still affects recovery. The core module never imports this
one (it would be circular); it exposes these names lazily for backwards-compatible imports.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Connection, Engine

from app.backend.capture import provisional
from app.backend.capture.owned_artifacts import resolve_owned_queue_artifact_id
from app.backend.capture.trusted_paths import is_plain_file, queue_filename_id, queued_pdf_entry_path
from app.backend.persistence import capture_events_repo, provisional_artifacts_repo
from app.backend.persistence.sqlite_retry import run_write

# --- startup recovery -------------------------------------------------------------------------------


def recover_at_startup(engine: Engine, library_root: Path) -> None:
    """Reconcile `_Import Queue/*.pdf` against `provisional_artifacts`. Called once at backend
    startup. Never deletes a real, unrecoverable user artifact -- see the plan's enumerated crash
    windows. A file with no matching row is ADOPTED (using the sidecar if present, else an honest
    "context unrecoverable" record), never discarded, unless its content hash proves it is a
    redundant physical copy of bytes already tracked under a different artifact_id."""
    directory = provisional.queue_dir(library_root)
    if not directory.is_dir():
        return

    with engine.connect() as conn:
        known_ids = provisional_artifacts_repo.all_ids(conn)
        known_hashes = {
            str(row["content_hash"]): str(row["id"])
            for row in (provisional_artifacts_repo.get(conn, i) for i in known_ids)
            if row is not None
        }

    for pdf_file in sorted(directory.iterdir()):
        # A directory entry is identity ONLY through its exact canonical name (`<32 lowercase hex>.pdf`) and only if it is
        # itself a regular file. Anything else -- a stray file, an upper-case or oddly named PDF, a symlink -- is not a
        # Callosum queue entry: it is left untouched (never adopted, followed or deleted).
        artifact_id = queue_filename_id(pdf_file.name)
        if artifact_id is None or not is_plain_file(pdf_file):
            continue
        if artifact_id in known_ids:
            continue  # legitimate: row exists, inference may simply not have run yet -- left as-is

        try:
            data = pdf_file.read_bytes()
        except OSError:
            continue
        content_hash = sha256(data).hexdigest()

        if content_hash in known_hashes:
            # A redundant physical copy of bytes already tracked under a different artifact_id --
            # nothing is lost by removing the duplicate file itself.
            pdf_file.unlink(missing_ok=True)
            continue

        sidecar = provisional.sidecar_path(library_root, artifact_id)
        first_event = None
        if is_plain_file(sidecar):  # a symlinked sidecar is not followed
            try:
                payload = json.loads(sidecar.read_text(encoding="utf-8"))
                first_event = payload.get("first_capture_event")
            except (OSError, json.JSONDecodeError):
                first_event = None

        def _adopt(
            conn: Connection,
            artifact_id=artifact_id,
            content_hash=content_hash,
            pdf_file=pdf_file,
            first_event=first_event,
        ) -> None:
            provisional_artifacts_repo.create(
                conn,
                artifact_id=artifact_id,
                content_hash=content_hash,
                pdf_path=str(pdf_file),
                provenance_sidecar_state="ok" if first_event else "pending",
            )
            capture_events_repo.create(
                conn,
                capture_event_id=(first_event or {}).get("capture_event_id") or uuid4().hex,
                artifact_id=artifact_id,
                source_url=(first_event or {}).get("source_url"),
                captured_at_client=(first_event or {}).get("captured_at_client"),
                original_filename=(first_event or {}).get("original_filename"),
                producer_kind=(first_event or {}).get("producer_kind"),
            )

        run_write(engine, _adopt)


# --- permanent deletion -------------------------------------------------------------------------------


def permanently_delete_provisional_artifact(engine: Engine, artifact_id: str, library_root: Path) -> bool:
    """Delete the queue PDF, the sidecar, and the DB rows (cascading to capture_events) of an ACTIVE Import Queue artifact.
    Never time-based -- only explicit user action reaches this.

    `artifact_id` is the caller's CLAIM, resolved once to a server-owned active queue ID. Every filesystem step derives
    from that owned ID -- the persisted `pdf_path` column is not authority, so a poisoned value can never make this delete
    anything outside the queue. The derived paths are directory ENTRIES: `unlink` removes the entry itself and never follows
    a symlink, so a symlink planted in the queue is removed as a link and its target is untouched.
    """
    with engine.connect() as conn:
        owned_id = resolve_owned_queue_artifact_id(conn, artifact_id)
    if owned_id is None:
        return False

    queue_entry = queued_pdf_entry_path(provisional.queue_dir(library_root), owned_id)
    if queue_entry.is_symlink() or is_plain_file(queue_entry):
        queue_entry.unlink(missing_ok=True)
    provisional.sidecar_path(library_root, owned_id).unlink(missing_ok=True)

    def _delete(conn: Connection) -> bool:
        return provisional_artifacts_repo.delete_artifact(conn, owned_id)

    return run_write(engine, _delete)
