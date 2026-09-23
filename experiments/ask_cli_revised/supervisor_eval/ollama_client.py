"""Thin, model-agnostic Ollama client for the bakeoff. Loopback only.

The JUNO Ollama is reached through the standing SSH forward on 127.0.0.1:11434, so this client refuses
any non-loopback host: a typo can never send a prompt anywhere else. Every chat call is streamed so a
long thinking pass never sits behind an idle socket, and every Ollama timing field is captured.
Failures are *classified and returned*, never raised, so a crash/timeout is a recorded observation
rather than a lost one.
"""

import json
import time
from urllib.parse import urlparse

import httpx

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_TIMING_FIELDS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)


def gpu_fraction(ps_entry):
    size = ps_entry.get("size") or 0
    return (ps_entry.get("size_vram") or 0) / size if size else 0.0


def summarize_show(show):
    details = show.get("details") or {}
    info = show.get("model_info") or {}
    context = next((v for k, v in info.items() if k.endswith(".context_length")), None)
    license_text = (show.get("license") or "").strip()
    return {
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
        "quantization_level": details.get("quantization_level"),
        "context_length": context,
        "capabilities": list(show.get("capabilities") or []),
        "license_head": license_text.splitlines()[0][:120] if license_text else None,
    }


def _split_think(content):
    if content.lstrip().startswith("<think>") and "</think>" in content:
        head, _, rest = content.partition("</think>")
        return rest.strip(), head.split("<think>", 1)[1].strip()
    return content, None


class OllamaClient:
    def __init__(self, base_url="http://127.0.0.1:11434", *, transport=None, connect_timeout=10.0, read_timeout=900.0):
        if urlparse(base_url).hostname not in LOOPBACK_HOSTS:
            raise ValueError(f"refusing non-loopback Ollama endpoint {base_url!r}; use the SSH forward on 127.0.0.1")
        self._http = httpx.Client(
            base_url=base_url,
            transport=transport,
            timeout=httpx.Timeout(connect_timeout, read=read_timeout, write=60.0, pool=30.0),
        )

    def close(self):
        self._http.close()

    def _get(self, path):
        response = self._http.get(path)
        response.raise_for_status()
        return response.json()

    def version(self):
        return self._get("/api/version")["version"]

    def tags(self):
        return self._get("/api/tags").get("models", [])

    def ps(self):
        return self._get("/api/ps").get("models", [])

    def show(self, model):
        response = self._http.post("/api/show", json={"model": model})
        response.raise_for_status()
        return response.json()

    def unload(self, model):
        self._http.post("/api/generate", json={"model": model, "keep_alive": 0})

    def pull(self, model, on_progress=None):
        try:
            with self._http.stream(
                "POST", "/api/pull", json={"model": model, "stream": True}, timeout=httpx.Timeout(10.0, read=None)
            ) as response:
                if response.status_code != 200:
                    return {
                        "status": "error",
                        "error": f"HTTP {response.status_code}: {response.read().decode(errors='replace')[:400]}",
                    }
                last = {}
                for line in response.iter_lines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if "error" in row:
                        return {"status": "error", "error": row["error"]}
                    last = row
                    if on_progress:
                        on_progress(row)
                return last or {"status": "error", "error": "empty pull response"}
        except httpx.HTTPError as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    def chat(
        self, model, prompt, *, schema, options, think=None, keep_alive="30m", wall_timeout=1200.0, clock=time.monotonic
    ):
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "format": schema,
            "options": dict(options),
            "keep_alive": keep_alive,
        }
        if think is not None:
            body["think"] = think
        start = clock()
        state = {"content": [], "thinking": [], "final": {}, "first_token": None}

        def record(status, error=None):
            content, inline_think = _split_think("".join(state["content"]))
            thinking = "".join(state["thinking"]) or inline_think
            final = state["final"]
            timings = {k: final.get(k) for k in _TIMING_FIELDS}
            eval_s = (timings["eval_duration"] or 0) / 1e9
            return {
                "status": status,
                "error": error,
                "content": content,
                "thinking": thinking,
                "done_reason": final.get("done_reason"),
                "timings": timings,
                "wall_seconds": clock() - start,
                "time_to_first_token": state["first_token"],
                "generation_tokens_per_second": (timings["eval_count"] / eval_s) if eval_s else None,
            }

        try:
            with self._http.stream("POST", "/api/chat", json=body) as response:
                if response.status_code != 200:
                    text = response.read().decode(errors="replace")[:400]
                    return record("http_error", f"HTTP {response.status_code}: {text}")
                for line in response.iter_lines():
                    if clock() - start > wall_timeout:
                        return record("timeout", f"wall-clock watchdog exceeded {wall_timeout:.0f}s")
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if "error" in row:
                        return record("runtime_error", str(row["error"]))
                    message = row.get("message") or {}
                    if message.get("content") or message.get("thinking"):
                        if state["first_token"] is None:
                            state["first_token"] = clock() - start
                        state["content"].append(message.get("content") or "")
                        state["thinking"].append(message.get("thinking") or "")
                    if row.get("done"):
                        state["final"] = row
                return record("ok")
        except httpx.TimeoutException as exc:
            return record("timeout", f"{type(exc).__name__}: {exc}")
        except httpx.HTTPError as exc:
            return record("transport_error", f"{type(exc).__name__}: {exc}")
