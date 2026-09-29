"""The ``prepared`` writer variant: corrected-full plus deterministic preparation (``prepare.py``).

Only what differs from the historical corrected-full prompt is here. A child with nothing to prepare is rendered by ``prompts.render_full``
itself, byte for byte. A prepared child gets the same substance record, the same schema, cap and limits, and the same safeguards; what changes is
the extract it starts from (approved referents, added cues, lead-in, closing punctuation and any carried context already put in place by code),
an "already made by code" list with each edit's source, and a list of what the finished wording will be checked for.

The natural-language request and the contract are built from the same preparation record, so they trace to the same obligations."""

from __future__ import annotations

from experiments.ask_cli_revised.decompose import children as ch
from experiments.ask_cli_revised.decompose import prepare, prompts
from experiments.ask_cli_revised.decompose.prompts import (
    HEADER,
    MATCHED_LIMITS,
    MATCHED_OUTPUT_CAP,
    MATCHED_SCHEMA,
    SAFEGUARDS,
    _line,
    _means_label,
    _relationship_facts,
)

PREPARED_RULES = (
    "Edits already made by code (listed above, each with its source) are final: keep them exactly; do not undo, reword, move or repeat them.",
    "Beyond those edits, change only what is still needed for the request to stand alone: the smallest grammatical words, and only joining "
    "words the researcher approved (listed above).",
)
SCAFFOLD_RULE = (
    "The prepared request is a complete standalone request built by code from the parts listed above. Return it unchanged unless a word in it is "
    "plainly wrong; anything you change will be listed and the wording held for the researcher's approval."
)
CARRY_RULE = (
    "Carried context only says what this request is about. Do not ask it (add no question word for it) and do not restate the question it "
    "comes from."
)


def _span(s) -> str:
    return f"{s[0]}-{s[1]}"


def _quoted(items: list[dict]) -> str:
    """Quote source words; two pieces that sit next to each other in the source (an article and its noun) read as one phrase."""
    groups: list[list[dict]] = []
    for x in items:
        if groups and groups[-1][-1]["span"][1] + 1 == x["span"][0]:
            groups[-1].append(x)
        else:
            groups.append([x])
    return " + ".join('"' + " ".join(y["text"] for y in g) + '"' for g in groups)


def _edit_sentence(e: dict) -> str:
    op = e["op"]
    if op == "context_prefix":
        return (
            f'Opened the request with the approved joining words "{e["supplied"][0]["text"]}" and the source words {_quoted(e["from_source"])} '
            f"({e['clarification']}, decision {e.get('decision')}; the joining words are the researcher's, not the source's)."
        )
    if op == "reference_resolved":
        extra = f" plus the grammatical suffix {e['supplied'][0]['text']}" if e["supplied"] else ""
        return (
            f'Replaced "{e["replaces"]["text"]}" (chars {_span(e["replaces"]["source_span"])}) with the source words {_quoted(e["from_source"])}{extra} '
            f"({e['clarification']})."
        )
    if op == "inflection_corrected":
        return (
            f'Corrected the inflection of the source word "{e["replaces"]["text"]}" (chars {_span(e["replaces"]["source_span"])}) to '
            f'"{e["result"]}" (a grammatical correction of that one word; no new word).'
        )
    if op == "cue_added":
        where = "after" if "inserted_after_source_span" in e else "before"
        return (
            f'Added "{e["result"].strip()}" {where} the source words "{e["anchor_text"]}" ({e["clarification"]}: the researcher approved that '
            f"this request also asks it; these words are not in the source)."
        )
    return f'Kept the source\'s closing "{e["result"]}" (chars {_span(e["from_source"][0]["span"])}).'


def _relationship_block(rel: dict, by_clarification: dict) -> str:
    """The relationship lines of corrected-full, with each word code already replaced shown as replaced (so the contract and the request agree)."""

    def replaced(word: str, cid: str | None) -> str | None:
        e = by_clarification.get(cid)
        if e and e["replaces"]["text"].lower() == word.lower():
            return f'already replaced by code with "{e["result"]}" ({cid}), so the request now reads that way'
        return None

    lines = [
        "Relationship to keep, parsed from the source words. Keep the subject, the relation, the target and the direction exactly:"
    ]
    subject = f'- subject: "{rel["subject"]}" (chars {_span(rel["subject_span"])})'
    if rel["subject_is"]:
        done = next((replaced(rel["subject"], cid) for cid in by_clarification), None)
        subject += (
            f", {done}" if done else f', clarified by the researcher to point at the source words "{rel["subject_is"]}"'
        )
    elif rel["subject_unresolved"]:
        subject += ", an unclarified reference: keep it as written and report it"
    lines.append(subject)
    lines.append(f'- relation: "{rel["relation"]}" (chars {_span(rel["relation_span"])})')
    lines.append(f'- target: "{rel["target"]}" (chars {_span(rel["target_span"])})')
    for r in rel["target_refs"]:
        done = replaced(r["word"], r["id"])
        lines.append(
            f'  - in the target, "{r["word"]}" is {done}'
            if done
            else f'  - in the target, "{r["word"]}" is clarified ({r["id"]}) to point at the source words "{r["points_at"]}"'
        )
    lines.append(
        f"- what it asks: {' AND '.join(_relationship_facts(rel)) or 'nothing beyond the relationship itself'}; answer form: {rel['answer_form']}"
        + (f' ("{rel["answer_marker"]}")' if rel["answer_marker"] else "")
    )
    if rel["qualifications"]:
        lines.append("- qualifications: " + "; ".join(f'"{x}"' for x in rel["qualifications"]))
    return "\n".join(lines)


def _piece_sentence(p: dict) -> str:
    """One scaffold piece and exactly where its words came from."""
    o, t = p["origin"], p["text"]
    if o == "source":
        return f'"{t}": source chars {_span(p["span"])}'
    if o == "approved_joining_word":
        return f'"{t}": the researcher\'s approved joining word ({p["clarification"]}, decision {p.get("decision")}); not a source word'
    if o == "rule":
        basis = f"; {p['basis']}" if p.get("basis") else ""
        return f'"{t}": a grammatical word supplied by rule {p["rule"]}; not a source word{basis}'
    if o == "reference_resolution":
        suffix = " plus the suffix " + p["supplied"][0]["text"] if p["supplied"] else ""
        return (
            f'"{t}": replaces "{p["replaces"]["text"]}" (chars {_span(p["replaces"]["source_span"])}) with the source words '
            f"{_quoted(p['from_source'])}{suffix} ({p['clarification']})"
        )
    if o == "inferred_reference":
        return (
            f'"{t}": replaces "{p["replaces"]["text"]}" (chars {_span(p["replaces"]["source_span"])}); an inference from {p["based_on"]}, '
            "pending the researcher's confirmation"
        )
    return f'"{t}": inflection of the source word "{p["inflection_of"]["text"]}" (chars {_span(p["inflection_of"]["source_span"])}) by rule {p["rule"]}'


def render_prepared(parent: dict, sub: dict, prep: dict) -> str:
    """The prepared prompt for one child; identical to corrected-full when there is nothing to prepare."""
    if not prep["active"]:
        return prompts.render_full(sub)
    edits = prep["edits"]
    carry = prep["carry"]
    scaffold = prep.get("scaffold")
    built = bool(scaffold and scaffold["built"])
    by_clarification = {
        e["clarification"]: e for e in [*edits, *(carry["edits"] if carry else [])] if e["op"] == "reference_resolved"
    }
    added = {e["clarification"] for e in edits if e["op"] == "cue_added"}
    out = [
        "What this request must ask (its owned items, exact words from the source):\n"
        + "\n".join(_line(n, r) for n, (_, r) in enumerate(sub["owned"], 1))
    ]
    if sub["relationship"]:
        out.append(_relationship_block(sub["relationship"], by_clarification))
    if sub["shared"]:
        out.append(
            "Framing that introduces these items (include it so the request reads naturally):\n"
            + "\n".join(_line(n, r) for n, (_, r) in enumerate(sub["shared"], 1))
        )
    lines = prep["prepared_lines"]
    if built:
        out.append(
            "Prepared request: a complete standalone request built by code from the fragment's own source words, the recorded structure of "
            "the question it continues and any joining word the researcher approved (the parts and their sources are listed below). This is "
            "your starting point:\n" + "\n".join(f'- "{t}"' for t in lines)
        )
        out.append(
            "Built by code, part by part (do not undo, reword, reorder or repeat):\n"
            + "\n".join(f"- {_piece_sentence(p)}" for p in scaffold["pieces"])
        )
        if scaffold["dropped_source_words"]:
            out.append(
                "Source words of the fragment or the continued question that are NOT in the request: "
                + "; ".join(
                    f'"{d["text"]}" (chars {_span(d["span"])}): {d["why"]}' for d in scaffold["dropped_source_words"]
                )
            )
        if scaffold["pending"]:
            out.append(
                "Awaiting the researcher's confirmation (do not treat as settled):\n"
                + "\n".join(f"- {p['reason']}" for p in scaffold["pending"])
            )
    else:
        out.append(
            "Prepared request: the source's own words for this request (the other questions' words already left out), with the edits listed "
            "below already made by code. This is your starting point; return it unchanged unless it still cannot stand alone:\n"
            + "\n".join(f'- "{t}"' for t in lines)
        )
        made = [f"- {_edit_sentence(e)}" for e in edits]
        if made:
            out.append(
                "Already made by code (each from the source or an approved clarification; do not undo, reword or repeat):\n"
                + "\n".join(made)
            )
    left = [f"- {n['reason']}" for n in prep["not_applied"]] + [f"- {n['reason']}" for n in prep["not_prepared"]]
    if scaffold and not built:
        left += [f"- {n['reason']}" for n in scaffold["not_built"] if n["template"]]
    if left:
        out.append(
            "Not prepared by code (left for you, using the approved meanings below; nothing else may be assumed):\n"
            + "\n".join(left)
        )
    for g in prep["grammar_notes"]:
        out.append(f"Grammar note: {g['note']}.")
    ctx = sub["context"]
    if ctx["words"] and not prep["prefix"] and not carry and not built:
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
        if c["id"] in by_clarification:
            continue
        cl.append(
            f'- "{c["on"]}" (chars {_span(c["span"])}, {c["id"]}): replace it with the exact source words "{c["points_at"]}". Explanation for your understanding only, do not copy it: {_means_label(c)}: "{c["means"]}"'
        )
    for c in sub["meaning_clarifications"]:
        adds = (
            "; it also asks "
            + " and ".join("how" if a == "manner" else "whether" for a in c["adds"])
            + (" (already in the prepared request)" if c["id"] in added else "")
            if c["adds"]
            else ""
        )
        link = f'; the approved joining words are "{c["link"]}"' if c["link"] else ""
        pointing = f'; it points at the source words "{c["points_at"]}"' if c["points_at"] else ""
        cl.append(
            f'- "{c["on"]}" (chars {_span(c["span"])}, {c["id"]}){adds}{link}{pointing}. Explanation for your understanding only, do not copy it: {_means_label(c)}: "{c["means"]}"'
        )
    if cl:
        out.append(
            "Clarified by the researcher (authoritative meanings; they are NOT text to paste):\n" + "\n".join(cl)
        )
    if sub["inherited_subject"]:
        out.append(
            "Context from the question above this one (it is asked separately: do NOT ask it again):\n"
            + "\n".join(
                f'- "{i["words"]}" (chars {_span(i["span"])}), asked by {i["from"]}' for i in sub["inherited_subject"]
            )
        )
    if carry and not built:
        joined = prep["join"]
        join = f' Join it only with the approved word "{joined["text"]}" ({joined["clarification"]}).' if joined else ""
        out.append(
            f"Carried context ({carry['clarification']}; the source words of {carry['from_node']}, which is asked separately, with approved references replaced): "
            f'"{carry["text"]}"\nThis is CONTEXT ONLY: it says what this request is about. Do NOT turn it into a question (add no question word for it).{join}'
        )
    elif not built:
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
            + "\n".join(f'- "{u["word"]}" (chars {_span(u["span"])})' for u in sub["unresolved_references"])
        )
    out.append("Your request will be checked for:\n" + "\n".join(f"- {r['text']}" for r in prep["requirements"]))
    rules = (
        [SAFEGUARDS[k]["full"][1] for k in SAFEGUARDS]
        + list(PREPARED_RULES)
        + ([SCAFFOLD_RULE] if built else [CARRY_RULE] if carry else [])
    )
    return (
        HEADER
        + "\n\n"
        + "\n\n".join(out)
        + "\n\nRules:\n"
        + "\n".join(f"- {r}" for r in rules)
        + '\nReturn only JSON: {"question":"...","unresolved":[{"word":"...","reading_used":"...","other_readings":["..."]}]}'
    )


def prepared_for(parent: dict, plan: dict, plans: list[dict], by_id: dict) -> tuple[dict, dict]:
    """(substance record, preparation record) for one child, both from the same context."""
    ctx = ch.child_context(parent, plan, by_id, plans=plans, governing_operation=True)
    sub = prompts.substance(parent, plan, plans, by_id)
    prep = prepare.prepare_child(parent, plan, plans, by_id, ctx)
    lines = prompts._join_extract(parent, prep["extract_entries"])
    if prep["prefix"]:
        lines[0] = f"{prep['prefix']} {lines[0]}"
    if prep.get("scaffold") and prep["scaffold"]["built"]:
        lines = [
            prep["scaffold"]["text"]
        ]  # the deterministic scaffold replaces the extract as the writer's starting point
    prep["prepared_lines"] = lines  # the exact starting point the writer is given (one line per source sentence)
    prep["prepared_request"] = " ".join(lines)
    return sub, prep


def _render(parent: dict, plan: dict, plans: list[dict], by_id: dict) -> str:
    sub, prep = prepared_for(parent, plan, plans, by_id)
    return render_prepared(parent, sub, prep)


def _prepare(parent: dict, plan: dict, plans: list[dict], by_id: dict) -> dict:
    return prepared_for(parent, plan, plans, by_id)[1]


def settings() -> dict:
    """Writer settings: the SAME matched schema, cap, limits, extract mode and preflight as corrected-full; only the prompt differs."""
    return {
        "variant": "prepared",
        "schema": MATCHED_SCHEMA,
        "cap": MATCHED_OUTPUT_CAP,
        "limits": MATCHED_LIMITS,
        "extract_mode": "governing",
        "preflight": True,
        "use_proposed_briefs": False,
        "render": _render,
        "prepare": _prepare,
    }
