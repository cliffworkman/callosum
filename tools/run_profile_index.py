"""Drive a supervised profile index build from a terminal, exactly as the app does (developer tool, inc 610).

Uses the production ``IndexSupervisor`` + ``SubprocessLauncher`` + worker -- no separate indexing logic -- so a run
here exercises the same reconciliation, resource policy and bounded recovery the Settings button does. It first
reconciles whatever a previous (possibly killed) run left behind, then starts or resumes the build, samples memory,
and exits when the build reaches a terminal state. Ctrl-C stops the owned worker like an app exit (``interrupted``,
work committed). ``--kill-after-chunks N`` kills the worker once from outside after N new vectors, to prove
checkpoint recovery on a real model. Not reachable from the app; no endpoint.

    python tools/run_profile_index.py --db-url sqlite:///C:/path/copy.sqlite --profile arctic-s --local-files-only
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backend.embeddings import index_runs  # noqa: E402
from app.backend.embeddings.index_supervisor import IndexSupervisor, SupervisorConfig  # noqa: E402
from app.backend.embeddings.profiles import get_profile, profile_coverage  # noqa: E402
from app.backend.embeddings.resources import ResourcePolicy, measure, process_rss_mb  # noqa: E402
from app.backend.persistence.database import make_engine  # noqa: E402

TERMINAL = ("completed", "failed", "paused", "cancelled", "interrupted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--profile", default="arctic-s")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--kill-after-chunks", type=int, default=0)
    parser.add_argument("--samples", type=Path, required=True, help="JSONL resource/progress samples")
    parser.add_argument("--sample-seconds", type=float, default=10.0)
    args = parser.parse_args()

    engine = make_engine(args.db_url)
    profile = get_profile(args.profile)
    supervisor = IndexSupervisor(engine, SupervisorConfig(db_url=args.db_url, local_files_only=args.local_files_only))
    policy = ResourcePolicy.for_machine(measure())
    log = args.samples.open("a", encoding="utf-8")

    def emit(event: str, **extra: object) -> None:
        row = supervisor.row(profile.key) or {}
        live = supervisor._live.get(profile.key)
        rss = process_rss_mb(live.handle.pid) if live is not None else None
        record = {
            "t": round(time.time(), 1),
            "event": event,
            "state": row.get("state"),
            "indexed": row.get("indexed_chunks"),
            "eligible": row.get("eligible_chunks"),
            "batch_size": row.get("batch_size"),
            "attempts": row.get("attempts"),
            "failure_kind": row.get("failure_kind"),
            "worker_pid": live.handle.pid if live else None,
            "worker_rss_mb": rss,
            "resources": measure().as_dict(),
            **extra,
        }
        log.write(json.dumps(record, default=str) + "\n")
        log.flush()

    emit("policy", policy=policy.as_dict())
    recovered = supervisor.reconcile_on_startup()
    emit("reconciled", rows=len(recovered))
    row = supervisor.row(profile.key)
    if row is None or row["state"] not in (*index_runs.ACTIVE_STATES,):
        supervisor.start(profile)
    emit("started")
    baseline = int((supervisor.row(profile.key) or {}).get("indexed_chunks") or 0)
    killed = False
    last_sample = 0.0
    try:
        while True:
            supervisor.tick()
            row = supervisor.row(profile.key) or {}
            live = supervisor._live.get(profile.key)
            if (
                args.kill_after_chunks
                and not killed
                and live
                and int(row.get("indexed_chunks") or 0) >= baseline + args.kill_after_chunks
            ):
                emit("injected_external_kill", pid=live.handle.pid)
                os.kill(live.handle.pid, signal.SIGTERM if sys.platform == "win32" else signal.SIGKILL)
                killed = True
            if time.monotonic() - last_sample >= args.sample_seconds:
                emit("sample")
                last_sample = time.monotonic()
            if row.get("state") in TERMINAL and profile.key not in supervisor._live:
                break
            time.sleep(supervisor.config.poll_seconds)
    except KeyboardInterrupt:
        supervisor.shutdown()
        emit("interrupted_by_operator")
        return 130
    with engine.connect() as conn:
        coverage = profile_coverage(conn, profile)
    emit("finished", coverage=coverage)
    engine.dispose()
    return 0 if row.get("state") == "completed" and coverage["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
