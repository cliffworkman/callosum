"""Two views of ONE frozen run, and the crosswalk that ties them together. Pure functions of a finished ``run_engine`` result: no model
call, no reading of any held-out reference, no rewriting.

* ``natural_language_view``: the EXACT request the writer produced for every child, in its actual hierarchy (nesting and folded
  children as the tree recorded them). Nothing is cleaned up, repaired or replaced. A child that was not written is shown as its
  retained source words and marked ``UNWRITTEN``; a source gap, a child with a detected independence problem, and a review state are
  marked in words, beside (never instead of) the text.
* ``contract_view``: for each child its owned obligations, source spans, the source extract the writer was given, inherited context,
  dependencies and nesting basis, the approved clarifications and requirement records that apply (with their provenance), the
  relationship requirement, unresolved meanings and the acceptance status.
* ``crosswalk``: every child id traced to its natural-language entry, its contract entry, its tree node and its obligations.

The views report; they do not score. There is deliberately no overall success number: the natural-language requests are for the
researcher and Lucien to judge, and the contract is for independent review. A marker such as "no independence problem detected"
means only that no check found one; it never certifies that the request runs on its own or preserves the meaning.
"""

from __future__ import annotations

from collections import Counter

from experiments.ask_cli_revised.decompose import children as ch
from experiments.ask_cli_revised.decompose import ledger

UNWRITTEN = {
    "unit_level": "no anchor obligation was found in this unit, so nothing was written",
    "unresolved_elliptical": "an elliptical fragment whose target no approved clarification states, so it was not written",
    "not_selected": "left out of a subset run",
    "fallback": "the writer produced no usable question (or the call cap was reached); the exact source words are kept",
    "constraint_failure": "the request cannot fit the output limits; it was not sent and not shortened",
}
INDEPENDENCE_FLAGS = (
    "not_self_contained",
    "context_missing",
    "context_link_unstated",
    "clarified_reference_unresolved",
    "silent_resolution_of_referent",
)
REVIEW_STATUSES = (
    "semantic_conflict",
    "conditional_on_unresolved_reading",
    "semantic_review_required",
    "output_constraint_failure",
    "pending_researcher_confirmation",
)
NOT_A_CERTIFICATE = "a marker reports what the checks found; 'no independence problem detected' is not a certificate that the request runs on its own"


def runnability(child: dict) -> dict:
    """How this child should be read: written or not, and whether a check found it cannot run on its own. Never a certificate."""
    kind = child["kind"]
    if kind == "passthrough":
        return {
            "markers": ["PASSED THROUGH UNCHANGED"],
            "state": "original_request_unchanged",
            "reasons": [
                "the original request, kept exactly; it still goes through the normal Ask path once and is NOT answered"
            ],
        }
    if kind in UNWRITTEN:
        return {"markers": ["UNWRITTEN"], "state": "not_a_generated_request", "reasons": [UNWRITTEN[kind]]}
    reasons = [
        f"{f['flag']}: {f.get('note') or ', '.join(f.get('words') or f.get('tokens') or [])}"
        for f in child["flags"]
        if f.get("flag") in INDEPENDENCE_FLAGS
    ]
    reasons += [f"{u['kind']}: {u['note']}" for u in child.get("unresolved_links") or []]
    markers = []
    if child["status"] == "source_gap":
        markers.append("SOURCE GAP")
    if reasons:
        markers.append("NOT INDEPENDENTLY RUNNABLE (detected)")
    if child["status"] in REVIEW_STATUSES:
        markers.append(f"REVIEW: {child['status']}")
    if child.get("human_review_required"):
        markers.append("HUMAN REVIEW KEPT (researcher decision)")
    state = (child.get("execution") or {}).get("state")
    if state == "requires_researcher_approval":
        markers.append("REQUIRES RESEARCHER APPROVAL BEFORE ASK RUNS IT")
    elif state == "not_executable":
        markers.append("NOT EXECUTABLE AS WRITTEN")
    elif state == "researcher_approved":
        markers.append("RESEARCHER APPROVED (this exact wording)")
    return {
        "markers": markers,
        "state": "not_independently_runnable_detected" if reasons else "no_independence_problem_detected",
        "reasons": reasons,
    }


def _call_block(result: dict) -> dict:
    by_task = Counter(r["task"] for r in result["calls"])
    return {
        "total_calls": len(result["calls"]),
        "by_task": dict(by_task),
        "writer_calls": by_task.get("children.write", 0) + by_task.get("children.repair", 0),
        "elapsed_seconds_total": round(sum(r["elapsed_seconds"] for r in result["calls"]), 2),
    }


def _decision_block(result: dict) -> dict | None:
    d = result.get("decomposition_decision")
    if not d:
        return None
    return {
        k: d.get(k)
        for k in (
            "outcome",
            "applied",
            "basis",
            "blocking",
            "checks",
            "model_calls_avoided",
            "not_applied_because",
            "downstream",
        )
    }


def natural_language_view(result: dict) -> dict:
    p1, parent = result["pass1"], result["parent_contract"]
    by_child = {c["child_id"]: c for c in p1["children"]}
    nodes = {n["node_id"]: n for n in (p1.get("question_tree") or {}).get("nodes", [])}
    kids: dict[str, list[str]] = {}
    for n in nodes.values():
        kids.setdefault(n["parent"], []).append(n["node_id"])
    flat: list[dict] = []

    def entry(cid: str, depth: int) -> dict:
        c, n = by_child[cid], nodes.get(cid, {})
        run = runnability(c)
        written = c["kind"] in ("generated", "passthrough")
        row = {
            "child_id": cid,
            "depth": depth,
            "parent": n.get("parent"),
            "nesting_basis": n.get("nesting_basis"),
            "kind": c["kind"],
            "acceptance_status": c["status"],
            "request": c["question"] if written else None,
            "retained_source_words_not_a_request": None if written else c["question"],
            "markers": run["markers"],
            "independence": {"state": run["state"], "reasons": run["reasons"]},
            "folded_children": [
                {
                    "child_id": f["child_id"],
                    "slot": f["slot"],
                    "note": "its words are part of this request; it has no request of its own",
                }
                for f in (n.get("folded_from") or [])
            ],
            "subordinates": kids.get(cid, []),
            **({"execution": c["execution"]} if c.get("execution") else {}),
        }
        flat.append(row)
        for sub in kids.get(cid, []):
            entry(sub, depth + 1)
        return row

    for top in kids.get("R", []):
        entry(top, 1)
    return {
        "view": "natural_language",
        "engine_version": result["engine_version"],
        "prompt_variant": result["manifest"]["prompt_variant"],
        "original_request": result["question"],
        "decision": _decision_block(result),
        "calls": _call_block(result),
        "run_completeness": result["manifest"].get("run_completeness"),
        "answer_state": "not_executed",
        "exactness": "each `request` is the writer's output exactly as returned (surrounding whitespace only stripped by the engine); nothing was cleaned up, repaired or replaced",
        "not_a_certificate": NOT_A_CERTIFICATE,
        "root_units": [
            {"id": u["source_unit_id"], "text": u["text"], "span": [u["start"], u["end"]]}
            for u in parent["source_units"]
        ],
        "nodes": flat,
    }


def _clarification_rows(parent: dict, child: dict, plan: dict, by_id: dict) -> list[dict]:
    used = set((child.get("edit_ledger") or {}).get("clarifications_used", []))
    results = {r["id"]: r for r in (child.get("edit_ledger") or {}).get("requirements", [])}
    out = []
    for c in ledger._applicable(parent, plan, by_id):
        out.append(
            {
                "id": c["id"],
                "kind": c["kind"],
                "phrase": c["phrase"],
                "span": c["span"],
                "target_span": c["target_span"],
                "means_approved": c["means"],
                "authorized_by": c["authorized_by"],
                "authorization": c.get("authorization"),
                "refers_to": c.get("refers_to"),
                "pairs": [m["text"] for m in c.get("pairs") or []],
                "adds": c.get("adds") or [],
                "context_link": c.get("context_link"),
                "human_review": c.get("human_review"),
                "used_in_this_child_wording": c["id"] in used,
                "requirement_records": [
                    {**r, "result_for_this_child": (results.get(r["id"]) or {}).get("state")}
                    for r in c.get("requirements", [])
                ],
            }
        )
    return out


def _unresolved(child: dict, ctx: dict) -> dict:
    return {
        "reported_by_the_writer": child.get("declared_unresolved") or [],
        "unstated_links_found_by_the_ledger": child.get("unresolved_links") or [],
        "references_left_without_an_approved_clarification": [
            {
                "word": u["word"],
                "span": u["span"],
                "candidates": [
                    c["text"] if isinstance(c, dict) and "text" in c else c for c in u.get("candidates", [])
                ],
            }
            for u in ctx["unresolved"]
        ],
        "reference_readings_used": [
            i for i in child.get("interpretations") or [] if i["kind"].startswith("reference_resolved")
        ],
        "open_ambiguities": [i for i in child.get("interpretations") or [] if i["kind"] == "depends_on_open_ambiguity"],
    }


def preparation_view(prep: dict) -> dict:
    """What code prepared before the writer saw the child, recorded APART from what the model returned. Each edit names its source."""
    return {
        "note": "deterministic preparation (no model); the wording the model returned is recorded separately and is never edited by it",
        "applied": prep["active"],
        "extract_before": prep["original_extract_text"],
        "extract_after": " ".join(e["text"] for e in prep["extract_entries"]),
        "lead_in": prep["prefix"],
        "edits": prep["edits"],
        "carried_context": prep["carry"],
        "approved_joining_words": prep["join"],
        "not_applied_with_reason": prep["not_applied"],
        "not_prepared_with_reason": prep["not_prepared"],
        "grammar_notes": prep["grammar_notes"],
        "meaning_requirements_for_human_review": prep["scope_review"],
        "scaffold": prep.get("scaffold"),
        "the_finished_wording_is_held_to": prep["requirements"],
    }


def contract_view(result: dict) -> dict:
    p1, parent = result["pass1"], result["parent_contract"]
    by_id = ch.by_id_map(parent)
    plans = {p["child_id"]: p for p in p1["plans"]}
    all_plans = p1["plans"]
    nodes = {n["node_id"]: n for n in (p1.get("question_tree") or {}).get("nodes", [])}
    contracts = []
    for c in p1["children"]:
        plan, n = plans[c["child_id"]], nodes.get(c["child_id"], {})
        ctx = ch.child_context(parent, plan, by_id, plans=all_plans, governing_operation=True)
        led = c.get("edit_ledger") or {}
        contracts.append(
            {
                "child_id": c["child_id"],
                "kind": c["kind"],
                "acceptance_status": c["status"],
                "acceptance": {
                    "status": c["status"],
                    "flags": [
                        {
                            k: v
                            for k, v in f.items()
                            if k
                            in (
                                "flag",
                                "kind",
                                "class",
                                "words",
                                "note",
                                "informational",
                                "source_gap",
                                "pending_confirmation",
                                "source_edit",
                            )
                        }
                        for f in c["flags"]
                    ],
                    "output_acceptance": c.get("output_acceptance"),
                    "output_budget": c.get("output_budget"),
                    "preflight": c.get("preflight"),
                    "ledger_status": led.get("status"),
                    "semantic_fidelity": "not_certified",
                },
                "owned_obligations": [
                    {
                        "id": i,
                        "kind": by_id[i]["kind"],
                        "text": by_id[i]["text"],
                        "spans": by_id[i]["spans"],
                        "origin": by_id[i]["origin"],
                        "produced_by": by_id[i]["produced_by"],
                        "anchoring": by_id[i]["anchoring"],
                        "part_of": by_id[i].get("part_of"),
                    }
                    for i in c["owns"]
                ],
                "shared_frames": [
                    {"id": i, "kind": by_id[i]["kind"], "text": by_id[i]["text"], "spans": by_id[i]["spans"]}
                    for i in c["carries_shared"]
                ],
                "folded_children": c.get("folded") or [],
                "source": {
                    "unit_ids": c["origin"]["source_unit_ids"],
                    "spans": c["origin"]["source_spans"],
                    "extract_given_to_the_writer": [{"text": e["text"], "span": e["span"]} for e in ctx["extract"]],
                    "governing_operation": parent["original_question"][ctx["governing"][0] : ctx["governing"][1]]
                    if ctx["governing"]
                    else None,
                },
                "background_referent": [
                    {
                        "id": r["id"],
                        "text": r["text"],
                        "spans": r["spans"],
                        "note": "background only; never owned or asked",
                    }
                    for r in ctx["subject"]
                ],
                "approved_context_link": ctx["link"],
                "nesting": {
                    "parent": n.get("parent"),
                    "depth": n.get("depth"),
                    "basis": n.get("nesting_basis"),
                    "subordinates": n.get("subordinates") or [],
                    "joint_answer_groups": n.get("joint_answer_groups") or [],
                },
                "inherited_context": n.get("inherited") or [],
                "inherited_source_words_of_the_question_continued": [
                    {
                        "from_node": o["from_node"],
                        "text": " ".join(e["text"] for e in o["entries"]),
                        "note": "context only; never asked again",
                    }
                    for o in ctx["inherited_extracts"]
                ],
                "dependencies": {
                    "approved": n.get("depends_on") or [],
                    "candidate_not_approved": n.get("candidate_dependencies") or [],
                },
                "clarifications_that_apply": _clarification_rows(parent, c, plan, by_id),
                "relationship_requirement": c.get("relation_contract"),
                "relationship_conformance": (c.get("diagnostics") or {}).get("relation"),
                "pairs_that_must_stay_together": ctx["joint"],
                "requirement_results": led.get("requirements", []),
                "unresolved_meanings": _unresolved(c, ctx),
                "edit_ledger": {
                    "status": led.get("status"),
                    "summary": led.get("summary"),
                    "clarifications_used": led.get("clarifications_used"),
                    "flags": led.get("flags"),
                    "ops": led.get("ops"),
                    "verification_limits": led.get("verification_limits"),
                    "human_review_required": led.get("human_review_required", False),
                },
                "independence": runnability(c),
                **({"execution": c["execution"]} if c.get("execution") else {}),
                **({"model_raw": c["model_raw"]} if c.get("model_raw") else {}),
                **({"preparation": preparation_view(c["preparation"])} if c.get("preparation") else {}),
            }
        )
    rec = p1["reconciliation"]
    return {
        "view": "contract",
        "engine_version": result["engine_version"],
        "prompt_variant": result["manifest"]["prompt_variant"],
        "parent_contract": {
            "original_request": parent["original_question"],
            "source_units": parent["source_units"],
            "obligations": [
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "text": r["text"],
                    "spans": r["spans"],
                    "origin": r["origin"],
                    "produced_by": r["produced_by"],
                    "anchoring": r["anchoring"],
                    "superseded": r.get("superseded"),
                }
                for r in parent["requirements"]
                if r["origin"] != "source_unit_floor"
            ],
            "ambiguities": [
                {
                    "id": a["id"],
                    "text": a["text"],
                    "spans": a["spans"],
                    "alternatives": a.get("alternatives"),
                    "status": a.get("status"),
                    "clarification": a.get("clarification"),
                }
                for a in parent["ambiguities"]
            ],
            "referents": [
                {"id": r["id"], "text": r["text"], "spans": r["spans"], "status": r["status"]}
                for r in parent.get("referents", [])
            ],
            "clarifications": [
                {
                    "id": c["id"],
                    "kind": c["kind"],
                    "phrase": c["phrase"],
                    "means": c["means"],
                    "authorized_by": c["authorized_by"],
                }
                for c in parent.get("clarifications", [])
            ],
            "researcher_decisions": result["manifest"].get("researcher_decisions"),
            "pending_researcher_decisions": result["manifest"].get("pending_researcher_decisions"),
        },
        "decision": _decision_block(result),
        "question_tree": p1.get("question_tree"),
        "joint_answer_groups": (p1.get("question_tree") or {}).get("joint_answer_groups"),
        "reconciliation_summary": rec["summary"],
        "known_limitations": result["manifest"].get("known_limitations"),
        "children": contracts,
    }


def crosswalk(result: dict) -> dict:
    p1 = result["pass1"]
    nodes = {n["node_id"]: n for n in (p1.get("question_tree") or {}).get("nodes", [])}
    rec = p1["reconciliation"]
    rows = []
    for c in p1["children"]:
        n = nodes.get(c["child_id"], {})
        rows.append(
            {
                "child_id": c["child_id"],
                "natural_language_entry": f"NATURAL_LANGUAGE_VIEW: node {c['child_id']}",
                "contract_entry": f"CONTRACT_VIEW: children[child_id={c['child_id']}]",
                "tree_parent": n.get("parent"),
                "depth": n.get("depth"),
                "kind": c["kind"],
                "acceptance_status": c["status"],
                "source_unit_ids": c["origin"]["source_unit_ids"],
                "owned_obligation_ids": c["owns"],
                "shared_frame_ids": c["carries_shared"],
                "folded_child_ids": [f["child_id"] for f in c.get("folded") or []],
                "clarifications_used": (c.get("edit_ledger") or {}).get("clarifications_used", []),
            }
        )
    return {
        "view": "crosswalk",
        "root": {"node_id": "R", "meaning": "the original request"},
        "children": rows,
        "obligation_to_child": [
            {
                "obligation_id": r["id"],
                "kind": r["kind"],
                "text": r["text"],
                "owners": [o["child_id"] for o in r.get("owners", [])],
                "carried_shared_by": r.get("carried_shared_by", []),
                "reconciliation_status": r["status"],
            }
            for r in rec["rows"]
            if r["kind"] not in ("source_unit", "ambiguity", "subject") and "owners" in r
        ],
    }


# ---- Markdown renderings (presentation only; the JSON is the record) ---------------------------------------------------------------------
def _quote(text: str, pad: str) -> list[str]:
    if "\n" in text or "`" in text:
        return [f"{pad}````text", *[f"{pad}{line}" for line in text.split("\n")], f"{pad}````"]
    return [f"{pad}> {text}"]


def render_natural_language(view: dict) -> str:
    d, calls = view["decision"], view["calls"]
    lines = [
        "# Natural-language decomposition (the writer's exact output, unedited)",
        "",
        f"Engine `{view['engine_version']}` | writer variant `{view['prompt_variant']}` | answer state `{view['answer_state']}` (nothing here is an answer)",
        "",
        "**Original request**",
        "",
        *_quote(view["original_request"], ""),
        "",
        f"**Decomposition decision:** `{d['outcome'] if d else 'not evaluated'}`"
        + (
            " (applied: the original request is kept unchanged; the writer was not called)"
            if d and d.get("applied")
            else ""
        )
        + (f" | {d['basis']}" if d else ""),
        f"**Model calls:** {calls['total_calls']} total {calls['by_task']} | writer calls {calls['writer_calls']} | model time {calls['elapsed_seconds_total']}s",
        f"**Run completeness:** {'COMPLETE' if view['run_completeness']['complete'] else 'INCOMPLETE'} {view['run_completeness']['reasons'] or ''}".rstrip(),
        "",
        "Markers: `UNWRITTEN` (no generated request; the retained source words are shown), `SOURCE GAP`, `NOT INDEPENDENTLY RUNNABLE (detected)`, "
        "`REVIEW: <status>`, `PASSED THROUGH UNCHANGED`. " + view["not_a_certificate"] + ".",
        "",
        "## Hierarchy",
        "",
    ]
    for n in view["nodes"]:
        pad = "  " * (n["depth"] - 1)
        basis = n["nesting_basis"] or {}
        where = (
            "top level"
            if n["depth"] == 1
            else f"nested under {n['parent']} ({basis.get('kind')}"
            + (f" via {basis['clarification']}" if basis.get("clarification") else "")
            + ")"
        )
        lines.append(f"{pad}- **{n['child_id']}** [{n['acceptance_status']}] {where}")
        if n["request"] is not None:
            lines += _quote(n["request"], pad + "  ")
        else:
            lines.append(
                f"{pad}  **UNWRITTEN: no generated request.** Retained source words: {n['retained_source_words_not_a_request']!r}"
            )
        if n["markers"]:
            lines.append(f"{pad}  markers: {'; '.join(n['markers'])}")
        for r in n["independence"]["reasons"]:
            lines.append(f"{pad}  - {r}")
        ex = n.get("execution")
        if ex:
            lines.append(f"{pad}  execution: `{ex['state']}` | " + "; ".join(ex["reasons"]))
            fb = ex.get("fallback_proposal")
            if fb:
                lines.append(f"{pad}  SEPARATE PROPOSAL ({fb['origin']}; NOT the model's wording; requires approval):")
                lines += _quote(fb["text"], pad + "    ")
        for f in n["folded_children"]:
            lines.append(f"{pad}  - folded: {f['child_id']} ({f['slot']}): {f['note']}")
    return "\n".join(lines) + "\n"


def render_contract(view: dict) -> str:
    pc = view["parent_contract"]
    lines = [
        "# Structured contract (one entry per child; JSON is the record)",
        "",
        f"Engine `{view['engine_version']}` | writer variant `{view['prompt_variant']}`",
        "",
        f"Original request: {pc['original_request']!r}",
        "",
        "## Researcher decisions recorded for this run",
        "",
        *[
            f"- {d['id']}: {d['decision']} (authorized by {d['authorized_by']})"
            for d in pc.get("researcher_decisions") or []
        ],
        f"- still pending with the researcher: {pc.get('pending_researcher_decisions') or 'none'}",
        "",
    ]
    for c in view["children"]:
        src, nest = c["source"], c["nesting"]
        lines += [
            f"## {c['child_id']} [{c['kind']}] status `{c['acceptance_status']}`",
            "",
            f"- nesting: parent `{nest['parent']}`, depth {nest['depth']}, basis {nest['basis']}",
            "- owned obligations: "
            + "; ".join(f"{o['id']}[{o['kind']}] {o['text']!r} {o['spans']}" for o in c["owned_obligations"]),
            f"- source spans: {src['spans']} (units {src['unit_ids']}); extract given to the writer: {[e['text'] for e in src['extract_given_to_the_writer']]}",
        ]
        if c["background_referent"]:
            lines.append(
                f"- background referent (never asked): {[r['text'] for r in c['background_referent']]}; approved link: {c['approved_context_link']}"
            )
        if c["inherited_context"]:
            lines.append(
                "- inherited context: "
                + "; ".join(
                    f"{i['role']} {i['text']!r} from {i['from_node']}"
                    + (f" via {i['clarification']}" if i.get("clarification") else "")
                    for i in c["inherited_context"]
                )
            )
        if c["dependencies"]["approved"] or c["dependencies"]["candidate_not_approved"]:
            lines.append(
                f"- dependencies: approved {c['dependencies']['approved']}; candidate (not approved) {c['dependencies']['candidate_not_approved']}"
            )
        for cl in c["clarifications_that_apply"]:
            lines.append(
                f"- clarification {cl['id']} ({cl['kind']}, authorized by {cl['authorized_by']}): used in wording: {cl['used_in_this_child_wording']}"
                + (
                    f"; joining words {cl['context_link']['text']!r} ({cl['context_link']['authority']})"
                    if cl.get("context_link")
                    else ""
                )
            )
        rel = c["relationship_requirement"]
        if rel:
            lines.append(
                "- relationship requirement: "
                + (
                    f"subject {rel['subject']['text']!r}, relation {rel['relation']['text']!r}, target {rel['target']['text']!r}, whether {rel['polarity']['requested']}, how {rel['manner']['requested']}, answer form {rel['answer_form']['form']}"
                    if rel["parse_status"] == "parsed"
                    else f"NOT PARSED ({rel.get('reason')})"
                )
            )
        if c["pairs_that_must_stay_together"]:
            lines.append(f"- pairs that must stay together: {c['pairs_that_must_stay_together']}")
        prep = c.get("preparation")
        if prep:
            lines.append(
                f"- preparation (by code, before the writer): {prep['extract_before']!r} -> {prep['extract_after']!r}; lead-in {prep['lead_in']!r}"
            )
            for e in prep["edits"]:
                src = "; ".join(f"{x['text']!r} {x['span']}" for x in e["from_source"]) or "no source words"
                sup = "; ".join(f"{x['text']!r} by {x['by']}" for x in e["supplied"]) or "nothing supplied"
                lines.append(
                    f"  - edit {e['op']} ({e['rule']}, {e.get('clarification') or 'no clarification'}): source {src}; supplied {sup}"
                )
            sc = prep.get("scaffold")
            if sc and sc.get("built"):
                lines.append(f"  - scaffold ({sc['template']}): {sc['text']!r}")
                for p in sc["pieces"]:
                    lines.append(
                        f"    - {p['text']!r} [{p['origin']}]"
                        + (f" source {p['span']}" if p.get("span") else "")
                        + (f" {p['clarification']}" if p.get("clarification") else "")
                        + (f" rule {p['rule']}" if p.get("rule") else "")
                    )
                lines += [
                    f"    - not in the request: {d['text']!r} {d['span']}: {d['why']}"
                    for d in sc["dropped_source_words"]
                ]
                lines += [f"    - PENDING researcher confirmation ({x['kind']}): {x['reason']}" for x in sc["pending"]]
            elif sc:
                lines += [f"  - scaffold NOT built: {x['reason']}" for x in sc["not_built"]]
            if prep["carried_context"]:
                cc = prep["carried_context"]
                lines.append(
                    f"  - carried context from {cc['from_node']} via {cc['clarification']}: {cc['text']!r} (relationship covering these words parsed: {cc['relationship_parsed']}); {cc['why']}"
                )
            if prep["approved_joining_words"]:
                lines.append(
                    f"  - approved joining words: {prep['approved_joining_words']['text']!r} ({prep['approved_joining_words']['clarification']})"
                )
            for x in prep["not_applied_with_reason"] + prep["not_prepared_with_reason"]:
                lines.append(f"  - NOT prepared: {x['reason']}")
            for g in prep["grammar_notes"]:
                lines.append(f"  - grammar note: {g['note']}")
            for r in prep["meaning_requirements_for_human_review"]:
                lines.append(
                    f"  - meaning requirement for human review ({r['clarification']}, {r['decision']}): {r['text']!r}"
                )
            lines.append(
                "  - the finished wording is held to: "
                + "; ".join(f"{r['text']} [{r['check']}]" for r in prep["the_finished_wording_is_held_to"])
            )
        um = c["unresolved_meanings"]
        lines.append(
            f"- unresolved meanings: writer reported {len(um['reported_by_the_writer'])}; ledger unstated links {len(um['unstated_links_found_by_the_ledger'])}; unapproved references {[u['word'] for u in um['references_left_without_an_approved_clarification']]}"
        )
        flags = [f"{f.get('flag') or f.get('kind')}" for f in c["acceptance"]["flags"] if not f.get("informational")]
        lines += [
            f"- detected: {flags or 'nothing'}",
            f"- requirement results: {[(r['id'], r['state']) for r in c['requirement_results'] if r['state'] != 'not_applicable']}",
            f"- independence: {c['independence']['state']} {c['independence']['markers']}",
        ]
        if c.get("execution"):
            ex = c["execution"]
            lines.append(
                f"- execution readiness: `{ex['state']}` (wording sha256 {ex['wording_sha256'][:16]}...): "
                + "; ".join(ex["reasons"])
            )
            if ex.get("fallback_proposal"):
                lines.append(
                    f"  - separate deterministic proposal (not the model's wording; requires approval): {ex['fallback_proposal']['text']!r}"
                )
        if c.get("model_raw"):
            lines.append(f"- the model's exact response: {c['model_raw']['response_text']!r}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_crosswalk(cw: dict) -> str:
    lines = [
        "# Child-ID crosswalk",
        "",
        "| child | tree parent | kind | acceptance status | source units | owned obligations | folded children | clarifications used |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in cw["children"]:
        lines.append(
            f"| {r['child_id']} | {r['tree_parent']} | {r['kind']} | {r['acceptance_status']} | {', '.join(r['source_unit_ids'])} | {', '.join(r['owned_obligation_ids'])} | {', '.join(r['folded_child_ids']) or '-'} | {', '.join(r['clarifications_used']) or '-'} |"
        )
    lines += [
        "",
        "Root `R` is the original request. Every child id above is the same id in the natural-language view and in the contract view.",
        "",
        "## Obligation to child",
        "",
        "| obligation | kind | owners | status |",
        "|---|---|---|---|",
    ]
    for r in cw["obligation_to_child"]:
        lines.append(
            f"| {r['obligation_id']} {r['text'][:60]!r} | {r['kind']} | {', '.join(r['owners']) or '-'} | {r['reconciliation_status']} |"
        )
    return "\n".join(lines) + "\n"
