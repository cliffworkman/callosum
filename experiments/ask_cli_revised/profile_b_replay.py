"""Offline snapshot transport for explicit profile B. Never invokes a producer/model."""

import base64
from pathlib import Path

from experiments.ask_cli_revised import profile_b
from experiments.ask_cli_revised._layerc_common import PROFILE, canonical, require
from experiments.ask_cli_revised._producer_schema import decode
from experiments.ask_cli_revised.producer_authorization import ProducerInputBundle


def replay(snapshot_path, output_dir):
    # File locations select untrusted data only; D1's fixed loader owns trust configuration.
    raw = decode(Path(snapshot_path).read_bytes())
    require(
        set(raw) == {"schema", "map", "sealed_bytes", "authored_contract", "producer_receipt", "input_bundle"},
        "profile-B snapshot fields",
    )
    require(raw["schema"] == "profile-b-input-snapshot-v1", "profile-B snapshot schema")
    bundle = raw["input_bundle"]
    require(
        set(bundle) == {"files", "nominations", "replay_requests", "ownership_context", "recovery_targets"},
        "snapshot bundle fields",
    )
    inputs = ProducerInputBundle(
        {k: base64.b64decode(v, validate=True) for k, v in bundle["files"].items()},
        bundle["nominations"],
        bundle["replay_requests"],
        bundle["ownership_context"],
        bundle["recovery_targets"],
    )
    result = profile_b.build_profile_b(
        raw["map"],
        base64.b64decode(raw["sealed_bytes"], validate=True),
        raw["authored_contract"],
        raw["producer_receipt"],
        input_bundle=inputs,
        profile=PROFILE,
    )
    destination = Path(output_dir).resolve()
    root = Path(__file__).resolve().parents[2]
    require(
        not destination.is_relative_to(root) or destination.is_relative_to(root / ".local/i4-4d2"),
        "dedicated profile-B output required",
    )
    require(not destination.exists(), "profile-B output directory must be new")
    destination.mkdir(parents=True)
    (destination / "profile_b_output.json").write_text(canonical(result) + "\n", encoding="utf-8")
    (destination / "deterministic_layer1.md").write_text(result["render"]["layer1"], encoding="utf-8")
    return result
