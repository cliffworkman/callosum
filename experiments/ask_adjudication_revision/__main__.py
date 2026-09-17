"""Synthetic preparation only. No archive input, sealed key, or live submission command."""

import argparse
import json
import sys

from .capability import capability_template, suite
from .copy_capability import copy_suite, packet_from_receipt
from .core import ROSTER, canonical, identifier, require
from .guard import offline_guard
from .manifest import implementation_manifest
from .storage import Store


def main(argv=None, *, stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            print('{"success": false, "error": "INVALID_COMMAND"}', file=stdout)
            raise SystemExit(2)

    parser = SafeParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-capability", help="create synthetic packets; do not contact surfaces")
    prepare.add_argument("--format", choices=("txt", "json", "csv", "markdown"), default="txt")
    prepare.add_argument("--fixture", choices=("counting-v1", "literal-copy-v2"), default="counting-v1")
    prepare.add_argument("--intended-count", type=int, default=8)
    prepare.add_argument("--intended-padding", type=int, default=2048)
    prepare.add_argument("--largest-padding", type=int, default=16000)
    prepare.add_argument("--response-width", type=int, default=160)
    capture = commands.add_parser(
        "capture-capability", help="non-echo stdin sink for responses to owned synthetic packets"
    )
    capture.add_argument("--run", required=True)
    capture.add_argument("--packet-id", required=True)
    capture.add_argument("--surface", choices=tuple(dict(ROSTER)), required=True)
    capture.add_argument("--attempt", type=int, choices=(1, 2), default=1)
    capture.add_argument("--amendment-sha256")
    amendment = commands.add_parser("record-mechanical-amendment", help="store an amendment from non-echo stdin")
    amendment.add_argument("--run", required=True)
    amendment.add_argument("--id", required=True)
    verify = commands.add_parser("verify-store")
    verify.add_argument("--run", required=True)
    commands.add_parser("demo-synthetic", help="simulate both studies using fabricated responses and labels")
    args = parser.parse_args(argv)
    try:
        with offline_guard():
            if args.command == "prepare-capability":
                packets = suite(
                    intended_count=args.intended_count,
                    intended_padding=args.intended_padding,
                    largest_padding=args.largest_padding,
                    response_width=args.response_width,
                    format=args.format,
                )
                if args.fixture == "literal-copy-v2":
                    require(
                        (
                            args.format,
                            args.intended_count,
                            args.intended_padding,
                            args.largest_padding,
                            args.response_width,
                        )
                        == ("txt", 8, 2048, 16000, 160),
                        "V2_ENVELOPE_IS_FIXED",
                    )
                    packets = copy_suite()
                # Validate/render before creating any output directory.
                receipts = [p.receipt() for p in packets]
                store = Store.create()
                store.write("implementation_manifest.json", canonical(implementation_manifest()))
                store.write(
                    "capability_manifest.json",
                    canonical(
                        {
                            "origin": "SYNTHETIC",
                            "packets": receipts,
                            "all_surfaces": "UNTESTED",
                            "live_submission_implemented": False,
                        }
                    ),
                )
                for packet in packets:
                    store.write(f"{packet.packet_id}.txt", packet.payload, kind="SYNTHETIC_CAPABILITY_PACKET")
                for sid, label in ROSTER:
                    store.write(f"{sid}_capability_template.json", canonical(capability_template(sid, label)))
                result = {"prepared": True, "run": str(store.root), "inference_calls": 0, **store.verify()}
            elif args.command == "capture-capability":
                require(not stdin.isatty(), "NON_ECHO_INPUT_REQUIRED")
                identifier(args.packet_id)
                store = Store(args.run)
                store.verify()
                manifest = json.loads(store.read("capability_manifest.json"))
                record = next((p for p in manifest["packets"] if p["packet_id"] == args.packet_id), None)
                require(record is not None, "UNKNOWN_CAPABILITY_PACKET")
                packet = packet_from_receipt(record)
                raw = stdin.buffer.read(8 * 1024 * 1024 + 1)
                result = store.capture(
                    packet, raw, surface_id=args.surface, attempt=args.attempt, amendment_id=args.amendment_sha256
                )
            elif args.command == "record-mechanical-amendment":
                require(not stdin.isatty(), "NON_ECHO_INPUT_REQUIRED")
                identifier(args.id)
                store = Store(args.run)
                store.verify()
                raw = stdin.buffer.read(65537)
                require(len(raw) <= 65536, "AMENDMENT_SIZE_LIMIT")
                value = json.loads(raw)
                fields = {
                    "what",
                    "why",
                    "when_utc",
                    "semantic_results_visible",
                    "cliff_blinded",
                    "consequences",
                    "artifact_hashes",
                }
                require(isinstance(value, dict) and set(value) == fields, "AMENDMENT_FIELDS_REQUIRED")
                require(
                    value["semantic_results_visible"] is False and value["cliff_blinded"] is True,
                    "BLINDING_REVIEW_REQUIRED",
                )
                require(
                    all(value[k] for k in ("what", "why", "when_utc", "consequences", "artifact_hashes")),
                    "AMENDMENT_INCOMPLETE",
                )
                result = store.write(f"amendment_{args.id}.json", canonical(value), kind="MECHANICAL_AMENDMENT")
            elif args.command == "verify-store":
                result = Store(args.run).verify()
            else:
                from .demo import run_demo

                store = run_demo()
                result = {"synthetic_demo_passed": True, "run": str(store.root), "inference_calls": 0, **store.verify()}
        print(json.dumps(result), file=stdout)
        return 0
    except Exception:
        # Never include exception repr/args, traceback, raw text, labels, or caller input.
        print('{"success": false, "error": "OPERATION_BLOCKED_OR_INVALID"}', file=stdout)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
