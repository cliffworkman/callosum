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
