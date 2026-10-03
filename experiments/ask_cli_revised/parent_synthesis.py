"""Phase 27: bounded parent realization -- ONE S2 call over the Phase-26 claim ledger, then two independent
fidelity layers and one batched local-NLI pass. The model decides only HOW to phrase each already-authorized
ParentClaim. It never chooses which claims exist, which are related, which passages cite them, which gaps
exist, or whether an upstream semantic assignment is correct. The ledger remains semantic authority.

Pure orchestration over an injected supervisor and entailment scorer. The only side effect is the single
``supervisor.call`` (exactly one per run, never retried). Per-claim fallback is the Phase-26 literal rendering.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import overview_guards as guards
from experiments.ask_cli_revised import parent_synthesis_render as psr
from experiments.ask_cli_revised import stages
from experiments.ask_cli_revised import topology as topo

VERSION = "parent-synthesis-realization-v1"
STAGE = "parent_synthesis"  # the supervisor's own stage label (trace/records)
STAGE_LABEL = "S2"  # the e2e stage-log name, next to the per-child S1:* entries
PARENT_PROMPT_MAX_CHARS = 16_000  # prompt cap; with num_ctx 12,288 leaves room for num_predict 4,096
OUTPUT_BUDGET_CHARS = int(topo.PARENT_SYNTHESIS_S_OPTIONS["num_predict"] * stages.CHARS_PER_TOKEN)
# A role value with at most this many content words must be carried in full by its statement. Short values are
# the slot-identity carriers (a named region, a named measure); if a statement drops one of their content words and
# substitutes another phrase, it has changed the slot's value. Longer values (a whole sentence) are not coverage-
# checked here: a faithful summary of a sentence cannot be word-for-word, and the source/NLI layers guard them.
COVERAGE_MAX_CONTENT_WORDS = 8

SKIP_REASONS = (
    "no_claims",
    "no_s_supervisor",
    "no_entailment_scorer",
    "s_binding_not_parent_envelope",
    "output_cap_exceeded",
    "prompt_too_large",
)

_PHRASE = {"supported": "supported", "not_supported": "not supported", "mixed": "mixed"}

# Overview's own cue regex is private to overview_evidence; these are the parent-specific relation cues. Matching
# uses the public ``oe.cue_stems`` helper, so no private name is reached into.
RELATION_CUES = re.compile(
    r"\b(?:because|since|while|whereas|compared|versus|than|between|linked|relationship|relation|depends?|"
    r"in contrast|unlike|together with|combined with|led to|leads to|results? in|due to|associated with|"
    r"associat\w*|correlat\w*|predict\w*|related to|relates to)\b",
    re.IGNORECASE,
)
# An overall or consensus claim about a heterogeneous or conflicting effect is never allowed to pass as one.
COLLAPSE_CUES = re.compile(
    r"\b(?:overall|in general|on average|generally|typically|consistently|across all|across every|in all|"
    r"all instances|every instance|always|universally|uniformly)\b",
    re.IGNORECASE,
)
# A heterogeneous or conflicting claim may pass by explicitly stating the disagreement, or by naming each observed
# outcome faithfully. Either way the statement must not collapse the instances to one unqualified direction.
ACKNOWLEDGE_CUES = re.compile(
    r"\b(?:differ\w*|disagree\w*|heterogene\w*|vary|varied|varies|varying|mixed|inconsisten\w*|conflict\w*|"
    r"contradict\w*|some instances|other instances|in some|in others|across instances|between instances|"
    r"did not agree|not all)\b",
    re.IGNORECASE,
)


class MalformedParentOutput(ValueError):
    """The whole model answer is not the closed item-list shape. Every claim falls back; nothing is partially trusted."""


# ---------------------------------------------------------------------------------------------
# The authorized claim envelope: a deterministic serialization of exactly what a claim may say.
# ---------------------------------------------------------------------------------------------


def _phrase(value) -> str:
    return _PHRASE.get(value, value)


def authorized_claim_text(claim: dict) -> str:
    """The only content the model is shown for a claim, and the premise of its claim-value screen. Built from
    ParentClaim fields alone: no proposition ids, no passage text beyond the claim's own values, no internal
    instance keys. Pure serialization, never a new inference."""
    kind = claim["claim_kind"]
    if kind == "role_value":
        value = claim["values"][0]
        return f"Category: {claim['category_description']}\nValue for {value['role']}: {value['exact_text']}"
    if kind == "category_list":
        items = "\n".join(f"- {v['exact_text']}" for v in claim["values"])
        return (
            f"Category: {claim['category_description']}\n"
            f"Every value listed under {claim['role']} (each must be stated):\n{items}"
        )
    if kind == "relational":
        pairs = "\n".join(f"- {v['role']}: {v['exact_text']}" for v in claim["values"])
        return f"One already-established joint relation, not separable into its parts:\n{pairs}"
    summary = claim["direction_or_effectiveness"]
    observed = ", ".join(_phrase(v) for v in summary["observed_values"]) or "none"
    consensus = (
        _phrase(summary["consensus_value"]) if summary["consensus_value"] is not None else "none (no single consensus)"
    )
    return (
        f"Structured {summary['field']} summary across instances:\n"
        f"- observed values: {observed}\n"
        f"- consensus: {consensus}\n"
        f"- heterogeneous across instances: {'yes' if summary['has_across_instance_heterogeneity'] else 'no'}\n"
        f"- conflicting within an instance: {'yes' if summary['has_within_instance_conflict'] else 'no'}"
    )


_PROMPT_HEAD = (
    "You are writing one short statement for each claim below, for a scholar's research answer. Each claim is a closed, "
    "already-decided block of content. Use ONLY the words and values given for that claim.\n\n"
    "Rules:\n"
    "- Write exactly one statement per claim_id. Do not omit a claim, add a claim, or choose which claims matter.\n"
    "- Never relate one claim to another and never combine claims. Never add a cause, a direction, a population, a "
    "mechanism, or a conclusion that the claim does not state.\n"
    "- Keep every hedge and every negation. For a claim listing observed values that differ across instances, do not "
    "state an overall effect.\n"
    "- Do not add citations or identifiers.\n\n"
)
_RETURN_SHAPE = '\n\nReturn JSON only, in this shape: {"items": [{"claim_id": "<one of the claim ids above>", "statement": "<text>"}]}\n'


def build_prompt(claim_ledger: list[dict], question: str) -> str:
    blocks = "\n\n".join(f"[{c['claim_id']}]\n{authorized_claim_text(c)}" for c in claim_ledger)
    return f"Original request (verbatim):\n{question}\n\n{_PROMPT_HEAD}Claims:\n\n{blocks}{_RETURN_SHAPE}"


def build_schema(claim_ids: list[str]) -> dict:
    """Closed: the claim id is an enum of exactly the supplied ids; the statement is bounded; there is no citation
    field, so the model has no way to name a proposition. ``maxItems`` is the claim count."""
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "maxItems": len(claim_ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_id": {"type": "string", "enum": list(claim_ids)},
                        "statement": {
                            "type": "string",
                            "minLength": guards.MIN_SENTENCE_CHARS,
                            "maxLength": guards.MAX_SENTENCE_CHARS,
                        },
                    },
                    "required": ["claim_id", "statement"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def worst_case_output_chars(schema: dict) -> int:
    return ov.worst_case_output_chars(schema)


def contract_sha256() -> str:
    """Identity of everything model-facing about this stage: version, the fixed head, the bounded schema shape, the
    caps, the screen version and the envelope. The same discipline the Overview contract uses."""
    body = {
        "version": VERSION,
        "head": _PROMPT_HEAD,
        "return_shape": _RETURN_SHAPE,
        "schema": build_schema(["X"]),
        "limits": {
            "prompt_max_chars": PARENT_PROMPT_MAX_CHARS,
            "output_budget_chars": OUTPUT_BUDGET_CHARS,
            "coverage_max_content_words": COVERAGE_MAX_CONTENT_WORDS,
        },
        "screen_version": guards.SCREEN_VERSION,
        "options": topo.PARENT_SYNTHESIS_S_OPTIONS,
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def parse_items(answer) -> list[dict]:
    """The closed item shape, or the whole answer is malformed. Extra keys are refused, never tolerated."""
    if not isinstance(answer, dict) or not isinstance(answer.get("items"), list):
        raise MalformedParentOutput("the answer is not an object carrying an items list")
    items = []
    for item in answer["items"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"claim_id", "statement"}
            or not isinstance(item["claim_id"], str)
            or not isinstance(item["statement"], str)
        ):
            raise MalformedParentOutput("an item is not exactly {claim_id, statement}")
        items.append({"claim_id": item["claim_id"], "statement": item["statement"]})
    return items


# ---------------------------------------------------------------------------------------------
# Layer A: CLAIM-VALUE fidelity -- the statement against ONLY the authorized claim envelope.
# ---------------------------------------------------------------------------------------------


def _content_stems(text: str) -> set[str]:
    return {oe.stem(w) for w in oe.words(text) if len(w) >= 4 and w not in oe._GLUE}  # noqa: SLF001 - sibling-module precedent (overview_guards)


def claim_value_reasons(claim: dict, statement: str, claim_ledger: list[dict]) -> list[str]:
    """Reasons a statement is not faithful to the claim's own authorized content. Empty means it passed."""
    envelope = authorized_claim_text(claim)
    cid = claim["claim_id"]
    unit = {"unit_id": cid, "passage": envelope, "paper_id": 0, "flags": oe.passage_flags(envelope)}
    reasons = list(
        guards.screen({"text": statement, "unit_ids": [cid], "bears_on": []}, units={cid: unit}, part_ids=set())
    )

    statement_stems = {oe.stem(w) for w in oe.words(statement)}
    envelope_stems = {oe.stem(w) for w in oe.words(envelope)}
    # Slot identity: a short role value must be carried in full. Dropping its words in favour of another phrase
    # from the same passage changes which thing the slot holds, even when every word that was written is supported.
    for value in claim["values"]:
        tokens = _content_stems(value["exact_text"])
        if 0 < len(tokens) <= COVERAGE_MAX_CONTENT_WORDS:
            missing = sorted(tokens - statement_stems)
            if missing:
                reasons.append(f"value_not_covered:{value['role']}:{','.join(missing)}")
    # Semantic content imported from another claim: every token of another claim's value present in this statement
    # and absent from this claim's own envelope.
    for other in claim_ledger:
        if other["claim_id"] == cid:
            continue
        for value in other["values"]:
            tokens = _content_stems(value["exact_text"])
            if tokens and tokens <= statement_stems and not tokens <= envelope_stems:
                reasons.append(f"imports_other_claim:{other['claim_id']}")
                break
    # New relationship language the claim does not state.
    new_cues = oe.cue_stems(RELATION_CUES, statement) - oe.cue_stems(RELATION_CUES, envelope)
    if new_cues:
        reasons.append(f"relation_language_not_in_claim:{','.join(sorted(new_cues))}")
    return reasons


# ---------------------------------------------------------------------------------------------
# Layer B: SOURCE-PASSAGE fidelity -- the statement against ONLY the claim's authorized passages.
# ---------------------------------------------------------------------------------------------


def _passage_units(claim: dict, sealed: dict) -> tuple[list[str], dict | None]:
    index = {row["proposition_id"]: row for row in sealed["verified_propositions"]}
    ids = list(claim["admissible_proposition_ids"])
    units = {}
    for pid in ids:
        row = index.get(pid)
        if row is None:
            return ids, None  # an unresolvable authorized passage: the caller treats the layer as unavailable
        units[pid] = {
            "unit_id": pid,
            "passage": row["quote"],
            "paper_id": row["paper_id"],
            "flags": oe.passage_flags(row["quote"]),
        }
    return ids, units


def source_passage_reasons(claim: dict, statement: str, sealed: dict) -> list[str]:
    """Is this phrasing supported by the evidence the semantic engine already authorized for this claim? Answers
    nothing about whether the claim itself is scientifically right."""
    ids, units = _passage_units(claim, sealed)
    if not ids:
        return ["no_admissible_passage"]
    if len(ids) > guards.MAX_UNIT_IDS:
        return ["source_set_exceeds_screen_limit"]
    if units is None:
        return ["unresolved_authorized_passage"]
    return list(guards.screen({"text": statement, "unit_ids": ids, "bears_on": []}, units=units, part_ids=set()))


# ---------------------------------------------------------------------------------------------
# The parent-only heterogeneity / conflict guard (Phase 25 §11; Phase 18 semantics are NOT touched here).
# ---------------------------------------------------------------------------------------------


def heterogeneity_reasons(claim: dict, statement: str) -> list[str]:
    summary = claim.get("conflict_or_heterogeneity")
    if not summary or not (summary["has_within_instance_conflict"] or summary["has_across_instance_heterogeneity"]):
        return []
    collapses = sorted({m.group(0).lower() for m in COLLAPSE_CUES.finditer(statement)})
    if collapses:
        return [f"consensus_collapse:{c}" for c in collapses]
    if ACKNOWLEDGE_CUES.search(statement):
        return []
    words = {w.lower() for w in re.findall(r"[A-Za-z']+", statement)}
    observed = claim["direction_or_effectiveness"]["observed_values"]
    if observed and all(all(w in words for w in _phrase(v).lower().split()) for v in observed):
        return []  # every observed outcome is named faithfully
    return ["heterogeneity_not_stated"]


# ---------------------------------------------------------------------------------------------
# Screening all candidates: lexical layers per claim, then ONE batched NLI pass.
# ---------------------------------------------------------------------------------------------


def lexical_screens(claim: dict, statement: str, claim_ledger: list[dict], sealed: dict) -> dict:
    """The three pure, cheap layers, separately reported. Used by the screen and re-run by the audit."""
    return {
        "claim": claim_value_reasons(claim, statement, claim_ledger),
        "evidence": source_passage_reasons(claim, statement, sealed),
        "heterogeneity": heterogeneity_reasons(claim, statement),
    }


def _screen_candidates(candidates: list[dict], claim_ledger: list[dict], sealed: dict, entail) -> dict[str, dict]:
    """``{claim_id: screen}`` for every candidate. The NLI pairs for ALL candidates go through ``entail`` in one call
    (claim-envelope -> statement, then authorized-passage -> statement, interleaved per candidate). Results are
    reattached positionally, the same discipline ``overview.screen_proposals`` already uses. A scorer failure
    withholds every candidate that needed it; it never approves one."""
    by_claim = {c["claim_id"]: c for c in claim_ledger}
    screens: dict[str, dict] = {}
    pairs, slots = [], []
    for item in candidates:
        claim = by_claim[item["claim_id"]]
        statement = item["statement"]
        lexical = lexical_screens(claim, statement, claim_ledger, sealed)
        screens[claim["claim_id"]] = {**lexical, "nli": {"claim": None, "evidence": None}, "nli_error": None}
        envelope_unit = {claim["claim_id"]: {"passage": authorized_claim_text(claim)}}
        pairs.append(guards.nli_pair({"unit_ids": [claim["claim_id"]], "text": statement}, envelope_unit))
        slots.append((claim["claim_id"], "claim"))
        ids, units = _passage_units(claim, sealed)
        if ids and units is not None and len(ids) <= guards.MAX_UNIT_IDS:
            pairs.append(guards.nli_pair({"unit_ids": ids, "text": statement}, units))
            slots.append((claim["claim_id"], "evidence"))
    if pairs:
        try:
            scores = list(entail(pairs))
            if len(scores) != len(pairs):
                raise ValueError("entailment scorer returned a different number of scores than pairs")
        except Exception as exc:  # noqa: BLE001 - a scorer failure withholds; it never approves
            scores = [(None, None)] * len(pairs)
            for cid, _layer in slots:
                screens[cid]["nli_error"] = type(exc).__name__
        for (cid, layer), (support, contradiction) in zip(slots, scores, strict=True):
            screens[cid]["nli"][layer] = {"support": support, "contradiction": contradiction}
    for screen in screens.values():
        if screen["nli_error"] is not None:
            screen["nli_reasons"] = ["nli_unavailable"]
            continue
        screen["nli_reasons"] = [
            reason
            for layer in ("claim", "evidence")
            if screen["nli"][layer] is not None
            for reason in guards.nli_reasons(screen["nli"][layer]["support"], screen["nli"][layer]["contradiction"])
        ]
    return screens


# ---------------------------------------------------------------------------------------------
# The one realization call and its per-claim decisions.
# ---------------------------------------------------------------------------------------------


def _segment(claim: dict, *, status: str, proposed=None, screen=None) -> dict:
    screen = screen or {}
    grounded = status == "grounded"
    reasons_nli = screen.get("nli_reasons", [])
    return {
        "claim_id": claim["claim_id"],
        "claim_kind": claim["claim_kind"],
        "proposed_text": proposed,
        "final_text": proposed if grounded else psr.literal_statement(claim),
        "status": status,
        "fallback_used": not grounded,
        "claim_screen_reasons": list(screen.get("claim", [])),
        "evidence_screen_reasons": list(screen.get("evidence", [])),
        "heterogeneity_reasons": list(screen.get("heterogeneity", [])),
        "nli_reasons": list(reasons_nli),
        "nli": screen.get("nli"),
        "nli_error": screen.get("nli_error"),
        "cited_proposition_ids": list(claim["admissible_proposition_ids"]),
    }


def _result(
    state,
    *,
    claim_ledger,
    segments,
    call_attempted,
    skip_reason=None,
    whole_status=None,
    unknown=(),
    model=None,
    prompt_sha=None,
    schema_sha=None,
    outcome=None,
) -> dict:
    grounded = sum(1 for s in segments if s["status"] == "grounded")
    return {
        "state": state,
        "skip_reason": skip_reason,
        "call_attempted": call_attempted,
        "whole_call_status": whole_status,
        "call_outcome": outcome,
        "model": model,
        "prompt_sha256": prompt_sha,
        "schema_sha256": schema_sha,
        "contract_sha256": contract_sha256() if call_attempted else None,
        "segments": segments,
        "unknown_claim_ids": sorted(unknown),
        "grounded_count": grounded,
        "fallback_count": len(segments) - grounded,
        "claim_count": len(claim_ledger),
    }


def _all_fallback(claim_ledger, status):
    return [_segment(c, status=status) for c in claim_ledger]


def realize(
    claim_ledger: list[dict],
    sealed: dict,
    *,
    supervisor,
    entail,
    question: str,
    prompt_char_cap: int = PARENT_PROMPT_MAX_CHARS,
    call_context=None,
) -> dict:
    """The bounded realization. At most ONE supervisor call, never retried, and one batched screen. Every ParentClaim
    yields exactly one segment: grounded model text, or the deterministic literal, for the reason recorded on it.

    ``call_context``, when supplied, is a zero-argument callable returning a context manager entered only around the
    single supervisor call (the e2e caller passes its stage logger, so a skipped run leaves no S2 entry)."""
    if not claim_ledger:
        return _result(
            "no_claims", claim_ledger=claim_ledger, segments=[], call_attempted=False, skip_reason="no_claims"
        )

    def skipped(reason):
        return _result(
            "deterministic_fallback",
            claim_ledger=claim_ledger,
            segments=_all_fallback(claim_ledger, "not_called"),
            call_attempted=False,
            skip_reason=reason,
        )

    if supervisor is None:
        return skipped("no_s_supervisor")
    if entail is None:
        return skipped("no_entailment_scorer")
    binding = supervisor.binding
    if not (
        binding.kind == "ollama"
        and binding.think is False
        and dict(supervisor.base_options) == topo.PARENT_SYNTHESIS_S_OPTIONS
    ):
        return skipped("s_binding_not_parent_envelope")

    ids = [c["claim_id"] for c in claim_ledger]
    schema = build_schema(ids)
    if worst_case_output_chars(schema) > OUTPUT_BUDGET_CHARS:
        return skipped("output_cap_exceeded")
    prompt = build_prompt(claim_ledger, question)
    if len(prompt) > prompt_char_cap:
        return skipped("prompt_too_large")

    model = {"role": "S", "model_name": binding.model, "think": binding.think, "options": dict(supervisor.base_options)}
    prompt_sha, schema_sha = (
        hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        hashlib.sha256(json.dumps(schema, sort_keys=True).encode("utf-8")).hexdigest(),
    )

    try:
        with call_context() if call_context is not None else contextlib.nullcontext():
            result = supervisor.call(STAGE, prompt, schema, input_text=question)
    except Exception as exc:  # noqa: BLE001 - a transport failure falls back; it is never retried
        return _result(
            "deterministic_fallback",
            claim_ledger=claim_ledger,
            segments=_all_fallback(claim_ledger, "whole_call_failed"),
            call_attempted=True,
            whole_status=f"exception:{type(exc).__name__}",
            model=model,
            prompt_sha=prompt_sha,
            schema_sha=schema_sha,
        )
    outcome = (result.record or {}).get("outcome")
    if result.answer is None:
        return _result(
            "deterministic_fallback",
            claim_ledger=claim_ledger,
            segments=_all_fallback(claim_ledger, "whole_call_failed"),
            call_attempted=True,
            whole_status="model_no_answer",
            model=model,
            prompt_sha=prompt_sha,
            schema_sha=schema_sha,
            outcome=outcome,
        )
    try:
        items = parse_items(result.answer)
    except MalformedParentOutput:
        return _result(
            "deterministic_fallback",
            claim_ledger=claim_ledger,
            segments=_all_fallback(claim_ledger, "whole_call_failed"),
            call_attempted=True,
            whole_status="malformed_output",
            model=model,
            prompt_sha=prompt_sha,
            schema_sha=schema_sha,
            outcome=outcome,
        )

    by_id: dict[str, list[dict]] = {}
    for item in items:
        by_id.setdefault(item["claim_id"], []).append(item)
    unknown = [cid for cid in by_id if cid not in ids]

    candidates = []
    statuses: dict[str, str] = {}
    for claim in claim_ledger:
        matched = by_id.get(claim["claim_id"], [])
        if not matched:
            statuses[claim["claim_id"]] = "missing"
        elif len(matched) > 1:
            statuses[claim["claim_id"]] = "duplicate"
        else:
            statuses[claim["claim_id"]] = "candidate"
            candidates.append(matched[0])

    screens = _screen_candidates(candidates, claim_ledger, sealed, entail)
    proposed = {c["claim_id"]: c["statement"] for c in candidates}
    segments = []
    for claim in claim_ledger:
        cid = claim["claim_id"]
        if statuses[cid] != "candidate":
            segments.append(_segment(claim, status=statuses[cid]))
            continue
        screen = screens[cid]
        clean = not (screen["claim"] or screen["evidence"] or screen["heterogeneity"] or screen["nli_reasons"])
        segments.append(
            _segment(claim, status="grounded" if clean else "withheld", proposed=proposed[cid], screen=screen)
        )

    grounded = sum(1 for s in segments if s["status"] == "grounded")
    state = (
        "model_realized"
        if grounded == len(segments)
        else ("deterministic_fallback" if grounded == 0 else "mixed_model_and_fallback")
    )
    return _result(
        state,
        claim_ledger=claim_ledger,
        segments=segments,
        call_attempted=True,
        model=model,
        prompt_sha=prompt_sha,
        schema_sha=schema_sha,
        unknown=unknown,
        outcome=outcome,
        whole_status="ok",
    )
