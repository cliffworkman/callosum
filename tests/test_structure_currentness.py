"""Inc 614: classification currentness covers exactly the population the derivation classifies.

The derivation classifies article full-text chunks only. Before inc 614 the currentness predicate also counted
preregistration/supplement/other chunks, which never receive a row, so a paper with such an attachment was re-derived
on every run and coverage never reached 100 %. These tests pin the shared definition and its staleness behaviour.
"""

from __future__ import annotations

from sqlalchemy import select, update

from app.backend.pdf_processing.structure_backfill import _paper_rows, backfill, coverage
from app.backend.persistence.chunk_structure_repo import (
    CLASSIFIED_DOCUMENT_ROLES,
    papers_with_classified_chunks,
    papers_with_current_structure,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import chunks
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION, chunk_structure
from tests.test_source_role_migration import PLAIN

OTHER = "We preregistered the hypotheses, sample size and exclusion rules before any data were collected."


def _attachment(conn, paper_id: int, role: str | None, tag: str) -> int:  # type: ignore[no-untyped-def]
    return create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum=f"cur-{tag}",
        role=role,
    )


def _chunk(conn, paper_id: int, attachment_id: int, text: str, version: str) -> int:  # type: ignore[no-untyped-def]
    return create_chunk(
        conn,
        paper_id=paper_id,
        attachment_id=attachment_id,
        text=text,
        page_start=2,
        page_end=2,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="fixture",
        extraction_version="1",
        chunking_strategy="paragraph",
        chunk_version=version,
        source_attachment_checksum="cur",
        section="methods",
    )


def _paper(conn, title: str, roles: list[str | None]) -> tuple[int, list[int]]:  # type: ignore[no-untyped-def]
    """One paper with one two-chunk attachment per role in ``roles``."""
    paper_id = create_paper(conn, title=title, csl_json={"title": title})
    ids = []
    for i, role in enumerate(roles):
        att = _attachment(conn, paper_id, role, f"{title}-{i}")
        for j in range(2):
            ids.append(_chunk(conn, paper_id, att, f"{PLAIN} ({title} {i}.{j})", f"{title}-{i}-{j}-v1"))
    return paper_id, ids


def _rows(engine) -> list[tuple]:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        cols = [c for c in chunk_structure.c if c.name != "created_at"]
        return [tuple(r) for r in conn.execute(select(*cols).order_by(chunk_structure.c.chunk_id))]


def test_the_classified_population_is_the_article_population() -> None:
    assert CLASSIFIED_DOCUMENT_ROLES == ARTICLE_DOCUMENT_ROLES == ("article-fulltext",)


def test_mixed_attachment_paper_becomes_current_and_stays_current(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        mixed, mixed_ids = _paper(conn, "mixed", ["article-fulltext", "preregistration", "supplement", "other"])
        legacy, _ = _paper(conn, "legacy", ["primary", "protocol"])  # legacy 'primary' normalizes to article
        clean, _ = _paper(conn, "clean", ["article-fulltext"])

    first = backfill(engine)
    assert first["papers"] == 3
    with engine.begin() as conn:
        assert papers_with_current_structure(conn, DERIVATION_VERSION) == {mixed, legacy, clean}
        classified = {int(r[0]) for r in conn.execute(select(chunk_structure.c.chunk_id))}
    assert classified & set(mixed_ids) == set(mixed_ids[:2])  # only the article chunks receive rows

    rows = _rows(engine)
    again = backfill(engine)
    assert (again["papers"], again["chunks"], again["skipped_current"]) == (0, 0, 3)  # no perpetual re-derive
    assert _rows(engine) == rows  # idempotent: output untouched
    cov = coverage(engine)
    assert (cov["papers_with_chunks"], cov["papers_current"], cov["papers_needing_derivation"]) == (3, 3, 0)
    engine.dispose()


def test_paper_without_classified_chunks_is_neither_pending_nor_looping(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        only_reg, _ = _paper(conn, "registration-only", ["preregistration", "supplement"])
        clean, _ = _paper(conn, "clean", ["article-fulltext"])
        assert papers_with_classified_chunks(conn) == {clean}
        assert _paper_rows(conn, only_reg) == []

    backfill(engine)
    cov = coverage(engine)
    assert cov["papers_needing_derivation"] == 0
    assert cov["papers_current"] == 1
    assert cov["papers_without_classified_chunks"] == 1
    again = backfill(engine)
    assert (again["papers"], again["chunks"]) == (0, 0)
    with engine.begin() as conn:
        assert not conn.execute(
            select(chunk_structure.c.chunk_id)
            .join(chunks, chunks.c.id == chunk_structure.c.chunk_id)
            .where(chunks.c.paper_id == only_reg)
        ).first()
    engine.dispose()


def test_new_eligible_chunk_makes_the_paper_pending_but_a_new_registration_chunk_does_not(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper, _ = _paper(conn, "p", ["article-fulltext", "preregistration"])
    backfill(engine)
    with engine.begin() as conn:
        reg_att = _attachment(conn, paper, "preregistration", "late-reg")
        _chunk(conn, paper, reg_att, OTHER, "late-reg-v1")
        assert paper in papers_with_current_structure(conn, DERIVATION_VERSION)

        art_att = _attachment(conn, paper, "article-fulltext", "late-art")
        _chunk(conn, paper, art_att, f"{PLAIN} (late)", "late-art-v1")
        assert paper not in papers_with_current_structure(conn, DERIVATION_VERSION)
    assert backfill(engine)["papers"] == 1
    with engine.begin() as conn:
        assert paper in papers_with_current_structure(conn, DERIVATION_VERSION)
    engine.dispose()


def test_text_hash_and_chunk_version_changes_invalidate_only_classified_chunks(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper, ids = _paper(conn, "p", ["article-fulltext", "preregistration"])
    backfill(engine)
    article_chunk, reg_chunk = ids[0], ids[2]

    with engine.begin() as conn:  # editing a non-classified chunk changes nothing
        conn.execute(update(chunks).where(chunks.c.id == reg_chunk).values(text=OTHER, chunk_version="reg-v2"))
        assert paper in papers_with_current_structure(conn, DERIVATION_VERSION)

    with engine.begin() as conn:  # a text edit on a classified chunk makes the paper stale
        conn.execute(update(chunks).where(chunks.c.id == article_chunk).values(text=f"{PLAIN} edited"))
        assert paper not in papers_with_current_structure(conn, DERIVATION_VERSION)
    backfill(engine)

    with engine.begin() as conn:  # so does a chunk-version change with identical text
        assert paper in papers_with_current_structure(conn, DERIVATION_VERSION)
        conn.execute(update(chunks).where(chunks.c.id == article_chunk).values(chunk_version="art-v2"))
        assert paper not in papers_with_current_structure(conn, DERIVATION_VERSION)
    backfill(engine)

    with engine.begin() as conn:  # and an older derivation version
        assert paper in papers_with_current_structure(conn, DERIVATION_VERSION)
        conn.execute(
            update(chunk_structure)
            .where(chunk_structure.c.chunk_id == article_chunk)
            .values(derivation_version="chunk-structure-v1")
        )
        assert paper not in papers_with_current_structure(conn, DERIVATION_VERSION)
    engine.dispose()
