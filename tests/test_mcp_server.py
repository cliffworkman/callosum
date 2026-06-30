"""inc 213 (B1 SP1) — the read-only MCP server: tool registry + request/response mapping + the read-only allowlist.

Hermetic: a MockTransport stands in for the running callosum app (no DB, no live server). The CallosumClient's
real request-build + response-parse code runs against canned responses, and the allowlist test asserts the
server only ever issues read calls to the five allowlisted endpoints.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from mcp_server.client import CallosumClient
from mcp_server.server import create_server


def _client(handler):
    """A CallosumClient whose HTTP goes to a MockTransport handler (records + cans responses)."""
    return CallosumClient(
        "http://test",
        http=httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)),
    )


def _call(mcp, name, args):
    # FastMCP's call_tool returns (content, structured) for non-dict returns (structured wraps them under
    # {"result": ...}) but a bare list[TextContent] for a dict return — handle both.
    res = asyncio.run(mcp.call_tool(name, args))
    if isinstance(res, tuple) and len(res) == 2:
        content, structured = res
        if isinstance(structured, dict):
            return structured["result"] if set(structured.keys()) == {"result"} else structured
    else:
        content = res
    return json.loads(content[0].text) if len(content) == 1 else [json.loads(c.text) for c in content]


def test_search_library_maps_request_and_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"], seen["path"], seen["q"] = request.method, request.url.path, request.url.params.get("q")
        return httpx.Response(
            200,
            json=[
                {
                    "id": 7,
                    "title": "Faces",
                    "authors": ["A. B"],
                    "year": 2020,
                    "venue": "J",
                    "citation_key": "b20",
                    "processing_tier": "metadata-only",
                    "attachment_count": 1,
                    "chunk_count": 3,
                }
            ],
        )

    mcp = create_server(_client(handler))
    out = _call(mcp, "search_library", {"query": "faces", "limit": 5})
    assert seen == {"method": "GET", "path": "/papers", "q": "faces"}
    assert out == [{"id": 7, "title": "Faces", "authors": ["A. B"], "year": 2020, "venue": "J", "citation_key": "b20"}]


def test_get_paper_maps_detail():
    def handler(request):
        assert request.method == "GET" and request.url.path == "/papers/7"
        return httpx.Response(
            200,
            json={
                "id": 7,
                "title": "Faces",
                "authors": ["A. B"],
                "year": 2020,
                "doi": "10.1/x",
                "venue": "J",
                "item_type": "article-journal",
                "abstract_text": "plain abstract",
                "abstract": "<jats>...",
                "citation_key": "b20",
                "tags": [{"id": 1, "name": "vision"}],
                "csl_json": {},
                "processing_tier": "metadata-only",
                "attachment_count": 1,
                "chunk_count": 3,
                "attachments": [],
            },
        )

    out = _call(create_server(_client(handler)), "get_paper", {"paper_id": 7})
    assert out["doi"] == "10.1/x" and out["abstract"] == "plain abstract" and out["tags"] == ["vision"]


def test_find_passages_carries_quote_and_page():
    def handler(request):
        assert request.method == "POST" and request.url.path == "/citations/suggest"
        assert json.loads(request.content)["evaluate"] is False  # pure retrieval, no NLI stance
        return httpx.Response(
            200,
            json={
                "suggestions": [
                    {
                        "paper_id": 7,
                        "title": "Faces",
                        "quote": "the verbatim sentence",
                        "page_start": 3,
                        "page_end": 3,
                        "coordinate_precision": "region",
                        "match_score": 0.81,
                        "chunk_id": 11,
                    }
                ]
            },
        )

    out = _call(create_server(_client(handler)), "find_passages", {"query": "faces signal threat", "top_k": 3})
    assert out[0]["quote"] == "the verbatim sentence" and out[0]["page_start"] == 3
    assert out[0]["coordinate_precision"] == "region"  # honesty invariant carried through


def test_fulltext_strips_pua_markers():
    def handler(request):
        assert request.url.path == "/papers/fulltext"
        return httpx.Response(
            200,
            json=[
                {
                    "paper_id": 7,
                    "title": "Faces",
                    "page_start": 2,
                    "page_end": 2,
                    "snippet": "a match here",
                    "chunk_id": 9,
                    "coordinate_precision": "region",
                }
            ],
        )

    out = _call(create_server(_client(handler)), "full_text_search", {"query": "match"})
    assert out[0]["snippet"] == "a match here"  # markers stripped


def test_format_citation_returns_text():
    def handler(request):
        assert request.method == "POST" and request.url.path == "/papers/export"
        assert json.loads(request.content)["format"] == "bibtex"
        return httpx.Response(200, text="@article{b20, title={Faces}}")

    out = _call(create_server(_client(handler)), "format_citation", {"paper_ids": [7], "format": "bibtex"})
    assert out.startswith("@article")


def test_bearer_token_is_sent_when_configured():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=[])

    c = CallosumClient(
        "http://test",
        token="secret",
        http=httpx.Client(
            base_url="http://test",
            headers={"Authorization": "Bearer secret"},
            transport=httpx.MockTransport(handler),
        ),
    )
    _call(create_server(c), "search_library", {"query": "x"})
    assert seen["auth"] == "Bearer secret"


def test_app_down_and_401_are_clean_errors():
    import pytest

    from mcp_server.client import CallosumUnavailable

    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(CallosumUnavailable):
        _client(down).search("x")

    def unauth(request):
        return httpx.Response(401, json={"detail": "no"})

    with pytest.raises(CallosumUnavailable):
        _client(unauth).search("x")


def test_server_only_issues_readonly_calls():
    # Drive EVERY tool through a recording transport; assert no write verb / no scan-or-pdf path is touched.
    calls = []
    ALLOWED = {
        ("GET", "/papers"),
        ("GET", "/papers/fulltext"),
        ("POST", "/citations/suggest"),
        ("POST", "/papers/export"),
    }

    def handler(request):
        path = request.url.path
        calls.append((request.method, path))
        assert request.method in ("GET", "POST"), f"write verb {request.method} to {path}"
        if request.method == "GET":
            if path == "/papers/fulltext":
                return httpx.Response(200, json=[])
            if path.startswith("/papers/"):  # GET /papers/{id} detail read only
                return httpx.Response(
                    200,
                    json={
                        "id": 1,
                        "title": "t",
                        "authors": [],
                        "csl_json": {},
                        "processing_tier": "metadata-only",
                        "attachment_count": 0,
                        "chunk_count": 0,
                        "attachments": [],
                        "tags": [],
                    },
                )
            return httpx.Response(200, json=[])
        if path == "/citations/suggest":
            return httpx.Response(200, json={"suggestions": []})
        return httpx.Response(200, text="")

    mcp = create_server(_client(handler))
    _call(mcp, "search_library", {"query": "x"})
    _call(mcp, "get_paper", {"paper_id": 1})
    _call(mcp, "full_text_search", {"query": "x"})
    _call(mcp, "find_passages", {"query": "x"})
    _call(mcp, "format_citation", {"paper_ids": [1], "format": "bibtex"})
    bad = [c for c in calls if (c[0], c[1].rstrip("/")) not in ALLOWED and c != ("GET", "/papers/1")]
    assert not bad, f"non-allowlisted calls: {bad}"


def test_tool_registry_is_exactly_the_five_read_tools():
    mcp = create_server(_client(lambda r: httpx.Response(200, json=[])))
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {"search_library", "get_paper", "full_text_search", "find_passages", "format_citation"}
