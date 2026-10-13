"""Restrict authorized value-local display inputs using existing presentation checks.

Two corrections to how those checks are applied here (2026-10-13), both narrowing a restriction that withheld
verified, authorized evidence. The checks themselves are unchanged; the corrections are in
``answer_plan.display_corrections`` and apply only when ``corrected`` is set, which the fresh route does. A
recorded reproduction (Profile B over the preserved Phase 28 evidence) keeps the original behavior exactly.

1. Referential closure is judged on the text actually proposed for display. When the display envelope narrows a
   sentence to a clause, the original sentence's closure failure no longer vetoes the clause, provided the clause
   passes the closure check itself and the words removed carry no negation, hedge, condition, contrast or causal
   cue. Every other restriction of the original sentence still applies. The decision and the removed words are
   recorded on the attempt. A second value of the same proposition whose own authorized sentence fails only that
   check may be shown with the same clause, when the clause lies inside its sentence and contains its literal. No
   source, proposition or value association is added: the clause is a verbatim part of a quotation that value was
   already authorized to display.
2. A qualified result is not an aim. A passage whose own results are the subject of "suggest / indicate / show"
   is not withheld as ``aim_or_hypothesis`` merely because it also contains the noun "hypothesis". An author's own
   interpretation ("we suggest"), a stated aim, or a prediction keeps its classification. The sentence is shown
   verbatim, so its hedge stays in the displayed text.
"""

from experiments.ask_cli_revised._layerc_common import plain, require, text_hash
from experiments.ask_cli_revised.answer_plan import classify as cl
from experiments.ask_cli_revised.answer_plan import display_corrections as dc
from experiments.ask_cli_revised.answer_plan import text as tx


def finalize_display(projection, sealed, authored, *, corrected=False):
    r = projection.records
    props = {p["proposition_id"]: plain(p) for p in sealed["verified_propositions"]}
    spans = {}
    for s in sealed["evidence_spans"]:
        spans.setdefault(s["paper_id"], []).append(s["text"])
    overlay = authored["overlay"]
    specs = {q["id"]: q for rows in authored["requirements"].values() for q in rows}
    generic = {}
    for path in r["value_coverage"].values():
        value = r["semantic_values"][path["value_id"]]
        if value["kind"] not in ("evidence_slot", "literal_assertion"):
            continue
        view = r["support_views"][path["establishment_refs"][0]["ref"]]
        record = r["support_records"][view["support_ref"]]
        generic.setdefault(cl.canonicalize_quote_text(record["exact_text"]), set()).add(
            path["placement"]["requirement_id"]
        )
    finalized = {}
    closure_only = []  # attempts that failed on referential closure alone, kept with what a retry needs
    for ref, path in sorted(r["value_coverage"].items()):
        value = r["semantic_values"][path["value_id"]]
        attempts, accepted = [], []
        for source in path["authorized_display_source_refs"]:
            require(source in path["citation_source_refs"], "unauthorized display/citation association")
            record = r["sources"][source["source_ref"]]
            pid = source["proposition_id"]
            prop = props[pid]
            require(text_hash(prop["quote"]) == record["quote_sha256"], "presentation sealed source mismatch")
            envelope = r["display_envelopes"][source["display_envelope_ref"]]
            left, right = envelope["display_span"]
            passage = prop["quote"][left:right]
            require(envelope["semantic_support_added"] is False, "wrapper cannot add support")
            # The source is already authorized for this value. Text matching only validates
            # presentation inside that exact envelope and never discovers another association.
            selected = r["support_views"][path["establishment_refs"][0]["ref"]]
            exact = r["support_records"][selected["support_ref"]]["exact_text"]
            target = value.get("literal", exact)
            local_props = {pid: {**prop, "quote": passage}}
            ctx = cl.Ctx(
                props=local_props,
                span_texts_by_paper=spans,
                generic_map=generic,
                facet_terms={path["placement"]["requirement_id"]: list(overlay.get("requested_construct_terms", []))},
                facet_phrases=plain(overlay.get("facet_phrases", {})),
                direction_semantics="sufficiency-semantics-v8",
            )
            for sentence in tx.split_sentences(passage):
                if not tx.contains(target, sentence):
                    continue
                attempt = cl.evaluate_sentence(
                    sentence,
                    pid,
                    ctx,
                    [path["placement"]["requirement_id"]],
                    trait_role=any(
                        "trait" in role for role in specs[path["placement"]["requirement_id"]]["role_specs"]
                    ),
                )
                # Existing passage/context restrictions still apply after narrowing. This
                # can only remove permission; the original sentence never becomes display
                # evidence and cannot expand the accepted envelope.
                if corrected:
                    attempt = dc.qualified_result_not_aim(attempt, passage)
                if passage != prop["quote"]:
                    source_ctx = cl.Ctx(
                        props={pid: prop},
                        span_texts_by_paper=spans,
                        generic_map=generic,
                        facet_terms=ctx.facet_terms,
                        facet_phrases=ctx.facet_phrases,
                        direction_semantics=ctx.direction_semantics,
                    )
                    for original_sentence in tx.split_sentences(prop["quote"]):
                        if tx.contains(exact, original_sentence):
                            restriction = cl.evaluate_sentence(
                                original_sentence,
                                pid,
                                source_ctx,
                                [path["placement"]["requirement_id"]],
                                trait_role=any(
                                    "trait" in role for role in specs[path["placement"]["requirement_id"]]["role_specs"]
                                ),
                            )
                            removed = None
                            if corrected:
                                restriction = dc.qualified_result_not_aim(restriction, prop["quote"])
                                if dc.CLOSURE in restriction["reasons"] and dc.CLOSURE not in attempt["reasons"]:
                                    removed = dc.removed_text_is_immaterial(original_sentence, sentence)
                            if removed is not None:
                                # The displayed clause stands on its own; the anaphor it left behind is not shown.
                                restriction["checks"] = [
                                    {
                                        "check": "referentially_closed_after_narrowing",
                                        "passed": True,
                                        "detail": {"original_sentence_failures": c["detail"], "removed_text": removed},
                                    }
                                    if c["check"] == dc.CLOSURE
                                    else c
                                    for c in restriction["checks"]
                                ]
                                restriction = dc.recompute(restriction)
                            attempt["checks"].extend(restriction["checks"])
                            attempt["reasons"] = sorted(set(attempt["reasons"] + restriction["reasons"]))
                            attempt["ok"] = attempt["ok"] and restriction["ok"]
                item = {**plain(source), **attempt}
                attempts.append(item)
                if attempt["ok"]:
                    accepted.append(item)
                elif corrected and attempt["reasons"] == [dc.CLOSURE]:
                    closure_only.append((ref, item, target, ctx, path["placement"]["requirement_id"]))
        finalized[ref] = {
            "schema": "finalized-value-display-v1",
            "coverage_ref": ref,
            "value_ref": path["value_id"],
            "semantic_value": plain(value),
            "coverage": plain(path),
            "display_state": "supported"
            if accepted
            else "restricted"
            if attempts or path["authorized_display_source_refs"]
            else "unavailable",
            "attempts": attempts,
            "accepted": accepted,
            "scientific_goal_state": path["scientific_goal_state"],
            "reported_finding": path["reported_finding"],
        }
    # Clauses Layer C itself narrowed to and that passed every check, by the proposition they were cut from.
    clauses = {}
    for entry in finalized.values():
        for item in entry["accepted"]:
            if any(c["check"] == "referentially_closed_after_narrowing" for c in item["checks"]):
                clauses.setdefault(item["proposition_id"], set()).add(item["raw_sentence"])
    for ref, item, target, ctx, requirement_id in closure_only:
        for clause in sorted(clauses.get(item["proposition_id"], ())):
            removed = dc.removed_text_is_immaterial(item["raw_sentence"], clause)
            if removed is None or not tx.contains(target, clause):
                continue
            retry = cl.evaluate_sentence(
                clause,
                item["proposition_id"],
                ctx,
                [requirement_id],
                trait_role=any("trait" in role for role in specs[requirement_id]["role_specs"]),
            )
            retry = dc.qualified_result_not_aim(retry, ctx.props[item["proposition_id"]]["quote"])
            retry["checks"].append(
                {
                    "check": "referentially_closed_after_narrowing",
                    "passed": True,
                    "detail": {"original_sentence_failures": item["reasons"], "removed_text": removed},
                }
            )
            shown = {**{k: v for k, v in item.items() if k not in retry}, **retry}
            finalized[ref]["attempts"].append(shown)
            if retry["ok"]:
                finalized[ref]["accepted"].append(shown)
                finalized[ref]["display_state"] = "supported"
    return finalized
