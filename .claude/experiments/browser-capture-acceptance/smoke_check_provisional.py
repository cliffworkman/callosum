"""Fast direct-HTTP smoke check of the provisional-capture contract against the freshly rebuilt
packaged binary -- BEFORE trusting an expensive real-Edge cycle. Bypasses Edge/native-messaging
entirely (raw HTTP, reading the real pairing secret straight off disk) to prove the backend contract
itself is live in the rebuilt binary. Reuses the acceptance harness's proven isolate/restore/health
helpers rather than re-implementing that safety-critical logic.

Throwaway verification tool, not part of the committed acceptance evidence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import run_acceptance_AtoE as base  # noqa: E402
from run_acceptance_AtoE import (  # noqa: E402
    APP_DATA,
    SHELL_EXE,
    db_connect,
    db_path,
    fail,
    kill_edge,
    log,
    sha256_of,
    shell_running,
    wait_for_health,
)

import contextlib
import os
from datetime import datetime, timezone


def main() -> int:
    if not SHELL_EXE.is_file():
        fail(f"packaged binary not found: {SHELL_EXE}")
    if shell_running():
        fail("installed Callosum is still running; close it first")
    kill_edge()

    identity = json.loads((ROOT / "app" / "desktop-shell" / "connector" / "identity.json").read_text(encoding="utf-8"))
    if identity.get("production_extension_ids") != []:
        fail("production_extension_ids is not empty -- refusing to run")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    parked = APP_DATA.with_name(f"com.callosum.desktop.real-{stamp}")
    had_real_dir = APP_DATA.exists()
    baseline_hash = baseline_size = None
    if had_real_dir and db_path().exists():
        baseline_hash = sha256_of(db_path())
        baseline_size = db_path().stat().st_size
        log(f"baseline real callosum.sqlite: sha256={baseline_hash} size={baseline_size}")
    if had_real_dir:
        APP_DATA.rename(parked)
        log(f"[isolate] real app-data parked at {parked.name}")

    shell_proc = None
    try:
        disposable = ROOT / ".local" / "smoke-disposable-library"
        shutil.rmtree(disposable, ignore_errors=True)
        disposable.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "CALLOSUM_LIBRARY_DIR_OVERRIDE": str(disposable)}
        shell_proc = subprocess.Popen([str(SHELL_EXE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        port = wait_for_health()
        log(f"backend healthy on port {port}")

        # Real pairing secret lives beside the (unisolated) real settings file -- fine, it carries no
        # user content, just a per-install random secret.
        from app.backend.app_settings import settings_path

        pairing_path = settings_path().parent / "capture-pairing.json"
        deadline = time.monotonic() + 30
        secret = None
        while time.monotonic() < deadline:
            if pairing_path.is_file():
                secret = json.loads(pairing_path.read_text(encoding="utf-8")).get("pairing_secret")
                if secret:
                    break
            time.sleep(0.5)
        if not secret:
            fail("pairing secret never appeared")
        log("pairing secret read")

        base_url = f"http://127.0.0.1:{port}"

        def post(path: str, body: bytes, headers: dict) -> tuple[int, dict]:
            req = urllib.request.Request(base_url + path, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))

        status, session = post(
            "/capture/session",
            json.dumps({"pairing_secret": secret}).encode(),
            {"Content-Type": "application/json"},
        )
        assert status == 200, session
        token = session["session_token"]
        log("session token obtained")

        cap_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "x-callosum-capture": "browser-capture-v1",
            "Idempotency-Key": "smoke-check-1",
        }
        envelope = {
            "envelope_version": 1,
            "source_url": "https://example.org/smoke.pdf",
            "captured_at": "2026-09-16T00:00:00Z",
            "producer_kind": "direct-pdf",
            "producer_label": "smoke-check",
            "title": "smoke.pdf",
            "pdf_bytes_from_active_tab": True,
        }
        status, outcome = post("/capture/item", json.dumps(envelope).encode(), cap_headers)
        log(f"/capture/item -> {status} {outcome}")
        assert status == 200, outcome
        assert outcome["status"] == "direct_pdf_identity_unresolved", outcome
        assert outcome["pdf_accepted"] is True, "REGRESSION: bytes not accepted for provisional capture"
        assert outcome["pdf_reason"] == "provisional_capture", outcome
        assert outcome["capture_id"], "REGRESSION: no capture_id minted"
        capture_id = outcome["capture_id"]

        import fitz

        pdf_path = disposable.parent / "smoke.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(str(pdf_path))
        doc.close()
        pdf_bytes = pdf_path.read_bytes()

        pdf_headers = {
            "Content-Type": "application/pdf",
            "Authorization": f"Bearer {token}",
            "x-callosum-capture": "browser-capture-v1",
        }
        status, pdf_outcome = post(f"/capture/item/{capture_id}/pdf", pdf_bytes, pdf_headers)
        log(f"/capture/item/{{id}}/pdf -> {status} {pdf_outcome}")
        assert status == 200, pdf_outcome
        assert pdf_outcome["status"] == "direct_pdf_queued_for_review", pdf_outcome
        assert pdf_outcome["paper_id"] is None, "REGRESSION: an anonymous paper was created"

        with contextlib.closing(db_connect()) as conn:
            total_papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            artifacts = conn.execute("SELECT * FROM provisional_artifacts").fetchall()
        assert total_papers == 0, f"REGRESSION: {total_papers} papers exist"
        assert len(artifacts) == 1, artifacts
        log(f"provisional_artifacts row: {artifacts[0]}")

        queue_files = list((disposable / "_Import Queue").glob("*.pdf"))
        assert len(queue_files) == 1, queue_files
        log(f"Import Queue file present: {queue_files[0].name}")

        # GET/DELETE /library/import-queue (plain, unauthenticated -- desktop-UI surface)
        with urllib.request.urlopen(base_url + "/library/import-queue", timeout=10) as resp:
            listed = json.loads(resp.read().decode("utf-8"))
        assert len(listed["items"]) == 1, listed
        artifact_id = listed["items"][0]["artifact_id"]
        log(f"GET /library/import-queue -> {listed}")

        req = urllib.request.Request(
            f"{base_url}/library/import-queue/{artifact_id}", method="DELETE"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 204, resp.status
        log("DELETE /library/import-queue/{id} -> 204")

        with urllib.request.urlopen(base_url + "/library/import-queue", timeout=10) as resp:
            listed_after = json.loads(resp.read().decode("utf-8"))
        assert listed_after["items"] == [], listed_after
        assert list((disposable / "_Import Queue").glob("*.pdf")) == [], "queue file not deleted"

        print("\nSMOKE CHECK: ALL ASSERTIONS PASSED\n")
        return 0
    finally:
        kill_edge()
        if shell_proc is not None:
            shell_proc.terminate()
            try:
                shell_proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                shell_proc.kill()
        subprocess.run(["taskkill", "/F", "/T", "/IM", "callosum-shell.exe"], capture_output=True)
        time.sleep(2)
        if had_real_dir:
            for _ in range(5):
                if not APP_DATA.exists():
                    break
                shutil.rmtree(APP_DATA, ignore_errors=True)
                if APP_DATA.exists():
                    time.sleep(2)
            if APP_DATA.exists():
                print(f"WARNING: could not remove disposable dir; real data still at {parked}", file=sys.stderr)
            else:
                parked.rename(APP_DATA)
                log("[restore] real app-data directory restored")
                if baseline_hash and db_path().exists():
                    restored_hash = sha256_of(db_path())
                    restored_size = db_path().stat().st_size
                    if restored_hash == baseline_hash and restored_size == baseline_size:
                        log(f"[verify] restored callosum.sqlite matches baseline: sha256={restored_hash}")
                    else:
                        print("CRITICAL: restored database does NOT match baseline!", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
