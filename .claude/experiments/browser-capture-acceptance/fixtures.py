"""Local HTML/PDF fixtures for the packaged acceptance harness -- no live publisher pages.

Each fixture is served over a throwaway http://127.0.0.1 server (not file://, which extensions
cannot script without a manual "Allow access to file URLs" toggle) so the harness never depends on
a real journal site staying up or keeping its markup stable.
"""

from __future__ import annotations

import http.server
import socket
import threading
from pathlib import Path

SCHOLARLY_HTML = """<!doctype html>
<html><head>
<title>A Fixture Paper</title>
<meta name="citation_doi" content="10.9999/fixture-a">
<meta name="citation_title" content="A Fixture Scholarly Paper">
<meta name="citation_author" content="Ada Lovelace">
<meta name="citation_journal_title" content="Journal of Acceptance Testing">
<meta name="citation_publication_date" content="2024/01/01">
</head><body><h1>A Fixture Scholarly Paper</h1></body></html>
"""

# Case E reuses the SAME doi as the scholarly fixture above so the paper the direct-PDF click
# targets already exists with an attachment -- "unsafe attachment state" per the plan's Case E.
EXISTING_ATTACHMENT_HTML = SCHOLARLY_HTML


def write_fixture_pdf(path: Path) -> None:
    """A real, minimally valid one-page PDF -- generated with PyMuPDF (already a project
    dependency), not hand-crafted bytes, so it round-trips through the real admission PDF checks
    exactly like the request-body validation in capture.py does."""
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Fixture PDF for case B")
    document.save(str(path))
    document.close()


class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        pass  # keep the harness's own output readable


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve_fixtures(fixture_dir: Path) -> tuple[threading.Thread, http.server.HTTPServer, int]:
    """Serve `fixture_dir` at 127.0.0.1:<port> on a background thread. Caller shuts it down."""
    (fixture_dir / "scholarly.html").write_text(SCHOLARLY_HTML, encoding="utf-8")
    write_fixture_pdf(fixture_dir / "paper.pdf")

    port = _free_port()
    server = http.server.HTTPServer(
        ("127.0.0.1", port), lambda *a, **kw: _Handler(*a, directory=str(fixture_dir), **kw)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread, server, port
