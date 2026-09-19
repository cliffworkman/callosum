"""Startup hooks for browser capture (#61), split out of ``app.py`` (rule #1, 600-line cap).

Both hooks are run from the FastAPI lifespan in ``app.py``. They share one posture: scoped to the canonical UI
instance only (never a Word-HTTPS or tunnel-target sibling), and NON-FATAL -- browser capture is an optional
integration, so an unrecoverable environment must never stop the rest of Callosum from starting.

Two lookups here are deliberately late-bound so tests (and any future seam) can replace them:

* ``pairing.ensure_pairing_secret`` is called through its module, never imported by name;
* ``recover_at_startup`` and ``library_dir`` are imported inside the ``try`` at call time, so an import failure is
  contained by the same handler as a runtime failure.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine

from app.backend.api.routers.health import UI_ROLE, reported_instance_role
from app.backend.capture import pairing

_log = logging.getLogger(__name__)


def ensure_capture_pairing_ready() -> None:
    """Mint the browser-capture pairing secret on startup, UI instances only (#61 Phase 2, Part 5).

    Stage 1 built ``pairing.ensure_pairing_secret()`` but nothing called it in production, so
    ``/capture/session`` 401'd for every host no matter how correctly it was paired -- there was no
    secret to pair against. This closes that gap the same way every other capture control is
    scoped: only the canonical UI backend ever creates it, matching `require_capture_boundary`'s own
    role gate, so a sibling (Word-HTTPS, tunnel-target) never touches the pairing file.

    A failure here (read-only filesystem, permissions, disk full) must fail CLOSED for browser
    capture only, never take down the rest of the app: capture is an optional integration, and
    every other Callosum feature already tolerates an absent pairing secret by design --
    `/capture/session` simply 401s with no secret to check against, which is exactly the state a
    failed mint leaves it in. Logged once, loudly, so a real failure is diagnosable rather than a
    silent "browser capture just doesn't work" report with no lead.
    """
    if reported_instance_role() != UI_ROLE:
        return
    try:
        pairing.ensure_pairing_secret()
    except OSError:
        _log.warning(
            "Browser capture is disabled: could not create the pairing secret at %s. "
            "The rest of Callosum is unaffected; /capture/session will 401 until this is resolved.",
            pairing.pairing_file_path(),
            exc_info=True,
        )


def recover_provisional_captures(engine: Engine) -> None:
    """Reconcile the Import Queue against ``provisional_artifacts`` on startup (#61 provisional
    ingestion). Adopts any queue PDF a prior run wrote to disk but never got a durable database row
    for (a crash between the file write and the commit) -- see ``provisional.recover_at_startup``'s
    own docstring for the full enumeration of crash windows. Same non-fatal, UI-only posture as
    ``ensure_capture_pairing_ready``: an unrecoverable environment must never block the rest of
    Callosum from starting, and recovery only matters on the instance that actually serves capture.
    """
    if reported_instance_role() != UI_ROLE:
        return
    try:
        from app.backend.acquisition.fetch import library_dir
        from app.backend.capture.provisional import recover_at_startup

        recover_at_startup(engine, library_dir())
    except Exception:
        _log.warning("Import Queue recovery failed at startup; continuing without it.", exc_info=True)
