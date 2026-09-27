"""Reports over a run's receipts: per-child trace, baseline-vs-new review sheet, route attribution, expectation results.

No composite score anywhere. The review sheet puts the baseline and the new raw answers, their evidence, the diagnostics and the
unresolved units side by side for Cliff to adjudicate. Route attribution is DESCRIPTIVE provenance of ONE union run: it says
which routes reached what, not how a route-exclusive run would have performed.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import expectations, freeze

ATTRIBUTION_CAVEAT = (
    "Descriptive provenance of one union run. It does not show how a route-exclusive run would have performed."
)


def _jsonl(path: Path) -> list[dict]:
    return (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if path.exists()
        else []
    )


def route_attribution(run_dir: Path | str) -> dict:
    run = Path(run_dir)
    noms = _jsonl(run / "01_nominations.jsonl")
    nbhds = _jsonl(run / "05_neighborhoods.jsonl")
    packets = [p for p in _jsonl(run / "07_packets.jsonl") if p.get("state") == "built"]
    elig = [e for e in _jsonl(run / "08_eligibility.jsonl") if e.get("state") == "usable"]
    closing = {
        e["packet_id"] for e in elig if any(u["status"] == "directly_establishes" for u in e["per_unit"].values())
    }
    nomination = Counter()
    for row in noms:
        for route in {r["route"] for r in row["routes"]}:
            nomination[route] += 1
    by_anchor = defaultdict(lambda: Counter())
    routes_of_nbhd = {n["nbhd_id"]: n.get("routes", []) for n in nbhds}
    for n in nbhds:
        for route in {r.split(":")[0] for r in n.get("routes", [])}:
            by_anchor[route][f"neighborhoods_{n['state']}"] += 1
    for p in packets:
        for route in {r.split(":")[0] for r in routes_of_nbhd.get(p["nbhd_id"], p.get("anchor_routes", []))}:
            by_anchor[route]["packets"] += 1
            if p["packet_id"] in closing:
                by_anchor[route]["packets_that_closed_a_unit"] += 1
    return {
        "caveat": ATTRIBUTION_CAVEAT,
        "nominated_papers_by_route": dict(nomination),
        "anchor_routes": {k: dict(v) for k, v in by_anchor.items()},
    }


def child_trace(run_dir: Path | str, substrate: freeze.FrozenSubstrate, child_id: str) -> str:
    run = Path(run_dir)
    child = substrate.child(child_id)
    lines = [f"# {child_id}: contract to raw answer", "", f"**Approved contract (exact):** {child.contract_text}", ""]
    lines += [
        "## Units",
        *[f"- {u.unit_id} ({u.kind}{', condition' if u.is_condition else ''}): {u.text}" for u in child.units],
        "",
    ]
    noms = [n for n in _jsonl(run / "01_nominations.jsonl") if n["child_id"] == child_id]
    lines += [
        f"## Nominations ({len(noms)})",
        *[
            f"- paper {n['paper_id']} [{n['budget_state']}] routes: {sorted({r['route'] for r in n['routes']})}"
            for n in noms[:30]
        ],
        "",
    ]
    triage = [t for t in _jsonl(run / "02_triage.jsonl") if t["child_id"] == child_id]
    lines += [
        f"## Triage ({len(triage)})",
        *[
            f"- paper {t['paper_id']}: {t.get('state')} / {t.get('relation_to_child')} / {t.get('contribution_type')}"
            for t in triage[:30]
        ],
        "",
    ]
    nbhds = [n for n in _jsonl(run / "05_neighborhoods.jsonl") if n["child_id"] == child_id]
    lines += [
        f"## Neighborhoods ({len(nbhds)})",
        *[
            f"- [{n['state']}] paper {n['paper_id']} att {n['attachment_id']} chunks {n['chunk_ids'][0]}-{n['chunk_ids'][-1]} routes {n.get('routes')}"
            for n in nbhds
        ],
        "",
    ]
    packets = [
        p for p in _jsonl(run / "07_packets.jsonl") if p.get("state") == "built" and child_id in p["found_under"]
    ]
    lines += [f"## Packets found under {child_id} ({len(packets)})"]
    for p in packets:
        lines.append(
            f"- {p['packet_id']} paper {p['paper_id']} att {p['attachment']['id']} ({'primary' if p['attachment']['is_primary'] else 'alternate'}) form={p['evidence_form']} attribution={p['part_attribution']}"
        )
        for part in p["parts"]:
            lines.append(
                f"    - [{part['span_id']}] {part['role']} {part['section']} p.{part['page_start']}: {part['text'][:200]}"
            )
    lines.append("")
    elig = [
        e for e in _jsonl(run / "08_eligibility.jsonl") if e.get("child_id") == child_id and e.get("state") == "usable"
    ]
    lines += [f"## Eligibility for {child_id} ({len(elig)} packet-child rows)"]
    for e in elig:
        lines.append(
            f"- {e['packet_id']} ({e['route_relation']}): "
            + "; ".join(
                f"{u}={s['status']}{'(missing ' + ','.join(s['missing']) + ')' if s['missing'] else ''}"
                for u, s in e["per_unit"].items()
            )
        )
    lines.append("")
    rows = (
        json.loads((run / "09_coverage.json").read_text(encoding="utf-8")).get(child_id, [])
        if (run / "09_coverage.json").exists()
        else []
    )
    lines += [
        "## Coverage (never a completeness claim)",
        *[f"- {r['unit_id']} ({r['row_type']}): {r['state']}" for r in rows],
        "",
    ]
    rec = [r for r in _jsonl(run / "10_recovery.jsonl") if r["child_id"] == child_id]
    lines += [
        f"## Recovery ({len(rec)} actions)",
        *[f"- {r['action']} for {r['unit_id']} because {r['trigger_reason']}; recovers {r['recovers']}" for r in rec],
        "",
    ]
    answer = run / "12_answers" / f"{child_id}_raw_answer.txt"
    if answer.exists():
        rec_json = json.loads((run / "12_answers" / f"{child_id}_record.json").read_text(encoding="utf-8"))
        lines += [
            "## Raw answer (exactly as generated)",
            "",
            answer.read_text(encoding="utf-8"),
            "",
            "## Advisory diagnostics (never gate)",
            "```json",
            json.dumps(rec_json["diagnostics"], indent=2, ensure_ascii=False),
            "```",
        ]
    return "\n".join(lines)


def review_sheet(
    run_dir: Path | str, substrate: freeze.FrozenSubstrate, child_ids: list[str], ab_root: Path | str = freeze.AB_ROOT
) -> str:
    run, root = Path(run_dir), Path(ab_root)
    baseline = json.loads(
        (root / "child_evidence_diag" / "00_contracts_evidence_and_receipt.json").read_text(encoding="utf-8")
    )
    base = {c["child_id"]: c for c in baseline["children"]}
    out = ["# Review sheet: baseline vs new, per child (Cliff adjudicates; no composite score)", ""]
    for cid in child_ids:
        child = substrate.child(cid)
        answer_path = run / "12_answers" / f"{cid}_raw_answer.txt"
        base_answer = (root / "child_evidence_diag" / "answers" / f"{cid}_raw_answer.txt").read_text(encoding="utf-8")
        out += [
            f"## {cid}",
            f"**Contract:** {child.contract_text}",
            "",
            "### Baseline evidence (own route, claim-verified)",
        ]
        out += [
            f"- [{p['unit_id']}] paper {p['paper_id']}: {p['passage'][:220]}" for p in base[cid]["eligible_passages"]
        ] or ["- (none)"]
        out += ["", "### Baseline raw answer", "", base_answer, "", "### New evidence given"]
        if answer_path.exists():
            rec = json.loads((run / "12_answers" / f"{cid}_record.json").read_text(encoding="utf-8"))
            out += [f"- shown {shown}: packet {pid}" for shown, pid in rec["id_map"].items()] or [
                "- (none: no eligible evidence)"
            ]
            out += [
                "",
                "### New raw answer",
                "",
                answer_path.read_text(encoding="utf-8"),
                "",
                "### Advisory flags",
                f"- acronym expansions not in any passage: {rec['diagnostics']['acronym_expansions_not_in_any_passage']}",
                f"- directional terms not in cited text: {[f['sentence'] for f in rec['diagnostics']['directional_terms_not_in_cited_passages']]}",
                f"- multi-packet sentences: {[s['sentence'] for s in rec['diagnostics']['multi_packet_sentences']]}",
                f"- invalid cited ids: {rec['diagnostics']['invalid_cited_ids']}",
            ]
        else:
            out += ["- (child not run)"]
        rows = (
            json.loads((run / "09_coverage.json").read_text(encoding="utf-8")).get(cid, [])
            if (run / "09_coverage.json").exists()
            else []
        )
        out += [
            "",
            "### Unit coverage",
            *[f"- {r['unit_id']}: {r['state']}" for r in rows if r["row_type"] == "content"],
            "",
        ]
    return "\n".join(out)


def write_all(
    run_dir: Path | str,
    substrate: freeze.FrozenSubstrate,
    child_ids: list[str],
    *,
    integrity: dict | None = None,
    ab_root: Path | str = freeze.AB_ROOT,
) -> dict:
    run = Path(run_dir)
    results = expectations.evaluate(run, integrity=integrity, children_in_run=child_ids)
    (run / "15_expectation_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run / "16_route_attribution.json").write_text(json.dumps(route_attribution(run), indent=2), encoding="utf-8")
    (run / "17_review_sheet.md").write_text(review_sheet(run, substrate, child_ids, ab_root), encoding="utf-8")
    for cid in child_ids:
        (run / f"trace_{cid}.md").write_text(child_trace(run, substrate, cid), encoding="utf-8")
    tally = Counter(r["status"] for r in results)
    return {
        "expectations": dict(tally),
        "files": [
            "15_expectation_results.json",
            "16_route_attribution.json",
            "17_review_sheet.md",
            *[f"trace_{c}.md" for c in child_ids],
        ],
    }
