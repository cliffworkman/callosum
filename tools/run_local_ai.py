"""Start managed Local AI for a DEV (browser) session, with the packaged desktop app closed (backlog #72).

Why this exists
---------------
`_preview_descriptor_path()` requires `CALLOSUM_APP_DATA_DIR`, and the only thing that ever sets it is the
Tauri shell (`src-tauri/src/backend.rs`). So a source-checkout backend -- `tools/run_dev.py`, or a bare
`uvicorn` -- can never reach Local AI: `resolve_managed_local_provider()` raises `app_data_missing` and every
generative feature fails (inc 568 made that failure honest; it did not make it go away). Testing any
Local-AI-backed change therefore meant a full Tauri rebuild, an hours-long loop.

This launcher starts the SAME llama-server the packaged app would, from the SAME already-installed and
already-verified artifacts, and publishes a descriptor the unmodified `load_preview_target()` accepts.

Scope boundary (deliberate, read before extending)
--------------------------------------------------
CLAUDE.md records that **Tauri alone owns the managed llama-server lifecycle** (incs 498/547). That governs
the SHIPPED PRODUCT -- what an end user's installed app does. This is a developer-only tool under `tools/`,
outside production paths, following the inc-542 precedent (the approved developer-only MariaDB executor).
The boundary is kept by construction, not by promise:

* **Zero production code changes.** Nothing in `app/` or `integrations/` knows this file exists. It only
  writes files that the unmodified `load_preview_target()` already validates and is free to reject.
* **It never downloads anything.** Install Local AI once through the desktop app; this tool deliberately
  has no downloader and no network access at all beyond its own loopback readiness probe.
* **It writes to a separate dev directory**, never the packaged app's, so it cannot clobber the real
  descriptor and both can run at the same time.

Usage
-----
    python tools/run_local_ai.py            # start, print the dev app-data dir, run until Ctrl-C
    python tools/run_dev.py --local-ai      # the normal path: both servers + this, one supervisor

Platform note: verified on Windows. The artifact layout is resolved dynamically rather than hard-coded, but
macOS/Linux are UNVERIFIED -- see INCREMENT-569-NOTES.md rather than assuming parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # script mode omits the project root (the inc-508 run_https.py trap)

# Import the real constants rather than re-typing them: this file's whole job is to produce a descriptor the
# validator accepts, so a silent drift between the two would be the one bug most likely to waste a day.
from app.backend.llm.managed_local import (  # noqa: E402
    _PREVIEW_CONTEXT_TOKENS,
    _PREVIEW_OUTPUT_TOKENS,
    EXPECTED_PREVIEW_MODEL_DIGEST,
    MODEL_ALIAS,
    PREVIEW_QUALIFICATION_STATE,
)

# Imported, never restated: `_target_from_payload` pins this exact value for a non-developer
# qualification state and fails CLOSED on a mismatch, so a hardcoded copy here silently breaks the dev
# launcher the moment the real cap moves -- which is exactly what happened when it went 2048 -> 4096.
PREVIEW_MAX_OUTPUT_TOKENS = _PREVIEW_OUTPUT_TOKENS
READINESS_TIMEOUT = 300.0  # a cold 1.04 GiB model load on CPU is slow; this is a ceiling, not an expectation
READINESS_INTERVAL = 1.0
HASH_CHUNK = 1024 * 1024


def _default_app_data() -> Path | None:
    """Where the packaged desktop app keeps its artifacts (identifier `com.callosum.desktop`)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return Path(base) / "com.callosum.desktop" if base else None
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "com.callosum.desktop"
    return Path.home() / ".local" / "share" / "com.callosum.desktop"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:  # streamed: the model is ~1 GiB and must not be read into memory
        for block in iter(lambda: handle.read(HASH_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _launcher_name() -> str:
    return "llama-server.exe" if sys.platform == "win32" else "llama-server"


def _find_artifacts(install_dir: Path) -> tuple[dict, Path, Path]:
    """Resolve install.json, the llama-server launcher, and the model, or explain exactly what is missing."""
    manifest_path = install_dir / "install.json"
    if not manifest_path.is_file():
        raise SystemExit(
            f"No Local AI installation at {install_dir}.\n"
            "Install it once through the packaged desktop app (Settings -> AI features -> Set up Local AI).\n"
            "This developer tool deliberately has no downloader."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    models = sorted(install_dir.glob("*.gguf"))
    if len(models) != 1:
        raise SystemExit(f"Expected exactly one .gguf in {install_dir}, found {len(models)}.")

    launchers = sorted(install_dir.glob(f"*/{_launcher_name()}"))
    if len(launchers) != 1:
        raise SystemExit(f"Expected exactly one {_launcher_name()} under {install_dir}, found {len(launchers)}.")
    return manifest, launchers[0], models[0]


def _verify(manifest: dict, launcher: Path, model: Path) -> None:
    """Re-hash both artifacts before exec. This is what makes re-using files we did not fetch defensible:
    a swapped binary or model is rejected here rather than silently launched and trusted."""
    for label, path, expected in (
        ("runtime launcher", launcher, manifest.get("runtime_launcher_sha256")),
        ("model", model, manifest.get("model_sha256")),
    ):
        actual = _sha256(path)
        if actual != expected:
            raise SystemExit(f"{label} digest mismatch for {path}\n  expected {expected}\n  actual   {actual}")
    if manifest.get("model_sha256") != EXPECTED_PREVIEW_MODEL_DIGEST:
        raise SystemExit(
            "The installed model is not the pinned preview model; `load_preview_target()` would reject it."
        )
    if manifest.get("declared_build_backend") != "cpu":
        raise SystemExit(
            f"Only the CPU runtime is supported here (found {manifest.get('declared_build_backend')!r}). "
            "A GPU bundle would need its observed execution verified differently."
        )


def _install_shutdown_handlers() -> None:
    """Turn the signals a supervisor actually sends into KeyboardInterrupt, so `finally` cleanup runs.

    Only SIGINT unwinds the stack by default. A Windows CTRL_BREAK_EVENT or a SIGTERM from `run_dev.py`
    otherwise terminates the interpreter outright (observed: exit 0xC000013A), leaving a descriptor that
    points at a dead port -- a target the backend would then report as available and fail on at request
    time. That is precisely the silent-lie failure inc 568 existed to remove, so it is worth handling.

    A hard kill (TerminateProcess / SIGKILL) still cannot be intercepted by any in-process handler; the
    start-time removal in `_write_credential` is the backstop for that case.
    """

    def _raise(_signum, _frame):
        raise KeyboardInterrupt

    for name in ("SIGTERM", "SIGBREAK"):
        handler = getattr(signal, name, None)
        if handler is not None:
            signal.signal(handler, _raise)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _runtime_version(launcher: Path) -> str:
    """Record what the binary actually reports. `runtime_version` is length-bounded but not value-checked, so
    an honest observation beats a hard-coded string that could drift from the installed build."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no request-derived input
            [str(launcher), "--version"], capture_output=True, text=True, timeout=60, cwd=str(launcher.parent)
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Could not run {launcher} --version: {exc}") from exc
    for line in (result.stdout + result.stderr).splitlines():
        if "version" in line.lower():
            return line.strip()[:160]
    return f"llama.cpp {launcher.parent.name}"[:160]  # never observed in practice; still a bounded honest string


def _spawn(launcher: Path, model: Path, port: int, credential: Path, log: Path) -> subprocess.Popen:
    """Mirror the packaged app's argv (`managed_local_ai.rs::server_args`) rather than inventing one.

    Two elements are load-bearing and easy to get wrong:
    * `--api-key-file`, never `--api-key` -- an inline token would be visible in the process table to every
      other process on the machine. The packaged app deliberately passes a path; so do we.
    * `--log-verbosity 4` -- the `offloaded N/M layers to GPU` line the execution check depends on is emitted
      at trace level only. Drop this and observed execution becomes unverifiable.
    """
    argv = [
        str(launcher),
        "--model",
        str(model),
        "--host",
        "127.0.0.1",  # literal loopback, never 0.0.0.0
        "--port",
        str(port),
        "--ctx-size",
        str(_PREVIEW_CONTEXT_TOKENS),
        "--n-predict",
        str(PREVIEW_MAX_OUTPUT_TOKENS),
        "--threads",
        "4",
        "--temp",
        "0",
        "--seed",
        "42",
        "--api-key-file",
        str(credential),
        "--alias",
        MODEL_ALIAS,
        "--no-webui",
        "--log-verbosity",
        "4",
        "--log-colors",
        "off",
        "--offline",
        "--n-gpu-layers",
        "0",
    ]
    handle = log.open("w", encoding="utf-8", errors="replace")
    return subprocess.Popen(argv, stdout=handle, stderr=subprocess.STDOUT, cwd=str(launcher.parent))  # noqa: S603


def _probe_once(port: int, token: str) -> str | None:
    """One pass of the packaged app's readiness contract (`managed_local_ai.rs::authenticated_probe`).

    A 200 from `/health` is not readiness: the model may still be loading, and an open socket says nothing
    about whether generation works. So this also requires the alias to be listed AND a real completion to
    come back. Returns the chat-template digest (or None when the server does not report one).
    """
    import httpx

    auth = {"Authorization": f"Bearer {token}"}
    base = f"http://127.0.0.1:{port}"
    if httpx.get(f"{base}/health", timeout=5.0).status_code // 100 != 2:
        raise RuntimeError("health not ok")

    models = httpx.get(f"{base}/v1/models", timeout=5.0).json()
    if not any(item.get("id") == MODEL_ALIAS for item in models.get("data", [])):
        raise RuntimeError(f"{MODEL_ALIAS} not listed yet")

    template_digest: str | None = None
    props = httpx.get(f"{base}/props", headers=auth, timeout=5.0)
    if props.status_code == 200:
        template = props.json().get("chat_template")
        if isinstance(template, str):
            template_digest = hashlib.sha256(template.encode("utf-8")).hexdigest()

    completion = httpx.post(
        f"{base}/v1/chat/completions",
        headers=auth,
        json={
            "model": MODEL_ALIAS,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 1,
            "temperature": 0,
            "seed": 42,
        },
        timeout=60.0,
    )
    content = completion.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise RuntimeError("completion returned no string content")
    return template_digest


def _await_ready(port: int, token: str, proc: subprocess.Popen) -> str | None:
    """Poll until the full contract passes. Never publish a descriptor before this returns."""
    deadline = time.monotonic() + READINESS_TIMEOUT
    last = "no response yet"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"llama-server exited during startup (code {proc.returncode}); see the log.")
        try:
            return _probe_once(port, token)
        except Exception as exc:  # noqa: BLE001 - the server is simply not up yet for most of this loop
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(READINESS_INTERVAL)
    raise SystemExit(f"llama-server did not become ready within {READINESS_TIMEOUT:.0f}s (last: {last}).")


def _verify_observed_execution(log: Path) -> None:
    """Confirm CPU/0-layer execution from the server's OWN output, positively.

    `_target_from_payload` requires `requested_execution == observed_execution`, and writing that pair
    without looking would make the descriptor assert something never observed. So this parses llama.cpp's
    trace line (`load_tensors: offloaded 0/25 layers to GPU`) the same way the packaged app does, and fails
    closed when it is absent -- silence is not proof of CPU execution.

    The offload COUNT is the whole signal, deliberately: `observation.rs` also treats backend as CPU iff
    zero layers were offloaded. Scanning for device-discovery lines instead would be wrong -- a machine can
    report `ggml_cuda_init: found 1 CUDA devices` and still be executing purely on CPU under `-ngl 0`, so
    that check would refuse to start on any developer machine that merely HAS a GPU.
    """
    text = log.read_text(encoding="utf-8", errors="replace").lower()
    offloaded: int | None = None
    for line in text.splitlines():
        if "offloaded " in line and " layers to gpu" in line:
            counts = line.split("offloaded ", 1)[1].split(" layers to gpu", 1)[0].strip()
            head, _, tail = counts.partition("/")
            if head.isdigit() and tail.isdigit():
                offloaded = int(head)
    if offloaded is None:
        raise SystemExit(
            f"Could not observe layer offload in {log} -- refusing to publish an unverified execution claim.\n"
            "Check that --log-verbosity 4 reached llama-server (the offload line is trace-level)."
        )
    if offloaded != 0:
        raise SystemExit(f"llama-server offloaded {offloaded} layers to GPU; this launcher declares CPU-only.")


def _write_credential(dev_dir: Path, token: str) -> Path:
    """Create the token file BEFORE spawning: llama-server reads it via `--api-key-file`, and
    `_credential_path` later requires exactly this name beside the descriptor.

    Any stale pair from a previous run is removed first, mirroring the packaged app -- a leftover descriptor
    pointing at a dead port is worse than none, because the backend would resolve it and fail at request time.
    """
    managed = dev_dir / "managed-local-ai"
    managed.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        managed.chmod(0o700)
    for name in ("target.json", "auth-token"):
        (managed / name).unlink(missing_ok=True)
    credential = managed / "auth-token"
    credential.write_text(token, encoding="utf-8")
    if sys.platform != "win32":
        credential.chmod(0o600)
    return credential


def _publish(
    dev_dir: Path, manifest: dict, port: int, credential: Path, runtime_version: str, template_digest: str | None
) -> Path:
    """Write the descriptor last -- its presence is the signal that the target is usable."""
    managed = dev_dir / "managed-local-ai"
    bundle_digest = manifest["runtime_bundle_manifest_sha256"]
    model_digest = manifest["model_sha256"]
    execution = {"backend": "cpu", "gpu_layers": 0}
    descriptor = managed / "target.json"
    descriptor.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "kind": "device_local",
                "wire_format": "chat_completions",
                "model_alias": MODEL_ALIAS,
                "runtime_family": "llama.cpp",
                # PREVIEW, not DEVELOPER_TEST_ONLY: the developer state is pinned to 256 max output tokens,
                # far too small to exercise primary synthesis, which is exactly what dev needs to test.
                "qualification_state": PREVIEW_QUALIFICATION_STATE,
                "target_id": f"llama-cpp-{bundle_digest[:12]}-{model_digest[:12]}",
                "endpoint": f"http://127.0.0.1:{port}",
                "credential_ref": str(credential),
                "runtime_version": runtime_version,
                "runtime_binary_digest": manifest["runtime_launcher_sha256"],
                "runtime_bundle_manifest_digest": bundle_digest,
                "declared_build_backend": "cpu",
                "model_artifact_digest": model_digest,
                # Read back from the server's own /props during readiness, exactly as the packaged app does.
                # The validator accepts null, so an absent template is recorded as absent, never invented.
                "chat_template_digest": template_digest,
                "context_tokens": _PREVIEW_CONTEXT_TOKENS,
                "max_output_tokens": PREVIEW_MAX_OUTPUT_TOKENS,
                "temperature": 0,
                "seed": 42,
                "requested_execution": execution,
                "observed_execution": execution,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return descriptor


def _cleanup(proc: subprocess.Popen | None, dev_dir: Path) -> None:
    """Remove the descriptor FIRST: a live descriptor pointing at a dead server is worse than none, because
    the backend would keep resolving it and failing at request time."""
    managed = dev_dir / "managed-local-ai"
    for name in ("target.json", "auth-token"):
        try:
            (managed / name).unlink(missing_ok=True)
        except OSError:
            pass
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        # terminate() kills only this PID; the packaged app uses `taskkill /T` so no descendant survives.
        subprocess.run(  # noqa: S603 - fixed argv apart from our own child's pid
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False
        )
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--install-dir", type=Path, default=None, help="managed-local-ai-install/ to use")
    parser.add_argument(
        "--dev-dir",
        type=Path,
        default=ROOT / ".local" / "dev-app-data",
        help="dev CALLOSUM_APP_DATA_DIR to publish into (never the packaged app's)",
    )
    args = parser.parse_args(argv)

    install_dir = args.install_dir
    if install_dir is None:
        packaged = _default_app_data()
        if packaged is None:
            raise SystemExit("Could not determine the packaged app data directory; pass --install-dir.")
        install_dir = packaged / "managed-local-ai-install"
    dev_dir: Path = args.dev_dir.resolve()
    if _default_app_data() is not None and dev_dir == _default_app_data().resolve():
        raise SystemExit("--dev-dir must not be the packaged app's data directory; it would clobber its descriptor.")

    _install_shutdown_handlers()
    manifest, launcher, model = _find_artifacts(install_dir)
    print(f"[local-ai] verifying artifacts in {install_dir} ...")
    _verify(manifest, launcher, model)
    print(f"[local-ai] ok: {manifest.get('model_id')} + llama.cpp {manifest.get('runtime_version')}")

    port, token = _free_port(), secrets.token_hex(32)
    dev_dir.mkdir(parents=True, exist_ok=True)
    log = dev_dir / "llama-server.log"
    proc: subprocess.Popen | None = None
    try:
        runtime_version = _runtime_version(launcher)
        credential = _write_credential(dev_dir, token)
        proc = _spawn(launcher, model, port, credential, log)
        print(f"[local-ai] starting llama-server on 127.0.0.1:{port} (log: {log})")
        template_digest = _await_ready(port, token, proc)
        _verify_observed_execution(log)
        descriptor = _publish(dev_dir, manifest, port, credential, runtime_version, template_digest)
        print(f"[local-ai] ready. descriptor: {descriptor}")
        print(f"[local-ai] point the backend at it with:  CALLOSUM_APP_DATA_DIR={dev_dir}")
        print("[local-ai] Ctrl-C to stop and remove the descriptor.")
        while proc.poll() is None:
            time.sleep(0.5)
        print(f"[local-ai] llama-server exited (code {proc.returncode}).")
        return 1
    except KeyboardInterrupt:
        print("\n[local-ai] stopping...")
        return 0
    finally:
        _cleanup(proc, dev_dir)


if __name__ == "__main__":
    raise SystemExit(main())
