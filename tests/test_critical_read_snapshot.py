"""inc 601: durable per-paper critique snapshot + reaccessible read (GET .../critical-read/snapshot).

Covers the repo write/guard, the read endpoint's version/parse/staleness honesty, and the fulltext-gate
contract the FRONTEND relies on (this endpoint runs nothing — a metadata-only paper simply has no snapshot).
Hermetic; no network. The critique COMPUTATION is unchanged and covered by tests/test_critical_review.py.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from alembic import command
from alembic.config import Config
from app.backend.api import create_app
from app.backend.methods.critical_review import CRITICAL_REVIEW_VERSION
from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper


def _migrated(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'cr-snap.sqlite').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


_BACKBONE = {"method_signals": [], "citation_signal": None, "contested_claims": [], "triage_status": None}


def _save(engine, pid, *, requested_at, version=CRITICAL_REVIEW_VERSION, schema=1, fp="fp1", backbone=None):
    with engine.begin() as conn:
        return repo.save_backbone_snapshot(
            conn,
            pid,
            backbone if backbone is not None else _BACKBONE,
            requested_at=requested_at,
            critical_review_version=version,
            content_fingerprint=fp,
            snapshot_schema_version=schema,
        )


def test_snapshot_endpoint_returns_null_when_none_saved(tmp_path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
    engine.dispose()
    r = TestClient(create_app(db_url=url)).get(f"/papers/{pid}/critical-read/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["backbone"] is None and body["refresh_required"] is False and body["running_job_id"] is None


def test_saved_snapshot_is_returned_and_reopenable(tmp_path):
    from app.backend.persistence.statcheck_cache_repo import compute_content_fingerprint

    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        real_fp = compute_content_fingerprint(conn, pid)  # store the ACTUAL fingerprint → not stale
    _save(engine, pid, requested_at="2026-01-02T00:00:00+00:00", fp=real_fp)
    engine.dispose()
    body = TestClient(create_app(db_url=url)).get(f"/papers/{pid}/critical-read/snapshot").json()
    assert body["backbone"] is not None and body["stale"] is False and body["refresh_required"] is False


def test_monotonic_guard_rejects_an_older_run(tmp_path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
    assert _save(engine, pid, requested_at="2026-05-05T00:00:00+00:00", fp="new") is True
    # An out-of-order (older) completing run must not clobber the newer snapshot.
    assert _save(engine, pid, requested_at="2026-01-01T00:00:00+00:00", fp="old") is False
    with engine.begin() as conn:
        row = repo.read_backbone_snapshot(conn, pid)
    engine.dispose()
    assert row["content_fingerprint"] == "new"


def test_version_mismatch_reads_as_refresh_required_not_a_crash(tmp_path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
    _save(engine, pid, requested_at="2026-01-02T00:00:00+00:00", version="0")  # a pre-bump payload
    engine.dispose()
    body = TestClient(create_app(db_url=url)).get(f"/papers/{pid}/critical-read/snapshot").json()
    assert body["backbone"] is None and body["refresh_required"] is True


def test_unparseable_payload_reads_as_refresh_required(tmp_path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
    # A structurally-invalid backbone (method_signals must be a list of objects, not a string).
    _save(engine, pid, requested_at="2026-01-02T00:00:00+00:00", backbone={"method_signals": "oops"})
    engine.dispose()
    body = TestClient(create_app(db_url=url)).get(f"/papers/{pid}/critical-read/snapshot").json()
    assert body["backbone"] is None and body["refresh_required"] is True


def test_stale_hint_flips_when_content_fingerprint_changes(tmp_path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
    # A paper with no chunks/attachments has a fixed fingerprint; store a DIFFERENT one to force stale=True.
    _save(engine, pid, requested_at="2026-01-02T00:00:00+00:00", fp="a-different-fingerprint")
    engine.dispose()
    body = TestClient(create_app(db_url=url)).get(f"/papers/{pid}/critical-read/snapshot").json()
    assert body["backbone"] is not None and body["stale"] is True  # honest "paper changed since" hint


def test_snapshot_cascades_when_paper_deleted(tmp_path):
    url = _migrated(tmp_path)
    engine = make_engine(url)
    from sqlalchemy import delete, func, select

    from app.backend.persistence.schema import critical_read_snapshots, papers

    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
    _save(engine, pid, requested_at="2026-01-02T00:00:00+00:00")
    with engine.begin() as conn:
        conn.execute(delete(papers).where(papers.c.id == pid))  # hard delete → FK CASCADE
        remaining = conn.execute(
            select(func.count()).select_from(critical_read_snapshots).where(critical_read_snapshots.c.paper_id == pid)
        ).scalar()
    engine.dispose()
    assert remaining == 0
