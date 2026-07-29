"""Where an in-app feedback report is addressed (inc 265).

**Blank by default.** callosum ships with no hard-coded maintainer address, so a report is never
pre-addressed to someone the user didn't choose — the same "defaults are the user's" posture as the
egress gate. The value is a plain preference (not a secret): it lives beside the other non-secret prefs
in the local settings file via ``app_settings.load_settings``/``save_settings``, and is kept *here*
rather than in ``app_settings.py`` so the feature stays self-contained (and that file stays well under
the 600-line cap).

``CALLOSUM_FEEDBACK_EMAIL`` is an env fallback, so a packaged/institutional build can ship a default
without touching the code.
"""

from __future__ import annotations

import os

from app.backend import app_settings

DESTINATION_EMAIL_MAX_LEN = 254  # RFC-5321 max address length; the boundary validator enforces it too
DESTINATION_ENV_VAR = "CALLOSUM_FEEDBACK_EMAIL"
_EMAIL_KEY = "feedback_email"


def stored_destination_email() -> str | None:
    """The UI-set destination address, or ``None`` if unset/blank."""
    value = app_settings.load_settings().get(_EMAIL_KEY)
    return value if isinstance(value, str) and value.strip() else None


def set_destination_email(email: str | None) -> None:
    """Persist the destination address; an empty/whitespace value clears it."""
    data = app_settings.load_settings()
    cleaned = (email or "").strip()
    if cleaned:
        data[_EMAIL_KEY] = cleaned
    else:
        data.pop(_EMAIL_KEY, None)
    app_settings.save_settings(data)


def resolved_destination() -> tuple[str, str | None]:
    """``(address, source)`` — the stored value wins over the env fallback. ``("", None)`` when unset."""
    stored = stored_destination_email()
    if stored:
        return stored, "ui"
    env = (os.getenv(DESTINATION_ENV_VAR) or "").strip()
    if env:
        return env, "env"
    return "", None
