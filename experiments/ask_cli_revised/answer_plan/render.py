"""Renderers for the Phase-30 AnswerPlan: Layer 1 (answer), Layer 2 (supporting evidence), Layer 3 (audit). Pure.

Layer 1 contains no proposition ids, claim ids, role names, snake_case identifiers, or internal reason codes. Citations
are numbered markers that map to a source list; the mapping to proposition ids lives in Layer 2/3.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.answer_plan import text as tx
from experiments.ask_cli_revised.answer_plan.plan import REASON_TEXT, SILENT_REASONS

STATUS_LINE = {
    "answered": "Answered.",
    "partial": "Answered in part.",
    "not_established": "Not established in the retrieved evidence.",
    "searched_empty": "The scoped search completed without establishing an answer.",
}


def _passage_key(prop: dict) -> tuple:
    page = (prop.get("verification") or {}).get("page_start")
    return (prop["paper_id"], page, prop.get("evidence_span_id"))


def _statement_keys(statement: dict, props: dict) -> list[tuple]:
    """Passage keys a statement cites: its verified propositions, or (for a promoted qualifier) its own sealed span."""
    if statement.get("prop_ids"):
        return [_passage_key(props[pid]) for pid in statement["prop_ids"]]
    return [(statement["paper_id"], None, statement["span_id"])]


def citation_map(plan: dict, props: dict) -> tuple[dict, list[tuple]]:
    """Numbered source markers, assigned in first-appearance order across the Layer-1 statements."""
    numbers: dict[tuple, int] = {}
    order: list[tuple] = []
    for node in plan["nodes"]:
        for statement in node["statements"]:
            for key in _statement_keys(statement, props):
                if key not in numbers:
                    numbers[key] = len(numbers) + 1
                    order.append(key)
    return numbers, order


def _markers(statement: dict, props: dict, numbers: dict) -> str:
    seen: list[int] = []
    for key in _statement_keys(statement, props):
        n = numbers[key]
        if n not in seen:
            seen.append(n)
    return "".join(f"[{n}]" for n in seen)


def _ensure_terminal(sentence: str) -> str:
    sentence = sentence.rstrip()
    return sentence if sentence.endswith((".", "?", "!", ")", "”", '"')) else sentence + "."


def render_layer1(plan: dict, props: dict, corpus_words: set[str]) -> str:
    numbers, order = citation_map(plan, props)
    lines = [
        "# Answer (offline deterministic replay, Step 1)",
        "",
        "_No model wrote this text. Every sentence is a verbatim source sentence or a fixed disclosure._",
        "",
    ]
    for node in plan["nodes"]:
        indent = "&emsp;&emsp;" if node["parent"] else ""
        lines.append(f"{indent}**{node['label']}. {node['literal_text']}**")
        lines.append("")
        lines.append(f"{indent}*{STATUS_LINE[node['status']]}*")
        lines.append("")
        parts = []
        for statement in node["statements"]:
            text = tx.display_text(statement["text"], corpus_words)
            parts.append(_ensure_terminal(text) + _markers(statement, props, numbers))
        parts.extend(node["disclosures"])
        parts.extend(node["not_assessed"])
        if parts:
            lines.append(f"{indent}" + " ".join(parts))
            lines.append("")
    lines.append("## Sources")
    lines.append("")
    for index, key in enumerate(order, start=1):
        paper, page, span_id = key
        page_text = f", page {page}" if page is not None else ""
        qualifier = "" if page is not None else ", qualifying passage"
        lines.append(f"[{index}] Paper {paper}{page_text}{qualifier}.")
    lines.append("")
    return "\n".join(lines)


def _facet_to_node(plan: dict) -> dict:
    out = {}
    for node in plan["nodes"]:
        for facet in node["facets"]:
            out[facet["facet_id"]] = node["label"]
    return out


def render_layer2(plan: dict, props: dict) -> str:
    """Supporting evidence per node: candidates that did not reach Layer 1, each with its verbatim passage and the
    fixed human reason. Claim ids and check names stay in Layer 3."""
    facet_node = _facet_to_node(plan)
    by_node: dict[str, list[str]] = {node["label"]: [] for node in plan["nodes"]}
    for record in plan["claim_roles"]:
        if record.get("layer") == "layer1" or record.get("layer") == "layer1_via_relation":
            continue
        node = facet_node.get(record.get("facet_id"))
        if node is None:
            continue
        reasons = []
        for reason in record.get("reasons", []):
            if reason in REASON_TEXT and reason not in SILENT_REASONS and REASON_TEXT[reason] not in reasons:
                reasons.append(REASON_TEXT[reason])
        if record.get("attached_unit") and not reasons:
            reasons.append(
                "This direction is tied to a relation that is not stated as an answer, so it is not stated separately."
            )
        for pid in record["admissible_proposition_ids"]:
            quote = props[pid]["quote"].strip()
            page = (props[pid].get("verification") or {}).get("page_start")
            where = f"Paper {props[pid]['paper_id']}" + (f", page {page}" if page is not None else "")
            why = " ".join(reasons) if reasons else "Listed for reference."
            by_node[node].append(f"- {why} Source passage ({where}): “{quote}”")
    lines = ["# Supporting evidence (Layer 2, deterministic replay)", ""]
    for node in plan["nodes"]:
        lines.append(f"## {node['label']}. {node['literal_text']}")
        lines.append("")
        items = []
        for item in by_node[node["label"]]:
            if item not in items:
                items.append(item)
        lines.extend(items if items else ["- No additional passages were set aside for this item."])
        lines.append("")
    return "\n".join(lines)


def invariant_report(plan: dict, layer1_text: str, props: dict) -> list[dict]:
    """Mechanical checks over the replay. Each check is a named, reproducible property of the output, not a judgment
    about the science. The U-numbers refer to the Phase-29 audit's replay checks (Phase-30 section 8)."""
    checks: list[dict] = []

    def add(name: str, passed: bool, detail=None) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    statements = [(node, s) for node in plan["nodes"] for s in node["statements"]]
    rendered = [s["text"] for _node, s in statements]

    snake = sorted(set(re.findall(r"\b[a-z]+(?:_[a-z]+)+\b", layer1_text)))
    add("layer1_no_snake_case_identifiers", not snake, snake)
    pids = sorted(set(re.findall(r"\bp\d+\b", layer1_text)))
    add("layer1_no_proposition_ids", not pids, pids)
    hashes = sorted(set(re.findall(r"::[0-9a-f]{8,}", layer1_text)))
    add("layer1_no_claim_ids", not hashes, hashes)
    forbidden = [
        w
        for w in (
            "no_grounded_sentences",
            "relationship_unverified",
            "searched_no_support",
            "direction finding",
            "reported relationship",
            "ParentClaim",
            "ResolvedEmptyOutcome",
            "individual_difference",
            "relationship_to_bias",
        )
        if w.lower() in layer1_text.lower()
    ]
    add("layer1_no_internal_terms_or_templates", not forbidden, forbidden)
    missing = [n["label"] for n in plan["nodes"] if f"**{n['label']}. " not in layer1_text]
    add("every_confirmed_node_appears_with_literal_wording", not missing, missing)
    nested = [n["label"] for n in plan["nodes"] if n.get("parent")]
    add("nested_labels_visible", all(f"**{x}. " in layer1_text for x in nested), nested)
    add("no_linebreak_hyphen_artifacts", not re.search(r"[A-Za-z]- [a-z]", layer1_text))
    unexpanded = sorted(set(re.findall(r"\b[A-Z]{2,}\s*\([^)]{3,}\)", layer1_text)))
    add("no_acronym_expansion_printed", not unexpanded, unexpanded)

    # Verbatim authority (D5): each statement, with its recorded label edit reversed, is contained in its own passage.
    for _node, statement in statements:
        core = statement["text"]
        for edit in statement.get("edits") or []:
            if edit["kind"] == "self_reference_to_source_label":
                core = core.replace(edit["to"], edit["from"], 1)
        if statement["kind"] == "enumeration":
            verbatim = all(
                any(tx.contains(value, props[pid]["quote"]) for pid in statement["prop_ids"])
                for value in statement.get("values", [])
            )
        elif statement.get("prop_ids"):
            verbatim = any(tx.contains(core, props[pid]["quote"]) for pid in statement["prop_ids"])
        else:
            verbatim = tx.contains(core, statement.get("span_text") or "")
        add(f"verbatim_from_passage:{statement['claim_id']}", verbatim, None if verbatim else core[:120])
        if statement.get("prop_ids"):
            restated = tx.normalized_key(statement["text"]) == tx.normalized_key(
                props[statement["prop_ids"][0]]["proposition_text"]
            )
            add(
                f"not_restatement_text:{statement['claim_id']}",
                not restated
                or tx.normalized_key(statement["text"]) == tx.normalized_key(props[statement["prop_ids"][0]]["quote"]),
            )

    add(
        "U1_generic_summary_not_stated",
        not any("earlier reports" in t for t in rendered),
        [t[:70] for t in rendered if "earlier reports" in t],
    )
    add(
        "U2_no_bare_polarity_keyword",
        not any(t.strip().rstrip(".").lower() in {"implicit", "explicit"} for t in rendered)
        and not any(t.lower().startswith("attitude category") for t in rendered),
    )
    add(
        "U3_speculative_trait_list_not_stated",
        not any("negative attitudes (IAT" in t or "undesirable behaviors" in t for t in rendered),
    )
    add(
        "U4_face_ratings_not_perceiver_traits",
        not any(re.search(r"\b(attractiveness|threateningness)\b", t) for t in rendered),
    )
    add(
        "U5_caption_not_a_finding",
        not any("Table S" in t or "Correlations between implicit biases" in t for t in rendered),
    )
    add(
        "U6_prior_work_not_stated_as_result",
        not any("Laypersons with high levels" in t or "implicated certain" in t for t in rendered),
    )
    adjacent_nodes = [n["label"] for n in plan["nodes"] if n["label"] in ("2", "4A")]
    adjacent_leak = [
        s["text"][:70]
        for node, s in statements
        if node["label"] in adjacent_nodes and any(props[pid]["paper_id"] == 14 for pid in s["prop_ids"])
    ]
    add("U7_adjacent_construct_not_an_answer", not adjacent_leak, adjacent_leak)
    add(
        "U8_bias_description_not_intervention_outcome",
        not any("This research confirmed earlier reports" in t for t in rendered),
    )
    unwitnessed_leak = [
        (node["label"], s["claim_id"])
        for node, s in statements
        if s["kind"] == "relation_sentence"
        and next(f for f in node["facets"] if f["facet_id"] == s["facet_id"])["relation_status"] != "witnessed"
    ]
    add("U9_unwitnessed_relation_not_claimable", not unwitnessed_leak, unwitnessed_leak)
    valence = [s for _node, s in statements if s["kind"] == "value_level_valence"]
    add(
        "U10_direction_names_its_subject",
        all(s.get("subject") and s["subject"] in s["text"] for s in valence),
        [s["text"][:70] for s in valence],
    )
    add("U11_no_unsupported_expansion", not unexpanded, unexpanded)
    add("U14_task_description_not_a_result", not any("several brain regions" in t for t in rendered))
    add("U15_display_hyphen_normalized", not re.search(r"attrac- tiveness|anomalous-is- bad", layer1_text))
    return checks
