"""Deterministic Run 0.6a self-checks — no network, no Qwen, no embedder load.

Proves: no forbidden provider/Qwen/Gemini import on the analysis path; the metric-only path (policy_a +
build_hm) never uses the model-authored reference fidelity labels; each Policy-A drift comparator ranks an obviously-better
candidate correctly (direction proof); label set + H2 non-deployable marking; and (when the frozen run06 dir
is present) same-source-unit substitution provenance, baseline availability, and no newly-generated text.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_RUN06 = HERE.parent / "runs" / "run06-20260908T041153Z"
# Import module-path fragments that would indicate a provider/Qwen/HTTP dependency on the analysis path.
_FORBIDDEN_IMPORTS = ("managed_local", "gemini", "ollama", "httpx", "requests", "llm.providers", "provider_runtime")
# Unambiguous call/name fragments (won't occur in prose) — catch provider/Qwen invocation directly.
_FORBIDDEN_CALLS = ("resolve_managed", "run_schema_call", "build_runtime(", ".complete(")
_ANALYSIS_FILES = ("inputs.py", "fidelity.py", "policy_a.py", "hybrid.py", "metrics_audit.py", "report06a.py", "run_run06a.py")


def _imported_modules(module_path: Path) -> list[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            mods.append(base)
            mods.extend(f"{base}.{a.name}" for a in node.names)
    return mods


def _check(name, cond):
    if not cond:
        raise AssertionError(f"FAILED: {name}")
    print(f"  ok: {name}")


def _fn_source(module_path: Path, fn_name: str) -> str:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            return ast.get_source_segment(module_path.read_text(encoding="utf-8"), node) or ""
    raise AssertionError(f"function {fn_name} not found in {module_path.name}")


def main() -> int:
    from experiments.ask_cli_revised.calibration.run06a import fidelity, inputs, policy_a

    # ---- no forbidden provider/Qwen/Gemini import or call anywhere on the analysis path ----
    # (selfcheck.py itself is excluded: it necessarily names the forbidden tokens to scan for them.)
    for name in _ANALYSIS_FILES:
        mods = _imported_modules(HERE / name)
        bad = [m for m in mods for frag in _FORBIDDEN_IMPORTS if frag in m]
        _check(f"{name} imports no provider/Qwen/HTTP module", not bad)
        src = (HERE / name).read_text(encoding="utf-8")
        for tok in _FORBIDDEN_CALLS:
            _check(f"{name} has no forbidden call '{tok}'", tok not in src)

    # ---- metric-only path never touches the model-authored reference labels ----
    _check("policy_a.py does not reference fidelity", "fidelity" not in (HERE / "policy_a.py").read_text(encoding="utf-8"))
    hm_src = _fn_source(HERE / "hybrid.py", "build_hm")
    _check("build_hm (metric-only) does not reference fidelity", "fidelity" not in hm_src)
    _check("build_hm evaluates trials against H0 (order-independent)", "trial = {**h0" in hm_src and "accepted" in hm_src)

    # ---- Policy-A comparator direction proof (synthetic) ----
    good1 = [{"item_id": "g", "source_unit_id": "u1", "source_local_similarity": 0.95}]
    bad1 = [{"item_id": "b", "source_unit_id": "u1", "source_local_similarity": 0.10}]
    good2 = [{"item_id": "a", "source_unit_id": "u1", "source_local_similarity": 0.9},
             {"item_id": "b", "source_unit_id": "u1", "source_local_similarity": 0.9}]
    bad2 = [{"item_id": "a", "source_unit_id": "u1", "source_local_similarity": 0.9},
            {"item_id": "b", "source_unit_id": "u1", "source_local_similarity": 0.1}]
    for summary in policy_a.DRIFT_SUMMARIES:
        _check(f"comparator '{summary}': low-drift < high-drift burden (single-item)",
               policy_a.drift_burden(good1, summary) < policy_a.drift_burden(bad1, summary))
        _check(f"comparator '{summary}': low-drift < high-drift burden (bundle)",
               policy_a.drift_burden(good2, summary) < policy_a.drift_burden(bad2, summary))

    # ---- label set + H2 non-deployable marking ----
    _check("label set is the 5 expected", set(fidelity.LABELS) == {"FAITHFUL", "LOSS", "ADDITION", "LOSS_AND_ADDITION", "MALFORMED_OR_UNUSABLE"})
    hybrid_src = (HERE / "hybrid.py").read_text(encoding="utf-8")
    _check("H2 explicitly marked ORACLE / non-deployable", "ORACLE" in hybrid_src and "NON-DEPLOYABLE" in hybrid_src.upper())

    # ---- data-backed checks (only if the frozen run06 dir is present) ----
    run06 = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RUN06
    if run06.exists():
        from experiments.ask_cli_revised.calibration.run06a import hybrid
        frozen = inputs.load_frozen(run06)
        all_texts = set()
        for case in inputs.RICH_CASES:
            for style in inputs.STYLES:
                for it in frozen["data"]["02_candidates.json"][case]["candidates"][style]["items"]:
                    all_texts.add(it["text"])
        for it in [i for c in inputs.RICH_CASES for i in inputs.frozen_selection(frozen, c)["items"]]:
            all_texts.add(it["text"])  # include repaired selected items

        for case in inputs.RICH_CASES:
            units = [u["source_unit_id"] for u in inputs.source_units(frozen, case)]
            for uid in units:
                _check(f"{case} {uid}: baseline representation available",
                       inputs.representation(frozen, case, "baseline", uid) is not None)
            for name, builder in (("H1", hybrid.build_h1), ("H2", hybrid.build_h2_oracle)):
                reps = builder(frozen, case)
                for uid, rep in reps.items():
                    _check(f"{case} {name} {uid}: all items share source_unit_id",
                           all(i["source_unit_id"] == uid for i in rep["items"]))
                    _check(f"{case} {name} {uid}: no newly-generated text",
                           all(i["text"] in all_texts for i in rep["items"]))

        # ---- H0 provenance is reconstructed from the frozen decomposition, NOT candidate text ----
        # The expected side is derived INDEPENDENTLY from the raw 04_frozen fields (is_baseline / repaired /
        # selected_candidate) and never calls _recover_style or a helper it shares; it cross-checks that the
        # recovered H0 style is consistent with each unit's raw frozen metadata.
        for case in inputs.RICH_CASES:
            dec = inputs.frozen_selection(frozen, case)
            sel_base = dec["selected_candidate"].split("+")[0]
            raw_by_unit: dict[str, list[dict]] = {}
            for it in dec["items"]:
                raw_by_unit.setdefault(it["source_unit_id"], []).append(it)
            recovered = hybrid.h0_representations(frozen, case)
            for uid, raw_items in raw_by_unit.items():
                style = recovered[uid]["style"]
                if all(i.get("is_baseline") for i in raw_items):
                    _check(f"{case} {uid}: H0 provenance 'baseline' <=> every frozen item is_baseline", style == "baseline")
                elif any(i.get("repaired") for i in raw_items):
                    _check(f"{case} {uid}: H0 provenance 'selected' when a frozen item is repaired", style == "selected")
                else:
                    _check(f"{case} {uid}: H0 provenance is the selected_candidate base for an un-flagged Qwen unit",
                           style == sel_base and not any(i.get("is_baseline") for i in raw_items))

        # ---- named regression: provenance must beat a byte-identical text twin (q_builtenv u7) ----
        dec_be = inputs.frozen_selection(frozen, "q_builtenv")
        _check("q_builtenv selected_candidate == 'baseline'", dec_be["selected_candidate"] == "baseline")
        u7 = next(i for i in dec_be["items"] if i["source_unit_id"] == "u7")
        _check("q_builtenv frozen u7 is_baseline is true", u7.get("is_baseline") is True)
        _check("q_builtenv frozen u7 from_fallback is true", u7.get("from_fallback") is True)
        cands_be = frozen["data"]["02_candidates.json"]["q_builtenv"]["candidates"]
        rel_u7 = [i["text"] for i in cands_be["relation"]["items"] if i["source_unit_id"] == "u7"]
        base_u7 = [i["text"] for i in cands_be["baseline"]["items"] if i["source_unit_id"] == "u7"]
        _check("q_builtenv u7 relation candidate is byte-identical to baseline/source text (the trap)",
               rel_u7 == base_u7 == [u7["text"]] == [u7["source_text"]])
        _check("q_builtenv u7 H0 style is 'baseline' despite the relation text twin (provenance beats text)",
               hybrid.h0_representations(frozen, "q_builtenv")["u7"]["style"] == "baseline")
    else:
        print(f"  (skipped data-backed checks: {run06} not present)")

    print("ALL RUN 0.6a SELF-CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
