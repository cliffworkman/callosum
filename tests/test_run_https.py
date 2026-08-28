"""tools/run_https.py (inc 508 sys.path fix; inc 511 Remote-Access exemption).

Unlike most tools/ scripts, inc 511 gives this one real security-relevant behavior (it exempts its own process
from the Remote Access token gate), so — unlike the sys.path fix, which had no test coverage per inc-508's own
notes — this specific claim gets a real regression test: a future refactor that drops the env-var line would
silently reopen exactly the friction inc 511 fixed.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from tools import run_https


def test_main_sets_the_disable_hatch_before_starting_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CALLOSUM_DISABLE_REMOTE_ACCESS", raising=False)
    monkeypatch.setattr(run_https, "_dev_cert_paths", lambda: ("fake.crt", "fake.key"))
    fake_uvicorn = MagicMock()
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    assert run_https.main() == 0

    import os

    assert os.environ.get("CALLOSUM_DISABLE_REMOTE_ACCESS") == "1"
    fake_uvicorn.run.assert_called_once()
    kwargs = fake_uvicorn.run.call_args.kwargs
    assert kwargs["host"] == "localhost"
    assert kwargs["ssl_certfile"] == "fake.crt"
    assert kwargs["ssl_keyfile"] == "fake.key"


def test_main_refuses_without_a_dev_cert(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(run_https, "_dev_cert_paths", lambda: (None, None))
    assert run_https.main() == 1
    assert "office-addin-dev-certs" in capsys.readouterr().err
