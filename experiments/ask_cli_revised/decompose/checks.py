"""Deterministic checks. Two different things, kept apart on purpose:

* VERIFIED TRACEABILITY: the cited words and offsets really exist, ids resolve, links point at real obligations. This
  is a fact about the artifact, and ``verify_traceability`` can certify it.
* DIAGNOSTICS (stem overlap, additions, lost cues, clause attachment, deixis, bundling suspicion): heuristics that raise
  flags. They are NOT evidence that a child preserves what the parent's words require. Nothing here, and nothing in
  the generator, certifies semantic fidelity; every artifact says ``semantic_fidelity: not_certified``.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.decompose import ledger, tree
from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose.parent import _LIST_SPLIT
from experiments.ask_cli_revised.request_contract import _sentence_spans

LEXICAL_SUPPORT_THRESHOLD = (
    0.6  # share of an obligation's content stems that must appear in a child to call it "preserved"
)
COMPOUND_COVERAGE = 0.9  # a child covering this much of another obligation's distinct words is suspected of bundling it
KINDS_WORDS = frozenset("kind kinds type types sort sorts form forms variety varieties which what".split())

_POLAR_START = {
    "do",
    "does",
    "did",
    "is",
    "are",
    "can",
    "could",
    "was",
    "were",
    "has",
    "have",
    "will",
    "would",
    "should",
}
_MANNER = {"how", "way", "ways", "manner", "mechanism", "mechanisms", "means", "method", "process"}
_CUE_EQUIV = {
    "how": _MANNER,
    "any": {"any", "some", "is", "are", "there"},
    "all": {"all", "every", "each", "which"},
    "each": {"each", "every", "all", "which"},
    "every": {"each", "every", "all", "which"},
}


def cue_preserved(cue_text: str, child_text: str) -> bool:
    words = [w for w in lx.tokens(cue_text) if w != "and"]
    child_tokens = lx.tokens(child_text)
    if words in (["whether"], ["if", "so"]):  # polar: the word, "if", or a polar question that STARTS with an auxiliary
        return (
            "whether" in child_tokens or "if" in child_tokens or bool(child_tokens and child_tokens[0] in _POLAR_START)
        )
    if len(words) == 1 and words[0] in _CUE_EQUIV:
        return bool(_CUE_EQUIV[words[0]] & set(child_tokens))
    return any(
        any(lx.stems_match(lx.stem(w), lx.stem(t)) for t in child_tokens)
        for w in words
        if len(w) > 3 or len(words) == 1
    )


def unsupported_additions(child_text: str, question_stems: list[str]) -> list[str]:
    return [t for t in lx.tokens(child_text) if lx.is_content_token(t) and not lx.has_stem(question_stems, lx.stem(t))]


def lexical_overlap(requirement_text: str, child_text: str) -> float:
    return round(lx.coverage_fraction(lx.content_stems(requirement_text), lx.content_stems(child_text)), 3)


def _norm(text: str) -> str:
    return " ".join(lx.tokens(text))


_WH = {"what", "which", "who", "whom", "whose", "when", "where", "why", "how"}


def _question_form(text: str) -> bool:
    toks = lx.tokens(text)
    return bool(toks) and (toks[0] in _POLAR_START or toks[0] in _WH)


def attachment(req: dict, holder: dict, text: str) -> dict:
    """DIAGNOSTIC: is a polarity ("whether") or manner ("how") obligation attached to the obligation it qualifies?

    Producing the word somewhere in the child is not enough. The clause that carries the qualified obligation's words
    must itself be the polar question (or contain "whether"/"if"), and "how" must sit in that clause or in the short
    clause that follows it ("..., and if so how")."""
    holder_stems = lx.content_stems(holder["text"])
    if not holder_stems:
        ok = cue_preserved("whether" if req["kind"] == "polarity" else "how", text)
        return {"preserved": ok, "method": "cue (holder has no content words)", "missing": [] if ok else [req["text"]]}
    clauses = [c.strip() for c in re.split(r"[,;:]", text) if c.strip()]
    idx = next(
        (
            i
            for i, c in enumerate(clauses)
            if lx.coverage_fraction(holder_stems, lx.content_stems(c)) >= LEXICAL_SUPPORT_THRESHOLD
        ),
        None,
    )
    if idx is None:
        return {
            "preserved": False,
            "method": "attachment to the qualified obligation's clause",
            "missing": [req["text"]],
            "note": f"the words of {holder['id']} are not together in one clause, so this cannot be attached to it",
        }
    toks = lx.tokens(clauses[idx])
    toks = toks[1:] if toks and toks[0] == "and" else toks
    if req["kind"] == "polarity":
        ok = "whether" in toks or "if" in toks or bool(toks and toks[0] in _POLAR_START)
    else:
        follow = lx.tokens(clauses[idx + 1]) if idx + 1 < len(clauses) else []
        ok = bool(_MANNER & set(toks)) or (len(follow) <= 5 and "how" in follow)
    return {
        "preserved": ok,
        "method": "attachment to the qualified obligation's clause",
        "missing": [] if ok else [req["text"]],
        "note": None if ok else f"the {req['kind']} marker is not in the clause that carries {holder['id']}",
    }


def obligation_preservation(req: dict, text: str, by_id: dict | None = None) -> dict:
    """DIAGNOSTIC: are this obligation's words still asked in the child? ``preserved`` is True/False/None (not assessable)."""
    kind, tokens = req["kind"], lx.tokens(text)
    holder = (by_id or {}).get(req.get("part_of") or "")
    if (
        kind in ("polarity", "manner")
        and holder is not None
        and holder["origin"] != "source_unit_floor"
        and holder["kind"] != "source_unit"
    ):
        return attachment(req, holder, text)
    if kind == "polarity" or kind == "existence":
        polar = cue_preserved("whether", text)
        stems_ok = kind == "polarity" or lexical_overlap(req["text"], text) >= LEXICAL_SUPPORT_THRESHOLD
        return {
            "preserved": polar and stems_ok,
            "method": "polar form + stems",
            "missing": [] if polar and stems_ok else [req["text"]],
        }
    if kind == "manner":
        ok = cue_preserved("how", text)
        return {"preserved": ok, "method": "manner cue", "missing": [] if ok else [req["text"]]}
    if req["origin"] == "deterministic_cue" and kind in ("qualifier", "operation"):
        ok = cue_preserved(req["text"], text)
        return {"preserved": ok, "method": "cue", "missing": [] if ok else [req["text"]]}
    missing = []
    assessed = False
    for a in req["anchors"]:
        if not a["span"]:
            continue
        stems = lx.content_stems(a["quote"])
        if not stems:
            continue
        assessed = True
        if lx.coverage_fraction(stems, lx.content_stems(text)) < LEXICAL_SUPPORT_THRESHOLD:
            missing.append(a["quote"])
    if kind == "kinds" and not (KINDS_WORDS & set(tokens)):
        assessed = True
        missing.append("(asks for kinds/types)")
    return {
        "preserved": (not missing) if assessed else None,
        "method": "endpoint stems (every quote must be covered)",
        "missing": missing,
    }


def reference_words_in(parent: dict, ids: list[str], by_id: dict) -> list[dict]:
    """Deterministic reference cues (they, its, this...) that fall inside the given obligations' spans."""
    spans = [tuple(s) for i in ids for s in by_id[i]["spans"]]
    return [
        a
        for a in parent["ambiguities"]
        if a["origin"] == "deterministic_cue"
        and a["spans"]
        and any(s[0] <= a["spans"][0][0] and a["spans"][0][1] <= s[1] for s in spans)
    ]


def child_diagnostics(parent: dict, child: dict, by_id: dict) -> dict:
    """DIAGNOSTIC record for one child. Flags and lexical checks only; never a fidelity certificate."""
    text = child["question"]
    units = parent["source_units"]
    q_stems = lx.content_stems(parent["original_question"])
    child_stems = lx.content_stems(text)
    tokens = set(lx.tokens(text))
    ids = [i for i in [*child["owns"], *child["carries_shared"]] if i in by_id]
    preservation = {i: obligation_preservation(by_id[i], text, by_id) for i in ids}
    lost = [i for i, v in preservation.items() if v["preserved"] is False]
    additions = unsupported_additions(text, q_stems)
    deixis = lx.deixis_in(text)
    question = parent["original_question"]
    source_texts = [(u["source_unit_id"], u["text"]) for u in units] + [
        (f"sentence[{lo}:{hi}]", question[lo:hi]) for lo, hi in _sentence_spans(question)
    ]
    live_anchors = [
        r
        for r in parent["requirements"]
        if r["kind"] in ("requested_item", "relationship", "existence")
        and not r.get("superseded")
        and r["origin"] != "source_unit_floor"
        and r["spans"]
    ]
    spans_of = {u["source_unit_id"]: (u["start"], u["end"]) for u in units}
    spans_of.update({f"sentence[{lo}:{hi}]": (lo, hi) for lo, hi in _sentence_spans(question)})

    def holds_several_asks(label: str) -> bool:
        lo, hi = spans_of[label]
        return sum(1 for a in live_anchors if any(lo <= s[0] and s[1] <= hi for s in a["spans"])) >= 2

    # a child equal to a whole unit/sentence is a copy only when that span holds SEVERAL asks (a compound repeated);
    # a unit that is itself one atomic ask ("is there any X?") is legitimately asked as it stands
    copies = [label for label, t in source_texts if _norm(t) == _norm(text) and holds_several_asks(label)]
    copies += [
        i
        for i in ids
        if by_id[i]["spans"]
        and _norm(by_id[i]["text"]) == _norm(text)
        and by_id[i]["kind"] != "source_unit"
        and not _question_form(text)  # the bare owned words are a copy unless they already read as a question
    ]
    anchors = [
        r
        for r in parent["requirements"]
        if r["kind"] in ("requested_item", "relationship", "existence")
        and not r.get("superseded")
        and r["origin"] != "source_unit_floor"
        and r["spans"]
    ]
    own_stems = {s for i in ids for s in lx.content_stems(by_id[i]["text"])}
    # a fragment that continues another question may name what it is about: that question's words are context, so restating
    # them is not bundling (restating its ASK is caught separately, as an added operator, by the edit ledger)
    context_owned = {
        i for inh in (child.get("node") or {}).get("inherited", []) for i in inh.get("owner_obligations", [])
    }
    covered_other = []
    for a in anchors:
        if a["id"] in ids or a.get("part_of") in ids or a["id"] in context_owned:
            continue
        distinct = [s for s in lx.content_stems(a["text"]) if s not in own_stems]
        if len(distinct) >= 2 and lx.coverage_fraction(distinct, child_stems) >= COMPOUND_COVERAGE:
            covered_other.append(a)
    # restating another anchor that is only a noun phrase (a requested item) is normal for a relationship child; restating
    # another relationship/existence ask, or covering two or more other anchors, is suspected bundling
    bundling = (
        [a["id"] for a in covered_other]
        if (len(covered_other) >= 2 or any(a["kind"] in ("relationship", "existence") for a in covered_other))
        else []
    )
    listed = [
        i
        for i in child["owns"]
        if by_id[i]["kind"] in ("requested_item", "relationship", "existence")
        and len([p for p in _LIST_SPLIT.split(by_id[i]["text"]) if p.strip()]) >= 3
        and len(by_id[i]["spans"]) == 1
    ]
    # unresolved referents: a reference word in the owned words that the child no longer contains has been resolved BY THE
    # WORDING; that is only acceptable if the writer reported it (declared_unresolved). Otherwise it is a silent resolution.
    declared = {str(d.get("word", "")).strip().lower() for d in child.get("declared_unresolved") or []}
    refs = [
        a for a in reference_words_in(parent, ids, by_id) if not a.get("clarification")
    ]  # a clarified word is settled by the user
    resolved = [a["text"] for a in refs if a["text"].lower() not in tokens]
    silent = [w for w in resolved if w.lower() not in declared]
    at_limit = len(text) >= (child.get("output_limits") or {}).get("question_max", 300) - 5
    return {
        "preservation": preservation,
        "lost": lost,
        "unsupported_additions": additions,
        "deixis": deixis,
        "copies_of_source_text": copies,
        "possible_bundling_of_other_obligations": bundling,
        "bundled_list": listed,
        "assumed_readings": resolved,
        "silent_resolution": silent,
        "at_schema_length_limit": at_limit,
        "hard_fail": (not text.strip()) or at_limit or bool(copies) or bool(silent),
        "diagnostic_only": True,
    }


def _edit_kinds(diag: dict) -> set[str]:
    se = diag.get("source_edit") or {}
    return {*se.get("conflict", []), *se.get("review", [])}


def _edit_findings(diag: dict) -> set[str]:
    return set((diag.get("source_edit") or {}).get("findings", []))


def repair_reasons(diag: dict) -> list[str]:
    out = [f"lost_obligation:{i}" for i in diag["lost"]]
    if diag["unsupported_additions"]:
        out.append("unsupported_additions")
    if diag["deixis"]:
        out.append("unresolved_deixis")
    if diag["copies_of_source_text"]:
        out.append("copy_of_source_text")
    if diag["bundled_list"]:
        out.append("bundled_list")
    if diag["possible_bundling_of_other_obligations"]:
        out.append("possible_bundling")
    if diag["silent_resolution"]:
        out.append("silent_resolution")
    if diag["at_schema_length_limit"]:
        out.append("cut_at_length_limit")
    for v in (diag.get("relation") or {}).get("violations", []):
        out.append(f"relation_conflict:{v['kind']}")
    if diag.get("identity_introduced"):
        out.append("identity_introduced")
    if diag.get("relationship_introduced"):
        out.append("relationship_introduced")
    out += [f"source_edit:{k}" for k in sorted(_edit_kinds(diag))]
    return out


def repair_acceptable(before: dict, after: dict) -> tuple[bool, str]:
    """A repair is an improvement only if it loses NO obligation the first pass preserved (relationship endpoints,
    qualifiers, polarity and manner ATTACHED to what they qualify, operations, kinds), resolves no referent silently,
    acquires nothing new, AND resolves at least one flag. Passing more lexical checks while losing an obligation is a
    regression, not an improvement. Even an accepted repair is only a candidate pending human review."""
    changed = (after.get("relation") or {}).get("violations", [])
    if changed:  # a wording that changes what relates to what is never accepted on lexical grounds
        return False, "changes the relationship: " + ", ".join(v["kind"] for v in changed)
    if after.get("identity_introduced"):
        return False, "equates an item with the subject (an identity the request never states)"
    if after.get("relationship_introduced") and not before.get("relationship_introduced"):
        return False, "states a relationship the request does not attach to this item"
    before_edits, after_edits = _edit_findings(before), _edit_findings(after)
    if after_edits - before_edits:  # a repair may not trade one departure from the researcher's wording for another
        return False, "departs from the researcher's wording: " + ", ".join(sorted(after_edits - before_edits))
    departures = sorted(f for f in after_edits if f.split(":")[0] not in ledger.GAP_KINDS)
    if departures:  # passing other checks does not certify wording that still departs from what the researcher wrote
        return False, "the repaired wording still departs from the researcher's: " + ", ".join(departures)
    if after["hard_fail"]:
        return False, "the repair is itself a hard failure"
    regressed = [
        i
        for i, v in before["preservation"].items()
        if v["preserved"] is True and after["preservation"].get(i, {}).get("preserved") is False
    ]
    if regressed:
        return False, f"loses previously preserved obligation(s) {regressed}"
    if len(after["unsupported_additions"]) > len(before["unsupported_additions"]):
        return False, "adds more unsupported words"
    if len(after["possible_bundling_of_other_obligations"]) > len(before["possible_bundling_of_other_obligations"]):
        return False, "bundles more obligations"
    if len(after["assumed_readings"]) > len(before["assumed_readings"]):
        return False, "resolves more referents than the first pass"
    improved = (
        len(after["lost"]) < len(before["lost"])
        or len(after["unsupported_additions"]) < len(before["unsupported_additions"])
        or len(after["deixis"]) < len(before["deixis"])
        or len(after["silent_resolution"]) < len(before["silent_resolution"])
        or (before["hard_fail"] and not after["hard_fail"])
        or bool(before.get("relationship_introduced") and not after.get("relationship_introduced"))
        or bool(
            before_edits and not after_edits
        )  # cleared them ALL; removing some while others remain is not an improvement
    )
    if improved:
        return True, "resolves a flag without losing or acquiring anything (lexical + attachment checks only)"
    if after_edits:
        return False, "no improvement; source-edit findings remain: " + ", ".join(sorted(after_edits))
    return False, "no improvement"


def _norm_ws(s: str) -> str:
    return " ".join(s.split())


def verify_traceability(parent: dict, doc: dict) -> dict:
    """VERIFIED TRACEABILITY only: offsets, quotes, ids, links. Says nothing about semantic fidelity."""
    q = parent["original_question"]
    bad: list[str] = []
    units = {u["source_unit_id"]: u for u in parent["source_units"]}
    for u in units.values():
        if q[u["start"] : u["end"]] != u["text"]:
            bad.append(f"unit {u['source_unit_id']}: text does not equal original[{u['start']}:{u['end']}]")
    for c in parent.get("clarifications", []):
        lo, hi = c["span"]
        tlo, thi = c["target_span"]
        if q[lo:hi] != c["phrase"] or q[tlo:thi] != c["target_text"] or not (lo <= tlo < thi <= hi):
            bad.append(f"clarification {c['id']}: its span or target words do not match the request")
        for link in [c["refers_to"], *c["pairs"]] if c.get("refers_to") else c.get("pairs", []):
            if q[link["span"][0] : link["span"][1]] != link["text"]:
                bad.append(f"clarification {c['id']}: a linked span does not match the request at {link['span']}")
    ids: set[str] = set()
    reqs = {}
    for r in [*parent["requirements"], *parent["ambiguities"], *parent.get("referents", [])]:
        if r["id"] in ids:
            bad.append(f"duplicate requirement id {r['id']}")
        ids.add(r["id"])
        reqs[r["id"]] = r
        for a in r["anchors"]:
            if a["span"] is None:
                if a["state"] != "unanchored":
                    bad.append(f"{r['id']}: null span but state {a['state']}")
                continue
            lo, hi = a["span"]
            if not (0 <= lo < hi <= len(q)):
                bad.append(f"{r['id']}: span {a['span']} outside the request")
                continue
            got, want = q[lo:hi], (a["quote"] or "").strip()
            ok = {
                "exact": got == want,
                "case_insensitive": got.lower() == want.lower(),
                "whitespace_normalized": _norm_ws(got).lower() == _norm_ws(want).lower(),
            }.get(a["state"], False)
            if not ok:
                bad.append(f"{r['id']}: quote {want!r} does not match original[{lo}:{hi}] = {got!r} ({a['state']})")
    for r in parent["requirements"]:
        for key in ("part_of", "split_from"):
            if r.get(key) and r[key] not in reqs:
                bad.append(f"{r['id']}: {key} points at unknown requirement {r[key]}")
    child_ids: set[str] = set()
    touched: set[str] = set()
    for c in doc["children"]:
        if c["child_id"] in child_ids:
            bad.append(f"duplicate child id {c['child_id']}")
        child_ids.add(c["child_id"])
        if not isinstance(c["question"], str) or not c["question"].strip():
            bad.append(f"{c['child_id']}: empty question")
        for uid in c["origin"]["source_unit_ids"]:
            if uid not in units:
                bad.append(f"{c['child_id']}: unknown source unit {uid}")
            touched.add(uid)
        for rid in [*c["owns"], *c["carries_shared"], *c.get("context_referents", [])]:
            if rid not in reqs:
                bad.append(f"{c['child_id']}: owns/carries/uses unknown requirement {rid}")
        for rid in c.get("context_referents", []):
            if rid in c["owns"]:
                bad.append(f"{c['child_id']}: a context referent ({rid}) must never be owned as an obligation")
        for span in c["origin"]["source_spans"]:
            if not (0 <= span[0] < span[1] <= len(q)):
                bad.append(f"{c['child_id']}: source span {span} outside the request")
        for link in c["parent_links"]:
            r = reqs.get(link["requirement_id"])
            if r is None:
                bad.append(f"{c['child_id']}: link to unknown requirement {link['requirement_id']}")
            elif link["spans"] != r["spans"]:
                bad.append(f"{c['child_id']}: link spans differ from {r['id']}'s spans")
    if doc.get("question_tree"):
        bad += tree.verify(parent, doc["question_tree"])
    return {
        "ok": not bad,
        "violations": bad,
        "units_without_child": [u for u in units if u not in touched],
        "scope": "offsets, quotes, ids and links only; says nothing about semantic fidelity",
    }
