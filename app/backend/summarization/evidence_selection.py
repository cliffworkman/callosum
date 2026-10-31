"""Reference-eligibility seam for the narrow synthesis path (``pipeline.summarize_scope``).

The narrow path's only reference guard was the heading-based reference-section filter (query scope only);
the anchored ``chunk_structure`` labels that already recognised bibliography text were never read. This seam
reads them (current rows only, stale ones recorded) and applies the shared policy in ``evidence_eligibility``:
an anchored ``bibliographic`` label DEMOTES a chunk behind every eligible candidate -- it never withholds it, since
the detector's documented precision (~77%) includes genuine Results prose. Demotion happens before the reading
budget is sliced, so eligible chunks backfill the slots; a disputed chunk fills a slot only when eligible
candidates run out, and that fallback is logged rather than silently passing as ordinary evidence.

The application has no native (Docling) exclusion authority, so nothing here withholds; ``withheld`` decisions
can only come from the research route. On a library without ``chunk_structure`` rows this is an exact no-op.
"""

from __future__ import annotations

import logging

from sqlalchemy.engine import Connection

from app.backend.persistence.chunk_structure_repo import structure_role_states
from app.backend.summarization.evidence_eligibility import DEMOTED_ANCHORED_ROLES, AnchoredState, decide
from app.backend.summarization.generators import SourceChunk

# Extra ranked candidates fetched beyond the budget so demoted chunks can be backfilled from real eligible ones.
ELIGIBILITY_OVERFETCH = 3

_log = logging.getLogger(__name__)


def _anchored(state) -> AnchoredState:  # type: ignore[no-untyped-def]
    if state is None:
        return AnchoredState("absent")
    detail = {"roles": [state.evidence_role], "chunk_types": [state.chunk_type]}
    if state.state != "current":
        return AnchoredState("stale", 0.0, {**detail, "stale_reason": state.stale_reason})
    if state.evidence_role in DEMOTED_ANCHORED_ROLES:
        return AnchoredState("current_bibliographic", 1.0, detail)
    return AnchoredState("current_other", 0.0, detail)


def split_by_reference_eligibility(
    conn: Connection, ranked: list[SourceChunk]
) -> tuple[list[SourceChunk], list[SourceChunk]]:
    """Stable split of ``ranked`` into (eligible, disputed); relevance order is preserved within each band."""
    states = structure_role_states(conn, [chunk.chunk_id for chunk in ranked])
    if not states:
        return list(ranked), []
    eligible: list[SourceChunk] = []
    disputed: list[SourceChunk] = []
    stale = 0
    for chunk in ranked:
        anchored = _anchored(states.get(chunk.chunk_id))
        stale += anchored.state == "stale"
        # No native authority here, so ``decide`` never reaches the coverage branch that reads ``key_length``;
        # building each chunk's comparison key (~1 ms/chunk) would be pure cost on the selected-papers path.
        decision = decide(str(chunk.chunk_id), key_length=0, native=None, anchored=anchored)
        (disputed if decision.substantive != "eligible" else eligible).append(chunk)
    if disputed or stale:
        _log.info(
            "reference eligibility: %d of %d candidates demoted as disputed bibliography; %d stale labels ignored",
            len(disputed),
            len(ranked),
            stale,
        )
    return eligible, disputed


def order_for_budget(conn: Connection, ranked: list[SourceChunk], top_k: int) -> list[SourceChunk]:
    """Eligible candidates first, disputed only as backfill; logs when a disputed chunk takes a slot."""
    eligible, disputed = split_by_reference_eligibility(conn, ranked)
    ordered = eligible + disputed
    fallback = max(0, min(top_k, len(ordered)) - len(eligible))
    if fallback:
        _log.info("reference eligibility: %d disputed chunk(s) used as fallback to fill the reading budget", fallback)
    return ordered
