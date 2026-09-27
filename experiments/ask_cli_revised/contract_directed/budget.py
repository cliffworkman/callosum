"""Explicit, enforceable worst-case budgets, and the authorization file that gates every live stage.

The budget is EXPERIMENTAL CONTROL, not latency tuning: per-child x per-paper triage, neighborhood localization and cross-child
eligibility multiply, so every cap is a number here, the worst-case call count is COMPUTED from those numbers, and a live run
refuses to start unless an authorization file (a plain-English brief confirmed by Cliff) carries ceilings at or above them.
Overflow is recorded (`capped_out`, `budget_capped`, `not_checked_budget`, `not_run_budget`), never silently dropped.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import freeze


class AuthorizationRefused(RuntimeError):
    """A live stage was started without an authorization that covers exactly this run."""


@dataclass(frozen=True)
class Caps:
    triage_papers: int = 25  # T: nominated papers triaged per child (baseline nomination cap)
    inspected_papers: int = 6  # I
    neighborhoods: int = 18  # N = I x (1 abstract page + at most 2 content units)
    recovery_neighborhoods: int = 6  # R: one bounded recovery pass, only for children with an unresolved unit
    bridge_neighborhoods: int = 3  # B: only if the conditional bridge triggers
    propositions_per_neighborhood: int = 3
    neighborhood_chars: int = 9000
    eligibility_packets: int = 40  # P_max unique packets checked against every child in the run

    def as_dict(self) -> dict:
        return asdict(self)


PILOT_CHILDREN = ("c5", "c6", "c9", "c10", "c11")
PILOT_CAPS = Caps(eligibility_packets=40)
FULL_CAPS = Caps(eligibility_packets=60)
PILOT_CEILINGS = {"max_calls": 500, "wall_seconds": 120 * 60}
FULL_CEILINGS = {"max_calls": 1300, "wall_seconds": 300 * 60}


def worst_case(children: int, caps: Caps, *, include_conditional: bool = True) -> dict:
    """Worst-case model calls per stage for a run over `children` children (deterministic stages cost no calls)."""
    triage = children * caps.triage_papers
    localization = children * (
        caps.neighborhoods + caps.recovery_neighborhoods + (caps.bridge_neighborhoods if include_conditional else 0)
    )
    eligibility = caps.eligibility_packets * children
    answers = children
    total = triage + localization + eligibility + answers
    return {
        "children": children,
        "triage": triage,
        "localization": localization,
        "eligibility": eligibility,
        "answers": answers,
        "worst_case_total_calls": total,
        "characters_inspected_per_child_max": (
            caps.neighborhoods + caps.recovery_neighborhoods + caps.bridge_neighborhoods
        )
        * caps.neighborhood_chars,
        "packets_possible_before_cap": localization * caps.propositions_per_neighborhood,
        "note": "packets beyond eligibility_packets are recorded not_checked_budget in a fixed priority order, never dropped silently",
    }


def run_budget(children: list[str], caps: Caps, ceilings: dict) -> dict:
    wc = worst_case(len(children), caps)
    return {
        "children": list(children),
        "caps": caps.as_dict(),
        "worst_case": wc,
        "ceilings": dict(ceilings),
        "within_ceilings": wc["worst_case_total_calls"] <= ceilings["max_calls"],
    }


def authorization_template(experiment_id: str, budget: dict, question_sha256: str = freeze.QUESTION_SHA256) -> dict:
    """The file Cliff signs. `brief_confirmed` is False until he states he has read the brief for THIS experiment."""
    return {
        "experiment_id": experiment_id,
        "question_sha256s": [question_sha256],
        "children": budget["children"],
        "caps": budget["caps"],
        "ceilings": budget["ceilings"],
        "authorized_by": None,
        "authorized_at": None,
        "brief_confirmed": False,
    }


def check_authorization(
    path: Path | str, budget: dict, *, experiment_id: str, question_sha256: str = freeze.QUESTION_SHA256
) -> dict:
    """Refuse unless the file names this experiment, this question, these children, brief_confirmed true, and covers the budget."""
    file = Path(path)
    if not file.is_file():
        raise AuthorizationRefused("no authorization file")
    auth = json.loads(file.read_text(encoding="utf-8"))
    problems = []
    if auth.get("brief_confirmed") is not True:
        problems.append("brief_confirmed is not true")
    if not auth.get("authorized_by") or not auth.get("authorized_at"):
        problems.append("authorized_by / authorized_at missing")
    if auth.get("experiment_id") != experiment_id:
        problems.append(f"experiment_id {auth.get('experiment_id')!r} != {experiment_id!r}")
    if question_sha256 not in (auth.get("question_sha256s") or []):
        problems.append("question hash not named")
    if not set(budget["children"]) <= set(auth.get("children") or []):
        problems.append("children exceed those authorized")
    for key, value in budget["caps"].items():
        if auth.get("caps", {}).get(key, -1) < value:
            problems.append(f"cap {key}={value} exceeds authorized {auth.get('caps', {}).get(key)}")
    for key, value in budget["ceilings"].items():
        if auth.get("ceilings", {}).get(key, -1) < value:
            problems.append(f"ceiling {key}={value} exceeds authorized {auth.get('ceilings', {}).get(key)}")
    if problems:
        raise AuthorizationRefused("; ".join(problems))
    return auth
