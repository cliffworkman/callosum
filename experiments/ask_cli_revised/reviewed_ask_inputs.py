"""Explicit reviewed authoring snapshots. Content hashes bind review; they do not issue it."""

import json
from dataclasses import dataclass
from pathlib import Path

from experiments.ask_cli_revised import reporting_contract as rc
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised._layerc_common import body_reference, freeze, plain, require
from experiments.ask_cli_revised.request_contract import request_subquestions

_ORIGIN = object()


def input_refs(request, scientific, reporting, parent_of):
    return {
        "request_ref": rc.request_ref(request),
        "scientific_ref": body_reference("reviewed-scientific-contract-v1", scientific),
        "reporting_ref": rc.reporting_ref(reporting),
        "parent_context_ref": body_reference("reviewed-parent-context-v1", parent_of),
    }


@dataclass(frozen=True, init=False)
class ReviewedAskInputs:
    request: object
    scientific: object
    reporting: object
    parent_of: object
    review: object
    refs: object
    _origin: object

    def __init__(self):
        raise TypeError("use bind_reviewed_inputs with an actual joint review")

    def __reduce__(self):
        raise TypeError("reviewed state is not a serialized credential")


def bind_reviewed_inputs(request, scientific, reporting, parent_of, review):
    """Accept existing joint review, never create a reviewer/approval or infer science.

    The authoring caller is trusted to supply its real review record, just as the existing
    frozen/review loader is. This is not authentication of arbitrary scientific output.
    """
    request, scientific, reporting, parent_of, review = plain([request, scientific, reporting, parent_of, review])
    require(isinstance(scientific, dict) and bool(scientific), "reviewed science required")
    require(all(se.frozen_view(c) == c for c in scientific.values()), "authoring must contain frozen definitions only")
    rc.validate(reporting, request, scientific)
    ids = {sq["obligations"][0]["field_id"] for sq in request_subquestions(request)}
    require(ids == set(scientific), "scientific children must equal actual request obligation IDs")
    require(isinstance(parent_of, dict) and set(parent_of) <= ids, "scientific parent scope")
    for cid, parent in parent_of.items():
        require(parent in ids or parent == "R", "unknown scientific parent")
        seen = {cid}
        while parent in parent_of:
            require(parent not in seen, "scientific parent cycle")
            seen.add(parent)
            parent = parent_of[parent]
    if request.get("version") == "hierarchical-request-v1":
        from experiments.ask_cli_revised import hierarchy_contract

        hierarchy_contract.assert_executable(request)
        require(parent_of == hierarchy_contract.parent_of(request), "reviewed hierarchy parent mismatch")
    else:
        require(
            request.get("version") == "literal-request-v1" and not parent_of, "flat request has no scientific hierarchy"
        )
    refs = input_refs(request, scientific, reporting, parent_of)
    require(
        isinstance(review, dict) and set(review) == {"schema", "status", "reviewed_by", "reviewed_at", "inputs"},
        "joint review fields",
    )
    require(
        review["schema"] == "reviewed-ask-inputs-v1" and review["status"] == "reviewed", "actual joint review required"
    )
    require(
        all(isinstance(review[k], str) and review[k].strip() for k in ("reviewed_by", "reviewed_at")),
        "review attribution required",
    )
    require(review["inputs"] == refs, "joint review input mismatch")
    result = object.__new__(ReviewedAskInputs)
    for key, value in dict(
        request=request, scientific=scientific, reporting=reporting, parent_of=parent_of, review=review, refs=refs
    ).items():
        object.__setattr__(result, key, freeze(value))
    object.__setattr__(result, "_origin", _ORIGIN)
    return result


def validate_bound(inputs):
    require(type(inputs) is ReviewedAskInputs and inputs._origin is _ORIGIN, "bound reviewed inputs required")
    require(
        input_refs(inputs.request, inputs.scientific, inputs.reporting, inputs.parent_of) == plain(inputs.refs),
        "reviewed inputs mutated",
    )
    require(plain(inputs.review)["inputs"] == plain(inputs.refs), "review changed")


def load_reviewed_inputs(*, request_path, scientific_path, reporting_path, parent_path, review_path):
    """Read each explicit authored path once; no default files and no persisted maps."""
    values = [
        json.loads(Path(p).read_bytes())
        for p in (request_path, scientific_path, reporting_path, parent_path, review_path)
    ]
    return bind_reviewed_inputs(*values)
