"""Materializes sufficiency_authoring's q_aib SufficiencyContract to disk as an UNREVIEWED_
CANDIDATE frozen pin, mirroring hierarchy_contract.py's own FROZEN_PATH convention (a sibling
JSON file next to the authoring module, named by question_key). Never writes a `.review.json` --
that file records an explicit human review and only Cliff can author it truthfully; see
hierarchy_contract.py's own review gate for the precedent this defers to.

``load_verified`` (Phase 20a) is the reader half of that same precedent: it is the one place a
real hierarchy run sources its ``{child_id: SufficiencyContract}`` input, verified against both
the frozen artifact's own per-child/combined hashes and a recorded human review naming that exact
``combined_hash`` -- never by re-running ``sufficiency_authoring.build_qaib_contract`` at runtime
and hoping it still matches (CLAUDE.md's own standing rule for this subsystem: the frozen artifact
is authoritative, re-authoring is not a substitute for loading it).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_authoring as sa
from experiments.ask_cli_revised import sufficiency_engine as se

FROZEN_PATH = Path(__file__).with_name(f"sufficiency_contract.{sa.QUESTION_KEY}.frozen.json")
REVIEW_PATH = Path(__file__).with_name(f"sufficiency_contract.{sa.QUESTION_KEY}.review.json")


class SufficiencyContractRejected(RuntimeError):
    """A frozen sufficiency-contract artifact failed integrity or review verification. Mirrors
    ``hierarchy_contract.HierarchyRejected``'s fail-closed convention (same base class, same
    ``problems`` shape) for the sibling frozen-contract artifact this module owns; carries every
    problem found, never just the first."""

    def __init__(self, problems):
        self.problems = [str(p) for p in problems]
        super().__init__(f"sufficiency contract rejected: {'; '.join(self.problems)}")


_DEFAULT_REQUEST_CONTRACT = (
    Path(__file__).resolve().parents[2]
    / ".local"
    / "e2e-runs"
    / "q-aib-hierarchical-t5c-live-20260930"
    / "run"
    / "01_request_contract.json"
)


def _load_children_by_id(request_contract_path: Path) -> dict:
    data = json.loads(request_contract_path.read_text(encoding="utf-8"))
    return {c["child_id"]: c for c in data["hierarchy"]["children"]}


def write_frozen(
    children_by_id: dict | None = None,
    *,
    request_contract_path: Path | None = None,
    output_path: Path | None = None,
) -> dict:
    """Builds + freezes q_aib's contract and writes it to `output_path` (default: FROZEN_PATH).
    Returns the written dict. Pure aside from this one write -- never touches
    hierarchy_contract.py's own frozen pin or review file, and never writes a `.review.json`."""
    if children_by_id is None:
        path = request_contract_path or Path(os.environ.get("QAIB_REQUEST_CONTRACT", str(_DEFAULT_REQUEST_CONTRACT)))
        children_by_id = _load_children_by_id(path)
    contract = sa.build_qaib_contract(children_by_id)
    frozen = sa.freeze(contract)
    target = output_path or FROZEN_PATH
    target.write_text(json.dumps(frozen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return frozen


def load_verified(*, frozen_path: Path | None = None, review_path: Path | None = None) -> dict | None:
    """Loads + verifies the frozen, human-reviewed sufficiency contract, returning
    ``{child_id: SufficiencyContract}`` -- exactly the shape
    ``sufficiency_diagnostic.compute_diagnostic_sufficiency_map``'s own ``contract_by_child``
    parameter expects, read straight from each child's already-stripped ``frozen_view`` (never
    re-authored at runtime).

    Returns ``None`` -- never raises -- only when `frozen_path` itself does not exist: a question
    with no authored sufficiency contract at all is a legitimate, benign absence (today, every
    question except q_aib), not a defect. Once the file exists, every problem below is fatal and
    raises ``SufficiencyContractRejected`` naming all of them -- the frozen file's own ``status``
    field is explicit that "no live run should trust this without a recorded human review naming
    this combined_hash", so an existing-but-unverifiable artifact is never silently used:

    - each child's `frozen_view` must still hash to its own recorded `hash` (per-child integrity --
      `se.contract_hash` is the exact function `sufficiency_authoring.freeze` used to produce it);
    - the recomputed `combined_hash` over the file's own `per_child` mapping must match its
      recorded `combined_hash` (whole-file integrity, the same computation `freeze` performs);
    - a review record must exist at `review_path` (default: the sibling `REVIEW_PATH`) naming this
      exact `combined_hash` and `question_key`, with non-empty `reviewed_by`/`reviewed_at` fields.
    """
    path = Path(frozen_path) if frozen_path is not None else FROZEN_PATH
    if not path.is_file():
        return None
    try:
        frozen = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SufficiencyContractRejected([f"frozen contract unreadable ({type(exc).__name__}: {exc})"]) from exc

    problems: list[str] = []
    per_child = frozen.get("per_child") or {}
    if not isinstance(per_child, dict) or not per_child:
        problems.append("the frozen contract carries no per_child entries")
    for child_id, entry in sorted(per_child.items()):
        recomputed = se.contract_hash(entry["frozen_view"])
        if recomputed != entry.get("hash"):
            problems.append(f"{child_id}: frozen_view no longer matches its recorded per-child hash")
    recomputed_combined = hashlib.sha256(
        json.dumps(per_child, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if recomputed_combined != frozen.get("combined_hash"):
        problems.append("combined_hash does not match the frozen file's own per_child content")

    rpath = Path(review_path) if review_path is not None else REVIEW_PATH
    try:
        review = json.loads(rpath.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"no review record at {rpath.name} -- a live run needs an explicit human review")
        review = {}
    except (OSError, ValueError) as exc:
        problems.append(f"review record unreadable ({type(exc).__name__}: {exc})")
        review = {}
    if review.get("combined_hash") != frozen.get("combined_hash"):
        problems.append("review: combined_hash does not match the current frozen file (it changed after review)")
    if review.get("question_key") != frozen.get("question_key"):
        problems.append("review: question_key does not match the frozen file")
    for field in ("reviewed_by", "reviewed_at"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            problems.append(f"review: {field} is missing")

    if problems:
        raise SufficiencyContractRejected(problems)
    return {child_id: entry["frozen_view"] for child_id, entry in per_child.items()}


def main(argv: list[str] | None = None) -> int:
    frozen = write_frozen()
    print(f"wrote {FROZEN_PATH.name}")
    print(f"combined_hash: {frozen['combined_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
