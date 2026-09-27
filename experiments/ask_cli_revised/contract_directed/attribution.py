"""Who does a passage attribute a statement to? (own finding / another study / speculation / unresolved)

Section labels are provenance CLUES, not judgments: an Introduction can preview the present study's findings and a
Discussion can report them, while a Discussion or Introduction can equally recount another study. So attribution is
derived from what the sentence itself says, by explicit deterministic cues; the model's provenance label may only
*downgrade* (never upgrade) the result, and uncertainty is a first-class state that is preserved, never resolved by
guessing.

States: own_established | methods_own | other_study | speculation | mixed | unresolved.
A unit closes a first-hand-finding obligation only when its state is `own_established`.

Own-study bases (any one): an explicit first-person/this-study cue; reported test statistics; or a result statement
that also appears in the paper's OWN abstract (an authors' summary of their own work) and reports a result with no
contrary cue. `methods_own` is a *separate*, narrower state (Cliff's correction, session 2026-09-27): a Methods-
section sentence whose subject IS the instrument itself ("The IRI assessed …") legitimately describes what this
study measured without any first-person cue, but it must never be confused with `own_established` — closure.py
restricts exactly which slots may accept it (see `A1_A4_CORRECTION_DECISIONS.md`).

**Clause scoping (Cliff's correction, session 2026-09-27):** a span is not one verdict. `derive_attribution` no
longer promotes a whole multi-clause span to `own_established`/`methods_own` because ONE of its clauses qualifies —
the returned `state` is informational only (the clauses agree, or `mixed` when they don't); `closure.py` is the one
caller that reads `clauses` directly and decides, per listed span id and per slot, which *specific clause* actually
supports that slot. A factual clause can support a descriptive slot; it can never validate a relationship or
outcome asserted only in a different, speculative clause of the same sentence.
"""

from __future__ import annotations

import re

from app.backend.pdf_processing.extraction import canonical_text_contains

_FLAGS = re.IGNORECASE

_OWN_VERBS = (
    r"found|observed|show(?:ed|n)?|report(?:ed)?|test(?:ed)?|examined|measured|assess(?:ed)?|recruit(?:ed)?|present(?:ed)?|"
    r"ask(?:ed)?|conduct(?:ed)?|replicat(?:ed)?|identif(?:ied)?|demonstrat(?:ed)?|detect(?:ed)?|used|administer(?:ed)?|"
    r"collect(?:ed)?|compar(?:ed)?|analy[sz](?:ed)?|pool(?:ed)?|obtain(?:ed)?|record(?:ed)?|manipulat(?:ed)?|expos(?:ed)?|"
    r"describ(?:ed)?|confirm(?:ed)?|ran|performed|extend(?:ed)?|investigat(?:ed)?"
)
_OWN = [
    re.compile(rf"\bwe\s+(?:also\s+|further\s+|then\s+|first\s+|next\s+|thus\s+|now\s+)?(?:{_OWN_VERBS})\b", _FLAGS),
    re.compile(
        r"\b(?:this|the present|the current|present|current|our)\s+"
        r"(?:study|studies|research|paper|work|experiment|experiments|analysis|investigation|article|manuscript|"
        r"meta-analysis|review|sample|data|findings|results|participants)\b",
        _FLAGS,
    ),
    re.compile(
        r"\b(?:these|the)\s+(?:results|findings|data)\s+(?:suggest|show|indicate|demonstrate|reveal|confirm|provide)\b",
        _FLAGS,
    ),
    re.compile(r"\bparticipants\s+(?:\w+ed|were|had|did|made|chose|saw|rated|took|gave|held)\b", _FLAGS),
]
_INTERPRETATION = [
    re.compile(r"\bwe\s+(?:suggest|propose|speculate|hypothesi[sz]e|argue|believe|posit|conjecture|contend)\b", _FLAGS)
]
_PRIOR = [
    re.compile(
        r"\b(?:previous|prior|earlier|past|recent|existing|other)\s+"
        r"(?:studies|study|research|work|reports?|findings|literature|evidence|investigations?|papers|experiments)\b",
        _FLAGS,
    ),
    re.compile(
        r"\b(?:has|have)\s+(?:been\s+)?(?:shown|found|reported|demonstrated|suggested|documented|established)\b", _FLAGS
    ),
    re.compile(r"\b[A-Z][A-Za-z\-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z\-]+|\s+et\s+al\.?),?\s*\(?\d{4}[a-z]?\)?"),
    re.compile(r"\baccording to\b", _FLAGS),
    re.compile(r"\b(?:was|were)\s+(?:reported|shown|found|demonstrated)\s+(?:by|in)\b", _FLAGS),
]
_HEDGE = re.compile(
    r"\b(?:might|may|could|would|possibly|perhaps|potentially|should|hypothesi[sz]ed|theori[sz]ed|proposed|speculat\w*)\b",
    _FLAGS,
)
_STATISTICS = re.compile(
    r"(?:\b[pP]\s*[<=>≤≥]\s*\.?\d|\bβ\s*=|\b[tFrzZ]\s*(?:\(\d+(?:,\s*\d+)?\))?\s*=\s*[−\-–]?\d|\bSE\s*=\s*\d|"
    r"\bN\s*=\s*\d|\bn\s*=\s*\d|\bd\s*=\s*[−\-–]?\d|\bOR\s*=\s*\d|\bR2\s*=|\b\d+(?:\.\d+)?\s*%|\bCI\b)"
)
_RESULT_PREDICATE = re.compile(
    r"\b(?:correlated|demonstrated|showed|found|revealed|identified|replicated|chose|rated|expected|predicted|differed|"
    r"responded|exhibited|reported|detected|observed|increased|decreased|associated|were\s+(?:more|less|subjected)|"
    r"was\s+(?:greater|lower|higher|stronger|weaker|sensitive))\b",
    _FLAGS,
)

# Instrument-shaped noun phrase (mirrors links._INSTRUMENT so both modules share exactly one shape) + a measurement
# verb, either directly ("The IRI assessed X") or via a relative clause ("a Just World Beliefs Scale, which measures
# X"). Shared with deterministic_candidates.py (Task C) so there is exactly one pattern and one verb list.
INSTRUMENT_PHRASE = r"\b(?:[A-Z][\w\-]*\s+){1,4}(?:[Ss]cale|[Ii]ndex|[Qq]uestionnaire|Test|Game|Task|Inventory|Paradigm|Survey|Battery|Checklist|Interview)"
# no trailing \b: a citation superscript (e.g. "scale33") can be glued directly onto the suffix word with no
# word-boundary between them — INSTRUMENT_DESCRIBES' own optional `,?\d{0,3}` consumes that; the measurement verb
# at the end of INSTRUMENT_DESCRIBES still carries its own \b.
MEASUREMENT_VERBS = r"assess(?:ed|es)?|measur(?:ed|es)|quantif(?:ied|ies)|examin(?:ed|es)|captur(?:ed|es)|evaluat(?:ed|es)|index(?:ed|es)"
INSTRUMENT_DESCRIBES = re.compile(
    # An optional inline citation marker follows the instrument name directly (no space), e.g. "...Scale,31 which
    # measures..." — the comma comes before the superscript digits in this corpus's own extracted text.
    rf"(?:{INSTRUMENT_PHRASE})(?:\s*\([A-Z]{{2,7}}\))?,?\d{{0,3}}\s*(?:which\s+|that\s+)?"
    rf"(?:was\s+used\s+to\s+|were\s+used\s+to\s+)?(?:{MEASUREMENT_VERBS})\b",
    _FLAGS,
)
_INSTRUMENT_DESCRIBES = INSTRUMENT_DESCRIBES  # kept for any internal call site written against the old name

_LINE_WRAP_HYPHEN = re.compile(r"(\w)-\s+(\w)")


def dehyphenate_for_matching(text: str) -> str:
    """A copy of `text` with mid-word "line-wrap" hyphens ("mea- sures") collapsed, for PATTERN MATCHING only —
    never for the verbatim spans/offsets this module reports elsewhere, which are always the untouched original.
    This corpus's own extraction leaves a hyphen-plus-space exactly where a PDF line broke inside a word."""
    return _LINE_WRAP_HYPHEN.sub(r"\1\2", text)


OWN_ESTABLISHED = "own_established"
METHODS_OWN = "methods_own"
OTHER_STUDY = "other_study"
SPECULATION = "speculation"
MIXED = "mixed"
UNRESOLVED = "unresolved"
_OWN_LIKE = frozenset({OWN_ESTABLISHED, METHODS_OWN})

_MODEL_NON_OWN = frozenset({"recounts_other_study", "background_generic", "hypothesis_or_speculation"})

# Clause boundaries actually observed in this corpus: a semicolon, or a comma followed by a contrastive/hedging
# connective introducing a new clause ("evidence ... ; the byproduct hypothesis would predict ..." is the real,
# motivating case — a semicolon split). Offsets are exact; nothing here re-types source text.
_CLAUSE_BOUNDARY = re.compile(r";\s*|,\s+(?:but|whereas|although|while|however)\s+", _FLAGS)


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def split_clauses(text: str) -> list[tuple[int, int, str]]:
    """Exact (start, end, text[start:end]) clause spans. Never re-types text; a clause with no internal boundary is
    the whole string as one clause. A boundary INSIDE parentheses is never a split — a citation-style aside such as
    "(β = -1.002 ...; see Table S6)" is one clause, not a competing attribution claim."""
    spans: list[tuple[int, int, str]] = []
    start = 0
    depth = 0
    pos = 0
    for match in _CLAUSE_BOUNDARY.finditer(text):
        depth += text.count("(", pos, match.start()) - text.count(")", pos, match.start())
        pos = match.start()
        if depth > 0:
            continue
        s, e = _trim(text, start, match.start())
        if e > s:
            spans.append((s, e, text[s:e]))
        start = match.end()
    s, e = _trim(text, start, len(text))
    if e > s:
        spans.append((s, e, text[s:e]))
    return spans or ([(0, len(text), text)] if text else [])


def detect_cues(text: str) -> dict:
    """Explicit attribution cues found in `text` (each list holds the matched phrases, in order)."""
    return {
        "own": [m.group(0) for p in _OWN for m in p.finditer(text)],
        "own_interpretation": [m.group(0) for p in _INTERPRETATION for m in p.finditer(text)],
        "prior": [m.group(0) for p in _PRIOR for m in p.finditer(text)],
        "hedge": [m.group(0) for m in _HEDGE.finditer(text)],
    }


def has_statistics(text: str) -> bool:
    return bool(_STATISTICS.search(text))


def has_result_predicate(text: str) -> bool:
    """Whether `text` itself states a result/relation (`correlated`, `associated`, `predicted`, ...). Used to keep a
    clean-but-unrelated clause from validating a relationship or outcome asserted only elsewhere in the same span."""
    return bool(_RESULT_PREDICATE.search(text))


def in_abstract(text: str, abstract_clean: str | None) -> bool:
    if not abstract_clean or not text.strip():
        return False
    return canonical_text_contains(needle=text.strip(), haystack=abstract_clean)


def _clause_state(clause_text: str, *, abstract_clean: str | None, section: str | None) -> tuple[str, list[str], dict]:
    cues = detect_cues(clause_text)
    bases: list[str] = []
    if cues["own"]:
        bases.append("explicit_own_cue")
    if has_statistics(clause_text):
        bases.append("result_statistics")
    if in_abstract(clause_text, abstract_clean) and has_result_predicate(clause_text):
        bases.append("authors_abstract_result_statement")
    methods_basis = (
        section == "methods"
        and bool(INSTRUMENT_DESCRIBES.search(dehyphenate_for_matching(clause_text)))
        and not cues["prior"]
    )

    prior, hedge, interpretation = cues["prior"], cues["hedge"], cues["own_interpretation"]
    if bases and prior:
        state = MIXED
    elif prior:
        state = OTHER_STUDY
    elif interpretation and "result_statistics" not in bases:
        state = SPECULATION
    elif bases:
        state = OWN_ESTABLISHED
    elif methods_basis:
        bases.append("methods_instrument_description")
        state = METHODS_OWN
    elif hedge:
        state = SPECULATION
    else:
        state = UNRESOLVED
    return state, bases, cues


def derive_attribution_clauses(
    text: str, *, abstract_clean: str | None = None, section: str | None = None
) -> list[dict]:
    """Per-clause attribution, exact offsets. This — not the aggregate `state` below — is what closure.py reads."""
    out = []
    for start, end, clause_text in split_clauses(text):
        state, bases, cues = _clause_state(clause_text, abstract_clean=abstract_clean, section=section)
        out.append(
            {
                "start": start,
                "end": end,
                "text": clause_text,
                "state": state,
                "bases": bases,
                "cues": cues,
                "has_result_predicate": has_result_predicate(clause_text),
            }
        )
    return out


def derive_attribution(
    texts: list[str],
    *,
    abstract_clean: str | None = None,
    model_class: str | None = None,
    basis_phrase: str | None = None,
    section: str | None = None,
) -> dict:
    """Attribution of the statement carried by `texts` (the establishing units' display texts).

    `state` is informational only (agreeing clauses -> that state, disagreeing -> `mixed`); it is never what
    closure.py uses to accept or reject a span for a slot — that decision reads `clauses` directly, per Cliff's
    correction (session 2026-09-27): a whole span is never promoted to `own_established`/`methods_own` because one
    of its clauses qualifies. `section` is recorded only as an informational flag on each clause; it never changes
    a clause's state except by gating `methods_own` to Methods-section text.
    """
    joined = " ".join(t.strip() for t in texts if t.strip())
    clauses = derive_attribution_clauses(joined, abstract_clean=abstract_clean, section=section)
    # A model_class disagreement/refusal is evaluated against whichever clauses would otherwise be own-like; it may
    # only downgrade those clauses, never upgrade a different one.
    for clause in clauses:
        if clause["state"] in _OWN_LIKE and model_class in _MODEL_NON_OWN:
            clause["state"] = UNRESOLVED
            clause["flags"] = ["model_disagrees_with_cues"]
        else:
            clause["flags"] = []
        if clause["state"] in _OWN_LIKE and clause["cues"]["hedge"]:
            clause["flags"].append("hedged")
    states = {c["state"] for c in clauses}
    if len(states) <= 1:
        overall = next(iter(states), UNRESOLVED)
    elif states & _OWN_LIKE and states - _OWN_LIKE:
        overall = MIXED
    else:
        # No clause is own-like; report the first non-unresolved verdict found, else unresolved. This value is
        # informational only (see docstring) — nothing in closure.py's acceptance decision reads it.
        overall = next((c["state"] for c in clauses if c["state"] != UNRESOLVED), UNRESOLVED)

    flags: list[str] = sorted({f for c in clauses for f in c["flags"]})
    if basis_phrase and not canonical_text_contains(needle=basis_phrase, haystack=joined):
        flags.append("model_basis_phrase_not_in_text")
    if model_class == "this_study_reports" and overall not in _OWN_LIKE | {MIXED}:
        flags.append("model_upgrade_refused")
    if section == "introduction" and overall in _OWN_LIKE:
        flags.append("own_claim_in_introduction_preview")
    if section in {"results", "discussion"} and overall == OTHER_STUDY:
        flags.append("other_study_recital_in_" + section)

    return {
        "state": overall,
        "bases": sorted({b for c in clauses for b in c["bases"]}),
        "cues": {
            key: [m for c in clauses for m in c["cues"][key]] for key in ("own", "own_interpretation", "prior", "hedge")
        },
        "flags": flags,
        "model_class": model_class,
        "clauses": clauses,
    }
