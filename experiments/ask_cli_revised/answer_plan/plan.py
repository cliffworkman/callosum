"""Deterministic AnswerPlan assembly (Phase 30 Step 1). Pure: no model, no I/O beyond the inputs passed in.

Pipeline: overlay (confirmed visible structure) -> claims (deterministic ParentClaim ledger, reused unchanged) -> per-claim
classification (classify.py) -> facets and nodes -> de-duplication and subsumption -> derived answerability states and
fixed human-language disclosures. Nothing here chooses a new semantic binding. A relation is never assembled from two
passages; a direction is never printed without its operands.
"""

from __future__ import annotations

from collections import defaultdict

from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised.answer_plan import classify as cl
from experiments.ask_cli_revised.answer_plan import overlay as ov
from experiments.ask_cli_revised.answer_plan import relations as rel
from experiments.ask_cli_revised.answer_plan import step2 as st
from experiments.ask_cli_revised.answer_plan import text as tx

PLAN_VERSION = "answer-plan-step2-v2"

# Fixed, human-language disclosure per candidate-rejection reason. Never a role name, claim id or reason code.
REASON_TEXT = {
    "passage_not_generic_summary": "A passage gives only a general summary, without a specific measure or result, so it is listed in the supporting evidence instead.",
    "referentially_closed": "A passage that bears on this question depends on context that is not in the retrieved text, so it is not stated as an answer.",
    "passage_complete": "A passage that may bear on this question ends before its finding is complete, so it is not stated.",
    "caption_source": "A table or figure caption mentions this topic, but the retrieved text does not give its results, so it is not stated as a finding.",
    "attribution_caption": "A table or figure caption mentions this topic, but the retrieved text does not give its results, so it is not stated as a finding.",
    "attribution_prior_work": "Earlier work reports this, and the retrieved text does not present it as this study's result, so it is listed in the supporting evidence.",
    "attribution_aim_or_hypothesis": "The authors present this as a suggestion or a study aim, so it is not stated as a result.",
    "attribution_unknown": "The retrieved text does not make clear that this is a result of the study, so it is not stated.",
    "requested_construct_direct": "Related evidence on a different construct is listed in the supporting evidence and does not answer this question.",
    "not_stimulus_rating": "A rating of stimuli is not stated as a characteristic of people.",
    "operands_not_in_one_sentence": "The relevant parts appear in separate sentences, so no single statement is given.",
    "direction_without_relation_or_subject": "A direction is reported without a stated relationship or subject, so it is not stated.",
}
# Reasons that describe a relation, already covered by the relation disclosure, or that carry no user-facing text.
SILENT_REASONS = {"unwitnessed_relation", "value_not_in_witness_sentence"}

ANSWERED, PARTIAL, NOT_ESTABLISHED, SEARCHED_EMPTY = "answered", "partial", "not_established", "searched_empty"


def _facet_for(claim: dict, facets: dict) -> str:
    """Owning facet: the requirement whose required roles include the claim's own role, else the first requirement."""
    candidates = sorted(claim["requirement_ids"])
    for rid in candidates:
        if rid in facets and claim.get("role") in facets[rid]["required_roles"]:
            return rid
    return candidates[0]


def _roles_of(claim: dict) -> set[str]:
    return {value["role"] for value in claim["values"] if value.get("role")} or (
        {claim["role"]} if claim.get("role") else set()
    )


def build_plan(
    sealed: dict,
    smap: dict,
    overlay: dict,
    *,
    scoped_final: dict | None = None,
    frozen_contract: dict | None = None,
    inputs: dict | None = None,
    labels: dict | None = None,
) -> dict:
    """`labels` maps paper id -> citeproc-style label record (source_metadata.labels_for). Papers without a label get the
    neutral label, so a missing metadata extract never blocks a replay."""
    if frozen_contract is not None:
        problems = ov.validate_overlay(overlay, smap, frozen_contract)
        if problems:
            raise ValueError("overlay invalid: " + "; ".join(problems))
    labels = dict(labels or {})
    props = {row["proposition_id"]: row for row in sealed["verified_propositions"]}
    span_texts: dict = defaultdict(list)
    for span in sealed["evidence_spans"]:
        span_texts[span["paper_id"]].append(span["text"])
    facet_terms = {}
    for child in smap:
        for requirement in smap[child]["requirements"]:
            facet_terms[requirement["id"]] = list(overlay["requested_construct_terms"])
    ctx = cl.Ctx(
        props=props,
        span_texts_by_paper=dict(span_texts),
        generic_map=cl.build_generic_map(smap, props),
        facet_terms=facet_terms,
        facet_phrases=overlay["facet_phrases"],
        corpus_words=tx.corpus_word_set([span["text"] for span in sealed["evidence_spans"]]),
        labels=labels,
    )
    ctx.span_rows = [
        {
            "paper_id": span["paper_id"],
            "span_id": span["span_id"],
            "text": span["text"],
            "section_family": span.get("section_family"),
        }
        for span in sealed["evidence_spans"]
    ]
    claims = psl.build_claim_ledger(smap, sealed)
    units = rel.relation_units(smap, sealed)
    evaluations = {claim["claim_id"]: cl.evaluate_claim(claim, ctx, units) for claim in claims}
    facets = _build_facets(smap, overlay, units)
    for claim in claims:
        evaluation = evaluations[claim["claim_id"]]
        facet_id = _facet_for(claim, facets)
        evaluation["facet_id"] = facet_id
        for render in evaluation["renders"]:
            render["facet_id"] = facet_id
            render["roles"] = sorted(_roles_of(claim))
            facets[facet_id]["renders"].append(render)
        facets[facet_id]["claim_ids"].append(claim["claim_id"])

    resolved = {o["requirement_id"] for o in psl.build_resolved_empty_outcomes(smap, scoped_final or {})}
    for node in overlay["nodes"]:
        facet_ids = [r["id"] for child in node["owning_child_ids"] for r in smap[child]["requirements"]]
        _dedupe_node(facet_ids, facets)

    nodes = [_build_node(node, facets, evaluations, ctx, overlay, resolved, smap) for node in overlay["nodes"]]
    step2 = st.finalize(nodes, ctx, props, _set_aside_by_node(overlay, smap, facets, evaluations, ctx))
    plan = {
        "plan_version": PLAN_VERSION,
        "inputs": dict(inputs or {}),
        "overlay_status": overlay["status"],
        "source_labels": {str(pid): labels[pid] for pid in sorted(labels)},
        "nodes": nodes,
        "step2": step2,
        "claim_roles": [_claim_role_record(claim, evaluations[claim["claim_id"]]) for claim in claims],
        "relation_units": units,
        "disagreements": _disagreements(units),
        "parent": _parent_plan(nodes),
    }
    plan["plan_sha256"] = ov.sha256_obj(plan)
    return plan


def _build_facets(smap, overlay, units) -> dict:
    facets: dict = {}
    for node in overlay["nodes"]:
        for child in node["owning_child_ids"]:
            for requirement in smap[child]["requirements"]:
                required = list(requirement["role_completion"]["required_roles"])
                facets[requirement["id"]] = {
                    "facet_id": requirement["id"],
                    "node_label": node["label"],
                    "child_id": child,
                    "phrase": overlay["facet_phrases"][requirement["id"]],
                    "required_roles": required,
                    "cardinality": requirement["instance_quantifier"] == "all_requested_categories",
                    "relation_required": requirement.get("kind") == "relational",
                    "relation_status": rel.requirement_relation_status(units, requirement["id"]),
                    "instances": _instance_bindings(requirement, required),
                    "renders": [],
                    "claim_ids": [],
                }
    return facets


def _instance_bindings(requirement, required) -> dict:
    """instance key -> {role: filled binding text}. Used for role and category coverage, never to create content."""
    out = {}
    for instance in requirement["instances"]:
        texts = {}
        for role in required:
            binding = instance["role_bindings"].get(role) or {}
            if binding.get("state") == "filled" and binding.get("exact_text"):
                texts[role] = binding["exact_text"]
        out[instance["instance_key"]] = texts
    return out


def _dedupe_node(facet_ids: list[str], facets: dict) -> None:
    """Within one node (across its facets): identical normalized sentences collapse to the first. The kept render takes
    the values of every duplicate, so a value whose own sentence is the same passage is still covered. A value sentence
    contained in a relation sentence is subsumed by that relation (Phase-29 S1/S2)."""
    renders = [r for fid in facet_ids for r in facets[fid]["renders"]]
    kept: dict[str, dict] = {}
    relation_renders = [r for r in renders if r["kind"] == "relation_sentence"]
    for render in renders:
        key = tx.normalized_key(render["text"])
        render["status"] = "displayed"
        if key in kept and kept[key]["claim_id"] != render["claim_id"]:
            render["status"] = "duplicate"
            render["duplicate_of"] = kept[key]["claim_id"]
            for value in render.get("values", []):
                if value not in kept[key]["values"]:
                    kept[key]["values"].append(value)
            continue
        kept.setdefault(key, render)
        if render["kind"] != "relation_sentence":
            for relation in relation_renders:
                if relation is not render and tx.contains(render["text"], relation["text"]):
                    render["status"] = "subsumed"
                    render["subsumed_by"] = relation["claim_id"]
                    break


def _displayed(facet: dict) -> list[dict]:
    return [r for r in facet["renders"] if r.get("status") == "displayed"]


def _coverage_pool(facet: dict, kept_by_claim: dict) -> list[dict]:
    """Renders that count toward this facet's coverage: its own displayed renders, plus the displayed sentence that each
    of its duplicate renders resolved to (a sentence may be displayed under another facet and still witness this one)."""
    pool = _displayed(facet)
    for render in facet["renders"]:
        if render.get("status") == "duplicate" and render.get("duplicate_of") in kept_by_claim:
            pool.append(kept_by_claim[render["duplicate_of"]])
    return pool


def _covered_roles(facet: dict, displayed: list[dict]) -> set[str]:
    covered: set[str] = set()
    for render in displayed:
        covered.update(render.get("roles") or [])
    texts = [render["text"] for render in displayed]
    for instance_texts in facet["instances"].values():
        for role, binding_text in instance_texts.items():
            if any(tx.contains(binding_text, text) for text in texts):
                covered.add(role)
    return covered


def _covered_categories(facet: dict, displayed: list[dict]) -> set[str]:
    covered: set[str] = set()
    for render in displayed:
        values = {tx.normalized_key(v) for v in render.get("values", [])}
        for key, instance_texts in facet["instances"].items():
            for binding_text in instance_texts.values():
                if tx.normalized_key(binding_text) in values:
                    covered.add(key)
    return covered


def _facet_state(facet: dict, displayed: list[dict], resolved: set[str]) -> dict:
    covered = _covered_roles(facet, displayed)
    required = set(facet["required_roles"])
    rel_ok = (not facet["relation_required"]) or facet["relation_status"] == "witnessed"
    result = {"covered_roles": sorted(covered), "relation_status": facet["relation_status"]}
    if facet["cardinality"]:
        cats = _covered_categories(facet, displayed)
        result["covered_categories"] = sorted(cats)
        result["uncovered_categories"] = sorted(set(facet["instances"]) - cats)
        if not displayed:
            state = SEARCHED_EMPTY if facet["facet_id"] in resolved else NOT_ESTABLISHED
        elif not result["uncovered_categories"]:
            state = ANSWERED
        else:
            state = PARTIAL
        result["state"] = state
        return result
    if not displayed:
        state = SEARCHED_EMPTY if facet["facet_id"] in resolved else NOT_ESTABLISHED
    elif required <= covered and rel_ok:
        state = ANSWERED
    else:
        state = PARTIAL
    result["state"] = state
    result["uncovered_roles"] = sorted(required - covered)
    return result


def _join_phrases(phrases: list[str]) -> str:
    if len(phrases) <= 1:
        return "".join(phrases)
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


def _reasons(facet_claims: list[str], evaluations: dict) -> list[str]:
    """Distinct reason codes across a facet's claims, in first-seen order. Silent codes carry no user-facing text."""
    codes: list[str] = []
    for cid in facet_claims:
        evaluation = evaluations[cid]
        found = list(evaluation.get("reasons", []))
        for result in evaluation.get("value_results", []):
            found.extend(result.get("reasons", []))
        for code in found:
            if code in REASON_TEXT and code not in SILENT_REASONS and code not in codes:
                codes.append(code)
    return codes


def _disclosure_items(facet: dict, state: dict, displayed: list[dict], evaluations: dict, overlay: dict) -> list[dict]:
    """Structured per-facet disclosure items (Step 2, A). Each item keeps one facet's own state, so consolidation in step2.py
    may word items together but never drops or merges their states. `text` is the item's standalone wording."""
    roles_phrase = overlay["role_phrases"]
    items: list[dict] = []

    def add(kind: str, text: str, phrase: str | None = None, **extra) -> None:
        items.append({"kind": kind, "facet_id": facet["facet_id"], "phrase": phrase, "text": text, **extra})

    if state["state"] == ANSWERED:
        return items
    if state["state"] == SEARCHED_EMPTY:
        add("searched_empty", f"The scoped search completed without establishing {facet['phrase']}.", facet["phrase"])
        return items
    required = facet["required_roles"]
    covered = set(state["covered_roles"])
    if facet["cardinality"]:
        if not displayed:
            add("not_established", f"The retrieved evidence does not establish {facet['phrase']}.", facet["phrase"])
        else:
            for key in state.get("uncovered_categories", []):
                phrase = overlay["category_phrases"].get(key, key + " findings")
                add("not_established", f"The retrieved evidence does not establish {phrase}.", phrase, category=key)
    elif facet["relation_required"] and facet["relation_status"] != "witnessed":
        phrases = [roles_phrase[r] for r in required]
        if set(required) <= covered:
            text = f"The retrieved evidence reports {_join_phrases(phrases)} separately, but does not establish how they relate."
        else:
            text = f"The retrieved evidence does not establish how {_join_phrases(phrases)} relate."
        add("relation_unwitnessed", text)
    elif not displayed:
        add("not_established", f"The retrieved evidence does not establish {facet['phrase']}.", facet["phrase"])
    else:
        for role in state.get("uncovered_roles", []):
            add(
                "role_missing",
                f"The retrieved evidence does not state {roles_phrase[role]} as a separate finding.",
                role=role,
            )
    reason_items: list[dict] = []
    for code in _reasons(facet["claim_ids"], evaluations):
        if all(item["text"] != REASON_TEXT[code] for item in reason_items):
            reason_items.append(
                {
                    "kind": "reason",
                    "facet_id": facet["facet_id"],
                    "phrase": None,
                    "text": REASON_TEXT[code],
                    "code": code,
                }
            )
    items.extend(reason_items[:2])
    return items


def _build_node(node, facets, evaluations, ctx, overlay, resolved, smap) -> dict:
    facet_rows = []
    statements: list[dict] = []
    items: list[dict] = []
    facet_states = []
    kept_by_claim = {
        r["claim_id"]: r
        for child in node["owning_child_ids"]
        for requirement in smap[child]["requirements"]
        for r in _displayed(facets[requirement["id"]])
    }
    for child in node["owning_child_ids"]:
        for requirement in smap[child]["requirements"]:
            facet = facets[requirement["id"]]
            displayed = _displayed(facet)
            pool = _coverage_pool(facet, kept_by_claim)
            state = _facet_state(facet, pool, resolved)
            facet_states.append(state["state"])
            facet_items = _disclosure_items(facet, state, pool, evaluations, overlay)
            items.extend(facet_items)
            facet_rows.append(
                {
                    "facet_id": facet["facet_id"],
                    "phrase": facet["phrase"],
                    "state": state["state"],
                    "covered_roles": state["covered_roles"],
                    "uncovered_roles": state.get("uncovered_roles", []),
                    "required_roles": facet["required_roles"],
                    "covered_categories": state.get("covered_categories", []),
                    "uncovered_categories": state.get("uncovered_categories", []),
                    "relation_status": facet["relation_status"],
                    "claim_ids": facet["claim_ids"],
                    "displayed_render_count": len(displayed),
                    "disclosures": [item["text"] for item in facet_items],
                }
            )
            statements.extend({**render, "facet_state": state["state"]} for render in displayed)
    if all(s == ANSWERED for s in facet_states):
        status = ANSWERED
    elif any(s in (ANSWERED, PARTIAL) for s in facet_states):
        status = PARTIAL
    elif all(s == SEARCHED_EMPTY for s in facet_states):
        status = SEARCHED_EMPTY
    else:
        status = NOT_ESTABLISHED
    obligations = [
        f"This run did not assess {overlay['obligation_phrases'][o]}." for o in node["human_review_obligations"]
    ]
    return {
        "label": node["label"],
        "parent": node["parent"],
        "nesting": node["nesting"],
        "literal_text": node["literal_text"],
        "owning_child_ids": node["owning_child_ids"],
        "status": status,
        "facets": facet_rows,
        "statements": [_statement_record(s) for s in statements],
        "disclosure_items": items,
        "not_assessed": obligations,
        "disclosures": [],
    }


def _set_aside_by_node(overlay: dict, smap: dict, facets: dict, evaluations: dict, ctx) -> dict:
    """Layer-2 records of candidate passages that were not stated as an answer: attributed, adjacent, duplicate, subsumed,
    or suppressed. Each keeps its verbatim passage and the fixed human reasons (none is a claim id or a role name)."""
    out: dict = {}
    for node in overlay["nodes"]:
        entries: list[dict] = []
        seen: set = set()
        for child in node["owning_child_ids"]:
            for requirement in smap[child]["requirements"]:
                for cid in facets[requirement["id"]]["claim_ids"]:
                    evaluation = evaluations[cid]
                    statuses = {r.get("status") for r in evaluation.get("renders", [])}
                    if "displayed" in statuses:
                        continue
                    if "duplicate" in statuses:
                        basis = "the same sentence is stated under another item"
                    elif "subsumed" in statuses:
                        basis = "the sentence is contained in a relation stated above"
                    else:
                        basis = None
                    reasons = [REASON_TEXT[code] for code in _reasons([cid], evaluations)]
                    for pid in evaluation.get("admissible_proposition_ids") or []:
                        key = tx.normalized_key(ctx.props[pid]["quote"])
                        if key in seen:
                            continue
                        seen.add(key)
                        entries.append(
                            {
                                "claim_id": cid,
                                "proposition_id": pid,
                                "paper_id": ctx.props[pid]["paper_id"],
                                "quote": ctx.props[pid]["quote"],
                                "role": evaluation.get("role"),
                                "basis": basis,
                                "reasons": reasons,
                            }
                        )
        out[node["label"]] = entries
    return out


def _statement_record(render: dict) -> dict:
    return {
        "claim_id": render["claim_id"],
        "facet_id": render["facet_id"],
        "kind": render["kind"],
        "text": render["text"],
        "prop_ids": render["prop_ids"],
        "attribution": render["attribution"],
        "edits": render["edits"],
        "facet_state": render.get("facet_state"),
        "subject": render.get("subject"),
        "span_id": render.get("span_id"),
        "paper_id": render.get("paper_id"),
        "span_text": render.get("span_text"),
        "values": render.get("values"),
    }


def _claim_role_record(claim: dict, evaluation: dict) -> dict:
    record = _claim_role_fields(claim, evaluation)
    if "direction_target" in evaluation:  # Phase 32 / I1b: present on direction claims only
        record["direction_target"] = evaluation["direction_target"]
    return record


def _claim_role_fields(claim: dict, evaluation: dict) -> dict:
    renders = evaluation.get("renders", [])
    return {
        "claim_id": claim["claim_id"],
        "claim_kind": claim["claim_kind"],
        "child_ids": claim["child_ids"],
        "requirement_ids": claim["requirement_ids"],
        "role_in_claim": claim.get("role"),
        "facet_id": evaluation.get("facet_id"),
        "role": evaluation.get("role"),
        "layer": evaluation.get("layer"),
        "reasons": evaluation.get("reasons", []),
        "value_results": evaluation.get("value_results", []),
        "sentence_attempts": evaluation.get("sentence_attempts", []),
        "render_status": [
            {
                "text": r["text"],
                "status": r.get("status"),
                "duplicate_of": r.get("duplicate_of"),
                "subsumed_by": r.get("subsumed_by"),
            }
            for r in renders
        ],
        "admissible_proposition_ids": evaluation.get("admissible_proposition_ids"),
        "attached_unit": evaluation.get("attached_unit"),
        "enumeration_candidate": evaluation.get("enumeration_candidate"),
        "direction_sign": evaluation.get("direction_sign"),
    }


def _disagreements(units: list[dict]) -> list[dict]:
    return [
        {
            "child_id": u["child_id"],
            "requirement_id": u["requirement_id"],
            "instance_key": u["instance_key"],
            "engine_complete": True,
            "answerplan_relation_witnessed": False,
            "parent_context_operand_roles": u["parent_context_operand_roles"],
        }
        for u in units
        if u["status"] == "unwitnessed_complete"
    ]


def _parent_plan(nodes: list[dict]) -> dict:
    counts = {ANSWERED: 0, PARTIAL: 0, NOT_ESTABLISHED: 0, SEARCHED_EMPTY: 0}
    for node in nodes:
        counts[node["status"]] = counts.get(node["status"], 0) + 1
    allowed = [f"{node['label']}:{i}" for node in nodes for i, _ in enumerate(node["statements"])]
    return {
        "allowed_statement_ids": allowed,
        "node_state_counts": counts,
        "note": "Stored only. No count sentence is rendered in Layer 1 (Phase-30 D10).",
    }
