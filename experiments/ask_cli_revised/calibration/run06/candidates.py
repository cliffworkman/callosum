"""Run 0.6 candidate decompositions: three Qwen styles + a deterministic source baseline.

Every candidate preserves the SAME canonical source units (`segment_source_units_v2`); a candidate differs
only in HOW those units are rewritten. Qwen rewrites one unit at a time and can neither create nor delete a
canonical unit; a failed rewrite falls back to the exact source text. Reuses Run 0.5 `decomposition`
primitives (`_rewrite_once`, `_item`, `_call_record`, `_repair_prompt`, `_multi_prompt`, schemas) unchanged.
"""

from __future__ import annotations

from experiments.ask_cli_revised.calibration import decomposition as dec
from experiments.ask_cli_revised.calibration.run06.segment import segment_source_units_v2
from experiments.ask_cli_revised.calibration.structured_output import run_schema_call

QWEN_STYLES = ("minimal", "relation", "multi")


def minimal_prompt(question: str, unit_text: str) -> str:
    """Leaner than RELATION-PRESERVING: minimum wording to make the part standalone + reference-resolved."""
    return (
        "You are rephrasing ONE part of a longer scholarly question into a single standalone question for a "
        "literature search.\n\n"
        "Rewrite ONLY the part shown, using the MINIMUM wording needed to make it a standalone question — "
        "just enough to resolve references such as 'this', 'it', or 'these'.\n"
        "Do not answer it. Do not add topics, populations, comparisons, methods, or constructs it does not "
        "mention. Do not merge in other parts of the question. If the part is an open-ended request (for "
        "example 'and other relevant findings' or 'and more'), keep it open-ended — do not invent specific "
        "topics for it.\n"
        "The full original question is provided ONLY so you can resolve references.\n\n"
        'Return only JSON: {"rewrite":"..."}\n\n'
        f"Full original question (context only):\n{question}\n\nPart to rewrite:\n{unit_text}"
    )


def _single_style(base_config, question, units, *, style, mode):
    prompt_builder = minimal_prompt if style == "minimal" else dec._rewrite_prompt
    items, calls = [], []
    for unit in units:
        text, call = dec._rewrite_once(base_config, prompt_builder(question, unit["text"]), mode=mode)
        calls.append(dec._call_record(f"candidate.{style}", unit["source_unit_id"], unit["text"], text, call))
        items.append(dec._item(unit["source_unit_id"], unit["text"], 1, text or unit["text"], fallback=text is None))
    return items, calls


def _multi_style(base_config, question, units, *, mode):
    items, calls = [], []
    for unit in units:
        call = run_schema_call(
            base_config,
            dec._multi_prompt(question, unit["text"]),
            output_cap=dec._MULTI_OUTPUT_CAP,
            json_schema=dec._MULTI_SCHEMA,
            mode=mode,
        )
        rewrites = []
        if isinstance(call.parsed, dict) and isinstance(call.parsed.get("rewrites"), list):
            rewrites = [v.strip() for v in call.parsed["rewrites"] if isinstance(v, str) and v.strip()]
        calls.append(dec._call_record("candidate.multi", unit["source_unit_id"], unit["text"], rewrites or None, call))
        if not rewrites:
            items.append(dec._item(unit["source_unit_id"], unit["text"], 1, unit["text"], fallback=True))
        else:
            for ordinal, text in enumerate(rewrites, start=1):
                items.append(dec._item(unit["source_unit_id"], unit["text"], ordinal, text, fallback=False))
    return items, calls


def run_candidate(base_config, question: str, *, style: str, mode: str) -> dict:
    """One Qwen candidate decomposition over the v2 source units. `style` in QWEN_STYLES."""
    units = segment_source_units_v2(question)
    if style in ("minimal", "relation"):
        items, calls = _single_style(base_config, question, units, style=style, mode=mode)
    elif style == "multi":
        items, calls = _multi_style(base_config, question, units, mode=mode)
    else:  # pragma: no cover - guarded by QWEN_STYLES
        raise ValueError(f"unknown style: {style}")
    return {"style": style, "units": units, "items": items, "calls": calls}


def source_baseline(question: str) -> dict:
    """The no-Qwen deterministic baseline: each item IS its exact source unit (reference + fallback)."""
    units = segment_source_units_v2(question)
    items = []
    for unit in units:
        item = dec._item(unit["source_unit_id"], unit["text"], 1, unit["text"], fallback=True)
        item["is_baseline"] = True
        items.append(item)
    return {"style": "baseline", "units": units, "items": items, "calls": []}
