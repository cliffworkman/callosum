"""Real Edge rerun for the PROVISIONAL-INGESTION direct-PDF contract (#61 / #96) -- cases B and E.

Third rerun of the direct-PDF path. History, in order:

1. The original A-E sweep (`run_acceptance_AtoE.py`) found B and E both silently created an
   anonymous, no-identity Paper from a PDF filename.
2. The first fix (`f03b242c`, reran by `run_acceptance_BE_direct_pdf.py`) replaced that with a
   terminal refusal: `direct_pdf_identity_unresolved`, `pdf_accepted=False`, nothing preserved.
3. THIS rerun exercises the reframed contract: the filename-is-not-identity invariant from (2) is
   PERMANENT, but the PDF bytes are now preserved for provisional capture instead of being refused.
   Identity is attempted from the PDF itself (front-matter DOI + title corroboration); a uniquely
   strong candidate promotes automatically through the unchanged `add_paper_by_doi` /
   `attachment_decision` substrate, otherwise the artifact stays in a durable Import Queue.

Expected outcome under the new contract -- reported as whatever ACTUALLY happens, never forced:

- B: the real PMC direct-PDF URL. Whatever its own front matter does or does not contain, the PDF
  must be preserved (queue file + provisional_artifacts row) either way; it may promote if the real
  PDF happens to carry a Crossref-resolvable front-matter DOI whose title agrees with the PDF's own
  title, or it may remain queued for review. Either is a PASS; `failed` or data loss is not.
- E: a NEW local fixture PDF that embeds a REAL, Crossref-resolvable DOI
  (`FIXTURE_E_REAL_DOI`, verified resolvable via a live Crossref lookup before this script was
  written) and a title matching that DOI's real registered title, in its own front-matter text --
  a genuinely identity-sufficient envelope, not a manufactured one. The SAME real DOI is seeded as
  an "existing paper with an attachment" beforehand. If the identity pipeline resolves the DOI
  through the REAL Crossref API and the title agrees, `add_paper_by_doi` finds the ALREADY-SEEDED
  paper (status "existing"), and `attachment_decision` refuses because it already carries an
  attachment -- proving the attachment-safety branch reachable via a REAL Edge click against REAL
  Crossref resolution, not merely at component/test level. If for any reason the real Crossref call
  does not resolve as expected (network hiccup, API change), this is reported honestly as
  unreachable-this-run rather than faked.

Reuses every proven helper from `run_acceptance_AtoE.py` (isolation, CALLOSUM_LIBRARY_DIR_OVERRIDE,
click/CDP helpers, connector registration, screenshot capture). Screenshot capture is redirected to
THIS script's own evidence directory by monkeypatching `run_acceptance_AtoE.EVIDENCE_DIR` before any
click -- reusing `click_and_capture` unmodified must never again overwrite another run's committed
evidence, which is exactly what happened the first time this pattern was reused naively.

Usage:
    python .claude/experiments/browser-capture-acceptance/run_acceptance_direct_pdf_provisional.py
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import run_acceptance_AtoE as base  # noqa: E402
from run_acceptance_AtoE import (  # noqa: E402
    APP_DATA,
    CLICK_HELPER,
    DEV_EXTENSION_DIR,
    EDGE,
    IDENTITY_PATH,
    PAGE_READY_HELPER,
    READ_STATE_HELPER,
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
    retry_on_locked,
    sha256_of,
    shell_running,
    wait_for_health,
    wait_for_page_load,
    wait_for_page_ready,
)
from tools.run_dev import _clear_dev_connector, _dev_connector_binary, _register_dev_connector  # noqa: E402

EVIDENCE_DIR = HERE / "evidence-run-provisional-direct-pdf"
FIXTURE_DIR = ROOT / ".local" / "acceptance-fixtures-provisional"

# Verified resolvable via a live `curl https://api.crossref.org/works/<doi>` lookup before this
# script was written (2026-09-16) -- title copied VERBATIM from that response so the front-matter
# title-agreement check has no reason to fail. Deliberately NOT the same DOI as REAL_PDF_URL's own
# article (10.1371/journal.pone.0000308), so Case E's seeded paper can never collide with whatever
# Case B's real click does or does not create in the same disposable Library.
FIXTURE_E_REAL_DOI = "10.1371/journal.pone.0198331"
FIXTURE_E_REAL_TITLE = (
    "Finite element analysis of annuloplasty and papillary muscle relocation on a "
    "patient-specific mitral regurgitation model"
)


def write_fixture_pdf_with_real_doi(path: Path, *, doi: str, title: str) -> None:
    """A real, minimally valid PDF whose metadata title AND page-1 text carry a genuinely
    Crossref-resolvable DOI -- the "genuinely identity-sufficient envelope" the attachment-safety
    branch needs to be proven reachable via a real Edge click, not merely asserted."""
    import fitz

    document = fitz.open()
    document.set_metadata({"title": title})
    page = document.new_page()
    page.insert_text((72, 72), f"https://doi.org/{doi}")
    page.insert_text((72, 100), title[:90])
    document.save(str(path))
    document.close()


def seed_existing_attachment_paper_real_doi(doi: str, title: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with contextlib.closing(db_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO papers (title, doi, csl_json, imported_source, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, doi, "{}", "capture:browser", now, now),
        )
        paper_id = cur.lastrowid
        conn.execute(
            "INSERT INTO attachments (paper_id, storage_mode, availability, content_type) VALUES (?, ?, ?, ?)",
            (paper_id, "managed", "available", "application/pdf"),
        )
        conn.commit()
        return paper_id


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


def total_paper_count() -> int:
    with contextlib.closing(db_connect()) as conn:
        return conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]


def provisional_artifacts_snapshot() -> list[dict]:
    with contextlib.closing(db_connect()) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM provisional_artifacts").fetchall()
        except sqlite3.OperationalError as exc:
            return [{"error": f"provisional_artifacts query failed: {exc}"}]
        return [dict(r) for r in rows]


def capture_events_snapshot() -> list[dict]:
    with contextlib.closing(db_connect()) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM capture_events").fetchall()
        except sqlite3.OperationalError as exc:
            return [{"error": f"capture_events query failed: {exc}"}]
        return [dict(r) for r in rows]


def import_queue_files(library_root: Path) -> list[str]:
    queue_dir = library_root / "_Import Queue"
    if not queue_dir.is_dir():
        return []
    return sorted(p.name for p in queue_dir.glob("*.pdf"))


def provenance_sidecar_files(library_root: Path) -> list[str]:
    prov_dir = library_root / ".provenance" / "artifacts"
    if not prov_dir.is_dir():
        return []
    return sorted(p.name for p in prov_dir.glob("*.json"))


def canonical_capture_files(library_root: Path) -> list[str]:
    if not library_root.is_dir():
        return []
    return sorted(p.name for p in library_root.glob("capture-*.pdf"))


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
        disposable_library_dir = ROOT / ".local" / "acceptance-disposable-library-provisional"
        shutil.rmtree(disposable_library_dir, ignore_errors=True)
        disposable_library_dir.mkdir(parents=True, exist_ok=True)
        shell_env = {**os.environ, "CALLOSUM_LIBRARY_DIR_OVERRIDE": str(disposable_library_dir)}
        shell_proc = subprocess.Popen(
            [str(SHELL_EXE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=shell_env
        )
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
        write_fixture_pdf_with_real_doi(
            FIXTURE_DIR / "existing_real_identity.pdf", doi=FIXTURE_E_REAL_DOI, title=FIXTURE_E_REAL_TITLE
        )
        import http.server
        import threading

        server = http.server.HTTPServer(
            ("127.0.0.1", 0), lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(FIXTURE_DIR), **kw)
        )
        fixture_port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        log(f"local fixture server on 127.0.0.1:{fixture_port}")

        cdp_port = 19334  # distinct from the prior BE rerun's port, in case of a leftover process

        # Redirect click_and_capture's screenshot writes into THIS script's own evidence dir --
        # never evidence-run/ (the original A-E sweep's committed screenshots), never
        # evidence-run-be-direct-pdf/ (the prior refusal-contract rerun's).
        base.EVIDENCE_DIR = EVIDENCE_DIR

        # =====================================================================================
        # CASE B: real direct-PDF URL, no prior identity anywhere in the Library
        # =====================================================================================
        log("=== CASE B (provisional rerun): real direct-PDF URL, report whatever actually happens ===")
        before_total_b = total_paper_count()
        edge_proc = launch_edge(REAL_PDF_URL, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case B: page never loaded")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case B page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evB = click_and_capture("B", REAL_PDF_URL, cdp_port, edge_pid)
        time.sleep(6)  # bounded settle: the identity pipeline now makes a real synchronous Crossref call
        after_total_b = total_paper_count()
        evB.db_before = {"total_papers": before_total_b}
        evB.db_after = {
            "total_papers": after_total_b,
            "provisional_artifacts": provisional_artifacts_snapshot(),
            "capture_events": capture_events_snapshot(),
            "import_queue_files": import_queue_files(disposable_library_dir),
            "provenance_sidecar_files": provenance_sidecar_files(disposable_library_dir),
            "canonical_capture_files": canonical_capture_files(disposable_library_dir),
        }
        item_lines_b = capture_endpoint_lines('"POST /capture/item ')
        pdf_lines_b = [line for line in capture_endpoint_lines("/capture/item/") if "/pdf HTTP" in line]
        evB.notes.append(f"backend.log /capture/item lines: {item_lines_b[-5:]}")
        evB.notes.append(f"backend.log /capture/item/*/pdf lines (expected to be present now): {pdf_lines_b}")
        all_evidence.append(evB)
        write_evidence(all_evidence)
        log(f"Case B click result: {evB.click_result}")
        log(f"Case B extension state: {evB.extension_state_raw[-400:]}")
        log(f"Case B papers before={before_total_b} after={after_total_b}")
        log(f"Case B provisional_artifacts: {evB.db_after['provisional_artifacts']}")
        log(f"Case B import queue files: {evB.db_after['import_queue_files']}")
        kill_edge()

        # =====================================================================================
        # CASE E: seeded existing-attachment paper with a REAL, Crossref-resolvable DOI + a real
        # local fixture PDF that genuinely carries that same DOI/title in its own front matter.
        # =====================================================================================
        log("=== CASE E (provisional rerun): genuinely identity-sufficient envelope, real Crossref ===")
        e_paper_id = retry_on_locked(seed_existing_attachment_paper_real_doi, FIXTURE_E_REAL_DOI, FIXTURE_E_REAL_TITLE)
        log(
            f"Case E precondition seeded: paper_id={e_paper_id} doi={FIXTURE_E_REAL_DOI} "
            f"title={FIXTURE_E_REAL_TITLE!r} attachments=1"
        )
        before_total_e = total_paper_count()

        e_url = f"http://127.0.0.1:{fixture_port}/existing_real_identity.pdf"
        edge_proc = launch_edge(e_url, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case E: page never loaded")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case E page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evE = click_and_capture("E", e_url, cdp_port, edge_pid)
        time.sleep(6)
        after_total_e = total_paper_count()
        with contextlib.closing(db_connect()) as conn:
            conn.row_factory = sqlite3.Row
            seeded_after = dict(conn.execute("SELECT * FROM papers WHERE id = ?", (e_paper_id,)).fetchone())
            attachment_count_after = conn.execute(
                "SELECT COUNT(*) FROM attachments WHERE paper_id = ?", (e_paper_id,)
            ).fetchone()[0]
        evE.db_before = {"total_papers": before_total_e, "seeded_paper_id": e_paper_id}
        evE.db_after = {
            "total_papers": after_total_e,
            "seeded_paper_row": seeded_after,
            "seeded_paper_attachment_count": attachment_count_after,
            "provisional_artifacts": provisional_artifacts_snapshot(),
            "capture_events": capture_events_snapshot(),
            "import_queue_files": import_queue_files(disposable_library_dir),
            "provenance_sidecar_files": provenance_sidecar_files(disposable_library_dir),
            "canonical_capture_files": canonical_capture_files(disposable_library_dir),
        }
        pdf_lines_e = [line for line in capture_endpoint_lines("/capture/item/") if "/pdf HTTP" in line]
        evE.notes.append(f"backend.log /capture/item/*/pdf lines: {pdf_lines_e}")
        all_evidence.append(evE)
        write_evidence(all_evidence)
        log(f"Case E click result: {evE.click_result}")
        log(f"Case E extension state: {evE.extension_state_raw[-400:]}")
        log(f"Case E seeded-paper attachment count after: {attachment_count_after} (expect 1, unchanged)")
        log(f"Case E total papers before={before_total_e} after={after_total_e}")
        log(f"Case E provisional_artifacts: {evE.db_after['provisional_artifacts']}")
        log(f"Case E import queue files: {evE.db_after['import_queue_files']}")
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
