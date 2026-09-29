"""Child questions generated FROM OBLIGATIONS, with SCOPED context.

Each anchor obligation (a requested item, a relationship, an existence ask) becomes one child. The child OWNS that
anchor plus every dependent obligation attached to it (polarity, manner, kinds, qualifier, population, operation) and
CARRIES the shared frame words that introduce it. Ownership is structural (by construction), not a guess.

Each wording call is given ONLY: the owned obligations with their exact words and offsets; the shared framing; the
subject as a background referent (never an obligation); the excerpts of the request those words come from (in order,
across units when the obligation spans units); and the unresolved readings that touch those words. It is never given the
whole request, so a child cannot acquire requirements from material it does not own.

A unit that has no anchor obligation, and an elliptical fragment whose target is not stated ("and using which scales?"),
are NOT written: they stay unresolved with their exact words rather than becoming a plausible but unsupported rewrite.
A referent the wording resolves is an assumed, unapproved reading and must be reported. Nothing here certifies
semantic fidelity.
"""

from __future__ import annotations

import copy
import re

from experiments.ask_cli_revised.decompose import checks, execution, ledger, relations, structure, tree
from experiments.ask_cli_revised.decompose import clarifications as clar
from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose.calllog import CallCapReached, CallLog
from experiments.ask_cli_revised.decompose.parent import ANCHOR_KINDS, PARENT_LEVEL_KINDS
from experiments.ask_cli_revised.request_contract import _sentence_spans

CHILD_SCHEMA = {
    "type": "object",
    "required": ["question", "unresolved"],
    "additionalProperties": False,
    "properties": {
        "question": {"type": "string", "maxLength": 300},
        "unresolved": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "required": ["word", "reading_used", "other_readings"],
                "additionalProperties": False,
                "properties": {
                    "word": {"type": "string", "maxLength": 40},
                    "reading_used": {"type": "string", "maxLength": 120},
                    "other_readings": {"type": "array", "maxItems": 3, "items": {"type": "string", "maxLength": 120}},
                },
            },
        },
    },
}
CHILD_OUTPUT_CAP = 384
V3_LIMITS = {"question_max": 300, "unresolved_max": 4, "cap": CHILD_OUTPUT_CAP}
NOT_CERTIFIED = {
    "status": "not_certified",
    "note": "diagnostics flag; nothing here certifies that the child preserves the parent's meaning",
}
_CONJUNCTIONS = ("and", "or", "but", "also", "then", "plus")
WRITTEN_KINDS = ("generated",)  # kinds that a model wrote; everything else is exact words, unresolved


def by_id_map(parent: dict) -> dict:
    return {r["id"]: r for r in [*parent["requirements"], *parent["ambiguities"], *parent.get("referents", [])]}


def elliptical_units(parent: dict) -> set[str]:
    """Units that are elliptical fragments: they begin with a conjunction and state (almost) nothing themselves."""
    out = set()
    for u in parent["source_units"]:
        toks = lx.tokens(u["text"])
        if toks and toks[0] in _CONJUNCTIONS and len(lx.content_stems(u["text"])) <= 2:
            out.add(u["source_unit_id"])
    return out


def plan_children(parent: dict) -> list[dict]:
    """Deterministic grouping: one child per anchor obligation, owning the anchor and its attached dependents."""
    live = [r for r in parent["requirements"] if not r.get("superseded")]
    anchors = [
        r for r in live if r["kind"] in ANCHOR_KINDS and r["origin"] != "source_unit_floor" and r["anchoring"] != "none"
    ]
    frames = [r for r in live if r["kind"] == "shared_frame" and r["anchoring"] != "none"]
    referents = [r["id"] for r in parent.get("referents", [])]
    elliptical = elliptical_units(parent)
    plans: list[dict] = []
    for a in anchors:
        shared: list[str] = []
        for f in frames:
            # a frame introduced a split list -> shared by that list's items; a model-proposed frame -> shared by anchors inside its units
            applies = (
                a.get("split_from") == f["frame_for"]
                if f.get("frame_for")
                else set(a["unit_ids"]) <= set(f["unit_ids"])
            )
            if applies:
                shared += [f["id"], *[r["id"] for r in live if r.get("part_of") == f["id"]]]
        kind = "elliptical" if a["unit_ids"] and set(a["unit_ids"]) <= elliptical else "anchor"
        plans.append(
            {
                "anchor_id": a["id"],
                "owns": [a["id"], *[r["id"] for r in live if r.get("part_of") == a["id"]]],
                "carries_shared": shared,
                "context_referents": list(referents),
                "relation": relations.build_contract(parent, a) if a["kind"] == "relationship" else None,
                "kind": kind,
                "unit_level": False,
                "start": min(s[0] for s in a["spans"]),
            }
        )
    covered = {u for a in anchors for u in a["unit_ids"]}
    parent_level = {u for r in live if r["kind"] in PARENT_LEVEL_KINDS for u in r["unit_ids"]}
    for u in parent["source_units"]:
        uid = u["source_unit_id"]
        if uid in covered or uid in parent_level:
            continue
        floor_id = f"P-{uid}"
        plans.append(
            {
                "anchor_id": floor_id,
                "owns": [floor_id, *[r["id"] for r in live if r.get("part_of") == floor_id]],
                "carries_shared": [],
                "context_referents": [],
                "relation": None,
                "kind": "unit_level",
                "unit_level": True,
                "start": u["start"],
            }
        )
    plans.sort(key=lambda p: p["start"])
    for i, p in enumerate(plans, 1):
        p["child_id"] = (
            f"c{i}"  # ids are fixed BEFORE anything is folded, so a folded child leaves a gap, never a renumbering
        )
    _fold_slot_items(parent, plans)
    _clarified_fragments(parent, plans)
    tree.annotate_plans(parent, plans)
    return plans


def _fold_slot_items(parent: dict, plans: list[dict]) -> None:
    """A requested item that IS the subject or the target slot of a relationship in the same words belongs to that
    relationship's question: asking "which traits" and "do traits relate to X" as two questions duplicates one ask and
    lets the item's wording drift from the relationship it fills. The folded child keeps its id in ``folded``."""
    by = by_id_map(parent)
    for plan in plans:
        rc = plan.get("relation")
        if not (rc and rc.get("parse_status") == "parsed"):
            continue
        slots = [] if rc["subject"]["is_reference"] else [("subject", rc["subject"]["spans"][0])]
        slots.append(("target", rc["target"]["spans"][0]))
        for other in list(plans):
            if other is plan or other["kind"] != "anchor" or other.get("relation"):
                continue
            item = by[other["anchor_id"]]
            if item["kind"] != "requested_item":
                continue
            slot = next((n for n, (lo, hi) in slots if all(lo <= s[0] and s[1] <= hi for s in item["spans"])), None)
            if slot:
                plan["owns"] += other["owns"]
                plan.setdefault("folded", []).append(
                    {
                        "child_id": other["child_id"],
                        "anchor_id": other["anchor_id"],
                        "slot": slot,
                        "owned": other["owns"],
                    }
                )
                plans.remove(other)


def _clarified_fragments(parent: dict, plans: list[dict]) -> None:
    """A fragment that states no target of its own is not written UNLESS the user has said what it asks (a meaning
    clarification covering all of its words); then it is written like any other question, with that clarification shown."""
    by = by_id_map(parent)
    for p in plans:
        if p["kind"] not in ("elliptical", "unit_level"):
            continue
        c = clar.fragment_clarification(parent, [s for i in p["owns"] for s in by[i]["spans"]])
        if c:
            p["kind"], p["unit_level"], p["clarified_fragment"] = "anchor", False, c["id"]


# ---- scoped context ------------------------------------------------------------------------------------------------


def _function_gap(question: str, lo: int, hi: int) -> bool:
    gap = question[lo:hi]
    toks = lx.tokens(gap)
    return (
        hi - lo <= 30
        and len(toks) <= 4
        and all(not lx.is_content_token(t) for t in toks)
        and not re.search(r"[.?!]", gap)
    )


def _unit_of_pos(parent: dict, pos: int) -> str | None:
    return next((u["source_unit_id"] for u in parent["source_units"] if u["start"] <= pos < u["end"]), None)


def excerpts(parent: dict, spans: list[list[int]], splice: dict | None = None) -> list[dict]:
    """The exact request wording around the given spans, in order. Short function-word gaps are kept so the excerpt
    reads naturally; anything else is left out and marked with an ellipsis between separate excerpts.

    ``splice`` handles one ITEM of a split list: the connector before the list ("... manifest in") plus the item are
    joined from their exact source spans, so a later list item keeps the preposition its own position lacks."""
    q = parent["original_question"]
    merged: list[list[int]] = []
    for lo, hi in sorted({(s[0], s[1]) for s in spans}):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        elif merged and _function_gap(q, merged[-1][1], lo):
            merged[-1][1] = hi
        else:
            merged.append([lo, hi])
    out = []
    for lo, hi in merged:
        entry = {"unit_id": _unit_of_pos(parent, lo), "span": [lo, hi], "text": q[lo:hi]}
        if splice and hi == splice["lead_hi"]:
            x, y = splice["item"]
            entry.update(text=q[lo:hi] + q[x:y], spans=[[lo, hi], [x, y]], spliced=True)
            splice = None
        out.append(entry)
    if splice:  # the connector was not adjacent to the frame: keep the item as its own excerpt rather than lose it
        x, y = splice["item"]
        out.append({"unit_id": _unit_of_pos(parent, x), "span": [x, y], "text": q[x:y]})
    return out


def _lead_scaffold(parent: dict, core: list[list[int]]) -> list[int] | None:
    """The researcher's own operation words directly before the first owned words ("please return"), when no other
    question owns them. Never extended over a conjunction, a word another question owns, or a non-function word."""
    q = parent["original_question"]
    first = min(core, key=lambda s: s[0])[0] if core else None
    unit = next((u for u in parent["source_units"] if first is not None and u["start"] <= first < u["end"]), None)
    if unit is None:
        return None
    owned_elsewhere = [
        tuple(s)
        for r in parent["requirements"]
        if not r.get("superseded")
        and r["origin"] != "source_unit_floor"
        and r["kind"] != "operation"
        and r["kind"] not in PARENT_LEVEL_KINDS  # a whole-answer expectation restates words; it does not own them
        for s in r["spans"]
    ]
    left = first
    for m in reversed(list(re.finditer(r"[A-Za-z0-9]+", q[unit["start"] : first]))):
        lo, hi = unit["start"] + m.start(), unit["start"] + m.end()
        word = m.group(0).lower()
        if (
            word not in lx.FUNCTION_WORDS
            or word in _CONJUNCTIONS
            or any(a <= lo and hi <= b for a, b in owned_elsewhere)
        ):
            break
        left = lo
    return [left, first] if left < first else None


def _governing_operation(parent: dict, core: list[list[int]], plan: dict) -> list[int] | None:
    """The researcher's own sentence-initial operation ("please return") when it governs this question in the original
    sentence: an operation cue that no question owns, that opens the sentence (only function words before it), and that
    precedes this question's first owned words with no sentence end between. Copying it is source preservation."""
    if not core:
        return None
    q = parent["original_question"]
    first = min(s[0] for s in core)
    sent = next(((a, b) for a, b in _sentence_spans(q) if a <= first < b), None)
    if sent is None:
        return None
    own = {*plan["owns"], *plan["carries_shared"]}
    for r in parent["requirements"]:
        if r["kind"] != "operation" or r["origin"] != "deterministic_cue" or r.get("superseded") or not r["spans"]:
            continue
        if r["id"] in own or r.get("part_of"):  # an operation another question owns is that question's, not shared
            continue
        s = r["spans"][0]
        if not (sent[0] <= s[0] and s[1] <= first):
            continue
        if any(lx.is_content_token(t) for t in lx.tokens(q[sent[0] : s[0]])):
            continue  # not sentence-initial
        left = s[0]
        for m in reversed(list(re.finditer(r"[A-Za-z0-9]+", q[sent[0] : s[0]]))):
            word = m.group(0).lower()
            if word in _CONJUNCTIONS or word not in lx.FUNCTION_WORDS:
                break
            left = sent[0] + m.start()
        return [left, s[1]]
    return None


def child_context(
    parent: dict, plan: dict, by_id: dict, *, plans: list[dict] | None = None, governing_operation: bool = False
) -> dict:
    q = parent["original_question"]
    owned, shared = plan["owns"], plan["carries_shared"]
    subject = [by_id[i] for i in plan["context_referents"]]
    core = [s for i in [*owned, *shared] for s in by_id[i]["spans"]]
    rc = plan.get("relation")
    if rc and rc.get("parse_status") == "parsed":
        # the excerpt must show every word the relationship structure names (its subject with modifiers, the relation, the
        # target and the question-form marker), or the structure and the wording the writer sees would disagree
        core += [s for k in ("subject", "relation", "target", "answer_form") for s in rc[k]["spans"]]
    splice = None
    anchor = by_id[plan["anchor_id"]]
    if anchor.get("split_from") and shared:
        list_lo = by_id[anchor["split_from"]]["spans"][0][0]
        ends = [s[1] for i in shared for s in by_id[i]["spans"] if s[1] <= list_lo]
        if ends and _function_gap(q, max(ends), list_lo):
            core.append([max(ends), list_lo])  # the connector ("in") that introduces the list
            if anchor["spans"][0][0] > list_lo:
                core = [s for s in core if s not in anchor["spans"]]
                splice = {"lead_hi": list_lo, "item": anchor["spans"][0]}
    lead = _lead_scaffold(parent, core)
    if lead:
        core.append(lead)
    governing = _governing_operation(parent, core, plan) if governing_operation else None
    if governing and not any(c[0] <= governing[0] and governing[1] <= c[1] for c in core):
        core.append(governing)
    # a subject that sits between the extracted words in one unit ("how does <subject> manifest in <item>") is part of the
    # source stretch, not restored context
    for r in subject:
        for s in r["spans"]:
            hull = [c for c in core if _unit_of_pos(parent, c[0]) == _unit_of_pos(parent, s[0])]
            if hull and min(c[0] for c in hull) <= s[0] and s[1] <= max(c[1] for c in hull):
                core.append(s)
    spans = core + [s for r in subject for s in r["spans"]]
    unresolved, clarified = [], []
    for a in checks.reference_words_in(parent, [*owned, *shared], by_id):
        c = clar.covering(parent, a["spans"][0])
        if c:
            clarified.append(
                {
                    "id": a["id"],
                    "word": a["text"],
                    "span": a["spans"][0],
                    "means": c["means"],
                    "clarification": c["id"],
                    "authorized_by": c["authorized_by"],
                    "refers_to": c.get("refers_to"),
                }
            )
        else:
            unresolved.append(
                {
                    "kind": "reference",
                    "id": a["id"],
                    "word": a["text"],
                    "span": a["spans"][0],
                    "candidates": relations.candidate_antecedents(parent, a),
                    "alternatives": [],
                }
            )
    for a in touching_ambiguities(parent, [*owned, *shared], by_id):
        if a["origin"] != "deterministic_cue" and not a.get("clarification"):
            unresolved.append(
                {
                    "kind": "ambiguity",
                    "id": a["id"],
                    "word": a["text"],
                    "span": a["spans"][0],
                    "candidates": [],
                    "alternatives": a.get("alternatives") or [],
                }
            )
    own_spans = [s for i in [*owned, *shared] for s in by_id[i]["spans"]]
    for c in clar.meanings_touching(parent, own_spans):
        clarified.append(
            {
                "id": c["id"],
                "word": c["target_text"],
                "span": c["target_span"],
                "means": c["means"],
                "clarification": c["id"],
                "authorized_by": c["authorized_by"],
                "refers_to": c.get("refers_to"),
            }
        )
    joint = []
    for c in parent.get("clarifications", []):
        hit = [
            m for m in c.get("pairs") or [] if any(max(m["span"][0], s[0]) < min(m["span"][1], s[1]) for s in own_spans)
        ]
        if len(hit) >= 2:  # both halves of a pairing are in this question: it must keep them paired
            joint.append({"clarification": c["id"], "members": [m["text"] for m in c["pairs"]]})
    return {
        "owned": owned,
        "shared": shared,
        "subject": subject,
        "relation": plan.get("relation"),
        "extract": excerpts(parent, core, splice),
        "governing": governing,
        "link": clar.context_link(parent, own_spans),
        "inherited_extracts": _inherited_extracts(parent, plan, plans, by_id) if governing_operation else [],
        "excerpts": excerpts(parent, spans, splice),
        "unresolved": unresolved,
        "clarified": clarified,
        "joint": joint,
        "inherited": [i for i in (plan.get("node") or {}).get("inherited", []) if i["from_node"] != tree.ROOT],
    }


def _inherited_extracts(parent: dict, plan: dict, plans: list[dict] | None, by_id: dict) -> list[dict]:
    """For a fragment that continues another question, that question's SOURCE words: context only, never to be asked again."""
    out = []
    for inh in (plan.get("node") or {}).get("inherited", []):
        if inh["role"] != "fragment_target" or inh["from_node"] == tree.ROOT:
            continue
        owner = next((p for p in plans or [] if p["child_id"] == inh["from_node"]), None)
        if owner is not None:
            ctx = child_context(parent, owner, by_id, governing_operation=False)
            out.append({"from_node": owner["child_id"], "entries": ctx["extract"], "obligations": owner["owns"]})
    return out


def touching_ambiguities(parent: dict, ids: list[str], by_id: dict) -> list[dict]:
    spans = [tuple(s) for i in ids for s in by_id[i]["spans"]]
    return [
        a
        for a in parent["ambiguities"]
        if a["spans"] and any(max(s[0], t[0]) < min(s[1], t[1]) for s in spans for t in map(tuple, a["spans"]))
    ]


def _line(n: int, r: dict) -> str:
    spans = ", ".join(f"{a}-{b}" for a, b in r["spans"])
    return f'{n}. [{r["kind"]}] "{r["text"]}" (chars {spans})'


def context_block(parent: dict, plan: dict, by_id: dict) -> str:
    ctx = child_context(parent, plan, by_id)
    lines = [
        "What this question must ask (its owned items, exact words from the request):\n"
        + "\n".join(_line(n, by_id[i]) for n, i in enumerate(ctx["owned"], 1))
    ]
    if ctx["relation"]:
        lines.append(relations.render(ctx["relation"]))
    if ctx["shared"]:
        lines.append(
            "Framing that introduces these items (include it so the question reads naturally):\n"
            + "\n".join(_line(n, by_id[i]) for n, i in enumerate(ctx["shared"], 1))
        )
    lines.append(
        "Source extract: the request's own words for this question, with the other questions' words already left out. "
        "This is your starting point; return it unchanged unless it cannot stand alone:\n"
        + "\n".join(f'- [{e["unit_id"]}] "{e["text"]}"' for e in ctx["extract"])
    )
    if ctx["subject"]:
        lines.append(
            "Background referent: what the request is about. If the extract does not already say it and the question needs it to stand alone, you may copy its exact words; do NOT ask about it and do NOT add anything else from it:\n"
            + "\n".join(
                f'- subject: "{r["text"]}" (chars {r["spans"][0][0]}-{r["spans"][0][1]})' for r in ctx["subject"]
            )
        )
    lines.append(
        "The request's own wording these come from (excerpts in order; \u2026 marks omitted text; a joined excerpt is spliced from exact spans):\n"
        + "\n".join(f'- [{e["unit_id"]}] "{e["text"]}"' for e in ctx["excerpts"])
    )
    if ctx["clarified"]:
        lines.append(
            "Clarified by the user (authoritative; use these meanings, do not reinterpret them):\n"
            + "\n".join(
                f'- "{c["word"]}" (chars {c["span"][0]}-{c["span"][1]}) means: "{c["means"]}" ({c["clarification"]}, authorized by {c["authorized_by"]})'
                + (f'; it points at the request words "{c["refers_to"]["text"]}"' if c.get("refers_to") else "")
                for c in ctx["clarified"]
            )
        )
    if ctx["inherited"]:
        lines.append(
            "Inherited from a question that sits above this one (context only; it is asked separately, so do NOT ask it again):"
            + chr(10)
            + chr(10).join(
                f'- "{i["text"]}" (chars {i["spans"][0][0]}-{i["spans"][0][1]}), asked by {i["from_node"]}: '
                + (
                    "what this question's subject points at"
                    if i["role"].startswith("subject")
                    else "what this fragment is about"
                )
                for i in ctx["inherited"]
            )
        )
    for j in ctx["joint"]:
        lines.append(
            f"Paired answers ({j['clarification']}): "
            + " and ".join(f'"{m}"' for m in j["members"])
            + " must be asked as pairs (each value with its counterpart), not as independent lists."
        )
    if ctx["unresolved"]:
        rows = []
        for u in ctx["unresolved"]:
            options = [f'"{c["text"]}" ({c["role"]})' for c in u["candidates"]] + [f'"{a}"' for a in u["alternatives"]]
            rows.append(
                f'- "{u["word"]}" (chars {u["span"][0]}-{u["span"][1]}): could mean {" | ".join(options) if options else "something the request does not state"}; other readings may exist'
            )
        lines.append("Unresolved wording (NOT settled; no reading is approved):\n" + "\n".join(rows))
    return "\n\n".join(lines)


def child_prompt(parent: dict, plan: dict, by_id: dict) -> str:
    return (
        "You are writing ONE standalone question for a literature search, from a few things a longer request asks for. "
        "You are not shown the rest of the request.\n\n" + context_block(parent, plan, by_id) + "\n\nRules:\n"
        "- This is a minimal EXTRACTION, not a rewrite. Start from the source extract and change as little as possible. The researcher's own "
        "words stay: never swap their verbs, nouns, qualifiers or question words for other terms, however precise they seem.\n"
        "- Allowed edits, in order of preference: (1) copy exact source words; (2) leave out words that belong to other questions; "
        "(3) restore context the question needs by copying its exact words; (4) fix grammar and punctuation (a capital, a final '?', "
        "do/does/is/are so a statement reads as a question); (5) replace a reference word using a NAMED user clarification.\n"
        "- Do not add a connecting word (in, of, for, about, with, to, and, or...) or any relation between two things unless the source or a named "
        "clarification supplies it. If the request does not say how an item relates to its subject, do not choose a relation: keep the source words "
        'and report the unstated link under "unresolved" (word = the words involved, reading_used = "none chosen").\n'
        "- Keep every question word and qualifier the researcher used (whether, how, which, what kind of, any, effective, not...) and add none: "
        "whether stays whether/yes-no, how stays how, which/what stays which/what, negation is neither added nor removed.\n"
        "- Ask ONLY the owned items. The framing and the background referent are there so the question makes sense; do not add requirements from them.\n"
        "- If a relationship is listed, keep its subject, relation, target and direction exactly as parsed, and keep the answer form "
        "(a yes/no ask stays yes/no; a what/which ask stays what/which). Never swap subject and target and never replace either.\n"
        "- Do not add topics, populations, comparisons or methods that are not in the owned words or a named clarification.\n"
        "- A meaning the user has clarified is authoritative: use it. If a word is still unresolved (listed above) you may use its most direct reading "
        'so the question stands alone, but you MUST report it in "unresolved" (the word, the reading you used, the other readings). Never resolve one silently.\n'
        'Return only JSON: {"question":"...","unresolved":[{"word":"...","reading_used":"...","other_readings":["..."]}]}'
    )


# The frozen v3 writer: the prompt above, its schema and its cap. Later variants live in ``prompts.py`` and never edit these.
V3_SETTINGS = {
    "variant": "v3",
    "schema": CHILD_SCHEMA,
    "cap": CHILD_OUTPUT_CAP,
    "limits": V3_LIMITS,
    "extract_mode": "v3",
    "preflight": False,
    "render": lambda parent, plan, plans, by_id: child_prompt(parent, plan, by_id),
}

# ---- children ------------------------------------------------------------------------------------------------------------


def _exact_words(parent: dict, plan: dict, by_id: dict) -> str:
    return (
        by_id[plan["anchor_id"]]["text"]
        if plan["kind"] == "anchor"
        else by_id[f"P-{by_id[plan['anchor_id']]['unit_ids'][0]}"]["text"]
    )


def _targets_before(parent: dict, unit_ids: list[str]) -> list[dict]:
    """Candidate targets for an elliptical fragment: the anchor obligations of the unit just before it."""
    order = [u["source_unit_id"] for u in parent["source_units"]]
    prev = order[order.index(unit_ids[0]) - 1] if unit_ids and order.index(unit_ids[0]) > 0 else None
    return [
        {"id": r["id"], "text": r["text"]}
        for r in parent["requirements"]
        if prev
        and r["kind"] in ANCHOR_KINDS
        and not r.get("superseded")
        and r["origin"] != "source_unit_floor"
        and r["unit_ids"] == [prev]
    ][-3:]  # the anchors NEAREST the fragment (the end of the previous unit)


OFFLINE_MODES = frozenset({"scripted", "replay"})  # calls that legitimately carry no provider stop reason
CARRIER_KINDS = ("generated", "passthrough")  # kinds that carry a request forward (a passthrough is the request itself)
_STATUS = {
    "generated": "candidate",
    "passthrough": "no_decomposition_needed",
    "fallback": "fallback_unresolved",
    "unit_level": "unit_level_unresolved",
    "unresolved_elliptical": "elliptical_unresolved",
    "constraint_failure": "constraint_failure",
    "not_selected": "not_selected",
}


def _new_child(
    parent: dict,
    plan: dict,
    by_id: dict,
    text: str,
    *,
    kind: str,
    pass_no: int,
    produced_by: str,
    style: str,
    settings: dict | None = None,
    extract_mode: str | None = None,
) -> dict:
    ids = [*plan["owns"], *plan["carries_shared"]]
    spans = sorted({tuple(s) for i in ids for s in by_id[i]["spans"]})
    child = {
        "child_id": plan["child_id"],
        "question": text,
        "kind": kind,
        "status": _STATUS[kind],
        "is_decomposition": kind == "generated",
        "origin": {
            "source_unit_ids": sorted({u for i in ids for u in by_id[i]["unit_ids"]}, key=lambda x: int(x[1:])),
            "source_spans": [list(s) for s in spans],
            "source_text": " … ".join(by_id[i]["text"] for i in plan["owns"][:1]),
            "anchor_id": plan["anchor_id"],
            "style": style,
            "pass": pass_no,
            "produced_by": produced_by,
        },
        "prompt_variant": (settings or {}).get("variant", "v3"),
        "extract_mode": extract_mode or (settings or {}).get("extract_mode", "v3"),
        "output_limits": dict((settings or {}).get("limits", V3_LIMITS)),
        "owns": list(plan["owns"]),
        "carries_shared": list(plan["carries_shared"]),
        "context_referents": list(plan["context_referents"]),
        "relation_contract": plan.get("relation"),
        "node": plan.get("node"),
        "folded": plan.get("folded", []),
        "clarified_fragment": plan.get("clarified_fragment"),
        "parent_links": [
            {
                "requirement_id": i,
                "kind": by_id[i]["kind"],
                "role": "owned_anchor"
                if i == plan["anchor_id"]
                else (
                    "slot_item"
                    if any(i in f["owned"] for f in plan.get("folded", []))
                    else ("owned_dependent" if i in plan["owns"] else "shared_frame")
                ),
                "spans": by_id[i]["spans"],
                "text": by_id[i]["text"],
            }
            for i in ids
        ],
        "declared_unresolved": [],
        "interpretations": [],
        "flags": [],
        "diagnostics": None,
        "semantic_fidelity": dict(NOT_CERTIFIED),
    }
    if kind == "unresolved_elliptical":
        child["candidate_targets"] = _targets_before(parent, child["origin"]["source_unit_ids"])
    return child


def annotate(parent: dict, child: dict, by_id: dict, plans: list[dict] | None = None) -> dict:
    """Attach diagnostics, flags, interpretations and the execution readiness to a child. The readiness is a separate fact from the status: a
    ``candidate`` label alone never authorizes Ask to run a wording (see ``execution``)."""
    _annotate(parent, child, by_id, plans)
    starting = None
    if "preparation" not in child and child["kind"] == "generated":
        plan = next((p for p in plans or [] if p["child_id"] == child["child_id"]), None)
        if plan is not None:
            ctx = child_context(
                parent, plan, by_id, plans=plans, governing_operation=child.get("extract_mode") == "governing"
            )
            starting = " ".join(e["text"] for e in ctx["extract"])
    child["execution"] = execution.readiness(child, starting_point=starting)
    return child


def _annotate(parent: dict, child: dict, by_id: dict, plans: list[dict] | None = None) -> dict:
    """Attach diagnostics, flags and interpretations to a child (diagnostic only; nothing here certifies fidelity)."""
    child["flags"], child["interpretations"] = [], []
    if child["kind"] == "fallback":
        child["flags"].append(
            {"flag": "exact_source_text_fallback", "note": "safe output, not a decomposition; unresolved"}
        )
        return child
    if child["kind"] == "constraint_failure":
        child["flags"].append(
            {
                "flag": "output_constraint_failure",
                "note": "the request cannot fit the configured output limits; it was NOT shortened and NOT sent to the model",
                **child.get("constraint", {}),
            }
        )
        return child
    if child["kind"] == "not_selected":
        child["flags"].append({"flag": "not_selected", "note": "left out of this subset run; no model call was made"})
        return child
    if child["kind"] == "passthrough":
        child["flags"].append(
            {
                "flag": "no_decomposition_needed",
                "note": "the request is already one independently runnable Ask request: kept exactly as written and not sent to "
                "the decomposition writer. It is NOT answered: it still goes through the normal Ask execution path once",
                "informational": True,
            }
        )
        return child
    if child["kind"] == "unit_level":
        child["flags"].append(
            {
                "flag": "unit_level_no_obligations_found",
                "note": "no anchor obligation was found in this unit; kept as its exact words, unresolved",
            }
        )
        return child
    if child["kind"] == "unresolved_elliptical":
        child["flags"].append(
            {
                "flag": "elliptical_fragment_target_not_stated",
                "note": "the ask has no stated target; not written, to avoid an unsupported rewrite",
                "candidate_targets": child.get("candidate_targets", []),
            }
        )
        return child
    diag = checks.child_diagnostics(parent, child, by_id)
    child["diagnostics"] = diag
    for i in diag["lost"]:
        child["flags"].append(
            {
                "flag": "obligation_not_lexically_preserved",
                "obligation": i,
                "kind": by_id[i]["kind"],
                "words": by_id[i]["text"],
                "note": diag["preservation"][i].get("note"),
                "diagnostic_only": True,
            }
        )
    for key, flag in (("unsupported_additions", "possible_unsupported_addition"), ("deixis", "not_self_contained")):
        if diag[key]:
            child["flags"].append({"flag": flag, "tokens": diag[key], "diagnostic_only": True})
    for key, flag in (
        ("copies_of_source_text", "copy_of_source_text"),
        ("bundled_list", "bundled_list"),
        ("possible_bundling_of_other_obligations", "possible_bundling_of_other_obligations"),
    ):
        if diag[key]:
            child["flags"].append({"flag": flag, "obligations": diag[key], "diagnostic_only": True})
    if diag["silent_resolution"]:
        child["flags"].append(
            {
                "flag": "silent_resolution_of_referent",
                "words": diag["silent_resolution"],
                "note": "the wording resolved a referent and did not report it",
            }
        )
    if diag["at_schema_length_limit"]:
        child["flags"].append({"flag": "cut_at_length_limit", "diagnostic_only": True})
    # the relationship's structure: a wording that changes its subject, target, direction, relation or answer form is a
    # semantic conflict, whatever the lexical checks say
    diag["relation"], diag["identity_introduced"] = None, False
    if child.get("relation_contract"):
        rel = relations.conformance(child["relation_contract"], child["question"])
        diag["relation"] = rel
        for v in rel["violations"]:
            child["flags"].append({"flag": "relationship_changed", "kind": v["kind"], "note": v["note"]})
        for r_ in rel["review"]:
            child["flags"].append({"flag": "semantic_review_required", "kind": r_["kind"], "note": r_["note"]})
    for ref in [by_id[i] for i in child.get("context_referents", [])]:
        if relations.copular_identity(child["question"], ref["text"]):
            diag["identity_introduced"] = True
            child["flags"].append(
                {
                    "flag": "identity_introduced",
                    "note": f'the wording equates an item with the subject "{ref["text"]}" with a bare copula; the request never says that',
                }
            )
    diag["relationship_introduced"] = None
    if not child.get("relation_contract"):
        words = " ".join(by_id[i]["text"] for i in [*child["owns"], *child["carries_shared"]])
        frag_plan = next((p for p in plans or [] if p["child_id"] == child["child_id"]), None)
        if frag_plan is not None and frag_plan.get("clarified_fragment"):
            # a fragment continues another question: that question's relationship is CONTEXT it may carry (asking the ancestor's
            # question again is caught separately by the protected question words), not one the fragment introduces
            words += " " + " ".join(
                e["text"] for o in _inherited_extracts(parent, frag_plan, plans, by_id) for e in o["entries"]
            )
        diag["relationship_introduced"] = relations.introduced_relation(child["question"], words)
        if diag["relationship_introduced"]:
            child["flags"].append(
                {
                    "flag": "relationship_introduced",
                    "note": f'the wording states a relationship ("{diag["relationship_introduced"]["verb"]}") that the request does not attach to this item; any relationship the request states is asked by the child that owns it',
                }
            )
    diag["source_edit"] = {"conflict": [], "review": [], "pending": [], "notes": [], "findings": []}
    expected_unresolved = 0
    plan = next((p for p in plans or [] if p["child_id"] == child["child_id"]), None)
    if plan is not None:
        ctx = child_context(
            parent, plan, by_id, plans=plans, governing_operation=child.get("extract_mode") == "governing"
        )
        led = ledger.build(parent, child, plan, plans, ctx, by_id)
        child["edit_ledger"] = led
        diag["source_edit"]["gap"] = []
        # a wording that IS the deterministic scaffold: the words the scaffold supplied by rule (and the fragment-to-question change it makes on
        # purpose) are explained by its recorded pieces, so the ledger's "no recorded span supplies it" findings about exactly those words are not
        # treated as the writer's additions; the scaffold's own pending items are what wait for the researcher instead
        scaffold = (child.get("preparation") or {}).get("scaffold") or {}
        verbatim = bool(scaffold.get("built")) and structure.normalize(child["question"]) == structure.normalize(
            scaffold["text"]
        )
        rule_words = (
            {t for p in scaffold["pieces"] if p["origin"] == "rule" for t in lx.tokens(p["text"])}
            if verbatim
            else set()
        )
        for f in led["flags"]:
            if (
                verbatim
                and f["class"] in ("conflict", "review")
                and (
                    f["kind"] == "request_form_changed"
                    or (
                        f["kind"] in ("relation_word_added", "operator_added")
                        and {w.lower() for w in f["words"] or []} <= rule_words
                    )
                )
            ):
                child["flags"].append(
                    {
                        "flag": "explained_by_scaffold",
                        "kind": f["kind"],
                        "words": f["words"],
                        "note": "the wording is exactly the deterministic scaffold, whose recorded pieces supply these words by rule; the scaffold's own pending items still wait for the researcher",
                        "informational": True,
                    }
                )
                continue
            if f["class"] == "gap":
                diag["source_edit"]["gap"].append(f["kind"])
                child["flags"].append({"flag": f["kind"], "words": f["words"], "note": f["note"], "source_gap": True})
            if f["class"] in ("conflict", "review"):
                child["flags"].append({"flag": f["kind"], "words": f["words"], "note": f["note"], "source_edit": True})
                diag["source_edit"][f["class"]].append(f["kind"])
                diag["source_edit"]["notes"].append(f["note"])
                diag["source_edit"]["findings"] += [f"{f['kind']}:{w}" for w in (f["words"] or [""])]
            if f["class"] == "pending":
                child["flags"].append(
                    {"flag": f["kind"], "words": f["words"], "note": f["note"], "pending_confirmation": True}
                )
                diag["source_edit"]["pending"].append(f["kind"])
        if verbatim and scaffold.get("pending"):
            child["flags"].append(
                {
                    "flag": "scaffold_pending_confirmation",
                    "words": [p["kind"] for p in scaffold["pending"]],
                    "note": "the deterministic scaffold has parts the engine inferred or supplied that the researcher has not confirmed: "
                    + "; ".join(p["reason"] for p in scaffold["pending"]),
                    "pending_confirmation": True,
                }
            )
            diag["source_edit"]["pending"].append("scaffold_pending_confirmation")
        child["unresolved_links"] = led["unresolved"]
        expected_unresolved = len(ctx["unresolved"]) + len(led["unresolved"])
        for limit in led.get("verification_limits", []):
            child["flags"].append({"flag": "lexical_check_limit", "note": limit, "informational": True})
        child["human_review_required"] = bool(led.get("human_review_required"))
        if child["human_review_required"]:
            child["flags"].append(
                {
                    "flag": "human_review_required",
                    "note": "the researcher kept a human read of this relationship or pairing; no lexical check replaces it",
                    "informational": True,
                }
            )
        if ctx["subject"]:
            stems = lx.content_stems(ctx["subject"][0]["text"])
            if lx.coverage_fraction(stems, lx.content_stems(" ".join(e["text"] for e in ctx["extract"]))) < 0.6:
                child["flags"].append(
                    {
                        "flag": "background_subject_scope_unverified",
                        "note": f'the request has ONE derived background subject ("{ctx["subject"][0]["text"]}", from the first source unit only). '
                        "It is offered to every question but nothing shows it applies to this one: a request about several unrelated subjects is not modelled",
                        "informational": True,
                    }
                )
    structure_review = False
    for finding in structure.findings(child):
        child["flags"].append(
            {
                "flag": finding["flag"],
                "words": finding.get("words") or finding.get("words_added"),
                "note": finding["note"],
                "structure_review": True,
            }
        )
        structure_review = True
    acceptance = output_acceptance(child, expected_unresolved)
    child["output_acceptance"] = acceptance
    for item in acceptance["findings"]:
        child["flags"].append({"flag": item["flag"], "note": item["note"], "output_acceptance": item["level"]})
        if item["level"] == "hard":
            diag["hard_fail"] = True
    conflict = (
        bool(diag["relation"] and diag["relation"]["violations"])
        or diag["identity_introduced"]
        or bool(diag["source_edit"]["conflict"])
    )
    if conflict:
        diag["hard_fail"] = True
    tokens = set(lx.tokens(child["question"]))
    declared = {str(d.get("word", "")).strip().lower(): d for d in child.get("declared_unresolved") or []}
    for a in touching_ambiguities(parent, [*child["owns"], *child["carries_shared"]], by_id):
        child["interpretations"].append(
            {
                "kind": "depends_on_open_ambiguity" if not a.get("clarification") else "clarified_ambiguity",
                "ambiguity_id": a["id"],
                "text": a["text"],
                "alternatives": a.get("alternatives") or [],
                "status": "reading_not_established" if not a.get("clarification") else "resolved_by_user_clarification",
            }
        )
    for a in checks.reference_words_in(parent, [*child["owns"], *child["carries_shared"]], by_id):
        if a["text"].lower() in tokens:
            continue
        c = clar.covering(parent, a["spans"][0])
        if c:
            child["interpretations"].append(
                {
                    "kind": "reference_resolved_by_user_clarification",
                    "ambiguity_id": a["id"],
                    "original_text": a["text"],
                    "original_span": a["spans"][0],
                    "status": "approved_by_user",
                    "clarification": c["id"],
                    "means": c["means"],
                }
            )
            continue
        d = declared.get(a["text"].lower())
        child["interpretations"].append(
            {
                "kind": "reference_resolved_by_rewrite",
                "ambiguity_id": a["id"],
                "original_text": a["text"],
                "original_span": a["spans"][0],
                "status": "assumed_not_approved",
                "declared_by_writer": bool(d),
                "reading_used": d.get("reading_used") if d else None,
                "other_readings": d.get("other_readings") if d else [],
                "note": "the reference word is absent from this child: the wording adopted a reading the request does not establish",
            }
        )
    if conflict:
        child["status"] = "semantic_conflict"
    elif acceptance["constraint_failure"]:
        child["status"] = "output_constraint_failure"
    elif any(i["kind"] == "reference_resolved_by_rewrite" for i in child["interpretations"]):
        child["status"] = "conditional_on_unresolved_reading"
    elif (
        diag["relationship_introduced"]
        or structure_review
        or diag["source_edit"]["review"]
        or (diag["relation"] and diag["relation"]["status"] in ("review_required", "not_verifiable"))
        or acceptance["review"]
    ):
        child["status"] = "semantic_review_required"
    elif diag["source_edit"].get("gap"):
        # the source (with the approved clarifications) does not settle how to make this runnable on its own: that is a
        # finding about the REQUEST, kept apart from a writer failure, and it waits for the researcher's decision
        child["status"] = "source_gap"
    elif diag["source_edit"]["pending"]:
        # nothing is wrong that the checks can see, but the wording relies on a permission the researcher has not confirmed: a
        # QUALIFIED result, never an unqualified clean one
        child["status"] = "pending_researcher_confirmation"
    return child


def output_acceptance(child: dict, expected_unresolved: int) -> dict:
    """ONE acceptance rule for the writer's output, shared by every prompt variant: how the call ended, whether it parsed, whether the
    request reached its length limit, and whether the unresolved list is saturated. Nothing is shortened to fit.

    * a live call that did not report ``stop`` is never treated as a confirmed normal stop (scripted and replayed calls legitimately
      lack the metadata and are reported as such, not as confirmed);
    * ``length`` (or a field at its limit) is a hard failure: the wording may be cut off;
    * a FULL unresolved list is not proof of truncation, so it is status-bearing (review), unless the engine positively knows more
      items had to be reported than the schema allows: then it is a constraint failure."""
    budget = child.get("output_budget") or {}
    limits = child.get("output_limits") or {}
    findings: list[dict] = []
    stop = budget.get("stop_state")
    if budget.get("truncated"):
        findings.append(
            {
                "flag": "output_truncated",
                "level": "hard",
                "note": "the model ran out of output budget (done_reason=length); the wording may be cut off",
            }
        )
    elif stop == "unconfirmed_live":
        findings.append(
            {
                "flag": "output_stop_reason_unconfirmed",
                "level": "review",
                "note": f"a live model call ended with stop reason {budget.get('stop_reason')!r}, not a confirmed normal stop; the output cannot be presumed complete",
            }
        )
    if budget.get("question_at_limit"):
        findings.append(
            {
                "flag": "output_question_at_limit",
                "level": "hard",
                "note": "the question reached the schema's length limit and may have been cut off",
            }
        )
    if budget.get("field_at_limit"):
        findings.append(
            {
                "flag": "output_field_at_limit",
                "level": "hard",
                "note": "an unresolved field reached its schema length limit and may have been cut off",
            }
        )
    constraint = False
    if budget.get("unresolved_at_capacity"):
        omitted = expected_unresolved > limits.get("unresolved_max", 10**9)
        constraint = omitted
        findings.append(
            {
                "flag": "output_unresolved_omitted" if omitted else "unresolved_list_at_capacity",
                "level": "hard" if omitted else "review",
                "note": (
                    f"{expected_unresolved} unresolved items had to be reported but the schema allows {limits.get('unresolved_max')}: items were necessarily omitted"
                    if omitted
                    else "the unresolved list is full; this is not proof that items were omitted, but the report cannot be presumed complete"
                ),
            }
        )
    return {
        "stop_reason": budget.get("stop_reason"),
        "stop_state": stop,
        "parse_valid": budget.get("parse_valid", True),
        "final_chars": budget.get("final_chars"),
        "question_max": limits.get("question_max"),
        "findings": findings,
        "constraint_failure": constraint,
        "review": any(f["level"] == "review" for f in findings),
    }


def write_child(
    log: CallLog,
    parent: dict,
    plan: dict,
    by_id: dict,
    *,
    pass_no: int,
    prompt: str | None = None,
    task: str = "children.write",
    settings: dict | None = None,
    plans: list[dict] | None = None,
) -> dict:
    settings = settings or V3_SETTINGS
    if plan["kind"] in (
        "unit_level",
        "elliptical",
    ):  # not written: exact words retained, unresolved (no model call spent)
        kind = "unit_level" if plan["kind"] == "unit_level" else "unresolved_elliptical"
        return _new_child(
            parent,
            plan,
            by_id,
            _exact_words(parent, plan, by_id),
            kind=kind,
            pass_no=pass_no,
            produced_by="deterministic",
            style="not_written",
            settings=settings,
        )
    if settings.get("preflight"):
        blocked = _constraint_failure(parent, plan, by_id, plans, settings)
        if blocked:
            child = _new_child(
                parent,
                plan,
                by_id,
                blocked.pop("extract_text"),
                kind="constraint_failure",
                pass_no=pass_no,
                produced_by="deterministic",
                style="preflight",
                settings=settings,
            )
            child["constraint"] = blocked
            return child
    prompt = prompt or settings["render"](parent, plan, plans, by_id)
    try:
        call = log.call(task, prompt, settings["schema"], settings["cap"], unit_id=plan["child_id"])
    except CallCapReached:
        child = _new_child(
            parent,
            plan,
            by_id,
            by_id[plan["anchor_id"]]["text"],
            kind="fallback",
            pass_no=pass_no,
            produced_by="deterministic",
            style=task,
            settings=settings,
        )
        child["flags"].append({"flag": "call_cap_reached"})
        return child
    text = call.parsed.get("question") if isinstance(call.parsed, dict) else None
    if not isinstance(text, str) or not text.strip():
        child = _new_child(
            parent,
            plan,
            by_id,
            by_id[plan["anchor_id"]]["text"],
            kind="fallback",
            pass_no=pass_no,
            produced_by="deterministic",
            style=task,
            settings=settings,
        )
        child["fallback_reason"] = call.failure_reason or "no usable question"
        if call.truncated:
            child["flags"].append({"flag": "output_truncated", "note": "the model ran out of output budget"})
        return child
    child = _new_child(
        parent,
        plan,
        by_id,
        text.strip(),
        kind="generated",
        pass_no=pass_no,
        produced_by=log.model.label,
        style=task,
        settings=settings,
    )
    child["model_raw"] = {
        "response_text": call.raw_text,
        "question_as_returned": text,
        "whitespace_stripped": text != text.strip(),
        "note": "the model's exact response; `question` is this string with only surrounding whitespace removed",
    }
    if settings.get(
        "prepare"
    ):  # the deterministic edits the writer was given, recorded APART from what the model returned
        child["preparation"] = settings["prepare"](parent, plan, plans, by_id)
    raw = call.parsed.get("unresolved") if isinstance(call.parsed, dict) else None
    child["declared_unresolved"] = [d for d in raw or [] if isinstance(d, dict) and isinstance(d.get("word"), str)]
    limits = child["output_limits"]
    live = call.mode not in OFFLINE_MODES
    stop = getattr(call, "done_reason", None)
    child["output_budget"] = {
        "call_mode": call.mode,
        "live_call": live,
        "stop_reason": stop,
        "stop_state": (
            "not_applicable_offline"
            if not live
            else "confirmed_stop"
            if stop == "stop"
            else "length"
            if stop == "length" or call.truncated
            else "unconfirmed_live"
        ),
        "parse_valid": bool(call.schema_ok),
        "final_chars": len(text),
        "truncated": bool(call.truncated),
        "question_at_limit": len(text) >= limits["question_max"] - 5,
        "unresolved_at_capacity": isinstance(raw, list) and len(raw) >= limits["unresolved_max"],
        "field_at_limit": any(
            len(str(d.get(k, ""))) >= n
            for d in child["declared_unresolved"]
            for k, n in (("word", limits.get("word_max", 10**9)), ("reading_used", limits.get("reading_max", 10**9)))
        ),
    }
    if settings.get("preflight"):
        child["preflight"] = {
            k: v for k, v in preflight_sizes(parent, plan, by_id, plans, settings).items() if k != "extract_text"
        }
    return child


def preflight_sizes(parent: dict, plan: dict, by_id: dict, plans: list[dict] | None, settings: dict) -> dict:
    """How long the request must be, split by how sure we are that the wording is needed:

    * ``indispensable``: the extract plus the words that a required clarified reference must be replaced by (the reference word
      cannot stand alone). If even this exceeds the limit the request demonstrably cannot fit.
    * ``expected_additional``: context the request MAY need (the subject and its approved joining words, a fragment's inherited
      context). It is a maximum, not a requirement: it never fails a request by itself; the actual output is validated instead."""
    ctx = child_context(
        parent, plan, by_id, plans=plans, governing_operation=settings.get("extract_mode") == "governing"
    )
    text = " ".join(e["text"] for e in ctx["extract"])
    extract_stems = lx.content_stems(text)
    growth = 0
    for c in ctx["clarified"]:
        clar = next((x for x in parent["clarifications"] if x["id"] == c["clarification"]), None)
        ant = (clar or {}).get("refers_to")
        if (
            clar
            and clar["kind"] == "reference"
            and ant
            and lx.missing_stems(lx.content_stems(ant["text"]), extract_stems)
        ):
            growth += max(0, len(ant["text"]) - len(c["word"]))
    subject = ctx["subject"][0]["text"] if ctx["subject"] else None
    expected = 0
    if subject and lx.coverage_fraction(lx.content_stems(subject), extract_stems) < 0.6 and ctx["link"]:
        expected += len(subject) + len(ctx["link"]["text"]) + 2
    for owner in ctx["inherited_extracts"]:
        expected += sum(len(e["text"]) for e in owner["entries"])
    limit = settings["limits"]["question_max"] - 5
    return {
        "extract_chars": len(text),
        "indispensable_growth_chars": growth,
        "indispensable_chars": len(text) + growth,
        "expected_additional_chars": expected,
        "limit_chars": settings["limits"]["question_max"],
        "may_exceed_limit_if_all_expected_context_is_added": len(text) + growth + expected > limit,
        "extract_text": text,
        "unresolved_needed": len(ctx["unresolved"]),
    }


def _constraint_failure(parent: dict, plan: dict, by_id: dict, plans: list[dict] | None, settings: dict) -> dict | None:
    """A request that demonstrably cannot fit the configured output limits is REPORTED, never shortened to fit and never sent. Only
    the INDISPENSABLE wording counts: an over-inclusive estimate of optional context is recorded but never fails a request."""
    sizes = preflight_sizes(parent, plan, by_id, plans, settings)
    limits = settings["limits"]
    room = limits["question_max"] - 5
    if sizes["extract_chars"] > room:
        return {
            "constraint": "question_length",
            "needed_chars": sizes["extract_chars"],
            "limit_chars": limits["question_max"],
            "extract_text": sizes["extract_text"],
            "sizes": sizes,
        }
    if sizes["indispensable_chars"] > room:
        return {
            "constraint": "restored_question_length",
            "needed_chars": sizes["indispensable_chars"],
            "limit_chars": limits["question_max"],
            "extract_text": sizes["extract_text"],
            "sizes": sizes,
        }
    if sizes["unresolved_needed"] > limits["unresolved_max"]:
        return {
            "constraint": "unresolved_capacity",
            "needed_items": sizes["unresolved_needed"],
            "limit_items": limits["unresolved_max"],
            "extract_text": sizes["extract_text"],
            "sizes": sizes,
        }
    return None


def passthrough_child(parent: dict, plan: dict, by_id: dict, decision: dict, settings: dict) -> dict:
    """The original request, exactly as written, as the ONE child of a request that needs no decomposition. No writer call is made,
    and nothing is answered: ``downstream`` says the request still runs once through the normal Ask path."""
    child = _new_child(
        parent,
        plan,
        by_id,
        parent["original_question"],
        kind="passthrough",
        pass_no=1,
        produced_by="deterministic",
        style="passthrough",
        settings=settings,
    )
    child["decision"] = {k: decision[k] for k in ("outcome", "basis", "checks")}
    child["downstream"] = dict(decision["downstream"])
    return child


def build_pass(
    log: CallLog,
    parent: dict,
    settings: dict | None = None,
    only: list[str] | None = None,
    *,
    decision: dict | None = None,
    plans: list[dict] | None = None,
) -> dict:
    """``decision`` (from ``passthrough.decide``) with outcome ``no_decomposition_needed`` replaces the whole writing stage by the
    original request itself; any other decision, or none, runs the existing per-anchor path unchanged."""
    by_id = by_id_map(parent)
    plans = plans if plans is not None else plan_children(parent)
    settings = settings or V3_SETTINGS
    children = []
    if decision and decision["outcome"] == "no_decomposition_needed" and only is None:
        child = passthrough_child(parent, plans[0], by_id, decision, settings)
        annotate(parent, child, by_id, plans)
        return {"pass": 1, "plans": plans, "children": [child], "decision": decision}
    for plan in plans:
        if only is not None and plan["child_id"] not in only:
            child = _new_child(
                parent,
                plan,
                by_id,
                _exact_words(parent, plan, by_id),
                kind="not_selected",
                pass_no=1,
                produced_by="deterministic",
                style="not_selected",
                settings=settings,
            )
        else:
            child = write_child(log, parent, plan, by_id, pass_no=1, settings=settings, plans=plans)
        kept = list(child["flags"])
        annotate(parent, child, by_id, plans)
        child["flags"] = kept + [f for f in child["flags"] if f not in kept]
        children.append(child)
    return {"pass": 1, "plans": plans, "children": children, "decision": decision}


# ---- repair --------------------------------------------------------------------------------------------------------------


def _problems(diag: dict, by_id: dict) -> list[str]:
    out = []
    for i in diag["lost"]:
        r = by_id[i]
        note = diag["preservation"][i].get("note")
        hint = {
            "polarity": " (it must be a yes/no question about that item)",
            "existence": " (it must be a yes/no question)",
            "manner": " (it must ask how, about that same item)",
            "kinds": " (it must ask which kinds)",
        }.get(r["kind"], "")
        out.append(f'The question does not properly ask: "{r["text"]}"{hint}.' + (f" {note}." if note else ""))
    if diag["unsupported_additions"]:
        out.append(
            f"It adds words that are not in the request: {', '.join(sorted(set(diag['unsupported_additions'])))}."
        )
    if diag["deixis"]:
        out.append(
            f"It still refers to something outside itself ({', '.join(diag['deixis'])}); say what it refers to and report that reading under unresolved."
        )
    if diag["silent_resolution"]:
        out.append(
            f"It resolved {', '.join(diag['silent_resolution'])} without reporting it; report the reading used under unresolved."
        )
    if diag["copies_of_source_text"]:
        out.append("It repeats the request text; write it as a standalone question.")
    if diag["bundled_list"] or diag["possible_bundling_of_other_obligations"]:
        out.append("It asks for other things as well; ask ONLY the owned items.")
    if diag["at_schema_length_limit"]:
        out.append("It is too long and was cut off; make it shorter.")
    for v in (diag.get("relation") or {}).get("violations", []):
        out.append(f"It changes the relationship ({v['kind']}): {v['note']}. Restore it exactly.")
    if diag.get("identity_introduced"):
        out.append("It equates an item with the subject; ask what relates to the subject instead.")
    if diag.get("relationship_introduced"):
        out.append(
            f'It states a relationship ("{diag["relationship_introduced"]["verb"]}") the request does not attach to this item; ask only the owned items.'
        )
    out += [
        f"{note.rstrip('.')}. Return to the researcher's own wording."
        for note in (diag.get("source_edit") or {}).get("notes", [])
    ]
    return out


def repair_prompt(parent: dict, plan: dict, by_id: dict, current: str, problems: list[str]) -> str:
    plain = "\n".join(f"- {p}" for p in problems)
    return (
        "You previously wrote ONE standalone question from a few things a longer request asks for. A plain check found problems.\n\n"
        "Write the question again so it fixes ONLY these problems and STILL asks every owned item. Do not drop any owned item to fix a problem.\n"
        f"Problems found:\n{plain}\n\nCurrent question: {current}\n\n"
        + context_block(parent, plan, by_id)
        + '\n\nReturn only JSON: {"question":"...","unresolved":[{"word":"...","reading_used":"...","other_readings":["..."]}]}'
    )


def repair_pass(log: CallLog, parent: dict, pass1: dict, settings: dict | None = None) -> dict:
    """At most ONE bounded repair attempt per flagged child, stored separately; the first pass is never modified.

    A repair replaces a child only if it loses no obligation the first pass preserved (polarity and manner must stay
    attached to what they qualify), resolves no referent silently, acquires nothing, AND resolves a flag
    (``checks.repair_acceptable``). Accepted repairs are still only candidates pending human review. When the call
    budget runs out the remaining children are recorded as not attempted."""
    by_id = by_id_map(parent)
    plans = {p["child_id"]: p for p in pass1["plans"]}
    children = copy.deepcopy(pass1["children"])
    todo = []
    for c in children:
        if c["kind"] == "fallback" and not any(f["flag"] == "call_cap_reached" for f in c["flags"]):
            reasons = ["exact_source_text_fallback"]
        else:
            reasons = checks.repair_reasons(c["diagnostics"]) if c["diagnostics"] else []
        if reasons:
            todo.append((c, reasons))
    todo.sort(key=lambda t: -len(t[1]))
    repairs = []
    for child, reasons in todo:
        left = log.remaining()
        if left is not None and left <= 0:
            repairs.append(
                {
                    "child_id": child["child_id"],
                    "reasons": reasons,
                    "attempted": False,
                    "accepted": False,
                    "rejected_reason": "call budget exhausted",
                }
            )
            continue
        plan = plans[child["child_id"]]
        before = child["diagnostics"]
        problems = _problems(before, by_id) if before else ["No usable question was written; write one."]
        record = {
            "child_id": child["child_id"],
            "reasons": reasons,
            "problems": problems,
            "before": child["question"],
            "attempted": True,
            "produced_by": log.model.label,
        }
        new = write_child(
            log,
            parent,
            plan,
            by_id,
            pass_no=2,
            prompt=repair_prompt(parent, plan, by_id, child["question"], problems),
            task="children.repair",
            settings=settings,
            plans=list(plans.values()),
        )
        record["call_seq"] = log.records[-1]["seq"] if log.records else None
        record["after"] = new["question"]
        if new["kind"] == "fallback":
            record.update(accepted=False, rejected_reason=new.get("fallback_reason") or "no usable question")
        else:
            annotate(parent, new, by_id, list(plans.values()))
            if child["kind"] == "fallback":
                ok, why = (
                    (not new["diagnostics"]["hard_fail"]),
                    "replaces a fallback with a usable rewrite (lexical + attachment checks only)",
                )
            else:
                ok, why = checks.repair_acceptable(before, new["diagnostics"])
            record.update(
                accepted=ok,
                rejected_reason=None if ok else why,
                acceptance_basis=why if ok else None,
                pending_human_review=ok,
                after_diagnostics=new["diagnostics"],
                declared_unresolved=new["declared_unresolved"],
            )
            if ok:
                new["repaired_from"] = child["question"]
                new["pending_human_review"] = True
                children[children.index(child)] = new
        repairs.append(record)
    return {"pass": 2, "plans": pass1["plans"], "children": children, "repairs": repairs}


def score_candidates(
    parent: dict,
    plans: list[dict],
    candidates: dict,
    *,
    pass_no: int = 1,
    produced_by: str = "recorded",
    extract_mode: str = "v3",
) -> dict:
    """Score RECORDED wording candidates ({child_id: {"question", "unresolved"}}) under the current contracts and checks,
    with no model call. A plan with no candidate becomes a fallback; unresolved kinds are never written."""
    by_id = by_id_map(parent)
    children = []
    for plan in plans:
        if plan["kind"] in ("unit_level", "elliptical"):
            child = write_child(None, parent, plan, by_id, pass_no=pass_no)
        elif plan["child_id"] in candidates:
            cand = candidates[plan["child_id"]]
            child = _new_child(
                parent,
                plan,
                by_id,
                cand["question"],
                kind="generated",
                pass_no=pass_no,
                produced_by=produced_by,
                style="recorded",
                extract_mode=extract_mode,
            )
            child["declared_unresolved"] = [
                d for d in cand.get("unresolved") or [] if isinstance(d, dict) and isinstance(d.get("word"), str)
            ]
        else:
            child = _new_child(
                parent,
                plan,
                by_id,
                by_id[plan["anchor_id"]]["text"],
                kind="fallback",
                pass_no=pass_no,
                produced_by="deterministic",
                style="recorded",
                extract_mode=extract_mode,
            )
            child["flags"].append({"flag": "no_recorded_candidate"})
        kept = list(child["flags"])
        annotate(parent, child, by_id, plans)
        child["flags"] = kept + [f for f in child["flags"] if f not in kept]
        children.append(child)
    return {"pass": pass_no, "plans": plans, "children": children}
