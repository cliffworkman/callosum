"""Fast direct-HTTP smoke check of the Import Queue review-loop endpoints against the freshly rebuilt
packaged binary -- BEFORE trusting the expensive real-Edge R1-R4 cycle. Bypasses Edge/native-messaging
for the CAPTURE step too (same pairing-secret-off-disk trick as smoke_check_provisional.py), so this
whole check is a single fast round trip. Throwaway verification tool, not part of committed evidence.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

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
        disposable = ROOT / ".local" / "smoke-disposable-library-review"
        shutil.rmtree(disposable, ignore_errors=True)
        disposable.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "CALLOSUM_LIBRARY_DIR_OVERRIDE": str(disposable)}
        shell_proc = subprocess.Popen([str(SHELL_EXE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        port = wait_for_health()
        log(f"backend healthy on port {port}")

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

        base_url = f"http://127.0.0.1:{port}"

        def post(path: str, body: bytes, headers: dict) -> tuple[int, dict]:
            req = urllib.request.Request(base_url + path, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))

        status, session = post(
            "/capture/session", json.dumps({"pairing_secret": secret}).encode(), {"Content-Type": "application/json"}
        )
        assert status == 200, session
        token = session["session_token"]

        cap_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "x-callosum-capture": "browser-capture-v1",
            "Idempotency-Key": "smoke-review-1",
        }
        envelope = {
            "envelope_version": 1,
            "source_url": "https://example.org/smoke-review.pdf",
            "captured_at": "2026-09-17T00:00:00Z",
            "producer_kind": "direct-pdf",
            "producer_label": "smoke-check",
            "title": "smoke-review.pdf",
            "pdf_bytes_from_active_tab": True,
        }
        status, outcome = post("/capture/item", json.dumps(envelope).encode(), cap_headers)
        assert status == 200 and outcome["pdf_reason"] == "provisional_capture", outcome
        capture_id = outcome["capture_id"]

        import fitz

        pdf_path = disposable.parent / "smoke-review.pdf"
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
        assert status == 200 and pdf_outcome["status"] == "direct_pdf_queued_for_review", pdf_outcome
        log(f"captured + queued: {pdf_outcome}")

        with contextlib.closing(db_connect()):
            pass  # not used further; db_connect import kept for parity with the sibling smoke script

        # --- NEW review-loop endpoints, exercised directly ---
        with urllib.request.urlopen(base_url + "/library/import-queue", timeout=10) as resp:
            listed = json.loads(resp.read().decode("utf-8"))
        assert len(listed["items"]) == 1, listed
        artifact_id = listed["items"][0]["artifact_id"]
        log(f"GET /library/import-queue -> 1 item, artifact_id={artifact_id}")

        with urllib.request.urlopen(f"{base_url}/library/import-queue/{artifact_id}", timeout=10) as resp:
            detail = json.loads(resp.read().decode("utf-8"))
        assert "candidates" in detail["evidence"], detail
        log("GET /library/import-queue/{id} -> detail with evidence OK")

        req = urllib.request.Request(f"{base_url}/library/import-queue/{artifact_id}/pdf", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            preview_status = resp.status
            preview_bytes = resp.read()
        assert preview_status == 200 and preview_bytes.startswith(b"%PDF-"), "preview stream did not return real bytes"
        log(f"GET /library/import-queue/{{id}}/pdf -> {len(preview_bytes)} real PDF bytes")

        status, preview_doi = post(
            f"/library/import-queue/{artifact_id}/preview-doi",
            json.dumps({"doi": "not a doi"}).encode(),
            {"Content-Type": "application/json"},
        )
        assert status == 200 and preview_doi["status"] == "invalid", preview_doi
        log(f"POST preview-doi (invalid) -> {preview_doi} (no mutation)")

        status, confirm_result = post(
            f"/library/import-queue/{artifact_id}/confirm",
            json.dumps({"doi": "not-a-real-doi", "source": "manual"}).encode(),
            {"Content-Type": "application/json"},
        )
        assert status == 200 and confirm_result["promotion_state"] == "pending_review", confirm_result
        log(f"POST confirm (invalid doi) -> {confirm_result} (still queued, no mutation)")

        req = urllib.request.Request(f"{base_url}/library/import-queue/{artifact_id}", method="DELETE")
        with urllib.request.urlopen(req, timeout=10) as resp:
            delete_status = resp.status
        assert delete_status == 204, delete_status
        with urllib.request.urlopen(base_url + "/library/import-queue", timeout=10) as resp:
            listed_after = json.loads(resp.read().decode("utf-8"))
        assert listed_after["items"] == [], listed_after
        log("DELETE /library/import-queue/{id} -> 204, queue empty")

        print("\nSMOKE CHECK: ALL REVIEW-LOOP ASSERTIONS PASSED\n")
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
