from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, insert, select

from alembic import command
from alembic.config import Config
from app.backend.importers import mendeley as mendeley_importer
from app.backend.importers.mendeley import (
    MENDELEY_ID_PROVIDER,
    MendeleyImportError,
    import_mendeley_snapshot,
    normalize_mendeley_document,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import (
    collection_papers,
    collections,
    paper_external_identifiers,
    papers,
)

DOC_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOC_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
DOC_C = "cccccccc-cccc-cccc-cccc-cccccccccccc"
FOLDER_A = "11111111-1111-1111-1111-111111111111"
FOLDER_B = "22222222-2222-2222-2222-222222222222"


def _engine(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'callosum.sqlite').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return make_engine(url)


def _document(document_id: str, title: str, **overrides):
    document = {
        "id": document_id,
        "title": title,
        "type": "journal",
        "authors": [{"first_name": "Ada", "last_name": "Scholar"}],
        "year": 2025,
        "source": "Journal of Bounded Imports",
        "identifiers": {"doi": f"10.1234/{document_id[:8]}", "pmid": document_id[:8]},
    }
    document.update(overrides)
    return document


def _folders():
    return (
        {"id": FOLDER_A, "name": "Evidence"},
        {"id": FOLDER_B, "name": "Null results", "parent_id": FOLDER_A},
    )


def test_document_normalization_uses_existing_csl_contract_and_bounded_official_fields() -> None:
    csl = normalize_mendeley_document(
        _document(
            DOC_A,
            "A bounded study",
            abstract="A synthetic abstract.",
            websites=["https://example.test/article"],
            volume="12",
            issue="3",
            pages="10-20",
            publisher="Example Press",
            language="en",
            citation_key="Scholar2025",
        )
    )

    assert csl == {
        "id": DOC_A,
        "type": "article-journal",
        "title": "A bounded study",
        "mendeley": {
            "document_id": DOC_A,
            "document_type": "journal",
            "identifiers": {"doi": "10.1234/aaaaaaaa", "pmid": "aaaaaaaa"},
            "websites": ["https://example.test/article"],
        },
        "author": [{"family": "Scholar", "given": "Ada"}],
        "issued": {"date-parts": [[2025]]},
        "container-title": "Journal of Bounded Imports",
        "abstract": "A synthetic abstract.",
        "DOI": "10.1234/aaaaaaaa",
        "volume": "12",
        "issue": "3",
        "page": "10-20",
        "publisher": "Example Press",
        "language": "en",
        "citation-key": "Scholar2025",
        "URL": "https://example.test/article",
    }


def test_snapshot_import_deduplicates_by_canonical_identity_and_source_id_and_preserves_folders(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with engine.begin() as conn:
        existing_id = create_paper(
            conn,
            title="Existing canonical record",
            csl_json={"title": "Existing canonical record", "DOI": "10.1234/aaaaaaaa"},
            doi="10.1234/aaaaaaaa",
        )
        documents = (
            _document(DOC_A, "Provider title differs only because DOI wins"),
            _document(DOC_B, "Identity-poor record", authors=[], year=None, identifiers={}),
        )
        memberships = {FOLDER_A: (DOC_A,), FOLDER_B: (DOC_A, DOC_B)}
        first = import_mendeley_snapshot(conn, documents=documents, folders=_folders(), folder_document_ids=memberships)
        second = import_mendeley_snapshot(
            conn, documents=documents, folders=_folders(), folder_document_ids={FOLDER_A: (), FOLDER_B: (DOC_B,)}
        )

        paper_rows = list(conn.execute(select(papers)).mappings())
        provenance = list(
            conn.execute(
                select(paper_external_identifiers).where(paper_external_identifiers.c.provider == MENDELEY_ID_PROVIDER)
            ).mappings()
        )
        folder_rows = list(conn.execute(select(collections).order_by(collections.c.external_id)).mappings())
        membership_rows = list(conn.execute(select(collection_papers)).mappings())

    assert first.papers_created == 1 and first.papers_matched == 1
    assert second.papers_created == 0 and second.papers_matched == 2
    assert len(paper_rows) == 2
    assert {row["identifier"] for row in provenance} == {DOC_A, DOC_B}
    assert next(row for row in provenance if row["identifier"] == DOC_A)["paper_id"] == existing_id
    assert [row["name"] for row in folder_rows] == ["Evidence", "Null results"]
    assert folder_rows[1]["parent_id"] == folder_rows[0]["id"]
    assert len(membership_rows) == 1
    identity_poor_id = next(row["id"] for row in paper_rows if row["title"] == "Identity-poor record")
    assert membership_rows[0]["paper_id"] == identity_poor_id
    assert membership_rows[0]["collection_id"] == folder_rows[1]["id"]


def test_two_source_documents_that_share_a_doi_link_to_one_paper_and_one_folder_membership(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    same_doi = {"doi": "10.1234/shared"}
    with engine.begin() as conn:
        result = import_mendeley_snapshot(
            conn,
            documents=(
                _document(DOC_A, "First", identifiers=same_doi),
                _document(DOC_B, "Second", identifiers=same_doi),
            ),
            folders=({"id": FOLDER_A, "name": "Shared"},),
            folder_document_ids={FOLDER_A: (DOC_A, DOC_B)},
        )
        paper_count = conn.execute(select(func.count()).select_from(papers)).scalar_one()
        provenance_count = conn.execute(
            select(func.count())
            .select_from(paper_external_identifiers)
            .where(paper_external_identifiers.c.provider == MENDELEY_ID_PROVIDER)
        ).scalar_one()
        membership_count = conn.execute(select(func.count()).select_from(collection_papers)).scalar_one()

    assert result.papers_created == 1 and result.papers_matched == 1
    assert result.memberships_imported == 1
    assert (paper_count, provenance_count, membership_count) == (1, 2, 1)


@pytest.mark.parametrize(
    ("folders", "memberships", "message"),
    [
        (({"id": FOLDER_A, "name": "A", "parent_id": FOLDER_B},), {}, "missing parent"),
        (
            (
                {"id": FOLDER_A, "name": "A", "parent_id": FOLDER_B},
                {"id": FOLDER_B, "name": "B", "parent_id": FOLDER_A},
            ),
            {},
            "cycle",
        ),
        (({"id": FOLDER_A, "name": "A"},), {FOLDER_B: (DOC_A,)}, "unknown folder"),
        (({"id": FOLDER_A, "name": "A"},), {FOLDER_A: (DOC_B,)}, "unknown document"),
    ],
)
def test_snapshot_rejects_orphan_cycle_and_unknown_memberships(folders, memberships, message) -> None:
    with pytest.raises(MendeleyImportError, match=message):
        import_mendeley_snapshot(
            _NoWriteConnection(),
            documents=(_document(DOC_A, "One"),),
            folders=folders,
            folder_document_ids=memberships,
        )


def test_snapshot_conflict_rolls_back_prior_paper_and_provenance_writes(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with engine.begin() as conn:
        source_paper = create_paper(conn, title="Source", csl_json={"title": "Source"})
        doi_paper = create_paper(
            conn,
            title="DOI owner",
            csl_json={"title": "DOI owner", "DOI": "10.1234/conflict"},
            doi="10.1234/conflict",
        )
        conn.execute(
            insert(paper_external_identifiers).values(
                paper_id=source_paper,
                provider=MENDELEY_ID_PROVIDER,
                identifier=DOC_B,
            )
        )
        before = conn.execute(select(func.count()).select_from(papers)).scalar_one()

        with pytest.raises(MendeleyImportError, match="conflicts"):
            import_mendeley_snapshot(
                conn,
                documents=(
                    _document(DOC_A, "Would otherwise be created"),
                    _document(DOC_B, "Conflicting identity", identifiers={"doi": "10.1234/conflict"}),
                ),
                folders=({"id": FOLDER_A, "name": "Never written"},),
                folder_document_ids={FOLDER_A: (DOC_A,)},
            )

        assert conn.execute(select(func.count()).select_from(papers)).scalar_one() == before
        assert conn.execute(select(func.count()).select_from(collections)).scalar_one() == 0
        assert (
            conn.execute(
                select(func.count())
                .select_from(paper_external_identifiers)
                .where(paper_external_identifiers.c.identifier == DOC_A)
            ).scalar_one()
            == 0
        )
        assert source_paper != doi_paper


def test_bounds_and_malformed_payloads_fail_before_database_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mendeley_importer, "MAX_DOCUMENTS", 1)
    with pytest.raises(MendeleyImportError, match="documents exceeded"):
        import_mendeley_snapshot(
            _NoWriteConnection(),
            documents=(_document(DOC_A, "One"), _document(DOC_B, "Two")),
            folders=(),
            folder_document_ids={},
        )
    with pytest.raises(MendeleyImportError, match="last name"):
        normalize_mendeley_document(_document(DOC_A, "One", authors=[{"first_name": "No family"}]))
    with pytest.raises(MendeleyImportError, match="document-ID collection"):
        import_mendeley_snapshot(
            _NoWriteConnection(),
            documents=(_document(DOC_A, "One"),),
            folders=({"id": FOLDER_A, "name": "A"},),
            folder_document_ids={FOLDER_A: DOC_A},
        )


class _NoWriteConnection:
    def begin_nested(self):  # pragma: no cover - reaching this means validation did not fail closed
        raise AssertionError("database access occurred before snapshot validation")
