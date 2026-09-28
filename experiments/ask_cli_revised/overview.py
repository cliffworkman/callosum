"""The researcher-facing overview stage (role S): one model call over source-paired claims, then local screening.

The overview is written by the S model from deduplicated source passages ("units") paired with the ledger claims that
restate them. The passage is the authority; a claim is a candidate that may say more or less than its passage. The model
may consolidate, qualify or omit. Every proposed statement must cite passage ids, and is then screened by deterministic
lexical rules (``overview_guards``) and one batched local NLI call. Screening can only withhold a statement; it never
proves one correct, and the exact cited passage is shown beside every statement that survives.

The result is a SEPARATE, separately hashed artifact that references the sealed evidence ledger by hash. The sealed ledger
itself is never modified, so model-written synthesis stays distinguishable from source-verified claim records.

Failure is explicit and never a scientific conclusion: no eligible evidence (no call is made), a mechanical NO ANSWER, an
empty answer, or every statement withheld. An overview with any withheld statement is marked partial.
"""

from __future__ import annotations

import hashlib
import json

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import overview_guards as guards

OVERVIEW_VERSION = "overview-v1"
STAGE = "overview_synthesis"
MAX_SENTENCES = 6
MAX_PROMPT_CHARS = (
    12_000  # ~4,096 estimated tokens at the harness's 3 chars/token; leaves the rest of num_ctx for reasoning
)
MIN_REASONING_HEADROOM = 4096  # tokens of thinking the schema's worst-case output must still leave inside the allowance
SCREENING_NOTE = (
    "Screening (lexical rules plus a local NLI model) can withhold a statement but cannot prove one correct."
)

STATES = ("ok", "no_eligible_evidence", "model_no_answer", "model_returned_empty", "no_grounded_sentences")

# An optional, additive section (never present unless a caller supplies constraints; the pinned PROMPT_TEMPLATE
# below is untouched either way). A "coverage constraint" states a LIMIT of the admitted evidence -- it is never
# itself a source passage, is never added to `units` so it is structurally impossible to cite in `unit_ids`
# (schema `unit_ids` is a closed enum built only from real unit ids), and must never assert or imply that
# something was measured and found absent -- only that the admitted evidence does not establish it.
COVERAGE_CONSTRAINTS_HEADER = (
    "EVIDENCE-COVERAGE LIMITS (instructions about what the admitted evidence does and does not establish -- never "
    "a source passage, never citable in unit_ids, and never itself a finding to restate):"
)

PROMPT_TEMPLATE = """You are writing the opening OVERVIEW of a research answer for a scholar, using ONLY the retrieved source passages below.

Original request (verbatim):
{question}

Request parts. Use these ids only to tag which parts a statement directly addresses:
{parts}

Source passages. Each passage is exact text from a paper and is the ONLY authority. Under each passage are candidate claims: machine-written restatements that may say more or less than the passage, and that may be wrong. Never use a claim's wording unless its passage establishes it. Where a claim contains a term its passage lacks (listed after "not in passage:"), do not carry that term into the overview.

{units}

Write a short overview (1 to 6 statements) that answers the original request as far as the passages allow. Synthesize across passages; do not repeat claims one by one.
- State only what a passage says. Keep exactly who did or felt what toward whom, the direction of any difference (more or less), the population, and whether a finding is an association or a causal claim.
- Keep every hedge (might, may, suggest). Do not turn a suggestion, a description of what a study set out to do, or an untested idea into a finding. Do not say an intervention works, or that a brain-outcome relationship is established, unless a passage itself says so.
- Consolidate passages that say the same thing into one statement. Do not use words such as several, consistently or studies unless the cited passages come from more than one paper.
- Say nothing about what is missing or unknown; a separate step reports that. If no passage supports any statement, return an empty list.
- Every statement cites 1 to 3 passage ids in unit_ids. In bears_on list the request parts the statement directly addresses (an empty list is fine). bears_on is a tag, not a claim that a part is fully answered.
Return JSON only, in this shape (the values in angle brackets are placeholders, not suggestions): {{"overview": [{{"text": "<statement>", "unit_ids": ["<passage id>"], "bears_on": ["<part id>"]}}]}}
"""


# ---- prompt and schema -----------------------------------------------------------------------------------------------
def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def render_part_lines(states: list[dict]) -> str:
    return "\n".join(f"- {s['field_id']}: {_clip(s['note'], 220)}" for s in states)


def render_unit_block(unit: dict, claims: list[dict]) -> str:
    lines = [f"[{unit['unit_id']}] paper {unit['paper_id']}", f'Passage: "{unit["passage"]}"', "Candidate claims:"]
    for claim in claims[: oe.MAX_CLAIMS_SHOWN]:
        extra = f" (not in passage: {', '.join(claim['novel_terms'])})" if claim["novel_terms"] else ""
        lines.append(f'- {claim["proposition_id"]}: "{_clip(claim["text"], oe.MAX_CLAIM_CHARS)}"{extra}')
    return "\n".join(lines)


def render_coverage_constraints(coverage_constraints: tuple[str, ...]) -> str:
    """The additive section text, or "" when there are no constraints (the caller then gets today's exact prompt)."""
    if not coverage_constraints:
        return ""
    lines = "\n".join(f"- {c}" for c in coverage_constraints)
    return f"{COVERAGE_CONSTRAINTS_HEADER}\n{lines}\n\n"


def render_prompt(
    question: str, states: list[dict], blocks: list[str], *, coverage_constraints: tuple[str, ...] = ()
) -> str:
    base = PROMPT_TEMPLATE.format(question=question, parts=render_part_lines(states), units="\n\n".join(blocks))
    section = render_coverage_constraints(coverage_constraints)
    if not section:
        return base  # byte-identical to every existing caller; PROMPT_TEMPLATE itself is never touched
    anchor = "Write a short overview"
    idx = base.index(anchor)
    return base[:idx] + section + base[idx:]


def select_for_prompt(
    units: list[dict],
    claims: list[dict],
    question: str,
    states: list[dict],
    *,
    coverage_constraints: tuple[str, ...] = (),
) -> tuple[list[str], str]:
    """Pack eligible units in ledger order until the prompt cap; the rest are recorded ``omitted_by_prompt_cap``.

    Marks every unit with ``sent_to_model`` and ``not_sent_reason`` (derived, deterministic, re-derived by the audit).
    ``coverage_constraints`` is optional and additive (see `render_prompt`); omitting it reproduces today's exact
    behavior, and when supplied it counts toward the same prompt cap so packing stays accurate.
    """
    by_unit: dict[str, list[dict]] = {}
    for claim in claims:
        by_unit.setdefault(claim["unit_id"], []).append(claim)
    blocks: list[str] = []
    sent: list[str] = []
    for unit in units:
        unit["sent_to_model"], unit["not_sent_reason"] = False, None
        if not unit["eligibility"]["eligible"]:
            unit["not_sent_reason"] = "ineligible"
            continue
        block = render_unit_block(unit, by_unit.get(unit["unit_id"], []))
        prompt_len = len(render_prompt(question, states, [*blocks, block], coverage_constraints=coverage_constraints))
        if len(sent) >= oe.MAX_UNITS or prompt_len > MAX_PROMPT_CHARS:
            unit["not_sent_reason"] = "omitted_by_prompt_cap"
            continue
        blocks.append(block)
        sent.append(unit["unit_id"])
        unit["sent_to_model"] = True
    return sent, render_prompt(question, states, blocks, coverage_constraints=coverage_constraints)


def schema_overview(unit_ids: list[str], part_ids: list[str]) -> dict:
    """Closed enums and a maxLength on every growable field, so the worst case fits the output allowance by construction."""
    return {
        "type": "object",
        "properties": {
            "overview": {
                "type": "array",
                "maxItems": MAX_SENTENCES,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "minLength": guards.MIN_SENTENCE_CHARS,
                            "maxLength": guards.MAX_SENTENCE_CHARS,
                        },
                        "unit_ids": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": guards.MAX_UNIT_IDS,
                            "uniqueItems": True,
                            "items": {"enum": list(unit_ids)},
                        },
                        "bears_on": {
                            "type": "array",
                            "maxItems": guards.MAX_BEARS_ON,
                            "uniqueItems": True,
                            "items": {"enum": list(part_ids)},
                        },
                    },
                    "required": ["text", "unit_ids", "bears_on"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["overview"],
        "additionalProperties": False,
    }


def worst_case_output_chars(schema: dict) -> int:
    """The longest JSON this schema permits, counting structure. Recomputed from the schema itself, never hand-estimated."""
    kind = schema.get("type")
    if "enum" in schema:
        return max(len(json.dumps(v)) for v in schema["enum"])
    if kind == "string":
        if "maxLength" not in schema:
            raise ValueError(f"unbounded string node (no maxLength): {schema!r}")
        return schema["maxLength"] + 2
    if kind == "array":
        if "maxItems" not in schema:
            raise ValueError(f"unbounded array node (no maxItems): {schema!r}")
        return 2 + schema["maxItems"] * (worst_case_output_chars(schema["items"]) + 2)
    if kind == "object":
        return 2 + sum(len(key) + 6 + worst_case_output_chars(sub) for key, sub in schema["properties"].items())
    raise ValueError(f"unbounded schema node: {schema!r}")


def contract_sha256(options: dict) -> str:
    """Identity of everything model-facing about this stage: prompt, schema shape, caps, screen version, budget."""
    body = {
        "version": OVERVIEW_VERSION,
        "template": PROMPT_TEMPLATE,
        "schema": schema_overview(["U1"], ["c1"]),
        "limits": {
            "max_units": oe.MAX_UNITS,
            "max_passage_chars": oe.MAX_PASSAGE_CHARS,
            "max_claims_shown": oe.MAX_CLAIMS_SHOWN,
            "max_claim_chars": oe.MAX_CLAIM_CHARS,
            "max_prompt_chars": MAX_PROMPT_CHARS,
            "max_sentences": MAX_SENTENCES,
        },
        "screen_version": guards.SCREEN_VERSION,
        "options": options,
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def repetition_ratio(text: str, *, shingle: int = 8) -> float:
    """Share of repeated word 8-grams in a reasoning trace: ~0 for honest reasoning, near 1 for a loop. Descriptive only."""
    tokens = (text or "").split()
    if len(tokens) < shingle * 2:
        return 0.0
    grams = [tuple(tokens[i : i + shingle]) for i in range(len(tokens) - shingle + 1)]
    return round(1 - len(set(grams)) / len(grams), 4)


def canonical_hash(record: dict) -> str:
    body = {k: v for k, v in record.items() if k != "overview_hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ---- screening a model answer -----------------------------------------------------------------------------------------
def screen_proposals(proposals: list[dict], units: dict[str, dict], part_ids: set[str], entail) -> list[dict]:
    """Deterministic screen for every proposal, then ONE batched NLI call for all of them; positional reconstruction."""
    records = []
    pairs, positions = [], []
    for index, proposal in enumerate(proposals):
        reasons = guards.screen(proposal, units=units, part_ids=part_ids)
        text, unit_ids = proposal.get("text"), proposal.get("unit_ids")
        # NLI_REPAIR_DESIGN.md Section 2: a redundant inline citation marker (e.g. " (U1)") is separated from
        # the text NLI scores here -- proposal["text"] itself, saved below, is never touched by this.
        marker = (
            guards.strip_redundant_unit_markers(text, unit_ids)
            if isinstance(text, str) and isinstance(unit_ids, list)
            else None
        )
        record = {
            "index": index,
            "text": text,
            "unit_ids": unit_ids,
            "bears_on": proposal.get("bears_on"),
            "screen_reasons": reasons,
            "nli_hypothesis_text": marker["nli_hypothesis_text"] if marker else text,
            "marker_outcome": marker["marker_outcome"] if marker else None,
            "stripped_marker": marker["stripped_marker"] if marker else None,
            "nli": None,
            "nli_reasons": [],
        }
        records.append(record)
        if (
            isinstance(proposal.get("text"), str)
            and isinstance(proposal.get("unit_ids"), list)
            and all(i in units for i in proposal["unit_ids"])
            and proposal["unit_ids"]
        ):
            hypothesis = marker["nli_hypothesis_text"] if marker else text
            pairs.append(guards.nli_pair(proposal, units, hypothesis_text=hypothesis))
            positions.append(index)
    scores: list = []
    if pairs:
        try:
            scores = list(entail(pairs))
            if len(scores) != len(pairs):
                raise ValueError("entailment scorer returned a different number of scores than pairs")
        except Exception as exc:  # noqa: BLE001 - a scorer failure withholds; it never approves
            scores = [(None, None)] * len(pairs)
            for position in positions:
                records[position]["nli_error"] = type(exc).__name__
    for position, (support, contradiction) in zip(positions, scores, strict=True):
        records[position]["nli"] = {"support": support, "contradiction": contradiction}
        records[position]["nli_reasons"] = guards.nli_reasons(support, contradiction)
    for record in records:
        record["reasons"] = [*record["screen_reasons"], *record["nli_reasons"]]
        record["status"] = "withheld" if record["reasons"] else "grounded"
    return records


# ---- request-part status ------------------------------------------------------------------------------------------------
def parts_status(states: list[dict], units: list[dict], proposals: list[dict]) -> list[dict]:
    """Per request part: what the overview states about it, and what has only been judged topically responsive.

    Four statuses, none a completeness verdict (whether a part is fully answered is never assessed):
    ``passage_stated`` (a screened, unhedged statement is tagged to the part), ``hedged_only`` (only hedged statements),
    ``topical_only`` (the coverage authority attached passages but no overview statement bears on the part) and
    ``no_responsive_evidence`` (nothing attached, nothing stated). A tag is the overview model's reading of what a
    statement addresses; it is screened for well-formedness only and is displayed as such.
    """
    by_id = {u["unit_id"]: u for u in units}
    parts = []
    for state in states:
        child = state["field_id"]
        tagged = [p for p in proposals if p["status"] == "grounded" and child in (p.get("bears_on") or [])]
        attached = [u["unit_id"] for u in units if child in u["attached_children"]]
        hedged = [all(by_id[i]["flags"]["hedged"] for i in p["unit_ids"]) for p in tagged]
        if tagged and not all(hedged):
            status = "passage_stated"
        elif tagged:
            status = "hedged_only"
        elif attached:
            status = "topical_only"
        else:
            status = "no_responsive_evidence" if state["state"] != "not_assessed" else "not_assessed"
        parts.append(
            {
                "child_id": child,
                "note": state["note"],
                "coverage_state": state["state"],
                "status": status,
                "statement_indices": [p["index"] for p in tagged],
                "attached_unit_ids": attached,
                "attached_not_used": {
                    i: by_id[i]["eligibility"]["reasons"] for i in attached if not by_id[i]["eligibility"]["eligible"]
                },
            }
        )
    return parts


# ---- the stage ---------------------------------------------------------------------------------------------------------
def _call_record(result, prompt: str, reasoning: str) -> dict:
    record = dict(result.record)
    record["prompt_chars"] = len(prompt)
    record["repetition_ratio"] = repetition_ratio(reasoning)
    return record


def build_overview(
    sealed: dict,
    sealed_hash: str,
    *,
    supervisor,
    entail,
    coverage_constraints: tuple[str, ...] = (),
    on_prompt_ready=None,
    on_raw_response=None,
) -> tuple[dict, str]:
    """``(overview_record, reasoning_text)``. One model call and one NLI batch at most; the sealed ledger is only read.

    ``coverage_constraints`` is optional and additive (see `render_prompt`'s docstring) -- every existing caller
    that omits it gets today's exact prompt and behavior, unchanged.

    ``on_prompt_ready`` and ``on_raw_response`` are optional, additive crash-recovery hooks (2026-09-27); omitting
    either reproduces today's exact behavior, since neither is ever called when absent. A caller that supplies
    one is expected to persist data durably and synchronously inside it -- this function makes no retry and no
    behavior change based on what a hook does, and does not catch an exception a hook raises.

    ``on_prompt_ready(prompt: str, manifest: dict)`` fires once, unconditionally, before any model call is made
    (even when nothing will be sent) -- the "before inference" boundary.

    ``on_raw_response(result)`` fires once, immediately after the model call returns, before this function does
    anything else with the answer -- no parsing beyond what ``supervisor.call`` itself already returned, no
    screening, no ``parts_status``. ``result`` is the raw ``StageResult`` (``.answer``, ``.record``, ``.raw_text``,
    ``.thinking``) -- the earliest point at which the actual model response exists in this process at all.
    """
    question = sealed["request_contract"]["original_question"]
    states = sealed["obligation_states"]
    part_ids = [s["field_id"] for s in states]
    units, claims = oe.build_units(sealed)
    sent, prompt = select_for_prompt(units, claims, question, states, coverage_constraints=coverage_constraints)
    if on_prompt_ready is not None:
        on_prompt_ready(
            prompt,
            {
                "sealed_ledger_hash": sealed_hash,
                "question_hash": sealed["request_contract"]["question_hash"],
                "sent_unit_ids": sent,
                "eligible_unit_ids": [u["unit_id"] for u in units if u["eligibility"]["eligible"]],
                "part_ids": part_ids,
                "coverage_constraints": list(coverage_constraints),
            },
        )
    by_id = {u["unit_id"]: u for u in units}
    options = dict(getattr(supervisor, "base_options", {}))
    binding = getattr(supervisor, "binding", None)
    record: dict = {
        "version": OVERVIEW_VERSION,
        "screen_version": guards.SCREEN_VERSION,
        "screening_note": SCREENING_NOTE,
        "sealed_ledger_hash": sealed_hash,
        "question_hash": sealed["request_contract"]["question_hash"],
        "model": getattr(binding, "model", None),
        "think": getattr(binding, "think", None),
        "options": options,
        "contract_sha256": contract_sha256(options),
        "limits": {"max_units": oe.MAX_UNITS, "max_prompt_chars": MAX_PROMPT_CHARS, "max_sentences": MAX_SENTENCES},
        "coverage_constraints": list(coverage_constraints),
        "units": units,
        "claims": claims,
        "proposals": [],
        "displayed": [],
        "call": None,
        "state": "no_eligible_evidence",
        "reason_code": None
        if sent
        else ("prompt_cap" if any(u["eligibility"]["eligible"] for u in units) else "none_eligible"),
    }
    reasoning = ""
    proposals: list[dict] = []
    if sent:
        result = supervisor.call(STAGE, prompt, schema_overview(sent, part_ids), input_text=question)
        if on_raw_response is not None:
            on_raw_response(result)  # earliest boundary: before this function parses/screens anything itself
        reasoning = getattr(result, "thinking", "") or ""
        record["call"] = _call_record(result, prompt, reasoning)
        if result.answer is None:
            record["state"], record["reason_code"] = "model_no_answer", result.record.get("outcome")
        else:
            raw = result.answer.get("overview") or []
            if not raw:
                record["state"], record["reason_code"] = "model_returned_empty", None
            else:
                proposals = screen_proposals(raw, {u: by_id[u] for u in sent}, set(part_ids), entail)
                grounded = [p for p in proposals if p["status"] == "grounded"]
                record["state"] = "ok" if grounded else "no_grounded_sentences"
                record["reason_code"] = None
    record["proposals"] = proposals
    record["displayed"] = [p["index"] for p in proposals if p["status"] == "grounded"]
    record["partial"] = bool(record["displayed"]) and len(record["displayed"]) < len(proposals)
    cited = {u for p in proposals if p["status"] == "grounded" for u in p["unit_ids"]}
    record["single_passage"] = len(cited) == 1
    record["items"] = [
        {
            "sentence_id": f"o{n}",
            "text": proposals[i]["text"],
            "unit_ids": proposals[i]["unit_ids"],
            "unit_numbers": [by_id[u]["number"] for u in proposals[i]["unit_ids"]],
            "proposition_ids": sorted(
                {pid for u in proposals[i]["unit_ids"] for pid in by_id[u]["proposition_ids"]}, key=lambda s: int(s[1:])
            ),
            "bears_on": proposals[i]["bears_on"],
        }
        for n, i in enumerate(record["displayed"], start=1)
    ]
    record["parts"] = parts_status(states, units, proposals)
    record["overview_hash"] = canonical_hash(record)
    return record, reasoning


def stage_detail(record: dict) -> dict:
    return {
        "state": record["state"],
        "partial": record["partial"],
        "units": len(record["units"]),
        "units_sent": sum(1 for u in record["units"] if u["sent_to_model"]),
        "proposals": len(record["proposals"]),
        "displayed": len(record["displayed"]),
        "overview_hash": record["overview_hash"],
    }


def manifest_record(record: dict) -> dict:
    call = record["call"] or {}
    return {
        **stage_detail(record),
        "sealed_ledger_hash": record["sealed_ledger_hash"],
        "reason_code": record["reason_code"],
        "single_passage": record["single_passage"],
        "model": record["model"],
        "think": record["think"],
        "options": record["options"],
        "contract_sha256": record["contract_sha256"],
        "call": {
            k: call.get(k)
            for k in (
                "outcome",
                "done_reason",
                "allowance",
                "prompt_tokens",
                "generated_tokens",
                "wall_seconds",
                "thinking_chars",
                "repetition_ratio",
                "prompt_chars",
            )
        },
    }


def preflight_report(options: dict) -> str:
    """What S would be told and allowed, without touching a ledger, a model or the network."""
    schema = schema_overview(["U1"], ["c1"])
    tokens = worst_case_output_chars(schema)
    return "\n".join(
        [
            f"overview stage {OVERVIEW_VERSION} (role S) contract sha256 {contract_sha256(options)}",
            f"options (explicit, fixed; no fallback): {json.dumps(options, sort_keys=True)}",
            f"prompt cap {MAX_PROMPT_CHARS} chars; worst-case schema output {tokens} chars "
            f"(counted as {tokens} tokens) + {MIN_REASONING_HEADROOM} reasoning headroom vs allowance {options.get('num_predict')}",
            "",
            "PROMPT TEMPLATE",
            PROMPT_TEMPLATE,
        ]
    )
