"""Offline dispatch through real recovery orchestration and reviewed output accounting."""

import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from experiments.ask_cli_revised import e2e, recovery_routing, reviewed_ask, reviewed_ask_inputs
from experiments.ask_cli_revised import test_e2e_run as harness
from experiments.ask_cli_revised import test_reviewed_fresh as fresh
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.request_contract import request_subquestions


def test_authoritative_owners_do_not_depend_on_id_spelling():
    subquestions = [
        {"subquestion_id": "s1", "obligations": [{"field_id": "s1-o1"}, {"field_id": "another-child"}]},
        {"subquestion_id": "retrieval:opaque", "obligations": [{"field_id": "unrelated/name"}]},
        {"subquestion_id": "child-C", "obligations": [{"field_id": "child-C"}]},
    ]
    for child, sid in [
        ("s1-o1", "s1"),
        ("another-child", "s1"),
        ("unrelated/name", "retrieval:opaque"),
        ("child-C", "child-C"),
    ]:
        assert recovery_routing.subquestion_id_for_obligation(subquestions, child) == sid


@pytest.mark.parametrize(
    "subquestions,reason",
    [
        ([], "recovery_owner_missing"),
        ([{"subquestion_id": "s1", "obligations": [{"field_id": "other"}]}], "recovery_owner_missing"),
        (
            [{"subquestion_id": "s1", "obligations": [{"field_id": "child"}, {"field_id": "child"}]}],
            "recovery_owner_ambiguous",
        ),
        (
            [{"subquestion_id": sid, "obligations": [{"field_id": "child"}]} for sid in ("one", "two")],
            "recovery_owner_ambiguous",
        ),
        ([{"obligations": [{"field_id": "child"}]}], "recovery_owner_missing_subquestion_id"),
        (
            [
                {"subquestion_id": "same", "obligations": [{"field_id": "child"}]},
                {"subquestion_id": "same", "obligations": []},
            ],
            "recovery_owner_ambiguous_subquestion_id",
        ),
    ],
)
def test_invalid_ownership_fails_explicitly(subquestions, reason):
    with pytest.raises(ValueError, match=reason):
        recovery_routing.subquestion_id_for_obligation(subquestions, "child")


def test_hierarchical_request_owners_preserve_ids():
    from experiments.ask_cli_revised import hierarchy_contract as hc
    from experiments.ask_cli_revised.hierarchy_test_support import ARTIFACTS_PRESENT
    from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

    if not ARTIFACTS_PRESENT:
        pytest.skip("preserved hierarchy unavailable")
    subquestions = request_subquestions(hc.load_contract(BENCHMARK_QUESTION, pins=None))
    for sq in subquestions:
        for obligation in sq["obligations"]:
            assert (
                recovery_routing.subquestion_id_for_obligation(subquestions, obligation["field_id"])
                == sq["subquestion_id"]
            )


@pytest.mark.parametrize("outcome", ["found", "empty", "query_failed"])
def test_public_flat_target_reaches_real_recovery_and_status(monkeypatch, outcome):
    values = fresh.inputs()
    cid = "s1-o1"
    # Match the preserved live target's scientific identity without importing its artifacts.
    req = values[1][cid]["requirements"][0]
    req["id"] = "Q1-s1-o1"
    req["role_specs"] = {"finding": dict(req["role_specs"]["outcome"], role="finding")}
    req["role_completion"]["required_roles"] = ["finding"]
    values[4]["inputs"] = reviewed_ask_inputs.input_refs(*values[:4])
    bound_inputs = fresh.bind(values)
    client = harness.ScriptedClient(r=harness.r_maps(cid))
    h = harness.Harness(topo.WAVE1["T0"], clients={"shared": client})
    h.rt.model = object()
    h.rt.vector_store = object()
    bound = e2e.bind(h.profile, rt=h.rt, clients=h.clients, trace=h.trace, managed_chat=lambda _: client)
    query = Mock(return_value=None if outcome == "query_failed" else "neutral recovery query")
    bound.qwen.recovery_query = query
    retrieve = Mock(return_value=[SimpleNamespace()])
    nominate = Mock(return_value=([], []))
    dispatched = []

    def process(conn, **kwargs):
        # Only retrieval/extraction/verification workers are substituted. cli._recover,
        # target routing, status, mapping, sealing and Layer C all execute normally.
        dispatched.append(copy.deepcopy(kwargs["subquestion"]))
        # Let generic LEGACY's deepen + nominate find nothing; only the third
        # extraction dispatch (the scientific target's deepen) contributes evidence.
        if outcome == "found" and len(dispatched) == 3:
            quote = "We found alpha increased."
            row = harness.rec("s1", quote, chunk=11, origin="recovery")
            row["quote"] = quote
            kwargs["all_records"].append(row)
            kwargs["evidence_packets"].append(
                {"paper_id": 7, "candidate_spans": [{"chunk_id": 11, "span_id": "e1", "text": quote}]}
            )

    try:
        monkeypatch.setattr(e2e, "_initial_pass", h._initial_pass)
        monkeypatch.setattr(e2e.cli.retrieval, "within_paper_retrieve", retrieve)
        monkeypatch.setattr(e2e.cli.discovery, "nominate_papers", nominate)
        monkeypatch.setattr(e2e.cli, "_process_hits", process)
        result = reviewed_ask.run_reviewed_request(
            bound_inputs,
            rt=h.rt,
            profile=h.profile,
            trace=h.trace,
            guard=h.guard,
            bound=bound,
            sufficiency_recovery=True,
        )
        targets = result["sufficiency_recovery_targets_initial"]
        assert set(targets) == {"s1-o1::2dc69aed8aff6365"}
        target_id = next(iter(targets))
        target_before = copy.deepcopy(targets[target_id])
        rows = result["recovery_log"]
        structured = [r for r in rows if r["gap"].get("_recovery_target_id") == target_id]
        generic = [r for r in rows if "_recovery_target_id" not in r["gap"]]
        assert len(structured) == len(generic) == 1
        gap = structured[0]["gap"]
        assert gap["field_id"] == cid and gap["subquestion_id"] == "s1"
        assert gap["_recovery_target_id"] == target_before["target_id"]
        assert targets[target_id] == target_before and target_before["search_child_id"] == cid
        assert query.call_count == 2  # generic and scoped attempts, not a substituted recovery round
        assert all(c.kwargs["subquestion"] == request_subquestions(values[0])[0]["text"] for c in query.call_args_list)
        state = result["scoped_search_round"]["Q1-s1-o1"]["target_states"][target_id]
        if outcome == "query_failed":
            assert state == {"state": "not_completed", "reason_code": "recovery_query_no_answer"}
            retrieve.assert_not_called()
            assert not dispatched
        else:
            assert state["state"] == "completed"
            assert retrieve.called and all(c.kwargs["subquestion_id"] == "s1" for c in retrieve.call_args_list)
            assert all(sq["obligations"][0]["field_id"] == cid for sq in dispatched)
            assert sum(r["new_verified"] for r in rows) == (1 if outcome == "found" else 0)
            if outcome == "empty":
                assert state["reason_code"] == "recovery_no_new_evidence"
            else:
                assert structured[0]["new_verified"] == 1
                assert state["reason_code"] == "recovery_added_evidence"
        assert result["final_audit"]["selected_render_exact"]
    finally:
        h.close()


@pytest.mark.parametrize("bad_owner", ["missing", "ambiguous"])
def test_dispatch_refuses_invalid_target_ownership_before_recovery(monkeypatch, bad_owner):
    real = e2e.sufficiency_recovery_targets.compute_recovery_targets
    real_subquestions = e2e.request_subquestions

    def targets(*args, **kwargs):
        result = real(*args, **kwargs)
        if bad_owner == "missing":
            for target in result.values():
                target["search_child_id"] = "no declared owner"
        return result

    def subquestions(request):
        rows = real_subquestions(request)
        if bad_owner == "ambiguous":
            rows[0]["obligations"].append(copy.deepcopy(rows[0]["obligations"][0]))
        return rows

    recovery = Mock(side_effect=AssertionError("must fail before dispatch"))
    monkeypatch.setattr(e2e.sufficiency_recovery_targets, "compute_recovery_targets", targets)
    monkeypatch.setattr(e2e, "request_subquestions", subquestions)
    monkeypatch.setattr(e2e, "_recover_round", recovery)
    with pytest.raises(ValueError, match="recovery_owner_" + bad_owner):
        fresh.run_public(monkeypatch, no_evidence=True, sufficiency_recovery=True)
    recovery.assert_not_called()
