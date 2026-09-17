"""Entry point: build the blinded Cliff adjudication slice, then validate it.

Run:  python -m experiments.ask_cli_revised.calibration.run06a_cliff.run_adjudication

Deterministic + offline. Prints a blind-safe summary only — it never prints the
specimen -> style/unit/canonical identity mapping.
"""

from __future__ import annotations

import sys

from . import build, selfcheck


def main() -> int:
    out = build.build()
    ok = selfcheck.run(out["out_dir"])
    print()
    print("Output directory:")
    print(f"  {out['out_dir']}")
    print()
    print("Hand back to Cliff — open and complete this file:")
    print(f"  {out['md_path'].name}")
    print("(The JSON template and manifest were generated and validated alongside it.)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
