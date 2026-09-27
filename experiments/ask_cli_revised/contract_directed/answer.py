"""The child-answering prompt: one approved contract + its eligible evidence, nothing else.

``PROMPT_TEMPLATE`` is byte-identical to the baseline diagnostic (`child_evidence_diag`), so a difference in an answer
comes from the evidence, not from the instructions. The baseline-compat renderer reproduces the 11 recorded prompts
exactly (the fidelity test). The packet renderer differs from it only in the evidence block: it adds deterministic source
metadata (paper, section, page, attachment role, join/link notes). Those are source attributes, never machine-written
claims. No parent question, sibling wording or sibling evidence is ever rendered.
"""

from __future__ import annotations

PROMPT_TEMPLATE = """You are answering one question for a scholar, using ONLY the source passages listed below. Each passage is exact text from a paper; the bracketed id (for example [U3]) identifies it.

Question (any interpretation notes in square brackets belong to the question):
{contract}

Eligible source passages assigned to this question:
{passages}

Answer the question in natural scientific prose, at whatever length the passages warrant. Cite the passage id(s) you rely on, in square brackets, next to what they support. Report associations as associations, keep the direction of any difference and every qualification a passage states, and do not go beyond what a passage says. If the passages cannot establish an answer to the question, or can establish only part of it, say so explicitly and say which part.
"""
NO_EVIDENCE_BLOCK = "(none: no eligible source passage was assigned to this question)"

CHARS_PER_TOKEN = 3.0  # the conservative estimate the supervisory stages use


def baseline_block(unit: dict) -> str:
    """The baseline diagnostic's exact per-passage rendering."""
    return f'[{unit["unit_id"]}] paper {unit["paper_id"]}\nPassage: "{unit["passage"]}"'


def render_baseline_prompt(contract_text: str, units: list[dict]) -> str:
    blocks = [baseline_block(u) for u in units]
    passages = "\n\n".join(blocks) if blocks else NO_EVIDENCE_BLOCK
    return PROMPT_TEMPLATE.format(contract=contract_text, passages=passages)


# ---- packet rendering (the new evidence block) ---------------------------------------------------------------------------

_SECTION_LABELS = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "methods": "Methods",
    "results": "Results",
    "discussion": "Discussion",
    "references": "References",
    "supplementary_material": "Supplementary material",
}


def _page(part: dict) -> str | None:
    start, end = part.get("page_start"), part.get("page_end")
    if start is None:
        return None
    return f"p.{start}" if end in (None, start) else f"p.{start}-{end}"


def _label(part: dict) -> str:
    bits = []
    section = part.get("section")
    if section:
        bits.append(_SECTION_LABELS.get(section, section.replace("_", " ").capitalize()))
    page = _page(part)
    if page:
        bits.append(page)
    return " · ".join(bits)


def _attachment_label(packet: dict) -> str:
    att = packet.get("attachment") or {}
    if att.get("id") is None:
        return ""
    role = "primary" if att.get("is_primary") else "alternate attachment, role " + str(att.get("role") or "unset")
    return f"attachment {att['id']} ({role})"


def packet_block(packet_number: int, packet: dict) -> str:
    """One packet as the answerer sees it. Every part keeps its own exact text; nothing is merged into a quotation."""
    pid = f"P{packet_number}"
    head_bits = [f"paper {packet['paper_id']}"]
    attachment = _attachment_label(packet)
    if attachment:
        head_bits.append(attachment)
    parts = packet["parts"]
    if len(parts) == 1 and not parts[0].get("note"):
        part = parts[0]
        label = _label(part)
        if label:
            head_bits.append(label)
        return f'[{pid}] {" · ".join(head_bits)}\nPassage: "{part["text"]}"'
    lines = [f"[{pid}] {' · '.join(head_bits)}"]
    for index, part in enumerate(parts):
        tag = f"({chr(ord('a') + index)})"
        label = _label(part)
        note = part.get("note")
        prefix = " ".join(bit for bit in (tag, label + " —" if label else "—", f"{note} —" if note else "") if bit)
        lines.append(f'  {prefix} "{part["text"]}"')
    return "\n".join(lines)


def render_packet_prompt(contract_text: str, packets: list[dict]) -> tuple[str, dict[str, str]]:
    """Return (prompt, id_map): id_map maps each shown id ("P1", ...) to its packet_id."""
    blocks, id_map = [], {}
    for number, packet in enumerate(packets, start=1):
        blocks.append(packet_block(number, packet))
        id_map[f"P{number}"] = packet["packet_id"]
    passages = "\n\n".join(blocks) if blocks else NO_EVIDENCE_BLOCK
    return PROMPT_TEMPLATE.format(contract=contract_text, passages=passages), id_map


def select_within_context(
    contract_text: str, packets: list[dict], *, num_ctx: int = 12288, allowance: int = 4096
) -> tuple[list[dict], list[str]]:
    """Keep packets in the caller's priority order while the estimated prompt fits; never truncate a packet.

    Returns (kept, omitted_packet_ids). An omitted packet is recorded, not silently dropped.
    """
    kept: list[dict] = []
    omitted: list[str] = []
    for packet in packets:
        candidate = kept + [packet]
        prompt, _ = render_packet_prompt(contract_text, candidate)
        if len(prompt) / CHARS_PER_TOKEN + allowance > num_ctx:
            omitted.append(packet["packet_id"])
        else:
            kept = candidate
    return kept, omitted
