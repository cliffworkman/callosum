"""A separate, user-level Ollama for the bakeoff. The shared Ollama service is never touched.

The shared service (port 11434, `/usr/share/ollama`, systemd) keeps its version, models and configuration. This
module only builds commands for a second, self-contained server run as the ordinary JUNO user: its own binary
(a pinned upstream release, checksum-verified), its own model store, its own HOME/TMPDIR, its own loopback
port 11435. Every path lives under /media/brain/JUNO (the standing storage directive). No sudo, no systemctl,
no shared port, and no double quotes (they do not survive PowerShell -> plink -> the remote shell intact).
"""

import re

BASE_DIR = "/media/brain/JUNO/ollama-bakeoff"
MODELS_DIR = "/media/brain/JUNO/ollama-models/ask-070-bakeoff"
HOME_DIR = f"{BASE_DIR}/home"
TMP_DIR = f"{BASE_DIR}/tmp"
DL_DIR = f"{BASE_DIR}/dl"
PID_FILE = f"{BASE_DIR}/server.pid"
LOG_FILE = f"{BASE_DIR}/server.log"
PORT = 11435
HOST = f"127.0.0.1:{PORT}"
ASSET_NAME = "ollama-linux-amd64.tar.zst"
RELEASE_API = "https://api.github.com/repos/ollama/ollama/releases/latest"
_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_URL = "https://github.com/ollama/ollama/releases/download/{tag}/{name}"


def _tag(tag):
    if not isinstance(tag, str) or not _TAG.match(tag):
        raise ValueError(f"unsafe or non-stable release tag {tag!r}")
    return tag


def _pid(pid):
    if not isinstance(pid, int) or isinstance(pid, bool):
        raise ValueError(f"pid must be an integer, got {pid!r}")
    return pid


def install_dir(tag):
    return f"{BASE_DIR}/ollama-{_tag(tag)}"


def binary_path(tag):
    return f"{install_dir(tag)}/bin/ollama"


def pick_asset(release):
    """The verified linux/amd64 asset of a *stable* release, with its published sha256."""
    if release.get("prerelease") or release.get("draft"):
        raise ValueError("refusing a prerelease or draft Ollama release")
    tag = _tag(release.get("tag_name"))
    asset = next((a for a in release.get("assets", []) if a.get("name") == ASSET_NAME), None)
    if asset is None:
        raise ValueError(f"release {tag} has no {ASSET_NAME}")
    digest = asset.get("digest") or ""
    sha = digest.removeprefix("sha256:")
    if not digest.startswith("sha256:") or not _SHA.match(sha):
        raise ValueError(f"{ASSET_NAME} has no published sha256 digest; refusing an unverifiable download")
    url = asset.get("browser_download_url")
    if url != _URL.format(tag=tag, name=ASSET_NAME):
        raise ValueError(f"unexpected download URL {url!r}")
    return {"tag": tag, "name": ASSET_NAME, "url": url, "size": asset.get("size"), "sha256": sha}


def release_command():
    return f"curl -fsSL -m 30 {RELEASE_API}"


def prepare_command():
    return f"mkdir -p {BASE_DIR} {HOME_DIR} {TMP_DIR} {DL_DIR} {MODELS_DIR}"


def download_command(asset):
    return f"mkdir -p {DL_DIR} && curl -fL --retry 3 -C - -o {DL_DIR}/{asset['name']} {asset['url']}"


def sha256_command(asset):
    return f"sha256sum {DL_DIR}/{asset['name']}"


def verify_digest(asset, sha256sum_output):
    found = re.match(r"\s*([0-9a-f]{64})\b", sha256sum_output or "")
    return bool(found) and found.group(1) == asset["sha256"]


def extract_command(asset):
    target = install_dir(asset["tag"])
    return f"mkdir -p {target} && zstd -dc {DL_DIR}/{asset['name']} | tar -x -C {target}"


def start_command(tag):
    env = (
        f"HOME={HOME_DIR} TMPDIR={TMP_DIR} OLLAMA_HOST={HOST} OLLAMA_MODELS={MODELS_DIR} "
        "OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1"
    )
    return f"setsid nohup env {env} {binary_path(tag)} serve >> {LOG_FILE} 2>&1 < /dev/null & echo $! | tee {PID_FILE}"


def pid_command():
    return f"cat {PID_FILE}"


def stop_command(pid):
    return f"kill {_pid(pid)}"


def env_probe_command(pid):
    return f"cat /proc/{_pid(pid)}/environ | tr '\\0' '\\n' | grep '^OLLAMA_'"


def store_probe_command():
    return (
        f"P=$(cat {PID_FILE}); cat /proc/$P/environ | tr '\\0' '\\n' | grep '^OLLAMA_MODELS'; "
        f"echo '---DF---'; df -BG /media/brain/JUNO; echo '---DU---'; du -sh {MODELS_DIR} 2>&1"
    )


def identity_command(tag):
    binary = binary_path(tag)
    return (
        f"env OLLAMA_HOST={HOST} {binary} --version 2>&1; echo '---'; sha256sum {binary}; echo '---'; "
        "nvidia-smi --query-gpu=driver_version --format=csv,noheader"
    )


def log_tail_command():
    return f"grep -i -E 'inference compute|driver too old|no compatible' {LOG_FILE} | tail -6"


def parse_env(text):
    out = {}
    for line in (text or "").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.startswith("OLLAMA_"):
            out[key] = value.strip()
    return out


def parse_identity(text):
    parts = [p.strip() for p in (text or "").split("---")]
    if len(parts) < 3:
        return {}
    version = re.search(r"version is (\S+)", parts[0])
    sha = re.match(r"([0-9a-f]{64})\b", parts[1])
    if not (version and sha):
        return {}
    return {
        "binary_version": version.group(1),
        "binary_sha256": sha.group(1),
        "nvidia_driver": parts[2].splitlines()[0],
    }


def parse_gpu_backend(log_text):
    # the log is append-only across restarts: the LAST selection line is the one the running server made
    lines = [ln for ln in (log_text or "").splitlines() if "inference compute" in ln]
    if not lines:
        return {}
    line, out = lines[-1], {}
    for key in ("library", "compute", "name", "libdirs", "driver", "total", "available"):
        found = re.search(rf'\b{key}=(?:"([^"]*)"|(\S+))', line)
        if found:
            out[key] = found.group(1) if found.group(1) is not None else found.group(2)
    return out
