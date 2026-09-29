"""The reusable decomposition engine: ``run_engine(question, model)`` -> all documents, no I/O and no CLI.

Any caller (the experiments CLI today, the Callosum pipeline later) supplies a ``JsonModel``; nothing here writes files
or touches a UI. The first pass is never overwritten; a bounded repair pass is stored separately.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.ask_cli_revised.decompose import ENGINE_VERSION, passthrough, prompts, requirements, tree
from experiments.ask_cli_revised.decompose import clarifications as clar
from experiments.ask_cli_revised.decompose.calllog import CallLog, RunHalted
from experiments.ask_cli_revised.decompose.checks import verify_traceability
from experiments.ask_cli_revised.decompose.children import (
    build_pass,
    by_id_map,
    plan_children,
    repair_pass,
    score_candidates,
)
from experiments.ask_cli_revised.decompose.model import JsonModel
from experiments.ask_cli_revised.decompose.parent import build_parent_contract
from experiments.ask_cli_revised.decompose.reconcile import reconcile

DEFAULT_MAX_CALLS = 40


class WriterBudgetExceeded(RuntimeError):
    """The planned number of writer calls exceeds the budget. Raised BEFORE the first writer call, so no child is written, none is
    dropped and no partial run can be mistaken for a complete one. It carries what exists at that point (the inventory calls, the
    parent contract, the plans and the decomposition decision) so it can be reported as an INCOMPLETE run."""

    def __init__(
        self, needed: int, budget: int, *, parent: dict, plans: list[dict], decision: dict | None, calls: list
    ):
        super().__init__(f"the plan needs {needed} writer calls but the budget is {budget}")
        self.needed, self.budget = needed, budget
        self.parent, self.plans, self.decision, self.calls = parent, plans, decision, calls


__all__ = ["DEFAULT_MAX_CALLS", "RunHalted", "WriterBudgetExceeded", "code_hashes", "rescore", "run_engine"]


def code_hashes() -> dict[str, str]:
    root = Path(__file__).parent
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        for p in sorted(root.glob("*.py"))
        if not p.name.startswith("test_")
    }


def _embedding_audit(embed_model, parent: dict, doc: dict) -> dict | None:
    """DIAGNOSTIC only (reused run06 audit, provisional fixed gates); never gates anything."""
    if embed_model is None:
        return None
    from experiments.ask_cli_revised.calibration.audit import AuditThresholds
    from experiments.ask_cli_revised.calibration.run06.audit_ext import audit_candidate

    units = [{"source_unit_id": u["source_unit_id"], "text": u["text"]} for u in parent["source_units"]]
    items = [
        {
            "item_id": c["child_id"],
            "source_unit_id": c["origin"]["source_unit_ids"][0],
            "source_text": c["origin"]["source_text"],
            "text": c["question"],
        }
        for c in doc["children"]
        if c["kind"] != "fallback"
    ]
    if not items:
        return {"skipped": "no non-fallback children"}
    audit = audit_candidate(
        parent["original_question"],
        units,
        items,
        embed_model,
        thresholds=AuditThresholds(global_gate=0.30, coverage_gate=0.30),
    )
    audit["diagnostic_only"] = True
    return audit


def _apply_clarifications(parent: dict, rows: list[dict] | None, allow_pending: bool) -> None:
    clar.apply(parent, rows)  # user-authorized, span-linked; every other ambiguity stays open
    waiting = clar.pending(parent)
    if waiting and not allow_pending:
        raise clar.ClarificationError(
            f"clarification(s) {waiting} are proposals awaiting the user's approval; they are not applied unless explicitly allowed"
        )


def _finish(parent: dict, doc: dict, embed_model) -> dict:
    doc["question_tree"] = tree.question_tree(parent, doc["plans"])
    doc["verified_traceability"] = verify_traceability(parent, doc)
    doc["reconciliation"] = reconcile(parent, doc, doc["verified_traceability"])
    doc["embedding_audit_diagnostic"] = _embedding_audit(embed_model, parent, doc)
    return doc


def run_engine(
    question: str,
    model: JsonModel,
    *,
    repair: bool = True,
    whole_pass: bool = True,
    max_calls: int | None = DEFAULT_MAX_CALLS,
    embed_model=None,
    call_sink=None,
    inventory_model: JsonModel | None = None,
    clarifications: list[dict] | None = None,
    allow_pending_clarifications: bool = False,
    prompt_variant: str = "v3",
    only: list[str] | None = None,
    clarification_annotations: list[dict] | None = None,
    use_proposed_briefs: bool = False,
    passthrough_enabled: bool = True,
    max_seconds: float | None = None,
    halt_on=None,
    max_writer_calls: int | None = None,
    researcher_decisions: list[dict] | None = None,
) -> dict:
    """Obligation inventory -> one child per anchor obligation -> checks -> at most one bounded repair pass.

    ``max_calls`` is a hard cap: the call after the last permitted one is refused, the affected children become
    ``fallback_unresolved``, and the run reports ``call_cap_reached`` instead of continuing.

    ``inventory_model`` (optional) builds the obligation inventory with a different model than the wording stage, for
    example a ``ReplayModel`` over an earlier run's recorded inventory calls, so the wording stage can be tested without
    spending model calls on the inventory. The cap applies to ``model`` only.

    ``passthrough_enabled``: when the inventory AND the independent deterministic checks establish that the request is already one
    independently runnable Ask request, the original request is kept unchanged and the writer is not called. That is a statement
    about decomposition only; it never means the request was answered. Any other outcome runs the existing path.

    Bounds that keep a run COMPLETE or visibly INCOMPLETE (never quietly partial): ``max_calls`` (hard), ``max_seconds`` (wall clock for
    the whole run), ``halt_on`` (a stop condition checked after every call; see ``calllog.strict_live_halt``) raise ``RunHalted``, and
    ``max_writer_calls`` raises ``WriterBudgetExceeded`` after the inventory and planning but BEFORE any child is written.

    ``researcher_decisions`` (see ``clarifications.load_decisions``) are recorded with their provenance in the manifest."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("a nonempty original question is required")
    decisions = researcher_decisions or []
    if use_proposed_briefs and any((d.get("effect") or {}).get("briefs") == "unapproved_unused" for d in decisions):
        raise clar.ClarificationError(
            "the researcher decided the proposed briefs stay unapproved and UNUSED; a what-if with briefs is refused"
        )
    log = CallLog(model, max_calls=max_calls, sink=call_sink, max_seconds=max_seconds, halt_on=halt_on)
    inventory_log = log if inventory_model is None else CallLog(inventory_model)
    parent = build_parent_contract(inventory_log, question, whole_pass=whole_pass)
    _apply_clarifications(parent, clarifications, allow_pending_clarifications)
    clar.annotate(parent, clarification_annotations)
    parent["researcher_decisions"] = decisions
    settings = prompts.settings_for(prompt_variant, use_proposed_briefs=use_proposed_briefs)
    plans = plan_children(parent)
    decision = passthrough.decide(parent, plans, by_id_map(parent)) if passthrough_enabled else None
    applied = bool(decision and decision["outcome"] == passthrough.NO_DECOMPOSITION and only is None)
    if decision:
        decision["applied"] = applied
        decision["model_calls_avoided"] = {
            "writer_calls": sum(1 for p in plans if p["kind"] in ("anchor",)) if applied else 0,
            "note": "counted from the written children that were skipped; the inventory calls are unchanged",
        }
        if decision["outcome"] == passthrough.NO_DECOMPOSITION and not applied:
            decision["not_applied_because"] = "a subset run (--only) always writes the listed children"
    if max_writer_calls is not None and not applied:
        needed = sum(1 for p in plans if p["kind"] == "anchor" and (only is None or p["child_id"] in only))
        if needed > max_writer_calls:
            raise WriterBudgetExceeded(
                needed, max_writer_calls, parent=parent, plans=plans, decision=decision, calls=log.records
            )
    pass1 = _finish(parent, build_pass(log, parent, settings, only, decision=decision, plans=plans), embed_model)
    pass2 = _finish(parent, repair_pass(log, parent, pass1, settings), embed_model) if repair and not applied else None
    # Repairs are PROPOSALS. Lexical/attachment checks cannot see when a repair damages the meaning (a proposal can pass
    # every check by deleting the verb that linked the item to its subject), so none is ever applied to the final output
    # automatically: the final is the first pass, and pass 2 is stored for a human to accept or reject child by child.
    final = pass1
    incomplete = []
    if log.cap_hit:
        incomplete.append("call_cap_reached")
    incomplete += [
        f"{c['child_id']}: {c['kind']}" for c in pass1["children"] if c["kind"] in ("fallback", "not_selected")
    ]
    return {
        "engine_version": ENGINE_VERSION,
        "question": question,
        "question_sha256": parent["question_sha256"],
        "parent_contract": parent,
        "decomposition_decision": decision,
        "pass1": pass1,
        "pass2": pass2,
        "final_pass": final["pass"],
        "final": final,
        "calls": log.records,
        "inventory_calls": inventory_log.records if inventory_model is not None else [],
        "manifest": {
            "engine_version": ENGINE_VERSION,
            "model_identity": model.identity(),
            "model_label": model.label,
            "inventory_model": inventory_model.identity() if inventory_model is not None else "same model as wording",
            "inventory_call_summary": inventory_log.summary() if inventory_model is not None else None,
            "repair": repair,
            "whole_pass": whole_pass,
            "embedding_audit": embed_model is not None,
            "code_sha256_prefixes": code_hashes(),
            "call_summary": log.summary(),
            "call_cap_reached": log.cap_hit,
            "clarifications": [c["id"] for c in parent["clarifications"]],
            "pending_clarifications": clar.pending(parent),
            "proposed_briefs_present": clar.proposed_briefs(parent),
            "proposed_briefs_shown_to_the_model": bool(use_proposed_briefs and clar.proposed_briefs(parent)),
            "prompt_variant": settings["variant"],
            "extract_mode": settings["extract_mode"],
            "output_limits": settings["limits"],
            "schema_sha256": hashlib.sha256(json.dumps(settings["schema"], sort_keys=True).encode()).hexdigest(),
            "only": only,
            "decomposition_outcome": decision["outcome"] if decision else "not_evaluated",
            "decomposition_applied": applied,
            "answer_state": "not_executed",
            "run_completeness": {
                "complete": not incomplete,
                "reasons": incomplete,
                "note": "complete = every planned child was written or passed through; any cap, fallback or subset makes the run INCOMPLETE",
            },
            "researcher_decisions": [
                {k: d[k] for k in ("id", "decision", "authorized_by", "authorization", "recorded", "applies_to")}
                for d in decisions
            ],
            "pending_researcher_decisions": requirements.pending_decisions(parent),
            "known_limitations": list(requirements.KNOWN_LIMITATIONS),
            "semantic_fidelity": "not_certified",
        },
    }


def rescore(
    question: str,
    inventory_model: JsonModel,
    candidates: dict,
    *,
    clarifications: list[dict] | None = None,
    produced_by: str = "recorded",
    embed_model=None,
    allow_pending_clarifications: bool = False,
    extract_mode: str = "v3",
    clarification_annotations: list[dict] | None = None,
) -> dict:
    """Re-score RECORDED wording candidates ({child_id: {"question", "unresolved"}}) under the current contracts and checks.
    No model is called: the inventory comes from ``inventory_model`` (recorded calls) and the wording from ``candidates``."""
    parent = build_parent_contract(CallLog(inventory_model), question)
    _apply_clarifications(parent, clarifications, allow_pending_clarifications)
    clar.annotate(parent, clarification_annotations)
    plans = plan_children(parent)
    doc = _finish(
        parent,
        score_candidates(parent, plans, candidates, produced_by=produced_by, extract_mode=extract_mode),
        embed_model,
    )
    return {"question": question, "parent_contract": parent, "pass1": doc, "final": doc, "final_pass": 1}
