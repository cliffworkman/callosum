"""Obligation inventory for the WHOLE original request.

Sources, always labelled: a deterministic floor (one requirement per source unit), deterministic cue hits (a fixed,
disclosed English cue table, including "whether" and "how" as separate polarity/manner obligations), model-proposed
obligations (one pass per source unit for fine granularity, one whole-request pass for what spans units), and
model-proposed ambiguities with alternative readings.

An obligation may have several exact source spans and may cross unit boundaries. Spans and offsets are FACTS once
anchored (the quoted words really are at those offsets); kinds, groupings and readings are model CANDIDATES. An
unanchorable quote is kept as ``unanchored`` and flagged, never dropped or repaired.

Deterministic post-processing (each step recorded, none silent): merge overlapping same-kind obligations, drop a cue
hit a model obligation already covers, split an enumerated list into one item per listed thing (reclassifying the
words that introduce the list as a shared frame), and attach dependent obligations (polarity, manner, kinds,
qualifier, population, operation) to the anchor obligation that contains or is nearest to them.
"""

from __future__ import annotations

import hashlib
import re

from experiments.ask_cli_revised.decompose import ENGINE_VERSION
from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose.calllog import CallCapReached, CallLog
from experiments.ask_cli_revised.request_contract import build_request_contract

KINDS_MODEL = (
    "requested_item",
    "relationship",
    "existence",
    "polarity",
    "manner",
    "kinds",
    "qualifier",
    "population",
    "operation",
    "shared_frame",
    "scope",
    "output_expectation",
)
ANCHOR_KINDS = frozenset({"requested_item", "relationship", "existence"})  # each becomes one child question
DEPENDENT_KINDS = frozenset({"polarity", "manner", "kinds", "qualifier", "population", "operation"})
PARENT_LEVEL_KINDS = frozenset({"output_expectation", "scope"})
SPLIT_KINDS = frozenset({"requested_item", "population"})
MERGE_OVERLAP = 0.4

# Fixed, generic English cue table. A cue HIT is a fact about the text; what it means is not asserted.
CUES = {
    "polarity": ("whether", "if so"),
    "manner": ("how",),
    "qualifier": (
        "specific",
        "specifically",
        "particularly",
        "especially",
        "only",
        "effective",
        "effectively",
        "mixed",
        "null",
        "uncertain",
        "most",
        "primarily",
        "mainly",
        "at least",
        "and more",
        "and other",
        "other relevant",
        "any",
        "all",
        "each",
        "every",
        "not",
        "without",
        "except",
        "rather than",
    ),
    "operation": (
        "synthesize",
        "synthesise",
        "summarize",
        "summarise",
        "list",
        "compare",
        "contrast",
        "return",
        "give me",
        "describe",
        "explain",
        "identify",
        "evaluate",
        "review",
        "rank",
        "quantify",
        "measure",
        "measured",
        "measures",
        "using which",
    ),
    "reference": (
        "they",
        "them",
        "their",
        "theirs",
        "it",
        "its",
        "itself",
        "this",
        "these",
        "those",
        "such",
        "the latter",
        "the former",
    ),
}

_OBLIGATION_SCHEMA = {
    "type": "object",
    "required": ["requirements"],
    "additionalProperties": False,
    "properties": {
        "requirements": {
            "type": "array",
            "maxItems": 14,
            "items": {
                "type": "object",
                "required": ["kind", "quotes", "note"],
                "additionalProperties": False,
                "properties": {
                    "kind": {"type": "string", "enum": list(KINDS_MODEL)},
                    "quotes": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {"type": "string", "maxLength": 240},
                    },
                    "note": {"type": "string", "maxLength": 160},
                },
            },
        }
    },
}
_AMBIGUITY_SCHEMA = {
    "type": "object",
    "required": ["ambiguities"],
    "additionalProperties": False,
    "properties": {
        "ambiguities": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "required": ["quote", "alternatives", "note"],
                "additionalProperties": False,
                "properties": {
                    "quote": {"type": "string", "maxLength": 240},
                    "alternatives": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 3,
                        "items": {"type": "string", "maxLength": 160},
                    },
                    "note": {"type": "string", "maxLength": 160},
                },
            },
        }
    },
}
OBLIGATION_OUTPUT_CAP = 768
AMBIGUITY_OUTPUT_CAP = 640

_KIND_HELP = (
    "Kinds: requested_item = a thing the user wants returned (if a part lists several things, e.g. 'a, b, and c', give "
    "one requested_item per listed thing and put the words they share in a shared_frame); relationship = a link the "
    "user asks about between two or more things (quote each thing); existence = whether something exists ('is there "
    "any...'); polarity = a yes/no ask ('whether'); manner = a how-ask ('how'); kinds = 'which kinds/types of' something; "
    "qualifier = a word that narrows or hedges what is asked; population = a group, culture or sample the request "
    "restricts to; operation = an action the user asks for (list, compare, measure); shared_frame = words that several "
    "separate asks share; scope = a limit that applies to more than one ask; output_expectation = the form of the "
    "whole answer requested.\n"
    "If a part asks BOTH whether something holds AND how, list polarity and manner as two separate items."
)


# The example phrases the inventory prompt itself quotes ('is there any...', 'whether', 'how', ...), derived from the prompt text so the two can
# never drift apart. A model sometimes copies one back as if it were a quote from the request; when that quote is NOT in the request it is an echo
# of the prompt, not an obligation (recorded, never counted, never allowed to force a decomposition decision).
PROMPT_EXAMPLES = tuple(re.findall(r"'([^']+)'", _KIND_HELP))


def _example_key(text: str) -> str:
    return re.sub(r"[\s.…]+$", "", " ".join(str(text).lower().split()))


_EXAMPLE_KEYS = frozenset(_example_key(x) for x in PROMPT_EXAMPLES)


def is_prompt_echo(quote: str) -> bool:
    """True when ``quote`` is (up to case, spacing and trailing dots) one of the prompt's own example phrases."""
    return _example_key(quote) in _EXAMPLE_KEYS


def unit_prompt(question: str, unit_text: str) -> str:
    return (
        "You are reading ONE part of a longer scholarly question. List the separate things this part asks for or "
        "constrains.\n\nDo not answer it. Do not add anything the part does not say. Copy each quote EXACTLY as "
        "written in the part; do not paraphrase.\n" + _KIND_HELP + "\nThe full original question is provided ONLY as "
        'context.\n\nReturn only JSON: {"requirements":[{"kind":"...","quotes":["..."],"note":"..."}]}\n\n'
        f"Full original question (context only):\n{question}\n\nPart to read:\n{unit_text}"
    )


def whole_prompt(question: str) -> str:
    return (
        "You are reading a whole scholarly question. List the things that CONNECT different parts of it, refer back "
        "to something said elsewhere, or apply to the answer as a whole.\n\nDo not answer it. Do not add anything the "
        "question does not say. Copy every quote EXACTLY as written; do not paraphrase. For a word that refers back to "
        "something (they, it, its, this), give two quotes: the word and what it refers to.\n" + _KIND_HELP + "\n\n"
        'Return only JSON: {"requirements":[{"kind":"...","quotes":["..."],"note":"..."}]}\n\n'
        f"Question:\n{question}"
    )


def ambiguity_prompt(question: str) -> str:
    return (
        "You are reading a whole scholarly question. List the places where it can reasonably be read in more than one "
        "way AND the reading would change what a good answer contains (for example a 'they' that could mean two "
        "different things, or a phrase whose target is unclear).\n\nDo not choose a reading. Copy each quote EXACTLY "
        "as written. Give two or three short alternative readings for each. Do not list ordinary wording that has one "
        'clear meaning.\n\nReturn only JSON: {"ambiguities":[{"quote":"...","alternatives":["...","..."],"note":"..."}]}\n\n'
        f"Question:\n{question}"
    )


def anchor(question: str, lo: int, hi: int, quote: str) -> dict:
    """Deterministically locate ``quote`` in the unit ``[lo, hi)`` first, then in the whole question."""
    q = (quote or "").strip()
    out = {"quote": quote, "span": None, "state": "unanchored", "scope": None, "occurrences": 0}
    if not q:
        return out
    ws = r"\s+".join(map(re.escape, q.split()))
    for scope, base, hay in (("unit", lo, question[lo:hi]), ("question", 0, question)):
        for state, flags in (("exact", 0), ("case_insensitive", re.I), ("whitespace_normalized", re.I)):
            pattern = re.escape(q) if state != "whitespace_normalized" else ws
            m = re.search(pattern, hay, flags)
            if m:
                out.update(
                    span=[base + m.start(), base + m.end()],
                    state=state,
                    scope=scope,
                    occurrences=len(re.findall(pattern, hay, flags)),
                )
                return out
    return out


def _unit_at(units: list[dict], pos: int) -> str | None:
    for unit in units:
        if unit["start"] <= pos < unit["end"]:
            return unit["source_unit_id"]
    return None


def maximal_spans(spans: list[list[int]]) -> list[list[int]]:
    """Drop a span wholly contained in another span of the same list (a model quote repeated inside a longer quote), so a
    requirement's words are never displayed or excerpted twice. The anchors themselves are kept for traceability."""
    uniq = sorted({(s[0], s[1]) for s in spans})
    return [list(s) for s in uniq if not any(o != s and o[0] <= s[0] and s[1] <= o[1] for o in uniq)]


def make_requirement(
    req_id, kind, origin, produced_by, anchors, question, units, *, note="", status="candidate"
) -> dict:
    anchored = [a["span"] for a in anchors if a["span"]]
    spans = maximal_spans(anchored)
    anchoring = "none" if not anchored else ("complete" if len(anchored) == len(anchors) else "partial")
    unit_ids = sorted({u for s in spans if (u := _unit_at(units, s[0]))}, key=lambda x: int(x[1:]))
    return {
        "id": req_id,
        "kind": kind,
        "origin": origin,
        "produced_by": produced_by,
        "unit_ids": unit_ids,
        "anchors": anchors,
        "spans": spans,
        "text": " … ".join(question[s[0] : s[1]] for s in spans) if spans else " … ".join(a["quote"] for a in anchors),
        "anchoring": anchoring,
        "note": note,
        "status": status,
    }


def find_cues(question: str, units: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deterministic cue hits: polarity/manner/qualifier/operation become obligations, reference words become ambiguity candidates."""
    reqs: list[dict] = []
    ambs: list[dict] = []
    for kind, cues in CUES.items():
        alternation = "|".join(sorted((r"\s+".join(map(re.escape, c.split())) for c in cues), key=len, reverse=True))
        for m in re.finditer(r"(?<![A-Za-z0-9])(?:" + alternation + r")(?![A-Za-z0-9])", question, re.I):
            anchors = [
                {
                    "quote": m.group(0),
                    "span": [m.start(), m.end()],
                    "state": "exact",
                    "scope": "question",
                    "occurrences": 1,
                }
            ]
            target = ambs if kind == "reference" else reqs
            target.append(
                make_requirement(
                    "tmp",
                    "reference" if kind == "reference" else kind,
                    "deterministic_cue",
                    "deterministic",
                    anchors,
                    question,
                    units,
                    status="cue_hit",
                )
            )
    reqs.sort(key=lambda r: r["spans"][0][0])
    ambs.sort(key=lambda r: r["spans"][0][0])
    for i, r in enumerate(reqs, 1):
        r["id"] = f"C{i}"
    for i, r in enumerate(ambs, 1):
        r["id"] = f"A-ref{i}"
    return reqs, ambs


def accounting(question: str, requirements: list[dict]) -> list[dict]:
    """DIAGNOSTIC: runs of content words in the original that no non-floor obligation span touches."""
    covered = [tuple(s) for r in requirements if r["origin"] != "source_unit_floor" for s in r["spans"]]
    runs: list[list[int]] = []
    pending: list[int] | None = None
    for m in re.finditer(r"[A-Za-z0-9]+", question):
        tok = m.group(0).lower()
        hit = any(lo <= m.start() and m.end() <= hi for lo, hi in covered)
        if hit:
            if pending is not None:
                runs.append(pending)
                pending = None
        elif lx.is_content_token(tok):
            pending = [m.start(), m.end()] if pending is None else [pending[0], m.end()]
    if pending is not None:
        runs.append(pending)
    return [{"span": r, "text": question[r[0] : r[1]]} for r in runs]


def _model_obligations(log: CallLog, question: str, units: list[dict], unit: dict | None, counter: dict) -> list[dict]:
    if unit is None:
        task, prompt = "parent.obligations_whole", whole_prompt(question)
    else:
        task, prompt = "parent.obligations_unit", unit_prompt(question, unit["text"])
    try:
        call = log.call(
            task, prompt, _OBLIGATION_SCHEMA, OBLIGATION_OUTPUT_CAP, unit_id=unit["source_unit_id"] if unit else None
        )
    except CallCapReached:
        return []
    rows = call.parsed.get("requirements") if isinstance(call.parsed, dict) else None
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict) or row.get("kind") not in KINDS_MODEL or not isinstance(row.get("quotes"), list):
            continue
        lo, hi = (unit["start"], unit["end"]) if unit else (0, len(question))
        anchors = [anchor(question, lo, hi, q) for q in row["quotes"] if isinstance(q, str) and q.strip()]
        echoes = [a for a in anchors if a["span"] is None and is_prompt_echo(a["quote"])]
        if echoes:
            counter.setdefault("set_aside", []).append(
                {
                    "task": "obligations_whole" if unit is None else "obligations_unit",
                    "unit": unit["source_unit_id"] if unit else None,
                    "kind": row["kind"],
                    "quotes": [a["quote"] for a in echoes],
                    "reason": "prompt_example_echo: the quote is one of the inventory prompt's own example phrases and is not in the request",
                    "note": str(row.get("note", ""))[:160],
                }
            )
            anchors = [a for a in anchors if a not in echoes]
        if not anchors:
            continue
        counter["n"] += 1
        req = make_requirement(
            f"{'M' if unit else 'W'}{counter['n']}",
            row["kind"],
            "model_unit" if unit else "model_whole",
            log.model.label,
            anchors,
            question,
            units,
            note=str(row.get("note", ""))[:160],
        )
        if unit and not req["unit_ids"]:
            req["unit_ids"] = [unit["source_unit_id"]]
        out.append(req)
    return out


def _model_ambiguities(log: CallLog, question: str, units: list[dict], start: int) -> list[dict]:
    try:
        call = log.call("parent.ambiguities", ambiguity_prompt(question), _AMBIGUITY_SCHEMA, AMBIGUITY_OUTPUT_CAP)
    except CallCapReached:
        return []
    rows = call.parsed.get("ambiguities") if isinstance(call.parsed, dict) else None
    out: list[dict] = []
    for row in rows or []:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("quote"), str)
            or not isinstance(row.get("alternatives"), list)
        ):
            continue
        alts = [a.strip() for a in row["alternatives"] if isinstance(a, str) and a.strip()]
        a = anchor(question, 0, len(question), row["quote"])
        req = make_requirement(
            f"A{start + len(out) + 1}",
            "ambiguity",
            "model_whole",
            log.model.label,
            [a],
            question,
            units,
            note=str(row.get("note", ""))[:160],
        )
        req["alternatives"] = alts
        out.append(req)
    return out


def _chars(spans: list[list[int]]) -> set[int]:
    out: set[int] = set()
    for lo, hi in spans:
        out.update(range(lo, hi))
    return out


def merge_overlapping(reqs: list[dict]) -> list[dict]:
    """Merge same-kind model obligations whose spans overlap (>= MERGE_OVERLAP of the smaller); anchors are unioned."""
    kept: list[dict] = []
    for r in reqs:
        target = None
        if r["spans"]:
            mine = _chars(r["spans"])
            for k in kept:
                if k["kind"] == r["kind"] and k["spans"]:
                    theirs = _chars(k["spans"])
                    if len(mine & theirs) / min(len(mine), len(theirs)) >= MERGE_OVERLAP:
                        target = k
                        break
        if target is None:
            kept.append(r)
            continue
        have = {tuple(s) for s in target["spans"]}
        for a in r["anchors"]:
            if a["span"] and tuple(a["span"]) not in have:
                target["anchors"].append(a)
                have.add(tuple(a["span"]))
        target["anchors"].sort(key=lambda a: (a["span"] is None, a["span"] or [0, 0]))
        target["spans"] = maximal_spans([a["span"] for a in target["anchors"] if a["span"]])
        target["unit_ids"] = sorted(set(target["unit_ids"]) | set(r["unit_ids"]), key=lambda x: int(x[1:]))
        keep = {tuple(s) for s in target["spans"]}
        target["text"] = " … ".join(a["quote"] for a in target["anchors"] if a["span"] and tuple(a["span"]) in keep)
        target.setdefault("merged_from", []).append(r["id"])
    return kept


def absorb_covered_whole(reqs: list[dict]) -> list[dict]:
    """A whole-request obligation that lies inside one unit and is already accounted for (>= 80% of its words) by finer
    unit-pass obligations is recorded but not used: merging it would union separate asks into one compound obligation.
    Obligations that span two or more units are never absorbed (the link between the units is new information)."""
    finer = [
        r
        for r in reqs
        if r["origin"] == "model_unit" and r["kind"] not in ("operation", "output_expectation", "scope") and r["spans"]
    ]
    covered_chars = _chars([s for r in finer for s in r["spans"]])
    absorbed = []
    for w in reqs:
        if (
            w["origin"] != "model_whole"
            or not w["spans"]
            or len(w["unit_ids"]) >= 2
            or w["kind"] in ("operation", "output_expectation", "scope")
        ):
            continue
        mine = _chars(w["spans"])
        if len(mine & covered_chars) / len(mine) >= 0.8:
            w["superseded"] = True
            w["status"] = "covered_by_finer_obligations"
            w["superseded_by"] = [r["id"] for r in finer if _chars(r["spans"]) & mine]
            absorbed.append(w)
    return absorbed


def drop_covered_cues(reqs: list[dict]) -> tuple[list[dict], list[dict]]:
    """A cue hit is redundant when a model obligation of the same kind already overlaps its words."""
    model = [r for r in reqs if r["origin"] in ("model_unit", "model_whole")]
    kept, dropped = [], []
    for r in reqs:
        if r["origin"] == "deterministic_cue" and r["kind"] in DEPENDENT_KINDS:
            span = r["spans"][0]
            twin = next(
                (
                    m
                    for m in model
                    if m["kind"] == r["kind"] and any(max(span[0], s[0]) < min(span[1], s[1]) for s in m["spans"])
                ),
                None,
            )
            if twin:
                twin.setdefault("also_cue_hit", []).append(r["id"])
                dropped.append({"id": r["id"], "text": r["text"], "covered_by": twin["id"]})
                continue
        kept.append(r)
    return kept, dropped


_LIST_SPLIT = re.compile(r"\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+", re.I)


def split_lists(question: str, reqs: list[dict], units: list[dict]) -> list[dict]:
    """Deterministic rule: a model obligation that ENUMERATES three or more short items becomes one requested_item per
    item; an anchor obligation just before the list (only function words between) is reclassified shared_frame."""
    splits: list[dict] = []
    for r in list(reqs):
        if (
            r["origin"] not in ("model_unit", "model_whole")
            or r["kind"] not in SPLIT_KINDS
            or len(r["spans"]) != 1
            or r.get("superseded")
        ):
            continue
        lo, hi = r["spans"][0]
        text = question[lo:hi]
        if len(text.split()) > 14:
            continue
        parts = [p for p in _LIST_SPLIT.split(text) if p and p.strip()]
        if len(parts) < 3 or any(len(p.split()) > 6 for p in parts):
            continue
        cursor, items = 0, []
        for k, p in enumerate(parts, 1):
            i = text.find(p, cursor)
            cursor = i + len(p)
            anchors = [
                {"quote": p, "span": [lo + i, lo + i + len(p)], "state": "exact", "scope": "question", "occurrences": 1}
            ]
            item = make_requirement(
                f"{r['id']}.{k}",
                "requested_item",
                "deterministic_list_split",
                "deterministic",
                anchors,
                question,
                units,
                status="candidate",
            )
            item["split_from"] = r["id"]
            items.append(item)
        r["superseded"] = True
        r["status"] = "split_into_items"
        frame = None
        for f in reqs:
            if (
                f is r
                or f["kind"] not in ANCHOR_KINDS
                or f["origin"] not in ("model_unit", "model_whole")
                or f.get("superseded")
                or not f["spans"]
            ):
                continue
            end = max(s[1] for s in f["spans"])
            gap_tokens = lx.tokens(question[end:lo]) if end <= lo else None
            if (
                gap_tokens is not None
                and len(gap_tokens) <= 3
                and all(not lx.is_content_token(t) for t in gap_tokens)
                and lo - end <= 12
            ):
                if frame is None or end > max(s[1] for s in frame["spans"]):
                    frame = f
        if frame is not None:
            frame["reclassified_from"] = frame["kind"]
            frame["kind"] = "shared_frame"
            frame["reclassified_by"] = "frame_of_split_list"
            frame["frame_for"] = r["id"]
        reqs.extend(items)
        splits.append(
            {
                "list": r["id"],
                "items": [i["id"] for i in items],
                "frame": frame["id"] if frame else None,
                "rule": "enumeration of >=3 short items",
            }
        )
    return splits


def _gap(a: list[list[int]], b: list[list[int]]) -> int:
    return min(max(0, max(x[0], y[0]) - min(x[1], y[1])) for x in a for y in b)


def attach_dependents(reqs: list[dict]) -> None:
    """Attach each dependent obligation to the anchor/shared frame that contains it, else overlaps it, else is nearest."""
    holders = [
        r
        for r in reqs
        if (r["kind"] in ANCHOR_KINDS or r["kind"] == "shared_frame")
        and not r.get("superseded")
        and r["spans"]
        and r["origin"] != "source_unit_floor"
    ]
    floors = {r["unit_ids"][0]: r for r in reqs if r["origin"] == "source_unit_floor"}
    for r in reqs:
        if r["kind"] not in DEPENDENT_KINDS or not r["spans"]:
            continue
        if r["origin"] == "deterministic_cue" and r["kind"] == "operation":
            continue  # "please return", "list": instructions to the system, not asks a child must restate; recorded, not owned
        own = _chars(r["spans"])
        contained = [h for h in holders if own <= _chars(h["spans"]) and h is not r]
        if contained:
            best, basis = min(contained, key=lambda h: len(_chars(h["spans"]))), "contained"
        else:
            overlapping = [
                (len(own & _chars(h["spans"])) / len(own), h)
                for h in holders
                if h is not r and own & _chars(h["spans"])
            ]
            if overlapping and max(o for o, _ in overlapping) >= 0.5:
                best, basis = max(overlapping, key=lambda t: t[0])[1], "overlap"
            else:
                pool = [h for h in holders if h is not r and set(h["unit_ids"]) & set(r["unit_ids"])]
                if not pool:
                    # never attach across units: the dependent stays with its own unit, which then has no anchor
                    # (a unit-level child, unresolved) instead of being silently handed to another unit's obligation
                    floor = floors.get(r["unit_ids"][0]) if r["unit_ids"] else None
                    if floor:
                        r["part_of"], r["attach_basis"] = floor["id"], "unit_floor"
                    continue
                best, basis = (
                    min(pool, key=lambda h: (_gap(r["spans"], h["spans"]), len(_chars(h["spans"])))),
                    "nearest_in_unit",
                )
        r["part_of"], r["attach_basis"] = best["id"], basis


def derive_subject(parent: dict) -> None:
    """Record a candidate SUBJECT REFERENT: the longest run of content words in the first unit that no obligation covers.

    It lives in ``parent["referents"]``, never in ``requirements``, so it can never be owned by a child or become an
    answer obligation; it is background that says what the request is about. Deterministic, anchored, candidate only
    (a human confirms it). No subject is recorded when the first unit has no uncovered run of two or more content words."""
    parent["referents"] = []
    first = parent["source_units"][0]
    runs = [
        r
        for r in parent["unaccounted_text_diagnostic"]
        if first["start"] <= r["span"][0] and r["span"][1] <= first["end"] and len(lx.content_stems(r["text"])) >= 2
    ]
    if not runs:
        return
    best = max(runs, key=lambda r: len(lx.content_stems(r["text"])))
    anchor_ = {"quote": best["text"], "span": best["span"], "state": "exact", "scope": "unit", "occurrences": 1}
    ref = make_requirement(
        "S1",
        "subject",
        "deterministic_unaccounted_run",
        "deterministic",
        [anchor_],
        parent["original_question"],
        parent["source_units"],
        note="a candidate referent: what the request is about. Background only; not an answer obligation.",
        status="candidate_referent",
    )
    parent["referents"].append(ref)


def build_parent_contract(log: CallLog, question: str, *, whole_pass: bool = True, unit_pass: bool = True) -> dict:
    contract = build_request_contract(question)
    units = contract["source_units"]
    reqs: list[dict] = [
        make_requirement(
            f"P-{u['source_unit_id']}",
            "source_unit",
            "source_unit_floor",
            "deterministic",
            [{"quote": u["text"], "span": [u["start"], u["end"]], "state": "exact", "scope": "unit", "occurrences": 1}],
            question,
            units,
            status="fact",
        )
        for u in units
    ]
    cue_reqs, ambs = find_cues(question, units)
    counter = {"n": 0}
    model_reqs: list[dict] = []
    if unit_pass:
        for unit in units:
            model_reqs.extend(_model_obligations(log, question, units, unit, counter))
    if whole_pass:
        model_reqs.extend(_model_obligations(log, question, units, None, counter))
    ambs.extend(_model_ambiguities(log, question, units, len(ambs)))
    absorbed = absorb_covered_whole(model_reqs)
    inventory = merge_overlapping([r for r in model_reqs if not r.get("superseded")])
    combined, dropped_cues = drop_covered_cues([*inventory, *cue_reqs])
    splits = split_lists(question, combined, units)
    reqs.extend(combined)
    reqs.extend(absorbed)
    attach_dependents(reqs)
    parent = {
        "version": f"{ENGINE_VERSION}/parent",
        "original_question": question,
        "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
        "source_units": units,
        "requirements": reqs,
        "ambiguities": ambs,
        "post_processing": {
            "merged": [{"kept": r["id"], "merged": r["merged_from"]} for r in reqs if r.get("merged_from")],
            "dropped_cues": dropped_cues,
            "list_splits": splits,
            "absorbed_whole_pass": [
                {"id": w["id"], "text": w["text"], "covered_by": w["superseded_by"]} for w in absorbed
            ],
        },
        "unaccounted_text_diagnostic": accounting(question, reqs),
        "produced_by": {
            "deterministic": ["source units", "spans", "cue hits", "anchoring", "merge/split/attach rules"],
            "model": log.model.label,
        },
        "semantic_fidelity": {
            "status": "not_certified",
            "note": "kinds, quotes chosen and groupings are model candidates; only spans/offsets are verified facts",
        },
    }
    if counter.get(
        "set_aside"
    ):  # only when something was set aside, so a contract without echoes is unchanged byte for byte
        parent["post_processing"]["set_aside_prompt_echoes"] = counter["set_aside"]
    derive_subject(parent)
    return parent
