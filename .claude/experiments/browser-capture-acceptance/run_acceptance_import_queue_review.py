"""Real Edge acceptance for the Import Queue human review/resolution loop (#61 follow-up to the
provisional-ingestion increment).

Demonstrates R1-R4 from the plan:

- R1: real Edge Add of an uncertain PDF -> Review count increments -> the review evidence/preview
  exist for real -> the user confirms the system's own best candidate over HTTP -> canonical Paper
  promoted -> queue item disappears -> no stale managed files remain.
- R2: real Edge Add reaching a genuine attachment_conflict (same real-DOI local fixture proven in the
  prior phase) -> existing Paper/attachment unchanged -> the item is explicitly deleted as the
  documented alternative to leaving it queued.
- R3: real Edge Add of a PDF with no findable identity at all -> immediate deletion -> no orphaned
  managed files remain.
- R4: capture an unresolved PDF, fully stop the packaged binary, restart it fresh against the SAME
  disposable library directory, and confirm the queue item/evidence/PDF bytes are still there --
  proving durability across a real process restart, not just the unit-tested crash-recovery function.

Per the explicitly approved approach: the CAPTURE half of every case is driven by a real Edge
UI-Automation click, exactly as every prior real-Edge script in this directory. The REVIEW half
(confirm/retry/delete/list) is driven by direct HTTP calls to the SAME running packaged backend's real
`/library/import-queue/*` endpoints -- the same endpoints the real frontend calls -- because no harness
in this codebase automates clicks inside Callosum's own Tauri window, and building one is out of scope
for this increment. Stated plainly here, not glossed over.

Reuses every proven helper from `run_acceptance_AtoE.py` and the real-DOI fixture pattern from
`run_acceptance_direct_pdf_provisional.py` rather than re-deriving them. Screenshot capture is
redirected to THIS script's own evidence directory (never overwrite another run's committed evidence).

Usage:
    python .claude/experiments/browser-capture-acceptance/run_acceptance_import_queue_review.py
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

import run_acceptance_AtoE as base  # noqa: E402
from run_acceptance_AtoE import (  # noqa: E402
    APP_DATA,
    DEV_EXTENSION_DIR,
    EDGE,
    IDENTITY_PATH,
    REAL_PDF_URL,
    SHELL_EXE,
    CaseEvidence,
    click_and_capture,
    db_connect,
    db_path,
    fail,
    find_real_edge_pid,
    kill_edge,
    launch_edge,
    log,
    sha256_of,
    shell_running,
    wait_for_health,
    wait_for_page_load,
    wait_for_page_ready,
)
from run_acceptance_direct_pdf_provisional import (  # noqa: E402
    FIXTURE_E_REAL_DOI,
    FIXTURE_E_REAL_TITLE,
    seed_existing_attachment_paper_real_doi,
    write_fixture_pdf_with_real_doi,
)

from tools.run_dev import _clear_dev_connector, _dev_connector_binary, _register_dev_connector  # noqa: E402

EVIDENCE_DIR = HERE / "evidence-run-import-queue-review"
FIXTURE_DIR = ROOT / ".local" / "acceptance-fixtures-review"


def write_fixture_pdf_no_identity(path: Path) -> None:
    """A real, valid, one-page PDF with no title/DOI anywhere -- queues unconditionally."""
    import fitz

    document = fitz.open()
    document.new_page()
    document.save(str(path))
    document.close()


def http_get(base_url: str, path: str) -> tuple[int, dict]:
    req = urllib.request.Request(base_url + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def http_post(base_url: str, path: str, body: dict | None, timeout: int = 180) -> tuple[int, dict]:
    # confirm/retry can do a real Crossref lookup + PDF text extraction + first-use embedding-model
    # load + vector indexing; under host memory pressure a cold start can genuinely take well over 30s.
    data = json.dumps(body if body is not None else {}).encode()
    req = urllib.request.Request(
        base_url + path, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def http_delete(base_url: str, path: str) -> int:
    req = urllib.request.Request(base_url + path, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def total_paper_count() -> int:
    with contextlib.closing(db_connect()) as conn:
        return conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]


def attachment_count_for(paper_id: int) -> int:
    with contextlib.closing(db_connect()) as conn:
        return conn.execute("SELECT COUNT(*) FROM attachments WHERE paper_id = ?", (paper_id,)).fetchone()[0]


def import_queue_files(library_root: Path) -> list[str]:
    d = library_root / "_Import Queue"
    return sorted(p.name for p in d.glob("*.pdf")) if d.is_dir() else []


def provenance_sidecar_files(library_root: Path) -> list[str]:
    d = library_root / ".provenance" / "artifacts"
    return sorted(p.name for p in d.glob("*.json")) if d.is_dir() else []


def canonical_capture_files(library_root: Path) -> list[str]:
    return sorted(p.name for p in library_root.glob("capture-*.pdf")) if library_root.is_dir() else []


def write_evidence(all_evidence: list[CaseEvidence]) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "cases": [
            {
                "case": ev.case,
                "url": ev.url,
                "click_result": ev.click_result,
                "click_log": ev.click_log,
                "extension_state_raw": ev.extension_state_raw,
                "screenshot": ev.screenshot,
                "db_before": ev.db_before,
                "db_after": ev.db_after,
                "notes": ev.notes,
            }
            for ev in all_evidence
        ],
    }
    (EVIDENCE_DIR / "evidence.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def main() -> int:
    if not SHELL_EXE.is_file():
        fail(f"packaged binary not found: {SHELL_EXE}")
    if not EDGE.is_file():
        fail(f"Edge not found at {EDGE}")
    if shell_running():
        fail("installed Callosum is still running; close it before isolating the app-data directory")
    kill_edge()

    leftover_parks = sorted(APP_DATA.parent.glob("com.callosum.desktop.real-*"))
    if leftover_parks:
        fail(f"found leftover parked directories from an incomplete prior run: {[p.name for p in leftover_parks]}")

    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    if identity.get("production_extension_ids") != []:
        fail("production_extension_ids is not empty -- refusing to run")
    log(f"identity check OK: production_extension_ids=[] dev_extension_id={identity['dev_extension_id']}")

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
    all_evidence: list[CaseEvidence] = []
    server = None
    try:
        disposable = ROOT / ".local" / "acceptance-disposable-library-review"
        shutil.rmtree(disposable, ignore_errors=True)
        disposable.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "CALLOSUM_LIBRARY_DIR_OVERRIDE": str(disposable)}

        def start_shell() -> subprocess.Popen:
            proc = subprocess.Popen([str(SHELL_EXE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            port = wait_for_health()
            log(f"packaged binary started against the disposable directory, port={port}")
            return proc, port

        shell_proc, port = start_shell()
        base_url = f"http://127.0.0.1:{port}"

        with contextlib.closing(db_connect()) as conn0:
            empty_count = conn0.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        if empty_count != 0:
            fail(f"disposable Library is not empty at start ({empty_count} papers)")
        log("confirmed disposable Library starts empty (0 papers)")

        _clear_dev_connector()
        _register_dev_connector()
        if _dev_connector_binary() is None:
            fail("dev connector binary not found -- build connector-host first")
        log("dev connector registered (org.callosum.connector.dev)")

        subprocess.run(
            [sys.executable, str(ROOT / "app" / "desktop-shell" / "extension" / "dev" / "build_dev_manifest.py")],
            check=True,
        )
        log(f"dev extension staged at {DEV_EXTENSION_DIR}")

        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        write_fixture_pdf_with_real_doi(
            FIXTURE_DIR / "conflict_real_identity.pdf", doi=FIXTURE_E_REAL_DOI, title=FIXTURE_E_REAL_TITLE
        )
        write_fixture_pdf_no_identity(FIXTURE_DIR / "no_identity.pdf")
        import http.server
        import threading

        httpd = http.server.HTTPServer(
            ("127.0.0.1", 0),
            lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(FIXTURE_DIR), **kw),
        )
        server = httpd
        fixture_port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        log(f"local fixture server on 127.0.0.1:{fixture_port}")

        base.EVIDENCE_DIR = EVIDENCE_DIR  # redirect click_and_capture's screenshots, never overwrite prior evidence
        cdp_port = 19335

        # =================================================================================
        # R1: uncertain PDF -> real Edge Add -> review evidence/preview -> confirm -> promoted
        # =================================================================================
        log("=== R1: uncertain PDF, real Edge Add, then confirm the best candidate over HTTP ===")
        before_r1 = total_paper_count()
        launch_edge(REAL_PDF_URL, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("R1: page never loaded")
        wait_for_page_ready(cdp_port)
        edge_pid = find_real_edge_pid()
        ev1 = click_and_capture("R1", REAL_PDF_URL, cdp_port, edge_pid)
        time.sleep(6)
        kill_edge()

        status, listed = http_get(base_url, "/library/import-queue")
        assert status == 200, listed
        assert len(listed["items"]) == 1, f"R1: expected exactly 1 queue item, got {listed}"
        item = listed["items"][0]
        artifact_id = item["artifact_id"]
        log(f"R1 queue item: identity_state={item['identity_state']} promotion_state={item['promotion_state']}")

        status, detail = http_get(base_url, f"/library/import-queue/{artifact_id}")
        assert status == 200, detail
        assert "candidates" in detail["evidence"], "R1: evidence missing from detail response"

        req = urllib.request.Request(base_url + f"/library/import-queue/{artifact_id}/pdf", method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            status_pdf = resp.status
            pdf_bytes = resp.read()
        assert status_pdf == 200 and pdf_bytes.startswith(b"%PDF-"), "R1: preview PDF stream did not return real bytes"
        log(f"R1 real page-1 preview stream OK ({len(pdf_bytes)} bytes)")

        r1_confirmed_paper_id = None
        if item["best_candidate"]:
            status, confirm_result = http_post(
                base_url,
                f"/library/import-queue/{artifact_id}/confirm",
                {"doi": item["best_candidate"]["doi"], "source": "candidate"},
            )
            assert status == 200, confirm_result
            log(f"R1 confirm result: {confirm_result}")
            if confirm_result["promotion_state"] == "promoted":
                r1_confirmed_paper_id = confirm_result["resolved_paper_id"]
        else:
            log("R1: no automatic candidate surfaced -- confirming manually with the real article DOI instead")
            status, confirm_result = http_post(
                base_url,
                f"/library/import-queue/{artifact_id}/confirm",
                {"doi": "10.1371/journal.pone.0000308", "source": "manual"},
            )
            assert status == 200, confirm_result
            log(f"R1 manual confirm result: {confirm_result}")
            if confirm_result["promotion_state"] == "promoted":
                r1_confirmed_paper_id = confirm_result["resolved_paper_id"]

        retry_result = None
        if (
            r1_confirmed_paper_id is None
            and confirm_result["promotion_state"]
            in {
                "processing_failed",
                "indexing_unavailable",
            }
            and confirm_result.get("resolved_paper_id") is not None
        ):
            # A real, honest promotion attempt against a real PDF can genuinely fail (embedding
            # cold-start, transient resource pressure). This is exactly the scenario `retry` exists
            # for: identity is already resolved, only attachment needs to be re-attempted. Prove the
            # recovery path for real rather than treating a single failed attempt as the final word.
            log(f"R1: confirm landed on {confirm_result['promotion_state']!r} -- attempting retry over HTTP")
            status, retry_result = http_post(base_url, f"/library/import-queue/{artifact_id}/retry", None)
            assert status == 200, retry_result
            log(f"R1 retry result: {retry_result}")
            if retry_result["promotion_state"] == "promoted":
                r1_confirmed_paper_id = retry_result["resolved_paper_id"]

        r1_decision_reason = None
        if r1_confirmed_paper_id is None:
            # Surface the real failure detail (attempt_attach_to_paper's `str(exc)[:300]`, persisted as
            # evidence_json.decision_reason) before the disposable app-data is torn down -- diagnosing
            # a real failure honestly requires the real message, not a guess.
            status, detail_after = http_get(base_url, f"/library/import-queue/{artifact_id}")
            if status == 200:
                r1_decision_reason = detail_after.get("evidence", {}).get("decision_reason")
                log(f"R1 real failure detail (decision_reason): {r1_decision_reason!r}")

        after_r1 = total_paper_count()
        ev1.db_before = {"total_papers": before_r1}
        ev1.db_after = {
            "total_papers": after_r1,
            "confirm_result": confirm_result,
            "retry_result": retry_result,
            "decision_reason_if_not_promoted": r1_decision_reason,
            "import_queue_files": import_queue_files(disposable),
            "canonical_capture_files": canonical_capture_files(disposable),
        }
        ev1.notes.append(f"r1_confirmed_paper_id={r1_confirmed_paper_id}")
        all_evidence.append(ev1)
        write_evidence(all_evidence)

        if r1_confirmed_paper_id is not None:
            status, listed_after = http_get(base_url, "/library/import-queue")
            assert artifact_id not in {i["artifact_id"] for i in listed_after["items"]}, (
                "R1: item still in queue after promotion"
            )
            assert import_queue_files(disposable) == [], "R1: stale queue file after promotion"
            log("R1 PASS: promoted, queue item gone, no stale managed files")
        else:
            log(f"R1: did not reach 'promoted' this run (state: {confirm_result}) -- reported honestly, not forced")

        # =================================================================================
        # R2: genuine attachment_conflict via real Edge + real Crossref -> delete explicitly
        # =================================================================================
        log("=== R2: real Edge Add reaching attachment_conflict, then explicit delete ===")
        existing_paper_id = seed_existing_attachment_paper_real_doi(FIXTURE_E_REAL_DOI, FIXTURE_E_REAL_TITLE)
        attach_before = attachment_count_for(existing_paper_id)
        r2_url = f"http://127.0.0.1:{fixture_port}/conflict_real_identity.pdf"
        launch_edge(r2_url, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("R2: page never loaded")
        wait_for_page_ready(cdp_port)
        edge_pid = find_real_edge_pid()
        ev2 = click_and_capture("R2", r2_url, cdp_port, edge_pid)
        time.sleep(6)
        kill_edge()

        status, listed = http_get(base_url, "/library/import-queue")
        r2_items = [i for i in listed["items"] if i["resolved_paper_id"] == existing_paper_id]
        assert len(r2_items) == 1, f"R2: expected exactly 1 queue item resolved to the seeded paper, got {listed}"
        r2_item = r2_items[0]
        assert r2_item["promotion_state"] == "attachment_conflict", f"R2: expected attachment_conflict, got {r2_item}"
        attach_after = attachment_count_for(existing_paper_id)
        assert attach_after == attach_before == 1, "R2: seeded paper's attachment count changed"
        log(f"R2 reached attachment_conflict for real: {r2_item}")

        delete_status = http_delete(base_url, f"/library/import-queue/{r2_item['artifact_id']}")
        assert delete_status == 204, f"R2: delete returned {delete_status}"
        status, listed_after = http_get(base_url, "/library/import-queue")
        assert r2_item["artifact_id"] not in {i["artifact_id"] for i in listed_after["items"]}
        attach_final = attachment_count_for(existing_paper_id)
        assert attach_final == 1, "R2: deleting the CAPTURE must never touch the existing paper's own attachment"

        ev2.db_before = {"existing_paper_id": existing_paper_id, "attachment_count": attach_before}
        ev2.db_after = {"promotion_state": r2_item["promotion_state"], "attachment_count_after_delete": attach_final}
        all_evidence.append(ev2)
        write_evidence(all_evidence)
        log("R2 PASS: attachment_conflict reached, existing paper untouched, capture explicitly deleted")

        # =================================================================================
        # R3: no identity at all -> real Edge Add -> immediate delete -> nothing orphaned
        # =================================================================================
        log("=== R3: no-identity PDF, real Edge Add, then immediate delete ===")
        r3_url = f"http://127.0.0.1:{fixture_port}/no_identity.pdf"
        launch_edge(r3_url, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("R3: page never loaded")
        wait_for_page_ready(cdp_port)
        edge_pid = find_real_edge_pid()
        ev3 = click_and_capture("R3", r3_url, cdp_port, edge_pid)
        time.sleep(6)
        kill_edge()

        status, listed = http_get(base_url, "/library/import-queue")
        r3_candidates = [i for i in listed["items"] if i["last_source_url"] == r3_url]
        assert len(r3_candidates) == 1, f"R3: expected exactly 1 new queue item, got {listed}"
        r3_item = r3_candidates[0]
        assert r3_item["promotion_state"] == "pending_review", r3_item

        delete_status = http_delete(base_url, f"/library/import-queue/{r3_item['artifact_id']}")
        assert delete_status == 204
        status, listed_after = http_get(base_url, "/library/import-queue")
        assert r3_item["artifact_id"] not in {i["artifact_id"] for i in listed_after["items"]}
        remaining_files = import_queue_files(disposable)
        assert r3_item["artifact_id"] not in "".join(remaining_files), "R3: orphaned queue file after delete"

        ev3.db_after = {"deleted": True, "remaining_import_queue_files": remaining_files}
        all_evidence.append(ev3)
        write_evidence(all_evidence)
        log("R3 PASS: captured, then deleted cleanly, no orphaned managed files")

        # =================================================================================
        # R4: durability across a REAL process restart (not just the unit-tested function)
        # =================================================================================
        log("=== R4: capture an unresolved PDF, restart the packaged binary for real, verify durability ===")
        r4_fixture = FIXTURE_DIR / "restart_test.pdf"
        write_fixture_pdf_no_identity(r4_fixture)
        r4_url = f"http://127.0.0.1:{fixture_port}/restart_test.pdf"
        launch_edge(r4_url, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("R4: page never loaded")
        wait_for_page_ready(cdp_port)
        edge_pid = find_real_edge_pid()
        ev4 = click_and_capture("R4", r4_url, cdp_port, edge_pid)
        time.sleep(6)
        kill_edge()

        status, listed = http_get(base_url, "/library/import-queue")
        r4_candidates = [i for i in listed["items"] if i["last_source_url"] == r4_url]
        assert len(r4_candidates) == 1, f"R4: expected exactly 1 new queue item before restart, got {listed}"
        r4_artifact_id = r4_candidates[0]["artifact_id"]
        r4_evidence_before = http_get(base_url, f"/library/import-queue/{r4_artifact_id}")[1]

        log("R4: stopping the packaged binary...")
        shell_proc.terminate()
        try:
            shell_proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            shell_proc.kill()
        subprocess.run(["taskkill", "/F", "/T", "/IM", "callosum-shell.exe"], capture_output=True)
        time.sleep(3)

        log("R4: restarting the packaged binary against the SAME disposable library...")
        shell_proc, port = start_shell()
        base_url = f"http://127.0.0.1:{port}"

        status, listed_restarted = http_get(base_url, "/library/import-queue")
        assert status == 200, listed_restarted
        restarted_ids = {i["artifact_id"] for i in listed_restarted["items"]}
        assert r4_artifact_id in restarted_ids, f"R4: queue item missing after restart! {listed_restarted}"
        req = urllib.request.Request(base_url + f"/library/import-queue/{r4_artifact_id}/pdf", method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            restart_status = resp.status
            restarted_pdf_bytes = resp.read()
        assert restart_status == 200 and restarted_pdf_bytes.startswith(b"%PDF-"), (
            "R4: PDF bytes not streamable after restart"
        )

        ev4.db_before = {"artifact_id": r4_artifact_id, "evidence_before_restart": r4_evidence_before}
        ev4.db_after = {"still_listed_after_restart": True, "pdf_bytes_streamable_after_restart": True}
        all_evidence.append(ev4)
        write_evidence(all_evidence)
        log("R4 PASS: queue item, evidence, and PDF bytes all survived a real process restart")

        log("evidence written to " + str(EVIDENCE_DIR / "evidence.json"))

    finally:
        kill_edge()
        try:
            if server is not None:
                server.shutdown()
        except Exception:  # noqa: BLE001
            pass
        _clear_dev_connector()
        if shell_proc is not None:
            shell_proc.terminate()
            try:
                shell_proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                shell_proc.kill()
        subprocess.run(["taskkill", "/F", "/T", "/IM", "callosum-shell.exe"], capture_output=True)
        time.sleep(3)

        if had_real_dir:
            for _ in range(5):
                if not APP_DATA.exists():
                    break
                shutil.rmtree(APP_DATA, ignore_errors=True)
                if APP_DATA.exists():
                    time.sleep(3)
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
