"""Neutral-only Stage-1 specification and pure mechanical receipt assessment. Never executes."""

import math
from pathlib import Path

from .contracts import ContractError, FrozenTask
from .hashing import digest, read_json

SPEC = Path(__file__).parent / "specifications" / "neutral_preflight_v0.json"


def trials():
    spec = read_json(SPEC)
    return tuple(
        FrozenTask(
            "neutral-v0",
            "neutral_mechanical",
            "MECHANICAL",
            spec["neutral_prompt_utf8"],
            (("fixture", digest(spec)),),
            name,
        )
        for name in ("compact-cold", "compact-warm", "padded")
    )


def assess(observation, *, role):
    """Product budget exceedance is descriptive, NEVER a Stage-1 cull criterion."""
    reasons = []
    checks = ("loadable", "context_allocated", "complete_schema_valid", "runtime_template_contract")
    for check in checks:
        if observation.get(check) is not None and type(observation[check]) is not bool:
            raise ContractError("INVALID_MECHANICAL_OBSERVATION")
        if observation.get(check) is False:
            reasons.append(check.upper() + "_FAILED")
    if observation.get("crashed") is True:
        reasons.append("RUNTIME_CRASH")
    elapsed = observation.get("latency_seconds")
    if elapsed is not None and (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
        raise ContractError("INVALID_MECHANICAL_LATENCY")
    if elapsed is not None and elapsed > 600:
        reasons.append("CATASTROPHIC_LATENCY_CEILING")
    missing = [k for k in (*checks, "crashed", "latency_seconds") if observation.get(k) is None]
    budget = {"worker": 3.0, "orchestrator": 15.0}[role]
    warm = observation.get("thermal_state") == "warm"
    return {
        "decision": "MECHANICALLY_FAILED" if reasons else "INCOMPLETE" if missing else "MECHANICALLY_ADMITTED",
        "reason_codes": reasons,
        "missing": missing,
        "preferred_product_budget_seconds": budget,
        "exceeds_preferred_product_budget": elapsed > budget if warm and elapsed is not None else None,
        "product_budget_is_exclusion_threshold": False,
        "semantic_viability": "NOT_ASSESSED",
    }


def build_padded_prompt(render_and_tokenize):
    """Pure algorithm seam; caller must supply an already authorized tokenizer, never loaded here."""
    spec = read_json(SPEC)
    base = spec["neutral_prompt_utf8"]
    base_render, base_ids = render_and_tokenize(base)
    k = 1024
    attempts = []
    for _ in range(16):
        prompt = base + spec["deterministic_padding"]["alphabet"] * k
        rendered, ids = render_and_tokenize(prompt)
        n = len(ids)
        attempts.append({"padding_blocks": k, "rendered_tokens": n})
        if 8000 <= n <= 8128:
            return {
                "prompt": prompt,
                "rendered": rendered,
                "token_ids": list(ids),
                "attempts": attempts,
                "total_context": 12288,
                "mechanical_output_cap": 4096,
                "model_inference_calls": 0,
            }
        proposed = max(0, int(k * (8064 - len(base_ids)) / max(1, n - len(base_ids))))
        k = max(0, proposed if proposed != k else k + (1 if n < 8000 else -1))
    raise ContractError("NEUTRAL_PADDING_PREPARATION_UNRESOLVED")
