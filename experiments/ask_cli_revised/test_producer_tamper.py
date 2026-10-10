"""A-R substitution controls and closed trust-root/lifecycle negatives."""

import copy
from dataclasses import replace

import pytest

from experiments.ask_cli_revised import producer_authorization as auth
from experiments.ask_cli_revised import producer_authorization_store as store
from experiments.ask_cli_revised import test_producer_authorization as shared
from experiments.ask_cli_revised._producer_schema import (
    _LOADER_TOKEN,
    _trusted_registry,
    canonical,
    decode,
    digest,
    plain,
    reference,
    validate_material,
)
from experiments.ask_cli_revised.test_producer_authorization import EXPECTED, verify

real = shared.real


def trusted_test_registry(*, lifecycle="active", additive=False):
    """TEST ONLY; no caller/runtime entry point accepts these injection parameters."""
    original = store.load_trusted_producer_registry()
    body, materials = plain(original.body), plain(original.materials)
    entry = body["profiles"][EXPECTED["profile"]]
    entry.update(lifecycle=lifecycle, issue=lifecycle == "active", consume=lifecycle != "revoked")
    if additive:
        extra = copy.deepcopy(materials[EXPECTED["profile"]])
        extra["producer_id"] = "another-explicit-test-profile"
        ref = reference(extra)
        materials[ref] = extra
        body["profiles"][ref] = {
            "producer_id": extra["producer_id"],
            "lifecycle": "retired",
            "issue": False,
            "consume": True,
        }
    return _trusted_registry(body, materials, _LOADER_TOKEN)


@pytest.mark.parametrize("case", ["B", "C", "D", "I", "J", "K", "N", "O", "P", "Q", "new_event"])
def test_rehashed_unenrolled_or_incompatible_receipts_fail(real, case):
    receipt = copy.deepcopy(real.receipt)
    smap = copy.deepcopy(real.smap)
    if case == "B":
        receipt["producer_id"] = "unknown"
    elif case in ("C", "O"):
        profile = plain(store.load_trusted_producer_registry().materials[EXPECTED["profile"]])
        profile["implementation_id"] = "caller-self-authored"
        receipt["profile_ref"] = reference(profile)
    elif case == "D":
        smap["c1"]["requirements"][0]["state"] = "caller-changed"
        receipt["map_canonical_sha256"] = digest(smap)
    elif case in ("I", "K"):
        receipt["sufficiency_identity"]["status"] = "current"
    elif case == "J":
        receipt["sufficiency_identity"]["version"] = "sufficiency-semantics-v7"
    elif case == "N":
        receipt = None
    elif case == "P":
        receipt = {"schema": "downstream-output-authorization", "upstream": receipt, "digest": digest(receipt)}
    elif case == "Q":
        receipt["producer_code_manifest_ref"] = "producer-code-input-manifest-v1:sha256:" + "0" * 64
    else:
        receipt["event_key"] = "new-self-consistent-event"
    # Even a canonically serialized new hash is not enrollment.
    if receipt is not None:
        assert digest(receipt) == digest(decode(canonical(receipt)))
    with pytest.raises(auth.ProducerAuthorizationError):
        verify(real, smap=smap, producer_receipt=receipt)


@pytest.mark.parametrize("case", ["D", "E", "F", "G", "H", "context", "recovery", "sealed_index"])
def test_actual_artifact_substitution_fails_even_with_original_enrolled_receipt(real, case):
    changes = {}
    if case == "D":
        smap = copy.deepcopy(real.smap)
        smap["c1"]["requirements"][0]["state"] = "caller-changed"
        changes["smap"] = smap
    elif case in ("E", "sealed_index"):
        ledger = decode(real.input_bundle.files["preserved-run/11_verified_ledger.json"])
        ledger["verified_propositions"][0]["quote"] += " altered"
        changes["sealed_bytes"] = canonical(ledger)
    elif case in ("F", "G"):
        authored = copy.deepcopy(real.authored_contract)
        if case == "F":
            roles = authored["requirements"]["c1"][0]["role_specs"]
            roles[sorted(roles)[0]]["category_description"] = "forged"
        else:
            authored["overlay"]["status"] = "caller-confirmed"
        changes["authored_contract"] = authored
    else:
        field = {"H": "nominations", "context": "ownership_context", "recovery": "recovery_targets"}[case]
        data = plain(getattr(real.input_bundle, field))
        if case == "H":
            data[0]["request_context"] = "forged-slot"
        elif case == "context":
            data["manifest_sha256"] = "0" * 64
        else:
            data.pop(sorted(data)[0])
        changes["input_bundle"] = replace(real.input_bundle, **{field: data})
    with pytest.raises(auth.ProducerAuthorizationError):
        verify(real, **changes)


@pytest.mark.parametrize(
    "path",
    [
        "preserved-run/18_sufficiency_model_assist.json",
        "preserved-run/qwen_calls.jsonl",
        "preserved-run/17_sufficiency_map.json",
        "hierarchy-input/assembled",
        "experiments/ask_cli_revised/witness_i4_3c_replay_baseline.json",
        "experiments/ask_cli_revised/sufficiency_contract.aib_hier_v9.review.json",
    ],
)
def test_byte_substitution_cannot_be_blessed(real, path):
    files = dict(real.input_bundle.files)
    files[path] += b" "
    with pytest.raises(auth.ProducerAuthorizationError, match="input bytes"):
        verify(real, input_bundle=replace(real.input_bundle, files=files))


def test_forged_request_fingerprint(real):
    requests = plain(real.input_bundle.replay_requests)
    requests[0]["request_fingerprint"] = "0" * 64
    with pytest.raises(auth.ProducerAuthorizationError, match="fingerprint"):
        verify(real, input_bundle=replace(real.input_bundle, replay_requests=requests))


@pytest.mark.parametrize("registry", [{}, {"profiles": "*"}, None])
def test_caller_registry_is_not_trusted(real, registry):
    with pytest.raises(auth.ProducerAuthorizationError, match="trusted loader"):
        verify(real, trusted_registry=registry)


@pytest.mark.parametrize("state,allowed", [("active", True), ("retired", True), ("revoked", False)])
def test_R_consumption_after_registry_update(real, state, allowed):
    registry = trusted_test_registry(lifecycle=state, additive=True)
    if allowed:
        result = verify(real, trusted_registry=registry)
        assert result.identities["receipt_ref"] == EXPECTED["receipt"]
        assert result.identities["registry_ref"] != EXPECTED["registry"]
    else:
        with pytest.raises(auth.ProducerAuthorizationError, match="revoked"):
            verify(real, trusted_registry=registry)


@pytest.mark.parametrize("state", ["retired", "revoked"])
def test_retired_and_revoked_cannot_issue(real, state):
    with pytest.raises(auth.ProducerAuthorizationError):
        auth.resolve_authority(trusted_test_registry(lifecycle=state), real.receipt, issuance=True)


@pytest.mark.parametrize(
    "change",
    [
        {"lifecycle": "latest"},
        {"issue": False},
        {"consume": False},
        {"issue": 1},
    ],
)
def test_lifecycle_unknown_or_contradictory_fails(change):
    original = store.load_trusted_producer_registry()
    body = plain(original.body)
    body["profiles"][EXPECTED["profile"]].update(change)
    with pytest.raises(auth.ProducerAuthorizationError):
        _trusted_registry(body, original.materials, _LOADER_TOKEN)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema":"a","schema":"b"}',
        b'{"n":NaN}',
        b'{"n":Infinity}',
        b'{"n":-Infinity}',
        b'{"n":1e999}',
        b'{"schema":"unknown"}',
        b'{"schema":"producer-authorization-registry-v1","profiles":{},"accepted_receipts":{},"extra":1}',
    ],
)
def test_closed_json_rejections(raw):
    with pytest.raises(auth.ProducerAuthorizationError):
        validate_material(decode(raw))


@pytest.mark.parametrize("key", [k for k in EXPECTED if k != "registry"])
def test_every_material_schema_rejects_unknown_and_missing_field(key):
    registry = store.load_trusted_producer_registry()
    original = plain(registry.materials[EXPECTED[key]])
    extra = {**original, "caller_extension": 1}
    with pytest.raises(auth.ProducerAuthorizationError, match="fields"):
        validate_material(extra)
    removed = copy.deepcopy(original)
    removed.pop(next(k for k in removed if k != "schema"))
    with pytest.raises(auth.ProducerAuthorizationError, match="fields"):
        validate_material(removed)


def test_bad_material_content_identity():
    registry = store.load_trusted_producer_registry()
    body = plain(registry.materials[EXPECTED["profile"]])
    body["producer_id"] = "same-reference-different-body"
    with pytest.raises(auth.ProducerAuthorizationError, match="content ID"):
        validate_material(body, EXPECTED["profile"])


def test_provenance_seal_cannot_be_constructed_with_public_arguments():
    with pytest.raises(TypeError):
        auth.TrustedProducerRegistry(body={}, materials={})


def test_future_current_v8_does_not_retroactively_authorize_noncurrent_receipt(real, monkeypatch):
    from experiments.ask_cli_revised import sufficiency_engine as se

    monkeypatch.setattr(se, "SUFFICIENCY_SEMANTICS_VERSION", se.SUFFICIENCY_SEMANTICS_V8)
    with pytest.raises(auth.ProducerAuthorizationError):
        verify(real)
