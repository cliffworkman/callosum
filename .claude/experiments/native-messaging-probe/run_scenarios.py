"""Drive the native-messaging failure-mode matrix for issue #61. EXPERIMENTAL HARNESS, not product code.

Scenarios (each = re-register the host manifest, launch a clean browser profile, observe what the
extension's sendNativeMessage callback reported):

  healthy          - manifest + host present, origin allow-listed          -> expect a handshake
  wrong_origin     - manifest lists a DIFFERENT extension id              -> expect a rejection
  stale_host_path  - manifest registered, host binary GONE                -> the packaged upgrade/uninstall case
  missing_manifest - registry key removed entirely                        -> Callosum never installed
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
HOST_NAME = "com.callosum.connector.probe"
REAL_ID = "hpmccheafnpmlokifdmajgihenkcnnih"  # observed: Windows unpacked id = sha256(path as UTF-16LE)
MANIFEST = HERE / "nm-manifest.json"
REG_KEY = rf"HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\{HOST_NAME}"


def ps(cmd: str) -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=60)


def set_registry(path_to_manifest: str | None) -> None:
    if path_to_manifest is None:
        ps(f"Remove-Item -Path '{REG_KEY}' -Force -ErrorAction SilentlyContinue")
        return
    ps(f"New-Item -Path '{REG_KEY}' -Force | Out-Null; Set-ItemProperty -Path '{REG_KEY}' -Name '(Default)' -Value '{path_to_manifest}'")


def write_manifest(host_path: Path, origin_id: str) -> None:
    MANIFEST.write_text(
        json.dumps(
            {
                "name": HOST_NAME,
                "description": "EXPERIMENTAL native-messaging feasibility probe for issue #61",
                "path": str(host_path),
                "type": "stdio",
                "allowed_origins": [f"chrome-extension://{origin_id}/"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run(scenario: str, collector: subprocess.Popen) -> dict:
    profile = Path(rf"C:\Users\cliff\AppData\Local\Temp\nm-probe-{scenario}")
    shutil.rmtree(profile, ignore_errors=True)
    proc = subprocess.Popen(
        [
            str(EDGE),
            f"--user-data-dir={profile}",
            f"--load-extension={HERE / 'extension'}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(22)
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
    time.sleep(2)
    return {}


def main() -> None:
    collector = subprocess.Popen(
        [sys.executable, str(HERE / "collector.py")], stdout=subprocess.PIPE, text=True, bufsize=1
    )
    time.sleep(1)
    scenarios = [
        ("healthy", HERE / "host.bat", REAL_ID, True),
        ("wrong_origin", HERE / "host.bat", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", True),
        ("stale_host_path", HERE / "gone" / "host.bat", REAL_ID, True),
        ("missing_manifest", HERE / "host.bat", REAL_ID, False),
    ]
    results = {}
    for name, host_path, origin, registered in scenarios:
        write_manifest(host_path, origin)
        set_registry(str(MANIFEST) if registered else None)
        with (HERE / "observed.jsonl").open("a", encoding="utf-8") as marker:
            marker.write(json.dumps({"scenario": name}) + "\n")
        print(f"--- scenario: {name} ---", flush=True)
        run(name, collector)
        results[name] = "see collector output above"
    collector.terminate()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
