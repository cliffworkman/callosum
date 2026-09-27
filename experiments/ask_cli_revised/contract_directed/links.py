"""Explicit, verifiable links between spans of the SAME study (same attachment): a bundle, never a co-occurrence.

A finding stated in Results or Discussion may depend on a definition given elsewhere in the paper ("less generosity in the DG"
depends on Methods: "the Dictator Game (DG), one player decides how to split an endowment"). A link is accepted only when the
source itself establishes the connection through a checkable designator:

* `definition_acronym`: span A uses an acronym; span B defines it as "Full Term (ACR)" with matching initials.
* `shared_designator`: a specific named measure/task ("Just World Beliefs Scale", "Dictator Game") appears verbatim in both.
* `explicit_reference`: span A refers to "Table 2" / "Study 1" / "Figure 3"; span B is that caption or heading.

Topical or lexical co-occurrence (both mention "amygdala") is NOT a link. Linked spans may supply only descriptive slots
(instrument / procedure / population / pairing); the finding-bearing slots must come from the core proposition (closure.py).
Every link records both exact spans, their locators, the designator and the basis type; a study-label conflict (Study 1 vs
Study 2) refuses the link. Pure: no connection, no model.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from experiments.ask_cli_revised.contract_directed import sections, units

MAX_DESIGNATORS = 4
_STOP_ACRONYMS = frozenset({"THE", "AND", "FOR", "USA", "PDF", "NOT", "ALL", "ONE", "TWO", "DNA", "HTML", "ISBN"})
_DEFINITION_STOP = frozenset({"of", "the", "and", "for", "in", "to", "a", "an", "on", "with"})
_ACRONYM = re.compile(r"\b[A-Z]{2,6}\b")
_INSTRUMENT = re.compile(
    r"\b(?:[A-Z][\w\-]*\s+){1,4}(?:[Ss]cale|[Ii]ndex|[Qq]uestionnaire|Test|Game|Task|Inventory|Paradigm|Survey|Battery|Checklist|Interview)\b"
)
_LABEL = re.compile(r"\b(?:Supplementary\s+)?(?:Table|Figure|Fig\.|Study|Experiment|Hypothesis)\s+S?\d+[A-Za-z]?\b")
_STUDY = re.compile(r"\b(?:Study|Experiment)\s+(\d+)\b")
_PAREN_ACRONYM = re.compile(r"\(([A-Za-z]{2,7})s?\)")
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]*")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Designator:
    kind: str  # "acronym" | "instrument" | "label"
    surface: str


def _norm(text: str) -> str:
    return _WS.sub(" ", text.replace("-", " ")).strip().lower()


def definition_pairs(text: str) -> list[tuple[str, str]]:
    """(ACRONYM, full term surface) for every 'Full Term (ACR)' in `text` whose initials match the acronym."""
    pairs = []
    for match in _PAREN_ACRONYM.finditer(text):
        acronym = match.group(1)
        words = list(_WORD.finditer(text[: match.start()]))[-9:]
        for k in range(len(acronym), min(len(words), len(acronym) + 3) + 1):
            candidate = words[-k:]
            initials = "".join(w.group(0)[0] for w in candidate if w.group(0).lower() not in _DEFINITION_STOP)
            if initials.lower() == acronym.lower():
                surface = text[candidate[0].start() : match.start()].strip()
                pairs.append((acronym.upper(), surface))
                break
    return pairs


def extract_designators(text: str) -> list[Designator]:
    """Checkable designators in a span, most specific first; capped so linking stays bounded."""
    found: list[Designator] = []
    seen: set[str] = set()

    def add(kind: str, surface: str) -> None:
        key = f"{kind}:{_norm(surface)}"
        if key not in seen:
            seen.add(key)
            found.append(Designator(kind, surface.strip()))

    for m in _INSTRUMENT.finditer(text):
        add("instrument", m.group(0))
    for m in _LABEL.finditer(text):
        add("label", m.group(0))
    for m in _ACRONYM.finditer(text):
        if m.group(0) not in _STOP_ACRONYMS:
            add("acronym", m.group(0))
    return found[:MAX_DESIGNATORS]


def _contains(haystack: str, needle: str) -> bool:
    return _norm(needle) in _norm(haystack)


def _study_labels(text: str) -> set[str]:
    return set(_STUDY.findall(text))


def verify_link(finding_texts: list[str], linked_text: str, basis: dict) -> tuple[bool, str | None]:
    """(verified, refusal reason). Deterministic: the designator must be checkable in BOTH spans."""
    joined = " ".join(finding_texts)
    kind, surface = basis["type"], basis["designator"]
    finding_studies, linked_studies = _study_labels(joined), _study_labels(linked_text)
    if finding_studies and linked_studies and not (finding_studies & linked_studies):
        return False, "study_label_conflict"
    if kind == "definition_acronym":
        in_finding = re.search(rf"\b{re.escape(surface)}\b", joined) is not None
        defined = any(acr == surface.upper() for acr, _ in definition_pairs(linked_text))
        return (True, None) if in_finding and defined else (False, "acronym_not_used_or_not_defined")
    if kind == "shared_designator":
        ok = _contains(joined, surface) and _contains(linked_text, surface)
        return (True, None) if ok else (False, "designator_not_in_both_spans")
    if kind == "explicit_reference":
        opening = _norm(linked_text).startswith(_norm(surface))
        ok = _contains(joined, surface) and opening
        return (True, None) if ok else (False, "reference_target_not_found")
    return False, "unknown_basis"


def _link_id(finding_key: str, chunk_id: int, start: int, designator: str) -> str:
    return hashlib.sha256(f"{finding_key}|{chunk_id}|{start}|{designator}".encode()).hexdigest()[:12]


def find_links(
    finding_texts: list[str],
    attachment_pieces: list[dict],
    *,
    exclude_chunk_ids: set[int],
    finding_key: str = "",
) -> list[dict]:
    """Candidate links for a finding's spans, each verified or refused with its reason (both are recorded).

    `attachment_pieces`: dicts {chunk_id, start, end, text, section, grobid_kind?, page_start} for the finding's attachment, in
    document order. Chunks in `exclude_chunk_ids` (the finding's own neighborhood) and References are never link targets.
    At most one link per designator: the first verifying occurrence, preferring Methods/unlabelled text, plus an occurrence count.
    """
    joined = " ".join(finding_texts)
    results: list[dict] = []
    for designator in extract_designators(joined):
        candidates = []
        for piece in attachment_pieces:
            if piece["chunk_id"] in exclude_chunk_ids:
                continue
            family, _ = sections.family_of(piece.get("section"), piece.get("grobid_kind"))
            if family == "references":
                continue
            text = piece["text"]
            if designator.kind == "acronym":
                if any(acr == designator.surface for acr, _ in definition_pairs(text)):
                    candidates.append((piece, {"type": "definition_acronym", "designator": designator.surface}))
            elif designator.kind == "instrument":
                if _contains(text, designator.surface):
                    candidates.append((piece, {"type": "shared_designator", "designator": designator.surface}))
            elif designator.kind == "label" and _norm(text).startswith(_norm(designator.surface)):
                candidates.append((piece, {"type": "explicit_reference", "designator": designator.surface}))
        if not candidates:
            continue
        candidates.sort(key=lambda pc: (_family_rank(pc[0]), pc[0]["chunk_id"], pc[0]["start"]))
        for piece, basis in candidates:
            ok, reason = verify_link(finding_texts, piece["text"], basis)
            if ok:
                results.append(_record(finding_key, piece, basis, True, None, len(candidates)))
                break
        else:
            piece, basis = candidates[0]
            results.append(
                _record(
                    finding_key,
                    piece,
                    basis,
                    False,
                    verify_link(finding_texts, piece["text"], basis)[1],
                    len(candidates),
                )
            )
    return results


def _family_rank(piece: dict) -> int:
    family, _ = sections.family_of(piece.get("section"), piece.get("grobid_kind"))
    return {"methods": 0, None: 1}.get(family, 2)


def _record(finding_key: str, piece: dict, basis: dict, verified: bool, reason: str | None, occurrences: int) -> dict:
    return {
        "link_id": _link_id(finding_key, piece["chunk_id"], piece["start"], basis["designator"]),
        "basis": basis,
        "verified": verified,
        "refusal_reason": reason,
        "occurrences": occurrences,
        "linked": {
            "chunk_id": piece["chunk_id"],
            "start": piece["start"],
            "end": piece["end"],
            "text": piece["text"],
            "section": piece.get("section"),
            "page_start": piece.get("page_start"),
        },
    }


def attachment_pieces(chunks: list[dict]) -> list[dict]:
    """Piece dicts for `find_links` from ordered chunk dicts (chunk_id, text, section, page_start, ...)."""
    out = []
    for chunk in chunks:
        for piece in units.chunk_pieces(chunk["chunk_id"], chunk["text"]):
            out.append(
                {
                    "chunk_id": piece.chunk_id,
                    "start": piece.start,
                    "end": piece.end,
                    "text": piece.text,
                    "section": chunk.get("section"),
                    "grobid_kind": chunk.get("grobid_kind"),
                    "page_start": chunk.get("page_start"),
                }
            )
    return out
