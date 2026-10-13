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

Three further changes on the fresh route (2026-10-13, cross-stage audit), applied in ``_settle``:

3. The sealed claim is the statement. The worker already wrote a self-contained claim from the passage and its
   context, and the verifier approved it. When that claim passes the existing rephrasing screen against the one
   sentence authorized here, and names the authorized literal value, it is carried as ``statement``. The sentence
   stays as the evidence and remains what every authorization and relation check reads. Checks that exist only
   because a raw sentence was being printed (referential closure, truncation) are then not applied to the claim; a
   truncated source is said to be truncated. A claim that fails is not used and the sentence is judged as before.
4. Where the scientific record classified the assertion, that record decides attribution and the lexical display
   check does not. Prior evidence is shown with the existing qualifier; an aim or hypothesis is still not shown as a
   finding. Where no record exists, the lexical check remains the only attribution judgment and still applies.
5. ``ground_acronyms`` calls the existing Step 2 expansion for the statements of the rendered answer.
"""

from experiments.ask_cli_revised._layerc_common import plain, require, text_hash
from experiments.ask_cli_revised.answer_plan import classify as cl
from experiments.ask_cli_revised.answer_plan import disclosure_v5 as dv5
from experiments.ask_cli_revised.answer_plan import display_corrections as dc
from experiments.ask_cli_revised.answer_plan import step2
from experiments.ask_cli_revised.answer_plan import text as tx

TRUNCATED_PREFIX = "From a source passage cut off in extraction: "
INTERPRETATION_PREFIX = "The source offers this as an interpretation: "
_NOT_A_FINDING = ("aim_or_hypothesis", "unknown")


def _authority_payload(r, path, pid):
    """The scientific record's classification of the assertion behind this value: its own candidate record, else a
    record for the same requirement that rests on the same proposition. None when the mapping assessed neither."""
    view = r["support_views"][path["establishment_refs"][0]["ref"]]
    own = r["candidate_metadata_by_support"].get(view["support_ref"])
    if own is not None:
        return r["candidate_metadata"][own]["payload"]
    place = path["placement"]
    rows = [
        m["payload"]
        for _, m in sorted(r["candidate_metadata"].items())
        if not m["diagnostic_only"]
        and (m["placement"]["child_id"], m["placement"]["requirement_id"])
        == (place["child_id"], place["requirement_id"])
        and pid in m["payload"]["supporting_proposition_ids"]
    ]
    # Several records for one proposition: the most cautious reading governs.
    rows.sort(
        key=lambda x: (
            x["assertion_kind"] not in _NOT_A_FINDING,
            x["assertion_relation"] == "current_document",
        )
    )
    return rows[0] if rows else None


def _settle(attempt, r, path, value, prop, target):
    """Apply the authority record and the verified claim to one evaluated source sentence."""
    payload = _authority_payload(r, path, prop["proposition_id"])
    prefix = ""
    if payload is not None:
        kind, relation = payload["assertion_kind"], payload["assertion_relation"]
        record = {
            "check": "attribution_authority_record",
            "passed": kind not in _NOT_A_FINDING,
            "detail": {"assertion_kind": kind, "assertion_relation": relation, "aggregation": payload["aggregation"]},
        }
        attempt["checks"] = [record if c["check"].startswith("attribution_") else c for c in attempt["checks"]]
        attempt["attribution"] = f"{relation}:{kind}"
        prefix = dv5.prefix_for(relation, payload["aggregation"])
        if not prefix and kind == "interpretation":
            prefix = INTERPRETATION_PREFIX
    claim = prop.get("proposition_text")
    names_value = value["kind"] == "evidence_slot" or (
        isinstance(claim, str) and tx.contains(target.lower(), claim.lower())
    )
    reasons = (
        dc.claim_statement_reasons(claim, attempt["raw_sentence"]) if names_value else ["authorized_value_not_named"]
    )
    if reasons:
        attempt["claim_not_used"] = reasons
    else:
        attempt["statement"] = claim
        truncated = any(
            c["check"] == "passage_complete" and not c["passed"] for c in attempt["checks"]
        ) and not dc.ends_at_citation_marker(prop["quote"])
        attempt["checks"] = [
            {"check": c["check"] + "_not_applied_to_verified_claim", "passed": True, "detail": c["detail"]}
            if c["check"] in dc.RAW_SENTENCE_FORM and not c["passed"]
            else c
            for c in attempt["checks"]
        ]
        if truncated:
            prefix = TRUNCATED_PREFIX + prefix
    if prefix:
        attempt["qualification"] = {"prefix": prefix}
    return dc.recompute(attempt)


class _Spans:
    def __init__(self, rows):
        self.span_rows, self.props = rows, {}


def ground_acronyms(nodes, sealed):
    """First use of an acronym in the answer gains its long form, by the existing Step 2 rule: only when exactly one
    explicit definition exists in the same paper's sealed text. The edit and its defining span are recorded."""
    papers = {p["proposition_id"]: p["paper_id"] for p in sealed["verified_propositions"]}
    ctx, introduced, grounded = _Spans(sealed["evidence_spans"]), {}, set()
    for node in nodes:
        for statement in node["statements"]:
            view = {
                "text": statement["text"],
                "paper_id": sorted(papers[m["proposition_id"]] for m in statement["members"])[0],
            }
            step2._ground_node({"statements": [view]}, ctx, introduced, grounded)
            if view["text"] != statement["text"]:
                statement["text"], statement["edits"] = view["text"], view["edits"]


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
    closure_only = []  # attempts that may also be shown with a clause narrowed for a sibling value
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
                if corrected:
                    attempt = _settle(attempt, r, path, value, prop, target)
                item = {**plain(source), **attempt}
                attempts.append(item)
                if attempt["ok"]:
                    accepted.append(item)
                if corrected and (attempt["ok"] or attempt["reasons"] == [dc.CLOSURE]):
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
    # Accepted evidence sentences, by the proposition they were cut from. A relation is shown only when both of its
    # values accept the same sentence, so a value may also take a clause Layer C narrowed to for a sibling value.
    clauses = {}
    for entry in finalized.values():
        for item in entry["accepted"]:
            clauses.setdefault(item["proposition_id"], set()).add(item["raw_sentence"])
    for ref, item, target, ctx, requirement_id in closure_only:
        for clause in sorted(clauses.get(item["proposition_id"], ())):
            if clause == item["raw_sentence"] or any(
                a["proposition_id"] == item["proposition_id"] and a["raw_sentence"] == clause
                for a in finalized[ref]["attempts"]
            ):
                continue
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
            path = r["value_coverage"][ref]
            retry = _settle(
                retry, r, path, r["semantic_values"][path["value_id"]], props[item["proposition_id"]], target
            )
            carried = ("statement", "qualification", "claim_not_used")
            shown = {**{k: v for k, v in item.items() if k not in retry and k not in carried}, **retry}
            finalized[ref]["attempts"].append(shown)
            if retry["ok"]:
                finalized[ref]["accepted"].append(shown)
                finalized[ref]["display_state"] = "supported"
    return finalized
