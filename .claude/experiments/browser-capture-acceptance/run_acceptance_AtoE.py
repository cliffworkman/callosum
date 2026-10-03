"""Real Edge A-E acceptance sweep for browser capture (#61 Phase 1 functional acceptance).

Runs all five acceptance cases in ONE isolated session (one isolate/restore cycle covering all of
them, not five separate ones) against a real, packaged Callosum instance and a real Edge browser,
driven via a keyboard-navigation click mechanism proven in isolation beforehand (see
click_extension.ps1's header comment) to carry genuine activeTab/user-gesture semantics.

Safety: refuses to run if Callosum is already running; renames the REAL %APPDATA%\\com.callosum.desktop
out of the way before anything else; every exit path (including exceptions) restores it. Real
app-data is verified present/absent and the restored database's hash is checked against the baseline
recorded before isolation.

Cases A/B/C hit one real, openly-licensed PLOS ONE article (chosen for stable, genuine Highwire +
JSON-LD metadata and a real direct-PDF URL) -- a deliberate one-time exception to the extension unit
tests' "no live publisher pages" rule, appropriate here because this is a human-authorized, supervised
acceptance run, not a CI gate. Cases D/E use local fixtures with distinct DOIs so they can coexist in
one continuous session without colliding.

Usage:
    python .claude/experiments/browser-capture-acceptance/run_acceptance_AtoE.py
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from fixtures import write_fixture_pdf  # noqa: E402

from tools.run_dev import _clear_dev_connector, _dev_connector_binary, _register_dev_connector  # noqa: E402

APP_DATA = Path(os.environ["APPDATA"]) / "com.callosum.desktop"
SHELL_EXE = ROOT / "app" / "desktop-shell" / "src-tauri" / "target" / "release" / "callosum-shell.exe"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
DEV_EXTENSION_DIR = ROOT / ".local" / "dev-extension"
EDGE_PROFILE_DIR = ROOT / ".local" / "acceptance-edge-profile-full"
FIXTURE_DIR = ROOT / ".local" / "acceptance-fixtures-full"
CLICK_HELPER = HERE / "click_extension.ps1"
READ_STATE_HELPER = HERE / "read_extension_state.ps1"
PAGE_READY_HELPER = HERE / "wait_for_page_ready.ps1"
IDENTITY_PATH = ROOT / "app" / "desktop-shell" / "connector" / "identity.json"
EVIDENCE_DIR = HERE / "evidence-run"

# A genuinely fresh disposable app-data directory needs the managed Python runtime extracted/
# initialized from scratch (observed ~5-6 minutes empirically) -- the real daily-use directory never
# shows this cost since that runtime is already cached from months of prior real use. This is a
# harness-timeout concern, not a browser-capture defect.
HEALTH_TIMEOUT_S = 900
EXTENSION_NAME = "Callosum Capture"

# --- Real fixture for A/B/C -------------------------------------------------------------------
REAL_ARTICLE_URL = "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0000308"
REAL_ARTICLE_DOI = "10.1371/journal.pone.0000308"
REAL_PDF_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC1817752/pdf/pone.0000308.pdf"

# --- Local fixtures for D/E (distinct DOIs so both can be seeded in one continuous session) ----
FIXTURE_D_DOI = "10.9999/fixture-d"
FIXTURE_D_HTML = f"""<!doctype html>
<html><head>
<title>A Fixture Paper (D)</title>
<meta name="citation_doi" content="{FIXTURE_D_DOI}">
<meta name="citation_title" content="A Fixture Scholarly Paper D">
<meta name="citation_author" content="Ada Lovelace">
<meta name="citation_journal_title" content="Journal of Acceptance Testing">
<meta name="citation_publication_date" content="2024/01/01">
</head><body><h1>A Fixture Scholarly Paper D</h1></body></html>
"""
FIXTURE_E_DOI = "10.9999/fixture-e"
FIXTURE_E_TITLE = "A Fixture Paper With An Existing Attachment"


def fail(message: str) -> None:
    print(f"STOP: {message}", file=sys.stderr)
    raise SystemExit(1)


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def shell_running() -> bool:
    out = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=60).stdout.lower()
    return "callosum-shell.exe" in out


def db_path() -> Path:
    return APP_DATA / "callosum.sqlite"


def db_connect() -> sqlite3.Connection:
    # The real backend polls its own DB frequently (status/jobs) and can briefly hold the WAL
    # writer lock; a short default busy-timeout produced a genuine "database is locked" failure
    # during a real run, so this is generous on purpose.
    return sqlite3.connect(db_path(), timeout=30)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def run_powershell(script: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def take_screenshot(label: str) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVIDENCE_DIR / f"{label}.png"
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("{out_path}", [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
    return out_path


@dataclass
class CaseEvidence:
    case: str
    url: str
    click_log: str = ""
    click_result: str = ""
    extension_state_raw: str = ""
    screenshot: str = ""
    db_before: dict = field(default_factory=dict)
    db_after: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def write_evidence_incremental(all_evidence: list[CaseEvidence]) -> None:
    """Write whatever evidence exists so far -- called after every case, not just at the end, so a
    mid-run crash (e.g. an unexpected exception in a later case) does not lose earlier cases'
    already-collected real evidence."""
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


def query_papers_by_doi(doi: str) -> list[sqlite3.Row]:
    # Every DB helper below opens and closes its OWN short-lived connection (never returns one for
    # a caller to hold) -- a real run hit repeated "database is locked" failures caused by earlier
    # connections created inline (e.g. `db_connect().execute(...)`) never being explicitly closed,
    # which under WAL mode can block the backend's own writer indefinitely, not just briefly.
    with contextlib.closing(db_connect()) as conn:
        conn.row_factory = sqlite3.Row
        return list(conn.execute("SELECT * FROM papers WHERE doi = ?", (doi,)).fetchall())


def count_papers_with_doi(doi: str) -> int:
    with contextlib.closing(db_connect()) as conn:
        return conn.execute("SELECT COUNT(*) FROM papers WHERE doi = ?", (doi,)).fetchone()[0]


def paper_snapshot(doi: str | None = None, title: str | None = None) -> dict:
    with contextlib.closing(db_connect()) as conn:
        conn.row_factory = sqlite3.Row
        if doi:
            rows = conn.execute("SELECT * FROM papers WHERE doi = ?", (doi,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM papers WHERE title = ?", (title,)).fetchall()
        out = {"rows": []}
        for row in rows:
            pid = row["id"]
            attachments = conn.execute("SELECT COUNT(*) FROM attachments WHERE paper_id = ?", (pid,)).fetchone()[0]
            annotations = conn.execute("SELECT COUNT(*) FROM annotations WHERE paper_id = ?", (pid,)).fetchone()[0]
            embeddings = conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE target_type = 'paper' AND target_id = ?", (pid,)
            ).fetchone()[0]
            out["rows"].append(
                {
                    "id": pid,
                    "title": row["title"],
                    "doi": row["doi"],
                    "deleted_at": row["deleted_at"],
                    "imported_source": row["imported_source"] if "imported_source" in row.keys() else None,
                    "attachments": attachments,
                    "annotations": annotations,
                    "embeddings": embeddings,
                }
            )
        return out


def all_papers_summary() -> list[dict]:
    with contextlib.closing(db_connect()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, title, doi FROM papers ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def retry_on_locked(fn, *args, attempts: int = 10, delay_s: float = 5.0, **kwargs):
    """Retry a DB write on 'database is locked' -- a real run showed the backend can hold a
    sustained write lock (observed >30s, beyond a single connection's own busy-timeout) at
    unpredictable points; this is harness-side resilience, not a product-code change."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_exc = exc
            log(f"  retry {attempt}/{attempts} after 'database is locked' ({exc})")
            time.sleep(delay_s)
    raise last_exc  # noqa: RSE102


def seed_trashed_paper(doi: str, title: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with contextlib.closing(db_connect()) as conn:
        conn.execute(
            "INSERT INTO papers (title, doi, csl_json, imported_source, deleted_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, doi, "{}", "capture:browser", now, now, now),
        )
        conn.commit()


def seed_existing_attachment_paper(doi: str, title: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with contextlib.closing(db_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO papers (title, doi, csl_json, imported_source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (title, doi, "{}", "capture:browser", now, now),
        )
        paper_id = cur.lastrowid
        conn.execute(
            "INSERT INTO attachments (paper_id, storage_mode, availability, content_type) VALUES (?, ?, ?, ?)",
            (paper_id, "managed", "available", "application/pdf"),
        )
        conn.commit()
        return paper_id


def read_extension_state(cdp_port: int) -> str:
    state = run_powershell(READ_STATE_HELPER, ["-CdpPort", str(cdp_port)], timeout=30)
    return state.stdout + state.stderr


def click_and_capture(case: str, url_being_captured: str, cdp_port: int, edge_pid: int) -> CaseEvidence:
    ev = CaseEvidence(case=case, url=url_being_captured)
    result = run_powershell(CLICK_HELPER, ["-EdgePid", str(edge_pid), "-ExtensionName", EXTENSION_NAME], timeout=90)
    ev.click_log = result.stdout + result.stderr
    for line in ev.click_log.splitlines():
        if line.startswith("RESULT:"):
            ev.click_result = line

    # Bounded poll for the badge to leave "capturing" ("...") rather than a fixed sleep --
    # native messaging + a real network round-trip (Cases A/B hit live servers) has variable
    # latency.
    deadline = time.monotonic() + 30
    last_state = ""
    while time.monotonic() < deadline:
        last_state = read_extension_state(cdp_port)
        if '"…"' not in last_state and "capturing" not in last_state.lower():
            break
        time.sleep(1.0)
    ev.extension_state_raw = last_state
    ev.screenshot = str(take_screenshot(f"case_{case}_after_click"))
    return ev


def launch_edge(url: str, cdp_port: int) -> subprocess.Popen:
    if EDGE_PROFILE_DIR.exists():
        shutil.rmtree(EDGE_PROFILE_DIR, ignore_errors=True)
    default_dir = EDGE_PROFILE_DIR / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    prefs = {
        "signin": {"allowed": False, "allowed_on_next_startup": False},
        "sync": {"requested": False},
        "browser": {"show_signin_promo": False, "check_default_browser": False},
    }
    (default_dir / "Preferences").write_text(json.dumps(prefs), encoding="utf-8")
    args = [
        str(EDGE),
        f"--user-data-dir={EDGE_PROFILE_DIR}",
        f"--load-extension={DEV_EXTENSION_DIR}",
        f"--remote-debugging-port={cdp_port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-features=msImplicitSignin,SigninInterceptBubbleV2",
        url,
    ]
    proc = subprocess.Popen(args)
    return proc


def wait_for_page_load(cdp_port: int, timeout_s: int = 30) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=3) as resp:
                targets = json.loads(resp.read())
            pages = [t for t in targets if t.get("type") == "page"]
            if pages:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.0)
    return False


def wait_for_page_ready(cdp_port: int, timeout_s: int = 30) -> bool:
    """Poll document.readyState == 'complete' rather than a fixed sleep -- a real, heavier page
    (vs. an instant local fixture) can still be mid-load when a fixed sleep would have moved on,
    and Chromium's toolbar 'Refresh' button reads as 'Stop' while a page is loading, which broke
    the click helper's focus anchor in a real run before this wait was added."""
    result = run_powershell(
        PAGE_READY_HELPER, ["-CdpPort", str(cdp_port), "-TimeoutSec", str(timeout_s)], timeout=timeout_s + 15
    )
    return "READY" in result.stdout


def find_real_edge_pid() -> int | None:
    out = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-Process msedge | Sort-Object WorkingSet -Descending | Select-Object -First 1).Id",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    try:
        return int(out.stdout.strip())
    except ValueError:
        return None


def kill_edge() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], capture_output=True)
    time.sleep(1)


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

    # A prior run that failed to delete its disposable directory leaves the REAL data parked under
    # a "real-<timestamp>" name while a disposable directory sits at the live path -- a second run
    # started on top of that would treat the disposable leftover as "the real baseline" and could
    # compound the confusion (this happened once during development). Refuse outright rather than
    # guess which of possibly several parked directories is the genuine one.
    leftover_parks = sorted(APP_DATA.parent.glob("com.callosum.desktop.real-*"))
    if leftover_parks:
        fail(
            "found leftover parked director"
            + ("y" if len(leftover_parks) == 1 else "ies")
            + f" from an incomplete prior run: {[p.name for p in leftover_parks]}. "
            "Manually verify which one holds the real data (compare callosum.sqlite hash/size) and "
            "restore it by hand before running this script again."
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
    try:
        # --- launch packaged shell against the fresh disposable directory ---------------------
        disposable_library_dir = ROOT / ".local" / "acceptance-disposable-library"
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

        # --- seed local fixtures for D/E (distinct DOIs, coexist in one session) --------------
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        (FIXTURE_DIR / "fixture_d.html").write_text(FIXTURE_D_HTML, encoding="utf-8")
        write_fixture_pdf(FIXTURE_DIR / "existing.pdf")
        import http.server
        import threading

        server = http.server.HTTPServer(
            ("127.0.0.1", 0),
            lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(FIXTURE_DIR), **kw),
        )
        fixture_port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        log(f"local fixture server on 127.0.0.1:{fixture_port}")

        cdp_port = 19222

        # =====================================================================================
        # CASE A: real scholarly HTML -> new paper, capture:browser provenance
        # =====================================================================================
        log("=== CASE A: real PLOS ONE article ===")
        launch_edge(REAL_ARTICLE_URL, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case A: page never loaded (CDP /json showed no page target)")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case A page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evA = click_and_capture("A", REAL_ARTICLE_URL, cdp_port, edge_pid)
        evA.db_before = paper_snapshot(doi=REAL_ARTICLE_DOI)

        # bounded poll for the paper to appear (async admission + indexing)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if query_papers_by_doi(REAL_ARTICLE_DOI):
                break
            time.sleep(1)
        evA.db_after = paper_snapshot(doi=REAL_ARTICLE_DOI)
        all_evidence.append(evA)
        write_evidence_incremental(all_evidence)
        log(f"Case A click result: {evA.click_result}")
        log(f"Case A DB after: {evA.db_after}")
        kill_edge()

        # A -> B precondition: paper metadata-only (1 live row, 0 attachments, 0 annotations)
        pre_b = paper_snapshot(doi=REAL_ARTICLE_DOI)
        live_rows = [r for r in pre_b["rows"] if r["deleted_at"] is None]
        if len(live_rows) != 1 or live_rows[0]["attachments"] != 0 or live_rows[0]["annotations"] != 0:
            log(f"WARNING: A->B precondition not met exactly: {pre_b}")
        else:
            log(
                f"A->B precondition confirmed: 1 live row, 0 attachments, 0 annotations (paper_id={live_rows[0]['id']})"
            )

        # =====================================================================================
        # CASE B: real direct-PDF URL from the same article
        # =====================================================================================
        log("=== CASE B: real direct-PDF URL ===")
        launch_edge(REAL_PDF_URL, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case B: page never loaded")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case B page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evB = click_and_capture("B", REAL_PDF_URL, cdp_port, edge_pid)
        evB.db_before = pre_b
        time.sleep(4)  # allow POST /capture/item then /capture/item/{id}/pdf to complete
        evB.db_after = paper_snapshot(doi=REAL_ARTICLE_DOI)
        evB.notes.append(f"all papers after B: {all_papers_summary()}")
        all_evidence.append(evB)
        write_evidence_incremental(all_evidence)
        log(f"Case B click result: {evB.click_result}")
        log(f"Case B all papers: {evB.notes[-1]}")
        kill_edge()

        # =====================================================================================
        # CASE C: re-click A's real page -> already_present, no duplicate
        # =====================================================================================
        log("=== CASE C: re-click same real article ===")
        before_count = count_papers_with_doi(REAL_ARTICLE_DOI)
        launch_edge(REAL_ARTICLE_URL, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case C: page never loaded")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case C page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evC = click_and_capture("C", REAL_ARTICLE_URL, cdp_port, edge_pid)
        time.sleep(3)
        after_count = count_papers_with_doi(REAL_ARTICLE_DOI)
        evC.db_before = {"count_with_doi": before_count}
        evC.db_after = {"count_with_doi": after_count}
        all_evidence.append(evC)
        write_evidence_incremental(all_evidence)
        log(f"Case C click result: {evC.click_result}; count before={before_count} after={after_count}")
        kill_edge()

        # =====================================================================================
        # CASE D: local fixture, pre-seeded TRASHED -> stays deleted, no resurrection
        # =====================================================================================
        log("=== CASE D: trashed paper precondition ===")
        retry_on_locked(seed_trashed_paper, FIXTURE_D_DOI, "A Fixture Scholarly Paper D")
        # verify seeded identity matches what the fixture page will actually extract
        assert f'content="{FIXTURE_D_DOI}"' in FIXTURE_D_HTML
        log(
            f"Case D precondition seeded: doi={FIXTURE_D_DOI} deleted_at=<set>; fixture HTML citation_doi confirmed identical"
        )
        d_url = f"http://127.0.0.1:{fixture_port}/fixture_d.html"
        launch_edge(d_url, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case D: page never loaded")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case D page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evD = click_and_capture("D", d_url, cdp_port, edge_pid)
        evD.db_before = paper_snapshot(doi=FIXTURE_D_DOI)
        time.sleep(3)
        evD.db_after = paper_snapshot(doi=FIXTURE_D_DOI)
        all_evidence.append(evD)
        write_evidence_incremental(all_evidence)
        log(f"Case D click result: {evD.click_result}")
        log(f"Case D DB after: {evD.db_after}")
        kill_edge()

        # =====================================================================================
        # CASE E: local fixture PDF, pre-seeded paper WITH an existing attachment
        # =====================================================================================
        log("=== CASE E: existing-attachment precondition, direct-PDF click ===")
        e_paper_id = retry_on_locked(seed_existing_attachment_paper, FIXTURE_E_DOI, FIXTURE_E_TITLE)
        log(
            f"Case E precondition seeded: paper_id={e_paper_id} doi={FIXTURE_E_DOI} title={FIXTURE_E_TITLE!r} attachments=1"
        )
        e_url = f"http://127.0.0.1:{fixture_port}/existing.pdf"
        launch_edge(e_url, cdp_port)
        if not wait_for_page_load(cdp_port):
            fail("Case E: page never loaded")
        if not wait_for_page_ready(cdp_port):
            log("WARNING: Case E page did not reach readyState=complete within timeout; proceeding anyway")
        edge_pid = find_real_edge_pid()
        evE = click_and_capture("E", e_url, cdp_port, edge_pid)
        evE.db_before = paper_snapshot(doi=FIXTURE_E_DOI)
        time.sleep(4)
        evE.db_after = paper_snapshot(doi=FIXTURE_E_DOI)
        evE.notes.append(f"all papers after E: {all_papers_summary()}")
        backend_log = APP_DATA / "backend.log"
        pdf_endpoint_hits = []
        if backend_log.exists():
            text = backend_log.read_text(encoding="utf-8", errors="replace")
            pdf_endpoint_hits = [line for line in text.splitlines() if "/pdf" in line and "capture" in line]
        evE.notes.append(f"backend.log lines mentioning capture .../pdf: {pdf_endpoint_hits[-10:]}")
        all_evidence.append(evE)
        write_evidence_incremental(all_evidence)
        log(f"Case E click result: {evE.click_result}")
        log(f"Case E all papers: {evE.notes[-2]}")
        log(f"Case E endpoint evidence: {evE.notes[-1]}")
        kill_edge()

        # --- persist evidence to disk -----------------------------------------------------
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        report = {
            "branch_head_note": "see git rev-parse HEAD in the final report",
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
        log(f"evidence written to {EVIDENCE_DIR / 'evidence.json'}")

    finally:
        kill_edge()
        try:
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
        # /T kills the whole process tree (the backend runs as a child process and can otherwise
        # keep the disposable directory's SQLite files locked well after the shell exe itself exits,
        # which caused a real rmtree failure -- observed leaving the REAL data parked and requiring
        # manual recovery).
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
                        log(
                            f"[verify] restored callosum.sqlite matches baseline: sha256={restored_hash} size={restored_size}"
                        )
                    else:
                        print(
                            f"CRITICAL: restored database does NOT match baseline! "
                            f"baseline={baseline_hash}/{baseline_size} restored={restored_hash}/{restored_size}",
                            file=sys.stderr,
                        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
