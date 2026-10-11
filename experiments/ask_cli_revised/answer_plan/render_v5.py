"""Deterministic v5 rendering with member-specific citation transport."""

from experiments.ask_cli_revised._layerc_common import canonical, require


def render(plan, claims, receipts, synthesis):
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
                qualification = plan.get("source_qualifications", {}).get(receipt["coverage_ref"])
                prefix = qualification["prefix"] if qualification else ""
                key = (prefix, item["text"])
                entry = statements.setdefault(key, {"text": item["text"], "members": []})
                if qualification:
                    entry["qualification"] = qualification
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
        ordered = [statements[k] for k in sorted(statements)]
        for entry in ordered:
            entry["members"].sort(key=canonical)
        nodes.append(
            {"label": node["label"], "state": node["state"], "statements": ordered, "limitations": limitations}
        )
    numbers = {ref: n for n, ref in enumerate(sorted(citation_records), 1)}
    for node, rendered in zip(plan["nodes"], nodes, strict=True):
        text.append(f"{node['label']}. {node['literal_text']}")
        for statement in rendered["statements"]:
            cites = sorted({numbers[m["source_ref"]] for m in statement["members"]})
            prefix = statement.get("qualification", {}).get("prefix", "")
            text.append(prefix + statement["text"] + " " + "".join(f"[{n}]" for n in cites))
        messages = [x["text"] for x in rendered["limitations"]]
        text.extend(dict.fromkeys(messages) if "disclosure_context" in plan else messages)
        text.append("")
    return {
        "schema": "profile-b-render-v1",
        "nodes": nodes,
        "citations": {ref: {**citation_records[ref], "number": numbers[ref]} for ref in sorted(numbers)},
        "layer1": "\n".join(text).rstrip() + "\n",
    }
