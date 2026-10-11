"""Reviewed question-facing ownership, independent of scientific results."""

from experiments.ask_cli_revised._layerc_common import body_reference, plain, require

SCHEMA = "reporting-contract-v1"


def request_ref(request):
    return body_reference("request-contract", request)


def reporting_ref(reporting):
    return body_reference(SCHEMA, reporting)


def _names(values, message):
    require(isinstance(values, list), message)
    require(all(isinstance(v, str) and v.strip() for v in values), message)
    require(len(values) == len(set(values)), message)
    return set(values)


def validate(reporting, request, scientific):
    """Validate authored structure; never infer missing wording, scope or ownership."""
    require(isinstance(reporting, dict), "reporting body required")
    require(
        set(reporting) == {"schema", "request_ref", "nodes", "scientific_only_child_ids", "requested_construct_terms"},
        "closed reporting fields",
    )
    require(reporting["schema"] == SCHEMA, "reporting schema")
    require(reporting["request_ref"] == request_ref(request), "reporting request binding")
    require(isinstance(scientific, dict) and bool(scientific), "scientific inventory required")
    rids = []
    for cid, contract in scientific.items():
        require(isinstance(cid, str) and bool(cid.strip()) and contract["child_id"] == cid, "scientific child identity")
        require(bool(contract["requirements"]), "scientific child has no requirements")
        rids.extend(r["id"] for r in contract["requirements"])
    _names(rids, "globally unique requirement IDs required")
    nodes = reporting["nodes"]
    require(isinstance(nodes, list) and bool(nodes), "visible nodes required")
    seen, owned, stack = set(), set(), []
    for node in nodes:
        require(
            isinstance(node, dict) and set(node) == {"node_id", "literal_text", "parent_id", "owning_child_ids"},
            "closed reporting node fields",
        )
        nid, parent = node["node_id"], node["parent_id"]
        require(isinstance(nid, str) and bool(nid.strip()) and nid not in seen, "unique nonblank node ID required")
        require(isinstance(node["literal_text"], str) and bool(node["literal_text"].strip()), "literal required")
        require(parent is None or isinstance(parent, str), "parent ID type")
        if parent is None:
            stack = []
        else:
            require(parent in seen and parent in stack, "parent/order/cycle: depth-first preceding ancestor required")
            stack = stack[: stack.index(parent) + 1]
        stack.append(nid)
        seen.add(nid)
        children = _names(node["owning_child_ids"], "unique owned children required")
        require(bool(children), "visible node must own a scientific child")
        require(children <= set(scientific), "unknown scientific child")
        require(not children & owned, "duplicate scientific child ownership")
        owned.update(children)
    hidden = _names(reporting["scientific_only_child_ids"], "unique scientific-only children required")
    require(not hidden & owned and hidden | owned == set(scientific), "exact scientific child partition required")
    _names(reporting["requested_construct_terms"], "explicit unique construct terms required")
    return reporting_ref(reporting)


def single_question(request, scientific, *, requested_construct_terms):
    """Explicit authoring operation, not approval; caller must review the result."""
    from experiments.ask_cli_revised.request_contract import request_subquestions

    obligations = [sq["obligations"][0]["field_id"] for sq in request_subquestions(request)]
    require(len(obligations) == 1 and set(obligations) == set(scientific), "single actual obligation required")
    result = {
        "schema": SCHEMA,
        "request_ref": request_ref(request),
        "nodes": [
            {
                "node_id": "1",
                "literal_text": request["original_question"],
                "parent_id": None,
                "owning_child_ids": obligations,
            }
        ],
        "scientific_only_child_ids": [],
        "requested_construct_terms": list(requested_construct_terms),
    }
    validate(result, request, scientific)
    return result


def consumer_view(reporting):
    """Shape-only adaptation after validation; no historical overlay metadata."""
    return {
        "nodes": [
            {
                "label": n["node_id"],
                "literal_text": n["literal_text"],
                "parent": n["parent_id"],
                "owning_child_ids": list(n["owning_child_ids"]),
            }
            for n in reporting["nodes"]
        ],
        "requested_construct_terms": plain(reporting["requested_construct_terms"]),
    }
