"""Packaged acceptance harness for browser capture (#61 Phase 2). See README.md in this directory
for what this proves, why it registers the DEV connector rather than running the real installer,
and its current (unexecuted) status.

Isolation contract, identical in spirit to the native-messaging probe's own
`observe_packaged_role.py` (issue #61 prerequisite verification): refuse to run if Callosum is
already running; rename the REAL %APPDATA%\\com.callosum.desktop out of the way; let the packaged
build create a fresh, disposable app-data directory; run the case; delete the disposable directory;
restore the real directory unchanged. If any step of that cannot be completed, this STOPS rather
than falling back to the real library.

Usage:
    python .claude/experiments/browser-capture-acceptance/acceptance_harness.py --case A
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from fixtures import serve_fixtures  # noqa: E402 - sibling module, sys.path already has HERE via script invocation

from tools.run_dev import _clear_dev_connector, _dev_connector_binary, _register_dev_connector  # noqa: E402

APP_DATA = Path(os.environ["APPDATA"]) / "com.callosum.desktop"
SHELL_EXE = ROOT / "app" / "desktop-shell" / "src-tauri" / "target" / "release" / "callosum-shell.exe"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
HEALTH_TIMEOUT_S = 180

CASES = {
    "A": "scholarly HTML -> paper row with capture:browser provenance, paper embedding present",
    "B": "direct PDF -> attachment row + chunk embeddings, or a documented unsupported state",
    "C": "already present -> no second live row; status already_present",
    "D": "Trash -> deleted_at intact, zero live rows, status in_trash",
    "E": "unsafe attachment state -> attachment count unchanged, status attachment_review_required",
}


def fail(message: str) -> None:
    print(f"STOP: {message}", file=sys.stderr)
    raise SystemExit(1)


def shell_running() -> bool:
    out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=60).stdout.lower()
    return "callosum-shell.exe" in out


def db_path() -> Path:
    return APP_DATA / "callosum.sqlite"


def wait_for_health() -> int:
    port_file = APP_DATA / "last-port.txt"
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    while time.monotonic() < deadline:
        if port_file.is_file():
            try:
                port = int(port_file.read_text(encoding="utf-8").strip())
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                    if resp.status == 200:
                        return port
            except Exception:  # noqa: BLE001 - keep polling
                pass
        time.sleep(1.0)
    fail(f"backend never became healthy within {HEALTH_TIMEOUT_S}s")
    raise AssertionError("unreachable")


def seed_trashed_paper(conn: sqlite3.Connection) -> None:
    """Case D: the fixture's DOI already exists and is soft-deleted, before Edge ever opens."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO papers (title, doi, csl_json, imported_source, deleted_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("A Fixture Scholarly Paper", "10.9999/fixture-a", "{}", "capture:browser", now, now, now),
    )
    conn.commit()


def seed_existing_attachment(conn: sqlite3.Connection) -> None:
    """Case E: the fixture's DOI already exists WITH a live attachment, so a direct-PDF capture
    targeting the same identity must be refused for review rather than silently overwritten."""
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO papers (title, doi, csl_json, imported_source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("A Fixture Scholarly Paper", "10.9999/fixture-a", "{}", "capture:browser", now, now),
    )
    paper_id = cur.lastrowid
    conn.execute(
        "INSERT INTO attachments (paper_id, storage_mode, availability, content_type) VALUES (?, ?, ?, ?)",
        (paper_id, "managed", "available", "application/pdf"),
    )
    conn.commit()


def report_library_state(case: str) -> None:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, title, doi, imported_source, deleted_at FROM papers WHERE doi = '10.9999/fixture-a'"
    ).fetchall()
    print(f"\n--- Library state for case {case} (papers.doi = 10.9999/fixture-a) ---")
    for row in rows:
        attachments = conn.execute("SELECT COUNT(*) FROM attachments WHERE paper_id = ?", (row["id"],)).fetchone()[0]
        embeddings = conn.execute("SELECT COUNT(*) FROM embeddings WHERE paper_id = ?", (row["id"],)).fetchone()[0]
        print(
            f"  id={row['id']} title={row['title']!r} deleted_at={row['deleted_at']} "
            f"attachments={attachments} embeddings={embeddings}"
        )
    if not rows:
        print("  (no matching paper -- expected for a case that hasn't captured yet)")
    conn.close()
    print(f"Expected for case {case}: {CASES[case]}")
    input("Confirm the extension's rendered badge/tooltip agreed with this, then press Enter to continue...")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", choices=sorted(CASES), required=True)
    args = parser.parse_args()

    if not SHELL_EXE.is_file():
        fail(f"packaged binary not found: {SHELL_EXE} -- build it first (npx tauri build, or cargo build --release)")
    if not EDGE.is_file():
        fail(f"Edge not found at {EDGE}")
    if shell_running():
        fail("installed Callosum is still running; close it before isolating the app-data directory")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    parked = APP_DATA.with_name(f"com.callosum.desktop.real-{stamp}")
    had_real_dir = APP_DATA.exists()
    if had_real_dir:
        try:
            APP_DATA.rename(parked)
        except OSError as exc:
            fail(f"could not rename the real app-data directory ({exc}); refusing to run against it")
        print(f"[isolate] real app-data parked at {parked.name}")

    shell_proc: subprocess.Popen | None = None
    edge_proc: subprocess.Popen | None = None
    fixture_server = None
    try:
        shell_proc = subprocess.Popen([str(SHELL_EXE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[run] packaged binary started against the disposable directory")
        wait_for_health()
        print("[run] backend healthy")

        if args.case == "D":
            seed_trashed_paper(sqlite3.connect(db_path()))
        elif args.case == "E":
            seed_existing_attachment(sqlite3.connect(db_path()))

        _clear_dev_connector()
        _register_dev_connector()
        if _dev_connector_binary() is None:
            fail("dev connector binary not found -- run `cargo build --bin callosum_connector` first")

        subprocess.run(
            [sys.executable, str(ROOT / "app" / "desktop-shell" / "extension" / "dev" / "build_dev_manifest.py")],
            check=True,
        )
        dev_extension_dir = ROOT / ".local" / "dev-extension"

        fixture_dir = ROOT / ".local" / "acceptance-fixtures"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        _thread, fixture_server, port = serve_fixtures(fixture_dir)
        url = {
            "A": f"http://127.0.0.1:{port}/scholarly.html",
            "B": f"http://127.0.0.1:{port}/paper.pdf",
            "C": f"http://127.0.0.1:{port}/scholarly.html",
            "D": f"http://127.0.0.1:{port}/scholarly.html",
            "E": f"http://127.0.0.1:{port}/paper.pdf",
        }[args.case]

        edge_profile = ROOT / ".local" / "acceptance-edge-profile"
        shutil.rmtree(edge_profile, ignore_errors=True)
        edge_proc = subprocess.Popen(
            [
                str(EDGE),
                f"--user-data-dir={edge_profile}",
                f"--load-extension={dev_extension_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                url,
            ]
        )
        print(f"\n[edge] opened {url}")
        print(f"[edge] Click the 'Callosum Capture' toolbar icon now. ({CASES[args.case]})")
        report_library_state(args.case)

    finally:
        if edge_proc is not None:
            edge_proc.terminate()
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
        if fixture_server is not None:
            fixture_server.shutdown()
        _clear_dev_connector()
        if shell_proc is not None:
            shell_proc.terminate()
            try:
                shell_proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                shell_proc.kill()
        subprocess.run(["taskkill", "/F", "/IM", "callosum-shell.exe"], capture_output=True)
        time.sleep(2)

        if had_real_dir:
            if APP_DATA.exists():
                shutil.rmtree(APP_DATA, ignore_errors=True)
            if APP_DATA.exists():
                print(
                    f"WARNING: could not delete the disposable directory; the real one is still at {parked}",
                    file=sys.stderr,
                )
            else:
                parked.rename(APP_DATA)
                print("[restore] real app-data directory restored unchanged")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
