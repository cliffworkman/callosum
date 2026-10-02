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


class SealingPrefixDriftError(RuntimeError):
    """Phase 17 §C: the append-only prefix invariant (`_ledger`'s old pids keep referring to the
    same physical records once recovery only ever appends) does not hold. This is a structural
    assertion, not an ordinary mechanical-failure path -- it must never be discovered only after a
    wasted C2 model call, so it is raised BEFORE one is made."""


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
        return policy.StageResult(
            answer=result.answer, record=record, raw_text=result.raw_text, thinking=result.thinking
        )


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


def record_identity(record: dict) -> tuple:
    """The canonical identity of a source-verified record (Phase 17 §D). Reuses, rather than
    reinvents, the exact tuple `__main__._new_unique_verified` already established as "the
    smallest exact identity that distinguishes [two records sharing a physical evidence anchor]"
    -- this project's own existing precedent for the identical problem (two proposition records
    CAN share a physical chunk/anchor; the claim text is what tells them apart), not a fresh
    invention for this phase. `__main__.py` now delegates to this one copy."""
    return (record["paper_id"], record["evidence_anchor_chunk_id"], record["proposition_text"].casefold())


def verify_stable_prefix_and_new_pids(prior_sealed: dict, records: list[dict]) -> set[str]:
    """Phase 17 §C: before any new-only coverage-audit call, prove the old, already-sealed
    proposition prefix still names the same physical records -- recovery only ever appends to
    the records list within one `execute()` call, so `_ledger`'s positional pids are a stable
    prefix by construction, but that is an invariant to assert, never to assume blind. Returns
    exactly the new suffix's proposition ids (what the coverage call is allowed to see) and raises
    `SealingPrefixDriftError` -- fully BEFORE any model call -- if the prefix has drifted."""
    current_ledger = _ledger(records)
    prior_rows = prior_sealed["verified_propositions"]
    if len(current_ledger) < len(prior_rows):
        raise SealingPrefixDriftError(f"the ledger shrank from {len(prior_rows)} to {len(current_ledger)} propositions")
    for (pid, record), prior_row in zip(current_ledger, prior_rows):  # noqa: B905 -- deliberately not
        # strict: `current_ledger` is allowed (expected) to be LONGER than `prior_rows` -- that
        # extra suffix is exactly the new evidence this function exists to return.
        if pid != prior_row["proposition_id"] or record_identity(record) != record_identity(prior_row):
            raise SealingPrefixDriftError(f"{pid} no longer identifies the record it did when prior_sealed was built")
    return {pid for pid, _ in current_ledger[len(prior_rows) :]}


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
    row = {
        "field_id": obligation["field_id"],
        "subquestion_id": subquestion["subquestion_id"],
        "source_unit_id": obligation.get("source_unit_id"),
        "note": obligation["note"],
        "display": obligation_display(obligation),
        "state": state,
        "proposition_ids": proposition_ids,
        "mechanical_gaps": mechanical_gaps,
    }
    if (
        "hierarchy" in obligation
    ):  # a hierarchical child: its record travels with its item state (flat rows are unchanged)
        row["hierarchy"] = obligation["hierarchy"]
    return row


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
    classify_pids: set[str] | None = None,
) -> dict:
    """The model coverage audit (frozen Task-B contract); this result is the authority.

    Phase 17 §A/§G: `classify_pids=None` (the default) is byte-identical to the original
    whole-ledger behavior -- every existing call site is unaffected. When given, it restricts the
    model-FACING candidate proposition list to exactly that subset (recovery's own new-only
    locality, §F) while `obligations`/`subquestions` stay the FULL set regardless -- a newly
    recovered proposition remains fully, legitimately classifiable against any obligation,
    including one other than whatever triggered its search (§G: never narrowed to a
    triggering-child/search-owner/descendant scope). Proposition ids are still minted from the
    FULL `records` list (`_ledger` is untouched) -- only which rows are shown to the model changes,
    never how pids are numbered, so a restricted call's new propositions keep their real,
    globally-stable suffix ids (e.g. "p27"), never reminted from "p1"."""
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
    props_all = _proposition_rows(records, subquestions, with_quote=True)
    props = props_all if classify_pids is None else [p for p in props_all if p["proposition_id"] in classify_pids]
    if not props:  # classify_pids named no row in the ledger (e.g. a no-new-evidence round): nothing to ask
        rows = [_obligation_row(sq, NO_RESPONSIVE_CLAIM, [], 0) for sq in subquestions]
        return {
            "authority": authority,
            "assessed": True,
            "obligations": rows,
            "outcome": None,
            "skipped_reason": "empty_ledger",
        }
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


def _evidence_span_rows(paper_id: int, span: dict) -> list[dict]:
    """One row for the span itself (the existing shape -- for a Stage A continuation-joined span, its
    `chunk_id` is the PRIMARY anchor and its `text` is the full reconstructed quote, exactly what the
    legacy singular evidence_anchor_chunk_id/quote fields need to keep resolving against
    `evidence_spans`), PLUS one additional row per entry in `span.get("anchors")` -- each anchor's own
    (chunk_id, span_id, text), which is what ledger_renderer.validate_ledger's plural-anchor check and
    e2e.py's seed_pass_from rehydration both need to find a real source-span match for each real
    chunk a continuation join actually spans."""
    rows = [{"paper_id": paper_id, "chunk_id": span["chunk_id"], "span_id": span["span_id"], "text": span["text"]}]
    for anchor in span.get("anchors") or ():
        rows.append({"paper_id": paper_id, "chunk_id": anchor["chunk_id"], "span_id": anchor["span_id"], "text": anchor["text"]})  # fmt: skip
    return rows


def seal(
    contract: dict,
    subquestions: list[dict],
    records: list[dict],
    evidence_packets: list[dict],
    coverage: dict,
    *,
    prior_sealed: dict | None = None,
) -> dict:
    """The sealed ledger: source-verified claims, the final attachments and per-item states, and the source spans.

    Phase 17 §A/§B/§F: `prior_sealed=None` (the default) is byte-identical to the original
    behavior. When given, every proposition already present in `prior_sealed` keeps its
    `responsive_obligation_ids` byte-for-byte -- recovery is evidence ADDITION, never
    re-adjudication of unchanged old evidence (§F, the append-only invariant); only propositions
    absent from `prior_sealed` (the new suffix `coverage` was actually asked to classify) take
    their attachment from `coverage`'s own fresh result. `record_identity` guards every reused old
    attachment against silently landing on a different physical record (§D); `_ledger`'s positional
    stability within one `execute()` call is asserted by `verify_stable_prefix_and_new_pids`
    BEFORE this function is ever called with a restricted `coverage`, so this is a second,
    redundant check here, not the only one.

    `obligation_states`/`coverage_assessed`/`coverage_outcome`/`coverage_authority` are then
    re-derived from that SAME merged attachment map -- a truthful CUMULATIVE view, never
    "new-only evidence added nothing to item X" misread as "item X lacks support" (§B's own
    example) -- when the new-only `coverage` call succeeded; or inherited unchanged from
    `prior_sealed` when it mechanically failed, since old evidence's own already-assessed
    cumulative judgment must survive a failed attempt to add more (§H)."""
    fresh_attached: dict[str, list[str]] = {}
    for row in coverage["obligations"]:
        for pid in row["proposition_ids"]:
            fresh_attached.setdefault(pid, []).append(row["field_id"])

    prior_by_pid: dict[str, dict] = {}
    if prior_sealed is not None:
        prior_by_pid = {row["proposition_id"]: row for row in prior_sealed["verified_propositions"]}

    ledger = _ledger(records)
    merged_attached: dict[str, list[str]] = {}
    verified = []
    for pid, record in ledger:
        if pid in prior_by_pid:
            prior_row = prior_by_pid[pid]
            if record_identity(record) != record_identity(prior_row):
                raise SealingPrefixDriftError(f"{pid} no longer identifies the record it did in prior_sealed")
            ids = prior_row["responsive_obligation_ids"]  # byte-for-byte preserved, never reclassified
        else:
            ids = fresh_attached.get(pid, [])  # freshly classified this round (empty if not asked/not responsive)
        merged_attached[pid] = ids
        verified.append({"proposition_id": pid, **record, "responsive_obligation_ids": ids})

    if prior_sealed is None:
        states = coverage["obligations"]
        coverage_assessed = coverage["assessed"]
        coverage_outcome = coverage.get("outcome")
        coverage_authority = coverage["authority"]
    elif not coverage["assessed"]:
        # The new-only classification attempt failed mechanically; the cumulative ledger's own
        # already-assessed judgment stands exactly as it was (§H) -- a failed attempt to add more
        # evidence must never retroactively unassess what was already truthfully assessed.
        states = prior_sealed["obligation_states"]
        coverage_assessed = prior_sealed["coverage_assessed"]
        coverage_outcome = prior_sealed["coverage_outcome"]
        coverage_authority = prior_sealed["coverage_authority"]
    else:
        order = {pid: i for i, (pid, _) in enumerate(ledger)}
        states = []
        for sq in subquestions:
            fid = sq["obligations"][0]["field_id"]
            supported = sorted((pid for pid, ids in merged_attached.items() if fid in ids), key=order.get)
            states.append(_obligation_row(sq, JUDGED_RESPONSIVE if supported else NO_RESPONSIVE_CLAIM, supported, 0))
        coverage_assessed = True
        coverage_outcome = None
        coverage_authority = coverage["authority"]

    sealed = {
        "request_contract": contract,
        "subquestions": subquestions,
        "verified_propositions": verified,
        "evidence_spans": [
            row
            for packet in evidence_packets
            for span in packet["candidate_spans"]
            for row in _evidence_span_rows(packet["paper_id"], span)
        ],
        "coverage_authority": coverage_authority,
        "coverage_assessed": coverage_assessed,
        "coverage_outcome": coverage_outcome,
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
    if contract.get("version") == "hierarchical-request-v1":  # hierarchy_contract.HIER_VERSION
        from experiments.ask_cli_revised import hierarchy_contract

        sealed["hierarchy"] = hierarchy_contract.rollup(contract, states)
    return sealed
