"""Run the package tests with every socket refused, proving an offline suite makes no network call.

    python -m experiments.ask_cli_revised.contract_directed.offline_pytest [pytest args]

Two tests exercise the endpoint guard's own mechanics against the real socket layer (they need an unpatched socket to prove the
guard lets the isolated endpoint through and restores itself); they run in the ordinary suite and are deselected here.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import pytest  # noqa: E402

from experiments.ask_cli_revised.contract_directed import endpoint_guard  # noqa: E402

GUARD_MECHANICS = (
    "test_coverage_budget_guard.py::EndpointGuardTests::test_isolated_only_lets_the_isolated_endpoint_through_to_the_real_socket",
    "test_coverage_budget_guard.py::EndpointGuardTests::test_refuse_all_refuses_even_loopback_and_the_patch_is_removed_on_exit",
)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:]) or ["experiments/ask_cli_revised/contract_directed", "-q"]
    deselect = [f"--deselect=experiments/ask_cli_revised/contract_directed/{name}" for name in GUARD_MECHANICS]
    with endpoint_guard.refuse_all():
        return int(pytest.main(args + deselect))


if __name__ == "__main__":
    sys.exit(main())
