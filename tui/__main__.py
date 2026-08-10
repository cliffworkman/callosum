"""callosum TUI entrypoint.

No arguments → the interactive numbered-menu REPL.
`python -m tui <group> <action> [flags]` → one-shot mode (the agent path): prints the result and
exits, `--format json` for machine consumption.

Global flags:
  --base-url URL     callosum API (default $CALLOSUM_BASE_URL or http://127.0.0.1:8080)
  --token TOKEN      bearer token when remote access is enabled ($CALLOSUM_TOKEN)
  --agent            agent mode: reads + gated /agent/* writes only ($CALLOSUM_TUI_AGENT=1)
  --format table|json
  --yes              skip confirmation on destructive actions (one-shot only)
  --no-wait          submit job endpoints without polling to completion
  --extra-query k=v  extra query params (repeatable) — escape hatch for anything not modeled
  --body JSON        raw request body — overrides/merges with named body flags
  --out FILE         write the (possibly binary) response to FILE
  --self-test        offline self-check (no server needed), exit 0/1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import registry
from .client import AgentWritesDisabled, CallosumUnavailable, TuiClient
from .render import render


def _coerce(value: str, type_: str) -> Any:
    if type_ == "int":
        return int(value)
    if type_ == "float":
        return float(value)
    if type_ == "bool":
        v = value.strip().lower()
        if v in ("true", "1", "yes", "y"):
            return True
        if v in ("false", "0", "no", "n"):
            return False
        raise ValueError(f"expected true/false, got {value!r}")
    if type_ == "json":
        return json.loads(value)
    return value


def _global_flags(p: argparse.ArgumentParser) -> None:
    """Global flags, addable to the top parser AND every action subparser so they work in either
    position. Defaults are SUPPRESS so a subparser never clobbers a value given before the
    subcommand; the real defaults are set once via set_defaults on the top parser. When an
    action's own parameter claims the same flag (e.g. `papers export --format bibtex`), the
    action's flag wins on that subparser and the global is passed before the subcommand."""
    S = argparse.SUPPRESS
    flags: list[tuple[list, dict]] = [
        (["--base-url"], {"default": S}),
        (["--token"], {"default": S}),
        (["--agent"], {"action": "store_true", "default": S}),
        (["--format"], {"choices": ("table", "json"), "default": S}),
        (["--yes"], {"action": "store_true", "default": S, "help": "confirm destructive actions"}),
        (["--no-wait"], {"action": "store_true", "default": S, "help": "don't poll job endpoints"}),
        (["--timeout"], {"type": float, "default": S, "help": "job poll timeout (s)"}),
        (["--quiet"], {"action": "store_true", "default": S}),
        (["--out"], {"default": S, "help": "write response body to FILE"}),
        (["--self-test"], {"action": "store_true", "default": S}),
    ]
    for names, kwargs in flags:
        try:
            p.add_argument(*names, **kwargs)
        except argparse.ArgumentError:
            pass  # the action's own parameter owns this flag on this subparser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tui",
        description="Terminal client for callosum — every feature, numbered menus, agent-drivable.",
    )
    _global_flags(parser)
    parser.set_defaults(
        base_url=None,
        token=None,
        agent=os.environ.get("CALLOSUM_TUI_AGENT") == "1",
        format="table",
        yes=False,
        no_wait=False,
        timeout=600.0,
        quiet=False,
        out=None,
        self_test=False,
    )

    subs = parser.add_subparsers(dest="group")
    for g in registry.groups():
        gp = subs.add_parser(g.key, help=g.title)
        gsubs = gp.add_subparsers(dest="action")
        for a in registry.actions_for(g.key):
            ap = gsubs.add_parser(a.name, help=a.title + (f" — {a.help}" if a.help else ""))
            for name in a.path_params:
                ap.add_argument(name, type=(str if name in registry._STR_PATH_PARAMS else int))
            for p in a.params:
                ap.add_argument(
                    f"--{p.name.replace('_', '-')}", dest=f"p_{p.name}", required=False, help=p.help or p.kind
                )
            ap.add_argument("--extra-query", action="append", default=[], metavar="K=V")
            ap.add_argument("--body", default=None, metavar="JSON")
            _global_flags(ap)
    return parser


def _collect(action: registry.Action, ns: argparse.Namespace) -> tuple[dict, dict, Any]:
    path_args = {name: getattr(ns, name) for name in action.path_params}
    query: dict[str, Any] = {}
    body: dict[str, Any] = {}
    missing = []
    for p in action.params:
        raw = getattr(ns, f"p_{p.name}", None)
        if raw is None:
            if p.required and not ns.body:
                missing.append(p.name)
            continue
        target = query if p.kind == "query" else body
        target[p.name] = _coerce(raw, p.type)
    if missing:
        raise SystemExit(
            f"missing required: {', '.join('--' + m.replace('_', '-') for m in missing)} (or pass --body JSON)"
        )
    for kv in ns.extra_query:
        if "=" not in kv:
            raise SystemExit(f"--extra-query expects k=v, got {kv!r}")
        k, v = kv.split("=", 1)
        query[k] = v
    if ns.body:
        try:
            extra = json.loads(ns.body)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--body is not valid JSON: {exc}") from exc
        if not isinstance(extra, dict):
            return path_args, query, extra  # raw non-object body, sent as-is
        body = {**body, **extra}
    return path_args, query, (body or None)


def run_action(
    client: TuiClient,
    action: registry.Action,
    *,
    agent: bool,
    path_args: dict,
    query: dict,
    body: Any,
    yes: bool = False,
    wait: bool = True,
    timeout: float = 600.0,
    quiet: bool = True,
) -> Any:
    if agent and not action.agent_allowed():
        raise SystemExit(
            f"'{action.group} {action.name}' is not available in agent mode "
            f"({action.tier}); run without --agent, or do it in the callosum web UI."
        )
    if action.tier == registry.DESTRUCTIVE and not yes:
        raise SystemExit(f"'{action.group} {action.name}' is destructive — re-run with --yes.")
    path = action.effective_path(agent).format(**path_args)
    if agent and action.agent_path and body is not None and isinstance(body, dict):
        # /agent/* endpoints accept only their own minimal bodies; drop human-endpoint fields.
        allowed = {"tag", "paper_id", "identifier", "text"}
        body = {k: v for k, v in body.items() if k in allowed} or None
    resp = client.request(action.method, path, query=query or None, body=body)
    data = client.payload(resp)
    if action.job and wait:
        jid = client.job_id_of(data)
        if jid:
            tick = (
                None
                if quiet
                else (
                    lambda st: print(
                        f"  … {st.get('status', '?')} {st.get('progress_label', '')}".rstrip(), file=sys.stderr
                    )
                )
            )
            data = client.poll_job(action.job, jid, timeout=timeout, on_tick=tick)
    return data


def self_test() -> int:
    problems = registry.validate()
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/agent/status":
            return httpx.Response(200, json={"writes_enabled": False})
        if request.url.path == "/papers":
            return httpx.Response(200, json=[{"id": 1, "title": "T", "authors": ["A"]}])
        return httpx.Response(404, json={"detail": "nope"})

    client = TuiClient("http://test", http=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test"))
    try:
        assert client.payload(client.request("GET", "/health"))["status"] == "ok"
        assert client.agent_writes_enabled() is False
        health = registry.find("status", "health")
        assert health is not None
        out = run_action(client, health, agent=True, path_args={}, query={}, body=None)
        assert out["status"] == "ok"
        papers = registry.find("papers", "list")
        assert render(run_action(client, papers, agent=True, path_args={}, query={}, body=None))
        # agent-mode refusals
        for grp, name in (("papers", "delete"), ("papers", "edit"), ("library", "merge")):
            act = registry.find(grp, name)
            try:
                run_action(client, act, agent=True, path_args={"paper_id": 1}, query={}, body=None)
                problems.append(f"{grp} {name}: agent mode did not refuse")
            except SystemExit:
                pass
        # destructive confirmation
        try:
            run_action(
                client,
                registry.find("papers", "empty-trash"),
                agent=False,
                path_args={},
                query={},
                body=None,
                yes=False,
            )
            problems.append("empty-trash: ran without --yes")
        except SystemExit:
            pass
    except Exception as exc:  # noqa: BLE001
        problems.append(f"self-test error: {exc}")
    for p in problems:
        print(f"FAIL {p}", file=sys.stderr)
    print("self-test: " + ("OK" if not problems else f"{len(problems)} problem(s)"))
    return 0 if not problems else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.self_test:
        return self_test()
    if not ns.group:
        from .menus import repl

        return repl(TuiClient(ns.base_url, token=ns.token), agent=ns.agent)
    if not getattr(ns, "action", None):
        parser.parse_args([ns.group, "--help"])
        return 2
    action = registry.find(ns.group, ns.action)
    client = TuiClient(ns.base_url, token=ns.token)
    try:
        path_args, query, body = _collect(action, ns)
        data = run_action(
            client,
            action,
            agent=ns.agent,
            path_args=path_args,
            query=query,
            body=body,
            yes=ns.yes,
            wait=not ns.no_wait,
            timeout=ns.timeout,
            quiet=ns.quiet,
        )
    except AgentWritesDisabled as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except CallosumUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if ns.out and isinstance(data, (bytes, bytearray)):
        with open(ns.out, "wb") as fh:
            fh.write(data)
        if not ns.quiet:
            print(f"wrote {len(data)} bytes to {ns.out}")
        return 0
    if ns.out:
        with open(ns.out, "w") as fh:
            fh.write(render(data, "json" if ns.out.endswith(".json") else ns.format))
        return 0
    print(render(data, ns.format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
