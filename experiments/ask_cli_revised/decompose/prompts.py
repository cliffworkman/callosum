"""Prompt variants for the child writer: ``corrected-full`` and ``lean`` (the frozen ``v3`` prompt stays in ``children.py``).

Both variants render the SAME substance. ``substance()`` gathers everything the writer is allowed to know about one child (its
source extract, the context it may use, the approved clarifications that touch it, the relationship it must keep, the pairs
it must keep together, the limits it must fit) and each renderer only PRESENTS it. So a comparison between them varies
presentation and length, never what the writer has been told or which protections apply. ``SAFEGUARDS`` is the one registry of
protections; each variant carries every safeguard that applies to a child.

The writer's remaining job is small: keep the researcher's wording and request form, make only the edits needed for the
request to stand alone, and report meaning nobody has settled. Everything else (which threads exist, who owns what, nesting,
relationship parsing, the extract, clarification matching, and the acceptance checks) is deterministic code, done before or
after the call.
"""

from __future__ import annotations

import copy
import math

from experiments.ask_cli_revised.decompose import children as ch
from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.request_contract import _sentence_spans

# ---- one matched schema and generation budget for BOTH variants (the shape of ``CHILD_SCHEMA``; only the limits differ) ------------------
MATCHED_LIMITS = {"question_max": 600, "unresolved_max": 3, "word_max": 60, "reading_max": 60, "other_max": 60}


def _matched_schema(limits: dict) -> dict:
    schema = copy.deepcopy(ch.CHILD_SCHEMA)
    props = schema["properties"]
    props["question"]["maxLength"] = limits["question_max"]
    props["unresolved"]["maxItems"] = limits["unresolved_max"]
    item = props["unresolved"]["items"]["properties"]
    item["word"]["maxLength"] = limits["word_max"]
    item["reading_used"]["maxLength"] = limits["reading_max"]
    item["other_readings"]["maxItems"] = 2
    item["other_readings"]["items"]["maxLength"] = limits["other_max"]
    return schema


MATCHED_SCHEMA = _matched_schema(MATCHED_LIMITS)


def schema_max_chars(schema: dict) -> int:
    """The longest JSON text the schema permits, counting every string character once (no escapes, no whitespace)."""

    def size(node: dict, name: str | None = None) -> int:
        key = len(name) + 4 if name is not None else 0  # "name":
        kind = node.get("type")
        if kind == "string":
            return key + 2 + node["maxLength"]
        if kind == "array":
            n = node["maxItems"]
            return key + 2 + n * size(node["items"]) + max(0, n - 1)
        inner = [size(v, k) for k, v in node["properties"].items()]
        return key + 2 + sum(inner) + max(0, len(inner) - 1)

    return size(schema)


def schema_output_budget(schema: dict) -> dict:
    """The output budget the schema implies. These are ESTIMATES: characters per token depend on the tokenizer and the
    text, and JSON escapes can lengthen a string, so no token count here is a guaranteed bound. Truncation is therefore
    DETECTED at run time (done_reason=length, a field at its limit, a full unresolved list), never assumed away."""
    chars = schema_max_chars(schema)
    return {
        "max_chars": chars,
        "tokens_at_2_5_chars_per_token": math.ceil(chars / 2.5),
        "tokens_at_1_5_chars_per_token": math.ceil(chars / 1.5),
    }


_BUDGET = schema_output_budget(MATCHED_SCHEMA)
# comfortably above even the pessimistic estimate (1.5 chars per token), rounded up to a multiple of 256
MATCHED_OUTPUT_CAP = math.ceil(_BUDGET["tokens_at_1_5_chars_per_token"] * 1.15 / 256) * 256
MATCHED_LIMITS = {**MATCHED_LIMITS, "cap": MATCHED_OUTPUT_CAP}


# ---- safeguards: one registry, both variants -----------------------------------------------------------------------------------------------
# id -> {"full": (marker, text), "lean": (marker, text), "when": None | "relationship"}
SAFEGUARDS = {
    "FORM": {
        "full": (
            "request FORM",
            'Keep the researcher\'s wording and request FORM. An imperative (for example "please return X") stays an imperative; a '
            'question stays a question; a "whether" clause stays as written. Do not turn an imperative or a clause into a question, '
            'and do not add a final "?" to a request that has none.',
        ),
        "lean": (
            "request form",
            "Keep the researcher's wording and request form: an imperative stays an imperative, a question a question, a "
            '"whether" clause as written. Add no final "?".',
        ),
    },
    "EDITS": {
        "full": (
            "Allowed edits",
            "Allowed edits, in order of preference: (1) copy exact source words; (2) leave out words that belong to other questions; "
            "(3) restore context the request needs by copying its exact words; (4) fix capitalization, punctuation and grammar "
            "(an inflection, a typo) without changing what a word means; (5) replace a reference word by the exact words a NAMED "
            "clarification says it points at.",
        ),
        "lean": (
            "Allowed edits",
            "Allowed edits only: capitalization, punctuation, grammar; copy the context above if the extract cannot stand alone; "
            "replace a clarified reference with its exact words.",
        ),
    },
    "NO_LINK": {
        "full": (
            "connecting word",
            "Do not add a connecting word (in, of, for, about, with, to, and, or...) or any relation between two things unless the "
            "source or a named clarification supplies it. If the request does not say how an item relates to its subject, do not "
            'choose a relation: keep the source words and report the unstated link under "unresolved" (word = the words '
            'involved, reading_used = "none chosen").',
        ),
        "lean": (
            "connecting word",
            "Add no connecting word (in, of, for, about, with, to...) or relation unless the source or a clarification's cited "
            'words give it. If a needed link is not given, leave the extract as written and list the link under "unresolved" '
            '(reading_used = "none chosen").',
        ),
    },
    "PROTECTED": {
        "full": (
            "question word and qualifier",
            "Keep every question word and qualifier the researcher used (whether, how, which, what kind of, any, effective, "
            "not...) and add none: whether stays whether, how stays how, which/what stays which/what, negation is neither added "
            "nor removed.",
        ),
        "lean": (
            "question word and qualifier",
            "Keep every question word and qualifier (whether, how, which, what kind of, any, effective, not); add or drop none.",
        ),
    },
    "RELATION": {
        "when": "relationship",
        "full": (
            "keep its subject, relation, target",
            "If a relationship is listed, keep its subject, relation, target and direction exactly as parsed, and keep what it asks "
            "(whether, how, which kinds). Never swap subject and target and never replace either.",
        ),
        "lean": (
            "Keep the relationship",
            "Keep the relationship above exactly: subject, relation, target, direction, and what it asks.",
        ),
    },
    "UNRESOLVED": {
        "full": (
            "not clarified",
            'If a reference word is not clarified, keep it exactly as written and report it under "unresolved" (reading_used = '
            '"none chosen"). Never replace it with a guess, even when one reading seems obvious.',
        ),
        "lean": (
            "unclarified reference",
            'An unclarified reference stays as written: list it under "unresolved"; never guess its meaning.',
        ),
    },
    "NO_PASTE": {
        "full": (
            "never quote, paraphrase or paste",
            "A clarification tells you what the researcher meant. Use only the exact words it cites (the request words it points "
            "at, or the joining words it names); never quote, paraphrase or paste its explanation into the request.",
        ),
        "lean": ("never copy its explanation", "Use only the words a clarification cites; never copy its explanation."),
    },
    "SCOPE": {
        "full": (
            "Ask ONLY",
            "Ask ONLY the items this request owns. Context is there so the request stands alone; do not add requirements, topics, "
            "populations, comparisons or methods from it, and do not ask again what another question asks.",
        ),
        "lean": (
            "Ask only what this extract asks",
            "Ask only what this extract asks; do not add topics or restate the question it continues.",
        ),
    },
}


def applicable_safeguards(sub: dict) -> list[str]:
    return [k for k, v in SAFEGUARDS.items() if v.get("when") != "relationship" or sub["relationship"]]


# ---- substance -------------------------------------------------------------------------------------------------------------------------------
def _join_extract(parent: dict, entries: list[dict]) -> list[str]:
    """The extract's entries as source-order lines: entries from one sentence are joined by a space (exact words only)."""
    sents = _sentence_spans(parent["original_question"])
    lines: list[tuple[int, str]] = []
    for e in entries:
        idx = next((i for i, (a, b) in enumerate(sents) if a <= e["span"][0] < b), -1)
        if lines and lines[-1][0] == idx:
            lines[-1] = (idx, lines[-1][1] + " " + e["text"])
        else:
            lines.append((idx, e["text"]))
    return [text for _, text in lines]


def _annotated(parent: dict, entries: list[dict]) -> str:
    """Exact source words with each CLARIFIED reference marked inline by the words it points at: ``its [= the bias, RC-3]``."""
    q = parent["original_question"]
    refs = [c for c in parent.get("clarifications", []) if c["kind"] == "reference" and c.get("refers_to")]
    parts = []
    for e in entries:
        for lo, hi in e.get("spans") or [e["span"]]:
            out, at = "", lo
            for c in sorted(
                (c for c in refs if lo <= c["target_span"][0] and c["target_span"][1] <= hi),
                key=lambda c: c["target_span"][0],
            ):
                out += q[at : c["target_span"][1]] + f" [= {c['refers_to']['text']}, {c['id']}]"
                at = c["target_span"][1]
            parts.append((out + q[at:hi]).strip())
    return " ".join(parts)


def substance(parent: dict, plan: dict, plans: list[dict], by_id: dict, *, use_proposed_briefs: bool = False) -> dict:
    ctx = ch.child_context(parent, plan, by_id, plans=plans, governing_operation=True)
    q = parent["original_question"]
    extract_lines = _join_extract(parent, ctx["extract"])
    extract_text = " ".join(extract_lines)
    subject = ctx["subject"][0]["text"] if ctx["subject"] else None
    stems = lx.content_stems(subject) if subject else []
    in_extract = bool(subject) and lx.coverage_fraction(stems, lx.content_stems(extract_text)) >= 0.6
    spans_in_extract = [tuple(s) for e in ctx["extract"] for s in (e.get("spans") or [e["span"]])]
    via_reference = any(
        c["kind"] == "reference"
        and c.get("refers_to")
        and lx.coverage_fraction(stems, lx.content_stems(c["refers_to"]["text"])) >= 0.6
        and any(lo <= c["target_span"][0] and c["target_span"][1] <= hi for lo, hi in spans_in_extract)
        for c in parent.get("clarifications", [])
    )
    if not subject or in_extract:
        context = {"state": "not_needed", "words": subject}
    elif via_reference:
        context = {"state": "via_reference", "words": subject}
    elif ctx["inherited_extracts"]:
        context = {"state": "via_inherited", "words": subject}
    elif ctx["link"]:
        context = {
            "state": "available_with_link",
            "words": subject,
            "link": ctx["link"]["text"],
            "link_from": ctx["link"]["clarification"],
        }
    else:
        context = {"state": "unstated_link", "words": subject}
    clarified, meanings = [], []
    for c in ctx["clarified"]:
        clar = next(x for x in parent["clarifications"] if x["id"] == c["clarification"])
        brief = clar.get("brief")
        text = c["means"]
        proposed = False
        if use_proposed_briefs and brief:
            text, proposed = brief["text"], brief["status"] != "approved"
        row = {
            "id": clar["id"],
            "on": q[clar["target_span"][0] : clar["target_span"][1]],
            "span": clar["target_span"],
            "means": text,
            "means_is_proposed_condensation": proposed,
            "points_at": (clar.get("refers_to") or {}).get("text"),
            "points_at_span": (clar.get("refers_to") or {}).get("span"),
            "adds": clar.get("adds", []),
            "link": (clar.get("context_link") or {}).get("text"),
        }
        (clarified if clar["kind"] == "reference" else meanings).append(row)
    rc = plan.get("relation")
    relationship = None
    if rc and rc.get("parse_status") == "parsed":
        s, t = rc["subject"], rc["target"]
        relationship = {
            "subject": s["text"],
            "subject_span": s["spans"][0],
            "subject_is": s.get("resolved_text"),
            "subject_unresolved": bool(s["is_reference"] and not s.get("resolved_text")),
            "relation": rc["relation"]["text"],
            "relation_span": rc["relation"]["spans"][0],
            "target": t["text"],
            "target_span": t["spans"][0],
            "target_refs": [
                {
                    "word": r["word"],
                    "means": r.get("means"),
                    "points_at": (r.get("antecedent") or {}).get("text"),
                    "id": r.get("clarification"),
                }
                for r in t["references"]
                if r["status"] == "clarified_by_user"
            ],
            "whether": rc["polarity"]["requested"],
            "whether_basis": rc["polarity"].get("basis"),
            "how": rc["manner"]["requested"],
            "how_basis": rc["manner"].get("basis"),
            "how_from": rc["manner"].get("clarification"),
            "answer_form": rc["answer_form"]["form"],
            "answer_marker": rc["answer_form"].get("marker"),
            "qualifications": [x["text"] for x in rc["qualifications"]],
        }
    inherited_subject = [
        {"words": i["text"], "span": i["spans"][0], "from": i["from_node"], "id": i.get("clarification")}
        for i in ctx["inherited"]
        if i["role"] == "subject_antecedent"
    ]
    continues = [
        {"from": o["from_node"], "text": _annotated(parent, o["entries"]), "spans": [e["span"] for e in o["entries"]]}
        for o in ctx["inherited_extracts"]
    ]
    unresolved_refs = [{"word": u["word"], "span": u["span"]} for u in ctx["unresolved"] if u["kind"] == "reference"]
    return {
        "child": plan["child_id"],
        "extract_lines": extract_lines,
        "extract_text": extract_text,
        "extract_entries": ctx["extract"],
        "governing": q[ctx["governing"][0] : ctx["governing"][1]] if ctx["governing"] else None,
        "context": context,
        "owned": [(i, by_id[i]) for i in ctx["owned"]],
        "shared": [(i, by_id[i]) for i in ctx["shared"]],
        "excerpts": ctx["excerpts"],
        "clarified_references": clarified,
        "meaning_clarifications": meanings,
        "relationship": relationship,
        "inherited_subject": inherited_subject,
        "continues": continues,
        "pairs": ctx["joint"],
        "unresolved_references": unresolved_refs,
        "limits": MATCHED_LIMITS,
        "uses_proposed_briefs": use_proposed_briefs
        and any(m["means_is_proposed_condensation"] for m in [*clarified, *meanings]),
    }


# ---- shared wording of the clarification lines (same words in both variants) -----------------------------------------------------------------
def _means_label(c: dict, *, capital: bool = False) -> str:
    if c["means_is_proposed_condensation"]:
        return "PROPOSED condensation, NOT approved"
    return "Approved meaning" if capital else "approved meaning"


def _relationship_facts(rel: dict) -> list[str]:
    asks = []
    if rel["whether"]:
        asks.append(
            "whether (yes/no)" + ("" if rel["whether_basis"] != "clarification" else " [added by a clarification]")
        )
    if rel["how"]:
        asks.append(
            "how"
            + (
                f" [added by clarification {rel['how_from']}; not in the source words]"
                if rel["how_basis"] == "clarification"
                else ""
            )
        )
    return asks


# ---- the corrected FULL renderer -------------------------------------------------------------------------------------------------------------
HEADER = (
    "You are writing ONE standalone request for a literature search, from a few things a longer request asks for. "
    "You are not shown the rest of the request."
)


def _line(n: int, r: dict) -> str:
    return f'{n}. [{r["kind"]}] "{r["text"]}" (chars {", ".join(f"{a}-{b}" for a, b in r["spans"])})'


def render_full(sub: dict) -> str:
    out = [
        "What this request must ask (its owned items, exact words from the source):\n"
        + "\n".join(_line(n, r) for n, (_, r) in enumerate(sub["owned"], 1))
    ]
    rel = sub["relationship"]
    if rel:
        lines = [
            "Relationship to keep, parsed from the source words. Keep the subject, the relation, the target and the direction exactly:"
        ]
        if rel["subject_is"]:
            lines.append(
                f'- subject: "{rel["subject"]}" (chars {rel["subject_span"][0]}-{rel["subject_span"][1]}), clarified by the researcher to point at the source words "{rel["subject_is"]}"'
            )
        elif rel["subject_unresolved"]:
            lines.append(
                f'- subject: "{rel["subject"]}" (chars {rel["subject_span"][0]}-{rel["subject_span"][1]}), an unclarified reference: keep it as written and report it'
            )
        else:
            lines.append(f'- subject: "{rel["subject"]}" (chars {rel["subject_span"][0]}-{rel["subject_span"][1]})')
        lines.append(f'- relation: "{rel["relation"]}" (chars {rel["relation_span"][0]}-{rel["relation_span"][1]})')
        lines.append(f'- target: "{rel["target"]}" (chars {rel["target_span"][0]}-{rel["target_span"][1]})')
        for r in rel["target_refs"]:
            lines.append(
                f'  - in the target, "{r["word"]}" is clarified ({r["id"]}) to point at the source words "{r["points_at"]}"'
            )
        lines.append(
            f"- what it asks: {' AND '.join(_relationship_facts(rel)) or 'nothing beyond the relationship itself'}; answer form: {rel['answer_form']}"
            + (f' ("{rel["answer_marker"]}")' if rel["answer_marker"] else "")
        )
        if rel["qualifications"]:
            lines.append("- qualifications: " + "; ".join(f'"{x}"' for x in rel["qualifications"]))
        out.append("\n".join(lines))
    if sub["shared"]:
        out.append(
            "Framing that introduces these items (include it so the request reads naturally):\n"
            + "\n".join(_line(n, r) for n, (_, r) in enumerate(sub["shared"], 1))
        )
    out.append(
        "Source extract: the source's own words for this request, with the other questions' words already left out. This is your "
        "starting point; return it unchanged unless it cannot stand alone:\n"
        + "\n".join(f'- "{t}"' for t in sub["extract_lines"])
    )
    ctx = sub["context"]
    if ctx["words"]:
        note = {
            "not_needed": "the extract already says it",
            "via_reference": "the extract reaches it through a clarified reference",
            "via_inherited": "it is reached through the question this one continues (below)",
            "available_with_link": f'the researcher approved joining words for it: "{ctx.get("link", "")}" ({ctx.get("link_from", "")}); use only those words to join it',
            "unstated_link": 'NOTHING approved says how it joins this request: do not connect it; keep the extract as written and report the missing link under "unresolved"',
        }[ctx["state"]]
        out.append(
            f'Background subject of the whole request: "{ctx["words"]}". You may copy its exact words only if the extract cannot stand alone; here {note}. Add nothing else from it.'
        )
    out.append(
        "The source's own wording these come from (excerpts in order; … marks omitted text):\n"
        + "\n".join(f'- "{e["text"]}"' for e in sub["excerpts"])
    )
    cl = []
    for c in sub["clarified_references"]:
        cl.append(
            f'- "{c["on"]}" (chars {c["span"][0]}-{c["span"][1]}, {c["id"]}): replace it with the exact source words "{c["points_at"]}". Explanation for your understanding only, do not copy it: {_means_label(c)}: "{c["means"]}"'
        )
    for c in sub["meaning_clarifications"]:
        adds = (
            "; it also asks " + " and ".join("how" if a == "manner" else "whether" for a in c["adds"])
            if c["adds"]
            else ""
        )
        link = f'; the approved joining words are "{c["link"]}"' if c["link"] else ""
        pointing = f'; it points at the source words "{c["points_at"]}"' if c["points_at"] else ""
        cl.append(
            f'- "{c["on"]}" (chars {c["span"][0]}-{c["span"][1]}, {c["id"]}){adds}{link}{pointing}. Explanation for your understanding only, do not copy it: {_means_label(c)}: "{c["means"]}"'
        )
    if cl:
        out.append(
            "Clarified by the researcher (authoritative meanings; they are NOT text to paste):\n" + "\n".join(cl)
        )
    if sub["inherited_subject"]:
        out.append(
            "Context from the question above this one (it is asked separately: do NOT ask it again):\n"
            + "\n".join(
                f'- "{i["words"]}" (chars {i["span"][0]}-{i["span"][1]}), asked by {i["from"]}'
                for i in sub["inherited_subject"]
            )
        )
    for c in sub["continues"]:
        out.append(
            f'This request CONTINUES the question {c["from"]}, whose source words are (context only; do NOT ask that question again): "{c["text"]}"'
        )
    for j in sub["pairs"]:
        out.append(
            f"Paired answers ({j['clarification']}): "
            + " and ".join(f'"{m}"' for m in j["members"])
            + " must be kept together as pairs (each value with its counterpart), not as independent lists."
        )
    if sub["unresolved_references"]:
        out.append(
            'Not clarified (keep as written, report under "unresolved"):\n'
            + "\n".join(f'- "{u["word"]}" (chars {u["span"][0]}-{u["span"][1]})' for u in sub["unresolved_references"])
        )
    rules = [
        SAFEGUARDS[k]["full"][1] for k in SAFEGUARDS
    ]  # every safeguard, as the frozen v3 prompt also did for relationships
    return (
        HEADER
        + "\n\n"
        + "\n\n".join(out)
        + "\n\nRules:\n"
        + "\n".join(f"- {r}" for r in rules)
        + '\nReturn only JSON: {"question":"...","unresolved":[{"word":"...","reading_used":"...","other_readings":["..."]}]}'
    )


# ---- the LEAN renderer -------------------------------------------------------------------------------------------------------------------------
LEAN_HEADER = (
    "Write ONE request that can be run on its own, from the source extract below. Keep the researcher's exact wording and request "
    "form; change only what is needed for it to stand alone."
)


def render_lean(sub: dict) -> str:
    out = ["Source extract (exact words from the request):\n" + "\n".join(f'"{t}"' for t in sub["extract_lines"])]
    ctx = sub["context"]
    if ctx["state"] == "available_with_link":
        out.append(
            f'Context you may add if the extract cannot stand alone: "{ctx["words"]}", joined only with "{ctx["link"]}" ({ctx["link_from"]}).'
        )
    elif ctx["state"] == "unstated_link":
        out.append(
            f'The request is about "{ctx["words"]}", but nothing approved says how it joins this extract: do not connect them; keep the extract as written and list the missing link under "unresolved".'
        )
    elif ctx["state"] == "via_inherited":
        out.append(f'The request is about "{ctx["words"]}" (carried by the question this one continues, below).')
    cl = []
    for c in sub["clarified_references"]:
        cl.append(
            f'- "{c["on"]}" means the source words "{c["points_at"]}" ({c["id"]}: {_means_label(c)} "{c["means"]}"; do not copy it).'
        )
    for c in sub["meaning_clarifications"]:
        adds = (
            " It also asks " + " and ".join("how" if a == "manner" else "whether" for a in c["adds"]) + "."
            if c["adds"]
            else ""
        )
        link = f' Approved joining words: "{c["link"]}".' if c["link"] else ""
        pointing = f' It points at "{c["points_at"]}".' if c["points_at"] else ""
        cl.append(
            f'- On "{c["on"]}" ({c["id"]}).{adds}{link}{pointing} {_means_label(c, capital=True)}, for understanding only: "{c["means"]}"'
        )
    if cl:
        out.append("Clarified by the researcher:\n" + "\n".join(cl))
    rel = sub["relationship"]
    if rel:
        subject = f'"{rel["subject"]}"' + (
            f' (= "{rel["subject_is"]}")'
            if rel["subject_is"]
            else " (unclarified: keep as written)"
            if rel["subject_unresolved"]
            else ""
        )
        target = f'"{rel["target"]}"' + "".join(f' ("{r["word"]}" = "{r["points_at"]}")' for r in rel["target_refs"])
        asks = " AND ".join(_relationship_facts(rel)) or "nothing beyond the relationship"
        qual = ("; also " + "; ".join(f'"{x}"' for x in rel["qualifications"])) if rel["qualifications"] else ""
        out.append(
            f'Relationship (keep exactly): {subject} -> "{rel["relation"]}" -> {target}. Asks: {asks}{qual}. Answer form: {rel["answer_form"]}.'
        )
    for c in sub["continues"]:
        out.append(f'Continues {c["from"]} (context only; do not ask it again): "{c["text"]}"')
    for i in sub["inherited_subject"]:
        out.append(f'Context (asked separately; do not ask it again): "{i["words"]}" ({i["from"]}).')
    for j in sub["pairs"]:
        out.append(f"Keep paired ({j['clarification']}): " + " and ".join(f'"{m}"' for m in j["members"]) + ".")
    if sub["unresolved_references"]:
        out.append(
            "Not clarified (keep as written; list under unresolved): "
            + ", ".join(f'"{u["word"]}"' for u in sub["unresolved_references"])
            + "."
        )
    rules = [SAFEGUARDS[k]["lean"][1] for k in applicable_safeguards(sub)]
    fields = 'Fields: "question" is the request text; "unresolved" lists meaning you could not settle, each with word, reading_used = "none chosen", other_readings = [] (usually empty).'
    return (
        LEAN_HEADER
        + "\n\n"
        + "\n\n".join(out)
        + "\n\nRules:\n"
        + "\n".join(f"{n}. {r}" for n, r in enumerate(rules, 1))
        + "\n"
        + fields
    )


# ---- variants -------------------------------------------------------------------------------------------------------------------------------------------
def settings_for(variant: str, *, use_proposed_briefs: bool = False) -> dict:
    """Writer settings for a variant. ``v3`` is the frozen prompt, schema and cap; the other two share ONE matched schema/cap."""
    if variant == "v3":
        return ch.V3_SETTINGS
    if (
        variant == "prepared"
    ):  # corrected-full + deterministic preparation (prepare.py); imported late: it builds on this module
        from experiments.ask_cli_revised.decompose import prompts_prepared

        return prompts_prepared.settings()
    render = {"corrected-full": render_full, "lean": render_lean}[variant]

    def _render(parent: dict, plan: dict, plans: list[dict], by_id: dict) -> str:
        return render(substance(parent, plan, plans, by_id, use_proposed_briefs=use_proposed_briefs))

    return {
        "variant": variant,
        "schema": MATCHED_SCHEMA,
        "cap": MATCHED_OUTPUT_CAP,
        "limits": MATCHED_LIMITS,
        "extract_mode": "governing",
        "preflight": True,
        "use_proposed_briefs": use_proposed_briefs,
        "render": _render,
    }


VARIANTS = ("v3", "corrected-full", "lean", "prepared")
