from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from tests.api_helpers import _seed_library


def test_seed_library_populates_item_type_filter_fixture(temp_db_url: str) -> None:
    _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get("/papers/item-types")

    assert response.status_code == 200
    assert response.json() == [{"item_type": "article-journal", "count": 2}]
