"""Public offline fresh execution, real mapper/proofs and reviewed input boundaries."""

import copy
import json
import pickle

import pytest

from experiments.ask_cli_revised import e2e, fresh_invocation, fresh_layerc, reviewed_ask, reviewed_ask_inputs
from experiments.ask_cli_revised import reporting_contract as rc
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import test_e2e_run as harness
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised._layerc_common import canonical
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions


def inputs(relational=False):
    request = build_request_contract("What was found about alpha?")
    cid = request_subquestions(request)[0]["obligations"][0]["field_id"]
    specs = {"outcome": se.new_role_spec("outcome", "reported result", "achieved_outcome_predicate")}
    if relational:
        specs["outcome"] = se.new_role_spec("outcome", "reported direction", "direction_or_sign_pattern")
        specs["measure"] = se.new_role_spec("measure", "named measure", "named_instrument_lexicon")
    req = se.new_requirement(
        "result-obligation",
        "relational" if relational else "atomic",
        specs,
        se.new_role_completion(required_roles=list(specs)),
        "exists",
    )
    science = {cid: se.frozen_view(se.new_contract(cid, [req]))}
    reporting = rc.single_question(request, science, requested_construct_terms=["alpha"])
    review = {
        "schema": "reviewed-ask-inputs-v1",
        "status": "reviewed",
        "reviewed_by": "OFFLINE TEST AUTHOR; not a production approval",
        "reviewed_at": "2026-10-11",
        "inputs": reviewed_ask_inputs.input_refs(request, science, reporting, {}),
    }
    return request, science, reporting, {}, review


def bind(values=None):
    return reviewed_ask_inputs.bind_reviewed_inputs(*(values or inputs()))


def run_public(monkeypatch, *, relational=False, recovery=False):
    values = inputs(relational)
    bound_inputs = bind(values)
    cid = next(iter(values[1]))
    quote = (
        "We found that the Amber Scale measures alpha and was positively associated with beta."
        if relational
        else "We found alpha increased."
    )
    row = harness.rec("s1", quote, chunk=11, origin="recovery" if recovery else "initial")
    row["quote"] = quote
    client = harness.ScriptedClient(r=harness.r_maps(cid))
    h = harness.Harness(
        topo.WAVE1["T0"],
        initial=[] if recovery else [row],
        recovery=[row] if recovery else [],
        clients={"shared": client},
    )
    bound = e2e.bind(h.profile, rt=h.rt, clients=h.clients, trace=h.trace, managed_chat=lambda config: client)
    maps = []
    real_consume = fresh_layerc.consume

    def consume(authority, smap, raw, authored, **kwargs):
        before = canonical([smap, authored, kwargs])
        result = real_consume(authority, smap, raw, authored, **kwargs)
        assert canonical([smap, authored, kwargs]) == before
        maps.append(copy.deepcopy(smap))
        return result

    try:
        with monkeypatch.context() as m:
            m.setattr(e2e, "_initial_pass", h._initial_pass)
            m.setattr(e2e, "_recover_round", h._recover_round)
            m.setattr(fresh_layerc, "consume", consume)
            m.setattr(e2e.sufficiency_freeze, "load_verified", lambda **kw: pytest.fail("fixture fallback"))
            result = reviewed_ask.run_reviewed_request(
                bound_inputs, rt=h.rt, profile=h.profile, trace=h.trace, guard=h.guard, bound=bound
            )
        assert result["sufficiency_map_final"] == maps[0]
        assert (h.trace.dir / "14_final_answer.md").read_text(encoding="utf-8") == result["selected_answer"]
        assert result["selected_answer"] == result["layerc_v2"]["render"]["layer1"]
        assert result["final_audit"]["output_valid"] and result["final_audit"]["selected_render_exact"]
        assert (
            json.loads((h.trace.dir / "15_v2_output.json").read_text())["combined_sha256"]
            == result["layerc_v2"]["combined_sha256"]
        )
        return result
    finally:
        h.close()


@pytest.mark.parametrize("relational,recovery", [(False, False), (False, True), (True, False), (True, True)])
def test_public_fresh_mapper_and_selected_output(monkeypatch, relational, recovery):
    result = run_public(monkeypatch, relational=relational, recovery=recovery)
    output = result["layerc_v2"]
    assert output["plan"]["nodes"][0]["state"] == "answered"
    assert output["claims"] and output["claim_evidence"]
    assert "alpha" in result["selected_answer"] and "[1]" in result["selected_answer"]
    assert output["plan"]["upstream_authority"]["kind"] == "trusted_fresh_invocation"
    assert "verified_producer_authorization_ref" not in output["plan"]
    assert output["invocation_provenance"]["sufficiency_identity"] == {
        "status": "supported_noncurrent",
        "version": se.SUFFICIENCY_SEMANTICS_V8,
    }
    assert "U1" in harness.stage_names(result)
    if recovery:
        assert "U2" in harness.stage_names(result)
    if relational:
        assert any(c["semantic_identity"]["family"] == "relational" for c in output["claims"])
        assert any(u["relation_witnessed"] for u in output["relation_units"].values())
        for receipt in output["claim_evidence"].values():
            assert receipt["citation"]


def test_fresh_current_v8(monkeypatch):
    with monkeypatch.context() as current:
        current.setattr(se, "SUFFICIENCY_SEMANTICS_VERSION", se.SUFFICIENCY_SEMANTICS_V8)
        result = run_public(current)
        assert result["layerc_v2"]["plan"]["sufficiency_identity"] == {
            "status": "current",
            "version": se.SUFFICIENCY_SEMANTICS_V8,
        }
    assert se.SUFFICIENCY_SEMANTICS_VERSION == se.SUFFICIENCY_SEMANTICS_V7


@pytest.mark.parametrize("index", range(4))
def test_review_mismatch_rejected(index):
    values = list(inputs())
    if index == 0:
        values[0]["original_question"] += " changed"
    elif index == 1:
        values[1]["s1-o1"]["requirements"][0]["source_wording_span"] = "changed"
    elif index == 2:
        values[2]["nodes"][0]["literal_text"] += " changed"
    else:
        values[3]["s1-o1"] = "R"
    with pytest.raises(ValueError):
        bind(values)


def test_snapshots_and_no_persisted_fresh_constructor():
    values = inputs()
    bound = bind(values)
    values[2]["nodes"][0]["literal_text"] = "changed caller object"
    assert bound.reporting["nodes"][0]["literal_text"] != "changed caller object"
    with pytest.raises(TypeError):
        bound.reporting["nodes"][0]["literal_text"] = "mutation"
    for cls in (fresh_invocation.TrustedFreshInvocation, reviewed_ask_inputs.ReviewedAskInputs):
        with pytest.raises(TypeError):
            cls()
    with pytest.raises(TypeError):
        pickle.dumps(bound)
    with pytest.raises(ValueError):
        fresh_layerc.consume({"schema": "trusted-fresh-invocation-v1"}, {}, b"{}", {}, recovery=[], search={})
    with pytest.raises(TypeError):
        reviewed_ask.run_reviewed_request(bound, smap={})


def test_handoff_rejects_substituted_science_and_authoring(monkeypatch):
    original = fresh_layerc.consume
    checked = []

    def inspect(authority, smap, raw, authored, **kwargs):
        for changed in ("map", "sealed", "authoring", "recovery"):
            m, b, a, kw = copy.deepcopy(smap), raw, copy.deepcopy(authored), copy.deepcopy(kwargs)
            if changed == "map":
                m["s1-o1"]["requirements"][0]["state"] = "substituted"
            elif changed == "sealed":
                b = raw + b" "
            elif changed == "authoring":
                a["overlay"]["nodes"][0]["literal_text"] = "different question"
            else:
                kw["recovery"] = {"substituted": True}
            with pytest.raises(ValueError):
                original(authority, m, b, a, **kw)
            checked.append(changed)
        with pytest.raises(TypeError):
            pickle.dumps(authority)
        return original(authority, smap, raw, authored, **kwargs)

    monkeypatch.setattr(fresh_layerc, "consume", inspect)
    run_public(monkeypatch)
    assert checked == ["map", "sealed", "authoring", "recovery"]


def test_runtime_authoring_mutation_cannot_reach_layerc(monkeypatch):
    mapper = e2e.sufficiency_diagnostic.compute_diagnostic_sufficiency_map

    def mutate(sealed, scientific, parent, **kwargs):
        output = mapper(sealed, scientific, parent, **kwargs)
        scientific["s1-o1"]["requirements"][0]["source_wording_span"] = "changed during execution"
        return output

    monkeypatch.setattr(e2e.sufficiency_diagnostic, "compute_diagnostic_sufficiency_map", mutate)
    with pytest.raises(ValueError, match="execution authoring mutated"):
        run_public(monkeypatch)
