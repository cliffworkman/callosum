"""Browser distribution policy and historical store-ID ratchet. Does not publish anything."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from connector_identity import is_valid_extension_id, validate_identity

ROOT = Path(__file__).resolve().parents[3]
IDENTITY = "app/desktop-shell/connector/identity.json"
BROKEN_INTEL_RUNTIMES = {
    "macos-x86_64-py3.11-s1-6d36a5056fd72fbd",
    "macos-x86_64-py3.11-s1-73624c15ff4d9219",
}


def validate_release(identity: dict, previous: list[dict] = ()) -> list[str]:
    problems = validate_identity(identity)
    channel = identity.get("release_channel", "unreleased")
    released = identity.get("released", False)
    if not isinstance(released, bool) or channel not in {"unreleased", "manual_preview", "store"}:
        problems.append("invalid browser-capture release state")
    if channel == "manual_preview" and not identity.get("preview_extension_id"):
        problems.append("manual_preview requires a separate verified preview identity")
    # `released` is the store-release ratchet; preview is an explicit, separately disclosed channel.
    if (channel == "store") != (released is True):
        problems.append("store distribution and released=true must be enabled together")
    production = identity.get("production_extension_ids", [])
    if released is True:
        stores = identity.get("store_extension_ids", {})
        if not isinstance(stores, dict) or any(
            not is_valid_extension_id(stores.get(store)) or stores.get(store) not in production
            for store in ("chrome", "edge")
        ):
            problems.append("store release requires confirmed Chrome and Edge IDs in production_extension_ids")
    for old in previous:
        if old.get("released") is True:
            if released is not True:
                problems.append("an earlier store release cannot revert to unreleased or preview-only")
            if not set(old.get("production_extension_ids", [])).issubset(set(production)):
                problems.append("previously released store IDs cannot disappear without a reviewed migration")
    return problems


def previous_identities(root: Path = ROOT) -> list[dict]:
    if subprocess.check_output(["git", "rev-parse", "--is-shallow-repository"], cwd=root, text=True).strip() != "false":
        raise ValueError("Release identity ratchet requires full git history and tags")
    # Include tags on other branches too: releasing an older branch must not reset store identity.
    tags = subprocess.check_output(["git", "tag", "--list", "v*"], cwd=root, text=True).splitlines()
    previous = []
    for tag in tags:
        result = subprocess.run(
            ["git", "show", f"{tag}:{IDENTITY}"], cwd=root, capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            previous.append(json.loads(result.stdout))
    return previous


def validate_runtime(inputs: dict) -> list[str]:
    runtime_id = inputs["platforms"]["macos-x86_64"]["runtime_id"]
    return (
        [
            "Public release blocked: known-broken pristine Intel runtime; integrate the verified immutable correction first"
        ]
        if runtime_id in BROKEN_INTEL_RUNTIMES
        else []
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-release", action="store_true")
    args = parser.parse_args()
    identity = json.loads((ROOT / IDENTITY).read_text(encoding="utf-8"))
    problems = validate_release(identity, previous_identities() if args.public_release else [])
    if args.public_release:
        inputs = json.loads(
            (ROOT / "app/desktop-shell/packaging/python-runtime-inputs.json").read_text(encoding="utf-8")
        )
        problems.extend(validate_runtime(inputs))
    if problems:
        raise SystemExit("\n".join(problems))
    print("Browser capture identity/release policy verified")
