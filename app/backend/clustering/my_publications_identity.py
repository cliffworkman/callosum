"""Identity establishment and OpenAlex enrichment for My Publications.

ORCID validity is local and authoritative for a Callosum identity. OpenAlex is
optional metadata enrichment and reports its linkage state separately.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection

from app.backend.diagnostic_report import diagnostic_report
from app.backend.persistence.profile_repo import get_profile
from app.backend.researcher_identity import InvalidOrcid, normalize_orcid


def resolve_identity_fetch(conn: Connection, *, author_client, force: bool):
    """Resolve identity and fetch works without writing through ``conn``."""

    profile = get_profile(conn)
    if not profile or not ((profile.get("display_name") or "").strip() or (profile.get("orcid") or "").strip()):
        return {"status": "no-identity"}, None, []
    if profile.get("my_publications_dismissed") and not force:
        return {"status": "dismissed"}, None, []
    try:
        canonical_orcid = normalize_orcid(profile.get("orcid"))
    except InvalidOrcid:
        return (
            _identity_failure(
                "invalid-orcid",
                "IDENTITY_ORCID_INVALID",
                "The saved ORCID iD is not structurally valid.",
                "Correct the ORCID iD and retry.",
                identity_established=False,
                details={"matching_method": "orcid", "orcid_checksum_valid": False, "stage": "identity_validation"},
            ),
            None,
            [],
        )

    names = [profile.get("display_name"), *(profile.get("name_variants") or [])]
    richer_resolver = getattr(author_client, "resolve_author_result", None)
    if callable(richer_resolver):
        resolution = richer_resolver(conn, orcid=canonical_orcid, names=names)
        author = resolution.author
        if author is None:
            return _resolution_failure(resolution, canonical_orcid), None, []
    else:
        author = author_client.resolve_author(conn, orcid=canonical_orcid, name=profile.get("display_name"))
    if author is None:
        if canonical_orcid:
            return (
                _identity_failure(
                    "enrichment-not-found",
                    "IDENTITY_ENRICHMENT_OPENALEX_NOT_FOUND",
                    "Your ORCID iD is saved as your Callosum identity, but no linked OpenAlex profile was found.",
                    "You can continue using Callosum; retry later to gather publications.",
                    identity_established=True,
                    details={"matching_method": "orcid", "orcid_checksum_valid": True, "stage": "profile_resolution"},
                ),
                None,
                [],
            )
        return {"status": "no-match", "name": (profile.get("display_name") or "").strip() or None}, None, []
    return _fetch_works(conn, author_client, author, profile, canonical_orcid)


def _resolution_failure(resolution, canonical_orcid: str | None) -> dict[str, Any]:
    established = canonical_orcid is not None
    details = _resolution_details(resolution, canonical_orcid)
    if resolution.state == "unavailable":
        return _identity_failure(
            "enrichment-failed",
            "IDENTITY_ENRICHMENT_OPENALEX_FAILED",
            "Your identity is saved, but OpenAlex could not be reached to gather publications."
            if established
            else "OpenAlex could not be reached to match that name.",
            "Check the internet connection and retry.",
            identity_established=established,
            details=details,
        )
    if resolution.state == "candidate_rejected":
        code = (
            "IDENTITY_OPENALEX_LINK_MISMATCH"
            if resolution.rejection_reason == "returned_orcid_mismatch"
            else "IDENTITY_OPENALEX_CANDIDATE_REJECTED"
        )
        return _identity_failure(
            "enrichment-link-mismatch" if established else "no-match",
            code,
            "Your identity is saved, but the OpenAlex candidate did not safely match it."
            if established
            else "OpenAlex returned candidates, but none safely matched that name.",
            "Check the name details and retry; use Copy diagnostics if this persists.",
            identity_established=established,
            details=details,
        )
    if established:
        return _identity_failure(
            "enrichment-not-found",
            "IDENTITY_ENRICHMENT_OPENALEX_NOT_FOUND",
            "Your ORCID iD is saved as your Callosum identity, but no linked OpenAlex profile was found.",
            "You can continue using Callosum; retry later to gather publications.",
            identity_established=True,
            details=details,
        )
    return _identity_failure(
        "no-match",
        "IDENTITY_NAME_NO_MATCH",
        "No unambiguous OpenAlex author matched that name.",
        "Enter your full published name or a valid ORCID iD, then retry.",
        identity_established=False,
        details=details,
    )


def _fetch_works(conn, author_client, author, profile, canonical_orcid):
    result_fetcher = getattr(author_client, "fetch_author_works_result", None)
    if callable(result_fetcher):
        result = result_fetcher(conn, author.author_id, refresh=True)
        if not result.complete:
            return (
                {
                    "status": "refresh-incomplete",
                    "name": author.display_name or (profile.get("display_name") or "").strip() or None,
                    "capped": bool(result.capped),
                    "identity_established": bool(canonical_orcid),
                    "enrichment_status": "linked",
                    "diagnostic": diagnostic_report(
                        code="IDENTITY_METADATA_UNAVAILABLE",
                        feature="My Publications identity",
                        message="OpenAlex linked the author, but the publications response was incomplete.",
                        suggested_action="Retry the refresh; no partial publication list was saved.",
                        details={"matching_method": author.matched_by, "stage": "works_fetch"},
                    ),
                },
                None,
                [],
            )
        works = list(result.works)
    else:
        works = author_client.fetch_author_works(conn, author.author_id, refresh=True)
    return None, author, works


def _resolution_details(resolution, canonical_orcid: str | None) -> dict[str, Any]:
    return {
        "matching_method": resolution.method,
        "orcid_checksum_valid": canonical_orcid is not None,
        "openalex_lookup_attempted": True,
        "candidate_count": resolution.candidate_count,
        "candidate_returned": resolution.candidate_returned,
        "candidate_orcid_match": resolution.candidate_orcid_match,
        "candidate_name_match": resolution.candidate_name_match,
        "rejection_reason": resolution.rejection_reason,
        "stage": "profile_resolution",
    }


def _identity_failure(
    status: str,
    code: str,
    message: str,
    suggested_action: str,
    *,
    identity_established: bool,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "identity_established": identity_established,
        "enrichment_status": "failed" if "FAILED" in code or "UNAVAILABLE" in code else "not_linked",
        "diagnostic": diagnostic_report(
            code=code,
            feature="My Publications identity",
            message=message,
            suggested_action=suggested_action,
            details=details,
        ),
    }
