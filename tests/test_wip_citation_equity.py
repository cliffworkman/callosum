"""Citation concentration for WIP manuscripts (backlog #48) — the ephemeral audit over `wip_references`
"cited" rows, reusing `audit_reference_list` unmodified with an honest empty author-family set and no
field-topic comparison (a manuscript has no OpenAlex record of its own to draw one from)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import papers
from integrations.openalex.adapter import OpenAlexClient
from tests.test_citation_equity import _fetcher, _ref_work


def _manuscript(client: TestClient, folder: Path) -> int:
    folder.mkdir()
    created = client.post("/wip/watch-roots", json={"path": str(folder), "discovery_mode": "folder"}).json()
    assert client.post(f"/wip/watch-roots/{created['id']}/scan").status_code == 202
    return client.get("/wip/manuscripts").json()[0]["id"]


def _seed_paper(conn, title: str, doi: str | None, authors=None) -> int:
    csl = {"title": title, "DOI": doi}
    if authors:
        csl["author"] = authors
    return int(conn.execute(insert(papers).values(title=title, csl_json=csl, doi=doi)).inserted_primary_key[0])


def _link(client: TestClient, manuscript_id: int, paper_id: int, state: str) -> None:
    r = client.post(
        f"/wip/manuscripts/{manuscript_id}/references", json={"paper_id": paper_id, "relationship_state": state}
    )
    assert r.status_code == 200, r.text


def _drive(client: TestClient, manuscript_id: int) -> dict:
    r = client.post(f"/wip/manuscripts/{manuscript_id}/citation-equity/run")
    assert r.status_code == 202
    jid = r.json()["job_id"]
    data = {}
    for _ in range(40):
        data = client.get(f"/wip/citation-equity/run/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    assert data["status"] == "done", data
    return data["report"]


def test_run_uses_only_cited_references_and_has_no_field_comparison(temp_db_url, tmp_path: Path) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        cited_id = _seed_paper(conn, "Cited work", "10.1/cited", authors=[{"family": "Okafor", "given": "Amara"}])
        not_cited_id = _seed_paper(conn, "Background reading only", "10.1/bg")
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id = _manuscript(client, tmp_path / "Draft")
    _link(client, manuscript_id, cited_id, "cited")
    _link(client, manuscript_id, not_cited_id, "background-reading")

    works_by_doi = {"10.1/cited": _ref_work("W1", cited=10, venue="Nature", authors=("Amara Okafor",))}
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher(works_by_doi, {}, []))

    report = _drive(client, manuscript_id)

    assert report["references_total"] == 1  # only the "cited" row, not the "background-reading" one
    assert report["references_resolved"] == 1
    assert report["field_topic"] is None and report["field_sample_size"] == 0  # no manuscript-of-its-own to draw from
    by_key = {s["key"]: s for s in report["signals"]}
    assert set(by_key) == {"self_citation", "matthew", "venue", "institution"}
    assert by_key["self_citation"]["list_pct"] is None
    assert "was not computed" in by_key["self_citation"]["summary"]


def test_run_with_zero_cited_references_is_an_honest_empty_report(temp_db_url, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id = _manuscript(client, tmp_path / "Draft")

    report = _drive(client, manuscript_id)

    assert report["references_total"] == 0
    assert report["references_resolved"] == 0
    assert report["field_topic"] is None


def test_run_404_for_unknown_manuscript(temp_db_url) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/wip/manuscripts/999999/citation-equity/run").status_code == 404


def test_openalex_outage_marks_wip_audit_error_instead_of_empty(temp_db_url, tmp_path: Path) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        cited_id = _seed_paper(conn, "Cited work", "10.1/cited")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id = _manuscript(client, tmp_path / "Draft")
    _link(client, manuscript_id, cited_id, "cited")
    client.app.state.openalex_client = OpenAlexClient(fetcher=lambda *a, **k: (503, {"error": "unavailable"}))

    started = client.post(f"/wip/manuscripts/{manuscript_id}/citation-equity/run")
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(40):
        result = client.get(f"/wip/citation-equity/run/{job_id}").json()
        if result["status"] in {"done", "error"}:
            break

    assert result["status"] == "error"
    assert "unavailable" in result["detail"].lower()


def test_status_nav_points_at_work_meta_reference(temp_db_url, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    manuscript_id = _manuscript(client, tmp_path / "Draft")
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher({}, {}, []))

    r = client.post(f"/wip/manuscripts/{manuscript_id}/citation-equity/run")
    job_id = r.json()["job_id"]
    for _ in range(40):
        if client.get(f"/wip/citation-equity/run/{job_id}").json()["status"] in ("done", "error"):
            break

    status = client.get("/status/jobs").json()
    row = next(j for j in status["jobs"] if j["job_id"] == job_id)
    assert row["nav"] == {"workspace": "work", "tab": "meta-reference", "manuscript_id": manuscript_id}
