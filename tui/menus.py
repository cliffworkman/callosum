"""Interactive numbered-menu REPL over the action registry.

Plain stdin/stdout — no curses — so it works over ssh, in pipes, and under an agent. Navigation:
bare number selects, `0` goes back, `q` quits, blank re-prints the menu. Destructive actions ask
y/N; agent mode hides everything the gate disallows.
"""

from __future__ import annotations

import json
import sys

from . import registry
from .client import AgentWritesDisabled, CallosumUnavailable, TuiClient
from .render import render


def _say(text: str = "") -> None:
    print(text)


def _ask(prompt: str) -> str | None:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return None


def _pick(title: str, items: list[tuple[str, str]], breadcrumb: str) -> int | None:
    """Show a numbered menu; return the 0-based index, or None for back/quit."""
    _say()
    _say(f"[{breadcrumb}]")
    _say(title)
    for i, (label, hint) in enumerate(items, start=1):
        _say(f"{i:3}  {label}" + (f"  — {hint}" if hint else ""))
    _say("  0  back        q  quit")
    while True:
        raw = _ask("> ")
        if raw is None or raw.lower() == "q":
            return None
        if raw == "0":
            return -1
        if raw == "":
            return _pick(title, items, breadcrumb)
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return int(raw) - 1
        _say(f"pick 1–{len(items)}, 0 for back, q to quit")


def _prompt_params(action: registry.Action) -> tuple[dict, dict, dict] | None:
    path_args: dict = {}
    query: dict = {}
    body: dict = {}
    for name in action.path_params:
        raw = _ask(f"{name}: ")
        if raw is None or raw == "":
            _say("(cancelled)")
            return None
        path_args[name] = raw if name in registry._STR_PATH_PARAMS else int(raw)
    for p in action.params:
        raw = _ask(f"{p.name}{' (required)' if p.required else ''}{f' — {p.help}' if p.help else ''}: ")
        if raw is None:
            return None
        if raw == "":
            if p.required:
                _say("(required — cancelled)")
                return None
            continue
        try:
            value = raw
            if p.type == "int":
                value = int(raw)
            elif p.type == "float":
                value = float(raw)
            elif p.type == "bool":
                value = raw.lower() in ("y", "yes", "true", "1")
            elif p.type == "json":
                value = json.loads(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            _say(f"bad value for {p.name}: {exc} — cancelled")
            return None
        (query if p.kind == "query" else body)[p.name] = value
    if action.method in ("POST", "PUT", "PATCH") and not body and not action.params:
        raw = _ask("body JSON (blank for none): ")
        if raw:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError as exc:
                _say(f"not valid JSON: {exc} — cancelled")
                return None
    return path_args, query, body


def repl(client: TuiClient, agent: bool = False) -> int:
    from .__main__ import run_action  # late import to avoid a cycle

    mode = " (agent mode: reads + audited /agent/* writes only)" if agent else ""
    _say(f"callosum TUI — {client.base_url}{mode}")
    try:
        health = client.payload(client.request("GET", "/health"))
        _say(f"connected: {health.get('status', 'ok')}")
    except CallosumUnavailable as exc:
        _say(f"warning: {exc}")

    groups = list(registry.groups())
    while True:
        gi = _pick("Main menu", [(g.title, g.blurb) for g in groups], "callosum")
        if gi is None:
            return 0
        if gi == -1:
            continue
        group = groups[gi]
        while True:
            acts = registry.actions_for(group.key, agent=agent)
            items = [(a.title, ("destructive — confirms" if a.tier == registry.DESTRUCTIVE else a.help)) for a in acts]
            ai = _pick(group.title, items, f"callosum / {group.title}")
            if ai is None:
                return 0
            if ai == -1:
                break
            action = acts[ai]
            got = _prompt_params(action)
            if got is None:
                continue
            path_args, query, body = got
            if action.tier == registry.DESTRUCTIVE:
                sure = _ask(f"really run '{action.title}'? [y/N] ")
                if not sure or sure.lower() not in ("y", "yes"):
                    _say("(skipped)")
                    continue
            try:
                data = run_action(
                    client,
                    action,
                    agent=agent,
                    path_args=path_args,
                    query=query,
                    body=body or None,
                    yes=True,
                    wait=True,
                    quiet=False,
                )
                _say(render(data))
            except (CallosumUnavailable, AgentWritesDisabled) as exc:
                _say(f"error: {exc}")
            except SystemExit as exc:
                _say(f"error: {exc}")
            except Exception as exc:  # noqa: BLE001 — REPL must survive anything
                _say(f"unexpected error: {exc}")


if __name__ == "__main__":
    sys.exit(repl(TuiClient()))
