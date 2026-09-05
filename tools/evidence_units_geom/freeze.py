"""Record the frozen H1a input state and run corpus-level distribution sanity checks.

Increment 577 shipped a bug where the research prototype and the production SQLAlchemy path
disagreed catastrophically -- `chunks.bbox_json` is a JSON column, so a DB read returns a decoded
list while a fixture returns a string, and `json.loads()` on the list raised a TypeError that a
broad `except` swallowed. Every geometry rule was silently disabled: 3,228 repeats detected but all
misfiled `middle_band`, zero running heads, zero table debris. Fixture tests passed throughout.

So every detector in this study is checked BOTH ways: fixture-level correctness and corpus-level
distribution sanity. A detector that returns zero, or that returns everything, fails the sanity
check even when its unit tests are green.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STUDY_DIR = ROOT / ".local" / "evidence-units-geom"
DB = STUDY_DIR / "h1a.sqlite"

# A detector whose share falls outside these bounds is reporting nonsense even if its tests pass.
SANITY_BOUNDS = {
    "unknown": (0.20, 0.80),
    "body_prose": (0.03, 0.40),
    "reference_entry": (0.02, 0.30),
    "table_cell_debris": (0.01, 0.35),
    "running_head": (0.005, 0.15),
    "caption": (0.005, 0.10),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    import sqlite3

    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()
    migration = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    total_papers = conn.execute("SELECT COUNT(DISTINCT paper_id) FROM chunks").fetchone()[0]
    dist = dict(conn.execute("SELECT chunk_type, COUNT(*) FROM chunk_structure GROUP BY 1").fetchall())
    roles = dict(conn.execute("SELECT evidence_role, COUNT(*) FROM chunk_structure GROUP BY 1").fetchall())
    classified = sum(dist.values())

    # Geometry parse rate -- the exact signal the inc-577 bug drove to zero.
    geom_ok = 0
    for (raw,) in conn.execute("SELECT bbox_json FROM chunks WHERE bbox_json IS NOT NULL LIMIT 4000"):
        spans = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        if isinstance(spans, list) and spans and isinstance(spans[0], dict) and "x0" in spans[0]:
            geom_ok += 1

    print(f"H1a commit        : {head}")
    print(f"migration head    : {migration}")
    print(f"study DB          : {DB.name}")
    print(f"study DB sha256   : {sha256_file(DB)}")
    print(f"chunks            : {total_chunks} across {total_papers} papers")
    print(f"classified        : {classified}")
    print(f"geometry parseable: {geom_ok}/4000 sampled\n")

    print(f"{'chunk_type':<24}{'n':>7}{'share':>8}   sanity")
    failures = []
    for kind, n in sorted(dist.items(), key=lambda kv: -kv[1]):
        share = n / classified
        lo, hi = SANITY_BOUNDS.get(kind, (0.0, 1.0))
        ok = lo <= share <= hi
        if not ok:
            failures.append((kind, share, lo, hi))
        note = "ok" if ok else f"OUT OF BOUNDS [{lo:.3f},{hi:.3f}]"
        print(f"  {kind:<22}{n:>7}{100 * share:>7.1f}%   {note}")

    print(f"\nevidence_role: {roles}")
    # The two signals inc 577's bug zeroed out. Their absence is the canary.
    for canary in ("running_head", "running_footer", "table_cell_debris"):
        if dist.get(canary, 0) == 0:
            failures.append((canary, 0.0, 0.001, 1.0))
            print(f"  CANARY FAILED: {canary} is zero -- geometry is probably disabled")

    record = {
        "h1a_commit": head,
        "migration_head": migration,
        "study_db_sha256": sha256_file(DB),
        "total_chunks": total_chunks,
        "total_papers": total_papers,
        "chunk_type_distribution": dist,
        "evidence_role_distribution": roles,
        "geometry_parseable_sampled": geom_ok,
        "sanity_failures": failures,
    }
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    (STUDY_DIR / "freeze_record.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"\nsanity failures: {len(failures)}")
    print("wrote freeze_record.json")


if __name__ == "__main__":
    main()
