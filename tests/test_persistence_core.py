from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import insert, inspect, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.config import Config
from app.backend.persistence.annotations_repo import (
    create_annotation,
    delete_annotation,
    get_annotation,
    list_annotations_for_paper,
    update_annotation,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import (
    create_attachment,
    create_chunk,
    create_paper,
    find_existing_paper_by_identity,
    get_attachments_for_paper,
    get_chunks_for_paper,
    get_paper,
)
from app.backend.persistence.schema import (
    annotations,
    chunks,
    citation_mappings,
    evidence_quotes,
    metadata,
    papers,
    summaries,
    summary_sentences,
)


@pytest.fixture()
def migrated_db_url(tmp_path: Path) -> str:
    db_path = tmp_path / "callosum-test.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url


def test_alembic_migration_creates_persistence_schema(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)

    expected_tables = {
        "papers",
        "paper_external_identifiers",
        "attachments",
        "collections",
        "collection_papers",
        "tags",
        "paper_tags",
        "notes",
        "annotations",
        "processing_versions",
        "chunks",
        "embeddings",
        "axes",
        "cluster_nodes",
        "cluster_node_papers",
        "summaries",
        "summary_sentences",
        "citation_mappings",
        "evidence_quotes",
        "external_api_cache",
        "jobs",
        "job_errors",
        "missing_literature_suggestions",
        "open_science_signals",
        "watched_folders",
    }

    assert expected_tables.issubset(set(inspect(engine).get_table_names()))


def test_alembic_downgrade_to_base_drops_application_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "callosum-downgrade.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = make_engine(url)
    remaining_tables = set(inspect(engine).get_table_names())
    application_tables = set(metadata.tables)

    assert remaining_tables.isdisjoint(application_tables)


def test_round_trips_paper_attachment_and_chunk(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)
    csl = {
        "id": "doe2024",
        "type": "article-journal",
        "title": "Source Grounded Summaries",
        "author": [{"family": "Doe", "given": "Jane"}],
    }

    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Source Grounded Summaries",
            abstract="A paper about grounded summaries.",
            year=2024,
            doi="10.5555/CALLOSUM.1",
            venue="Journal of Local First Tools",
            item_type="article-journal",
            language="en",
            publication_date="2024-02-03",
            first_author_family_name="Doe",
            imported_source="fixture",
            csl_json=csl,
            processing_tier="metadata-only",
        )
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            original_path=r"C:\source\paper.pdf",
            resolved_path="library-store/pdfs/aa/abc.pdf",
            checksum="abc123",
            file_size=12345,
            content_type="application/pdf",
            import_source="fixture",
            attachment_type="pdf",
            role="primary",
        )
        chunk_id = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="This exact quote appears on the first page.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture-extractor",
            extraction_version="0.1",
            chunking_strategy="paragraph-v1",
            chunk_version="paragraph-v1:abc123",
            source_attachment_checksum="abc123",
            char_start=0,
            char_end=45,
            bbox_json=[{"x0": 10, "y0": 20, "x1": 200, "y1": 40}],
        )

        paper = get_paper(conn, paper_id)
        attachments = get_attachments_for_paper(conn, paper_id)
        paper_chunks = get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES)

    assert paper["title"] == "Source Grounded Summaries"
    assert paper["doi"] == "10.5555/callosum.1"
    assert paper["csl_json"] == csl
    assert attachments[0]["id"] == attachment_id
    assert attachments[0]["checksum"] == "abc123"
    assert paper_chunks[0]["id"] == chunk_id
    assert paper_chunks[0]["chunk_version"] == "paragraph-v1:abc123"


def test_identity_resolution_prefers_exact_doi_then_zotero_key(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)

    with engine.begin() as conn:
        doi_paper_id = create_paper(
            conn,
            title="DOI wins",
            year=2020,
            doi="10.1000/WINS",
            csl_json={"id": "doi-wins", "type": "article-journal", "title": "DOI wins"},
        )
        zotero_paper_id = create_paper(
            conn,
            title="Zotero fallback",
            year=2021,
            zotero_library_id="lib-1",
            zotero_item_key="ABC123",
            csl_json={"id": "zotero", "type": "article-journal", "title": "Zotero fallback"},
        )

        doi_match = find_existing_paper_by_identity(
            conn,
            doi="10.1000/wins",
            zotero_library_id="lib-1",
            zotero_item_key="ABC123",
        )
        zotero_match = find_existing_paper_by_identity(
            conn,
            zotero_library_id="lib-1",
            zotero_item_key="ABC123",
        )

    assert doi_match is not None
    assert doi_match[0] == "doi"
    assert doi_match[1]["id"] == doi_paper_id
    assert zotero_match is not None
    assert zotero_match[0] == "zotero_key"
    assert zotero_match[1]["id"] == zotero_paper_id


def test_chunk_requires_provenance_and_version_columns(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)

    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Chunk provenance",
            csl_json={"id": "chunk-provenance", "type": "article-journal", "title": "Chunk provenance"},
        )
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            checksum="checksum-1",
            content_type="application/pdf",
        )

        with pytest.raises(IntegrityError):
            conn.execute(
                insert(chunks).values(
                    paper_id=paper_id,
                    attachment_id=attachment_id,
                    text="Missing required provenance.",
                    page_start=1,
                    page_end=1,
                    bbox_coordinate_system="pdf-points-top-left",
                    extraction_version="0.1",
                    chunking_strategy="paragraph-v1",
                    chunk_version="paragraph-v1:checksum-1",
                    source_attachment_checksum="checksum-1",
                )
            )


def test_citation_mapping_records_verified_chunk_and_embedding_versions(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)

    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Versioned evidence",
            csl_json={"id": "versioned", "type": "article-journal", "title": "Versioned evidence"},
        )
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            checksum="checksum-2",
            content_type="application/pdf",
        )
        chunk_id = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="Evidence sentence.",
            page_start=2,
            page_end=2,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="fixture-extractor",
            extraction_version="0.1",
            chunking_strategy="sentence-window-v1",
            chunk_version="sentence-window-v1:checksum-2",
            source_attachment_checksum="checksum-2",
        )
        summary_id = conn.execute(
            insert(summaries).values(
                scope_type="paper",
                scope_ref_json={"paper_ids": [paper_id]},
                content="A summary.",
                generated_by="fixture",
                chunk_version_verified_against="sentence-window-v1:checksum-2",
                embedding_version_verified_against="bge-base:v1",
                verification_version="nli-v1",
            )
        ).inserted_primary_key[0]
        sentence_id = conn.execute(
            insert(summary_sentences).values(
                summary_id=summary_id,
                ordinal=0,
                text="The paper contains evidence.",
            )
        ).inserted_primary_key[0]
        mapping_id = conn.execute(
            insert(citation_mappings).values(
                summary_sentence_id=sentence_id,
                chunk_id=chunk_id,
                status="verified",
                chunk_version_verified_against="sentence-window-v1:checksum-2",
                embedding_version_verified_against="bge-base:v1",
                verification_version="nli-v1",
            )
        ).inserted_primary_key[0]
        conn.execute(
            insert(evidence_quotes).values(
                citation_mapping_id=mapping_id,
                chunk_id=chunk_id,
                quote_text="Evidence sentence.",
                page_start=2,
                page_end=2,
                retrieval_confidence=0.92,
                quote_confidence=1.0,
                support_confidence=0.88,
            )
        )

        mapping = conn.execute(select(citation_mappings).where(citation_mappings.c.id == mapping_id)).mappings().one()

    assert mapping["status"] == "verified"
    assert mapping["chunk_version_verified_against"] == "sentence-window-v1:checksum-2"
    assert mapping["embedding_version_verified_against"] == "bge-base:v1"


def test_trust_spine_round_trip(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)

    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Spine Paper",
            csl_json={"id": "spine", "type": "article-journal", "title": "Spine Paper"},
        )
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            checksum="spine-checksum",
            content_type="application/pdf",
        )
        chunk_id = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="Source chunk text.",
            page_start=5,
            page_end=5,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="spine-tool",
            extraction_version="1.0",
            chunking_strategy="spine-strat",
            chunk_version="spine-v1",
            source_attachment_checksum="spine-checksum",
        )

        summary_id = conn.execute(
            insert(summaries).values(
                scope_type="paper",
                scope_ref_json={"paper_ids": [paper_id]},
                content="Full summary content.",
                generated_by="spine-generator",
                chunk_version_verified_against="spine-v1",
                embedding_version_verified_against="spine-embed-v1",
            )
        ).inserted_primary_key[0]

        sentence_id = conn.execute(
            insert(summary_sentences).values(
                summary_id=summary_id,
                ordinal=1,
                text="A specific summary sentence.",
            )
        ).inserted_primary_key[0]

        mapping_id = conn.execute(
            insert(citation_mappings).values(
                summary_sentence_id=sentence_id,
                chunk_id=chunk_id,
                status="weak",
                chunk_version_verified_against="spine-v1",
                embedding_version_verified_against="spine-embed-v1",
            )
        ).inserted_primary_key[0]

        quote_id = conn.execute(
            insert(evidence_quotes).values(
                citation_mapping_id=mapping_id,
                chunk_id=chunk_id,
                quote_text="Source chunk text.",
                page_start=5,
                page_end=5,
                retrieval_confidence=0.7,
                quote_confidence=0.8,
                support_confidence=0.9,
            )
        ).inserted_primary_key[0]

        # Verify round-trip
        s_row = conn.execute(select(summaries).where(summaries.c.id == summary_id)).mappings().one()
        ss_row = conn.execute(select(summary_sentences).where(summary_sentences.c.id == sentence_id)).mappings().one()
        cm_row = conn.execute(select(citation_mappings).where(citation_mappings.c.id == mapping_id)).mappings().one()
        eq_row = conn.execute(select(evidence_quotes).where(evidence_quotes.c.id == quote_id)).mappings().one()

    assert s_row["content"] == "Full summary content."
    assert ss_row["summary_id"] == summary_id
    assert ss_row["ordinal"] == 1
    assert cm_row["summary_sentence_id"] == sentence_id
    assert cm_row["chunk_id"] == chunk_id
    assert cm_row["status"] == "weak"
    assert eq_row["citation_mapping_id"] == mapping_id
    assert eq_row["chunk_id"] == chunk_id
    assert eq_row["retrieval_confidence"] == 0.7
    assert eq_row["quote_confidence"] == 0.8
    assert eq_row["support_confidence"] == 0.9


def test_summary_cascade_delete(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)

    with engine.begin() as conn:
        # Enable foreign keys for SQLite
        conn.execute(text("PRAGMA foreign_keys = ON"))

        paper_id = create_paper(
            conn,
            title="Delete Paper",
            csl_json={"id": "delete", "type": "article-journal", "title": "Delete Paper"},
        )
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            checksum="delete-checksum",
            content_type="application/pdf",
        )
        chunk_id = create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="Chunk.",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="test",
            extraction_tool="test",
            extraction_version="1",
            chunking_strategy="test",
            chunk_version="1",
            source_attachment_checksum="delete-checksum",
        )

        summary_id = conn.execute(
            insert(summaries).values(
                scope_type="paper",
                chunk_version_verified_against="1",
                embedding_version_verified_against="1",
            )
        ).inserted_primary_key[0]

        sentence_id = conn.execute(
            insert(summary_sentences).values(summary_id=summary_id, ordinal=0, text="S1")
        ).inserted_primary_key[0]

        mapping_id = conn.execute(
            insert(citation_mappings).values(
                summary_sentence_id=sentence_id,
                chunk_id=chunk_id,
                status="verified",
                chunk_version_verified_against="1",
                embedding_version_verified_against="1",
            )
        ).inserted_primary_key[0]

        quote_id = conn.execute(
            insert(evidence_quotes).values(
                citation_mapping_id=mapping_id,
                chunk_id=chunk_id,
                quote_text="Q1",
                retrieval_confidence=1.0,
                quote_confidence=1.0,
                support_confidence=1.0,
            )
        ).inserted_primary_key[0]

        # Deleting summary should cascade to sentences, mappings, and quotes
        # But chunk should remain, and mapping/quote references to chunk should be SET NULL
        # Wait, if mapping is CASCADE deleted, its chunk_id is gone anyway.
        # If quote is CASCADE deleted, its chunk_id is gone anyway.
        # The schema says:
        # summary_sentences.summary_id: CASCADE
        # citation_mappings.summary_sentence_id: CASCADE
        # citation_mappings.chunk_id: SET NULL
        # evidence_quotes.citation_mapping_id: CASCADE
        # evidence_quotes.chunk_id: SET NULL

        conn.execute(summaries.delete().where(summaries.c.id == summary_id))

        sentence_exists = conn.execute(select(summary_sentences).where(summary_sentences.c.id == sentence_id)).first()
        mapping_exists = conn.execute(select(citation_mappings).where(citation_mappings.c.id == mapping_id)).first()
        quote_exists = conn.execute(select(evidence_quotes).where(evidence_quotes.c.id == quote_id)).first()
        chunk_row = conn.execute(select(chunks).where(chunks.c.id == chunk_id)).first()

    assert sentence_exists is None
    assert mapping_exists is None
    assert quote_exists is None
    assert chunk_row is not None


def test_annotation_repository_round_trip(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)
    bboxes = [
        {"page": 2, "x0": 10.0, "y0": 20.0, "x1": 120.0, "y1": 34.0},
        {"page": 2, "x0": 10.0, "y0": 36.0, "x1": 90.0, "y1": 50.0},
    ]
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Annotated Paper",
            csl_json={"id": "anno", "type": "article-journal", "title": "Annotated Paper"},
        )
        # An imported (Zotero) row leaves `source` NULL and must NOT be listed.
        conn.execute(
            insert(annotations).values(
                paper_id=paper_id, page=1, import_source="zotero", external_id="z-1", body="imported"
            )
        )
        annotation_id = create_annotation(
            conn,
            paper_id=paper_id,
            page=2,
            color="#7bc67e",
            bboxes_json=bboxes,
            anchor_text="hello world",
            prefix="pre",
            suffix="suf",
        )
        row = get_annotation(conn, annotation_id)
        listed = list_annotations_for_paper(conn, paper_id)

    assert row is not None
    assert row["source"] == "user"
    assert row["coordinate_system"] == "pdf-points-top-left"
    assert row["note"] is None
    assert row["color"] == "#7bc67e"
    assert row["bboxes_json"] == bboxes
    # Native-only scope: the imported row is excluded.
    assert [r["id"] for r in listed] == [annotation_id]

    with engine.begin() as conn:
        assert delete_annotation(conn, annotation_id) is True
        assert get_annotation(conn, annotation_id) is None
        assert delete_annotation(conn, 999999) is False
    engine.dispose()


def test_annotation_cascade_on_paper_delete(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        paper_id = create_paper(
            conn,
            title="Cascade Paper",
            csl_json={"id": "cascade", "type": "article-journal", "title": "Cascade Paper"},
        )
        annotation_id = create_annotation(
            conn,
            paper_id=paper_id,
            page=1,
            color="#6aa9ff",
            bboxes_json=[{"x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0}],
            anchor_text="x",
        )
        conn.execute(papers.delete().where(papers.c.id == paper_id))
        remaining = conn.execute(select(annotations).where(annotations.c.id == annotation_id)).first()

    assert remaining is None
    engine.dispose()


def test_update_annotation_partial_and_unknown(migrated_db_url: str) -> None:
    engine = make_engine(migrated_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Updatable",
            csl_json={"id": "upd", "type": "article-journal", "title": "Updatable"},
        )
        annotation_id = create_annotation(
            conn,
            paper_id=paper_id,
            page=1,
            color="#ffd54a",
            bboxes_json=[{"x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0}],
            anchor_text="x",
        )
        # Partial update: note only; color is left untouched.
        assert update_annotation(conn, annotation_id, note="hello") is True
        row = get_annotation(conn, annotation_id)
        assert row["note"] == "hello"
        assert row["color"] == "#ffd54a"

        # Update color and clear the note in one call.
        assert update_annotation(conn, annotation_id, note=None, color="#6aa9ff") is True
        row = get_annotation(conn, annotation_id)
        assert row["note"] is None
        assert row["color"] == "#6aa9ff"

        # No fields supplied → no-op; unknown id → False.
        assert update_annotation(conn, annotation_id) is False
        assert update_annotation(conn, 999999, note="x") is False
    engine.dispose()
