"""Attachment-level source-representation state, and durable logical component identity (inc 579).

H1b decided whether a source graph was current from ``(source_checksum, derivation_version)`` alone.
An independent audit showed that was not enough: with the component cap lowered, a write that
persisted one page and zero components matched on both, so the partial graph was classified current
and an ordinary backfill would have skipped it forever. This module owns the repair.

Two concerns live here, and both exist so that a future study can reference this substrate safely:

* **Completeness.** ``source_representations`` records, per attachment, what was expected, what was
  written, and whether the result is ``complete`` / ``truncated`` / ``incomplete`` / ``failed``.
  Only ``complete`` may be current, and currentness additionally cross-checks the rows actually
  present against the counts the record claims -- for pages *and* components, because a graph with
  an intact page envelope but missing components is not a complete graph.
* **Durable identity.** A forced rebuild changes every ``source_pages.id`` and
  ``source_components.id`` while leaving the logical tree exact, so surrogate keys are not
  provenance. ``SourceLocator`` names a component by source checksum + extraction tool + extraction
  version + derivation version + page number + ``component_path``, every constituent inspectable.

Split out of ``source_components_repo`` (rule #1, the inc-137/220 pattern) and re-exported from it,
so existing call sites keep one import site. Nothing here is on the retrieval path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Connection

from app.backend.persistence.schema import attachments, papers
from app.backend.persistence.schema_source_components import (
    SOURCE_DERIVATION_VERSION,
    source_components,
    source_pages,
    source_representations,
)

# Representation states (inc 579, H1b.1). Only COMPLETE may satisfy currentness.
STATE_COMPLETE = "complete"
STATE_TRUNCATED = "truncated"
STATE_INCOMPLETE = "incomplete"
STATE_FAILED = "failed"


@dataclass(frozen=True)
class SourceWriteReceipt:
    """What one ``replace_attachment_source`` call actually persisted, and how complete it is."""

    expected_pages: int
    written_pages: int
    skipped_pages: int
    written_components: int
    state: str
    state_reason: str | None

    @property
    def is_complete(self) -> bool:
        return self.state == STATE_COMPLETE


@dataclass(frozen=True)
class SourceLocator:
    """The durable logical identity of one source component.

    Surrogate ``source_pages.id`` / ``source_components.id`` are **not** durable identity: an
    independent audit forced three attachments to rebuild and every surrogate id changed while every
    logical tree stayed exact. Durable provenance -- anything a future assembled evidence unit would
    reference -- must name a component by these six fields instead. Every constituent stays
    inspectable; ``as_key`` is a rendering of them, never an opaque digest.

    ``extraction_version`` is explicit rather than folded into ``extraction_tool``: a PyMuPDF
    upgrade can change what the extractor observes from the same bytes, and a locator that could not
    see that change would silently resolve to a different component.
    """

    source_checksum: str
    extraction_tool: str
    extraction_version: str
    derivation_version: str
    page_number: int
    component_path: str

    def as_key(self) -> str:
        return "|".join(
            (
                self.source_checksum,
                self.extraction_tool,
                self.extraction_version,
                self.derivation_version,
                f"p{self.page_number}",
                self.component_path,
            )
        )

    @classmethod
    def parse(cls, key: str) -> "SourceLocator":
        checksum, tool, version, derivation, page, path = key.split("|", 5)
        return cls(checksum, tool, version, derivation, int(page.lstrip("p")), path)


def clear_representation(conn: Connection, attachment_id: int) -> None:
    """Destroy an attachment's completeness claim.

    Called first by a rewrite, before the graph it describes is deleted, so there is no window in
    which a complete marker outlives the rows backing it.
    """
    conn.execute(delete(source_representations).where(source_representations.c.attachment_id == attachment_id))


def _replace_representation(conn: Connection, attachment_id: int, values: dict[str, Any]) -> None:
    """One row per attachment, delete-then-insert rather than an upsert, so both timestamps are the
    moment this representation was actually derived."""
    clear_representation(conn, attachment_id)
    conn.execute(source_representations.insert().values(attachment_id=attachment_id, **values))


def _current_source_stmt(derivation_version: str):
    """The whole currentness contract as one inspectable statement (inc 579, H1b.1).

        current  requires  complete
                 AND source checksum current
                 AND extraction/derivation identity current
                 AND every page extraction produced was written, none skipped
                 AND the rows actually present match the counts the record claims

    The last clause is not decoration. A status row can outlive the graph it describes -- the
    independent audit deleted an attachment's rows and reran -- and without the cross-check that
    combination reads as current. It is checked for **both** pages and components: a graph with an
    intact page envelope but missing component rows is not a complete source graph, and the
    invariant is about the completeness of the graph rather than of its envelope.
    """
    page_counts = (
        select(source_pages.c.attachment_id.label("aid"), func.count().label("n"))
        .group_by(source_pages.c.attachment_id)
        .subquery()
    )
    component_counts = (
        select(source_pages.c.attachment_id.label("aid"), func.count().label("n"))
        .select_from(source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id))
        .group_by(source_pages.c.attachment_id)
        .subquery()
    )
    rep = source_representations
    return (
        select(rep.c.attachment_id)
        .select_from(
            rep.join(attachments, attachments.c.id == rep.c.attachment_id)
            .outerjoin(page_counts, page_counts.c.aid == rep.c.attachment_id)
            .outerjoin(component_counts, component_counts.c.aid == rep.c.attachment_id)
        )
        .where(
            rep.c.state == STATE_COMPLETE,
            rep.c.derivation_version == derivation_version,
            attachments.c.checksum.is_not(None),
            func.trim(attachments.c.checksum) != "",
            rep.c.source_checksum == attachments.c.checksum,
            rep.c.expected_pages > 0,
            rep.c.written_pages == rep.c.expected_pages,
            rep.c.skipped_pages == 0,
            func.coalesce(page_counts.c.n, 0) == rep.c.written_pages,
            func.coalesce(component_counts.c.n, 0) == rep.c.written_components,
        )
    )


def attachments_with_current_source(conn: Connection, derivation_version: str = SOURCE_DERIVATION_VERSION) -> set[int]:
    """Attachment ids whose source representation is COMPLETE and current.

    This is what makes an interrupted backfill resumable without a cursor file. An attachment with
    no representation row, a stale one, an older derivation version, or a truncated / incomplete /
    failed one is simply absent from the set and will be re-derived by an ordinary rerun.
    """
    return {int(row[0]) for row in conn.execute(_current_source_stmt(derivation_version))}


def is_source_current(
    conn: Connection, attachment_id: int, derivation_version: str = SOURCE_DERIVATION_VERSION
) -> bool:
    """The same contract, scoped to one attachment."""
    stmt = _current_source_stmt(derivation_version).where(source_representations.c.attachment_id == attachment_id)
    return conn.execute(stmt).first() is not None


def record_source_failure(
    conn: Connection,
    *,
    attachment_id: int,
    source_checksum: str,
    extraction_tool: str,
    extraction_version: str,
    reason: str,
    derivation_version: str = SOURCE_DERIVATION_VERSION,
) -> bool:
    """Record that a derivation attempt failed -- unless a valid representation survived it.

    The **state of the persisted representation** and the **outcome of the latest attempt** are two
    different facts, and only the first decides currentness. When a rebuild fails and its savepoint
    rolls back, a previously committed complete representation for the same file is restored intact;
    marking that row ``failed`` would corrupt a perfectly good representation because a *later*
    attempt went wrong. So this checks first and declines, returning ``False`` for the caller to log
    the failed attempt through ordinary logging. No attempt history is kept -- that would be a job
    framework, which this deliberately is not.
    """
    if is_source_current(conn, attachment_id, derivation_version):
        return False
    _replace_representation(
        conn,
        attachment_id,
        {
            "source_checksum": source_checksum,
            "extraction_tool": extraction_tool,
            "extraction_version": extraction_version,
            "derivation_version": derivation_version,
            "expected_pages": 0,
            "written_pages": 0,
            "skipped_pages": 0,
            "written_components": 0,
            "state": STATE_FAILED,
            "state_reason": reason,
        },
    )
    return True


def source_representation_for(conn: Connection, attachment_id: int) -> dict[str, Any] | None:
    """One attachment's completeness record, for inspection. No currentness judgment attached."""
    row = (
        conn.execute(select(source_representations).where(source_representations.c.attachment_id == attachment_id))
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def source_representation_report(
    conn: Connection, derivation_version: str = SOURCE_DERIVATION_VERSION
) -> dict[str, int]:
    """Per-state counts over **live** PDF attachments, plus how many carry no record at all.

    Soft-deleted papers are outside live coverage by design and are counted separately by the caller
    rather than reported here as a gap. ``complete`` can legitimately exceed ``current``: a complete
    record whose file has since been replaced is complete *and* stale.
    """
    live_ids = {
        int(row[0])
        for row in conn.execute(
            select(attachments.c.id)
            .select_from(attachments.join(papers, papers.c.id == attachments.c.paper_id))
            .where(attachments.c.content_type == "application/pdf", papers.c.deleted_at.is_(None))
        )
    }
    states = {
        int(row[0]): row[1]
        for row in conn.execute(select(source_representations.c.attachment_id, source_representations.c.state))
    }
    report = {
        "live": len(live_ids),
        "current": len(live_ids & attachments_with_current_source(conn, derivation_version)),
        "absent": 0,
        STATE_COMPLETE: 0,
        STATE_TRUNCATED: 0,
        STATE_INCOMPLETE: 0,
        STATE_FAILED: 0,
    }
    for attachment_id in live_ids:
        state = states.get(attachment_id)
        report["absent" if state is None else state] += 1
    return report


def resolve_locator(conn: Connection, attachment_id: int, locator: SourceLocator) -> dict[str, Any] | None:
    """Resolve a durable logical locator to its component row, or ``None``.

    **Fails closed on any identity drift.** If the attachment's live checksum, or the stored page's
    extractor/derivation identity, no longer matches what the locator names, the locator is stale and
    resolves to nothing rather than to whatever component now occupies that path. That is the
    property surrogate ids cannot provide: a forced rebuild changes every id while leaving every
    logical path resolving to the same content.
    """
    live_checksum = conn.execute(select(attachments.c.checksum).where(attachments.c.id == attachment_id)).scalar()
    if (live_checksum or "") != locator.source_checksum:
        return None
    page = (
        conn.execute(
            select(source_pages).where(
                source_pages.c.attachment_id == attachment_id,
                source_pages.c.page_number == locator.page_number,
            )
        )
        .mappings()
        .first()
    )
    if page is None or (
        page["source_checksum"],
        page["extraction_tool"],
        page["extraction_version"],
        page["derivation_version"],
    ) != (
        locator.source_checksum,
        locator.extraction_tool,
        locator.extraction_version,
        locator.derivation_version,
    ):
        return None
    component = (
        conn.execute(
            select(source_components).where(
                source_components.c.source_page_id == page["id"],
                source_components.c.component_path == locator.component_path,
            )
        )
        .mappings()
        .first()
    )
    return dict(component) if component is not None else None


def locator_for_component(conn: Connection, component_id: int) -> SourceLocator | None:
    """The durable identity of an already-stored component -- the audit direction of the locator."""
    row = (
        conn.execute(
            select(
                source_pages.c.source_checksum,
                source_pages.c.extraction_tool,
                source_pages.c.extraction_version,
                source_pages.c.derivation_version,
                source_pages.c.page_number,
                source_components.c.component_path,
            )
            .select_from(source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id))
            .where(source_components.c.id == component_id)
        )
        .mappings()
        .first()
    )
    if row is None or not row["component_path"]:
        return None
    return SourceLocator(
        source_checksum=row["source_checksum"],
        extraction_tool=row["extraction_tool"],
        extraction_version=row["extraction_version"],
        derivation_version=row["derivation_version"],
        page_number=int(row["page_number"]),
        component_path=row["component_path"],
    )


__all__ = [
    "STATE_COMPLETE",
    "STATE_FAILED",
    "STATE_INCOMPLETE",
    "STATE_TRUNCATED",
    "SourceLocator",
    "SourceWriteReceipt",
    "attachments_with_current_source",
    "clear_representation",
    "is_source_current",
    "locator_for_component",
    "record_source_failure",
    "resolve_locator",
    "source_representation_for",
    "source_representation_report",
]
