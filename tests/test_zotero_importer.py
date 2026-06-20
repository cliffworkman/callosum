from __future__ import annotations

import sqlite3
from pathlib import Path

import fitz
from sqlalchemy import func, select

from alembic import command
from alembic.config import Config
from app.backend.importers.zotero import import_zotero_library
from app.backend.pdf_processing.extraction import file_sha256
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import attachments, chunks, collection_papers, notes, papers, tags


def test_zotero_importer_maps_metadata_attachments_chunks_and_is_idempotent(tmp_path: Path) -> None:
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    source_db = zotero_dir / "zotero.sqlite"
    source_checksum_before = file_sha256(source_db)
    source_tree_before = _tree_hashes(zotero_dir)
    db_path = tmp_path / "callosum.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)

    with engine.begin() as conn:
        first_result = import_zotero_library(conn, zotero_dir)
        second_result = import_zotero_library(conn, zotero_dir)

        paper_rows = list(conn.execute(select(papers)).mappings())
        doi_paper = conn.execute(select(papers).where(papers.c.doi == "10.1234/callosum.zotero")).mappings().one()
        key_only_paper = conn.execute(select(papers).where(papers.c.zotero_item_key == "KEYONLY1")).mappings().one()
        stored_attachment = (
            conn.execute(
                select(attachments).where(
                    attachments.c.paper_id == doi_paper["id"],
                    attachments.c.content_type == "application/pdf",
                )
            )
            .mappings()
            .one()
        )
        missing_attachment = (
            conn.execute(
                select(attachments).where(
                    attachments.c.paper_id == key_only_paper["id"],
                    attachments.c.availability == "missing",
                )
            )
            .mappings()
            .one()
        )
        url_attachment = conn.execute(select(attachments).where(attachments.c.storage_mode == "url")).mappings().one()
        chunk_count = conn.execute(
            select(func.count()).select_from(chunks).where(chunks.c.paper_id == doi_paper["id"])
        ).scalar_one()
        quote_match = locate_quote_for_attachment(
            conn,
            int(stored_attachment["id"]),
            "Stored Zotero PDF quote appears here.",
        )
        tag_names = {row["name"] for row in conn.execute(select(tags)).mappings()}
        note_count = conn.execute(select(func.count()).select_from(notes)).scalar_one()
        collection_membership_count = conn.execute(select(func.count()).select_from(collection_papers)).scalar_one()

    assert first_result.papers_created == 3
    assert second_result.papers_created == 0
    assert second_result.papers_matched == 3
    assert len(paper_rows) == 3

    assert doi_paper["title"] == "Stored PDF Article"
    assert doi_paper["processing_tier"] == "fully-chunked"
    assert doi_paper["zotero_library_id"] == "1"
    assert doi_paper["zotero_item_key"] == "DOIITEM1"
    assert doi_paper["csl_json"]["DOI"] == "10.1234/CALLOSUM.ZOTERO"
    assert doi_paper["csl_json"]["zotero"]["key"] == "DOIITEM1"

    assert key_only_paper["doi"] is None
    assert key_only_paper["zotero_item_key"] == "KEYONLY1"
    assert missing_attachment["availability"] == "missing"
    assert missing_attachment["resolved_path"].endswith("missing-linked.pdf")

    assert stored_attachment["storage_mode"] == "linked"
    assert stored_attachment["availability"] == "available"
    assert stored_attachment["checksum"]
    assert stored_attachment["file_size"] > 0
    assert chunk_count > 0
    assert quote_match.found
    assert quote_match.page_start == 1

    assert url_attachment["storage_mode"] == "url"
    assert url_attachment["availability"] == "available"
    assert url_attachment["original_path"] == "https://example.test/zotero-link"

    assert tag_names == {"important", "review"}
    assert note_count == 1
    assert collection_membership_count == 1
    assert file_sha256(source_db) == source_checksum_before
    assert _tree_hashes(zotero_dir) == source_tree_before


def test_zotero_importer_edge_cases(tmp_path: Path) -> None:
    zotero_dir = _make_zotero_edge_case_fixture(tmp_path / "zotero_edge")
    db_path = tmp_path / "callosum_edge.sqlite"
    url = f"sqlite:///{db_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = make_engine(url)

    with engine.begin() as conn:
        # 1. Pre-insert a paper with mixed-case DOI
        create_paper(
            conn,
            title="Existing DOI Paper",
            doi="10.1234/CaseMismatch",
            csl_json={"id": "existing", "type": "article-journal", "title": "Existing DOI Paper"},
        )

        # 2. Import from Zotero which has the same DOI but in lowercase
        result = import_zotero_library(conn, zotero_dir)

        # Verify no-title fallback
        no_title_paper = conn.execute(select(papers).where(papers.c.zotero_item_key == "NOTITLE1")).mappings().one()
        assert no_title_paper["title"] == "Untitled Zotero Item NOTITLE1"

        # Verify linked-URL attachment
        url_paper = conn.execute(select(papers).where(papers.c.zotero_item_key == "URLITEM1")).mappings().one()
        url_attachment = (
            conn.execute(select(attachments).where(attachments.c.paper_id == url_paper["id"])).mappings().one()
        )
        assert url_attachment["attachment_type"] == "url"
        assert url_attachment["storage_mode"] == "url"
        # Ensure no chunks created for URL
        url_chunk_count = conn.execute(
            select(func.count()).select_from(chunks).where(chunks.c.attachment_id == url_attachment["id"])
        ).scalar_one()
        assert url_chunk_count == 0

        # Verify DOI casing idempotency (should match existing instead of creating new)
        doi_papers = list(conn.execute(select(papers).where(papers.c.doi == "10.1234/casemismatch")).mappings())
        assert len(doi_papers) == 1
        assert doi_papers[0]["title"] == "Existing DOI Paper"

    assert result.papers_created == 2  # NOTITLE1 and URLITEM1. DOIITEM1 was matched.
    assert result.papers_matched == 1  # DOIITEM1


def _make_zotero_edge_case_fixture(zotero_dir: Path) -> Path:
    zotero_dir.mkdir()
    conn = sqlite3.connect(zotero_dir / "zotero.sqlite")
    try:
        _create_zotero_schema(conn)

        conn.executemany(
            "INSERT INTO itemTypes (itemTypeID, typeName) VALUES (?, ?)",
            [(1, "journalArticle"), (2, "attachment")],
        )
        conn.executemany(
            "INSERT INTO fields (fieldID, fieldName) VALUES (?, ?)",
            [(1, "title"), (2, "DOI")],
        )
        conn.executemany(
            "INSERT INTO itemDataValues (valueID, value) VALUES (?, ?)",
            [
                (1, "10.1234/casemismatch"),
                (2, "URL Item"),
            ],
        )
        conn.executemany(
            "INSERT INTO items (itemID, itemTypeID, key, libraryID) VALUES (?, ?, ?, ?)",
            [
                (1, 1, "DOIITEM1", 1),
                (2, 1, "NOTITLE1", 1),
                (3, 1, "URLITEM1", 1),
                (10, 2, "URLLINK1", 1),
            ],
        )
        conn.executemany(
            "INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, ?, ?)",
            [
                (1, 2, 1),
                (3, 1, 2),
            ],
        )
        conn.execute(
            """
            INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType, path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (10, 3, 3, "text/html", "https://example.test/edge"),
        )
        conn.commit()
    finally:
        conn.close()
    return zotero_dir


def _make_zotero_fixture(zotero_dir: Path) -> Path:
    zotero_dir.mkdir()
    storage_dir = zotero_dir / "storage" / "ATTACHPDF"
    storage_dir.mkdir(parents=True)
    _make_pdf(storage_dir / "stored.pdf")

    conn = sqlite3.connect(zotero_dir / "zotero.sqlite")
    try:
        _create_zotero_schema(conn)
        _insert_fixture_rows(conn, zotero_dir)
        conn.commit()
    finally:
        conn.close()
    return zotero_dir


def _create_zotero_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT NOT NULL);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INTEGER NOT NULL, key TEXT NOT NULL, libraryID INTEGER);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT NOT NULL);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE itemData (itemID INTEGER NOT NULL, fieldID INTEGER NOT NULL, valueID INTEGER NOT NULL);
        CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT);
        CREATE TABLE itemCreators (itemID INTEGER NOT NULL, creatorID INTEGER NOT NULL, orderIndex INTEGER);
        CREATE TABLE itemAttachments (
            itemID INTEGER PRIMARY KEY,
            parentItemID INTEGER,
            linkMode INTEGER NOT NULL,
            contentType TEXT,
            path TEXT
        );
        CREATE TABLE collections (
            collectionID INTEGER PRIMARY KEY,
            key TEXT,
            collectionName TEXT NOT NULL,
            parentCollectionID INTEGER
        );
        CREATE TABLE collectionItems (collectionID INTEGER NOT NULL, itemID INTEGER NOT NULL);
        CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE itemTags (itemID INTEGER NOT NULL, tagID INTEGER NOT NULL);
        CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, note TEXT);
        """
    )


def _insert_fixture_rows(conn: sqlite3.Connection, zotero_dir: Path) -> None:
    conn.executemany(
        "INSERT INTO itemTypes (itemTypeID, typeName) VALUES (?, ?)",
        [
            (1, "journalArticle"),
            (2, "attachment"),
            (3, "note"),
        ],
    )
    fields = [
        (1, "title"),
        (2, "DOI"),
        (3, "abstractNote"),
        (4, "date"),
        (5, "publicationTitle"),
        (6, "language"),
    ]
    conn.executemany("INSERT INTO fields (fieldID, fieldName) VALUES (?, ?)", fields)
    values = [
        (1, "Stored PDF Article"),
        (2, "10.1234/CALLOSUM.ZOTERO"),
        (3, "An abstract imported from Zotero."),
        (4, "2025-04-01"),
        (5, "Journal of Fixtures"),
        (6, "en"),
        (7, "Key Only Article"),
        (8, "2024"),
        (9, "URL Attachment Article"),
        (10, "2023"),
    ]
    conn.executemany("INSERT INTO itemDataValues (valueID, value) VALUES (?, ?)", values)
    conn.executemany(
        "INSERT INTO items (itemID, itemTypeID, key, libraryID) VALUES (?, ?, ?, ?)",
        [
            (1, 1, "DOIITEM1", 1),
            (2, 1, "KEYONLY1", 1),
            (3, 1, "URLITEM1", 1),
            (10, 2, "ATTACHPDF", 1),
            (11, 2, "MISSLINK", 1),
            (12, 2, "URLLINK", 1),
            (20, 3, "NOTE0001", 1),
        ],
    )
    item_data = [
        (1, 1, 1),
        (1, 2, 2),
        (1, 3, 3),
        (1, 4, 4),
        (1, 5, 5),
        (1, 6, 6),
        (2, 1, 7),
        (2, 4, 8),
        (3, 1, 9),
        (3, 4, 10),
    ]
    conn.executemany("INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, ?, ?)", item_data)
    conn.executemany(
        "INSERT INTO creators (creatorID, firstName, lastName) VALUES (?, ?, ?)",
        [(1, "Ada", "Lovelace"), (2, "Grace", "Hopper")],
    )
    conn.executemany(
        "INSERT INTO itemCreators (itemID, creatorID, orderIndex) VALUES (?, ?, ?)",
        [(1, 1, 0), (2, 2, 0)],
    )
    missing_path = zotero_dir / "missing-linked.pdf"
    conn.executemany(
        """
        INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType, path)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (10, 1, 0, "application/pdf", "storage:stored.pdf"),
            (11, 2, 2, "application/pdf", str(missing_path)),
            (12, 3, 3, "text/html", "https://example.test/zotero-link"),
        ],
    )
    conn.execute(
        "INSERT INTO collections (collectionID, key, collectionName, parentCollectionID) VALUES (?, ?, ?, ?)",
        (1, "COLL0001", "Fixture Collection", None),
    )
    conn.execute("INSERT INTO collectionItems (collectionID, itemID) VALUES (?, ?)", (1, 1))
    conn.executemany("INSERT INTO tags (tagID, name) VALUES (?, ?)", [(1, "important"), (2, "review")])
    conn.executemany("INSERT INTO itemTags (itemID, tagID) VALUES (?, ?)", [(1, 1), (2, 2)])
    conn.execute(
        "INSERT INTO itemNotes (itemID, parentItemID, note) VALUES (?, ?, ?)",
        (20, 1, "<p>Fixture note body</p>"),
    )


def _make_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=420, height=420)
    page.insert_text((50, 70), "Stored Zotero PDF quote appears here.", fontsize=12)
    page.insert_text((50, 105), "Additional paragraph text for chunk extraction.", fontsize=12)
    document.save(path)
    document.close()


def _tree_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): file_sha256(path) for path in sorted(root.rglob("*")) if path.is_file()}
