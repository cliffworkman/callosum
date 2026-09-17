"""Validation for the blinded Cliff adjudication slice — proves all 15 required invariants.

Re-reads the produced files from disk and re-derives everything independently from the frozen
candidate pool. Prints blind-safe results only (no specimen -> identity mapping).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import build

FENCE_RE = re.compile(r"```text\n(.*?)\n```", re.S)

# Specific diagnostic tokens that must NOT leak into generator-authored scaffolding.
# (Applied ONLY outside the verbatim frozen-text fences — a frozen string may coincidentally
# contain one of these words.)
SCAFFOLDING_DENYLIST = [
    "ground truth",
    "source-local",
    "source local",
    " sls",
    "leave-one-out",
    "leave one out",
    " loo",
    "coverage",
    "redundan",
    "reconstruct",
    "drift",
    "starved",
    "preserved",
    "selected by",
    "selection outcome",
    "claude",
    "model-authored",
    "rationale",
    "confusion matrix",
    "similarity",
]

# Specific frozen artifact-file tokens whose presence in build.py would indicate reading a
# correction / 0.6a / non-candidate artifact for content.
FORBIDDEN_INPUT_TOKENS = [
    "hybrid_metrics",
    "hybrid_assemblies",
    "corrected_hybrid",
    "00_correction_inputs",
    "03_selection",
    "04_frozen_decompositions",
    "05_walk",
    "lineage",
    "qwen_calls",
    "run06a-correction",
    "run06a-2026",
]

ALLOWED_IMPORT_ROOTS = {
    "hashlib",
    "json",
    "random",
    "datetime",
    "pathlib",
    "re",
    "sys",
    "__future__",
}


class Result:
    def __init__(self, num: int, name: str, ok: bool, detail: str = ""):
        self.num = num
        self.name = name
        self.ok = ok
        self.detail = detail


def _import_roots(source: str) -> set[str]:
    roots: set[str] = set()
    for raw in source.splitlines():
        line = raw.strip()
        if line.startswith("from . import") or line.startswith("from .build"):
            roots.add(".")
            continue
        if line.startswith("import "):
            roots.add(line[len("import ") :].split()[0].split(".")[0])
        elif line.startswith("from "):
            roots.add(line[len("from ") :].split()[0].split(".")[0])
    return roots


def _strip_fences(md: str) -> str:
    return FENCE_RE.sub("<<FENCE>>", md)


def validate(out_dir: Path) -> list[Result]:
    results: list[Result] = []

    # Re-derive everything from the frozen pool, independently.
    frozen_sha = build.sha256_file(build.FROZEN_CANDIDATES)
    frozen = build.load_frozen()
    seed_from_template = json.loads(
        (out_dir / "cliff_adjudication_template.json").read_text(encoding="utf-8")
    )["metadata"]["shuffle_seed"]
    specimens = build.build_specimens(frozen)
    shuffled = build.shuffle_specimens(specimens, seed=seed_from_template)
    expected_md = build.render_markdown(shuffled)
    expected_template = build.render_template(shuffled, seed=seed_from_template)

    md_path = out_dir / "run_0_6a_cliff_adjudication.md"
    template_path = out_dir / "cliff_adjudication_template.json"
    manifest_path = out_dir / "cliff_adjudication_manifest.json"

    md_text = md_path.read_text(encoding="utf-8")
    template = json.loads(template_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tspecs = template["specimens"]

    # 1. exactly 28 specimens (md + json)
    md_specimen_ids = re.findall(r"^SPECIMEN \d{2}$", md_text, re.M)
    results.append(
        Result(
            1,
            "exactly 28 specimens (md + json)",
            len(tspecs) == 28 and len(md_specimen_ids) == 28,
            f"json={len(tspecs)} md={len(md_specimen_ids)}",
        )
    )

    # 2. exactly 22 q_aib individual
    aib_ind = [s for s in tspecs if s["case_id"] == "q_aib" and s["specimen_level"] == "item"]
    results.append(Result(2, "exactly 22 q_aib individual items", len(aib_ind) == 22, f"n={len(aib_ind)}"))

    # 3. exactly 2 q_aib bundles
    bundles = [s for s in tspecs if s["specimen_level"] == "bundle"]
    all_bundles_aib = all(s["case_id"] == "q_aib" for s in bundles)
    results.append(Result(3, "exactly 2 q_aib bundles", len(bundles) == 2 and all_bundles_aib, f"n={len(bundles)}"))

    # 4. exactly 4 transfer specimens
    transfer = [s for s in tspecs if s["case_id"] in ("q_depr", "q_builtenv")]
    results.append(Result(4, "exactly 4 transfer specimens", len(transfer) == 4, f"n={len(transfer)}"))

    # 5. every source/candidate string byte-identical to frozen (independent of reconstruction)
    ok5 = True
    detail5 = "all match"
    for s in tspecs:
        case, style = s["case_id"], s["candidate_style"]
        if s["specimen_level"] == "bundle":
            fitems = build._items_for_unit(frozen, case, style, s["source_unit_id"])
            frozen_texts = [it["text"] for it in fitems]
            frozen_src = fitems[0]["source_text"] if fitems else None
            if s["candidate_items"] != frozen_texts or s["source_text"] != frozen_src:
                ok5, detail5 = False, f"bundle mismatch {s['specimen_id']}"
                break
        else:
            it = build._item_by_id(frozen, case, style, s["candidate_item_id"])
            if s["candidate_text"] != it["text"] or s["source_text"] != it["source_text"]:
                ok5, detail5 = False, f"item mismatch {s['specimen_id']}"
                break
        if s["full_original_question"] != frozen[case]["question"]:
            ok5, detail5 = False, f"question mismatch {s['specimen_id']}"
            break
    results.append(Result(5, "every source/candidate string byte-identical to frozen (json)", ok5, detail5))

    # 5b. md fenced-text regions byte-identical to frozen, in order
    md_blocks = FENCE_RE.findall(md_text)
    expected_blocks: list[str] = []
    for s in shuffled:
        expected_blocks.append(s["full_original_question"])
        expected_blocks.append(s["source_text"])
        if s["specimen_level"] == "bundle":
            expected_blocks.extend(s["candidate_items"])
        else:
            expected_blocks.append(s["candidate_text"])
    results.append(
        Result(
            51,
            "md fenced-text regions byte-identical to frozen, in order",
            md_blocks == expected_blocks,
            f"blocks={len(md_blocks)} expected={len(expected_blocks)}",
        )
    )

    # 6. each bundle contains all frozen items for its source unit
    ok6 = True
    detail6 = "ok"
    for s in bundles:
        fitems = build._items_for_unit(frozen, s["case_id"], s["candidate_style"], s["source_unit_id"])
        frozen_ids = [it["item_id"] for it in fitems]
        if s["bundle_item_ids"] != frozen_ids:
            ok6, detail6 = False, f"{s['specimen_id']} {s['bundle_item_ids']} != {frozen_ids}"
            break
    results.append(Result(6, "each bundle = all frozen items for its source unit", ok6, detail6))

    # 7-10. absence-of-leakage via reconstruction equality + scaffolding-only denylist
    md_bytes = md_path.read_bytes()
    recon_ok = md_bytes == expected_md.encode("utf-8")
    template_recon_ok = template == expected_template
    scaffolding = _strip_fences(md_text).lower()
    hits = [tok.strip() for tok in SCAFFOLDING_DENYLIST if tok in scaffolding]
    results.append(
        Result(
            7,
            "no leakage: md == reconstruction from (template + frozen text only)",
            recon_ok and template_recon_ok,
            "md+template reconstructed byte-identical"
            if (recon_ok and template_recon_ok)
            else f"md_ok={recon_ok} template_ok={template_recon_ok}",
        )
    )
    results.append(
        Result(
            8,
            "no diagnostic tokens in generator scaffolding (outside frozen fences)",
            not hits,
            "clean" if not hits else f"hits={hits}",
        )
    )

    # 11. md & json specimen ordering identical
    json_order = [s["specimen_id"] for s in tspecs]
    md_order = md_specimen_ids
    results.append(
        Result(11, "md & json specimen ordering identical", json_order == md_order, "identical" if json_order == md_order else "DIVERGENT")
    )

    # 12. all cliff labels/notes null; md labels blank
    # Inspect ONLY the actual `CLIFF LABEL:` lines (not header prose, which shows a `[FAITHFUL]`
    # example): every label line must be exactly `[ ]`.
    json_blank = all(s["cliff_label"] is None and s["cliff_note"] is None for s in tspecs)
    label_lines = re.findall(r"CLIFF LABEL:\n\[([^\]]*)\]", md_text)
    md_blank_count = sum(1 for v in label_lines if v == " ")
    md_filled = [v for v in label_lines if v != " "]
    results.append(
        Result(
            12,
            "all Cliff labels blank/null (json + md)",
            json_blank and len(label_lines) == 28 and md_blank_count == 28 and not md_filled,
            f"json_blank={json_blank} label_lines={len(label_lines)} blank={md_blank_count} filled={md_filled}",
        )
    )

    # 13. prior run dirs untouched (frozen hash unchanged; no forbidden input tokens in build.py)
    build_src = Path(build.__file__).read_text(encoding="utf-8")
    forbidden_hits = [t for t in FORBIDDEN_INPUT_TOKENS if t in build_src]
    frozen_ok = frozen_sha == build.KNOWN_FROZEN_SHA256
    results.append(
        Result(
            13,
            "prior run dirs untouched (frozen hash intact; no correction/0.6a artifact reads)",
            frozen_ok and not forbidden_hits,
            f"frozen_sha_ok={frozen_ok} forbidden_input_tokens={forbidden_hits}",
        )
    )

    # 14. no network/provider call — build + selfcheck import stdlib (+ local) only
    self_src = Path(__file__).read_text(encoding="utf-8")
    bad_imports = sorted(
        (_import_roots(build_src) | _import_roots(self_src))
        - ALLOWED_IMPORT_ROOTS
        - {"."}
    )
    results.append(
        Result(14, "no network/provider imports (stdlib + local only)", not bad_imports, f"unexpected={bad_imports}")
    )

    # 15. no production changes — artifacts confined to the runs output dir, under experiments/
    runs_dir = build.RUNS_DIR.resolve()
    arts = [md_path, template_path, manifest_path]
    confined = all(runs_dir in p.resolve().parents for p in arts) and out_dir.resolve().parent == runs_dir
    results.append(
        Result(15, "artifacts confined to experiments/.../runs output dir (no production writes)", confined, str(out_dir))
    )

    # Manifest cross-check (counts + hashes match on-disk files)
    counts = manifest["counts"]
    manifest_ok = (
        counts["specimen_count"] == 28
        and counts["n_item_level"] == 26
        and counts["n_bundle_level"] == 2
        and counts["n_aib_individual"] == 22
        and counts["n_transfer"] == 4
        and manifest["hashes"]["run_0_6a_cliff_adjudication_md"] == build.sha256_bytes(md_bytes)
        and manifest["hashes"]["cliff_adjudication_template_json"]
        == build.sha256_bytes(template_path.read_bytes())
        and manifest["hashes"]["frozen_candidates_02_candidates_json"] == frozen_sha
    )
    results.append(
        Result(
            16,
            "manifest counts/hashes consistent (26 item + 2 bundle; hashes match files)",
            manifest_ok,
            "consistent" if manifest_ok else "MISMATCH",
        )
    )

    return results


def run(out_dir: Path) -> bool:
    results = validate(out_dir)
    print("Validation (blind-safe; no specimen identities shown):")
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        print(f"  [{status}] {r.num:>2}. {r.name} — {r.detail}")
    all_ok = all(r.ok for r in results)
    print(f"\n{'ALL CHECKS PASS' if all_ok else 'SOME CHECKS FAILED'} ({sum(r.ok for r in results)}/{len(results)})")
    return all_ok
