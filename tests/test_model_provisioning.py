"""Inc 615: automatic, restart-safe model provisioning. Synthetic checkpoints and a mocked network only; the one
real-cache test reads already-present snapshots and refuses any fetch."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.backend.model_provisioning import manifests as mf
from app.backend.model_provisioning import provisioner as pv
from app.backend.model_provisioning import runner as rn
from app.backend.model_provisioning.manifests import ArtifactFile, ModelManifest

REPO = "example/tiny-encoder"
REV = "a" * 40
CONTENT = {
    "config.json": json.dumps({"model_type": "bert"}).encode(),
    "1_Pooling/config.json": json.dumps(
        {"pooling_mode_cls_token": True, "pooling_mode_mean_tokens": False, "word_embedding_dimension": 384}
    ).encode(),
    "sentence_bert_config.json": json.dumps({"max_seq_length": 512}).encode(),
    "model.safetensors": b"\x01weights" * 4096,
}


def manifest_for(content: dict[str, bytes], track: str = "synthetic", contract: dict | None = None) -> ModelManifest:
    return ModelManifest(
        track=track,
        repo_id=REPO,
        revision=REV,
        files=tuple(ArtifactFile(p, len(b), hashlib.sha256(b).hexdigest()) for p, b in sorted(content.items())),
        contract=contract or {"model_type": "bert", "pooling": "cls", "max_seq_length": 512, "dimension": 384},
    )


class FakeHub:
    """Mocked network: writes manifest files into the cache exactly where the Hub client would."""

    def __init__(self, content: dict[str, bytes]) -> None:
        self.content = dict(content)
        self.calls: list[tuple] = []
        self.failures: list[BaseException] = []  # raised (in order) before writing, one per call

    def __call__(self, repo_id, revision, filename, cache_dir, force):
        self.calls.append((repo_id, revision, filename, Path(cache_dir), force))
        if self.failures:
            raise self.failures.pop(0)
        root = Path(cache_dir) / ("models--" + repo_id.replace("/", "--")) / "snapshots" / revision
        target = root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.content[filename])
        return str(target)


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def make(tmp_path: Path, hub: FakeHub, manifest: ModelManifest | None = None, **kw) -> pv.Provisioner:
    kw.setdefault("free_bytes", lambda _p: 10**12)
    kw.setdefault("memory_ok", lambda: True)
    kw.setdefault("offline", lambda: False)
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)  # tests take the lock by hand
    return pv.Provisioner(
        manifest or manifest_for(CONTENT), cache_dir=tmp_path / "hub", state_dir=tmp_path / "state", fetcher=hub, **kw
    )


def seed_cache(p: pv.Provisioner, content: dict[str, bytes]) -> None:
    for name, data in content.items():
        target = p.snapshot_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def test_already_cached_needs_no_network(tmp_path):
    hub = FakeHub(CONTENT)
    p = make(tmp_path, hub)
    seed_cache(p, CONTENT)
    assert p.status()["state"] == pv.PRESENT_UNVERIFIED
    assert p.provision_once()["state"] == pv.VERIFIED
    assert hub.calls == []


def test_first_time_provisioning_fetches_each_file_once(tmp_path):
    hub = FakeHub(CONTENT)
    p = make(tmp_path, hub)
    assert p.status()["state"] == pv.ABSENT
    status = p.provision_once()
    assert status["state"] == pv.VERIFIED and status["verified_at"]
    assert sorted(c[2] for c in hub.calls) == sorted(CONTENT)
    assert all(c[:2] == (REPO, REV) and c[4] is False for c in hub.calls)


def test_network_unavailable_then_restored_with_bounded_backoff(tmp_path):
    hub = FakeHub(CONTENT)
    clock = Clock()
    p = make(tmp_path, hub, clock=clock, backoff=(30.0, 120.0))
    hub.failures = [ConnectionError("no route")]
    s1 = p.provision_once()
    assert (s1["state"], s1["error_kind"]) == (pv.WAITING_FOR_NETWORK, "network")
    assert s1["next_attempt_at"] == clock.now + 30.0
    hub.failures = [TimeoutError("timed out")]
    assert p.provision_once()["next_attempt_at"] == clock.now + 120.0
    hub.failures = [TimeoutError("timed out")]
    assert p.provision_once()["next_attempt_at"] == clock.now + 120.0  # capped, still retryable, never terminal
    restored = p.provision_once()
    assert restored["state"] == pv.VERIFIED and restored["error_kind"] is None


def test_offline_mode_waits_without_any_request(tmp_path):
    hub = FakeHub(CONTENT)
    p = make(tmp_path, hub, offline=lambda: True)
    assert p.provision_once()["state"] == pv.WAITING_FOR_NETWORK
    assert hub.calls == []


def test_interrupted_download_resumes_after_restart(tmp_path):
    hub = FakeHub(CONTENT)
    p = make(tmp_path, hub)

    class Killed(BaseException):  # not an Exception: models a process dying mid-transfer
        pass

    names = sorted(CONTENT)
    original = hub.__call__

    def dies_on_last(repo_id, revision, filename, cache_dir, force):
        if filename == names[-1]:
            partial = p.snapshot_root / f"{filename}.incomplete"
            partial.write_bytes(CONTENT[filename][:10])
            raise Killed()
        return original(repo_id, revision, filename, cache_dir, force)

    p._fetch = dies_on_last
    with pytest.raises(Killed):
        p.provision_once()
    restarted = make(tmp_path, hub)  # a fresh process: the OS released the lock
    assert restarted.status()["state"] == pv.INTERRUPTED
    hub.calls.clear()
    assert restarted.provision_once()["state"] == pv.VERIFIED
    assert [c[2] for c in hub.calls] == [names[-1]]  # completed files are not fetched again


def test_killed_process_releases_ownership(tmp_path):
    p = make(tmp_path, FakeHub(CONTENT))
    p._write(state=pv.DOWNLOADING)
    script = textwrap.dedent(
        f"""
        import sys, time
        sys.path.insert(0, {str(Path.cwd())!r})
        from app.backend.embeddings.index_lock import WorkerLock
        from pathlib import Path
        lock = WorkerLock(Path({str(tmp_path / "state" / "synthetic.lock")!r}))
        assert lock.acquire()
        print("held", flush=True)
        time.sleep(60)
        """
    )
    child = subprocess.Popen([sys.executable, "-I", "-c", script], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "held"
        status = p.status()
        assert status["state"] == pv.DOWNLOADING and status["owned_elsewhere"]
        hub = FakeHub(CONTENT)
        p._fetch = hub
        assert p.provision_once()["state"] == pv.DOWNLOADING and hub.calls == []  # no duplicate download
    finally:
        child.kill()
        child.wait(10)
    assert p.status()["state"] == pv.INTERRUPTED


def test_two_instances_never_download_concurrently(tmp_path):
    hub = FakeHub(CONTENT)
    a, b = make(tmp_path, hub), make(tmp_path, hub)
    assert a._lock.acquire()
    try:
        assert b.provision_once()["owned_elsewhere"] is True
        assert hub.calls == []
    finally:
        a._lock.release()
    assert b.provision_once()["state"] == pv.VERIFIED
    calls = len(hub.calls)
    assert a.provision_once()["state"] == pv.VERIFIED and len(hub.calls) == calls


def test_pinned_revision_unavailable_is_terminal_until_explicit_retry(tmp_path):
    class RevisionNotFoundError(Exception):
        pass

    hub = FakeHub(CONTENT)
    p = make(tmp_path, hub)
    hub.failures = [RevisionNotFoundError("404 revision")]
    status = p.provision_once()
    assert (status["state"], status["error_kind"]) == (pv.INVALID, "pinned_revision_unavailable")
    hub.calls.clear()
    assert p.provision_once()["state"] == pv.INVALID and hub.calls == []  # never retried automatically
    assert make(tmp_path, hub).status()["state"] == pv.INVALID  # survives restart
    assert p.provision_once(force=True)["state"] == pv.VERIFIED


def test_corrupt_download_is_terminal_and_explicit_retry_refetches_only_it(tmp_path):
    bad = dict(CONTENT, **{"model.safetensors": b"\x02weights" * 4096})  # same size, different bytes
    hub = FakeHub(bad)
    p = make(tmp_path, hub)
    status = p.provision_once()
    assert (status["state"], status["error_kind"]) == (pv.INVALID, "integrity")
    assert "model.safetensors" in status["diagnostic"]
    hub.calls.clear()
    assert p.provision_once()["state"] == pv.INVALID and hub.calls == []
    hub.content = dict(CONTENT)
    assert p.provision_once(force=True)["state"] == pv.VERIFIED
    assert [(c[2], c[4]) for c in hub.calls] == [("model.safetensors", True)]


def test_corrupt_cache_entry_is_reported_without_fetching(tmp_path):
    hub = FakeHub(CONTENT)
    p = make(tmp_path, hub)
    seed_cache(p, dict(CONTENT, **{"model.safetensors": b"weights" * 4096}))  # right size, wrong bytes
    assert p.provision_once()["state"] == pv.INVALID and hub.calls == []


def test_contract_mismatch_is_invalid(tmp_path):
    wrong = dict(
        CONTENT,
        **{
            "1_Pooling/config.json": json.dumps(
                {"pooling_mode_cls_token": False, "pooling_mode_mean_tokens": True, "word_embedding_dimension": 384}
            ).encode()
        },
    )
    p = make(tmp_path, FakeHub(wrong), manifest_for(wrong))
    status = p.provision_once()
    assert (status["state"], status["error_kind"]) == (pv.INVALID, "contract")


def test_deberta_static_contract_checks_labels_architecture_tokenizer(tmp_path):
    base = mf.MANIFESTS[mf.DEBERTA_TRACK]
    good = {
        "config.json": json.dumps(
            {
                "model_type": "deberta-v2",
                "architectures": ["DebertaV2ForSequenceClassification"],
                "id2label": {"0": "entailment", "1": "neutral", "2": "contradiction"},
            }
        ).encode(),
        "tokenizer_config.json": json.dumps({"tokenizer_class": "DebertaV2Tokenizer"}).encode(),
    }
    m = dataclasses.replace(manifest_for(good, track=mf.DEBERTA_TRACK), contract=base.contract)
    assert make(tmp_path / "ok", FakeHub(good), m).provision_once()["state"] == pv.VERIFIED
    swapped = dict(good)
    swapped["config.json"] = json.dumps(
        {
            "model_type": "deberta-v2",
            "architectures": ["DebertaV2ForSequenceClassification"],
            "id2label": {"0": "contradiction", "1": "neutral", "2": "entailment"},
        }
    ).encode()
    m2 = dataclasses.replace(manifest_for(swapped, track=mf.DEBERTA_TRACK), contract=base.contract)
    status = make(tmp_path / "bad", FakeHub(swapped), m2).provision_once()
    assert (status["state"], status["error_kind"]) == (pv.INVALID, "contract")
    assert "label order" in status["diagnostic"]


def test_verified_receipt_survives_restart_and_detects_changes(tmp_path):
    hub = FakeHub(CONTENT)
    p = make(tmp_path, hub)
    p.provision_once()
    restarted = make(tmp_path, hub)
    assert restarted.status()["state"] == pv.VERIFIED and restarted.is_verified()
    target = p.snapshot_root / "config.json"
    os.utime(target, ns=(target.stat().st_atime_ns, target.stat().st_mtime_ns + 10**9))
    assert restarted.status()["state"] == pv.PRESENT_UNVERIFIED  # touched: trust nothing until re-hashed
    hub.calls.clear()
    assert restarted.provision_once()["state"] == pv.VERIFIED and hub.calls == []


def test_insufficient_disk_or_memory_is_retryable(tmp_path):
    hub = FakeHub(CONTENT)
    disk = make(tmp_path / "d", hub, free_bytes=lambda _p: 1)
    status = disk.provision_once()
    assert (status["state"], status["error_kind"]) == (pv.INSUFFICIENT_RESOURCES, "disk_space")
    assert status["next_attempt_at"] is not None and hub.calls == []
    mem = make(tmp_path / "m", hub, memory_ok=lambda: False)
    assert mem.provision_once()["error_kind"] == "memory"
    enospc = make(tmp_path / "e", hub)
    hub.failures = [OSError(28, "No space left on device")]
    assert enospc.provision_once()["state"] == pv.INSUFFICIENT_RESOURCES


def test_tracks_are_independent(tmp_path):
    other = dict(CONTENT)
    hub_a = FakeHub(CONTENT)
    a = make(tmp_path, hub_a, manifest_for(CONTENT, track="track-a"))
    b = make(tmp_path, FakeHub(other), dataclasses.replace(manifest_for(other, track="track-b"), repo_id="x/other"))
    assert a._lock.acquire()
    try:
        assert b.provision_once()["state"] == pv.VERIFIED  # a's lock does not block b
    finally:
        a._lock.release()
    hub_a.failures = [type("RepositoryNotFoundError", (Exception,), {})("gone")]
    assert a.provision_once()["state"] == pv.INVALID
    assert b.status()["state"] == pv.VERIFIED


def test_requests_name_only_the_pinned_manifest(tmp_path):
    hub = FakeHub(CONTENT)
    p = make(tmp_path, hub)
    p.provision_once()
    allowed = {(REPO, REV, f.path) for f in p.manifest.files}
    assert {c[:3] for c in hub.calls} <= allowed
    assert all(c[3] == tmp_path / "hub" for c in hub.calls)


def test_classification_of_failures():
    from huggingface_hub.errors import LocalEntryNotFoundError

    def http(status):
        exc = Exception(f"HTTP {status}")
        exc.response = SimpleNamespace(status_code=status)
        return exc

    cases = {
        LocalEntryNotFoundError("cannot reach the Hub"): (pv.WAITING_FOR_NETWORK, "network"),
        ConnectionError("reset"): (pv.WAITING_FOR_NETWORK, "network"),
        type("ReadTimeout", (Exception,), {})("slow"): (pv.WAITING_FOR_NETWORK, "network"),
        type("ConnectError", (Exception,), {})("httpx"): (pv.WAITING_FOR_NETWORK, "network"),
        http(503): (pv.WAITING_FOR_NETWORK, "network"),
        http(429): (pv.WAITING_FOR_NETWORK, "network"),
        http(404): (pv.INVALID, "pinned_revision_unavailable"),
        type("RevisionNotFoundError", (Exception,), {})("x"): (pv.INVALID, "pinned_revision_unavailable"),
        OSError(28, "full"): (pv.INSUFFICIENT_RESOURCES, "disk_full"),
        ValueError("strange"): (pv.INTERRUPTED, "unexpected"),
    }
    for exc, expected in cases.items():
        assert pv.classify(exc) == expected, exc


def test_runner_retries_until_settled_then_stops(tmp_path):
    hub = FakeHub(CONTENT)
    hub.failures = [ConnectionError("down"), ConnectionError("down")]
    p = make(tmp_path, hub, backoff=(0.0,))
    runner = rn.ProvisioningRunner(p, min_wait_seconds=0.0)
    assert runner.run()["state"] == pv.VERIFIED
    assert len(hub.calls) == 2 + len(CONTENT)


def test_runner_stops_on_terminal_invalid(tmp_path):
    hub = FakeHub(CONTENT)
    hub.failures = [type("GatedRepoError", (Exception,), {})("gated")]
    runner = rn.ProvisioningRunner(make(tmp_path, hub), min_wait_seconds=0.0)
    assert runner.run()["state"] == pv.INVALID and len(hub.calls) == 1


def test_deberta_gate_is_not_armed_and_not_circular():
    assert rn.DEBERTA_RELEASE_GATES["runtime_qualification_recorded"] is True
    assert rn.deberta_auto_provisioning_armed() is False
    assert rn.provisioning_tracks() == [mf.ARCTIC_S_TRACK]
    assert all(isinstance(v, bool) for v in rn.DEBERTA_RELEASE_GATES.values())  # recorded facts, nothing derived
    armed = dict.fromkeys(rn.DEBERTA_RELEASE_GATES, True)
    assert rn.provisioning_tracks(armed) == [mf.ARCTIC_S_TRACK, mf.DEBERTA_TRACK]


def test_auto_provisioning_switch(monkeypatch):
    monkeypatch.delenv("CALLOSUM_DISABLE_MODEL_PROVISIONING", raising=False)
    monkeypatch.delenv("CALLOSUM_MODEL_PROVISIONING", raising=False)
    monkeypatch.delenv("CALLOSUM_APP_DATA_DIR", raising=False)
    assert rn.auto_provisioning_enabled() is False  # source checkout: no unrequested download
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", "C:/somewhere")
    assert rn.auto_provisioning_enabled() is True  # packaged app
    monkeypatch.setenv("CALLOSUM_DISABLE_MODEL_PROVISIONING", "1")
    assert rn.auto_provisioning_enabled() is False
    api = SimpleNamespace(state=SimpleNamespace())
    rn.start_model_provisioning(api)
    assert api.state.model_provisioning == {}
    rn.stop_model_provisioning(api)


def test_manifests_agree_with_the_profiles_they_provision():
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, PROFILES
    from app.backend.summarization.nli_profiles import DEBERTA_NLI_PROFILE_KEY, NLI_PROFILES

    arctic, deberta = mf.MANIFESTS[mf.ARCTIC_S_TRACK], mf.MANIFESTS[mf.DEBERTA_TRACK]
    profile, nli = PROFILES[ARCTIC_S_PROFILE_KEY], NLI_PROFILES[DEBERTA_NLI_PROFILE_KEY]
    assert (arctic.repo_id, arctic.revision) == (profile.model_name, profile.revision)
    assert (arctic.contract["pooling"], arctic.contract["max_seq_length"]) == (profile.pooling, profile.max_seq_length)
    assert arctic.contract["dimension"] == profile.dimension
    assert (deberta.repo_id, deberta.revision) == (nli.model_name, nli.revision)
    assert {int(k): v for k, v in deberta.contract["id2label"].items()} == nli.id2label
    assert deberta.contract["model_type"] == nli.model_type
    assert deberta.contract["tokenizer_class_prefix"] == nli.tokenizer_class_prefix
    assert 360_000_000 < deberta.total_bytes < 390_000_000  # ~369 MB of weights plus tokenizer


def test_provisioning_import_loads_no_model_framework():
    code = (
        "import sys; import app.backend.model_provisioning as m; "
        "bad = [n for n in ('torch', 'transformers', 'sentence_transformers', 'sqlalchemy.orm') if n in sys.modules];"
        "print(bad)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=Path.cwd(), check=True)
    assert out.stdout.strip() == "[]"


def test_local_files_only_follows_verification(tmp_path, monkeypatch):
    hub = FakeHub(CONTENT)
    manifest = dataclasses.replace(manifest_for(CONTENT), track=mf.ARCTIC_S_TRACK)
    p = make(tmp_path, hub, manifest)
    monkeypatch.setattr(rn, "default_provisioner", lambda track: p)
    monkeypatch.setitem(rn.TRACK_FOR_MODEL, REPO, mf.ARCTIC_S_TRACK)
    assert rn.local_files_only_for(REPO) is False
    p.provision_once()
    assert rn.local_files_only_for(REPO) is True
    assert rn.local_files_only_for("cross-encoder/nli-MiniLM2-L6-H768") is False  # baselines untouched


def test_index_worker_runs_offline_once_provisioned(monkeypatch):
    from app.backend.embeddings import index_supervisor as sup

    seen: list[list[str]] = []

    class Proc:
        pid = 1

    monkeypatch.setattr(sup.subprocess, "Popen", lambda argv, **kw: seen.append(argv) or Proc())
    launcher = sup.SubprocessLauncher(sup.SupervisorConfig(db_url="sqlite:///x.sqlite"))
    monkeypatch.setattr(sup, "local_files_only_for", lambda name: False)
    launcher.launch("arctic-s", "t", 8)
    monkeypatch.setattr(sup, "local_files_only_for", lambda name: name == "Snowflake/snowflake-arctic-embed-s")
    launcher.launch("arctic-s", "t", 8)
    assert "--local-files-only" not in seen[0] and "--local-files-only" in seen[1]


def test_resolvers_use_offline_loading_only_for_provisioned_profiles(monkeypatch):
    from app.backend.api import dependencies as deps
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, PROFILES
    from app.backend.summarization.nli_profiles import NLI_PROFILES

    calls: dict[str, list] = {"nli": [], "support": [], "embed": []}

    class Runtime:
        def run(self, op):
            return None

    class Registry:
        def get_nli_runtime(self, **kw):
            calls["nli"].append(kw)
            return Runtime()

        def get_support_scorer(self, **kw):
            calls["support"].append(kw)
            return "baseline"

        def get_embedding_model(self, **kw):
            calls["embed"].append(kw)
            return "arctic"

    app = SimpleNamespace(state=SimpleNamespace(model_runtime_registry=Registry()))
    monkeypatch.setattr(deps, "local_files_only_for", lambda name: True)
    deps.resolve_support_scorer(app, nli_profile=NLI_PROFILES["deberta-v3-base"])
    deps.resolve_support_scorer(app, nli_profile=NLI_PROFILES["minilm2"])
    deps.resolve_profile_embedding_model(app, PROFILES[ARCTIC_S_PROFILE_KEY])
    assert calls["nli"][0]["local_files_only"] is True
    assert calls["support"][0]["local_files_only"] is False  # MiniLM2 path unchanged
    assert calls["embed"][0]["local_files_only"] is True


@pytest.mark.parametrize("track", [mf.ARCTIC_S_TRACK, mf.DEBERTA_TRACK])
def test_real_pinned_snapshot_verifies_offline_when_present(tmp_path, track):
    cache = pv.default_cache_dir()
    manifest = mf.MANIFESTS[track]

    def no_network(*_a):
        raise AssertionError("a present snapshot must not fetch")

    p = pv.Provisioner(manifest, cache_dir=cache, state_dir=tmp_path, fetcher=no_network)
    if p.status()["files_present"] != len(manifest.files):
        pytest.skip(f"pinned {track} snapshot not in the local Hub cache")
    assert p.provision_once()["state"] == pv.VERIFIED
