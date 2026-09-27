"""Prompt renderers for the three judgment stages. Each shows the model ONE approved child contract (never the parent question or
a sibling) and exact source text, and asks for ids and short labels only.
"""

from __future__ import annotations

from experiments.ask_cli_revised.contract_directed import closure, schemas
from experiments.ask_cli_revised.contract_directed.answer import _SECTION_LABELS
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract

NO_ABSTRACT = "(no abstract available)"


def _label(family: str | None, page: int | None) -> str:
    bits = []
    if family:
        bits.append(_SECTION_LABELS.get(family, family.replace("_", " ").capitalize()))
    if page is not None:
        bits.append(f"p.{page}")
    return " · ".join(bits)


# ---- S2 triage --------------------------------------------------------------------------------------------------------------

TRIAGE_TEMPLATE = """You are screening one paper for a scholar, using only its title and abstract. An abstract can be incomplete or overgeneralized: treat it as a lead to inspect, never as verified evidence.

Question (any interpretation notes in square brackets belong to the question):
{contract}

Paper title: {title}
Abstract:
{abstract}

Return:
- contribution_type: what this paper contributes, judged only from the title and abstract (original_empirical = it reports its own new study; review_or_meta_analysis = it reviews or pools other work and may report its own synthesis; theory_or_commentary; methods_or_instrument = it introduces or validates a measure or method; undeterminable if you cannot tell).
- relation_to_child: directly_addresses = the abstract itself states something the question asks for; possibly_addresses = it may contain what is asked but the abstract does not say; topical_only = same topic but not what is asked; not_relevant; cannot_tell.
- abstract_quote: copy ONE sentence from the abstract EXACTLY as written that is your strongest basis, or an empty string if there is none.
- reason: one short sentence.
Do not use knowledge from outside the title and abstract."""


def render_triage(child: ChildContract, title: str, abstract_clean: str) -> str:
    return TRIAGE_TEMPLATE.format(
        contract=child.contract_text, title=title or "(untitled)", abstract=abstract_clean or NO_ABSTRACT
    )


# ---- S4 localization --------------------------------------------------------------------------------------------------------

LOCALIZE_TEMPLATE = """You are helping a scholar locate source text. You are given one question and a numbered list of sentence units from one part of a paper. Each unit is exact source text.

Question (any interpretation notes in square brackets belong to the question):
{contract}

Paper: {title}

Sentence units (id, then section and page when known):
{units}

A unit marked "fragment" is cut off at a page-block boundary and its continuation is NOT verified. Never assume two fragments continue each other.

Find any statements in these units that bear on the question. For each one, return ONLY unit ids and short labels, never quotes or your own wording:
- establishing: the unit(s) that themselves state what the question asks for.
- qualifying: unit(s) that limit or condition it (subgroup, moderator, null result, caveat, statistical qualification).
- referents: unit(s) that define what a pronoun or term in the establishing unit(s) refers to (a definition, a table or figure heading), only if visible above.
- provenance_class: what the establishing statement attributes to whom. this_study_reports = the paper reports it as its own result; review_own_synthesis = a review or meta-analysis reporting its own pooled result; recounts_other_study = it describes what earlier work found; background_generic = a general statement of background with no attribution to a result; hypothesis_or_speculation = a hypothesis, proposal or possibility; methods = a description of what was done or measured; null_result = the paper reports no effect or association; cannot_tell = you cannot tell from these units.
- attribution_basis_phrase: the exact words in the establishing unit(s) that show who the statement is attributed to (for example "we found", "previous studies", "participants completed"), or an empty string.
- relation_polarity: if the statement is about how two things are related: association, none (no association), mixed, or not_stated (it does not say whether they are related); not_a_relation if it is not about a relation.
- unresolved: what is needed to interpret it that is NOT visible in these units (for example "the measure called DG is defined elsewhere"), up to three short notes.
A statement that is only about the same topic, without stating what the question asks, is not establishing. A section heading does not tell you who a statement is attributed to: an Introduction may preview this paper's own findings and a Discussion may recount other studies, so read the sentence itself. If nothing here bears on the question, return an empty propositions list and set none_established to true. Do not use knowledge from outside the units."""


def unit_lines(unit_list, by_id: dict[int, dict]) -> str:
    from experiments.ask_cli_revised.contract_directed import sections

    lines = []
    for unit in unit_list:
        chunk = by_id[unit.pieces[0].chunk_id]
        family, _ = sections.family_of(chunk.get("section"), chunk.get("grobid_kind"))
        label = _label(family, chunk.get("page_start"))
        notes = []
        if unit.open_left:
            notes.append("fragment: begins mid-sentence, the preceding text is not verified")
        if unit.open_right:
            notes.append("fragment: ends mid-sentence, the continuation is not verified")
        if unit.join == "verified_seam":
            notes.append("joined across chunk boundaries; continuity verified by layout")
        meta = "; ".join(bit for bit in [label] + notes if bit)
        lines.append(f"[{unit.unit_id}] ({meta}) {unit.text}" if meta else f"[{unit.unit_id}] {unit.text}")
    return "\n".join(lines)


def render_localization(child: ChildContract, title: str, unit_list, by_id: dict[int, dict]) -> str:
    return LOCALIZE_TEMPLATE.format(
        contract=child.contract_text, title=title or "(untitled)", units=unit_lines(unit_list, by_id)
    )


# ---- S6 eligibility ---------------------------------------------------------------------------------------------------------

ELIGIBILITY_TEMPLATE = """You are checking whether ONE bundle of source spans can serve as evidence for ONE question. Each span is exact source text with its section and page. Judge only from the spans below.

Question (any interpretation notes in square brackets belong to the question):
{contract}

Source spans (id, role, section and page):
{spans}

The question asks for the following items. For each item, fill each slot with the ids of the spans that THEMSELVES supply it; use an empty list when no span does:
{items}

Rules: a slot is filled only if a listed span itself states it. Spans that merely mention related topics do not establish a relationship. A hypothesis, proposal or another study's result is not this paper's finding. A span marked "linked definition" defines a measure or term used by the other spans and may supply only descriptive slots, never the finding itself. A span marked "study context" is the paper's own abstract, shown only to help you judge the on_topic item; it may fill on_topic when it shows the finding belongs to this study and this question, but it never fills any other item. Do not combine spans that are not connected by what they say. For the polarity slot give the value association, none (the source reports no association), mixed, or not_stated (the source does not say whether they are related). Also give one short reason per item."""


def span_lines(packet: dict) -> str:
    lines = []
    for part in packet["parts"]:
        label = _label(part.get("section"), part.get("page_start"))
        role = part["role"].replace("_", " ")
        note = f"; {part['note']}" if part.get("note") else ""
        fragment = ""
        if part.get("open_left") or part.get("open_right"):
            fragment = "; fragment: continuation not verified"
        joined = "; joined across chunk boundaries, continuity verified" if part.get("join") == "verified_seam" else ""
        meta = f"{role}" + (f", {label}" if label else "") + note + fragment + joined
        lines.append(f"[{part['span_id']}] ({meta}) {part['text']}")
    return "\n".join(lines)


def item_lines(child: ChildContract) -> str:
    pair = bool(child.pair_requirement_ids)
    lines = []
    for unit in child.content_units:
        lines.append(f'Item {unit.unit_id} ({unit.kind}): "{unit.text}"')
        for slot in closure.all_slot_names(unit.kind, pair_required=pair):
            optional = " (fill if the source states it)" if slot in closure.OPTIONAL_SLOTS else ""
            lines.append(f"    slot {slot}: {closure.SLOT_DEFINITIONS[slot]}{optional}")
    return "\n".join(lines)


def render_eligibility(child: ChildContract, packet: dict) -> str:
    return ELIGIBILITY_TEMPLATE.format(contract=child.contract_text, spans=span_lines(packet), items=item_lines(child))


assert schemas  # the schemas module owns the enums quoted above; imported so a rename cannot drift silently
