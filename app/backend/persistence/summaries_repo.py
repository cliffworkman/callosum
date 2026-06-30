"""Summary (synthesis) data-access — extracted from repository.py (inc 220, to keep it under the 600-line cap).

Syntheses are a separate concern from the papers store; this is their list/get/delete CRUD (with the per-summary
verified/flagged sentence counts). Re-exported from ``repository`` so existing ``from …repository import
list_summaries`` call sites are unchanged (the inc-137 / inc-67 pattern). Bound-param SQLAlchemy Core (rule #3).
"""

from __future__ import annotations

from sqlalchemy import Connection, RowMapping, delete, exists, func, not_, select

from app.backend.persistence.schema import citation_mappings, summaries, summary_sentences


def list_summaries(conn: Connection, *, limit: int = 50, offset: int = 0) -> list[RowMapping]:
    sentence_count = (
        select(func.count())
        .select_from(summary_sentences)
        .where(summary_sentences.c.summary_id == summaries.c.id)
        .scalar_subquery()
    )
    verified_sentence_count = (
        select(func.count())
        .select_from(summary_sentences)
        .where(
            summary_sentences.c.summary_id == summaries.c.id,
            exists(
                select(citation_mappings.c.id).where(citation_mappings.c.summary_sentence_id == summary_sentences.c.id)
            ),
            not_(
                exists(
                    select(citation_mappings.c.id).where(
                        citation_mappings.c.summary_sentence_id == summary_sentences.c.id,
                        citation_mappings.c.status != "verified",
                    )
                )
            ),
        )
        .scalar_subquery()
    )
    stmt = (
        select(
            summaries,
            sentence_count.label("sentence_count"),
            verified_sentence_count.label("verified_sentence_count"),
            (sentence_count - verified_sentence_count).label("flagged_sentence_count"),
        )
        .order_by(summaries.c.created_at.desc(), summaries.c.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(conn.execute(stmt).mappings())


def get_summary(conn: Connection, summary_id: int) -> RowMapping:
    return conn.execute(select(summaries).where(summaries.c.id == summary_id)).mappings().one()


def delete_summary(conn: Connection, summary_id: int) -> bool:
    result = conn.execute(delete(summaries).where(summaries.c.id == summary_id))
    return bool(result.rowcount)
