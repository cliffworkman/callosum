"""Inc 619: per-operation synthesis verifier resolution (automatic DeBERTa with MiniLM2 compatibility).

Every test uses a disposable library, per-profile fake scorers or a fake checkpoint factory, injected release gates and
provisioning state, and a simulated memory probe. Nothing downloads, nothing measures this machine, and the production
release gates stay unarmed (asserted below).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.backend.api.job_timing import stage_reporter
from app.backend.embeddings.resources import ResourceSnapshot
from app.backend.model_provisioning import DEBERTA_RELEASE_GATES, deberta_auto_provisioning_armed
from app.backend.model_runtime import ModelRuntimeRegistry
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import library_settings, summaries
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator
from app.backend.summarization.nli_profiles import BASELINE_NLI_PROFILE_KEY, DEBERTA_NLI_PROFILE_KEY, NLI_PROFILES
from app.backend.summarization.verification import NLIInferenceError, VerificationConfig
from app.backend.summarization.verifier_resolution import (
    DEBERTA_LOAD_AND_RUN_MB,
    NliPreference,
    memory_check,
    read_nli_preference,
    set_nli_user_preference,
)
from tests.api_helpers import _seed_summarization_library, _summarization_app

MINILM, DEBERTA = BASELINE_NLI_PROFILE_KEY, DEBERTA_NLI_PROFILE_KEY
CLAIM = "Facial anomalies influence social judgments."
ARMED = dict.fromkeys(DEBERTA_RELEASE_GATES, True)
PLENTY = ResourceSnapshot(16000, 8000, 26000, 9000, "test")
LOW = ResourceSnapshot(16000, 1500, 26000, 9000, "test")  # 1,500 free < 1,500 need + 800 reserve


class Scorer:
    """A fake NLI scorer for one profile: records every batch, returns fixed (support, contradiction) pairs."""

    def __init__(self, name: str, support: float = 0.95, contradiction: float | None = 0.01, fail: bool = False):
        self.model_name, self.support, self.contradiction, self.fail, self.calls = (
            name,
            support,
            contradiction,
            fail,
            [],
        )

    def score(self, *, sentence: str, passage: str) -> float:
        return self.support_and_contradiction_many([(passage, sentence)])[0][0]

    def support_and_contradiction_many(self, pairs):
        self.calls.append(len(pairs))
        if self.fail:
            raise NLIInferenceError(f"{self.model_name} inference failed (simulated out of memory)")
        return [(self.support, self.contradiction) for _ in pairs]


class Env:
    def __init__(self, db_url: str, *, gates=None, state="verified", required=True, probe=PLENTY, deberta=None):
        self.db_url = db_url
        self.seeded = _seed_summarization_library(db_url)
        generator = FakeSummaryGenerator(
            sentences=[
                CandidateSummarySentence(
                    text=CLAIM, citations=[CandidateCitation(chunk_id=self.seeded["facial_chunk_id"], quote=CLAIM)]
                )
            ]
        )
        self.app = _summarization_app(db_url, generator=generator)
        self.minilm, self.deberta = Scorer(MINILM), deberta or Scorer(DEBERTA)
        self.app.state.nli_support_scorers = {MINILM: self.minilm, DEBERTA: self.deberta}
        self.app.state.deberta_release_gates = gates
        self.state = state
        self.app.state.deberta_model_state = lambda: self.state
        self.app.state.deberta_checkpoint_required = required
        self.probe = probe
        self.app.state.memory_probe = lambda: self.probe
        self.client = TestClient(self.app)

    def ask(self) -> dict:
        started = self.client.post(
            "/summarize", json={"scope_type": "papers", "paper_ids": [self.seeded["facial_paper_id"]]}
        )
        assert started.status_code == 202, started.text
        return self.client.get(f"/summarize/{started.json()['job_id']}").json()

    def nli(self, payload: dict) -> dict:
        engine = make_engine(self.db_url)
        with engine.connect() as conn:
            ref = conn.execute(
                select(summaries.c.scope_ref_json).where(summaries.c.id == payload["summary_id"])
            ).scalar_one()
        engine.dispose()
        return ref["verification_nli"]

    def summary_count(self) -> int:
        engine = make_engine(self.db_url)
        with engine.connect() as conn:
            n = conn.execute(select(func.count()).select_from(summaries)).scalar_one()
        engine.dispose()
        return n

    def prefer(self, key: str | None) -> None:
        engine = make_engine(self.db_url)
        with engine.begin() as conn:
            set_nli_user_preference(conn, key)
        engine.dispose()


def test_production_gates_stay_unarmed_and_packaged_acceptance_pending() -> None:
    assert DEBERTA_RELEASE_GATES["operation_memory_guard"] is True  # implemented in inc 619
    assert DEBERTA_RELEASE_GATES["verifier_provenance_and_failure"] is True  # implemented in inc 619
    assert DEBERTA_RELEASE_GATES["packaged_runtime_acceptance"] is False  # not done; never represented as done
    assert deberta_auto_provisioning_armed() is False


# 1
def test_automatic_uses_deberta_when_qualified_present_verified_and_memory_safe(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED)
    payload = env.ask()
    assert payload["status"] == "done", payload
    assert env.deberta.calls and not env.minilm.calls  # one verifier for the whole operation
    nli = env.nli(payload)
    assert (nli["profile"], nli["preference"], nli["fallback_reason"]) == (DEBERTA, "automatic", None)
    assert nli["model_name"] == NLI_PROFILES[DEBERTA].model_name and nli["revision"] == NLI_PROFILES[DEBERTA].revision
    assert nli["memory_check"]["ok"] is True and nli["memory_check"]["need_mb"] == DEBERTA_LOAD_AND_RUN_MB


# 2
def test_release_gate_off_uses_minilm2_not_qualified(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=None)  # the shipped gates
    payload = env.ask()
    assert payload["status"] == "done" and env.minilm.calls and not env.deberta.calls
    assert env.nli(payload)["fallback_reason"] == "not_qualified"


# 3
@pytest.mark.parametrize("state", ["absent", "downloading", "waiting_for_network", "interrupted"])
def test_checkpoint_absent_or_downloading_uses_minilm2(temp_db_url: str, state: str) -> None:
    env = Env(temp_db_url, gates=ARMED, state=state)
    payload = env.ask()
    assert payload["status"] == "done" and not env.deberta.calls
    assert env.nli(payload)["fallback_reason"] == "not_provisioned"


# 4
@pytest.mark.parametrize("state", ["invalid", "present_unverified", "something_new"])
def test_invalid_or_unverified_checkpoint_uses_minilm2(temp_db_url: str, state: str) -> None:
    env = Env(temp_db_url, gates=ARMED, state=state)
    payload = env.ask()
    assert payload["status"] == "done" and not env.deberta.calls
    assert env.nli(payload)["fallback_reason"] == "not_verified"


def test_a_checkpoint_that_fails_its_contract_at_load_falls_back_before_scoring(temp_db_url: str) -> None:
    from tests.test_nli_profiles import _fake_cross_encoder

    env = Env(temp_db_url, gates=ARMED)
    env.app.state.nli_support_scorers = {MINILM: env.minilm}  # DeBERTa goes through the real load path
    env.app.state.support_scorer = None
    seen = []

    def factory(identity):
        seen.append(identity.local_files_only)
        return _fake_cross_encoder(id2label={0: "LABEL_0", 1: "LABEL_1", 2: "LABEL_2"})  # corrupt label contract

    env.app.state.model_runtime_registry = ModelRuntimeRegistry(cross_encoder_factory=factory)
    payload = env.ask()
    assert payload["status"] == "done" and env.minilm.calls
    assert env.nli(payload)["fallback_reason"] == "not_verified"
    assert seen == [True]  # 20: loaded offline only, never a Hub fetch


# 5
def test_insufficient_memory_uses_minilm2(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED, probe=LOW)
    payload = env.ask()
    assert payload["status"] == "done" and not env.deberta.calls
    nli = env.nli(payload)
    assert nli["fallback_reason"] == "insufficient_memory" and nli["memory_check"]["free_mb"] == 1500


def test_unmeasurable_memory_is_never_enough(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED)

    def broken():
        raise OSError("no measurement")

    env.app.state.memory_probe = broken
    payload = env.ask()
    assert payload["status"] == "done" and env.nli(payload)["fallback_reason"] == "memory_unmeasured"


def test_memory_check_uses_the_lower_of_physical_and_commit_and_a_smaller_need_when_resident() -> None:
    commit_starved = ResourceSnapshot(16000, 8000, 26000, 1000, "GlobalMemoryStatusEx")
    assert memory_check(lambda: commit_starved, resident=False).ok is False
    assert memory_check(lambda: commit_starved, resident=False).free_mb == 1000
    tight = ResourceSnapshot(16000, 1500, None, None, "/proc/meminfo")  # 1,500 free, 800 reserve
    assert memory_check(lambda: tight, resident=False).ok is False
    assert memory_check(lambda: tight, resident=True).ok is True  # already loaded: only inference headroom


# 6
def test_a_running_arctic_index_worker_is_reserved_for(temp_db_url: str) -> None:
    from app.backend.embeddings import index_runs
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, PROFILES

    probe = ResourceSnapshot(16000, 2800, 26000, 9000, "test")  # fits DeBERTa alone (2,300), not with +700 (3,000)
    env = Env(temp_db_url, gates=ARMED, probe=probe)
    assert env.ask()["status"] == "done" and env.deberta.calls
    engine = make_engine(temp_db_url)
    index_runs.upsert_requested(engine, PROFILES[ARCTIC_S_PROFILE_KEY], batch_size=8)
    index_runs.update_run(engine, ARCTIC_S_PROFILE_KEY, state="running", peak_worker_rss_mb=700)
    engine.dispose()
    env.deberta.calls.clear()
    payload = env.ask()
    assert payload["status"] == "done" and not env.deberta.calls
    nli = env.nli(payload)
    assert nli["fallback_reason"] == "insufficient_memory" and nli["memory_check"]["indexing_reserve_mb"] == 700


# 7
def test_explicit_minilm2_is_never_overridden(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED)
    assert env.client.put("/verification-nli-profiles/active", json={"key": MINILM}).status_code == 200
    payload = env.ask()
    assert payload["status"] == "done" and not env.deberta.calls
    nli = env.nli(payload)
    assert (nli["profile"], nli["preference"], nli["fallback_reason"]) == (MINILM, "user", "user_choice")


# 8
def test_explicit_deberta_unavailable_reports_and_never_substitutes(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED, state="absent")
    refused = env.client.put("/verification-nli-profiles/active", json={"key": DEBERTA})
    assert refused.status_code == 409  # selection is refused while the checkpoint is not verified
    env.prefer(DEBERTA)  # a choice made earlier, whose checkpoint has since gone
    before = env.summary_count()
    payload = env.ask()
    assert payload["status"] == "error" and "Choose Automatic or MiniLM2" in payload["detail"]
    assert not env.minilm.calls and not env.deberta.calls and env.summary_count() == before
    state = env.client.get("/verification-nli-profiles").json()
    assert state["preference"] == DEBERTA and state["synthesis_blocked"]
    env.state, env.probe = "verified", LOW  # verified but no memory: still refused, never swapped
    payload = env.ask()
    assert payload["status"] == "error" and "not enough free memory" in payload["detail"] and not env.minilm.calls


# 9
def test_return_to_automatic(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED)
    env.client.put("/verification-nli-profiles/active", json={"key": MINILM})
    state = env.client.put("/verification-nli-profiles/active", json={"key": "automatic"}).json()
    assert state["preference"] == "automatic" and state["active"] == DEBERTA and state["fallback_reason"] is None
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(library_settings)).scalar_one() == 0
        assert read_nli_preference(conn) == NliPreference(None)
    engine.dispose()
    assert env.nli(env.ask())["profile"] == DEBERTA


# 10
@pytest.mark.parametrize("key", [MINILM, DEBERTA])
def test_a_legacy_selection_is_kept_as_the_users_choice(temp_db_url: str, key: str) -> None:
    env = Env(temp_db_url, gates=ARMED)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:  # written by inc 608/609: a key with no source
        conn.execute(library_settings.insert().values(key="verification_nli_profile", value=key))
        assert read_nli_preference(conn) == NliPreference(key, legacy=True)
    engine.dispose()
    state = env.client.get("/verification-nli-profiles").json()
    assert state["preference"] == key and state["legacy_preference"] is True and state["active"] == key
    nli = env.nli(env.ask())
    assert nli["profile"] == key and nli["preference"] == "user"


# 11, 12, 13, 15
def test_failure_after_selection_fails_closed_without_substitution_then_the_next_operation_resolves(
    temp_db_url: str,
) -> None:
    env = Env(temp_db_url, gates=ARMED, deberta=Scorer(DEBERTA, fail=True))
    before = env.summary_count()
    payload = env.ask()
    assert payload["status"] == "error"
    assert payload["detail"].startswith("Citation verification failed, so no synthesis was saved.")  # 11
    assert env.deberta.calls and not env.minilm.calls  # 12: no MiniLM2 claim in the failed operation
    assert env.summary_count() == before  # 15: nothing partial saved
    env.deberta.fail = False  # 13: the next operation resolves again
    payload = env.ask()
    assert payload["status"] == "done" and env.nli(payload)["profile"] == DEBERTA and not env.minilm.calls
    env.probe = LOW  # and again: now memory is short, so this one is MiniLM2 with the reason
    payload = env.ask()
    assert env.nli(payload)["fallback_reason"] == "insufficient_memory" and env.minilm.calls


# 14, 21
def test_saved_provenance_identity_reason_and_unchanged_thresholds(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED, probe=LOW)
    payload = env.ask()
    nli = env.nli(payload)
    assert nli["model_name"] == NLI_PROFILES[MINILM].model_name and nli["revision"] == NLI_PROFILES[MINILM].revision
    assert nli["preferred_profile"] == DEBERTA and nli["thresholds_calibrated_on"] == NLI_PROFILES[MINILM].model_name
    assert (nli["support_threshold"], nli["contradiction_threshold"], nli["similarity_threshold"]) == (0.55, 0.55, 0.7)
    default = VerificationConfig()
    assert (default.support_threshold, default.contradiction_threshold, default.retrieval_threshold) == (
        0.55,
        0.55,
        0.7,
    )
    shown = env.client.get(f"/summaries/{payload['summary_id']}").json()["model_provenance"]["verification"]
    assert shown["fallback_reason"] == "insufficient_memory" and "not enough free memory" in shown["note"]
    assert shown["profile"] == MINILM and shown["cautious_contradictions"] is False  # never called DeBERTa-verified


# 16
def test_deberta_contradiction_uses_cautious_wording_and_keeps_the_machine_status(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED, deberta=Scorer(DEBERTA, support=0.1, contradiction=0.9))
    env.minilm.support, env.minilm.contradiction = 0.1, 0.9
    citation = env.ask()["sentences"][0]["citations"][0]
    assert citation["status"] == "contradicted"
    assert citation["status_note"] == (
        "The model flags a possible disagreement with the source. Review the cited passage."
    )
    assert citation["quote"]  # the quote stays visible
    env.prefer(MINILM)
    citation = env.ask()["sentences"][0]["citations"][0]
    assert citation["status"] == "contradicted" and citation["status_note"] is None  # MiniLM2 wording unchanged


# 17
def test_verification_eta_is_keyed_by_the_verifier_and_never_reuses_minilm2_durations() -> None:
    marks = []
    store = SimpleNamespace(mark_stage=lambda job_id, key, label, **kw: marks.append((key, kw["timing_key"])))
    for verifier in (MINILM, DEBERTA):
        report = stage_reporter(store, "job", "synthesis|gemini", verifier=verifier)
        report("generating_summary", "Generating", 3, False)
        report("verifying_citations", "Verifying", 21, False)
    (_, gen_minilm), (_, ver_minilm), (_, gen_deberta), (_, ver_deberta) = marks
    assert gen_minilm == gen_deberta == ver_minilm == "synthesis|gemini"  # MiniLM2 history and generation unchanged
    assert ver_deberta == "synthesis|gemini|nli-deberta-v3-base"  # fresh: indeterminate until it has receipts


# 18
def test_same_effective_model_behaves_identically_automatic_or_explicit(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=ARMED)
    automatic = env.ask()
    env.prefer(DEBERTA)
    explicit = env.ask()

    def strip(payload):
        return [
            [
                {k: c[k] for k in ("status", "support_confidence", "quote", "status_note", "chunk_id")}
                for c in s["citations"]
            ]
            for s in payload["sentences"]
        ]

    assert strip(automatic) == strip(explicit)
    assert env.nli(automatic)["profile"] == env.nli(explicit)["profile"] == DEBERTA
    assert (env.nli(automatic)["preference"], env.nli(explicit)["preference"]) == ("automatic", "user")


# 19
def test_stance_and_critical_read_keep_minilm2_when_deberta_is_automatic(temp_db_url: str) -> None:
    from app.backend.api.dependencies import resolve_stance_scorer
    from app.backend.summarization.verification import DEFAULT_NLI_MODEL

    env = Env(temp_db_url, gates=ARMED)
    env.ask()
    assert resolve_stance_scorer(env.app).model_name == DEFAULT_NLI_MODEL


# 20
def test_no_download_side_effects(temp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolution only reads the inc-615 provisioner's status; it never runs it, and DeBERTa loads offline only."""
    from app.backend.model_provisioning import runner

    def no_download(*args, **kwargs):
        raise AssertionError("inference must never start a model download")

    read = []
    status = SimpleNamespace(status=lambda: read.append(1) or {"state": "absent"})
    monkeypatch.setattr(runner, "default_provisioner", lambda track: status)
    monkeypatch.setattr(runner.ProvisioningRunner, "run", no_download)
    env = Env(temp_db_url, gates=ARMED)
    env.app.state.deberta_model_state = None  # the real status path
    payload = env.ask()
    assert payload["status"] == "done" and read and env.nli(payload)["fallback_reason"] == "not_provisioned"
    assert env.client.put("/verification-nli-profiles/active", json={"key": DEBERTA}).status_code == 409


# 22
def test_historical_provenance_stays_readable_and_is_not_rewritten(temp_db_url: str) -> None:
    env = Env(temp_db_url, gates=None)
    payload = env.ask()
    engine = make_engine(temp_db_url)
    old = {
        "profile": MINILM,
        "model_name": NLI_PROFILES[MINILM].model_name,
        "revision": "b95119ce",
        "embedding_fallback": False,
    }
    with engine.begin() as conn:
        ref = conn.execute(
            select(summaries.c.scope_ref_json).where(summaries.c.id == payload["summary_id"])
        ).scalar_one()
        ref = {**ref, "verification_nli": old}  # an inc-609 row: none of the inc-619 keys
        conn.execute(update(summaries).where(summaries.c.id == payload["summary_id"]).values(scope_ref_json=ref))
    engine.dispose()
    shown = env.client.get(f"/summaries/{payload['summary_id']}").json()
    verification = shown["model_provenance"]["verification"]
    assert verification["profile"] == MINILM
    for key in ("preference", "preferred_profile", "fallback_reason", "support_threshold", "note"):
        assert verification[key] is None  # unknown, not guessed
    assert verification["cautious_contradictions"] is False
    assert env.nli(payload) == old  # reading never rewrites the stored record
