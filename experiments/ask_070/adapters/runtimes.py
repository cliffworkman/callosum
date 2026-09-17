"""Deterministic wire construction only; deliberately no HTTP client or runtime loader."""

from dataclasses import asdict
from typing import Protocol

from ..contracts import ContractError, PreparedRequest, RuntimeObservation
from ..hashing import canonical, digest

ROUTES = ("ollama_openai", "llama_cpp", "ollama_native")


class ModelRuntimeAdapter(Protocol):
    """Future implementation seam; this delivery provides only a deterministic fake observer."""

    def observe(self, request: PreparedRequest) -> RuntimeObservation: ...


def serialize(model, prepared, *, context, output_cap):
    if model.runtime not in ROUTES:
        raise ContractError("UNSUPPORTED_RUNTIME_ROUTE")
    if type(output_cap) is not int or not 0 < output_cap < context:
        raise ContractError("INVALID_TOTAL_CONTEXT_OUTPUT_BUDGET")
    body = {"model": model.candidate_id, "messages": [{"role": "user", "content": prepared["prompt"]}], "stream": False}
    prerequisites = {
        "exact_configuration": asdict(model),
        "total_context": context,
        "rendered_prompt_max_tokens": context - output_cap,
        "template_and_runtime_tokens": "REQUIRES_PREFLIGHT",
        "no_auto_fit": True,
        "no_context_shift": True,
        "weight_quantization": model.weight_quantization,
        "kv_configuration": {"k": model.kv_k, "v": model.kv_v},
        "local_artifact_verification": model.local_hash_status,
    }
    if model.runtime == "ollama_native":
        body.update(
            format=prepared["schema"],
            options={
                "num_ctx": context,
                "num_predict": output_cap,
                "temperature": model.temperature,
                "seed": model.seed,
                "num_thread": model.threads,
                "num_batch": model.batch,
                "num_gpu": model.gpu_layers,
            },
        )
    else:
        body.update(temperature=model.temperature, seed=model.seed, max_tokens=output_cap)
        if model.runtime == "llama_cpp":
            body.update(json_schema=prepared["schema"], cache_prompt=False)
            prerequisites["server_context_flag"] = ["--ctx-size", str(context)]
        else:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": prepared["schema_name"], "strict": True, "schema": prepared["schema"]},
            }
            prerequisites["modelfile_context"] = {"PARAMETER num_ctx": context}
    if model.thinking == "DISABLED":
        if model.runtime == "ollama_native":
            body["think"] = False
        elif model.runtime == "ollama_openai":
            body["reasoning_effort"] = "none"
        else:
            prerequisites["template_controls"] = {"enable_thinking": False, "reasoning_budget": 0}
        prerequisites["thinking_control_enforcement"] = "REQUIRES_PREFLIGHT_STOP_IF_UNSUPPORTED"
    elif model.thinking not in ("NOT_APPLICABLE", "REQUIRED_FINAL_FREEZE_VALUE"):
        raise ContractError("UNDECLARED_THINKING_POLICY")
    elif model.thinking == "REQUIRED_FINAL_FREEZE_VALUE":
        raise ContractError("THINKING_POLICY_REQUIRES_FINAL_FREEZE")
    return PreparedRequest(canonical(body), canonical(prerequisites), digest(asdict(model)), context)
