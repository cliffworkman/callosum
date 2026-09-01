"""Persisted-summary response models + the pure row->response shaping helpers for summaries.py.

Split out of summaries.py (rule #1, the 600-line cap) as a leaf module: these read already-committed rows
and build the shared response contract, with no job-running or LLM logic of their own. Re-exported from
summaries.py so existing `from app.backend.api.routers.summaries import SummarizeJobResponse` (and sibling
model) call sites keep resolving unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import Connection, select

from app.backend.api.routers.paper_files import _is_pdf_attachment
from app.backend.persistence.repository import get_summary
from app.backend.persistence.schema import (
    attachments,
    chunks,
    citation_mappings,
    evidence_quotes,
    papers,
    summary_sentences,
)
from app.backend.summarization.overview_lifecycle import OverviewStatus, overview_status_for_row

IMPORTED_STATUS = "imported"  # a relayed synthesis carries the sender's verification (B2 SP2)


class SummaryCitationResponse(BaseModel):
    mapping_id: int | None = None  # None for a relayed (imported) citation — no local mapping/evidence/chunk id
    evidence_quote_id: int | None = None
    chunk_id: int | None = None
    paper_id: int | None = None  # None = the source paper isn't in the recipient's library (evidence still shown)
    paper_title: str
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    quote: str
    retrieval_confidence: float
    quote_confidence: float
    support_confidence: float
    status: str
    coordinate_precision: str | None = None
    bbox_json: Any | None = None
    attachment_id: int | None = None  # #5: only set when the underlying attachment is a PDF (never docx/html/etc.)


class SummarySentenceResponse(BaseModel):
    sentence_id: int
    ordinal: int
    text: str
    flagged: bool
    citations: list[SummaryCitationResponse]


class OverviewItemResponse(BaseModel):
    text: str
    claim_ordinals: list[int]  # ordinals of the verified sentences this Overview sentence restates


class SummarizeJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    summary_id: int | None = None
    summary_status: str | None = None
    source_chunk_count: int | None = None
    section_filter: list[str] = []
    sentences: list[SummarySentenceResponse] | None = None
    overview: list[OverviewItemResponse] | None = None
    overview_status: OverviewStatus = "not_requested"
    overview_updated_at: datetime | None = None
    imported: bool = False  # B2 SP2: a relayed synthesis — the sender's assessment, region precision, not re-verified


class SummaryListItem(BaseModel):
    summary_id: int
    scope_type: str
    scope_label: str
    status: str
    created_at: str | None = None
    sentence_count: int
    verified_sentence_count: int
    flagged_sentence_count: int
    imported: bool = False  # B2 SP2: flags a relayed synthesis in the history list


def _persisted_summary_response(conn: Connection, *, summary_id: int, job_id: str) -> SummarizeJobResponse:
    summary = get_summary(conn, summary_id)
    imported_blob = summary["imported_json"] if "imported_json" in summary else None
    if imported_blob:  # B2 SP2: a relayed synthesis — build the response from its self-contained display blob
        return _imported_summary_response(imported_blob, summary_id=summary_id, job_id=job_id)
    sentence_rows = list(
        conn.execute(
            select(summary_sentences)
            .where(summary_sentences.c.summary_id == summary_id)
            .order_by(summary_sentences.c.ordinal, summary_sentences.c.id)
        ).mappings()
    )
    overview_raw = summary["overview_json"] if "overview_json" in summary else None
    overview = (
        [
            OverviewItemResponse(text=str(i["text"]), claim_ordinals=[int(o) for o in i["claim_ordinals"]])
            for i in overview_raw
            if isinstance(i, dict) and i.get("text") and isinstance(i.get("claim_ordinals"), list)
        ]
        if isinstance(overview_raw, list)
        else None
    )
    return SummarizeJobResponse(
        job_id=job_id,
        status="done",
        summary_id=summary_id,
        summary_status=summary["status"],
        source_chunk_count=_source_chunk_count_from_ref(summary["scope_ref_json"]),
        section_filter=_section_filter_from_ref(summary["scope_ref_json"]),
        sentences=[_summary_sentence_response(conn, sentence) for sentence in sentence_rows],
        overview=overview,
        overview_status=overview_status_for_row(summary),
        overview_updated_at=summary["overview_updated_at"],
    )


def _imported_summary_response(blob: Any, *, summary_id: int, job_id: str) -> SummarizeJobResponse:
    """Build the response for a RELAYED synthesis from its display blob (B2 SP2): region-precision citations, the
    sender's statuses, `imported=True`. Never touches the verification tables."""
    sentences = []
    for i, st in enumerate(blob.get("sentences") or []):
        if not isinstance(st, dict):
            continue
        citations = [
            SummaryCitationResponse(
                paper_id=c.get("paper_id"),
                paper_title=str(c.get("paper_title") or ""),
                page_start=c.get("page_start"),
                page_end=c.get("page_end"),
                section=c.get("section"),
                quote=str(c.get("quote") or ""),
                retrieval_confidence=float(c.get("retrieval_confidence") or 0.0),
                quote_confidence=float(c.get("quote_confidence") or 0.0),
                support_confidence=float(c.get("support_confidence") or 0.0),
                status=str(c.get("status") or "unverified"),
                coordinate_precision="region",  # the sender's box is for the sender's PDF — always region here
            )
            for c in (st.get("citations") or [])
            if isinstance(c, dict)
        ]
        sentences.append(
            SummarySentenceResponse(
                sentence_id=i,
                ordinal=int(st.get("ordinal") or i),
                text=str(st.get("text") or ""),
                flagged=bool(st.get("flagged")),
                citations=citations,
            )
        )
    ov = blob.get("overview")
    overview = (
        [
            OverviewItemResponse(text=str(i["text"]), claim_ordinals=[int(o) for o in i["claim_ordinals"]])
            for i in ov
            if isinstance(i, dict) and i.get("text") and isinstance(i.get("claim_ordinals"), list)
        ]
        if isinstance(ov, list)
        else None
    )
    return SummarizeJobResponse(
        job_id=job_id,
        status="done",
        summary_id=summary_id,
        summary_status=IMPORTED_STATUS,
        section_filter=[],
        sentences=sentences,
        overview=overview,
        overview_status="complete" if overview else "not_requested",
        imported=True,
    )


def _summary_sentence_response(conn: Connection, sentence: Any) -> SummarySentenceResponse:
    citations = [_summary_citation_response(row) for row in _summary_citation_rows(conn, int(sentence["id"]))]
    return SummarySentenceResponse(
        sentence_id=int(sentence["id"]),
        ordinal=int(sentence["ordinal"]),
        text=sentence["text"],
        flagged=not citations or any(citation.status != "verified" for citation in citations),
        citations=citations,
    )


def _summary_citation_rows(conn: Connection, sentence_id: int) -> list[Any]:
    return list(
        conn.execute(
            select(
                citation_mappings.c.id.label("mapping_id"),
                citation_mappings.c.chunk_id.label("mapping_chunk_id"),
                citation_mappings.c.status,
                evidence_quotes.c.id.label("evidence_quote_id"),
                evidence_quotes.c.chunk_id.label("evidence_chunk_id"),
                evidence_quotes.c.quote_text,
                evidence_quotes.c.page_start,
                evidence_quotes.c.page_end,
                evidence_quotes.c.bbox_json,
                evidence_quotes.c.retrieval_confidence,
                evidence_quotes.c.quote_confidence,
                evidence_quotes.c.support_confidence,
                chunks.c.paper_id,
                chunks.c.section,
                chunks.c.attachment_id,
                attachments.c.content_type.label("attachment_content_type"),
                attachments.c.attachment_type,
                papers.c.title.label("paper_title"),
            )
            .select_from(
                citation_mappings.join(evidence_quotes, evidence_quotes.c.citation_mapping_id == citation_mappings.c.id)
                .join(chunks, chunks.c.id == evidence_quotes.c.chunk_id)
                .join(papers, papers.c.id == chunks.c.paper_id)
                # inner join is safe: chunks.attachment_id is a non-nullable FK (every chunk has one)
                .join(attachments, attachments.c.id == chunks.c.attachment_id)
            )
            .where(citation_mappings.c.summary_sentence_id == sentence_id)
            .order_by(citation_mappings.c.id)
        ).mappings()
    )


def _summary_citation_response(row: Any) -> SummaryCitationResponse:
    bbox_json = row["bbox_json"]
    chunk_id = row["evidence_chunk_id"] or row["mapping_chunk_id"]
    # #5: only surface attachment_id when it's a real PDF — a citation whose text came from a non-PDF
    # supplementary-text attachment (docx/html/jats-xml, role="supplementary-text") must keep degrading to the
    # paper's primary PDF (today's honest null-precision fallback), not 404 as "no local PDF" for a paper that
    # actually has one.
    is_pdf = _is_pdf_attachment(
        {"content_type": row["attachment_content_type"], "attachment_type": row["attachment_type"]}
    )
    return SummaryCitationResponse(
        mapping_id=row["mapping_id"],
        evidence_quote_id=row["evidence_quote_id"],
        chunk_id=chunk_id,
        paper_id=row["paper_id"],
        paper_title=row["paper_title"],
        page_start=row["page_start"],
        page_end=row["page_end"],
        section=row["section"],
        quote=row["quote_text"],
        retrieval_confidence=row["retrieval_confidence"],
        quote_confidence=row["quote_confidence"],
        support_confidence=row["support_confidence"],
        status=row["status"],
        coordinate_precision=_coordinate_precision_from_bbox(bbox_json),
        bbox_json=bbox_json,
        attachment_id=row["attachment_id"] if is_pdf else None,
    )


def _summary_list_item(row: Any) -> SummaryListItem:
    return SummaryListItem(
        summary_id=row["id"],
        scope_type=row["scope_type"],
        scope_label=_summary_scope_label(row["scope_type"], row["scope_ref_json"]),
        status=row["status"],
        created_at=str(row["created_at"]) if row["created_at"] is not None else None,
        sentence_count=int(row["sentence_count"]),
        verified_sentence_count=int(row["verified_sentence_count"]),
        flagged_sentence_count=int(row["flagged_sentence_count"]),
        imported=row["status"] == IMPORTED_STATUS,
    )


def _summary_scope_label(scope_type: str, scope_ref: Any) -> str:
    if not isinstance(scope_ref, dict):
        return scope_type
    if scope_type == "query":
        query = scope_ref.get("query")
        return str(query) if query else "Query summary"
    if scope_type == "papers":
        paper_ids = scope_ref.get("paper_ids") or []
        if isinstance(paper_ids, list) and paper_ids:
            return f"{len(paper_ids)} paper{'s' if len(paper_ids) != 1 else ''}"
        return "Paper summary"
    if scope_type == "cluster_node":
        cluster_node_id = scope_ref.get("cluster_node_id")
        return f"Cluster node {cluster_node_id}" if cluster_node_id is not None else "Cluster summary"
    return scope_type


def _source_chunk_count_from_ref(scope_ref: Any) -> int | None:
    if not isinstance(scope_ref, dict) or scope_ref.get("source_chunk_count") is None:
        return None
    try:
        return int(scope_ref["source_chunk_count"])
    except (TypeError, ValueError):
        return None


def _section_filter_from_ref(scope_ref: Any) -> list[str]:
    if not isinstance(scope_ref, dict) or not isinstance(scope_ref.get("sections"), list):
        return []
    return [str(item) for item in scope_ref["sections"] if str(item)]


def _coordinate_precision_from_bbox(bbox_json: Any) -> str | None:
    if isinstance(bbox_json, list):
        for item in bbox_json:
            if isinstance(item, dict) and item.get("coordinate_precision"):
                return str(item["coordinate_precision"])
    if isinstance(bbox_json, dict) and bbox_json.get("coordinate_precision"):
        return str(bbox_json["coordinate_precision"])
    return None
