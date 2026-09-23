"""Frozen prompt templates. One template per task, identical for every candidate model.

Provider/model neutral: no few-shot examples, no model names, no per-model wording. The supervisory
standard is stated openly (a claim must directly support the user's actual obligation; the nearest
vaguely related bucket is a failure), because a hidden rule cannot fairly be called a reasoning failure.
Task A is claim-only (it mirrors the real map call); verbatim source quotes appear only in Task B and
only at render time from the private battery.
"""

from experiments.ask_cli_revised.supervisor_eval import cases

_NOTES = {o["field_id"]: o["note"] for o in cases.OBLIGATIONS}
_PROPS = {p["proposition_id"]: p for p in cases.PROPOSITIONS}

_A = """\
You are supervising a literature-question pipeline. A user asked a multi-part research question. It was split into requested items. A candidate scientific claim was proposed for it.

The user's original request:
{question}

Decide which requested items, if any, the claim directly answers or gives evidence about.

Select only requested items that the claim directly helps answer. Do not infer extra relationships. If it answers none, return an empty list.

Judge the claim exactly as written:
- A claim that is merely on a related topic, or is true and interesting but does not address what an item asks, answers none of the items.
- Do not use outside knowledge to connect the claim to an item. If the claim does not state the connection, it does not make it.
- Judge each item independently. Do not select an item because of where it appears in the list.
- Use only the item ids shown.

Candidate claim:
{claim}

Requested items:
{items}

Return only JSON with two fields: "rationale" (one or two sentences explaining your judgment) and "responsive_obligation_ids" (the ids of the selected items; an empty list if none).
"""

_B = """\
You are auditing evidence coverage for a multi-part research question. It was split into requested items. Candidate verified propositions were gathered while searching for them.

The user's original request:
{question}

Requested items:
{items}

Verified propositions:
{propositions}

For each requested item decide:
- responsive_support: at least one listed proposition directly answers or gives evidence about what that item asks. List the ids of those propositions.
- unresolved: none of the listed propositions does.

Rules:
- Each proposition has already been verified against its source. That says the claim matches its source, NOT that it answers the request item. Judge responsiveness separately.
- The item a proposition was retrieved for is not evidence that it answers that item.
- A proposition may support one item, several items, or none. A proposition that is scientifically valid but does not directly address an item must not be listed as support for it.
- "unresolved" means only that none of the listed propositions supports the item. It does not mean the literature has no such evidence; do not say or imply that.
- Use only the item ids and proposition ids shown.

Return only JSON with two fields: "rationale" (one or two sentences) and "coverage" (an object with one entry for every requested item id; each entry has "status", either "responsive_support" or "unresolved", and "supporting_proposition_ids", the ids of the listed propositions that support the item, empty when unresolved).
"""

_C = """\
You are supervising the bounded recovery step of a literature-question pipeline. A user asked a multi-part research question. It was split into requested items. Some items are still unresolved. For every requested item below, choose exactly one legal next action.

The user's original request:
{question}

Policy for this step:
{policy}

Verified claims on file (from the ledger):
{ledger}

What the actions mean:
- DEEPEN: re-search the candidate papers already nominated for the item with a reformulated query.
- NOMINATE: nominate additional candidate papers from the wider corpus for the item.
- MARK_COVERED:<claim id>: treat the item as covered by that verified claim.
- NO_RECOVERY_NEEDED: the item needs no further recovery.
- PRESERVE_UNRESOLVED: stop, and keep the item as unresolved.

{blocks}

Return only JSON with two fields: "rationale" (one or two sentences) and "plan" (an object with one entry for every requested item id, whose value is one legal action id for that item, written exactly as shown above).
"""


def _items(order):
    return "\n".join(f"- {ob}: {_NOTES[ob]}" for ob in order)


def _render_a(spec):
    return _A.format(question=cases.ORIGINAL_QUESTION, claim=spec["claim"], items=_items(spec["obligation_order"]))


def _render_b(spec, quotes):
    if not quotes:
        raise ValueError("Task B needs the private source quotes; render it from the private battery")
    lines = []
    for pid in spec["proposition_order"]:
        p = _PROPS[pid]
        lines.append(
            f"- {pid}: {p['claim']}\n    retrieved while searching for: {p['retrieved_for']} | "
            f'source: paper {p["paper_id"]}\n    supporting quote: "{quotes[pid]}"'
        )
    return _B.format(
        question=cases.ORIGINAL_QUESTION, items=_items(spec["obligation_order"]), propositions="\n".join(lines)
    )


def _render_c(spec):
    state, actions = spec["state"], spec["legal"]["actions"]
    ledger = "\n".join(
        f"- {p['proposition_id']}: {p['claim']} (retrieved while searching for {p['retrieved_for']})"
        for p in cases.PROPOSITIONS
    )
    blocks = []
    for ob in spec["obligation_order"]:
        s = state[ob]
        support = ", ".join(s["coverage_support"]) or "none"
        on_file = ", ".join(s["on_file"]) or "none"
        lines = [
            f"Requested item {ob}: {_NOTES[ob]}",
            f"  Coverage audit, responsive support found in: {support}",
            f"  Verified claims retrieved for this item: {on_file}",
            "  Search so far:",
        ]
        for action in ("DEEPEN", "NOMINATE"):
            if s["performed"].get(action):
                lines.append(f"    - {action}: performed; {s['searched'][action]}")
            else:
                lines.append(f"    - {action}: not yet performed")
        lines.append("  Legal actions:")
        for action_id in actions[ob]:
            name = action_id.split(":", 1)[1]
            flag = " (ALREADY PERFORMED)" if s["performed"].get(name) else ""
            lines.append(f"    - {action_id}{flag}")
        blocks.append("\n".join(lines))
    policy = "\n".join(f"- {sentence}" for sentence in cases.RECOVERY_POLICY)
    return _C.format(question=cases.ORIGINAL_QUESTION, policy=policy, ledger=ledger, blocks="\n\n".join(blocks))


def render(spec, quotes=None):
    family = spec["family"]
    if family == "A":
        return _render_a(spec)
    if family == "B":
        return _render_b(spec, quotes)
    if family == "C":
        return _render_c(spec)
    raise ValueError(f"unknown family {family!r}")
