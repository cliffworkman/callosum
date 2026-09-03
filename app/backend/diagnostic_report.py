"""Small privacy-safe diagnostics intended for direct copy/paste into a bug report."""

from __future__ import annotations

import os
import platform
from datetime import UTC, datetime
from typing import Any


def diagnostic_report(
    *, code: str, feature: str, message: str, suggested_action: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build a bounded report without paths, secrets, document content, or raw identifiers."""

    safe_details = {
        str(key): value
        for key, value in (details or {}).items()
        if value is None or isinstance(value, (bool, int, float, str))
    }
    return {
        "code": code,
        "feature": feature,
        "message": message,
        "suggested_action": suggested_action,
        "callosum_version": (os.getenv("CALLOSUM_APP_VERSION") or "development").strip(),
        "platform": f"{platform.system() or 'unknown'} {platform.machine() or 'unknown'}",
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "details": safe_details,
    }
