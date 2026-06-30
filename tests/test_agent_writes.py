"""B1 SP2 — gated MCP agent writes: the audit repo + the /agent/* endpoints (gate, provenance, audit, revert)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.agent_repo import get_agent_write, list_agent_writes, mark_reverted, record_agent_write
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from tests.api_helpers import _seed_library


def test_agent_writes_repo_round_trip(temp_db_url: str) -> None:
    with make_engine(temp_db_url).begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        wid = record_agent_write(conn, action="tag", target_paper_id=pid, detail={"tag_id": 5}, tool="add_tag")
        row = get_agent_write(conn, wid)
        assert row["action"] == "tag" and row["detail_json"]["tag_id"] == 5 and row["reverted_at"] is None
        assert len(list_agent_writes(conn)) == 1
        mark_reverted(conn, wid)
        assert get_agent_write(conn, wid)["reverted_at"] is not None


def _enable_writes(client: TestClient) -> None:
    client.put("/settings", json={"agent_writes_enabled": True})


class _FakeCrossref:
    """Injected Crossref seam (create_app(crossref_client=...)) — resolves a fixed record (or refuses)."""

    def __init__(self, *, resolved: bool, csl: dict | None = None) -> None:
        self._resolved, self._csl = resolved, csl

    def resolve_doi(self, conn, doi):
        from integrations.crossref.adapter import CrossrefResolution

        return CrossrefResolution(doi=doi, resolved=self._resolved, csl_json=self._csl)


def _seed_axis(db_url: str, *, kind: str = "standard") -> int:
    from app.backend.clustering.axis_scoring import create_axis

    with make_engine(db_url).begin() as conn:
        return create_axis(conn, label="Lens", description="lens", kind=kind)


# --- the opt-in gate ---


def test_agent_writes_gated_off_by_default(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))  # default: writes OFF
    r = client.post(f"/agent/papers/{seeded['signal_paper_id']}/tags", json={"tag": "x"})
    assert r.status_code == 403
    # status reflects it, and flips on
    assert client.get("/agent/status").json()["writes_enabled"] is False
    _enable_writes(client)
    assert client.get("/agent/status").json()["writes_enabled"] is True


# --- add_tag ---


def test_agent_add_tag_stamps_ai_agent_and_audits(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    pid = seeded["signal_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    _enable_writes(client)
    r = client.post(f"/agent/papers/{pid}/tags", json={"tag": "from-agent"})
    assert r.status_code == 200 and "write_id" in r.json()
    tags = client.get(f"/papers/{pid}").json()["tags"]
    assert any(t["name"] == "from-agent" and t["source"] == "ai-agent" for t in tags)
    assert len(client.get("/agent/writes").json()) == 1


# --- add_to_axis ---


def test_agent_add_to_standard_axis(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    axis_id = _seed_axis(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    _enable_writes(client)
    r = client.post(f"/agent/axes/{axis_id}/papers", json={"paper_id": seeded["signal_paper_id"]})
    assert r.status_code == 200 and r.json()["axis_id"] == axis_id


def test_agent_add_to_my_pubs_axis_refused(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    axis_id = _seed_axis(temp_db_url, kind="my_publications")
    client = TestClient(create_app(db_url=temp_db_url))
    _enable_writes(client)
    r = client.post(f"/agent/axes/{axis_id}/papers", json={"paper_id": seeded["signal_paper_id"]})
    assert r.status_code == 422  # authorship is the user's to assert, never an agent's


# --- save_reference (DOI-verified) ---


def test_agent_save_reference_rejects_unresolvable(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=False)))
    _enable_writes(client)
    assert client.post("/agent/references", json={"identifier": "10.999/nope"}).status_code == 422


def test_agent_save_reference_creates_verified_ai_agent_record(temp_db_url: str) -> None:
    csl = {"title": "Real Paper", "DOI": "10.1/real", "type": "article-journal"}
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=True, csl=csl)))
    _enable_writes(client)
    body = client.post("/agent/references", json={"identifier": "10.1/real"}).json()
    assert body["created"] is True
    detail = client.get(f"/papers/{body['paper_id']}").json()
    assert detail["title"] == "Real Paper" and detail["imported_source"] == "ai-agent"


def test_agent_save_reference_dedups_existing(temp_db_url: str) -> None:
    # a paper already in the library by DOI → re-saving it returns created:false (and won't trash on revert)
    with make_engine(temp_db_url).begin() as conn:
        create_paper(conn, title="Already Here", csl_json={"title": "Already Here", "DOI": "10.5/dup"}, doi="10.5/dup")
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=False)))
    _enable_writes(client)
    body = client.post("/agent/references", json={"identifier": "10.5/dup"}).json()
    assert body["created"] is False  # found by dedup; Crossref never consulted


# --- annotate ---


def test_agent_annotate_adds_note(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    _enable_writes(client)
    assert (
        client.post(f"/agent/papers/{seeded['signal_paper_id']}/notes", json={"text": "agent note"}).status_code == 200
    )


# --- revert (per action, idempotent, dedup-safe) ---


def test_revert_tag_undoes_idempotently(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    pid = seeded["signal_paper_id"]
    client = TestClient(create_app(db_url=temp_db_url))
    _enable_writes(client)
    wid = client.post(f"/agent/papers/{pid}/tags", json={"tag": "tmp"}).json()["write_id"]
    assert client.post(f"/agent/writes/{wid}/revert").json()["reverted"] is True
    assert not any(t["name"] == "tmp" for t in client.get(f"/papers/{pid}").json()["tags"])
    assert client.post(f"/agent/writes/{wid}/revert").json()["reverted"] is True  # idempotent


def test_revert_reference_trashes_only_when_created(temp_db_url: str) -> None:
    # a created reference → revert soft-deletes it; a re-found one → revert leaves it live (dedup-safe)
    with make_engine(temp_db_url).begin() as conn:
        existing = create_paper(conn, title="Keep", csl_json={"title": "Keep", "DOI": "10.5/keep"}, doi="10.5/keep")
    csl = {"title": "Fresh", "DOI": "10.1/fresh", "type": "article-journal"}
    client = TestClient(create_app(db_url=temp_db_url, crossref_client=_FakeCrossref(resolved=True, csl=csl)))
    _enable_writes(client)
    created = client.post("/agent/references", json={"identifier": "10.1/fresh"}).json()
    refound = client.post("/agent/references", json={"identifier": "10.5/keep"}).json()
    client.post(f"/agent/writes/{created['write_id']}/revert")
    client.post(f"/agent/writes/{refound['write_id']}/revert")
    trashed = {p["id"] for p in client.get("/papers?deleted=true").json()}
    live = {p["id"] for p in client.get("/papers").json()}
    assert created["paper_id"] in trashed and created["paper_id"] not in live  # created → trashed
    assert existing in live and existing not in trashed  # re-found → left alone
