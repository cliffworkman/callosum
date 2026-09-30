"""Overview evidence: deduplicated source passages ("units") built from a sealed ledger, with deterministic lexical flags.

Pure: no model, no I/O, no network. The sealed ledger is only read.

A *unit* is one exact source passage plus the ledger claims that restate it. The passage is the authority; a claim is a
machine-written restatement that can say more or less than its passage (the real q_aib ledger has 24 claims resting on 10
distinct passages, and one claim added a direction and a population its passage never states). Duplicate retrieval of
one passage is not corroboration, so units are keyed by passage, not by claim or by request item.

Everything here is a lexical screen over exact text. The flags are inspectable facts about a passage ("this passage
contains a hedge word"), never a judgment of what it means. They feed two things: which passages may be shown to the
overview model, and the deterministic sentence screen in ``overview_guards``.
"""

from __future__ import annotations

import difflib
import os
import re
import unicodedata

# ---- caps (recorded in the overview artifact; overflow is recorded, never silent) ---------------------------------------
MAX_UNITS = 12
MAX_PASSAGE_CHARS = 600
MAX_CLAIMS_SHOWN = 3
MAX_CLAIM_CHARS = 200

# ---- text normalization ----------------------------------------------------------------------------------------------
_TOKEN = re.compile(r"[A-Za-z][A-Za-z']*")
_LINEBREAK_HYPHEN = re.compile(r"(?<=\w)-\s+(?=\w)")
_REPLACEMENT_BREAK = re.compile(r"(?<=\w)�\s+(?=\w)")  # a lost hyphen at a line break, extracted as U+FFFD
_SOFT_BREAK = re.compile(r"(?<=\w)­\s*(?=\w)")  # the same break, extracted as a soft hyphen + space ("sen\xad sitivity")
_SUFFIXES = (
    "ations", "ation", "ities", "ity", "ings", "ing", "ness", "ally", "ly", "ions", "ion", "ies", "ied", "ers", "er",
    "ed", "es", "s", "ous", "ive", "ic", "al", "y", "e",
)  # fmt: skip


def _clean(text: str) -> str:
    text = _SOFT_BREAK.sub("", unicodedata.normalize("NFKC", text)).replace("­", "")
    return text.replace("’", "'")


def words(text: str) -> list[str]:
    """Lowercase alphabetic tokens; a line-break hyphen or a lost-hyphen replacement char joins the two halves."""
    text = _REPLACEMENT_BREAK.sub("", _clean(text))
    return [w.lower().strip("'") for w in _TOKEN.findall(_LINEBREAK_HYPHEN.sub("", text.replace("�", " ")))]


def passage_words(text: str) -> set[str]:
    """Every token a passage could be read as containing: joined and split readings of a hyphen at a line break."""
    cleaned = _clean(text).replace("�", " ")
    joined = {w.lower().strip("'") for w in _TOKEN.findall(_LINEBREAK_HYPHEN.sub("", cleaned))}
    split = {w.lower().strip("'") for w in _TOKEN.findall(cleaned)}
    return joined | split | set(words(text))


def stem(word: str) -> str:
    """A deliberately small suffix stripper. It only has to make two forms of one word agree, never to be linguistic."""
    word = word.lower().strip("'")
    if word.endswith("'s"):
        word = word[:-2]
    for _ in range(2):
        for suffix in _SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[: -len(suffix)]
                break
    return word


def stems(text: str) -> set[str]:
    return {stem(w) for w in passage_words(text)}


# ---- lexicons (closed, documented, individually tested) ---------------------------------------------------------------
_GLUE = frozenset(
    """
    that this these those with from into onto over under between among within without about across after before during
    through their there them they then than have been being were will would could should might must shall does done
    doing which while where when what whom whose also such each both other another same only very some much
    study paper papers research article work finding findings result results evidence report reports reported show shows
    shown showed found find finds suggest suggests suggested suggesting indicate indicates indicated participants
    participant people person individuals individual sample samples group groups overall generally appears appear
    seems seem likely possibly potentially perhaps probably
    """.split()
)
_HEDGE = re.compile(
    r"\b(?:might|may|could|would|possibly|potentially|perhaps|probably|likely|tentative(?:ly)?|preliminary|"
    r"suggest(?:s|ed|ing)?|appear(?:s|ed|ing)?|seem(?:s|ed|ing)?)\b",
    re.I,
)
_NEGATION = re.compile(
    r"\b(?:not|no|never|neither|nor|without|fail(?:s|ed|ure)?|lack(?:s|ed|ing)?|non-?significant)\b|n't\b", re.I
)
_CAUSAL = re.compile(
    r"\b(?:caus(?:e|es|ed|ing|al)|lead(?:s|ing)? to|led to|result(?:s|ed|ing)? in|because|due to|"
    r"(?:effects?|impact) (?:of|on)|effective(?:ly|ness)?|efficac(?:y|ious)|driv(?:e|es|en|ing)|"
    r"produc(?:e|es|ed|ing)|induc(?:e|es|ed|ing)|trigger(?:s|ed|ing)?|determin(?:e|es|ed|ing)|"
    r"mediat(?:e|es|ed|ing)|underpin(?:s|ned|ning)?|responsible for)\b",
    re.I,
)
_CORRELATIONAL = re.compile(
    r"\b(?:correlat\w*|associat\w*|relat(?:ed|ion|ionship|ions)|link(?:ed|s)|predict\w*)\b", re.I
)
_DIRECTION_WORDS = (
    "reduce reduced reduces reducing reduction less lower lowered decrease decreased decreases decline declined fewer "
    "weaker weaken diminish diminished more greater higher increase increased increases stronger strengthen enhance "
    "enhanced elevated improve improved improves worse worsen better positive negative attenuated heightened lessen boost"
).split()
DIRECTION_STEMS = frozenset(stem(w) for w in _DIRECTION_WORDS)
_CORROBORATION = re.compile(
    r"\b(?:several|multiple|numerous|consistent(?:ly)?|repeated(?:ly)?|replicat\w+|converg\w+|studies|papers|"
    r"literature|series of)\b",
    re.I,
)
_STUDY_SUBJECT = re.compile(
    r"\b(?:this|the present|the current|our)\s+(?:study|research|paper|work|article|review)\b", re.I
)
_STUDY_VERB = re.compile(
    r"\b(?:aimed|examined|investigated|explored|characteri[sz]ed|assessed|tested|sought|set out|"
    r"we\s+(?:examined|investigated|explored|assessed|tested|aimed|sought))\b",
    re.I,
)
_RESULT_CUE = re.compile(
    r"\b(?:found|showed|shows|show|revealed|reveals|demonstrated|correlat\w+|associat\w+|greater|less|higher|lower|"
    r"significant\w*|increas\w+|decreas\w+|confirm\w*|detect\w*|evidence|effect\w*|suggest\w*|indicat\w+|predict\w+|"
    r"were|was)\b",
    re.I,
)
_ABSENCE = re.compile(
    r"\b(?:(?:did|do|does|has|have)\s+not\s+(?:examine|investigate|test|assess|address|study|include|measure|evaluate|"
    r"explore)|no\s+(?:studies|study|evidence|research|data)\b|not\s+(?:been\s+)?(?:examined|investigated|tested|"
    r"studied|assessed))",
    re.I,
)
_TERMINAL = re.compile(r"""[.!?]["')\]”’]*\d{0,3}\s*$""")


def cue_stems(pattern: re.Pattern, text: str) -> set[str]:
    return {stem(m.group(0).split()[0]) for m in pattern.finditer(_clean(text))}


def has_hedge(text: str) -> bool:
    return bool(_HEDGE.search(_clean(text)))


def has_negation(text: str) -> bool:
    return bool(_NEGATION.search(_clean(text)))


def direction_stems(text: str) -> set[str]:
    return {stem(w) for w in words(text)} & DIRECTION_STEMS


def causal_stems(text: str) -> set[str]:
    return cue_stems(_CAUSAL, text)


def corroboration_words(text: str) -> set[str]:
    return {m.group(0).lower() for m in _CORROBORATION.finditer(_clean(text))}


def novel_terms(text: str, passage: str) -> list[str]:
    """Content words (4+ letters, not glue) of ``text`` whose stem is absent from ``passage``, in order of first use."""
    known = stems(passage)
    seen: list[str] = []
    for word in words(text):
        if len(word) >= 4 and word not in _GLUE and stem(word) not in known and word not in seen:
            seen.append(word)
    return seen


def lookalike_substitutions(text: str, passage: str) -> list[str]:
    """Novel words in ``text`` that are near-spellings of a DIFFERENT passage word: a substitution, not a paraphrase.

    "culturally shaped" for a passage's "culturally shared" adds one novel word, far below any vocabulary budget, and
    reverses the finding. Morphological variants of one word (correlated/correlation) share a stem prefix and are exempt.
    """
    candidates = sorted(w for w in passage_words(passage) if len(w) >= 5)
    found = []
    for word in novel_terms(text, passage):
        if len(word) < 5:
            continue
        mine = stem(word)
        for other in candidates:
            theirs = stem(other)
            if theirs == mine or len(os.path.commonprefix([mine, theirs])) >= 5:
                continue
            if difflib.SequenceMatcher(None, word, other).ratio() >= 0.8:
                found.append(f"{word}~{other}")
                break
    return found


# ---- passage flags ----------------------------------------------------------------------------------------------------
def passage_flags(passage: str) -> dict:
    text = _clean(passage)
    first = next((c for c in text if c.isalpha()), "")
    study = bool(_STUDY_SUBJECT.search(text) and _STUDY_VERB.search(text)) or bool(
        re.search(r"\bwe\s+(?:examined|investigated|explored|assessed|tested|aimed|sought)\b", text, re.I)
    )
    finding_cue = bool(_RESULT_CUE.search(_STUDY_VERB.sub("", text)))
    return {
        "hedged": has_hedge(text),
        "negated": has_negation(text),
        "fragment": not _TERMINAL.search(text),  # cut off: a qualification may be missing
        "starts_mid_sentence": bool(first) and first.islower(),
        "study_description": study and not finding_cue,
        "absence_statement": bool(_ABSENCE.search(text)),
        "causal_cues": sorted(
            {m.group(0).lower() for m in _CAUSAL.finditer(text)}
        ),  # the words as written, for the reader
        "correlational": bool(_CORRELATIONAL.search(text)),
    }


def eligibility(passage: str, flags: dict, *, attached: list[str], catalog_ok: bool) -> dict:
    reasons = []
    if not catalog_ok:
        reasons.append("catalog_mismatch")
    if not attached:
        reasons.append("no_coverage_attachment")
    if flags["fragment"]:
        reasons.append("truncated_passage")
    if flags["study_description"]:
        reasons.append("study_description_only")
    if flags["absence_statement"]:
        reasons.append("absence_statement")
    if len(passage) > MAX_PASSAGE_CHARS:
        reasons.append("passage_too_long")
    return {"eligible": not reasons, "reasons": reasons}


# ---- units ------------------------------------------------------------------------------------------------------------
def _dedupe_key(paper_id: int, passage: str) -> tuple:
    return (paper_id, " ".join(words(passage)))


def build_units(sealed: dict) -> tuple[list[dict], list[dict]]:
    """``(units, claims)`` from a sealed ledger, in order of first restating claim. The ledger is not modified.

    Attachments (``responsive_obligation_ids``) are recorded as the coverage authority's topical judgments. They are a
    necessary screen (a passage judged responsive to nothing is not offered) and never a limit on what a passage may be
    used for: the overview model sees every eligible passage, without knowing which request item it was attached to.
    """
    catalog = {(s["paper_id"], s["chunk_id"], s["span_id"]): s["text"] for s in sealed.get("evidence_spans", [])}
    by_key: dict[tuple, dict] = {}
    claims: list[dict] = []
    for row in sealed["verified_propositions"]:
        passage = row["quote"]
        loc = (row["paper_id"], row["evidence_anchor_chunk_id"], row["evidence_span_id"])
        key = _dedupe_key(row["paper_id"], passage)
        unit = by_key.get(key)
        if unit is None:
            unit = {
                "unit_id": f"U{len(by_key) + 1}",
                "number": len(by_key) + 1,
                "paper_id": row["paper_id"],
                "locators": [],
                "passage": passage,
                "proposition_ids": [],
                "attached_children": [],
                "verification": dict(row.get("verification") or {}),
                "_catalog_ok": True,
            }
            by_key[key] = unit
        # Stage A (plural evidence anchors): a continuation-joined row's locators include every real
        # anchor it spans, not just the primary -- a downstream citation can then name every real
        # chunk location, not just the one evidence_anchor_chunk_id happens to point at.
        anchor_locators = (
            [{"chunk_id": a["chunk_id"], "span_id": a["span_id"]} for a in row["anchors"]]
            if row.get("anchors")
            else [{"chunk_id": loc[1], "span_id": loc[2]}]
        )
        for locator in anchor_locators:
            if locator not in unit["locators"]:
                unit["locators"].append(locator)
        unit["proposition_ids"].append(row["proposition_id"])
        unit["attached_children"] = sorted(
            set(unit["attached_children"]) | set(row.get("responsive_obligation_ids", []))
        )
        unit["_catalog_ok"] = unit["_catalog_ok"] and catalog.get(loc) == passage
        claims.append(
            {
                "proposition_id": row["proposition_id"],
                "unit_id": unit["unit_id"],
                "text": row["proposition_text"],
                "novel_terms": novel_terms(row["proposition_text"], passage),
                "attached_children": list(row.get("responsive_obligation_ids", [])),
            }
        )
    units = []
    for unit in by_key.values():
        flags = passage_flags(unit["passage"])
        catalog_ok = unit.pop("_catalog_ok")
        unit["flags"] = flags
        unit["eligibility"] = eligibility(
            unit["passage"], flags, attached=unit["attached_children"], catalog_ok=catalog_ok
        )
        units.append(unit)
    return units, claims
