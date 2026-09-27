"""The sequencing core: frozen contracts -> child answers, with an append-only receipt per stage.

Order (per run): S1 nominate -> S2 triage -> S3 obligation/section-directed anchors and neighborhoods -> S4 localization ->
S5 packets -> S6 cross-child eligibility -> S7 coverage -> S8 ONE recovery pass -> conditional bridge -> S9 raw answers ->
diagnostics. Deterministic stages need no model; model stages take an `Env` (a fake in tests, the isolated Ollama live).
A mechanical failure is NO ANSWER and stays distinct from "nothing relevant"; a ceiling stops the run and what did not run is
recorded `not_run_budget`. Nothing here reads or writes the library (it is opened read-only) and nothing gates an answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import (
    abstracts,
    anchors,
    bridge,
    budget,
    coverage,
    diagnostics,
    nominate,
    recovery,
)
from experiments.ask_cli_revised.contract_directed import (
    model_stages as ms,
)
from experiments.ask_cli_revised.contract_directed import (
    packet as packet_mod,
)
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract, FrozenSubstrate
from experiments.ask_cli_revised.contract_directed.retriever import Retriever
from experiments.ask_cli_revised.contract_directed.store import Library


@dataclass
class Run:
    run_dir: Path
    library: Library
    retriever: Retriever
    substrate: FrozenSubstrate
    caps: budget.Caps
    env: ms.Env | None = None
    trace: object | None = None
    axis_cache: dict = field(default_factory=dict)

    def write_json(self, name: str, payload) -> None:
        (self.run_dir / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
        )

    def append_jsonl(self, name: str, row) -> None:
        with (self.run_dir / name).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


# ---- deterministic front half (S1, S3) -------------------------------------------------------------------------------------


def nominate_child(run: Run, child: ChildContract) -> dict:
    nom = nominate.nominate(child, run.library, run.retriever, axis_cache=run.axis_cache, cap=run.caps.triage_papers)
    for row in nom["nominations"] + nom["capped_out"]:
        run.append_jsonl("01_nominations.jsonl", row)
    return nom


def inspect_and_neighborhoods(run: Run, child: ChildContract, nom: dict, triage: dict[int, dict] | None = None) -> dict:
    """S3: which papers are read, which of their chunks, and the neighborhoods that fit the budget (rest = budget_capped)."""
    order = nominate.inspect_order(nom["nominations"], run.library, triage, cap=run.caps.inspected_papers)
    per_paper, anchor_sets = [], []
    for paper_id in order["inspect"]:
        quote = (triage or {}).get(paper_id, {}).get("abstract_quote") or None
        aset = anchors.select_anchors(child, paper_id, run.library, run.retriever, abstract_quote=quote)
        anchor_sets.append(aset)
        run.append_jsonl(
            "04_anchors.jsonl",
            {
                "child_id": child.child_id,
                "paper_id": paper_id,
                "attachment": aset["attachment"],
                "anchors": aset["anchors"],
                "skipped": aset["skipped"],
                "abstract_page_chunk": aset.get("abstract_page_chunk"),
            },
        )
        per_paper.append(anchors.neighborhoods_for(aset, run.library))
    selection = anchors.select_neighborhoods(per_paper, child, cap=run.caps.neighborhoods)
    for state, group in (("read", selection["read"]), ("budget_capped", selection["budget_capped"])):
        for nb in group:
            run.append_jsonl(
                "05_neighborhoods.jsonl", {"child_id": child.child_id, "state": state, **{k: v for k, v in nb.items()}}
            )
    return {
        "order": order,
        "read": selection["read"],
        "budget_capped": selection["budget_capped"],
        "anchor_sets": anchor_sets,
    }


# ---- model stages --------------------------------------------------------------------------------------------------------------


def triage_child(run: Run, child: ChildContract, nom: dict) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for row in nom["nominations"]:
        paper = run.library.paper(row["paper_id"])
        if paper is None:
            continue
        try:
            record = ms.triage_paper(run.env, child, paper)
        except ms.BudgetExceeded as exc:
            record = {
                "child_id": child.child_id,
                "paper_id": row["paper_id"],
                "state": "not_run_budget",
                "outcome": str(exc),
            }
        out[row["paper_id"]] = record
        run.append_jsonl("02_triage.jsonl", record)
    return out


def localize_all(run: Run, child: ChildContract, neighborhoods: list[dict]) -> dict:
    packets, records, not_run = [], [], []
    for nb in neighborhoods:
        try:
            record = ms.localize_neighborhood(run.env, child, nb, run.library)
        except ms.BudgetExceeded as exc:
            not_run.append({"nbhd_id": nb["nbhd_id"], "state": "not_run_budget", "outcome": str(exc)})
            continue
        for p in record.get("packets", []):
            packets.append(p)
        slim = {k: v for k, v in record.items() if k != "packets"}
        slim["packet_ids"] = [p["packet_id"] for p in record.get("packets", [])]
        records.append(slim)
        run.append_jsonl("06_localization.jsonl", slim)
        for p in record.get("packets", []):
            run.append_jsonl("07_packets.jsonl", p)
        for p in record.get("unresolved_preserved", []):
            run.append_jsonl("07_packets.jsonl", p)
    return {"packets": packets, "records": records, "not_run": not_run}


def eligibility_priority(packet: dict) -> tuple:
    """Fixed order for spending the eligibility budget: found under more children, higher neighborhood score, then ids."""
    return (-len(packet["found_under"]), -packet.get("nbhd_score", 0.0), packet["paper_id"], packet["packet_id"])


def judge_pairs(run: Run, children: list[ChildContract], packets: list[dict], *, spent_packets: set[str]) -> dict:
    """Cross-child eligibility: every packet against every child (route irrelevant), within the unique-packet cap."""
    merged = packet_mod.merge_duplicates(packets)
    ordered = sorted((p for p in merged if p["packet_id"] not in spent_packets), key=eligibility_priority)
    room = max(0, run.caps.eligibility_packets - len(spent_packets))
    chosen, over = ordered[:room], ordered[room:]
    records: dict[str, list[dict]] = {c.child_id: [] for c in children}
    not_run: list[dict] = []
    for packet in chosen:
        spent_packets.add(packet["packet_id"])
        for child in children:
            try:
                record = ms.judge_packet(run.env, child, packet)
            except ms.BudgetExceeded as exc:
                not_run.append(
                    {
                        "packet_id": packet["packet_id"],
                        "child_id": child.child_id,
                        "state": "not_run_budget",
                        "outcome": str(exc),
                    }
                )
                continue
            records[child.child_id].append(record)
            run.append_jsonl("08_eligibility.jsonl", record)
    for packet in over:
        row = {
            "packet_id": packet["packet_id"],
            "state": "not_checked_budget",
            "reason": "unique-packet cap for eligibility reached",
            "found_under": packet["found_under"],
        }
        not_run.append(row)
        run.append_jsonl("08_eligibility.jsonl", row)
    return {"records": records, "not_run": not_run, "packets": {p["packet_id"]: p for p in merged}}


def search_summary(
    nom: dict,
    plan: dict,
    loc_records: list[dict],
    loc_not_run: list[dict],
    elig_not_run: list[dict],
    child_id: str,
    *,
    recovery_run: bool,
) -> dict:
    mech = sum(1 for r in loc_records if r.get("state") == "no_answer")
    return {
        "papers_nominated": len(nom["nominations"]),
        "papers_capped_out_of_nomination": len(nom["capped_out"]),
        "papers_inspected": len(plan["order"]["inspect"]),
        "papers_deferred": len(plan["order"]["deferred"]),
        "not_inspectable_no_chunks": len(plan["order"]["not_inspectable_no_chunks"]),
        "neighborhoods_read": len(plan["read"]),
        "none_established": sum(1 for r in loc_records if r.get("state") == "none_established"),
        "budget_capped": len(plan["budget_capped"]) if not recovery_run else 0,
        "not_run_budget": len(loc_not_run) + sum(1 for r in elig_not_run if r.get("child_id") in (None, child_id)),
        "no_answer_calls": mech,
        "recovery_run": recovery_run,
    }


# ---- the run ----------------------------------------------------------------------------------------------------------------------


def run_children(run: Run, child_ids: list[str]) -> dict:
    """Execute every stage for the given children. Returns a summary; every stage's receipt is on disk."""
    children = [run.substrate.child(c) for c in child_ids]
    stage_status: dict = {"children": child_ids, "halted": None}
    plans: dict[str, dict] = {}
    noms: dict[str, dict] = {}
    all_packets: list[dict] = []
    loc_by_child: dict[str, dict] = {}
    try:
        for child in children:
            noms[child.child_id] = nominate_child(run, child)
            triage = triage_child(run, child, noms[child.child_id])
            plans[child.child_id] = inspect_and_neighborhoods(run, child, noms[child.child_id], triage)
            loc_by_child[child.child_id] = localize_all(run, child, plans[child.child_id]["read"])
            all_packets += loc_by_child[child.child_id]["packets"]
        spent: set[str] = set()
        judged = judge_pairs(run, children, all_packets, spent_packets=spent)
        packets_by_id = dict(judged["packets"])
        elig = judged["records"]
        elig_not_run = judged["not_run"]

        rows_by_child: dict[str, list[dict]] = {}
        recovery_log: list[dict] = []
        for child in children:
            summary = search_summary(
                noms[child.child_id],
                plans[child.child_id],
                loc_by_child[child.child_id]["records"],
                loc_by_child[child.child_id]["not_run"],
                elig_not_run,
                child.child_id,
                recovery_run=False,
            )
            rows_by_child[child.child_id] = coverage.coverage_rows(child, elig[child.child_id], search=summary)
        # S8: one bounded recovery pass per child with an unresolved unit
        recovered_packets: list[dict] = []
        for child in children:
            plan = plans[child.child_id]
            actions = recovery.plan_recovery(
                child,
                rows_by_child[child.child_id],
                read=plan["read"],
                capped=plan["budget_capped"],
                inspected=plan["order"]["inspect"],
                deferred=plan["order"]["deferred"],
                packets_by_id=packets_by_id,
                library=run.library,
                retriever=run.retriever,
                cap=run.caps.recovery_neighborhoods,
            )
            for action in actions:
                run.append_jsonl(
                    "10_recovery.jsonl",
                    {k: v for k, v in action.items() if k != "nbhd"}
                    | {
                        "nbhd_id": action["nbhd"]["nbhd_id"],
                        "chunk_ids": action["nbhd"]["chunk_ids"],
                        "attachment": action["nbhd"].get("attachment"),
                    },
                )
            recovery_log += actions
            got = localize_all(run, child, [a["nbhd"] for a in actions])
            recovered_packets += got["packets"]
            loc_by_child[child.child_id]["records"] += got["records"]
            loc_by_child[child.child_id]["not_run"] += got["not_run"]
        if recovered_packets:
            second = judge_pairs(run, children, recovered_packets, spent_packets=spent)
            packets_by_id.update(second["packets"])
            for child in children:
                elig[child.child_id] += second["records"][child.child_id]
            elig_not_run += second["not_run"]
            for child in children:
                summary = search_summary(
                    noms[child.child_id],
                    plans[child.child_id],
                    loc_by_child[child.child_id]["records"],
                    loc_by_child[child.child_id]["not_run"],
                    elig_not_run,
                    child.child_id,
                    recovery_run=True,
                )
                rows_by_child[child.child_id] = coverage.coverage_rows(child, elig[child.child_id], search=summary)
        # conditional bridge (only when a unit is still unresolved and an independent seed exists)
        seeds = sorted(
            {
                packets_by_id[pid]["paper_id"]
                for c in children
                for r in rows_by_child[c.child_id]
                if r["row_type"] == "content"
                for pid in r.get("closing_packet_ids", [])
                if pid in packets_by_id
            }
        )
        for child in children:
            trigger = bridge.bridge_trigger(rows_by_child[child.child_id], seeds)
            run.append_jsonl(
                "11_bridge.jsonl",
                {
                    "child_id": child.child_id,
                    "trigger": trigger,
                    "executed": False,
                    "note": "the bridge is built and tested offline; it executes live only if triggered AND separately authorized",
                },
            )

        run.write_json("09_coverage.json", rows_by_child)
        run.write_json("13_assignment_matrix.json", coverage.assignment_matrix([c.child_id for c in children], elig))
        overlap = packet_mod.overlapping_spans(list(packets_by_id.values()))
        run.write_json("13b_span_overlap.json", overlap)

        # S9: raw answers, saved before any diagnostic runs
        answers_dir = run.run_dir / "12_answers"
        answers_dir.mkdir(exist_ok=True)
        for child in children:
            given = coverage.child_evidence(child, packets_by_id, elig[child.child_id])
            record = ms.answer_child(run.env, child, given)
            (answers_dir / f"{child.child_id}_raw_answer.txt").write_text(record["raw_answer"], encoding="utf-8")
            packet_texts = {
                shown: " ".join(p["text"] for p in packets_by_id[pid]["parts"])
                for shown, pid in record["id_map"].items()
            }
            diag = diagnostics.answer_diagnostics(
                record["raw_answer"], prompt=record["prompt"], id_map=record["id_map"], packet_texts=packet_texts,
                parent_question=run.substrate.contract["original_question"],
                other_wordings=[c.wording for c in run.substrate.children if c.child_id != child.child_id],
                carried_scope=child.scope_carrier_wording,
            )  # fmt: skip
            (answers_dir / f"{child.child_id}_record.json").write_text(
                json.dumps(
                    {**{k: v for k, v in record.items() if k != "raw_answer"}, "diagnostics": diag},
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
    except ms.StageHalt as exc:
        stage_status["halted"] = str(exc)
    except ms.BudgetExceeded as exc:
        stage_status["halted"] = f"budget: {exc}"
    finally:
        run.write_json("14_ledger.json", run.env.ledger.summary() if run.env else {})
    stage_status["ledger"] = run.env.ledger.summary() if run.env else {}
    return stage_status


def deterministic_dry_run(run: Run, child_ids: list[str]) -> dict:
    """The offline half for Gate 1 receipts: nominations, inspection order, anchors and read/capped neighborhoods with seam states."""
    summary = {}
    for cid in child_ids:
        child = run.substrate.child(cid)
        nom = nominate_child(run, child)
        plan = inspect_and_neighborhoods(run, child, nom, triage=None)
        seams = []
        for nb in plan["read"]:
            unit_list, _ = packet_mod.neighborhood_units(nb, run.library)
            seams.append(
                {
                    "nbhd_id": nb["nbhd_id"],
                    "paper_id": nb["paper_id"],
                    "units": len(unit_list),
                    "verified_joins": sum(1 for u in unit_list if u.join == "verified_seam"),
                    "open_fragments": sum(1 for u in unit_list if u.open_left or u.open_right),
                }
            )
        for row in seams:
            run.append_jsonl("05b_seam_states.jsonl", {"child_id": cid, **row})
        summary[cid] = {
            "nominated": len(nom["nominations"]), "capped_out": len(nom["capped_out"]), "inspect": plan["order"]["inspect"],
            "deferred": plan["order"]["deferred"], "not_inspectable_no_chunks": plan["order"]["not_inspectable_no_chunks"],
            "neighborhoods_read": len(plan["read"]), "budget_capped": len(plan["budget_capped"]),
            "chars_in_read_neighborhoods": sum(nb["char_len"] for nb in plan["read"]),
            "verified_joins": sum(r["verified_joins"] for r in seams), "open_fragments": sum(r["open_fragments"] for r in seams),
        }  # fmt: skip
    return summary


assert abstracts  # imported for its side-effect-free helpers used by callers of this module
