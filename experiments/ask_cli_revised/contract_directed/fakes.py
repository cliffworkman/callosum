"""Test doubles: a scripted stand-in for the Ollama client and a tiny in-memory library. Never used by a live run."""

from __future__ import annotations

import json

from experiments.ask_cli_revised.contract_directed import seams


class FakeClient:
    """`responder(kind, prompt, schema)` returns a dict/list (JSON answer), a string (raw content) or a full call dict."""

    def __init__(self, responder):
        self.responder = responder
        self.calls: list[dict] = []

    @staticmethod
    def _wrap(out) -> dict:
        if isinstance(out, dict) and "status" in out:
            return out
        content = out if isinstance(out, str) else json.dumps(out)
        return {
            "status": "ok", "error": None, "content": content, "thinking": "", "done_reason": "stop",
            "timings": {"prompt_eval_count": 10, "eval_count": 5}, "wall_seconds": 0.01,
        }  # fmt: skip

    def chat(self, model, prompt, *, schema, options, think=None, keep_alive=None, wall_timeout=None):
        self.calls.append(
            {"kind": "json", "prompt": prompt, "schema": schema, "think": think, "options": dict(options)}
        )
        return self._wrap(self.responder("json", prompt, schema))

    def chat_free(self, model, prompt, *, options, think=False, keep_alive=None, wall_timeout=None):
        self.calls.append({"kind": "free", "prompt": prompt, "schema": None, "think": think, "options": dict(options)})
        return self._wrap(self.responder("free", prompt, None))


class FakeLibrary:
    """One attachment; seams never verify unless a verifier is supplied; no links unless the chunks contain a definition."""

    def __init__(self, chunks, *, paper=None, verifier=None):
        self._chunks = chunks
        self._paper = paper or {"id": 1, "title": "A paper", "abstract": None}
        self._verifier = verifier or (lambda a, b: seams.SeamVerdict("not_established", ("fake",), {}))

    def attachment_chunks(self, attachment_id):
        return self._chunks

    def paper(self, paper_id):
        return self._paper

    def attachment(self, attachment_id):
        return {"id": attachment_id, "role": "primary", "checksum": "abc", "is_primary": True}

    def chunk(self, chunk_id):
        return next(c for c in self._chunks if c["chunk_id"] == chunk_id)

    def seam_verifier(self):
        return self._verifier


def fake_chunk(cid, text, **over):
    base = {
        "chunk_id": cid, "paper_id": 1, "attachment_id": 9, "text": text, "section": "results", "grobid_kind": None,
        "page_start": 1, "page_end": 1, "char_start": cid * 1000, "char_end": cid * 1000 + len(text),
    }  # fmt: skip
    return base | over
