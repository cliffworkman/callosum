"""callosum read-first MCP server (B1 SP1).

Each tool calls one read endpoint via CallosumClient and returns a compact, JSON-able result. Read-only —
search / read / full-text / grounded passages / formatted citations. No write/scan/mutating route is reachable
(the client exposes only the five read methods). stdio transport only; local; no egress of its own.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.client import CallosumClient, default_client


def create_server(client: CallosumClient) -> FastMCP:
    mcp = FastMCP("callosum-library")

    @mcp.tool()
    def search_library(query: str, limit: int = 20) -> list[dict]:
        """Search the callosum reference library by keyword (matches title, authors, journal, abstract).
        Returns matching papers with their id, title, authors, year, and venue."""
        return client.search(query, limit)

    return mcp


def build() -> FastMCP:
    return create_server(default_client())
