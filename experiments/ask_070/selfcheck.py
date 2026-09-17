"""Run the synthetic suite under process-local offline guards."""

import sys
from pathlib import Path

from .offline_guard import offline_guard


def main():
    import pytest

    with offline_guard():
        return pytest.main([str(Path(__file__).parent / "tests"), "-q", "-p", "no:cacheprovider"])


if __name__ == "__main__":
    sys.exit(main())
