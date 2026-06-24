#!/usr/bin/env python3
"""QA supervisor — dispatch callosum QA routes to Codex `exec`, with no human nudging.

The point: spend Codex credits (the executor) instead of dev attention (the orchestrator). The
supervisor walks the QA routes in complexity order (the route number NN), hands each to a headless
`codex exec` run whose contract is the route file itself, waits for that route's deposit to land in
`.claude/qa-inbox/<run-id>/`, records pass/fail, retries failures, and at the end writes a
`run-summary.md` that leads with Critical/High findings plus the coverage-gate result.

Codex CLI semantics relied on (current as of mid-2026 — verify with `codex exec --help`):
  * `codex exec "<prompt>"` runs non-interactively, streams progress to stderr, prints the final
    agent message to stdout, and EXITS NON-ZERO on failure.
  * `--sandbox danger-full-access` is needed because each route spins a local uvicorn server + a
    Playwright browser and talks to loopback; in exec mode approvals are auto-`never`. (Use
    `workspace-write` first; escalate to full access only if loopback/browser spawning is blocked.
    This runs on the user's own machine against a throwaway DB, so full access is acceptable here.)
  * `-o/--output-last-message <file>` captures the final message; we also keep stdout/stderr logs.
  * Auth: `codex exec` reuses your saved CLI login by default (so it draws on your ChatGPT/Codex
    credits). No API key is required for local runs.

Examples:
    python tools/qa/supervisor.py                       # all routes, ascending
    python tools/qa/supervisor.py --tier 0              # only Tier-0 (route_0*) — the cheap gate
    python tools/qa/supervisor.py --routes 00,30        # just those route numbers
    python tools/qa/supervisor.py --max 4 --dry-run     # show the plan + the exact codex commands
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Windows consoles default to cp1252, which can't encode the unicode glyphs this script prints
# (→ ✓ —) — force UTF-8 so progress output works in any shell or redirected/background pipe.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

THIS = Path(__file__).resolve()
REPO_ROOT = THIS.parents[2]
QA_ROUTES_DIR = REPO_ROOT / ".claude" / "qa-routes"
QA_INBOX = REPO_ROOT / ".claude" / "qa-inbox"
QA_TOOLS = REPO_ROOT / "tools" / "qa"
PROMPT_TEMPLATE = QA_TOOLS / "route_runner_prompt.md"
SURFACE_MAP_TOOL = QA_TOOLS / "build_surface_map.py"

# defaults (all overridable by flag/env)
DEFAULT_SANDBOX = os.environ.get("CODEX_QA_SANDBOX", "danger-full-access")
DEFAULT_MODEL = os.environ.get("CODEX_QA_MODEL")  # None → codex default
DEFAULT_TIMEOUT_S = int(os.environ.get("CODEX_QA_TIMEOUT_S", "1800"))  # 30 min/route
DEFAULT_RETRIES = int(os.environ.get("CODEX_QA_RETRIES", "1"))

SEVERITY_RE = re.compile(r"\b(Critical|High)\b", re.IGNORECASE)


@dataclass
class Route:
    stem: str  # e.g. route_00_smoke_readonly
    number: str  # e.g. "00"
    path: Path
    status: str = "pending"  # pending | done | failed
    attempts: int = 0
    deposit: Path | None = None
    notes: str = ""


@dataclass
class RunState:
    run_id: str
    routes: list[Route] = field(default_factory=list)


# --------------------------------------------------------------------------------------------
def discover_routes(tier: int | None, only: set[str] | None) -> list[Route]:
    routes: list[Route] = []
    for p in sorted(QA_ROUTES_DIR.glob("route_*.md")):
        m = re.match(r"route_(\d+)_", p.name)
        if not m:
            continue
        num = m.group(1)
        if tier is not None:
            # tier 0 = 00-09, tier 1 = 10-49, tier 2 = 50+
            n = int(num)
            band = 0 if n < 10 else (1 if n < 50 else 2)
            if band != tier:
                continue
        if only is not None and num not in only:
            continue
        routes.append(Route(stem=p.stem, number=num, path=p))
    return routes


def build_prompt(route: Route, run_id: str) -> str:
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    rel = route.path.relative_to(REPO_ROOT).as_posix()
    return template.replace("{ROUTE_FILE}", rel).replace("{RUN_ID}", run_id).replace("{ROUTE_STEM}", route.stem)


def _codex_bin() -> str:
    """Resolve the codex executable to a full path. On Windows ``codex`` is an npm shim (``codex.CMD``) that
    bare ``subprocess`` (no shell) can't find on PATH; ``shutil.which`` resolves it (and the POSIX path too)."""
    return shutil.which("codex") or "codex"


def codex_command(sandbox: str, model: str | None, last_msg_file: Path) -> list[str]:
    # The prompt is piped via stdin (the trailing ``-``), NOT passed as an argument — a large multi-line prompt
    # as a Windows .CMD argument is mangled by cmd.exe arg parsing (% & < > …). stdin sidesteps all of that.
    cmd = [_codex_bin(), "exec"]
    if model:
        cmd += ["--model", model]
    cmd += ["--sandbox", sandbox, "-o", str(last_msg_file), "-"]
    return cmd


def dispatch(route: Route, state: RunState, *, sandbox: str, model: str | None, timeout_s: int, log_dir: Path) -> bool:
    route.attempts += 1
    prompt = build_prompt(route, state.run_id)
    deposit = QA_INBOX / state.run_id / f"{route.stem}.md"
    route.deposit = deposit
    last_msg = log_dir / f"{route.stem}.final.txt"
    cmd = codex_command(sandbox, model, last_msg)

    print(f"\n[supervisor] → {route.stem} (attempt {route.attempts})")
    print(f"[supervisor]   deposit expected at: {deposit.relative_to(REPO_ROOT)}")

    log = log_dir / f"{route.stem}.attempt{route.attempts}.log"
    try:
        with log.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                input=prompt,  # the route prompt is piped to codex via stdin (see codex_command)
                text=True,
                encoding="utf-8",  # don't let Windows default the stdin pipe to cp1252
                stdout=fh,
                stderr=subprocess.STDOUT,
                timeout=timeout_s,
                check=False,
            )
    except subprocess.TimeoutExpired:
        route.status = "failed"
        route.notes = f"timed out after {timeout_s}s"
        print(f"[supervisor]   TIMEOUT after {timeout_s}s")
        return False

    # success = codex exited 0 AND the route actually deposited its report
    deposited = deposit.exists()
    if proc.returncode == 0 and deposited:
        route.status = "done"
        print("[supervisor]   done (exit 0, deposit present)")
        return True

    route.status = "failed"
    route.notes = f"exit={proc.returncode}, deposit={'present' if deposited else 'MISSING'} (see {log.name})"
    print(f"[supervisor]   FAILED — {route.notes}")
    return False


def collect_findings(state: RunState) -> list[str]:
    lines: list[str] = []
    for r in state.routes:
        if r.deposit and r.deposit.exists():
            for ln in r.deposit.read_text(encoding="utf-8", errors="replace").splitlines():
                if SEVERITY_RE.search(ln) and ("severity" in ln.lower() or "**" in ln):
                    lines.append(f"[{r.stem}] {ln.strip()}")
    return lines


def coverage_summary() -> str:
    try:
        out = subprocess.run(
            [sys.executable, str(SURFACE_MAP_TOOL), "check"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        head = "\n".join(out.stdout.splitlines()[:2])
        return head + ("\n(uncovered surfaces listed in `build_surface_map.py check` output)" if out.returncode else "")
    except Exception as exc:
        return f"(coverage check failed to run: {exc})"


def write_summary(state: RunState, run_dir: Path) -> Path:
    done = [r for r in state.routes if r.status == "done"]
    failed = [r for r in state.routes if r.status != "done"]
    findings = collect_findings(state)
    summary = run_dir / "run-summary.md"
    lines = [
        f"# QA run {state.run_id}",
        "",
        f"- routes attempted: {len(state.routes)}",
        f"- passed (deposited): {len(done)}",
        f"- failed/incomplete: {len(failed)}",
        "",
        "## Coverage gate",
        "",
        "```",
        coverage_summary(),
        "```",
        "",
        "## Critical / High findings (read these first)",
        "",
    ]
    lines += [f"- {f}" for f in findings] or ["- (none flagged Critical/High in the deposits)"]
    lines += ["", "## Routes", ""]
    for r in state.routes:
        mark = "✓" if r.status == "done" else "✗"
        lines.append(f"- {mark} `{r.stem}` — {r.status}" + (f" — {r.notes}" if r.notes else ""))
    lines += [
        "",
        "*Triage per `.claude/QA-POLICY.md`: fix Critical/High in-session, file the rest to "
        "`INCREMENT-BACKLOG.md`, open audit stubs for security-class findings, then move this run "
        "to `.claude/qa-inbox/_processed/`.*",
        "",
    ]
    summary.write_text("\n".join(lines), encoding="utf-8")
    return summary


# --------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="callosum QA supervisor (Codex exec dispatcher)")
    parser.add_argument("--tier", type=int, choices=[0, 1, 2], help="run only this tier (0=00-09, 1=10-49, 2=50+)")
    parser.add_argument("--routes", help="comma-separated route numbers, e.g. 00,30")
    parser.add_argument("--max", type=int, help="cap number of routes this run (budget)")
    parser.add_argument("--sandbox", default=DEFAULT_SANDBOX)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES)
    parser.add_argument("--dry-run", action="store_true", help="print the plan + exact codex commands, run nothing")
    args = parser.parse_args(argv)

    if not QA_ROUTES_DIR.exists():
        print(f"[supervisor] no routes at {QA_ROUTES_DIR}", file=sys.stderr)
        return 2

    only = set(s.strip() for s in args.routes.split(",")) if args.routes else None
    routes = discover_routes(args.tier, only)
    if args.max:
        routes = routes[: args.max]
    if not routes:
        print("[supervisor] no routes matched the filter.", file=sys.stderr)
        return 2

    run_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    state = RunState(run_id=run_id, routes=routes)
    run_dir = QA_INBOX / run_id
    log_dir = run_dir / "_logs"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "screenshots").mkdir(exist_ok=True)
    log_dir.mkdir(exist_ok=True)

    print(
        f"[supervisor] run {run_id} — {len(routes)} route(s), sandbox={args.sandbox}, model={args.model or '(codex default)'}"
    )
    for r in routes:
        print(f"  - {r.stem}")

    if args.dry_run:
        print("\n[supervisor] DRY RUN — exact commands (route prompt piped via stdin):")
        for r in routes:
            cmd = codex_command(args.sandbox, args.model, log_dir / f"{r.stem}.final.txt")
            print("  (cwd=%s) %s   < <route prompt on stdin>" % (REPO_ROOT, " ".join(cmd)))
        print(
            "\n[supervisor] regenerate the surface map first on a real run: python tools/qa/build_surface_map.py extract"
        )
        return 0

    # always refresh the surface map so coverage reflects the current tree
    subprocess.run([sys.executable, str(SURFACE_MAP_TOOL), "extract"], cwd=str(REPO_ROOT), check=False)

    for r in routes:
        ok = False
        while not ok and r.attempts <= args.retries:
            ok = dispatch(r, state, sandbox=args.sandbox, model=args.model, timeout_s=args.timeout, log_dir=log_dir)
        # Tier-0 is the gate: if route_00 fails, stop — deeper routes aren't worth the spend.
        if r.number == "00" and r.status != "done":
            print("[supervisor] Tier-0 smoke failed — halting before deeper routes (fix the smoke first).")
            break

    summary = write_summary(state, run_dir)
    print(f"\n[supervisor] run complete. Summary: {summary.relative_to(REPO_ROOT)}")
    failed = [r for r in state.routes if r.status != "done"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
