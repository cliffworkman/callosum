"""Evidence packets: exact source spans + locators + the explicit basis for every link, built deterministically.

The model only names sentence-unit ids. Here code resolves those ids to exact substrings, checks each one against its own chunk
(`canonical_text_contains` is never relaxed), derives per-span attribution from what the text itself says, attaches VERIFIED
links (a definition elsewhere in the same study), and records the attachment identity. A joined sentence is shown only when the
seam verifier established continuity; otherwise fragments stay separate and are flagged. Nothing is concatenated into a
fabricated quotation: every part keeps its own text, pieces and locator.
"""

from __future__ import annotations

import hashlib

from app.backend.pdf_processing.extraction import canonical_text_contains
from experiments.ask_cli_revised.contract_directed import abstracts, attribution, links, sections, units
from experiments.ask_cli_revised.contract_directed.store import Library

ROLES = ("establishing", "qualifying", "referent")


def neighborhood_units(nbhd: dict, library: Library) -> tuple[list[units.SentenceUnit], dict[int, dict]]:
    """Sentence units over a neighborhood's chunks (seams verified by the library-bound verifier) and the chunk lookup."""
    ordered = library.attachment_chunks(nbhd["attachment_id"])
    by_id = {c["chunk_id"]: c for c in ordered}
    members = [by_id[i] for i in nbhd["chunk_ids"]]
    return units.build_units(members, library.seam_verifier()), by_id


def _section_of(chunk: dict) -> tuple[str | None, str]:
    return sections.family_of(chunk.get("section"), chunk.get("grobid_kind"))


def _verified_pieces(unit_or_piece_list, by_id: dict[int, dict]) -> tuple[list[dict], bool]:
    """Piece dicts for a unit, each checked as an exact, canonical-verbatim slice of its own chunk."""
    out, ok = [], True
    for piece in unit_or_piece_list:
        chunk_text = by_id[piece.chunk_id]["text"]
        exact = chunk_text[piece.start : piece.end] == piece.text
        verbatim = canonical_text_contains(needle=piece.text, haystack=chunk_text)
        ok &= exact and verbatim
        out.append(
            {
                "chunk_id": piece.chunk_id,
                "start": piece.start,
                "end": piece.end,
                "text": piece.text,
                "verbatim_ok": exact and verbatim,
            }
        )
    return out, ok


def _part(span_id: str, role: str, unit_index: int, unit: units.SentenceUnit, by_id: dict[int, dict]) -> dict | None:
    pieces, ok = _verified_pieces(unit.pieces, by_id)
    if not ok:
        return None
    first = by_id[unit.pieces[0].chunk_id]
    family, state = _section_of(first)
    return {
        "span_id": span_id,
        "role": role,
        "unit_index": unit_index,
        "unit_id": unit.unit_id,
        "text": unit.text,
        "pieces": pieces,
        "join": unit.join,
        "open_left": unit.open_left,
        "open_right": unit.open_right,
        "seam": unit.seam,
        "section": family,
        "section_state": state,
        "page_start": first.get("page_start"),
        "page_end": first.get("page_end"),
        "note": None,
        "linked_from": None,
    }


def evidence_form(parts: list[dict]) -> str:
    core = [p for p in parts if p["role"] != "linked_definition"]
    if any(p["open_left"] or p["open_right"] for p in core):
        return "fragments_unresolved_seam"
    if any(p["join"] == "verified_seam" for p in core):
        return "assembled_verified_seam"
    return "verbatim"


def packet_id_for(attachment_checksum: str | None, parts: list[dict]) -> str:
    """Stable id from the exact core spans (source checksum + sorted piece ranges); identical evidence gets an identical id."""
    keys = sorted(
        f"{pc['chunk_id']}:{pc['start']}:{pc['end']}"
        for p in parts
        if p["role"] != "linked_definition"
        for pc in p["pieces"]
    )
    return hashlib.sha256(f"{attachment_checksum}|{'|'.join(keys)}".encode()).hexdigest()[:12]


_PIECE_CACHE: dict[tuple[int, int], list[dict]] = {}


def attachment_piece_index(library: Library, attachment_id: int) -> list[dict]:
    key = (id(library), attachment_id)
    if key not in _PIECE_CACHE:
        _PIECE_CACHE[key] = links.attachment_pieces(library.attachment_chunks(attachment_id))
    return _PIECE_CACHE[key]


def build_packet(
    nbhd: dict,
    unit_list: list[units.SentenceUnit],
    by_id: dict[int, dict],
    proposition: dict,
    *,
    library: Library,
    child_id: str,
    nbhd_units_key: str | None = None,
) -> dict:
    """One packet from one validated localization proposition, or an `unresolved_preserved` record if it cannot be built.

    `proposition`: {establishing, qualifying, referents (unit ids), provenance_class, attribution_basis_phrase, relation_polarity,
    unresolved}. Ids are already validated against `unit_list`.
    """
    index = {u.unit_id: i for i, u in enumerate(unit_list)}
    roles: dict[str, str] = {}
    for role_name, ids in (
        ("establishing", proposition["establishing"]),
        ("qualifying", proposition["qualifying"]),
        ("referent", proposition["referents"]),
    ):
        for uid in ids:
            roles.setdefault(uid, role_name)  # establishing wins over a later role for the same unit
    ordered_ids = sorted(roles, key=lambda uid: index[uid])
    paper = library.paper(nbhd["paper_id"]) or {}
    abstract_clean = abstracts.clean_abstract(paper.get("abstract"))
    attachment = nbhd.get("attachment") or library.attachment(nbhd["attachment_id"]) or {}
    parts: list[dict] = []
    dropped: list[dict] = []
    for n, uid in enumerate(ordered_ids, start=1):
        part = _part(f"p{n}", roles[uid], index[uid], unit_list[index[uid]], by_id)
        if part is None:
            dropped.append({"unit_id": uid, "reason": "piece_not_verbatim_in_its_chunk"})
        else:
            parts.append(part)
    if not any(p["role"] == "establishing" for p in parts):
        return {
            "state": "unresolved_preserved",
            "reason": "no_verifiable_establishing_span",
            "nbhd_id": nbhd["nbhd_id"],
            "child_id": child_id,
            "dropped_parts": dropped,
            "proposition": proposition,
        }

    attributions: dict[str, dict] = {}
    for part in parts:
        if part["role"] == "establishing" or part["role"] == "qualifying" or part["role"] == "referent":
            attributions[part["span_id"]] = attribution.derive_attribution(
                [part["text"]],
                abstract_clean=abstract_clean,
                model_class=proposition.get("provenance_class") if part["role"] == "establishing" else None,
                basis_phrase=proposition.get("attribution_basis_phrase") if part["role"] == "establishing" else None,
                section=part["section"],
            )

    core_texts = [p["text"] for p in parts]
    link_records = links.find_links(
        core_texts,
        attachment_piece_index(library, nbhd["attachment_id"]),
        exclude_chunk_ids=set(nbhd["chunk_ids"]),
        finding_key=nbhd["nbhd_id"] + "|" + "|".join(p["unit_id"] for p in parts),
    )
    for record in link_records:
        if not record["verified"]:
            continue
        linked = record["linked"]
        chunk = by_id.get(linked["chunk_id"]) or library.chunk(linked["chunk_id"])
        chunk_text = chunk["text"]
        exact = chunk_text[linked["start"] : linked["end"]] == linked["text"]
        if not (exact and canonical_text_contains(needle=linked["text"], haystack=chunk_text)):
            record["verified"], record["refusal_reason"] = False, "linked_span_not_verbatim"
            continue
        family, state = _section_of(chunk)
        n = len(parts) + 1
        parts.append(
            {
                "span_id": f"p{n}",
                "role": "linked_definition",
                "unit_index": None,
                "unit_id": None,
                "text": linked["text"],
                "pieces": [
                    {
                        "chunk_id": linked["chunk_id"],
                        "start": linked["start"],
                        "end": linked["end"],
                        "text": linked["text"],
                        "verbatim_ok": True,
                    }
                ],
                "join": "none",
                "open_left": False,
                "open_right": False,
                "seam": None,
                "section": family,
                "section_state": state,
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "note": f'linked by {record["basis"]["type"].replace("_", " ")} "{record["basis"]["designator"]}"',
                "linked_from": record["link_id"],
            }
        )

    return {
        "state": "built",
        "packet_id": packet_id_for(attachment.get("checksum"), parts),
        "paper_id": nbhd["paper_id"],
        "attachment": {k: attachment.get(k) for k in ("id", "role", "checksum", "is_primary")},
        "nbhd_id": nbhd["nbhd_id"],
        "parts": parts,
        "links": link_records,
        "part_attribution": {sid: a["state"] for sid, a in attributions.items()},
        "attribution": attributions,
        "provenance_class_model": proposition.get("provenance_class"),
        "relation_polarity_model": proposition.get("relation_polarity"),
        "evidence_form": evidence_form(parts),
        "unresolved_notes": list(proposition.get("unresolved", [])),
        "dropped_parts": dropped,
        "found_under": [child_id],
    }


def merge_duplicates(packets: list[dict]) -> list[dict]:
    """Identical packets (same id) are one piece of evidence: keep one, union `found_under`. Multiplicity is preserved, not counted."""
    merged: dict[str, dict] = {}
    for packet in packets:
        if packet.get("state") != "built":
            continue
        existing = merged.get(packet["packet_id"])
        if existing is None:
            merged[packet["packet_id"]] = packet
        else:
            existing["found_under"] = sorted(set(existing["found_under"]) | set(packet["found_under"]))
    return list(merged.values())


def overlapping_spans(packets: list[dict]) -> dict[str, list[str]]:
    """Piece key -> packet ids that contain it. Two packets sharing a span are one source, never independent corroboration."""
    seen: dict[str, list[str]] = {}
    for packet in packets:
        for part in packet["parts"]:
            for piece in part["pieces"]:
                seen.setdefault(f"{piece['chunk_id']}:{piece['start']}:{piece['end']}", []).append(packet["packet_id"])
    return {k: v for k, v in seen.items() if len(set(v)) > 1}
