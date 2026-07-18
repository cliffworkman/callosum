"""inc 219 — the reading queue: the repo (add/list/remove/reorder, idempotent, trashed-excluded, CASCADE) + the
4 endpoints. Hermetic (temp_db_url + make_engine / TestClient)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.reading_queue_repo import (
    add_to_queue,
    list_reading_queue,
    remove_from_queue,
    set_queue_order,
)
from app.backend.persistence.repository import create_paper, soft_delete_paper
from app.backend.persistence.schema import papers


def _paper(conn, title, **kw) -> int:
    csl = kw.pop("csl_json", {"title": title, "author": [{"family": title, "given": "A."}]})
    return create_paper(conn, title=title, csl_json=csl, **kw)


# ---- repo ------------------------------------------------------------------


def test_add_list_idempotent_and_authors(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Alpha", year=2020)
        b = _paper(conn, "Beta", year=2021)
        assert add_to_queue(conn, a) is True
        assert add_to_queue(conn, b) is True
        assert add_to_queue(conn, a) is False  # idempotent — no duplicate row
        rows = list_reading_queue(conn)
    engine.dispose()
    assert [r["id"] for r in rows] == [a, b]  # insertion order (position 0,1)
    first = rows[0]
    assert first["title"] == "Alpha" and first["year"] == 2020


def test_list_excludes_trashed_papers(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Live")
        b = _paper(conn, "Trashed")
        add_to_queue(conn, a)
        add_to_queue(conn, b)
        soft_delete_paper(conn, b)
        ids = [r["id"] for r in list_reading_queue(conn)]
    engine.dispose()
    assert ids == [a]  # the trashed paper's queue row exists but is hidden from the list


def test_remove_is_idempotent(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Alpha")
        add_to_queue(conn, a)
        assert remove_from_queue(conn, a) is True
        assert remove_from_queue(conn, a) is False  # already gone
        assert list_reading_queue(conn) == []
    engine.dispose()


def test_set_order_reorders_and_rejects_foreign_set(temp_db_url):
    import pytest

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Alpha")
        b = _paper(conn, "Beta")
        c = _paper(conn, "Gamma")
        for pid in (a, b, c):
            add_to_queue(conn, pid)
        set_queue_order(conn, [c, a, b])
        assert [r["id"] for r in list_reading_queue(conn)] == [c, a, b]
        # a partial set, a foreign id, or a wrong-length list → ValueError (the full-id-list contract)
        with pytest.raises(ValueError):
            set_queue_order(conn, [c, a])
        with pytest.raises(ValueError):
            set_queue_order(conn, [c, a, 99999])
    engine.dispose()


def test_purging_a_paper_cascade_drops_its_queue_row(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Alpha")
        add_to_queue(conn, a)
        conn.execute(delete(papers).where(papers.c.id == a))  # FK ondelete=CASCADE fires
        assert list_reading_queue(conn) == []
    engine.dispose()


# ---- endpoints -------------------------------------------------------------


def test_reading_queue_endpoints(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Alpha", year=2019)
        b = _paper(conn, "Beta", year=2020)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    assert client.get("/reading-queue").json() == []
    assert client.post("/reading-queue", json={"paper_id": a}).json() == {"added": True}
    assert client.post("/reading-queue", json={"paper_id": a}).json() == {"added": False}  # idempotent
    client.post("/reading-queue", json={"paper_id": b})

    listed = client.get("/reading-queue").json()
    assert [it["id"] for it in listed] == [a, b]
    assert listed[0]["title"] == "Alpha" and listed[0]["authors"]  # authors derived from csl_json

    # reorder
    assert client.put("/reading-queue/order", json={"paper_ids": [b, a]}).status_code == 204
    assert [it["id"] for it in client.get("/reading-queue").json()] == [b, a]
    # a foreign id set → 422
    assert client.put("/reading-queue/order", json={"paper_ids": [a]}).status_code == 422

    # remove (idempotent 204)
    assert client.delete(f"/reading-queue/{a}").status_code == 204
    assert client.delete(f"/reading-queue/{a}").status_code == 204
    assert [it["id"] for it in client.get("/reading-queue").json()] == [b]

    # adding a nonexistent paper → 404
    assert client.post("/reading-queue", json={"paper_id": 99999}).status_code == 404


# ---- priority strata (inc 294) --------------------------------------------


def test_list_reading_queue_surfaces_priority(temp_db_url):
    from app.backend.persistence.repository import set_paper_priority

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Alpha")
        b = _paper(conn, "Beta")
        add_to_queue(conn, a)
        add_to_queue(conn, b)
        set_paper_priority(conn, a, "high")
        rows = {r["id"]: r["priority"] for r in list_reading_queue(conn)}
    engine.dispose()
    assert rows[a] == "high"
    assert rows[b] is None  # unset → null → the frontend's "Unprioritized" group


def test_priority_surfaces_in_queue_and_clears(temp_db_url):
    # The cross-group drag reuses POST /papers/{id}/priority; the queue GET must then reflect the new label, and a
    # drop into "Unprioritized" clears it (priority: null).
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Alpha")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/reading-queue", json={"paper_id": a})

    assert client.get("/reading-queue").json()[0]["priority"] is None  # unset → Unprioritized
    assert client.post(f"/papers/{a}/priority", json={"priority": "high"}).status_code == 200
    assert client.get("/reading-queue").json()[0]["priority"] == "high"  # drag Low→High reflected
    assert client.post(f"/papers/{a}/priority", json={"priority": None}).status_code == 200
    assert client.get("/reading-queue").json()[0]["priority"] is None  # drag → Unprioritized clears it
