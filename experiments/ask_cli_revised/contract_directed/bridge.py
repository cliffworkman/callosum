"""Conditional corpus bridge (R&D #4): author terminology from a seed paper, used ONLY to decide where to look next.

A bridge is permission to INSPECT a candidate, never permission to change the child contract or to treat related concepts as
equivalent. It is conditional, not mandatory: it triggers only when a content unit is still unresolved after the first pass and
recovery AND at least one independently responsive seed paper exists (a paper that closed a unit for some child in this run).
The one route available in this library is verbatim author wording: phrases from the seed's own title/abstract that are not
already in the unit's words (for example the authors write "dispositions" where the question says "personality traits").
Citation-context bridges are NOT available here (parsed references exist for 5 of 256 papers) and are reported as deferred.
Every phrase is verified verbatim in its source; the receipt records seeds, phrases, locators, scope and outcome. A bridge never
closes a unit: candidates found through it go through the ordinary localization, eligibility and closure like any other.
"""

from __future__ import annotations

import re

from app.backend.pdf_processing.extraction import canonical_text_contains
from experiments.ask_cli_revised.contract_directed import abstracts, coverage

BRIDGE_NEIGHBORHOODS = 3
TOP_PHRASES = 3
_STOP = frozenset(
    "a an and are as at be been by for from has have in is it its of on or that the their this to was were which with we our not can may more less than into these those such other between across among within about during after before over under using used".split()
)
SCOPE = "retrieval-only: permission to inspect a candidate paper; not an equivalence, not an answer obligation, never closes a unit"


def bridge_trigger(rows: list[dict], seed_paper_ids: list[int]) -> dict:
    unresolved = [r["unit_id"] for r in coverage.unresolved_content_rows(rows)]
    triggered = bool(unresolved) and bool(seed_paper_ids)
    reason = (
        "triggered" if triggered else ("no_unresolved_unit" if not unresolved else "no_independently_responsive_seed")
    )
    return {
        "triggered": triggered,
        "reason": reason,
        "unresolved_units": unresolved,
        "seed_paper_ids": list(seed_paper_ids),
    }


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z\-]+", text)


def candidate_phrases(source_text: str, unit_text: str) -> list[str]:
    """2-3 word phrases (verbatim from the source) containing at least one content word the unit's own wording lacks."""
    unit_words = {w.lower() for w in _tokens(unit_text)}
    words = _tokens(source_text)
    seen: dict[str, None] = {}
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            gram = words[i : i + n]
            lowered = [w.lower() for w in gram]
            if lowered[0] in _STOP or lowered[-1] in _STOP:
                continue
            new = [w for w in lowered if w not in _STOP and w not in unit_words]
            if not new:
                continue
            phrase = " ".join(gram)
            if canonical_text_contains(needle=phrase, haystack=source_text):
                seen.setdefault(phrase, None)
    return list(seen)


def harvest_phrases(seed: dict, unit_text: str, retriever, *, top_n: int = TOP_PHRASES) -> list[dict]:
    """Phrases from the seed's title + abstract, ranked by closeness to the unit's words (embedding cosine), each verified verbatim."""
    clean = abstracts.clean_abstract(seed.get("abstract"))
    sources = [("title", seed.get("title") or ""), ("abstract", clean)]
    candidates = [(src, p) for src, text in sources for p in candidate_phrases(text, unit_text) if text]
    if not candidates:
        return []
    unit_vec = retriever.encode(unit_text)
    vectors = retriever.model.encode_texts([p for _, p in candidates])
    ranked = sorted(
        (
            (sum(a * b for a, b in zip(unit_vec, v, strict=False)), src, p)
            for (src, p), v in zip(candidates, vectors, strict=True)
        ),
        key=lambda t: -t[0],
    )
    out, used = [], set()
    for score, src, phrase in ranked:
        if phrase.lower() in used or any(phrase.lower() in u or u in phrase.lower() for u in used):
            continue
        used.add(phrase.lower())
        text = seed.get("title") if src == "title" else clean
        out.append(
            {
                "phrase": phrase,
                "paper_id": seed["id"],
                "source": src,
                "verbatim_in_source": canonical_text_contains(needle=phrase, haystack=text or ""),
                "similarity_to_unit": round(float(score), 4),
            }
        )
        if len(out) >= top_n:
            break
    return out


def bridge_receipt(
    child_id: str, unit_id: str, trigger: dict, phrases: list[dict], neighborhoods: list[dict], outcome: str
) -> dict:
    return {
        "child_id": child_id,
        "unit_id": unit_id,
        "trigger": trigger,
        "seeds": trigger["seed_paper_ids"],
        "phrases": phrases,
        "probe_scope": SCOPE,
        "neighborhoods_found": [{"nbhd_id": n["nbhd_id"], "paper_id": n["paper_id"]} for n in neighborhoods],
        "outcome": outcome,
        "citation_context_bridge": "not_available: parsed references exist for 5 of 256 papers in this library",
        "contract_unchanged": True,
    }
