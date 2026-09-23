"""Pure hard-gate scoring. No I/O, no model calls, no weighted composite.

A model is *qualified* only if every gate passes. A single severe failure is never averaged away;
diagnostic behavior (ambiguous cases) is reported and can neither rescue nor sink a model. Output is
re-validated against the case schema after parsing, so a runtime that fails to enforce an enum shows up
as an invented ID rather than being silently trusted. Duplicate IDs are removed after parsing.
"""

import json
import re

import jsonschema

from experiments.ask_cli_revised.supervisor_eval import schemas

GATES = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8")

# G8: a frozen phrase list for "claimed the corpus/literature lacks evidence because none was surfaced".
# Hits are not auto-failures: each is adjudicated against the frozen definition (an assertion that
# evidence does not exist in the library/corpus/literature, as opposed to that none was surfaced or supplied).
_ABSENCE = [
    re.compile(p, re.I)
    for p in (
        r"\bno\b[^.]{0,80}\b(?:evidence|studies|research|papers|literature)\b[^.]{0,60}"
        r"\b(?:in|within|across)\s+the\s+(?:literature|corpus|library|collection|field|database)\b",
        r"\b(?:does not|doesn't|do not|don't)\s+exist\b",
        r"\bno\s+such\s+(?:evidence|studies|research|papers)\b",
        r"\babsent\s+from\s+the\s+(?:corpus|library|literature|collection|field)\b",
        r"\b(?:library|corpus|literature|collection)\s+(?:contains|has|holds)\s+no\b",
        r"\b(?:library|corpus|literature|collection)\s+(?:lacks|does not contain|doesn't contain)\b",
        r"\bno\s+(?:evidence|studies|research)\s+(?:exists?|is available|are available|was found in)\b",
        r"\bnone\s+exists?\b",
    )
]


def corpus_absence_hits(text):
    return [m.group(0) for pattern in _ABSENCE for m in pattern.finditer(text or "")]


def _strip_think(content):
    if content.lstrip().startswith("<think>") and "</think>" in content:
        head, _, rest = content.partition("</think>")
        return rest.strip(), True
    return content.strip(), False


def _parse(call):
    content, had_think = _strip_think(call.get("content") or "")
    try:
        return json.loads(content), had_think, None
    except json.JSONDecodeError as exc:
        return None, had_think, f"unparseable JSON ({exc.msg})"


def _dedupe(ids):
    seen, dups = [], []
    for i in ids:
        (dups if i in seen else seen).append(i)
    return seen, dups


def _mentioned_ids(spec, obj):
    """Best-effort ids appearing anywhere an id is expected, for G2 (works even on invalid output)."""
    legal, family, bad = spec["legal"], spec["family"], []
    if not isinstance(obj, dict):
        return bad
    if family == "A":
        for i in obj.get("responsive_obligation_ids") or []:
            if i not in legal["obligation_ids"]:
                bad.append(i)
    elif family == "B":
        coverage = obj.get("coverage")
        for ob, entry in coverage.items() if isinstance(coverage, dict) else []:
            if ob not in legal["obligation_ids"]:
                bad.append(ob)
            supports = entry.get("supporting_proposition_ids") if isinstance(entry, dict) else None
            for pid in supports if isinstance(supports, list) else []:
                if pid not in legal["proposition_ids"]:
                    bad.append(pid)
    else:
        plan = obj.get("plan")
        for ob, action in plan.items() if isinstance(plan, dict) else []:
            if ob not in legal["obligation_ids"]:
                bad.append(ob)
            elif action not in legal["actions"][ob]:
                bad.append(action)
    return [b for b in bad if isinstance(b, str)]


def _b_inconsistency(obj):
    problems = []
    for ob, entry in obj["coverage"].items():
        ids = entry["supporting_proposition_ids"]
        if entry["status"] == "unresolved" and ids:
            problems.append(f"{ob} is 'unresolved' but lists support {ids}")
        if entry["status"] == "responsive_support" and not ids:
            problems.append(f"{ob} is 'responsive_support' but lists no proposition")
    return problems


def _observe(spec, call):
    """One call -> its mechanical status and parsed content."""
    out = {
        "case_id": spec["case_id"],
        "mechanical": [],
        "invented": [],
        "obj": None,
        "think_prefix": False,
        "rationale": "",
    }
    if call is None:
        out["mechanical"].append("missing (no call recorded)")
        return out
    if call.get("status") != "ok":
        out["mechanical"].append(f"call status {call.get('status')}: {call.get('error') or 'no detail'}")
        return out
    if call.get("done_reason") != "stop":
        out["mechanical"].append(f"done_reason={call.get('done_reason')} (output not completed)")
    obj, out["think_prefix"], error = _parse(call)
    if error:
        out["mechanical"].append(error)
        return out
    out["invented"] = _mentioned_ids(spec, obj)
    schema_errors = list(jsonschema.Draft202012Validator(schemas.build_schema(spec)).iter_errors(obj))
    if schema_errors:
        out["mechanical"].append(f"schema-invalid: {schema_errors[0].message[:160]}")
    elif spec["family"] == "B":
        out["mechanical"] += [f"inconsistent: {p}" for p in _b_inconsistency(obj)]
    if not out["mechanical"]:
        out["obj"] = obj
    out["rationale"] = (
        obj.get("rationale", "") if isinstance(obj, dict) and isinstance(obj.get("rationale"), str) else ""
    )
    return out


def _judge_a(spec, obs):
    exp = spec["expected"]
    ids, dups = _dedupe(obs["obj"]["responsive_obligation_ids"])
    allowed = set(exp["required"]) | set(exp["diagnostic"])
    extra = [i for i in ids if i not in allowed]
    missing = [i for i in exp["required"] if i not in ids]
    verdict = "diagnostic" if not exp["gated"] else ("pass" if not extra and not missing else "fail")
    reasons = ([f"missing required {missing}"] if missing else []) + ([f"selected forbidden {extra}"] if extra else [])
    return {
        "selected": ids,
        "duplicates": dups,
        "verdict": verdict,
        "reasons": reasons,
        "diagnostic_selected": [i for i in ids if i in exp["diagnostic"]],
    }


def _judge_b(spec, obs):
    exp, cov = spec["expected"], obs["obj"]["coverage"]
    reasons = []
    for ob, pids in exp["required_support"].items():
        for pid in pids:
            if cov[ob]["status"] != "responsive_support" or pid not in cov[ob]["supporting_proposition_ids"]:
                reasons.append(f"{pid} not credited as support for {ob}")
    for ob in exp["must_be_unresolved"]:
        if cov[ob]["status"] != "unresolved" or cov[ob]["supporting_proposition_ids"]:
            reasons.append(f"{ob} was promoted without responsive evidence")
    for pid, obligations in exp["forbidden_attach"].items():
        for ob in obligations:
            if pid in cov[ob]["supporting_proposition_ids"]:
                reasons.append(f"{pid} attached as support for {ob}")
    attached = sorted({pid for e in cov.values() for pid in e["supporting_proposition_ids"]})
    return {
        "verdict": "fail" if reasons else "pass",
        "reasons": reasons,
        "attached": attached,
        "unmapped": [p for p in spec["legal"]["proposition_ids"] if p not in attached],
    }


def _judge_c(spec, obs):
    exp, plan = spec["expected"], obs["obj"]["plan"]
    reasons = []
    for ob, wanted in exp["required_choice"].items():
        if plan[ob] != wanted:
            reasons.append(f"{ob} chose {plan[ob]} (policy requires {wanted})")
    for ob in exp["closure_forbidden"]:
        if plan[ob].split(":")[1] in ("MARK_COVERED", "NO_RECOVERY_NEEDED"):
            reasons.append(f"{ob} was closed without responsive support ({plan[ob]})")
    for ob in exp["repeat_forbidden"]:
        if plan[ob] in exp["performed"]:
            reasons.append(f"{ob} repeated an already-performed action ({plan[ob]})")
    return {"verdict": "fail" if reasons else "pass", "reasons": reasons, "plan": dict(plan)}


def _judge(spec, obs):
    if obs["obj"] is None:
        return {"verdict": "unusable", "reasons": list(obs["mechanical"])}
    return {"A": _judge_a, "B": _judge_b, "C": _judge_c}[spec["family"]](spec, obs)


def _gate(failures):
    return {"status": "FAIL" if failures else "PASS", "detail": failures}


def _role_gate(specs, cases_out, role):
    failures = []
    for spec in specs:
        if spec["family"] == "A" and spec["role"] == role:
            c = cases_out[spec["case_id"]]
            if c["verdict"] != "pass":
                failures.append(f"{spec['case_id']}: " + ("; ".join(c["reasons"]) or c["verdict"]))
    return _gate(failures)


def _order_gate(specs, cases_out):
    failures = []
    for base in sorted({s["base_id"] for s in specs if s["family"] == "A" and s["order_robust"]}):
        rows = [s for s in specs if s["base_id"] == base]
        results = [cases_out[s["case_id"]] for s in rows]
        if any(r["verdict"] == "unusable" for r in results):
            failures.append(f"{base}: an ordering produced no usable observation")
            continue
        sets = {tuple(sorted(r["selected"])) for r in results}
        if len(sets) > 1:
            by_order = {s["ordering"]: sorted(cases_out[s["case_id"]]["selected"]) for s in rows}
            failures.append(f"{base}: selection changed with presentation order {by_order}")
    return _gate(failures)


def _family_gate(specs, cases_out, family):
    failures = []
    for spec in specs:
        if spec["family"] == family:
            c = cases_out[spec["case_id"]]
            if c["verdict"] != "pass":
                failures.append(f"{spec['case_id']}: " + ("; ".join(c["reasons"]) or c["verdict"]))
    return _gate(failures)


def score_model(specs, calls):
    """Score one model's calls (list of records with a `case_id`) against the frozen specs."""
    by_case = {c["case_id"]: c for c in calls}
    observed = {s["case_id"]: _observe(s, by_case.get(s["case_id"])) for s in specs}
    cases_out = {s["case_id"]: _judge(s, observed[s["case_id"]]) for s in specs}

    g1 = _gate([f"{cid}: {reason}" for cid, o in observed.items() for reason in o["mechanical"]])
    g2 = _gate([f"{cid}: invented id {bad!r}" for cid, o in observed.items() for bad in o["invented"]])
    hits = [(cid, h) for cid, o in observed.items() for h in corpus_absence_hits(o["rationale"])]
    g8 = {"status": "NEEDS_ADJUDICATION" if hits else "PASS", "detail": [f"{cid}: {h!r}" for cid, h in hits]}
    gates = {
        "G1": g1,
        "G2": g2,
        "G3": _role_gate(specs, cases_out, "positive"),
        "G4": _role_gate(specs, cases_out, "negative"),
        "G5": _order_gate(specs, cases_out),
        "G6": _family_gate(specs, cases_out, "B"),
        "G7": _family_gate(specs, cases_out, "C"),
        "G8": g8,
    }

    statuses = [g["status"] for g in gates.values()]
    qualified = False if "FAIL" in statuses else (None if "NEEDS_ADJUDICATION" in statuses else True)
    negatives = [cases_out[s["case_id"]] for s in specs if s["family"] == "A" and s["role"] == "negative"]
    for spec in specs:
        cases_out[spec["case_id"]]["think_prefix"] = observed[spec["case_id"]]["think_prefix"]
    return {
        "gates": gates,
        "cases": cases_out,
        "qualified": qualified,
        "diagnostics": {"negative_cases_with_any_selection": sum(1 for c in negatives if c.get("selected"))},
    }
