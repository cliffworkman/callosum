"""One bounded, contract-directed recovery pass for a child whose obligation units are unresolved or only partially established.

Recovery revisits what was already found or set aside, not only unvisited papers. Candidate actions, in priority order:
 1. `read_budget_capped_neighborhood`: a neighborhood the first pass had to defer for the budget (best for the unresolved unit);
 2. `widen_neighborhood`: a larger neighborhood around the anchor of a packet that only partially established a unit, or whose
    referent/seam was unresolved;
 3. `other_section_family`: a section family the unit points to that no read neighborhood of an inspected paper covered;
 4. `other_attachment`: a different article attachment of an inspected paper (labelled alternate, never counted as corroboration);
 5. `deferred_paper`: a nominated paper the first pass did not inspect.
Every action keeps the ORIGINAL failed route (`recovers`) and the reason recovery was needed (`trigger_reason`); nothing already
recorded is edited (append-only). The pass is capped at `cap` neighborhoods in total.
"""

from __future__ import annotations

from experiments.ask_cli_revised.contract_directed import anchors as anchors_mod
from experiments.ask_cli_revised.contract_directed import coverage, neighborhood, sections
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract

RECOVERY_CAP = 6
WIDE_SIDE = 6
WIDE_CHARS = 12000
DEFERRED_PAPERS = 2


def _nbhd_at(
    library,
    attachment: dict,
    chunk_id: int,
    *,
    routes: list[str],
    unit_scores: dict | None = None,
    wide: bool = False,
    score: float = 0.0,
) -> dict | None:
    ordered = library.attachment_chunks(attachment["id"])
    index = next((i for i, c in enumerate(ordered) if c["chunk_id"] == chunk_id), None)
    if index is None:
        return None
    kwargs = {"max_side": WIDE_SIDE, "max_chars": WIDE_CHARS, "cross_sections": True} if wide else {}
    nb = neighborhood.build_neighborhood(ordered, index, **kwargs)
    nb.update(
        {
            "anchors": [{"chunk_id": chunk_id, "routes": routes, "route_scores": {r: score for r in routes}}],
            "routes": routes,
            "unit_scores": unit_scores or {},
            "best_score": score,
            "attachment": {k: attachment[k] for k in ("id", "role", "checksum", "is_primary")},
            "recovery": True,
        }
    )
    return nb


def _covered_chunks(neighborhoods: list[dict]) -> set[int]:
    return {c for n in neighborhoods for c in n["chunk_ids"]}


def plan_recovery(
    child: ChildContract,
    rows: list[dict],
    *,
    read: list[dict],
    capped: list[dict],
    inspected: list[int],
    deferred: list[int],
    packets_by_id: dict[str, dict],
    library,
    retriever,
    cap: int = RECOVERY_CAP,
) -> list[dict]:
    unresolved = coverage.unresolved_content_rows(rows)
    if not unresolved:
        return []
    actions: list[dict] = []
    seen_nbhds = {n["nbhd_id"] for n in read}
    covered = _covered_chunks(read)

    def add(row: dict, trigger: str, action: str, recovers: dict, nbhd: dict | None) -> None:
        if nbhd is None or len(actions) >= cap or nbhd["nbhd_id"] in seen_nbhds:
            return
        seen_nbhds.add(nbhd["nbhd_id"])
        actions.append(
            {
                "recovery_id": f"{child.child_id}:r{len(actions) + 1}",
                "child_id": child.child_id,
                "unit_id": row["unit_id"],
                "trigger_reason": trigger,
                "action": action,
                "recovers": recovers,
                "nbhd": nbhd,
            }
        )

    # 1. budget-capped neighborhoods, best first for each unresolved unit
    for row in unresolved:
        candidates = sorted(
            (n for n in capped if row["unit_id"] in n.get("unit_scores", {})),
            key=lambda n: -n["unit_scores"][row["unit_id"]],
        )
        for nb in candidates[:2]:
            add(row, "budget_capped", "read_budget_capped_neighborhood",
                {"nbhd_id": nb["nbhd_id"], "paper_id": nb["paper_id"], "why": "deferred by the neighborhood budget in the first pass"}, nb)  # fmt: skip

    # 2. widen around the anchor of a partially established packet (or one with an unresolved referent / seam)
    by_nbhd = {n["nbhd_id"]: n for n in read}
    for row in unresolved:
        for pid in row.get("partial_packet_ids", []):
            packet = packets_by_id.get(pid)
            origin = by_nbhd.get(packet["nbhd_id"]) if packet else None
            if origin is None or not origin["anchor_chunk_ids"]:
                continue
            missing = (row.get("missing_by_partial_packet", {}).get(pid) or {}).get("missing", [])
            trigger = (
                "seam_unresolved" if packet["evidence_form"] == "fragments_unresolved_seam"
                else ("unresolved_referent" if packet.get("unresolved_notes") else f"partial_slot:{','.join(missing[:2]) or 'unspecified'}")
            )  # fmt: skip
            nb = _nbhd_at(
                library,
                origin["attachment"],
                origin["anchor_chunk_ids"][0],
                routes=["recovery:widen"],
                wide=True,
                unit_scores=origin.get("unit_scores"),
            )
            if nb is not None and len(nb["chunk_ids"]) > len(origin["chunk_ids"]):
                add(
                    row,
                    trigger,
                    "widen_neighborhood",
                    {
                        "nbhd_id": origin["nbhd_id"],
                        "packet_id": pid,
                        "paper_id": origin["paper_id"],
                        "missing": missing,
                    },
                    nb,
                )

    # 3. another section family of an inspected paper, and 4. another attachment of an inspected paper
    for row in unresolved:
        unit = child.unit(row["unit_id"])
        families = sections.families_for_units([unit.kind])
        for paper_id in inspected:
            attachments = library.article_attachments(paper_id)
            if not attachments:
                continue
            working = attachments[0]
            chunks = library.attachment_chunks(working["id"])
            read_here = [n for n in read if n["paper_id"] == paper_id]
            families_read = {a.get("family") for n in read_here for a in n.get("anchors", [])}
            unread = tuple(f for f in families if f not in families_read)
            if unread:
                pool = [c for c in sections.family_pool(chunks, unread) if c["chunk_id"] not in covered]
                hits = retriever.search(unit.text, chunk_ids={c["chunk_id"] for c in pool}, top_k=3) if pool else []
                if hits:
                    add(row, "no_closing_packet", "other_section_family", {"paper_id": paper_id, "families_wanted": list(families), "families_read": sorted(f for f in families_read if f)},
                        _nbhd_at(library, working, hits[0].chunk_id, routes=[f"recovery:section_family:{row['unit_id']}"], unit_scores={row["unit_id"]: hits[0].score}, score=hits[0].score))  # fmt: skip
            for alt in attachments[1:]:
                alt_chunks = library.attachment_chunks(alt["id"])
                pool = sections.family_pool(alt_chunks, families)
                hits = retriever.search(unit.text, chunk_ids={c["chunk_id"] for c in pool}, top_k=3) if pool else []
                if hits:
                    add(row, "no_closing_packet", "other_attachment", {"paper_id": paper_id, "primary_attachment": working["id"], "alternate_attachment": alt["id"], "note": "alternate attachment; never counted as corroboration of the primary"},
                        _nbhd_at(library, alt, hits[0].chunk_id, routes=[f"recovery:other_attachment:{row['unit_id']}"], unit_scores={row["unit_id"]: hits[0].score}, score=hits[0].score))  # fmt: skip

    # 5. deferred papers (the first pass did not inspect them)
    first = unresolved[0]
    for paper_id in deferred[:DEFERRED_PAPERS]:
        anchor_set = anchors_mod.select_anchors(child, paper_id, library, retriever)
        candidates = anchors_mod.neighborhoods_for(anchor_set, library)
        candidates = [n for n in candidates if first["unit_id"] in n.get("unit_scores", {})] or candidates
        if candidates:
            best = max(candidates, key=lambda n: n.get("unit_scores", {}).get(first["unit_id"], n["best_score"]))
            best = {**best, "recovery": True}
            add(
                first,
                "paper_deferred",
                "deferred_paper",
                {"paper_id": paper_id, "why": "nominated but not inspected in the first pass"},
                best,
            )
    return actions
