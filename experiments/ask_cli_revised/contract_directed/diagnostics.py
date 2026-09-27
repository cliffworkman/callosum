"""Advisory checks on a raw child answer. They NEVER gate, alter or hide the answer: the raw text is saved before
this runs.

**Citation parsing (Cliff's correction, session 2026-09-27): built on the exact render-time map, not a re-derived
guess.** `answer.render_packet_prompt` is the only place that decides which part gets which letter — including that
a `linked_definition` part IS lettered like any other (a real citation such as `[P3(f)]` legitimately points at a
linked Methods definition). `letter_map` (threaded in from `pipeline.py`) is that exact map; every check below reads
it rather than re-deriving the indexing. Real formats this parses: `[P1]`, `[P1, P2]`, `[P2(d)]`, `[P3a]`, and a
letter range `[P1(a)-(d)]`.

Each check below targets a failure observed in the Gate 1 pilot answers, is advisory only (a flag is a prompt for
review, never a gate), and states its own false-positive limits in its docstring — a pattern match can be present
in a sentence that is, in fact, entirely well-supported.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.contract_directed import attribution as at
from experiments.ask_cli_revised.contract_directed import links

_CITATION_GROUP = re.compile(r"\[([^\[\]]+)\]")
_CITE_TOKEN = re.compile(r"^P(\d+)(?:\((?:([a-z])-\(?([a-z])\)?|([a-z]))\)|([a-z]))?$")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")
_PAREN_EXPANSION = re.compile(r"\b([A-Z]{2,6})\s*\(([A-Za-z][A-Za-z \-]{4,70})\)")
_CAUSAL_CONNECTOR = re.compile(
    r"\b(?:which in turn|thereby|leading to|as a result of|resulting in|thus causing|consequently)\b", re.IGNORECASE
)
_ABSOLUTE_TERMS = (
    "absent", "reversed", "always", "never", "universal", "entirely", "exclusively",
)  # fmt: skip
_DIRECTIONAL = re.compile(
    r"\b(less|more|reduc\w*|increas\w*|decreas\w*|lower\w*|higher|greater|fewer|stronger|weaker|declin\w*|improv\w*|"
    r"negative\w*|positive\w*)\b",
    re.IGNORECASE,
)
_DIRECTIONAL_ROOTS = (
    "less", "more", "reduc", "increas", "decreas", "lower", "higher", "greater", "fewer", "stronger", "weaker",
    "declin", "improv", "negativ", "positiv",
)  # fmt: skip
_NON_ESTABLISHED = frozenset({at.OTHER_STUDY, at.SPECULATION, at.MIXED, at.UNRESOLVED})


def _root(word: str, roots: tuple[str, ...]) -> str:
    lowered = word.lower()
    return next((r for r in roots if lowered.startswith(r)), lowered)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("-", " ")).strip().lower()


# ---- citation parsing: three distinct failure categories, not one flat "invalid" list --------------------------------------


def parse_citation_tokens(raw: str) -> list[dict]:
    """Every citation token found in `raw`: `{"shown_id": "P1", "letters": [...] | [], "malformed": bool}`.
    `letters` is `[]` when the token cites the whole packet (no sub-reference); a malformed token (doesn't parse
    as `P<digits>` optionally lettered/ranged) is recorded, never silently dropped."""
    out: list[dict] = []
    for group in _CITATION_GROUP.finditer(raw):
        for token in group.group(1).split(","):
            token = token.strip()
            if not token:
                continue
            m = _CITE_TOKEN.match(token)
            if not m:
                out.append({"shown_id": None, "letters": [], "malformed": True, "raw": token})
                continue
            num, range_start, range_end, single_paren, single_bare = m.groups()
            shown = f"P{num}"
            if range_start and range_end:
                letters = [chr(c) for c in range(ord(range_start), ord(range_end) + 1)]
            elif single_paren:
                letters = [single_paren]
            elif single_bare:
                letters = [single_bare]
            else:
                letters = []
            out.append({"shown_id": shown, "letters": letters, "malformed": False, "raw": token})
    return out


def cited_ids(text: str) -> list[str]:
    """Unique base shown ids (`P1`, `P2`, ...) cited anywhere in `text` — the existing external contract, now built
    on the real parser instead of a bare-`[Pn]`-only regex."""
    return list(dict.fromkeys(t["shown_id"] for t in parse_citation_tokens(text) if not t["malformed"]))


def sentences_with_citations(raw: str) -> list[dict]:
    return [{"text": s.strip(), "cited": cited_ids(s)} for s in _SENTENCE.split(raw) if s.strip()]


def _sentence_tokens(sentence_text: str) -> list[dict]:
    return [t for t in parse_citation_tokens(sentence_text) if not t["malformed"]]


def cited_part_text(letter_map: dict[str, dict], shown_id: str, letters: list[str], whole_packet_text: str) -> str:
    """The exact text a citation actually points at: the cited letters' own part text when letters are given
    (falling back to the whole packet when a letter doesn't resolve — never silently empty), or the whole packet
    when no letter was given."""
    parts_by_letter = letter_map.get(shown_id) or {}
    if not letters:
        return whole_packet_text
    texts = [parts_by_letter[c]["text"] for c in letters if c in parts_by_letter]
    return " ".join(texts) if texts else whole_packet_text


def invalid_and_wrong_citations(raw: str, id_map: dict[str, str], letter_map: dict[str, dict]) -> dict:
    """Distinguishes: malformed tokens; a nonexistent shown id (`Pn` not in `id_map`); and a nonexistent PART (a
    letter beyond that packet's actual lettered range — computed from `letter_map`, which counts every part
    including a `linked_definition` one, exactly as `answer.packet_block` renders it)."""
    malformed, nonexistent_id, nonexistent_part = [], [], []
    for t in parse_citation_tokens(raw):
        if t["malformed"]:
            malformed.append(t["raw"])
            continue
        if t["shown_id"] not in id_map:
            nonexistent_id.append(t["shown_id"])
            continue
        letters = letter_map.get(t["shown_id"]) or {}
        for letter in t["letters"]:
            if letter not in letters:
                nonexistent_part.append(f"{t['shown_id']}({letter})")
    return {
        "malformed_citations": sorted(set(malformed)),
        "cited_ids_not_given": sorted(set(nonexistent_id)),
        "cited_parts_that_do_not_exist": sorted(set(nonexistent_part)),
    }


# ---- fidelity checks: each states what it can establish, what it misses, and that it is advisory --------------------------


def acronym_expansions_not_in_packets(raw: str, packet_text: str) -> list[dict]:
    """Acronym expansions the answer states that appear in none of the given passages. Misses: an expansion that IS
    correct but phrased differently than the source (a paraphrase is not flagged, by design)."""
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


def directional_terms_not_in_cited(
    raw: str, id_map: dict[str, str], letter_map: dict[str, dict], packet_texts: dict[str, str]
) -> list[dict]:
    """Sentences whose directional wording (less/more/reduction/...) does not occur in the SPECIFIC cited part(s)
    (precise once a letter is given — Cliff's correction; falls back to the whole packet when no letter is given).
    Misses: a direction correctly paraphrased in words this check's fixed list doesn't cover."""
    flagged = []
    for sentence_text in (s.strip() for s in _SENTENCE.split(raw) if s.strip()):
        tokens = _sentence_tokens(sentence_text)
        if not tokens:
            continue
        roots = {_root(m.group(0), _DIRECTIONAL_ROOTS) for m in _DIRECTIONAL.finditer(sentence_text)}
        if not roots:
            continue
        cited_text = " ".join(
            cited_part_text(letter_map, t["shown_id"], t["letters"], packet_texts.get(t["shown_id"], ""))
            for t in tokens
        ).lower()
        missing = sorted(r for r in roots if r not in cited_text)
        if missing:
            flagged.append(
                {
                    "sentence": sentence_text[:240],
                    "directional_terms_absent_from_cited_text": missing,
                    "cited": sorted({t["shown_id"] for t in tokens}),
                }
            )
    return flagged


def absolute_terms_not_in_cited_passages(
    raw: str, letter_map: dict[str, dict], packet_texts: dict[str, str]
) -> list[dict]:
    """Sentences using an absolute/categorical term (`absent`, `reversed`, `always`, `never`, `universal`,
    `entirely`, `exclusively`) that does not appear in the specific cited part(s) — a general form of the c10-shaped
    over-generalization ("absent or reversed" stated more strongly than a source's own hedged wording). Misses: a
    genuinely absolute finding phrased with a synonym this fixed list doesn't cover."""
    flagged = []
    for sentence_text in (s.strip() for s in _SENTENCE.split(raw) if s.strip()):
        tokens = _sentence_tokens(sentence_text)
        if not tokens:
            continue
        lowered = sentence_text.lower()
        terms = [w for w in _ABSOLUTE_TERMS if re.search(rf"\b{w}\b", lowered)]
        if not terms:
            continue
        cited_text = " ".join(
            cited_part_text(letter_map, t["shown_id"], t["letters"], packet_texts.get(t["shown_id"], ""))
            for t in tokens
        ).lower()
        missing = [w for w in terms if w not in cited_text]
        if missing:
            flagged.append(
                {
                    "sentence": sentence_text[:240],
                    "absolute_terms_not_in_cited_text": missing,
                    "cited": sorted({t["shown_id"] for t in tokens}),
                }
            )
    return flagged


def causal_connector_phrases(raw: str) -> list[dict]:
    """Sentences containing a causal/mediational connector ("which in turn", "thereby", "leading to", ...) across
    cited facts. Cannot establish that a causal relationship is unsupported — a TRUE, well-written causal claim
    citing a passage that itself states the mechanism would also match this pattern. It is a prompt to check the
    actual source for whether IT states the causal link, never a verdict on its own."""
    flagged = []
    for sentence in sentences_with_citations(raw):
        if not sentence["cited"]:
            continue
        hits = [m.group(0) for m in _CAUSAL_CONNECTOR.finditer(sentence["text"])]
        if hits:
            flagged.append({"sentence": sentence["text"][:240], "causal_connectors": hits, "cited": sentence["cited"]})
    return flagged


def asserts_unhedged_from_non_established_provenance(
    raw: str, id_map: dict[str, str], letter_map: dict[str, dict], packets_by_shown_id: dict[str, dict]
) -> list[dict]:
    """A cited sentence with no hedge word of its own, where a cited part's ALREADY-COMPUTED attribution (from
    `packet["attribution"]`, clause-scoped — no new judgment invented here) is speculative/other-study/mixed/
    unresolved. Misses: a case where the answer's own surrounding prose already signals uncertainty in words this
    check's fixed hedge list doesn't cover."""
    flagged = []
    for sentence_text in (s.strip() for s in _SENTENCE.split(raw) if s.strip()):
        tokens = _sentence_tokens(sentence_text)
        if not tokens or at._HEDGE.search(sentence_text):
            continue
        for t in tokens:
            packet = packets_by_shown_id.get(t["shown_id"])
            if not packet:
                continue
            letters = letter_map.get(t["shown_id"]) or {}
            span_ids = [letters[c]["span_id"] for c in t["letters"] if c in letters] or [
                p["span_id"] for p in packet["parts"] if p["role"] not in ("linked_definition", "study_context")
            ]
            states = {packet.get("attribution", {}).get(sid, {}).get("state") for sid in span_ids}
            bad = states & _NON_ESTABLISHED
            if bad:
                flagged.append(
                    {"sentence": sentence_text[:240], "cited": t["shown_id"], "non_established_states": sorted(bad)}
                )
    return flagged


def instrument_pairing_not_in_cited_text(
    raw: str, letter_map: dict[str, dict], packet_texts: dict[str, str]
) -> list[dict]:
    """Generalizes the pilot's ad hoc instrument-check with NO hardcoded instrument names: extracts instrument-
    shaped phrases from the ANSWER itself (`links._INSTRUMENT`) and, for the sentence naming one, checks whether the
    cited part's own text contains that instrument name. Flags only when the instrument name itself is NOT
    corroborated by the citation — it does not attempt to verify the claimed construct (that needs semantic
    judgment this pattern match cannot make), so a wrong pairing with the right instrument name is not caught here."""
    flagged = []
    for sentence_text in (s.strip() for s in _SENTENCE.split(raw) if s.strip()):
        tokens = _sentence_tokens(sentence_text)
        if not tokens:
            continue
        instruments = [m.group(0).strip() for m in links._INSTRUMENT.finditer(sentence_text)]
        if not instruments:
            continue
        cited_text = " ".join(
            cited_part_text(letter_map, t["shown_id"], t["letters"], packet_texts.get(t["shown_id"], ""))
            for t in tokens
        )
        cited_norm = _norm(cited_text)
        missing = [name for name in instruments if _norm(name) not in cited_norm]
        if missing:
            flagged.append(
                {
                    "sentence": sentence_text[:240],
                    "instruments_not_in_cited_text": missing,
                    "cited": sorted({t["shown_id"] for t in tokens}),
                }
            )
    return flagged


def instruments_in_evidence_present_but_unnamed(raw: str, packet_texts: dict[str, str]) -> list[dict]:
    """The complement check: an instrument name verifiably present in the evidence GIVEN to the answerer but never
    named anywhere in the answer at all. Together with `instrument_pairing_not_in_cited_text`, this is what actually
    tests "do all N instrument-construct pairings survive" — catching omission as well as misattribution. Misses:
    an instrument the answer refers to only by a paraphrase or acronym this pattern match doesn't recognize as the
    same name."""
    named_in_answer = _norm(raw)
    seen: set[str] = set()
    flagged = []
    for shown, text in packet_texts.items():
        for m in links._INSTRUMENT.finditer(text):
            name = m.group(0).strip()
            key = _norm(name)
            if key in seen:
                continue
            seen.add(key)
            if key not in named_in_answer:
                flagged.append({"instrument": name, "present_in_evidence_shown_as": shown, "named_in_answer": False})
    return flagged


def multi_packet_sentences(raw: str) -> list[dict]:
    """Sentences resting on more than one PACKET id — a relationship possibly assembled across separately-sourced
    bundles. Advisory: a sentence citing several packets can be entirely correct (a comparison across studies)."""
    return [
        {"sentence": s["text"][:240], "cited": s["cited"]}
        for s in sentences_with_citations(raw)
        if len(s["cited"]) >= 2
    ]


def multi_part_sentences(raw: str) -> list[dict]:
    """Sentences citing more than one DISTINCT LETTERED PART of the SAME packet (`[P5(a), P5(d)]`) — the shape that
    lets two different sub-findings of one paper (e.g. a behavioral experiment and a separate fMRI experiment) be
    merged into one claim. Invisible to `multi_packet_sentences`, which only counts distinct packet ids."""
    flagged = []
    for sentence_text in (s.strip() for s in _SENTENCE.split(raw) if s.strip()):
        by_packet: dict[str, set] = {}
        for t in _sentence_tokens(sentence_text):
            by_packet.setdefault(t["shown_id"], set()).update(t["letters"])
        multi = {pid: sorted(letters) for pid, letters in by_packet.items() if len(letters) >= 2}
        if multi:
            flagged.append({"sentence": sentence_text[:240], "multiple_parts_of_one_packet": multi})
    return flagged


def answer_diagnostics(
    raw: str,
    *,
    prompt: str,
    id_map: dict[str, str],
    letter_map: dict[str, dict],
    packets_by_shown_id: dict[str, dict],
    parent_question: str,
    other_wordings: list[str],
    carried_scope: str | None = None,
) -> dict:
    """`packets_by_shown_id`: shown id ("P1") -> the real packet dict (Cliff's correction: real packet objects, not
    pre-flattened text, so every check below can resolve the EXACT cited part). Advisory only."""
    packet_texts = {
        shown: " ".join(p["text"] for p in packet["parts"]) for shown, packet in packets_by_shown_id.items()
    }
    cited = cited_ids(raw)
    unique = list(dict.fromkeys(cited))
    invalid = invalid_and_wrong_citations(raw, id_map, letter_map)
    all_text = " ".join(packet_texts.values())
    return {
        "gating": False,
        "advisory": "these flags prompt review; they never change, hide or reject the raw answer",
        "cited_ids": unique,
        "invalid_cited_ids": invalid["cited_ids_not_given"],
        "malformed_citations": invalid["malformed_citations"],
        "cited_parts_that_do_not_exist": invalid["cited_parts_that_do_not_exist"],
        "packets_given_but_never_cited": [i for i in id_map if i not in unique],
        "answer_cites_nothing": not unique,
        "multi_packet_sentences": multi_packet_sentences(raw),
        "multi_part_sentences": multi_part_sentences(raw),
        "acronym_expansions_not_in_any_passage": acronym_expansions_not_in_packets(raw, all_text),
        "directional_terms_not_in_cited_passages": directional_terms_not_in_cited(
            raw, id_map, letter_map, packet_texts
        ),
        "absolute_terms_not_in_cited_passages": absolute_terms_not_in_cited_passages(raw, letter_map, packet_texts),
        "causal_connector_phrases": causal_connector_phrases(raw),
        "asserts_unhedged_from_non_established_provenance": asserts_unhedged_from_non_established_provenance(
            raw, id_map, letter_map, packets_by_shown_id
        ),
        "instrument_pairing_not_in_cited_text": instrument_pairing_not_in_cited_text(raw, letter_map, packet_texts),
        "instruments_in_evidence_present_but_unnamed": instruments_in_evidence_present_but_unnamed(raw, packet_texts),
        "prompt_leakage": {
            "contains_parent_question": parent_question in prompt,
            "contains_other_child_wording": [w for w in other_wordings if w in prompt and w != carried_scope],
            "contains_machine_claim_marker": "Candidate claims" in prompt or "model_written_claim" in prompt,
        },
        "nli_support": "not_run",
    }
