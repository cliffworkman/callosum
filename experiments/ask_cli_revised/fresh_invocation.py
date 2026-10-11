"""Local invocation provenance, issued only at the active execution's post-U2 boundary.

Private issuance is an in-process capability, not a defense against code running with
arbitrary Python reflection privileges. No deserialization or persisted-map issuer exists.
"""

from dataclasses import dataclass

from experiments.ask_cli_revised import reporting_contract as rc
from experiments.ask_cli_revised import reviewed_ask_inputs as reviewed
from experiments.ask_cli_revised import sufficiency_identity as si
from experiments.ask_cli_revised._layerc_common import V8, body_reference, digest, freeze, plain, require, text_hash

PROFILE = "fresh-v8-layerc-v2-plan-v5"
_ORIGIN = object()


@dataclass(frozen=True, init=False)
class TrustedFreshInvocation:
    body: object
    provenance_ref: str
    _origin: object

    def __init__(self):
        raise TypeError("fresh provenance requires active post-U2 execution")

    def __reduce__(self):
        raise TypeError("fresh provenance cannot be deserialized")

    def validate(self):
        require(self._origin is _ORIGIN, "not trusted invocation provenance")
        require(
            self.provenance_ref == body_reference("trusted-fresh-invocation-v1", self.body), "fresh provenance mutated"
        )

    def projection_profile(self):
        self.validate()
        b = plain(self.body)
        return {
            "name": PROFILE,
            "sufficiency_identity": b["sufficiency_identity"],
            "map_sha256": b["map_sha256"],
            "sealed_artifact_sha256": b["sealed_artifact_sha256"],
            "sealed_proposition_index_sha256": b["sealed_proposition_index_sha256"],
            "authored_contract_sha256": b["authored_contract_sha256"],
            "overlay_sha256": b["reporting_view_sha256"],
            "context_manifest_sha256": digest(()),
            "containment_semantics": V8,
            "direction_semantics": V8,
            "upstream_authority": {"kind": "trusted_fresh_invocation", "ref": self.provenance_ref},
            "reporting_contract_ref": b["reporting_ref"],
        }

    def validate_projection(self, smap, raw, authored, profile, contexts):
        self.validate()
        require(profile == self.projection_profile() and not contexts, "fresh projection profile mismatch")
        b = self.body
        require(
            digest(smap) == b["map_sha256"] and text_hash(raw.decode("utf-8")) == b["sealed_artifact_sha256"],
            "fresh scientific input mismatch",
        )
        require(
            digest(authored["requirements"]) == b["authored_contract_sha256"]
            and digest(authored["overlay"]) == b["reporting_view_sha256"],
            "fresh authored input mismatch",
        )


class _Execution:
    def __init__(self, inputs):
        reviewed.validate_bound(inputs)
        self.inputs = inputs
        self.active = True

    def finish(self, *, request, scientific, parent_of, smap, sealed, ownership_context, recovery, search):
        require(self.active, "fresh execution already consumed")
        self.active = False
        reviewed.validate_bound(self.inputs)
        inputs = self.inputs
        require(
            plain(inputs.request) == request
            and plain(inputs.scientific) == scientific
            and plain(inputs.parent_of) == parent_of,
            "execution authoring mutated",
        )
        identity = si.read_map_identity(smap, accept_supported_noncurrent=True)
        require(
            identity["version"] == V8 and identity["status"] in {"current", "supported_noncurrent"},
            "explicit fresh v8 required",
        )
        props = {p["proposition_id"]: p for p in sealed["verified_propositions"]}
        from experiments.ask_cli_revised._layerc_common import canonical

        raw = canonical(sealed).encode("utf-8")
        authored = {
            "requirements": {cid: c["requirements"] for cid, c in scientific.items()},
            "overlay": rc.consumer_view(inputs.reporting),
        }
        body = {
            "schema": "trusted-fresh-invocation-v1",
            **plain(inputs.refs),
            "review_ref": body_reference("reviewed-ask-inputs-v1", inputs.review),
            "sufficiency_identity": identity,
            "map_sha256": digest(smap),
            "sealed_artifact_sha256": text_hash(raw.decode("utf-8")),
            "sealed_proposition_index_sha256": digest(props),
            "ownership_context_sha256": digest(ownership_context),
            "recovery_sha256": digest(recovery),
            "search_sha256": digest(search),
            "authored_contract_sha256": digest(authored["requirements"]),
            "reporting_view_sha256": digest(authored["overlay"]),
        }
        result = object.__new__(TrustedFreshInvocation)
        object.__setattr__(result, "body", freeze(body))
        object.__setattr__(result, "provenance_ref", body_reference("trusted-fresh-invocation-v1", body))
        object.__setattr__(result, "_origin", _ORIGIN)
        return result, raw, authored


def _begin_execution(inputs):
    """Private capability: only e2e.execute calls this before its scientific stages."""
    return _Execution(inputs)
