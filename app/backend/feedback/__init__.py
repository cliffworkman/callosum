"""In-app feedback reporter (inc 265) — bug reports + feature requests, assembled locally.

The subsystem writes a self-contained report bundle (`report.md` + an optional `screenshot.png`) under
``~/.callosum/feedback/`` and hands the user a prefilled ``mailto:`` draft. **The server never sends
anything** — no SMTP, no HTTP, no new egress channel (invariant #3): composing and sending stays in the
user's own mail client, and the exact payload is shown before it leaves.
"""

from app.backend.feedback.bundle import (
    FEEDBACK_KINDS,
    FeedbackBundle,
    build_mailto_url,
    decode_screenshot,
    feedback_root,
    render_report,
    write_bundle,
)
from app.backend.feedback.destination import (
    DESTINATION_EMAIL_MAX_LEN,
    resolved_destination,
    set_destination_email,
    stored_destination_email,
)
from app.backend.feedback.diagnostics import clean_client_diagnostics, server_diagnostics

__all__ = [
    "DESTINATION_EMAIL_MAX_LEN",
    "FEEDBACK_KINDS",
    "FeedbackBundle",
    "build_mailto_url",
    "clean_client_diagnostics",
    "decode_screenshot",
    "feedback_root",
    "render_report",
    "resolved_destination",
    "server_diagnostics",
    "set_destination_email",
    "stored_destination_email",
    "write_bundle",
]
