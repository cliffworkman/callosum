"""Build the blinded Cliff fidelity-adjudication reference slice (Run 0.6a).

SOLE content input: the frozen Run 0.6 candidate pool `02_candidates.json`. Nothing else is
read for specimen content (no Run 0.6a fidelity / correction artifacts). Stdlib only; no
network, no provider, no model.

Specimen set (exactly 28):
  A. 22 q_aib individual items  — minimal(6) + relation(6) + multi(10)
  B.  2 q_aib multi bundles     — source units u3 and u5 (all frozen multi items for the unit)
  C.  4 transfer specimens      — q_depr minimal u2, q_depr relation u8,
                                   q_builtenv multi u5, q_builtenv minimal u4
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------------------------
# Fixed constants / provenance
# --------------------------------------------------------------------------------------------

# Repo root = .../callosum ; this file is experiments/ask_cli_revised/calibration/run06a_cliff/
REPO_ROOT = Path(__file__).resolve().parents[4]
RUNS_DIR = REPO_ROOT / "experiments" / "ask_cli_revised" / "calibration" / "runs"
FROZEN_CANDIDATES = RUNS_DIR / "run06-20260908T041153Z" / "02_candidates.json"

# Recorded, fixed shuffle seed (see plan). Reproducible via random.Random(seed).
SHUFFLE_SEED = 20260908

# Known-good SHA-256 of the frozen candidate pool (integrity anchor).
KNOWN_FROZEN_SHA256 = "de93a2c542de81cccaac260ca9adf503f29703f88614bfda2d9f2be7cd84141f"

ALLOWED_LABELS = [
    "FAITHFUL",
    "LOSS",
    "ADDITION",
    "LOSS_AND_ADDITION",
    "MALFORMED_OR_UNUSABLE",
    "UNSURE",
]

FENCE = "```"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


# --------------------------------------------------------------------------------------------
# Specimen extraction (from frozen JSON only)
# --------------------------------------------------------------------------------------------


def load_frozen(path: Path = FROZEN_CANDIDATES) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _items(frozen: dict, case: str, style: str) -> list[dict]:
    return frozen[case]["candidates"][style]["items"]


def _item_by_id(frozen: dict, case: str, style: str, item_id: str) -> dict:
    for it in _items(frozen, case, style):
        if it["item_id"] == item_id:
            return it
    raise KeyError(f"missing item {case}/{style}/{item_id}")


def _items_for_unit(frozen: dict, case: str, style: str, unit: str) -> list[dict]:
    return [it for it in _items(frozen, case, style) if it["source_unit_id"] == unit]


def _make_item_specimen(frozen: dict, case: str, style: str, item_id: str) -> dict:
    it = _item_by_id(frozen, case, style, item_id)
    return {
        "canonical_id": f"{case}:{style}:{item_id}",
        "specimen_level": "item",
        "case_id": case,
        "candidate_style": style,
        "source_unit_id": it["source_unit_id"],
        "source_text": it["source_text"],
        "full_original_question": frozen[case]["question"],
        "candidate_item_id": item_id,
        "candidate_text": it["text"],
    }


def _make_bundle_specimen(frozen: dict, case: str, style: str, unit: str) -> dict:
    unit_items = _items_for_unit(frozen, case, style, unit)
    if not unit_items:
        raise KeyError(f"no items for bundle {case}/{style}/{unit}")
    source_texts = {it["source_text"] for it in unit_items}
    if len(source_texts) != 1:
        raise ValueError(f"bundle {case}/{style}/{unit} spans multiple source texts")
    return {
        "canonical_id": f"{case}:{style}:bundle:{unit}",
        "specimen_level": "bundle",
        "case_id": case,
        "candidate_style": style,
        "source_unit_id": unit,
        "source_text": unit_items[0]["source_text"],
        "full_original_question": frozen[case]["question"],
        "bundle_item_ids": [it["item_id"] for it in unit_items],
        "candidate_items": [it["text"] for it in unit_items],
    }


def build_specimens(frozen: dict) -> list[dict]:
    """Canonical (pre-shuffle) order. Derived from frozen items for robustness."""
    specimens: list[dict] = []

    # A. q_aib individual items — take exactly what is frozen, in frozen order.
    for style in ("minimal", "relation", "multi"):
        for it in _items(frozen, "q_aib", style):
            specimens.append(_make_item_specimen(frozen, "q_aib", style, it["item_id"]))

    # B. q_aib multi bundles for source units u3 and u5.
    specimens.append(_make_bundle_specimen(frozen, "q_aib", "multi", "u3"))
    specimens.append(_make_bundle_specimen(frozen, "q_aib", "multi", "u5"))

    # C. transfer specimens (each a single frozen item).
    transfer = [
        ("q_depr", "minimal", "u2-r1"),
        ("q_depr", "relation", "u8-r1"),
        ("q_builtenv", "multi", "u5-r1"),
        ("q_builtenv", "minimal", "u4-r1"),
    ]
    for case, style, item_id in transfer:
        specimens.append(_make_item_specimen(frozen, case, style, item_id))

    _assert_canonical_shape(specimens)
    return specimens


def _assert_canonical_shape(specimens: list[dict]) -> None:
    if len(specimens) != 28:
        raise ValueError(f"expected 28 specimens, got {len(specimens)}")
    aib_individual = [
        s for s in specimens if s["case_id"] == "q_aib" and s["specimen_level"] == "item"
    ]
    bundles = [s for s in specimens if s["specimen_level"] == "bundle"]
    transfer = [s for s in specimens if s["case_id"] in ("q_depr", "q_builtenv")]
    if len(aib_individual) != 22:
        raise ValueError(f"expected 22 q_aib individual, got {len(aib_individual)}")
    if len(bundles) != 2:
        raise ValueError(f"expected 2 bundles, got {len(bundles)}")
    if len(transfer) != 4:
        raise ValueError(f"expected 4 transfer, got {len(transfer)}")
    # per-style q_aib individual counts
    counts = {"minimal": 0, "relation": 0, "multi": 0}
    for s in aib_individual:
        counts[s["candidate_style"]] += 1
    if counts != {"minimal": 6, "relation": 6, "multi": 10}:
        raise ValueError(f"unexpected q_aib style counts: {counts}")


def shuffle_specimens(specimens: list[dict], seed: int = SHUFFLE_SEED) -> list[dict]:
    """Deterministic shuffle; assign neutral specimen numbers/ids in the shuffled order."""
    order = list(specimens)
    random.Random(seed).shuffle(order)
    numbered = []
    for i, spec in enumerate(order, start=1):
        s = dict(spec)
        s["specimen_number"] = i
        s["specimen_id"] = f"SPECIMEN {i:02d}"
        numbered.append(s)
    return numbered


# --------------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------------

WORKSHEET_HEADER = """\
# Run 0.6a — Cliff fidelity adjudication (blinded reference slice)

You are producing an **independent human adjudication reference slice**. Later evaluation will
measure agreement against your labels; this is a reference slice for that comparison.

Below are 28 numbered specimens in a fixed, shuffled order. For each, read the source unit and
the candidate representation, then write one label on the `CLIFF LABEL:` line.

## What you are judging

**Textual intent fidelity only.**

You are NOT judging:
- scientific correctness
- plausibility
- retrieval quality
- whether the candidate would find better papers
- whether you personally like the wording
- grammar, except when malformedness makes the representation unusable

The question is:

> "Does this candidate representation faithfully preserve what the user asked in this source
> unit, using the full original question only to resolve references?"

## Reference-resolution rule

Each specimen includes the FULL ORIGINAL QUESTION. It is supplied ONLY so you can interpret
elliptical source units such as "and using which scales?", "which cultures and how was this
measured?", "and more", "it", "this".

A candidate may legitimately add words needed to resolve such references. However, a candidate
does NOT become faithful merely because added material appears somewhere else in the full
question. The test remains: **was that material required to resolve THIS source unit?** Do not
let unrelated neighboring requests migrate freely between units.

## A note on specimens with more than one representation

A few specimens present more than one candidate representation of the same source unit (a
numbered list). For those, judge whether the set, taken together, faithfully preserves the
source unit.

## Allowed labels

- **FAITHFUL** — preserves the meaning of the source unit. May rephrase, fix grammar, make an
  elliptical unit standalone, resolve a pronoun/reference using the original question, or add
  wording required only to make the source intelligible out of context. Must not materially add
  or remove user intent.
- **LOSS** — drops, narrows, generalizes away, replaces, or breaks meaning explicitly present
  in the source unit (e.g. omitting a requested relationship, dropping a requested
  measurement/method, replacing a specific referent with a broader one, or keeping the topic
  but losing what the user wanted to know about it).
- **ADDITION** — adds meaning not present in the source unit and not required only to resolve a
  reference or make the source standalone (a new request, example, construct, behavior,
  attitude, population, relationship, measurement, causal assumption, specificity, or importing
  a neighboring source unit's request when not required to resolve this one). Scientific
  plausibility does NOT make an addition faithful.
- **LOSS_AND_ADDITION** — both happen: some source meaning is lost AND some new meaning is added.
- **MALFORMED_OR_UNUSABLE** — the wording is syntactically broken, incoherent, corrupted, or
  otherwise unusable as a scholarly retrieval representation. Use only when malformedness /
  usability is the primary problem, not merely because wording is awkward.
- **UNSURE** — genuinely ambiguous; adjudication withheld. Not a sixth fidelity class.

## How to fill this in

For each specimen, replace the empty brackets on the `CLIFF LABEL:` line with exactly one of
the allowed labels (e.g. `[FAITHFUL]`). Use the `OPTIONAL NOTE:` line only if you want to.
"""

SPECIMEN_RULE = "-" * 60


def _fence_block(text: str) -> str:
    return f"{FENCE}text\n{text}\n{FENCE}"


def _render_specimen(spec: dict) -> str:
    parts: list[str] = []
    parts.append(SPECIMEN_RULE)
    parts.append(spec["specimen_id"])
    parts.append(SPECIMEN_RULE)
    parts.append("")
    parts.append("FULL ORIGINAL QUESTION:")
    parts.append("")
    parts.append(_fence_block(spec["full_original_question"]))
    parts.append("")
    parts.append("SOURCE UNIT:")
    parts.append("")
    parts.append(_fence_block(spec["source_text"]))
    parts.append("")
    if spec["specimen_level"] == "bundle":
        parts.append("CANDIDATE REPRESENTATION:")
        parts.append("")
        for i, item_text in enumerate(spec["candidate_items"], start=1):
            parts.append(f"{i}.")
            parts.append(_fence_block(item_text))
            parts.append("")
    else:
        parts.append("CANDIDATE REPRESENTATION:")
        parts.append("")
        parts.append(_fence_block(spec["candidate_text"]))
        parts.append("")
    parts.append("CLIFF LABEL:")
    parts.append("[ ]")
    parts.append("")
    parts.append("Allowed: " + " / ".join(ALLOWED_LABELS))
    parts.append("")
    parts.append("OPTIONAL NOTE:")
    parts.append("[ ]")
    parts.append("")
    return "\n".join(parts)


def render_markdown(shuffled: list[dict]) -> str:
    chunks = [WORKSHEET_HEADER, ""]
    for spec in shuffled:
        chunks.append(_render_specimen(spec))
    return "\n".join(chunks).rstrip("\n") + "\n"


def render_template(shuffled: list[dict], seed: int = SHUFFLE_SEED) -> dict:
    specimens = []
    for spec in shuffled:
        entry = {
            "specimen_id": spec["specimen_id"],
            "specimen_number": spec["specimen_number"],
            "specimen_level": spec["specimen_level"],
            "case_id": spec["case_id"],
            "source_unit_id": spec["source_unit_id"],
            "candidate_style": spec["candidate_style"],
            "source_text": spec["source_text"],
            "full_original_question": spec["full_original_question"],
            "cliff_label": None,
            "cliff_note": None,
        }
        if spec["specimen_level"] == "bundle":
            entry["bundle_item_ids"] = spec["bundle_item_ids"]
            entry["candidate_items"] = spec["candidate_items"]
        else:
            entry["candidate_item_id"] = spec["candidate_item_id"]
            entry["candidate_text"] = spec["candidate_text"]
        specimens.append(entry)
    return {
        "metadata": {
            "purpose": "independent human textual-fidelity adjudication reference slice",
            "adjudicator": "Cliff",
            "reference_slice": True,
            "not_ground_truth": True,
            "n_specimens": len(specimens),
            "shuffle_seed": seed,
            "sole_content_input": "run06-20260908T041153Z/02_candidates.json",
            "allowed_labels": list(ALLOWED_LABELS),
        },
        "specimens": specimens,
    }


def render_manifest(
    shuffled: list[dict],
    frozen_sha: str,
    md_bytes: bytes,
    template_bytes: bytes,
    seed: int = SHUFFLE_SEED,
) -> dict:
    item_level = [s for s in shuffled if s["specimen_level"] == "item"]
    bundle_level = [s for s in shuffled if s["specimen_level"] == "bundle"]
    aib_individual = [
        s for s in shuffled if s["case_id"] == "q_aib" and s["specimen_level"] == "item"
    ]
    transfer = [s for s in shuffled if s["case_id"] in ("q_depr", "q_builtenv")]
    return {
        "artifact": "run_0_6a_cliff_adjudication",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "sole_content_input": {
            "path": "run06-20260908T041153Z/02_candidates.json",
            "sha256": frozen_sha,
            "known_good_sha256": KNOWN_FROZEN_SHA256,
            "sha256_matches_known_good": frozen_sha == KNOWN_FROZEN_SHA256,
        },
        "hashes": {
            "frozen_candidates_02_candidates_json": frozen_sha,
            "run_0_6a_cliff_adjudication_md": sha256_bytes(md_bytes),
            "cliff_adjudication_template_json": sha256_bytes(template_bytes),
        },
        "counts": {
            "specimen_count": len(shuffled),
            "n_aib_individual": len(aib_individual),
            "n_aib_bundles": len(bundle_level),
            "n_transfer": len(transfer),
            "n_item_level": len(item_level),
            "n_bundle_level": len(bundle_level),
        },
        "shuffle_seed": seed,
        "specimen_index": [
            {
                "specimen_id": s["specimen_id"],
                "canonical_id": s["canonical_id"],
                "specimen_level": s["specimen_level"],
            }
            for s in shuffled
        ],
        "confirmations": {
            "no_model_or_reference_labels_embedded": True,
            "no_candidate_text_generated_or_altered": True,
            "no_correction_or_fidelity_artifacts_read_for_content": True,
            "all_cliff_labels_blank": True,
        },
    }


# --------------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------------


def _json_bytes(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build(output_root: Path = RUNS_DIR, seed: int = SHUFFLE_SEED) -> dict:
    frozen_sha = sha256_file(FROZEN_CANDIDATES)
    if frozen_sha != KNOWN_FROZEN_SHA256:
        raise ValueError(
            f"frozen candidate pool hash mismatch: {frozen_sha} != {KNOWN_FROZEN_SHA256}"
        )
    frozen = load_frozen()
    specimens = build_specimens(frozen)
    shuffled = shuffle_specimens(specimens, seed=seed)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = output_root / f"run06a-cliff-adjudication-{ts}"
    out_dir.mkdir(parents=True, exist_ok=False)

    md_text = render_markdown(shuffled)
    md_bytes = md_text.encode("utf-8")
    template = render_template(shuffled, seed=seed)
    template_bytes = _json_bytes(template)
    manifest = render_manifest(shuffled, frozen_sha, md_bytes, template_bytes, seed=seed)
    manifest_bytes = _json_bytes(manifest)

    md_path = out_dir / "run_0_6a_cliff_adjudication.md"
    template_path = out_dir / "cliff_adjudication_template.json"
    manifest_path = out_dir / "cliff_adjudication_manifest.json"

    md_path.write_bytes(md_bytes)
    template_path.write_bytes(template_bytes)
    manifest_path.write_bytes(manifest_bytes)

    return {
        "out_dir": out_dir,
        "md_path": md_path,
        "template_path": template_path,
        "manifest_path": manifest_path,
        "n_specimens": len(shuffled),
    }
