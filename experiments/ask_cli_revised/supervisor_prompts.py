"""The frozen R / C / P contracts (bakeoff Tasks A / B / C), filled in for any question.

The jurisdiction evidence for claim responsiveness (R), coverage audit (C) and recovery planning (P) was produced under
the frozen prompt templates and schemas in ``supervisor_eval``. This module changes only *what is filled in*: the
template text comes from the frozen module and the schemas are built by the frozen ``schemas.build_schema``, so
``test_supervisor_prompts`` can prove byte-for-byte equivalence on the frozen AIB battery. Obligations are shown with
``obligation_display`` so a list fragment keeps its frame.
"""

from __future__ import annotations

from experiments.ask_cli_revised.request_contract import obligation_display
from experiments.ask_cli_revised.supervisor_eval import prompts as _frozen
from experiments.ask_cli_revised.supervisor_eval import schemas as _schemas

# The frozen recovery policy (bakeoff Task C), verbatim.
from experiments.ask_cli_revised.supervisor_eval.cases import RECOVERY_POLICY  # noqa: F401  (re-exported)


def _items(obligations: list[dict]) -> str:
    return "\n".join(f"- {o['field_id']}: {obligation_display(o)}" for o in obligations)


def render_responsiveness(question: str, claim: str, obligations: list[dict]) -> str:
    """R: which requested items, if any, does this source-verified claim directly answer? (frozen Task A)"""
    return _frozen._A.format(question=question, claim=claim, items=_items(obligations))


def render_coverage(question: str, obligations: list[dict], propositions: list[dict]) -> str:
    """C: per requested item, which listed source-verified propositions directly support it? (frozen Task B)"""
    lines = [
        f"- {p['proposition_id']}: {p['claim']}\n    retrieved while searching for: {p['retrieved_for']} | "
        f'source: paper {p["paper_id"]}\n    supporting quote: "{p["quote"]}"'
        for p in propositions
    ]
    return _frozen._B.format(question=question, items=_items(obligations), propositions="\n".join(lines))


def render_recovery(
    question: str,
    obligations: list[dict],
    ledger: list[dict],
    state: dict,
    actions: dict,
    policy: list[str],
) -> str:
    """P: choose exactly one legal next action per requested item. (frozen Task C)"""
    ledger_lines = "\n".join(
        f"- {p['proposition_id']}: {p['claim']} (retrieved while searching for {p['retrieved_for']})" for p in ledger
    )
    blocks = []
    for obligation in obligations:
        ob = obligation["field_id"]
        s = state[ob]
        lines = [
            f"Requested item {ob}: {obligation_display(obligation)}",
            f"  Coverage audit, responsive support found in: {', '.join(s['coverage_support']) or 'none'}",
            f"  Verified claims retrieved for this item: {', '.join(s['on_file']) or 'none'}",
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
    policy_text = "\n".join(f"- {sentence}" for sentence in policy)
    return _frozen._C.format(question=question, policy=policy_text, ledger=ledger_lines, blocks="\n\n".join(blocks))


def schema_responsiveness(obligation_ids: list[str]) -> dict:
    return _schemas.build_schema({"family": "A", "legal": {"obligation_ids": list(obligation_ids)}})


def schema_coverage(obligation_ids: list[str], proposition_ids: list[str]) -> dict:
    legal = {"obligation_ids": list(obligation_ids), "proposition_ids": list(proposition_ids)}
    return _schemas.build_schema({"family": "B", "legal": legal})


def schema_recovery(obligation_ids: list[str], actions: dict) -> dict:
    legal = {"obligation_ids": list(obligation_ids), "actions": actions}
    return _schemas.build_schema({"family": "C", "legal": legal})


def legal_actions(obligation_ids: list[str], on_file: dict[str, list[str]]) -> dict[str, list[str]]:
    """The frozen action menu per item: search actions, mark-covered by a claim on file, or stop."""
    actions = {}
    for ob in obligation_ids:
        ids = [f"{ob}:DEEPEN", f"{ob}:NOMINATE"]
        ids += [f"{ob}:MARK_COVERED:{pid}" for pid in on_file.get(ob, [])]
        ids += [f"{ob}:NO_RECOVERY_NEEDED", f"{ob}:PRESERVE_UNRESOLVED"]
        actions[ob] = ids
    return actions


def initial_recovery_state(obligation_ids: list[str], support: dict, on_file: dict) -> dict:
    """The state at the single planning call: the initial pass counts as neither recovery action."""
    return {
        ob: {
            "coverage_support": list(support.get(ob, [])),
            "on_file": list(on_file.get(ob, [])),
            "performed": {"DEEPEN": False, "NOMINATE": False},
            "searched": {},
        }
        for ob in obligation_ids
    }
