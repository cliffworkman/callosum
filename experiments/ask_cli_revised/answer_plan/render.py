"""Renderers for the Phase-30 AnswerPlan: Layer 1 (answer), Layer 2 (supporting evidence), Layer 3 (mechanical audit). Pure.

Layer 1 contains no proposition ids, claim ids, role names, snake_case identifiers, or internal reason codes. Citations are
numbered markers that map to a source list labelled with citeproc-style author-date labels from library metadata. Layer 2
holds passages and the human reasons they were not stated as answers. Layer 3 holds every identifier, hash, and check.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.answer_plan import text as tx
from experiments.ask_cli_revised.answer_plan.plan import REASON_TEXT
from experiments.ask_cli_revised.answer_plan.step2 import POINTER

STATUS_LINE = {
    "answered": "Answered.",
    "partial": "Answered in part.",
    "not_established": "Not established in the retrieved evidence.",
    "searched_empty": "The scoped search completed without establishing an answer.",
}
ROLE_TEXT = {
    "attributed_only": "Attributed to earlier work, so not stated as this study's result.",
    "suppressed": "Not stated as an answer to this item.",
    "attached_to_relation": "Tied to a relation that is not stated as an answer.",
    "duplicate": "The same sentence is stated under another item.",
}
# Words that may appear in fixed Layer-1 text. Any of these in generated (non-verbatim) text is a Layer-3 leak.
LAYER3_VOCABULARY = re.compile(
    r"\b(?:proposition\w*|claim\w*|facet\w*|witness\w*|reason\w*|hash\w*|sha256|engine\w*|layer\d?|parentclaim|"
    r"role\w*|overlay\w*|requirement\w*|sufficiency)\b",
    re.IGNORECASE,
)


def _passage_key(prop: dict) -> tuple:
    page = (prop.get("verification") or {}).get("page_start")
    return (prop["paper_id"], page, prop.get("evidence_span_id"))


def _statement_keys(statement: dict, props: dict) -> list[tuple]:
    """Passage keys a statement cites: its verified propositions, or (for a promoted limitation) its own sealed span."""
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


def _label(plan: dict, pid, form: str = "narrative") -> str:
    record = plan["source_labels"].get(str(pid))
    return record[form] if record else f"Source {pid}"


def layer1_body_words(layer1_text: str) -> int:
    """Words in the answer body: everything above the source list, without markdown and citation markers."""
    body = layer1_text.split("## Sources", 1)[0]
    body = re.sub(r"\[\d+\]", " ", body)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", body))


def render_layer1(plan: dict, props: dict, corpus_words: set[str]) -> str:
    numbers, order = citation_map(plan, props)
    lines = [
        "# Answer (offline deterministic replay, Step 2)",
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
        paper, page, _span_id = key
        page_text = f", page {page}" if page is not None else ""
        qualifier = "" if page is not None else ", qualifying passage"
        lines.append(f"[{index}] {_label(plan, paper, 'list')}{page_text}{qualifier}.")
    lines.append("")
    return "\n".join(lines)


def _section(title: str, items: list[str]) -> list[str]:
    return [f"### {title}", "", *(items or ["- None for this item."]), ""]


def _passage_line(plan: dict, passage: dict) -> str:
    page = f", page {passage['page']}" if passage["page"] is not None else ""
    statistics = " Reports statistics." if passage["statistics"] else ""
    return f"- {_label(plan, passage['paper_id'], 'list')}{page}: “{passage['quote'].strip()}”{statistics}"


def _limitation_line(plan: dict, entry: dict) -> str:
    where = f"{_label(plan, entry['paper_id'], 'list')}"
    why = "; ".join(entry["why_attached"])
    if entry["promoted"]:
        outcome = "Stated in Layer 1 above, because it " + "; and it ".join(entry["promotion_basis"]) + "."
    else:
        outcome = f"Not stated in Layer 1: {entry['not_promoted_reason']}."
    return f"- “{entry['text']}” ({where}). Attached because {why.lower()}. {outcome}"


def _definition_line(plan: dict, definition: dict) -> str:
    expanded = definition["term"] in (plan["step2"].get("introduced_terms") or {})
    if definition["long_form"]:
        head = f"- {definition['term']} = {definition['long_form']}."
    else:
        head = f"- {definition['term']}."
    state = "Expanded in Layer 1 at first use." if expanded else "Not expanded in Layer 1."
    return f"{head} {definition['why'][0].upper() + definition['why'][1:]}. {state}"


def _set_aside_line(plan: dict, entry: dict) -> str:
    reasons = list(entry["reasons"])
    if entry["basis"]:
        reasons.append(entry["basis"][0].upper() + entry["basis"][1:] + ".")
    if not reasons:
        reasons.append(ROLE_TEXT.get(entry["role"], "Not stated as an answer to this item."))
    where = _label(plan, entry["paper_id"], "list")
    return f"- {' '.join(reasons)} Source passage ({where}): “{entry['quote'].strip()}”"


def render_layer2(plan: dict, props: dict) -> str:
    """Per-item supporting evidence: verbatim passages, the qualifications attached from the same paper with the reason each
    was attached and whether it reached Layer 1, grounded definitions, and set-aside candidates with fixed human reasons."""
    lines = [
        "# Supporting evidence (Layer 2, deterministic replay)",
        "",
        "Every passage is verbatim from the sealed source. A passage here is not an answer unless it also appears in Layer 1.",
        "",
    ]
    for node in plan["nodes"]:
        layer2 = node["layer2"]
        lines.append(f"## {node['label']}. {node['literal_text']}")
        lines.append("")
        lines.append(f"*{STATUS_LINE[node['status']]}*")
        lines.append("")
        lines.extend(_section("Supporting passages", [_passage_line(plan, p) for p in layer2["passages"]]))
        lines.extend(
            _section(
                "Qualifications and limitations from the same paper",
                [_limitation_line(plan, e) for e in layer2["limitations"]],
            )
        )
        lines.extend(
            _section("Definitions in the retrieved text", [_definition_line(plan, d) for d in layer2["definitions"]])
        )
        lines.extend(
            _section(
                "Attributed, adjacent, or set-aside evidence",
                [_set_aside_line(plan, e) for e in layer2["set_aside"]],
            )
        )
        lines.extend(_section("Not assessed in this run", layer2["not_assessed"]))
    return "\n".join(lines)


def render_layer3(plan: dict, authorization: dict) -> str:
    """Mechanical audit. Identifiers, hashes, roles, reason codes, and every facet state. Never shown in Layer 1."""
    lines = [
        "# Mechanical audit (Layer 3, deterministic replay)",
        "",
        f"- plan_sha256: `{plan['plan_sha256']}`",
        f"- plan_version: `{plan['plan_version']}`",
        f"- replay_authorization_sha256: `{authorization['authorization_sha256']}`",
        f"- source_label_extract_sha256: `{plan['inputs'].get('source_metadata_sha256')}`",
        f"- library_fingerprint_sha256: `{plan['inputs'].get('library_fingerprint_sha256')}`",
        f"- grounded acronyms: {plan['step2']['grounded_terms']}",
        f"- introduced in Layer 1: {list((plan['step2'].get('introduced_terms') or {}).keys())}",
        f"- promoted limitations: {plan['step2']['promoted_count']} of {plan['step2']['discovered_candidate_count']} candidates scanned",
        f"- structural section metadata present in sealed spans: {plan['step2']['structural_metadata_available']}",
        f"- node states: {plan['parent']['node_state_counts']}",
        "",
        "## Engine-complete relations not witnessed by one AnswerPlan passage",
        "",
    ]
    for item in plan["disagreements"] or [{"child_id": "none"}]:
        lines.append(
            f"- {item.get('child_id')} {item.get('requirement_id', '')} {item.get('instance_key', '')}".rstrip()
        )
    lines.append("")
    for node in plan["nodes"]:
        lines.append(f"## Node {node['label']} ({node['status']}) — children {', '.join(node['owning_child_ids'])}")
        lines.append("")
        lines.append("| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |")
        lines.append("|---|---|---|---|---|---|---|")
        for facet in node["facets"]:
            lines.append(
                f"| `{facet['facet_id']}` | {facet['state']} | {', '.join(facet['covered_roles']) or '-'} | "
                f"{', '.join(facet['uncovered_roles']) or '-'} | {', '.join(facet['uncovered_categories']) or '-'} | "
                f"{facet['relation_status'] or '-'} | {', '.join(f'`{c}`' for c in facet['claim_ids']) or '-'} |"
            )
        lines.append("")
        lines.append("Limitation decisions (every candidate from a contributing paper):")
        for decision in node["layer3"]["limitation_decisions"]:
            outcome = (
                "promoted" if decision.get("promoted") else f"not promoted ({decision.get('not_promoted_reason')})"
            )
            lines.append(
                f"- span `{decision['span_id']}` paper {decision['paper_id']} cues {decision['cues']}: "
                f"{outcome}; excluded: {decision['excluded'] or 'no'}; basis: {decision.get('promotion_basis') or []}"
            )
        lines.append("")
        lines.append("Definition decisions:")
        for definition in node["layer2"]["definitions"]:
            lines.append(
                f"- `{definition['term']}` long form {definition['long_form']}; same-paper spans "
                f"{definition['supporting_span_ids']}; other-paper spans {definition['other_paper_span_ids']}; {definition['why']}"
            )
        lines.append("")
        lines.append("Disclosure items (raw, before consolidation):")
        for item in node["layer3"]["disclosure_items"]:
            lines.append(
                f"- `{item['facet_id']}` {item['kind']}" + (f" code `{item['code']}`" if item.get("code") else "")
            )
        lines.append("")
    lines.append("## Claim roles")
    lines.append("")
    for record in plan["claim_roles"]:
        lines.append(
            f"- `{record['claim_id']}` role={record['role']} layer={record['layer']} "
            f"reasons={record['reasons'] or '-'} children={record['child_ids']}"
        )
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
    fixed_lines = [line for node in plan["nodes"] for line in node["disclosures"] + node["not_assessed"]]
    leaked = sorted({m.group(0).lower() for line in fixed_lines for m in LAYER3_VOCABULARY.finditer(line)})
    add("layer1_fixed_text_has_no_layer3_vocabulary", not leaked, leaked)
    missing = [n["label"] for n in plan["nodes"] if f"**{n['label']}. " not in layer1_text]
    add("every_confirmed_node_appears_with_literal_wording", not missing, missing)
    nested = [n["label"] for n in plan["nodes"] if n.get("parent")]
    add("nested_labels_visible", all(f"**{x}. " in layer1_text for x in nested), nested)
    add("no_linebreak_hyphen_artifacts", not re.search(r"[A-Za-z]- [a-z]", layer1_text))
    unexpanded = sorted(set(re.findall(r"\b[A-Z]{2,}\s*\([^)]{3,}\)", layer1_text)))
    add("no_acronym_expansion_printed", not unexpanded, unexpanded)
    grounded = set(plan["step2"]["grounded_terms"])
    ungrounded = sorted({m for m in re.findall(r"\(([A-Z]{2,})\)", layer1_text) if m not in grounded})
    add("parenthetical_acronyms_are_grounded", not ungrounded, ungrounded)
    for term, edit in (plan["step2"].get("introduced_terms") or {}).items():
        if edit.get("applied") == "expanded_at_first_use":
            add(f"expansion_printed:{term}", edit["to"] in layer1_text, edit["to"])
    bare_paper = re.findall(r"\bPaper \d+\b", layer1_text)
    add("layer1_uses_source_labels_not_paper_numbers", not bare_paper, bare_paper)
    repeated = {text: layer1_text.count(text) for text in list(REASON_TEXT.values()) + [POINTER]}
    repeated = {text[:60]: n for text, n in repeated.items() if n > 1}
    add("generic_explanation_stated_once_per_answer", not repeated, repeated)
    no_why = [e["text"][:60] for n in plan["nodes"] for e in n["layer2"]["limitations"] if not e["why_attached"]]
    add("every_attached_limitation_records_why", not no_why, no_why)
    states = {f["state"] for n in plan["nodes"] for f in n["facets"]}
    add(
        "every_facet_has_a_recorded_state",
        states <= {"answered", "partial", "not_established", "searched_empty"},
        sorted(states),
    )

    # Verbatim authority (D5): each statement, with its recorded edits reversed, is contained in its own passage.
    for _node, statement in statements:
        core = statement["text"]
        for edit in statement.get("edits") or []:
            if edit["kind"] in ("self_reference_to_source_label", "acronym_expansion_introduced"):
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
    add("U11_no_unsupported_expansion", not unexpanded and not ungrounded, unexpanded + ungrounded)
    add("U14_task_description_not_a_result", not any("several brain regions" in t for t in rendered))
    add("U15_display_hyphen_normalized", not re.search(r"attrac- tiveness|anomalous-is- bad", layer1_text))
    return checks
