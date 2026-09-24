"""The supervised stages of a topology: R (claim responsiveness), C (coverage audit), P (recovery planning).

Vocabulary is deliberate. A *source-verified* claim is supported by its source passage (the verifier's judgment). Whether
it is *judged responsive* to a request item is a separate judgment made by R (per claim) or C (over the ledger). Neither
model judgment is called "verified", and a mechanical failure is never a semantic verdict: a call that does not produce a
usable structured answer is NO ANSWER, and it is recorded as such at every level (claim mapping, item state, plan).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from experiments.ask_cli_revised import execution_policy as policy
from experiments.ask_cli_revised import supervisor_prompts as sp
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.request_contract import obligation_display

# Prompts grow with the ledger (C, P), unlike the fixed bakeoff battery. A conservative characters-per-token estimate
# refuses a call that could not fit the context, rather than letting the runtime silently truncate the prompt.
CHARS_PER_TOKEN = 3.0
PROMPT_TOO_LARGE = "prompt_too_large"
INCONSISTENT = "inconsistent_answer"

JUDGED_RESPONSIVE = "judged_responsive"
NO_RESPONSIVE_CLAIM = "no_responsive_claim"
NOT_ASSESSED = "not_assessed"


@dataclass
class Supervisor:
    """One bound supervisory role. Every call goes through the execution-policy seam, exactly once."""

    role: str
    binding: topo.Binding
    client: object
    base_options: dict
    trace: object | None = None
    records: list = field(default_factory=list)

    def call(self, stage: str, prompt: str, schema: dict, *, input_text: str = "") -> policy.StageResult:
        allowance = policy.generation_allowance(self.base_options, self.binding.model, stage)
        estimated = int(len(prompt) / CHARS_PER_TOKEN)
        if estimated + allowance > self.base_options["num_ctx"]:
            record = {
                "model": self.binding.model,
                "stage": stage,
                "role": self.role,
                "allowance": allowance,
                "done_reason": None,
                "usable": False,
                "outcome": PROMPT_TOO_LARGE,
                "status": "not_sent",
                "prompt_tokens": None,
                "estimated_prompt_tokens": estimated,
                "generated_tokens": None,
                "wall_seconds": 0.0,
                "load_seconds": None,
                "thinking_chars": 0,
            }
            if self.trace is not None:
                self.trace.qwen_call(
                    stage=stage,
                    task=stage,
                    input_text=input_text,
                    prompt_text=prompt,
                    raw_output="",
                    provider_ok=False,
                    parse_ok=False,
                    validation_ok=False,
                    failure_reason=PROMPT_TOO_LARGE,
                    deterministic_fallback_used=False,
                    downstream_consequence="NO ANSWER (mechanical): prompt would not fit the context; not sent",
                    elapsed_seconds=0.0,
                    output_cap=allowance,
                    extra=record,
                )
            self.records.append(record)
            return policy.StageResult(answer=None, record=record)
        result = policy.run_stage_call(
            self.client,
            model_tag=self.binding.model,
            stage=stage,
            prompt=prompt,
            schema=schema,
            base_options=self.base_options,
            think=self.binding.think,
            keep_alive=topo.KEEP_ALIVE,
            wall_timeout=topo.WALL_TIMEOUT_SECONDS,
            trace=self.trace,
            input_text=input_text,
        )
        record = {**result.record, "role": self.role}
        self.records.append(record)
        return policy.StageResult(answer=result.answer, record=record, raw_text=result.raw_text)


# ---- the ledger ------------------------------------------------------------------------------------------------


def source_verified(records: list[dict]) -> list[dict]:
    """The ledger's members: source-verified and not a re-discovered duplicate of earlier evidence."""
    return [
        r
        for r in records
        if r["verification"]["status"] == "verified" and not r["provenance"].get("duplicate_of_existing_evidence")
    ]


def _retrieved_for(subquestions: list[dict]) -> dict[str, str]:
    return {sq["subquestion_id"]: sq["obligations"][0]["field_id"] for sq in subquestions}


def _ledger(records: list[dict]) -> list[tuple[str, dict]]:
    return [(f"p{i}", r) for i, r in enumerate(source_verified(records), start=1)]


def _proposition_rows(records: list[dict], subquestions: list[dict], *, with_quote: bool) -> list[dict]:
    retrieved_for = _retrieved_for(subquestions)
    rows = []
    for pid, r in _ledger(records):
        row = {
            "proposition_id": pid,
            "claim": r["proposition_text"],
            "retrieved_for": retrieved_for.get(r["subquestion_id"], r["subquestion_id"]),
            "paper_id": r["paper_id"],
        }
        if with_quote:
            row["quote"] = r["quote"]
        rows.append(row)
    return rows


# ---- R: claim responsiveness -----------------------------------------------------------------------------------


def run_responsiveness(supervisor, *, question: str, obligations: list[dict], records: list[dict]) -> dict:
    """Ask R about each source-verified claim that has not been mapped yet (frozen Task-A contract).

    A usable answer maps the claim to the items it directly answers (possibly none). NO ANSWER leaves the claim
    ``no_answer``: it is not "responsive to none", and it can never count as evidence of absence.
    """
    ids = [o["field_id"] for o in obligations]
    schema = sp.schema_responsiveness(ids)
    counts = {"asked": 0, "mapped": 0, "no_answer": 0}
    for record in source_verified(records):
        if record.get("mapping_state") != "pending":
            continue
        counts["asked"] += 1
        prompt = sp.render_responsiveness(question, record["proposition_text"], obligations)
        result = supervisor.call("claim_responsiveness", prompt, schema, input_text=record["proposition_text"])
        if result.answer is None:
            record["obligation_ids"] = []
            record["mapping_state"] = "no_answer"
            record["mapping"] = {"outcome": result.record["outcome"]}
            counts["no_answer"] += 1
            continue
        chosen = set(result.answer["responsive_obligation_ids"])
        record["obligation_ids"] = [i for i in ids if i in chosen]  # obligation order, deduplicated
        record["mapping_state"] = "mapped"
        record["mapping"] = {"rationale": result.answer.get("rationale", "")}
        counts["mapped"] += 1
    return counts


# ---- C: coverage ------------------------------------------------------------------------------------------------


def _obligation_row(subquestion: dict, state: str, proposition_ids: list[str], mechanical_gaps: int) -> dict:
    obligation = subquestion["obligations"][0]
    return {
        "field_id": obligation["field_id"],
        "subquestion_id": subquestion["subquestion_id"],
        "source_unit_id": obligation.get("source_unit_id"),
        "note": obligation["note"],
        "display": obligation_display(obligation),
        "state": state,
        "proposition_ids": proposition_ids,
        "mechanical_gaps": mechanical_gaps,
    }


def det_coverage(subquestions: list[dict], records: list[dict], *, authority: dict) -> dict:
    """The shipped mechanism: attachments are R's mappings; an item with none is unresolved (not asserted absent)."""
    ledger = _ledger(records)
    rows = []
    for subquestion in subquestions:
        ob = subquestion["obligations"][0]["field_id"]
        attached = [pid for pid, r in ledger if ob in r.get("obligation_ids", [])]
        gaps = sum(
            1
            for _, r in ledger
            if r.get("mapping_state") == "no_answer" and r["subquestion_id"] == subquestion["subquestion_id"]
        )
        rows.append(
            _obligation_row(subquestion, JUDGED_RESPONSIVE if attached else NO_RESPONSIVE_CLAIM, attached, gaps)
        )
    return {"authority": authority, "assessed": True, "obligations": rows, "outcome": None}


def _inconsistencies(coverage: dict) -> list[str]:
    problems = []
    for ob, entry in coverage.items():
        ids = entry["supporting_proposition_ids"]
        if entry["status"] == "unresolved" and ids:
            problems.append(f"{ob} is 'unresolved' but lists support {ids}")
        if entry["status"] == "responsive_support" and not ids:
            problems.append(f"{ob} is 'responsive_support' but lists no proposition")
    return problems


def run_coverage_audit(
    supervisor,
    *,
    question: str,
    obligations: list[dict],
    subquestions: list[dict],
    records: list[dict],
    authority: dict,
) -> dict:
    """The model coverage audit over the whole ledger (frozen Task-B contract); this result is the authority."""
    ledger = _ledger(records)
    ids = [o["field_id"] for o in obligations]
    if not ledger:  # nothing to audit; the frozen schema cannot express an empty proposition enum
        rows = [_obligation_row(sq, NO_RESPONSIVE_CLAIM, [], 0) for sq in subquestions]
        return {
            "authority": authority,
            "assessed": True,
            "obligations": rows,
            "outcome": None,
            "skipped_reason": "empty_ledger",
        }
    props = _proposition_rows(records, subquestions, with_quote=True)
    prompt = sp.render_coverage(question, obligations, props)
    schema = sp.schema_coverage(ids, [p["proposition_id"] for p in props])
    result = supervisor.call("coverage_audit", prompt, schema)
    outcome = result.record["outcome"] if result.answer is None else None
    if result.answer is not None and _inconsistencies(result.answer["coverage"]):
        # An answer that contradicts itself is mechanically unusable (bakeoff G1), not a coverage judgment.
        result.record["usable"] = False
        result.record["outcome"] = INCONSISTENT
        result.record["inconsistencies"] = _inconsistencies(result.answer["coverage"])
        outcome = INCONSISTENT
    if outcome is not None:
        rows = [_obligation_row(sq, NOT_ASSESSED, [], 0) for sq in subquestions]
        return {"authority": authority, "assessed": False, "obligations": rows, "outcome": outcome}
    order = {p["proposition_id"]: i for i, p in enumerate(props)}
    rows = []
    for sq in subquestions:
        entry = result.answer["coverage"][sq["obligations"][0]["field_id"]]
        supported = sorted(set(entry["supporting_proposition_ids"]), key=order.get)
        rows.append(
            _obligation_row(sq, JUDGED_RESPONSIVE if entry["status"] == "responsive_support" else NO_RESPONSIVE_CLAIM,
                            supported, 0)
        )  # fmt: skip
    return {"authority": authority, "assessed": True, "obligations": rows, "outcome": None}


# ---- P: recovery planning ----------------------------------------------------------------------------------------


def legacy_plan(obligations: list[dict]) -> dict:
    """The shipped recovery: every item gets the legacy deepen-then-nominate sequence. No model, no planner."""
    return {"source": "legacy", "state": "planned", "plan": {o["field_id"]: "LEGACY" for o in obligations}}


def run_recovery_plan(
    supervisor, *, question: str, obligations: list[dict], subquestions: list[dict], records: list[dict], coverage: dict
) -> dict:
    """One bounded plan (frozen Task-C contract). NO ANSWER performs no planned action and is recorded as such."""
    ids = [o["field_id"] for o in obligations]
    ledger_rows = _proposition_rows(records, subquestions, with_quote=False)
    on_file: dict[str, list[str]] = {ob: [] for ob in ids}
    for row in ledger_rows:
        on_file.setdefault(row["retrieved_for"], []).append(row["proposition_id"])
    support = {row["field_id"]: row["proposition_ids"] for row in coverage["obligations"]}
    state = sp.initial_recovery_state(ids, support, on_file)
    actions = sp.legal_actions(ids, on_file)
    prompt = sp.render_recovery(question, obligations, ledger_rows, state, actions, sp.RECOVERY_POLICY)
    result = supervisor.call(policy.RECOVERY_PLANNING, prompt, sp.schema_recovery(ids, actions))
    if result.answer is None:
        return {
            "source": "model",
            "state": "no_answer",
            "plan": {},
            "reason_code": "recovery_plan_no_answer",
            "outcome": result.record["outcome"],
        }
    plan = {ob: result.answer["plan"][ob].split(":", 1)[1] for ob in ids}
    return {"source": "model", "state": "planned", "plan": plan, "rationale": result.answer.get("rationale", "")}


# ---- sealing ------------------------------------------------------------------------------------------------------


def seal(
    contract: dict, subquestions: list[dict], records: list[dict], evidence_packets: list[dict], coverage: dict
) -> dict:
    """The sealed ledger: source-verified claims, the final attachments and per-item states, and the source spans."""
    attached: dict[str, list[str]] = {}
    for row in coverage["obligations"]:
        for pid in row["proposition_ids"]:
            attached.setdefault(pid, []).append(row["field_id"])
    verified = []
    for pid, record in _ledger(records):
        verified.append({"proposition_id": pid, **record, "responsive_obligation_ids": attached.get(pid, [])})
    states = coverage["obligations"]
    return {
        "request_contract": contract,
        "subquestions": subquestions,
        "verified_propositions": verified,
        "evidence_spans": [
            {
                "paper_id": packet["paper_id"],
                "chunk_id": span["chunk_id"],
                "span_id": span["span_id"],
                "text": span["text"],
            }
            for packet in evidence_packets
            for span in packet["candidate_spans"]
        ],
        "coverage_authority": coverage["authority"],
        "coverage_assessed": coverage["assessed"],
        "coverage_outcome": coverage.get("outcome"),
        "obligation_states": states,
        "coverage": {
            "original_request": {
                "question_hash": contract["question_hash"],
                "source_units": [
                    {
                        "source_unit_id": row["source_unit_id"],
                        "state": row["state"],
                        "proposition_ids": row["proposition_ids"],
                        "completeness": "not_certified",
                    }
                    for row in states
                ],
                "completeness": "not_certified",
            }
        },
    }
