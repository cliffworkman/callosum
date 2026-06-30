"""inc 213 (B1 SP1) — the read-only MCP server: tool registry + request/response mapping + the read-only allowlist.

Hermetic: a MockTransport stands in for the running callosum app (no DB, no live server). The CallosumClient's
real request-build + response-parse code runs against canned responses, and the allowlist test asserts the
server only ever issues read calls to the five allowlisted endpoints.
"""

from __future__ import annotations

import asyncio

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
    # FastMCP returns (content, structured); structured wraps a non-dict return under {"result": ...}.
    _content, structured = asyncio.run(mcp.call_tool(name, args))
    if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
        return structured["result"]
    return structured


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
    assert out == [
        {"id": 7, "title": "Faces", "authors": ["A. B"], "year": 2020, "venue": "J", "citation_key": "b20"}
    ]
