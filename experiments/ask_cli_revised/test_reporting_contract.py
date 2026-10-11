"""Closed reporting structure and review binding; no scientific output can author nodes."""

import copy
import json

import pytest

from experiments.ask_cli_revised import reporting_contract as rc
from experiments.ask_cli_revised import reviewed_ask_inputs as ri
from experiments.ask_cli_revised._layerc_common import plain
from experiments.ask_cli_revised.test_reviewed_fresh import inputs


def forest():
    request, science, _, _, _ = inputs()
    template = next(iter(science.values()))
    science = {}
    for cid in ("main", "left", "leaf", "right", "other", "helper"):
        c = copy.deepcopy(template)
        c["child_id"] = cid
        c["requirements"][0]["id"] = cid + "-requirement"
        science[cid] = c
    pairs = [
        ("a", None, ["main"]),
        ("b", "a", ["left"]),
        ("c", "b", ["leaf"]),
        ("d", "a", ["right"]),
        ("e", None, ["other"]),
    ]
    reporting = {
        "schema": rc.SCHEMA,
        "request_ref": rc.request_ref(request),
        "nodes": [
            {"node_id": nid, "literal_text": "Question " + nid, "parent_id": parent, "owning_child_ids": children}
            for nid, parent, children in pairs
        ],
        "scientific_only_child_ids": ["helper"],
        "requested_construct_terms": [],
    }
    return request, science, reporting


def test_canonical_identity_and_exact_view():
    request, scientific, report = forest()
    ref = rc.validate(report, request, scientific)
    assert ref == rc.reporting_ref(dict(reversed(list(report.items()))))
    view = rc.consumer_view(report)
    assert set(view) == {"nodes", "requested_construct_terms"}
    assert [n["label"] for n in view["nodes"]] == ["a", "b", "c", "d", "e"]
    assert view["nodes"][2]["parent"] == "b"
    assert "helper" not in str(view)
    report["nodes"][0]["literal_text"] += " revised"
    assert ref != rc.reporting_ref(report)


def test_many_children_one_node():
    request, science, report = forest()
    report["nodes"] = [report["nodes"][0]]
    report["nodes"][0]["owning_child_ids"] = [c for c in science if c != "helper"]
    assert rc.validate(report, request, science)


@pytest.mark.parametrize(
    "case",
    [
        "extra",
        "schema",
        "request",
        "nodes_missing",
        "nodes_empty",
        "node_extra",
        "node_id_duplicate",
        "node_id_blank",
        "literal_missing",
        "literal_blank",
        "parent_missing",
        "parent_unknown",
        "self_cycle",
        "future_parent",
        "noncontiguous",
        "unknown_child",
        "duplicate_child",
        "duplicate_owner",
        "unowned",
        "hidden_owned",
        "hidden_unknown",
        "hidden_duplicate",
        "zero_owned",
        "missing_terms",
        "duplicate_terms",
        "blank_terms",
        "term_string",
        "child_identity",
        "requirement_collision",
        "empty_science",
    ],
)
def test_invalid_structure(case):
    request, science, report = forest()
    nodes = report["nodes"]
    if case == "extra":
        report["state"] = "answered"
    elif case == "schema":
        report["schema"] = "future"
    elif case == "request":
        report["request_ref"] += "bad"
    elif case == "nodes_missing":
        del report["nodes"]
    elif case == "nodes_empty":
        report["nodes"] = []
    elif case == "node_extra":
        nodes[0]["evidence"] = []
    elif case == "node_id_duplicate":
        nodes[1]["node_id"] = "a"
    elif case == "node_id_blank":
        nodes[0]["node_id"] = " "
    elif case == "literal_missing":
        del nodes[0]["literal_text"]
    elif case == "literal_blank":
        nodes[0]["literal_text"] = " "
    elif case == "parent_missing":
        del nodes[0]["parent_id"]
    elif case == "parent_unknown":
        nodes[0]["parent_id"] = "unknown"
    elif case == "self_cycle":
        nodes[0]["parent_id"] = "a"
    elif case == "future_parent":
        nodes[0]["parent_id"] = "b"
    elif case == "noncontiguous":
        report["nodes"] = [nodes[0], nodes[1], nodes[3], nodes[2], nodes[4]]
    elif case == "unknown_child":
        nodes[0]["owning_child_ids"] = ["absent"]
    elif case == "duplicate_child":
        nodes[0]["owning_child_ids"] *= 2
    elif case == "duplicate_owner":
        nodes[1]["owning_child_ids"] = ["main"]
    elif case == "unowned":
        report["scientific_only_child_ids"] = []
    elif case == "hidden_owned":
        report["scientific_only_child_ids"].append("main")
    elif case == "hidden_unknown":
        report["scientific_only_child_ids"].append("absent")
    elif case == "hidden_duplicate":
        report["scientific_only_child_ids"] *= 2
    elif case == "zero_owned":
        nodes[0]["owning_child_ids"] = []
    elif case == "missing_terms":
        del report["requested_construct_terms"]
    elif case == "duplicate_terms":
        report["requested_construct_terms"] = ["alpha", "alpha"]
    elif case == "blank_terms":
        report["requested_construct_terms"] = [""]
    elif case == "term_string":
        report["requested_construct_terms"] = "alpha"
    elif case == "child_identity":
        science["main"]["child_id"] = "other"
    elif case == "requirement_collision":
        science["left"]["requirements"][0]["id"] = "main-requirement"
    elif case == "empty_science":
        science = {}
    with pytest.raises(ValueError):
        rc.validate(report, request, science)


def test_explicit_loader_snapshots_and_no_defaults(tmp_path):
    values = inputs()
    names = ["request", "scientific", "reporting", "parent", "review"]
    paths = {}
    for name, value in zip(names, values, strict=True):
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps(value), encoding="utf-8")
        paths[name + "_path"] = p
    bound = ri.load_reviewed_inputs(**paths)
    paths["reporting_path"].write_text("{}")
    assert plain(bound.reporting) == values[2]
    ri.validate_bound(bound)
    with pytest.raises(TypeError):
        ri.load_reviewed_inputs()
    with pytest.raises(ValueError):
        ri.load_reviewed_inputs(**paths)


@pytest.mark.parametrize(
    "case", ["status", "reviewer", "date", "schema", "hash_only", "extra", "runtime_science", "fake_child"]
)
def test_no_invented_review(case):
    request, science, report, parent, review = inputs()
    if case == "status":
        review["status"] = "candidate"
    elif case == "reviewer":
        review["reviewed_by"] = ""
    elif case == "date":
        review["reviewed_at"] = ""
    elif case == "schema":
        review["schema"] = "fake"
    elif case == "hash_only":
        review = {"inputs": review["inputs"]}
    elif case == "extra":
        review["signature"] = "not authority"
    elif case == "runtime_science":
        science["s1-o1"]["requirements"][0]["instances"] = []
    elif case == "fake_child":
        science["root"] = science.pop("s1-o1")
        science["root"]["child_id"] = "root"
        report["nodes"][0]["owning_child_ids"] = ["root"]
        review["inputs"] = ri.input_refs(request, science, report, parent)
    with pytest.raises(ValueError):
        ri.bind_reviewed_inputs(request, science, report, parent, review)
