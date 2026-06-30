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

    @mcp.tool()
    def get_paper(paper_id: int) -> dict:
        """Full metadata for one library paper by id: title, authors, year, DOI, venue, abstract, tags, type."""
        return client.get_paper(paper_id)

    @mcp.tool()
    def full_text_search(query: str, limit: int = 20) -> list[dict]:
        """Search the VERBATIM text inside the library's PDFs for an exact phrase. Returns per-occurrence hits
        with the paper, the page, and a text snippet. Use this for exact wording; use search_library for
        keyword/metadata search."""
        return client.fulltext(query, limit)

    @mcp.tool()
    def find_passages(query: str, top_k: int = 5) -> list[dict]:
        """Retrieve the library passages most relevant to a claim or question — GROUNDED: each result carries
        its verbatim quote and page number, so you can cite the source. Use this to ground a statement in the
        library."""
        return client.find_passages(query, top_k)

    @mcp.tool()
    def format_citation(paper_ids: list[int], format: str = "bibtex") -> str:
        """Format one or more library papers as a citation string. format is one of "bibtex", "ris", "csl-json"."""
        return client.format_citation(paper_ids, format)

    return mcp


def build() -> FastMCP:
    return create_server(default_client())
