"""Relevant existing deterministic tests; allows app definitions, denies actual inference entrypoints."""

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

from .hashing import write_json
from .offline_guard import COUNTERS, offline_guard


def main(out):
    # Only pytest startup is outside the guard; no test/app module is imported here.
    import pytest

    modules = [
        "experiments.ask_cli.selfcheck",
        "experiments.ask_cli_revised.selfcheck",
        "experiments.ask_cli_revised.calibration.selfcheck",
        "experiments.ask_cli_revised.calibration.run06.selfcheck",
        "experiments.ask_cli_revised.calibration.run06a.selfcheck",
        "experiments.ask_cli_revised.calibration.run06b.selfcheck",
    ]
    results = {}
    with offline_guard(allow_app_definitions=True):
        for module in modules:
            with patch.object(sys, "argv", [module]):
                code = importlib.import_module(module).main()
            results[module] = code
            if code not in (0, None):
                raise AssertionError(module)
        files = [
            "tests/test_query_planner.py",
            "experiments/ask_cli_revised/test_selection_contract.py",
            "experiments/ask_cli_revised/test_request_contract.py",
            "experiments/ask_cli_revised/test_ledger_renderer.py",
            "experiments/ask_cli_revised/test_cli_060.py",
        ]
        results["pytest_exit_code"] = pytest.main(
            [*files, "-q", "-p", "no:cacheprovider", "--basetemp", str(Path(out) / "pytest")]
        )
        results["guard_denials"] = dict(COUNTERS)
        write_json(Path(out) / "regression-results.json", results)
    return results["pytest_exit_code"]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    raise SystemExit(main(args.out))
