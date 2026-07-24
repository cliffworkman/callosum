"""Real-UNO round-trip orchestrator for the LibreOffice adapter (inc 108; promoted from the gitignored
`.local/lo_roundtrip/` into a committed path in the test-hardening pass that closed out backlog #33/#34 — this
was previously dev-only and had zero CI enforcement). Seeds a temp DB with two papers, starts a callosum uvicorn
server, starts a headless LibreOffice with its OWN UNO socket + user profile (never touches an operator's real
LibreOffice session, and only ever kills the soffice process it itself spawned), runs `selftest_uno.py` under
LibreOffice's own Python bridge, and tears everything down.

Cross-platform (Windows for local dev, Linux for `.github/workflows/libreoffice-adapter.yml`): on Linux the
`uno` bridge module lives in the SYSTEM python3 that `python3-uno` installs into (not any project venv), so this
always shells out to a real LibreOffice-side Python rather than importing `uno` in-process.

    python adapters/libreoffice/run_roundtrip.py
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / ".local" / "lo_roundtrip"  # generated artifacts (temp DB, LO profile) — NOT this script's own dir
HERE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))  # so `import app...` resolves when run as a script
SELFTEST = ROOT / "adapters" / "libreoffice" / "selftest_uno.py"
PORT_HTTP = 8100
PORT_UNO = 2003

if platform.system() == "Windows":
    _LO_DIR = Path(r"C:\Program Files\LibreOffice\program")
    SOFFICE = _LO_DIR / "soffice.exe"
    LO_PYTHON = _LO_DIR / "python.exe"
    UNOPKG = _LO_DIR / "unopkg.com"
else:
    # Ubuntu's `libreoffice` + `python3-uno` packages put `soffice`/`unopkg` on PATH and the `uno` module into the
    # SYSTEM python3's site-packages — not whatever python actions/setup-python provisioned, and not a project venv.
    SOFFICE = Path(shutil.which("soffice") or "/usr/bin/soffice")
    LO_PYTHON = Path("/usr/bin/python3")
    UNOPKG = Path(shutil.which("unopkg") or "/usr/bin/unopkg")

VASWANI = {
    "type": "article-journal",
    "title": "Attention is all you need",
    "author": [{"family": "Vaswani", "given": "Ashish"}, {"family": "Shazeer", "given": "Noam"}],
    "issued": {"date-parts": [[2017]]},
    "container-title": "Advances in Neural Information Processing Systems",
}
DEVLIN = {
    "type": "article-journal",
    "title": "BERT: Pre-training of deep bidirectional transformers",
    "author": [{"family": "Devlin", "given": "Jacob"}, {"family": "Chang", "given": "Ming-Wei"}],
    "issued": {"date-parts": [[2019]]},
    "container-title": "NAACL",
}


def seed_db() -> tuple[str, int, int]:
    from alembic import command
    from alembic.config import Config
    from app.backend.embeddings.models import DEFAULT_EMBEDDING_MODEL, SentenceTransformerEmbeddingModel
    from app.backend.embeddings.pipeline import embed_chunks
    from app.backend.embeddings.vector_store import SQLiteVecVectorStore
    from app.backend.persistence.database import make_engine
    from app.backend.persistence.repository import create_attachment, create_chunk, create_paper

    db_path = HERE / "roundtrip.sqlite"
    if db_path.exists():
        db_path.unlink()
    db_url = f"sqlite:///{db_path.as_posix()}"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
    engine = make_engine(db_url)
    with engine.begin() as conn:
        p1 = create_paper(conn, title=VASWANI["title"], csl_json=VASWANI)
        p2 = create_paper(conn, title=DEVLIN["title"], csl_json=DEVLIN)
        # inc 157: a chunk per paper + embeddings, so /citations/suggest (inc 156) returns results in the round-trip.
        for pid, checksum, snippet in (
            (
                p1,
                "rt-vaswani",
                "We propose the Transformer, a model architecture relying entirely on attention "
                "mechanisms, dispensing with recurrence and convolutions.",
            ),
            (
                p2,
                "rt-devlin",
                "BERT pre-trains deep bidirectional representations from unlabeled text by jointly "
                "conditioning on both left and right context.",
            ),
        ):
            att = create_attachment(
                conn,
                paper_id=pid,
                storage_mode="linked",
                availability="available",
                content_type="application/pdf",
                checksum=checksum,
                import_source="test",
                attachment_type="pdf",
                role="primary",
            )
            create_chunk(
                conn,
                paper_id=pid,
                attachment_id=att,
                text=snippet,
                page_start=1,
                page_end=1,
                bbox_coordinate_system="pdf-points-top-left",
                extraction_tool="fixture",
                extraction_version="1",
                chunking_strategy="paragraph",
                chunk_version="rt-v1",
                source_attachment_checksum=checksum,
                bbox_json=[{"page": 1, "x0": 10, "y0": 20, "x1": 120, "y1": 40}],
            )
        embed_chunks(
            conn,
            model=SentenceTransformerEmbeddingModel(name=DEFAULT_EMBEDDING_MODEL, version=DEFAULT_EMBEDDING_MODEL),
            vector_store=SQLiteVecVectorStore(),
        )
    engine.dispose()
    return db_url, p1, p2


def wait_http(url: str, attempts: int = 60) -> None:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"server never became healthy: {url}")


def wait_port(port: int, attempts: int = 60) -> None:
    for _ in range(attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(1)
    raise RuntimeError(f"nothing listening on UNO port {port}")


def soffice_pids() -> set[str]:
    if platform.system() == "Windows":
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq soffice.bin", "/FO", "CSV", "/NH"], capture_output=True, text=True
        ).stdout
        pids = set()
        for line in out.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 2 and parts[0].lower().startswith("soffice"):
                pids.add(parts[1])
        return pids
    out = subprocess.run(["pgrep", "-x", "soffice.bin"], capture_output=True, text=True).stdout
    return {pid.strip() for pid in out.splitlines() if pid.strip()}


def kill_pid(pid: str) -> None:
    if platform.system() == "Windows":
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    else:
        subprocess.run(["kill", "-9", pid], capture_output=True)


def install_oxt(profile_uri: str) -> None:
    """inc 162: build callosum.oxt + unopkg-add it into the isolated profile BEFORE soffice launches, so the
    Callosum menu/toolbar + the dispatcher component are registered when the selftest connects."""
    sys.path.insert(0, str(ROOT / "tools"))
    from build_libreoffice_oxt import build_oxt

    oxt = build_oxt()
    res = subprocess.run(
        [str(UNOPKG), "add", "--suppress-license", f"-env:UserInstallation={profile_uri}", str(oxt)],
        capture_output=True,
        text=True,
    )
    print(f"unopkg add rc={res.returncode} out={res.stdout.strip()[:160]} err={res.stderr.strip()[:160]}", flush=True)


def start_stack():
    db_url, p1, p2 = seed_db()
    print(f"seeded: {db_url}  ids={p1},{p2}", flush=True)
    env = dict(os.environ, CALLOSUM_DB_URL=db_url)
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.backend.api.app:app", "--host", "127.0.0.1", "--port", str(PORT_HTTP)],
        cwd=str(ROOT),
        env=env,
    )
    before = soffice_pids()
    soffice = None
    profile_dir = HERE / f"lo_profile_{os.getpid()}_{time.time_ns()}"
    try:
        profile = profile_dir.as_uri()
        install_oxt(profile)
        # unopkg's bootstrap soffice.bin can linger and hold the profile lock; clear it before launching ours.
        for pid in soffice_pids() - before:
            kill_pid(pid)
        time.sleep(2)
        soffice = subprocess.Popen(
            [
                str(SOFFICE),
                "--headless",
                "--norestore",
                "--nologo",
                "--nofirststartwizard",
                f"--accept=socket,host=localhost,port={PORT_UNO};urp;",
                f"-env:UserInstallation={profile}",
            ]
        )
        wait_http(f"http://127.0.0.1:{PORT_HTTP}/health")
        print("server up", flush=True)
        wait_port(PORT_UNO)
        print("soffice UNO socket up", flush=True)
        return server, soffice, before, p1, p2, profile_dir
    except Exception:
        teardown(server, soffice, before, profile_dir)  # never leak processes/profile on a startup failure
        raise


def teardown(server, soffice, before, profile_dir=None):
    for proc in (server, soffice):
        try:
            proc.terminate()
        except Exception:
            pass
    for pid in soffice_pids() - before:  # kill only the soffice.bin we spawned
        kill_pid(pid)
    time.sleep(1)
    if profile_dir is not None:
        shutil.rmtree(profile_dir, ignore_errors=True)


def main() -> int:
    serve = len(sys.argv) > 1 and sys.argv[1] == "serve"
    server, soffice, before, p1, p2, profile_dir = start_stack()
    try:
        if serve:
            print(f"READY base=http://127.0.0.1:{PORT_HTTP} ids={p1},{p2} uno_port={PORT_UNO}", flush=True)
            while True:
                time.sleep(3600)
        print("---- selftest (live) ----", flush=True)
        try:
            return subprocess.run(
                [str(LO_PYTHON), str(SELFTEST), f"http://127.0.0.1:{PORT_HTTP}", str(p1), str(p2), str(PORT_UNO)],
                timeout=1500,  # the cumulative style/note/conversion/lifecycle suite now exceeds 12 minutes on
                # Windows; retain a bounded ceiling without skipping the installed-Writer proof
            ).returncode
        except subprocess.TimeoutExpired:
            print("SELFTEST TIMED OUT", flush=True)
            return 2
    finally:
        if not serve:
            teardown(server, soffice, before, profile_dir)


if __name__ == "__main__":
    print(json.dumps({"root": str(ROOT), "soffice": str(SOFFICE), "lo_python": str(LO_PYTHON)}))
    sys.exit(main())
