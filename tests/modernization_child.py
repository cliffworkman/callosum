"""Subprocess entry for inc 617's coordinator tests: a real second Callosum-like process on the same library.

Runs ``ModernizationCoordinator`` with the production classifier (slowed per paper, so a test can observe and kill it
mid-pass) and no verified model, so only classification runs. Leadership is the real OS lock, so a parent process
competing for the same library sees genuine cross-process ownership. ``--marker`` is touched once this process leads
and has committed at least one paper.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from app.backend.embeddings.resources import ResourceSnapshot
from app.backend.modernization import CoordinatorConfig, ModernizationCoordinator
from app.backend.modernization.classification import SourceRoleClassifier
from app.backend.pdf_processing.structure_backfill import derive_paper
from app.backend.persistence.database import make_engine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--marker", required=True)
    args = parser.parse_args()
    engine = make_engine(args.db_url)
    derived = 0

    def slow_derive(conn, paper_id, references):  # type: ignore[no-untyped-def]
        nonlocal derived
        written = derive_paper(conn, paper_id, references)
        time.sleep(args.delay)  # inside the paper's transaction: a kill here must roll the paper back
        derived += 1
        return written

    classifier = SourceRoleClassifier(
        engine,
        args.db_url,
        probe=lambda: ResourceSnapshot(16000, 8000, 26000, 9000, "test"),
        disk_usage=lambda _p: type("Usage", (), {"free": 10**12})(),
        derive=slow_derive,
        papers_per_pass=1,
    )
    coordinator = ModernizationCoordinator(
        engine,
        CoordinatorConfig(db_url=args.db_url),
        supervisor=lambda: None,
        model_status=lambda: {"state": "absent"},
        classifier=classifier,
    )
    marker = Path(args.marker)
    while True:
        delay = coordinator.tick()
        if derived and coordinator.is_leader and not marker.exists():
            marker.write_text("leading", encoding="utf-8")
        if delay > 0:
            time.sleep(0.05)


if __name__ == "__main__":
    raise SystemExit(main())
