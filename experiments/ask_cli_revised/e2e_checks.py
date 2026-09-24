"""Mechanical checks and telemetry for a completed E2E run, plus the blinded adjudication-sheet generator.

Everything here reads artifacts already on disk (nothing re-infers), so it is re-runnable offline on any run directory and
cannot change a run. Two failure classes are kept apart on purpose. A *model mechanical failure* (a capped, unparseable or
schema-invalid answer from a reachable model) counts against the arm: it is measured and reported, never retried and never
auto-invalidating. An *infrastructure failure* (provider/transport/HTTP error) says nothing about the model and is a
technical-validity issue for the run. A wall-clock timeout and a refused oversized prompt are reported in their own buckets
rather than guessed into either class. No check here scores a run, and none turns a mechanical failure into a verdict.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path

from experiments.ask_cli_revised import e2e_contracts, stages
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.ledger_renderer import validate_ledger
from experiments.ask_cli_revised.supervisor_eval import cases
from experiments.ask_cli_revised.supervisor_eval.scoring import corpus_absence_hits

WORKER_TASKS = ("context_gate", "select_evidence", "form_claim", "recovery_query")
SUPERVISOR_TASKS = ("claim_responsiveness", "coverage_audit", "recovery_planning")
_INFRASTRUCTURE_STATUSES = frozenset({"http_error", "runtime_error", "transport_error", "provider_error"})
_SEARCH_ACTIONS = frozenset({"DEEPEN", "NOMINATE", "LEGACY"})
_PLAN_ACTIONS = _SEARCH_ACTIONS | {"NO_RECOVERY_NEEDED", "PRESERVE_UNRESOLVED"}
_SCOPE_SENTENCE = "makes no statement about what the library or the literature holds"
_INCOMPLETE_HEADING = "Completeness remains unresolved"


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---- NO ANSWER accounting ----------------------------------------------------------------------------------------------


def classify_call(record: dict) -> tuple[str, str]:
    """``(class, reason)``: usable | model | infrastructure | timeout | prompt_too_large."""
    if record.get("validation_ok"):
        return "usable", "usable"
    reason = record.get("failure_reason")
    status = record.get("status")
    if reason == "prompt_too_large":
        return "prompt_too_large", "prompt_too_large"
    if status == "timeout":
        return "timeout", "timeout"
    if status in _INFRASTRUCTURE_STATUSES or (isinstance(reason, str) and reason.startswith("provider_error")):
        return "infrastructure", reason or status
    return "model", reason or "invalid_output"


def _empty_counts() -> dict:
    return {
        "calls": 0,
        "usable": 0,
        "model": 0,
        "infrastructure": 0,
        "timeout": 0,
        "prompt_too_large": 0,
        "reasons": {},
    }


def no_answer_table(rows: list[dict], *, worker_model: str | None) -> dict:
    """NO ANSWER counts by task and model, the gate's measured rate, and the count of infrastructure failures."""
    by_task: dict[str, dict[str, dict]] = {}
    for row in rows:
        task = row.get("task") or row.get("stage") or "unknown"
        model = row.get("model") or (worker_model if task in WORKER_TASKS else None) or "unknown"
        counts = by_task.setdefault(task, {}).setdefault(model, _empty_counts())
        kind, reason = classify_call(row)
        counts["calls"] += 1
        counts[kind] += 1
        if kind != "usable":
            counts["reasons"][reason] = counts["reasons"].get(reason, 0) + 1
    gate_calls = sum(c["calls"] for c in by_task.get("context_gate", {}).values())
    gate_bad = sum(c["calls"] - c["usable"] for c in by_task.get("context_gate", {}).values())
    infra = sum(c["infrastructure"] for models in by_task.values() for c in models.values())
    return {
        "by_task": by_task,
        "gate": {"calls": gate_calls, "no_answer": gate_bad, "rate": (gate_bad / gate_calls) if gate_calls else None},
        "infrastructure_failures": infra,
    }


# ---- frozen-label reuse ------------------------------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).rstrip(".").casefold()


def _frozen_labels() -> dict[str, dict]:
    """Cliff's expected judgments on the AIB claims, keyed by normalized claim text (Task A battery + Task B expectations)."""
    ids = list(cases.OBLIGATION_IDS)
    labels: dict[str, dict] = {}
    for base in cases._A_BASES:
        allowed = set(base["required"]) | set(base["diagnostic"])
        labels[_normalize(base["claim"])] = {
            "frozen_id": base["base_id"],
            "required": list(base["required"]),
            "diagnostic": list(base["diagnostic"]),
            "forbidden": [i for i in ids if i not in allowed],
        }
    expected = cases._B_EXPECTED
    for prop in cases.PROPOSITIONS:
        entry = labels.setdefault(
            _normalize(prop["claim"]),
            {"frozen_id": prop["proposition_id"], "required": [], "diagnostic": [], "forbidden": []},
        )
        entry["forbidden"] = sorted(
            set(entry["forbidden"]) | set(expected["forbidden_attach"].get(prop["proposition_id"], []))
        )
        for ob, pids in expected["required_support"].items():
            if prop["proposition_id"] in pids and ob not in entry["required"]:
                entry["required"].append(ob)
    return labels


def frozen_label_reuse(ledger: dict, question_key: str) -> dict:
    """Ledger claims that match a frozen AIB claim inherit its expected judgment; everything else is unlabelled."""
    rows = ledger["verified_propositions"]
    responsive = [r["proposition_id"] for r in rows if r.get("responsive_obligation_ids")]
    if question_key != "aib":
        return {
            "applicable": False,
            "matched": [],
            "violations": [],
            "missing_required": [],
            "unlabelled_responsive": responsive,
        }
    labels = _frozen_labels()
    matched, violations, missing, labelled = [], [], [], set()
    for row in rows:
        label = labels.get(_normalize(row["proposition_text"]))
        if label is None:
            continue
        labelled.add(row["proposition_id"])
        attached = list(row.get("responsive_obligation_ids", []))
        matched.append({"proposition_id": row["proposition_id"], "frozen_id": label["frozen_id"], "attached": attached})
        violations += [
            {"proposition_id": row["proposition_id"], "frozen_id": label["frozen_id"], "obligation_id": ob}
            for ob in attached
            if ob in label["forbidden"]
        ]
        missing += [
            {"proposition_id": row["proposition_id"], "frozen_id": label["frozen_id"], "obligation_id": ob}
            for ob in label["required"]
            if ob not in attached
        ]
    return {
        "applicable": True,
        "matched": matched,
        "violations": violations,
        "missing_required": missing,
        "unlabelled_responsive": [pid for pid in responsive if pid not in labelled],
    }


# ---- the run-directory report ------------------------------------------------------------------------------------------


def _check(ok: bool, **detail) -> dict:
    return {"ok": bool(ok), **detail}


def _plan_legal(plan_record: dict, ledger_ids: set[str], obligation_ids: list[str]) -> dict:
    problems = []
    for ob, action in plan_record.get("plan", {}).items():
        if ob not in obligation_ids:
            problems.append(f"{ob}: not a requested item")
        elif action in _PLAN_ACTIONS:
            continue
        elif action.startswith("MARK_COVERED:") and action.split(":", 1)[1] in ledger_ids:
            continue
        else:
            problems.append(f"{ob}: illegal action {action!r}")
    return _check(not problems, problems=problems, state=plan_record.get("state"))


def _coverage_from_authority(coverage: dict, ledger_rows: list[dict], profile: topo.Profile | None) -> dict:
    """A det arm's states must be exactly R's mappings; a model arm's come from C alone (nothing here can recompute them)."""
    if profile is not None and profile.C.kind != "det":
        return _check(True, basis="model_authority")
    if not coverage.get("assessed", True):
        return _check(True, basis="not_assessed")
    mapped: dict[str, list[str]] = {}
    for row in ledger_rows:
        for ob in row.get("obligation_ids", []):
            mapped.setdefault(ob, []).append(row["proposition_id"])
    problems = []
    for entry in coverage["obligations"]:
        expected = mapped.get(entry["field_id"], [])
        if sorted(entry["proposition_ids"]) != sorted(expected):
            problems.append(f"{entry['field_id']}: states {entry['proposition_ids']} but R mapped {expected}")
    return _check(not problems, basis="det_mappings", problems=problems)


def _recovery_accounting(rows: list[dict]) -> dict:
    by_action: dict[str, dict] = {}
    reasons: dict[str, int] = {}
    for row in rows:
        action = row.get("action")
        entry = by_action.setdefault(str(action), {"gaps": 0, "new_verified": 0})
        entry["gaps"] += 1
        entry["new_verified"] += row.get("new_verified") or 0
        if row.get("reason_code"):
            reasons[row["reason_code"]] = reasons.get(row["reason_code"], 0) + 1
    return {
        "rows": len(rows),
        "by_action": by_action,
        "reason_codes": reasons,
        "recovery_query_no_answer": reasons.get("recovery_query_no_answer", 0),
        "plan_no_search": reasons.get("plan_no_search", 0),
    }


def mechanical_report(run_dir, *, profile: topo.Profile | None = None, question_key: str | None = None) -> dict:
    run = Path(run_dir)
    ledger = _read_json(run / "11_verified_ledger.json")
    render_manifest = _read_json(run / "14_render_manifest.json")
    coverage_final = _read_json(run / "12_coverage_audit.json")
    coverage_initial = _read_json(run / "12_coverage_audit.initial.json")
    plan_record = _read_json(run / "13_recovery_plan.json")
    recovery_rows = _read_json(run / "13_gap_recovery.json")
    stage_log = _read_json(run / "stage_log.json")
    answer = (run / "14_final_answer.md").read_text(encoding="utf-8")
    calls = _read_jsonl(run / "qwen_calls.jsonl")
    growth = _read_jsonl(run / "07_context_growth.jsonl")

    contract = ledger["request_contract"]
    frozen = e2e_contracts.frozen_record(contract["original_question"])
    frozen_ids = [o["field_id"] for o in frozen["obligations"]]
    state_ids = [s["field_id"] for s in ledger["obligation_states"]]
    contract_ok = (
        contract["question_hash"] == frozen["question_hash"]
        and len(contract["source_units"]) == frozen["n_units"]
        and state_ids == frozen_ids
    )
    if question_key is not None:
        recorded = _read_json(e2e_contracts.FROZEN_PATH)["questions"].get(question_key, {})
        contract_ok = contract_ok and recorded.get("model_facing_sha256") == frozen["model_facing_sha256"]

    try:
        validate_ledger(ledger)
        ledger_ok, ledger_error = True, None
    except Exception as exc:  # noqa: BLE001 - any validation failure is a failed check, reported verbatim
        ledger_ok, ledger_error = False, str(exc)

    ledger_rows = ledger["verified_propositions"]
    ledger_ids = {r["proposition_id"] for r in ledger_rows}
    by_id = {r["proposition_id"]: r for r in ledger_rows}
    from experiments.ask_cli_revised.ledger_renderer import audit_final

    audit = audit_final(ledger, answer)
    rendered = [pid for claim in render_manifest.get("claims", []) for pid in claim["proposition_ids"]]
    unsupported = [
        pid for pid in rendered if pid not in by_id or by_id[pid].get("verification", {}).get("status") != "verified"
    ]
    scope_ok = True
    if render_manifest.get("mode") == "responsive-ledger-v1":
        scope_ok = _SCOPE_SENTENCE in answer and _INCOMPLETE_HEADING in answer

    worker_model = profile.W.model if profile is not None else None
    table = no_answer_table(calls, worker_model=worker_model)
    executed = {entry["stage"] for entry in stage_log["stages"]}
    inconsistent = int(coverage_initial.get("outcome") == stages.INCONSISTENT)
    if "C2" in executed:
        inconsistent += int(coverage_final.get("outcome") == stages.INCONSISTENT)
    table["inconsistent_coverage_answers"] = inconsistent
    table["gate"]["packets_excluded_no_answer"] = sum(
        1 for row in growth if row.get("discard_reason") == "gate_no_answer"
    )

    absence = corpus_absence_hits(answer)
    labels = frozen_label_reuse(ledger, question_key) if question_key is not None else None
    checks = {
        "contract_preserved": _check(contract_ok),
        "ledger_valid": _check(ledger_ok, error=ledger_error),
        "final_conformant": _check(
            audit["constrained_render_match"] and not audit["nonexistent_ids"], nonexistent_ids=audit["nonexistent_ids"]
        ),
        "unsupported_final_claims": _check(not unsupported, count=len(unsupported), proposition_ids=unsupported),
        "scope_statement": _check(scope_ok),
        "plan_legal": _plan_legal(plan_record, ledger_ids, state_ids),
        "coverage_from_authority": _coverage_from_authority(coverage_final, ledger_rows, profile),
        "corpus_absence": _check(not absence, hits=absence),
    }
    issues = []
    if table["infrastructure_failures"]:
        issues.append(f"infrastructure_failures: {table['infrastructure_failures']} call(s)")
    return {
        "checks": checks,
        "no_answer": table,
        "recovery": _recovery_accounting(recovery_rows),
        "frozen_labels": labels,
        "technical_validity": {"valid": not issues, "issues": issues},
    }


# ---- blinded adjudication ----------------------------------------------------------------------------------------------

_SHEET_HEADER = (
    "# Adjudication sheet\n\n"
    "For each item, read the request item and the claim with its source quote, and judge whether the claim **directly "
    "answers that request item**: Yes, Partly, or No. Judge the claim against the item only; the order of items carries "
    "no meaning.\n"
)


def build_adjudication_sheet(runs: dict[str, dict], question_key: str, out_dir, *, salt: str | None = None):
    """One blinded sheet of the attachments to judge, and a separate key that restores which arm asserted what.

    Only claims an arm *judged responsive* are asked about, and on AIB only those with no frozen label (the frozen labels
    already decide the rest). Identical (claim, item) pairs asserted by several arms appear once. Ids are opaque, items are
    ordered by id, and the sheet carries no arm, proposition id or model name.
    """
    salt = salt or secrets.token_hex(8)
    labels = _frozen_labels() if question_key == "aib" else {}
    items: dict[str, dict] = {}
    for arm, sealed in runs.items():
        display = {s["field_id"]: s.get("display") or s.get("note") for s in sealed["obligation_states"]}
        for row in sealed["verified_propositions"]:
            if _normalize(row["proposition_text"]) in labels:
                continue
            for ob in row.get("responsive_obligation_ids", []):
                digest = hashlib.sha256(f"{salt}|{_normalize(row['proposition_text'])}|{ob}".encode()).hexdigest()[:8]
                item = items.setdefault(
                    digest,
                    {
                        "claim": row["proposition_text"],
                        "quote": row.get("quote", ""),
                        "obligation_id": ob,
                        "request_item": display.get(ob, ob),
                        "attachments": [],
                    },
                )
                item["attachments"].append({"arm": arm, "proposition_id": row["proposition_id"]})
    lines = [_SHEET_HEADER]
    for item_id in sorted(items):
        item = items[item_id]
        lines += [
            f"## Item {item_id}",
            "",
            f"**Request item:** {item['request_item']}",
            "",
            f"**Claim:** {item['claim']}",
            "",
            f"**Source quote:** {item['quote']}",
            "",
            "**Judgment (Yes / Partly / No):** ",
            "",
        ]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sheet_path = out / f"adjudication_{question_key}.md"
    key_path = out / f"adjudication_{question_key}.key.json"
    sheet_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    key_path.write_text(
        json.dumps({"salt": salt, "question_key": question_key, "items": items}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return sheet_path, key_path
