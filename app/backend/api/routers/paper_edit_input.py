"""Normalise a Details-pane edit request into the dict ``build_paper_update`` consumes (inc 214 split).

Extracted verbatim from ``routers/papers.py`` (which crossed the 600-line cap when the inc-214 extra-URLs
field landed). These are the request-side validators/normalisers: strip strings (""→None clears a field),
enforce caps (rule #4), and reject reserved keys in the generic "More" passthrough. ``edits_from_request``
is the only public entry; it is duck-typed on the request (``model_fields_set`` + ``getattr``) so it needn't
import ``PaperUpdateRequest`` (no import cycle with ``papers.py``).
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from app.backend.metadata.paper_edits import RESERVED_CSL_KEYS

# Caps for the generic "More" passthrough (free-form scalar csl fields a DOI populated). The
# named core fields carry their own length caps; the generic patch is the one place arbitrary
# keys arrive, so it is bounded explicitly (rule #4: validate untrusted input).
CSL_PATCH_MAX_KEYS = 60
CSL_PATCH_KEY_MAX_LEN = 64
CSL_PATCH_VALUE_MAX_LEN = 4000
AUTHOR_MAX_LEN = 1000
URL_MAX_LEN = 2000
_CSL_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def edits_from_request(request: Any) -> dict[str, Any]:
    """Normalise the user-set fields into the dict build_paper_update consumes.

    Strings are stripped with ""→None (clears the field); title must stay non-empty; the generic
    `csl` passthrough is key/value-validated. Only fields in model_fields_set are included.
    """
    fields = request.model_fields_set
    edits: dict[str, Any] = {}
    for name in fields:
        value = getattr(request, name)
        if name == "title":
            title = (value or "").strip()
            if not title:
                raise HTTPException(status_code=422, detail="Title must not be empty")
            edits["title"] = title
        elif name in ("year", "month", "day"):
            edits[name] = value
        elif name in ("authors", "translators"):
            edits[name] = _clean_authors(value)
        elif name == "extra_urls":
            edits["extra_urls"] = _clean_urls(value)
        elif name == "csl":
            edits["csl"] = _validate_csl_patch(value)
        else:
            edits[name] = _norm_str(value)
    return edits


def _norm_str(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_authors(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    cleaned: list[str] = []
    for author in value:
        text = (author or "").strip()
        if not text:
            continue
        if len(text) > AUTHOR_MAX_LEN:
            raise HTTPException(status_code=422, detail="Author name exceeds the maximum length")
        cleaned.append(text)
    return cleaned


def _clean_urls(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    cleaned: list[str] = []
    for url in value:
        text = (url or "").strip()
        if not text:
            continue
        if len(text) > URL_MAX_LEN:
            raise HTTPException(status_code=422, detail="URL exceeds the maximum length")
        if not (text.startswith("http://") or text.startswith("https://")):
            raise HTTPException(status_code=422, detail="URL must start with http:// or https://")
        cleaned.append(text)
    return cleaned


def _validate_csl_patch(value: dict[str, str | None] | None) -> dict[str, str | None] | None:
    if value is None:
        return None
    if len(value) > CSL_PATCH_MAX_KEYS:
        raise HTTPException(status_code=422, detail="Too many additional fields")
    cleaned: dict[str, str | None] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or len(key) > CSL_PATCH_KEY_MAX_LEN or not _CSL_KEY_RE.match(key):
            raise HTTPException(status_code=422, detail="Invalid additional-field name")
        if key in RESERVED_CSL_KEYS:
            raise HTTPException(
                status_code=422, detail=f"'{key}' is edited through its own field, not the additional fields"
            )
        if raw is not None:
            if not isinstance(raw, str) or len(raw) > CSL_PATCH_VALUE_MAX_LEN:
                raise HTTPException(status_code=422, detail="Additional-field value is invalid or too long")
            raw = raw.strip() or None
        cleaned[key] = raw
    return cleaned
