"""Advisory checks on a raw child answer. They NEVER gate, alter or hide the answer: the raw text is saved before this runs.

Each check targets a failure observed in the baseline answers: a citation to a passage that was not given; an acronym expansion
that appears in no passage ("EBQ" expanded as "Empathy Bias Questionnaire" when the source says "Explicit Bias Questionnaire");
a direction the cited text never states ("a reduction in prosociality" citing a passage that only says "affecting prosociality");
one sentence resting on several passages (a relationship assembled across bundles); and leakage of the parent question, a
sibling's wording or a machine-written claim into the prompt. Results are labelled `advisory`; a flag is a prompt for review.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.contract_directed import links

_CITATION = re.compile(r"\[(P\d+(?:\s*,\s*P\d+)*)\]")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")
_PAREN_EXPANSION = re.compile(r"\b([A-Z]{2,6})\s*\(([A-Za-z][A-Za-z \-]{4,70})\)")
_DIRECTIONAL = re.compile(
    r"\b(less|more|reduc\w*|increas\w*|decreas\w*|lower\w*|higher|greater|fewer|stronger|weaker|declin\w*|improv\w*|"
    r"negative\w*|positive\w*)\b",
    re.IGNORECASE,
)
_DIRECTIONAL_ROOTS = (
    "less",
    "more",
    "reduc",
    "increas",
    "decreas",
    "lower",
    "higher",
    "greater",
    "fewer",
    "stronger",
    "weaker",
    "declin",
    "improv",
    "negativ",
    "positiv",
)


def _root(word: str) -> str:
    lowered = word.lower()
    return next((r for r in _DIRECTIONAL_ROOTS if lowered.startswith(r)), lowered)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("-", " ")).strip().lower()


def cited_ids(text: str) -> list[str]:
    ids: list[str] = []
    for match in _CITATION.finditer(text):
        ids += [i.strip() for i in match.group(1).split(",")]
    return ids


def sentences_with_citations(raw: str) -> list[dict]:
    return [{"text": s.strip(), "cited": list(dict.fromkeys(cited_ids(s)))} for s in _SENTENCE.split(raw) if s.strip()]


def acronym_expansions_not_in_packets(raw: str, packet_text: str) -> list[dict]:
    """Acronym expansions the answer states that appear in none of the given passages."""
    pairs = list(links.definition_pairs(raw))
    for match in _PAREN_EXPANSION.finditer(raw):
        acronym, expansion = match.group(1), match.group(2).strip()
        initials = "".join(
            w[0] for w in re.findall(r"[A-Za-z]+", expansion) if w.lower() not in {"of", "the", "and", "for"}
        )
        if initials.lower() == acronym.lower():
            pairs.append((acronym, expansion))
    body = _norm(packet_text)
    flagged, seen = [], set()
    for acronym, expansion in pairs:
        key = (acronym.upper(), _norm(expansion))
        if key in seen:
            continue
        seen.add(key)
        if _norm(expansion) not in body:
            flagged.append({"acronym": acronym.upper(), "expansion_in_answer": expansion, "in_any_passage": False})
    return flagged


def directional_terms_not_in_cited(raw: str, packets_by_shown_id: dict[str, str]) -> list[dict]:
    """Sentences whose directional wording (less/more/reduction/...) does not occur in any passage they cite."""
    flagged = []
    for sentence in sentences_with_citations(raw):
        if not sentence["cited"]:
            continue
        roots = {_root(m.group(0)) for m in _DIRECTIONAL.finditer(sentence["text"])}
        cited_text = " ".join(packets_by_shown_id.get(i, "") for i in sentence["cited"]).lower()
        missing = sorted(r for r in roots if r not in cited_text)
        if missing:
            flagged.append(
                {
                    "sentence": sentence["text"][:240],
                    "directional_terms_absent_from_cited_text": missing,
                    "cited": sentence["cited"],
                }
            )
    return flagged


def answer_diagnostics(
    raw: str,
    *,
    prompt: str,
    id_map: dict[str, str],
    packet_texts: dict[str, str],
    parent_question: str,
    other_wordings: list[str],
    carried_scope: str | None = None,
) -> dict:
    """`packet_texts`: shown id ("P1") -> the full text shown for that packet. Advisory only."""
    cited = cited_ids(raw)
    unique = list(dict.fromkeys(cited))
    sentences = sentences_with_citations(raw)
    multi = [s for s in sentences if len(s["cited"]) >= 2]
    all_text = " ".join(packet_texts.values())
    return {
        "gating": False,
        "advisory": "these flags prompt review; they never change, hide or reject the raw answer",
        "cited_ids": unique,
        "invalid_cited_ids": [i for i in unique if i not in id_map],
        "packets_given_but_never_cited": [i for i in id_map if i not in unique],
        "answer_cites_nothing": not unique,
        "multi_packet_sentences": [{"sentence": s["text"][:240], "cited": s["cited"]} for s in multi],
        "acronym_expansions_not_in_any_passage": acronym_expansions_not_in_packets(raw, all_text),
        "directional_terms_not_in_cited_passages": directional_terms_not_in_cited(raw, packet_texts),
        "prompt_leakage": {
            "contains_parent_question": parent_question in prompt,
            "contains_other_child_wording": [w for w in other_wordings if w in prompt and w != carried_scope],
            "contains_machine_claim_marker": "Candidate claims" in prompt or "model_written_claim" in prompt,
        },
        "nli_support": "not_run",
    }
