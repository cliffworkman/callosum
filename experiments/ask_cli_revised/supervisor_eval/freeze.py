"""Freeze = hash-pin everything a candidate is judged by, including inputs we never publish.

`FREEZE.txt` (committed) holds only digests: the code that scores, the public manifest, the run
envelope, and the sha256 of each private file (verbatim quotes, rendered prompts). Anyone holding the
private inputs can verify every candidate saw the same battery without those inputs being published.

Code files are hashed with line endings normalized: the demo/showcase drift gates were once silently
green locally and red in CI because a CRLF checkout hashed differently.
"""

import hashlib
import json
from pathlib import Path

from experiments.ask_070.hashing import digest

FREEZE_VERSION = 1


def normalized_sha256(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _hash_code(files):
    return {name: normalized_sha256(Path(path).read_bytes()) for name, path in sorted(files.items())}


def _hash_private(files):
    out = {}
    for name, path in sorted(files.items()):
        p = Path(path)
        out[name] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING"
    return out


def _body(spec):
    return {
        "freeze_version": FREEZE_VERSION,
        "code_files": _hash_code(spec["code_files"]),
        "json": {name: digest(obj) for name, obj in sorted(spec["json"].items())},
        "private_files": _hash_private(spec["private_files"]),
    }


def compute(spec):
    body = _body(spec)
    return {**body, "freeze_sha256": digest(body)}


def write(path, frozen):
    Path(path).write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def verify(path, spec):
    """Return a list of mismatches (empty = the frozen battery is intact)."""
    stored = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = []
    body = {k: v for k, v in stored.items() if k != "freeze_sha256"}
    if digest(body) != stored.get("freeze_sha256"):
        problems.append("freeze_sha256 does not match the freeze file's own contents (file was edited)")
    current = _body(spec)
    for section in ("code_files", "json", "private_files"):
        for name in sorted(set(stored.get(section, {})) | set(current[section])):
            was, now = stored.get(section, {}).get(name), current[section].get(name)
            if now == "MISSING":
                problems.append(f"{section}/{name}: missing")
            elif was != now:
                problems.append(f"{section}/{name}: changed since freeze")
    return problems
