"""Deterministic screening of overview proposals against the source passages they cite.

This is SCREENING, not proof of semantic correctness. Every check is a lexical or local-model test that can only *withhold*
a proposed sentence; none can certify one. A sentence that passes is one these tests could not fault, and the exact cited
passage is always shown beside it so a reader can judge. The checks exist because the failure modes are known from the real
q_aib run: a claim that invented a direction and a population its passage never states, a passage-attached hedge ("might")
restated as a finding, and an actor/recipient reversal ("toward" rewritten as "in").

Each check returns short stable reason codes; a proposal with any reason is withheld (never shown as overview, never
dropped from the inspection record).
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised.supervisor_eval.scoring import corpus_absence_hits

SCREEN_VERSION = "overview-screen-v1"
MAX_SENTENCE_CHARS = 400
MIN_SENTENCE_CHARS = 15
MAX_UNIT_IDS = 3
MAX_BEARS_ON = 4
MAX_NOVEL_TERMS = 3
_NEGATION_WINDOW = 6

# "toward Y" names who is on the receiving end; "in/among/by Y" names where or by whom it is found. Swapping one family
# for the other on the same head word reverses actor and recipient.
RECIPIENT_PREPS = frozenset({"toward", "towards", "against", "to", "for"})
LOCUS_PREPS = frozenset({"in", "among", "by", "from", "on", "within"})
_ABSENCE_EXTRA = re.compile(r"\b(?:no|little|limited|insufficient)\s+(?:evidence|research|data|studies)\b", re.I)

# A trailing parenthetical containing ONLY comma-separated "U<digits>" tokens, immediately before at most one
# closing punctuation mark, at the very end of the text. Deliberately narrow (NLI_REPAIR_DESIGN.md Section 2):
# does not match a parenthetical containing prose (e.g. " (see above)"), one not at the end of the text (no
# real model output has ever placed one mid-sentence), or one mixing a unit token with other content
# (e.g. " (U1, p. 4)") -- those simply don't "purport to be a unit citation" by this narrow shape and are left
# alone, unflagged. A marker that DOES match this shape but disagrees with the proposal's own unit_ids is a
# different case (see `strip_redundant_unit_markers`): recognizable, but a known attribution mismatch.
_TRAILING_UNIT_MARKER = re.compile(r"\s*\((U\d+(?:,\s*U\d+)*)\)([.!?]?)\s*$")


def _content_stems(text: str) -> set[str]:
    return {oe.stem(w) for w in oe.words(text) if len(w) >= 4 and w not in oe._GLUE}


def _prep_pairs(text: str) -> dict[tuple[str, str], str]:
    """``{(head stem, preposition): head word as written}`` for each word directly followed by a role preposition."""
    toks = oe.words(text)
    return {
        (oe.stem(toks[i - 1]), toks[i]): toks[i - 1]
        for i in range(1, len(toks))
        if toks[i] in RECIPIENT_PREPS | LOCUS_PREPS and len(toks[i - 1]) >= 4 and toks[i - 1] not in oe._GLUE
    }


def _negated_windows(passage: str) -> list[set[str]]:
    toks = oe.words(passage)
    windows = []
    for i, tok in enumerate(toks):
        if oe.has_negation(tok):
            near = toks[max(0, i - _NEGATION_WINDOW) : i + _NEGATION_WINDOW + 1]
            windows.append({oe.stem(w) for w in near if len(w) >= 4 and w not in oe._GLUE and not oe.has_negation(w)})
    return windows


def is_absence_claim(text: str) -> bool:
    return bool(corpus_absence_hits(text) or oe._ABSENCE.search(text) or _ABSENCE_EXTRA.search(text))


def screen(proposal: dict, *, units: dict[str, dict], part_ids: set[str]) -> list[str]:
    """Reason codes for one proposal ({text, unit_ids, bears_on}); empty means the deterministic screen found no fault."""
    text, ids, tags = proposal.get("text"), proposal.get("unit_ids"), proposal.get("bears_on")
    if not isinstance(text, str) or not text.strip():
        return ["empty_text"]
    reasons: list[str] = []
    if len(text) > MAX_SENTENCE_CHARS:
        reasons.append("text_too_long")
    if len(text.strip()) < MIN_SENTENCE_CHARS:
        reasons.append("text_too_short")
    if (
        not isinstance(tags, list)
        or len(tags) > MAX_BEARS_ON
        or len(set(tags)) != len(tags)
        or any(t not in part_ids for t in tags)
    ):
        reasons.append("bad_bears_on")
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_UNIT_IDS or len(set(ids)) != len(ids):
        return reasons + ["bad_unit_id_list"]
    unknown = [i for i in ids if i not in units]
    if unknown:
        return reasons + [f"unknown_unit_id:{','.join(map(str, unknown))}"]

    # a recognizable trailing unit-citation marker that disagrees with the proposal's own structured unit_ids
    # is a known attribution mismatch -- never left eligible merely because it also wasn't stripped for NLI
    marker = strip_redundant_unit_markers(text, ids)
    if marker["conflict_reason"]:
        reasons.append(marker["conflict_reason"])

    cited = [units[i] for i in ids]
    joined = " ".join(u["passage"] for u in cited)

    # numbers and acronyms may not appear from nowhere. A structurally validated, redundant unit-citation
    # marker (e.g. " (U1)") is not scientific claim content -- checking it here would read the marker's own
    # digit as an invented number even after the citation boundary already separated it from the NLI
    # hypothesis. Reuse that SAME validated transformation, never a second, looser stripper:
    # `marker["nli_hypothesis_text"]` equals `text` unchanged whenever nothing was cleanly stripped (no
    # marker, or a conflicting one) -- a conflicting marker stays fully subject to this check, since its own
    # `conflict_reason` above already withholds it and an extra number flag on unverified text is harmless.
    for number in dict.fromkeys(n.rstrip(".,") for n in re.findall(r"\d[\d.,%]*", marker["nli_hypothesis_text"])):
        if number not in joined:
            reasons.append(f"number_not_in_passage:{number}")
    for acronym in dict.fromkeys(re.findall(r"\b[A-Z]{2,}\b", text)):
        if acronym not in joined:
            reasons.append(f"acronym_not_in_passage:{acronym}")

    # direction and causal force may not be added
    added_direction = oe.direction_stems(text) - oe.direction_stems(joined)
    if added_direction:
        shown = [w for w in oe.words(text) if oe.stem(w) in added_direction]
        reasons.append(f"direction_word_not_in_passage:{','.join(dict.fromkeys(shown))}")
    added_causal = oe.causal_stems(text) - oe.causal_stems(joined)
    if added_causal:
        reasons.append(f"causal_cue_not_in_passage:{','.join(sorted(added_causal))}")

    # hedges and nulls must be kept
    if all(u["flags"]["hedged"] for u in cited) and not oe.has_hedge(text):
        reasons.append("hedge_dropped")
    if oe.has_negation(text) and not oe.has_negation(joined):
        reasons.append("negation_introduced")
    elif not oe.has_negation(text):
        mine = _content_stems(text)
        if any(len(mine & window) >= 2 for u in cited for window in _negated_windows(u["passage"])):
            reasons.append("negation_dropped")

    # actor/recipient: a head word the passage attaches with one preposition family may not be re-attached with the other
    passage_pairs = _prep_pairs(joined)
    for (head, prep), surface in sorted(_prep_pairs(text).items()):
        theirs = {p for h, p in passage_pairs if h == head}
        if theirs and (head, prep) not in passage_pairs:
            if (prep in RECIPIENT_PREPS and theirs & LOCUS_PREPS) or (prep in LOCUS_PREPS and theirs & RECIPIENT_PREPS):
                reasons.append(f"preposition_shift:{surface}:{prep}!={'/'.join(sorted(theirs))}")

    # vocabulary the passages do not contain
    novel = oe.novel_terms(text, joined)
    if len(novel) > MAX_NOVEL_TERMS:
        reasons.append(f"too_many_novel_terms:{','.join(novel[:8])}")
    for pair in oe.lookalike_substitutions(text, joined):
        reasons.append(f"lookalike_substitution:{pair}")

    # repeated citations of one paper are not corroboration
    claimed = {w for w in oe.corroboration_words(text) if w not in {x.lower() for x in oe.corroboration_words(joined)}}
    if claimed and len({u["paper_id"] for u in cited}) < 2:
        reasons.append(f"corroboration_language_single_source:{','.join(sorted(claimed))}")

    # nothing about absence: another, deterministic section reports what this run did not find
    if is_absence_claim(text):
        reasons.append("absence_claim")
    return reasons


def strip_redundant_unit_markers(text: str, unit_ids: list[str]) -> dict:
    """Separates a redundant inline unit-citation marker (e.g. " (U1)", " (U2, U3)") from the text an NLI
    scorer should be given, WITHOUT ever modifying ``text`` itself. Strips a marker ONLY when its token set
    exactly equals ``unit_ids`` (no duplicate, missing, or foreign id) -- every other shape is left completely
    untouched. A marker that IS recognizable (matches the strict citation shape) but disagrees with
    ``unit_ids`` sets ``conflict_reason`` to a screen()-style reason code rather than guessing; a marker that
    was never recognizable in the first place (no parens, non-citation prose, not at the end of the text)
    leaves ``conflict_reason`` ``None`` -- it was never treated as purporting to be a citation at all.

    Motivating minimal pair (nli-boundary-diagnostic-001, pairs A/B): the SAME source-faithful c9 statement
    scored support=0.81 without a trailing " (U1)." and support=0.24 with it appended -- the exact substring
    this function separates from the scored hypothesis. See NLI_REPAIR_DESIGN.md Section 2.

    Returns a dict: ``nli_hypothesis_text`` (what a scorer should be given -- == ``text`` unless cleanly
    stripped), ``raw_text`` (always the untouched input), ``stripped_marker`` (the exact removed substring, or
    None), ``marker_outcome`` (``"none"`` / ``"stripped_matches_unit_ids"`` / ``"conflicts_with_unit_ids"``),
    ``conflict_reason`` (a ready-to-use reason string, or None).
    """
    match = _TRAILING_UNIT_MARKER.search(text)
    if match is None:
        return {
            "nli_hypothesis_text": text,
            "raw_text": text,
            "stripped_marker": None,
            "marker_outcome": "none",
            "conflict_reason": None,
        }
    marker_ids = [tok.strip() for tok in match.group(1).split(",")]
    if len(marker_ids) != len(set(marker_ids)) or set(marker_ids) != set(unit_ids):
        return {
            "nli_hypothesis_text": text,
            "raw_text": text,
            "stripped_marker": None,
            "marker_outcome": "conflicts_with_unit_ids",
            "conflict_reason": f"unit_marker_conflicts_with_unit_ids:{','.join(marker_ids)}!={','.join(unit_ids)}",
        }
    trailing_punct = match.group(2) or ""
    stripped_span = match.group(0)
    removed = stripped_span[: len(stripped_span) - len(trailing_punct)] if trailing_punct else stripped_span
    return {
        "nli_hypothesis_text": text[: match.start()] + trailing_punct,
        "raw_text": text,
        "stripped_marker": removed,
        "marker_outcome": "stripped_matches_unit_ids",
        "conflict_reason": None,
    }


def nli_pair(proposal: dict, units: dict[str, dict], *, hypothesis_text: str | None = None) -> tuple[str, str]:
    """``(premise, hypothesis)`` in the order ``support_and_contradiction_many`` takes: passage first.

    ``hypothesis_text``, when given, overrides ``proposal["text"]`` as the hypothesis -- used to submit a
    citation-marker-stripped hypothesis while ``proposal["text"]`` itself is never touched. Omitting it (every
    existing caller) reproduces today's exact behavior."""
    premise = " ".join(units[i]["passage"] for i in proposal["unit_ids"])
    hypothesis = proposal["text"] if hypothesis_text is None else hypothesis_text
    return premise, hypothesis


def nli_reasons(support: float | None, contradiction: float | None, config=None) -> list[str]:
    """Reason codes from the local NLI scores. ``contradiction is None`` means the embedding fallback ran, which cannot
    tell entailment from mere topical overlap, so it fails closed."""
    from app.backend.summarization.verification import VerificationConfig

    config = config or VerificationConfig()
    if support is None or contradiction is None:
        return ["nli_unavailable"]
    if contradiction >= config.contradiction_threshold and contradiction > support:
        return [f"nli_contradicted:{contradiction:.2f}"]
    if support < config.support_threshold:
        return [f"nli_low_support:{support:.2f}"]
    return []
