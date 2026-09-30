"""Materializes sufficiency_authoring's q_aib SufficiencyContract to disk as an UNREVIEWED_
CANDIDATE frozen pin, mirroring hierarchy_contract.py's own FROZEN_PATH convention (a sibling
JSON file next to the authoring module, named by question_key). Never writes a `.review.json` --
that file records an explicit human review and only Cliff can author it truthfully; see
hierarchy_contract.py's own review gate for the precedent this defers to.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_authoring as sa

FROZEN_PATH = Path(__file__).with_name(f"sufficiency_contract.{sa.QUESTION_KEY}.frozen.json")

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


def main(argv: list[str] | None = None) -> int:
    frozen = write_frozen()
    print(f"wrote {FROZEN_PATH.name}")
    print(f"combined_hash: {frozen['combined_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
