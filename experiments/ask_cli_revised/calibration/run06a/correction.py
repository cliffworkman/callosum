"""Run 0.6a correction pass — provenance-only fix of q_builtenv u7's H0 style label.

Run 0.6a recovered H0 provenance by matching frozen-selection text against the candidate pool in STYLES
order (minimal, relation, multi, baseline). q_builtenv fell back to a whole-question BASELINE, but its u7
baseline item ("visuospatial processing and more.") is byte-identical to the `relation` candidate for the
same unit, so text-matching mislabeled u7 as "relation". `hybrid._recover_style` is now authoritative
(reads the frozen decomposition's own is_baseline / repaired / selected_candidate metadata); this module
re-derives H0 provenance with that fixed, PURE logic and writes corrected copies of the two affected Run
0.6a machine artifacts into a NEW directory.

Provenance-only by construction: the corrected item texts are byte-identical to the originals, so every
numeric metric is carried verbatim and re-asserted equal. No embedder, Qwen, Ollama, Gemini, retrieval,
context, or verifier is loaded or called; neither frozen run directory is written. The pass STOPS on any
difference beyond the single expected provenance correction, and never begins Run 0.7.

    python -m experiments.ask_cli_revised.calibration.run06a.correction \
        --run06 <run06-dir> --run06a <run06a-dir> [--out <correction-dir>]
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.ask_cli_revised.calibration.run06a import hybrid, inputs  # noqa: E402
from experiments.ask_cli_revised.trace import TraceWriter  # noqa: E402

RICH_CASES = inputs.RICH_CASES
# The single provenance correction this pass is allowed to make. Any deviation is a STOP condition.
EXPECTED_DIFF = {("q_builtenv", "u7"): ("relation", "baseline")}
H0_INHERITING_MAPS = ("H0", "H1", "H2_oracle", "Hm_metric_only")
_BASELINE_LABEL = {"label": "FAITHFUL", "reason": "exact source text."}


class CorrectionStop(RuntimeError):
    """Raised when an unexpected difference is found — the pass stops rather than rationalizing it."""


# --------------------------------------------------------------------------------------------------
# pure diff + provenance helpers (no I/O)
# --------------------------------------------------------------------------------------------------
def leaf_diffs(a, b, path: str = "") -> list[tuple[str, object, object]]:
    """Every differing leaf (and structural difference) between two JSON-shaped values, as (path, a, b)."""
    diffs: list[tuple[str, object, object]] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                diffs.append((f"{path}.{k}", a.get(k, "<MISSING>"), b.get(k, "<MISSING>")))
            else:
                diffs.extend(leaf_diffs(a[k], b[k], f"{path}.{k}"))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((f"{path}[len]", len(a), len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b, strict=True)):
                diffs.extend(leaf_diffs(x, y, f"{path}[{i}]"))
    elif a != b:
        diffs.append((path, a, b))
    return diffs


def corrected_h0_provenance(frozen, case) -> dict[str, str]:
    """unit_id -> corrected H0 style, from the FIXED authoritative recovery (pure JSON, no embedder)."""
    return {uid: rep["style"] for uid, rep in hybrid.h0_representations(frozen, case).items()}


def provenance_diff(frozen, orig_assemblies) -> dict[tuple[str, str], tuple[str, str]]:
    """{(case, unit): (recorded_H0_style, corrected_H0_style)} for every unit whose H0 provenance moved."""
    diff: dict[tuple[str, str], tuple[str, str]] = {}
    for case in RICH_CASES:
        recorded = orig_assemblies[case]["H0"]
        corrected = corrected_h0_provenance(frozen, case)
        for uid, new_style in corrected.items():
            old_style = recorded.get(uid)
            if old_style != new_style:
                diff[(case, uid)] = (old_style, new_style)
    return diff


def baseline_label_by_construction(frozen, case: str, unit_id: str) -> dict[str, str]:
    """FAITHFUL / 'exact source text.' — established from the raw frozen fields, NOT via the label module.

    An exact baseline item (is_baseline and source_text == text) is faithful to itself by construction; the
    correction is provenance-only, so it does not reach into the reference-label module to rediscover that.
    """
    items = [i for i in inputs.frozen_selection(frozen, case)["items"] if i["source_unit_id"] == unit_id]
    if not items or not all(i.get("is_baseline") and i["source_text"] == i["text"] for i in items):
        raise CorrectionStop(
            f"{case} {unit_id}: corrected-to-baseline unit is not an exact frozen baseline item "
            "(is_baseline / source_text == text failed) — refusing to assert FAITHFUL by construction"
        )
    return dict(_BASELINE_LABEL)


# --------------------------------------------------------------------------------------------------
# corrected artifact builders
# --------------------------------------------------------------------------------------------------
def correct_assemblies(orig_assemblies: dict, diff: dict) -> dict:
    """Propagate each H0 provenance correction into the H0-inheriting maps ONLY where they inherited it."""
    out = copy.deepcopy(orig_assemblies)
    for (case, uid), (old_style, new_style) in diff.items():
        for m in H0_INHERITING_MAPS:
            if out[case][m].get(uid) == old_style:  # was H0-inherited, not a substitution
                out[case][m][uid] = new_style
    return out


def correct_metrics(frozen, orig_metrics: dict, diff: dict) -> dict:
    """Correct the provenance label (reps.style + fidelity.per_unit.{style,label,reason}) only; carry every
    numeric metric verbatim. A baseline correction's label is set by construction (FAITHFUL)."""
    out = copy.deepcopy(orig_metrics)
    for (case, uid), (old_style, new_style) in diff.items():
        by_construction = baseline_label_by_construction(frozen, case, uid) if new_style == "baseline" else None
        for hyp in out[case].values():  # H0 / H1 / H2 / Hm records
            reps = hyp.get("reps", {})
            if reps.get(uid, {}).get("style") == old_style:
                reps[uid]["style"] = new_style
            per_unit = hyp.get("fidelity", {}).get("per_unit", {})
            if per_unit.get(uid, {}).get("style") == old_style:
                per_unit[uid]["style"] = new_style
                if by_construction is not None:
                    per_unit[uid]["label"] = by_construction["label"]
                    per_unit[uid]["reason"] = by_construction["reason"]
    return out


# --------------------------------------------------------------------------------------------------
# verification (independent, post-build)
# --------------------------------------------------------------------------------------------------
def verify_assemblies(orig: dict, corrected: dict, diff: dict) -> list[tuple[str, object, object]]:
    """Every assembly change must be an expected H0-inheriting-map style flip for a diffed unit; nothing else."""
    allowed = {
        f".{case}.{m}.{uid}": (old, new)
        for (case, uid), (old, new) in diff.items()
        for m in H0_INHERITING_MAPS
        if orig[case][m].get(uid) == old
    }
    diffs = leaf_diffs(orig, corrected)
    for path, old, new in diffs:
        if allowed.get(path) != (old, new):
            raise CorrectionStop(f"unexpected assembly change: {path} {old!r} -> {new!r}")
    if len(diffs) != len(allowed):
        raise CorrectionStop(f"assembly changed {len(diffs)} leaves; expected exactly {len(allowed)}")
    return diffs


def verify_metrics(orig: dict, corrected: dict, diff: dict) -> list[tuple[str, object, object]]:
    """Every metrics change must be a provenance-label field (style/label/reason) for a diffed unit; assert
    ZERO numeric change. label FAITHFUL is unchanged here, so only style + reason move."""
    diffs = leaf_diffs(orig, corrected)
    changed_units = {(case, uid) for (case, uid) in diff}
    for path, old, new in diffs:
        ok = False
        for (case, uid), (old_style, new_style) in diff.items():
            if not path.startswith(f".{case}."):
                continue
            if path.endswith(f".reps.{uid}.style") and (old, new) == (old_style, new_style):
                ok = True
            elif path.endswith(f".per_unit.{uid}.style") and (old, new) == (old_style, new_style):
                ok = True
            elif path.endswith(f".per_unit.{uid}.reason") and new == _BASELINE_LABEL["reason"]:
                ok = True
            if ok:
                break
        if not ok:
            raise CorrectionStop(f"unexpected metrics change (possible numeric drift): {path} {old!r} -> {new!r}")
        # No numeric/aggregate field may ever appear among the changes.
        for forbidden in (".metrics.", ".counts.", ".interaction", ".substitutions", ".item_ids"):
            if forbidden in path:
                raise CorrectionStop(f"metrics correction touched a numeric/aggregate field: {path}")
    # label must be unchanged (FAITHFUL -> FAITHFUL) and counts identical for every diffed case.
    for (case, uid) in changed_units:
        for hyp_name, hyp in orig[case].items():
            o = hyp["fidelity"]["per_unit"].get(uid, {}).get("label")
            c = corrected[case][hyp_name]["fidelity"]["per_unit"].get(uid, {}).get("label")
            if o != c:
                raise CorrectionStop(f"{case} {hyp_name} {uid}: fidelity label moved {o!r} -> {c!r}")
            if orig[case][hyp_name]["fidelity"]["counts"] != corrected[case][hyp_name]["fidelity"]["counts"]:
                raise CorrectionStop(f"{case} {hyp_name}: fidelity counts changed")
    return diffs


# --------------------------------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------------------------------
def _u7_frozen(frozen) -> dict:
    return next(i for i in inputs.frozen_selection(frozen, "q_builtenv")["items"] if i["source_unit_id"] == "u7")


def correction_report_md(*, frozen, orig_metrics, corrected_metrics, diff, asm_diffs, met_diffs, inputs_rec) -> list[str]:
    be = frozen["data"]["04_frozen_decompositions.json"]["q_builtenv"]
    u7 = _u7_frozen(frozen)
    rel_u7 = [i["text"] for i in frozen["data"]["02_candidates.json"]["q_builtenv"]["candidates"]["relation"]["items"] if i["source_unit_id"] == "u7"][0]
    base_u7 = [i["text"] for i in frozen["data"]["02_candidates.json"]["q_builtenv"]["candidates"]["baseline"]["items"] if i["source_unit_id"] == "u7"][0]
    h0o = orig_metrics["q_builtenv"]["H0"]
    h0c = corrected_metrics["q_builtenv"]["H0"]
    m = h0o["metrics"]

    L = ["# Run 0.6a correction — q_builtenv u7 H0 provenance (provenance-only)", ""]
    L += ["This pass corrects a single mislabeled provenance value in the frozen Run 0.6a machine artifacts.",
          "It is provenance-only: no item text changed, and every numeric metric is carried verbatim and",
          "re-asserted equal. The original Run 0.6 and Run 0.6a directories are left byte-for-byte unchanged;",
          "corrected copies are written here. No embedder / Qwen / provider / retrieval / verifier ran.", ""]

    L += ["## 1. Exact frozen Run 0.6 provenance for q_builtenv (`04_frozen_decompositions.json`)", "",
          f"- `selected_candidate` = `{be['selected_candidate']}` (whole-question fallback).",
          f"- `selection.reason` = {json.dumps(be['selection']['reason'])}",
          f"- `decomposition_hash` = `{be['decomposition_hash']}`",
          f"- frozen u7 item `{u7['item_id']}`: `is_baseline` = {json.dumps(u7['is_baseline'])}, "
          f"`from_fallback` = {json.dumps(u7['from_fallback'])}, `repaired` = {json.dumps(u7['repaired'])}",
          f"- frozen u7 `source_text` = {json.dumps(u7['source_text'])}",
          f"- frozen u7 `text`        = {json.dumps(u7['text'])}",
          "- every q_builtenv frozen item has `is_baseline: true` — the whole question fell back to exact source units.", ""]

    L += ["## 2. Erroneous Run 0.6a provenance + root cause", "",
          "- `hybrid_assemblies.json`: q_builtenv u7 recorded as `\"relation\"` in H0/H1/H2_oracle/Hm_metric_only.",
          f"- `hybrid_metrics.json`: q_builtenv `reps.u7.style` = `\"relation\"` and "
          f"`fidelity.per_unit.u7` = `{{style: relation, label: FAITHFUL, reason: {json.dumps(h0o['fidelity']['per_unit']['u7']['reason'])}}}`.",
          "- **Root cause:** H0 provenance was recovered by matching the frozen-selection text against the",
          "  candidate pool in `STYLES` order (`minimal, relation, multi, baseline`). The `relation` candidate",
          "  for u7 is byte-identical to the baseline/source text, so `relation` matched before `baseline` was",
          "  ever tried. Text identity, not provenance, decided the label.", "",
          f"  - relation-candidate u7 text = {json.dumps(rel_u7)}",
          f"  - baseline-candidate u7 text = {json.dumps(base_u7)}",
          f"  - byte-identical (relation == baseline == source == frozen text): "
          f"{rel_u7 == base_u7 == u7['text'] == u7['source_text']}", ""]

    L += ["## 3. Corrected provenance", "",
          "- `hybrid._recover_style` is now authoritative: `all(is_baseline) -> \"baseline\"`; "
          "`any(repaired) -> \"selected\"`; else the question's `selected_candidate` base style.",
          "- q_builtenv u7 H0 style: `\"relation\"` -> `\"baseline\"` (and the same in every H0-inheriting map).",
          f"- `fidelity.per_unit.u7`: style -> `\"baseline\"`, reason -> {json.dumps(_BASELINE_LABEL['reason'])}, "
          f"label unchanged (`\"{h0c['fidelity']['per_unit']['u7']['label']}\"`, exact source text is faithful by construction).", ""]

    L += ["## 4. Did any text change? **NO.**", "",
          "The u7 baseline and relation representations are byte-identical, so the assembled item-set for every",
          "hypothesis is unchanged. Only the provenance *label* moved.", ""]

    L += ["## 5. Did any numeric metric change? **NO.**", "",
          "The embedder was not re-run; because the assembled text is identical, the frozen Run 0.6a metrics are",
          "carried verbatim and independently re-asserted equal (leaf diff over the full artifacts finds only",
          "`style`/`reason` string changes for q_builtenv u7 — never a numeric field).", "",
          "| metric (q_builtenv H0) | before | after |", "| --- | --- | --- |",
          f"| global_reconstruction | {m['global_reconstruction']} | {h0c['metrics']['global_reconstruction']} |",
          f"| weakest_coverage | {m['weakest_coverage']} | {h0c['metrics']['weakest_coverage']} |",
          f"| n_items | {m['n_items']} | {h0c['metrics']['n_items']} |",
          f"| fidelity FAITHFUL count | {h0o['fidelity']['counts']['FAITHFUL']} | {h0c['fidelity']['counts']['FAITHFUL']} |", "",
          f"- assembly leaf changes: {len(asm_diffs)} (all `\"relation\" -> \"baseline\"` for q_builtenv u7 maps).",
          f"- metrics leaf changes: {len(met_diffs)} (all `style`/`reason` fields for q_builtenv u7; zero numeric).", ""]

    L += ["## 6. Did any substantive Run 0.6a conclusion change? **NO.**", "",
          "- u7 remains `FAITHFUL`; q_builtenv `drifted_units` remains `[]`; no Hm substitution occurs.",
          "- The fix removes an internal inconsistency: the machine artifacts now agree with the orchestrator's",
          "  own `RUN06_SELECTED_BASE[\"q_builtenv\"] = \"baseline\"` and with `RUN_0_6A_REPORT.md`'s narrative",
          "  that q_builtenv was a whole-question baseline fallback (u7 already appears there among the faithful",
          "  Qwen rewrites *discarded* by that fallback). No policy comparison, specimen, or finding changes.", ""]

    L += ["## Terminology correction (Correction 2)", "",
          "The Run 0.6a `fidelity_labels.json` labels were authored by Claude from source + candidate text; they",
          "are **not yet human ground truth**. They must be called **model-authored reference fidelity labels**",
          "(or **frozen reference fidelity labels**), not \"human fidelity labels\", until a subset is adjudicated.",
          "This wording is corrected in the reusable analysis code edited in this pass (`hybrid.py`,",
          "`selfcheck.py`). The frozen `fidelity_labels.json` and `RUN_0_6A_REPORT.md` are deliberately left",
          "unchanged, and the legacy \"human\" wording still present in the sibling `fidelity.py` /",
          "`metrics_audit.py` / `run_run06a.py` / `report06a.py` is a noted future pass, not touched here.", ""]

    L += ["## Integrity", "",
          f"- frozen Run 0.6 dir: `{inputs_rec['run06_dir']}` — `dir_digest` unchanged "
          f"(`{inputs_rec['run06_dir_digest'][:16]}...`).",
          f"- original Run 0.6a dir: `{inputs_rec['run06a_dir']}` — `dir_digest` unchanged before/after "
          f"(`{inputs_rec['run06a_dir_digest'][:16]}...`).",
          f"- provenance diffs found: exactly {len(diff)} (`{sorted(diff)}`), the single expected correction.",
          "- STOPPED after writing the correction artifacts — Run 0.7 not started.", ""]
    return L


# --------------------------------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------------------------------
def run(run06_dir: str, run06a_dir: str, out_dir: str | None) -> int:
    run06a_path = Path(run06a_dir)
    if out_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = str(run06a_path.parent / f"run06a-correction-{ts}")
    out_path = Path(out_dir)
    if out_path.resolve() in (Path(run06_dir).resolve(), run06a_path.resolve()):
        raise CorrectionStop("refusing to write into a frozen run directory")

    # read-only load + hash of both frozen directories
    frozen = inputs.load_frozen(run06_dir)
    run06a_digest_before = inputs.dir_digest(run06a_path)
    orig_assemblies = json.loads((run06a_path / "hybrid_assemblies.json").read_text(encoding="utf-8"))
    orig_metrics = json.loads((run06a_path / "hybrid_metrics.json").read_text(encoding="utf-8"))

    # corrected provenance + the exactly-one-diff guard
    diff = provenance_diff(frozen, orig_assemblies)
    if diff != EXPECTED_DIFF:
        raise CorrectionStop(f"provenance diff is not the single expected correction: got {sorted(diff.items())}")

    corrected_assemblies = correct_assemblies(orig_assemblies, diff)
    corrected_metrics = correct_metrics(frozen, orig_metrics, diff)
    asm_diffs = verify_assemblies(orig_assemblies, corrected_assemblies, diff)
    met_diffs = verify_metrics(orig_metrics, corrected_metrics, diff)

    inputs_rec = {
        "run06_dir": frozen["dir"],
        "run06_hashes": frozen["hashes"],
        "run06_dir_digest": frozen["dir_digest"],
        "run06a_dir": str(run06a_path),
        "run06a_dir_digest": run06a_digest_before,
        "run06a_artifacts_sha256": {
            "hybrid_assemblies.json": inputs.sha256_file(run06a_path / "hybrid_assemblies.json"),
            "hybrid_metrics.json": inputs.sha256_file(run06a_path / "hybrid_metrics.json"),
        },
        "embedder": "NOT LOADED — provenance-only correction, no re-audit",
        "provenance_diff": {f"{c}:{u}": {"from": old, "to": new} for (c, u), (old, new) in diff.items()},
        "assembly_leaf_changes": len(asm_diffs),
        "metrics_leaf_changes": len(met_diffs),
    }

    trace = TraceWriter(out_dir)
    trace.write_json("00_correction_inputs.json", inputs_rec)
    trace.write_json("corrected_hybrid_assemblies.json", corrected_assemblies)
    trace.write_json("corrected_hybrid_metrics.json", corrected_metrics)
    trace.write_report(
        "RUN_0_6A_CORRECTION.md",
        correction_report_md(frozen=frozen, orig_metrics=orig_metrics, corrected_metrics=corrected_metrics,
                             diff=diff, asm_diffs=asm_diffs, met_diffs=met_diffs, inputs_rec=inputs_rec),
    )

    # post-write integrity: neither frozen directory moved
    after = inputs.load_frozen(run06_dir)
    if after["hashes"] != frozen["hashes"] or after["dir_digest"] != frozen["dir_digest"]:
        raise CorrectionStop("frozen Run 0.6 directory changed during the pass!")
    if inputs.dir_digest(run06a_path) != run06a_digest_before:
        raise CorrectionStop("original Run 0.6a directory changed during the pass!")

    print(f"[run0.6a-correction] provenance-only fix written -> {out_dir}")
    print(f"[run0.6a-correction] diff = {sorted(diff.items())}; assembly changes = {len(asm_diffs)}; "
          f"metrics changes = {len(met_diffs)} (zero numeric)")
    print("[run0.6a-correction] frozen Run 0.6 + Run 0.6a directories unchanged. STOP -- Run 0.7 not started.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run06", required=True, help="the frozen Run 0.6 run directory")
    p.add_argument("--run06a", required=True, help="the frozen Run 0.6a output directory (read-only)")
    p.add_argument("--out", default=None, help="correction output directory (default: runs/run06a-correction-<ts>)")
    args = p.parse_args(argv)
    return run(args.run06, args.run06a, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
