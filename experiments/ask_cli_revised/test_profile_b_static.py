"""Closed profile-B consumer boundaries, explicit routing and offline execution."""

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import parent_synthesis as legacy
from experiments.ask_cli_revised import parent_synthesis_audit as legacy_audit
from experiments.ask_cli_revised import parent_synthesis_render as legacy_render
from experiments.ask_cli_revised import profile_b_replay
from experiments.ask_cli_revised import test_layerc_integrity as h
from experiments.ask_cli_revised import test_profile_b_matrix as matrix
from experiments.ask_cli_revised.answer_plan import replay
from experiments.ask_cli_revised.test_layerc_static import FORBIDDEN as C_FORBIDDEN
from experiments.ask_cli_revised.test_producer_static_replay import FORBIDDEN, imports

BASE = Path(__file__).parent
IMPORTS = {
    "layerc_consumer": {
        "json",
        "dataclasses",
        "layerc_projection",
        "producer_authorization",
        "_layerc_common",
        "producer_authorization_store",
    },
    "claim_v2": {"_layerc_common"},
    "layerc_presentation": {"_layerc_common", "answer_plan"},
    "relation_unit_v2": {"_layerc_common", "claim_v2", "text"},
    "parent_synthesis_v2": {"_layerc_common"},
    "profile_b": {
        "layerc_pipeline",
        "claim_v2",
        "layerc_presentation",
        "parent_synthesis_v2",
        "relation_unit_v2",
        "layerc_consumer",
        "_layerc_common",
        "answer_plan",
    },
    "profile_b_replay": {
        "base64",
        "pathlib",
        "profile_b",
        "_layerc_common",
        "producer_authorization",
        "_producer_schema",
    },
    "answer_plan/plan_v5": {"_layerc_common", "claim_v2", "fresh_invocation"},
    "answer_plan/render_v5": {"_layerc_common"},
}


@pytest.mark.parametrize("name", sorted(IMPORTS))
def test_closed_consumer_imports_and_no_scientific_selection(name):
    root = ast.parse((BASE / (name + ".py")).read_text(encoding="utf-8"))
    assert set(imports(root)) <= IMPORTS[name]
    forbidden = (FORBIDDEN | C_FORBIDDEN | {"reproduce_accepted_v8"}) - {"getattr"}
    if name == "profile_b_replay":
        forbidden -= {"read_bytes", "write_text"}
    for n in ast.walk(root):
        if isinstance(n, ast.Call):
            call = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", None)
            assert call not in forbidden, (name, call)
        if isinstance(n, ast.Constant):
            assert n.value != "candidate_supports", name
        if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store):
            assert not isinstance(n.value, ast.Name) or n.value.id not in {
                "smap",
                "proof",
                "receipt",
                "candidate",
                "binding",
                "authored_contract",
                "projection",
            }, name


def test_default_and_legacy_route_never_activate_B(tmp_path):
    class LegacyEntered(Exception):
        pass

    for flags in (
        [],
        ["--allow-supported-noncurrent"],
        ["--layerc-profile", "v8-legacy-layerc-plan-v4-characterization", "--allow-supported-noncurrent"],
    ):
        with (
            patch.object(replay, "_load", side_effect=LegacyEntered),
            patch.object(profile_b_replay, "replay", side_effect=AssertionError("implicit B")),
        ):
            with pytest.raises(LegacyEntered):
                replay.main(["--out-dir", str(tmp_path), *flags])


def test_explicit_B_routes_without_legacy_read_or_issuer(tmp_path):
    with (
        patch.object(replay, "_load", side_effect=AssertionError("legacy read")),
        patch.object(profile_b_replay, "replay", return_value={}) as route,
    ):
        assert (
            replay.main(
                [
                    "--layerc-profile",
                    "v8-layerc-v2-plan-v5",
                    "--profile-b-input",
                    "snapshot.json",
                    "--out-dir",
                    str(tmp_path),
                ]
            )
            == 0
        )
        route.assert_called_once_with(Path("snapshot.json"), tmp_path)


@pytest.mark.parametrize(
    "flags",
    [
        ["--layerc-profile", "v8-layerc-v2-plan-v5"],
        ["--profile-b-input", "snapshot.json"],
        ["--allow-supported-noncurrent", "--profile-b-input", "snapshot.json"],
    ],
)
def test_no_ambiguous_activation(flags):
    with patch.object(replay, "_load", side_effect=AssertionError("read before reject")):
        with pytest.raises(ValueError):
            replay.main(flags)


@pytest.mark.parametrize("boundary", ["text", "prompt", "value", "passage", "realize", "render", "audit"])
def test_v2_rejected_at_legacy_flat_boundaries(boundary):
    claim = {"schema": "parent-claim-v2"}
    calls = {
        "text": lambda: legacy.authorized_claim_text(claim),
        "prompt": lambda: legacy.build_prompt([claim], "question"),
        "value": lambda: legacy.claim_value_reasons(claim, "text", [claim]),
        "passage": lambda: legacy.source_passage_reasons(claim, "text", {}),
        "realize": lambda: legacy.realize([claim], {}, supervisor=None, entail=None, question="question"),
        "render": lambda: legacy_render.literal_statement(claim),
        "audit": lambda: legacy_audit.audit_parent_synthesis({}, {}, {}, {"version": "parent-synthesis-v2"}),
    }
    with pytest.raises(ValueError, match="v2"):
        calls[boundary]()


def test_detached_consumers_do_not_call_scientific_machinery(monkeypatch):
    args = h.fixture()

    def denied(*a, **kw):
        raise AssertionError("consumer attempted scientific selection")

    for name in (
        "build_support_views",
        "common_assignments",
        "select_completion_proofs",
        "select_i1_proofs",
        "finalize_instance",
        "validate_witness_bundle",
    ):
        monkeypatch.setattr(h.h.cw, name, denied)
    monkeypatch.setattr(h.h.rw, "witness_instance", denied)
    monkeypatch.setattr(h.sm.cp, "classify_category_observation", denied)
    monkeypatch.setattr(h.h.sp, "default_support_policy", denied)
    assert matrix.consume(args)[0]["claims"]
