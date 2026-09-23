"""JUNO host observation for the bakeoff: GPU/RAM/swap/Ollama-RSS snapshots, a remote ~0.4 s sampler, and
the model-store assessment. Reaches JUNO only through juno.ps1, which owns the credential convention;
nothing here reads, builds, logs, or stores a credential. Remote commands contain no double quotes (they
do not survive PowerShell -> plink -> the remote shell intact); the sampler script is shipped as base64.

All remote scratch lives under /media/brain/JUNO (the standing directive: `/` has ~18 GB free).
"""

import base64
import os
import re
import shutil
import subprocess

REMOTE_DIR = "/media/brain/JUNO/01_WORK/ask-070-supervisor-bakeoff"
DEFAULT_JUNO_PS1 = r"C:\Users\cliff\Dropbox\Dropbox\01_Work\_networking\juno.ps1"
STORE_ROOT = "/media/brain/JUNO"
_SAFE = re.compile(r"^[A-Za-z0-9._-]+$")

SNAPSHOT_COMMAND = (
    "nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits; "
    "free -m; ps -C ollama -o rss= | awk '{s+=$1} END {print int(s/1024)}'"
)

STORE_COMMAND = (
    "systemctl show ollama -p Environment; "
    "sudo -n cat /proc/$(pgrep -o -x ollama)/environ 2>/dev/null | tr '\\0' '\\n' | grep '^OLLAMA_'; "
    "echo '---DF---'; df -BG / /media/brain/JUNO; echo '---DU---'; "
    "du -sh /usr/share/ollama/.ollama/models 2>&1"
)


def shell_executable(which=shutil.which):
    """juno.ps1 is unsigned: it runs under pwsh (RemoteSigned) but not under this machine's Windows PowerShell 5.1."""
    return "pwsh" if which("pwsh") else "powershell"


def run_remote(command, *, runner=subprocess.run, ps1=None, timeout=120):
    ps1 = ps1 or os.environ.get("JUNO_PS1", DEFAULT_JUNO_PS1)
    done = runner(
        [shell_executable(), "-NoProfile", "-File", ps1, command], capture_output=True, text=True, timeout=timeout
    )
    if done.returncode != 0:
        raise RuntimeError(f"remote command failed ({done.returncode}): {done.stderr.strip()[:400]}")
    return done.stdout


def parse_snapshot(text):
    lines = [line for line in text.strip().splitlines() if line.strip()]
    try:
        gpu = [int(x) for x in lines[0].replace(" ", "").split(",")]
        mem = next(line.split() for line in lines if line.startswith("Mem:"))
        swap = next(line.split() for line in lines if line.startswith("Swap:"))
        return {
            "gpu_mem_used_mib": gpu[0],
            "gpu_mem_total_mib": gpu[1],
            "gpu_util_pct": gpu[2],
            "ram_used_mib": int(mem[2]),
            "ram_available_mib": int(mem[6]),
            "swap_used_mib": int(swap[2]),
            "ollama_rss_mib": int(lines[-1]),
        }
    except (ValueError, IndexError, StopIteration):
        return {}


def snapshot(**kw):
    return parse_snapshot(run_remote(SNAPSHOT_COMMAND, **kw))


def summarize_samples(csv_text, start=None, end=None):
    """Peaks/troughs from sampler rows `ts,gpu_mib,gpu_util,ram_used,ram_avail,swap_used,ollama_rss`."""
    rows = []
    for line in csv_text.splitlines():
        try:
            ts, gpu, _util, used, avail, swap, rss = (float(x) for x in line.split(","))
        except ValueError:
            continue  # a torn/partial line at the moment of sampling
        if (start is None or ts >= start) and (end is None or ts <= end):
            rows.append((gpu, used, avail, swap, rss))
    if not rows:
        return {"n_samples": 0}
    cols = list(zip(*rows, strict=True))
    return {
        "n_samples": len(rows),
        "peak_gpu_mem_mib": int(max(cols[0])),
        "peak_ram_used_mib": int(max(cols[1])),
        "min_ram_available_mib": int(min(cols[2])),
        "peak_swap_used_mib": int(max(cols[3])),
        "peak_ollama_rss_mib": int(max(cols[4])),
    }


def sampler_script():
    return """#!/bin/bash
out="$1"
while true; do
  ts=$(date +%s.%N)
  g=$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits | tr -d ' ')
  m=$(free -m | awk 'NR==2{u=$3;a=$7} NR==3{s=$3} END{print u","a","s}')
  r=$(ps -C ollama -o rss= | awk '{s+=$1} END{print int(s/1024)}')
  echo "$ts,$g,$m,$r" >> "$out"
  sleep 0.4
done
"""


def _safe(token):
    if not _SAFE.match(str(token)):
        raise ValueError(f"unsafe token {token!r}")
    return str(token)


def deploy_command():
    payload = base64.b64encode(sampler_script().encode()).decode()
    return (
        f"mkdir -p {REMOTE_DIR} && echo {payload} | base64 -d > {REMOTE_DIR}/sampler.sh "
        f"&& chmod +x {REMOTE_DIR}/sampler.sh"
    )


def start_command(tag):
    tag = _safe(tag)
    return f"setsid nohup {REMOTE_DIR}/sampler.sh {REMOTE_DIR}/{tag}.csv >/dev/null 2>&1 < /dev/null & echo $!"


def stop_command(pid):
    if not isinstance(pid, int):
        raise ValueError(f"pid must be an integer, got {pid!r}")
    return f"kill {pid}"


def fetch_command(tag):
    return f"cat {REMOTE_DIR}/{_safe(tag)}.csv"


def assess_store(text, needed_gb, margin_gb=5.0):
    """Does the *active* Ollama store satisfy the /media/brain/JUNO directive and have room?"""
    if "---DF---" not in text:
        return {
            "ok": False,
            "store_path": None,
            "free_gb": None,
            "reason": "could not read the Ollama store configuration from JUNO",
        }
    env_part, _, rest = text.partition("---DF---")
    df_part = rest.partition("---DU---")[0]
    found = re.search(r"OLLAMA_MODELS=(\S+)", env_part)
    if not found:
        return {
            "ok": False,
            "store_path": None,
            "free_gb": None,
            "reason": "no OLLAMA_MODELS override found: Ollama's default store is on the small OS disk, "
            f"not {STORE_ROOT}",
        }
    path = found.group(1)
    if not (path == STORE_ROOT or path.startswith(STORE_ROOT + "/")):
        return {
            "ok": False,
            "store_path": path,
            "free_gb": None,
            "reason": f"the Ollama store {path} is not under {STORE_ROOT} (standing directive)",
        }
    free = None
    best = -1
    for line in df_part.splitlines():
        cols = line.split()
        if len(cols) >= 6 and cols[3].endswith("G"):
            mount = cols[-1]
            if (path == mount or path.startswith(mount.rstrip("/") + "/")) and len(mount) > best:
                best, free = len(mount), float(cols[3][:-1])
    if free is None:
        return {"ok": False, "store_path": path, "free_gb": None, "reason": "could not determine free space"}
    if free < needed_gb + margin_gb:
        return {
            "ok": False,
            "store_path": path,
            "free_gb": free,
            "reason": f"only {free:.0f} GB free at {path}; the model needs about {needed_gb:.1f} GB "
            f"plus a {margin_gb:.0f} GB margin",
        }
    return {"ok": True, "store_path": path, "free_gb": free, "reason": None}


class JunoSampler:
    """Background remote sampler around one candidate's battery. Failure degrades to a note; it never aborts a run."""

    def __init__(self, run=run_remote, out_dir=None):
        self._run, self._out_dir = run, out_dir
        self._pid = self._tag = self._error = None

    def start(self, tag):
        try:
            self._run(deploy_command())
            out = self._run(start_command(tag))
            self._pid, self._tag = int(out.strip().splitlines()[-1]), tag
        except (RuntimeError, ValueError, IndexError) as exc:
            self._error = f"sampler unavailable: {exc}"

    def stop(self):
        if self._pid is None:
            return {"n_samples": 0, **({"error": self._error} if self._error else {})}
        try:
            self._run(stop_command(self._pid))
            csv_text = self._run(fetch_command(self._tag))
        except RuntimeError as exc:
            return {"n_samples": 0, "error": f"sampler unavailable: {exc}"}
        finally:
            self._pid = None
        if self._out_dir is not None:
            (self._out_dir / f"{self._tag}.csv").write_text(csv_text, encoding="utf-8", newline="\n")
        return summarize_samples(csv_text)
