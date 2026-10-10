"""Canonical, detached substrate records. No consumer activation or scientific decisions."""

import hashlib
import json
from collections.abc import Mapping
from types import MappingProxyType

V8 = "sufficiency-semantics-v8"
PROFILE = "v8-layerc-v2-plan-v5"
STRATEGIES = frozenset(
    {
        "named_instrument_lexicon",
        "achieved_outcome_predicate",
        "explicit_category_terms",
        "direction_or_sign_pattern",
        "model_nomination_only",
    }
)


class ProjectionIntegrityError(ValueError):
    """Stored scientific outputs or their authorization do not agree."""


def require(condition, message):
    if not condition:
        raise ProjectionIntegrityError(message)


def plain(value):
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def canonical(value):
    return json.dumps(plain(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def text_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value is not None else None


def reference(scheme, body):
    return scheme + ":sha256:" + digest({"scheme": scheme, **body})


def body_reference(scheme, body):
    return scheme + ":sha256:" + digest(body)


def freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    require(value is None or type(value) in (str, bool, int, float), "non-JSON projection value")
    return value


def put(registry, key, value):
    require(key not in registry or registry[key] == value, "conflicting reference: " + key)
    registry[key] = value


def source_identity(prop):
    return {k: prop.get(k) for k in ("paper_id", "evidence_anchor_chunk_id", "evidence_span_id", "anchors")}


def outer_source(binding):
    p = binding.get("provenance") or {}
    return {k: p.get(k) for k in ("candidate_source", "model", "upstream_model_dependent", "source_lineage")}


def own_source(binding):
    return "inherited" if outer_source(binding)["candidate_source"] == "parent_context" else "own"


def quote_identity(pid, props):
    require(pid in props and isinstance(props[pid].get("quote"), str), "missing sealed quote")
    return {
        "proposition_id": pid,
        "quote_sha256": text_hash(props[pid]["quote"]),
        "source_identity": source_identity(props[pid]),
    }


def check_span(span, quote):
    require(
        isinstance(span, list)
        and len(span) == 2
        and all(type(n) is int for n in span)
        and 0 <= span[0] < span[1] <= len(quote),
        "invalid source span",
    )


def display_envelope(source_ref, quote, evidence_span):
    """Only adjacent whitespace and an unambiguous adjacent period; never find substitute text."""
    check_span(evidence_span, quote)
    start, end = evidence_span
    left, right = start, end
    while left and quote[left - 1].isspace():
        left -= 1
    rules = []
    if left != start:
        rules.append("adjacent_whitespace")
    # A following alphanumeric continuation, ellipsis or existing terminal mark is not a wrapper.
    if (
        right < len(quote)
        and quote[right] == "."
        and quote[right - 1] not in ".!?"
        and (right + 1 == len(quote) or quote[right + 1].isspace())
    ):
        right += 1
        rules.append("adjacent_terminal_period")
    after = right
    while right < len(quote) and quote[right].isspace():
        right += 1
    if right != after and "adjacent_whitespace" not in rules:
        rules.append("adjacent_whitespace")
    additions = []
    if left < start:
        additions.append({"span": [left, start], "text": quote[left:start]})
    if end < right:
        additions.append({"span": [end, right], "text": quote[end:right]})
    body = {
        "schema": "display-envelope-v1",
        "source_ref": source_ref,
        "quote_sha256": text_hash(quote),
        "evidence_span": evidence_span[:],
        "display_span": [left, right],
        "added_intervals": additions,
        "wrapper_rule_ids": sorted(rules),
        "semantic_support_added": False,
    }
    return body_reference("display-envelope-v1", body), body


def semantic_claim_id(family, scope, content):
    """Pure closed future identity helper; does not construct or activate ParentClaims."""
    fields = {
        "role_value": {"role", "value_id"},
        "category_list": {"role", "member_value_ids", "grouping"},
        "relational": {"relation_kind", "operands", "relation_contract"},
        "direction_or_effectiveness": {"summary_kind", "operands", "target_contract", "consensus", "conflict"},
    }
    require(family in fields and set(content) == fields[family], "invalid claim identity content")
    require(set(scope) == {"owner_ids", "requirement_ids"}, "invalid claim scope")
    content = plain(content)
    if family == "category_list":
        require(
            set(content["grouping"]) == {"instance_quantifier", "quantifier_n", "requested_category_terms"},
            "invalid grouping identity",
        )
        content["member_value_ids"] = sorted(set(content["member_value_ids"]))
        content["grouping"]["requested_category_terms"] = sorted(set(content["grouping"]["requested_category_terms"]))
    if family == "relational":
        require(content["relation_kind"] in ("joint_own_completion", "required_role_relation"), "relation kind")
        contract = content["relation_contract"]
        require(
            set(contract) == {"required_roles", "alternative_role_groups", "relationship_verifiers"},
            "invalid relation contract",
        )
        for k in ("required_roles", "relationship_verifiers"):
            contract[k] = sorted(set(contract[k]))
        contract["alternative_role_groups"] = sorted(
            {tuple(sorted(set(g))) for g in contract["alternative_role_groups"]}
        )
    forbidden = {"proposition_id", "proof_id", "receipt_id", "instance_key", "support_ref", "display_text"}

    def check(value):
        if isinstance(value, dict):
            require(not forbidden.intersection(value), "evidence in semantic identity")
            for v in value.values():
                check(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                check(v)

    check(content)
    body = {
        "schema": "parent-claim-v2",
        "family": family,
        "scope": {k: sorted(set(scope[k])) for k in sorted(scope)},
        "content": content,
    }
    return body_reference("parent-claim-v2", body)
