"""New pre-execution manifest, with detached integrity hash and explicit unresolved dependencies."""

from pathlib import Path

from .contracts import ContractError
from .hashing import file_hash, read_json, write_json
from .validation import validate

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
MANIFEST = PACKAGE / "frozen" / "freeze_manifest_v0.json"


def validate_links(value):
    if isinstance(value, dict):
        if {"path", "sha256"} <= set(value):
            path = (ROOT / value["path"]).resolve()
            if not path.is_relative_to(ROOT) or file_hash(path) != value["sha256"]:
                raise ContractError("FROZEN_REFERENCE_HASH_MISMATCH:" + value["path"])
        for child in value.values():
            validate_links(child)
    elif isinstance(value, list):
        for child in value:
            validate_links(child)


def inventory_files():
    return sorted(
        p
        for p in PACKAGE.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and ".pytest_cache" not in p.parts
        and p.suffix in (".py", ".json", ".md")
        and p != MANIFEST
    )


def build(payload, *, target=MANIFEST):
    if payload.get("representation_packages", {}).get("R_0_6", {}).get("status") != "NOT_YET_AVAILABLE":
        raise ContractError("R_0_6_MUST_REMAIN_UNAVAILABLE")
    if payload.get("execution_authorized") is not False:
        raise ContractError("V0_MUST_NOT_AUTHORIZE_EXECUTION")
    result = dict(payload)
    result["file_hashes"] = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in inventory_files()}
    for ref in result["governing_sources"]:
        p = ROOT / ref["path"]
        if file_hash(p) != ref["sha256"]:
            raise ContractError("GOVERNING_SOURCE_HASH_MISMATCH")
    validate(result, read_json(PACKAGE / "schemas/freeze_manifest_v0.schema.json"))
    validate_links(result)
    write_json(target, result)
    Path(target).with_suffix(".sha256").write_text(file_hash(target) + "\n", encoding="ascii")
    return result


def verify(path=MANIFEST):
    path = Path(path)
    if file_hash(path) != path.with_suffix(".sha256").read_text().strip():
        raise ContractError("MANIFEST_HASH_MISMATCH")
    data = read_json(path)
    validate(data, read_json(PACKAGE / "schemas/freeze_manifest_v0.schema.json"))
    validate_links(data)
    if (
        data["execution_authorized"] is not False
        or data["representation_packages"]["R_0_6"]["status"] != "NOT_YET_AVAILABLE"
    ):
        raise ContractError("INVALID_PREFREEZE_STATE")
    for name, expected in data["file_hashes"].items():
        resolved = (ROOT / name).resolve()
        if not resolved.is_relative_to(ROOT) or file_hash(resolved) != expected:
            raise ContractError("FROZEN_INPUT_HASH_MISMATCH:" + name)
    for ref in data["governing_sources"]:
        if file_hash(ROOT / ref["path"]) != ref["sha256"]:
            raise ContractError("GOVERNING_SOURCE_HASH_MISMATCH")
    return {"status": "VERIFIED", "files": len(data["file_hashes"]), "execution_authorized": False}
