"""One-shot diagnostic: deterministic-only vs deterministic+model-nomination sufficiency mapping
over the PRESERVED q_aib hierarchical live run. Consumes the already-materialized, committed
`sufficiency_contract.aib_hier_v8.frozen.json` (Cliff's correction #6) -- it never calls
`sufficiency_authoring.build_qaib_contract` itself, so it can never silently regenerate the
scientific contract out from under a reviewed hash. Refuses to make a live model call without an
explicit, matching experiment-authorization file (mirrors EXPERIMENT_GATE.md's mechanical guard,
scoped to this one experiment) that ALSO names the exact frozen-artifact hash it was authorized
against -- a file that has since changed on disk refuses too, never silently proceeds on stale
authorization. `--dry-run` proves every mechanical step EXCEPT the live call itself, using a null
model client that nominates nothing -- safe to run with no network access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised import sufficiency_freeze as sf

EXPERIMENT_ID = "q_aib_sufficiency_model_nomination_diagnostic_v1"

_DEFAULT_RUN_DIR = (
    Path(__file__).resolve().parents[2] / ".local" / "e2e-runs" / "q-aib-hierarchical-t5c-live-20260930" / "run"
)


class _NullModelClient:
    """--dry-run only: proves the pipeline runs end-to-end without ever proposing a nomination."""

    model_name = "null-dry-run"

    def nominate_sufficiency_role(self, *, category_description: str, candidates: list[dict]) -> list[dict]:
        return []


def load_frozen_contract(path: Path | None = None) -> dict:
    """Reads the already-materialized frozen pin (default: `sufficiency_freeze.FROZEN_PATH`) and
    returns `{child_id: SufficiencyContract}` built from its own `frozen_view` rows -- never from
    `sufficiency_authoring.build_qaib_contract`. Empirically confirmed byte-identical to a direct
    build against the same request contract (see this module's own test file)."""
    target = path or sf.FROZEN_PATH
    frozen = json.loads(target.read_text(encoding="utf-8"))
    return frozen, {cid: row["frozen_view"] for cid, row in frozen["per_child"].items()}


def verify_frozen_integrity(frozen: dict) -> bool:
    """Recomputes every per-child hash and the combined hash from the frozen content itself and
    compares against the stored values -- detects a hand-edited or corrupted frozen file. Does
    NOT compare against any externally-authorized hash; that is `_load_authorization`'s job."""
    for child_id, row in frozen.get("per_child", {}).items():
        recomputed = se.contract_hash({"child_id": child_id, "requirements": row["frozen_view"]["requirements"]})
        if recomputed != row["hash"]:
            return False
    per_child = {cid: row for cid, row in frozen["per_child"].items()}
    recomputed_combined = hashlib.sha256(
        json.dumps(per_child, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return recomputed_combined == frozen["combined_hash"]


def _load_authorization(path: Path, *, question_sha256: str, frozen_combined_hash: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError(f"authorization file is for a different experiment_id: {data.get('experiment_id')!r}")
    if question_sha256 not in (data.get("question_sha256s") or []):
        raise ValueError("authorization file does not name this run's own question_sha256")
    if data.get("brief_confirmed") is not True:
        raise ValueError("authorization file does not carry brief_confirmed: true")
    if not data.get("authorized_by") or not data.get("authorized_at"):
        raise ValueError("authorization file is missing authorized_by/authorized_at")
    if data.get("frozen_contract_hash") != frozen_combined_hash:
        raise ValueError(
            "the frozen artifact on disk does not match the hash this authorization was granted "
            f"for ({data.get('frozen_contract_hash')!r} != {frozen_combined_hash!r}) -- refusing"
        )
    return data


def _load_sealed(run_dir: Path) -> dict:
    raw = json.loads((run_dir / "11_verified_ledger.json").read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if k != "sealed_hash"}


def _load_children_by_id(run_dir: Path) -> dict:
    data = json.loads((run_dir / "01_request_contract.json").read_text(encoding="utf-8"))
    return {c["child_id"]: c for c in data["hierarchy"]["children"]}


def _parent_of(children_by_id: dict) -> dict:
    return {cid: c["parent"] for cid, c in children_by_id.items() if c.get("parent") and c["parent"] != "R"}


def run(*, run_dir: Path, contract_by_child: dict, model_client, model_name: str) -> dict:
    """`contract_by_child` must come from `load_frozen_contract` -- never re-authored here."""
    children = _load_children_by_id(run_dir)
    sealed = _load_sealed(run_dir)
    parent_of = _parent_of(children)
    deterministic_only = sd.compute_diagnostic_sufficiency_map(sealed, contract_by_child, parent_of)
    with_model = sd.compute_diagnostic_sufficiency_map(sealed, contract_by_child, parent_of, model_client=model_client)
    return {"deterministic_only": deterministic_only, "with_model": with_model, "model_name": model_name}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=_DEFAULT_RUN_DIR)
    parser.add_argument("--frozen-contract", type=Path, help="default: sufficiency_freeze.FROZEN_PATH")
    parser.add_argument("--experiment-authorization", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="no model client; proves the pipeline mechanically")
    parser.add_argument("--out", type=Path, help="where to write the full audit trace JSON")
    args = parser.parse_args(argv)

    frozen, contract_by_child = load_frozen_contract(args.frozen_contract)
    if not verify_frozen_integrity(frozen):
        raise SystemExit("refusing: the frozen contract file fails its own internal hash check")
    question_sha256 = json.loads((args.run_dir / "01_request_contract.json").read_text(encoding="utf-8"))[
        "question_hash"
    ]

    if args.dry_run:
        model_client, model_name = _NullModelClient(), _NullModelClient.model_name
    else:
        if not args.experiment_authorization:
            raise SystemExit("refusing: --experiment-authorization FILE is required for a live run")
        _load_authorization(
            args.experiment_authorization,
            question_sha256=question_sha256,
            frozen_combined_hash=frozen["combined_hash"],
        )
        # NOTE (Phase 2 implementer): construct the real Ollama-backed QwenTasks exactly as the
        # live q_aib E2E driver already does for its own W-role calls (see e2e.py's own
        # construction site) -- not written here, since Phase 1 must not wire a reachable live
        # client at all.
        raise SystemExit("live model path is intentionally not wired in Phase 1 -- see the handback notes")

    result = run(
        run_dir=args.run_dir, contract_by_child=contract_by_child, model_client=model_client, model_name=model_name
    )
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"deterministic_only children: {len(result['deterministic_only'])}")
    print(f"with_model children: {len(result['with_model'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
