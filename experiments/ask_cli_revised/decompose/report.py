"""Human-readable REPORT.md for one engine run. Presentation only; every claim comes from the documents."""

from __future__ import annotations


def _cell(text: str, n: int = 200) -> str:
    text = " ".join(str(text).split())
    return (text[: n - 1] + "…" if len(text) > n else text).replace("|", "\\|")


def _owned(child: dict, by_id: dict) -> str:
    own = "; ".join(f"{i}[{by_id[i]['kind']}] {by_id[i]['text']}" for i in child["owns"])
    shared = (
        ("<br>shared: " + "; ".join(f"{i}[{by_id[i]['kind']}] {by_id[i]['text']}" for i in child["carries_shared"]))
        if child["carries_shared"]
        else ""
    )
    return _cell(own, 260) + shared[:200]


def render_report(result: dict) -> str:
    q, final, parent = result["question"], result["final"], result["parent_contract"]
    by_id = {r["id"]: r for r in [*parent["requirements"], *parent["ambiguities"]]}
    rec = final["reconciliation"]
    man = result["manifest"]
    lines = [
        "# Decomposition report",
        "",
        f"Engine `{man['engine_version']}` | model `{man['model_label']}` | request sha256 `{result['question_sha256'][:16]}` | final = pass {result['final_pass']} | "
        f"calls {man['call_summary']['calls']}/{man['call_summary']['max_calls']} (cap reached: {man['call_cap_reached']})",
        "",
        "**Semantic fidelity is NOT certified.** Verified traceability (cited words and offsets exist) is a different, narrower fact. "
        "Ownership is structural; preservation, addition, bundling and cue checks are lexical diagnostics. Obligation kinds and ambiguity readings are model candidates.",
        "",
        "## Original request",
        "",
        f"> {q}",
        "",
        "## Children (final pass), with the obligations each owns",
        "",
        "| id | kind | question | owns / shared obligations | flags |",
        "|---|---|---|---|---|",
    ]
    for c in final["children"]:
        flags = ", ".join(f["flag"] for f in c["flags"]) + (
            " | " + ", ".join(sorted({i["kind"] for i in c["interpretations"]})) if c["interpretations"] else ""
        )
        lines.append(
            f"| {c['child_id']} | {c['kind']} | {_cell(c['question'])} | {_owned(c, by_id)} | {_cell(flags, 160)} |"
        )
    dec = result.get("decomposition_decision")
    if dec:
        lines += [
            "",
            "## Decomposition decision (about DECOMPOSITION only; nothing here is an answer)",
            "",
            f"**{dec['outcome']}**{' (applied: the original request is kept exactly and sent through the normal Ask path once, without the writer)' if dec.get('applied') else ''}: {dec['basis']}",
            "",
        ]
        lines += [f"- [{'x' if c['passed'] else ' '}] {c['check']}: {_cell(c['evidence'], 120)}" for c in dec["checks"]]
        lines += [f"- limit: {x}" for x in dec["limits"]]
        lines += [
            f"- answer state: `{dec['downstream']['answer_state']}` ({dec['downstream']['note']})",
            f"- writer calls avoided: {dec.get('model_calls_avoided', {}).get('writer_calls', 0)}",
        ]
    if parent.get("clarifications"):
        lines += ["", "## User clarifications applied (span-linked; every other ambiguity stays open)", ""]
        lines += [
            f'- {c["id"]} [{c["kind"]}] on "{c["target_text"]}" {c["target_span"]} in "{c["phrase"]}": means "{c["means"]}" (authorized by {c["authorized_by"]})'
            + (f' | points at "{c["refers_to"]["text"]}" {c["refers_to"]["span"]}' if c.get("refers_to") else "")
            + (f" | pairs: {[m['text'] for m in c['pairs']]}" if c.get("pairs") else "")
            for c in parent["clarifications"]
        ]
    qt = final.get("question_tree")
    if qt:
        roll = rec.get("question_tree") or {}
        lines += ["", "## Question tree (nesting comes only from approved clarifications)", ""]

        def walk(node_id: str, depth: int) -> None:
            n = next(x for x in qt["nodes"] if x["node_id"] == node_id)
            r = (roll.get("nodes") or {}).get(node_id, {})
            lines.append(
                "  " * depth
                + f"- {node_id} [{r.get('own_state', '?')}] owns {[o['id'] for o in n['own_obligations']]}"
                + (f" | folded {[f['child_id'] for f in n['folded_from']]}" if n["folded_from"] else "")
                + (f" | depends on {[d['node'] for d in n['depends_on'] if d.get('node')]}" if n["depends_on"] else "")
            )
            for sub in n["subordinates"]:
                walk(sub, depth + 1)

        for top in qt["root"]["subordinates"]:
            walk(top, 0)
        lines += [f"- joint answers: {[(g['id'], g['status']) for g in roll.get('joint_answer_groups', [])] or 'none'}"]
        lines += [f"- closure rule: {qt['closure_rule']}"]
    contracts = [c for c in final["children"] if c.get("relation_contract")]
    if contracts:
        lines += ["", "## Relationship contracts (parsed from the request's exact words)", ""]
        for c in contracts:
            rc = c["relation_contract"]
            if rc["parse_status"] != "parsed":
                lines.append(f"- {c['child_id']} ({rc['obligation_id']}): unparsed - {rc.get('reason')}")
                continue
            lines.append(
                f'- {c["child_id"]} ({rc["obligation_id"]}): subject "{rc["subject"]["text"]}" {rc["subject"]["spans"][0]}'
                + (
                    f" [clarified: {rc['subject']['resolved_text']}]"
                    if rc["subject"].get("resolved_text")
                    else (" [unresolved reference]" if rc["subject"]["is_reference"] else "")
                )
                + f' | relation "{rc["relation"]["text"]}" | target "{rc["target"]["text"]}" {rc["target"]["spans"][0]}'
                + f" | polarity {rc['polarity']['requested']} manner {rc['manner']['requested']} | form {rc['answer_form']['form']}"
            )
            conflict = (c.get("diagnostics") or {}).get("relation") or {}
            lines += [f"  - CONFLICT {v['kind']}: {v['note']}" for v in conflict.get("violations", [])]
            lines += [f"  - review {v['kind']}: {v['note']}" for v in conflict.get("review", [])]
    audited = [c for c in final["children"] if c.get("edit_ledger")]
    if audited:
        lines += [
            "",
            "## Source-edit ledger (an AUDIT of detected source-edit problems, not proof of provenance or fidelity)",
            "",
            "| id | ledger | copied | context | siblings left out | grammatical | clarification-supplied | detected problems | clarifications used |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for c in audited:
            led = c["edit_ledger"]
            s = led["summary"]
            problems = "; ".join(
                f"{f['kind']}({', '.join(f['words'][:4])})" for f in led["flags"] if f["class"] != "info"
            )
            lines.append(
                f"| {c['child_id']} | {led['status']} | {s['copied']} | {s['context_carried']} | {s['sibling_removed']} | {s['grammatical']} | "
                f"{s['clarification_supplied']} | {_cell(problems or 'none', 160)} | {', '.join(led['clarifications_used']) or '-'} |"
            )
    tr = final["verified_traceability"]
    lines += [
        "",
        "## Verified traceability",
        "",
        f"ok = **{tr['ok']}** ({tr['scope']}); units without a child: {tr['units_without_child'] or 'none'}",
    ]
    lines += [f"- {v}" for v in tr["violations"][:20]]
    s = rec["summary"]
    lines += [
        "",
        "## Reconciliation",
        "",
        f"children {s['children_by_kind']} | successful (not fallback/unit-level/bundled/hard-fail) {s['successful_children']} | bundled {s['bundled_children']} | "
        f"with an obligation not lexically preserved {s['children_with_unpreserved_obligations']} | open ambiguities {s['open_ambiguities']} | unresolved rows {s['unresolved_count']}",
        "",
        "Statuses: " + ", ".join(f"{k}={v}" for k, v in s["status_counts"].items()),
        "",
        "### Unresolved",
        "",
    ]
    lines += [
        f"- `{r['id']}` [{r['kind']}, {r['status']}] {_cell(r['text'], 140)}"
        + (f" -> readings: {r['alternatives']}" if r.get("alternatives") else "")
        for r in rec["unresolved"]
    ]
    lines += ["", "### Unaccounted original text (diagnostic)", ""]
    lines += [f"- {u['span']} {_cell(u['text'], 120)}" for u in rec["unaccounted_text_diagnostic"]] or ["- none"]
    pp = parent["post_processing"]
    lines += [
        "",
        "## Deterministic inventory post-processing",
        "",
        f"- merged overlapping obligations: {pp['merged'] or 'none'}",
        f"- cue hits dropped because a model obligation covered them: {[d['id'] for d in pp['dropped_cues']] or 'none'}",
        f"- list splits: {pp['list_splits'] or 'none'}",
        f"- whole-pass obligations absorbed by finer unit obligations (not merged): {[a['id'] for a in pp['absorbed_whole_pass']] or 'none'}",
    ]
    if result["pass2"]:
        lines += [
            "",
            "## Repair PROPOSALS (stored separately; NOT applied to the final; the first pass is unchanged)",
            "",
        ]
        for r in result["pass2"]["repairs"]:
            verdict = (
                "lexically acceptable, pending human review"
                if r.get("accepted")
                else f"rejected ({r.get('rejected_reason')})"
            )
            lines.append(f"- {r['child_id']}: {verdict}; reasons {r['reasons']}")
            if r.get("attempted"):
                lines += [f"  - before: {_cell(r['before'], 200)}", f"  - after: {_cell(r['after'], 200)}"]
    pend = man.get("pending_researcher_decisions") or []
    if pend:
        lines += ["", "## Decisions still PENDING with the researcher (the engine makes none of them)", ""]
        lines += [f"- {d['id']}: {d['what']}" for d in pend]
    if s.get("pending_researcher_confirmation") or s.get("unverified_by_lexical_checks"):
        lines += ["", "## Qualified results", ""]
        lines += [
            f"- pending researcher confirmation (relies on engine-recorded wording): {s['pending_researcher_confirmation'] or 'none'}",
            f"- lexical-check limits recorded for: {sorted(s['unverified_by_lexical_checks']) or 'none'}",
        ]
    lines += ["", "## Known limitations", ""] + [f"- {x}" for x in s.get("known_limitations", [])]
    lines += ["", "## Calls", "", f"{man['call_summary']}"]
    return "\n".join(lines) + "\n"
