"""Canonical researcher-identity primitives.

An ORCID iD is a first-class Callosum identity.  Provider records such as
OpenAlex may enrich that identity, but they do not make the identity valid.
"""

from __future__ import annotations

import re
import unicodedata

_ORCID_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", re.IGNORECASE)
_ORCID_URL_RE = re.compile(r"^https?://(?:www\.)?orcid\.org/", re.IGNORECASE)


class InvalidOrcid(ValueError):
    """A supplied ORCID iD is malformed or has the wrong ISO 7064 check digit."""


def normalize_orcid(value: str | None) -> str | None:
    """Return a canonical bare ORCID iD, validating its MOD 11-2 check digit.

    Accepts the ordinary bare and ``orcid.org`` URL forms.  Blank input is
    represented as ``None``; non-blank invalid input raises ``InvalidOrcid``.
    """

    text = unicodedata.normalize("NFKC", value or "").strip()
    if not text:
        return None
    text = _ORCID_URL_RE.sub("", text).strip().strip("/").upper()
    if not _ORCID_RE.fullmatch(text) or not _orcid_checksum_valid(text):
        raise InvalidOrcid("Enter a valid ORCID iD, such as 0000-0002-1825-0097.")
    return text


def orcid_is_valid(value: str | None) -> bool:
    try:
        return normalize_orcid(value) is not None
    except InvalidOrcid:
        return False


def normalize_person_name(value: str | None) -> str:
    """Comparison form tolerant of case, diacritics, punctuation, and spacing."""

    decomposed = unicodedata.normalize("NFKD", value or "").casefold()
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[^\W_]+", without_marks, flags=re.UNICODE))


def _orcid_checksum_valid(orcid: str) -> bool:
    digits = orcid.replace("-", "")
    total = 0
    for char in digits[:15]:
        total = (total + int(char)) * 2
    result = (12 - (total % 11)) % 11
    expected = "X" if result == 10 else str(result)
    return digits[-1].upper() == expected
