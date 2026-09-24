"""Exact code identity for a scored run: the commit SHA, and a refusal to score from a dirty tree.

A comparison between arms is only meaningful if every arm ran the same, recorded code. The whole worktree counts —
a modified or untracked file anywhere could change what the run imports — so a scored run refuses to start unless
the tree is clean, and the manifest records the exact SHA it ran at.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class DirtyTreeError(RuntimeError):
    """The worktree has uncommitted or untracked changes, so the run's code identity would be unrecorded."""


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kwargs)  # noqa: S603 - fixed argv


def git_state(root: Path | str, runner=_run) -> dict:
    """``{"sha", "branch", "dirty_paths"}`` for the worktree at ``root``."""
    cwd = str(root)
    sha = runner(["git", "rev-parse", "HEAD"], cwd=cwd).stdout.strip()
    branch = runner(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd).stdout.strip()
    status = runner(["git", "status", "--porcelain", "--untracked-files=all"], cwd=cwd).stdout
    dirty = [line[3:] for line in status.splitlines() if line.strip()]
    return {"sha": sha, "branch": branch, "dirty_paths": dirty}


def assert_clean(state: dict) -> None:
    if state["dirty_paths"]:
        shown = ", ".join(state["dirty_paths"][:5])
        more = len(state["dirty_paths"]) - 5
        raise DirtyTreeError(
            f"refusing a scored run from a dirty tree ({shown}{f', +{more} more' if more > 0 else ''})"
        )
