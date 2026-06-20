"""Tests for the OA wanted list + re-check (inc 76) — hermetic (the re-check uses an injected fake registry +
fake download/import; no real network or file IO)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.acquisition.registry import OaLocation
from app.backend.acquisition.wanted import run_recheck
from app.backend.api import create_app
from app.backend.persistence import wanted_repo
from app.backend.persistence.acquisition_repo import set_attachment_oa_labels
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import attachments, papers
from tests.api_helpers import _seed_library


def _pdfless_paper(engine, *, doi: str | None = None, title: str = "Wanted Paper") -> int:
    with engine.begin() as conn:
        return create_paper(
            conn, title=title, csl_json={"id": doi or title, "type": "document", "title": title}, doi=doi
        )


def _loc(color="gold", version="vor", url="https://oa.example/x.pdf", source="openalex") -> OaLocation:
    return OaLocation(pdf_url=url, oa_color=color, version=version, source=source)


class _FakeRegistry:
    """Resolves by lower-cased DOI; records every resolve so a test can prove OA-only routing."""

    def __init__(self, by_doi=None):
        self.by_doi = by_doi or {}
        self.resolved = []

    def resolve(self, conn, ref):
        self.resolved.append(ref)
        return self.by_doi.get((ref.doi or "").lower())


class _FakeDownload:
    def __init__(self, fail_urls=()):
        self.fail_urls = set(fail_urls)
        self.calls = []

    def __call__(self, location):
        self.calls.append(location)
        if location.pdf_url in self.fail_urls:
            raise RuntimeError("download boom")
        return Path("fake.pdf")  # never read — the fake import doesn't touch the filesystem


class _FakeImport:
    def __init__(self):
        self.calls = []

    def __call__(self, conn, location, temp, *, paper_id, crossref_client=None):
        self.calls.append({"paper_id": paper_id, "location": location})
        return {"paper_id": paper_id, "attachment_id": 1, "filename": "x.pdf"}


# --- wanted_repo ------------------------------------------------------------------------------------------


def test_add_external_get_or_create(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = wanted_repo.add_wanted(conn, doi="10.1/x")
        b = wanted_repo.add_wanted(conn, doi="10.1/X")  # case-insensitive dedup
        items = wanted_repo.list_wanted(conn)
    assert a == b and len(items) == 1 and items[0]["paper_id"] is None


def test_add_library_get_or_create(temp_db_url):
    engine = make_engine(temp_db_url)
    pid = _pdfless_paper(engine, doi="10.1/lib")
    with engine.begin() as conn:
        a = wanted_repo.add_wanted(conn, paper_id=pid)
        b = wanted_repo.add_wanted(conn, paper_id=pid)
        items = wanted_repo.list_wanted(conn)
    assert a == b and len(items) == 1


def test_remove_wanted(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        wid = wanted_repo.add_wanted(conn, doi="10.1/x")
        assert wanted_repo.remove_wanted(conn, wid) is True
        assert wanted_repo.list_wanted(conn) == []
        assert wanted_repo.remove_wanted(conn, wid) is False  # idempotent


def test_sync_from_library_only_pdfless_and_idempotent(temp_db_url):
    ids = _seed_library(temp_db_url)  # facial has PDFs; signal has none
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        added = wanted_repo.sync_from_library(conn)
        again = wanted_repo.sync_from_library(conn)
        items = wanted_repo.list_wanted(conn)
    assert added == 1 and again == 0
    assert {it["paper_id"] for it in items} == {ids["signal_paper_id"]}


def test_coverage_stats(temp_db_url):
    ids = _seed_library(temp_db_url)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        att_id = conn.execute(
            select(attachments.c.id).where(attachments.c.paper_id == ids["facial_paper_id"]).limit(1)
        ).scalar()
        set_attachment_oa_labels(conn, int(att_id), oa_color="gold", oa_version="vor", oa_source="openalex")
        cov = wanted_repo.coverage_stats(conn)
    assert cov["library_total"] == 2 and cov["with_pdf"] == 1 and cov["without_pdf"] == 1
    assert cov["acquired_oa"]["gold"] == 1


# --- run_recheck (the service) ----------------------------------------------------------------------------


def test_recheck_fulfills_library_want(temp_db_url):
    engine = make_engine(temp_db_url)
    pid = _pdfless_paper(engine, doi="10.1/lib")
    with engine.begin() as conn:
        wid = wanted_repo.add_wanted(conn, paper_id=pid)
    reg = _FakeRegistry({"10.1/lib": _loc("gold", "vor")})
    dl, imp = _FakeDownload(), _FakeImport()

    summary = run_recheck(engine, reg, download=dl, import_=imp)

    assert summary["checked"] == 1 and len(summary["acquired"]) == 1
    assert imp.calls and imp.calls[0]["paper_id"] == pid
    assert dl.calls and dl.calls[0] is reg.by_doi["10.1/lib"]  # the only fetch was the registry's OaLocation
    with engine.begin() as conn:
        row = wanted_repo.get_wanted(conn, wid)
    assert row["status"] == "fulfilled" and row["last_result"] == "gold/vor"


def test_recheck_external_doi_creates_paper_then_imports(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        before = conn.execute(select(func.count()).select_from(papers)).scalar()
        wid = wanted_repo.add_wanted(conn, doi="10.1/ext", title="External Paper")
    reg = _FakeRegistry({"10.1/ext": _loc("green", "preprint")})
    imp = _FakeImport()

    summary = run_recheck(engine, reg, download=_FakeDownload(), import_=imp)

    assert len(summary["acquired"]) == 1
    with engine.begin() as conn:
        after = conn.execute(select(func.count()).select_from(papers)).scalar()
        row = wanted_repo.get_wanted(conn, wid)
    assert after == before + 1  # a paper was created for the external want
    assert row["status"] == "fulfilled" and row["paper_id"] is not None
    assert imp.calls[0]["paper_id"] == row["paper_id"]


def test_recheck_skips_title_only_external(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        before = conn.execute(select(func.count()).select_from(papers)).scalar()
        wid = wanted_repo.add_wanted(conn, title="Just A Title")
    reg = _FakeRegistry({})

    summary = run_recheck(engine, reg, download=_FakeDownload(), import_=_FakeImport())

    assert summary["skipped"] == 1 and reg.resolved == []  # never resolved a title-only external
    with engine.begin() as conn:
        after = conn.execute(select(func.count()).select_from(papers)).scalar()
        row = wanted_repo.get_wanted(conn, wid)
    assert after == before  # no paper minted from a fuzzy title
    assert row["status"] == "wanted" and row["last_result"] == "needs-id"


def test_recheck_miss_keeps_wanted(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        wid = wanted_repo.add_wanted(conn, doi="10.1/closed")
    reg = _FakeRegistry({})  # returns None for 10.1/closed

    summary = run_recheck(engine, reg, download=_FakeDownload(), import_=_FakeImport())

    assert summary["still_wanted"] == 1 and not summary["acquired"]
    assert reg.resolved  # it WAS resolved (it has a doi) — just no OA copy
    with engine.begin() as conn:
        row = wanted_repo.get_wanted(conn, wid)
    assert row["status"] == "wanted" and row["last_result"] == "none"


def test_recheck_error_does_not_abort_run(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        wanted_repo.add_wanted(conn, doi="10.1/boom")
        wanted_repo.add_wanted(conn, doi="10.1/ok")
    reg = _FakeRegistry(
        {"10.1/boom": _loc(url="https://oa.example/boom.pdf"), "10.1/ok": _loc(url="https://oa.example/ok.pdf")}
    )
    dl = _FakeDownload(fail_urls=["https://oa.example/boom.pdf"])

    summary = run_recheck(engine, reg, download=dl, import_=_FakeImport())

    assert summary["checked"] == 2 and summary["errors"] == 1 and len(summary["acquired"]) == 1


# --- endpoints --------------------------------------------------------------------------------------------


def test_wanted_endpoints_crud(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    created = client.post("/wanted", json={"doi": "10.1/x"})
    assert created.status_code == 201
    wid = created.json()["id"]
    assert any(i["id"] == wid for i in client.get("/wanted").json()["items"])
    assert client.delete(f"/wanted/{wid}").status_code == 204
    assert client.get("/wanted").json()["items"] == []


def test_wanted_post_empty_is_422(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/wanted", json={}).status_code == 422


def test_wanted_sync_and_coverage_endpoints(temp_db_url):
    _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/wanted/sync-library").json()["added"] == 1
    cov = client.get("/wanted/coverage").json()
    assert cov["library_total"] == 2 and cov["without_pdf"] == 1 and cov["with_pdf"] == 1
