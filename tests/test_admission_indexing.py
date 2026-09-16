"""The post-admission indexing invariant, enforced across every metadata-admission front end (#61).

**The rule under test:** if a record is admitted to the active Library and has enough metadata to
participate in the paper-level index, its indexing state must not depend on which front end created it.

Callosum has no single successful-admission lifecycle seam — a dozen ``create_paper`` call sites and
no post-admission hook — so this was previously a convention each front end had to remember, and
several did not. This test is what makes the invariant enforced rather than remembered: a new
admission endpoint that forgets to index fails here instead of silently shipping papers that are
invisible to every paper-level vector path.

Hermetic: fake embedding model + in-memory vector store, injected Crossref, no network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.api import create_app
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import embeddings
from tests.api_helpers import ApiFakeEmbeddingModel


class _FakeCrossref:
    def resolve_doi(self, conn, doi):
        from integrations.crossref.adapter import CrossrefResolution

        return CrossrefResolution(
            doi=doi,
            resolved=True,
            csl_json={
                "DOI": doi,
                "title": "An Admitted Paper",
                "abstract": "Enough text for the paper-level embedding to be non-empty.",
                "container-title": "Journal of Admission",
                "issued": {"date-parts": [[2024]]},
                "author": [{"family": "Rivera", "given": "A"}],
            },
        )


def _paper_embedding_count(db_url: str, paper_id: int) -> int:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        count = conn.execute(
            select(func.count())
            .select_from(embeddings)
            .where(embeddings.c.target_type == "paper", embeddings.c.target_id == paper_id)
        ).scalar_one()
    engine.dispose()
    return int(count)


def _client(temp_db_url: str) -> TestClient:
    return TestClient(
        create_app(
            db_url=temp_db_url,
            crossref_client=_FakeCrossref(),
            embedding_model=ApiFakeEmbeddingModel(),
            vector_store=InMemoryVectorStore(),
        )
    )


def _admit_by_doi(client: TestClient) -> int:
    resp = client.post("/papers/by-doi", json={"doi": "10.1/admitted-by-doi", "acquire_oa": False})
    assert resp.status_code in (200, 201), resp.text  # 201 on create, 200 when surfacing an existing paper
    return int(resp.json()["paper_id"])


def _admit_by_discovery_save(client: TestClient) -> int:
    resp = client.post(
        "/discovery/save",
        json={
            "title": "An Admitted Paper",
            "doi": "10.1/admitted-by-discovery",
            "abstract": "Enough text for the paper-level embedding to be non-empty.",
            "authors": ["Rivera, A"],
            "journal": "Journal of Admission",
            "year": 2024,
        },
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["paper_id"])


def _admit_by_zotero_resolve(client: TestClient) -> int:
    resp = client.post(
        "/citations/zotero/resolve",
        json={
            "items": [
                {
                    "item_data": {
                        "type": "article-journal",
                        "title": "An Admitted Paper",
                        "DOI": "10.1/admitted-by-zotero",
                        "issued": {"date-parts": [[2024]]},
                        "author": [{"family": "Rivera", "given": "A"}],
                    },
                    "uris": ["http://zotero.org/users/1/items/ADMIT001"],
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()[0]["paper_id"])


ADMISSION_FRONT_ENDS = [
    pytest.param(_admit_by_doi, id="library-add-by-doi"),
    pytest.param(_admit_by_discovery_save, id="discovery-save"),
    pytest.param(_admit_by_zotero_resolve, id="zotero-citation-resolve"),
]


@pytest.mark.parametrize("admit", ADMISSION_FRONT_ENDS)
def test_every_admission_front_end_indexes_the_paper(temp_db_url: str, admit) -> None:
    client = _client(temp_db_url)
    paper_id = admit(client)
    assert _paper_embedding_count(temp_db_url, paper_id) == 1, (
        "an admitted paper must be indexed regardless of which front end created it"
    )


@pytest.mark.parametrize("admit", ADMISSION_FRONT_ENDS)
def test_admission_indexing_does_no_duplicate_work_on_a_second_run(temp_db_url: str, admit) -> None:
    """The invariant is idempotent: re-admitting the same record must not write a second embedding."""
    client = _client(temp_db_url)
    paper_id = admit(client)
    again = admit(client)

    assert again == paper_id, "the second admission should surface the same paper, not create another"
    assert _paper_embedding_count(temp_db_url, paper_id) == 1
