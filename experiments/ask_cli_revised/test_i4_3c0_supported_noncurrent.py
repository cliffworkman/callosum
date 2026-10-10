"""I4-3C0: explicit noncurrent identity, orthogonal opt-ins and exact authorization."""

import ast
import copy
import itertools
import json
from pathlib import Path

import pytest

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised import test_sufficiency_semantics_version as old
from experiments.ask_cli_revised.answer_plan import overlay as ov
from experiments.ask_cli_revised.answer_plan import replay

SENTINEL = "sufficiency-semantics-test-supported-noncurrent"
FLAGS = (
    "accept_historical_versioned",
    "accept_historical_unversioned",
    "accept_supported_noncurrent",
)
COMBINATIONS = list(itertools.product((False, True), repeat=3))


@pytest.fixture
def supported(monkeypatch):
    monkeypatch.setattr(
        se,
        "SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS",
        se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS | {SENTINEL},
    )


def stamped(version):
    return {"c": {se.SEMANTICS_VERSION_KEY: version}}


def identity(status, version):
    return {"status": status, "version": version}


@pytest.mark.parametrize("flags", COMBINATIONS)
@pytest.mark.parametrize("kind", ("current", "historical_versioned", "historical_unversioned", "supported_noncurrent"))
def test_all_dispositions_and_orthogonal_flags(supported, flags, kind):
    versions = {
        "current": se.SUFFICIENCY_SEMANTICS_VERSION,
        "historical_versioned": se.SUFFICIENCY_SEMANTICS_V1,
        "historical_unversioned": None,
        "supported_noncurrent": SENTINEL,
    }
    version = versions[kind]
    smap = {"c": {}} if version is None else stamped(version)
    allowed = (
        kind == "current"
        or flags[("historical_versioned", "historical_unversioned", "supported_noncurrent").index(kind)]
    )
    before = copy.deepcopy(smap)
    if allowed:
        assert si.read_map_identity(smap, **dict(zip(FLAGS, flags, strict=True))) == identity(kind, version)
    else:
        with pytest.raises(si.SemanticsIdentityError, match="not accepted"):
            si.read_map_identity(smap, **dict(zip(FLAGS, flags, strict=True)))
    assert smap == before


@pytest.mark.parametrize("flags", COMBINATIONS)
@pytest.mark.parametrize(
    "smap",
    [
        stamped("unknown"),
        {"a": {se.SEMANTICS_VERSION_KEY: se.SUFFICIENCY_SEMANTICS_VERSION}, "b": {se.SEMANTICS_VERSION_KEY: SENTINEL}},
        {"a": {se.SEMANTICS_VERSION_KEY: SENTINEL}, "b": {}},
        stamped(None),
        stamped(7),
        stamped(["version"]),
        {},
        {"c": None},
    ],
)
def test_invalid_maps_fail_in_every_mode(supported, flags, smap):
    with pytest.raises(si.SemanticsIdentityError):
        si.read_map_identity(smap, **dict(zip(FLAGS, flags, strict=True)))


@pytest.mark.parametrize("status", ("current", "historical_versioned", "supported_noncurrent"))
def test_versioned_application_uses_recorded_version(status):
    assert si.applied_semantics_version(identity(status, SENTINEL)) == SENTINEL
    with pytest.raises(KeyError):
        si.applied_semantics_version({"status": status})


def test_unversioned_and_invalid_application_contract():
    assert si.applied_semantics_version(identity("historical_unversioned", None)) == se.SUFFICIENCY_SEMANTICS_VERSION
    for value in ({}, identity("unknown", SENTINEL)):
        with pytest.raises(si.SemanticsIdentityError):
            si.applied_semantics_version(value)
    with pytest.raises(AttributeError):
        si.applied_semantics_version(None)


@pytest.mark.parametrize(
    "status,version",
    [
        ("current", se.SUFFICIENCY_SEMANTICS_VERSION),
        ("historical_versioned", se.SUFFICIENCY_SEMANTICS_V1),
        ("historical_unversioned", None),
        ("supported_noncurrent", SENTINEL),
    ],
)
def test_exact_authorization_binding(supported, status, version):
    smap = {"c": {}} if version is None else stamped(version)
    si.check_authorization_binding(identity(status, version), smap)
    for other in ("current", "historical_versioned", "historical_unversioned", "supported_noncurrent"):
        if other != status:
            with pytest.raises(si.SemanticsIdentityError, match="binds"):
                si.check_authorization_binding(identity(other, version), smap)
    with pytest.raises(si.SemanticsIdentityError, match="binds"):
        si.check_authorization_binding(identity(status, "wrong"), smap)


@pytest.mark.parametrize(
    "bound",
    [
        None,
        {},
        {"status": "current"},
        {"version": SENTINEL},
        {"status": "supported_noncurrent", "version": SENTINEL, "extra": True},
    ],
)
def test_malformed_authorization(supported, bound):
    with pytest.raises(si.SemanticsIdentityError, match="malformed"):
        si.check_authorization_binding(bound, stamped(SENTINEL))


@pytest.mark.parametrize(
    "smap",
    [
        stamped("unknown"),
        {"a": {se.SEMANTICS_VERSION_KEY: SENTINEL}, "b": {se.SEMANTICS_VERSION_KEY: se.SUFFICIENCY_SEMANTICS_VERSION}},
    ],
)
def test_invalid_actual_map_authorization(supported, smap):
    with pytest.raises(si.SemanticsIdentityError):
        si.check_authorization_binding(identity("supported_noncurrent", SENTINEL), smap)


def authorization(bound):
    body = {
        "bound_inputs": {
            "sufficiency_semantics": bound,
            "answer_containment_semantics": bound["version"],
            "answer_direction_semantics": bound["version"],
        }
    }
    return {**body, "authorization_sha256": ov.sha256_obj(body)}


def test_promotion_and_historical_lifecycle_requires_fresh_authorization(supported, monkeypatch):
    smap = si.stamp_map({"c": {}}, semantics_version=SENTINEL)
    original = json.dumps(smap, sort_keys=True)
    noncurrent = identity("supported_noncurrent", SENTINEL)
    receipt = authorization(noncurrent)
    assert si.read_map_identity(smap, accept_supported_noncurrent=True) == noncurrent
    replay.verify_replay_authorization(receipt, smap)
    with monkeypatch.context() as promotion:
        promotion.setattr(se, "SUFFICIENCY_SEMANTICS_VERSION", SENTINEL)
        # Current wins even if also enumerated historical.
        promotion.setattr(
            se, "HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS", se.HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS | {SENTINEL}
        )
        assert si.read_map_identity(smap) == identity("current", SENTINEL)
        with pytest.raises(si.SemanticsIdentityError, match="binds"):
            replay.verify_replay_authorization(receipt, smap)
        replay.verify_replay_authorization(authorization(identity("current", SENTINEL)), smap)
    monkeypatch.setattr(
        se, "HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS", se.HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS | {SENTINEL}
    )
    with pytest.raises(si.SemanticsIdentityError):
        si.read_map_identity(smap, accept_supported_noncurrent=True)
    assert si.read_map_identity(smap, accept_historical_versioned=True, accept_supported_noncurrent=True) == identity(
        "historical_versioned", SENTINEL
    )
    with pytest.raises(si.SemanticsIdentityError, match="binds"):
        replay.verify_replay_authorization(receipt, smap)
    replay.verify_replay_authorization(authorization(identity("historical_versioned", SENTINEL)), smap)
    assert json.dumps(smap, sort_keys=True) == original


def test_replay_authorization_digest_status_and_applied_version(supported):
    smap = stamped(SENTINEL)
    receipt = authorization(identity("supported_noncurrent", SENTINEL))
    replay.verify_replay_authorization(receipt, smap)
    forged = copy.deepcopy(receipt)
    forged["bound_inputs"]["sufficiency_semantics"]["status"] = "historical_versioned"
    with pytest.raises(si.SemanticsIdentityError, match="digest"):
        replay.verify_replay_authorization(forged, smap)
    forged["authorization_sha256"] = ov.sha256_obj({k: v for k, v in forged.items() if k != "authorization_sha256"})
    with pytest.raises(si.SemanticsIdentityError, match="binds"):
        replay.verify_replay_authorization(forged, smap)
    for key in ("answer_containment_semantics", "answer_direction_semantics"):
        forged = copy.deepcopy(receipt)
        forged["bound_inputs"][key] = se.SUFFICIENCY_SEMANTICS_VERSION
        forged["authorization_sha256"] = ov.sha256_obj({k: v for k, v in forged.items() if k != "authorization_sha256"})
        with pytest.raises(si.SemanticsIdentityError, match="implies"):
            replay.verify_replay_authorization(forged, smap)


@old._needs_preserved
def test_cli_explicit_opt_in_and_exact_version_transport(supported, monkeypatch, tmp_path):
    run = old._current_run_dir(tmp_path)
    path = run / "17_sufficiency_map.json"
    smap = json.loads(path.read_text(encoding="utf-8"))
    si.stamp_map(smap, semantics_version=SENTINEL)
    path.write_text(json.dumps(smap), encoding="utf-8")
    original_bytes = path.read_bytes()
    args = ["--run-dir", str(run), "--out-dir", str(tmp_path / "out")]
    for flags in ([], ["--allow-historical-versioned"], ["--allow-historical-unversioned-map"]):
        with pytest.raises(si.SemanticsIdentityError, match="supported_noncurrent"):
            replay.main(args + flags)
    # Sentinel has NO semantic implementation. This test-only downstream stand-in
    # checks exact version transport, then exercises the unchanged v7 plan/render path.
    build = replay.pl.build_plan
    received = []

    def stand_in(*positional, **kwargs):
        received.append((kwargs["containment_semantics"], kwargs["direction_semantics"]))
        assert received[-1] == (SENTINEL, SENTINEL)
        kwargs["containment_semantics"] = se.SUFFICIENCY_SEMANTICS_VERSION
        kwargs["direction_semantics"] = se.SUFFICIENCY_SEMANTICS_VERSION
        return build(*positional, **kwargs)

    monkeypatch.setattr(replay.pl, "build_plan", stand_in)
    assert replay.main(args + ["--allow-supported-noncurrent"]) == 0
    assert received == [(SENTINEL, SENTINEL)] * 2
    receipt = json.loads((tmp_path / "out/replay_decomposition_authorization.json").read_text(encoding="utf-8"))
    assert receipt["bound_inputs"]["sufficiency_semantics"] == identity("supported_noncurrent", SENTINEL)
    replay.verify_replay_authorization(receipt, smap)
    assert path.read_bytes() == original_bytes


def test_opt_in_call_sites_are_closed_and_explicit():
    root = Path(__file__).resolve().parents[2]
    found = {}
    for folder in ("experiments", "app", "integrations"):
        for path in (root / folder).rglob("*.py"):
            if path.name.startswith("test") or "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg == "accept_supported_noncurrent":
                            found.setdefault(path.relative_to(root).as_posix(), []).append(ast.unparse(kw.value))
    assert found == {
        "experiments/ask_cli_revised/sufficiency_identity.py": ["True"],
        "experiments/ask_cli_revised/answer_plan/replay.py": ["args.allow_supported_noncurrent"],
    }
    signature = __import__("inspect").signature(si.read_map_identity)
    assert all(signature.parameters[flag].default is False for flag in FLAGS)


def test_no_real_new_version_support():
    assert se.SUFFICIENCY_SEMANTICS_VERSION == "sufficiency-semantics-v7"
    assert SENTINEL not in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS
    assert "sufficiency-semantics-v8" not in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS
    assert not hasattr(se, "SUFFICIENCY_SEMANTICS_V8")
