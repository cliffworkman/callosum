"""Collector for the native-messaging probe: records what the EXTENSION side observed.

EXPERIMENTAL HARNESS for issue #61. Not product code.

Note for anyone reading the earlier results: this file was committed with a broken string literal
(a literal newline inside `"\n"`), so it could not start and captured nothing. The previous
increment's failure-mode matrix therefore rests entirely on the HOST-side log
(`probe-log.jsonl`) — "was the host launched, or not" — which is independent of this collector and
is the evidence that actually matters for "fails closed". Fixed here.
"""

from __future__ import annotations

import json
import pathlib
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

OUT = pathlib.Path(__file__).with_name("observed.jsonl")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's required spelling
        query = urllib.parse.urlparse(self.path).query
        raw = urllib.parse.parse_qs(query).get("r", ["{}"])[0]
        with OUT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"observed": json.loads(raw)}) + "\n")
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args: object) -> None:
        """Silence the default stderr access log — the probe's own files are the record."""


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8777), Handler).serve_forever()
