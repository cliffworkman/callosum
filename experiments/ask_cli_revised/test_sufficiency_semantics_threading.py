"""Phase 33 / I2-0: explicit sufficiency-semantics-version threading. ZERO semantic change.

- Explicit v3 reproduces the pre-I2-0 offline baseline exactly (digests of the canonical outputs, captured before the
  threading landed).
- Explicit v3 reaches every lower semantic entry point (spies), and every produced map is stamped with it.
- Omitting the version fails at the API boundary; unsupported versions fail closed.
- The top-level production drivers pass the current constant explicitly; lower semantic modules never select it.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised import relation_witness as rw
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_freeze as sf
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_recovery_targets as srt
from experiments.ask_cli_revised.answer_plan import relations as rel
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / ".local" / "e2e-runs" / "phase28-live-parent-synthesis-attempt2-20261004T014500Z" / "run"
LEDGER = RUN / "11_verified_ledger.json"
V3 = se.SUFFICIENCY_SEMANTICS_V3
HERE = Path(__file__).resolve().parent

# sha256 of each canonical output, captured on the unchanged tree (HEAD 3c06123f) before I2-0. Recorded here as test
# assertions only; no generated pin artifact is produced or refreshed.
PRE_I2_0_DIGESTS = {
    "map": "5277801dd99e67792d19190326de3af538df40c501c0c1f4c8b8ada7decb76ea",
    "targets": "36b214f732294ee067ac0bbbbceed7f662b04d3a735d4a2e40c67b7d80bd5e52",
    "stop_recovery": "c7aed9771b2363b9c2ae5ec213e501c0d9fa11c1192d103bda66d4ad077ced27",
    "claims": "b890f2f55fadd71496576c19b62bcb7ec2a7117f2abb108e769a27424b376813",
    "relation_units": "ba712e0b1a3b73e4b21becc8c8151da545678ac264b4b990ea935d50c999b379",
    "terminal_empty": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
}

THREADED_NAMES = {
    "compute_diagnostic_sufficiency_map",
    "map_any_requirement",
    "map_requirement",
    "map_paired_requirement",
    "map_cardinality_requirement",
    "_bind_role_candidates",
    "_fork_instances_over_role",
    "recompute_requirement",
    "recompute_instance",
    "compute_recovery_targets",
    "terminal_search_status",
    "stamp_map",
    "_incomplete_instance_targets",
    "_targets_for_instance",
    "_gate_status",
}
PRODUCTION_DRIVERS = [
    "e2e.py",
    "phase13_c4_recovery_experiment.py",
    "phase15_c4_semantic_consumption_experiment.py",
    "phase21_live_initial_model_assist_validation.py",
    "phase23_live_recovery_targeted_u2_remap_validation.py",
    "sufficiency_model_nomination_diagnostic.py",
    "sufficiency_recovery_targets_inventory.py",
]
LOWER_SEMANTIC_MODULES = [
    "sufficiency_mapping.py",
    "sufficiency_recovery_targets.py",
    "sufficiency_diagnostic.py",
]


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=1, default=str)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


needs_preserved_ledger = pytest.mark.skipif(not LEDGER.is_file(), reason="the preserved Attempt-2 ledger is absent")


def _preserved_inputs():
    sealed = json.loads(LEDGER.read_text(encoding="utf-8"))
    contracts = sf.load_verified()
    parent_of = hc.parent_of(hc.load_contract(BENCHMARK_QUESTION, pins=None))
    return sealed, contracts, parent_of


def _outputs_under_explicit_v3():
    sealed, contracts, parent_of = _preserved_inputs()
    mapped = sd.compute_diagnostic_sufficiency_map(sealed, contracts, parent_of, semantics_version=V3)
    targets = srt.compute_recovery_targets(mapped, parent_of, semantics_version=V3)
    stop = {}
    for contract_row in mapped.values():
        for req in contract_row["requirements"]:
            stop[req["id"]] = {
                "state": req["state"],
                "reason": req["reason"],
                "certified": se.compute_stop_search_certified(req),
                "recovery_needed": se.compute_recovery_needed(req, se.new_search_status(req["id"])),
                "recovery_needed_completed": se.compute_recovery_needed(
                    req, se.new_search_status(req["id"], scoped_search_completed_no_additional_support=True)
                ),
            }
    return {
        "map": mapped,
        "targets": targets,
        "stop_recovery": stop,
        "claims": psl.build_claim_ledger(mapped, sealed, parent_of),
        "relation_units": rel.relation_units(mapped, sealed, semantics_version=V3),
        "terminal_empty": srt.terminal_search_status(mapped, {}, semantics_version=V3),
    }


@needs_preserved_ledger
def test_explicit_v3_reproduces_the_pre_i2_0_baseline_byte_for_byte():
    outputs = _outputs_under_explicit_v3()
    for name, expected in PRE_I2_0_DIGESTS.items():
        assert _digest(_canon(outputs[name])) == expected, f"{name} drifted from the pre-I2-0 baseline"


@needs_preserved_ledger
def test_explicit_v3_reaches_every_lower_entry_point_and_stamps_the_map(monkeypatch):
    calls: dict[str, list] = {}

    def spy(name, fn):
        def wrapper(*args, **kwargs):
            calls.setdefault(name, []).append(kwargs.get("semantics_version", "<missing>"))
            return fn(*args, **kwargs)

        return wrapper

    watched = [
        (sm, "map_any_requirement"),
        (sm, "map_requirement"),
        (sm, "map_paired_requirement"),
        (sm, "map_cardinality_requirement"),
        (sm, "_bind_role_candidates"),
        (sm, "_fork_instances_over_role"),
        (se, "recompute_requirement"),
        (se, "recompute_instance"),
        (si, "stamp_map"),
        (rw, "attach_relation_witnesses"),
    ]
    for module, name in watched:
        monkeypatch.setattr(module, name, spy(name, getattr(module, name)))

    sealed, contracts, parent_of = _preserved_inputs()
    mapped = sd.compute_diagnostic_sufficiency_map(sealed, contracts, parent_of, semantics_version=V3)

    for _, name in watched:
        assert calls.get(name), f"{name} was never reached under explicit v3"
        assert set(calls[name]) == {V3}, f"{name} received {set(calls[name])!r}"
    assert all(contract[se.SEMANTICS_VERSION_KEY] == V3 for contract in mapped.values())


def test_omitting_the_version_fails_at_the_api_boundary():
    req = se.new_requirement("r", "atomic", {}, se.new_role_completion(), "exists")
    calls = [
        lambda: sd.compute_diagnostic_sufficiency_map({}, {}, {}),
        lambda: sm.map_any_requirement(req, []),
        lambda: sm.map_requirement(req, []),
        lambda: sm.map_cardinality_requirement(req, []),
        lambda: sm.map_paired_requirement(req, req, []),
        lambda: sm._bind_role_candidates({}, []),
        lambda: se.recompute_requirement(req),
        lambda: srt.compute_recovery_targets({}, {}),
        lambda: srt.terminal_search_status({}, {}),
        lambda: si.stamp_map({}),
    ]
    for call in calls:
        with pytest.raises(TypeError, match="semantics_version"):
            call()


@pytest.mark.parametrize("bad", ["sufficiency-semantics-v9", "", None, 3])
def test_unsupported_versions_fail_closed(bad):
    req = se.new_requirement("r", "atomic", {}, se.new_role_completion(), "exists")
    calls = [
        lambda: sd.compute_diagnostic_sufficiency_map({}, {}, {}, semantics_version=bad),
        lambda: sm.map_any_requirement(req, [], semantics_version=bad),
        lambda: sm.map_requirement(req, [], semantics_version=bad),
        lambda: sm.map_cardinality_requirement(req, [], semantics_version=bad),
        lambda: sm._bind_role_candidates({}, [], semantics_version=bad),
        lambda: se.recompute_requirement(req, semantics_version=bad),
        lambda: srt.compute_recovery_targets({}, {}, semantics_version=bad),
        lambda: srt.terminal_search_status({}, {}, semantics_version=bad),
        lambda: si.stamp_map({}, semantics_version=bad),
    ]
    for call in calls:
        with pytest.raises(ValueError, match="unsupported sufficiency semantics version"):
            call()


def test_readable_historical_versions_are_accepted_and_nothing_else_is():
    for version in (
        se.SUFFICIENCY_SEMANTICS_V1,
        se.SUFFICIENCY_SEMANTICS_V2,
        se.SUFFICIENCY_SEMANTICS_V3,
        se.SUFFICIENCY_SEMANTICS_V4,
        se.SUFFICIENCY_SEMANTICS_V5,
    ):
        assert se.require_supported_semantics_version(version) == version
    with pytest.raises(ValueError):
        se.require_supported_semantics_version("sufficiency-semantics-v999")


def test_stamp_map_stamps_exactly_the_version_it_is_given():
    stamped = si.stamp_map({"c1": {"requirements": []}}, semantics_version=V3)
    assert stamped["c1"][se.SEMANTICS_VERSION_KEY] == V3
    historical = si.stamp_map({"c1": {"requirements": []}}, semantics_version=se.SUFFICIENCY_SEMANTICS_V1)
    assert historical["c1"][se.SEMANTICS_VERSION_KEY] == se.SUFFICIENCY_SEMANTICS_V1


def _threaded_calls(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if name in THREADED_NAMES:
            yield name, node


@pytest.mark.parametrize("filename", PRODUCTION_DRIVERS)
def test_production_drivers_pass_the_current_constant_explicitly(filename):
    tree = ast.parse((HERE / filename).read_text(encoding="utf-8"))
    checked = 0
    for name, node in _threaded_calls(tree):
        keywords = {kw.arg: kw.value for kw in node.keywords}
        assert "semantics_version" in keywords, f"{filename}:{node.lineno} {name}() omits semantics_version"
        value = keywords["semantics_version"]
        assert isinstance(value, ast.Attribute) and value.attr == "SUFFICIENCY_SEMANTICS_VERSION", (
            f"{filename}:{node.lineno} {name}() must pass the current constant, not {ast.dump(value)[:80]}"
        )
        checked += 1
    if filename == "e2e.py":
        assert checked >= 1, "the main production driver must exercise the threaded entry points"


@pytest.mark.parametrize("filename", LOWER_SEMANTIC_MODULES)
def test_lower_semantic_modules_never_select_the_current_constant(filename):
    source = (HERE / filename).read_text(encoding="utf-8")
    assert not re.search(r"\bSUFFICIENCY_SEMANTICS_VERSION\b", source), (
        f"{filename} selects the current version by default; it must receive the version explicitly"
    )
