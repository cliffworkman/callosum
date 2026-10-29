"""Read-only counterfactual + independent validation of the repaired reference-eligibility policy (q_lld).

Reads the frozen q_lld shadow run, the frozen guarded corpus and both frozen run libraries strictly read-only
(SQLite ``mode=ro&immutable=1``). It never rewrites a packet, ranking, embedding, response or judgment, makes no
model or network call, and writes only into ``--out``. It applies the frozen allocation rule (12 nominated papers
x 6 whole units) with the repaired eligibility policy, then re-validates the frozen outputs.

    python -m experiments.ask_cli_revised.focused_discovery.reference_eligibility_cli --out <dir>
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import time
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

from sqlalchemy import create_engine, text

from app.backend.persistence.chunk_structure_repo import structure_role_states
from app.backend.summarization import evidence_eligibility as policy
from app.backend.summarization.evidence_eligibility import KeyedText, NativeCoverage, decide

from .reference_eligibility import (
    MAX_UNMAPPED_REFERENCE_FRACTION,
    allocate_packet,
    authority_record,
    continuation_flags,
    guarded_anchored_state,
    legacy_anchored_state,
    map_native_regions,
    mapping_audit,
    validate_claims,
)

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / ".local"
QLLD = LOCAL / "q-lld-shadow-e2e-20261019-175119Z"
GUARD = LOCAL / "guarded-evidence-arctic-bge-20261018-212644Z"
INVESTIGATION = LOCAL / "reference-leakage-investigation-20261028Z"
LIBS = Path("C:/Users/cliff/callosum-data/shadow-3embed-20261015/run_libraries")
RUN = QLLD / "juno_run/continuation-c9-20261022-201142Z"


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def ro_engine(path: Path):
    return create_engine(f"sqlite:///file:{Path(path).as_posix()}?mode=ro&immutable=1&uri=true")


def parse_output(content: str):
    t = content.strip()
    if t.startswith("```") and t.endswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(t)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def main() -> None:  # noqa: C901 - one linear, auditable read-only pipeline
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()

    documents = {int(Path(p).stem[1:]): read(p) for p in glob.glob(str(GUARD / "corpus/documents/a*.json"))}
    regions = {a: d["regions"] for a, d in documents.items()}
    flags = {a: continuation_flags(r) for a, r in regions.items()}

    # ---- Arm A (MiniLM, legacy PyMuPDF chunks) -------------------------------------------------------------
    handoff = read(QLLD / "prep/baseline/handoff.json")
    legacy_a = handoff["chunks"]
    coverage_a, ledger = map_native_regions(legacy_a, regions)
    audit = mapping_audit(ledger)
    with ro_engine(LIBS / "minilm.sqlite").connect() as conn:
        roles_a = structure_role_states(conn, [c["id"] for c in legacy_a])
    decisions_a = {}
    for chunk in legacy_a:
        cov = coverage_a[chunk["id"]]
        # The handoff's own "text_sha256" is a canonical-JSON digest; the classifier pins the raw text sha256.
        raw = hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest()
        anchored = legacy_anchored_state(chunk["id"], roles_a, text_sha256=raw)
        decisions_a[str(chunk["id"])] = decide(
            str(chunk["id"]), key_length=cov.key_length, native=cov, anchored=anchored
        )

    # ---- Arm B (Arctic S, guarded Docling units) ---------------------------------------------------------------
    units_b = read(GUARD / "corpus/EVIDENCE_UNITS.json")
    with ro_engine(LIBS / "arctic_s.sqlite").connect() as conn:
        legacy_b = [
            dict(r)
            for r in conn.execute(
                text("select id, attachment_id, page_start, page_end, text from chunks order by id")
            ).mappings()
        ]
        roles_b = structure_role_states(conn, [c["id"] for c in legacy_b])
    by_attachment = defaultdict(list)
    for chunk in legacy_b:
        by_attachment[int(chunk["attachment_id"])].append(chunk)
    keyed = {int(c["id"]): KeyedText.build(str(c["id"]), c["text"] or "") for c in legacy_b}
    decisions_b = {}
    for unit in units_b:
        anchored = guarded_anchored_state(unit, by_attachment[int(unit["attachment_id"])], roles_b, keyed=keyed)
        key_len = len(KeyedText.build("u", unit["text"]).key)
        decision = decide(
            str(unit["research_chunk_id"]),
            key_length=key_len,
            native=NativeCoverage(key_len),
            anchored=anchored,
            native_unit_role=unit.get("source_role"),
        )
        if any(r in flags.get(int(unit["attachment_id"]), set()) for r in unit["native_regions"]):
            decision = replace(decision, reasons=decision.reasons + ("native_region_between_excluded_references_flag",))
        decisions_b[str(unit["research_chunk_id"])] = decision

    # ---- Frozen allocation rule with repaired eligibility ------------------------------------------------------
    side = read(QLLD / "prep/SOURCE_ACTION_SIDECAR.json")
    skip = {"A": set(side["A_entire_navigation_unit_ids"]), "B": set(side["B_entire_navigation_unit_ids"])}
    sources = {s["attachment_id"] for s in read(GUARD / "inputs/SOURCES.json") if s["status"] == "available"}
    by_a = {c["id"]: c for c in legacy_a}
    by_b = {u["research_chunk_id"]: u for u in units_b}
    nomination = {
        "A": read(QLLD / "prep/baseline/nomination_C.json"),
        "B": read(GUARD / "computed/arctic_s/q_lld.nomination_C.json"),
    }
    children = [c["child_id"] for c in read(QLLD / "prep/inputs/q_lld.scope.json")["children"]]

    def eligible_unit(arm):
        def check(uid):
            if arm == "A":
                c = by_a[uid]
                return (
                    c["attachment_id"] in sources and uid not in skip["A"] and c.get("page_start") and c.get("page_end")
                )
            u = by_b[uid]
            return u["attachment_id"] in sources and uid not in skip["B"] and bool(u.get("pages"))

        return check

    inventory = read(INVESTIGATION / "CONFIRMED_LEAKAGE_INVENTORY.json")["inventory"]
    inv = {(x["arm"], int(x["internal_unit_id"])): x for x in inventory}
    decisions = {"A": decisions_a, "B": decisions_b}
    namespace = {"A": "legacy_chunk", "B": "guarded_research_unit"}
    per_child, delivered_units = [], {"A": set(), "B": set()}
    for arm in "AB":
        for cid in children:
            ranking = (
                read(QLLD / f"prep/baseline/{cid}.ranking.json")
                if arm == "A"
                else read(GUARD / f"computed/arctic_s/q_lld.{cid}.ranking.json")
            )
            frozen = read(QLLD / f"prep/prepared/{arm}/{cid}.evidence.json")["evidence"]
            frozen_ids = [int(e["internal_unit_id"]) for e in frozen]
            delivered_units[arm].update(frozen_ids)
            alloc = allocate_packet(
                nomination[arm]["child_orders"][cid], ranking, decisions[arm], eligible_unit=eligible_unit(arm)
            )
            chosen = [(int(u), s) for p in alloc["papers"] for u, s in p["slots"].selected]
            chosen_ids = [u for u, _ in chosen]
            papers = [p["paper_id"] for p in alloc["papers"] if not p["skipped"]]
            frozen_papers = read(QLLD / f"prep/prepared/{arm}/{cid}.evidence.json")["selected_physical_papers"]
            row = {
                "arm": arm,
                "child_id": cid,
                "frozen_slots": len(frozen_ids),
                "frozen_bibliography_slots": sum(
                    inv.get((arm, u), {}).get("category") == "standalone_bibliography" for u in frozen_ids
                ),
                "frozen_metadata_slots": sum(
                    str(inv.get((arm, u), {}).get("category", "")).startswith("article_metadata") for u in frozen_ids
                ),
                "corrected_slots": len(chosen),
                "corrected_eligible_slots": sum(s == "eligible" for _, s in chosen),
                "corrected_disputed_fallback_slots": sum(s == "disputed" for _, s in chosen),
                "corrected_bibliography_slots": sum(
                    inv.get((arm, u), {}).get("category") == "standalone_bibliography" for u in chosen_ids
                ),
                "corrected_bibliography_slots_as_disputed": sum(
                    inv.get((arm, u), {}).get("category") == "standalone_bibliography" and s == "disputed"
                    for u, s in chosen
                ),
                "corrected_metadata_slots": sum(
                    str(inv.get((arm, u), {}).get("category", "")).startswith("article_metadata") for u in chosen_ids
                ),
                "units_removed_from_frozen_packet": len(set(frozen_ids) - set(chosen_ids)),
                "units_added_by_backfill": len(set(chosen_ids) - set(frozen_ids)),
                "withheld_units_encountered": sum(len(p["slots"].withheld) for p in alloc["papers"]),
                "demoted_units_not_used": sum(len(p["slots"].demoted_unused) for p in alloc["papers"]),
                "paper_shortages": {
                    str(p["paper_id"]): p["slots"].shortage for p in alloc["papers"] if p["slots"].shortage
                },
                "selected_papers_changed": papers != frozen_papers,
                "removed_unit_ids": sorted(set(frozen_ids) - set(chosen_ids)),
            }
            per_child.append(row)

    # ---- Inventory reproduction and false positives ------------------------------------------------------------
    def status(arm, uid):
        return decisions[arm][str(uid)]

    inv_rows = []
    for (arm, uid), x in sorted(inv.items()):
        d = status(arm, uid)
        inv_rows.append(
            {
                "source_id": x["source_id"],
                "arm": arm,
                "internal_unit_id": uid,
                "category": x["category"],
                "substantive_eligibility": d.substantive,
                "decision": d.decision,
                "native_reference_coverage": round(d.native_reference_coverage, 4),
                "native_nonsubstantive_coverage": round(d.native_nonsubstantive_coverage, 4),
                "anchored_state": d.anchored.state,
                "anchored_coverage": round(d.anchored.coverage, 4),
                "join_coverage": d.anchored.detail.get("join_coverage"),
                "reasons": list(d.reasons),
            }
        )
    bib = [r for r in inv_rows if r["category"] == "standalone_bibliography"]
    meta = [r for r in inv_rows if r["category"].startswith("article_metadata")]
    non_inventory_flagged = []
    for arm in "AB":
        for uid in sorted(delivered_units[arm]):
            if (arm, uid) in inv:
                continue
            d = status(arm, uid)
            if d.substantive != "eligible":
                t = by_a[uid]["text"] if arm == "A" else by_b[uid]["text"]
                non_inventory_flagged.append(
                    {
                        "arm": arm,
                        "internal_unit_id": uid,
                        "substantive_eligibility": d.substantive,
                        "decision": d.decision,
                        "anchored_state": d.anchored.state,
                        "native_nonsubstantive_coverage": round(d.native_nonsubstantive_coverage, 4),
                        "text_head": t[:200],
                    }
                )

    # ---- Independent validation of the frozen outputs ---------------------------------------------------------
    auth = {}
    for arm in "AB":
        for uid, d in decisions[arm].items():
            auth[(namespace[arm], uid)] = d.as_record()
    packets = {
        (arm, cid): {e["source_id"]: e for e in read(QLLD / f"prep/prepared/{arm}/{cid}.evidence.json")["evidence"]}
        for arm in "AB"
        for cid in children
    }
    validation = []
    for arm in "AB":
        for case in children + ["parent"]:
            resp = RUN / f"generations/{arm}/{case}.response.json"
            parsed = parse_output(read(resp)["message"]["content"])
            evidence = (
                packets[(arm, case)]
                if case != "parent"
                else {k: v for c in children for k, v in packets[(arm, c)].items()}
            )
            row = {"arm": arm, "case": case, "parseable": parsed is not None}
            if parsed is not None:
                findings = validate_claims(parsed, evidence, auth)
                row["finding_counts"] = dict(Counter(f["finding"] for f in findings))
                row["findings"] = findings
            validation.append(row)
    totals = Counter()
    for row in validation:
        totals.update(row.get("finding_counts", {}))
    critical = [f for r in validation for f in r.get("findings", []) if f["source_id"] == "S6db56bec1dbc892a85"]

    summary = {
        "policy_version": policy.POLICY_VERSION,
        "thresholds": {
            "NATIVE_COVERAGE_THRESHOLD": policy.NATIVE_COVERAGE_THRESHOLD,
            "ANCHORED_COVERAGE_THRESHOLD": policy.ANCHORED_COVERAGE_THRESHOLD,
            "JOIN_VERIFIED_COVERAGE": policy.JOIN_VERIFIED_COVERAGE,
            "MIN_MATCH_KEY_CHARS": policy.MIN_MATCH_KEY_CHARS,
            "MIN_UNIT_KEY_CHARS": policy.MIN_UNIT_KEY_CHARS,
            "MAX_UNMAPPED_REFERENCE_FRACTION": MAX_UNMAPPED_REFERENCE_FRACTION,
        },
        "native_mapping_audit": audit,
        "as_run_sidecar_reference_mapping": Counter(
            a["mapping_status"] for a in side["actions"] if a["role"] == "exclude_reference"
        ),
        "decision_counts": {arm: dict(Counter(d.decision for d in decisions[arm].values())) for arm in "AB"},
        "anchored_state_counts": {
            arm: dict(Counter(d.anchored.state for d in decisions[arm].values())) for arm in "AB"
        },
        "inventory_bibliography": {
            arm: dict(Counter((r["substantive_eligibility"], r["decision"]).__str__() for r in bib if r["arm"] == arm))
            for arm in "AB"
        },
        "inventory_bibliography_withheld_by_native": sum(r["decision"] == "native_reference_exclusion" for r in bib),
        "inventory_bibliography_native_any_withheld": sum(r["substantive_eligibility"] == "withheld" for r in bib),
        "inventory_bibliography_anchored_bibliographic": sum(
            r["anchored_state"] == "current_bibliographic" for r in bib
        ),
        "inventory_bibliography_still_eligible": [r for r in bib if r["substantive_eligibility"] == "eligible"],
        "inventory_metadata": dict(Counter(r["substantive_eligibility"] for r in meta)),
        "non_inventory_delivered_units_not_eligible": non_inventory_flagged,
        "validation_totals": dict(totals),
        "validation_S6db56bec1dbc892a85": critical,
        "seconds": round(time.time() - started, 1),
    }
    (out / "counterfactual_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    (out / "counterfactual_per_child.json").write_text(json.dumps(per_child, indent=1), encoding="utf-8")
    (out / "inventory_decisions.json").write_text(json.dumps(inv_rows, indent=1), encoding="utf-8")
    (out / "independent_validation.json").write_text(json.dumps(validation, indent=1), encoding="utf-8")
    (out / "native_mapping_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    auth_a = authority_record("legacy_chunk", decisions_a, {"handoff": str(QLLD / "prep/baseline/handoff.json")})
    auth_b = authority_record(
        "guarded_research_unit", decisions_b, {"units": str(GUARD / "corpus/EVIDENCE_UNITS.json")}
    )
    (out / "eligibility_authority_A.json").write_text(json.dumps(auth_a), encoding="utf-8")
    (out / "eligibility_authority_B.json").write_text(json.dumps(auth_b), encoding="utf-8")
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k
                not in (
                    "non_inventory_delivered_units_not_eligible",
                    "inventory_bibliography_still_eligible",
                    "validation_S6db56bec1dbc892a85",
                )
            },
            indent=1,
            default=str,
        )
    )
    print("sha", hashlib.sha256((out / "counterfactual_summary.json").read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
