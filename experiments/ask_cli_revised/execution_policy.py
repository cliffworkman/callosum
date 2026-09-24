"""Execution-policy seam for supervisory model calls in the Ask 0.7 experiment.

This is the seam upcoming role binding will call. No live revised-Ask stage uses it yet (the pipeline has no Qwen3.5 /
Ollama-native supervisory path), so today it is exercised only through a fake client in ``test_execution_policy.py``.

The runtime supplies its ordinary base options; this module changes exactly one thing, and only where evidence supports it:
Qwen3.5 bounded-recovery planning may generate up to 8,192 tokens, because those calls needed 6.1-7.1K reasoning + answer
tokens and were correct when given them (supervisor_eval/QWEN35_8K_SENSITIVITY.md section 7). Every other call keeps the
caller's allowance. There is no escalation ladder, no retry, and no scheduler: one call, one allowance.

A call that does not produce a usable structured answer within its allowance is **NO ANSWER** (``answer is None``): a
mechanical state, never a semantic judgment. A valid empty selection (``{"...": []}``) is an *answer* and stays distinct.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import jsonschema

RECOVERY_PLANNING = "recovery_planning"

# Mechanical outcomes. Anything but USABLE is NO ANSWER.
USABLE = "usable"
CAPPED = "capped_at_allowance"
UNPARSEABLE = "unparseable"
SCHEMA_INVALID = "schema_invalid"
CALL_FAILED = "call_failed"

_QWEN35_FAMILY = "qwen3.5"
_RECOVERY_ALLOWANCE = 8192


def _family(model_tag: str) -> str:
    return model_tag.split(":", 1)[0].strip().lower()


def generation_allowance(base_options: dict, model_tag: str, stage: str) -> int:
    """The ``num_predict`` for one call. The caller's ordinary allowance, except Qwen3.5 recovery planning (8,192)."""
    base = base_options.get("num_predict")
    if not isinstance(base, int) or isinstance(base, bool) or base <= 0:
        raise ValueError(
            f"base options need a positive integer num_predict (never an unbounded generation); got {base!r}"
        )
    if stage == RECOVERY_PLANNING and _family(model_tag) == _QWEN35_FAMILY:
        return max(base, _RECOVERY_ALLOWANCE)
    return base


def stage_options(base_options: dict, model_tag: str, stage: str) -> dict:
    """A copy of the caller's options with only ``num_predict`` chosen by policy (``num_ctx`` is never touched)."""
    return {**base_options, "num_predict": generation_allowance(base_options, model_tag, stage)}


@dataclass(frozen=True)
class StageResult:
    answer: dict | list | None  # the parsed structured answer iff usable; None == NO ANSWER (mechanically unresolved)
    record: dict  # model, stage, allowance, done_reason, usable, outcome, status, tokens, wall (never any text)


def _classify(call: dict, schema: dict) -> tuple[dict | list | None, str]:
    if call.get("status") != "ok":
        return None, CALL_FAILED
    done_reason = call.get("done_reason")
    if done_reason == "length":
        # A capped decode is not a clean success even if the partial content happens to parse
        # (same rule as calibration.structured_output.classify and supervisor_eval.scoring._observe).
        return None, CAPPED
    if done_reason != "stop":
        return None, CALL_FAILED
    try:
        answer = json.loads(call.get("content") or "")
    except ValueError:
        return None, UNPARSEABLE
    if not isinstance(answer, (dict, list)):
        return None, SCHEMA_INVALID
    if next(jsonschema.Draft202012Validator(schema).iter_errors(answer), None) is not None:
        return None, SCHEMA_INVALID
    return answer, USABLE


def run_stage_call(
    client,
    *,
    model_tag: str,
    stage: str,
    prompt: str,
    schema: dict,
    base_options: dict,
    think=None,
    keep_alive: str | None = None,
    wall_timeout: float | None = None,
    trace=None,
    input_text: str = "",
) -> StageResult:
    """Exactly one ``client.chat`` at the policy allowance; classify the outcome mechanically; never retry or escalate."""
    allowance = generation_allowance(base_options, model_tag, stage)
    chat_kwargs = {"schema": schema, "options": {**base_options, "num_predict": allowance}, "think": think}
    if keep_alive is not None:
        chat_kwargs["keep_alive"] = keep_alive
    if wall_timeout is not None:
        chat_kwargs["wall_timeout"] = wall_timeout
    call = client.chat(model_tag, prompt, **chat_kwargs)

    answer, outcome = _classify(call, schema)
    usable = outcome == USABLE
    timings = call.get("timings") or {}
    record = {
        "model": model_tag,
        "stage": stage,
        "allowance": allowance,
        "done_reason": call.get("done_reason"),
        "usable": usable,
        "outcome": outcome,
        "status": call.get("status"),
        "prompt_tokens": timings.get("prompt_eval_count"),
        "generated_tokens": timings.get("eval_count"),
        "wall_seconds": call.get("wall_seconds"),
    }
    if trace is not None:
        trace.qwen_call(
            stage=stage,
            task=stage,
            input_text=input_text,
            prompt_text=prompt,
            raw_output=call.get("content") or "",
            provider_ok=call.get("status") == "ok" and call.get("done_reason") == "stop",
            parse_ok=outcome in (USABLE, SCHEMA_INVALID),
            validation_ok=usable,
            failure_reason=None if usable else outcome,
            deterministic_fallback_used=False,
            downstream_consequence=(
                "usable structured answer" if usable else f"NO ANSWER (mechanical: {outcome}); not a semantic judgment"
            ),
            elapsed_seconds=call.get("wall_seconds"),
            output_cap=allowance,
            extra=record,
        )
    return StageResult(answer=answer, record=record)
