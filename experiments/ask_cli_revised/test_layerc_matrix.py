"""Preregistered A-R coverage permissions; future display/facet results are fixtures, not activation."""

import copy

import pytest

from experiments.ask_cli_revised import test_layerc_integrity as h
from experiments.ask_cli_revised import test_layerc_projection as f
from experiments.ask_cli_revised._layerc_common import ProjectionIntegrityError

# Final display/facet states belong to I4-4D; C preserves authorized inputs plus required checks.
MATRIX = [
    ("A", "selected", True, True, "answered"),
    ("B", "display_restricted", True, True, "partial"),
    ("C", "category_alternative", True, True, "answered"),
    ("D", "foreign_category", True, False, "partial"),
    ("E", "text_only", True, False, "partial"),
    ("F", "missing_category", False, False, "reject_inconsistent"),
    ("G", "two_values_one_covered", True, True, "partial"),
    ("H", "two_observations_one_source", True, True, "answered"),
    ("I", "one_observation_two_words", True, False, "partial"),
    ("J", "two_sources", True, True, "answered"),
    ("K", "distinct_scopes", True, True, "scoped"),
    ("L", "excluded", False, False, "not_established"),
    ("M", "ambiguous", False, False, "not_established"),
    ("N", "legacy", True, True, "answered_or_display_restricted"),
    ("O", "unlocated", True, False, "partial"),
    ("P", "punctuation", True, True, "unchanged"),
    ("Q", "second_assertion", True, True, "no_added_coverage"),
    ("R", "link_only", True, True, "narrow_relation_only"),
]


@pytest.mark.parametrize("case,mode,established,display_input,future", MATRIX, ids=[x[0] for x in MATRIX])
def test_value_coverage_matrix(case, mode, established, display_input, future):
    assert future  # Preregistered handoff, never passed into the substrate as an input.
    if mode in ("category_alternative", "two_sources"):
        args = h.category(["Alpha increased.", "Alpha increased in another sample."])
        p = f.project(args).records
        r = next(iter(p["value_coverage"].values()))
        assert len(r["scientific_coverage_refs"]) == len(r["authorized_display_source_refs"]) == 2
    elif mode in ("foreign_category", "text_only", "one_observation_two_words"):
        args = h.category(["Beta increased and Alpha was measured."], terms=("Alpha", "Beta"))
        p = f.project(args).records
        for r in p["value_coverage"].values():
            for e in r["scientific_coverage_refs"]:
                obs = p["category_observations"][e["ref"]]
                assert obs["placement"] == r["placement"]
        # There is no permission to transplant Beta's record into Alpha's exact scope.
        alpha = next(i for i in h.instance(args)["category_observations"] if i["term"] == "Alpha")
        altered = copy.deepcopy(args)
        h.instance(altered)["category_observations"][0]["term"] = "Beta"
        with pytest.raises(ProjectionIntegrityError):
            f.project(altered)
        assert alpha["term"] == "Alpha"
    elif mode == "missing_category":
        args = h.category()
        h.instance(args)["role_bindings"]["category"]["state"] = "missing"
        with pytest.raises(ProjectionIntegrityError):
            f.project(args)
    elif mode == "two_values_one_covered":
        p = f.project(h.category(["Alpha increased; Beta was measured."], terms=("Alpha", "Beta"))).records
        paths = list(p["value_coverage"].values())
        assert any(r["scientific_coverage_refs"] for r in paths)
        assert any(not r["scientific_coverage_refs"] for r in paths)
    elif mode == "two_observations_one_source":
        p = f.project(h.category(["Alpha increased while Beta decreased."], terms=("Alpha", "Beta"))).records
        assert len(p["category_observations"]) == 2
        assert len({r["value_id"] for r in p["value_coverage"].values()}) == 2
        assert {
            s["proposition_id"] for r in p["value_coverage"].values() for s in r["authorized_display_source_refs"]
        } == {"P0"}
    elif mode == "distinct_scopes":
        a, b = f.project(h.category(requirement_id="A")).records, f.project(h.category(requirement_id="B")).records
        assert not set(a["semantic_values"]) & set(b["semantic_values"])
    elif mode in ("excluded", "ambiguous"):
        status = "policy" if mode == "excluded" else "ambiguous"
        c = h.h.candidate("P2", "Alpha increased.", status=status)
        p = f.project(h.fixture({"x": h.h.binding("x", [c])}, {"P2": h.h.prop("P2", "Alpha increased.")})).records
        assert not p["value_coverage"]
    elif mode == "unlocated":
        c = h.h.candidate("P2", "Alpha increased.", span=None, text="Alpha increased")
        p = f.project(h.fixture({"x": h.h.binding("x", [c])}, {"P2": h.h.prop("P2", "Alpha increased.")})).records
        r = next(iter(p["value_coverage"].values()))
        assert r["scientific_coverage_refs"] and not r["authorized_display_source_refs"]
    elif mode == "link_only":
        props = {"P1": h.h.prop("P1", "XYZ"), "P2": h.h.prop("P2", "XYZ")}
        args = h.fixture(
            {"a": h.h.legacy("a", "P1", "XYZ"), "b": h.h.legacy("b", "P2", "XYZ")},
            props,
            context={"attachment_pieces": ["XYZ"]},
            verifiers=["contract_directed_links"],
        )
        p = f.project(args).records
        assert next(iter(p["link_context_status"].values()))["status"] == "missing"
        assert not h.instance(args)["relation_witnessed"]
    elif mode in ("punctuation", "second_assertion"):
        quote = "Alpha increased." if mode == "punctuation" else "Alpha increased while Beta decreased."
        c = h.h.candidate("P2", quote, span=[0, 15])
        p = f.project(h.fixture({"x": h.h.binding("x", [c])}, {"P2": h.h.prop("P2", quote)})).records
        for envelope in p["display_envelopes"].values():
            assert envelope["display_span"][1] <= 16
    else:
        args = h.fixture({"x": h.h.legacy("x", "P2", "alpha")})
        p = f.project(args).records
        r = next(iter(p["value_coverage"].values()))
        assert r["scientific_goal_state"] == "established"
        assert r["authorized_display_source_refs"] and r["citation_source_refs"]
        assert r["presentation"]["finalization_required"]
        assert "display_state" not in r
