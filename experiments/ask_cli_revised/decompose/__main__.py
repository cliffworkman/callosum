"""Arbitrary-question decomposition CLI (thin wrapper over ``engine.run_engine``).

    python -m experiments.ask_cli_revised.decompose --question-file q.txt --out DIR [--model M --endpoint URL]
    python -m experiments.ask_cli_revised.decompose --question-file q.txt --out DIR --model qwen3.5:9b --endpoint http://127.0.0.1:11435 --think false --max-calls 40

Protected requests (q_lld, q_builtenv) are refused without ``--experiment-authorization`` (see EXPERIMENT_GATE.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ask_cli_revised.decompose import gate  # noqa: E402
from experiments.ask_cli_revised.decompose.engine import DEFAULT_MAX_CALLS, run_engine  # noqa: E402
from experiments.ask_cli_revised.decompose.model import DEFAULT_ENDPOINT, DEFAULT_MODEL, OllamaJsonModel  # noqa: E402
from experiments.ask_cli_revised.decompose.report import render_report  # noqa: E402


def _dump(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_artifacts(result: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    parent = result["parent_contract"]
    _dump(
        out / "00_request.json",
        {
            "question": result["question"],
            "question_sha256": result["question_sha256"],
            "source_units": parent["source_units"],
        },
    )
    _dump(out / "01_parent_contract.json", parent)
    _dump(out / "08_decomposition_decision.json", result.get("decomposition_decision"))
    p1 = result["pass1"]
    _dump(out / "02_pass1_children.json", {"pass": 1, "plans": p1.get("plans", []), "children": p1["children"]})
    _dump(
        out / "03_pass1_audit.json",
        {
            "verified_traceability": p1["verified_traceability"],
            "embedding_audit_diagnostic": p1["embedding_audit_diagnostic"],
            "reconciliation": p1["reconciliation"],
        },
    )
    if result["pass2"]:
        p2 = result["pass2"]
        _dump(
            out / "04_pass2_repaired.json",
            {"pass": 2, "plans": p2.get("plans", []), "children": p2["children"], "repairs": p2.get("repairs", [])},
        )
        _dump(
            out / "05_pass2_audit.json",
            {
                "verified_traceability": p2["verified_traceability"],
                "embedding_audit_diagnostic": p2["embedding_audit_diagnostic"],
                "reconciliation": p2["reconciliation"],
            },
        )
    _dump(
        out / "06_final_reconciliation.json", {"final_pass": result["final_pass"], **result["final"]["reconciliation"]}
    )
    _dump(
        out / "07_question_tree.json",
        {
            "final_pass": result["final_pass"],
            "question_tree": result["final"]["question_tree"],
            "roll_up": result["final"]["reconciliation"].get("question_tree"),
        },
    )
    with (out / "model_calls.jsonl").open("w", encoding="utf-8") as fh:
        for rec in result["calls"]:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    if result.get("inventory_calls"):
        with (out / "inventory_calls_replayed.jsonl").open("w", encoding="utf-8") as fh:
            for rec in result["inventory_calls"]:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    _dump(out / "engine_manifest.json", result["manifest"])
    (out / "REPORT.md").write_text(render_report(result), encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--question")
    src.add_argument("--question-file")
    p.add_argument("--out", required=True)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument(
        "--think",
        choices=("default", "false", "true"),
        default="default",
        help="native reasoning setting for models that have one (Qwen3.5: false)",
    )
    p.add_argument(
        "--max-calls",
        type=int,
        default=DEFAULT_MAX_CALLS,
        help="hard cap on model calls; the run degrades to fallback_unresolved rather than exceed it",
    )
    p.add_argument("--no-repair", action="store_true")
    p.add_argument("--no-whole-pass", action="store_true")
    p.add_argument(
        "--embedding-audit", action="store_true", help="optional diagnostic: reuse the run06 embedding audit"
    )
    p.add_argument(
        "--replay-calls",
        help="model_calls.jsonl of an earlier run: re-score its recorded outputs with the current code (no model is called)",
    )
    p.add_argument(
        "--inventory-replay",
        help="model_calls.jsonl of an earlier run: build the obligation inventory from its RECORDED parent.* calls (no model call) and use --model only for the wording stage",
    )
    p.add_argument(
        "--clarifications",
        help="JSON file of user-authorized, span-linked clarifications (see clarifications.py); nothing else is resolved",
    )
    p.add_argument(
        "--prompt-variant",
        choices=("v3", "corrected-full", "lean", "prepared"),
        default="v3",
        help="child-writer prompt: the frozen v3, or one of the matched prospective variants (same schema and budget; prepared = corrected-full + deterministic preparation)",
    )
    p.add_argument("--only", help="comma-separated child ids to write (the rest are recorded not_selected, no call)")
    p.add_argument(
        "--clarification-annotations",
        nargs="+",
        help="one or more JSON files of context_link / brief / requirements annotations beside the clarifications (merged by clarification id)",
    )
    p.add_argument(
        "--no-passthrough",
        action="store_true",
        help="always run the writer, even for a request the engine judges to need no decomposition",
    )
    p.add_argument(
        "--use-proposed-briefs",
        action="store_true",
        help="WHAT-IF only: show PROPOSED (unapproved) clarification condensations to the model; never authorizes wording",
    )
    p.add_argument(
        "--allow-pending-clarifications",
        action="store_true",
        help="use clarifications marked PENDING (proposals not yet approved by the user) for a labelled what-if only",
    )
    p.add_argument("--experiment-authorization")
    args = p.parse_args(argv)
    question = (
        args.question if args.question is not None else Path(args.question_file).read_text(encoding="utf-8").strip()
    )
    try:
        gate.check(question, args.experiment_authorization)
    except gate.GateRefused as exc:
        print(f"[decompose] REFUSED: {exc}", file=sys.stderr)
        return 4
    if args.replay_calls:
        from experiments.ask_cli_revised.decompose.model import ReplayModel

        records = [
            json.loads(line)
            for line in Path(args.replay_calls).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        model = ReplayModel(records, records[0]["produced_by"])
    else:
        model = OllamaJsonModel(
            args.model, args.endpoint, think={"default": None, "false": False, "true": True}[args.think]
        )
    from experiments.ask_cli_revised.decompose import clarifications as clar_mod

    clarifications = None
    if args.clarifications:
        try:
            clarifications = clar_mod.load(args.clarifications)
        except clar_mod.ClarificationError as exc:
            print(f"[decompose] REFUSED: {exc}", file=sys.stderr)
            return 6
    inventory_model = None
    if args.inventory_replay:
        from experiments.ask_cli_revised.decompose.model import ReplayModel

        recorded = [
            json.loads(line)
            for line in Path(args.inventory_replay).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        inventory_model = ReplayModel(
            [r for r in recorded if r["task"].startswith("parent.")], recorded[0]["produced_by"]
        )
    out = Path(args.out)
    embed = None
    if args.embedding_audit:
        from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, DEFAULT_NORMALIZATION
        from app.backend.model_runtime import PINNED_MODEL_REVISIONS, ModelRuntimeRegistry

        embed = ModelRuntimeRegistry().get_embedding_model(
            name=DEFAULT_EMBEDDING_MODEL,
            normalization=DEFAULT_NORMALIZATION,
            revision=PINNED_MODEL_REVISIONS.get(DEFAULT_EMBEDDING_MODEL),
        )
    out.mkdir(parents=True, exist_ok=True)
    sink = out / "model_calls.jsonl"
    sink.write_text("", encoding="utf-8")
    from experiments.ask_cli_revised.decompose.clarifications import ClarificationError

    try:
        result = run_engine(
            question,
            model,
            repair=not args.no_repair,
            whole_pass=not args.no_whole_pass,
            max_calls=args.max_calls,
            embed_model=embed,
            call_sink=sink,
            inventory_model=inventory_model,
            clarifications=clarifications,
            allow_pending_clarifications=args.allow_pending_clarifications,
            prompt_variant=args.prompt_variant,
            only=[x.strip() for x in args.only.split(",") if x.strip()] if args.only else None,
            clarification_annotations=[
                row for path in args.clarification_annotations for row in clar_mod.load_annotations(path)
            ]
            if args.clarification_annotations
            else None,
            use_proposed_briefs=args.use_proposed_briefs,
            passthrough_enabled=not args.no_passthrough,
        )
    except ClarificationError as exc:
        print(f"[decompose] REFUSED: {exc}", file=sys.stderr)
        return 6
    write_artifacts(result, out)
    print(
        f"[decompose] wrote {out}  children(final)={len(result['final']['children'])}  final_pass={result['final_pass']}  calls={result['manifest']['call_summary']['calls']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
