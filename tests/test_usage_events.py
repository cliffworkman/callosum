"""Local usage instrumentation (backlog #38A, inc 450) -- the repo, the record_event() seam (gating + the closed
event-type allowlist), the settings toggle, and the 4 /usage/* endpoints. Zero egress: nothing here ever makes an
HTTP request. The autouse conftest fixture isolates CALLOSUM_SETTINGS_PATH per test, so app_settings state never
leaks across tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.backend import app_settings
from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema_usage import USAGE_EVENT_TYPES, usage_events
from app.backend.persistence.usage_repo import (
    clear_usage_events,
    insert_usage_event,
    list_usage_events,
    usage_summary,
)
from app.backend.usage import record_event

# ---- repo-level -------------------------------------------------------------


def test_insert_and_summary_counts_per_type(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        insert_usage_event(conn, "citation_export", count=3)
        insert_usage_event(conn, "citation_export", count=2)
        insert_usage_event(conn, "duplicate_resolved", count=1)
        rows = usage_summary(conn)
    engine.dispose()
    by_type = {r["event_type"]: r for r in rows}
    # never-empty: every USAGE_EVENT_TYPES entry gets a row, even at 0 (Principles #6 -- silence isn't a certificate)
    assert set(by_type) == set(USAGE_EVENT_TYPES)
    assert by_type["citation_export"]["all_time"] == 5
    assert by_type["duplicate_resolved"]["all_time"] == 1
    assert by_type["quote_located"]["all_time"] == 0
    # fixed taxonomy order, never sorted by count (that would read as a ranking)
    assert [r["event_type"] for r in rows] == list(USAGE_EVENT_TYPES)


def test_summary_30_day_cutoff_excludes_old_rows(temp_db_url):
    engine = make_engine(temp_db_url)
    # one row backdated ~40 days -- genuinely new query territory (no existing date-cutoff query in this
    # codebase to copy), so this needs real test coverage, not just trust
    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=40)
    with engine.begin() as conn:
        conn.execute(usage_events.insert().values(event_type="flag_reviewed", count=1, created_at=old))
        insert_usage_event(conn, "flag_reviewed", count=1)  # a fresh row, stays within the cutoff
        rows = usage_summary(conn, days=30)
    engine.dispose()
    by_type = {r["event_type"]: r for r in rows}
    assert by_type["flag_reviewed"]["all_time"] == 2
    assert by_type["flag_reviewed"]["last_30_days"] == 1  # only the never-backdated fresh insert survives the cutoff


def test_list_events_never_carries_a_payload_field(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        insert_usage_event(conn, "citation_export", count=2)
        rows = list_usage_events(conn)
    engine.dispose()
    assert rows == [
        {"event_type": "citation_export", "count": 2, "duration_ms": None, "created_at": rows[0]["created_at"]}
    ]
    assert set(rows[0]) == {"event_type", "count", "duration_ms", "created_at"}  # structurally no payload column


def test_clear_removes_everything_and_reports_count(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        insert_usage_event(conn, "citation_export", count=1)
        insert_usage_event(conn, "duplicate_resolved", count=1)
        deleted = clear_usage_events(conn)
        remaining = list_usage_events(conn)
    engine.dispose()
    assert deleted == 2
    assert remaining == []


# ---- record_event() seam: the central gate + allowlist ----------------------


def test_record_event_rejects_unknown_type(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        with pytest.raises(ValueError):
            record_event(conn, "not_a_real_event_type")
    engine.dispose()


def test_record_event_no_ops_when_disabled(temp_db_url):
    app_settings.set_usage_events_enabled(False)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        record_event(conn, "citation_export", count=5)
        rows = list_usage_events(conn)
    engine.dispose()
    assert rows == []  # disabled means disabled -- no event recorded anywhere


def test_record_event_writes_when_enabled_default(temp_db_url):
    # default is True -- nothing needs to be turned on first
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        record_event(conn, "citation_export", count=1)
        rows = list_usage_events(conn)
    engine.dispose()
    assert len(rows) == 1


# ---- settings toggle ----------------------------------------------------------


def test_usage_events_enabled_defaults_true_and_round_trips():
    assert app_settings.stored_usage_events_enabled() is True
    app_settings.set_usage_events_enabled(False)
    assert app_settings.stored_usage_events_enabled() is False
    app_settings.set_usage_events_enabled(True)
    assert app_settings.stored_usage_events_enabled() is True


# ---- endpoints ----------------------------------------------------------------


def test_usage_summary_endpoint_reflects_enabled_state_and_counts(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    pre = client.get("/usage/summary").json()
    assert pre["enabled"] is True
    assert {t["event_type"] for t in pre["types"]} == set(USAGE_EVENT_TYPES)

    r = client.post("/usage/events", json={"event_type": "quote_located", "count": 1})
    assert r.status_code == 204

    post = client.get("/usage/summary").json()
    quote_row = next(t for t in post["types"] if t["event_type"] == "quote_located")
    assert quote_row["all_time"] == 1 and quote_row["last_30_days"] == 1


def test_usage_events_endpoint_rejects_unknown_type_and_bad_count(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/usage/events", json={"event_type": "made_up"}).status_code == 422
    assert client.post("/usage/events", json={"event_type": "quote_located", "count": 0}).status_code == 422
    assert client.post("/usage/events", json={"event_type": "quote_located", "count": 5000}).status_code == 422


def test_usage_events_endpoint_disabled_records_nothing(temp_db_url):
    app_settings.set_usage_events_enabled(False)
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/usage/events", json={"event_type": "quote_located", "count": 1})
    assert r.status_code == 204  # accepted, but a silent no-op -- disabled means disabled
    summary = client.get("/usage/summary").json()
    assert summary["enabled"] is False
    assert all(t["all_time"] == 0 for t in summary["types"])


def test_usage_export_endpoint_returns_json_download_with_no_payload_fields(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/usage/events", json={"event_type": "citation_export", "count": 3})
    r = client.get("/usage/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    body = r.json()
    assert len(body["events"]) == 1
    assert set(body["events"][0]) == {"event_type", "count", "duration_ms", "created_at"}


def test_usage_clear_endpoint_zeroes_counts_and_works_regardless_of_toggle(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    client.post("/usage/events", json={"event_type": "citation_export", "count": 1})
    app_settings.set_usage_events_enabled(False)  # clear must still work even while recording is off
    r = client.post("/usage/clear")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1
    summary = client.get("/usage/summary").json()
    assert all(t["all_time"] == 0 for t in summary["types"])


def test_usage_settings_toggle_round_trips_through_the_settings_endpoint(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/settings").json()["usage_events_enabled"] is True
    r = client.put("/settings", json={"usage_events_enabled": False})
    assert r.status_code == 200 and r.json()["usage_events_enabled"] is False
    assert client.get("/settings").json()["usage_events_enabled"] is False
