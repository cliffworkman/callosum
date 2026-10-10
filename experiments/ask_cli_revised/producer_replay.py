"""The sole bounded v8 reproduction issuer; never accepts a caller map or provider."""

import copy
import platform
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from types import FunctionType, SimpleNamespace

from experiments.ask_cli_revised import ownership_context as oc
from experiments.ask_cli_revised import producer_authorization as auth
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_freeze as sf
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import sufficiency_model_scope as scope
from experiments.ask_cli_revised import sufficiency_recovery_targets as rt
from experiments.ask_cli_revised._producer_inputs import (
    FROZEN,
    OVERLAY,
    REVIEW,
    RUN,
    held_nominations,
    parent_map,
    requirements,
    reviewed_contracts,
    validate_nomination_requests,
    validate_preserved_nominations,
    validate_request_record,
)
from experiments.ask_cli_revised._producer_schema import (
    PREFIX,
    V8,
    ProducerInputBundle,
    byte_hash,
    canonical,
    decode,
    digest,
    plain,
    reference,
    require,
    safe_path,
)
from experiments.ask_cli_revised.producer_authorization_store import load_trusted_producer_registry

_ROOT = Path(__file__).resolve().parents[2]
_PRESERVED = _ROOT / ".local/e2e-runs/phase28-live-parent-synthesis-attempt2-20261004T014500Z/run"
_HIERARCHY_SOURCES = {
    "assembled": ".local/decompose-runs/aib-dev/closure_v8/ASSEMBLED_HIERARCHY.json",
    "approvals": ".local/decompose-runs/aib-dev/closure_v8/CLOSURE_APPROVALS.json",
    "decisions": ".local/decompose-runs/aib-dev/clarifications/q_aib.v6.researcher_decisions.json",
    "closure": ".local/decompose-runs/aib-dev/clarifications/q_aib.v8.closure_decisions.json",
}


@dataclass(frozen=True)
class ProducerReproduction:
    smap: dict
    receipt: dict
    input_bundle: ProducerInputBundle
    authored_contract: dict
    verified_authorization: auth.VerifiedProducerAuthorization


def _input_path(alias):
    safe_path(alias)
    if alias.startswith(RUN):
        return _PRESERVED / alias.removeprefix(RUN)
    if alias.startswith("hierarchy-input/"):
        name = alias.removeprefix("hierarchy-input/")
        require(name in _HIERARCHY_SOURCES, "unknown hierarchy input alias")
        return _ROOT / _HIERARCHY_SOURCES[name]
    require(alias.startswith(PREFIX), "unknown input source alias")
    return _ROOT / alias


def _snapshot_inputs(event):
    snapshots = {}
    for alias, expected in event["files"].items():
        path = _input_path(alias)
        require(path.resolve().is_relative_to(_ROOT.resolve()), "input source escapes repository")
        raw = path.read_bytes()
        require(byte_hash(raw) == expected, "enrolled input drift: " + alias)
        snapshots[alias] = raw
    return snapshots


def _verify_installed_producer(profile, code):
    runtime = profile["runtime_contract"]
    require(platform.python_implementation() == runtime["implementation"] == "CPython", "runtime implementation")
    require(platform.python_version() == runtime["version"] == "3.12.7", "runtime version")
    require(runtime["semantic_dependencies"] == "stdlib-and-pinned-local-callables-only", "runtime dependencies")
    require(len(code["files"]) == 26, "producer source inventory")
    snapshots = {}
    for relative, expected in code["files"].items():
        safe_path(relative)
        path = _ROOT / relative
        require(path.resolve().is_relative_to(_ROOT.resolve()), "producer source path escape")
        raw = path.read_bytes()
        normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode()
        require(byte_hash(normalized) == expected, "producer source drift: " + relative)
        snapshots[relative] = raw
    return snapshots


def _load_authoring_snapshot(files):
    # The existing loader requires paths. Give it private files made from verified snapshots,
    # never a second read from the mutable original paths.
    with TemporaryDirectory(prefix="callosum-producer-authoring-") as tmp:
        frozen, review = Path(tmp) / "frozen.json", Path(tmp) / "review.json"
        frozen.write_bytes(files[FROZEN])
        review.write_bytes(files[REVIEW])
        contracts = sf.load_verified(frozen_path=frozen, review_path=review)
    require(contracts == reviewed_contracts(files), "authoring snapshot mismatch")
    return contracts


def _isolated_functions(module):
    """Reuse pinned function code with a per-invocation globals namespace; no eval/exec."""
    namespace = dict(vars(module))
    for name, function in tuple(namespace.items()):
        if isinstance(function, FunctionType) and function.__module__ == module.__name__:
            isolated = FunctionType(function.__code__, namespace, name, function.__defaults__, function.__closure__)
            isolated.__kwdefaults__ = copy.deepcopy(function.__kwdefaults__)
            isolated.__annotations__ = dict(function.__annotations__)
            namespace[name] = isolated
    return namespace


def _no_fresh_nomination(*args, **kwargs):
    raise auth.ProducerAuthorizationError("fresh model nomination forbidden")


def _produce(files, contracts, parent, context, nominations, manifest):
    _, specs, traces = validate_preserved_nominations(files, contracts, nominations, manifest)
    held = {(tuple(row["scope"]) + (row["request_context"],)): row["bindings"] for row in nominations}
    requests = []
    mapper = _isolated_functions(sm)
    original = mapper["_bind_role_candidates"]

    def preserved_binding(spec, units, **kwargs):
        require(
            kwargs.get("model_client") is None and kwargs.get("nomination_context") is None, "fresh provider forbidden"
        )
        if spec["mapping_strategy"] != "model_nomination_only":
            return original(spec, units, **kwargs)
        key = (kwargs.get("child_id"), kwargs.get("requirement_id"), spec["role"], kwargs.get("request_context"))
        require(key in held, "unrecorded nomination slot")
        rows = mapper["_candidate_rows_for_role"](spec, units)
        request = {
            "scope": list(key[:3]),
            "request_context": key[3],
            "category_description": spec["category_description"],
            "candidate_rows": rows,
            "request_fingerprint": scope.request_fingerprint(spec["category_description"], rows),
        }
        validate_request_record(request, nominations, specs, traces)
        requests.append(request)
        return copy.deepcopy(held[key])

    mapper["_bind_role_candidates"] = preserved_binding
    mapper["nominate_with_model"] = _no_fresh_nomination
    diagnostic = _isolated_functions(sd)
    diagnostic["sm"] = SimpleNamespace(**mapper)
    sealed = decode(files[RUN + "11_verified_ledger.json"])
    mapped = diagnostic["compute_diagnostic_sufficiency_map"](
        sealed,
        contracts,
        parent,
        semantics_version=V8,
        ownership_context_index=context,
    )
    diagnostic["compute_direction_and_effectiveness"](sealed, mapped, semantics_version=V8)
    return mapped, sorted(requests, key=canonical)


def _inventory(mapped):
    requirements_ = [q for c in mapped.values() for q in c["requirements"]]
    instances = [i for q in requirements_ for i in q["instances"]]
    proofs = [p for i in instances for p in i["witness_bundle"]["proofs"].values()]
    require(len(requirements_) == 13 and len(instances) == 46, "scientific state inventory")
    require(len(proofs) == 20 and sum(p["purpose"] == "completion_joint" for p in proofs) == 11, "proof inventory")
    require(sum(len(i.get("direction_observations", [])) for i in instances) == 6, "direction inventory")
    require(not any(i.get("effectiveness_observations") for i in instances), "effectiveness inventory")


def _write_output(output_dir, result):
    destination = Path(output_dir).resolve()
    if destination.is_relative_to(_ROOT.resolve()):
        require(
            destination.is_relative_to((_ROOT / ".local/i4-4d1").resolve()), "dedicated reproduction directory required"
        )
    require(not destination.is_relative_to(_PRESERVED.resolve()), "historical directory is immutable")
    protected = (_ROOT / "experiments").resolve()
    require(not destination.is_relative_to(protected), "enrollment/material directories are immutable")
    require(not destination.exists(), "reproduction output must be a new directory")
    destination.mkdir(parents=True)
    (destination / "sufficiency_map.json").write_bytes(canonical(result.smap))
    (destination / "producer_output_receipt.json").write_bytes(canonical(result.receipt))
    (destination / "verified_authorization.json").write_bytes(
        canonical(
            {
                "authorization_ref": result.verified_authorization.authorization_ref,
                "identities": result.verified_authorization.identities,
            }
        )
    )


def reproduce_accepted_v8(*, output_dir=None):
    """Issue only the independently enrolled logical event, from its fixed preserved inputs."""
    registry = load_trusted_producer_registry()
    require(len(registry.body["profiles"]) == len(registry.body["accepted_receipts"]) == 1, "single-event issuer scope")
    receipt_ref = next(iter(registry.body["accepted_receipts"]))
    target = registry.materials[receipt_ref]
    profile, _ = auth.resolve_authority(registry, target, issuance=True)
    code = registry.materials[profile["producer_code_manifest_ref"]]
    source_snapshots = _verify_installed_producer(profile, code)
    require(len(source_snapshots) == 26, "incomplete producer snapshot")
    event = registry.materials[target["input_manifest_ref"]]
    files = _snapshot_inputs(event)
    contracts = _load_authoring_snapshot(files)
    parent = parent_map(files)
    authored = {"requirements": requirements(contracts), "overlay": decode(files[OVERLAY])}
    require(digest(parent) == registry.materials[target["authored_inputs_ref"]]["parent_map_sha256"], "parent identity")
    nominations = held_nominations(decode(files[RUN + "17_sufficiency_map.json"]))
    sealed = decode(files[RUN + "11_verified_ledger.json"])
    packets = [decode(line) for line in files[RUN + "08_evidence_packets.jsonl"].splitlines() if line.strip()]
    context = oc.build_context_index(sealed, packets)
    before = canonical([files[RUN + "11_verified_ledger.json"].decode(), contracts, nominations, context])
    manifest = registry.materials[target["nomination_inputs_ref"]]
    mapped, requests = _produce(files, contracts, parent, context, nominations, manifest)
    require(
        canonical([files[RUN + "11_verified_ledger.json"].decode(), contracts, nominations, context]) == before,
        "producer mutated inputs",
    )
    validate_nomination_requests(files, contracts, nominations, requests, manifest)
    require(digest(mapped) == target["map_canonical_sha256"], "accepted v8 map drift")
    _inventory(mapped)
    recovery = rt.compute_recovery_targets(mapped, parent, semantics_version=V8)
    require(len(recovery) == 48 and digest(recovery) == target["recovery_targets_sha256"], "recovery drift")
    bundle = ProducerInputBundle(files, nominations, requests, context, recovery)
    # Copy the fixed event template, then bind values actually produced in this invocation.
    # There is no public arbitrary-map receipt constructor and no registry write.
    receipt = plain(target)
    receipt["map_canonical_sha256"] = digest(mapped)
    receipt["recovery_targets_sha256"] = digest(recovery)
    receipt["sealed_artifact_bytes_sha256"] = byte_hash(files[RUN + "11_verified_ledger.json"])
    require(reference(receipt) == receipt_ref, "preregistered receipt drift")
    verified = auth.verify_producer_authorization(
        mapped,
        files[RUN + "11_verified_ledger.json"],
        authored,
        receipt,
        input_bundle=bundle,
        trusted_registry=registry,
    )
    result = ProducerReproduction(copy.deepcopy(mapped), receipt, bundle, copy.deepcopy(authored), verified)
    if output_dir is not None:
        _write_output(output_dir, result)
    return result
