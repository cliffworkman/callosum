"""Run 0.6 request lineage: source_unit -> chosen item(s) -> retrieval query -> papers -> anchors -> A/B/C/D/E.

Assembles the machine-readable lineage graph + the human `run_0_6_request_lineage.md` + Phase-12
stage-by-stage survival metrics. STARVED is a DETERMINISTIC signal (a source unit that produced 0 papers, 0
anchors, or 0 non-E envelopes). PRESERVED / DRIFTED remain POST-HOC HUMAN labels — this module leaves an
`assessment` slot null; it never asks Qwen and never alters the run. Pure (operates on frozen decomposition +
walk records + the frozen decomposition's audit).
"""

from __future__ import annotations

from collections import Counter


def _audit_by_item(audit: dict) -> dict:
    cov = {c["source_unit_id"]: c for c in audit["source_unit_coverage"]}
    loo = {d["item_id"]: d for d in audit["leave_one_out"]}
    drift = {d["item_id"]: d for d in audit.get("source_local_drift", [])}
    return {"coverage": cov, "loo": loo, "drift": drift}


def build_lineage(frozen: dict, walk_records: list[dict], audit: dict) -> dict:
    """One lineage row per canonical source unit (grouping this unit's item walks)."""
    idx = _audit_by_item(audit)
    walks_by_unit: dict[str, list[dict]] = {}
    for record in walk_records:
        walks_by_unit.setdefault(record["source_unit_id"], []).append(record)

    rows = []
    for unit in frozen["items"]:  # frozen items preserve source order; dedupe unit ids below
        pass
    seen: set[str] = set()
    ordered_units = [i["source_unit_id"] for i in frozen["items"] if not (i["source_unit_id"] in seen or seen.add(i["source_unit_id"]))]

    for unit_id in ordered_units:
        items = [i for i in frozen["items"] if i["source_unit_id"] == unit_id]
        source_text = items[0]["source_text"]
        item_walks = walks_by_unit.get(unit_id, [])

        paper_ids = {n["paper_id"] for w in item_walks for n in w["nominations"]}
        anchors = [a for w in item_walks for a in w["anchors"]]
        anchor_paper_ids = {a["paper_id"] for a in anchors}
        window_choices = [a["window_choice"] for a in anchors if a["window_choice"] is not None]
        non_e = [c for c in window_choices if c in ("A", "B", "C", "D")]
        axis_contribution = sum(w["axis_nomination_count"] for w in item_walks)

        starved = (len(paper_ids) == 0) or (len(anchors) == 0) or (len(non_e) == 0)

        rows.append(
            {
                "source_unit_id": unit_id,
                "source_text": source_text,
                "items": [
                    {
                        "item_id": i["item_id"],
                        "text": i["text"],
                        "from_fallback": i.get("from_fallback", False),
                        "repaired": i.get("repaired", False),
                        "source_local_similarity": idx["drift"].get(i["item_id"], {}).get("source_local_similarity"),
                        "loo_delta": idx["loo"].get(i["item_id"], {}).get("delta"),
                    }
                    for i in items
                ],
                "coverage_best_match": idx["coverage"].get(unit_id, {}).get("best_match"),
                "coverage_weak": idx["coverage"].get(unit_id, {}).get("weak"),
                "retrieval_queries": [w["retrieval_query"] for w in item_walks],
                "discovery": {
                    "n_candidate_papers": sum(w["n_papers"] for w in item_walks),
                    "n_distinct_papers": len(paper_ids),
                    "axis_nomination_count": axis_contribution,
                    "top_scores": sorted(
                        (round(n["score"], 4) for w in item_walks for n in w["nominations"]), reverse=True
                    )[:5],
                },
                "retrieval": {
                    "n_anchors": len(anchors),
                    "n_distinct_papers_with_anchors": len(anchor_paper_ids),
                    "score_min": round(min((a["retrieval_score"] for a in anchors), default=0.0), 4),
                    "score_max": round(max((a["retrieval_score"] for a in anchors), default=0.0), 4),
                },
                "context": {
                    "n_anchors_reaching_context": len(window_choices),
                    "choice_distribution": dict(Counter(window_choices)),
                    "non_e_envelopes": len(non_e),
                },
                "starved": starved,
                "assessment": None,  # POST-HOC HUMAN: PRESERVED / DRIFTED / STARVED (filled during review)
                "notes": None,
            }
        )
    return {"case_id": frozen["case_id"], "selected_candidate": frozen["selected_candidate"], "units": rows}


def aggregate_survival(lineage_rows: list[dict]) -> dict:
    """Where does intent begin to disappear? Aggregate stage-by-stage across a question's source units."""
    units = lineage_rows
    n = len(units)
    starved = [u["source_unit_id"] for u in units if u["starved"]]
    no_papers = [u["source_unit_id"] for u in units if u["discovery"]["n_distinct_papers"] == 0]
    no_anchors = [u["source_unit_id"] for u in units if u["retrieval"]["n_anchors"] == 0]
    no_non_e = [u["source_unit_id"] for u in units if u["context"]["non_e_envelopes"] == 0]
    all_choices: Counter = Counter()
    for u in units:
        all_choices.update(u["context"]["choice_distribution"])
    return {
        "n_source_units": n,
        "starved_units": starved,
        "units_with_no_papers": no_papers,
        "units_with_no_anchors": no_anchors,
        "units_with_no_non_e_envelope": no_non_e,
        "context_choice_distribution": dict(all_choices),
    }


def lineage_markdown(all_lineage: list[dict]) -> list[str]:
    lines = ["# Run 0.6 — request-lineage review artifact", ""]
    lines.append(
        "Per canonical source unit: original text -> chosen standalone rewrite(s) -> decomposition audit -> "
        "retrieval query -> paper discovery -> within-paper anchors -> A/B/C/D/E context envelopes. "
        "PRESERVED / DRIFTED are post-hoc human labels (STARVED is computed); the `ASSESSMENT` line is filled "
        "during review, never by the model."
    )
    lines.append("")
    for lin in all_lineage:
        lines.append(f"## {lin['case_id']} (selected: {lin['selected_candidate']})")
        lines.append("")
        for u in lin["units"]:
            lines.append(f"### REQUEST UNIT {u['source_unit_id']}")
            lines.append("")
            lines.append(f"ORIGINAL SOURCE TEXT: {u['source_text']!r}")
            lines.append("")
            lines.append("CHOSEN STANDALONE DECOMPOSITION:")
            for it in u["items"]:
                flags = []
                if it["from_fallback"]:
                    flags.append("fallback=source-text")
                if it["repaired"]:
                    flags.append("repaired")
                tag = f" ({', '.join(flags)})" if flags else ""
                lines.append(f"  - [{it['item_id']}] {it['text']!r}{tag}")
            lines.append("")
            lines.append("DECOMPOSITION AUDIT:")
            lines.append(f"  coverage best_match={u['coverage_best_match']} weak={u['coverage_weak']}")
            for it in u["items"]:
                lines.append(
                    f"  {it['item_id']}: source_local_similarity={it['source_local_similarity']} loo_delta={it['loo_delta']}"
                )
            lines.append("")
            lines.append(f"RETRIEVAL QUERY / QUERIES: {u['retrieval_queries']}")
            lines.append("")
            d = u["discovery"]
            lines.append(
                f"PAPER DISCOVERY: distinct_papers={d['n_distinct_papers']} candidate_slots={d['n_candidate_papers']} "
                f"axis_nominations={d['axis_nomination_count']} top_scores={d['top_scores']}"
            )
            r = u["retrieval"]
            lines.append(
                f"WITHIN-PAPER RETRIEVAL: anchors={r['n_anchors']} distinct_papers={r['n_distinct_papers_with_anchors']} "
                f"score_range=[{r['score_min']}, {r['score_max']}]"
            )
            c = u["context"]
            lines.append(
                f"MINIMUM-SUFFICIENT CONTEXT: anchors_selected={c['n_anchors_reaching_context']} "
                f"distribution={c['choice_distribution']} non_e_envelopes={c['non_e_envelopes']}"
            )
            lines.append("")
            lines.append(f"LINEAGE ASSESSMENT (computed): starved={u['starved']}")
            lines.append("ASSESSMENT (human, post-hoc): PRESERVED / DRIFTED / STARVED — _to fill_")
            lines.append("NOTES: _to fill_")
            lines.append("")
            lines.append("---")
            lines.append("")
    return lines
