"""The frozen substrate: the approved decomposition, the library copy and the baseline artifacts.

Nothing here re-derives, reinterprets or edits a contract. The approved hierarchy is read from the completed T5O run's
recorded request contract and verified against the identities recorded in that run's manifest; any mismatch makes the
substrate unusable (fail closed), never "close enough".
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from experiments.ask_cli_revised import hierarchy_contract as hc
from experiments.ask_cli_revised import library_copy

AB_ROOT = Path(os.environ.get("CALLOSUM_AB_ROOT", "C:/Users/cliff/callosum-data/ab-backend-2026-09-26"))
SLICE_ROOT = Path(os.environ.get("CALLOSUM_SLICE_ROOT", "C:/Users/cliff/callosum-data/contract-directed-slice"))

QUESTION_SHA256 = "6e037bab4baad2c0b4427a1c73c6e1720296292b3be36189cd9cf02436e57030"
HIERARCHY_INTEGRITY_SHA256 = "c45630b81a7c92683a6c9a07037f580f1750b65c5a3c5dae7aac79289a2b6e20"
MODEL_FACING_SHA256 = "c1f3be3b35e7b74c0044ef1f2e6c21072ee0e90bd47fba9a01d7149b88fd41cb"
LIBRARY_SHA256 = "4f2e98a54c92790e791d841ef63e2fd60c4b411246f9c29590c19e56da892523"
MODEL = "qwen3.5:9b"
MODEL_DIGEST = "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"
OLLAMA_VERSION = "0.34.3"
CHILD_IDS = ("c1", "c2", "c3", "c4", "c5", "c6", "c8", "c9", "c10", "c11", "c12")


@dataclass(frozen=True)
class Unit:
    """One frozen obligation owned by a child. Condition units (whether/how/specific/any/effective) modify a content unit."""

    unit_id: str
    kind: str
    text: str
    is_condition: bool


@dataclass(frozen=True)
class ChildContract:
    child_id: str
    parent: str
    contract_text: str  # the exact model_display the approved run showed models
    contract_sha256: str
    wording: str
    wording_sha256: str
    scope_carrier_wording: str | None
    units: tuple[Unit, ...]
    primary_unit_id: str  # the content unit that this child's condition units modify
    pair_requirement_ids: tuple[str, ...]  # frozen structural "#pair" requirements (c9, c11)
    machine_side_constraints: tuple[dict, ...]  # exact approved text kept out of model input

    @property
    def content_units(self) -> tuple[Unit, ...]:
        return tuple(u for u in self.units if not u.is_condition)

    @property
    def condition_units(self) -> tuple[Unit, ...]:
        return tuple(u for u in self.units if u.is_condition)

    def unit(self, unit_id: str) -> Unit:
        return next(u for u in self.units if u.unit_id == unit_id)

    def retrieval_query(self) -> str:
        """A child-only retrieval view: the approved wording plus the approved carried scope. The parent question is not used."""
        if not self.scope_carrier_wording:
            return self.wording
        return f"{self.wording} {self.scope_carrier_wording}"


@dataclass(frozen=True)
class FrozenSubstrate:
    contract: dict
    children: tuple[ChildContract, ...]
    checks: dict

    def child(self, child_id: str) -> ChildContract:
        return next(c for c in self.children if c.child_id == child_id)

    @property
    def all_checks_pass(self) -> bool:
        return all(self.checks.values())


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def _units_for(child: dict, obligations: dict[str, dict]) -> tuple[tuple[Unit, ...], str]:
    units = []
    for oid in child["owned_obligation_ids"]:
        ob = obligations[oid]
        # Frozen convention: obligations id'd "C*" are the clarification/condition units (whether, how, specific, any,
        # effective); "M*" and "W*" carry content the child must establish.
        units.append(Unit(oid, ob["kind"], ob["text"], is_condition=oid.startswith("C")))
    primary = next((u.unit_id for u in units if not u.is_condition), units[0].unit_id)
    return tuple(units), primary


def build_children(contract: dict) -> tuple[ChildContract, ...]:
    hier = contract["hierarchy"]
    obligations = {o["id"]: o for o in hier["obligations"]}
    displays = {s["subquestion_id"]: s["obligations"][0]["model_display"] for s in hc.hierarchy_subquestions(contract)}
    out = []
    for child in hier["children"]:
        cid = child["child_id"]
        units, primary = _units_for(child, obligations)
        carrier = child["scope_carrier"]["wording"] if child["scope_carrier"] else None
        out.append(
            ChildContract(
                child_id=cid,
                parent=child["parent"],
                contract_text=displays[cid],
                contract_sha256=hc.sha256_text(displays[cid]),
                wording=child["wording"],
                wording_sha256=child["wording_sha256"],
                scope_carrier_wording=carrier,
                units=units,
                primary_unit_id=primary,
                pair_requirement_ids=tuple(
                    s["id"] for s in child["structural_requirements"] if s["id"].endswith("#pair")
                ),
                machine_side_constraints=tuple(
                    q for q in child["qualifications"] + child["requirements"] if not q.get("model_facing")
                ),
            )
        )
    return tuple(out)


def load_frozen(ab_root: Path | str = AB_ROOT) -> FrozenSubstrate:
    """Load the approved contract and run every identity check. Raises if the contract itself is not executable."""
    root = Path(ab_root)
    contract = json.loads((root / "runB" / "out" / "01_request_contract.json").read_text(encoding="utf-8"))
    hc.assert_executable(contract)  # recomputes the seal, the question hash and each child's wording hash
    children = build_children(contract)
    baseline = json.loads(
        (root / "child_evidence_diag" / "00_contracts_evidence_and_receipt.json").read_text(encoding="utf-8")
    )
    recorded = {c["child_id"]: c["approved_child_contract_as_shown_to_models"] for c in baseline["children"]}
    owned = sorted(u.unit_id for c in children for u in c.units)
    checks = {
        "question_sha256": contract["question_hash"] == QUESTION_SHA256,
        "hierarchy_integrity_sha256": contract["hierarchy"]["integrity_sha256"] == HIERARCHY_INTEGRITY_SHA256,
        "model_facing_sha256": hc.model_facing_sha256(contract) == MODEL_FACING_SHA256,
        "eleven_children_in_recorded_order": tuple(c.child_id for c in children) == CHILD_IDS,
        "contract_text_equals_baseline_recorded_display": all(
            c.contract_text == recorded[c.child_id] for c in children
        ),
        "every_unit_owned_exactly_once": owned == sorted(set(owned))
        and set(owned) == {o["id"] for o in contract["hierarchy"]["obligations"] if o["owner"] in CHILD_IDS},
    }
    return FrozenSubstrate(contract=contract, children=children, checks=checks)


def baseline_manifest(ab_root: Path | str = AB_ROOT) -> dict:
    """Hashes of the baseline artifacts that must not change: the completed run's outputs and both diagnostics."""
    root = Path(ab_root)
    rows = {}
    for sub in ("runB/out", "child_evidence_diag", "child_answer_diag", "receipts"):
        for path in sorted((root / sub).rglob("*")):
            if path.is_file() and "PRIVATE" not in path.name and path.suffix in {".json", ".jsonl", ".txt", ".md"}:
                rows[path.relative_to(root).as_posix()] = sha256_file(path)
    lib = json.loads((root / "runB" / "library.sqlite.fingerprint.json").read_text(encoding="utf-8"))
    return {
        "root": str(root),
        "library_fingerprint": lib,
        "files": rows,
        "expected": {
            "question_sha256": QUESTION_SHA256,
            "hierarchy_integrity_sha256": HIERARCHY_INTEGRITY_SHA256,
            "model_facing_sha256": MODEL_FACING_SHA256,
            "library_sha256": LIBRARY_SHA256,
            "model": MODEL,
            "model_digest": MODEL_DIGEST,
            "ollama_version": OLLAMA_VERSION,
        },
    }


def verify_baseline_unchanged(manifest: dict, ab_root: Path | str = AB_ROOT) -> list[str]:
    """Relative paths whose bytes no longer match the manifest (empty list == unchanged)."""
    root = Path(ab_root)
    changed = []
    for rel, digest in manifest["files"].items():
        path = root / rel
        if not path.is_file() or sha256_file(path) != digest:
            changed.append(rel)
    return changed


def make_disposable_library(
    dest_dir: Path | str = SLICE_ROOT, source: Path | str | None = None, *, expected_sha256: str = LIBRARY_SHA256
) -> Path:
    """Copy the frozen library (already byte-identical to the source) into the slice directory and fingerprint the copy.

    Refuses if the source does not carry the frozen hash; never writes the baseline copy in place. The copy is read-only by
    contract: every stage verifies its fingerprint before and after.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    src = Path(source) if source else AB_ROOT / "runB" / "library.sqlite"
    target = dest / "library.sqlite"
    if target.exists():
        raise FileExistsError(f"{target} already exists; refusing to overwrite a fingerprinted copy")
    if sha256_file(src) != expected_sha256:
        raise ValueError("the source library does not carry the frozen sha256; refusing to copy")
    shutil.copyfile(src, target)
    record = library_copy.freeze(target, dest / "library.sqlite.fingerprint.json")
    if record["sha256"] != expected_sha256:
        target.unlink()
        raise ValueError("the copied library does not carry the frozen sha256; copy removed")
    return target
