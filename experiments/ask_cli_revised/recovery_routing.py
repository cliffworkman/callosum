"""Resolve scientific recovery ownership through the actual request obligations."""


def subquestion_id_for_obligation(subquestions: list[dict], obligation_id: str) -> str:
    """Return the unique retrieval owner, without deriving IDs from their spelling.

    A malformed ownership join is an integration failure, not a completed search or
    a scientific absence. Fail before dispatch rather than silently losing a target.
    """
    owners = [
        sq
        for sq in subquestions
        for obligation in sq.get("obligations", [])
        if obligation.get("field_id") == obligation_id
    ]
    if not owners:
        raise ValueError(f"recovery_owner_missing: {obligation_id!r}")
    if len(owners) != 1:
        raise ValueError(f"recovery_owner_ambiguous: {obligation_id!r}")
    sid = owners[0].get("subquestion_id")
    if not isinstance(sid, str) or not sid:
        raise ValueError(f"recovery_owner_missing_subquestion_id: {obligation_id!r}")
    if sum(sq.get("subquestion_id") == sid for sq in subquestions) != 1:
        raise ValueError(f"recovery_owner_ambiguous_subquestion_id: {obligation_id!r}")
    return sid
