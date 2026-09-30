"""Managed-local Qwen task wrappers for the staged synthesis experiment.

The local model is used as a natural-language reader, not as a scientific authority or database clerk.
Each call has one bounded job. Deterministic code owns IDs, taxonomy-free bookkeeping, provenance,
validation, and orchestration. Raw prompts/outputs and timings are preserved for postmortem analysis.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from typing import Any

from app.backend.llm.managed_local import ManagedProviderRuntime
from app.backend.llm.providers import ProviderError, complete
from experiments.ask_cli_revised import execution_policy
from experiments.ask_cli_revised.backends import NativeWorker
from experiments.ask_cli_revised.calibration.structured_output import RESPONSE_FORMAT, schema_config
from experiments.ask_cli_revised.request_contract import obligation_display
from experiments.ask_cli_revised.retrieval import GATE_NO_ANSWER
from experiments.ask_cli_revised.trace import TraceWriter

_DECOMPOSE_OUTPUT_TOKENS = 512
_OBLIGATION_OUTPUT_TOKENS = 256
_GATE_OUTPUT_TOKENS = 48
_EVIDENCE_SELECT_OUTPUT_TOKENS = 96
_CLAIM_OUTPUT_TOKENS = 512
_OBLIGATION_MAP_OUTPUT_TOKENS = 96
_RECOVERY_OUTPUT_TOKENS = 64
_NOMINATION_OUTPUT_TOKENS = 256
_NOMINATION_EXACT_TEXT_MAX_LEN = 300
_NOMINATION_MAX_ITEMS = 8


def evidence_selection_schema(span_ids: list[str], max_spans: int = 4) -> dict:
    """Wrap the existing ID-only task; empty selection remains a valid result."""
    return {
        "type": "object",
        "required": ["span_ids"],
        "additionalProperties": False,
        "properties": {
            "span_ids": {
                "type": "array",
                "maxItems": max_spans,
                "items": {"type": "string", "enum": span_ids},
            }
        },
    }


def nomination_prompt(*, category_description: str, candidates: list[dict]) -> str:
    """Pure prompt builder, separated from `QwenTasks.nominate_sufficiency_role` so its
    leakage-safety (no provenance token, no hidden benchmark vocabulary, no requirement/child id)
    is directly testable without any model or network call. The ONLY sufficiency-layer string
    this ever interpolates from the contract is `category_description` (see
    `sufficiency_authoring.py`'s own D10 compliance note); `candidates` are already-verified
    excerpt text a caller supplies -- genuine evidence-originated terms there are not a leak
    (see `test_sufficiency_leakage.py`'s explicit scope note)."""
    excerpt_text = "\n\n".join(f"[{c['proposition_id']}] {c['passage']}" for c in candidates)
    return (
        f"Does any excerpt below name a SPECIFIC instance of {category_description}, as "
        f"opposed to a generic/unspecified reference to {category_description}?\n\n"
        "For each excerpt that names one, return its id and the exact supporting substring "
        "copied verbatim from that excerpt. An excerpt may name more than one distinct "
        "instance -- return each separately. Do not paraphrase. Do not invent an excerpt id. "
        "If none qualify, return an empty list.\n\n"
        'Return only JSON: {"nominations":[{"proposition_id":"...","exact_text":"..."}]}\n\n'
        f"Excerpts:\n{excerpt_text}"
    )


def nomination_schema(proposition_ids: list[str], max_items: int = _NOMINATION_MAX_ITEMS) -> dict:
    """Closed-enum proposition_id (never a unit_id and never an index-based translation -- a
    hallucinated or mistranslated id is schema-impossible). exact_text stays free text; grounding
    is re-verified deterministically by the caller (`sufficiency_mapping.nominate_with_model`),
    never trusted from the schema alone."""
    return {
        "type": "object",
        "required": ["nominations"],
        "additionalProperties": False,
        "properties": {
            "nominations": {
                "type": "array",
                "maxItems": max_items,
                "items": {
                    "type": "object",
                    "required": ["proposition_id", "exact_text"],
                    "additionalProperties": False,
                    "properties": {
                        "proposition_id": {"type": "string", "enum": proposition_ids},
                        "exact_text": {"type": "string", "maxLength": _NOMINATION_EXACT_TEXT_MAX_LEN},
                    },
                },
            }
        },
    }


def _validate_nominations(payload: Any, *, allowed_proposition_ids: set[str], limit: int) -> tuple[list[dict], bool]:
    if not isinstance(payload, dict) or not isinstance(payload.get("nominations"), list):
        return [], False
    out: list[dict] = []
    for item in payload["nominations"][:limit]:
        if not isinstance(item, dict):
            continue
        proposition_id = item.get("proposition_id")
        exact_text = item.get("exact_text")
        if not isinstance(proposition_id, str) or proposition_id not in allowed_proposition_ids:
            continue
        if not isinstance(exact_text, str) or not exact_text.strip():
            continue
        out.append(
            {"proposition_id": proposition_id, "exact_text": exact_text.strip()[:_NOMINATION_EXACT_TEXT_MAX_LEN]}
        )
    return out, True


# Same grammar-constrained mechanism as evidence_selection_schema, applied to the demonstrated
# claim-formation truncation failure (Sep-7/Sep-9 postmortems). A plain string (empty = no claim)
# avoids relying on the grammar converter's nullable-type support -- the untested question here is
# "does schema enforcement fix truncation", not "does this topology support `string|null`".
_CLAIM_SCHEMA = {
    "type": "object",
    "required": ["claim"],
    "additionalProperties": False,
    "properties": {"claim": {"type": "string", "maxLength": 800}},
}


# The gate action is a closed enum, so it is schema-constrained like the other worker tasks. The unconstrained
# 48-token call let the model write prose before its JSON: 99 of 152 gate calls in run9 were truncated and then
# silently treated as "accept". A residual mechanical failure now returns NO ANSWER, never an implicit accept.
_GATE_ACTIONS = ["accept", "before", "after", "both", "discard"]
_GATE_SCHEMA = {
    "type": "object",
    "required": ["action"],
    "additionalProperties": False,
    "properties": {"action": {"type": "string", "enum": _GATE_ACTIONS}},
}
# Same repair for the recovery query (3 of 6 run9 queries were truncated and replaced by the literal obligation
# text, i.e. a "recovery" that re-searched the initial view).
_QUERY_SCHEMA = {
    "type": "object",
    "required": ["query"],
    "additionalProperties": False,
    "properties": {"query": {"type": "string", "maxLength": 200}},
}


def _extract_json(text: str):
    """Return the first balanced JSON value embedded in model text."""
    if not text:
        return None
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(text, index)
        except ValueError:
            continue
        return payload
    return None


def _with_output_cap(config: object, output_cap: int) -> object:
    """Return a managed-local config with a small task-specific generation ceiling.

    The production managed target is intentionally unchanged. This experiment only replaces the request-side
    wrapper so a 20-token classification cannot spend 4096 tokens or sit at the 10-minute transport ceiling.
    """
    runtime = getattr(config, "provider_runtime", None)
    if not isinstance(runtime, ManagedProviderRuntime):
        return config
    capped_runtime = ManagedProviderRuntime(runtime.base_runtime, output_cap=output_cap, contract=None)
    return replace(
        config,
        provider_runtime=capped_runtime,
        max_output_tokens=output_cap,
        managed_output_contract=None,
    )


@dataclass(frozen=True)
class _CallResult:
    raw_text: str
    provider_ok: bool
    failure_reason: str | None
    elapsed_seconds: float
    output_cap: int
    extra: dict | None = None  # per-call telemetry (model, allowance, done_reason, ...) for Ollama-native workers


@dataclass
class QwenTasks:
    config: object  # ManagedProviderConfig
    trace: TraceWriter

    def _call_native(self, *, prompt: str, output_cap: int, json_schema: dict | None) -> _CallResult:
        """An Ollama-native worker: one call through the execution-policy seam at the task's own small cap."""
        if json_schema is None:
            raise ValueError("native worker calls are schema-constrained; pass json_schema")
        worker = self.config
        result = execution_policy.run_stage_call(
            worker.client,
            model_tag=worker.model,
            stage="worker",
            prompt=prompt,
            schema=json_schema,
            base_options={**worker.base_options, "num_predict": output_cap},
            think=worker.think,
        )
        record = result.record
        outcome = record["outcome"]
        return _CallResult(
            raw_text=result.raw_text,
            provider_ok=record["usable"],
            failure_reason=None
            if record["usable"]
            else ("truncated_at_output_cap" if outcome == execution_policy.CAPPED else outcome),
            elapsed_seconds=record.get("wall_seconds") or 0.0,
            output_cap=output_cap,
            extra=record,
        )

    def _call(self, *, prompt: str, output_cap: int, json_schema: dict | None = None) -> _CallResult:
        if isinstance(self.config, NativeWorker):
            return self._call_native(prompt=prompt, output_cap=output_cap, json_schema=json_schema)
        started = time.monotonic()
        try:
            config = (
                schema_config(self.config, output_cap=output_cap, json_schema=json_schema, mode=RESPONSE_FORMAT)
                if json_schema is not None
                else _with_output_cap(self.config, output_cap)
            )
            result = complete(config, prompt)
        except ProviderError as exc:
            return _CallResult(
                raw_text="",
                provider_ok=False,
                failure_reason=f"provider_error: {exc}",
                elapsed_seconds=time.monotonic() - started,
                output_cap=output_cap,
            )
        if getattr(result, "truncated", False):
            return _CallResult(
                raw_text=result.text or "",
                provider_ok=False,
                failure_reason="truncated_at_output_cap",
                elapsed_seconds=time.monotonic() - started,
                output_cap=output_cap,
            )
        return _CallResult(
            raw_text=result.text or "",
            provider_ok=True,
            failure_reason=None,
            elapsed_seconds=time.monotonic() - started,
            output_cap=output_cap,
        )

    def _record(
        self,
        *,
        stage: str,
        task: str,
        prompt: str,
        input_text: str,
        call: _CallResult,
        parsed: Any,
        valid: bool,
        fallback_used: bool,
        consequence: str,
    ) -> None:
        self.trace.qwen_call(
            stage=stage,
            task=task,
            input_text=input_text,
            prompt_text=prompt,
            raw_output=call.raw_text,
            provider_ok=call.provider_ok,
            parse_ok=parsed is not None,
            validation_ok=valid,
            failure_reason=call.failure_reason,
            deterministic_fallback_used=fallback_used,
            downstream_consequence=consequence,
            elapsed_seconds=call.elapsed_seconds,
            output_cap=call.output_cap,
            extra=getattr(call, "extra", None),
        )

    # ---- Stage 1: question interpretation ---------------------------------------------------------

    def interpret(self, question: str) -> tuple[list[dict], bool]:
        """Decompose first, then identify requested information one subquestion at a time.

        Natural-language obligations are canonical. Qwen never assigns IDs or maps requests into a closed
        ontology. Those were independent failure surfaces in the first frozen run and were not needed by the
        downstream experiment.
        """
        prompt = (
            "You are reading a complex scholarly question.\n\n"
            "Your only job is to identify the separate questions the user is asking.\n"
            "Do not answer them.\n"
            "Do not add scientific knowledge.\n"
            "Do not introduce comparisons, populations, causes, constructs, or relationships that the user "
            "did not explicitly request.\n"
            "Preserve the user's meaning and wording as closely as possible.\n"
            "Preserve relationships between things the user asked about.\n"
            "If one requested detail modifies another, keep them together in the same subquestion.\n\n"
            "Write each subquestion as a complete standalone question.\n\n"
            "Return only JSON:\n"
            '[{"question":"..."}]\n\n'
            f"Question:\n{question}"
        )
        call = self._call(prompt=prompt, output_cap=_DECOMPOSE_OUTPUT_TOKENS)
        parsed = _extract_json(call.raw_text) if call.provider_ok else None
        texts, valid = _validate_subquestion_texts(parsed)
        # A long request containing several explicit question marks cannot be faithfully represented by one
        # short subquestion. Run 0 exposed exactly this failure: parseable JSON preserved only the first clause.
        # Treat that as semantic incompleteness, not success, and let the whole-question fallback feed the
        # separate requested-information reader instead of silently deleting the remaining requests.
        if valid and len(texts) == 1 and question.count("?") > 1:
            valid = False
        decomposition_fallback = not (call.provider_ok and valid)
        if decomposition_fallback:
            texts = [question.strip()]
        self._record(
            stage="01_interpret",
            task="decompose_subquestions",
            prompt=prompt,
            input_text=question,
            call=call,
            parsed=parsed,
            valid=valid,
            fallback_used=decomposition_fallback,
            consequence=(
                "one whole-question fallback subquestion"
                if decomposition_fallback
                else f"{len(texts)} natural-language subquestions"
            ),
        )

        subquestions: list[dict] = []
        any_fallback = decomposition_fallback
        for index, text in enumerate(texts, start=1):
            sid = f"s{index}"
            obligations, used_fallback = self._requested_information(text, sid)
            any_fallback = any_fallback or used_fallback
            subquestions.append({"subquestion_id": sid, "text": text, "obligations": obligations})
        return subquestions, any_fallback

    def _requested_information(self, subquestion: str, sid: str) -> tuple[list[dict], bool]:
        prompt = (
            "You are reading one scholarly subquestion.\n\n"
            "Your only job is to list the specific pieces of information the user explicitly asks for.\n"
            "Do not answer the question.\n"
            "Do not add information or infer requests that are not present.\n"
            "Preserve requested relationships between things.\n"
            "Use the user's wording where possible.\n\n"
            "Return only JSON:\n"
            '[{"requested":"..."}]\n\n'
            f"Subquestion:\n{subquestion}"
        )
        call = self._call(prompt=prompt, output_cap=_OBLIGATION_OUTPUT_TOKENS)
        parsed = _extract_json(call.raw_text) if call.provider_ok else None
        requested, valid = _validate_requested_items(parsed)
        used_fallback = not (call.provider_ok and valid)
        if used_fallback:
            requested = [subquestion.strip()]
        obligations = [{"field_id": f"{sid}-o{index}", "note": item} for index, item in enumerate(requested, start=1)]
        self._record(
            stage="01_interpret",
            task="extract_requested_information",
            prompt=prompt,
            input_text=subquestion,
            call=call,
            parsed=parsed,
            valid=valid,
            fallback_used=used_fallback,
            consequence=f"{len(obligations)} natural-language obligations for {sid}",
        )
        return obligations, used_fallback

    # ---- Stage 5: context-growth controller -------------------------------------------------------

    def context_gate(self, *, packet_text: str, subquestion: str) -> dict:
        prompt = (
            "You are reading a passage from a scholarly paper because it may help answer one question.\n\n"
            "Choose what Callosum should do next:\n"
            "accept = the current text already contains at least one complete scientific claim relevant to "
            "the question. Stop reading farther even if nearby text might contain additional findings.\n"
            "before = the text may be relevant, but preceding context is likely needed to understand a useful "
            "complete thought.\n"
            "after = the text may be relevant, but following context is likely needed to understand a useful "
            "complete thought.\n"
            "both = context on both sides is likely needed.\n"
            "discard = even with nearby context, this text is unlikely to provide a scientific claim that helps "
            "answer the question. Examples include abbreviation lists, headings, bibliographic metadata, keyword "
            "lists, and unrelated discussion.\n\n"
            "Do not answer the scholarly question. Do not choose before/after/both merely because more nearby "
            "material could be interesting. Grow only when context is needed to make the current material "
            "interpretable or potentially responsive.\n\n"
            'Return only JSON: {"action":"accept|before|after|both|discard"}\n\n'
            f"Question:\n{subquestion}\n\nCurrent text:\n{packet_text}"
        )
        call = self._call(prompt=prompt, output_cap=_GATE_OUTPUT_TOKENS, json_schema=_GATE_SCHEMA)
        parsed = _extract_json(call.raw_text) if call.provider_ok else None
        gate, valid = _validate_gate(parsed)
        no_answer = not (call.provider_ok and valid)
        if no_answer:
            gate = {"action": GATE_NO_ANSWER}
        self._record(
            stage="05_context_gate",
            task="context_gate",
            prompt=prompt,
            input_text=f"[subq] {subquestion}\n[packet] {packet_text}",
            call=call,
            parsed=parsed,
            valid=valid,
            fallback_used=False,  # NO ANSWER is a mechanical state, not a fallback verdict
            consequence=(
                "NO ANSWER (mechanical): packet not accepted, not grown, excluded from evidence extraction"
                if no_answer
                else f"action={gate['action']}"
            ),
        )
        return gate

    # ---- Stage 6: small evidence/claim tasks ------------------------------------------------------

    def select_evidence(
        self, *, spans: list[dict], subquestion: str, obligations: list[dict], max_spans: int = 4
    ) -> list[str]:
        requested = "\n".join(f"- {o['field_id']}: {obligation_display(o)}" for o in obligations)
        span_text = "\n\n".join(f"[{s['span_id']}] {s['text']}" for s in spans)
        prompt = (
            "You are choosing exact source excerpts that may answer one scholarly question.\n\n"
            "Select only excerpts that directly state a scientific finding, result, association, null result, "
            "or scientifically informative conclusion responsive to the question or requested information.\n"
            "Do not select contact information, headings, keyword lists, references, or hypotheses stated only "
            "as predictions. Methods are useful only when the requested information explicitly asks how something "
            "was measured.\n"
            "Do not paraphrase or copy the excerpts. Return only their IDs.\n"
            f"Select at most {max_spans}. If none are useful, return an empty list.\n\n"
            'Return only JSON: {"span_ids":["e1"]}\n\n'
            f"Question:\n{subquestion}\n\nRequested information:\n{requested or '(none)'}\n\n"
            f"Candidate excerpts:\n{span_text}"
        )
        call = self._call(
            prompt=prompt,
            output_cap=_EVIDENCE_SELECT_OUTPUT_TOKENS,
            json_schema=evidence_selection_schema([s["span_id"] for s in spans], max_spans),
        )
        parsed = _extract_json(call.raw_text) if call.provider_ok else None
        allowed = {s["span_id"] for s in spans}
        selected, valid = _validate_id_list(parsed, key="span_ids", allowed=allowed, limit=max_spans)
        used_fallback = not (call.provider_ok and valid)
        if used_fallback:
            selected = []
        self._record(
            stage="06_extract",
            task="select_evidence",
            prompt=prompt,
            input_text=f"[subq] {subquestion}\n[span_ids] {[s['span_id'] for s in spans]}",
            call=call,
            parsed=parsed,
            valid=valid,
            fallback_used=used_fallback,
            consequence=f"selected {len(selected)} exact source excerpts",
        )
        return selected

    def form_claim(self, *, quote: str, context_text: str, subquestion: str) -> str | None:
        prompt = (
            "You are given ONE exact excerpt from a scholarly paper plus surrounding context.\n\n"
            "Your only job is to state ONE atomic scientific claim directly supported by the exact excerpt.\n"
            "Use surrounding context only to resolve what the excerpt means.\n"
            "Do not add outside knowledge, mechanisms, causes, populations, or interpretations not supported by "
            "the excerpt and its context.\n"
            "Preserve negation, null findings, direction, uncertainty, and qualifications.\n"
            "Do not turn a hypothesis or method into a result.\n"
            "If the exact excerpt does not support a scientific claim responsive to the question, return an "
            "empty string.\n\n"
            'Return only JSON: {"claim":"..."} or {"claim":""}\n\n'
            f"Question:\n{subquestion}\n\nSurrounding context:\n{context_text}\n\n"
            f"Exact evidence:\n{quote}"
        )
        call = self._call(prompt=prompt, output_cap=_CLAIM_OUTPUT_TOKENS, json_schema=_CLAIM_SCHEMA)
        parsed = _extract_json(call.raw_text) if call.provider_ok else None
        claim, valid = _validate_claim(parsed)
        used_fallback = not (call.provider_ok and valid)
        if used_fallback:
            claim = None
        self._record(
            stage="06_extract",
            task="form_claim",
            prompt=prompt,
            input_text=f"[subq] {subquestion}\n[quote] {quote}",
            call=call,
            parsed=parsed,
            valid=valid,
            fallback_used=used_fallback,
            consequence="one candidate claim" if claim else "no candidate claim",
        )
        return claim

    def map_obligations(self, *, claim: str, obligations: list[dict]) -> list[str]:
        if not obligations:
            return []
        if len(obligations) == 1:
            return [obligations[0]["field_id"]]
        requested = "\n".join(f"- {o['field_id']}: {obligation_display(o)}" for o in obligations)
        prompt = (
            "You are mapping one candidate scientific claim to the user's requested information.\n\n"
            "Select only requested items that the claim directly helps answer. Do not infer extra relationships.\n"
            "If it answers none, return an empty list.\n\n"
            'Return only JSON: {"field_ids":["s1-o1"]}\n\n'
            f"Candidate claim:\n{claim}\n\nRequested information:\n{requested}"
        )
        call = self._call(prompt=prompt, output_cap=_OBLIGATION_MAP_OUTPUT_TOKENS)
        parsed = _extract_json(call.raw_text) if call.provider_ok else None
        allowed = {o["field_id"] for o in obligations}
        mapped, valid = _validate_id_list(parsed, key="field_ids", allowed=allowed, limit=len(allowed))
        used_fallback = not (call.provider_ok and valid)
        if used_fallback:
            mapped = []
        self._record(
            stage="06_extract",
            task="map_obligations",
            prompt=prompt,
            input_text=claim,
            call=call,
            parsed=parsed,
            valid=valid,
            fallback_used=used_fallback,
            consequence=f"mapped to {len(mapped)} requested items",
        )
        return mapped

    # ---- Stage 10: recovery query ----------------------------------------------------------------

    def recovery_query(self, *, subquestion: str, obligation_note: str) -> str | None:
        """A short retrieval phrase, or ``None`` (NO ANSWER) when the call fails: never the literal obligation text."""
        prompt = (
            "Write a short retrieval phrase for finding the missing information below.\n"
            "Use wording from the scholarly question and missing information.\n"
            "Do not answer the question and do not add related concepts.\n"
            "Use at most 12 words.\n\n"
            'Return only JSON: {"query":"..."}\n\n'
            f"Scholarly question:\n{subquestion}\n\nMissing information:\n{obligation_note}"
        )
        call = self._call(prompt=prompt, output_cap=_RECOVERY_OUTPUT_TOKENS, json_schema=_QUERY_SCHEMA)
        parsed = _extract_json(call.raw_text) if call.provider_ok else None
        query, valid = _validate_query(parsed)
        no_answer = not (call.provider_ok and valid)
        self._record(
            stage="10_recovery",
            task="recovery_query",
            prompt=prompt,
            input_text=f"[subq] {subquestion}\n[missing] {obligation_note}",
            call=call,
            parsed=parsed,
            valid=valid,
            fallback_used=False,  # NO ANSWER is a mechanical state, not a fallback query
            consequence=(
                "NO ANSWER (mechanical): no recovery search for this gap"
                if no_answer
                else f"recovery query = {query[:200]!r}"
            ),
        )
        return None if no_answer else query[:200]

    # ---- Sufficiency Layer B/C: model-assisted role nomination ------------------------------------

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        """Narrow evidence-grounded nomination: given ONLY already-verified candidate excerpts
        (one row per proposition_id, never a unit_id or a hidden requirement/child id) and one
        role's category_description, ask which excerpts name a SPECIFIC instance of that
        category, and return their exact supporting substrings. Never a verdict -- the caller
        (`sufficiency_mapping.nominate_with_model`) independently re-verifies literal grounding
        and admissibility before anything can become a `filled` role binding.

        `candidates`: `[{"proposition_id": str, "passage": str}, ...]`. Returns validated
        `[{"proposition_id": str, "exact_text": str}, ...]` -- may be empty, and may contain more
        than one entry when several excerpts (or several distinct mentions within them) qualify.
        """
        if not candidates:
            return []
        proposition_ids = [c["proposition_id"] for c in candidates]
        prompt = nomination_prompt(category_description=category_description, candidates=candidates)
        call = self._call(
            prompt=prompt,
            output_cap=_NOMINATION_OUTPUT_TOKENS,
            json_schema=nomination_schema(proposition_ids),
        )
        parsed = _extract_json(call.raw_text) if call.provider_ok else None
        nominations, valid = _validate_nominations(
            parsed, allowed_proposition_ids=set(proposition_ids), limit=_NOMINATION_MAX_ITEMS
        )
        used_fallback = not (call.provider_ok and valid)
        if used_fallback:
            nominations = []
        self._record(
            stage="17_sufficiency_nomination",
            task="nominate_sufficiency_role",
            prompt=prompt,
            input_text=f"[category] {category_description}\n[proposition_ids] {proposition_ids}",
            call=call,
            parsed=parsed,
            valid=valid,
            fallback_used=used_fallback,
            consequence=f"{len(nominations)} raw nominations",
        )
        return nominations


# ---- strict validators + deterministic fallbacks -------------------------------------------------


def _validate_subquestion_texts(payload: Any) -> tuple[list[str], bool]:
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        return [], False
    out: list[str] = []
    for item in payload[:12]:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("question") or item.get("text") or "").strip()
        else:
            continue
        if text:
            out.append(text[:600])
    return out, bool(out)


def _validate_requested_items(payload: Any) -> tuple[list[str], bool]:
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        return [], False
    out: list[str] = []
    for item in payload[:20]:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("requested") or item.get("text") or item.get("note") or "").strip()
        else:
            continue
        if text:
            out.append(text[:300])
    return out, bool(out)


def _validate_gate(payload: Any) -> tuple[dict, bool]:
    if not isinstance(payload, dict):
        return {"action": GATE_NO_ANSWER}, False
    action = payload.get("action")
    if not isinstance(action, str):
        return {"action": GATE_NO_ANSWER}, False
    action = action.strip().lower()
    if action not in _GATE_ACTIONS:
        return {"action": GATE_NO_ANSWER}, False
    return {"action": action}, True


def _validate_id_list(payload: Any, *, key: str, allowed: set[str], limit: int) -> tuple[list[str], bool]:
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        return [], False
    out: list[str] = []
    for value in payload[key]:
        item = str(value).strip()
        if item in allowed and item not in out:
            out.append(item)
        if len(out) >= limit:
            break
    return out, True


def _validate_claim(payload: Any) -> tuple[str | None, bool]:
    if not isinstance(payload, dict) or "claim" not in payload:
        return None, False
    value = payload.get("claim")
    if not isinstance(value, str):
        return None, False
    stripped = value.strip()
    if not stripped:
        return None, True  # explicit "no claim" (empty string), not a fallback
    return stripped[:800], True


def _validate_query(payload: Any) -> tuple[str, bool]:
    if not isinstance(payload, dict) or not isinstance(payload.get("query"), str):
        return "", False
    query = payload["query"].strip()
    return (query, bool(query))
