"""Restrict authorized value-local display inputs using existing presentation checks."""

from experiments.ask_cli_revised._layerc_common import plain, require, text_hash
from experiments.ask_cli_revised.answer_plan import classify as cl
from experiments.ask_cli_revised.answer_plan import text as tx


def finalize_display(projection, sealed, authored):
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
                            attempt["checks"].extend(restriction["checks"])
                            attempt["reasons"] = sorted(set(attempt["reasons"] + restriction["reasons"]))
                            attempt["ok"] = attempt["ok"] and restriction["ok"]
                item = {**plain(source), **attempt}
                attempts.append(item)
                if attempt["ok"]:
                    accepted.append(item)
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
    return finalized
