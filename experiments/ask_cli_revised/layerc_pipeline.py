"""Shared deterministic v2 consumers; upstream authority is established by the caller."""

from experiments.ask_cli_revised import claim_v2, layerc_presentation, parent_synthesis_v2, relation_unit_v2
from experiments.ask_cli_revised.answer_plan import plan_v5, render_v5


def build_components(projection, authored, sealed, verified=None, *, fresh_authority=None, recovery=None, search=None):
    # The display corrections apply to a fresh invocation; a recorded reproduction keeps its frozen behavior.
    finalized = layerc_presentation.finalize_display(
        projection, sealed, authored, corrected=fresh_authority is not None
    )
    claims = claim_v2.build_claims(projection, authored)
    receipts = claim_v2.evidence_receipts(projection, claims, finalized)
    units = relation_unit_v2.build_relation_units(projection, authored, claims, receipts, finalized)
    synthesis = parent_synthesis_v2.realize(claims, projection, receipts, finalized, units)
    parent_synthesis_v2.audit(synthesis, claims, projection, receipts, finalized, units)
    plan = plan_v5.build_plan(
        projection,
        authored,
        claims,
        receipts,
        units,
        finalized,
        synthesis,
        verified,
        fresh_authority=fresh_authority,
        recovery=recovery,
        search=search,
    )
    ground = None
    if fresh_authority is not None:

        def ground(nodes):
            layerc_presentation.ground_acronyms(nodes, sealed)

    rendered = render_v5.render(plan, claims, receipts, synthesis, ground=ground)
    return {
        "claims": claims,
        "claim_evidence": receipts,
        "relation_units": units,
        "value_coverage": finalized,
        "parent_synthesis": synthesis,
        "plan": plan,
        "render": rendered,
    }
