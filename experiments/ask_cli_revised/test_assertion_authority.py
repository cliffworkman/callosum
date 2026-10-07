"""PHASE 34 I4-1 gates: preregistered expectations, contract invariants, purity, and the unwired static guard."""

import ast
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised.answer_plan import plan as pl

HERE = Path(__file__).resolve().parent
PREREG = json.loads((HERE / "assertion_authority_preregistered.json").read_text(encoding="utf-8"))
_CASES = PREREG["cases"]


def _run(case):
    tgt = case["target"]
    text = case["text"]
    ctx = case.get("structural_context")
    if tgt.get("whole"):
        return None, aa.classify_assertion_authority(
            text, target_start=0, target_end=len(text), is_caption=case.get("is_caption", False), structural_context=ctx
        )
    out = aa.classify_surface(
        text,
        tgt["surface"],
        occurrence=tgt.get("occurrence"),
        is_caption=case.get("is_caption", False),
        structural_context=ctx,
    )
    return out, out["results"]


@pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
def test_preregistered_expectations(case):
    surface_out, res = _run(case)
    if "expect_surface" in case:
        for key, value in case["expect_surface"].items():
            assert surface_out[key] == value
    if "expect" in case:
        assert res is not None, f"no single result: {surface_out and surface_out['ambiguity']}"
        for key, value in case["expect"].items():
            assert res[key] == value, f"{case['id']}: {key}"


def test_preregistered_file_has_no_duplicate_ids():
    ids = [c["id"] for c in _CASES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "source,kind,caption,expected",
    [
        ("this_study", "result", False, "authoritative"),
        ("this_study", "result", True, "candidate"),
        ("this_study", "method_or_description", False, "candidate"),
        ("this_study", "aim_or_hypothesis", False, "candidate"),
        ("this_study", "interpretation", False, "candidate"),
        ("this_study", "unknown", False, "candidate"),
        ("prior_work", "result", False, "candidate"),
        ("prior_work", "result", True, "candidate"),
        ("unknown", "result", False, "candidate"),
        ("unknown", "unknown", False, "candidate"),
    ],
)
def test_finding_authority_truth_table(source, kind, caption, expected):
    assert aa.finding_authority(source, kind, caption) == expected


def test_finding_authority_rejects_unknown_axis_values():
    with pytest.raises(ValueError):
        aa.finding_authority("probably_this_study", "result")
    with pytest.raises(ValueError):
        aa.finding_authority("this_study", "confident_result")


def test_outputs_are_json_safe_and_deterministic():
    text = "This research confirmed earlier reports that X predicted Y, detected explicit biases, and described Z."
    first = aa.classify_surface(text, "explicit biases")["results"]
    second = aa.classify_surface(text, "explicit biases")["results"]
    assert first == second
    json.dumps(first, allow_nan=False)


def test_target_span_is_validated():
    with pytest.raises(ValueError):
        aa.classify_assertion_authority("We found X.", target_start=5, target_end=5)
    with pytest.raises(ValueError):
        aa.classify_assertion_authority("We found X.", target_start=0, target_end=999)


def test_repeated_surface_is_never_silently_resolved():
    text = "We tested whether X predicted Y and found that X predicted Y."
    out = aa.classify_surface(text, "X predicted Y")
    assert out["ambiguity"] == "repeated_target_occurrence"
    assert out["occurrence_count"] == 2
    assert out["results"] is None


def test_all_occurrences_are_classified_separately():
    text = "We tested whether X predicted Y and found that X predicted Y."
    results = aa.classify_all_occurrences(text, "X predicted Y")
    assert [r["assertion_kind"] for r in results] == ["aim_or_hypothesis", "result"]
    assert [r["finding_authority"] for r in results] == ["candidate", "authoritative"]


def test_owner_signal_is_validated_and_recorded_only_when_applied():
    with pytest.raises(ValueError):
        aa.classify_surface(
            "Participants expressed explicit bias.",
            "explicit bias",
            structural_context={"owner_signal": "participants"},
        )
    without = aa.classify_surface("Participants expressed explicit bias.", "explicit bias")["results"]
    assert without["structural_context_consumed"] is None
    assert without["assertion_source"] == "unknown"
    with_ctx = aa.classify_surface(
        "Participants expressed explicit bias.", "explicit bias", structural_context={"owner_signal": "this_study"}
    )["results"]
    assert with_ctx["structural_context_consumed"]["owner_signal"] == "this_study"
    assert with_ctx["finding_authority"] == "authoritative"


def test_owned_assertion_ignores_supplied_context():
    res = aa.classify_surface(
        "We found that X predicted Y.", "X predicted Y", structural_context={"owner_signal": "prior_work"}
    )["results"]
    assert res["assertion_source"] == "this_study"
    assert res["structural_context_consumed"] is None


def test_locator_uses_existing_fields_and_quote_hash():
    text = "We found that X predicted Y."
    res = aa.classify_surface(text, "X predicted Y", locator={"paper_id": 67, "evidence_anchor_chunk_id": 35068})[
        "results"
    ]
    assert res["input"]["locator"]["paper_id"] == 67
    assert res["input"]["locator"]["evidence_anchor_chunk_id"] == 35068
    assert len(res["input"]["locator"]["quote_sha256"]) == 64
    assert aa.durable_locator(67, 35068, text)["quote_sha256"] == res["input"]["locator"]["quote_sha256"]


def test_no_participant_or_population_noun_is_a_cue():
    tree = ast.parse((HERE / "assertion_authority.py").read_text(encoding="utf-8"))
    words = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            words.update(node.value.lower().split())
    for forbidden in ("participants", "patients", "students", "observers", "users", "subjects", "respondents"):
        assert forbidden not in words, forbidden


def test_module_is_pure_stdlib_only():
    tree = ast.parse((HERE / "assertion_authority.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "hashlib", "re", "collections"}, imported


def test_module_has_no_q_aib_vocabulary():
    source = (HERE / "assertion_authority.py").read_text(encoding="utf-8").lower()
    assert "q_aib" not in source and "aib" not in source


def test_semantics_and_plan_versions_are_unchanged():
    assert se.SUFFICIENCY_SEMANTICS_VERSION == "sufficiency-semantics-v4"
    assert pl.PLAN_VERSION == "answer-plan-step2-v4"


def test_classifier_is_unwired_static_guard():
    """No non-test module in the repository may import the I4-1 classifier. Test modules may."""
    repo = HERE.parents[1]
    offenders = []
    for root in ("app", "integrations", "experiments", "tools", "tests", "mcp_server", "tui", "sync_server"):
        base = repo / root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path.name.startswith("test_") or path.name == "assertion_authority.py":
                continue
            if "__pycache__" in path.relative_to(repo).parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "assertion_authority" in text:
                offenders.append(str(path.relative_to(repo)))
    assert offenders == []


def test_classifier_does_no_io(monkeypatch):
    import builtins

    def _forbidden(*args, **kwargs):
        raise AssertionError("I/O attempted by a pure classifier")

    monkeypatch.setattr(builtins, "open", _forbidden)
    res = aa.classify_surface("We found that X predicted Y.", "X predicted Y")["results"]
    assert res["assertion_source"] == "this_study"
