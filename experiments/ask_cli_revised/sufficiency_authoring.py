"""Layer B -- contract-generation architecture. A calibration/gold-standard authoring path
today, mirroring ``hierarchy_contract.py``'s own ``freeze``/``review``/pin cycle, NOT the
intended permanent per-query production mechanism: nothing here should be read as requiring a
human to hand-author and approve a frozen contract for every future Ask question. The eventual
general path needs an automatic proposal mechanism (from the original request + decomposition +
clarifications, with its own validation/review mechanics) -- not built in this task;
``author_supersession`` is the named seam it would occupy, still subject to the same
human-review gate before freezing.

Two input sources feed a ``SufficiencyContract``, never conflated:

* ``extract_recorded_requirements`` -- deterministic, reads already-approved requirement/
  qualification text already sitting on the hierarchy contract (reading, not inferring).
* Explicit researcher authorship (``author_supersession``) -- for intent the original request or
  Cliff's own specification carries but that no existing child-level record captures. This is
  how c1/c2/c3/c4/c8/c10 gain their full richness below; every such addition is dated,
  attributed, and provenanced, never a silent rewrite of the hierarchy contract or of D-1.

No model call exists anywhere in this module. No external scholarly method is implemented or
operationalized here (see CREDIT-THE-LINEAGE.md) -- q_aib's own contract content is derived
from Cliff's own scientific request and his explicit researcher authorship, not from a
published method.

Freezing (``freeze``) never touches ``hierarchy_contract.py``'s own ``D1_RECORD``, pin, or hash,
and this module never writes a persistent frozen artifact to disk on its own -- ``freeze``
returns a pure dict; installing it as a reviewed, on-disk pin is a separate, later, explicitly
human-approved act (see ``hierarchy_contract.py``'s own review requirement), not performed here.
"""

from __future__ import annotations

import hashlib
import json

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_mapping as sm

QUESTION_KEY = "aib_hier_v8"
SUFFICIENCY_CONTRACT_VERSION = "sufficiency-contract-v1"

# ---------------------------------------------------------------------------------------------
# D-1 and c3: explicit, provenanced supersession -- never a silent rewrite of frozen history.
# ---------------------------------------------------------------------------------------------

D1_SUFFICIENCY_SUPERSESSION = {
    "supersedes": "D-1",
    "prior_option": "A",
    "authorized_by": "Cliff",
    "date": "2026-09-30",
    "scope": (
        "Sufficiency assessment only. Does not amend hierarchy_contract.py's D1_RECORD, its pin, "
        "or its hash, and does not change model-facing status -- these roles are assessed only "
        "from already-verified evidence after the fact, never shown to a model as contract text."
    ),
    "operationalized_now": [
        "RC-9#scope:documented-nature-direction (c5 direction)",
        "RC-8#scope:documented-nature-direction (c6 direction)",
        "RC-8#scope:measures-implicit-explicit (c6 implicit/explicit)",
        "RC-9#scope:measures-of-behavior (c5 behavior/behavioral-measure specificity)",
    ],
    "still_not_operationalized": [
        "RC-9#expression:where-supported",
        "RC-8#expression:where-supported",
    ],
}

C3_SEMANTIC_SUPERSESSION = {
    "child_id": "c3",
    "authorized_by": "Cliff",
    "date": "2026-09-30",
    "rationale": (
        "The frozen hierarchy contract records no requirement/qualification on c3, but the "
        "original request and current researcher intent require implicit AND explicit attitude "
        "coverage on c3 specifically (RC-8's own text is scoped to c6, the brain-attitude "
        "relationship, not to c3's own bare manifestation ask)."
    ),
    "added_requirement": "c3#suff:implicit-explicit-coverage (cardinality, all_requested_categories)",
    "note": (
        "This authorizes the SUFFICIENCY contract only. The hierarchy contract's own c3 record "
        "(wording, hash, pin) is untouched; a parallel amendment there -- a new "
        "c3#scope:measures-implicit-explicit qualification, mirroring c6's -- is recommended as "
        "a separate, later re-freeze/review decision, not built in this task."
    ),
}


def assert_hierarchy_contract_untouched(hierarchy_contract_module) -> None:
    """A test-facing guard: the supersession records above must never coincide with any mutation
    of hierarchy_contract.py's own D1_RECORD. Byte-identity of the dict before/after this module
    is imported is the caller's own check (see test_sufficiency_leakage.py); this function just
    names the invariant so it isn't only implicit in a docstring."""
    assert hierarchy_contract_module.D1_RECORD["decision"] == "D-1"
    assert hierarchy_contract_module.D1_RECORD["option"] == "A"


# ---------------------------------------------------------------------------------------------
# Deterministic extraction of already-approved text (reading, never inferring)
# ---------------------------------------------------------------------------------------------


def extract_recorded_requirements(child: dict) -> list[dict]:
    """Surfaces every already-approved requirement/qualification/structural-requirement/scope-
    carrier record already sitting on a hierarchy_contract child. This is "genuinely reliable"
    because it reads text a human already wrote and approved (RC-9/RC-8/RC-5/RC-6/etc.) -- it
    infers nothing from raw wording. Returns raw fragments for provenance cross-checking; how
    they assemble into a SufficiencyRequirement's role_completion/quantifier structure is a
    design-time authoring act (`build_qaib_contract` below), never mechanical.
    """
    fragments: list[dict] = []
    for qual in child.get("qualifications") or []:
        fragments.append({"id": qual["id"], "text": qual["text"], "source": "qualification"})
    for req in child.get("requirements") or []:
        fragments.append({"id": req["id"], "text": req["text"], "source": "requirement", "class": req.get("class")})
    for structural in child.get("structural_requirements") or []:
        fragments.append(
            {"id": structural["id"], "text": None, "source": "structural_requirement", "state": structural.get("state")}
        )
    if child.get("scope_carrier"):
        carrier = child["scope_carrier"]
        fragments.append(
            {"id": f"scope_carrier:{carrier['from']}", "text": carrier["wording"], "source": "scope_carrier"}
        )
    return fragments


def author_supersession(requirement: dict, *, authorized_by: str, date: str, rationale: str) -> dict:
    """Attaches a dated, attributed provenance record to a requirement built from intent not
    captured by any existing recorded child-level text -- never a silent invention. Named,
    swappable seam: a future automatic proposer could occupy this exact call site, still subject
    to the same human-review gate before freezing."""
    return {**requirement, "_authored": {"authorized_by": authorized_by, "date": date, "rationale": rationale}}


# ---------------------------------------------------------------------------------------------
# q_aib's own frozen instance (Layer C) -- hand-authored, the calibration/gold-standard case.
#
# D10 compliance note: role `category_description` text is the ONLY sufficiency-layer string a
# future model-assisted nomination pass would ever put in front of a model
# (`sufficiency_mapping.MODEL_NOMINATION_PROMPT_TEMPLATE`). hierarchy_contract.py's own D10
# record keeps "networks" optional-by-amendment and NEVER model-facing; a brain-region role's
# description therefore says "brain area" (the original request's own model-facing wording),
# never "region or network" -- caught by test_sufficiency_leakage.py's `mentions_networks` check
# before this shipped, not discovered live.
# ---------------------------------------------------------------------------------------------

_ACHIEVED = list(sm.ACHIEVED_OUTCOME_DEFAULT_GUARDS)
_NAMED = list(sm.NAMED_ENTITY_DEFAULT_GUARDS)


def _entity_role(
    name: str, description: str, wording: str, *, strategy: str = "model_nomination_only", **kwargs
) -> dict:
    return se.new_role_spec(
        name, description, strategy, disqualifying_guards=_NAMED, source_wording_span=wording, **kwargs
    )


def _manifestation_role(name: str, description: str, wording: str, *, disqualifying_guards=None) -> dict:
    return se.new_role_spec(
        name,
        description,
        "achieved_outcome_predicate",
        disqualifying_guards=disqualifying_guards if disqualifying_guards is not None else _ACHIEVED,
        source_wording_span=wording,
    )


def _build_c1(wording: str) -> dict:
    specs = {
        "neural_measure_or_modality": _entity_role(
            "neural_measure_or_modality", "a neural measure or imaging modality", wording
        ),
        "brain_region_or_network": _entity_role("brain_region_or_network", "a specific named brain area", wording),
        "neural_manifestation_evidence": _manifestation_role(
            "neural_manifestation_evidence", "an observed neural finding bearing on the bias", wording
        ),
    }
    completion = se.new_role_completion(
        required_roles=["neural_manifestation_evidence"],
        alternative_role_groups=[["neural_measure_or_modality", "brain_region_or_network"]],
    )
    req = se.new_requirement(
        "c1#suff:neural-manifestation", "atomic", specs, completion, "exists", source_wording_span=wording
    )
    return author_supersession(
        req,
        authorized_by="Cliff",
        date="2026-09-30",
        rationale="c1's model-facing wording is bare manifestation; the identification-vs-manifestation split is "
        "researcher-authored per the generic distinction, not present as separate recorded requirement text.",
    )


def _build_c2(wording: str) -> dict:
    specs = {
        "behavior_or_behavioral_measure": _entity_role(
            "behavior_or_behavioral_measure", "a named behavior or behavioral measure", wording
        ),
        "behavioral_manifestation_evidence": _manifestation_role(
            "behavioral_manifestation_evidence", "an observed behavioral finding bearing on the bias", wording
        ),
    }
    completion = se.new_role_completion(
        required_roles=["behavior_or_behavioral_measure", "behavioral_manifestation_evidence"]
    )
    req = se.new_requirement(
        "c2#suff:behavioral-manifestation", "atomic", specs, completion, "exists", source_wording_span=wording
    )
    return author_supersession(
        req,
        authorized_by="Cliff",
        date="2026-09-30",
        rationale="Same identification-vs-manifestation split as c1, applied to c2's own bare behavioral ask.",
    )


def _category_requirement(req_id: str, wording: str, terms: list[str]) -> dict:
    spec = se.new_role_spec(
        "category_evidence",
        "attitude category (implicit/explicit) evidence",
        "explicit_category_terms",
        disqualifying_guards=[],
        requested_category_terms=terms,
        source_wording_span=wording,
    )
    completion = se.new_role_completion(required_roles=["category_evidence"])
    return se.new_requirement(
        req_id,
        "cardinality",
        {"category_evidence": spec},
        completion,
        "all_requested_categories",
        multi_instance=True,
        source_wording_span=wording,
    )


def _build_c3(wording: str) -> list[dict]:
    atomic_specs = {
        "attitude_manifestation_evidence": _manifestation_role(
            "attitude_manifestation_evidence", "an observed attitude finding bearing on the bias", wording
        )
    }
    atomic_completion = se.new_role_completion(required_roles=["attitude_manifestation_evidence"])
    atomic_req = se.new_requirement(
        "c3#suff:attitude-manifestation",
        "atomic",
        atomic_specs,
        atomic_completion,
        "exists",
        source_wording_span=wording,
    )
    cardinality_req = author_supersession(
        _category_requirement("c3#suff:implicit-explicit-coverage", wording, ["implicit", "explicit"]),
        authorized_by=C3_SEMANTIC_SUPERSESSION["authorized_by"],
        date=C3_SEMANTIC_SUPERSESSION["date"],
        rationale=C3_SEMANTIC_SUPERSESSION["rationale"],
    )
    return [atomic_req, cardinality_req]


def _build_c4(wording: str) -> dict:
    specs = {
        "named_brain_region_or_network": _entity_role(
            "named_brain_region_or_network", "a specific NAMED brain area", wording
        ),
        "region_bears_on_bias_evidence": _manifestation_role(
            "region_bears_on_bias_evidence", "evidence that the named region bears on the bias", wording
        ),
    }
    completion = se.new_role_completion(
        required_roles=["named_brain_region_or_network", "region_bears_on_bias_evidence"]
    )
    return se.new_requirement(
        "c4#suff:specific-region",
        "atomic",
        specs,
        completion,
        "exists",
        empty_result_semantically_allowed=True,
        source_wording_span=wording,
    )


def _build_c5(wording: str) -> dict:
    # Role name MUST match c4's own role name exactly ("named_brain_region_or_network") -- see
    # the c9/c8 comment above; the same mismatch class was found here by the same real-run replay.
    specs = {
        "named_brain_region_or_network": _entity_role(
            "named_brain_region_or_network", "a specific named brain area", wording
        ),
        "behavior_or_behavioral_measure": _entity_role(
            "behavior_or_behavioral_measure", "a named behavior or behavioral measure", wording
        ),
    }
    completion = se.new_role_completion(
        required_roles=["named_brain_region_or_network", "behavior_or_behavioral_measure"]
    )
    return se.new_requirement(
        "c5#suff:brain-behavior",
        "relational",
        specs,
        completion,
        "exists",
        parent_context_roles=["named_brain_region_or_network"],
        direction=se.new_direction_assessment(),
        source_wording_span=wording,
    )


def _build_c6(wording: str) -> list[dict]:
    specs = {
        "named_brain_region_or_network": _entity_role(
            "named_brain_region_or_network", "a specific named brain area", wording
        ),
        "attitude_type_or_measure": _entity_role(
            "attitude_type_or_measure", "a named attitude type or measure", wording
        ),
    }
    completion = se.new_role_completion(required_roles=["named_brain_region_or_network", "attitude_type_or_measure"])
    relational_req = se.new_requirement(
        "c6#suff:brain-attitude",
        "relational",
        specs,
        completion,
        "exists",
        parent_context_roles=["named_brain_region_or_network"],
        direction=se.new_direction_assessment(),
        source_wording_span=wording,
    )
    cardinality_req = _category_requirement("c6#suff:implicit-explicit-coverage", wording, ["implicit", "explicit"])
    return [relational_req, cardinality_req]


def _build_c8(wording: str) -> dict:
    specs = {
        "individual_difference_trait_or_construct": _entity_role(
            "individual_difference_trait_or_construct", "a named individual-difference trait or construct", wording
        ),
        "relationship_to_bias_manifestation": _manifestation_role(
            "relationship_to_bias_manifestation",
            "evidence relating the trait/construct to the bias's manifestation",
            wording,
        ),
    }
    completion = se.new_role_completion(
        required_roles=["individual_difference_trait_or_construct", "relationship_to_bias_manifestation"]
    )
    return se.new_requirement(
        "c8#suff:trait-construct",
        "atomic",
        specs,
        completion,
        "open_list",
        multi_instance=True,
        source_wording_span=wording,
    )


def _build_c9(wording: str) -> dict:
    # Role name MUST match c8's own role name exactly ("individual_difference_trait_or_construct")
    # -- pairing resolves the parent requirement by looking up which of the PARENT's own roles is
    # named `parent_context_roles[0]` (`sufficiency_diagnostic.compute_diagnostic_sufficiency_map`).
    # A naming mismatch here silently falls through to the generic (non-paired) mapper instead of
    # raising -- caught live by the offline replay against the real preserved run, not by
    # inspection; see INCREMENT notes / the hand-back report for the concrete failure this fixed.
    specs = {
        "individual_difference_trait_or_construct": _entity_role(
            "individual_difference_trait_or_construct", "a named individual-difference trait or construct", wording
        ),
        "named_scale_or_instrument": se.new_role_spec(
            "named_scale_or_instrument",
            "a named scale or instrument",
            "named_instrument_lexicon",
            disqualifying_guards=[],
            source_wording_span=wording,
        ),
    }
    completion = se.new_role_completion(
        required_roles=["individual_difference_trait_or_construct", "named_scale_or_instrument"]
    )
    return se.new_requirement(
        "c9#suff:trait-scale-pairing",
        "relational",
        specs,
        completion,
        "for_each_discovered_instance",
        multi_instance=True,
        parent_context_roles=["individual_difference_trait_or_construct"],
        source_wording_span=wording,
    )


def _build_c10(wording: str) -> dict:
    specs = {
        "named_culture_or_population": _entity_role(
            "named_culture_or_population", "a named culture or population", wording
        ),
        "bias_evidence_in_population": _manifestation_role(
            "bias_evidence_in_population", "evidence bearing on the bias/generalizability in that population", wording
        ),
    }
    completion = se.new_role_completion(required_roles=["named_culture_or_population", "bias_evidence_in_population"])
    return se.new_requirement(
        "c10#suff:culture-existence", "atomic", specs, completion, "exists", source_wording_span=wording
    )


def _build_c11(wording: str) -> dict:
    specs = {
        "culture_or_population": _entity_role("culture_or_population", "a named culture or population", wording),
        "operationalization_or_measure": _entity_role(
            "operationalization_or_measure", "how the bias was measured/operationalized there", wording
        ),
    }
    completion = se.new_role_completion(required_roles=["culture_or_population", "operationalization_or_measure"])
    return se.new_requirement(
        "c11#suff:culture-operationalization-pairing",
        "relational",
        specs,
        completion,
        "for_each_discovered_instance",
        multi_instance=True,
        source_wording_span=wording,
    )


def _build_c12(wording: str) -> dict:
    specs = {
        "intervention": _entity_role("intervention", "a named intervention", wording),
        "target_manifestation": _entity_role(
            "target_manifestation", "which aspect of the bias the intervention targets", wording
        ),
        "observed_effect_or_outcome": _manifestation_role(
            "observed_effect_or_outcome",
            "a definitive, non-speculative reported outcome",
            wording,
            disqualifying_guards=list(sm.ACHIEVED_OUTCOME_DEFAULT_GUARDS),
        ),
    }
    completion = se.new_role_completion(
        required_roles=["intervention", "target_manifestation", "observed_effect_or_outcome"]
    )
    return se.new_requirement(
        "c12#suff:intervention-effectiveness",
        "relational",
        specs,
        completion,
        "exists",
        multi_instance=True,
        effectiveness=se.new_effectiveness_assessment(),
        source_wording_span=wording,
    )


_BUILDERS = {
    "c1": _build_c1,
    "c2": _build_c2,
    "c3": _build_c3,
    "c4": _build_c4,
    "c5": _build_c5,
    "c6": _build_c6,
    "c8": _build_c8,
    "c9": _build_c9,
    "c10": _build_c10,
    "c11": _build_c11,
    "c12": _build_c12,
}


def build_qaib_contract(children_by_id: dict) -> dict:
    """The first reviewed Layer B output: q_aib's own SufficiencyContract per child.
    `children_by_id` is the REAL, approved `01_request_contract.json`'s `hierarchy.children`,
    keyed by child_id -- nothing here is invented from scratch; `wording` is read verbatim from
    that live artifact. Returns `{child_id: SufficiencyContract}`."""
    contracts: dict[str, dict] = {}
    for child_id, builder in _BUILDERS.items():
        wording = children_by_id[child_id]["wording"]
        result = builder(wording)
        requirements = result if isinstance(result, list) else [result]
        contracts[child_id] = se.new_contract(child_id, requirements)
    return contracts


# ---------------------------------------------------------------------------------------------
# Freeze -- a pure function; never writes a persistent pin to disk on its own (see module docstring).
# ---------------------------------------------------------------------------------------------


def freeze(contracts: dict) -> dict:
    """contracts: {child_id: SufficiencyContract}. Returns the frozen artifact dict -- never
    written to disk here; installing a reviewed on-disk pin is a separate, later, explicitly
    human-approved act."""
    per_child = {}
    for child_id in sorted(contracts):
        contract = contracts[child_id]
        per_child[child_id] = {"frozen_view": se.frozen_view(contract), "hash": se.contract_hash(contract)}
    combined = hashlib.sha256(json.dumps(per_child, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "version": SUFFICIENCY_CONTRACT_VERSION,
        "question_key": QUESTION_KEY,
        "status": "UNREVIEWED_CANDIDATE: generated by sufficiency_authoring; not reviewed or approved. "
        "No live run should trust this without a recorded human review naming this combined_hash.",
        "per_child": per_child,
        "combined_hash": combined,
        "supersessions": {"D1": D1_SUFFICIENCY_SUPERSESSION, "C3": C3_SEMANTIC_SUPERSESSION},
    }
