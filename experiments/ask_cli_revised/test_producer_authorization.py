"""Exact D0 identities, accepted reproduction and pure authorization qualification."""

import copy
import json
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import producer_authorization as auth
from experiments.ask_cli_revised import producer_authorization_store as store
from experiments.ask_cli_revised import producer_replay as issuer
from experiments.ask_cli_revised._producer_inputs import RUN
from experiments.ask_cli_revised._producer_schema import canonical, plain, reference

BASE = Path(__file__).parent
EXPECTED = {
    "authored_inputs": "reviewed-authored-inputs-v1:sha256:2187272f3314817ca687fd1add912c4b178b68063c864d16024cc8db14cd8a83",
    "code_manifest": "producer-code-input-manifest-v1:sha256:3ea98ca41a74f6fdb6fc4e4391032ecb7c2b6b361eead954d560a02081670625",
    "event_inputs": "producer-event-input-manifest-v1:sha256:5ce389c0bd2baec24044131ddd464b309308a592c33a34032d8acf3f57d3ea3e",
    "nomination_inputs": "preserved-nomination-input-manifest-v1:sha256:4aac7557e6421be49255ffdeefd26508dd7b92856f88afdd291c4e6dc0a8710c",
    "profile": "qualified-producer-profile-v1:sha256:0c739b235dd983b77f3f9adfca22bebea90255f0f51f57f45cd7e699ef0bd2cd",
    "receipt": "producer-output-receipt-v1:sha256:a040ad7757ee792e9c0a7f0414bead5ce22ed5eb5d19e1bdc37931b4f0d4071d",
    "registry": "producer-authorization-registry-v1:sha256:3ca420b42e64046470738773b2affad9509ffbab4f0b0df166963fcc0308d0ef",
}
MAP_SHA = "e1c6d1027c96098dce96b7c86ee9259d1c50e379845c1d9bb3adeb62ba00b8cf"


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    output = tmp_path_factory.mktemp("producer-d1") / "reproduction"
    with (
        patch.object(socket.socket, "connect", side_effect=AssertionError("network")),
        patch.object(socket, "create_connection", side_effect=AssertionError("network")),
        patch.object(issuer.sm, "nominate_with_model", side_effect=AssertionError("fresh model")),
    ):
        result = issuer.reproduce_accepted_v8(output_dir=output)
    assert (output / "producer_output_receipt.json").read_bytes() == canonical(result.receipt)
    assert (output / "sufficiency_map.json").read_bytes() == canonical(result.smap)
    return result


def verify(real, **changes):
    kwargs = {
        "smap": real.smap,
        "sealed_bytes": real.input_bundle.files[RUN + "11_verified_ledger.json"],
        "authored_contract": real.authored_contract,
        "producer_receipt": real.receipt,
        "input_bundle": real.input_bundle,
    }
    kwargs.update(changes)
    if "trusted_registry" not in kwargs:
        kwargs["trusted_registry"] = store.load_trusted_producer_registry()
    return auth.verify_producer_authorization(**kwargs)


def test_all_preregistered_material_ids():
    registry = store.load_trusted_producer_registry()
    assert registry.registry_ref == EXPECTED["registry"]
    assert set(registry.materials) == set(EXPECTED.values()) - {EXPECTED["registry"]}
    assert len(registry.body["profiles"]) == len(registry.body["accepted_receipts"]) == 1
    for ref, body in registry.materials.items():
        assert reference(body) == ref
    # The committed design is an independent preregistration, not generated from implementation.
    report = (BASE / "PHASE34_I4_4D0_PRODUCER_AUTHORIZATION_DESIGN.md").read_text(encoding="utf-8")
    assert all(ref in report for ref in EXPECTED.values())


def test_exact_reproduction_and_A_L(real):
    result = verify(real)
    assert result.identities["map_canonical_sha256"] == MAP_SHA
    assert result.identities["receipt_ref"] == EXPECTED["receipt"]
    assert result == real.verified_authorization
    assert real.receipt["event_kind"] == "post_hoc_deterministic_reproduction"
    assert real.receipt["historical_receipt_existed"] is False
    assert len(real.input_bundle.nominations) == 32
    assert sum(len(row["bindings"]) for row in real.input_bundle.nominations) == 21
    assert len(real.input_bundle.replay_requests) == 33
    assert len(real.input_bundle.recovery_targets) == 48


def test_pure_verifier_detached_immutable_and_no_io(real):
    before = canonical([real.smap, real.receipt, real.authored_contract, plain(real.input_bundle.replay_requests)])
    registry = store.load_trusted_producer_registry()
    with (
        patch("builtins.open", side_effect=AssertionError("I/O")),
        patch.object(Path, "read_bytes", side_effect=AssertionError("I/O")),
        patch.object(issuer, "reproduce_accepted_v8", side_effect=AssertionError("producer")),
        patch.object(issuer.oc, "build_context_index", side_effect=AssertionError("context producer")),
    ):
        verified = verify(real, trusted_registry=registry)
    assert (
        canonical([real.smap, real.receipt, real.authored_contract, plain(real.input_bundle.replay_requests)]) == before
    )
    with pytest.raises(TypeError):
        verified.identities["bad"] = "bad"
    with pytest.raises(TypeError):
        verified.identities["rulesets"]["witness_semantics"] = "bad"
    with pytest.raises(TypeError):
        real.input_bundle.files["bad"] = b"bad"


def test_map_and_receipt_not_rewritten_by_verification(real):
    smap, receipt = copy.deepcopy(real.smap), copy.deepcopy(real.receipt)
    verify(real, smap=smap, producer_receipt=receipt)
    assert smap == real.smap and receipt == real.receipt
    assert json.loads(canonical(real.receipt)) == real.receipt
