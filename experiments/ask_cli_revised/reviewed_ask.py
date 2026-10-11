"""Public experimental reviewed-authored runner. No persisted scientific output input.

Load explicit authoring paths with reviewed_ask_inputs.load_reviewed_inputs, or bind the
actual authoring caller's joint review. Runtime/trace/residency/bound roles are the same
ordinary execution objects used by e2e.execute. This route never chooses fixture defaults.
Current science/plan selection is owned by this reviewed route; historical producers and
explicit replay serializers keep their enrolled defaults and identities.
"""

from experiments.ask_cli_revised import e2e
from experiments.ask_cli_revised import reviewed_ask_inputs as reviewed
from experiments.ask_cli_revised._layerc_common import plain
from experiments.ask_cli_revised.fresh_invocation import CURRENT_PLAN_VERSION as CURRENT_PLAN_VERSION
from experiments.ask_cli_revised.fresh_invocation import CURRENT_SEMANTICS_VERSION as CURRENT_SEMANTICS_VERSION


def run_reviewed_request(inputs, *, rt, profile, trace, guard, bound, entail=None, sufficiency_recovery=False):
    """Execute the reviewed request from retrieval through selected v2 rendering."""
    reviewed.validate_bound(inputs)
    return e2e.execute(
        rt=rt,
        profile=profile,
        trace=trace,
        guard=guard,
        bound=bound,
        entail=entail,
        contract=plain(inputs.request),
        sufficiency_contract=plain(inputs.scientific),
        sufficiency_parent_of=plain(inputs.parent_of),
        sufficiency_recovery_gate_enabled=sufficiency_recovery,
        _reviewed_inputs=inputs,
    )
