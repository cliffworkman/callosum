"""Paper abstracts as source metadata: deterministic cleaning only (raw text is always kept alongside).

`papers.abstract` carries JATS markup (`<jats:title>Abstract</jats:title><jats:p>…`) that the paper-metadata embedding also
ingests. Cleaning is a pure text transform; it never paraphrases, and the raw field is what receipts hash.
"""

from __future__ import annotations

import hashlib
import html
import re

_TAG = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<jats:title>\s*abstract\s*</jats:title>", re.IGNORECASE)
_WS = re.compile(r"\s+")


def clean_abstract(raw: str | None) -> str:
    """Strip markup and the leading 'Abstract' title, unescape entities, collapse whitespace. Empty string if absent."""
    if not raw or not raw.strip():
        return ""
    text = _TITLE.sub(" ", raw)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    return _WS.sub(" ", text).strip()


def abstract_state(raw: str | None) -> str:
    """`present` or `absent`. An absent abstract never removes a paper from consideration."""
    return "present" if clean_abstract(raw) else "absent"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
