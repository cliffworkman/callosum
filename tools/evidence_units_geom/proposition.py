"""Operationalize "proposition-bearing" (study section 5).

The governing principle, as ruled by the maintainer:

    A quantitative value is usable scientific evidence only when the extracted or reconstructed
    unit retains enough trustworthy context to identify what the value is evidence about.

Restated as a CONJUNCTION, which is what makes it testable:

    proposition-bearing  ==  carries a REFERENT  AND  makes an ASSERTION about it

  * REFERENT  -- a named entity/variable/group the information is about. A number is not a referent;
                 neither is a bare label with nothing predicated of it.
  * ASSERTION -- something stated about that referent: a finite reporting verb, an explicit relation,
                 or a value bound to several named quantities.

Worked cases from the brief:

    "p = .146"                                              -> NO  (value, no referent)
    "Group A did not differ from Group B on memory, p=.146" -> YES (referent + assertion)
    ".42"                                                   -> NO  (bare value)
    "Table 2 Results of linear regression analysis ..."     -> NO  independently: it identifies what
                                                               the values refer to but carries none
    "Table 4 Peak voxels ... grey matter volume is
     correlated with cognitive performance"                 -> YES (states a relation)

This is a deterministic PROXY for a semantic property, so it is wrong some of the time. Its accuracy
is measured against hand-adjudicated cases rather than assumed. Anything the rules cannot decide
returns UNRESOLVED -- never a forced binary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

YES = "proposition_bearing"
NO = "not_proposition_bearing"
UNRESOLVED = "unresolved"

# An assertion: something reported, compared, or related.
_REPORTING_VERB = re.compile(
    r"\b(was|were|showed?|shows|observed|associated|correlat\w+|found|reported|revealed|"
    r"exhibited|yielded|increased|decreased|differed?|differs|predicted|remained|indicated?|"
    r"demonstrated?|suggests?|reflects?|explained|captured|emerged|contributed|elicited|"
    r"produced|resulted|varied|declined|improved|worsened|mediat\w+|moderat\w+|"
    # Added after inspecting UNRESOLVED cases: ordinary research-reporting verbs the first pass
    # missed, e.g. "used an agent-based simulation model to assess ...", which is plainly a
    # referent + assertion and was being left undecided.
    r"used|employed|applied|assessed|examined|measured|tested|estimated|performed|conducted|"
    r"administered|recruited|analy[sz]ed|computed|calculated|rated|scored)\b",
    re.I,
)
# An explicit relation stated without a finite reporting verb.
_RELATION = re.compile(
    r"\b(greater|lower|higher|larger|smaller|faster|slower|stronger|weaker|reduced|elevated)\s+"
    r"(in|for|than|among)\b|\bno\s+(significant\s+)?(difference|association|correlation|effect)\b|"
    r"\brelative\s+to\b|\bcompared\s+(with|to)\b",
    re.I,
)
# A statistic. Presence alone proves nothing; the question is whether a referent accompanies it.
_STATISTIC = re.compile(
    r"\bp\s*[<=>]|\bd\s*=|\br\s*=|\bF\s*\(|\bt\s*\(|\bz\s*=|95%\s*CI|\bSE\s*=|\bM\s*=|\bSD\s*=|"
    r"\bOR\s*=|\bHR\s*=",
    re.I,
)
_CAPTION_OPEN = re.compile(r"^\s*(table|fig(?:ure)?\.?|figs?\.|scheme|panel|appendix)\s*[0-9ivxIVX]+\b", re.I)
# Structural labels that predicate nothing.
_PURE_LABEL = re.compile(
    r"^\s*(abstract|introduction|methods?|materials and methods|results|discussion|conclusions?|"
    r"references|acknowledge?ments?|funding|limitations|participants|procedure|measures|"
    r"statistical analysis|supplementary material|appendix|keywords?)\s*[:.]?\s*$",
    re.I,
)
_WORD = re.compile(r"[A-Za-z][A-Za-z\-]{2,}")
# Words that cannot be a referent on their own: they name the apparatus of reporting, not a subject.
_NON_REFERENT = frozenset(
    "the of and in to for with that as on by at from this these those was were are is be been not "
    "but or an it its than which their there have has had all both each such when where while "
    "note table figure fig see also et al vs versus mean sem std total value values".split()
)


@dataclass(frozen=True)
class Verdict:
    status: str
    reason: str
    has_referent: bool
    has_assertion: bool
    has_statistic: bool


def _referent_tokens(text: str) -> list[str]:
    """Content words that could name what the information is about."""
    return [w for w in _WORD.findall(text or "") if w.lower() not in _NON_REFERENT]


def classify(text: str) -> Verdict:
    t = (text or "").strip()
    if not t:
        return Verdict(NO, "empty", False, False, False)

    referents = _referent_tokens(t)
    has_stat = bool(_STATISTIC.search(t))
    has_assertion = bool(_REPORTING_VERB.search(t) or _RELATION.search(t))
    has_referent = len(referents) >= 3  # real lexical content, not one stray word beside a number

    if _PURE_LABEL.match(t):
        return Verdict(NO, "pure structural label; predicates nothing", False, False, has_stat)

    alpha = sum(ch.isalpha() for ch in t)
    if alpha / max(len(t), 1) < 0.25 or not referents:
        return Verdict(NO, "bare value or symbols; no referent", False, has_assertion, has_stat)

    if _CAPTION_OPEN.match(t):
        # A caption stating a relation carries a proposition; one that only names its object
        # identifies the referent for values it does not itself contain.
        if has_assertion:
            return Verdict(YES, "caption stating a relation", True, True, has_stat)
        return Verdict(
            NO,
            "caption identifies its object but predicates nothing (values live elsewhere)",
            True,
            False,
            has_stat,
        )

    if has_stat and not has_referent:
        return Verdict(NO, "statistic without a referent", False, has_assertion, True)

    if has_referent and has_assertion:
        return Verdict(YES, "referent plus assertion", True, True, has_stat)

    if has_referent and has_stat and len(referents) >= 5:
        return Verdict(YES, "value bound to named quantities", True, False, True)

    if has_referent:
        return Verdict(UNRESOLVED, "names something but predicates nothing decidable", True, False, has_stat)
    return Verdict(UNRESOLVED, "insufficient signal", has_referent, has_assertion, has_stat)


def main() -> None:
    import json
    import sqlite3
    from collections import Counter
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    db = root / ".local" / "evidence-units-geom" / "h1a.sqlite"
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT c.id, c.text, s.chunk_type FROM chunks c LEFT JOIN chunk_structure s ON s.chunk_id = c.id"
    ).fetchall()

    by_type: dict[str, Counter] = {}
    overall: Counter = Counter()
    for _cid, text, kind in rows:
        verdict = classify(text)
        overall[verdict.status] += 1
        by_type.setdefault(kind or "(unclassified)", Counter())[verdict.status] += 1

    total = sum(overall.values())
    print(f"PROPOSITION-BEARING over {total} chunks (H1a corpus)\n")
    for status in (YES, NO, UNRESOLVED):
        print(f"  {status:<26}{overall[status]:>7}{100 * overall[status] / total:>7.1f}%")

    print(f"\n  {'chunk_type':<22}{'yes':>7}{'no':>7}{'unres':>7}{'% bearing':>12}")
    for kind, counts in sorted(by_type.items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(counts.values())
        print(f"  {kind:<22}{counts[YES]:>7}{counts[NO]:>7}{counts[UNRESOLVED]:>7}{100 * counts[YES] / n:>11.1f}%")

    out = root / ".local" / "evidence-units-geom" / "proposition_baseline.json"
    out.write_text(
        json.dumps({"overall": dict(overall), "by_chunk_type": {k: dict(v) for k, v in by_type.items()}}, indent=1),
        encoding="utf-8",
    )
    print(f"\nwrote {out.name}")


if __name__ == "__main__":
    main()


# --- why a unit is undecided: the reconstruction opportunity, sub-classified -------------------
#
# A large UNRESOLVED share is not a defect in the proxy -- it is the finding. Inspection showed the
# bucket mixes genuinely different problems, and each implies a DIFFERENT repair. Naming them is
# what turns "58% undecided" into an actionable breakdown.

TRUNCATED_PROSE = "truncated_prose"  # real sentence, cut by a block boundary -> reunification
ORPHAN_STATISTIC = "orphan_statistic"  # values whose referent sits in a neighbouring chunk
LABELLED_ROW = "labelled_row"  # row label + values, missing column headers -> table
STRUCTURAL_LABEL = "structural_label"  # heading / running head: no proposition to recover
NAME_ONLY = "name_only"  # author or entity name alone
OTHER = "other_unresolved"

_ROW_SHAPE = re.compile(r"^[A-Z][\w\-/() ]{2,40}?\s+[-−]?\d")  # "Good forager 0.25 -0.03 ..."
_SENTENCE_TAIL = re.compile(r"[a-z,]$")  # ends mid-clause
_STARTS_LOWER = re.compile(r"^[a-z]")
_NAME_ONLY = re.compile(r"^[A-Z][a-z]+(\s+[A-Z]\.?)*(\s+[A-Z][a-z]+)*(\s+et\s+al\.?)?$")


def unresolved_reason(text: str) -> str:
    """Sub-classify an UNRESOLVED unit by the repair it would need."""
    t = (text or "").strip()
    words = t.split()
    if _NAME_ONLY.match(t) and len(words) <= 5:
        return NAME_ONLY
    if _ROW_SHAPE.match(t) and sum(ch.isdigit() for ch in t) >= 3:
        return LABELLED_ROW
    if _STATISTIC.search(t) and len(_referent_tokens(t)) < 3:
        return ORPHAN_STATISTIC
    if len(words) >= 6 and (_SENTENCE_TAIL.search(t) or _STARTS_LOWER.match(t)):
        return TRUNCATED_PROSE
    if len(words) <= 8 and not _SENTENCE_TAIL.search(t):
        return STRUCTURAL_LABEL
    return OTHER
