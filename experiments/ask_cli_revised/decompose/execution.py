"""Execution readiness: whether Ask may run a child's exact wording. A status label is a finding about a wording, never an authorization to run it.

States (checked in this order; the first that applies wins):

* ``runnable_original``: a legitimate pass-through, the researcher's request kept exactly.
* ``not_executable``: the wording cannot be run as it stands (a conflict, an unresolved reading, a constraint failure, an unwritten or
  left-out child). Nothing here is overridden by an approval.
* ``researcher_approved``: a recorded approval names this child AND the SHA-256 of this exact wording (a different string is a different wording).
* ``requires_researcher_approval``: anything the checks or the researcher's own decisions leave to a human: a review, source-gap or pending status, a
  kept human read, a wording that departs from the deterministic preparation, or a wording with nothing to compare it with.
* ``runnable_by_construction``: a clean candidate whose wording IS the deterministic preparation (source words with recorded edits, or a tested
  scaffold with nothing pending), so no composition by the writer is involved.

The writer's exact returned wording is never replaced. When a wording is held because it departs from a defensible deterministic proposal, that
proposal is offered SEPARATELY as ``fallback_proposal`` (labelled as deterministic, not model output, and itself awaiting approval).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.ask_cli_revised.decompose import structure

RUNNABLE_ORIGINAL = "runnable_original"
RUNNABLE_BY_CONSTRUCTION = "runnable_by_construction"
RESEARCHER_APPROVED = "researcher_approved"
REQUIRES_APPROVAL = "requires_researcher_approval"
NOT_EXECUTABLE = "not_executable"
EXECUTABLE = frozenset({RUNNABLE_ORIGINAL, RUNNABLE_BY_CONSTRUCTION, RESEARCHER_APPROVED})
HARD_KINDS = ("fallback", "unit_level", "unresolved_elliptical", "constraint_failure", "not_selected")
HARD_STATUSES = ("semantic_conflict", "output_constraint_failure", "conditional_on_unresolved_reading")
REVIEW_STATUSES = ("semantic_review_required", "source_gap", "pending_researcher_confirmation")
APPROVAL_FIELDS = ("child_id", "wording_sha256", "approved_by", "authorization_quote")
# what an approved wording IS (approval never changes this): a deterministic scaffold stays a deterministic scaffold, and so on
PROVENANCES = ("deterministic_scaffold", "deterministic_preparation", "researcher_supplied", "model_output")


def wording_sha256(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def load_approvals(path: str | Path) -> list[dict]:
    """Researcher approvals of exact wordings: ``{"approvals": [{child_id, wording_sha256, approved_by, authorization_quote, ...}]}``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("approvals") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("approvals file must be an object with an 'approvals' list")
    for row in rows:
        missing = [k for k in APPROVAL_FIELDS if not str(row.get(k) or "").strip()]
        if missing:
            raise ValueError(f"an approval needs {', '.join(APPROVAL_FIELDS)}; missing {missing}")
        if len(str(row["wording_sha256"])) != 64:
            raise ValueError("wording_sha256 must be a SHA-256 hex digest of the exact wording")
        if row.get("wording_provenance") is not None and row["wording_provenance"] not in PROVENANCES:
            raise ValueError(f"wording_provenance must be one of {PROVENANCES}")
        if row.get("wording") is not None and wording_sha256(row["wording"]) != row["wording_sha256"]:
            raise ValueError(f"the recorded wording of {row['child_id']} does not hash to its wording_sha256")
    return rows


def verify_approvals(approvals) -> list[str]:
    """Problems in a set of approvals: a recorded wording that does not hash to its digest, or two approvals of one child (empty = sound)."""
    problems = [
        f"{a['child_id']}: the recorded wording does not hash to its wording_sha256"
        for a in approvals
        if a.get("wording") is not None and wording_sha256(a["wording"]) != a["wording_sha256"]
    ]
    ids = [a["child_id"] for a in approvals]
    problems += [f"{i}: more than one approval" for i in sorted(set(ids)) if ids.count(i) > 1]
    return problems


def readiness(child: dict, *, starting_point: str | None = None, approvals=()) -> dict:
    """The execution state of one child. ``starting_point`` is the deterministic wording to compare an unprepared child with."""
    kind, status = child["kind"], child["status"]
    sha = wording_sha256(child["question"])
    prep = child.get("preparation")
    out = {"state": None, "executable": False, "reasons": [], "wording_sha256": sha, "fallback_proposal": None}
    if kind == "passthrough":
        return {
            **out,
            "state": RUNNABLE_ORIGINAL,
            "executable": True,
            "reasons": ["the original request, kept exactly as written"],
        }
    hard = [f"kind {kind}"] if kind in HARD_KINDS else []
    hard += [f"status {status}"] if status in HARD_STATUSES else []
    if hard:
        return {**out, "state": NOT_EXECUTABLE, "reasons": hard}
    match = next((a for a in approvals if a["child_id"] == child["child_id"] and a["wording_sha256"] == sha), None)
    if match:
        return {
            **out,
            "state": RESEARCHER_APPROVED,
            "executable": True,
            "reasons": ["the researcher approved this exact wording"],
            "approval": {
                k: match.get(k)
                for k in (
                    "child_id",
                    "approval_ref",
                    "wording_provenance",
                    "approved_by",
                    "recorded",
                    "confirms_pending",
                )
                if match.get(k) is not None
            },
            "qualifications": match.get("qualifications", []),
        }
    if kind == "researcher_supplied":
        return {
            **out,
            "state": REQUIRES_APPROVAL,
            "reasons": ["a researcher-supplied wording runs only through a recorded approval of this exact string"],
        }
    reasons: list[str] = []
    if status in REVIEW_STATUSES:
        reasons.append(f"status {status}")
    if child.get("human_review_required"):
        reasons.append("the researcher kept a human read of this child")
    departure = None
    if prep is not None:
        found = structure.findings(child)
        reasons += [f["note"] for f in found]
        departure = next((f for f in found if f["flag"] == "departs_from_prepared_request"), None)
        scaffold = prep.get("scaffold") or {}
        if not found and scaffold.get("built") and scaffold.get("pending"):
            reasons.append("the deterministic scaffold has parts awaiting the researcher's confirmation")
    elif starting_point is not None:
        if structure.normalize(child["question"]) != structure.normalize(starting_point):
            reasons.append("the wording is not the deterministic starting point (the writer edited it)")
    else:
        reasons.append("there is no deterministic starting point to compare the wording with")
    if reasons:
        out.update(state=REQUIRES_APPROVAL, reasons=reasons)
        scaffold = (prep or {}).get("scaffold") or {}
        defensible = scaffold.get("built") or (not (prep or {}).get("carry") and not (prep or {}).get("not_prepared"))
        if departure and defensible:
            out["fallback_proposal"] = {
                "text": prep["prepared_request"],
                "origin": "deterministic preparation, not model output",
                "requires_researcher_approval": True,
                "note": "offered as a separate proposal; the writer's own wording above is unchanged and is not replaced by it",
            }
        return out
    if status == "candidate":
        return {
            **out,
            "state": RUNNABLE_BY_CONSTRUCTION,
            "executable": True,
            "reasons": ["the wording is the deterministic preparation, with no open finding"],
        }
    return {**out, "state": REQUIRES_APPROVAL, "reasons": [f"status {status}"]}


def summarize(children: list[dict]) -> dict:
    """Which children Ask may run as they stand, which wait for the researcher, and which cannot run (by child id; no score, no verdict)."""
    groups: dict[str, list[str]] = {"executable": [], "requires_researcher_approval": [], "not_executable": []}
    for c in children:
        state = (c.get("execution") or readiness(c))["state"]
        key = "executable" if state in EXECUTABLE else state
        groups[key].append(c["child_id"])
    return {
        **groups,
        "all_executable": not groups["requires_researcher_approval"] and not groups["not_executable"],
        "note": "a request is ready for Ask only when every child it decomposes into is executable; nothing here is an answer",
    }
