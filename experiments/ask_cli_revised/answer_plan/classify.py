"""Deterministic claim classification for the Phase-30 AnswerPlan. Pure: no model, no I/O.

Every candidate sentence is tested against its own verbatim source passage. A sentence is renderable only if EVERY
check passes. Each check is recorded, so the audit shows why a candidate was primary, attributed, duplicate, subsumed,
suppressed, or Layer-2-only. The only rendering units are verbatim source sentences (with recorded, meaning-neutral edits)
and, for multi-value category lists, an enumeration whose values are all verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.backend.pdf_processing.extraction import canonicalize_quote_text
from experiments.ask_cli_revised.answer_plan import direction_target as dt
from experiments.ask_cli_revised.answer_plan import relations as rel
from experiments.ask_cli_revised.answer_plan import text as tx


@dataclass
class Ctx:
    props: dict  # proposition_id -> sealed row
    span_texts_by_paper: dict  # paper_id -> [span text]
    generic_map: dict  # canonical whole-passage quote -> requirement ids that bound it as a predicate match
    facet_terms: dict  # requirement_id -> requested-construct terms
    facet_phrases: dict  # requirement_id -> human phrase
    corpus_words: set = field(default_factory=set)

    labels: dict = field(default_factory=dict)  # paper id -> label record (source_metadata.label_for)

    def paper_label(self, paper_id) -> str:
        """The narrative source label for a paper, from library metadata; neutral when metadata are absent."""
        record = self.labels.get(paper_id)
        return record["narrative"] if record else f"Source {paper_id}"

    def generic_requirements(self, quote: str) -> list[str]:
        return sorted(self.generic_map.get(canonicalize_quote_text(quote), ()))


def build_generic_map(smap: dict, props: dict) -> dict:
    """Whole-passage predicate bindings (the achieved-outcome strategy returns the whole passage). A passage that is bound
    this way under two or more distinct requirements is a generic summary, not a specific finding for any of them
    (Phase-30 U1). Keys are canonical quote text, so identical sentences from different propositions group together."""
    out: dict[str, set] = {}
    for child in smap:
        for requirement in smap[child]["requirements"]:
            specs = requirement["role_specs"]
            for instance in requirement["instances"]:
                for role, binding in instance["role_bindings"].items():
                    if binding.get("state") != "filled":
                        continue
                    if (specs.get(role) or {}).get("mapping_strategy") != "achieved_outcome_predicate":
                        continue
                    key = canonicalize_quote_text(binding.get("exact_text") or "")
                    if key:
                        out.setdefault(key, set()).add(requirement["id"])
    return out


def _check(name: str, passed: bool, detail=None) -> dict:
    return {"check": name, "passed": bool(passed), "detail": detail}


def evaluate_sentence(sentence: str, prop_id, ctx: Ctx, requirement_ids: list, *, trait_role: bool = False) -> dict:
    """Test one candidate sentence against the verbatim passage it came from. Pure."""
    row = ctx.props[prop_id]
    quote = row["quote"]
    spans = ctx.span_texts_by_paper.get(row["paper_id"], [])
    caption = tx.is_caption_passage(quote, spans)
    kind = tx.attribution_kind(quote, caption)
    generic_ids = ctx.generic_requirements(quote)
    stripped, edit_heading = tx.strip_run_in_heading(sentence)
    final, edit_label = tx.substitute_source_label(stripped, ctx.paper_label(row["paper_id"]))
    closure = tx.closure_failures(final)
    terms = [term for rid in requirement_ids for term in ctx.facet_terms.get(rid, [])]
    checks = [
        _check("caption_source", not caption),
        _check("passage_complete", not tx.is_truncated(quote)),
        _check("passage_not_generic_summary", len(generic_ids) < 2, generic_ids),
        _check(f"attribution_{kind}", kind == "this_study_result", kind),
        _check("referentially_closed", not closure, closure),
        _check("requested_construct_direct", tx.construct_direct(quote, spans, terms)),
    ]
    if trait_role:
        checks.append(_check("not_stimulus_rating", not tx.stimulus_rating_cue(quote)))
    edits = [edit for edit in (edit_heading, edit_label) if edit]
    return {
        "ok": all(c["passed"] for c in checks),
        "prop_id": prop_id,
        "sentence": final,
        "raw_sentence": sentence,
        "attribution": kind,
        "checks": checks,
        "reasons": [c["check"] for c in checks if not c["passed"]],
        "edits": edits,
    }


def _candidates_containing(texts: list[str], claim: dict, ctx: Ctx) -> list[tuple]:
    """(proposition id, sentence) pairs where one sentence of the verbatim passage contains every given text."""
    out = []
    for pid in sorted(claim["admissible_proposition_ids"]):
        for sentence in tx.split_sentences(ctx.props[pid]["quote"]):
            if all(tx.contains(text, sentence) for text in texts):
                out.append((pid, sentence))
    return out


def _render(kind: str, claim: dict, attempt: dict, values: list[str], facet_id: str) -> dict:
    return {
        "kind": kind,
        "claim_id": claim["claim_id"],
        "facet_id": facet_id,
        "text": attempt["sentence"],
        "values": values,
        "prop_ids": [attempt["prop_id"]],
        "attribution": attempt["attribution"],
        "edits": attempt["edits"],
    }


def evaluate_claim(claim: dict, ctx: Ctx, units: list[dict]) -> dict:
    """Role and renderable candidates for one ParentClaim. The returned dict is the audit record for that claim."""
    record = {
        "claim_id": claim["claim_id"],
        "claim_kind": claim["claim_kind"],
        "child_ids": claim["child_ids"],
        "requirement_ids": claim["requirement_ids"],
        "role_in_claim": claim.get("role"),
        "admissible_proposition_ids": sorted(claim["admissible_proposition_ids"]),
        "renders": [],
        "value_results": [],
        "reasons": [],
    }
    primary_facet = _primary_facet(claim)
    if claim["claim_kind"] == "direction_or_effectiveness":
        return _evaluate_direction(claim, ctx, units, record)
    if claim["claim_kind"] == "relational":
        return _evaluate_relational(claim, ctx, units, record, primary_facet)
    return _evaluate_values(claim, ctx, record, primary_facet)


def _primary_facet(claim: dict) -> str:
    return sorted(claim["requirement_ids"])[0]


def _evaluate_relational(claim, ctx, units, record, facet_id) -> dict:
    if not rel.claim_witnessed(units, claim):
        record.update(role="suppressed", reasons=["unwitnessed_relation"], layer="layer2")
        return record
    texts = [value["exact_text"] for value in claim["values"]]
    attempts = [
        evaluate_sentence(sentence, pid, ctx, claim["requirement_ids"], trait_role=_trait(claim))
        for pid, sentence in _candidates_containing(texts, claim, ctx)
    ]
    if not attempts:
        record.update(role="suppressed", reasons=["operands_not_in_one_sentence"], layer="layer2")
        return record
    winner = next((a for a in attempts if a["ok"]), None)
    record["sentence_attempts"] = [{"prop_id": a["prop_id"], "reasons": a["reasons"]} for a in attempts]
    if winner is None:
        record.update(role="suppressed", reasons=attempts[0]["reasons"], layer="layer2")
        return record
    record["renders"].append(_render("relation_sentence", claim, winner, texts, facet_id))
    record.update(role="primary", reasons=[], layer="layer1")
    return record


def _trait(claim: dict) -> bool:
    return any("trait" in (value.get("role") or "") for value in claim["values"])


def _evaluate_values(claim, ctx, record, facet_id) -> dict:
    values: list[str] = []
    for value in claim["values"]:
        if value["exact_text"] not in values:
            values.append(value["exact_text"])
    results = []
    for value_text in values:
        attempts = [
            evaluate_sentence(sentence, pid, ctx, claim["requirement_ids"], trait_role=_trait(claim))
            for pid, sentence in _candidates_containing([value_text], claim, ctx)
        ]
        if not attempts:
            results.append({"value": value_text, "ok": False, "reasons": ["value_not_in_witness_sentence"]})
            continue
        winner = next((a for a in attempts if a["ok"]), None)
        if winner:
            results.append({"value": value_text, "ok": True, "attempt": winner})
        else:
            results.append({"value": value_text, "ok": False, "reasons": attempts[0]["reasons"]})
    record["value_results"] = [{k: v for k, v in r.items() if k != "attempt"} for r in results]
    passing = [r for r in results if r["ok"]]
    if not passing:
        reasons = []
        for r in results:
            for reason in r["reasons"]:
                if reason not in reasons:
                    reasons.append(reason)
        role = (
            "attributed_only" if reasons and all(r.startswith("attribution_prior") for r in reasons) else "suppressed"
        )
        record.update(role=role, reasons=reasons, layer="layer2")
        return record
    phrase = ctx.facet_phrases.get(facet_id)
    enumerable = (
        claim["claim_kind"] == "category_list"
        and phrase is not None
        and len(passing) >= 2
        and all(
            len(r["value"].split()) >= 2
            and len(tx.split_sentences(r["value"])) == 1
            and r["value"].rstrip()[-1:] not in ".!?"
            and not tx.negation_or_hedge(r["attempt"]["sentence"])
            for r in passing
        )
    )
    if enumerable:
        values = [r["value"] for r in passing]
        label = phrase[:1].upper() + phrase[1:]
        record["renders"].append(
            {
                "kind": "enumeration",
                "claim_id": claim["claim_id"],
                "facet_id": facet_id,
                "text": f"{label}: " + "; ".join(values) + ".",
                "values": values,
                "prop_ids": sorted({r["attempt"]["prop_id"] for r in passing}),
                "attribution": "this_study_result",
                "edits": [],
            }
        )
        record.update(role="primary", reasons=[], layer="layer1")
        return record
    by_sentence: dict[str, dict] = {}
    for r in passing:
        attempt = r["attempt"]
        key = tx.normalized_key(attempt["sentence"])
        if key in by_sentence:
            # Two values witnessed by the same sentence: one render, both values recorded.
            by_sentence[key]["values"].append(r["value"])
            continue
        by_sentence[key] = _render("value_sentence", claim, attempt, [r["value"]], facet_id)
        record["renders"].append(by_sentence[key])
    record.update(role="primary", reasons=[], layer="layer1")
    if claim["claim_kind"] == "category_list" and len(passing) >= 2:
        if all(len(r["value"].split()) >= 2 for r in passing) and all(
            not tx.negation_or_hedge(r["attempt"]["sentence"]) for r in passing
        ):
            record["enumeration_candidate"] = {"values": [r["value"] for r in passing], "eligible": True}
    return record


def _operand_surfaces(unit: dict) -> dict[str, str]:
    return {op["role"]: op["exact_text"] for op in unit["operands"] if op.get("exact_text")}


def _evaluate_direction(claim, ctx, units, record) -> dict:
    """Phase 32 / I1b. A direction is attached to a relation only when the witness sentence itself targets the
    relational predicate. An operand-targeted sign is rendered as valence of that operand, identified by role. Any other
    sign is suppressed. A direction is never attached to a relation by proximity."""
    summary = claim["direction_or_effectiveness"]
    sign = summary.get("consensus_value")
    keys = set(claim["instance_keys"])
    admissible = set(claim["admissible_proposition_ids"])
    mine = [u for u in units if u["instance_key"] in keys and u["requirement_id"] in claim["requirement_ids"]]
    for unit in mine:
        if unit["status"] != "witnessed":
            continue
        surfaces = _operand_surfaces(unit)
        for pid in sorted(admissible & set(unit["witness_ids"])):
            for sentence in tx.split_sentences(ctx.props[pid]["quote"]):
                if dt.classify_sentence(sentence, surfaces, sign)["target"] == "relation":
                    record.update(
                        role="attached_to_relation",
                        attached_unit=f"{unit['child_id']}/{unit['requirement_id']}",
                        reasons=[],
                        layer="layer1_via_relation",
                        direction_target="relation",
                    )
                    return record
    attempts: list[dict] = []
    targets: list[str] = []
    if sign:
        for pid in sorted(admissible):
            for sentence in tx.split_sentences(ctx.props[pid]["quote"]):
                for unit in mine:
                    surfaces = _operand_surfaces(unit)
                    target = dt.classify_sentence(sentence, surfaces, sign)
                    targets.append(target["target"])
                    if target["target"] != "operand":
                        continue
                    subject = surfaces[target["role"]]
                    if not tx.contains(subject, sentence):
                        continue
                    attempt = evaluate_sentence(sentence, pid, ctx, claim["requirement_ids"])
                    attempt["subject"] = subject
                    attempts.append(attempt)
    winner = next((a for a in attempts if a["ok"]), None)
    if winner:
        render = _render("value_level_valence", claim, winner, [sign], _primary_facet(claim))
        render["subject"] = winner["subject"]
        record["renders"].append(render)
        record.update(role="value_level", reasons=[], layer="layer1", direction_sign=sign, direction_target="operand")
        return record
    if "relation" in targets:
        reasons, target = ["direction_relation_not_attachable"], "relation"
    elif "unknown" in targets:
        reasons, target = ["direction_target_unresolved"], "unknown"
    elif attempts:
        reasons, target = attempts[0]["reasons"], "operand"
    else:
        reasons, target = ["direction_without_relation_or_subject"], "none"
    record.update(role="suppressed", reasons=reasons, layer="layer2", direction_sign=sign, direction_target=target)
    return record
