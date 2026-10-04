"""Deterministic AnswerPlan assembly (Phase 30 Step 1). Pure: no model, no I/O beyond the inputs passed in.

Pipeline: overlay (confirmed visible structure) -> claims (deterministic ParentClaim ledger, reused unchanged) -> per-claim
classification (classify.py) -> facets and nodes -> de-duplication and subsumption -> derived answerability states and
fixed human-language disclosures. Nothing here chooses a new semantic binding. A relation is never assembled from two
passages; a direction is never printed without its operands.
"""

from __future__ import annotations

import re
from collections import defaultdict

from experiments.ask_cli_revised import parent_synthesis_ledger as psl
from experiments.ask_cli_revised.answer_plan import classify as cl
from experiments.ask_cli_revised.answer_plan import overlay as ov
from experiments.ask_cli_revised.answer_plan import relations as rel
from experiments.ask_cli_revised.answer_plan import text as tx

PLAN_VERSION = "answer-plan-step1-v1"

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
) -> dict:
    if frozen_contract is not None:
        problems = ov.validate_overlay(overlay, smap, frozen_contract)
        if problems:
            raise ValueError("overlay invalid: " + "; ".join(problems))
    props = {row["proposition_id"]: row for row in sealed["verified_propositions"]}
    span_texts: dict = defaultdict(list)
    for span in sealed["evidence_spans"]:
        span_texts[span["paper_id"]].append(span["text"])
    facet_terms = {}
    facet_phrases = overlay["facet_phrases"]
    for child in smap:
        for requirement in smap[child]["requirements"]:
            facet_terms[requirement["id"]] = list(overlay["requested_construct_terms"])
    ctx = cl.Ctx(
        props=props,
        span_texts_by_paper=dict(span_texts),
        generic_map=cl.build_generic_map(smap, props),
        facet_terms=facet_terms,
        facet_phrases=facet_phrases,
        corpus_words=tx.corpus_word_set([span["text"] for span in sealed["evidence_spans"]]),
    )
    claims = psl.build_claim_ledger(smap, sealed)
    units = rel.relation_units(smap)
    claim_by_id = {claim["claim_id"]: claim for claim in claims}
    evaluations = {claim["claim_id"]: cl.evaluate_claim(claim, ctx, units) for claim in claims}

    ctx.span_rows = [
        {"paper_id": span["paper_id"], "span_id": span["span_id"], "text": span["text"]}
        for span in sealed["evidence_spans"]
    ]
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

    nodes = []
    for node in overlay["nodes"]:
        nodes.append(_build_node(node, facets, evaluations, claim_by_id, units, ctx, overlay, resolved, smap))

    layer1_checked = [s for n in nodes for s in n["statement_texts"]]
    plan = {
        "plan_version": PLAN_VERSION,
        "inputs": dict(inputs or {}),
        "overlay_status": overlay["status"],
        "nodes": [{k: v for k, v in node.items() if k != "statement_texts"} for node in nodes],
        "claim_roles": [_claim_role_record(claim, evaluations[claim["claim_id"]], claim_by_id) for claim in claims],
        "relation_units": units,
        "disagreements": _disagreements(units),
        "parent": _parent_plan(nodes),
        "_layer1_check_texts": layer1_checked,
    }
    plan["plan_sha256"] = ov.sha256_obj({k: v for k, v in plan.items() if k != "_layer1_check_texts"})
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


def _reason_lines(facet_claims: list[dict], claim_by_id: dict, evaluations: dict) -> list[str]:
    reasons: list[str] = []
    for cid in facet_claims:
        evaluation = evaluations[cid]
        for reason in evaluation.get("reasons", []):
            if reason not in reasons:
                reasons.append(reason)
        for result in evaluation.get("value_results", []):
            for reason in result.get("reasons", []):
                if reason not in reasons:
                    reasons.append(reason)
    lines = []
    for reason in reasons:
        if reason in REASON_TEXT and reason not in SILENT_REASONS and REASON_TEXT[reason] not in lines:
            lines.append(REASON_TEXT[reason])
    return lines


def _join_phrases(phrases: list[str]) -> str:
    if len(phrases) <= 1:
        return "".join(phrases)
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


def _disclosures(
    facet: dict, state: dict, displayed: list[dict], facet_claims, claim_by_id, evaluations, ctx, overlay
) -> list[str]:
    """Fixed human-language lines for one facet. Never a role name, code, or id. A relational facet whose relation is not
    witnessed always says so (Phase-30 D3), naming the operands the answer layer could and could not establish."""
    roles_phrase = overlay["role_phrases"]
    lines: list[str] = []
    if state["state"] == ANSWERED:
        return lines
    if state["state"] == SEARCHED_EMPTY:
        return [f"The scoped search completed without establishing {facet['phrase']}."]
    required = facet["required_roles"]
    covered = set(state["covered_roles"])
    if facet["cardinality"]:
        if not displayed:
            lines.append(f"The retrieved evidence does not establish {facet['phrase']}.")
        for key in state.get("uncovered_categories", []):
            lines.append(
                f"The retrieved evidence does not establish {overlay['category_phrases'].get(key, key + ' findings')}."
            )
    elif facet["relation_required"] and facet["relation_status"] != "witnessed":
        phrases = [roles_phrase[r] for r in required]
        if set(required) <= covered:
            lines.append(
                f"The retrieved evidence reports {_join_phrases(phrases)} separately, but does not establish how they relate."
            )
        else:
            lines.append(f"The retrieved evidence does not establish how {_join_phrases(phrases)} relate.")
    else:
        if not displayed:
            lines.append(f"The retrieved evidence does not establish {facet['phrase']}.")
        elif state.get("uncovered_roles"):
            for role in state["uncovered_roles"]:
                lines.append(f"The retrieved evidence does not state {roles_phrase[role]} as a separate finding.")
    for line in _reason_lines(facet_claims, claim_by_id, evaluations)[:2]:
        if line not in lines:
            lines.append(line)
    return lines


_QUALIFICATION_CUE = re.compile(
    r"\b(?:limit\w*|proxies|proxy|may not|might not|cannot|further research|caveat|generaliz\w*)\b", re.IGNORECASE
)
_STOP = frozenset(
    "about after again against among because before being between could during every from have into more most other "
    "over same should some such than that their there these they this those through under until very when where which "
    "while with within would participants study research results were found been also".split()
)


def _content_tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z]{5,}", text) if t.lower() not in _STOP}


def _loose(text: str) -> str:
    """Comparison-only normalization: joins PDF line-break hyphens, drops punctuation, lowercases. It decides whether a
    sentence is contained in a verified quote. It is never used for display or for the rendered text."""
    joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", joined).lower().split())


_SCOPE_QUALIFIER = re.compile(
    r"\b(?:initial|preliminary|tentative\w*|rather than|interpret\w*|limitations?|limited|cannot|generaliz\w*|"
    r"further research|future research|durability|directly test\w*|possibility|alternative|explanation)\b",
    re.IGNORECASE,
)


_LITERATURE = re.compile(
    r"\b(?:meta-analys\w*|systematic review|(?:many|several|other|multiple|previous|prior|earlier|recent|existing)\s+"
    r"(?:studies|study|research|work|reports?|findings|investigations?)|studies (?:on|of)|the literature)\b",
    re.IGNORECASE,
)
_RATIONALE = re.compile(
    r"\b(?:motivated|we expected|expected|predict\w*|prediction|hypothes\w*|agnostic|anticipat\w*|expectation)\b",
    re.IGNORECASE,
)


def _qualification_candidates(statements: list[dict], props: dict, ctx: "cl.Ctx") -> tuple[list[dict], list[dict]]:
    """D6. A sealed SENTENCE that is not contained in any verified proposition's quote may QUALIFY (never create) a
    displayed finding. It must: carry an explicit limitation cue; come from the same paper; share at least two content
    words with the finding; and not be background or a stated aim (prior-work and aim sentences are literature, not
    qualifications). A qualifier is PROMOTED to Layer 1 only when it carries a scope qualifier AND stands on its own
    (closed, complete); otherwise the node carries a fixed pointer to it. Returns (attached, every decision)."""
    verified_quotes = [_loose(row["quote"]) for row in props.values()]
    attached: list[dict] = []
    decisions: list[dict] = []
    for span in ctx.span_rows:
        for sentence in tx.split_sentences(span["text"]):
            if not _QUALIFICATION_CUE.search(sentence):
                continue
            if any(_loose(sentence) in quote for quote in verified_quotes):
                continue
            kind = tx.attribution_kind(sentence, caption=False)
            background = (
                kind in ("prior_work", "aim_or_hypothesis")
                or bool(_LITERATURE.search(sentence))
                or bool(_RATIONALE.search(sentence))
            )
            standalone = not tx.closure_failures(sentence) and sentence.rstrip()[-1:] in '.!?)"”'
            scope = bool(_SCOPE_QUALIFIER.search(sentence))
            for statement in statements:
                paper = props[statement["prop_ids"][0]]["paper_id"]
                if span["paper_id"] != paper:
                    continue
                shared = sorted(_content_tokens(sentence) & _content_tokens(statement["text"]))
                record = {
                    "span_id": span["span_id"],
                    "paper_id": span["paper_id"],
                    "text": sentence,
                    "sentence_kind": kind,
                    "qualifies_claim_id": statement["claim_id"],
                    "shared_content_words": shared,
                    "attached": len(shared) >= 2 and not background,
                    "excluded_as_background": background and len(shared) >= 2,
                    "scope_qualifier": scope,
                    "standalone": standalone,
                    "promoted_to_layer1": len(shared) >= 2 and not background and scope and standalone,
                }
                decisions.append(record)
                if record["attached"]:
                    attached.append(record)
    return attached, decisions


def _term_support(items: list[tuple], ctx: "cl.Ctx") -> list[dict]:
    """U11. Every acronym in a displayed or candidate passage, with the explicit definitional support (if any) found in
    sealed text. Support is reported, never used to expand a term in a sentence the source did not expand."""
    found: dict[str, dict] = {}
    for text_item, paper in items:
        for term in tx.acronyms(text_item):
            if term not in found or not found[term]["supported"]:
                hit = tx.expansion_support(term, ctx.span_texts_by_paper, paper)
                found[term] = {"term": term, "supported": hit is not None, "support": hit}
    return [found[t] for t in sorted(found)]


def _build_node(node, facets, evaluations, claim_by_id, units, ctx, overlay, resolved, smap) -> dict:
    facet_rows = []
    statements: list[dict] = []
    disclosures: list[str] = []
    facet_states = []
    node_facet_ids = [r["id"] for child in node["owning_child_ids"] for r in smap[child]["requirements"]]
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
            lines = _disclosures(facet, state, pool, facet["claim_ids"], claim_by_id, evaluations, ctx, overlay)
            facet_rows.append(
                {
                    "facet_id": facet["facet_id"],
                    "phrase": facet["phrase"],
                    "state": state["state"],
                    "covered_roles": state["covered_roles"],
                    "required_roles": facet["required_roles"],
                    "relation_status": facet["relation_status"],
                    "claim_ids": facet["claim_ids"],
                    "displayed_render_count": len(displayed),
                    "disclosures": lines,
                }
            )
            for render in displayed:
                statements.append({**render, "facet_state": state["state"]})
            for line in lines:
                if line not in disclosures:
                    disclosures.append(line)
    if all(s == ANSWERED for s in facet_states):
        status = ANSWERED
    elif any(s in (ANSWERED, PARTIAL) for s in facet_states):
        status = PARTIAL
    elif all(s == SEARCHED_EMPTY for s in facet_states):
        status = SEARCHED_EMPTY
    else:
        status = NOT_ESTABLISHED
    obligations = []
    for obligation in node["human_review_obligations"]:
        phrase = overlay["obligation_phrases"][obligation]
        line = f"This run did not assess {phrase}."
        if line not in disclosures:
            obligations.append(line)
    qualifications, qualification_decisions = _qualification_candidates(
        [_statement_record(s) for s in statements], ctx.props, ctx
    )
    facet_of_claim = {s["claim_id"]: s["facet_id"] for s in statements}
    seen_qualifications: set = set()
    qualification_pointer = False
    promoted: list[dict] = []
    for record in qualifications:
        key = tx.normalized_key(record["text"])
        if key in seen_qualifications:
            continue
        seen_qualifications.add(key)
        if record["promoted_to_layer1"]:
            promoted.append(
                {
                    "claim_id": f"qualification:{record['span_id']}",
                    "facet_id": facet_of_claim.get(record["qualifies_claim_id"], node_facet_ids[0]),
                    "kind": "qualification_sentence",
                    "text": record["text"],
                    "prop_ids": [],
                    "span_id": record["span_id"],
                    "paper_id": record["paper_id"],
                    "span_text": record["text"],
                    "attribution": "qualification",
                    "edits": [],
                    "facet_state": None,
                    "subject": None,
                }
            )
        else:
            qualification_pointer = True
    statements = statements + promoted
    if qualification_pointer:
        pointer = "The paper adds a qualification to this result; it is listed in the supporting evidence."
        if pointer not in disclosures:
            disclosures.append(pointer)
    return {
        "label": node["label"],
        "parent": node["parent"],
        "nesting": node["nesting"],
        "literal_text": node["literal_text"],
        "owning_child_ids": node["owning_child_ids"],
        "status": status,
        "facets": facet_rows,
        "statements": [_statement_record(s) for s in statements],
        "disclosures": disclosures,
        "not_assessed": obligations,
        "statement_texts": [s["text"] for s in statements],
        "term_support": _term_support(
            [
                (s["text"], s["paper_id"] if "paper_id" in s else ctx.props[s["prop_ids"][0]]["paper_id"])
                for s in statements
            ]
            + [
                (ctx.props[pid]["quote"], ctx.props[pid]["paper_id"])
                for fid in node_facet_ids
                for cid in facets[fid]["claim_ids"]
                for pid in evaluations[cid].get("admissible_proposition_ids", [])
            ],
            ctx,
        ),
        "qualifications": qualifications,
        "qualification_candidates": qualification_decisions,
    }


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


def _claim_role_record(claim: dict, evaluation: dict, claim_by_id: dict) -> dict:
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
        "note": "Stored only. No count sentence is rendered in Layer 1 at Step 1 (Phase-30 D10).",
    }
