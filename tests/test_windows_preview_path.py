"""Windows transport regression for the packaged native host path."""

import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONNECTOR = ROOT / "app/desktop-shell/resources/connector/callosum-connector.exe"
ORIGIN = "chrome-extension://afmdgjbnfijcidfemekgbmagnhekfefj/"


@pytest.mark.skipif(os.name != "nt", reason="Windows native-messaging transport")
@pytest.mark.skipif(not CONNECTOR.is_file(), reason="requires packaging/stage_connector.py")
def test_cmd_can_launch_normalized_staged_connector(tmp_path):
    directory = tmp_path / "Callosum QA Zoë"
    directory.mkdir()
    executable = directory / CONNECTOR.name
    shutil.copy2(CONNECTOR, executable)
    payload = json.dumps({"protocol_version": 0}).encode()
    frame = struct.pack("<I", len(payload)) + payload
    # cmd /s /c strips the outer quotes. Pass the full command line so Python
    # does not apply C-runtime backslash escaping to cmd's nested quotes.
    command = f'"{os.environ["COMSPEC"]}" /d /s /c ""{executable}" {ORIGIN}"'
    result = subprocess.run(
        command,
        input=frame,
        capture_output=True,
        cwd=executable.parent,
        creationflags=0x08000000,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.stderr == b""
    assert len(result.stdout) >= 4
    length = struct.unpack("<I", result.stdout[:4])[0]
    assert len(result.stdout) == length + 4
    reply = json.loads(result.stdout[4:])
    assert reply["runtime_state"] == "version_incompatible"
    assert reply["connector_identity"] == "org.callosum.connector"
