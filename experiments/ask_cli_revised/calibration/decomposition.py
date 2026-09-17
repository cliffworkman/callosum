"""Decomposition designs A/B/C over deterministic, provenance-owned source units.

Deterministic code owns the ordered source units, their IDs, and their exact text (`datasets.segment_
source_units`). Qwen only rephrases a unit's language; it can neither create nor delete a canonical unit,
and any Qwen failure falls back to the exact source text. Design C adds the §7a self-audit + one bounded
targeted repair pass; semantic similarity there is measurement/repair-guidance, NEVER a delete rule.
"""

from __future__ import annotations

from experiments.ask_cli_revised.calibration import audit as audit_mod
from experiments.ask_cli_revised.calibration.datasets import segment_source_units
from experiments.ask_cli_revised.calibration.structured_output import run_schema_call

_REWRITE_SCHEMA = {
    "type": "object",
    "required": ["rewrite"],
    "additionalProperties": False,
    "properties": {"rewrite": {"type": "string", "maxLength": 400}},
}
_MULTI_SCHEMA = {
    "type": "object",
    "required": ["rewrites"],
    "additionalProperties": False,
    "properties": {
        "rewrites": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string", "maxLength": 400}}
    },
}
_REWRITE_OUTPUT_CAP = 256
_MULTI_OUTPUT_CAP = 448


def _rewrite_prompt(question: str, unit_text: str) -> str:
    return (
        "You are rephrasing ONE part of a longer scholarly question into a single clear, standalone "
        "question suitable for a literature search.\n\n"
        "Rewrite ONLY the part shown. Preserve its exact meaning and EVERY distinct thing it asks for.\n"
        "Do not answer it. Do not add topics, populations, comparisons, methods, or constructs it does "
        "not mention. Do not merge in other parts of the question.\n"
        "The full original question is provided ONLY so you can resolve references such as 'this', 'it', "
        "or 'these'.\n\n"
        'Return only JSON: {"rewrite":"..."}\n\n'
        f"Full original question (context only):\n{question}\n\nPart to rewrite:\n{unit_text}"
    )


def _multi_prompt(question: str, unit_text: str) -> str:
    return (
        "You are rephrasing ONE part of a longer scholarly question for a literature search.\n\n"
        "If this part asks for several DISTINCT things, return one standalone question per distinct thing. "
        "If it asks for only one thing, return a single question.\n"
        "Preserve EVERY distinct request in this part. Add nothing it does not mention. Do not merge in "
        "other parts of the question.\n"
        "The full original question is provided ONLY to resolve references such as 'this' or 'it'.\n\n"
        'Return only JSON: {"rewrites":["..."]}\n\n'
        f"Full original question (context only):\n{question}\n\nPart to rewrite:\n{unit_text}"
    )


def _repair_prompt(question: str, unit_text: str, current_rewrite: str, decomposition_texts: list[str]) -> str:
    others = "\n".join(f"- {t}" for t in decomposition_texts)
    return (
        "You previously rephrased the parts of a scholarly question below. One rephrasing does not yet "
        "fully cover the original part it came from.\n\n"
        "Revise ONLY the flagged rephrasing so it faithfully covers its original part. Preserve every "
        "distinct request in that part; add nothing not in it. Do not change the other rephrasings and do "
        "not duplicate them.\n"
        "The full original question is provided ONLY to resolve references.\n\n"
        'Return only JSON: {"rewrite":"..."}\n\n'
        f"Full original question (context only):\n{question}\n\n"
        f"Current rephrasings:\n{others}\n\n"
        f"Original part:\n{unit_text}\n\nFlagged rephrasing to revise:\n{current_rewrite}"
    )


def _rewrite_once(base_config, prompt: str, *, mode: str):
    call = run_schema_call(base_config, prompt, output_cap=_REWRITE_OUTPUT_CAP, json_schema=_REWRITE_SCHEMA, mode=mode)
    text = None
    if isinstance(call.parsed, dict):
        value = call.parsed.get("rewrite")
        if isinstance(value, str) and value.strip():
            text = value.strip()
    return text, call


def apply_source_fallback(items: list[dict], weak_unit_ids: set[str]) -> tuple[list[dict], list[str]]:
    """Reset weak units' items to their exact source text — NEVER delete an item. Pure/testable."""
    out: list[dict] = []
    fell_back: list[str] = []
    for item in items:
        if item["source_unit_id"] in weak_unit_ids and item["text"] != item["source_text"]:
            out.append({**item, "text": item["source_text"], "from_fallback": True})
            fell_back.append(item["source_unit_id"])
        else:
            out.append(dict(item))
    return out, fell_back


def _item(source_unit_id: str, source_text: str, ordinal: int, text: str, *, fallback: bool) -> dict:
    return {
        "item_id": f"{source_unit_id}-r{ordinal}",
        "source_unit_id": source_unit_id,
        "source_text": source_text,
        "text": text,
        "from_fallback": fallback,
    }


def run_design_a(base_config, question: str, *, mode: str) -> dict:
    """Single rewrite per source unit; exact source text on any failure."""
    units = segment_source_units(question)
    items: list[dict] = []
    calls: list[dict] = []
    for unit in units:
        text, call = _rewrite_once(base_config, _rewrite_prompt(question, unit["text"]), mode=mode)
        calls.append(_call_record("design_a.rewrite", unit["source_unit_id"], unit["text"], text, call))
        items.append(_item(unit["source_unit_id"], unit["text"], 1, text or unit["text"], fallback=text is None))
    return {"design": "A", "units": units, "items": items, "calls": calls}


def run_design_b(base_config, question: str, *, mode: str) -> dict:
    """Multiple standalone rewrites per bundled unit; exact source text on any failure."""
    units = segment_source_units(question)
    items: list[dict] = []
    calls: list[dict] = []
    for unit in units:
        call = run_schema_call(
            base_config,
            _multi_prompt(question, unit["text"]),
            output_cap=_MULTI_OUTPUT_CAP,
            json_schema=_MULTI_SCHEMA,
            mode=mode,
        )
        rewrites: list[str] = []
        if isinstance(call.parsed, dict) and isinstance(call.parsed.get("rewrites"), list):
            for value in call.parsed["rewrites"]:
                if isinstance(value, str) and value.strip():
                    rewrites.append(value.strip())
        calls.append(
            _call_record("design_b.multi_rewrite", unit["source_unit_id"], unit["text"], rewrites or None, call)
        )
        if not rewrites:
            items.append(_item(unit["source_unit_id"], unit["text"], 1, unit["text"], fallback=True))
        else:
            for ordinal, text in enumerate(rewrites, start=1):
                items.append(_item(unit["source_unit_id"], unit["text"], ordinal, text, fallback=False))
    return {"design": "B", "units": units, "items": items, "calls": calls}


def run_design_c(base_config, question: str, *, mode: str, embed_model, thresholds) -> dict:
    """Design A base + deterministic semantic audit + at most ONE targeted repair pass + re-audit.

    Similarity NEVER deletes an item or a source unit. If the repaired decomposition is still inadequate,
    fall back to the deterministic source units (their exact text), never repeated regeneration.
    ``thresholds`` is an ``audit.AuditThresholds`` (empirical Run 0.5 gates).
    """
    base = run_design_a(base_config, question, mode=mode)
    units = base["units"]
    items = [dict(item) for item in base["items"]]
    calls = list(base["calls"])

    initial_audit = audit_mod.audit_decomposition(question, units, items, embed_model, thresholds=thresholds)
    weak_units = {u["source_unit_id"] for u in initial_audit["source_unit_coverage"] if u["weak"]}

    repaired = False
    repair_details: list[dict] = []
    if not initial_audit["passes_global"] or weak_units:
        repaired = True
        decomposition_texts = [item["text"] for item in items]
        # Repair the single item belonging to each weak source unit (Design C base is single-rewrite).
        for index, item in enumerate(items):
            if item["source_unit_id"] not in weak_units:
                continue
            unit_text = item["source_text"]
            text, call = _rewrite_once(
                base_config,
                _repair_prompt(question, unit_text, item["text"], decomposition_texts),
                mode=mode,
            )
            calls.append(_call_record("design_c.repair", item["source_unit_id"], unit_text, text, call))
            before = item["text"]
            if text is not None:
                items[index] = {**item, "text": text, "from_fallback": False, "repaired": True}
            repair_details.append(
                {
                    "item_id": item["item_id"],
                    "before": before,
                    "after": items[index]["text"],
                    "changed": text is not None,
                }
            )

    final_audit = audit_mod.audit_decomposition(question, units, items, embed_model, thresholds=thresholds)

    # Conservative fallback ONLY if still inadequate after the single repair pass: replace still-weak
    # units' items with their exact source text (never delete; never regenerate again).
    fell_back_units: list[str] = []
    if repaired and not final_audit["passes_global"]:
        still_weak = {u["source_unit_id"] for u in final_audit["source_unit_coverage"] if u["weak"]}
        items, fell_back_units = apply_source_fallback(items, still_weak)
        if fell_back_units:
            final_audit = audit_mod.audit_decomposition(question, units, items, embed_model, thresholds=thresholds)

    return {
        "design": "C",
        "units": units,
        "items": items,
        "calls": calls,
        "initial_audit": initial_audit,
        "final_audit": final_audit,
        "repaired": repaired,
        "repair_details": repair_details,
        "fell_back_units": fell_back_units,
    }


def _call_record(task: str, source_unit_id: str, source_text: str, result, call) -> dict:
    return {
        "task": task,
        "source_unit_id": source_unit_id,
        "source_text": source_text,
        "raw_output": call.raw_text[:600],
        "parsed_result": result,
        "provider_ok": call.provider_ok,
        "schema_ok": call.schema_ok,
        "truncated": call.truncated,
        "failure_reason": call.failure_reason,
        "fallback_used": result is None,
        "elapsed_seconds": round(call.elapsed_seconds, 3),
        "mode": call.mode,
    }
