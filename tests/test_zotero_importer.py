from __future__ import annotations

import sqlite3
from pathlib import Path

import fitz
from sqlalchemy import func, select

from alembic import command
from alembic.config import Config
from app.backend.importers.zotero import import_zotero_library
from app.backend.importers.zotero_annotation_position import translate_zotero_position
from app.backend.pdf_processing.extraction import file_sha256
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import annotations, attachments, chunks, collection_papers, notes, papers, tags


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
        tag_rows = list(conn.execute(select(tags)).mappings())
        tag_names = {row["name"] for row in tag_rows}
        note_count = conn.execute(select(func.count()).select_from(notes)).scalar_one()
        annotation = conn.execute(select(annotations)).mappings().one()
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
    # backlog #9: Zotero-imported tags carry the formal namespaced provenance, not the bare "zotero" value used
    # for the paper/attachment/collection/note rows above.
    assert all(row["import_source"] == "import:zotero" for row in tag_rows)
    assert note_count == 1
    assert annotation["attachment_id"] == stored_attachment["id"]
    assert annotation["page"] == 1
    assert annotation["coordinate_system"] == "pdf-points-top-left"
    assert annotation["bboxes_json"] == [{"page": 1, "x0": 45.0, "y0": 55.0, "x1": 260.0, "y1": 80.0}]
    assert annotation["anchor_text"] == "Stored Zotero PDF quote appears here."
    assert annotation["note"] == "Fixture annotation comment"
    assert annotation["color"] == "#ffd400"
    assert annotation["position_json"] == {"raw": '{"pageIndex":0,"rects":[[45,340,260,365]]}'}
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


def test_zotero_importer_reports_created_paper_ids_and_chunk_ids_by_paper(temp_db_url: str, tmp_path: Path) -> None:
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        result = import_zotero_library(conn, zotero_dir)

    assert set(result.created_paper_ids) and len(result.created_paper_ids) == result.papers_created

    # DOIITEM1 is the only fixture item with an immediately-resolvable PDF -- it's the one paper that should
    # come back with real chunk ids recorded.
    assert result.chunk_ids_by_paper
    with engine.begin() as conn:
        for paper_id, chunk_ids in result.chunk_ids_by_paper.items():
            assert paper_id in result.created_paper_ids  # first run: every chunked paper here is newly created
            assert chunk_ids
            for chunk_id in chunk_ids:
                row = conn.execute(select(chunks.c.id).where(chunks.c.id == chunk_id)).first()
                assert row is not None


def test_zotero_importer_reports_progress(temp_db_url: str, tmp_path: Path) -> None:
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    engine = make_engine(temp_db_url)
    calls: list[tuple[int, int]] = []
    with engine.begin() as conn:
        import_zotero_library(conn, zotero_dir, on_progress=lambda current, total: calls.append((current, total)))

    assert calls
    totals = {total for _, total in calls}
    assert len(totals) == 1  # total item count stays constant across the run
    assert [current for current, _ in calls] == sorted(current for current, _ in calls)  # current is non-decreasing


def test_zotero_position_translation_fails_closed_without_false_exact_geometry(tmp_path: Path) -> None:
    pdf_path = tmp_path / "position.pdf"
    _make_pdf(pdf_path)

    malformed = translate_zotero_position({"raw": "not json"}, annotation_type=1, pdf_path=pdf_path)
    assert malformed.page is None and malformed.bboxes_json is None

    oversized = translate_zotero_position({"raw": "x" * 65_001}, annotation_type=1, pdf_path=pdf_path)
    assert oversized.page is None and oversized.bboxes_json is None

    out_of_bounds = translate_zotero_position(
        {"raw": '{"pageIndex":0,"rects":[[-1,340,260,365]]}'},
        annotation_type=1,
        pdf_path=pdf_path,
    )
    assert out_of_bounds.page == 1 and out_of_bounds.bboxes_json is None

    non_finite = translate_zotero_position(
        {"pageIndex": 0, "rects": [[45, 340, float("nan"), 365]]},
        annotation_type=1,
        pdf_path=pdf_path,
    )
    assert non_finite.page == 1 and non_finite.bboxes_json is None

    unsupported = translate_zotero_position(
        {"raw": '{"pageIndex":0,"rects":[[45,340,260,365]]}'},
        annotation_type=3,
        pdf_path=pdf_path,
    )
    assert unsupported.page == 1 and unsupported.bboxes_json is None

    rotated_path = tmp_path / "rotated.pdf"
    document = fitz.open(pdf_path)
    document[0].set_rotation(90)
    document.save(rotated_path)
    document.close()
    rotated = translate_zotero_position(
        {"raw": '{"pageIndex":0,"rects":[[45,340,260,365]]}'},
        annotation_type=1,
        pdf_path=rotated_path,
    )
    assert rotated.page == 1 and rotated.bboxes_json is None
    assert rotated.coordinate_system == "zotero-reader-json"


def test_zotero_importer_scopes_sibling_pdf_annotations_to_their_own_attachments(
    temp_db_url: str, tmp_path: Path
) -> None:
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    sibling_dir = zotero_dir / "storage" / "ATTACH02"
    sibling_dir.mkdir()
    _make_pdf(sibling_dir / "sibling.pdf", first_line="A different sibling PDF passage.")
    with sqlite3.connect(zotero_dir / "zotero.sqlite") as source:
        source.executemany(
            "INSERT INTO items (itemID, itemTypeID, key, libraryID) VALUES (?, ?, ?, ?)",
            [(13, 2, "ATTACH02", 1), (31, 4, "ANNOT002", 1)],
        )
        source.execute(
            """
            INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType, path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (13, 1, 0, "application/pdf", "storage:sibling.pdf"),
        )
        source.execute(
            """
            INSERT INTO itemAnnotations (itemID, parentItemID, type, text, comment, color, position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                31,
                13,
                1,
                "A different sibling PDF passage.",
                "Sibling annotation comment",
                "#7bc67e",
                '{"pageIndex":0,"rects":[[40,300,250,325]]}',
            ),
        )

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        import_zotero_library(conn, zotero_dir)
        paper_id = conn.execute(select(papers.c.id).where(papers.c.zotero_item_key == "DOIITEM1")).scalar_one()
        attachment_rows = list(conn.execute(select(attachments).where(attachments.c.paper_id == paper_id)).mappings())
        annotation_rows = list(conn.execute(select(annotations).where(annotations.c.paper_id == paper_id)).mappings())

    attachment_by_path = {row["original_path"]: row["id"] for row in attachment_rows}
    annotation_by_external_id = {row["external_id"]: row for row in annotation_rows}
    assert annotation_by_external_id["1:ANNOT001"]["attachment_id"] == attachment_by_path["storage:stored.pdf"]
    assert annotation_by_external_id["1:ANNOT002"]["attachment_id"] == attachment_by_path["storage:sibling.pdf"]
    assert (
        annotation_by_external_id["1:ANNOT001"]["attachment_id"]
        != annotation_by_external_id["1:ANNOT002"]["attachment_id"]
    )
    assert all(row["coordinate_system"] == "pdf-points-top-left" for row in annotation_rows)
    assert all(row["bboxes_json"] for row in annotation_rows)


def test_zotero_importer_persists_rotated_page_position_as_raw_only(temp_db_url: str, tmp_path: Path) -> None:
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    pdf_path = zotero_dir / "storage" / "ATTACHPDF" / "stored.pdf"
    with fitz.open(pdf_path) as document:
        document[0].set_rotation(90)
        document.saveIncr()

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        import_zotero_library(conn, zotero_dir)
        annotation = conn.execute(select(annotations).where(annotations.c.external_id == "1:ANNOT001")).mappings().one()

    assert annotation["attachment_id"] is not None
    assert annotation["page"] == 1
    assert annotation["coordinate_system"] == "zotero-reader-json"
    assert annotation["bboxes_json"] is None
    assert annotation["position_json"] == {"raw": '{"pageIndex":0,"rects":[[45,340,260,365]]}'}


def test_zotero_reimport_keeps_exact_annotation_pinned_when_attachment_is_relinked(
    temp_db_url: str, tmp_path: Path
) -> None:
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        import_zotero_library(conn, zotero_dir)
        original = conn.execute(select(annotations).where(annotations.c.external_id == "1:ANNOT001")).mappings().one()
        original_attachment_id = int(original["attachment_id"])
        original_bboxes = original["bboxes_json"]

    # Keep the same Zotero attachment/annotation identities but point them at a different, geometrically valid
    # PDF. Bounds alone cannot prove that an old exact mark belongs on these different bytes/text.
    replacement = zotero_dir / "storage" / "ATTACHPDF" / "replacement.pdf"
    _make_pdf(replacement, first_line="Replacement PDF with unrelated content.")
    with sqlite3.connect(zotero_dir / "zotero.sqlite") as source:
        source.execute(
            "UPDATE itemAttachments SET path = ? WHERE itemID = ?",
            ("storage:replacement.pdf", 10),
        )

    with engine.begin() as conn:
        import_zotero_library(conn, zotero_dir)
        after = conn.execute(select(annotations).where(annotations.c.external_id == "1:ANNOT001")).mappings().one()
        attachment_rows = list(
            conn.execute(select(attachments).where(attachments.c.paper_id == after["paper_id"])).mappings()
        )

    assert len([row for row in attachment_rows if row["content_type"] == "application/pdf"]) == 2
    assert after["attachment_id"] == original_attachment_id
    assert after["coordinate_system"] == "pdf-points-top-left"
    assert after["bboxes_json"] == original_bboxes


def test_zotero_importer_second_run_populates_chunk_ids_for_previously_missing_pdf(
    temp_db_url: str, tmp_path: Path
) -> None:
    # _make_zotero_fixture's KEYONLY1 item already models this case directly: its MISSLINK attachment points at
    # a linked-file path ("missing-linked.pdf") that doesn't exist on disk at fixture-build time -- no need for
    # a bespoke fixture or _make_zotero_edge_case_fixture.
    zotero_dir = _make_zotero_fixture(tmp_path / "zotero")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        first = import_zotero_library(conn, zotero_dir)
        key_only_paper_id = conn.execute(select(papers.c.id).where(papers.c.zotero_item_key == "KEYONLY1")).scalar_one()
    assert key_only_paper_id not in first.chunk_ids_by_paper

    # Materialize the previously-missing linked PDF at the exact path the fixture's attachment row points at.
    _make_pdf(zotero_dir / "missing-linked.pdf")

    with engine.begin() as conn:
        second = import_zotero_library(conn, zotero_dir)

    assert second.papers_created == 0
    assert second.papers_matched == first.papers_created + first.papers_matched
    assert key_only_paper_id in second.chunk_ids_by_paper
    assert second.chunk_ids_by_paper[key_only_paper_id]


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
        CREATE TABLE itemAnnotations (
            itemID INTEGER PRIMARY KEY,
            parentItemID INTEGER NOT NULL,
            type INTEGER NOT NULL,
            text TEXT,
            comment TEXT,
            color TEXT,
            position TEXT
        );
        """
    )


def _insert_fixture_rows(conn: sqlite3.Connection, zotero_dir: Path) -> None:
    conn.executemany(
        "INSERT INTO itemTypes (itemTypeID, typeName) VALUES (?, ?)",
        [
            (1, "journalArticle"),
            (2, "attachment"),
            (3, "note"),
            (4, "annotation"),
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
            (30, 4, "ANNOT001", 1),
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
    conn.execute(
        """
        INSERT INTO itemAnnotations (itemID, parentItemID, type, text, comment, color, position)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            30,
            10,
            1,
            "Stored Zotero PDF quote appears here.",
            "Fixture annotation comment",
            "#ffd400",
            '{"pageIndex":0,"rects":[[45,340,260,365]]}',
        ),
    )


def _make_pdf(path: Path, *, first_line: str = "Stored Zotero PDF quote appears here.") -> None:
    document = fitz.open()
    page = document.new_page(width=420, height=420)
    page.insert_text((50, 70), first_line, fontsize=12)
    page.insert_text((50, 105), "Additional paragraph text for chunk extraction.", fontsize=12)
    document.save(path)
    document.close()


def _tree_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): file_sha256(path) for path in sorted(root.rglob("*")) if path.is_file()}
