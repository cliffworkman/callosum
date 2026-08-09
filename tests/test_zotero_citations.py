from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api.app import create_app
from app.backend.importers.zotero import normalize_zotero_csl_item
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import papers

# --- normalize_zotero_csl_item (pure) -----------------------------------------------------------------------


def test_normalize_zotero_csl_item_extracts_doi_year_author_and_uri_identity():
    item_data = {
        "type": "article-journal",
        "title": "A Real Paper",
        "author": [{"family": "Smith", "given": "Jane"}, {"family": "Jones", "given": "Al"}],
        "issued": {"date-parts": [[2021, 5, 1]]},
        "DOI": "10.1/real",
        "container-title": "Journal of Things",
        "language": "en",
    }
    uris = ["http://zotero.org/users/123/items/ABCD1234"]
    out = normalize_zotero_csl_item(item_data, uris)
    assert out["title"] == "A Real Paper"
    assert out["doi"] == "10.1/real"
    assert out["year"] == 2021
    assert out["first_author_family_name"] == "Smith"
    assert out["venue"] == "Journal of Things"
    assert out["item_type"] == "article-journal"
    assert out["language"] == "en"
    assert out["zotero_library_id"] == "123"
    assert out["zotero_item_key"] == "ABCD1234"
    assert out["imported_source"] == "zotero"
    assert out["processing_tier"] == "metadata-only"
    assert out["csl_json"] == item_data


def test_normalize_zotero_csl_item_tolerates_missing_fields():
    out = normalize_zotero_csl_item({}, [])
    assert out["title"] == "Untitled Zotero Citation"
    assert out["doi"] is None
    assert out["year"] is None
    assert out["first_author_family_name"] is None
    assert out["zotero_library_id"] is None
    assert out["zotero_item_key"] is None


def test_normalize_zotero_csl_item_ignores_malformed_issued_and_non_matching_uri():
    out = normalize_zotero_csl_item({"issued": {"date-parts": "not-a-list"}}, ["https://example.com/not-zotero"])
    assert out["year"] is None
    assert out["zotero_library_id"] is None
    assert out["zotero_item_key"] is None


# --- POST /citations/zotero/resolve --------------------------------------------------------------------------


def _seed(conn, title, doi=None, year=None, first_author_family_name=None):
    return create_paper(
        conn,
        title=title,
        csl_json={"title": title, **({"DOI": doi} if doi else {})},
        doi=doi,
        year=year,
        first_author_family_name=first_author_family_name,
    )


def test_resolve_matches_existing_paper_by_doi(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _seed(conn, "Existing Paper", doi="10.1/existing")
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    resp = client.post(
        "/citations/zotero/resolve",
        json={"items": [{"item_data": {"title": "Existing Paper", "DOI": "10.1/existing"}, "uris": []}]},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert len(result) == 1
    assert result[0]["paper_id"] == paper_id
    assert result[0]["created"] is False


def test_resolve_matches_existing_paper_by_zotero_key_from_uri(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Keyed Paper",
            csl_json={"title": "Keyed Paper"},
            zotero_library_id="123",
            zotero_item_key="ABCD1234",
        )
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    resp = client.post(
        "/citations/zotero/resolve",
        json={
            "items": [
                {
                    "item_data": {"title": "Keyed Paper (different casing sent by Zotero)"},
                    "uris": ["http://zotero.org/users/123/items/ABCD1234"],
                }
            ]
        },
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result[0]["paper_id"] == paper_id
    assert result[0]["created"] is False


def test_resolve_matches_existing_paper_by_title_year_author(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = _seed(conn, "No DOI Paper", year=2019, first_author_family_name="Kim")
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    resp = client.post(
        "/citations/zotero/resolve",
        json={
            "items": [
                {
                    "item_data": {
                        "title": "No DOI Paper",
                        "issued": {"date-parts": [[2019]]},
                        "author": [{"family": "Kim", "given": "S"}],
                    },
                    "uris": [],
                }
            ]
        },
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result[0]["paper_id"] == paper_id
    assert result[0]["created"] is False


def test_resolve_creates_metadata_only_paper_when_no_match(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    resp = client.post(
        "/citations/zotero/resolve",
        json={
            "items": [
                {
                    "item_data": {
                        "type": "article-journal",
                        "title": "Brand New Work",
                        "DOI": "10.1/brand-new",
                        "issued": {"date-parts": [[2022]]},
                        "author": [{"family": "Nguyen", "given": "T"}],
                    },
                    "uris": ["http://zotero.org/groups/9/items/ZZZ99999"],
                }
            ]
        },
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result[0]["created"] is True
    paper_id = result[0]["paper_id"]

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        row = conn.execute(select(papers).where(papers.c.id == paper_id)).mappings().one()
    engine.dispose()
    assert row["title"] == "Brand New Work"
    assert row["doi"] == "10.1/brand-new"
    assert row["imported_source"] == "zotero"
    assert row["processing_tier"] == "metadata-only"
    assert row["zotero_library_id"] == "9"
    assert row["zotero_item_key"] == "ZZZ99999"


def test_resolve_rejects_empty_and_over_cap_input(temp_db_url):
    from app.backend.api.routers.zotero_citations import MAX_ZOTERO_DISTINCT_WORKS

    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/citations/zotero/resolve", json={"items": []}).status_code == 422
    too_many = [{"item_data": {"title": f"T{i}"}, "uris": []} for i in range(MAX_ZOTERO_DISTINCT_WORKS + 1)]
    assert client.post("/citations/zotero/resolve", json={"items": too_many}).status_code == 422
