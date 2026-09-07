"""Bounded query planner for the Synthesize -> Ask broad path (inc 581).

A broad, multifaceted question ("synthesize the systems involved in X, covering A, B, C, and
other findings") retrieves terribly when embedded as ONE vector: the centroid is near nothing
specific, so every facet is under-retrieved and the generator produces broad claims the verifier
correctly rejects. This module decomposes such a question into a small, bounded set of facets, each
with one retrieval subquery, so the downstream faceted pipeline can retrieve per facet.

Two-stage routing, deliberately cheap for the common case:

* ``classify_breadth`` -- a pure, deterministic pre-gate. A clearly-narrow question never reaches
  the provider; it routes straight to today's single-query path (zero added provider calls). The
  bias is slightly generous toward escalation, because the downside of a false escalation is only
  one planner call that then falls back to narrow, whereas a false *non*-escalation silently
  reproduces the old failure.
* ``plan_query`` -- one provider-agnostic structured call (injected ``complete_fn``), parsed and
  **strictly validated**. Any parse/validation/timeout/`<MIN_FACETS`-facet outcome degrades to a
  narrow plan, so a planner failure can only ever land on today's behavior, never worse.

The planner decides *what to retrieve*. It never makes a claim true -- every claim still faces the
unchanged local verifier downstream.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Literal

# Provider-neutral signature of the injected completion callable: (config, prompt) -> result with a
# ``.text`` attribute (exactly what ``app.backend.llm.providers.complete`` returns). Kept as a plain
# Callable so tests inject a fake without importing any provider.
CompleteFn = Callable[[object, str], object]

MIN_FACETS = 3
MAX_FACETS = 6
_MAX_LABEL_CHARS = 80
_MAX_QUERY_CHARS = 200
_MIN_QUESTION_CHARS = 40

PLANNER_PROMPT_VERSION = "query-planner-v1"

# Breadth framing markers -- a question using any of these AND of some length is treated as broad.
_BREADTH_MARKERS = (
    "synthesi",  # synthesis / synthesize
    "overview",
    "systematic",
    "review of",
    "summarize the",
    "summarise the",
    "landscape",
    "what is known about",
    "state of the",
    "across studies",
    "in the literature",
    "in my library",
    "systems involved",
    "systems implicated",
    "and other",
    "and more",
    "structured account",
    "mixed, null",
    "role each",
    "relevant findings",
)


@dataclass(frozen=True)
class Facet:
    """One retrieval facet: a human-readable label and ONE retrieval subquery (embedding target)."""

    label: str
    query: str


@dataclass(frozen=True)
class QueryPlan:
    scope: Literal["narrow", "broad"]
    facets: tuple[Facet, ...] = field(default_factory=tuple)
    planner_used: bool = False

    @property
    def is_broad(self) -> bool:
        return self.scope == "broad" and len(self.facets) >= MIN_FACETS


NARROW = QueryPlan(scope="narrow", facets=(), planner_used=False)


def classify_breadth(question: str) -> bool:
    """Deterministic pre-gate: should this question escalate to the planner? (pure, no I/O)

    True == plausibly broad -> call the planner. False == clearly narrow -> existing fast path.
    """
    q = (question or "").strip()
    if len(q) < _MIN_QUESTION_CHARS:
        return False
    low = q.lower()
    has_marker = any(marker in low for marker in _BREADTH_MARKERS)
    # Enumeration proxy: a broad question tends to list several sub-topics ("A, B, C, and D").
    listiness = low.count(",") + len(re.findall(r"\band\b", low))
    return (has_marker and len(q) >= 60) or listiness >= 4


def _planner_prompt(question: str) -> str:
    return (
        "You decompose a scholarly literature-synthesis question into facets for evidence retrieval. "
        "Decide whether the question is NARROW (one focused lookup) or BROAD (asks about several "
        f"distinct sub-topics). If BROAD, list {MIN_FACETS} to {MAX_FACETS} facets. Each facet is a "
        "distinct sub-topic the user named or clearly implied, with a concise retrieval query: a short "
        "phrase optimized for semantic search over scientific papers (not a question). "
        'Return ONLY JSON of the exact form {"scope": "narrow" | "broad", "facets": '
        '[{"label": "short label", "query": "retrieval phrase"}]}. For narrow, return '
        '{"scope": "narrow", "facets": []}. Do NOT answer the question, invent facets the question '
        "does not imply, or add any prose outside the JSON. Question: " + (question or "").strip()
    )


def plan_query(question: str, *, config: object, complete_fn: CompleteFn) -> QueryPlan:
    """Route a question to a bounded ``QueryPlan``. Fails safe to ``NARROW`` on any problem.

    ``complete_fn`` is the provider-agnostic completion seam (``complete``); ``config`` is the active
    LLM config. Neither is imported here so the planner stays pure and unit-testable with a fake.
    """
    if not classify_breadth(question):
        return NARROW
    try:
        result = complete_fn(config, _planner_prompt(question))
        text = str(getattr(result, "text", "") or "")
        payload = _extract_json_object(text)
        return _plan_from_payload(payload)
    except Exception:
        # Any provider error, egress refusal, timeout, or malformed response -> today's behavior.
        return NARROW


def _plan_from_payload(payload: object) -> QueryPlan:
    if not isinstance(payload, dict):
        return NARROW
    scope = str(payload.get("scope", "")).strip().lower()
    if scope != "broad":
        return NARROW
    raw_facets = payload.get("facets")
    if not isinstance(raw_facets, list):
        return NARROW
    facets: list[Facet] = []
    seen: set[str] = set()
    for item in raw_facets:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()[:_MAX_LABEL_CHARS]
        query = str(item.get("query", "")).strip()[:_MAX_QUERY_CHARS]
        if not label or not query:
            continue
        norm = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
        if not norm or norm in seen:  # drop near-duplicate retrieval queries
            continue
        seen.add(norm)
        facets.append(Facet(label=label, query=query))
        if len(facets) >= MAX_FACETS:
            break
    if len(facets) < MIN_FACETS:
        return NARROW
    return QueryPlan(scope="broad", facets=tuple(facets), planner_used=True)


def _extract_json_object(text: str) -> object | None:
    """The first balanced JSON object embedded in ``text`` (tolerates prose/preamble/code fences).

    Small local models and occasionally cloud ones wrap JSON in commentary; a whole-string
    ``json.loads`` would discard the real answer. Callers validate every field afterward, so this
    widens what can be READ without widening what is TRUSTED.
    """
    if not text:
        return None
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text, index)
        except ValueError:
            continue
        if isinstance(payload, dict):
            return payload
    return None
