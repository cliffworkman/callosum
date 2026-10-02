"""Phase 19: robust model-nomination scoping + nomination-receipt infrastructure.

Audit (`.claude/plans/pasted-content-id-ec13-new-architectura-snappy-storm.md`, 2026-10-02)
found production `e2e.py` supplies no `model_client` anywhere, so no model-assisted sufficiency
nomination happens today; the real gap before turning it on is an explicit, identity-safe scope
for "who/what may ask the model, and under what authorization" that never relies on descriptive-
text matching. This module owns that seam. It is deliberately dependency-free of both
`sufficiency_mapping.py` and `sufficiency_recovery_targets.py` (house style mirrors
`sufficiency_engine.py`'s own position below the mapper): every place this module would otherwise
need to call into mapping internals (making the actual model call, re-validating a prior receipt
against the current admissible candidate pool) is instead handed in by the caller as a plain
callable -- dependency inversion, not a missing feature. Plain dicts/tuples throughout, never a
class hierarchy, matching every sibling module's own stated house style
(`sufficiency_recovery_targets.py`'s "plain-dict builders, never a class/dataclass").

Zero question/domain-specific vocabulary appears below -- every function operates on any
`{child_id: SufficiencyContract}` or `RecoveryTarget`-shaped dict, never on q_aib's own role/
child names (proven generically in `test_sufficiency_model_scope.py`, then against the real
frozen v9 contract as a corroborating, not load-bearing, check).

**Production calls stay OFF in this phase.** Nothing here is wired into `e2e.py`; this module
and its integration checkpoint in `sufficiency_mapping.py` are reachable only when a caller
explicitly constructs and supplies a `nomination_context` (see `new_nomination_context`) --
every existing caller that omits it (including every production and historical-replay call site)
observes byte-identical pre-Phase-19 behavior.
"""

from __future__ import annotations

import hashlib
import json

# ---------------------------------------------------------------------------------------------
# Model-nomination scope identity: (child_id, requirement_id, role). Audit §3/§14: no instance_
# key, no binding index -- a model's own request never varies by instance, only by this triple.
# ---------------------------------------------------------------------------------------------


def new_model_nomination_scope(child_id: str, requirement_id: str, role: str) -> tuple[str, str, str]:
    """A plain, hashable 3-tuple -- the complete identity of one model-nomination task. Never
    derived from `category_description`/wording/a RecoveryTarget's own `target_id` (audit §4/§17):
    callers always supply `child_id`/`requirement_id`/`role` as explicit data, threaded
    structurally from where each is already known (`sufficiency_diagnostic`'s per-child loop,
    `requirement["id"]`, and a role_specs key, respectively) -- never parsed back out of a string."""
    if not child_id or not requirement_id or not role:
        raise ValueError(
            "a model-nomination scope requires non-empty child_id, requirement_id, and role; "
            f"got child_id={child_id!r}, requirement_id={requirement_id!r}, role={role!r}"
        )
    return (child_id, requirement_id, role)


def new_model_nomination_key(
    scope: tuple[str, str, str], request_context: str | None = None
) -> tuple[tuple[str, str, str], str | None]:
    """Phase 19b: the MEMOIZATION/receipt key, a strictly separate concept from `scope` itself.

    `scope` = `(child_id, requirement_id, role)` answers "may this semantic role make a fresh
    model request at all, under the current policy" -- AUTHORIZATION, unchanged from Phase 19,
    never touched by this function.

    `request_context` answers "which instance-local evidence partition, within an authorized
    scope, is THIS particular invocation about" -- it is the mapper's own already-computed
    PRE-FORK `root_key` (`sufficiency_mapping.map_requirement`'s own loop variable): `None` for
    every requirement `build_multi_instances` never partitions, or a candidate unit's own
    `unit_id` for one it does. Never the FINAL, rederived `instance_key`
    (`sufficiency_engine.derive_instance_key`) -- that value changes across a role's own forks
    specifically to keep genuinely-different bound content from colliding, which would destroy
    the role-fork deduplication Phase 19 already proved necessary (the Phase-21-preflight audit's
    own finding). Never a binding index, candidate order, category_description, or a request
    fingerprint -- none of those may ever decide identity, only content equivalence.

    ONE canonical constructor so this composite key is never hand-assembled ad hoc at a call site;
    every receipt store in this module (`in_pass_receipts`, `prior_receipts`) is keyed by this
    exact tuple shape."""
    return (scope, request_context)


def enumerate_model_nomination_scopes(contract_by_child: dict) -> list[tuple[str, str, str]]:
    """Every scope in `contract_by_child` (`{child_id: SufficiencyContract}`, frozen or mapped --
    both carry the same `role_specs`, since mapping never alters them) whose role is eligible for
    model-assisted nomination today: `mapping_strategy == "model_nomination_only"` AND
    `model_nomination_permitted`. This is the audit's §C/§8 mandatory preflight made mechanical
    and reusable, rather than a one-off hand count -- run it against any contract set, including
    a future non-q_aib one, with zero changes."""
    scopes: list[tuple[str, str, str]] = []
    for child_id, contract in contract_by_child.items():
        for requirement in contract["requirements"]:
            for role, spec in requirement["role_specs"].items():
                if spec["mapping_strategy"] == "model_nomination_only" and spec["model_nomination_permitted"]:
                    scopes.append(new_model_nomination_scope(child_id, requirement["id"], role))
    return scopes


# ---------------------------------------------------------------------------------------------
# Request fingerprint: proof that two physical invocations under one scope are equivalent
# requests. NOT part of scope identity, and NEVER used for authorization (audit §D/§E) -- only
# for safe in-pass memoization, replay validation, and auditability.
# ---------------------------------------------------------------------------------------------


def request_fingerprint(category_description: str, candidate_rows: list[dict]) -> str:
    """A canonical SHA-256 hex digest over `category_description` + the candidate rows actually
    offered to the model (`{proposition_id, passage}` pairs) -- `candidate_rows` is sorted by
    `proposition_id` before hashing so mere ordering is never mistaken for a semantic difference
    (audit §D). Mirrors `sufficiency_recovery_targets.new_target_id`'s own canonical-JSON-then-
    hash house style."""
    canonical_rows = sorted(
        ({"proposition_id": row["proposition_id"], "passage": row["passage"]} for row in candidate_rows),
        key=lambda row: row["proposition_id"],
    )
    payload = {"category_description": category_description, "candidates": canonical_rows}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RequestFingerprintMismatch(Exception):
    """Raised when the SAME (authorization scope, request context) memoization key is resolved
    twice within one mapping pass with two DIFFERENT model-facing requests. Phase 19b narrows this
    from Phase 19's own original "(child_id, requirement_id, role) implies one request" assumption
    -- the Phase-21 preflight falsified that for `multi_instance=True`, no-parent-context
    requirements (`build_multi_instances` partitions one authorization scope's candidates across
    several real evidence units, e.g. real q_aib c12: two units, two legitimately different
    requests, same scope). The memoization KEY now includes `request_context` (see
    `new_model_nomination_key`), so two different request contexts under one scope never collide
    here at all; this exception still fires, and must still never be silently papered over, when
    the SAME (scope, request_context) pair sees two different requests within one pass -- that
    remains a genuine same-slot drift, never a legitimate partitioning."""


# ---------------------------------------------------------------------------------------------
# Authorization policies: who may make a FRESH call this pass. Two policies for now (audit §K);
# both are plain dicts with a validated `kind`, matching this package's own enum-as-tuple style.
# ---------------------------------------------------------------------------------------------


def all_eligible_policy() -> dict:
    """Initial-pass-style policy: every structurally eligible scope may make one fresh call."""
    return {"kind": "all_eligible"}


def exact_scope_set_policy(scopes) -> dict:
    """Recovery-remap-style policy: only the named scopes may make a fresh call; every other
    model-assisted scope is held fixed (audit §5B/§7)."""
    return {"kind": "exact_scope_set", "scopes": frozenset(scopes)}


def is_authorized_for_fresh_call(policy: dict, scope: tuple[str, str, str]) -> bool:
    kind = policy["kind"]
    if kind == "all_eligible":
        return True
    if kind == "exact_scope_set":
        return scope in policy["scopes"]
    raise ValueError(f"unknown nomination authorization policy kind: {kind!r}")


# ---------------------------------------------------------------------------------------------
# Nomination receipts: the NORMALIZED/ACCEPTED output of `nominate_with_model` (audit §H/§I) --
# never the derived role binding. Upstream of instance forking, instance keys, provenance
# stamping, and parent-context propagation; those stay exactly as `sufficiency_mapping.py`/
# `sufficiency_engine.py` already build them from an accepted nomination list.
# ---------------------------------------------------------------------------------------------


def new_nomination_receipt(
    scope: tuple[str, str, str],
    *,
    request_context: str | None = None,
    model_name,
    request_fingerprint: str,
    candidates_offered: list[dict],
    accepted: list[dict],
    status: str,
) -> dict:
    """Phase 19b adds `request_context` (default `None`, matching every pre-Phase-19b caller and
    every non-partitioned requirement byte-identically) alongside the unchanged existing fields.
    Still upstream of binding construction -- never a mapped instance, role binding,
    RecoveryTarget, or final `instance_key` (those stay exactly where `sufficiency_mapping.py`/
    `sufficiency_engine.py` already build them)."""
    return {
        "scope": scope,
        "request_context": request_context,
        "model_name": model_name,
        "request_fingerprint": request_fingerprint,
        "candidates_offered": list(candidates_offered),
        "accepted": list(accepted),
        "status": status,
    }


def new_nomination_context(policy: dict, *, prior_receipts: dict | None = None) -> dict:
    """One per mapping pass. `in_pass_receipts` is mutated by `resolve_nomination` as the pass
    runs (the in-pass memoization store, audit §J); `prior_receipts` is supplied once by the
    caller and never mutated here -- it is the held-fixed/failure-fallback source (audit §L/§M/§N).
    Phase 19b: both are keyed by the composite `new_model_nomination_key(scope, request_context)`
    tuple, not by bare `scope` -- a caller building `prior_receipts` from a prior pass's own
    `in_pass_receipts` (e.g. `e2e.py`'s U1->U2 snapshot) already has the right key shape for free,
    since that dict was itself built the same way."""
    return {"policy": policy, "in_pass_receipts": {}, "prior_receipts": dict(prior_receipts or {})}


def _receipt_is_valid(receipt: dict | None, validate_prior_receipt) -> bool:
    if receipt is None:
        return False
    if validate_prior_receipt is None:
        # No validator supplied: fail closed. Never assume a prior receipt is still valid merely
        # because evidence is ordinarily append-only (audit §L: "do not merely assume that").
        return False
    return bool(validate_prior_receipt(receipt))


def _fallback_after_mechanical_failure(
    key: tuple, nomination_context: dict, validate_prior_receipt
) -> tuple[list[dict], str]:
    prior = nomination_context["prior_receipts"].get(key)
    if _receipt_is_valid(prior, validate_prior_receipt):
        return list(prior["accepted"]), "fresh_failed_fallback_to_prior"
    return [], "fresh_failed_no_valid_prior"


def resolve_nomination(
    scope: tuple[str, str, str] | None,
    *,
    request_context: str | None = None,
    candidate_rows: list[dict],
    category_description: str,
    model_name,
    make_fresh_call,
    nomination_context: dict | None,
    validate_prior_receipt=None,
) -> tuple[list[dict], str]:
    """The single Phase-19 orchestration checkpoint (audit §G/§19, request-identity corrected in
    Phase 19b): decides whether `scope` may make a fresh call this pass, whether an in-pass or
    prior-pass receipt should be reused instead, and records the outcome. Returns
    `(accepted_nominations, status)` where `status` is one of `fresh` / `fresh_no_candidates` /
    `memoized_in_pass` / `held_fixed_replay` / `held_fixed_no_valid_prior` /
    `fresh_failed_fallback_to_prior` / `fresh_failed_no_valid_prior` (audit §O's required
    distinctions; `fresh_no_candidates` added by the Phase-20 audit's §6/§8/§12 finding).

    `request_context` (Phase 19b, default `None`): the mapper's own pre-fork `root_key` --
    distinguishes several legitimate model-facing requests that share one AUTHORIZATION `scope`
    (the Phase-21-preflight finding: `build_multi_instances` partitions a `multi_instance=True`,
    no-parent-context requirement's real candidate units across several instances, each reaching
    the SAME `(child_id, requirement_id, role)` scope with a DIFFERENT, disjoint candidate pool --
    real q_aib c12 is the confirmed example, two units, two legitimate requests). AUTHORIZATION
    (`is_authorized_for_fresh_call`) is decided on `scope` ALONE, exactly as Phase 19 built it --
    `request_context` never enters that decision, only which receipt SLOT this invocation reads
    from or writes to. Every pre-Phase-19b caller omits it, giving every non-partitioned
    requirement the identical `None` context for its one-and-only request -- byte-identical
    behavior to before this phase.

    `fresh_no_candidates` (Phase 20b): when `scope` IS authorized for a fresh call but
    `candidate_rows` is empty, `make_fresh_call` is never invoked at all -- there is nothing to
    offer the model. Checked BEFORE `make_fresh_call`, not merely trusted to self-report an empty
    result, so this is mechanically distinguishable from "a physical call was made and legitimately
    returned nothing" (`fresh`, `accepted=[]`) without needing to inspect `candidates_offered`'s own
    length. Scoped strictly to the fresh-call branch: a HELD-FIXED scope's status is unaffected by
    the current candidate count (its own `candidates_offered` is still recorded for inspectability,
    but authorization and prior-receipt validity never depend on it).

    `make_fresh_call` is a zero-argument callable the CALLER binds to its own live/recorded/fake
    model client (e.g. `lambda: nominate_with_model(role_spec, units, model_client)`) -- this
    function never imports or knows about `sufficiency_mapping.nominate_with_model` itself,
    keeping this module one-directionally dependency-free of it (audit §19/§G). A mechanical
    failure from `make_fresh_call` (any raised exception) is caught here, never propagated --
    the model-nomination mapper must never crash on a transport failure (audit §N), and is isolated
    to THIS request slot alone -- it can never poison a sibling request_context's own receipt under
    the same scope.

    `nomination_context` and `scope` are both REQUIRED. This function is reached only once a
    caller has explicitly opted into Phase-19 scoping; the legacy, context-free path lives
    entirely in `sufficiency_mapping._bind_role_candidates`, which calls `make_fresh_call`'s
    equivalent (a direct `nominate_with_model` call) directly and never reaches this function at
    all when no `nomination_context` is supplied -- preserving byte-identical behavior for every
    existing caller without this function needing a redundant legacy branch (audit §A)."""
    if nomination_context is None:
        raise ValueError(
            "resolve_nomination requires an explicit nomination_context; a caller with no "
            "context should bypass this function entirely and call its own fresh-call path "
            "directly, preserving legacy (context-free) behavior unchanged"
        )
    if scope is None:
        raise ValueError("resolve_nomination requires a scope when a nomination_context is supplied")

    key = new_model_nomination_key(scope, request_context)
    fingerprint = request_fingerprint(category_description, candidate_rows)
    in_pass = nomination_context["in_pass_receipts"]

    if key in in_pass:
        existing = in_pass[key]
        if existing["request_fingerprint"] != fingerprint:
            raise RequestFingerprintMismatch(
                f"(scope={scope!r}, request_context={request_context!r}) was already resolved "
                f"earlier in this mapping pass with a different model-facing request (fingerprint "
                f"{existing['request_fingerprint']!r} != {fingerprint!r}) -- this is genuine "
                "same-slot drift within one memoization key, not legitimate multi-instance "
                "partitioning (which gets its own distinct request_context); investigate before "
                "proceeding."
            )
        return list(existing["accepted"]), "memoized_in_pass"

    policy = nomination_context["policy"]
    if is_authorized_for_fresh_call(policy, scope):
        if not candidate_rows:
            accepted, status = [], "fresh_no_candidates"
        else:
            try:
                accepted = make_fresh_call()
                status = "fresh"
            except Exception:
                accepted, status = _fallback_after_mechanical_failure(key, nomination_context, validate_prior_receipt)
    else:
        prior = nomination_context["prior_receipts"].get(key)
        if _receipt_is_valid(prior, validate_prior_receipt):
            accepted, status = list(prior["accepted"]), "held_fixed_replay"
        else:
            accepted, status = [], "held_fixed_no_valid_prior"

    in_pass[key] = new_nomination_receipt(
        scope,
        request_context=request_context,
        model_name=model_name,
        request_fingerprint=fingerprint,
        candidates_offered=candidate_rows,
        accepted=accepted,
        status=status,
    )
    return list(accepted), status


# ---------------------------------------------------------------------------------------------
# RecoveryTarget -> model-nomination scope projection (audit §P). Reads only the plain dict
# shape `sufficiency_recovery_targets.new_recovery_target` already produces -- no import of that
# module, so this stays usable even if a future RecoveryTarget-producing module replaces it.
# ---------------------------------------------------------------------------------------------


def model_scopes_for_recovery_target(target: dict, contract_by_child: dict) -> list[tuple[str, str, str]]:
    """Zero, one, or several scopes -- one per role named in `target["target_roles"]` that is
    actually `model_nomination_only` + permitted on the target's own requirement. Deliberately
    reads only `search_child_id`/`requirement_id`/`target_roles` -- never `target_id`, `reason`,
    `goal_mode`, or the target's own `scope` dict (audit §17: those describe the SEARCH
    obligation, not what the model is asked, and must never be folded into scope identity). An
    unknown child, requirement, or individual role name is skipped, never raised -- a RecoveryTarget
    is free to name a role this function can't resolve into a model scope; that's simply zero
    scopes for that role, not a defect in the target."""
    child_id = target["search_child_id"]
    requirement_id = target["requirement_id"]
    contract = contract_by_child.get(child_id)
    if contract is None:
        return []
    requirement = next((r for r in contract["requirements"] if r["id"] == requirement_id), None)
    if requirement is None:
        return []
    scopes: list[tuple[str, str, str]] = []
    for role in target["target_roles"]:
        spec = requirement["role_specs"].get(role)
        if spec is None:
            continue
        if spec["mapping_strategy"] == "model_nomination_only" and spec["model_nomination_permitted"]:
            scopes.append(new_model_nomination_scope(child_id, requirement_id, role))
    return scopes
