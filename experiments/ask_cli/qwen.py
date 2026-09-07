"""Managed-local Qwen task wrappers — the ONLY model-mediated intermediate work.

Every task: small + low-entropy prompt, tolerant JSON parse, strict validation, and — on any failure
(provider error, truncation, parse/validation failure) — a FROZEN deterministic fallback defined here
BEFORE the first run (never invented after seeing a poor result). Every call's raw state is preserved via
the TraceWriter so the postmortem can attribute a loss to Qwen. Qwen interprets/organizes; it never supplies
domain facts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.backend.llm.providers import ProviderError, complete
from experiments.ask_cli.trace import TraceWriter

_OBLIGATION_KINDS = {
    "brain_region",
    "brain_behavior_relation",
    "behavior",
    "brain_attitude_relation",
    "attitude_construct",
    "personality_trait",
    "instrument",
    "population_culture",
    "measurement_method",
    "intervention",
    "comparator",
    "outcome",
    "effectiveness",
}


def _extract_json(text: str):
    """First balanced JSON value (object or array) embedded in ``text`` (tolerates prose/code fences).

    Mirrors query_planner._extract_json_object but also accepts a top-level array — widens what can be READ
    without widening what is TRUSTED (every field is validated afterward)."""
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


@dataclass
class QwenTasks:
    config: object  # ManagedProviderConfig
    trace: TraceWriter

    def _call(self, *, stage: str, task: str, prompt: str) -> tuple[str, bool, str | None]:
        """Return (raw_text, ok, failure_reason). ``ok`` is False on provider error or truncation."""
        try:
            result = complete(self.config, prompt)
        except ProviderError as exc:
            return "", False, f"provider_error: {exc}"
        if getattr(result, "truncated", False):
            return result.text, False, "truncated_at_output_cap"
        return result.text, True, None

    # ---- Stage 1: interpretation -----------------------------------------------------------------
    def interpret(self, question: str) -> tuple[list[dict], bool]:
        prompt = (
            "You split a complex scholarly question into its distinct sub-questions, and for each list the "
            "specific requested fields. Do NOT answer the question or add domain knowledge. Return ONLY JSON: "
            '[{"subquestion_id":"s1","text":"...","obligations":[{"field_id":"s1-o1",'
            '"kind":"<one of: brain_region, brain_behavior_relation, behavior, brain_attitude_relation, '
            "attitude_construct, personality_trait, instrument, population_culture, measurement_method, "
            'intervention, comparator, outcome, effectiveness>","note":"short"}]}]. '
            "Question: " + question
        )
        raw, ok, reason = self._call(stage="01_interpret", task="interpret", prompt=prompt)
        subqs, valid = ([], False)
        if ok:
            subqs, valid = _validate_subquestions(_extract_json(raw))
        used_fallback = not (ok and valid)
        if used_fallback:
            subqs = _FROZEN_INTERPRET_FALLBACK(question)
        self.trace.qwen_call(
            stage="01_interpret",
            task="interpret",
            input_text=question,
            raw_output=raw,
            parse_ok=ok,
            validation_ok=valid,
            failure_reason=reason if ok else reason,
            deterministic_fallback_used=used_fallback,
            downstream_consequence="one whole-question subquestion, no obligations"
            if used_fallback
            else f"{len(subqs)} subquestions",
        )
        return subqs, used_fallback

    # ---- Stage 5: context-growth gate ------------------------------------------------------------
    def context_gate(self, *, packet_text: str, subquestion: str) -> dict:
        prompt = (
            "Judge one passage against one sub-question. Do NOT answer it or add knowledge. Return ONLY JSON: "
            '{"proposition_bearing":true|false,"answers_obligation":true|false,'
            '"grow":"none|before|after|both","dead_end":true|false}. '
            "A list of abbreviations or a bare heading is not proposition-bearing. If the passage refers to "
            "'these'/'this' without a resolvable referent, growing may help. "
            f"Sub-question: {subquestion}\nPassage: {packet_text}"
        )
        raw, ok, reason = self._call(stage="05_context_gate", task="context_gate", prompt=prompt)
        gate, valid = (dict(_FROZEN_GATE_FALLBACK), False)
        if ok:
            parsed = _extract_json(raw)
            g, valid = _validate_gate(parsed)
            if valid:
                gate = g
        used_fallback = not (ok and valid)
        self.trace.qwen_call(
            stage="05_context_gate",
            task="context_gate",
            input_text=f"[subq] {subquestion}\n[packet] {packet_text}",
            raw_output=raw,
            parse_ok=ok,
            validation_ok=valid,
            failure_reason=reason,
            deterministic_fallback_used=used_fallback,
            downstream_consequence=f"gate={gate}",
        )
        return gate

    # ---- Stage 6: proposition extraction ---------------------------------------------------------
    def extract_propositions(
        self, *, packet_chunks: list[dict], subquestion: str, obligations: list[dict]
    ) -> list[dict]:
        """``packet_chunks`` = [{chunk_id, text}]; ``obligations`` = [{field_id, kind, note}]. Returns raw
        proposition dicts (validated/verbatim-checked downstream). Qwen names the specific evidence-anchor
        chunk, an exact quote, and which requested field_ids the proposition covers."""
        packet_text = "\n\n".join(f"[chunk {c['chunk_id']}]\n{c['text']}" for c in packet_chunks)
        ob_text = "; ".join(f"{o['field_id']}={o['kind']}" for o in obligations) or "(none)"
        prompt = (
            "Using ONLY the supplied source text, extract atomic scientific propositions responsive to the "
            "sub-question. Do NOT add outside knowledge. For each, name the specific [chunk N] that contains "
            "the support, copy an EXACT verbatim substring of that chunk as the quote, and list which requested "
            "field_ids it covers (only from the provided list). Return ONLY JSON: "
            '[{"subject":"","relation":"","object":"","direction":"+|-|none|mixed","population":"",'
            '"measure":"","qualifier":"","obligation_ids":["..."],"evidence_anchor_chunk_id":N,'
            '"quote":"<verbatim substring>"}]. If nothing in the text is responsive, return []. '
            f"Requested fields: {ob_text}\nSub-question: {subquestion}\n\n{packet_text}"
        )
        raw, ok, reason = self._call(stage="06_extract", task="extract_propositions", prompt=prompt)
        allowed_obs = {o["field_id"] for o in obligations}
        props, valid = ([], False)
        if ok:
            props, valid = _validate_propositions(
                _extract_json(raw), {c["chunk_id"] for c in packet_chunks}, allowed_obs
            )
        used_fallback = not (ok and valid)  # frozen fallback is [] (no proposition)
        self.trace.qwen_call(
            stage="06_extract",
            task="extract_propositions",
            input_text=f"[subq] {subquestion}\n[chunks] {[c['chunk_id'] for c in packet_chunks]}",
            raw_output=raw,
            parse_ok=ok,
            validation_ok=valid,
            failure_reason=reason,
            deterministic_fallback_used=used_fallback,
            downstream_consequence=f"{len(props)} candidate propositions",
        )
        return props if not used_fallback else []

    # ---- Stage 10: recovery query phrasing -------------------------------------------------------
    def recovery_query(self, *, subquestion: str, obligation_kind: str, obligation_note: str) -> str:
        prompt = (
            "Produce a SHORT retrieval phrase (<=12 words, no punctuation, not a question) to find the "
            "missing requested field for this sub-question. Do NOT answer it. Return ONLY JSON: "
            '{"query":"..."}. '
            f"Sub-question: {subquestion}\nMissing field kind: {obligation_kind}\nNote: {obligation_note}"
        )
        raw, ok, reason = self._call(stage="10_recovery", task="recovery_query", prompt=prompt)
        query, valid = (f"{obligation_note} {obligation_kind}".strip(), False)  # frozen fallback
        if ok:
            parsed = _extract_json(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("query"), str) and parsed["query"].strip():
                query, valid = parsed["query"].strip()[:200], True
        used_fallback = not (ok and valid)
        self.trace.qwen_call(
            stage="10_recovery",
            task="recovery_query",
            input_text=f"[subq] {subquestion}\n[missing] {obligation_kind}: {obligation_note}",
            raw_output=raw,
            parse_ok=ok,
            validation_ok=valid,
            failure_reason=reason,
            deterministic_fallback_used=used_fallback,
            downstream_consequence=f"recovery query = {query!r}",
        )
        return query


# ---- validation + FROZEN fallbacks (defined before any run) --------------------------------------


def _validate_subquestions(payload: Any) -> tuple[list[dict], bool]:
    if not isinstance(payload, list) or not payload:
        return [], False
    out: list[dict] = []
    for i, item in enumerate(payload[:12]):
        if not isinstance(item, dict) or not str(item.get("text", "")).strip():
            continue
        sid = str(item.get("subquestion_id") or f"s{i + 1}")
        obligations = []
        raw_obs = item.get("obligations")
        if isinstance(raw_obs, list):
            for j, ob in enumerate(raw_obs[:20]):
                if not isinstance(ob, dict):
                    continue
                kind = str(ob.get("kind", "")).strip()
                if kind not in _OBLIGATION_KINDS:  # closed taxonomy — drop anything outside it
                    continue
                obligations.append(
                    {
                        "field_id": str(ob.get("field_id") or f"{sid}-o{j + 1}"),
                        "kind": kind,
                        "note": str(ob.get("note") or "")[:200],
                    }
                )
        out.append({"subquestion_id": sid, "text": str(item["text"]).strip()[:400], "obligations": obligations})
    return out, bool(out)


def _validate_gate(payload: Any) -> tuple[dict, bool]:
    if not isinstance(payload, dict):
        return dict(_FROZEN_GATE_FALLBACK), False
    grow = str(payload.get("grow", "none")).strip().lower()
    if grow not in {"none", "before", "after", "both"}:
        grow = "none"
    return (
        {
            "proposition_bearing": bool(payload.get("proposition_bearing", True)),
            "answers_obligation": bool(payload.get("answers_obligation", False)),
            "grow": grow,
            "dead_end": bool(payload.get("dead_end", False)),
        },
        True,
    )


def _validate_propositions(
    payload: Any, allowed_chunk_ids: set[int], allowed_obligations: set[str]
) -> tuple[list[dict], bool]:
    if not isinstance(payload, list):
        return [], False
    out: list[dict] = []
    for item in payload[:20]:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or "").strip()
        try:
            anchor = int(item.get("evidence_anchor_chunk_id"))
        except (TypeError, ValueError):
            continue
        if not quote or anchor not in allowed_chunk_ids:
            continue
        direction = str(item.get("direction", "none")).strip().lower()
        if direction not in {"+", "-", "none", "mixed"}:
            direction = "none"
        raw_obs = item.get("obligation_ids")
        obligation_ids = [str(o) for o in raw_obs if str(o) in allowed_obligations] if isinstance(raw_obs, list) else []
        out.append(
            {
                "subject": str(item.get("subject") or "")[:300],
                "relation": str(item.get("relation") or "")[:300],
                "object": str(item.get("object") or "")[:300],
                "direction": direction,
                "population": str(item.get("population") or "")[:200],
                "measure": str(item.get("measure") or "")[:200],
                "qualifier": str(item.get("qualifier") or "")[:200],
                "obligation_ids": obligation_ids,
                "evidence_anchor_chunk_id": anchor,
                "quote": quote[:600],
            }
        )
    return out, True  # an empty list is a valid (if unhelpful) result; the frozen no-op fallback is also []


def _FROZEN_INTERPRET_FALLBACK(question: str) -> list[dict]:
    """Honest degradation: one subquestion = the whole question, no obligations (→ mostly-unanswered coverage)."""
    return [{"subquestion_id": "s1", "text": question.strip()[:400], "obligations": []}]


_FROZEN_GATE_FALLBACK = {"proposition_bearing": True, "answers_obligation": False, "grow": "none", "dead_end": False}
