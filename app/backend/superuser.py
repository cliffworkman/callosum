"""Superuser identification (accounts SP1 follow-on, inc 195): a verified-ORCID allowlist.

Split out of ``app_settings.py`` (Sync SP4d, inc 478) to keep that file under the 600-line cap — the
established leaf-module pattern (inc 137/220/262/264). Re-exported from ``app_settings.py`` so every existing
call site (``app_settings.is_superuser_orcid`` / ``app_settings.superuser_orcids``) keeps working unchanged.

A superuser is identified by their VERIFIED ORCID claim (from the signed-in session), matched against the
``CALLOSUM_SUPERUSER_ORCIDS`` env allowlist (comma/semicolon-separated bare iDs). Configured via the
gitignored ``.env`` — never hardcoded in the public repo. It is NOT self-asserted (you can't claim it via the
API). What being a superuser GATES is deferred — for now it's just an honest, verified flag.
"""

from __future__ import annotations

import os


def _normalize_orcid(value: str | None) -> str | None:
    """A bare ORCID iD (``0000-0002-2206-0325``) from a value that may be a full ``https://orcid.org/…`` URL.
    Uppercases the checksum X; returns None for blanks."""
    v = (value or "").strip()
    if not v:
        return None
    if "orcid.org/" in v:
        v = v.rsplit("orcid.org/", 1)[1]
    v = v.strip().strip("/").upper()
    return v or None


def superuser_orcids() -> set[str]:
    """The normalized superuser-ORCID allowlist from ``CALLOSUM_SUPERUSER_ORCIDS`` (comma/semicolon-separated)."""
    raw = os.getenv("CALLOSUM_SUPERUSER_ORCIDS", "")
    out: set[str] = set()
    for part in raw.replace(";", ",").split(","):
        n = _normalize_orcid(part)
        if n:
            out.add(n)
    return out


def is_superuser_orcid(orcid: str | None) -> bool:
    """True iff the (verified) ORCID iD is in the allowlist. Match is normalization-insensitive (URL vs bare; X case)."""
    n = _normalize_orcid(orcid)
    return bool(n and n in superuser_orcids())
