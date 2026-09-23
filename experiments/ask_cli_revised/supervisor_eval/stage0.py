"""Stage 0: neutral mechanical preflight. No scholarly text, no semantic judgment.

Establishes only that a candidate loads, runs through the intended local path, produces structured output
under the uniform envelope, and can allocate the realistic 12,288-token context. Fixtures and limits come
from ask_070's neutral-preflight spec (loaded and hash-verified, never modified or executed as a run).
Eliminates only clear mechanical nonstarters; CPU offload or slowness never eliminates a candidate.
A candidate that cannot be pulled without changing shared infrastructure is BLOCKED_PENDING_RUNTIME_CHANGE.
"""

import json
import math
from pathlib import Path

import jsonschema

from experiments.ask_070.hashing import digest, text_hash
from experiments.ask_cli_revised.supervisor_eval import models
from experiments.ask_cli_revised.supervisor_eval.ollama_client import gpu_fraction, summarize_show

NEUTRAL_SPEC_PATH = Path(__file__).resolve().parents[2] / "ask_070" / "specifications" / "neutral_preflight_v0.json"
PADDING_BLOCK = ". 0 ~\n"
PADDED_TARGET_TOKENS = 8064
PADDED_BAND = (7800, 8192 - 64)
PROBE_BLOCKS = 128
ENUM_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string", "enum": ["alpha", "beta"]}},
    "required": ["answer"],
    "additionalProperties": False,
}
ENUM_PROMPT = "Return only JSON. Set answer to the word gamma."
_BLOCKING_HINTS = ("newer version", "no space left", "not enough space", "insufficient")


def load_neutral_fixtures(path=None):
    spec = json.loads(Path(path or NEUTRAL_SPEC_PATH).read_text(encoding="utf-8"))
    prompt, schema = spec["neutral_prompt_utf8"], spec["neutral_schema"]
    if text_hash(prompt) != spec["neutral_prompt_sha256"]:
        raise ValueError("neutral prompt does not match its recorded sha256")
    if digest(schema) != spec["neutral_schema_canonical_sha256"]:
        raise ValueError("neutral schema does not match its recorded canonical sha256")
    return {"prompt": prompt, "schema": schema}


def valid_neutral(content):
    try:
        jsonschema.validate(json.loads(content), load_neutral_fixtures()["schema"])
        return True
    except (json.JSONDecodeError, jsonschema.ValidationError, TypeError):
        return False


def estimate_k(base_tokens, probe_k, probe_tokens, target=PADDED_TARGET_TOKENS):
    per_block = (probe_tokens - base_tokens) / probe_k
    if per_block <= 0:
        raise ValueError("the calibration probe added no tokens")
    return max(0, math.floor((target - base_tokens) / per_block))


def padded_prompt(k, nonce, instruction):
    return f"[{nonce}]\n" + PADDING_BLOCK * k + instruction


def judge_enum_probe(content):
    try:
        answer = json.loads(content)["answer"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return answer in ("alpha", "beta")


def classify(trials):
    compact = [t for t in trials if t["name"].startswith("compact")]
    for t in compact:
        status, err = t["call"]["status"], t["call"].get("error")
        if status == "transport_error":
            return {"verdict": "technical", "reason": f"{t['name']}: {err}"}
        if status in ("http_error", "runtime_error", "timeout"):
            return {"verdict": "nonstarter", "reason": f"{t['name']}: {status}: {err}"}
    if compact and not any(t["valid_json"] for t in compact):
        return {"verdict": "nonstarter", "reason": f"no valid structured output (0/{len(compact)} compact calls)"}
    padded = next((t for t in trials if t["name"] == "padded"), None)
    notes = []
    if padded:
        status, err = padded["call"]["status"], padded["call"].get("error")
        if status == "transport_error":
            return {"verdict": "technical", "reason": f"padded: {err}"}
        if status in ("http_error", "runtime_error"):
            return {"verdict": "nonstarter", "reason": f"cannot allocate the realistic 12,288-token context: {err}"}
        if status == "timeout":
            notes.append("padded ~8k-token call hit the watchdog (descriptive only)")
    return {"verdict": "ok", "reason": None, "notes": notes}


def progress_logger(log, tag):
    """A pull-progress callback that logs each 10% step and each status change once, not every chunk."""
    state = {"decile": -1, "status": None}

    def callback(row):
        total, done = row.get("total") or 0, row.get("completed") or 0
        if total > 0:
            decile = min(100, int(100 * done / total) // 10 * 10)
            if decile != state["decile"]:
                state["decile"] = decile
                log(f"{tag}: pulling {decile}%")
        elif row.get("status") and row["status"] != state["status"]:
            state["status"] = row["status"]
            log(f"{tag}: {row['status']}")

    return callback


def _blocked(reason):
    return {"verdict": models.BLOCKED, "reason": reason}


def _has_model(client, tag):
    names = {m["name"] for m in client.tags()}
    return tag in names or f"{tag}:latest" in names


def _trial(client, tag, name, prompt, schema, think):
    call = client.chat(
        tag,
        prompt,
        schema=schema,
        options=models.ENVELOPE,
        think=think,
        keep_alive=models.KEEP_ALIVE,
        wall_timeout=models.STAGE0_CALL_WALL_TIMEOUT_S,
    )
    return {"name": name, "call": call, "valid_json": call["status"] == "ok" and valid_neutral(call["content"])}


def run(client, candidate, *, host_snapshot=lambda: {}, store_check=None, runtime=None, log=lambda message: None):
    tag = candidate["tag"]
    result = {
        "model": tag,
        "key": candidate["key"],
        "envelope": dict(models.ENVELOPE),
        "trials": [],
        "runtime": runtime,
        "store": store_check,
    }
    if not _has_model(client, tag):
        if store_check is not None and not store_check.get("ok", True):
            return {**result, **_blocked(store_check.get("reason") or "model store cannot hold this candidate")}
        log(f"pulling {tag}")
        pulled = client.pull(tag, on_progress=progress_logger(log, tag))
        if pulled.get("status") != "success":
            error = str(pulled.get("error", pulled))
            if any(hint in error.lower() for hint in _BLOCKING_HINTS):
                return {**result, **_blocked(error)}
            return {**result, "verdict": "technical", "reason": f"pull failed: {error}"}
    identity = summarize_show(client.show(tag))
    think = models.think_setting(candidate, identity["capabilities"])
    result.update({"identity": identity, "think_setting": think, "host_before": host_snapshot()})
    fixtures = load_neutral_fixtures()
    trials = result["trials"]
    try:
        for name in ("compact-cold", "compact-warm-1", "compact-warm-2"):
            log(f"{tag}: {name}")
            trials.append(_trial(client, tag, name, fixtures["prompt"], fixtures["schema"], think))
        early = classify(trials)
        if early["verdict"] != "ok":  # a failed compact call leaves nothing sound to calibrate against
            result.update(early)
            return result
        ps = next((m for m in client.ps() if m["name"] in (tag, f"{tag}:latest")), {})
        result["residency"] = {
            "size": ps.get("size"),
            "size_vram": ps.get("size_vram"),
            "gpu_fraction": gpu_fraction(ps) if ps else None,
        }
        result["host_resident"] = host_snapshot()
        probe = client.chat(
            tag,
            ENUM_PROMPT,
            schema=ENUM_SCHEMA,
            options=models.ENVELOPE,
            think=think,
            keep_alive=models.KEEP_ALIVE,
            wall_timeout=models.STAGE0_CALL_WALL_TIMEOUT_S,
        )
        result["enum_probe"] = {
            "enforced": judge_enum_probe(probe["content"]),
            "status": probe["status"],
            "content": probe["content"],
        }
        base = trials[0]["call"]["timings"]["prompt_eval_count"]
        if not base:
            result["padded"] = {"skipped": "the runtime reported no prompt token count to calibrate against"}
            result.update(classify(trials))
            return result
        calibration = client.chat(
            tag,
            padded_prompt(PROBE_BLOCKS, f"cal-{tag}", fixtures["prompt"]),
            schema=fixtures["schema"],
            options=models.ENVELOPE,
            think=think,
            keep_alive=models.KEEP_ALIVE,
            wall_timeout=models.STAGE0_CALL_WALL_TIMEOUT_S,
        )
        k = estimate_k(base, PROBE_BLOCKS, calibration["timings"]["prompt_eval_count"])
        log(f"{tag}: padded call with {k} blocks")
        trials.append(
            _trial(client, tag, "padded", padded_prompt(k, f"pad-{tag}", fixtures["prompt"]), fixtures["schema"], think)
        )
        tokens = trials[-1]["call"]["timings"]["prompt_eval_count"]
        result["padded"] = {
            "blocks": k,
            "prompt_tokens": tokens,
            "target": PADDED_TARGET_TOKENS,
            "in_band": tokens is not None and PADDED_BAND[0] <= tokens <= PADDED_BAND[1],
        }
        result["host_after"] = host_snapshot()
    finally:
        client.unload(tag)
    result.update(classify(trials))
    return result
