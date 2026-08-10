"""Thin HTTP client over the running callosum app for the TUI.

Modeled on mcp_server/client.py: httpx with an injectable transport so the hermetic tests can
drive an httpx.MockTransport, a single CallosumUnavailable error for "not running / wrong URL /
auth", and the 401 hint naming the fix. Unlike the MCP client this one covers writes — the
registry (tui/registry.py) decides which writes are reachable in agent mode, not this module.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
JOB_DONE_STATES = frozenset({"done", "completed", "complete", "succeeded", "error", "failed"})


class CallosumUnavailable(RuntimeError):
    """callosum isn't reachable (not running / wrong base URL / auth)."""


class AgentWritesDisabled(RuntimeError):
    """The agent-writes gate is off — enable it in callosum Settings → AI agent."""


class TuiClient:
    def __init__(
        self, base_url: str | None = None, *, token: str | None = None, http: httpx.Client | None = None
    ) -> None:
        self.base_url = (base_url or os.environ.get("CALLOSUM_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        token = token or os.environ.get("CALLOSUM_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = http or httpx.Client(base_url=self.base_url, headers=headers, timeout=60.0)

    # -- core ------------------------------------------------------------------

    def request(
        self, method: str, path: str, *, query: dict[str, Any] | None = None, body: Any | None = None
    ) -> httpx.Response:
        try:
            r = self._http.request(method, path, params=query or None, json=body if body is not None else None)
        except httpx.HTTPError as exc:
            raise CallosumUnavailable(
                f"callosum isn't reachable at {self.base_url} — is it running? "
                f"(cd ~/callosum && .venv/bin/uvicorn app.backend.api.app:app --port 8080) ({exc})"
            ) from exc
        return self._ok(r)

    @staticmethod
    def _ok(r: httpx.Response) -> httpx.Response:
        if r.status_code == 401:
            raise CallosumUnavailable(
                "callosum rejected the request (401) — set CALLOSUM_TOKEN to the app's access token."
            )
        if r.status_code == 403 and "agent" in r.text.lower():
            raise AgentWritesDisabled("AI-agent writes are disabled — enable them in callosum Settings → AI agent.")
        if r.status_code >= 400:
            detail = r.text[:300]
            try:
                detail = r.json().get("detail", detail)
            except Exception:
                pass
            raise CallosumUnavailable(f"callosum returned {r.status_code}: {detail}")
        return r

    @staticmethod
    def payload(r: httpx.Response) -> Any:
        if r.status_code == 204 or not r.content:
            return {"ok": True, "status": r.status_code}
        ctype = r.headers.get("content-type", "")
        if "application/json" in ctype:
            return r.json()
        return r.content  # binary (e.g. a PDF) or text export

    # -- jobs ------------------------------------------------------------------

    def poll_job(
        self, poll_template: str, job_id: str, *, timeout: float = 600.0, interval: float = 1.0, on_tick=None
    ) -> Any:
        """Poll a 202-style job endpoint until it reaches a terminal status."""
        path = poll_template.format(job_id=job_id)
        deadline = time.monotonic() + timeout
        last: Any = None
        while time.monotonic() < deadline:
            last = self.payload(self.request("GET", path))
            status = str(last.get("status", "")).lower() if isinstance(last, dict) else ""
            if status in JOB_DONE_STATES:
                return last
            if on_tick:
                on_tick(last)
            time.sleep(interval)
        raise CallosumUnavailable(
            f"job {job_id} did not finish within {int(timeout)}s (last state: "
            f"{json.dumps(last)[:200] if last is not None else 'none'}); "
            f"poll it yourself: GET {path}"
        )

    @staticmethod
    def job_id_of(payload: Any) -> str | None:
        if isinstance(payload, dict):
            jid = payload.get("job_id") or payload.get("id")
            if isinstance(jid, str) and jid:
                return jid
        return None

    # -- agent gate --------------------------------------------------------------

    def agent_writes_enabled(self) -> bool:
        data = self.payload(self.request("GET", "/agent/status"))
        return bool(isinstance(data, dict) and data.get("writes_enabled"))
