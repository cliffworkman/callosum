"""Reference-integrity for WIP manuscripts (backlog #48) — reuses `inspect_reference` unmodified against
`wip_references` "cited" rows instead of a discovered reference list, persists into the dedicated
`wip_reference_signals`/`wip_reference_reviews` tables (never the Library `reference_instances`, whose
`citing_paper_id` is a NOT NULL FK to `papers.id`), and reads a real cross-space propagation signal from the
existing, untouched Library `reference_entities` table."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.backend.api import create_app
from app.backend.methods.reference_integrity import ReferenceCandidate, entity_key, instance_key
from app.backend.methods.retraction import RetractionChecker, RetractionSignal
from app.backend.persistence.database import make_engine
from app.backend.persistence.reference_integrity_repo import (
    replace_instance_signals,
    upsert_reference_entity,
    upsert_reference_instance,
)
from app.backend.persistence.schema import papers
from integrations.crossref.adapter import CrossrefClient
from tests.test_reference_integrity import _CrossrefMiss, _OpenAlex


def _manuscript(client: TestClient, folder: Path) -> int:
    folder.mkdir()
    created = client.post("/wip/watch-roots", json={"path": str(folder), "discovery_mode": "folder"}).json()
    assert client.post(f"/wip/watch-roots/{created['id']}/scan").status_code == 202
    return client.get("/wip/manuscripts").json()[0]["id"]


def _seed_paper(conn, title: str, doi: str | None) -> int:
    csl = {"title": title, "DOI": doi} if doi else {"title": title}
    return int(conn.execute(insert(papers).values(title=title, csl_json=csl, doi=doi)).inserted_primary_key[0])


def _link(client: TestClient, manuscript_id: int, paper_id: int, state: str) -> None:
    r = client.post(
        f"/wip/manuscripts/{manuscript_id}/references", json={"paper_id": paper_id, "relationship_state": state}
    )
    assert r.status_code == 200, r.text


def _client(temp_db_url, *, openalex_records=None, retraction_flag_dois=None) -> TestClient:
    flags = {d.lower() for d in (retraction_flag_dois or [])}

    def retraction(conn, paper):
        return (
            RetractionSignal(source="crossref", status="retracted", notice_doi="10.1/notice", reason="registry")
            if str(paper.get("doi") or "").lower() in flags
            else None
        )

    app = create_app(
        db_url=temp_db_url,
        crossref_client=CrossrefClient(fetcher=_CrossrefMiss()),
        openalex_client=_OpenAlex(records=openalex_records or {}),
    )
    app.state.retraction_checkers = [RetractionChecker("crossref", retraction)]
    return TestClient(app)


def _drive(client: TestClient, manuscript_id: int) -> dict:
    r = client.post(f"/wip/manuscripts/{manuscript_id}/reference-integrity/run")
    assert r.status_code == 202
    jid = r.json()["job_id"]
    data = {}
    for _ in range(40):
        data = client.get(f"/wip/reference-integrity/run/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    assert data["status"] == "done", data
    return data["report"]


def test_run_flags_retracted_cited_reference_and_ignores_non_cited(temp_db_url, tmp_path: Path) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        retracted_id = _seed_paper(conn, "Retracted work", "10.1/retracted")
        clean_id = _seed_paper(conn, "Clean work", "10.1/clean")
        speculative_id = _seed_paper(conn, "Just background reading", "10.1/bg")
    engine.dispose()

    client = _client(
        temp_db_url,
        openalex_records={
            "10.1/retracted": {"title": "Retracted work", "DOI": "10.1/retracted", "type": "article-journal"},
            "10.1/clean": {"title": "Clean work", "DOI": "10.1/clean", "type": "article-journal"},
        },
        retraction_flag_dois=["10.1/retracted"],
    )
    manuscript_id = _manuscript(client, tmp_path / "Draft")
    _link(client, manuscript_id, retracted_id, "cited")
    _link(client, manuscript_id, clean_id, "cited")
    _link(client, manuscript_id, speculative_id, "background-reading")

    report = _drive(client, manuscript_id)

    assert report["checked_count"] == 2  # both "cited" references were checked -- the "background-reading" one wasn't
    assert report["active_count"] == 1  # only the retracted one has active signals
    assert len(report["items"]) == 1  # clean references with no signals are omitted from the displayed list
    item = report["items"][0]
    assert item["paper_id"] == retracted_id
    kinds = {s["detector_kind"] for s in item["signals"]}
    assert "retraction" in kinds
    assert any(s["provider"] == "WIP linked references" and s["result_count"] == 2 for s in report["provider_statuses"])


def test_review_dismiss_persists_and_report_reflects_it(temp_db_url, tmp_path: Path) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        retracted_id = _seed_paper(conn, "Retracted work", "10.1/retracted")
    engine.dispose()

    client = _client(temp_db_url, retraction_flag_dois=["10.1/retracted"])
    manuscript_id = _manuscript(client, tmp_path / "Draft")
    _link(client, manuscript_id, retracted_id, "cited")
    report = _drive(client, manuscript_id)
    reference_id = report["items"][0]["id"]

    reviewed = client.post(f"/wip/reference-integrity/{reference_id}/review", json={"state": "dismissed"})
    assert reviewed.status_code == 200
    assert reviewed.json()["active_count"] == 0  # dismissed signals no longer count as active

    fresh = client.get(f"/wip/manuscripts/{manuscript_id}/reference-integrity").json()
    assert fresh["items"][0]["review_state"] == "dismissed"


def test_review_rejects_unknown_reference(temp_db_url) -> None:
    client = _client(temp_db_url)
    assert client.post("/wip/reference-integrity/999999/review", json={"state": "dismissed"}).status_code == 404


def test_cross_space_propagation_from_the_library(temp_db_url, tmp_path: Path) -> None:
    """A reference already flagged elsewhere in the user's Library surfaces as `own_library_propagation` for a
    WIP manuscript citing the same work -- a pure additive read against the existing Library
    `reference_entities` table, seeded here the same way the real Library reference-integrity job would."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        other_citing_paper_id = _seed_paper(conn, "Some other Library paper", "10.1/other-citer")
        shared_ref_id = _seed_paper(conn, "Shared reference", "10.1/shared")
        candidate = ReferenceCandidate(
            source_ordinal=0,
            title="Shared reference",
            authors=[],
            year=2020,
            doi="10.1/shared",
            raw_text="Shared reference (2020)",
            context={"reference_source": "semantic-scholar"},
        )
        entity_id = upsert_reference_entity(conn, {"doi": "10.1/shared", "title": "Shared reference"})
        iid = upsert_reference_instance(
            conn,
            citing_paper_id=other_citing_paper_id,
            entity_id=entity_id,
            instance_key=instance_key(candidate),
            source="semantic-scholar",
            source_ordinal=0,
            raw_text=candidate.raw_text,
            title=candidate.title,
            authors=candidate.authors,
            year=candidate.year,
            doi=candidate.doi,
            context=candidate.context,
        )
        replace_instance_signals(
            conn,
            iid,
            [
                {
                    "detector_kind": "retraction",
                    "detector_status": "known_retraction_signal",
                    "evidence_json": {"label": "Known retraction signal"},
                    "source": "retraction-watch",
                    "snapshot_marker": "rw:test:1",
                    "signal_key": "retraction:1",
                }
            ],
        )
        assert entity_key({"doi": "10.1/shared"}) == entity_key({"doi": "10.1/shared"})  # sanity: keys are stable
    engine.dispose()

    client = _client(temp_db_url, openalex_records={"10.1/shared": {"title": "Shared reference", "DOI": "10.1/shared"}})
    manuscript_id = _manuscript(client, tmp_path / "Draft")
    _link(client, manuscript_id, shared_ref_id, "cited")

    report = _drive(client, manuscript_id)

    item = report["items"][0]
    kinds = {s["detector_kind"] for s in item["signals"]}
    assert "own_library_propagation" in kinds
    prop = next(s for s in item["signals"] if s["detector_kind"] == "own_library_propagation")
    assert prop["evidence"]["source_instances"][0]["citing_paper_id"] == other_citing_paper_id


def test_run_with_zero_cited_references_is_an_honest_empty_report(temp_db_url, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    manuscript_id = _manuscript(client, tmp_path / "Draft")

    report = _drive(client, manuscript_id)

    assert report["checked_count"] == 0
    assert report["active_count"] == 0
    assert report["items"] == []


def test_run_404_for_unknown_manuscript(temp_db_url) -> None:
    client = _client(temp_db_url)
    assert client.post("/wip/manuscripts/999999/reference-integrity/run").status_code == 404
    assert client.get("/wip/manuscripts/999999/reference-integrity").status_code == 404


def test_status_nav_points_at_work_meta_reference(temp_db_url, tmp_path: Path) -> None:
    client = _client(temp_db_url)
    manuscript_id = _manuscript(client, tmp_path / "Draft")
    _drive(client, manuscript_id)

    status = client.get("/status/jobs").json()
    row = next(
        j
        for j in status["jobs"]
        if (j["nav"] or {}).get("manuscript_id") == manuscript_id and j["store"] == "wip_reference_integrity_jobs"
    )
    assert row["nav"] == {"workspace": "work", "tab": "meta-reference", "manuscript_id": manuscript_id}
