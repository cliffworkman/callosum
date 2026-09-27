"""Bounded, structurally coherent neighborhoods around an anchor chunk (pure over an ordered chunk list).

A neighborhood is the anchor plus up to `MAX_SIDE` chunks on each side of the SAME attachment, clipped by: the attachment
edges; the References section; a section-family change (only between two KNOWN, different families; unknown labels never form a
boundary); the character budget. If the text is still shorter than `MIN_CHARS` (line-level chunking can make seven chunks a
couple of hundred characters) it keeps growing, up to `MAX_SIDE_EXTENDED` chunks per side, until it is readable.
One deliberate crossing: when the edge sentence is visibly open (no terminal punctuation) and the neighbor begins as its
continuation, ONE chunk may be taken across a family boundary so the sentence can be read (the seam verifier, not this module,
decides whether that join is real). Overlapping neighborhoods of one attachment merge if the union stays readable once.
Every clipping decision is recorded in `rule_trace`.
"""

from __future__ import annotations

import hashlib

from experiments.ask_cli_revised.contract_directed import sections, units

MAX_SIDE = 3
MAX_CHARS = 9000
MIN_CHARS = 1200
MAX_SIDE_EXTENDED = 12
MAX_MERGED_CHUNKS = 26
MAX_MERGED_CHARS = 12000


def _family(chunk: dict) -> str | None:
    return sections.family_of(chunk.get("section"), chunk.get("grobid_kind"))[0]


def _continues(left: dict, right: dict) -> bool:
    """Would `right` plausibly continue `left`: left's last sentence is open and right's first begins as a continuation?"""
    left_pieces = units.chunk_pieces(left["chunk_id"], left["text"])
    right_pieces = units.chunk_pieces(right["chunk_id"], right["text"])
    if not left_pieces or not right_pieces:
        return False
    return not units.ends_terminal(left_pieces[-1].text) and units.starts_as_continuation(right_pieces[0].text)


def _nbhd_id(attachment_id: int, chunk_ids: list[int]) -> str:
    return hashlib.sha256(f"{attachment_id}|{chunk_ids[0]}|{chunk_ids[-1]}|{len(chunk_ids)}".encode()).hexdigest()[:12]


def build_neighborhood(
    ordered: list[dict],
    anchor_index: int,
    *,
    max_side: int = MAX_SIDE,
    max_chars: int = MAX_CHARS,
    min_chars: int = MIN_CHARS,
    max_side_extended: int = MAX_SIDE_EXTENDED,
    cross_sections: bool = False,
) -> dict:
    """Neighborhood around `ordered[anchor_index]`. `ordered`: one attachment's chunks in stream order.

    `cross_sections` lets growth pass a section-family change (recovery uses it: a missing referent or definition may live in
    another section). References, attachment edges and the character budget still bound it.
    """
    anchor = ordered[anchor_index]
    lo = hi = anchor_index
    total = len(anchor["text"])
    trace: list[dict] = []
    boundary = {"left": "max_side", "right": "max_side"}
    open_sides = {"left": True, "right": True}
    anchor_family = _family(anchor)
    step = 0
    for step in range(1, max_side_extended + 1):
        if step > max_side and total >= min_chars:
            step -= 1
            break
        for side in ("left", "right"):
            if not open_sides[side]:
                continue
            idx = lo - 1 if side == "left" else hi + 1
            if idx < 0 or idx >= len(ordered):
                open_sides[side], boundary[side] = False, "attachment_edge"
                trace.append({"side": side, "stop": "attachment_edge"})
                continue
            cand = ordered[idx]
            edge = ordered[lo] if side == "left" else ordered[hi]
            family = _family(cand)
            if family == "references":
                open_sides[side], boundary[side] = False, "references"
                trace.append({"side": side, "stop": "references", "chunk_id": cand["chunk_id"]})
                continue
            crossing = (
                family is not None and anchor_family is not None and family != anchor_family and not cross_sections
            )
            if crossing:
                completes = _continues(edge, cand) if side == "right" else _continues(cand, edge)
                if not completes:
                    open_sides[side], boundary[side] = False, f"section_change:{anchor_family}->{family}"
                    trace.append({"side": side, "stop": "section_change", "from": anchor_family, "to": family})
                    continue
                trace.append(
                    {"side": side, "cross": "one_chunk_to_complete_an_open_sentence", "chunk_id": cand["chunk_id"]}
                )
                open_sides[side], boundary[side] = False, "section_change_after_completion"
            if total + len(cand["text"]) > max_chars:
                open_sides[side], boundary[side] = False, "char_budget"
                trace.append({"side": side, "stop": "char_budget", "chars": total})
                continue
            total += len(cand["text"])
            if side == "left":
                lo = idx
            else:
                hi = idx
        if not any(open_sides.values()):
            break
    if step > max_side:
        trace.append({"extended_for_min_chars": min_chars, "steps": step})
    members = ordered[lo : hi + 1]
    chunk_ids = [c["chunk_id"] for c in members]
    return {
        "nbhd_id": _nbhd_id(anchor["attachment_id"], chunk_ids),
        "paper_id": anchor["paper_id"],
        "attachment_id": anchor["attachment_id"],
        "anchor_chunk_ids": [anchor["chunk_id"]],
        "chunk_ids": chunk_ids,
        "boundary": boundary,
        "char_len": sum(len(c["text"]) for c in members),
        "rule_trace": trace,
    }


def merge_neighborhoods(nbhds: list[dict], ordered_by_attachment: dict[int, list[dict]]) -> list[dict]:
    """Merge neighborhoods of the same attachment whose chunk ranges overlap or touch, if the union stays readable once.

    Anchors and per-anchor routes are unioned. A union over the caps is NOT merged (the neighborhoods stay separate and may
    overlap); nothing is dropped.
    """
    by_att: dict[int, list[dict]] = {}
    for n in nbhds:
        by_att.setdefault(n["attachment_id"], []).append(n)
    out: list[dict] = []
    for att, group in by_att.items():
        ordered = ordered_by_attachment[att]
        text_len = {c["chunk_id"]: len(c["text"]) for c in ordered}
        pos = {c["chunk_id"]: i for i, c in enumerate(ordered)}
        group = sorted(group, key=lambda n: pos[n["chunk_ids"][0]])
        current: dict | None = None
        for n in group:
            if current is None:
                current = dict(n, anchor_chunk_ids=list(n["anchor_chunk_ids"]), merged_from=[n["nbhd_id"]])
                continue
            touches = pos[n["chunk_ids"][0]] <= pos[current["chunk_ids"][-1]] + 1
            union = ordered[
                pos[current["chunk_ids"][0]] : max(pos[current["chunk_ids"][-1]], pos[n["chunk_ids"][-1]]) + 1
            ]
            union_chars = sum(text_len[c["chunk_id"]] for c in union)
            if touches and len(union) <= MAX_MERGED_CHUNKS and union_chars <= MAX_MERGED_CHARS:
                ids = [c["chunk_id"] for c in union]
                current = {
                    **current,
                    "nbhd_id": _nbhd_id(att, ids),
                    "chunk_ids": ids,
                    "anchor_chunk_ids": sorted(set(current["anchor_chunk_ids"]) | set(n["anchor_chunk_ids"])),
                    "char_len": union_chars,
                    "boundary": {"left": current["boundary"]["left"], "right": n["boundary"]["right"]},
                    "rule_trace": current["rule_trace"] + n["rule_trace"],
                    "merged_from": current["merged_from"] + [n["nbhd_id"]],
                }
            else:
                out.append(current)
                current = dict(n, anchor_chunk_ids=list(n["anchor_chunk_ids"]), merged_from=[n["nbhd_id"]])
        if current is not None:
            out.append(current)
    return out
