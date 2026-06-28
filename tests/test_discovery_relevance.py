"""inc 185 — discovery SP1b: the axis-relevance highlight (a hint, never a filter).

Hermetic — a tiny keyword embedding model (2-D) makes cosine deterministic; axes are inserted directly. The
endpoint is exercised via ``create_app(embedding_model=...)``. Local — no egress.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.backend.api import create_app
from app.backend.clustering.my_publications import MY_PUBLICATIONS_KIND
from app.backend.discovery.relevance import score_axis_relevance
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import axes


def _vec(text: str) -> list[float]:
    t = text.lower()
    if "alpha" in t:
        return [1.0, 0.0]
    if "mid" in t:
        return [0.6, 0.8]  # already unit; cos with [1,0] = 0.6
    if "beta" in t:
        return [0.0, 1.0]
    return [0.0, 0.0]


class _KwModel:
    name = "kw"
    version = "v1"
    dimension = 2
    normalization = "none"

    def encode_texts(self, texts):
        return [_vec(t) for t in texts]


def _axis(conn, description, *, kind="standard", gain=None, label="Ax"):
    return int(
        conn.execute(
            insert(axes).values(label=label, description=description, kind=kind, scoring_gain=gain)
        ).inserted_primary_key[0]
    )


def test_relevance_returns_best_axis_above_cutoff(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        aid = _axis(conn, "alpha topics", label="Alpha")
        out = score_axis_relevance(
            conn,
            [{"dedup_key": "d1", "text": "Alpha study of things"}, {"dedup_key": "d2", "text": "Beta study"}],
            embedding_model=_KwModel(),
        )
    engine.dispose()
    assert set(out) == {"d1"}  # the beta item's best match is 0.0 < 0.35 → no badge
    assert out["d1"] == {"axis_id": aid, "axis_label": "Alpha", "similarity": 1.0}


def test_relevance_respects_per_axis_cutoff(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _axis(conn, "alpha topics", label="Alpha", gain=0.7)  # a stricter cutoff
        out = score_axis_relevance(
            conn,
            [{"dedup_key": "hi", "text": "Alpha paper"}, {"dedup_key": "mid", "text": "mid relevance paper"}],
            embedding_model=_KwModel(),
        )
    engine.dispose()
    assert set(out) == {"hi"}  # 1.0 >= 0.7 kept; the mid item (0.6 < 0.7) is omitted (no badge ≠ irrelevant)
    assert out["hi"]["similarity"] == 1.0


def test_relevance_excludes_my_publications_axis(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _axis(conn, "alpha topics", label="My Pubs", kind=MY_PUBLICATIONS_KIND)
        out = score_axis_relevance(conn, [{"dedup_key": "d1", "text": "Alpha study"}], embedding_model=_KwModel())
    engine.dispose()
    assert out == {}  # the authorship axis is not a topical lens


def test_relevance_no_axes_or_no_items(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert score_axis_relevance(conn, [{"dedup_key": "d1", "text": "Alpha"}], embedding_model=_KwModel()) == {}
        _axis(conn, "alpha topics")
        assert score_axis_relevance(conn, [], embedding_model=_KwModel()) == {}
    engine.dispose()


def test_relevance_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _axis(conn, "alpha topics", label="Alpha")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_KwModel()))
    r = client.post(
        "/discovery/relevance",
        json={
            "items": [
                {"dedup_key": "d1", "title": "Alpha", "abstract": "alpha methods"},
                {"dedup_key": "d2", "title": "Beta", "abstract": ""},
            ]
        },
    )
    assert r.status_code == 200
    rel = r.json()["relevance"]
    assert set(rel) == {"d1"} and rel["d1"]["axis_label"] == "Alpha"
    # bad inputs fail closed
    assert client.post("/discovery/relevance", json={"items": []}).status_code == 422
