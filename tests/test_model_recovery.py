"""Inc 622: the manual "Try again" for a terminally failed model checkpoint (recovery contract F8).

Everything is synthetic: mocked network (``FakeHub``), a synthetic manifest, disposable libraries. The action reuses
``Provisioner.provision_once(force=True)``; no test downloads anything, and no test loads a model.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend import app_settings
from app.backend.api import create_app
from app.backend.api.routers import modernization as router
from app.backend.embeddings.profiles import BASELINE_PROFILE_KEY
from app.backend.model_provisioning import provisioner as pv
from app.backend.model_provisioning.manifests import (
    ARCTIC_S_TRACK,
    DEBERTA_TRACK,
    MANIFESTS,
    ArtifactFile,
    ModelManifest,
)
from app.backend.model_provisioning.runner import DEBERTA_RELEASE_GATES, ProvisioningRunner, stop_model_provisioning
from app.backend.modernization import read_intent
from app.backend.modernization.presentation import recovery_message, summarize
from app.backend.persistence.schema import chunk_structure, chunks, embeddings
from tests.test_model_provisioning import CONTENT, REPO, REV, FakeHub
from tests.test_modernization import Recording, _add_paper, _coordinator, _minilm
from tests.test_modernization_status import _set_run, _status

READY_DISK = {"free_bytes": lambda _p: 10**12, "memory_ok": lambda: True, "offline": lambda: False}


DEBERTA_CONTENT = {
    "config.json": json.dumps(
        {
            "model_type": "deberta-v2",
            "architectures": ["DebertaV2ForSequenceClassification"],
            "id2label": {"0": "entailment", "1": "neutral", "2": "contradiction"},
        }
    ).encode(),
    "tokenizer_config.json": json.dumps({"tokenizer_class": "DebertaV2Tokenizer"}).encode(),
    "model.safetensors": b"weights" * 4096,
}


def _good(track: str) -> dict[str, bytes]:
    return DEBERTA_CONTENT if track == DEBERTA_TRACK else CONTENT


def _bad(track: str) -> dict[str, bytes]:
    return dict(_good(track), **{"model.safetensors": b"weights" * 4096})  # same size for Arctic: a hash failure


def _manifest(track: str) -> ModelManifest:
    return ModelManifest(
        track=track,
        repo_id=REPO + "-" + track,
        revision=REV,
        files=tuple(ArtifactFile(p, len(b), hashlib.sha256(b).hexdigest()) for p, b in sorted(_good(track).items())),
        contract=(
            MANIFESTS[DEBERTA_TRACK].contract
            if track == DEBERTA_TRACK
            else {"model_type": "bert", "pooling": "cls", "max_seq_length": 512, "dimension": 384}
        ),
    )


class Env:
    """A real app and real provisioner state on disk; only the network and the manifests' contents are synthetic."""

    def __init__(self, db_url: str, tmp: Path, monkeypatch: pytest.MonkeyPatch, *, papers: int = 2) -> None:
        self.tmp = tmp
        self.hubs = {track: FakeHub(_bad(track)) for track in MANIFESTS}
        self.created: list[pv.Provisioner] = []
        monkeypatch.setattr(router, "default_provisioner", self.provisioner)
        monkeypatch.setattr(router, "auto_provisioning_enabled", lambda: True)
        self.app = create_app(db_url=db_url)
        self.engine = self.app.state.engine
        self.ids: list[int] = []
        with self.engine.begin() as conn:
            for i in range(papers):
                _, ids = _add_paper(conn, f"Paper {i}", ["primary"], per_attachment=2)
                self.ids += ids
            _minilm(conn, self.ids)
        self.model_state = {"track": ARCTIC_S_TRACK, "automatic_provisioning": True}
        self.supervisor = Recording()
        self.coordinator = _coordinator(self.engine, self.supervisor, model=self.model_state)
        self.coordinator._model_status = self.arctic_status
        self.app.state.modernization = self.coordinator
        self.app.state.deberta_model_state = lambda: self.provisioner(DEBERTA_TRACK).status()["state"]
        self.client = TestClient(self.app)

    def provisioner(self, track: str) -> pv.Provisioner:
        p = pv.Provisioner(
            _manifest(track),
            cache_dir=self.tmp / "hub",
            state_dir=self.tmp / "state",
            fetcher=self.hubs[track],
            **READY_DISK,
        )
        self.created.append(p)
        return p

    def arctic_status(self) -> dict:
        return {
            "track": ARCTIC_S_TRACK,
            "state": self.provisioner(ARCTIC_S_TRACK).status()["state"],
            "automatic_provisioning": True,
        }

    def fail(self, track: str = ARCTIC_S_TRACK) -> None:
        """Reach the real terminal state the real way: a download whose bytes fail the pinned hash."""
        assert self.provisioner(track).provision_once()["state"] == pv.INVALID

    def retry(self, track: str = ARCTIC_S_TRACK):  # type: ignore[no-untyped-def]
        return self.client.post(f"/modernization/models/{track}/retry", json={})

    def settle(self, track: str = ARCTIC_S_TRACK, timeout: float = 15.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            runner = (getattr(self.app.state, "model_provisioning", None) or {}).get(track)
            if runner is None or not runner.active:
                return self.provisioner(track).status()
            time.sleep(0.02)
        raise AssertionError("retry did not settle")

    def recovery(self) -> dict:
        return {r["track"]: r for r in self.client.get("/modernization").json()["model_recovery"]}


@pytest.fixture
def env(temp_db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    created = Env(temp_db_url, tmp_path, monkeypatch)
    yield created
    stop_model_provisioning(created.app)


# ---- visibility -----------------------------------------------------------------------------------------------------


def test_invalid_checkpoint_offers_try_again_with_an_accurate_explanation(env: Env) -> None:  # 1
    env.fail()
    env.coordinator.tick()
    item = env.recovery()[ARCTIC_S_TRACK]
    assert item["can_retry"] is True and item["retrying"] is False and item["state"] == "invalid"
    body = env.client.get("/modernization").json()
    assert body["summary"]["state"] == "action_required"
    note = body["summary"]["notes"]["model"]
    assert "failed verification" in note and "will not retry by itself" in note and "Try again" in note
    assert "no in-app repair" not in note


@pytest.mark.parametrize(
    "state", ["absent", "downloading", "waiting_for_network", "insufficient_resources", "verified"]
)
def test_no_repair_offer_for_normal_states(env: Env, monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    real = pv.Provisioner.status

    def scripted(self):  # type: ignore[no-untyped-def]
        return {**real(self), "state": state} if self.manifest.track == ARCTIC_S_TRACK else real(self)

    monkeypatch.setattr(pv.Provisioner, "status", scripted)
    assert env.recovery() == {}
    assert env.retry().status_code == 409  # refused, and nothing was fetched
    assert env.hubs[ARCTIC_S_TRACK].calls == []


def test_pinned_version_unavailable_has_its_own_explanation() -> None:
    item = {
        "track": ARCTIC_S_TRACK,
        "state": "invalid",
        "error_kind": "pinned_revision_unavailable",
        "retrying": False,
        "can_retry": True,
        "manual_retries": 0,
    }
    note = summarize(_status(model={"state": "invalid", "automatic_provisioning": True}), recovery=[item])["notes"][
        "model"
    ]
    assert note == recovery_message(item)
    assert "could not be obtained" in note and "failed verification" not in note


# ---- the action -----------------------------------------------------------------------------------------------------


def test_successful_retry_progresses_to_verified_refetching_only_what_failed(env: Env) -> None:  # 2, 7
    env.fail()
    good = env.provisioner(ARCTIC_S_TRACK).snapshot_root / "config.json"
    before = good.stat().st_mtime_ns
    hub = env.hubs[ARCTIC_S_TRACK]
    hub.calls.clear()
    hub.content = dict(CONTENT)
    assert env.retry().status_code == 200
    assert env.settle()["state"] == pv.VERIFIED
    assert [(c[0], c[1], c[2], c[4]) for c in hub.calls] == [
        (_manifest(ARCTIC_S_TRACK).repo_id, REV, "model.safetensors", True)
    ]
    assert good.stat().st_mtime_ns == before  # a verified file is left alone
    assert env.recovery() == {}
    assert env.provisioner(ARCTIC_S_TRACK).is_verified()


def test_retry_that_fails_again_stays_visible_and_actionable(env: Env) -> None:  # 3, 16
    env.fail()
    assert env.retry().status_code == 200
    assert env.settle()["state"] == pv.INVALID  # the source still serves bad bytes
    item = env.recovery()[ARCTIC_S_TRACK]
    assert item["can_retry"] is True and item["manual_retries"] == 1
    assert "did not fix" in item["message"]
    assert not env.provisioner(ARCTIC_S_TRACK).is_verified()
    env.hubs[ARCTIC_S_TRACK].content = dict(CONTENT)
    env.retry()
    assert env.settle()["state"] == pv.VERIFIED
    assert env.provisioner(ARCTIC_S_TRACK)._read()["manual_retries"] == 0


def test_a_deterministic_failure_is_not_retried_without_another_click(env: Env) -> None:
    env.fail()
    env.retry()
    env.settle()
    calls = len(env.hubs[ARCTIC_S_TRACK].calls)
    time.sleep(0.3)
    assert len(env.hubs[ARCTIC_S_TRACK].calls) == calls


def test_network_loss_during_a_retry_keeps_the_retry_force_until_it_settles(tmp_path: Path) -> None:
    hub = FakeHub(_bad("synthetic"))
    p = pv.Provisioner(
        _manifest("synthetic"), cache_dir=tmp_path / "hub", state_dir=tmp_path / "s", fetcher=hub, **READY_DISK
    )
    assert p.provision_once()["state"] == pv.INVALID
    hub.content = dict(CONTENT)
    hub.failures = [ConnectionError("down")]
    p._backoff = (0.01,)
    runner = ProvisioningRunner(p, force=True, min_wait_seconds=0.01)
    assert runner.run()["state"] == pv.VERIFIED  # a plain attempt would have re-declared the corrupt file invalid


def test_retrying_one_model_does_not_touch_the_other(env: Env) -> None:  # 4
    env.fail(ARCTIC_S_TRACK)
    env.fail(DEBERTA_TRACK)
    arctic_before = env.provisioner(ARCTIC_S_TRACK)._read()
    env.hubs[ARCTIC_S_TRACK].calls.clear()
    env.hubs[DEBERTA_TRACK].calls.clear()
    env.hubs[DEBERTA_TRACK].content = dict(DEBERTA_CONTENT)
    assert env.retry(DEBERTA_TRACK).status_code == 200
    assert env.settle(DEBERTA_TRACK)["state"] == pv.VERIFIED
    assert env.hubs[ARCTIC_S_TRACK].calls == []
    assert env.provisioner(ARCTIC_S_TRACK)._read() == arctic_before
    assert list(env.recovery()) == [ARCTIC_S_TRACK]


def test_duplicate_clicks_start_one_retry(env: Env) -> None:  # 5
    env.fail()
    hub = env.hubs[ARCTIC_S_TRACK]
    hub.calls.clear()
    release = threading.Event()
    real = hub.__call__

    class Slow:
        def __call__(self, *args):  # type: ignore[no-untyped-def]
            release.wait(10)
            return real(*args)

    env.hubs[ARCTIC_S_TRACK] = Slow()  # type: ignore[assignment]
    first = env.retry()
    runner = env.app.state.model_provisioning[ARCTIC_S_TRACK]
    responses = [env.retry() for _ in range(5)]
    assert first.status_code == 200 and all(r.status_code == 200 for r in responses)
    assert env.app.state.model_provisioning[ARCTIC_S_TRACK] is runner
    item = env.recovery()[ARCTIC_S_TRACK]
    assert item["retrying"] is True and item["can_retry"] is False
    release.set()
    env.settle()
    assert [c[2] for c in hub.calls] == ["model.safetensors"]  # one fetch, not six


def test_two_processes_cannot_provision_the_same_checkpoint(env: Env) -> None:  # 6
    env.fail()
    hub = env.hubs[ARCTIC_S_TRACK]
    hub.calls.clear()
    other = env.provisioner(ARCTIC_S_TRACK)  # holds the same OS lock another Callosum process would hold
    assert other._lock.acquire()
    try:
        response = env.retry()  # that process owns the track: status reports it, and no second download starts
        assert response.status_code == 409 and hub.calls == []
    finally:
        other._lock.release()


def test_retry_cannot_name_a_repository_or_revision(env: Env) -> None:  # 7
    env.fail()
    hub = env.hubs[ARCTIC_S_TRACK]
    hub.calls.clear()
    response = env.client.post(
        f"/modernization/models/{ARCTIC_S_TRACK}/retry", json={"repo_id": "evil/model", "revision": "main"}
    )
    assert response.status_code == 200
    env.settle()
    assert {(c[0], c[1]) for c in hub.calls} == {(_manifest(ARCTIC_S_TRACK).repo_id, REV)}


@pytest.mark.parametrize(
    "name", ["unknown", "..%2f..%2fetc", "all-MiniLM-L6-v2", "Snowflake%2Fsnowflake-arctic-embed-s"]
)
def test_unknown_model_is_rejected(env: Env, name: str) -> None:  # 10
    response = env.client.post(f"/modernization/models/{name}/retry", json={})
    assert response.status_code in (404, 405)
    assert "app_data" not in response.text and "evil" not in response.text


def test_refused_when_automatic_provisioning_is_off(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    env.fail()
    monkeypatch.setattr(router, "auto_provisioning_enabled", lambda: False)
    item = env.recovery()[ARCTIC_S_TRACK]
    assert item["can_retry"] is False and "off in this build" in item["message"]
    assert env.retry().status_code == 409


def test_read_only_mode_rejects_retry(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:  # 8
    env.fail()
    env.hubs[ARCTIC_S_TRACK].calls.clear()
    monkeypatch.setenv("CALLOSUM_READ_ONLY", "1")
    assert env.retry().status_code == 403
    assert env.hubs[ARCTIC_S_TRACK].calls == []
    assert env.provisioner(ARCTIC_S_TRACK).status()["state"] == pv.INVALID


def test_unauthorized_request_is_rejected(env: Env) -> None:  # 9
    env.fail()
    env.hubs[ARCTIC_S_TRACK].calls.clear()
    app_settings.set_access_token("a-test-token-long-enough-for-the-gate")
    app_settings.set_remote_access_enabled(True)
    assert env.retry().status_code == 401
    assert env.hubs[ARCTIC_S_TRACK].calls == []
    ok = env.client.post(
        f"/modernization/models/{ARCTIC_S_TRACK}/retry",
        json={},
        headers={"Authorization": "Bearer a-test-token-long-enough-for-the-gate"},
    )
    assert ok.status_code == 200
    env.settle()


# ---- dependent work and frozen behaviour -----------------------------------------------------------------------------


def test_paused_modernization_stays_paused_after_repair(env: Env) -> None:  # 11
    env.fail()
    env.client.post("/modernization/pause", json={})
    env.hubs[ARCTIC_S_TRACK].content = dict(CONTENT)
    assert env.retry().status_code == 200
    assert env.settle()["state"] == pv.VERIFIED
    env.coordinator.tick()
    body = env.client.get("/modernization").json()
    assert read_intent(env.engine) == "paused" and body["summary"]["state"] == "paused"
    assert env.supervisor.starts == 0


def test_cancelled_build_is_not_restarted_by_a_repair(env: Env) -> None:
    env.fail()
    env.coordinator.tick()
    _set_run(env.engine, "cancelled", intent="cancel")
    env.hubs[ARCTIC_S_TRACK].content = dict(CONTENT)
    env.retry()
    assert env.settle()["state"] == pv.VERIFIED
    env.coordinator.tick()
    assert env.supervisor.starts == 0


def test_explicit_retrieval_choice_is_not_overridden(env: Env) -> None:
    env.fail()
    assert env.client.put("/embedding-profiles/active", json={"key": BASELINE_PROFILE_KEY}).status_code == 200
    before = env.client.get("/modernization").json()["retrieval_preference"]
    env.hubs[ARCTIC_S_TRACK].content = dict(CONTENT)
    env.retry()
    env.settle()
    env.coordinator.tick()
    assert env.client.get("/modernization").json()["retrieval_preference"] == before


def test_verified_repair_lets_scheduled_work_start_and_wakes_the_coordinator(env: Env) -> None:
    env.fail()
    env.coordinator.tick()
    assert env.supervisor.starts == 0  # nothing starts on an invalid checkpoint
    env.coordinator._wake.clear()
    env.hubs[ARCTIC_S_TRACK].content = dict(CONTENT)
    env.retry()
    env.settle()
    assert env.coordinator._wake.wait(5)  # no waiting for the next 60 s check
    env.coordinator.tick()
    assert env.supervisor.starts == 1


def test_minilm_serves_ask_throughout_the_repair(env: Env) -> None:  # 12, 15
    env.fail()
    assert env.client.get("/modernization").json()["effective_retrieval"]["profile"] == "minilm"
    release = threading.Event()
    real = env.hubs[ARCTIC_S_TRACK]
    real.content = dict(CONTENT)

    def slow(*args):  # type: ignore[no-untyped-def]
        release.wait(10)
        return real(*args)

    env.hubs[ARCTIC_S_TRACK] = slow  # type: ignore[assignment]
    env.retry()
    during = env.client.get("/modernization").json()
    assert during["effective_retrieval"]["profile"] == "minilm"
    assert not env.provisioner(ARCTIC_S_TRACK).is_verified()  # the only thing that lets a consumer load it
    assert all(e.loaded_model is None for e in env.app.state.model_runtime_registry.runtime_entries())
    release.set()
    env.settle()


def test_minilm2_stays_the_automatic_verifier_after_a_deberta_repair(env: Env) -> None:  # 13
    gates = dict(DEBERTA_RELEASE_GATES)
    env.fail(DEBERTA_TRACK)
    item = env.recovery()[DEBERTA_TRACK]
    assert "does not turn on automatic" in item["message"]
    env.hubs[DEBERTA_TRACK].content = dict(DEBERTA_CONTENT)
    env.retry(DEBERTA_TRACK)
    assert env.settle(DEBERTA_TRACK)["state"] == pv.VERIFIED
    verifier = env.client.get("/modernization").json()["verifier"]
    assert verifier["automatic_deberta_enabled"] is False and "DeBERTa" not in verifier["effective_label"]
    assert DEBERTA_RELEASE_GATES == gates and DEBERTA_RELEASE_GATES["packaged_runtime_acceptance"] is False


def test_interrupted_deberta_retry_is_not_stranded_after_a_restart(env: Env) -> None:
    env.fail(DEBERTA_TRACK)
    env.hubs[DEBERTA_TRACK].failures = [ConnectionError("down")]
    p = env.provisioner(DEBERTA_TRACK)
    assert p.provision_once(force=True)["state"] == pv.WAITING_FOR_NETWORK  # then the app restarts: no runner remains
    assert env.recovery()[DEBERTA_TRACK]["can_retry"] is True
    env.hubs[DEBERTA_TRACK].content = dict(DEBERTA_CONTENT)
    assert env.retry(DEBERTA_TRACK).status_code == 200
    assert env.settle(DEBERTA_TRACK)["state"] == pv.VERIFIED


def test_deberta_is_never_downloaded_unless_it_already_failed(env: Env) -> None:
    assert env.provisioner(DEBERTA_TRACK).status()["state"] == pv.ABSENT
    assert env.retry(DEBERTA_TRACK).status_code == 409
    assert env.hubs[DEBERTA_TRACK].calls == []


def _rows(env: Env) -> dict[str, list[tuple]]:
    with env.engine.connect() as conn:
        return {
            t.name: sorted((tuple(r) for r in conn.execute(select(t))), key=repr)
            for t in (chunks, chunk_structure, embeddings)
        }


def test_library_rows_and_unrelated_cache_are_untouched(env: Env) -> None:  # 14
    env.fail()
    env.coordinator.tick()  # classify first, so completed classification rows exist to be preserved
    before = _rows(env)
    assert before["chunk_structure"] and before["embeddings"]
    neighbour = env.tmp / "hub" / "models--someone--else" / "snapshots" / "abc" / "model.safetensors"
    neighbour.parent.mkdir(parents=True)
    neighbour.write_bytes(b"not ours")
    state_neighbour = env.tmp / "state" / "unrelated.json"
    state_neighbour.write_text("{}", encoding="utf-8")
    env.hubs[ARCTIC_S_TRACK].content = dict(CONTENT)
    env.retry()
    assert env.settle()["state"] == pv.VERIFIED
    assert neighbour.read_bytes() == b"not ours" and state_neighbour.read_text(encoding="utf-8") == "{}"
    assert _rows(env) == before


# ---- Status and Settings report the real state ---------------------------------------------------------------------


def test_status_and_settings_report_the_retry_not_success(env: Env) -> None:  # 16
    env.fail()
    release = threading.Event()
    real = env.hubs[ARCTIC_S_TRACK]
    real.content = dict(CONTENT)

    def slow(*args):  # type: ignore[no-untyped-def]
        release.wait(10)
        return real(*args)

    env.hubs[ARCTIC_S_TRACK] = slow  # type: ignore[assignment]
    env.retry()
    body = env.client.get("/modernization").json()
    assert body["model"]["verified"] is False
    assert "trying again" in body["summary"]["notes"]["model"].lower()
    assert body["summary"]["attention"] == []  # the failure is being acted on, not forgotten
    rows = [r for r in env.client.get("/status/jobs").json()["jobs"] if r["job_id"] == "library"]
    assert len(rows) == 1 and rows[0]["status"] == "running" and "again" in rows[0]["detail"]
    assert rows[0]["progress"] is None  # no invented download percentage
    release.set()
    env.settle()
    assert env.client.get("/modernization").json()["model"]["verified"] is True


def test_deberta_retry_is_findable_in_the_one_status_entry(env: Env) -> None:
    env.fail(DEBERTA_TRACK)
    env.hubs[DEBERTA_TRACK].content = dict(DEBERTA_CONTENT)
    release = threading.Event()
    real = env.hubs[DEBERTA_TRACK]

    def slow(*args):  # type: ignore[no-untyped-def]
        release.wait(10)
        return real(*args)

    env.hubs[DEBERTA_TRACK] = slow  # type: ignore[assignment]
    env.retry(DEBERTA_TRACK)
    rows = [r for r in env.client.get("/status/jobs").json()["jobs"] if r["job_id"] == "library"]
    assert len(rows) == 1 and rows[0]["status"] == "running"
    assert any("DeBERTa" in note for note in [rows[0]["detail"], *rows[0]["notes"]])
    release.set()
    env.settle(DEBERTA_TRACK)


def test_responses_carry_no_path_or_exception_text(env: Env) -> None:
    env.fail()
    env.retry()
    env.settle()
    text = env.client.get("/modernization").text + env.client.get("/status/jobs").text
    for secret in (str(env.tmp), "model.safetensors", "Traceback", "hash mismatch"):
        assert secret not in text
