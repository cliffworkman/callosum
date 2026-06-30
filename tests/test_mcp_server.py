"""inc 213 (B1 SP1) — the read-only MCP server: tool registry + request/response mapping + the read-only allowlist.

Hermetic: a MockTransport stands in for the running callosum app (no DB, no live server). The CallosumClient's
real request-build + response-parse code runs against canned responses, and the allowlist test asserts the
server only ever issues read calls to the five allowlisted endpoints.
"""

from __future__ import annotations

import asyncio
import json

import httpx

# The U+E000/U+E001 private-use chars callosum's FTS snippet wraps matched terms in (see fulltext_repo).
_FT_OPEN, _FT_CLOSE = chr(0xE000), chr(0xE001)

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
    assert out == [
        {"id": 7, "title": "Faces", "authors": ["A. B"], "year": 2020, "venue": "J", "citation_key": "b20"}
    ]


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
