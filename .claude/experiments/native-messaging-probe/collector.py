"""Collector for the native-messaging probe: records what the extension observed."""
import json, pathlib, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

OUT = pathlib.Path(__file__).with_name("observed.jsonl")

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        r = urllib.parse.parse_qs(q).get("r", ["{}"])[0]
        with OUT.open("a", encoding="utf-8") as f:
            f.write(r + "
")
        self.send_response(204); self.end_headers()
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", 8777), H).serve_forever()
