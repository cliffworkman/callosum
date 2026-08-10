"""The terminal client (tui/): registry invariants, client mapping, one-shot dispatch, agent gate.

Hermetic like test_mcp_server.py: an httpx.MockTransport stands in for the running app, so the
real request-build + response-parse + gating code runs against canned responses. The registry
tests are the structural guarantee that the TUI can never widen the agent surface beyond the
gated /agent/* writes, and that destructive actions stay human-only + confirmed.
"""

from __future__ import annotations

import json

import httpx
import pytest

from tui import registry
from tui.__main__ import build_parser, main, run_action, self_test
from tui.client import CallosumUnavailable, TuiClient
from tui.render import render


def _client(handler):
    return TuiClient(
        "http://test",
        http=httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)),
    )


# ---- registry invariants ------------------------------------------------------------


def test_registry_is_valid():
    assert registry.validate() == []


def test_agent_mode_writes_only_via_agent_endpoints():
    for a in registry.ACTIONS:
        if a.tier != registry.READ and a.agent_allowed():
            assert a.effective_path(agent=True).startswith("/agent/"), (a.group, a.name)


def test_no_destructive_action_in_agent_mode():
    for a in registry.ACTIONS:
        if a.tier == registry.DESTRUCTIVE:
            assert not a.agent_allowed(), (a.group, a.name)


def test_every_group_has_actions_and_parser_coverage():
    parser = build_parser()
    for g in registry.groups():
        acts = registry.actions_for(g.key)
        assert acts, g.key
        for a in acts:
            # every registry action parses as a subcommand (path params filled with dummies)
            argv = [g.key, a.name] + ["1" if p not in registry._STR_PATH_PARAMS else "x" for p in a.path_params]
            ns = parser.parse_args(argv)
            assert ns.group == g.key and ns.action == a.name


def test_the_four_audited_agent_writes_are_reachable_in_agent_mode():
    reachable = {
        a.effective_path(agent=True) for a in registry.ACTIONS if a.tier == registry.WRITE and a.agent_allowed()
    }
    assert "/agent/papers/{paper_id}/tags" in reachable
    assert "/agent/axes/{axis_id}/papers" in reachable
    assert "/agent/references" in reachable
    assert "/agent/papers/{paper_id}/notes" in reachable


# ---- client -------------------------------------------------------------------------


def test_client_down_message_names_the_fix():
    client = TuiClient("http://127.0.0.1:1")
    with pytest.raises(CallosumUnavailable, match="uvicorn"):
        client.request("GET", "/health")


def test_client_surfaces_api_detail():
    client = _client(lambda r: httpx.Response(422, json={"detail": "bad input"}))
    with pytest.raises(CallosumUnavailable, match="bad input"):
        client.request("GET", "/papers")


def test_poll_job_runs_to_done():
    states = iter(["pending", "running", "done"])

    def handler(request):
        if request.url.path == "/gaps/refresh":
            return httpx.Response(202, json={"job_id": "j1"})
        return httpx.Response(200, json={"status": next(states), "result": 7})

    client = _client(handler)
    action = registry.find("gaps", "refresh")
    out = run_action(client, action, agent=False, path_args={}, query={}, body=None)
    assert out["status"] == "done"


def test_agent_body_is_stripped_to_the_gated_fields():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"write_id": 1})

    client = _client(handler)
    action = registry.find("gaps", "add")  # human: /gaps/add {doi,...}; agent: /agent/references
    run_action(
        client, action, agent=True, path_args={}, query={}, body={"doi": "10.1/x", "identifier": "10.1/x", "title": "T"}
    )
    assert seen["path"] == "/agent/references"
    assert seen["body"] == {"identifier": "10.1/x"}


# ---- one-shot dispatch ---------------------------------------------------------------


def test_agent_mode_refuses_human_writes():
    client = _client(lambda r: httpx.Response(200, json={}))
    for grp, name, path_args in (
        ("papers", "edit", {"paper_id": 1}),
        ("wanted", "add", {}),
        ("papers", "delete", {"paper_id": 1}),
    ):
        with pytest.raises(SystemExit, match="agent mode"):
            run_action(client, registry.find(grp, name), agent=True, path_args=path_args, query={}, body=None)


def test_destructive_requires_yes_then_runs():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json={"removed": 3})

    client = _client(handler)
    action = registry.find("papers", "empty-trash")
    with pytest.raises(SystemExit, match="--yes"):
        run_action(client, action, agent=False, path_args={}, query={}, body=None, yes=False)
    assert calls == []
    out = run_action(client, action, agent=False, path_args={}, query={}, body=None, yes=True)
    assert out == {"removed": 3} and calls == [("POST", "/papers/trash/empty")]


def test_main_one_shot_json(capsys):
    # main() builds its own live client, so point it at a closed port for the error path only;
    # the happy path goes through run_action (covered above) — here we check exit codes + stderr.
    rc = main(["wanted", "list", "--base-url", "http://127.0.0.1:1"])
    assert rc == 2
    assert "isn't reachable" in capsys.readouterr().err


def test_self_test_passes():
    assert self_test() == 0


# ---- render ---------------------------------------------------------------------------


def test_render_table_and_json_and_envelope():
    rows = [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
    out = render(rows)
    assert "id" in out and "A" in out and "B" in out
    assert json.loads(render(rows, "json")) == rows
    enveloped = render({"total": 2, "items": rows})
    assert "total" in enveloped and "B" in enveloped
    assert "(no results)" in render([])
    assert "binary" in render(b"\x00" * 10)
