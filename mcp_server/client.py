"""Thin HTTP client over the running callosum app (B1 SP1).

The MCP server's only data path: each tool calls one read endpoint here, and this module shapes the
response. Read-only by construction — there are no write methods, and every request goes to a hardcoded
read endpoint. `http` is injectable so the hermetic tests can drive an httpx.MockTransport (no live app).
"""

from __future__ import annotations

import os

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8080"


class CallosumUnavailable(RuntimeError):
    """callosum isn't reachable (not running / wrong base URL / auth)."""


class CallosumClient:
    def __init__(self, base_url: str, *, token: str | None = None, http: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._http = http or httpx.Client(base_url=self.base_url, headers=headers, timeout=30.0)

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        try:
            return self._http.get(path, params=params)
        except httpx.HTTPError as exc:
            raise CallosumUnavailable(
                f"callosum isn't reachable at {self.base_url} — is it running? ({exc})"
            ) from exc

    @staticmethod
    def _ok(r: httpx.Response) -> httpx.Response:
        if r.status_code == 401:
            raise CallosumUnavailable(
                "callosum rejected the request (401) — set CALLOSUM_MCP_TOKEN to the app's access token."
            )
        if r.status_code >= 400:
            raise CallosumUnavailable(f"callosum returned {r.status_code}: {r.text[:200]}")
        return r

    def _post(self, path: str, body: dict) -> httpx.Response:
        try:
            return self._http.post(path, json=body)
        except httpx.HTTPError as exc:
            raise CallosumUnavailable(
                f"callosum isn't reachable at {self.base_url} — is it running? ({exc})"
            ) from exc

    def search(self, query: str, limit: int = 20) -> list[dict]:
        r = self._ok(self._get("/papers", {"q": query, "limit": limit}))
        return [
            {
                "id": p["id"],
                "title": p["title"],
                "authors": p.get("authors") or [],
                "year": p.get("year"),
                "venue": p.get("venue"),
                "citation_key": p.get("citation_key"),
            }
            for p in r.json()
        ]

    def get_paper(self, paper_id: int) -> dict:
        r = self._get(f"/papers/{int(paper_id)}")
        if r.status_code == 404:
            raise CallosumUnavailable(f"paper {paper_id} not found")
        p = self._ok(r).json()
        return {
            "id": p["id"],
            "title": p["title"],
            "authors": p.get("authors") or [],
            "year": p.get("year"),
            "doi": p.get("doi"),
            "venue": p.get("venue"),
            "item_type": p.get("item_type"),
            "abstract": p.get("abstract_text"),
            "citation_key": p.get("citation_key"),
            "tags": [t["name"] for t in (p.get("tags") or [])],
        }

    def fulltext(self, query: str, limit: int = 20) -> list[dict]:
        r = self._ok(self._get("/papers/fulltext", {"q": query, "limit": limit}))
        out = []
        for h in r.json():
            # Drop the U+E000/U+E001 bold markers callosum wraps matched terms in (see fulltext_repo).
            snippet = (h.get("snippet") or "").replace("", "").replace("", "")
            out.append(
                {
                    "paper_id": h["paper_id"],
                    "title": h.get("title"),
                    "page_start": h.get("page_start"),
                    "page_end": h.get("page_end"),
                    "snippet": snippet,
                }
            )
        return out

    def find_passages(self, query: str, top_k: int = 5) -> list[dict]:
        r = self._ok(self._post("/citations/suggest", {"text": query, "top_k": top_k, "evaluate": False}))
        return [
            {
                "paper_id": s["paper_id"],
                "title": s.get("title"),
                "quote": s.get("quote"),
                "page_start": s.get("page_start"),
                "page_end": s.get("page_end"),
                "coordinate_precision": s.get("coordinate_precision"),
                "match_score": s.get("match_score"),
            }
            for s in (r.json().get("suggestions") or [])
        ]

    def format_citation(self, paper_ids: list[int], fmt: str = "bibtex") -> str:
        r = self._ok(self._post("/papers/export", {"paper_ids": [int(i) for i in paper_ids], "format": fmt}))
        return r.text


def default_client() -> CallosumClient:
    return CallosumClient(
        os.environ.get("CALLOSUM_BASE_URL", DEFAULT_BASE_URL),
        token=os.environ.get("CALLOSUM_MCP_TOKEN") or None,
    )
