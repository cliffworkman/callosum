"""Real Edge rerun for the direct-PDF Phase 1 contract fix (#61) — cases B and E ONLY.

Follow-up to `run_acceptance_AtoE.py`'s full A-E sweep: A, C, D are proven and untouched by this
fix (the new admission rule is strictly gated on `pdf_bytes_from_active_tab`, which none of them
set) and are deliberately NOT rerun here. This script reruns only what the direct-PDF admission
change could plausibly affect.

Expected outcome under the new conservative contract (see admission.py's `admit()`):
- B: the real PMC direct-PDF URL used in the original run now returns `direct_pdf_identity_unresolved`
  instead of silently creating an anonymous paper. Zero mutation.
- E: the SAME seeded existing-attachment paper as before is re-seeded, but the real click on the
  real local-fixture PDF ALSO now returns `direct_pdf_identity_unresolved` -- not
  `attachment_review_required` -- because the real extension still cannot supply the seeded paper's
  DOI. This is the expected, reported architectural-unreachability finding, not a failure: the
  attachment-safety branch itself remains proven separately at the component level (see
  `tests/test_capture.py::test_existing_paper_with_a_pdf_refuses_capture_bytes`).

Reuses every proven helper from `run_acceptance_AtoE.py` (isolation, CALLOSUM_LIBRARY_DIR_OVERRIDE,
click/CDP helpers, connector registration) rather than reimplementing them.

Usage:
    python .claude/experiments/browser-capture-acceptance/run_acceptance_BE_direct_pdf.py
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from run_acceptance_AtoE import (  # noqa: E402
    APP_DATA,
    CLICK_HELPER,
    DEV_EXTENSION_DIR,
    EDGE,
    FIXTURE_E_DOI,
    FIXTURE_E_TITLE,
    IDENTITY_PATH,
    PAGE_READY_HELPER,
    READ_STATE_HELPER,
    REAL_PDF_URL,
    SHELL_EXE,
    CaseEvidence,
    all_papers_summary,
    click_and_capture,
    db_connect,
    db_path,
    fail,
    find_real_edge_pid,
    kill_edge,
    launch_edge,
    log,
    paper_snapshot,
    retry_on_locked,
    seed_existing_attachment_paper,
    sha256_of,
    shell_running,
    wait_for_health,
    wait_for_page_load,
    wait_for_page_ready,
)
from tools.run_dev import _clear_dev_connector, _dev_connector_binary, _register_dev_connector  # noqa: E402

EVIDENCE_DIR = HERE / "evidence-run-be-direct-pdf"
FIXTURE_DIR = ROOT / ".local" / "acceptance-fixtures-be"


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


def capture_endpoint_lines(substring: str) -> list[str]:
    backend_log = APP_DATA / "backend.log"
    if not backend_log.exists():
        return []
    text = backend_log.read_text(encoding="utf-8", errors="replace")
    return [line for line in text.splitlines() if substring in line]


def pdf_upload_lines() -> list[str]:
    """Every logged POST to /capture/item/{id}/pdf -- must be empty for both B and E under the new
    conservative contract, since neither ever receives a capture_id to post to."""
    return [line for line in capture_endpoint_lines("/capture/item/") if "/pdf HTTP" in line]


def total_paper_count() -> int:
    with contextlib.closing(db_connect()) as conn:
        return conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]


def main() -> int:
    if not SHELL_EXE.is_file():
        fail(f"packaged binary not found: {SHELL_EXE}")
    if not EDGE.is_file():
        fail(f"Edge not found at {EDGE}")
    if not CLICK_HELPER.is_file() or not READ_STATE_HELPER.is_file() or not PAGE_READY_HELPER.is_file():
        fail("click/evidence helper scripts missing")
    if shell_running():
        fail("installed Callosum is still running; close it before isolating the app-data directory")
    kill_edge()

    leftover_parks = sorted(APP_DATA.parent.glob("com.callosum.desktop.real-*"))
    if leftover_parks:
        fail(
            "found leftover parked director"
            + ("y" if len(leftover_parks) == 1 else "ies")
            + f" from an incomplete prior run: {[p.name for p in leftover_parks]}. "
            "Manually verify which one holds the real data and restore it by hand first."
        )

    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    if identity.get("production_extension_ids") != []:
        fail("production_extension_ids is not empty -- refusing to run (fail-closed identity check)")
    log(f"identity check OK: production_extension_ids=[] dev_extension_id={identity['dev_extension_id']}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    parked = APP_DATA.with_name(f"com.callosum.desktop.real-{stamp}")
    had_real_dir = APP_DATA.exists()

    baseline_hash = None
    baseline_size = None
    if had_real_dir and db_path().exists():
        baseline_hash = sha256_of(db_path())
        baseline_size = db_path().stat().st_size
        log(f"baseline real callosum.sqlite: sha256={baseline_hash} size={baseline_size}")

    if had_real_dir:
        try:
            APP_DATA.rename(parked)
        except OSError as exc:
            fail(f"could not rename the real app-data directory ({exc}); refusing to run against it")
        log(f"[isolate] real app-data parked at {parked.name}")

    shell_proc: subprocess.Popen | None = None
    all_evidence: list[CaseEvidence] = []
    edge_proc: subprocess.Popen | None = None
    server = None
    try:
        disposable_library_dir = ROOT / ".local" / "acceptance-disposable-library-be"
        shutil.rmtree(disposable_library_dir, ignore_errors=True)
        disposable_library_dir.mkdir(parents=True, exist_ok=True)
        shell_env = {**os.environ, "CALLOSUM_LIBRARY_DIR_OVERRIDE": str(disposable_library_dir)}
        shell_proc = subprocess.Popen([str(SHELL_EXE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=shell_env)
        log("packaged binary started against the disposable directory")
        backend_port = wait_for_health()
        log(f"backend healthy on port {backend_port}")

        with contextlib.closing(db_connect()) as conn0:
            empty_count = conn0.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        if empty_count != 0:
            fail(f"disposable Library is not empty at start ({empty_count} papers) -- refusing to proceed")
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
        sys.path.insert(0, str(HERE))
        from fixtures import write_fixture_pdf

        write_fixture_pdf(FIXTURE_DIR / "existing.pdf")
        import http.server
        import threading

        server = http.server.HTTPServer(
            ("127.0.0.1", 0), lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(FIXTURE_DIR), **kw)
        )
        fixture_port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        log(f"local fixture server on 127.0.0.1:{fixture_port}")

        cdp_port = 19333

        # =====================================================================================
        # CASE B: real direct-PDF URL, no prior identity anywhere in the Library
        # =====================================================================================
        log("=== CASE B (rerun): real direct-PDF URL, expect direct_pdf_identity_unresolved ===")
        before_total_b = total_paper_count()
        edge_proc = launch_edge(REAL_PDF_URL, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case B: page never loaded")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case B page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evB = click_and_capture("B", REAL_PDF_URL, cdp_port, edge_pid)
        time.sleep(4)  # bounded settle for the /capture/item round trip to fully log
        after_total_b = total_paper_count()
        evB.db_before = {"total_papers": before_total_b}
        evB.db_after = {"total_papers": after_total_b}
        evB.notes.append(f"all papers after B: {all_papers_summary()}")
        item_lines_b = capture_endpoint_lines('"POST /capture/item ')
        pdf_lines_b = pdf_upload_lines()
        evB.notes.append(f"backend.log /capture/item lines: {item_lines_b[-5:]}")
        evB.notes.append(f"backend.log /capture/item/*/pdf lines (must be empty): {pdf_lines_b}")
        all_evidence.append(evB)
        write_evidence(all_evidence)
        log(f"Case B click result: {evB.click_result}")
        log(f"Case B extension state: {evB.extension_state_raw[-400:]}")
        log(f"Case B papers before={before_total_b} after={after_total_b}")
        log(f"Case B pdf-endpoint lines (expect none): {pdf_lines_b}")
        kill_edge()

        # =====================================================================================
        # CASE E: seeded existing-attachment paper, real direct-PDF click on a local fixture
        # =====================================================================================
        log("=== CASE E (rerun): existing-attachment precondition + real direct-PDF click ===")
        e_paper_id = retry_on_locked(seed_existing_attachment_paper, FIXTURE_E_DOI, FIXTURE_E_TITLE)
        log(f"Case E precondition seeded: paper_id={e_paper_id} doi={FIXTURE_E_DOI} title={FIXTURE_E_TITLE!r} attachments=1")
        pre_e = paper_snapshot(doi=FIXTURE_E_DOI)
        before_total_e = total_paper_count()

        e_url = f"http://127.0.0.1:{fixture_port}/existing.pdf"
        edge_proc = launch_edge(e_url, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case E: page never loaded")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case E page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evE = click_and_capture("E", e_url, cdp_port, edge_pid)
        time.sleep(4)
        post_e = paper_snapshot(doi=FIXTURE_E_DOI)
        after_total_e = total_paper_count()
        evE.db_before = pre_e
        evE.db_after = post_e
        evE.notes.append(f"total papers before={before_total_e} after={after_total_e}")
        evE.notes.append(f"all papers after E: {all_papers_summary()}")
        pdf_lines_e = pdf_upload_lines()
        evE.notes.append(f"backend.log /capture/item/*/pdf lines (must be empty): {pdf_lines_e}")
        all_evidence.append(evE)
        write_evidence(all_evidence)
        log(f"Case E click result: {evE.click_result}")
        log(f"Case E extension state: {evE.extension_state_raw[-400:]}")
        log(f"Case E seeded-paper before: {pre_e}")
        log(f"Case E seeded-paper after:  {post_e}")
        log(f"Case E total papers before={before_total_e} after={after_total_e}")
        log(f"Case E pdf-endpoint lines (expect none): {pdf_lines_e}")
        kill_edge()

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
        subprocess.run(["taskkill", "/F", "/T", "/IM", "callosum_connector.exe"], capture_output=True)
        time.sleep(3)

        if had_real_dir:
            for _attempt in range(5):
                if not APP_DATA.exists():
                    break
                shutil.rmtree(APP_DATA, ignore_errors=True)
                if APP_DATA.exists():
                    time.sleep(3)
            if APP_DATA.exists():
                print(
                    f"WARNING: could not delete the disposable directory; the real one is still at {parked}",
                    file=sys.stderr,
                )
            else:
                parked.rename(APP_DATA)
                log("[restore] real app-data directory restored")
                if baseline_hash and db_path().exists():
                    restored_hash = sha256_of(db_path())
                    restored_size = db_path().stat().st_size
                    if restored_hash == baseline_hash and restored_size == baseline_size:
                        log(f"[verify] restored callosum.sqlite matches baseline: sha256={restored_hash} size={restored_size}")
                    else:
                        print(
                            f"CRITICAL: restored database does NOT match baseline! "
                            f"baseline={baseline_hash}/{baseline_size} restored={restored_hash}/{restored_size}",
                            file=sys.stderr,
                        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
