"""Recovery reuse shares only byte-identical work, keeps every requirement's own row, and is off by default.

No model, network or database: the worker backend, the verifier, retrieval and packet processing are stand-ins
that count how often they are reached.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.backend.summarization.generators import CandidateCitation
from app.backend.summarization.verification import LocalCitationVerifier, VerificationConfig
from experiments.ask_cli_revised import __main__ as cli
from experiments.ask_cli_revised import recovery_reuse as rr
from experiments.ask_cli_revised import timing
from experiments.ask_cli_revised.qwen import QwenTasks, _CallResult
from experiments.ask_cli_revised.trace import TraceWriter

SCHEMA = {"type": "object"}
WORKER = SimpleNamespace(model="qwen3.5:9b", think=False, base_options={"seed": 42, "temperature": 0})


class CountingQwen(QwenTasks):
    fail_next = False

    @property
    def backend_calls(self) -> list:
        return self.__dict__.setdefault("_backend_calls", [])

    def _call_backend(self, *, prompt, output_cap, json_schema=None):
        self.backend_calls.append(prompt)
        ok = not self.fail_next
        self.fail_next = False
        return _CallResult(
            raw_text=f"answer {len(self.backend_calls)}",
            provider_ok=ok,
            failure_reason=None if ok else "no_answer",
            elapsed_seconds=2.0,
            output_cap=output_cap,
            extra={"wall_seconds": 2.0},
        )


@pytest.fixture
def qwen():
    with tempfile.TemporaryDirectory() as tmp:
        yield CountingQwen(config=WORKER, trace=TraceWriter(Path(tmp)))


def call(q, prompt="p", cap=64, schema=SCHEMA):
    return q._call(prompt=prompt, output_cap=cap, json_schema=schema)


# ---- worker calls -------------------------------------------------------------------------------------------------------


def test_without_reuse_every_call_reaches_the_model(qwen):
    assert [call(qwen).raw_text, call(qwen).raw_text] == ["answer 1", "answer 2"]


def test_an_identical_call_is_answered_from_the_first_and_says_so(qwen):
    qwen.reuse = rr.RecoveryReuse()
    first, second = call(qwen), call(qwen)
    assert len(qwen.backend_calls) == 1
    assert second.raw_text == first.raw_text
    assert second.elapsed_seconds == 0.0 and second.extra["reused_identical_call"] is True
    assert "reused_identical_call" not in first.extra
    assert qwen.reuse.receipt()["calls_reused"] == 1
    assert qwen.reuse.receipt()["call_seconds_of_first_runs_reused"] == 2.0


@pytest.mark.parametrize(
    "change",
    [
        {"prompt": "the same passage, examined for a different requested item"},
        {"cap": 128},
        {"schema": {"type": "object", "required": ["claim"]}},
    ],
)
def test_any_difference_in_the_processing_inputs_is_a_different_call(qwen, change):
    qwen.reuse = rr.RecoveryReuse()
    call(qwen)
    call(qwen, **change)
    assert len(qwen.backend_calls) == 2


def test_a_different_model_thinking_setting_or_option_is_a_different_call():
    reuse = rr.RecoveryReuse()
    key = lambda cfg: reuse.call_key(config=cfg, prompt="p", output_cap=64, json_schema=SCHEMA)  # noqa: E731
    base = key(WORKER)
    assert key(SimpleNamespace(model="phi4:14b", think=False, base_options=WORKER.base_options)) != base
    assert key(SimpleNamespace(model=WORKER.model, think=True, base_options=WORKER.base_options)) != base
    assert key(SimpleNamespace(model=WORKER.model, think=False, base_options={"seed": 7, "temperature": 0})) != base
    assert key(SimpleNamespace(model=WORKER.model, think=False, base_options=dict(WORKER.base_options))) == base


def test_a_failed_call_is_not_stored_and_is_attempted_again(qwen):
    qwen.reuse = rr.RecoveryReuse()
    qwen.fail_next = True
    assert call(qwen).provider_ok is False
    assert call(qwen).provider_ok is True
    assert len(qwen.backend_calls) == 2


def test_a_reused_call_still_writes_its_own_trace_row(qwen):
    qwen.reuse = rr.RecoveryReuse()
    for _ in range(2):
        qwen.recovery_query(subquestion="which cultures?", obligation_note="a named culture")
    rows = [json.loads(x) for x in (qwen.trace.dir / "qwen_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 and len(qwen.backend_calls) == 1
    assert [bool(r.get("reused_identical_call")) for r in rows] == [False, True]
    assert rows[0]["prompt_text"] == rows[1]["prompt_text"]


# ---- source verification ------------------------------------------------------------------------------------------------


class CountingVerifier:
    config = VerificationConfig()

    def __init__(self):
        self.seen = []

    def verify_many(self, conn, *, items, source_chunks):
        self.seen.append([sentence for sentence, _ in items])
        return [f"result:{sentence}:{citation.chunk_id}:{citation.quote}" for sentence, citation in items]


def chunk(cid, text="passage text", version="v1"):
    return SimpleNamespace(chunk_id=cid, text=text, chunk_version=version)


def item(claim, cid=1, quote="q"):
    return (claim, CandidateCitation(chunk_id=cid, quote=quote))


def test_a_repeated_verification_is_reused_and_order_is_kept():
    inner, reuse = CountingVerifier(), rr.RecoveryReuse()
    verifier = rr.ReusingVerifier(inner, reuse)
    first = verifier.verify_many(None, items=[item("a"), item("b")], source_chunks=[chunk(1)])
    second = verifier.verify_many(None, items=[item("c"), item("a"), item("b"), item("d")], source_chunks=[chunk(1)])
    assert first == ["result:a:1:q", "result:b:1:q"]
    assert second == ["result:c:1:q", "result:a:1:q", "result:b:1:q", "result:d:1:q"]
    assert inner.seen == [["a", "b"], ["c", "d"]]
    assert (reuse.counts["verifications_run"], reuse.counts["verifications_reused"]) == (4, 2)
    assert verifier.config is inner.config  # everything else is the wrapped verifier's own


def test_a_different_claim_quote_chunk_or_chunk_text_is_verified_again():
    inner, reuse = CountingVerifier(), rr.RecoveryReuse()
    verifier = rr.ReusingVerifier(inner, reuse)
    verifier.verify_many(None, items=[item("a")], source_chunks=[chunk(1)])
    verifier.verify_many(None, items=[item("a", quote="another quote")], source_chunks=[chunk(1)])
    verifier.verify_many(None, items=[item("a", cid=2)], source_chunks=[chunk(2)])
    verifier.verify_many(None, items=[item("a")], source_chunks=[chunk(1, text="re-extracted text", version="v2")])
    assert reuse.counts["verifications_reused"] == 0 and len(inner.seen) == 4


def test_an_item_whose_chunk_is_not_in_the_pool_is_never_reused():
    inner, reuse = CountingVerifier(), rr.RecoveryReuse()
    verifier = rr.ReusingVerifier(inner, reuse)
    for _ in range(2):
        verifier.verify_many(None, items=[item("a", cid=9)], source_chunks=[chunk(1)])
    assert reuse.counts["verifications_reused"] == 0 and len(inner.seen) == 2


# ---- searches -----------------------------------------------------------------------------------------------------------


def _recover(monkeypatch, gaps, *, queries, reuse, plan=None, obligations=None):
    searched, processed = [], []
    monkeypatch.setattr(
        cli.retrieval, "within_paper_retrieve", lambda conn, **k: searched.append(k["subquestion_text"]) or ["h1", "h2"]
    )
    monkeypatch.setattr(cli, "_process_hits", lambda conn, **k: processed.append(k["subquestion"]["obligations"]) or 0)
    qwen = SimpleNamespace(recovery_query=lambda subquestion, obligation_note: queries[obligation_note])
    children = sorted({g["subquestion_id"] for g in gaps})
    subquestions = [
        {"subquestion_id": c, "text": f"text of {c}", "obligations": (obligations or {}).get(c, [{"field_id": c}])}
        for c in children
    ]
    log = cli._recover(
        None,
        rt=SimpleNamespace(model=None, vector_store=None, verifier=None),
        qwen=qwen,
        subquestions=subquestions,
        gaps=gaps,
        initial_nominations={c: [SimpleNamespace(paper_id=7, reasons=["kNN"])] for c in children},
        all_records=[],
        axis_cache={},
        trace=None,
        chunk_hits=[],
        context_growth=[],
        evidence_packets=[],
        propositions=[],
        verifications=[],
        plan=plan or {c: "DEEPEN" for c in children},
        map_claims=False,
        **({"reuse": reuse} if reuse is not None else {}),
    )
    return log, searched


def gap(child, note, target):
    return {"field_id": child, "subquestion_id": child, "note": note, "display": note, "_recovery_target_id": target}


def test_two_requirements_with_the_same_search_run_it_once_and_each_keeps_its_own_row(monkeypatch):
    gaps = [gap("c8", "a named trait", "c8::A"), gap("c8", "evidence relating the trait to the bias", "c8::B")]
    queries = {"a named trait": "traits and the bias", "evidence relating the trait to the bias": "traits and the bias"}
    log, searched = _recover(monkeypatch, gaps, queries=queries, reuse=rr.RecoveryReuse())
    assert searched == ["traits and the bias"]
    assert [row["gap"]["_recovery_target_id"] for row in log] == ["c8::A", "c8::B"]
    assert [row["gap"]["display"] for row in log] == ["a named trait", "evidence relating the trait to the bias"]
    assert "search_shared_with_target" not in log[0]
    assert log[1]["search_shared_with_target"] == "c8::A"
    assert log[1]["reason_code"] == "recovery_no_new_evidence" and log[1]["new_verified"] == 0
    assert log[1]["existing_hits"] == log[0]["existing_hits"] == 2
    assert log[1]["recovery_query"] == "traits and the bias"


def test_without_reuse_the_repeated_search_runs_as_before(monkeypatch):
    gaps = [gap("c8", "n1", "c8::A"), gap("c8", "n2", "c8::B")]
    log, searched = _recover(monkeypatch, gaps, queries={"n1": "q", "n2": "q"}, reuse=None)
    assert searched == ["q", "q"] and all("search_shared_with_target" not in row for row in log)


def test_the_same_query_for_another_child_is_a_different_search(monkeypatch):
    gaps = [gap("c10", "n", "c10::A"), gap("c11", "n", "c11::A")]
    _, searched = _recover(monkeypatch, gaps, queries={"n": "cross-cultural evidence"}, reuse=rr.RecoveryReuse())
    assert searched == ["cross-cultural evidence", "cross-cultural evidence"]


def test_a_different_query_for_the_same_child_is_a_different_search(monkeypatch):
    gaps = [gap("c11", "n1", "c11::A"), gap("c11", "n2", "c11::B")]
    _, searched = _recover(
        monkeypatch, gaps, queries={"n1": "which cultures", "n2": "how measured"}, reuse=rr.RecoveryReuse()
    )
    assert searched == ["which cultures", "how measured"]


def test_a_changed_retrieval_configuration_is_a_different_search():
    a, b = (
        rr.RecoveryReuse(retrieval_config={"within_paper_top_k": 8}),
        rr.RecoveryReuse(retrieval_config={"within_paper_top_k": 4}),
    )
    args = dict(
        child_id="c1", action="DEEPEN", query="q", paper_ids=[7], subquestion_text="t", obligations=[{"field_id": "c1"}]
    )
    assert a.search_key(**args) != b.search_key(**args)
    assert a.search_key(**args) != a.search_key(**{**args, "paper_ids": [7, 8]})
    assert a.search_key(**args) != a.search_key(**{**args, "obligations": [{"field_id": "c1", "note": "other"}]})


def test_only_a_deepen_search_is_ever_shared(monkeypatch):
    gaps = [gap("c1", "n1", "c1::A"), gap("c1", "n2", "c1::B")]
    monkeypatch.setattr(cli.discovery, "nominate_papers", lambda conn, **k: ([], None))
    reuse = rr.RecoveryReuse()
    log, _ = _recover(monkeypatch, gaps, queries={"n1": "q", "n2": "q"}, reuse=reuse, plan={"c1": "NOMINATE"})
    assert reuse.counts["searches_reused"] == 0 and all("search_shared_with_target" not in row for row in log)


# ---- timing -------------------------------------------------------------------------------------------------------------


def test_spans_cost_nothing_and_record_nothing_unless_collecting():
    with timing.span("x"):
        pass
    assert not timing.active()
    with timing.collect() as timings:
        with timing.span("x"):
            pass
        with timing.span("x"):
            pass
        assert timing.active()
    assert timings.summary()["x"]["count"] == 2 and not timing.active()


def test_the_timed_verifier_is_the_same_verifier_with_spans():
    scorer = SimpleNamespace(support_and_contradiction_many=lambda pairs: [(0.9, 0.01) for _ in pairs])
    plain = LocalCitationVerifier(model=None, vector_store=None, config=VerificationConfig(support_threshold=0.5), support_scorer=scorer)  # fmt: skip
    timed = timing.TimedVerifier.wrapping(plain)
    assert isinstance(timed, LocalCitationVerifier)
    assert (timed.model, timed.vector_store, timed.config, timed.support_scorer) == (None, None, plain.config, scorer)
    with timing.collect() as timings:
        assert timed._support_and_contradiction_many([("p", "h")]) == plain._support_and_contradiction_many(
            [("p", "h")]
        )
    assert timings.summary()["verify.nli"]["count"] == 1
    args = dict(retrieval_confidence=0.9, quote_confidence=1.0, support_confidence=0.52, contradiction_confidence=0.1)
    assert timed._status(**args) == plain._status(**args) == "verified"


# ---- wiring through run_topology ----------------------------------------------------------------------------------------


def _run_topology(tmp_path, **flags):
    import contextlib
    from unittest.mock import MagicMock, patch

    from experiments.ask_cli_revised import e2e
    from experiments.ask_cli_revised.test_e2e_run import INITIAL, NEW, ScriptedClient, add, r_maps

    shared = ScriptedClient(r=r_maps("s3-o1"))
    seen = {}

    def initial_pass(conn, *, rt, qwen, subquestions, sink, trace):
        for record in INITIAL:
            add(sink, dict(record, provenance=dict(record["provenance"])))

    def recover_round(conn, *, rt, qwen, subquestions, gaps, plan, sink, trace, **extra):
        seen.update(extra)
        for record in NEW:
            add(sink, dict(record, provenance=dict(record["provenance"])))
        return []

    rt = SimpleNamespace(
        engine=SimpleNamespace(connect=lambda: contextlib.nullcontext(MagicMock())),
        qwen_config="QWEN-CONFIG",
        close=lambda: None,
    )
    with patch.object(e2e, "_initial_pass", initial_pass), patch.object(e2e, "_recover_round", recover_round):
        manifest = e2e.run_topology(
            "T0",
            "lld",
            db_path=tmp_path / "library.sqlite",
            library_frozen=tmp_path / "library.frozen.json",
            out_dir=tmp_path / "out",
            git_root=tmp_path,
            git_state_fn=lambda root: {"sha": "abc123", "branch": "b", "dirty_paths": []},
            verify_library=lambda db, frozen: {"sha256": "same"},
            verify_contracts=lambda: None,
            runtime_factory=lambda db, **kwargs: rt,
            client_factory=lambda url: shared,
            managed_chat=lambda config: shared,
            **flags,
        )
    return manifest, seen


def test_by_default_a_run_gets_no_reuse_object_no_timing_file_and_no_new_manifest_key(tmp_path):
    manifest, seen = _run_topology(tmp_path)
    assert seen == {}
    assert "recovery_reuse" not in manifest and "timing" not in manifest
    assert not (tmp_path / "out" / "20_timing.json").exists()


def test_the_flags_reach_the_recovery_round_and_the_manifest(tmp_path):
    manifest, seen = _run_topology(tmp_path, recovery_reuse_enabled=True, timing_enabled=True)
    assert isinstance(seen["reuse"], rr.RecoveryReuse)
    assert seen["reuse"].retrieval_config  # the retrieval caps are part of every search identity
    assert manifest["recovery_reuse"]["searches_reused"] == 0
    assert isinstance(manifest["timing"], dict)
    assert (tmp_path / "out" / "20_timing.json").exists()
    assert manifest["technical_validity"] == {"valid": True, "issues": []}
