"""Tests for the cross-feature Status popover's backend (inc 406): the `/status/jobs` aggregator that
reflects over every `JobStore` on `api.state`, plus the dismiss/clear-finished endpoints. The crux checks:
a store name that exists on `api.state` but ISN'T a JobStore (e.g. `engine`) must never be resolvable
through the dismiss endpoint — the allowlist-by-reflection design must actually hold, not just avoid a
literal getattr(request-supplied-string)."""

from __future__ import annotations

import dataclasses

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.api.job_store import JobStore
from app.backend.api.routers.status import JOB_COMPUTE_KINDS, JOB_NAV_DEFAULTS, STATUS_HIDDEN_STORES, discover_stores


def _client(temp_db_url: str) -> TestClient:
    return TestClient(create_app(db_url=temp_db_url))


def test_empty_app_has_no_status_jobs(temp_db_url):
    client = _client(temp_db_url)
    assert client.get("/status/jobs").json() == {"jobs": []}


def test_freshly_created_job_not_yet_running_is_not_shown(temp_db_url):
    app = create_app(db_url=temp_db_url)
    app.state.citation_count_jobs.create()  # created, never mark_running'd — not worth a row yet
    client = TestClient(app)
    assert client.get("/status/jobs").json() == {"jobs": []}


def test_running_job_shows_real_progress_and_a_friendly_label(temp_db_url):
    app = create_app(db_url=temp_db_url)
    jid = app.state.citation_count_jobs.create()
    app.state.citation_count_jobs.mark_running(jid)
    app.state.citation_count_jobs.mark_progress(jid, 3, 10, "Fetching citation counts")
    client = TestClient(app)

    jobs = client.get("/status/jobs").json()["jobs"]
    assert len(jobs) == 1
    row = jobs[0]
    assert row["store"] == "citation_count_jobs"
    assert row["label"] == "Cited-by refresh"
    assert row["status"] == "running"
    assert row["progress"]["current"] == 3
    assert row["progress"]["total"] == 10
    assert row["progress"]["label"] == "Fetching citation counts"


def test_job_without_progress_shows_no_progress_block(temp_db_url):
    # Most job kinds (Ask, statcheck-all, ...) only ever go pending -> running -> done, no mark_progress call.
    # The row must still appear (indeterminate, per Phase 1's honest-spinner design) with progress=None.
    app = create_app(db_url=temp_db_url)
    jid = app.state.summary_jobs.create()
    app.state.summary_jobs.mark_running(jid)
    client = TestClient(app)

    jobs = client.get("/status/jobs").json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["label"] == "Synthesize · Ask"
    assert jobs[0]["status"] == "running"
    assert jobs[0]["progress"] is None


def test_finished_job_preserves_its_last_known_progress(temp_db_url):
    app = create_app(db_url=temp_db_url)
    jid = app.state.citation_count_jobs.create()
    app.state.citation_count_jobs.mark_running(jid)
    app.state.citation_count_jobs.mark_progress(jid, 10, 10, "Fetching citation counts")
    app.state.citation_count_jobs.mark_done(jid, result=None)
    client = TestClient(app)

    row = client.get("/status/jobs").json()["jobs"][0]
    assert row["status"] == "done"
    assert row["progress"]["current"] == 10 and row["progress"]["total"] == 10
    # A finished job never shows an ETA, even though the underlying Job still carries enough data to compute one.
    assert row["progress"]["eta_seconds"] is None


def test_status_job_nav_is_none_when_the_job_never_published_one(temp_db_url):
    # inc 415: most job kinds never set Job.nav — it must serialize cleanly as None, not crash or default
    # to something else.
    app = create_app(db_url=temp_db_url)
    app.state.zzz_demo_feature_jobs = JobStore()
    jid = app.state.zzz_demo_feature_jobs.create()
    app.state.zzz_demo_feature_jobs.mark_running(jid)
    app.state.zzz_demo_feature_jobs.mark_done(jid, result=None)
    client = TestClient(app)

    row = client.get("/status/jobs").json()["jobs"][0]
    assert row["nav"] is None


def test_status_job_surfaces_a_published_nav_payload(temp_db_url):
    # inc 415/436: a job may add a typed entity id to its server-owned destination — never job.result itself,
    # which StatusJob has no field for at all.
    app = create_app(db_url=temp_db_url)
    jid = app.state.summary_jobs.create()
    app.state.summary_jobs.mark_running(jid)
    app.state.summary_jobs.mark_done(jid, result=None, nav={"summary_id": 99})
    client = TestClient(app)

    row = client.get("/status/jobs").json()["jobs"][0]
    assert row["nav"] == {"workspace": "synthesis", "tab": "ask", "summary_id": 99}


def test_status_navigation_rejects_free_text_urls_and_destination_overrides(temp_db_url):
    app = create_app(db_url=temp_db_url)
    jid = app.state.summary_jobs.create(
        nav={"workspace": "settings", "url": "file:///secret", "detail": "private", "paper_id": 12}
    )
    app.state.summary_jobs.mark_running(jid)

    row = TestClient(app).get("/status/jobs").json()["jobs"][0]
    assert row["nav"] == {"workspace": "synthesis", "tab": "ask", "paper_id": 12}


def test_every_application_job_store_has_a_bounded_navigation_home(temp_db_url):
    app = create_app(db_url=temp_db_url)
    stores = discover_stores(app.state)
    visible_stores = set(stores) - STATUS_HIDDEN_STORES
    assert STATUS_HIDDEN_STORES <= set(stores)
    assert visible_stores <= set(JOB_NAV_DEFAULTS)
    assert visible_stores <= set(JOB_COMPUTE_KINDS)
    assert STATUS_HIDDEN_STORES.isdisjoint(JOB_NAV_DEFAULTS)
    assert STATUS_HIDDEN_STORES.isdisjoint(JOB_COMPUTE_KINDS)
    for nav in JOB_NAV_DEFAULTS.values():
        assert set(nav) <= {"workspace", "tab", "pane", "section", "modal", "view"}


def test_routine_library_and_wip_scans_do_not_appear_in_status(temp_db_url):
    app = create_app(db_url=temp_db_url)
    for store_name in STATUS_HIDDEN_STORES:
        store = getattr(app.state, store_name)
        job_id = store.create()
        store.mark_running(job_id)
    visible_id = app.state.summary_jobs.create()
    app.state.summary_jobs.mark_running(visible_id)

    rows = TestClient(app).get("/status/jobs").json()["jobs"]
    assert [row["store"] for row in rows] == ["summary_jobs"]


def test_job_navigation_survives_running_progress_and_error_transitions(temp_db_url):
    app = create_app(db_url=temp_db_url)
    jid = app.state.critical_review_jobs.create(nav={"paper_id": 42})
    app.state.critical_review_jobs.mark_running(jid)
    app.state.critical_review_jobs.mark_progress(jid, 1, 3, "Embedding claims")
    assert app.state.critical_review_jobs.get(jid).nav == {"paper_id": 42}
    app.state.critical_review_jobs.mark_error(jid, "fixture failure")

    row = TestClient(app).get("/status/jobs").json()["jobs"][0]
    assert row["nav"] == {"workspace": "synthesis", "tab": "critique", "paper_id": 42}
    assert row["compute_kind"] == "Provider AI + local verification"


def test_unregistered_job_store_falls_back_to_a_prettified_label(temp_db_url):
    app = create_app(db_url=temp_db_url)
    app.state.zzz_demo_feature_jobs = JobStore()  # simulates a future feature that never registers a JOB_LABELS entry
    jid = app.state.zzz_demo_feature_jobs.create()
    app.state.zzz_demo_feature_jobs.mark_running(jid)
    client = TestClient(app)

    jobs = client.get("/status/jobs").json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["store"] == "zzz_demo_feature_jobs"
    assert jobs[0]["label"] == "Zzz Demo Feature"


def test_dismiss_removes_a_finished_job_and_is_idempotent_404_after(temp_db_url):
    app = create_app(db_url=temp_db_url)
    jid = app.state.dedup_jobs.create()
    app.state.dedup_jobs.mark_running(jid)
    app.state.dedup_jobs.mark_done(jid, result=None)
    client = TestClient(app)

    assert len(client.get("/status/jobs").json()["jobs"]) == 1
    resp = client.post(f"/status/jobs/dedup_jobs/{jid}/dismiss")
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    assert client.get("/status/jobs").json() == {"jobs": []}

    again = client.post(f"/status/jobs/dedup_jobs/{jid}/dismiss")
    assert again.status_code == 404


def test_dismiss_rejects_a_state_attribute_that_is_not_a_job_store(temp_db_url):
    # `engine` is a REAL attribute on api.state (the SQLAlchemy engine) but not a JobStore. The dismiss
    # endpoint must 404, not resolve it via getattr and blow up (or worse, silently no-op on real state).
    app = create_app(db_url=temp_db_url)
    assert hasattr(app.state, "engine")
    client = TestClient(app)

    resp = client.post("/status/jobs/engine/some-id/dismiss")
    assert resp.status_code == 404

    resp2 = client.post("/status/jobs/not_a_real_attribute_at_all/some-id/dismiss")
    assert resp2.status_code == 404


def test_clear_finished_removes_only_done_and_error_jobs(temp_db_url):
    app = create_app(db_url=temp_db_url)
    running_id = app.state.axis_score_jobs.create()
    app.state.axis_score_jobs.mark_running(running_id)

    done_id = app.state.dedup_jobs.create()
    app.state.dedup_jobs.mark_running(done_id)
    app.state.dedup_jobs.mark_done(done_id, result=None)

    error_id = app.state.axis_suggest_jobs.create()
    app.state.axis_suggest_jobs.mark_running(error_id)
    app.state.axis_suggest_jobs.mark_error(error_id, "boom")

    client = TestClient(app)
    resp = client.post("/status/jobs/clear-finished")
    assert resp.status_code == 200 and resp.json() == {"ok": True, "cleared": 2}

    remaining = client.get("/status/jobs").json()["jobs"]
    assert len(remaining) == 1
    assert remaining[0]["job_id"] == running_id
    assert remaining[0]["status"] == "running"


def test_running_jobs_sort_before_finished_jobs(temp_db_url):
    app = create_app(db_url=temp_db_url)
    done_id = app.state.dedup_jobs.create()
    app.state.dedup_jobs.mark_running(done_id)
    app.state.dedup_jobs.mark_done(done_id, result=None)

    running_id = app.state.axis_score_jobs.create()
    app.state.axis_score_jobs.mark_running(running_id)

    client = TestClient(app)
    jobs = client.get("/status/jobs").json()["jobs"]
    assert [j["job_id"] for j in jobs] == [running_id, done_id]


def test_prune_finished_older_than_drops_stale_done_and_error_jobs():
    # A white-box unit test of JobStore itself (bypassing the endpoint) to exercise the 1-hour auto-expiry
    # backstop without actually waiting an hour.
    store: JobStore = JobStore()

    old_id = store.create()
    store.mark_done(old_id, result="ok")
    old_job = store.get(old_id)
    store._jobs[old_id] = dataclasses.replace(old_job, finished_at=old_job.finished_at - 7200)  # 2h in the "past"

    fresh_id = store.create()
    store.mark_done(fresh_id, result="ok")

    running_id = store.create()
    store.mark_running(running_id)

    store.prune_finished_older_than(3600)

    assert store.get(old_id) is None
    assert store.get(fresh_id) is not None
    assert store.get(running_id) is not None
