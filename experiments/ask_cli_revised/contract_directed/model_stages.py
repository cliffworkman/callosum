"""Model-backed stages (triage, localization, eligibility, answering) with mechanical accounting.

Every structured call goes through `execution_policy.run_stage_call` (one call, one allowance, no retry, no fallback): a call that
does not yield a usable structured answer is NO ANSWER, a MECHANICAL state recorded per stage and never read as "nothing relevant".
A valid answer that says nothing bears on the question is `none_established`, a SEMANTIC result counted separately. The ledger
enforces the frozen call and wall ceilings and halts a stage whose NO ANSWER rate exceeds the threshold; what is not run is
recorded `not_run_budget`, never silently dropped. The free-prose answer call keeps its raw text whatever any check says.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass, field

import httpx

from experiments.ask_cli_revised import execution_policy as policy
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.contract_directed import (
    abstracts,
    answer,
    closure,
    deterministic_candidates,
    prompts,
    schemas,
)
from experiments.ask_cli_revised.contract_directed import (
    packet as packet_mod,
)
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract
from experiments.ask_cli_revised.supervisor_eval.ollama_client import _TIMING_FIELDS, OllamaClient, _split_think

CHARS_PER_TOKEN = 3.0
PROMPT_TOO_LARGE = "prompt_too_large"
TRIAGE, LOCALIZE, ELIGIBILITY, ANSWER = "triage", "localization", "eligibility", "answer"


class BudgetExceeded(RuntimeError):
    """A frozen call or wall ceiling was reached: the remaining work is recorded `not_run_budget`, not attempted."""


class StageHalt(RuntimeError):
    """A stage's NO ANSWER rate exceeded the stop threshold: report and stop, do not retry or route around it."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Ledger:
    max_calls: int
    wall_seconds: float
    halt_rate: float = 0.10
    halt_min_calls: int = 20
    started: float = field(default_factory=time.monotonic)
    calls: int = 0
    stages: dict = field(default_factory=dict)

    def _counter(self, stage: str) -> Counter:
        return self.stages.setdefault(stage, Counter())

    def before(self, stage: str) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded("call_ceiling")
        if time.monotonic() - self.started > self.wall_seconds:
            raise BudgetExceeded("wall_ceiling")
        if self.should_halt(stage):
            raise StageHalt(
                f"{stage}: NO ANSWER rate above {self.halt_rate:.0%} over at least {self.halt_min_calls} calls"
            )

    def record(self, stage: str, record: dict, *, semantic: str | None = None) -> int:
        self.calls += 1
        counter = self._counter(stage)
        counter["calls"] += 1
        if record["usable"]:
            counter["usable"] += 1
        else:
            counter["no_answer"] += 1
            counter[f"no_answer:{record['outcome']}"] += 1
        if semantic:
            counter[semantic] += 1
        return self.calls

    def record_semantic(self, stage: str, label: str) -> None:
        self._counter(stage)[label] += 1

    def record_not_sent(self, stage: str, outcome: str) -> None:
        counter = self._counter(stage)
        counter["not_sent"] += 1
        counter[f"not_sent:{outcome}"] += 1

    def no_answer_rate(self, stage: str) -> float:
        counter = self.stages.get(stage)
        return counter["no_answer"] / counter["calls"] if counter and counter["calls"] else 0.0

    def should_halt(self, stage: str) -> bool:
        counter = self.stages.get(stage)
        return bool(counter and counter["calls"] >= self.halt_min_calls and self.no_answer_rate(stage) > self.halt_rate)

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "max_calls": self.max_calls,
            "elapsed_seconds": round(time.monotonic() - self.started, 1),
            "wall_seconds": self.wall_seconds,
            "stages": {stage: dict(counter) for stage, counter in self.stages.items()},
        }


class FreeChatClient(OllamaClient):
    """OllamaClient plus the baseline's free-prose chat (no structured-output `format`), thinking off."""

    def chat_free(
        self, model, prompt, *, options, think=False, keep_alive="30m", wall_timeout=1200.0, clock=time.monotonic
    ):
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": dict(options),
            "keep_alive": keep_alive,
        }
        if think is not None:
            body["think"] = think
        start = clock()
        state = {"content": [], "thinking": [], "final": {}, "first_token": None}

        def record(status, error=None):
            content, inline_think = _split_think("".join(state["content"]))
            thinking = "".join(state["thinking"]) or inline_think
            final = state["final"]
            return {
                "status": status, "error": error, "content": content, "thinking": thinking, "done_reason": final.get("done_reason"),
                "timings": {k: final.get(k) for k in _TIMING_FIELDS}, "wall_seconds": clock() - start,
                "time_to_first_token": state["first_token"],
            }  # fmt: skip

        try:
            with self._http.stream("POST", "/api/chat", json=body) as response:
                if response.status_code != 200:
                    return record(
                        "http_error", f"HTTP {response.status_code}: {response.read().decode(errors='replace')[:400]}"
                    )
                for line in response.iter_lines():
                    if clock() - start > wall_timeout:
                        return record("timeout", f"wall-clock watchdog exceeded {wall_timeout:.0f}s")
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if "error" in row:
                        return record("runtime_error", str(row["error"]))
                    message = row.get("message") or {}
                    if message.get("content") or message.get("thinking"):
                        if state["first_token"] is None:
                            state["first_token"] = clock() - start
                        state["content"].append(message.get("content") or "")
                        state["thinking"].append(message.get("thinking") or "")
                    if row.get("done"):
                        state["final"] = row
                return record("ok")
        except httpx.TimeoutException as exc:
            return record("timeout", f"{type(exc).__name__}: {exc}")
        except httpx.HTTPError as exc:
            return record("transport_error", f"{type(exc).__name__}: {exc}")


@dataclass
class Env:
    client: object
    ledger: Ledger
    model: str = "qwen3.5:9b"
    options: dict = field(default_factory=lambda: dict(topo.SUPERVISOR_BASE_OPTIONS))
    trace: object | None = None
    think: bool | None = False
    keep_alive: str = topo.KEEP_ALIVE
    wall_timeout: float = topo.WALL_TIMEOUT_SECONDS


def call_json(env: Env, stage: str, prompt: str, schema: dict, *, input_text: str = "") -> policy.StageResult:
    allowance = policy.generation_allowance(env.options, env.model, stage)
    if int(len(prompt) / CHARS_PER_TOKEN) + allowance > env.options["num_ctx"]:
        record = {
            "model": env.model,
            "stage": stage,
            "usable": False,
            "outcome": PROMPT_TOO_LARGE,
            "status": "not_sent",
            "prompt_sha256": sha(prompt),
        }
        env.ledger.record_not_sent(stage, PROMPT_TOO_LARGE)
        return policy.StageResult(answer=None, record=record)
    env.ledger.before(stage)
    result = policy.run_stage_call(
        env.client, model_tag=env.model, stage=stage, prompt=prompt, schema=schema, base_options=env.options,
        think=env.think, keep_alive=env.keep_alive, wall_timeout=env.wall_timeout, trace=env.trace, input_text=input_text,
    )  # fmt: skip
    index = env.ledger.record(stage, result.record)
    record = {**result.record, "call_index": index, "prompt_sha256": sha(prompt)}
    return policy.StageResult(answer=result.answer, record=record, raw_text=result.raw_text, thinking=result.thinking)


def _no_answer(record: dict) -> dict:
    return {"state": "no_answer", "outcome": record["outcome"], "call": record}


# ---- S2 triage ------------------------------------------------------------------------------------------------------------


def triage_paper(env: Env, child: ChildContract, paper: dict) -> dict:
    clean = abstracts.clean_abstract(paper.get("abstract"))
    base = {"child_id": child.child_id, "paper_id": paper["id"], "contract_sha256": child.contract_sha256}
    if not clean:
        env.ledger.record_semantic(TRIAGE, "abstract_absent")
        return {
            **base,
            "state": "abstract_absent",
            "abstract_state": "absent",
            "relation_to_child": "cannot_tell",
            "decision_rule": "no_abstract_stays_reachable",
        }
    prompt = prompts.render_triage(child, paper.get("title") or "", clean)
    result = call_json(env, TRIAGE, prompt, schemas.triage_schema(), input_text=paper.get("title") or "")
    if result.answer is None:
        return {
            **base,
            **_no_answer(result.record),
            "abstract_state": "present",
            "abstract_sha256": abstracts.sha256_text(clean),
        }
    checked = schemas.validate_triage(result.answer, clean)
    return {
        **base, "state": "usable", "abstract_state": "present", "abstract_sha256": abstracts.sha256_text(clean), **checked, "call": result.record,
    }  # fmt: skip


# ---- S4 localization ------------------------------------------------------------------------------------------------------


def _build_and_split(nbhd: dict, unit_list, by_id, propositions: list[dict], *, library, child_id: str):
    packets, unresolved = [], []
    for proposition in propositions:
        built = packet_mod.build_packet(nbhd, unit_list, by_id, proposition, library=library, child_id=child_id)
        if built["state"] == "built":
            built["nbhd_score"] = nbhd.get(
                "best_score", 0.0
            )  # provenance for the deterministic eligibility priority rule
            built["anchor_routes"] = list(nbhd.get("routes", []))
            built["from_recovery"] = bool(nbhd.get("recovery"))
        (packets if built["state"] == "built" else unresolved).append(built)
    return packets, unresolved


def localize_neighborhood(env: Env, child: ChildContract, nbhd: dict, library) -> dict:
    paper = library.paper(nbhd["paper_id"]) or {}
    unit_list, by_id = packet_mod.neighborhood_units(nbhd, library)
    unit_ids = [u.unit_id for u in unit_list]
    base = {
        "child_id": child.child_id,
        "nbhd_id": nbhd["nbhd_id"],
        "paper_id": nbhd["paper_id"],
        "contract_sha256": child.contract_sha256,
    }
    if not unit_ids:
        return {
            **base,
            "state": "none_established",
            "propositions": [],
            "invalid": [],
            "packets": [],
            "reason": "no_units",
        }
    deterministic = deterministic_candidates.find_instrument_pairing_candidates(unit_list, child)
    if deterministic and deterministic_candidates.only_instrument_manner_targeted(nbhd, child):
        # A clean, closed-class match, and nothing else about this neighborhood needed a model's attention: skip
        # the localization call. Eligibility (relata, on_topic, pairing) is entirely unaffected and still runs.
        packets, unresolved = _build_and_split(
            nbhd, unit_list, by_id, deterministic, library=library, child_id=child.child_id
        )
        env.ledger.record_semantic(LOCALIZE, "usable_deterministic")
        return {
            **base,
            "state": "usable_deterministic",
            "propositions": deterministic,
            "invalid": [],
            "packets": packets,
            "unresolved_preserved": unresolved,
            "call": None,
        }
    prompt = prompts.render_localization(child, paper.get("title") or "", unit_list, by_id)
    result = call_json(
        env, LOCALIZE, prompt, schemas.localization_schema(unit_ids), input_text=f"nbhd {nbhd['nbhd_id']}"
    )
    if result.answer is None:
        # A deterministic candidate found in a mixed-kind neighborhood is never discarded just because the model
        # call itself failed mechanically — it is still built and returned alongside the NO ANSWER record.
        packets, unresolved = _build_and_split(
            nbhd, unit_list, by_id, deterministic, library=library, child_id=child.child_id
        )
        return {**base, **_no_answer(result.record), "packets": packets, "unresolved_preserved": unresolved}
    checked = schemas.validate_localization(result.answer, unit_ids)
    all_propositions = checked["propositions"] + deterministic
    packets, unresolved = _build_and_split(
        nbhd, unit_list, by_id, all_propositions, library=library, child_id=child.child_id
    )
    state = checked["state"]
    if packets:
        state = "usable"
    elif state == "usable":
        state = "unresolved_preserved"
    env.ledger.record_semantic(LOCALIZE, state)
    return {
        **base,
        "state": state,
        "propositions": all_propositions,
        "invalid": checked["invalid"],
        "packets": packets,
        "unresolved_preserved": unresolved,
        "call": result.record,
    }


# ---- S6 eligibility -------------------------------------------------------------------------------------------------------


def judge_packet(env: Env, child: ChildContract, packet: dict) -> dict:
    base = {
        "packet_id": packet["packet_id"], "child_id": child.child_id, "contract_sha256": child.contract_sha256,
        "route_relation": "own_route" if child.child_id in packet["found_under"] else "cross_child",
    }  # fmt: skip
    span_ids = [p["span_id"] for p in packet["parts"]]
    prompt = prompts.render_eligibility(child, packet)
    result = call_json(
        env, ELIGIBILITY, prompt, schemas.eligibility_schema(child, span_ids), input_text=packet["packet_id"]
    )
    if result.answer is None:
        return {**base, **_no_answer(result.record)}
    pair = bool(child.pair_requirement_ids)
    # Pass 1: every content unit's base status, independently (never combining spans across units).
    base_results: dict[str, dict] = {}
    for unit in child.content_units:
        reported = result.answer["units"][unit.unit_id]
        base_results[unit.unit_id] = closure.derive_status(unit.kind, reported["slots"], packet, pair_required=pair)
    # Pass 2: for a #pair child's two paired units, a `pairing_expressed` the model left empty may still be derived —
    # never invented — from one connecting proposition (see closure.derive_pairing_bonus's exact requirements).
    partners = closure.pair_partners(child) if pair else {}
    for unit_id, partner_id in partners.items():
        result_unit = base_results[unit_id]
        if closure.PAIRING_SLOT not in result_unit["missing"]:
            continue
        bonus = closure.derive_pairing_bonus(
            child.unit(unit_id).kind, result_unit, child.unit(partner_id).kind, base_results[partner_id], packet
        )
        if bonus:
            base_results[unit_id] = closure.apply_pairing_bonus(result_unit, bonus)
    per_unit = {}
    for unit in child.content_units:
        reported = result.answer["units"][unit.unit_id]
        per_unit[unit.unit_id] = {
            **base_results[unit.unit_id],
            "unit_kind": unit.kind,
            "reason": (reported.get("reason") or "").strip(),
            "slots_reported": reported["slots"],
        }
    return {**base, "state": "usable", "per_unit": per_unit, "call": result.record}


# ---- S9 answering ---------------------------------------------------------------------------------------------------------


def answer_child(env: Env, child: ChildContract, packets: list[dict]) -> dict:
    """One thinking-off, free-prose call for one child. The RAW answer is returned exactly as generated, whatever any check says."""
    kept, omitted = answer.select_within_context(
        child.contract_text, packets, num_ctx=env.options["num_ctx"], allowance=env.options["num_predict"]
    )
    prompt, id_map, letter_map = answer.render_packet_prompt(child.contract_text, kept)
    env.ledger.before(ANSWER)
    call = env.client.chat_free(
        env.model, prompt, options=env.options, think=False, keep_alive=env.keep_alive, wall_timeout=env.wall_timeout
    )
    ok = call.get("status") == "ok"
    outcome = (
        "usable"
        if ok and call.get("done_reason") == "stop"
        else ("capped_at_allowance" if ok and call.get("done_reason") == "length" else "call_failed")
    )
    timings = call.get("timings") or {}
    record = {
        "model": env.model, "stage": ANSWER, "usable": outcome == "usable", "outcome": outcome, "status": call.get("status"),
        "done_reason": call.get("done_reason"), "prompt_tokens": timings.get("prompt_eval_count"),
        "generated_tokens": timings.get("eval_count"), "wall_seconds": call.get("wall_seconds"),
        "thinking_chars": len(call.get("thinking") or ""), "prompt_sha256": sha(prompt),
    }  # fmt: skip
    index = env.ledger.record(ANSWER, record)
    record["call_index"] = index
    if env.trace is not None:
        env.trace.qwen_call(
            stage=ANSWER, task=ANSWER, input_text=child.child_id, prompt_text=prompt, raw_output=call.get("content") or "",
            provider_ok=ok, parse_ok=True, validation_ok=outcome == "usable", failure_reason=None if outcome == "usable" else outcome,
            deterministic_fallback_used=False, downstream_consequence="raw answer preserved; diagnostics never gate it",
            elapsed_seconds=call.get("wall_seconds"), output_cap=env.options["num_predict"], extra=record,
        )  # fmt: skip
    return {
        "child_id": child.child_id, "contract_sha256": child.contract_sha256, "prompt": prompt, "prompt_sha256": record["prompt_sha256"],
        "id_map": id_map, "letter_map": letter_map, "packet_ids_given": [p["packet_id"] for p in kept], "omitted_for_context": omitted,
        "no_eligible_evidence": not kept, "raw_answer": call.get("content") or "", "call": record,
        "answer_state": outcome,
    }  # fmt: skip
