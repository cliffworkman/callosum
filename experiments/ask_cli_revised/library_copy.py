"""The experiment library copy: fingerprinted once, verified read-only before and after every scored run.

The live library is never touched by an experiment and the copy must not move under it either. A run whose copy
drifted (a stray write, a checkpoint, a swapped file) is not comparable to one that did not, so verification fails
closed. The stored fingerprint holds only counts, ids, size and a whole-file hash — no paper text and no paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

_COUNTED_TABLES = ("papers", "attachments", "chunks", "chunk_structure", "embeddings", "cluster_node_papers")
_HASH_BLOCK = 1 << 20


class LibraryCopyDrift(RuntimeError):
    """The library copy is missing, unreadable, or no longer matches its frozen fingerprint."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_HASH_BLOCK):
            digest.update(block)
    return digest.hexdigest()


def _wal_bytes(path: Path) -> int:
    wal = path.with_name(path.name + "-wal")
    return wal.stat().st_size if wal.exists() else 0


def fingerprint(db_path: Path | str) -> dict:
    """Read-only fingerprint of ``db_path``: table counts, max ids, soft-deleted papers, size, sha256, WAL bytes.

    Opened ``immutable`` so this can neither create a WAL/SHM sidecar nor checkpoint; a non-empty WAL is reported
    (``wal_bytes``) rather than read, and any difference in it fails verification.
    """
    path = Path(db_path)
    if not path.is_file():
        raise LibraryCopyDrift("library copy is missing")
    uri = f"file:{path.resolve().as_posix()}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    try:
        counts = {name: con.execute(f"select count(*) from {name}").fetchone()[0] for name in _COUNTED_TABLES}  # noqa: S608 - fixed allowlist
        deleted = con.execute("select count(*) from papers where deleted_at is not null").fetchone()[0]
        max_chunk = con.execute("select coalesce(max(id), 0) from chunks").fetchone()[0]
        max_paper = con.execute("select coalesce(max(id), 0) from papers").fetchone()[0]
    finally:
        con.close()
    return {
        "counts": counts,
        "deleted_papers": deleted,
        "max_chunk_id": max_chunk,
        "max_paper_id": max_paper,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "wal_bytes": _wal_bytes(path),
    }


def freeze(db_path: Path | str, frozen_path: Path | str) -> dict:
    """Record the copy's fingerprint next to it (private; never committed)."""
    record = fingerprint(db_path)
    Path(frozen_path).write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def verify(db_path: Path | str, frozen_path: Path | str) -> dict:
    """Return the current fingerprint if it equals the frozen one, else raise ``LibraryCopyDrift``."""
    frozen = Path(frozen_path)
    if not frozen.is_file():
        raise LibraryCopyDrift("no frozen fingerprint for the library copy")
    expected = json.loads(frozen.read_text(encoding="utf-8"))
    actual = fingerprint(db_path)
    changed = sorted(key for key in expected if expected[key] != actual.get(key))
    if changed:
        raise LibraryCopyDrift(f"library copy drifted from its frozen fingerprint: {', '.join(changed)}")
    return actual


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["freeze", "verify"])
    parser.add_argument("--db", required=True)
    parser.add_argument("--frozen", help="fingerprint file (default: <db>.fingerprint.json)")
    args = parser.parse_args(argv)
    frozen = args.frozen or f"{args.db}.fingerprint.json"
    try:
        record = freeze(args.db, frozen) if args.command == "freeze" else verify(args.db, frozen)
    except LibraryCopyDrift as exc:
        print(f"LIBRARY COPY DRIFT: {exc}")
        return 1
    shown = {k: v for k, v in record.items() if k != "sha256"}
    print(f"library copy {args.command}: {json.dumps(shown)} sha256={record['sha256'][:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
