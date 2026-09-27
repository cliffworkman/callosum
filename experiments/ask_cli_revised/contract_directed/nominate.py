"""S1 paper nomination: existing routes, unioned, each with its provenance, under a recorded cap. Not the centerpiece.

Routes: `direct_chunk` (whole-library chunk-first search with the child-only query), `paper_meta_knn` and `axis` (the existing
paper-metadata embedding + axis neighborhood nominators). A nomination is a lead, never evidence. Papers over the cap are
recorded as `capped_out`, not dropped silently. `inspect_order` then ranks the nominated papers that can actually be read.
"""

from __future__ import annotations

from experiments.ask_cli_revised import discovery
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract
from experiments.ask_cli_revised.contract_directed.retriever import Retriever
from experiments.ask_cli_revised.contract_directed.store import Library

NOMINATION_CAP = 25  # same as the baseline's per-subquestion nomination cap
DIRECT_TOP_K = 60
INSPECT_CAP = 6


def nominate(
    child: ChildContract, library: Library, retriever: Retriever, *, axis_cache: dict, cap: int = NOMINATION_CAP
) -> dict:
    query = child.retrieval_query()
    routes: dict[int, list[dict]] = {}

    seen: set[int] = set()
    for hit in retriever.search(query, top_k=DIRECT_TOP_K):
        if hit.paper_id in seen:
            continue
        seen.add(hit.paper_id)
        routes.setdefault(hit.paper_id, []).append(
            {"route": "direct_chunk", "rank": len(seen), "score": round(hit.score, 4), "chunk_id": hit.chunk_id}
        )
    with library.engine.connect() as conn:
        noms, _log = discovery.nominate_papers(
            conn, subquestion_text=query, model=retriever.model, vector_store=retriever.store, axis_cache=axis_cache
        )
    for rank, nom in enumerate(noms, start=1):
        for reason in nom.reasons:
            route = "paper_meta_knn" if reason == "paper_kNN" else "axis"
            score = nom.direct_score if route == "paper_meta_knn" else nom.axis_score
            routes.setdefault(nom.paper_id, []).append(
                {"route": route, "rank": rank, "score": round(float(score), 4), "detail": reason}
            )

    def priority(paper_id: int):
        rs = routes[paper_id]
        return (-len({r["route"] for r in rs}), -max(r["score"] for r in rs), paper_id)

    ordered = sorted(routes, key=priority)
    kept, capped = ordered[:cap], ordered[cap:]
    return {
        "child_id": child.child_id,
        "query_view": "child_only",
        "query_text": query,
        "nominations": [
            {"child_id": child.child_id, "paper_id": p, "routes": routes[p], "budget_state": "nominated"} for p in kept
        ],
        "capped_out": [
            {"child_id": child.child_id, "paper_id": p, "routes": routes[p], "budget_state": "capped_out"}
            for p in capped
        ],
    }


def inspect_order(
    nominated: list[dict], library: Library, triage: dict[int, dict] | None = None, *, cap: int = INSPECT_CAP
) -> dict:
    """Which nominated papers are read first. Deterministic: triage relation (when run) > route breadth > best score > id.

    A paper with no readable article chunks is never dropped: it is recorded as `not_inspectable_no_chunks` (an abstract-only
    lead). Papers beyond the cap are recorded `deferred` (available to recovery).
    """
    rank_of = {"directly_addresses": 0, "possibly_addresses": 1, "cannot_tell": 2, "topical_only": 4, "not_relevant": 5}
    readable, unreadable = [], []
    for nom in nominated:
        (readable if library.article_attachments(nom["paper_id"]) else unreadable).append(nom)

    def key(nom: dict):
        rs = nom["routes"]
        tri = (triage or {}).get(nom["paper_id"], {}).get("relation_to_child")
        return (rank_of.get(tri, 3), -len({r["route"] for r in rs}), -max(r["score"] for r in rs), nom["paper_id"])

    ranked = sorted(readable, key=key)
    return {
        "inspect": [n["paper_id"] for n in ranked[:cap]],
        "deferred": [n["paper_id"] for n in ranked[cap:]],
        "not_inspectable_no_chunks": [n["paper_id"] for n in unreadable],
    }
