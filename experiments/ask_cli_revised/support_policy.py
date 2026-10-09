"""Pure v7 evidence policy: supplied semantic triples only; no text or context classification."""

from experiments.ask_cli_revised import sufficiency_engine as se


def _triple(assertion_relation, aggregation, assertion_kind):
    for value, allowed in (
        (assertion_relation, se.SUPPORT_ASSERTION_RELATIONS),
        (aggregation, se.SUPPORT_AGGREGATIONS),
        (assertion_kind, se.SUPPORT_ASSERTION_KINDS),
    ):
        if not isinstance(value, str) or value not in allowed:
            raise ValueError("invalid support-policy semantic triple")


def _record(source, snapshot, failures):
    return {
        "schema_version": "support-policy-evaluation-v1",
        "policy_source": source,
        "policy_identity": se.support_policy_identity(source, snapshot),
        "policy_snapshot": snapshot,
        "passed": not failures,
        "failed_dimensions": [d for d, _ in failures],
        "reasons": [r for _, r in failures],
    }


def default_support_policy(*, assertion_relation, aggregation, assertion_kind):
    """The absent empirical rule; deliberately different from the permissive policy builder."""
    _triple(assertion_relation, aggregation, assertion_kind)
    failures = []
    if assertion_relation == "unresolved" and aggregation == "non_synthetic_or_unspecified":
        failures.append(("relation_aggregation", "unresolved_non_synthetic"))
    if assertion_kind != "result":
        failures.append(("kind", "non_result_kind"))
    return _record("absent_default", se.default_support_policy_snapshot(), failures)


def evaluate_authored_support_policy(policy, *, assertion_relation, aggregation, assertion_kind):
    """A complete authored policy replaces the empirical default, with three-dimensional AND."""
    snapshot = se.canonical_support_policy(policy)
    _triple(assertion_relation, aggregation, assertion_kind)
    failures = []
    if assertion_relation not in snapshot["allowed_assertion_relations"]:
        failures.append(("relation", "assertion_relation_not_allowed"))
    requirement = snapshot["aggregation_requirement"]
    if requirement == "require_synthesis" and aggregation != "literature_synthesis":
        failures.append(("aggregation", "aggregation_requires_synthesis"))
    if requirement == "exclude_synthesis" and aggregation != "non_synthetic_or_unspecified":
        failures.append(("aggregation", "aggregation_excludes_synthesis"))
    if assertion_kind not in snapshot["allowed_assertion_kinds"]:
        failures.append(("kind", "assertion_kind_not_allowed"))
    return _record("authored", snapshot, failures)
