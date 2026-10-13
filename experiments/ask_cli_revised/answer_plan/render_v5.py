"""Deterministic v5 rendering with member-specific citation transport."""

from experiments.ask_cli_revised._layerc_common import canonical, require


def _words(text):
    return {w.strip(".,;:()[]'" + '"').lower() for w in text.split()} - {""}


def _within(sentence, evidence):
    return any(sentence in e or e in sentence for e in evidence)


def _absorb(entries):
    """Do not print twice what one statement already conveys over the same evidence: a source sentence already shown as
    the evidence of a claim, or a claim that says nearly the same as a fuller claim on the same sentence (at least three
    quarters of its words). Members, and so citations, move to the statement that remains."""

    def host_of(a):
        prefix = a.get("qualification", {}).get("prefix", "")
        for b in entries:
            if b is a or "evidence" not in b or b.get("qualification", {}).get("prefix", "") != prefix:
                continue
            if "evidence" not in a:
                if _within(a["text"], b["evidence"]):
                    return b
            elif all(_within(e, b["evidence"]) for e in a["evidence"]):
                mine, theirs = _words(a["text"]), _words(b["text"])
                fuller = (len(theirs), b["text"]) > (len(mine), a["text"])
                if fuller and 4 * len(mine & theirs) >= 3 * len(mine):
                    return b
        return None

    hosts = {id(a): host_of(a) for a in entries}
    kept = []
    for a in entries:
        target, seen = hosts[id(a)], {id(a)}
        while target is not None and hosts[id(target)] is not None and id(target) not in seen:
            seen.add(id(target))
            target = hosts[id(target)]
        if target is None:
            kept.append(a)
            continue
        target["members"].extend(m for m in a["members"] if m not in target["members"])
    return kept


def render(plan, claims, receipts, synthesis, ground=None):
    by_claim = {c["claim_id"]: c for c in claims}
    nodes, citation_records, text = [], {}, []
    for node in plan["nodes"]:
        facets = {f["facet_id"] for f in node["facets"]}
        statements = {}
        for segment in synthesis["segments"]:
            claim = by_claim[segment["claim_ref"]]
            if not facets.intersection(claim["semantic_identity"]["scope"]["requirement_ids"]):
                continue
            for item in segment["items"]:
                receipt = receipts[item["receipt_ref"]]
                require(
                    receipt["value_ref"] == item["value_ref"] and item["source_ref"] in receipt["citation"],
                    "render value coverage",
                )
                # Text deduplication follows authorized member associations; it creates none.
                qualification = item.get("qualification") or plan.get("source_qualifications", {}).get(
                    receipt["coverage_ref"]
                )
                prefix = qualification["prefix"] if qualification else ""
                key = (prefix, item["text"])
                entry = statements.setdefault(key, {"text": item["text"], "members": []})
                if qualification:
                    entry["qualification"] = qualification
                if "evidence_sentence" in item and item["evidence_sentence"] not in entry.setdefault("evidence", []):
                    entry["evidence"].append(item["evidence_sentence"])
                if item not in entry["members"]:
                    entry["members"].append(item)
                citation_records[item["source_ref"]] = {
                    "proposition_id": item["proposition_id"],
                    "receipt_refs": sorted(
                        {ref for ref, rec in receipts.items() if item["source_ref"] in rec["citation"]}
                    ),
                }
        limitations = []
        for facet in node["facets"]:
            if "disclosures" in facet:
                limitations.extend(facet["disclosures"])
            elif facet["state"] == "partial" and facet["scientific_goal_state"] in ("established", "complete"):
                limitations.append(
                    {
                        "kind": "presentation_limitation",
                        "facet_id": facet["facet_id"],
                        "text": "An established finding has presentation limitations; see the supporting evidence.",
                    }
                )
            elif facet["state"] == "not_established":
                limitations.append(
                    {
                        "kind": "not_established",
                        "facet_id": facet["facet_id"],
                        "text": "The retrieved evidence does not establish an answer to this part.",
                    }
                )
        ordered = _absorb([statements[k] for k in sorted(statements)])
        for entry in ordered:
            entry["members"].sort(key=canonical)
        nodes.append(
            {"label": node["label"], "state": node["state"], "statements": ordered, "limitations": limitations}
        )
    if ground is not None:
        ground(nodes)
    numbers = {ref: n for n, ref in enumerate(sorted(citation_records), 1)}
    for node, rendered in zip(plan["nodes"], nodes, strict=True):
        text.append(f"{node['label']}. {node['literal_text']}")
        for statement in rendered["statements"]:
            cites = sorted({numbers[m["source_ref"]] for m in statement["members"]})
            prefix = statement.get("qualification", {}).get("prefix", "")
            text.append(prefix + statement["text"] + " " + "".join(f"[{n}]" for n in cites))
            # The source's own words, directly under the statement they support.
            evidence = [e for e in statement.get("evidence", ()) if e != statement["text"]]
            shown = sorted(e for e in evidence if not any(e != o and e in o for o in evidence))
            for sentence in shown:
                marks = sorted(
                    {
                        numbers[m["source_ref"]]
                        for m in statement["members"]
                        if m.get("evidence_sentence") in (sentence, None) or m.get("evidence_sentence", "") in sentence
                    }
                )
                text.append("    Source " + "".join(f"[{n}]" for n in marks) + ': "' + sentence + '"')
        messages = [x["text"] for x in rendered["limitations"]]
        text.extend(dict.fromkeys(messages) if "disclosure_context" in plan else messages)
        text.append("")
    return {
        "schema": "profile-b-render-v1",
        "nodes": nodes,
        "citations": {ref: {**citation_records[ref], "number": numbers[ref]} for ref in sorted(numbers)},
        "layer1": "\n".join(text).rstrip() + "\n",
    }
