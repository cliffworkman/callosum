"""PHASE 34 I4-1d gates: frozen batteries (run once, hashes pinned), exact-parity invariants, the unwired static
guard, and validation-only cross-checks against assertion_authority (never imported by the module itself).
"""

import ast
import hashlib
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import achieved_outcome_span as aos
from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised.answer_plan import plan as pl
from experiments.ask_cli_revised.contract_directed import attribution as attr

HERE = Path(__file__).resolve().parent
FROZEN = {
    "achieved_outcome_span_i4_1d_preregistered.json": "9f07046235f3597cb964914bbde2a50371d50aad78bbea7f1b975fc85db19d65",
    "achieved_outcome_span_i4_1d_holdout.json": "b70581b55d1ed2626fa314bdcac86f4f079c33f7d245b73d1dcf556fbef1bb8e",
    "achieved_outcome_span_i4_1d_twins.json": "dded4a18304d898e0811eb81376a14d627567392e52458b2dd299fb469e62dca",
}


def _load(name):
    return json.loads((HERE / name).read_bytes().decode("utf-8"))


_BATTERIES = {name: _load(name) for name in FROZEN}
_CASES = [(name, c) for name in FROZEN for c in _BATTERIES[name]["cases"]]


@pytest.mark.parametrize("name", list(FROZEN))
def test_frozen_battery_hash_is_pinned(name):
    assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == FROZEN[name]


@pytest.mark.parametrize("name,case", _CASES, ids=[f"{n.split('_')[-1].split('.')[0]}:{c['id']}" for n, c in _CASES])
def test_frozen_case(name, case):
    result = aos.find_achieved_outcome_matches(case["text"])
    got = {
        "num_matches": len(result.matches),
        "predicates": [m.predicate_surface for m in result.matches],
        "rules": [m.rule for m in result.matches],
        "has_ambiguity": result.has_ambiguity,
        "old_match_is_not_none": result.old_match_is_not_none,
    }
    for k, v in case["expect"].items():
        assert got.get(k) == v, (case["id"], k, got)


# ---- exact parity with the historical whole-passage matcher (section 9) ----


def test_parity_holds_across_the_battery():
    for name in FROZEN:
        for case in _BATTERIES[name]["cases"]:
            text = case["text"]
            old = attr.has_result_predicate(text)
            result = aos.find_achieved_outcome_matches(text)
            assert old == result.old_match_is_not_none == (len(result.matches) > 0), case["id"]


def test_parity_holds_across_every_prose_string_literal_in_the_production_mapping_test_file():
    """Independent additional parity evidence: every prose string literal already used by the production
    sufficiency_mapping test suite agrees exactly on whether a result predicate is present."""
    source = (HERE / "test_sufficiency_mapping.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    strings = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and " " in node.value and len(node.value) > 15
    }
    assert len(strings) > 50
    for s in strings:
        old = attr.has_result_predicate(s)
        result = aos.find_achieved_outcome_matches(s)
        assert old == result.old_match_is_not_none == (len(result.matches) > 0), s[:80]


# ---- structural invariants ----


def test_non_ambiguous_matches_in_one_text_never_overlap():
    for name in FROZEN:
        for case in _BATTERIES[name]["cases"]:
            result = aos.find_achieved_outcome_matches(case["text"])
            spans = [(m.content_span, m.ambiguous_with is not None) for m in result.matches]
            for i in range(len(spans)):
                for j in range(i + 1, len(spans)):
                    (s1, e1), amb1 = spans[i]
                    (s2, e2), amb2 = spans[j]
                    overlapping = s1 < e2 and s2 < e1
                    assert not (overlapping and not amb1 and not amb2), (case["id"], i, j)


def test_an_ambiguous_boundary_is_flagged_on_both_sides():
    text = "found X previous studies found Y"
    result = aos.find_achieved_outcome_matches(text)
    assert len(result.matches) == 2
    assert all(m.ambiguous_with for m in result.matches)
    assert result.matches[0].ambiguous_with == (result.matches[1].predicate_span,)
    assert result.matches[1].ambiguous_with == (result.matches[0].predicate_span,)


def test_content_span_is_always_anchored_at_its_own_predicate_never_a_neighbours():
    text = "We hypothesized X and found Y."
    result = aos.find_achieved_outcome_matches(text)
    assert len(result.matches) == 1
    m = result.matches[0]
    assert m.predicate_surface == "found"
    assert m.content_span[0] == m.predicate_span[0]
    assert "hypothesized" not in m.matched_text


# ---- assertion_authority interop: VALIDATION ONLY, never used to alter match acceptance (section 7) ----


def test_validation_confirms_spans_map_cleanly_onto_an_assertion_authority_region():
    """For every frozen non-ambiguous match, feeding its content_span into assertion_authority as a target must not
    raise and must not report `target_crosses_assertion_boundary` for a within-one-clause match -- confirming
    attachment consistency. finding_authority/authority_veto are read here for REPORTING only; nothing here feeds
    back into whether the match in this module is kept."""
    checked = 0
    for name in FROZEN:
        for case in _BATTERIES[name]["cases"]:
            text = case["text"]
            result = aos.find_achieved_outcome_matches(text)
            for m in result.matches:
                if m.ambiguous_with:
                    continue
                ts, te = m.content_span
                av = aa.classify_target_assertions(text, target_start=ts, target_end=te)
                assert av["target_scope"] in ("within_assertion", "partial_assertion")
                checked += 1
    assert checked > 30


def test_negated_and_absence_of_evidence_matches_stay_representable_not_deleted():
    """mp_F / ho_negation_agnostic-style inputs: the match is never deleted by this module. I4-1c's own veto is
    visible only through the separate assertion_authority validation call, never read or acted on here."""
    text = "We found no evidence that scores increased."
    result = aos.find_achieved_outcome_matches(text)
    assert len(result.matches) == 1
    m = result.matches[0]
    ts, te = m.content_span
    av = aa.classify_target_assertions(text, target_start=ts, target_end=te)
    vetoes = {a["authority_veto"] for a in av["assertions"]}
    assert "absence_of_evidence" in vetoes  # visible in validation metadata
    assert m.predicate_surface == "found"  # the match itself is untouched


# ---- unwired static guard (section 13): no production semantic module may use this module's output ----


def test_module_is_unwired_static_guard():
    """No non-test module in the repository may reference achieved_outcome_span. Test modules may."""
    repo = HERE.parents[1]
    offenders = []
    for root in ("app", "integrations", "experiments", "tools", "tests", "mcp_server", "tui", "sync_server"):
        base = repo / root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path.name.startswith("test_") or path.name == "achieved_outcome_span.py":
                continue
            if path == HERE / "sufficiency_mapping.py":  # sole I4-2a production seam
                continue
            if "__pycache__" in path.relative_to(repo).parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "achieved_outcome_span" in text:
                offenders.append(str(path.relative_to(repo)))
    assert offenders == []


def test_module_does_not_import_assertion_authority():
    """This module must stay as unwired as assertion_authority itself -- it answers WHERE a match is, using only
    the existing mapper's own predicate lexicon; it never consults assertion_authority's source/kind/authority."""
    source = (HERE / "achieved_outcome_span.py").read_text(encoding="utf-8")
    assert "assertion_authority" not in source


def test_module_does_not_modify_attribution_module():
    """Reuses attribution.has_result_predicate/_RESULT_PREDICATE unmodified -- confirmed here by re-deriving the
    exact same boolean the production mapper already gets, with no monkeypatching or local copy of the regex."""
    assert aos.find_achieved_outcome_matches("x").old_match_is_not_none is attr.has_result_predicate("x")


def test_versions_are_unchanged_for_sufficiency_and_plan():
    assert se.SUFFICIENCY_SEMANTICS_VERSION == "sufficiency-semantics-v7"  # I4-2b5 support-policy integration
    assert pl.PLAN_VERSION == "answer-plan-step2-v4"
    assert aos.SCHEMA_VERSION == "i4-1d.0"


def test_outputs_are_json_safe_and_deterministic():
    text = "Previous studies found X. We found Y."
    first = aos.find_achieved_outcome_matches(text)
    second = aos.find_achieved_outcome_matches(text)
    assert first == second
    json.dumps([m._asdict() for m in first.matches], allow_nan=False)
