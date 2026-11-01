"""Inc 620: the one "Library modernization" Status entry, the GET /modernization summary, and the frontend logic behind
the Settings panel and the 0.6.0 notice. Disposable databases and scripted model/coordinator state only: no model is
loaded, nothing is downloaded, and no scientific result is computed or changed."""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.embeddings import index_runs
from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, BASELINE_PROFILE_KEY
from app.backend.embeddings.retrieval_resolution import read_preference
from app.backend.model_provisioning.runner import DEBERTA_RELEASE_GATES
from app.backend.modernization.presentation import summarize
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import papers
from app.backend.summarization.nli_profiles import BASELINE_NLI_PROFILE_KEY
from app.backend.summarization.verifier_resolution import read_nli_preference
from tests.test_modernization import (
    ABSENT,
    VERIFIED,
    Counting,
    Recording,
    _add_paper,
    _coordinator,
    _library_0516,
    _snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app" / "frontend" / "js"
DOWNLOADING = {"track": "arctic-s", "state": "downloading", "automatic_provisioning": True}
OFFLINE = {"track": "arctic-s", "state": "waiting_for_network", "automatic_provisioning": True}
INVALID = {"track": "arctic-s", "state": "invalid", "automatic_provisioning": True}
READY = dict(VERIFIED, automatic_provisioning=True)


# ---- helpers ---------------------------------------------------------------------------------------------------------


def _app(db_url: str, model: dict, **kwargs):  # type: ignore[no-untyped-def]
    """An app whose modernization coordinator is enabled and scripted; the lifespan (and its thread) never runs."""
    app = create_app(db_url=db_url)
    coordinator = _coordinator(app.state.engine, kwargs.pop("supervisor", Recording()), model=model, **kwargs)
    app.state.modernization = coordinator
    return app, coordinator, TestClient(app)


def _rows(client: TestClient) -> list[dict]:
    return client.get("/status/jobs").json()["jobs"]


def _modernization_rows(client: TestClient) -> list[dict]:
    return [r for r in _rows(client) if r["store"] == "modernization"]


def _set_run(engine, state: str, **values: object) -> None:  # type: ignore[no-untyped-def]
    from app.backend.embeddings.profiles import PROFILES

    index_runs.upsert_requested(engine, PROFILES[ARCTIC_S_PROFILE_KEY], batch_size=32)
    index_runs.update_run(engine, ARCTIC_S_PROFILE_KEY, state=state, **values)


def _status(**over: object) -> dict:
    base = {
        "enabled": True,
        "intent": "auto",
        "classification": {
            "state": "complete",
            "papers_with_classified_chunks": 4,
            "papers_current": 4,
            "papers_pending": 0,
            "papers_failed_this_session": 0,
        },
        "indexing": {"state": "complete", "eligible_chunks": 8, "indexed_chunks": 8, "missing_chunks": 0},
        "model": dict(READY),
    }
    for key, value in over.items():
        base[key] = dict(base[key], **value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return base


# ---- the pure summary (state mapping) --------------------------------------------------------------------------------


def test_summary_maps_every_state_without_a_combined_percentage_or_estimate() -> None:
    assert summarize(_status())["state"] == "complete"
    assert summarize(_status(enabled=False))["state"] == "disabled"
    paused = summarize(_status(intent="paused", indexing={"state": "paused", "missing_chunks": 4, "indexed_chunks": 4}))
    assert paused["state"] == "paused" and paused["needs_user"] and not paused["automatic_recovery"]
    for s in (paused, summarize(_status(model=DOWNLOADING, indexing={"state": "waiting_for_model"}))):
        assert s["eta_seconds"] is None and "%" not in json.dumps(s)


def test_classification_in_progress_reports_grounded_paper_counts() -> None:  # §13.5
    s = summarize(_status(classification={"state": "running", "papers_current": 1, "papers_pending": 3}))
    assert s["state"] == "working" and s["headline"].startswith("Classifying")
    assert s["progress"] == {"current": 1, "total": 4, "label": "papers classified"}
    assert "1 of 4 papers current, 3 pending" in s["notes"]["classification"]


def test_indexing_outranks_classification_and_keeps_both_stages_visible() -> None:  # §4: concurrent, not sequential
    s = summarize(
        _status(
            classification={"state": "running", "papers_current": 2, "papers_pending": 2},
            indexing={"state": "running", "indexed_chunks": 3, "missing_chunks": 5},
        )
    )
    assert s["headline"] == "Building the Arctic S retrieval index."
    assert s["progress"] == {"current": 3, "total": 8, "label": "passages indexed"}
    assert "in progress" in s["notes"]["classification"] and "3 of 8 passages indexed" in s["notes"]["indexing"]


def test_model_download_has_a_state_label_but_no_byte_progress() -> None:  # §13.3
    s = summarize(
        _status(model=DOWNLOADING, indexing={"state": "waiting_for_model", "indexed_chunks": 0, "missing_chunks": 8})
    )
    assert (
        s["state"] == "working"
        and s["headline"] == "Downloading the Arctic S retrieval model."
        and s["progress"] is None
    )


def test_terminal_states_never_claim_automatic_resumption() -> None:  # §8, §13.14
    invalid = summarize(
        _status(model=INVALID, indexing={"state": "waiting_for_model", "missing_chunks": 8, "indexed_chunks": 0})
    )
    cancelled = summarize(_status(indexing={"state": "cancelled", "indexed_chunks": 2, "missing_chunks": 6}))
    failed = summarize(_status(indexing={"state": "failed", "indexed_chunks": 2, "missing_chunks": 6}))
    for s in (cancelled, failed):
        assert s["state"] == "action_required" and s["needs_user"] and not s["automatic_recovery"]
    assert invalid["attention"] and "will not retry by itself" in invalid["attention"][0]
    for s in (invalid, cancelled, failed):
        assert not any("resumes by itself" in a or "automatically" in a for a in s["attention"])


def test_one_terminal_stage_does_not_hide_a_working_stage() -> None:  # §8, §13.15
    s = summarize(
        _status(
            classification={
                "state": "running",
                "papers_current": 1,
                "papers_pending": 3,
                "papers_failed_this_session": 1,
            },
            indexing={"state": "cancelled", "indexed_chunks": 2, "missing_chunks": 6},
        )
    )
    assert s["state"] == "working" and len(s["attention"]) == 1 and s["progress"]["label"] == "papers classified"
    assert "1 could not be classified this session" in s["notes"]["classification"]


def test_waits_name_their_cause_and_say_they_recover() -> None:  # §7, §13.4, §13.10
    disk = summarize(
        _status(indexing={"state": "waiting_disk", "indexed_chunks": 2, "missing_chunks": 6}),
        run_message="Waiting for disk space. Completed work is saved. Callosum checks again every minute and resumes automatically.",
    )
    assert disk["state"] == "waiting" and "Completed work is saved" in disk["headline"] and disk["automatic_recovery"]
    offline = summarize(
        _status(model=OFFLINE, indexing={"state": "waiting_for_model", "missing_chunks": 8, "indexed_chunks": 0})
    )
    assert offline["state"] == "waiting" and "internet connection" in offline["notes"]["model"]
    memory = summarize(_status(classification={"state": "waiting_resources", "papers_current": 2, "papers_pending": 2}))
    assert memory["state"] == "waiting" and "available memory" in memory["headline"]


# ---- the API and the one Status entry --------------------------------------------------------------------------------


def test_upgrade_from_0516_shows_exactly_one_status_entry(temp_db_url: str) -> None:  # §13.1, §13.18
    _library_0516(temp_db_url, n_papers=2)
    app, coordinator, client = _app(temp_db_url, DOWNLOADING)
    jid = app.state.embedding_index_jobs.create()
    app.state.embedding_index_jobs.mark_running(jid)  # the build's own mirror row must not compete
    rows = _rows(client)
    assert [r["store"] for r in rows] == ["modernization"]
    row = rows[0]
    assert row["label"] == "Library modernization" and row["compute_kind"] == "Local AI" and row["persistent"]
    assert row["nav"] == {"workspace": "settings", "section": "modernization"} and row["status"] == "running"
    assert len(row["notes"]) == 3 and (row["progress"] is None or row["progress"]["eta_seconds"] is None)
    coordinator.enabled = False  # a build without automatic modernization keeps the ordinary build row
    assert [r["store"] for r in _rows(client)] == ["embedding_index_jobs"]


def test_fresh_install_is_marked_empty_and_shows_no_progress(temp_db_url: str) -> None:  # §13.2
    _, _, client = _app(temp_db_url, READY)
    body = client.get("/modernization").json()
    assert body["library_empty"] is True and body["summary"]["progress"] is None
    assert body["summary"]["state"] == "complete" and _modernization_rows(client) == []


def test_network_lost_then_restored(temp_db_url: str) -> None:  # §13.4
    _library_0516(temp_db_url, n_papers=1)
    _, coordinator, client = _app(temp_db_url, OFFLINE)
    assert "internet connection" in " ".join(_modernization_rows(client)[0]["notes"])
    coordinator.model_state["model"] = READY
    notes = " ".join(_modernization_rows(client)[0]["notes"])
    assert "internet" not in notes and "downloaded and verified" in notes


def test_classification_partly_complete_reports_real_counts(temp_db_url: str) -> None:  # §13.6
    _library_0516(temp_db_url, n_papers=4)
    _, coordinator, client = _app(temp_db_url, ABSENT, per_pass=1)
    coordinator.tick()
    c = client.get("/modernization").json()["classification"]
    assert 0 < c["papers_current"] < c["papers_with_classified_chunks"] == 4


def test_arctic_indexing_in_progress_and_import_catch_up(temp_db_url: str) -> None:  # §13.7, §13.8
    _library_0516(temp_db_url, n_papers=2)
    app, coordinator, client = _app(temp_db_url, READY)
    _set_run(app.state.engine, "running", indexed_chunks=1)
    body = client.get("/modernization").json()
    assert body["summary"]["headline"] == "Building the Arctic S retrieval index."
    assert body["summary"]["progress"]["label"] == "passages indexed" and body["summary"]["progress"]["total"] == 4
    index_runs.update_run(app.state.engine, ARCTIC_S_PROFILE_KEY, state="completed")
    before = client.get("/modernization").json()["indexing"]["eligible_chunks"]
    with app.state.engine.begin() as conn:
        _add_paper(conn, "imported later", ["article-fulltext"])
    coordinator._last_full = float("-inf")  # the periodic full check, without waiting half an hour
    coordinator.tick()
    after = client.get("/modernization").json()["indexing"]
    assert after["eligible_chunks"] == before + 2 and after["missing_chunks"] >= 2
    assert _modernization_rows(client)  # the entry reappears for the catch-up


def test_waiting_disk_keeps_the_entry_and_shows_space(temp_db_url: str) -> None:  # §7, §13.9
    _library_0516(temp_db_url, n_papers=1)
    app, _, client = _app(temp_db_url, READY)
    _set_run(
        app.state.engine,
        "waiting_disk",
        disk_required_bytes=5_000_000_000,
        disk_free_bytes=1_000_000_000,
        disk_estimated_bytes=4_000_000_000,
        failure_kind="insufficient_disk",
    )
    body = client.get("/modernization").json()
    assert (
        body["index_run"]["disk"]["required_free_bytes"] == 5_000_000_000 and body["index_run"]["auto_retry_scheduled"]
    )
    assert body["summary"]["state"] == "waiting" and "Completed work is saved" in body["summary"]["headline"]
    assert _modernization_rows(client)[0]["status"] == "running"
    index_runs.update_run(app.state.engine, ARCTIC_S_PROFILE_KEY, state="running")  # space freed: indexing continues
    assert client.get("/modernization").json()["summary"]["state"] == "working"


def test_waiting_for_memory(temp_db_url: str) -> None:  # §13.10
    _library_0516(temp_db_url, n_papers=1)
    app, _, client = _app(temp_db_url, READY)
    _set_run(app.state.engine, "waiting_resources")
    body = client.get("/modernization").json()
    assert body["summary"]["state"] == "waiting" and "memory is low" in body["summary"]["headline"]


def test_pause_survives_restart_resume_clears_it_and_preferences_never_change(temp_db_url: str) -> None:  # §13.11-12
    _library_0516(temp_db_url, n_papers=2)
    app, _, client = _app(temp_db_url, DOWNLOADING)
    with app.state.engine.connect() as conn:
        retrieval_before, nli_before = read_preference(conn), read_nli_preference(conn)
    assert client.post("/modernization/pause").json()["summary"]["state"] == "paused"
    assert client.post("/modernization/pause").json()["intent"] == "paused"  # duplicate Pause is harmless
    _, _, restarted = _app(temp_db_url, DOWNLOADING)
    row = _modernization_rows(restarted)[0]
    assert row["status"] == "pending" and "paused" in row["detail"].lower()
    assert restarted.post("/modernization/resume").json()["intent"] == "auto"
    assert _modernization_rows(restarted)[0]["status"] == "running"
    with app.state.engine.connect() as conn:
        assert read_preference(conn) == retrieval_before and read_nli_preference(conn) == nli_before


def test_cancelled_manual_build_is_action_required(temp_db_url: str) -> None:  # §13.13
    _library_0516(temp_db_url, n_papers=1)
    app, coordinator, client = _app(temp_db_url, READY)
    coordinator.tick()  # classification settles first
    _set_run(app.state.engine, "cancelled", intent="pause")
    row = _modernization_rows(client)[0]
    assert row["status"] == "error" and "cancelled" in row["notes"][0].lower()
    assert "Resume" in row["notes"][0] and "automatically" not in row["notes"][0]


def test_terminal_model_failure_is_action_required(temp_db_url: str) -> None:  # §13.14
    _library_0516(temp_db_url, n_papers=1)
    _, coordinator, client = _app(temp_db_url, INVALID)
    coordinator.tick()
    row = _modernization_rows(client)[0]
    assert row["status"] == "error" and "will not retry by itself" in row["notes"][0]


def test_one_failed_paper_while_indexing_continues(temp_db_url: str) -> None:  # §13.15
    ids = _library_0516(temp_db_url, n_papers=3)
    app, coordinator, client = _app(temp_db_url, READY, derive=Counting(fail_for={ids["papers"][1]}))
    coordinator.tick()
    _set_run(app.state.engine, "running")
    body = client.get("/modernization").json()
    assert body["classification"]["papers_failed_this_session"] == 1
    assert (
        body["summary"]["state"] == "working"
        and "could not be classified" in body["summary"]["notes"]["classification"]
    )


def test_two_app_processes_share_one_library(temp_db_url: str) -> None:  # §13.16
    _library_0516(temp_db_url, n_papers=2)
    _, first, first_client = _app(temp_db_url, READY)
    _, second, second_client = _app(temp_db_url, READY, per_pass=1)
    first._lead()  # the first window holds the library's coordination lock
    second.tick()
    assert len(_modernization_rows(second_client)) == 1
    assert "another Callosum window" in second_client.get("/modernization").json()["summary"]["notes"]["classification"]
    first.shutdown()
    second.shutdown()


def test_status_entry_is_continuous_across_restarts_and_stages(temp_db_url: str) -> None:  # §13.17
    _library_0516(temp_db_url, n_papers=2)
    app, coordinator, client = _app(temp_db_url, DOWNLOADING)
    first = _modernization_rows(client)[0]
    coordinator.model_state["model"] = READY
    _set_run(app.state.engine, "running", indexed_chunks=2)
    second = _modernization_rows(client)[0]
    _, _, restarted = _app(temp_db_url, READY)
    third = _modernization_rows(restarted)[0]
    assert {r["job_id"] for r in (first, second, third)} == {"library"}
    assert second["progress"]["current"] == third["progress"]["current"] == 2  # stored counts, not a reset
    assert restarted.post("/status/jobs/clear-finished").status_code in (200, 204)
    assert _modernization_rows(restarted)  # clearing finished rows never removes it


def test_status_list_survives_a_modernization_failure(temp_db_url: str) -> None:
    app, coordinator, client = _app(temp_db_url, READY)
    jid = app.state.citation_count_jobs.create()
    app.state.citation_count_jobs.mark_running(jid)

    def broken() -> dict:
        raise RuntimeError("C:\\private\\path should never reach Status")

    coordinator.status = broken  # type: ignore[method-assign]
    response = client.get("/status/jobs")
    assert response.status_code == 200 and [r["store"] for r in response.json()["jobs"]] == ["citation_count_jobs"]
    assert "private" not in response.text


def test_status_reads_do_not_wait_for_a_classification_pass(temp_db_url: str) -> None:
    _library_0516(temp_db_url, n_papers=1)
    _, coordinator, client = _app(temp_db_url, READY)
    coordinator.tick()
    held, release = threading.Event(), threading.Event()

    def hold() -> None:
        with coordinator._lock:
            held.set()
            release.wait(30)

    worker = threading.Thread(target=hold)
    worker.start()
    held.wait(5)
    try:
        start = time.monotonic()
        assert client.get("/modernization").status_code == 200 and _modernization_rows(client) is not None
        assert time.monotonic() - start < 5
    finally:
        release.set()
        worker.join()


def test_reading_status_loads_no_model(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:  # §13.22, §9
    _library_0516(temp_db_url, n_papers=1)
    app, _, client = _app(temp_db_url, READY)

    def forbidden(*_a, **_k):  # type: ignore[no-untyped-def]
        raise AssertionError("a status read loaded a model")

    registry = app.state.model_runtime_registry
    for name in ("get_nli_runtime", "get_sentence_transformer_runtime", "get_embedding_runtime"):
        if hasattr(registry, name):
            monkeypatch.setattr(registry, name, forbidden)
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", forbidden, raising=False)
    monkeypatch.setattr("sentence_transformers.CrossEncoder", forbidden, raising=False)
    assert client.get("/modernization").status_code == 200 and client.get("/status/jobs").status_code == 200


def test_no_private_data_or_paths_in_status_responses(temp_db_url: str) -> None:  # §13.23
    _library_0516(temp_db_url, n_papers=2)
    app, _, client = _app(temp_db_url, READY)
    _set_run(app.state.engine, "waiting_disk", disk_required_bytes=10, disk_free_bytes=1, disk_estimated_bytes=9)
    with app.state.engine.connect() as conn:
        titles = [t for (t,) in conn.execute(select(papers.c.title))]
    text = client.get("/modernization").text + client.get("/status/jobs").text
    for secret in titles + [Path(temp_db_url.split("///", 1)[1]).name, str(Path.home()), "Traceback", "huggingface"]:
        assert secret not in text


def test_automatic_retrieval_selection_and_unarmed_deberta(temp_db_url: str) -> None:  # §13.24, §13.25
    _library_0516(temp_db_url, n_papers=1)
    _, _, client = _app(temp_db_url, READY)
    body = client.get("/modernization").json()
    assert (
        body["effective_retrieval"]["profile"] == BASELINE_PROFILE_KEY
        and not body["effective_retrieval"]["ask_blocked"]
    )
    assert body["retrieval_preference"]["source"] != "user"
    verifier = body["verifier"]
    assert verifier["effective"] == BASELINE_NLI_PROFILE_KEY and verifier["automatic_deberta_enabled"] is False
    assert verifier["fallback_reason"] == "not_qualified" and "not enabled" in verifier["explanation"]
    assert DEBERTA_RELEASE_GATES["packaged_runtime_acceptance"] is False and not all(DEBERTA_RELEASE_GATES.values())


def test_polling_and_controls_change_no_scientific_record(temp_db_url: str) -> None:  # §11, §13.26
    _library_0516(temp_db_url, n_papers=2)
    engine = make_engine(temp_db_url)
    before = _snapshot(engine)
    _, _, client = _app(temp_db_url, READY)
    for _ in range(3):
        client.get("/modernization")
        client.get("/status/jobs")
    client.post("/modernization/pause")
    client.post("/modernization/resume")
    assert _snapshot(engine) == before
    engine.dispose()


# ---- the frontend logic (node) ---------------------------------------------------------------------------------------


def _node(chunks: list[str], body: str) -> dict:
    sources = []
    for name in chunks:
        text = (JS / name).read_text(encoding="utf-8")
        if name == "04e_whatsnew.jsx":
            text = text[: text.index("function WhatsNewBanner")]  # the pure part; the component is JSX
        sources.append(text)
    script = f"""
const vm = require('vm');
const calls = [];
const elements = {{}};
const document = {{ getElementById: id => elements[id] || null }};
const frames = [];
const requestAnimationFrame = fn => frames.push(fn);
const ctx = {{ console, document, requestAnimationFrame, elements, frames, calls, JSON }};
vm.runInNewContext({json.dumps(chr(10).join(sources))} + {json.dumps(body)}, ctx);
"""
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_settings_poll_keeps_running_through_waits_including_waiting_disk() -> None:  # §7, §13.9
    out = _node(
        ["04f_modernization_logic.jsx"],
        """
const runs = s => ({ profiles: [{ key: 'minilm' }, { key: 'arctic-s', index_run: { state: s } }] });
const mod = s => ({ summary: { state: s } });
console.log(JSON.stringify({
  running: modernizationPollDelay(mod('working'), runs('running')),
  disk: modernizationPollDelay(mod('waiting'), runs('waiting_disk')),
  memory: modernizationPollDelay(mod('waiting'), runs('waiting_resources')),
  retrying: modernizationPollDelay(mod('waiting'), runs('retrying')),
  classifying: modernizationPollDelay(mod('working'), runs('completed')),
  network: modernizationPollDelay(mod('waiting'), { profiles: [] }),
  paused: modernizationPollDelay(mod('paused'), runs('paused')),
  cancelled: modernizationPollDelay(mod('action_required'), runs('cancelled')),
  complete: modernizationPollDelay(mod('complete'), runs('completed')),
  unknown: modernizationPollDelay(null, null),
  active: INDEX_RUN_ACTIVE_STATES,
}));
""",
    )
    assert out["running"] == 2000 and out["disk"] == out["memory"] == out["retrying"] == 5000
    assert out["classifying"] == 3000 and out["network"] == 10000
    assert out["paused"] is out["cancelled"] is out["complete"] is out["unknown"] is None  # bounded: stops
    assert "waiting_disk" in out["active"]


def test_notice_wording_version_scoping_dismissal_and_action() -> None:  # §5, §13.19, §13.20
    entries = json.loads((ROOT / "app" / "frontend" / "whatsnew.json").read_text(encoding="utf-8"))["entries"]
    out = _node(
        ["04f_modernization_logic.jsx", "04e_whatsnew.jsx"],
        f"""
const entries = {json.dumps(entries)};
const pick = pickWhatsNew(entries, '0.6.0', '0.5.16');
const opened = [];
const action = _whatsNewAction(pick.actionKind, {{ onOpenModernization: () => opened.push(MODERNIZATION_SETTINGS_NAV) }});
action.run();
console.log(JSON.stringify({{
  upgrade: whatsNewHeadline(pick, false), fresh: whatsNewHeadline(pick, true),
  before: pickWhatsNew(entries, '0.5.16', '0.5.15') && pickWhatsNew(entries, '0.5.16', '0.5.15').version,
  dismissed: pickWhatsNew(entries, '0.6.0', '0.6.0'), label: action.label, opened,
}}));
""",
    )
    assert out["before"] != "0.6.0" and out["dismissed"] is None  # not shown before 0.6.0, gone once seen
    upgrade, fresh = out["upgrade"], out["fresh"]
    for phrase in ("stays usable", "untouched", "resumes by itself", "disk space", "Status or Settings"):
        assert phrase in upgrade
    assert upgrade != fresh and "thousand" not in upgrade + fresh and "hour" not in upgrade + fresh
    assert out["opened"] == [{"workspace": "settings", "section": "modernization"}] and out["label"]


def test_settings_section_focus_waits_for_the_lazily_mounted_page() -> None:  # §13.19
    out = _node(
        ["04f_modernization_logic.jsx"],
        """
_focusSettingsSection('modernization');
const pending = frames.length;
elements['modernization'] = { scrollIntoView: opts => calls.push(opts) };
while (frames.length) frames.shift()();
console.log(JSON.stringify({ pending, calls }));
""",
    )
    assert out["pending"] == 1 and out["calls"] == [{"block": "start"}]


def test_frontend_wires_one_loop_one_row_and_no_estimate() -> None:  # §3, §4, §7, §13.18, §13.21
    status = (JS / "04c_status.jsx").read_text(encoding="utf-8")
    settings = (JS / "35j_modernization.jsx").read_text(encoding="utf-8")
    retrieval_file = (JS / "35i_retrieval_profiles.jsx").read_text(encoding="utf-8")
    start = retrieval_file.index("function RetrievalProfileSettings")
    retrieval = retrieval_file[start : retrieval_file.index("\nfunction ", start + 1)]
    app = (JS / "40_app.jsx").read_text(encoding="utf-8")
    persistent = status[status.index("function PersistentStatusRow") : status.index("function StatusJobRow")]
    assert "onDismiss" not in persistent and "eta_seconds: null" in persistent
    assert "j.persistent ||" in status and "!j.persistent &&" in status  # clear-finished keeps the entry
    assert settings.count("setTimeout(") == 1 and "clearTimeout(timer.current)" in settings
    assert "setTimeout" not in retrieval and "useEffect" not in retrieval  # its old private loop is gone
    assert "eta_seconds: null" in settings and "<LibraryModelsSection />" in (JS / "35_settings.jsx").read_text(
        encoding="utf-8"
    )
    assert "_focusSettingsSection(nav.section)" in app and "MODERNIZATION_SETTINGS_NAV" in app
