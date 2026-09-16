"""Browser capture → the canonical Callosum admission path (#61 Phase 1).

This is an **adapter, not a new identity system**. Every decision that matters — what counts as the
same work, what may be written, what gets indexed — is delegated to the shared substrate hardened in
the previous increment. There is deliberately no fourth resolver here.

What this module owns is the two judgments that are genuinely capture-specific:

1. **When is generic page metadata safe to admit at all?** A DOI is a stable identifier and goes
   straight to ``add_paper_by_doi``. Without one, identity would rest on ``title_year_author`` — plain
   equality over bibliographic fields that are **not unique**, resolved with ``.limit(1)``. Silently
   taking the first row there is exactly the ambiguity collapse backlog #25 is open about, so Phase 1
   refuses instead: ``unresolved_review_required``, nothing created. Phase 1 does not pretend to have
   an ambiguity resolver it does not have.

2. **When may captured bytes touch an existing record?** See ``attachment_decision``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection

from app.backend.capture.envelope import CaptureEnvelope
from app.backend.metadata.doi import normalize_doi
from app.backend.metadata.doi_add import add_paper_by_doi
from app.backend.persistence.annotations_repo import count_all_annotations_for_paper
from app.backend.persistence.repository import create_paper, get_attachments_for_paper, resolve_library_state

# Provenance stamp. Follows the established "<feature>:<sub-source>" shape (cf. "registration:manual-local",
# "oa:<resolver>"). It is NOT in enrichment's crossref-update allowlist, so a later batch enrich cannot
# silently overwrite a user-captured record.
CAPTURE_SOURCE = "capture:browser"

# Machine-readable outcomes. The extension maps these to human text; the backend never ships prose
# that a UI would have to parse, and never leaks an exception string to an ordinary user.
STATUS_ADDED = "added"
STATUS_ALREADY_PRESENT = "already_present"
STATUS_IN_TRASH = "in_trash"
STATUS_UNRESOLVED = "unresolved_review_required"
STATUS_INVALID = "invalid_capture"

# Why a PDF was refused. Distinct from the admission status: metadata can succeed while bytes are declined.
PDF_OK = "ok"
PDF_NOT_OFFERED = "not_offered"
PDF_REVIEW_REQUIRED = "attachment_review_required"


@dataclass(frozen=True)
class AdmissionOutcome:
    """What happened to the metadata, and whether bytes may follow.

    ``pdf_accepted`` is decided HERE, before any bytes move, so a refusal is never discovered
    half-way through a mutation.
    """

    status: str
    paper_id: int | None = None
    created: bool = False
    pdf_accepted: bool = False
    pdf_reason: str = PDF_NOT_OFFERED
    title: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "paper_id": self.paper_id,
            "created": self.created,
            "pdf_accepted": self.pdf_accepted,
            "pdf_reason": self.pdf_reason,
            "title": self.title,
            "detail": self.detail,
        }


def attachment_decision(conn: Connection, paper_id: int, *, newly_created: bool) -> tuple[bool, str]:
    """May browser-supplied PDF bytes attach to this paper? ``(accepted, reason)``.

    A **newly created** paper is always safe: it has no attachments and no annotations by construction.

    An **existing** paper is safe only when it carries neither a PDF attachment nor ANY annotation:

    * an existing attachment would mean choosing between two PDFs, and Phase 1 never overwrites,
      replaces, demotes or deletes one — and there is no detach path to undo a mistake (#72);
    * an existing annotation is the subtler hazard. Rows with a NULL ``attachment_id`` render against
      whatever PDF the paper owns, and they are still written by supported workflows today (every
      bundle/share import does it deliberately). Attaching new bytes would light up old geometry over
      an unrelated document. Until that lifecycle is repaired, capture declines.

    The annotation check counts EVERY row, not the viewer-visible subset — see
    ``count_all_annotations_for_paper`` for why the viewer's filter is the wrong question here.
    """
    if newly_created:
        return True, PDF_OK
    for row in get_attachments_for_paper(conn, paper_id):
        content_type = (row["content_type"] or "").strip().lower()
        attachment_type = (row["attachment_type"] or "").strip().lower()
        if content_type == "application/pdf" or attachment_type == "pdf":
            return False, PDF_REVIEW_REQUIRED
    if count_all_annotations_for_paper(conn, paper_id) > 0:
        return False, PDF_REVIEW_REQUIRED
    return True, PDF_OK


def admit(conn: Connection, envelope: CaptureEnvelope, *, crossref_client: Any | None) -> AdmissionOutcome:
    """Resolve the captured page to a Library paper. Caller owns the transaction and the commit.

    Mirrors ``add_paper_by_doi``'s contract deliberately: metadata only, no PDF fetch, no commit — so
    a failed attachment can never masquerade as a failed admission.
    """
    doi = normalize_doi(envelope.identifiers.doi)

    # Trash is checked FIRST and for every path: a trashed paper must never be written to, silently
    # restored, or duplicated behind the user's back. The researcher decides in Callosum.
    state, row = resolve_library_state(
        conn,
        doi=doi,
        title=envelope.title,
        year=envelope.year,
        first_author_family_name=envelope.first_author_family(),
    )
    if state == "trashed" and row is not None:
        return AdmissionOutcome(
            status=STATUS_IN_TRASH,
            paper_id=int(row["id"]),
            title=str(row["title"]) if row["title"] else None,
            pdf_reason=PDF_NOT_OFFERED,
        )

    if doi:
        result = add_paper_by_doi(conn, doi, crossref_client=crossref_client, imported_source=CAPTURE_SOURCE)
        if result.status in {"invalid", "unresolved"}:
            # An unresolvable DOI creates nothing. If the page also gave us a usable title we could
            # fall back — but that would re-enter the non-unique title path below, so we do not.
            return AdmissionOutcome(
                status=STATUS_UNRESOLVED,
                detail=result.error,
                pdf_reason=PDF_NOT_OFFERED,
            )
        created = result.status == "created"
        paper_id = int(result.paper_id) if result.paper_id is not None else None
        if paper_id is None:  # defensive: created/existing always carry an id
            return AdmissionOutcome(status=STATUS_UNRESOLVED, pdf_reason=PDF_NOT_OFFERED)
        accepted, reason = attachment_decision(conn, paper_id, newly_created=created)
        return AdmissionOutcome(
            status=STATUS_ADDED if created else STATUS_ALREADY_PRESENT,
            paper_id=paper_id,
            created=created,
            pdf_accepted=accepted and envelope.pdf_bytes_from_active_tab,
            pdf_reason=reason if envelope.pdf_bytes_from_active_tab else PDF_NOT_OFFERED,
            title=result.title,
        )

    # --- no DOI ---------------------------------------------------------------------------------
    # An ACTIVE match found on a non-unique predicate is not trustworthy enough to write to, and not
    # trustworthy enough to create beside either. Report it for review rather than guessing.
    if state == "active" and row is not None:
        return AdmissionOutcome(
            status=STATUS_UNRESOLVED,
            paper_id=int(row["id"]),
            title=str(row["title"]) if row["title"] else None,
            detail="matched an existing paper on non-unique bibliographic fields",
            pdf_reason=PDF_NOT_OFFERED,
        )

    title = (envelope.title or "").strip()
    if not title:
        return AdmissionOutcome(
            status=STATUS_INVALID,
            detail="the page exposed neither a DOI nor a title",
            pdf_reason=PDF_NOT_OFFERED,
        )

    # Nothing in the Library matches and there is no stable identifier: creating a fresh
    # metadata-only record is safe (it cannot collide — no UNIQUE identifier is being claimed) and is
    # the honest outcome. A later enrich can still discover a DOI for it.
    paper_id = create_paper(
        conn,
        title=title,
        csl_json=_csl_from_envelope(envelope),
        abstract=envelope.abstract,
        year=envelope.year,
        venue=envelope.container_title,
        item_type=envelope.item_type,
        language=envelope.language,
        publication_date=envelope.publication_date,
        first_author_family_name=envelope.first_author_family(),
        imported_source=CAPTURE_SOURCE,
    )
    accepted, reason = attachment_decision(conn, paper_id, newly_created=True)
    return AdmissionOutcome(
        status=STATUS_ADDED,
        paper_id=paper_id,
        created=True,
        pdf_accepted=accepted and envelope.pdf_bytes_from_active_tab,
        pdf_reason=reason if envelope.pdf_bytes_from_active_tab else PDF_NOT_OFFERED,
        title=title,
    )


def _csl_from_envelope(envelope: CaptureEnvelope) -> dict[str, Any]:
    """Build the CSL record for a capture-created paper, mirroring ``discovery.search.save_item``.

    PMID/arXiv live in the CSL because ``papers`` has no column for them — the same place every other
    import path puts them, so a later enrich can pick them up.
    """
    csl: dict[str, Any] = {
        "id": envelope.identifiers.doi or envelope.source_url,
        "type": envelope.item_type or "article-journal",
        "title": envelope.title,
    }
    if envelope.abstract:
        csl["abstract"] = envelope.abstract
    if envelope.container_title:
        csl["container-title"] = envelope.container_title
    if envelope.publisher:
        csl["publisher"] = envelope.publisher
    if envelope.year:
        csl["issued"] = {"date-parts": [[envelope.year]]}
    if envelope.volume:
        csl["volume"] = envelope.volume
    if envelope.issue:
        csl["issue"] = envelope.issue
    if envelope.pages:
        csl["page"] = envelope.pages
    if envelope.language:
        csl["language"] = envelope.language
    if envelope.identifiers.doi:
        csl["DOI"] = envelope.identifiers.doi
    if envelope.identifiers.pmid:
        csl["PMID"] = envelope.identifiers.pmid
    if envelope.identifiers.arxiv:
        csl["arxiv"] = envelope.identifiers.arxiv
    if envelope.identifiers.isbn:
        csl["ISBN"] = envelope.identifiers.isbn
    if envelope.source_url:
        csl["URL"] = envelope.source_url
    authors = envelope.author_strings()
    if authors:
        csl["author"] = [
            {"family": name.split(",", 1)[0].strip(), "given": name.split(",", 1)[1].strip()}
            if "," in name
            else {"literal": name}
            for name in authors
        ]
    return csl
