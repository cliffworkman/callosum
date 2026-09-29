"""DEV-ONLY comparison of an engine run against the manually approved q_aib decomposition.

The manual reference is read here as DATA for comparison. It is never imported by the engine and never appears in a
prompt. Alignment is a LEXICAL DIAGNOSTIC (do the child's content stems cover the words the manual item carries), so it
can show a merge, a split or a missing word; it cannot show that a child preserves what the words mean. The
consequential-difference judgment is made by a human reading these tables.

    python -m experiments.ask_cli_revised.decompose.reference_compare --run RUN_DIR --reference-dir hier-decomp-aib
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose.checks import cue_preserved

THRESHOLD = 0.6


def _span_cov(spans: list, lo: int, hi: int) -> float:
    return round(len({x for a, b in spans for x in range(max(a, lo), min(b, hi))}) / (hi - lo), 2)


def _stems(text: str) -> list[str]:
    return lx.content_stems(re.sub(r"AMB-\d+:", " ", text))


def _cov(required: list[str], child_text: str) -> float:
    return round(lx.coverage_fraction(required, lx.content_stems(child_text)), 2)


def _load_final(run_dir: Path) -> tuple[dict, list[dict], int]:
    parent = json.loads((run_dir / "01_parent_contract.json").read_text(encoding="utf-8"))
    final_pass = json.loads((run_dir / "06_final_reconciliation.json").read_text(encoding="utf-8"))["final_pass"]
    name = "04_pass2_repaired.json" if final_pass == 2 else "02_pass1_children.json"
    return parent, json.loads((run_dir / name).read_text(encoding="utf-8"))["children"], final_pass


def compare(run_dir: Path, ref_dir: Path) -> dict:
    parent, children, final_pass = _load_final(run_dir)
    question = parent["original_question"]
    inv = json.loads((ref_dir / "01_parent_requirements.json").read_text(encoding="utf-8"))
    assert inv["original_question"] == question, "the run is not on the reference request"
    manual = json.loads((ref_dir / "design_v2_rev4" / "children_v2.json").read_text(encoding="utf-8"))["children"]
    generated = [c for c in children if c["kind"] != "fallback"]
    fallback = [c for c in children if c["kind"] == "fallback"]

    pairs = []
    for m in manual:
        required = list(dict.fromkeys(s for c in m["carries"] for s in _stems(c[1] or c[0])))
        rows = sorted(
            (
                {"child": c["child_id"], "coverage": _cov(required, c["question"]), "question": c["question"]}
                for c in generated
            ),
            key=lambda r: -r["coverage"],
        )
        rows = [r for r in rows if r["coverage"] >= THRESHOLD]
        polar = bool(m.get("wording")) and lx.tokens(m["wording"])[0] in {"do", "does", "is", "are"}
        polar_kept = [
            r["child"]
            for r in rows
            if cue_preserved("whether", next(c["question"] for c in generated if c["child_id"] == r["child"]))
        ]
        pairs.append(
            {
                "manual_id": m["id"],
                "scope": m["scope"],
                "manual": m.get("wording"),
                "required_stems": required,
                "generated": rows[:4],
                "manual_is_polar": polar,
                "polar_form_kept_by": polar_kept if polar else None,
                "verdict": "lexically_covered" if rows else "NO_GENERATED_CHILD_COVERS_ITS_WORDS",
            }
        )
    merges = []
    for c in generated:
        held = [
            p["manual_id"]
            for p in pairs
            if p["scope"] == "primary" and any(r["child"] == c["child_id"] for r in p["generated"])
        ]
        if len(held) >= 2:
            merges.append({"child": c["child_id"], "question": c["question"], "covers_manual_children": held})
    obligations = []
    for grp in ("requirements", "qualifiers", "output_expectations"):
        for r in inv[grp]:
            if not isinstance(r.get("span"), list):
                continue
            req = _stems(r["text"])
            if not req:  # only function/cue words (whether, any, please return): stem overlap cannot assess it
                obligations.append(
                    {
                        "id": r["id"],
                        "kind": r["kind"],
                        "text": r["text"],
                        "best_single_child": None,
                        "single_child_coverage": None,
                        "union_coverage": None,
                        "verdict": "not_lexically_assessable (no content words; cue-only)",
                    }
                )
                continue
            best = max(generated, key=lambda c: _cov(req, c["question"]), default=None)
            cov = _cov(req, best["question"]) if best else 0.0
            union = round(lx.coverage_fraction(req, [s for c in generated for s in lx.content_stems(c["question"])]), 2)
            obligations.append(
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "text": r["text"],
                    "best_single_child": best["child_id"] if best else None,
                    "single_child_coverage": cov,
                    "union_coverage": union,
                    "verdict": "carried_by_one_child"
                    if cov >= THRESHOLD
                    else ("spread_across_children" if union >= THRESHOLD else "NOT_CARRIED (candidate omission)"),
                }
            )
    relations = []
    for e in inv["relations"]:
        a, b = (_stems(x) for x in e["between"])
        holders = [
            c["child_id"]
            for c in generated
            if _cov(a, c["question"]) >= THRESHOLD and _cov(b, c["question"]) >= THRESHOLD
        ]
        anywhere = [c["child_id"] for c in generated if _cov(a, c["question"]) >= THRESHOLD] and [
            c["child_id"] for c in generated if _cov(b, c["question"]) >= THRESHOLD
        ]
        relations.append(
            {
                "id": e["id"],
                "between": e["between"],
                "asks": e["asks"],
                "children_with_both_endpoints": holders,
                "verdict": "both_endpoints_in_one_child"
                if holders
                else ("endpoints_only_in_different_children" if anywhere else "NOT_CARRIED"),
            }
        )
    ambiguities = []
    for a in inv["ambiguities"]:
        if isinstance(a.get("span"), list):
            spans = a["span"]
            gen = [
                g["id"]
                for g in parent["ambiguities"]
                if g["spans"] and any(max(spans[0], s[0]) < min(spans[1], s[1]) for s in g["spans"])
            ]
            ambiguities.append(
                {
                    "id": a["id"],
                    "phrase": a["phrase"],
                    "generated_ambiguity_ids": gen,
                    "verdict": "engine_recorded_an_ambiguity_here" if gen else "NOT_RECORDED",
                }
            )
    ownership = []
    for grp in ("requirements", "qualifiers", "output_expectations"):
        for r in inv[grp]:
            if not isinstance(r.get("span"), list):
                continue
            lo, hi = r["span"]
            owners = []
            for c in generated:
                own_spans = [s for link in c["parent_links"] if link["role"] != "shared_frame" for s in link["spans"]]
                shared_spans = [
                    s for link in c["parent_links"] if link["role"] == "shared_frame" for s in link["spans"]
                ]
                if _span_cov(own_spans, lo, hi) >= 0.5:
                    owners.append({"child": c["child_id"], "coverage": _span_cov(own_spans, lo, hi), "role": "owns"})
                elif _span_cov(shared_spans, lo, hi) >= 0.5:
                    owners.append(
                        {"child": c["child_id"], "coverage": _span_cov(shared_spans, lo, hi), "role": "shared"}
                    )
            ownership.append(
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "text": r["text"],
                    "owners": owners,
                    "verdict": "owned_or_shared_by_a_child" if owners else "NOT_OWNED (candidate omission)",
                }
            )
    matched = {r["child"] for p in pairs for r in p["generated"]}
    return {
        "final_pass": final_pass,
        "generated_children": len(generated),
        "fallback_children": len(fallback),
        "note": "lexical diagnostic, not a fidelity judgment; fallback children are excluded from every count",
        "manual_children_alignment": pairs,
        "merged_generated_children": merges,
        "manual_obligation_ownership": ownership,
        "manual_obligations": obligations,
        "manual_relations": relations,
        "generated_without_manual_counterpart": [
            {"child": c["child_id"], "question": c["question"]} for c in generated if c["child_id"] not in matched
        ],
        "manual_ambiguities": ambiguities,
    }


def render(result: dict) -> str:
    L = [
        "# q_aib engine output vs manual reference (lexical alignment)",
        "",
        result["note"],
        "",
        f"Generated (non-fallback) children: {result['generated_children']}; fallback children: {result['fallback_children']}; final pass {result['final_pass']}",
        "",
        "## Manual children -> generated children",
        "",
        "| manual | manual wording | generated children whose words cover it | polar form kept | verdict |",
        "|---|---|---|---|---|",
    ]
    for p in result["manual_children_alignment"]:
        gen = "<br>".join(f"{g['child']} ({g['coverage']}): {g['question']}" for g in p["generated"][:2]) or "-"
        L.append(
            f"| {p['manual_id']} ({p['scope']}) | {p['manual'] or '(exploratory)'} | {gen} | {p['polar_form_kept_by'] if p['manual_is_polar'] else 'n/a'} | {p['verdict']} |"
        )
    L += ["", "## Generated children that merge several manual children", ""]
    L += [
        f"- {m['child']}: covers {m['covers_manual_children']} — {m['question']}"
        for m in result["merged_generated_children"]
    ] or ["- none"]
    L += [
        "",
        "## Manual relations",
        "",
        "| id | between | children with both endpoints | verdict |",
        "|---|---|---|---|",
    ]
    L += [
        f"| {r['id']} | {r['between']} | {r['children_with_both_endpoints']} | {r['verdict']} |"
        for r in result["manual_relations"]
    ]
    L += [
        "",
        "## Manual obligations: which generated child OWNS the words (structural span overlap)",
        "",
        "| id | text | owners | verdict |",
        "|---|---|---|---|",
    ]
    L += [
        f"| {o['id']} [{o['kind']}] | {o['text'][:60]} | {[(x['child'], x['role']) for x in o['owners']]} | {o['verdict']} |"
        for o in result["manual_obligation_ownership"]
    ]
    L += [
        "",
        "## Manual obligations: lexical coverage (weaker; stem overlap only)",
        "",
        "| id | text | best child (coverage / union) | verdict |",
        "|---|---|---|---|",
    ]
    L += [
        f"| {o['id']} [{o['kind']}] | {o['text'][:60]} | {o['best_single_child']} ({o['single_child_coverage']} / {o['union_coverage']}) | {o['verdict']} |"
        for o in result["manual_obligations"]
    ]
    L += ["", "## Generated children with no manual counterpart", ""]
    L += [f"- {u['child']}: {u['question']}" for u in result["generated_without_manual_counterpart"]] or ["- none"]
    L += ["", "## Manual ambiguities", ""] + [
        f"- {a['id']} `{a['phrase']}`: {a['verdict']} {a['generated_ambiguity_ids']}"
        for a in result["manual_ambiguities"]
    ]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True)
    p.add_argument("--reference-dir", required=True)
    args = p.parse_args(argv)
    run = Path(args.run)
    result = compare(run, Path(args.reference_dir))
    (run / "REFERENCE_COMPARISON.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (run / "REFERENCE_COMPARISON.md").write_text(render(result), encoding="utf-8")
    print(f"wrote {run / 'REFERENCE_COMPARISON.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
