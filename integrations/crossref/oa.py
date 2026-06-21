"""Crossref open-access location — read a license + a direct PDF link from the (cached) Crossref work.

Crossref does not assert open access the way OpenAlex/DOAJ/Europe PMC do. So we are conservative: we return
an ``OaLocation`` **only** when the registered work carries a license (openness asserted by the metadata, not
guessed by us) AND a direct https PDF full-text ``link``. Reuses the existing ``CrossrefClient`` (and its DOI
cache via ``external_api_cache``) — no extra fetch. Returns ``OaLocation`` or None; never raises.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection

from app.backend.acquisition.registry import OaColor, OaLocation, PaperRef
from integrations.api_cache import get_cached
from integrations.crossref.adapter import CROSSREF_PROVIDER, CrossrefClient

CROSSREF_OA_SOURCE = "crossref"


def crossref_oa_location(conn: Connection, ref: PaperRef, *, client: CrossrefClient | None = None) -> OaLocation | None:
    if not ref.doi:
        return None
    client = client or CrossrefClient()
    doi = ref.doi.strip().lower()
    resolution = client.resolve_doi(conn, doi)  # populates / reads the crossref DOI cache
    if not resolution.resolved:
        return None
    cached = get_cached(conn, CROSSREF_PROVIDER, doi)
    if cached is None:
        return None
    body = cached["response_json"]
    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(message, dict):
        return None
    return _oa_from_message(message)


def _oa_from_message(message: dict[str, Any]) -> OaLocation | None:
    pdf_url = _pdf_link(message.get("link"))
    if pdf_url is None:
        return None
    license_url = _license_url(message.get("license"))
    if license_url is None:
        return None  # no asserted license → we do not guess OA
    color: OaColor = "gold" if "creativecommons.org" in license_url.lower() else "bronze"
    try:
        return OaLocation(
            pdf_url=pdf_url, oa_color=color, version="vor", source=CROSSREF_OA_SOURCE, license=license_url
        )
    except ValueError:
        return None


def _pdf_link(links: Any) -> str | None:
    if not isinstance(links, list):
        return None
    for link in links:
        if not isinstance(link, dict):
            continue
        url = link.get("URL")
        ctype = str(link.get("content-type") or "").lower()
        if (
            isinstance(url, str)
            and url.startswith("https://")
            and (ctype == "application/pdf" or url.lower().endswith(".pdf"))
        ):
            return url
    return None


def _license_url(licenses: Any) -> str | None:
    if not isinstance(licenses, list):
        return None
    for lic in licenses:
        if isinstance(lic, dict) and isinstance(lic.get("URL"), str) and lic["URL"]:
            return lic["URL"]
    return None
