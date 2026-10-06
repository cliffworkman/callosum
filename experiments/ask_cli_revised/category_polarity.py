"""Phase 33 / I2-1: pure, deterministic observation-polarity classifier for one category-term occurrence.

Unwired by design. No production module imports this file: it has no runtime authority in I2-1 and no effect on
mapping, completion, recovery, terminality, cardinality, ParentClaims or AnswerPlan. It performs no I/O, no model
call, and no lookup of a sufficiency or plan version. It classifies ONE observation; aggregation across observations,
goal satisfaction and search terminality belong to I2-2 and I2-3.

Classification of a single term occurrence, in order:

1. A not-only / not-less / no-less construction, or two or more negation cues in the term clause -> unknown.
2. A negation cue plus a significance/effect complement cue within a small token window in the term clause -> null.
   A self-null adjective (non-significant) is itself a null cue.
3. A single negation cue without a complement: unknown if the clause carries a finding or directional cue,
   otherwise mentioned-only (procedural or mention negation).
4. No negation in the term clause: examine the immediately following clause. If it is negated and does not mention a
   competing term, a finding predicate in the term clause is carried over only through the narrow ellipsis pattern
   "... but not <one complement cue>" (null). Any other negated following clause -> unknown.
5. Otherwise a local finding or assertion predicate -> positive; no such predicate -> mentioned-only.

Sentence scope: only the sentence containing the occurrence is consulted, so negation in another sentence never
alters the result. Clause boundaries for polarity are commas, semicolons, colons and the contrastive connectives
listed in _BOUNDARY_RE; "and" is not a boundary. Hedges are reported and never change polarity. contrary_finding is
reserved and never returned.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.direction_target import split_sentences

CLASSIFIER_ID = "observation-polarity/i2-1"
POSITIVE = "positive_finding"
NULL = "null_finding"
MENTIONED = "mentioned_only"
UNKNOWN = "unknown"
CONTRARY_RESERVED = "contrary_finding"  # vocabulary reserved for a later semantic; never returned in I2-1

WINDOW = 3  # token distance between a negation cue and the complement cue it governs
# Words that break negation-complement attachment: a negation before a coordinator or relativiser does not govern
# a complement after it.
GOVERNANCE_BREAKERS = frozenset({"and", "or", "that", "which", "who"})
# Result-report structures for "found" (R5): "found that"/"found to" report a result; "<result noun> of|with|between|for
# <term> ... was found" reports a result when not followed by a locative. Bare "found" is never a finding cue.
RESULT_HEADS = frozenset(
    {
        "association",
        "associations",
        "evidence",
        "effect",
        "effects",
        "relationship",
        "relationships",
        "correlation",
        "correlations",
        "difference",
        "differences",
    }
)
RESULT_HEAD_LINKS = frozenset({"of", "with", "between", "for"})
LOCATIVES = frozenset(
    {"in", "at", "on", "within", "from", "among", "into", "inside", "under", "across", "throughout", "near", "by"}
)

NEGATION_CUES = frozenset(
    {"not", "no", "never", "neither", "nor", "without", "fail", "failed", "fails", "lack", "lacked", "lacks"}
)
SELF_NULL_CUES = frozenset({"non-significant", "nonsignificant"})
COMPLEMENT_CUES = frozenset(
    {
        "significant",
        "significantly",
        "significance",
        "effect",
        "effects",
        "association",
        "associations",
        "correlation",
        "correlations",
        "difference",
        "differences",
        "relationship",
        "relationships",
        "evidence",
    }
)
# Generic finding/assertion predicates: past, third-person present and base forms. Valence and magnitude words are not
# here; they are directional cues only (see DIRECTIONAL_CUES).
FINDING_CUES = frozenset(
    {
        "observed",
        "observe",
        "observes",
        "showed",
        "show",
        "shows",
        "shown",
        "demonstrated",
        "demonstrate",
        "demonstrates",
        "revealed",
        "reveal",
        "reveals",
        "expressed",
        "express",
        "expresses",
        "detected",
        "detect",
        "detects",
        "reported",
        "report",
        "reports",
        "correlated",
        "correlate",
        "correlates",
        "associated",
        "associate",
        "associates",
        "predicted",
        "predict",
        "predicts",
        "differed",
        "differ",
        "differs",
        "responded",
        "respond",
        "responds",
        "exhibited",
        "exhibit",
        "exhibits",
        "identified",
        "identify",
        "identifies",
        "produced",
        "produce",
        "produces",
        "reduced",
        "reduce",
        "reduces",
        "increased",
        "increase",
        "increases",
        "decreased",
        "decrease",
        "decreases",
        "improved",
        "improve",
        "improves",
        "affected",
        "affect",
        "affects",
        "influenced",
        "influence",
        "influences",
        "altered",
        "alter",
        "alters",
        "changed",
        "change",
        "changes",
        "lowered",
        "lowers",
        "raised",
        "raise",
        "raises",
    }
)
DIRECTIONAL_CUES = FINDING_CUES | frozenset(
    {"lower", "higher", "more", "less", "found", "find", "finds"}
)  # never a finding; directional only
MEASUREMENT_CUES = frozenset(
    {
        "measured",
        "measure",
        "measures",
        "assessed",
        "assess",
        "assesses",
        "included",
        "include",
        "includes",
        "recruited",
        "recruit",
        "recruits",
        "administered",
        "administer",
        "administers",
        "collected",
        "collect",
        "collects",
        "tested",
        "test",
        "tests",
        "used",
        "use",
        "uses",
        "examined",
        "examine",
        "examines",
        "reviewed",
        "review",
        "reviews",
        "described",
        "describe",
        "describes",
        "mentioned",
        "mention",
        "mentions",
    }
)
HEDGE_CUES = frozenset(
    {
        "may", "might", "could", "possibly", "perhaps", "probably", "likely",
        "suggest", "suggests", "suggested", "appear", "appears", "appeared",
        "seem", "seems", "seemed", "tentatively", "preliminarily",
    }
)  # fmt: skip

_BOUNDARY_RE = re.compile(r"[,;:]|\b(?:but|whereas|although|though|while|however|yet)\b", re.IGNORECASE)
ELLIPSIS_CONNECTIVES = frozenset({"but", "whereas", "although", "though", "yet"})
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_NOT_ONLY_PAIRS = frozenset({("not", "only"), ("not", "less"), ("no", "less")})
_ABSENCE_RE = re.compile(
    r"\b(?:no\s+(?:studies|study|research|evidence|data)"
    r"|(?:did|do|does|has|have)\s+not\s+(?:examine|investigate|test|assess|address|study|include|measure|evaluate|explore))\b",
    re.IGNORECASE,
)


def _words(text: str) -> list[str]:
    out = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0).lower()
        if token.endswith("n't"):
            token = "not"
        out.append(token)
    return out


def _clauses(sentence: str) -> list[dict]:
    """Clauses of one sentence. Each records its span, text, and the boundary words that precede it (empty segments
    between consecutive boundaries are merged into the following clause)."""
    clauses = []
    start = 0
    pending: list[str] = []
    for match in _BOUNDARY_RE.finditer(sentence):
        segment = sentence[start : match.start()]
        if segment.strip():
            lead = len(segment) - len(segment.lstrip())
            clauses.append(
                {
                    "start": start + lead,
                    "end": start + len(segment.rstrip()),
                    "text": segment.strip(),
                    "bounds": tuple(pending),
                }
            )
            pending = []
        pending.append(match.group(0).lower())
        start = match.end()
    tail = sentence[start:]
    if tail.strip():
        lead = len(tail) - len(tail.lstrip())
        clauses.append(
            {
                "start": start + lead,
                "end": start + len(tail.rstrip()),
                "text": tail.strip(),
                "bounds": tuple(pending),
            }
        )
    return clauses


def _finding_positions(words: list[str], cues: frozenset[str]) -> list[str]:
    """Cue words that count as finding or directional evidence. A cue directly after the infinitive marker "to" is a
    purpose or procedure, not an asserted result, and is excluded (fail closed)."""
    found = []
    for index, word in enumerate(words):
        infinitive = index > 0 and words[index - 1] == "to"
        # "found to <cue>" is a result complement, not a purpose: the cue after it is not procedural.
        result_complement = index > 1 and words[index - 2] == "found" and infinitive
        if word in cues and not (infinitive and not result_complement):
            found.append(word)
    return found


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0).lower(), m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]


def _result_found(words: list[str], term_first: int, term_last: int) -> bool:
    """Whether a "found" in this clause reports a result (R5). Structural only: "found that", "found to", or a
    result-noun head before the term, linked by of/with/between/for, with "found" after the term and not followed by
    a locative. Object-location and procedural uses ("found in the database", "found the questionnaire") do not match."""
    for i, word in enumerate(words):
        if word != "found":
            continue
        following = words[i + 1] if i + 1 < len(words) else None
        if following in {"that", "to"}:
            return True
        if i > term_last and (following is None or following not in LOCATIVES):
            for h in range(max(term_first - 1, 0)):
                if words[h] in RESULT_HEADS and words[h + 1] in RESULT_HEAD_LINKS and h + 1 < term_first:
                    return True
    return False


def _classify_occurrence(sentence: str, start: int, end: int, competing: tuple[str, ...], surface: str) -> dict:
    clauses = _clauses(sentence)
    clause_index = next((i for i, c in enumerate(clauses) if c["start"] <= start < c["end"]), None)
    record = {
        "matched_surface": surface,
        "sentence": sentence,
        "term_clause": None,
        "contrast_clause": None,
        "contrast_connective": [],
        "finding_cues": [],
        "null_cues": {"negation": [], "self_null": [], "complement": []},
        "directional_cues": [],
        "measurement_cues": [],
        "competing_terms_in_contrast": [],
        "hedge": bool(set(_words(sentence)) & HEDGE_CUES),
        "absence_statement": bool(_ABSENCE_RE.search(sentence)),
    }
    if clause_index is None or end > clauses[clause_index]["end"]:
        return {
            **record,
            "observation_polarity": UNKNOWN,
            "rule": "term_spans_clause_boundary",
            "ambiguity": "term_spans_clause_boundary",
        }

    term_clause = clauses[clause_index]
    words = _words(term_clause["text"])
    record["term_clause"] = term_clause["text"]
    negation = [i for i, w in enumerate(words) if w in NEGATION_CUES]
    self_null = [i for i, w in enumerate(words) if w in SELF_NULL_CUES]
    complement = [i for i, w in enumerate(words) if w in COMPLEMENT_CUES]
    spans = _token_spans(term_clause["text"])
    rel_start, rel_end = start - term_clause["start"], end - term_clause["start"]
    overlap = [k for k, (_, s0, s1) in enumerate(spans) if s0 < rel_end and s1 > rel_start]
    term_first, term_last = (overlap[0], overlap[-1]) if overlap else (0, 0)
    finding = _finding_positions(words, FINDING_CUES)
    if _result_found(words, term_first, term_last):
        finding = finding + ["found"]
    directional = _finding_positions(words, DIRECTIONAL_CUES)
    record["finding_cues"] = sorted(set(finding))
    record["directional_cues"] = sorted(set(directional))
    record["measurement_cues"] = sorted({w for w in words if w in MEASUREMENT_CUES})
    record["null_cues"] = {
        "negation": [words[i] for i in negation],
        "self_null": [words[i] for i in self_null],
        "complement": [words[i] for i in complement],
    }

    def decide(polarity: str, rule: str, ambiguity: str | None = None, **extra) -> dict:
        return {**record, "observation_polarity": polarity, "rule": rule, "ambiguity": ambiguity, **extra}

    for i in range(len(words) - 1):
        if (words[i], words[i + 1]) in _NOT_ONLY_PAIRS:
            return decide(UNKNOWN, "not_only_construction", "not_only_construction")
    if len(negation) + len(self_null) >= 2:
        return decide(UNKNOWN, "multiple_negation_cues", "multiple_negation_cues")
    if self_null and not negation:
        return decide(NULL, "self_null_adjective")
    if negation:
        i = negation[0]
        governed = any(
            i < j <= i + WINDOW and not any(w in GOVERNANCE_BREAKERS for w in words[i + 1 : j]) for j in complement
        )
        if governed:
            return decide(NULL, "local_null_same_clause")
        if finding or directional:
            return decide(
                UNKNOWN, "negation_without_significance_complement", "negation_without_significance_complement"
            )
        return decide(MENTIONED, "procedural_or_mention_negation")

    following = clauses[clause_index + 1] if clause_index + 1 < len(clauses) else None
    if following is not None:
        following_words = _words(following["text"])
        following_negated = any(w in NEGATION_CUES or w in SELF_NULL_CUES for w in following_words)
        attached = [c for c in competing if c.lower() in following["text"].lower()]
        if attached:
            record["competing_terms_in_contrast"] = sorted(attached)
        if following_negated and not attached:
            record["contrast_clause"] = following["text"]
            record["contrast_connective"] = list(following["bounds"])
            if finding:
                narrow = (
                    any(b in ELLIPSIS_CONNECTIVES for b in following["bounds"])
                    and following_words[:1] == ["not"]
                    and len(following_words) == 2
                    and following_words[1] in COMPLEMENT_CUES
                )
                if narrow:
                    return decide(NULL, "narrow_ellipsis_null")
                return decide(UNKNOWN, "unresolved_contrast_negation", "unresolved_contrast_negation")
            return decide(UNKNOWN, "unattached_contrast_negation", "unattached_contrast_negation")

    if finding:
        return decide(POSITIVE, "local_finding_predicate")
    return decide(MENTIONED, "no_finding_predicate")


def classify_category_observation(text: str, term: str, *, competing_terms: tuple[str, ...] = ()) -> dict:
    """Classify one observation of `term` in `text`. Pure and deterministic.

    `competing_terms`: explicit sibling category surfaces. A following negated clause that mentions one of them is
    attributed to that sibling, not to `term`. Omitted, no sibling is known and the carryover rule fails closed.

    Repeated occurrences (two or more in the text) are not resolved by choice: the result is unknown with
    rule `repeated_term_occurrence`, and each occurrence is reported in `occurrence_results`.
    """
    if not isinstance(text, str) or not isinstance(term, str):
        raise TypeError("text and term must be strings")
    surface_term = term.strip()
    if not surface_term:
        raise ValueError("term must be a non-empty string")
    competing = tuple(c.strip() for c in competing_terms if isinstance(c, str) and c.strip())

    sentences = split_sentences(text)
    occurrences = []
    for sentence in sentences:
        for match in re.finditer(re.escape(surface_term), sentence, flags=re.IGNORECASE):
            occurrences.append((sentence, match.start(), match.end(), match.group(0)))

    base = {
        "classifier": CLASSIFIER_ID,
        "term": surface_term,
        "competing_terms": sorted(set(competing)),
        "term_occurrences": len(occurrences),
    }
    if not occurrences:
        return {
            **base,
            "observation_polarity": UNKNOWN,
            "rule": "term_absent",
            "ambiguity": "term_absent",
            "matched_surface": None,
            "occurrence_results": [],
        }
    if len(occurrences) > 1:
        results = []
        for sentence, start, end, surface in occurrences:
            single = _classify_occurrence(sentence, start, end, competing, surface)
            results.append(
                {
                    "observation_polarity": single["observation_polarity"],
                    "rule": single["rule"],
                    "sentence": single["sentence"],
                    "term_clause": single["term_clause"],
                }
            )
        return {
            **base,
            "observation_polarity": UNKNOWN,
            "rule": "repeated_term_occurrence",
            "ambiguity": "repeated_term_occurrence",
            "matched_surface": None,
            "occurrence_results": results,
        }
    sentence, start, end, surface = occurrences[0]
    single = _classify_occurrence(sentence, start, end, competing, surface)
    return {**base, **single, "occurrence_results": []}
