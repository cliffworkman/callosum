"""Layer A -- the generic, question/domain-agnostic semantic answer-sufficiency engine.

Pure: no model, no network, no database, no library access. This module contains zero
question- or domain-specific vocabulary -- no role name, no scientific concept, no q_aib
wording appears anywhere below. It knows only: requirement structures (atomic/relational/
cardinality, all descriptive labels -- see ``recompute_requirement``), role bindings,
evidence provenance, states, reason codes, quantifiers, role completion, direction/
effectiveness assessments, relationship verifiers, and run-level search-process bookkeeping.

A *contract* (built by Layer B, ``sufficiency_authoring.py``, for any question) declares, per
child, a list of ``SufficiencyRequirement`` dicts. This module's job is to compute, from a
contract plus a set of role-binding candidates the caller has already grounded, whether each
requirement is ``filled`` / ``partially_filled`` / ``missing`` / ``ambiguous`` -- never a score,
never a verdict on the literature as a whole.

No external scholarly method is implemented or operationalized here (see CREDIT-THE-LINEAGE.md);
this is original engineering scaffolding for evidence-bound completeness bookkeeping, not a
published method, so no lineage manifest applies.

Two axes that earlier drafts conflated, now separate (see the design doc):

* ``RoleCompletionSpec`` -- within ONE candidate instance, which roles must jointly be
  established for that instance to count as *complete*. ``exists`` means "at least one complete
  instance", never "one of several required roles happened to be found".
* ``instance_quantifier`` -- across complete instances, how many are enough.

The frozen contract (role specs, role completion, quantifier policy) never contains mutable,
per-run search-process facts (recovery budget, attempts made) -- those live in a caller-owned
``SearchStatus`` dict, joined at read time, never hashed into the contract. See
``frozen_view``/``contract_hash`` and ``compute_recovery_needed``.
"""

from __future__ import annotations

import copy
import hashlib
import json

# ---------------------------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------------------------

REQUIREMENT_KINDS = ("atomic", "relational", "cardinality")  # descriptive labels only; state
# computation dispatches on `role_completion` + `instance_quantifier`, never on `kind`.

REQUIREMENT_STATES = ("filled", "partially_filled", "missing", "ambiguous")  # never a score

REASON_CODES = (
    "not_found",  # no candidate for a required/alternative role in the searched scope yet
    "incomplete_instance",  # some required/alternative roles are filled, at least one is not
    "not_reported_in_current_evidence",  # a fact is established, but the specific requested
    # sub-fact (a sign, a category) isn't in the currently-verified evidence -- never "the
    # source doesn't have it"
    "speculative_only",  # only hedged/attempt-only language found
    "insufficient_specificity",  # evidence is generic, not a named/specific instance
    "category_missing",  # a required category has zero evidence
    "evidence_conflicting",  # verified evidence disagrees
)

INSTANCE_QUANTIFIER_POLICIES = (
    "exists",  # >=1 complete instance suffices
    "all_requested_categories",  # every named category needs its own complete instance
    "for_each_discovered_instance",  # every discovered instance-key needs its own complete pairing
    "at_least_n",  # a specific numeric floor (`quantifier_n`)
    "open_list",  # report what's supported in the inspected scope; never certifies exhaustive
    # completeness -- caps at `partially_filled`
)

MAPPING_STRATEGIES = (
    # A small, FIXED, engine-owned vocabulary. The engine dispatches its deterministic-first pass
    # on a role's DECLARED strategy name (see ``sufficiency_mapping.py``), never by inspecting or
    # pattern-matching the role's own label string -- that would be exactly the domain-ontology
    # leak this module promises not to have.
    "named_instrument_lexicon",
    "achieved_outcome_predicate",
    "explicit_category_terms",
    "direction_or_sign_pattern",
    "model_nomination_only",
)

CANDIDATE_SOURCES = ("deterministic_mapping", "model_mapping", "parent_context")

RELATIONSHIP_VERIFIERS = ("same_proposition", "contract_directed_links")

# Phase 32 / I1c: identity of the sufficiency layer's mapping, completion, recovery, stop-search and witness semantics.
# A produced map records the version under which it was computed.
#
# Versions (each identifies actual behaviour, not merely a label):
#   sufficiency-semantics-v1 (I1c, HEAD 144cc965 and earlier): inherited-referent containment is case-sensitive.
#       Every other behaviour existed before the constant.
#   sufficiency-semantics-v2 (I1d): inherited-referent containment is case-insensitive literal containment
#       (Unicode case folding of both the referent surface and the candidate quote, then the unchanged canonical
#       containment test). Whitespace, punctuation, hyphenation, morphology, aliases and paraphrase are NOT normalised
#       by this change. Direction is the v1 behaviour: first direction word per passage, literal sign only.
#   sufficiency-semantics-v3 (I3, CURRENT): v2 containment, plus direction observations carry an explicit target
#       (relation | operand:<role> | unknown | none) from the shared classifier (direction_target). Relation-level
#       direction requires a witnessed relation AND a relation-targeted direction sentence within that witness's
#       proposition. The single-operand fallback is removed (an unresolved sign with one realised operand is unknown).
#       Literal valence includes adverbial forms ("negatively associated"). Relation summaries count only
#       relation-eligible observations. Operand-level valence stays as observation metadata.
#   sufficiency-semantics-v4 (I2-2, CURRENT): v3 for every non-category mapping, direction, witness, effectiveness
#       and parent-context behaviour. For explicit_category_terms requirements (all_requested_categories only):
#       every admissible literal observation is collected and classified (category_polarity); the representative
#       binding is chosen by fixed polarity precedence; an instance is complete only when established_presence is
#       satisfied (at least one positive observation); an unsatisfied bound category yields a semantic_goal_unsatisfied
#       recovery target, terminal per target once its search completed. Historical v1-v3 keep first-match mapping.
#
# CURRENT is the only version new production accepts. SUPPORTED lists every version this code can READ; membership in
# it does not make a version current. Historical versions are readable only through an explicit historical path.
#
# INVARIANT (do not weaken): ANY future change to mapping derivation, binding admissibility, semantic satisfaction,
# relation completion semantics, recovery, stop-search, witness or direction/effectiveness semantics in this layer MUST
# bump SUFFICIENCY_SEMANTICS_VERSION. Authored contract changes need a new frozen contract version instead (Phase 31
# section 17). The two identify different things. Neither replaces the other.
SUFFICIENCY_SEMANTICS_V1 = "sufficiency-semantics-v1"
SUFFICIENCY_SEMANTICS_V2 = "sufficiency-semantics-v2"
SUFFICIENCY_SEMANTICS_V3 = "sufficiency-semantics-v3"
SUFFICIENCY_SEMANTICS_V4 = "sufficiency-semantics-v4"
SUFFICIENCY_SEMANTICS_VERSION = SUFFICIENCY_SEMANTICS_V4
HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS = frozenset(
    {SUFFICIENCY_SEMANTICS_V1, SUFFICIENCY_SEMANTICS_V2, SUFFICIENCY_SEMANTICS_V3}
)
SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS = (
    frozenset({SUFFICIENCY_SEMANTICS_VERSION}) | HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS
)
# Where the version is recorded: at the top level of every per-child contract in a produced map. The map keeps its
# child-keyed shape, which every existing consumer indexes by child.
SEMANTICS_VERSION_KEY = "sufficiency_semantics_version"


# I2-2: category semantics. Observation polarity strings mirror category_polarity's vocabulary (a test asserts the
# equality); the engine never imports or calls the classifier.
ESTABLISHED_PRESENCE = "established_presence"
CATEGORY_STRATEGY = "explicit_category_terms"
OBSERVATION_POSITIVE = "positive_finding"
OBSERVATION_NULL = "null_finding"
OBSERVATION_MENTIONED = "mentioned_only"
OBSERVATION_UNKNOWN = "unknown"


def is_category_requirement(requirement: dict) -> bool:
    """The v4 category machinery applies to a cardinality requirement whose every role is explicit_category_terms."""
    roles = list(requirement["role_specs"].values())
    return (
        requirement["instance_quantifier"] == "all_requested_categories"
        and bool(roles)
        and all(spec["mapping_strategy"] == CATEGORY_STRATEGY for spec in roles)
    )


def category_goal_satisfied(instance: dict) -> bool:
    """established_presence for one category instance: at least one positive observation. Unit order never decides.
    Fail closed: a v4 category instance must carry its observations."""
    observations = instance.get("category_observations")
    if observations is None:
        raise ValueError("a v4 category instance must carry category_observations")
    return any(obs["observation_polarity"] == OBSERVATION_POSITIVE for obs in observations)


def require_supported_semantics_version(version) -> str:
    """Fail-closed gate for every version-dispatched semantic entry point (I2-0).

    The caller names the version explicitly: only the top-level production caller selects the current constant,
    and nothing here infers it from omission. Membership in SUPPORTED means this code can READ the version, not
    that it is current."""
    if not isinstance(version, str) or version not in SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS:
        raise ValueError(f"unsupported sufficiency semantics version: {version!r}")
    return version


# ---------------------------------------------------------------------------------------------
# Builders -- plain dicts, mirroring hierarchy_contract.py's own house style
# ---------------------------------------------------------------------------------------------


def new_role_spec(
    role: str,
    category_description: str,
    mapping_strategy: str,
    *,
    disqualifying_guards=(),
    model_nomination_permitted: bool = True,
    requested_category_terms=(),
    source_wording_span: str = "",
    support_policy: dict | None = None,
) -> dict:
    """``requested_category_terms`` (I4-1e revision 2, section 11-13): historically populated only for
    ``explicit_category_terms`` roles, naming the closed category values a role searches for. Its documented
    contract is now generalized, WITHOUT a rename (judged not strictly necessary) and WITHOUT any new validation
    tying it to ``mapping_strategy``: verbatim requested target terms/phrases, optionally supplied by ANY
    strategy that supports target-aware local disambiguation -- today that is also
    ``achieved_outcome_predicate``, for disambiguating among several already-locally-valid candidate assertions
    sharing one passage (never to broaden what counts as a match, establish relevance, or establish authority;
    see :func:`reference_future_requested_terms_disambiguation`). No production mapping call site reads it for
    that strategy yet.

    ``support_policy`` (I4-1g, new, OPTIONAL): a requirement-side evidence-admissibility schema object (see
    :func:`new_support_policy`), validated/canonicalized when explicitly supplied. When omitted, the historical
    seven-key ``RoleSpec`` shape is produced EXACTLY as before -- this key is never materialized as a default or
    ``None`` placeholder (section 9's load-bearing compatibility rule). The DEFAULT admissibility predicate a role
    without an explicit policy will fall back to remains future I4-2 production behaviour, not schema data, and
    is not computed, inferred, or authored here."""
    if mapping_strategy not in MAPPING_STRATEGIES:
        raise ValueError(f"unknown mapping_strategy: {mapping_strategy!r}")
    spec = {
        "role": role,
        "category_description": category_description,
        "mapping_strategy": mapping_strategy,
        "disqualifying_guards": list(disqualifying_guards),
        "model_nomination_permitted": bool(model_nomination_permitted),
        "requested_category_terms": list(requested_category_terms),
        "source_wording_span": source_wording_span,
    }
    if support_policy is not None:
        spec["support_policy"] = _canonical_support_policy(support_policy)
    return spec


def new_role_completion(*, required_roles=(), alternative_role_groups=(), optional_roles=()) -> dict:
    return {
        "required_roles": list(required_roles),
        "alternative_role_groups": [list(g) for g in alternative_role_groups],
        "optional_roles": list(optional_roles),
    }


def completion_roles(role_completion: dict) -> list[str]:
    """Every role that participates in the completeness judgment (required + alternatives),
    in a stable order. `optional_roles` never gate completion and are excluded."""
    out = list(role_completion["required_roles"])
    for group in role_completion["alternative_role_groups"]:
        for role in group:
            if role not in out:
                out.append(role)
    return out


def new_role_binding(
    role: str,
    *,
    state: str = "missing",
    reason: str | None = None,
    proposition_id: str | None = None,
    exact_text: str | None = None,
    provenance: dict | None = None,
    guard: dict | None = None,
) -> dict:
    if state not in REQUIREMENT_STATES[:1] + ("missing", "ambiguous"):
        # a role binding is never itself "partially_filled" -- that's an instance/requirement-level state
        if state not in ("filled", "missing", "ambiguous"):
            raise ValueError(f"invalid role-binding state: {state!r}")
    return {
        "role": role,
        "state": state,
        "reason": reason,
        "proposition_id": proposition_id,
        "exact_text": exact_text,
        "provenance": provenance or {"candidate_source": None, "detail": "", "model": None},
        "guard": guard or {},
    }


def new_direction_assessment(
    *,
    reported: bool = False,
    sign: str | None = None,
    required_sign: str | None = None,
    causal_language_present: bool = False,
    proposition_id: str | None = None,
    exact_text: str | None = None,
) -> dict:
    return {
        "reported": bool(reported),
        "sign": sign,
        "required_sign": required_sign,
        "causal_language_present": bool(causal_language_present),
        "proposition_id": proposition_id,
        "exact_text": exact_text,
    }


DIRECTION_TARGETS = ("relation", "operand", "unknown", "none")


def new_targeted_direction_assessment(
    *,
    sign: str | None,
    required_sign: str | None,
    causal_language_present: bool,
    proposition_id: str | None,
    exact_text: str,
    target: str,
    target_role: str | None,
    target_reason: str,
    relation_eligible: bool,
) -> dict:
    """A v3 direction observation (I3). ``exact_text`` is the classified SENTENCE, not the bare direction word. The
    observation is provenance: its target is deterministic, never model-authored, and carries no confidence.
    ``relation_eligible`` is True only when the sentence targets the relation AND the observation's proposition is
    within the instance's relation witness evidence."""
    if target not in DIRECTION_TARGETS:
        raise ValueError(f"invalid direction target: {target!r}")
    if target == "operand" and not target_role:
        raise ValueError("an operand-targeted direction observation must name its operand role")
    if target != "operand" and target_role is not None:
        raise ValueError("only an operand-targeted direction observation may carry a target role")
    return {
        "reported": True,
        "sign": sign,
        "required_sign": required_sign,
        "causal_language_present": bool(causal_language_present),
        "proposition_id": proposition_id,
        "exact_text": exact_text,
        "target": target,
        "target_role": target_role,
        "target_reason": target_reason,
        "relation_eligible": bool(relation_eligible) and target == "relation",
    }


def new_effectiveness_assessment(
    *,
    outcome_reported: bool = False,
    conclusion: str | None = None,
    proposition_id: str | None = None,
    exact_text: str | None = None,
) -> dict:
    if conclusion is not None and conclusion not in ("supported", "not_supported", "mixed"):
        raise ValueError(f"invalid effectiveness conclusion: {conclusion!r}")
    return {
        "outcome_reported": bool(outcome_reported),
        "conclusion": conclusion,
        "proposition_id": proposition_id,
        "exact_text": exact_text,
    }


def new_instance(instance_key: str | None = None) -> dict:
    return {
        "instance_key": instance_key,
        "role_bindings": {},
        "complete": False,
        "state": "missing",
        "reason": None,
        # Phase 18: instance-grounded, multi-observation direction/effectiveness (replaced from
        # scratch by `sufficiency_diagnostic.compute_direction_and_effectiveness`, never appended
        # to). Always present, even on a requirement that never declares either field -- they just
        # stay empty forever for such a requirement, matching the uniform-default-shape house style
        # (`role_bindings`/`complete` are unconditionally present too).
        "direction_observations": [],
        "effectiveness_observations": [],
    }


def new_requirement(
    req_id: str,
    kind: str,
    role_specs: dict,
    role_completion: dict,
    instance_quantifier: str,
    *,
    quantifier_n: int | None = None,
    relationship_verifiers=("same_proposition",),
    multi_instance: bool = False,
    parent_context_roles=(),
    direction: dict | None = None,
    effectiveness: dict | None = None,
    empty_result_semantically_allowed: bool = False,
    source_wording_span: str = "",
) -> dict:
    if kind not in REQUIREMENT_KINDS:
        raise ValueError(f"unknown kind: {kind!r}")
    if instance_quantifier not in INSTANCE_QUANTIFIER_POLICIES:
        raise ValueError(f"unknown instance_quantifier: {instance_quantifier!r}")
    if instance_quantifier == "at_least_n" and not quantifier_n:
        raise ValueError("at_least_n requires quantifier_n")
    declared_roles = set(role_specs)
    used_roles = set(completion_roles(role_completion)) | set(role_completion["optional_roles"])
    missing_specs = used_roles - declared_roles
    if missing_specs:
        raise ValueError(f"role(s) {sorted(missing_specs)} used in role_completion but have no RoleSpec")
    for verifier in relationship_verifiers:
        if verifier not in RELATIONSHIP_VERIFIERS:
            raise ValueError(f"unknown relationship verifier: {verifier!r}")
    return {
        "id": req_id,
        "kind": kind,
        "role_specs": copy.deepcopy(role_specs),
        "role_completion": copy.deepcopy(role_completion),
        "instance_quantifier": instance_quantifier,
        "quantifier_n": quantifier_n,
        "relationship_verifiers": list(relationship_verifiers),
        "multi_instance": bool(multi_instance),
        "instances": [],
        "parent_context_roles": list(parent_context_roles),
        "direction": direction,
        "effectiveness": effectiveness,
        # Phase 18: runtime-only DERIVED views over instance-level observations (never a second
        # source of truth, never mutated into the authored `direction`/`effectiveness` template
        # above -- see `sufficiency_engine.summarize_observations` /
        # `sufficiency_diagnostic.compute_direction_and_effectiveness`).
        "direction_summary": None,
        "effectiveness_summary": None,
        "empty_result_semantically_allowed": bool(empty_result_semantically_allowed),
        "source_wording_span": source_wording_span,
        "state": "missing",
        "reason": "not_found",
    }


def new_contract(child_id: str, requirements: list[dict]) -> dict:
    return {"child_id": child_id, "requirements": copy.deepcopy(requirements)}


# ---------------------------------------------------------------------------------------------
# Frozen contract vs. per-run search state (never mixed; never hashed together)
# ---------------------------------------------------------------------------------------------

_RUNTIME_ONLY_KEYS = frozenset({"instances", "state", "reason", "direction_summary", "effectiveness_summary"})


def frozen_view(contract: dict) -> dict:
    """The contract's own definitional content -- role specs, role completion, quantifier
    policy, direction/effectiveness declarations -- with every run-populated field stripped.
    This is what gets hashed; it is identical whether or not mapping has ever been run, and
    identical across runs with different recovery budgets (those never appear here at all)."""
    out = {"child_id": contract["child_id"], "requirements": []}
    for req in contract["requirements"]:
        stripped = {k: v for k, v in req.items() if k not in _RUNTIME_ONLY_KEYS}
        out["requirements"].append(stripped)
    return out


def contract_hash(contract: dict) -> str:
    canonical = json.dumps(frozen_view(contract), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_instance_key(role_bindings: dict, *, root_key: str | None = None) -> str:
    """Deterministic, content-derived instance identity. Two instances with different bound
    content always get different keys; identical content always gets the same key across a
    deterministic replay (same canonical-hash discipline as `contract_hash` above).

    Exists specifically because a positional/index-based fork-suffix scheme (e.g.
    ``f"{parent_key}#{index}"``) can collide: when two roles in one requirement independently
    fork from a shared ancestor instance, two DIFFERENT final instances can end up computing the
    same local index at the same nesting depth even though their actual bound content differs
    (found live in the Phase 2 diagnostic's own replay -- see `MODEL_NOMINATION_DIAGNOSTIC_
    RESULTS.md` Finding 1). Deriving the key from the instance's own final content instead of its
    fork lineage/position makes two differently-bound instances structurally unable to collide.

    `root_key`: the instance's pre-fork identity (a multi-instance base's `unit_id`, or `None` for
    a single-instance requirement) -- kept as a human-legible prefix only; it is NEVER itself the
    uniqueness guarantee (two instances forked from the SAME root_key with different content must
    still diverge, which the content hash below provides).

    Deliberately NOT the same notion as a physical evidence anchor (paper/chunk/span) -- that is
    proposition/evidence identity, a separate axis from semantic-instance identity. Collapsing
    instances that share an anchor is `nominate_with_model`'s own dedup step, upstream of this
    function; this function only ever makes ALREADY-DECIDED distinct instances non-collidingly
    identifiable, never decides which instances should exist.
    """
    canonical = {
        role: {
            "state": binding.get("state"),
            "proposition_id": binding.get("proposition_id"),
            "exact_text": binding.get("exact_text"),
        }
        for role, binding in sorted(role_bindings.items())
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    prefix = root_key if root_key is not None else "i"
    return f"{prefix}::{digest}"


def new_search_status(
    requirement_id: str,
    *,
    configured_recovery_budget: int = 1,
    attempts_made: int = 0,
    recovery_budget_exhausted: bool = False,
    scoped_search_completed_no_additional_support: bool = False,
    breadth_pass_used: bool = False,
) -> dict:
    """RUN-LEVEL only. Never part of a SufficiencyContract; never hashed with it (see
    `contract_hash`). `breadth_pass_used` matters only for `open_list` requirements -- see
    `compute_recovery_needed`."""
    return {
        "requirement_id": requirement_id,
        "configured_recovery_budget": configured_recovery_budget,
        "attempts_made": attempts_made,
        "recovery_budget_exhausted": bool(recovery_budget_exhausted),
        "scoped_search_completed_no_additional_support": bool(scoped_search_completed_no_additional_support),
        "breadth_pass_used": bool(breadth_pass_used),
    }


# ---------------------------------------------------------------------------------------------
# I4-1g (I4-1e revision 2) -- pure, BACKWARD-COMPATIBLE SCHEMA PRIMITIVES for a future evidence-
# provenance/support-admissibility layer. NOTHING below this line is wired into
# `recompute_instance`/`recompute_requirement`, any mapping call site, or any production
# satisfaction/recovery/relation/direction/effectiveness/AnswerPlan path -- confirmed by the static
# guards in `test_sufficiency_support_schema.py`. Builders only: they validate and serialize
# already-decided values, and decide nothing themselves.
#
# This module imports nothing from the I4-1 pure/unwired classifier family's two sibling modules
# (and must not -- doing so would itself be a production reference, tripping their own unwired
# guards, which a plain substring scan of this file's own source also respects, deliberately kept
# out of every comment and docstring below). The three closed vocabularies here therefore exist
# independently, matching that family's own output values by STRING CONVENTION only:
# `current_document`/`attributed_external`/`unresolved` mirror its per-assertion relation values;
# `literature_synthesis`/`non_synthetic_or_unspecified` mirror its aggregation values; the five
# `SUPPORT_ASSERTION_KINDS` mirror its assertion-kind values (`unknown` included, for an assertion
# whose kind could not be determined). A future I4-2 integration is what would actually connect
# these two independently-true vocabularies; nothing here asserts or needs that connection to hold
# today.
# ---------------------------------------------------------------------------------------------

SUPPORT_ASSERTION_RELATIONS = ("current_document", "attributed_external", "unresolved")
SUPPORT_AGGREGATIONS = ("literature_synthesis", "non_synthetic_or_unspecified")
AGGREGATION_REQUIREMENTS = ("any", "require_synthesis", "exclude_synthesis")
SUPPORT_ASSERTION_KINDS = ("result", "method_or_description", "aim_or_hypothesis", "interpretation", "unknown")
SUPPORT_AUTHORITY_VETOES = (None, "negated_result_predicate", "absence_of_evidence")
CANDIDATE_SUPPORT_INADMISSIBILITY_REASONS = (None, "support_policy_excluded", "assertion_attachment_ambiguous")


def new_support_policy(
    *,
    allowed_assertion_relations=SUPPORT_ASSERTION_RELATIONS,
    aggregation_requirement: str = "any",
    allowed_assertion_kinds=("result",),
) -> dict:
    """Pure schema/builder for a future requirement-side support-admissibility policy (I4-1e revision 2,
    section 7/E4). NOT evaluated anywhere in this module, and not consumed by `recompute_instance`/
    `recompute_requirement` or any mapping call site -- a data contract only, for a future I4-2 integration.

    Canonicalizes ordering: both list inputs are deduplicated and sorted, so two policies built from
    differently-ordered but equal inputs always serialize identically. Rejects any value outside the closed
    vocabularies above, and rejects an EMPTY relation or kind set -- a policy admitting nothing is nonsensical,
    never a legitimate authored choice. Makes no inference from question text, and contains no q_aib/domain
    vocabulary anywhere in this function; its own keyword defaults are a usable, question-agnostic SCHEMA
    example, never the future I4-2 default-admissibility predicate itself (see the module notes for I4-1g)."""
    relations = sorted(set(allowed_assertion_relations))
    kinds = sorted(set(allowed_assertion_kinds))
    if not relations:
        raise ValueError("allowed_assertion_relations must not be empty")
    if not kinds:
        raise ValueError("allowed_assertion_kinds must not be empty")
    for relation in relations:
        if relation not in SUPPORT_ASSERTION_RELATIONS:
            raise ValueError(f"unknown assertion_relation: {relation!r}")
    if aggregation_requirement not in AGGREGATION_REQUIREMENTS:
        raise ValueError(f"unknown aggregation_requirement: {aggregation_requirement!r}")
    for kind in kinds:
        if kind not in SUPPORT_ASSERTION_KINDS:
            raise ValueError(f"unknown assertion_kind: {kind!r}")
    return {
        "allowed_assertion_relations": relations,
        "aggregation_requirement": aggregation_requirement,
        "allowed_assertion_kinds": kinds,
    }


_SUPPORT_POLICY_KEYS = frozenset({"allowed_assertion_relations", "aggregation_requirement", "allowed_assertion_kinds"})


def _canonical_support_policy(policy: dict) -> dict:
    """Validate and canonicalize a hand-authored ``support_policy`` dict to exactly what
    :func:`new_support_policy` would have produced from the same values. Used only by
    :func:`new_role_spec` when ``support_policy`` is explicitly supplied; never called when it is omitted."""
    if not isinstance(policy, dict) or set(policy) != _SUPPORT_POLICY_KEYS:
        raise ValueError(f"support_policy must have exactly the three declared fields: {policy!r}")
    return new_support_policy(
        allowed_assertion_relations=policy["allowed_assertion_relations"],
        aggregation_requirement=policy["aggregation_requirement"],
        allowed_assertion_kinds=policy["allowed_assertion_kinds"],
    )


def new_candidate_support(
    *,
    proposition_id,
    exact_text,
    assertion_relation: str,
    aggregation: str,
    assertion_kind: str,
    admissible: bool,
    assertion_span=None,
    predicate_span=None,
    content_span=None,
    support_label: str | None = None,
    authority_veto: str | None = None,
    is_caption: bool = False,
    attachment_ambiguous: bool = False,
    inadmissibility_reason: str | None = None,
) -> dict:
    """Pure DATA CONTRACT for one future candidate-support record (I4-1e revision 2, section 4/6). Validates
    and serializes already-computed values; this builder itself must never classify text, call any I4-1
    classifier, decide admissibility, mutate requirement state, or choose a representative -- every value is
    supplied by the (future, not-yet-built) caller that already decided it.

    No `authoritative`/`candidate` ``finding_authority`` vocabulary is serialized here -- I4-1e revision 2's own
    recommendation is that a downstream consumer need not re-expose that coarse field at all, since
    ``assertion_relation`` already carries its ownership information without the real naming-collision risk that
    value's literal ``"candidate"`` string would otherwise create next to this codebase's unrelated AI-funnel
    sense of the same word (``paper_findings.kind="candidate"``). ``authority_veto``/``is_caption`` are retained,
    as properties of this specific (assertion, target) binding attempt, not of the assertion alone."""
    if assertion_relation not in SUPPORT_ASSERTION_RELATIONS:
        raise ValueError(f"unknown assertion_relation: {assertion_relation!r}")
    if aggregation not in SUPPORT_AGGREGATIONS:
        raise ValueError(f"unknown aggregation: {aggregation!r}")
    if assertion_kind not in SUPPORT_ASSERTION_KINDS:
        raise ValueError(f"unknown assertion_kind: {assertion_kind!r}")
    if authority_veto not in SUPPORT_AUTHORITY_VETOES:
        raise ValueError(f"unknown authority_veto: {authority_veto!r}")
    if inadmissibility_reason not in CANDIDATE_SUPPORT_INADMISSIBILITY_REASONS:
        raise ValueError(f"unknown inadmissibility_reason: {inadmissibility_reason!r}")
    if admissible and inadmissibility_reason is not None:
        raise ValueError("an admissible candidate must not carry an inadmissibility_reason")
    if not admissible and inadmissibility_reason is None:
        raise ValueError("an inadmissible candidate must carry an inadmissibility_reason")
    return {
        "proposition_id": proposition_id,
        "exact_text": exact_text,
        "assertion_span": assertion_span,
        "predicate_span": predicate_span,
        "content_span": content_span,
        "assertion_relation": assertion_relation,
        "aggregation": aggregation,
        "assertion_kind": assertion_kind,
        "support_label": support_label,
        "authority_veto": authority_veto,
        "is_caption": bool(is_caption),
        "attachment_ambiguous": bool(attachment_ambiguous),
        "admissible": bool(admissible),
        "inadmissibility_reason": inadmissibility_reason,
    }


_CANDIDATE_SUPPORT_KEYS = frozenset(
    {
        "proposition_id",
        "exact_text",
        "assertion_span",
        "predicate_span",
        "content_span",
        "assertion_relation",
        "aggregation",
        "assertion_kind",
        "support_label",
        "authority_veto",
        "is_caption",
        "attachment_ambiguous",
        "admissible",
        "inadmissibility_reason",
    }
)


def new_candidate_supports(records: list[dict]) -> list[dict]:
    """An ORDERED list of candidate-support records (I4-1e revision 2, section 6/8/12). Preserves the caller's
    own traversal order exactly -- list position is NEVER semantically meaningful here (never a ranking by
    directness, never a chosen "winner"; see `reference_future_role_state` for how a future role STATE is meant
    to read this list without depending on order). Validates that every record has exactly the shape
    `new_candidate_support` produces; does not drop, reorder, rank, or filter any record -- "contains every
    relevant locally-valid candidate supplied to it" is enforced by refusing anything malformed, not by
    re-deciding relevance itself. Returns a fresh list (never aliases the caller's own)."""
    out = []
    for record in records:
        if not isinstance(record, dict) or set(record) != _CANDIDATE_SUPPORT_KEYS:
            raise ValueError(
                f"candidate-support record has an unexpected shape: {sorted(record) if isinstance(record, dict) else record!r}"
            )
        out.append(dict(record))
    return out


def reference_future_role_state(candidate_supports: list[dict]) -> tuple[str, str | None]:
    """REFERENCE ONLY -- freezes the I4-1e revision 2 section 6/10 future role-state aggregation contract for
    this increment's own tests (`test_sufficiency_support_schema.py`). NOT called by `recompute_instance`/
    `recompute_requirement` or any production path; a static guard proves this.

    Future I4-2 semantics, exactly: ``"filled"`` iff at least one relevant candidate is admissible;
    ``"ambiguous"`` iff no candidate is admissible AND at least one relevant candidate is blocked specifically
    because assertion attachment is ambiguous; ``"missing"`` otherwise. Policy-excluded evidence alone never
    creates ambiguity -- a role with only `support_policy_excluded` candidates aggregates to plain `"missing"`,
    not `"ambiguous"`. One ambiguous candidate never poisons another, separate, unambiguous admissible support:
    `"filled"` is checked FIRST, unconditionally on the presence of any admissible candidate regardless of what
    else the list also contains. The exact production reason-code mapping for the `"missing"` case is future
    I4-2 work, not decided here."""
    if any(candidate["admissible"] for candidate in candidate_supports):
        return "filled", None
    if any(candidate["inadmissibility_reason"] == "assertion_attachment_ambiguous" for candidate in candidate_supports):
        return "ambiguous", "assertion_attachment_ambiguous"
    return "missing", None


def reference_future_requested_terms_disambiguation(candidates: list[dict], requested_terms: list[str]) -> dict | None:
    """REFERENCE ONLY -- freezes the future `requested_category_terms` disambiguation contract for
    `achieved_outcome_predicate` roles (I4-1e revision 2, section 10/12/13). NOT called by production mapping.

    Literal containment only -- no fuzzy matching, no embeddings, no model call, no synonym expansion, no
    stemming (a future production wiring would reuse `sufficiency_mapping.py`'s own existing canonical-containment
    discipline; this reference helper intentionally does not import across the I4-1 classifier family's own
    unwired boundary to reuse it, even for a test-only reference). Each candidate dict
    must carry its own ``exact_text``. Returns the single candidate whose ``exact_text`` contains at least one
    requested term, when EXACTLY one candidate qualifies. Returns ``None`` (no disambiguation) when the term
    list is empty, when zero candidates qualify, or when more than one does -- never a first-match fallback."""
    if not requested_terms:
        return None
    matching = [
        candidate
        for candidate in candidates
        if any(term and term in candidate["exact_text"] for term in requested_terms)
    ]
    if len(matching) == 1:
        return matching[0]
    return None


# ---------------------------------------------------------------------------------------------
# Relationship verifiers -- joint-grounding for any 2+ jointly-required roles (§ role completion)
# ---------------------------------------------------------------------------------------------


def _support_set(binding: dict) -> set:
    """The full proposition-support set a binding represents for `same_proposition` joint-
    grounding -- `supporting_proposition_ids` (the Phase 3 anchor-dedup's own provenance field,
    present only on a model-sourced binding that collapsed 2+ same-anchor propositions) UNION the
    binding's own primary `proposition_id`, never the primary ALONE. The primary stays the
    deterministic citation/provenance representative; it must not by itself narrow the semantic
    support the binding actually carries (Phase 3's own `MODEL_NOMINATION_DIAGNOSTIC_RESULTS.md`/
    `PHASE3_BOUNDED_FIXES_RESULTS.md` finding: two jointly-required bindings collapsed to
    DIFFERENT primaries from the SAME anchor-duplicate pair could spuriously fail this check even
    though they share real, recorded proposition support). A binding with no `supporting_
    proposition_ids` (every deterministic binding, and every model binding that never needed to
    collapse anything) degrades to exactly `{proposition_id}` -- byte-identical to the pre-fix
    check for every such binding."""
    proposition_id = binding.get("proposition_id")
    supporting = binding.get("provenance", {}).get("supporting_proposition_ids")
    support = set(supporting) if supporting else set()
    if proposition_id is not None:
        support.add(proposition_id)
    return support


def _verify_same_proposition(role_bindings: dict, roles: list[str]) -> bool:
    """TRUE iff every role's own proposition-support set (see `_support_set`) shares at least one
    common proposition_id -- the natural N-way generalization of "all roles cite the identical
    proposition": when every binding's support set is a singleton (the universal case before
    Phase 3's dedup existed), this is byte-identical to the original literal-equality check.
    Deliberately still proposition-identity, never evidence-ANCHOR identity -- a physical anchor
    co-occurrence alone never satisfies this (see the module's own adversarial tests)."""
    support_sets = [_support_set(role_bindings[r]) for r in roles]
    if any(not s for s in support_sets):
        return False
    return bool(set.intersection(*support_sets))


def _verify_contract_directed_links(role_bindings: dict, roles: list[str], *, context: dict | None = None) -> bool:
    """One AVAILABLE verifier, never the universal mechanism (see the design doc). Reuses
    `contract_directed/links.py`'s closed designator kinds (definition/acronym, shared
    designator, explicit reference) when the caller supplies enough context to check them.

    `contract_directed/links.py`'s full `find_links`/`verify_link` operate over document-chunk
    `attachment_pieces` (section/page-scoped text) that a sealed-ledger-only sufficiency pass
    does not carry by default. Without that context this returns False -- an honest "not
    applicable here", never a silent pass -- rather than reimplementing a narrower, unverified
    substitute. When `context["attachment_pieces"]` is supplied, this checks the lightweight,
    real sub-case: the same extracted designator (instrument name, acronym, or explicit label)
    appears in more than one role's own `exact_text`, which is exactly `links.py`'s
    `shared_designator` basis applied to role-bound spans instead of finding-vs-attachment spans.
    """
    if not context or not context.get("attachment_pieces"):
        return False
    from experiments.ask_cli_revised.contract_directed import links as _links

    texts = [role_bindings[r].get("exact_text") for r in roles]
    if any(not t for t in texts):
        return False
    designator_sets = [{d.surface.lower() for d in _links.extract_designators(t)} for t in texts]
    shared = set.intersection(*designator_sets) if designator_sets else set()
    return bool(shared)


_VERIFIER_FUNCS = {
    "same_proposition": _verify_same_proposition,
    "contract_directed_links": _verify_contract_directed_links,
}


def _joint_grounded(
    role_bindings: dict, roles: list[str], verifiers: list[str], *, context: dict | None = None
) -> bool:
    if len(roles) < 2:
        return True  # nothing to jointly ground
    for name in verifiers:
        fn = _VERIFIER_FUNCS[name]
        try:
            ok = fn(role_bindings, roles, context=context) if name != "same_proposition" else fn(role_bindings, roles)
        except TypeError:
            ok = fn(role_bindings, roles)
        if ok:
            return True
    return False


def own_evidence_roles(role_completion: dict, bindings: dict) -> list[str]:
    """Every role (from `completion_roles`) whose binding is `filled` and NOT itself
    `parent_context`-sourced -- the exact filter `recompute_instance` applies before its own
    joint-grounding check, extracted here (Phase 18) so other consumers (`relationship_witness_
    support_ids` below) reuse the identical semantics rather than re-deriving a second, driftable
    copy. A pure function of `bindings`; does not depend on whether the instance is complete."""
    roles_in_play = completion_roles(role_completion)
    return [
        r
        for r in roles_in_play
        if bindings.get(r, {}).get("state") == "filled"
        and bindings[r].get("provenance", {}).get("candidate_source") != "parent_context"
    ]


def relationship_witness_support_ids(
    role_completion: dict, bindings: dict, relationship_verifiers: list[str], *, context: dict | None = None
) -> set[str]:
    """The proposition ids that actually WITNESS this instance's own-evidence relationship, for
    annotating direction/effectiveness (Phase 18) -- never a naive union of every own-evidence
    role's own support. A parent-context binding never contributes: it supplies trusted background
    identity (e.g. which brain region a relationship concerns), never evidence this child itself
    retrieved for the relationship's own valence/outcome.

    0 own-evidence roles: empty (nothing to annotate with).
    Exactly 1: that role's own `_support_set` -- no joint-grounding question arises.
    2+: completion already required them to be JOINTLY grounded (the same `_joint_grounded` check
    `recompute_instance` runs) -- the witness is the proposition-level intersection
    `_verify_same_proposition` itself computes, never the union of each role's independent support.
    A proposition that merely supports ONE ingredient role, without being the shared proposition
    that ties the relationship together, must not be allowed to supply the relationship's own
    direction/effectiveness (the adversarial case: role A's support is {p1,p2}, role B's is
    {p1,p3}; only p1 -- the shared witness -- is admissible; p2/p3 are not, even though each
    independently supports one role). If 2+ own-evidence roles were jointly grounded through a
    verifier that establishes no single shared proposition (`contract_directed_links`, link-based,
    not proposition-based -- unreachable in the current pipeline since no real call site ever
    supplies `context["attachment_pieces"]`, confirmed by direct grep), this returns empty rather
    than guessing or falling back to union: there is no proposition-level witness to annotate
    with."""
    roles = own_evidence_roles(role_completion, bindings)
    if not roles:
        return set()
    support_sets = [_support_set(bindings[r]) for r in roles]
    if len(roles) == 1:
        return support_sets[0]
    if any(not s for s in support_sets):
        return set()
    return set.intersection(*support_sets)


def _observation_sort_key(key):
    # `instance_key` may be `None` (an unforked single instance) -- sort None after every real
    # string key rather than raising `TypeError` on a mixed None/str comparison.
    return (key is None, key)


def counts_toward_relation_direction(observation: dict) -> bool:
    """Whether a direction observation counts toward a RELATION-level direction summary and admits its proposition to the
    direction ParentClaim. A v3 (targeted) observation counts only when it is relation-eligible. An untargeted v1/v2
    observation carries no ``target`` key and counts as recorded by its version, which keeps the historical summary exact."""
    if "target" not in observation:
        return True
    return observation.get("relation_eligible") is True


def summarize_observations(instances: list[dict], obs_key: str, value_key: str, *, observation_filter=None) -> dict:
    """A DERIVED VIEW only (Phase 18) -- never a second source of truth -- over COMPLETE
    instances' own `obs_key` observation lists (`"direction_observations"` /
    `"effectiveness_observations"`), reading `value_key` (`"sign"` / `"conclusion"`) from each.
    Within-instance conflict and across-instance heterogeneity are kept fully orthogonal facts,
    never collapsed into one "heterogeneous" fallback enum: a single internally-conflicted
    instance is NOT, by itself, across-instance heterogeneity, and both can co-occur. An
    INCOMPLETE instance never contributes here (Phase 16's own established principle: a partially-
    established candidate instance stays visible as diagnostic metadata without being promoted
    into a trusted downstream semantic conclusion) -- its own `obs_key` list, if any, is computed
    and stored on the instance regardless, just excluded from this summary."""
    complete = [i for i in instances if i["complete"]]
    complete_keys = sorted((i["instance_key"] for i in complete), key=_observation_sort_key)
    with_obs: list = []
    missing: list = []
    conflicted: list = []
    resolved_values: dict = {}
    for inst in complete:
        key = inst["instance_key"]
        values = {
            o[value_key]
            for o in inst.get(obs_key, [])
            if o.get(value_key) is not None and (observation_filter is None or observation_filter(o))
        }
        if not values:
            missing.append(key)
            continue
        with_obs.append(key)
        if len(values) == 1:
            resolved_values[key] = next(iter(values))
        else:
            conflicted.append(key)
    resolved = list(resolved_values.values())
    observed_values = sorted(set(resolved))
    has_conflict = bool(conflicted)
    has_heterogeneity = len(set(resolved)) > 1
    consensus_value = observed_values[0] if len(observed_values) == 1 and not has_conflict else None
    return {
        "observed_values": observed_values,
        "consensus_value": consensus_value,
        "has_within_instance_conflict": has_conflict,
        "has_across_instance_heterogeneity": has_heterogeneity,
        "complete_instance_keys": complete_keys,
        "instance_keys_with_observations": sorted(with_obs, key=_observation_sort_key),
        "instance_keys_missing_observations": sorted(missing, key=_observation_sort_key),
        "conflicted_instance_keys": sorted(conflicted, key=_observation_sort_key),
    }


# ---------------------------------------------------------------------------------------------
# State computation -- pure, dispatched by role_completion + instance_quantifier only
# ---------------------------------------------------------------------------------------------


def recompute_instance(
    role_completion: dict,
    instance: dict,
    relationship_verifiers: list[str],
    *,
    context: dict | None = None,
    semantics_version: str,
    goal_gate: bool = False,
) -> dict:
    """Pure: returns a NEW instance dict with `complete`/`state`/`reason` derived from
    `role_bindings`. `exists` (at the requirement level) means "at least one instance for which
    this returns complete=True" -- never "one role happened to be found"."""
    require_supported_semantics_version(semantics_version)
    bindings = instance["role_bindings"]
    required = role_completion["required_roles"]
    alt_groups = role_completion["alternative_role_groups"]

    def filled(role):
        return bindings.get(role, {}).get("state") == "filled"

    required_ok = all(filled(r) for r in required)
    alt_ok = all(any(filled(r) for r in group) for group in alt_groups)
    complete = required_ok and alt_ok
    if goal_gate:
        if semantics_version != SUFFICIENCY_SEMANTICS_V4:
            raise ValueError("the category goal gate is a v4 rule")
        complete = complete and category_goal_satisfied(instance)

    roles_in_play = completion_roles(role_completion)
    if complete:
        # Parent-context roles are trusted as background context, not evidence this child itself
        # retrieved -- they can never by themselves complete an instance (a required/alternative
        # role check already enforces that), and they structurally cannot share a proposition
        # with anything this child retrieves. Joint grounding (§ relational-binding semantics)
        # therefore applies only among roles this child's OWN evidence actually filled; a single
        # own-evidence role paired with trusted parent context needs nothing further to link, but
        # two or more OWN roles must still be shown to co-occur in evidence that ties them
        # together -- never independently true from unrelated propositions.
        own_roles = own_evidence_roles(role_completion, bindings)
        if len(own_roles) >= 2 and not _joint_grounded(bindings, own_roles, relationship_verifiers, context=context):
            complete = False

    any_ambiguous = any(bindings.get(r, {}).get("state") == "ambiguous" for r in roles_in_play)
    any_filled = any(filled(r) for r in roles_in_play)

    if complete:
        state, reason = "filled", None
    elif any_ambiguous:
        state, reason = "ambiguous", "evidence_conflicting"
    elif any_filled:
        state, reason = "partially_filled", "incomplete_instance"
    else:
        seen_reasons = {bindings[r]["reason"] for r in roles_in_play if r in bindings and bindings[r].get("reason")}
        reason = next(iter(seen_reasons), "not_found")
        state = "missing"

    return {**instance, "complete": bool(complete), "state": state, "reason": reason}


def _aggregate_exists(instances: list[dict]) -> tuple[str, str | None]:
    if any(i["complete"] for i in instances):
        return "filled", None
    if any(i["state"] == "ambiguous" for i in instances):
        return "ambiguous", "evidence_conflicting"
    if any(i["state"] == "partially_filled" for i in instances):
        return "partially_filled", "incomplete_instance"
    return "missing", "not_found"


def _aggregate_all_requested_categories(instances: list[dict]) -> tuple[str, str | None]:
    if not instances:
        return "missing", "category_missing"
    complete = sum(1 for i in instances if i["complete"])
    if complete == len(instances):
        return "filled", None
    if complete == 0:
        return "missing", "category_missing"
    return "partially_filled", "category_missing"


def _aggregate_for_each_discovered_instance(instances: list[dict]) -> tuple[str, str | None]:
    if not instances:
        return "missing", "not_found"
    complete = sum(1 for i in instances if i["complete"])
    if complete == len(instances):
        return "filled", None
    if any(i["state"] != "missing" for i in instances):
        return "partially_filled", "incomplete_instance"
    return "missing", "not_found"


def _aggregate_at_least_n(instances: list[dict], n: int) -> tuple[str, str | None]:
    complete = sum(1 for i in instances if i["complete"])
    if complete >= n:
        return "filled", None
    if complete == 0:
        return "missing", "not_found"
    return "partially_filled", "incomplete_instance"


def _aggregate_open_list(instances: list[dict]) -> tuple[str, str | None]:
    # NEVER "filled" -- an open-ended list can never be certified exhaustively answered.
    if any(i["complete"] for i in instances):
        return "partially_filled", None
    if any(i["state"] == "partially_filled" for i in instances):
        return "partially_filled", "incomplete_instance"
    return "missing", "not_found"


_AGGREGATORS = {
    "exists": lambda instances, n: _aggregate_exists(instances),
    "all_requested_categories": lambda instances, n: _aggregate_all_requested_categories(instances),
    "for_each_discovered_instance": lambda instances, n: _aggregate_for_each_discovered_instance(instances),
    "at_least_n": lambda instances, n: _aggregate_at_least_n(instances, n),
    "open_list": lambda instances, n: _aggregate_open_list(instances),
}


def recompute_requirement(requirement: dict, *, context: dict | None = None, semantics_version: str) -> dict:
    """Pure: returns a NEW requirement dict. Recomputes every instance's `complete`/`state`/
    `reason` from its `role_bindings`, then aggregates across instances per
    `instance_quantifier`. Never mutates the input."""
    require_supported_semantics_version(semantics_version)
    role_completion = requirement["role_completion"]
    verifiers = requirement["relationship_verifiers"]
    goal_gate = semantics_version == SUFFICIENCY_SEMANTICS_V4 and is_category_requirement(requirement)
    recomputed_instances = [
        recompute_instance(
            role_completion, inst, verifiers, context=context, semantics_version=semantics_version, goal_gate=goal_gate
        )
        for inst in requirement["instances"]
    ]
    aggregator = _AGGREGATORS[requirement["instance_quantifier"]]
    state, reason = aggregator(recomputed_instances, requirement.get("quantifier_n"))
    return {**requirement, "instances": recomputed_instances, "state": state, "reason": reason}


def complete_instance_count(requirement: dict) -> int:
    return sum(1 for inst in requirement["instances"] if inst["complete"])


# ---------------------------------------------------------------------------------------------
# Parent-instance eligibility (Phase 16) -- the ONE shared primitive deciding whether a parent
# requirement's own instance may supply trusted `parent_context` to a descendant. Found necessary
# by a real adversarial case (Phase 15's c4 recovery result): positional selection
# (`instances[0]`) let an INCOMPLETE, newly-nominated instance displace an already-COMPLETE one
# downstream, purely from raw model list order. `recompute_instance`'s own documented rationale
# for exempting `parent_context` bindings from joint-grounding is that such a binding is "already
# semantically established" -- which cannot be true of an instance the parent's OWN completion
# rule has not yet certified `complete`. Used identically by every parent-context consumer
# (`sufficiency_mapping.map_paired_requirement`, `sufficiency_recovery_targets.
# _first_instance_targets`) so the mapper and the RecoveryTarget layer can never disagree about
# whether a usable parent exists.
# ---------------------------------------------------------------------------------------------


def eligible_parent_instances(parent_requirement: dict, parent_role: str) -> list[dict]:
    """The subset of `parent_requirement["instances"]` eligible to supply trusted `parent_context`
    for `parent_role`: the requested role's own binding must be `state=="filled"` AND the
    supplying instance itself must be `complete`. Deliberately NOT the same question as
    `compute_stop_search_certified` -- a `complete` instance whose completion is model-dependent
    (`candidate_source=="model_mapping"`, directly or via an already-propagated
    `upstream_model_dependent` hop) remains eligible; its model-dependence is a provenance fact
    the caller carries forward (`_propagated_provenance`'s own `upstream_model_dependent`/
    `source_lineage`/`model_dependency_origins`), never a reason to withhold eligibility here.

    Returned sorted by `instance_key` (never raw list/positional order) -- stable for serialized
    output, but not itself load-bearing: the eligible SET is already order-independent by
    construction (a pure per-instance filter with no cross-instance state), so every caller's own
    semantic result is guaranteed invariant to how `parent_requirement["instances"]` was ordered."""
    eligible = [
        instance
        for instance in parent_requirement["instances"]
        if instance.get("complete") and instance["role_bindings"].get(parent_role, {}).get("state") == "filled"
    ]
    return sorted(eligible, key=lambda instance: instance["instance_key"] or "")


# ---------------------------------------------------------------------------------------------
# Stop-search authority -- a SEPARATE axis from semantic `state` (Phase 9, Phase 8 Option F).
#
# `state == "filled"` answers "is there enough evidence to construct an answer". It does NOT, by
# itself, answer "should a recovery controller stop searching" -- those are different questions a
# single boolean cannot honestly carry. A model-assisted nomination is exactly the PRINCIPLES.md
# "signal, not verdict" case applied to search control: Phase 7's live diagnostic found a model-
# sourced binding can complete a requirement on a vague, non-identifying nomination (see
# PHASE7_LIVE_TWO_KEY_DIAGNOSTIC_RESULTS.md) -- so a `filled` state that DEPENDS on one or more
# `model_mapping` bindings must never, by itself, certify that recovery should stop. It remains
# fully `filled` and fully usable for answer construction (never hidden, never downgraded in the
# user-facing map -- the direct analogue of invariant #4, "never hide a low-confidence or flagged
# claim") while a SEPARATE query, `compute_stop_search_certified`, tells a recovery controller
# whether THIS fill is safe to treat as a stop-search certificate.
# ---------------------------------------------------------------------------------------------


def _instance_completion_is_model_dependent(role_completion: dict, instance: dict) -> bool:
    """True iff this COMPLETE instance's own-evidence completion-critical bindings include at
    least one sourced from `model_mapping` -- DIRECTLY, or TRANSITIVELY through one or more
    `parent_context` hops (Phase 11 fix for a Phase 10-confirmed gap: a binding whose immediate
    `candidate_source` is `"parent_context"` can still owe its value to an upstream model
    nomination, and the ORIGINAL check here only ever looked at the immediate, re-stamped source).
    Mirrors `recompute_instance`'s own `filled_roles` subset (every role participating in
    `role_completion`, i.e. `completion_roles`). A binding's structured `provenance[
    "upstream_model_dependent"]` (see `sufficiency_mapping._propagated_provenance`) carries this
    transitively without ever parsing `detail`'s free text -- absent on every binding that was
    never propagated (deterministic or direct model_mapping), where it is simply not consulted."""
    if not instance.get("complete"):
        return False
    bindings = instance["role_bindings"]
    for role in completion_roles(role_completion):
        binding = bindings.get(role, {})
        if binding.get("state") != "filled":
            continue
        provenance = binding.get("provenance", {})
        if provenance.get("candidate_source") == "model_mapping":
            return True
        if provenance.get("upstream_model_dependent"):
            return True
    return False


def _stop_search_exists(flagged: list[dict], n) -> bool:
    return any(i["complete"] and not i["_model_dependent"] for i in flagged)


def _stop_search_all_complete_clean(flagged: list[dict], n) -> bool:
    complete = [i for i in flagged if i["complete"]]
    return bool(complete) and all(not i["_model_dependent"] for i in complete)


def _stop_search_at_least_n(flagged: list[dict], n: int) -> bool:
    clean_complete = sum(1 for i in flagged if i["complete"] and not i["_model_dependent"])
    return clean_complete >= n


_STOP_SEARCH_AGGREGATORS = {
    # Mirrors `_AGGREGATORS`'s own per-`instance_quantifier` dispatch shape exactly, evaluated
    # against "clean completion" (no model-mapping-dependent completion-critical binding) instead
    # of "any completion" -- a deterministic re-aggregation of the SAME instance set against an
    # already-present provenance fact, never a confidence score.
    "exists": _stop_search_exists,
    "all_requested_categories": _stop_search_all_complete_clean,
    "for_each_discovered_instance": _stop_search_all_complete_clean,
    "at_least_n": _stop_search_at_least_n,
    "open_list": lambda flagged, n: False,  # open_list's own aggregator never returns "filled"
}


def compute_stop_search_certified(requirement: dict) -> bool:
    """Whether `requirement`'s OWN `state == "filled"` can be explained WITHOUT relying on any
    model-mapping-sourced completion-critical binding. Returns True (certified) whenever
    `state != "filled"` -- this predicate is only ever meaningful, and only ever consulted, within
    `compute_recovery_needed`'s already-`filled` branch; outside that branch the caller's existing
    `state`-based logic already applies and this query has nothing to add.

    Reads only `state`/`instances`/`role_completion`/`instance_quantifier` -- already-computed,
    already-hashed-separately runtime fields (see `_RUNTIME_ONLY_KEYS`) and the frozen
    `role_completion`/`instance_quantifier` declarations themselves. Never mutates its input,
    never writes back a field onto the requirement -- `state` stays the sole semantic-completeness
    axis (never overloaded); this is a parallel, separately-named query, not a second state."""
    if requirement["state"] != "filled":
        return True
    role_completion = requirement["role_completion"]
    flagged = [
        {**inst, "_model_dependent": _instance_completion_is_model_dependent(role_completion, inst)}
        for inst in requirement["instances"]
    ]
    aggregator = _STOP_SEARCH_AGGREGATORS[requirement["instance_quantifier"]]
    return bool(aggregator(flagged, requirement.get("quantifier_n")))


# ---------------------------------------------------------------------------------------------
# Recovery routing -- run-level, separate from semantic `state` (never "keep recovering forever")
# ---------------------------------------------------------------------------------------------

_RECOVERABLE_REASONS = frozenset({"not_found", "incomplete_instance", "category_missing"})


def compute_recovery_needed(requirement: dict, search_status: dict) -> bool:
    """Whether this requirement should trigger a recovery attempt right now. A run-level
    decision, computed from `state`/`reason` (semantic) and `search_status` (process) together --
    never stored on the frozen contract, never conflated with `state` itself.

    `open_list` gets the approved bounded-breadth policy: once >=1 complete instance exists,
    exactly one more recovery attempt is allowed (if budget remains and the breadth pass hasn't
    already run) to look for additional supported instances; after that bounded pass, or once
    budget is exhausted, recovery stops and the requirement may terminate honestly as
    `partially_filled` -- disclosed as non-exhaustive (see the rendering layer), never as if the
    literature had been searched to completion.

    A `filled` requirement whose fill is NOT stop-search-certified (Phase 9, Phase 8 Option F --
    see `compute_stop_search_certified`) gets the SAME bounded-breadth shape `open_list` already
    uses, rather than either blind trust (treat a model-only fill like a certified one, Phase 7's
    own demonstrated failure mode) or unlimited re-search (treat it like `missing`): exactly one
    further recovery opportunity, then honest termination. Recovery stays OFF wherever this
    function's caller does not independently enable it; this function only ever computes whether
    recovery *would* be needed.
    """
    budget_spent = search_status.get("recovery_budget_exhausted") or search_status.get(
        "scoped_search_completed_no_additional_support"
    )
    if requirement["instance_quantifier"] == "open_list":
        if complete_instance_count(requirement) == 0:
            return not budget_spent
        if search_status.get("breadth_pass_used"):
            return False
        return not budget_spent
    if requirement["state"] == "filled":
        if compute_stop_search_certified(requirement):
            return False
        if search_status.get("breadth_pass_used"):
            return False
        return not budget_spent
    if budget_spent:
        return False
    return requirement.get("reason") in _RECOVERABLE_REASONS
