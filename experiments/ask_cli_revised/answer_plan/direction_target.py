"""Direction target classification for the answer layer (Phase 32 / I1b). Pure, deterministic, parser-free.

For one verbatim sentence, the operand surfaces it contains, and the requested sign, decide what the direction word
modifies:

- ``relation``: the direction belongs to the relational predicate that links two operands in this sentence
  (for example "alpha was negatively associated with beta", or "higher alpha predicted lower beta").
- ``operand``: the direction describes one operand, its valence or magnitude, identified by role
  (for example "alpha was associated with negative beta evaluations", or "beta scores were negative").
- ``unknown``: the target cannot be established deterministically, or the sentence is ambiguous. Fail closed.
- ``none``: no direction word of the requested sign is present.

A ``relation`` target is only a classification. Attaching it to a relation additionally requires a witnessed relation
(answer_plan.classify). Witnessing alone never makes a sign a relation direction.

Reuses the existing direction stems and stemmer (overview_evidence) and the existing correlational cue pattern. Adds no
domain vocabulary. The only additions are generic grammatical sets: copulas, comparatives, and clause boundaries.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised import overview_evidence as oe

RELATION_CUE = oe._CORRELATIONAL  # the existing "correlated / associated / related / linked / predicted" pattern
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_COPULA = frozenset({"was", "were", "is", "are", "be", "been", "being"})
_COMPARATIVE = frozenset(
    {"higher", "lower", "more", "less", "greater", "fewer", "larger", "smaller", "stronger", "weaker"}
)
_CLAUSE_BOUNDARY = re.compile(r",|;|\bbut\b|\band\b", re.IGNORECASE)


def _literal_sign(word: str) -> str | None:
    lowered = word.lower()
    if lowered.startswith("positiv"):
        return "positive"
    if lowered.startswith("negativ"):
        return "negative"
    return None


def _tokens(sentence: str) -> list[dict]:
    return [
        {"start": m.start(), "end": m.end(), "text": m.group(0), "lower": m.group(0).lower()}
        for m in _WORD.finditer(sentence)
    ]


def _occurrences(sentence: str, operands: dict[str, str]) -> list[dict]:
    found = []
    for role, surface in operands.items():
        if not surface:
            continue
        for match in re.finditer(re.escape(surface), sentence, re.IGNORECASE):
            found.append({"role": role, "start": match.start(), "end": match.end()})
    found.sort(key=lambda o: (o["start"], -(o["end"] - o["start"])))
    return found


def _relation_cue_between(sentence: str, low: int, high: int) -> bool:
    return bool(RELATION_CUE.search(sentence[low:high]))


def _attributive_role(token: dict, tokens: list[dict], occurrences: list[dict]) -> str | None:
    """The operand whose surface begins at the word immediately after the direction word."""
    index = tokens.index(token)
    if index + 1 >= len(tokens):
        return None
    following = tokens[index + 1]["start"]
    for occurrence in occurrences:
        if occurrence["start"] == following:
            return occurrence["role"]
    return None


def _predicative_role(sentence: str, token: dict, tokens: list[dict], occurrences: list[dict]) -> str | None:
    """A copula directly before the direction word, with an operand earlier in the same clause."""
    index = tokens.index(token)
    if index == 0 or tokens[index - 1]["lower"] not in _COPULA:
        return None
    clause_start = 0
    for boundary in _CLAUSE_BOUNDARY.finditer(sentence, 0, token["start"]):
        clause_start = boundary.end()
    inside = [o for o in occurrences if o["start"] >= clause_start and o["end"] <= token["start"]]
    return inside[-1]["role"] if inside else None


def _relation_bound(sentence: str, token: dict, tokens: list[dict]) -> bool:
    """The direction word sits directly next to a relational cue ("negatively associated", "correlated negatively")."""
    index = tokens.index(token)
    neighbours = []
    if index > 0:
        neighbours.append(tokens[index - 1]["text"])
    if index + 1 < len(tokens):
        neighbours.append(tokens[index + 1]["text"])
    return any(RELATION_CUE.fullmatch(word) or RELATION_CUE.match(word) for word in neighbours)


def classify_sentence(sentence: str, operands: dict[str, str], sign: str | None) -> dict:
    """Return {"target": relation|operand|unknown|none, "role": str|None, "reason": str} for one sentence."""
    tokens = _tokens(sentence)
    direction_tokens = [t for t in tokens if oe.stem(t["text"]) in oe.DIRECTION_STEMS]
    literal = {_literal_sign(t["text"]) for t in direction_tokens} - {None}
    if len(literal) > 1:
        return {"target": "unknown", "role": None, "reason": "conflicting_signs"}
    relevant = [t for t in direction_tokens if sign is None or _literal_sign(t["text"]) in (None, sign)]
    if not relevant:
        return {"target": "none", "role": None, "reason": "no_requested_direction_word"}

    occurrences = _occurrences(sentence, operands)
    roles_present = sorted({o["role"] for o in occurrences})
    resolved: dict[int, tuple[str, str | None]] = {}
    for token in relevant:
        key = token["start"]
        attributive = _attributive_role(token, tokens, occurrences)
        if attributive is not None and token["lower"] in _COMPARATIVE:
            # A comparative in front of an operand. Decided below: a pair across two operands is a relation; alone, it is
            # the magnitude of that operand.
            resolved[key] = ("comparative", attributive)
        elif _relation_bound(sentence, token, tokens):
            resolved[key] = ("relation", None)
        elif attributive is not None:
            resolved[key] = ("operand", attributive)
        else:
            predicative = _predicative_role(sentence, token, tokens, occurrences)
            resolved[key] = ("operand", predicative) if predicative is not None else ("unresolved", None)

    comparatives = [(t, resolved[t["start"]][1]) for t in relevant if resolved[t["start"]][0] == "comparative"]
    comparative_roles = {role for _, role in comparatives}
    paired = False
    if len(comparative_roles) >= 2:
        first, second = sorted((t["start"] for t, _ in comparatives))[:2]
        paired = _relation_cue_between(sentence, first, second)
    for t, role in comparatives:
        resolved[t["start"]] = ("relation", None) if paired else ("operand", role)

    kinds = {kind for kind, _ in resolved.values()}
    if "relation" in kinds:
        if "operand" in kinds or "unresolved" in kinds:
            return {"target": "unknown", "role": None, "reason": "mixed_targets"}
        if len(roles_present) < 2:
            return {"target": "unknown", "role": None, "reason": "relation_without_two_operands"}
        low = min(o["start"] for o in occurrences)
        high = max(o["end"] for o in occurrences)
        if not _relation_cue_between(sentence, low, high):
            return {"target": "unknown", "role": None, "reason": "relation_cue_not_between_operands"}
        return {"target": "relation", "role": None, "reason": "relational_predicate_targeted"}
    operand_roles = {role for kind, role in resolved.values() if kind == "operand"}
    if operand_roles:
        if "unresolved" in kinds or len(operand_roles) > 1:
            return {"target": "unknown", "role": None, "reason": "ambiguous_operand_target"}
        return {"target": "operand", "role": next(iter(operand_roles)), "reason": "operand_targeted"}
    # Nothing attaches the direction word to a relation or to an operand.
    if len(roles_present) == 1:
        # The only operand the sentence realises is the one the observation describes. This keeps the existing
        # attribution for single-operand sentences; the sign's grammatical object is not verified (see results).
        return {"target": "operand", "role": roles_present[0], "reason": "single_operand_sentence"}
    return {"target": "unknown", "role": None, "reason": "unbound_direction_word"}
