"""Shared fixtures for the parent-synthesis tests. Not a test module.

Mirrors ``overview_test_support.py``'s own "invented passages, real shape" discipline and
``test_sufficiency_recovery_targets.py``'s own ``_filled``/``_missing``/``_contract_with`` helpers --
reused rather than re-derived. The one c12-shaped fixture is lifted verbatim (same exact_text,
proposition content, and role bindings) from the real, frozen Phase-23 run artifact
(``.local/e2e-runs/phase23-live-recovery-targeted-u2-remap-validation-20261003T020939Z/
phase23_result.json``), hardcoded here as a frozen literal so the regression does not depend on
that directory existing in any given worktree (the same precedent Phase 16's own
``test_real_phase15_recorded_nomination_end_to_end_c6_inherits_amygdala_only`` established).
"""

from __future__ import annotations

from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se


def filled(role, prop_id, text, *, source="deterministic_mapping", provenance_extra=None):
    provenance = {"candidate_source": source, "detail": "", "model": None}
    if provenance_extra:
        provenance.update(provenance_extra)
    return se.new_role_binding(role, state="filled", proposition_id=prop_id, exact_text=text, provenance=provenance)


def missing(role, reason="not_found"):
    return se.new_role_binding(role, state="missing", reason=reason)


def instance(bindings: dict, *, instance_key: str | None = None) -> dict:
    inst = se.new_instance(instance_key)
    inst["role_bindings"] = dict(bindings)
    return inst


def map_with(child_id: str, requirement: dict) -> dict:
    """``{child_id: SufficiencyContract}`` -- the exact shape ``build_claim_ledger`` consumes, after
    the real ``recompute_requirement`` has already run (so ``complete``/``state`` are authentic)."""
    return {child_id: se.new_contract(child_id, [requirement])}


def requirement(
    req_id: str,
    role_specs: dict,
    role_completion: dict,
    instance_quantifier: str,
    instances: list[dict],
    *,
    kind: str = "atomic",
    **kwargs,
) -> dict:
    """Builds and recomputes in one step -- every fixture requirement in this suite goes through
    the real ``recompute_requirement`` exactly once, matching how ``sufficiency_diagnostic`` itself
    always hands ``build_claim_ledger`` an already-recomputed map. ``kind`` defaults to ``"atomic"``
    (the engine's own comment: a descriptive label only, state computation never dispatches on it,
    and neither does the parent-synthesis ledger builder -- see ``own_evidence_roles``-count
    dispatch); set it explicitly where a fixture is reproducing a real requirement's own label."""
    req = se.new_requirement(req_id, kind, role_specs, role_completion, instance_quantifier, **kwargs)
    req["instances"] = instances
    return se.recompute_requirement(req)


def spec(role: str, category_description: str, strategy: str = "model_nomination_only") -> dict:
    return se.new_role_spec(role, category_description, strategy)


def _span(paper_id: int, chunk_id: int, span_id: str, text: str) -> dict:
    return {"paper_id": paper_id, "chunk_id": chunk_id, "span_id": span_id, "text": text}


def _prop(pid: str, paper_id: int, text: str, children: list[str], *, chunk: int, span: str = "e1") -> dict:
    """Mirrors Phase 18's own synthetic-reproduction ``_prop`` shape (``PHASE18_DIRECTION_
    EFFECTIVENESS_SEMANTICS_RESULTS.md`` Section 18) -- a literal ``verified_propositions`` row fed
    into the real, unmodified ``overview_evidence.build_units``/``sufficiency_diagnostic.
    units_by_child``. Deliberately NOT built through ``overview_test_support.sealed_ledger``: that
    helper's ``det_coverage`` pass resolves responsiveness against the module's own FIXED
    ``SUBQUESTIONS`` (field ids ``s1-o1``/``s2-o1``/``s3-o1``), so an arbitrary child id (``"c12"``,
    ``"c1"``, ...) attached through it is silently dropped rather than recorded -- confirmed live
    while building this fixture (an empty ``effectiveness_observations`` where the real run has
    one). This builder sets ``responsive_obligation_ids`` directly, with no coverage-pass
    indirection, which is also the correct contract: ``build_claim_ledger`` never reads attachment
    tags at all (Phase 26 Section 24) -- only ``sufficiency_map_final``'s own role bindings do."""
    return {
        "proposition_id": pid,
        "proposition_text": text,
        "paper_id": paper_id,
        "quote": text,
        "evidence_anchor_chunk_id": chunk,
        "evidence_span_id": span,
        "responsive_obligation_ids": list(children),
        "anchors": [],
        "verification": {"status": "verified", "page_start": 1},
    }


def sealed_with(*specs: tuple) -> dict:
    """A literal sealed ledger from ``(proposition_id, paper_id, text, attached_children)`` specs
    (``chunk``/``span`` auto-assigned, distinct per entry) -- see ``_prop``'s own docstring for why
    this does not go through ``overview_test_support.sealed_ledger``."""
    props = [
        _prop(pid, paper_id, text, list(children), chunk=9000 + n)
        for n, (pid, paper_id, text, children) in enumerate(specs)
    ]
    spans = [_span(p["paper_id"], p["evidence_anchor_chunk_id"], p["evidence_span_id"], p["quote"]) for p in props]
    return {"verified_propositions": props, "evidence_spans": spans}


def proposition_ids(sealed: dict) -> list[str]:
    """``[proposition_id, ...]`` in ledger order -- a small reading convenience."""
    return [row["proposition_id"] for row in sealed["verified_propositions"]]


# ---------------------------------------------------------------------------------------------
# The real, frozen c12 upstream-error fixture (Phase 23a's own adjudicated finding), hardcoded.
# ---------------------------------------------------------------------------------------------

C12_INTERVENTION_TEXT = "the anomalous faces variant of the NAME intervention"
C12_OUTCOME_TEXT = (
    "Specificity and generalization of intervention effects We also observed that the anomalous "
    "faces variant of the NAME intervention produced a clear reduction in implicit bias against "
    "people with anomalous faces, whereas bias toward people of color in that condition remained "
    "essentially unchanged."
)
# The confirmed-WRONG value (Phase 23a #21): the source sentence's OTHER bias, which the
# intervention did NOT affect -- picked anyway. Reproduced verbatim; never corrected here.
C12_WRONG_TARGET_MANIFESTATION_TEXT = "bias toward people of color"
C12_OFFTOPIC_INTERVENTION_TEXT = "scalable real-world inoculation interventions"  # the COVID/"Bad News" passage


C12_OTHER_OUTCOME_TEXT = "Taken together, our data are consistent with the possibility"


def real_c12_fixture() -> tuple[dict, dict]:
    """``(sealed, sufficiency_map_final)`` reproducing the real, frozen
    ``c12#suff:intervention-effectiveness`` requirement from the Phase-23 run: kind=relational, 3
    required own-evidence roles, same_proposition-verified, 4 instances (U18
    complete/correct-intervention+WRONG-target_manifestation, U19/U28 incomplete, U30
    incomplete-but-off-topic-intervention). Every ``exact_text`` is the real recorded value,
    verbatim; proposition_ids are freshly assigned by the real ``sealed_with``/``stages.seal``
    pipeline rather than reusing the original run's own ``p33``/``p34``/``p45`` numbers (a ledger
    position, not semantic content). ``effectiveness_observations``/``effectiveness_summary`` are
    populated by the real, unmodified ``sufficiency_diagnostic.compute_direction_and_effectiveness``
    -- never hand-rolled -- exactly as the real pipeline would produce them."""
    sealed = sealed_with(
        ("p1", 90, C12_OUTCOME_TEXT, ["c12"]),
        ("p2", 91, C12_OTHER_OUTCOME_TEXT, ["c12"]),
        ("p3", 92, C12_OFFTOPIC_INTERVENTION_TEXT, ["c12"]),
    )
    p_outcome, p_other, p_offtopic = proposition_ids(sealed)

    specs = {
        "intervention": spec("intervention", "a named intervention or manipulation"),
        "target_manifestation": spec("target_manifestation", "the specific bias/behavior the intervention targets"),
        "observed_effect_or_outcome": spec(
            "observed_effect_or_outcome",
            "the measured effect of the intervention",
            strategy="achieved_outcome_predicate",
        ),
    }
    completion = se.new_role_completion(
        required_roles=["intervention", "target_manifestation", "observed_effect_or_outcome"]
    )
    u18 = instance(
        {
            "intervention": filled("intervention", p_outcome, C12_INTERVENTION_TEXT, source="model_mapping"),
            "target_manifestation": filled(
                "target_manifestation", p_outcome, C12_WRONG_TARGET_MANIFESTATION_TEXT, source="model_mapping"
            ),
            "observed_effect_or_outcome": filled("observed_effect_or_outcome", p_outcome, C12_OUTCOME_TEXT),
        },
        instance_key="U18",
    )
    u19 = instance(
        {
            "intervention": missing("intervention"),
            "target_manifestation": missing("target_manifestation"),
            "observed_effect_or_outcome": filled("observed_effect_or_outcome", p_other, C12_OTHER_OUTCOME_TEXT),
        },
        instance_key="U19",
    )
    u28 = instance(
        {
            "intervention": missing("intervention"),
            "target_manifestation": missing("target_manifestation"),
            "observed_effect_or_outcome": missing("observed_effect_or_outcome"),
        },
        instance_key="U28",
    )
    u30 = instance(
        {
            "intervention": filled("intervention", p_offtopic, C12_OFFTOPIC_INTERVENTION_TEXT, source="model_mapping"),
            "target_manifestation": missing("target_manifestation"),
            "observed_effect_or_outcome": missing("observed_effect_or_outcome"),
        },
        instance_key="U30",
    )
    req = requirement(
        "c12#suff:intervention-effectiveness",
        specs,
        completion,
        "exists",
        [u18, u19, u28, u30],
        kind="relational",
        multi_instance=True,
        effectiveness=se.new_effectiveness_assessment(),
    )
    sufficiency_map_final = map_with("c12", req)
    sd.compute_direction_and_effectiveness(sealed, sufficiency_map_final)
    return sealed, sufficiency_map_final
