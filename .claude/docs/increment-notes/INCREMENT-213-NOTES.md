# Increment 213 — read-first MCP server (backlog B1, SP1)

## Implemented
A new in-repo deployable **`mcp_server/`** — a Model Context Protocol **stdio** server that lets an external
agent host (Claude Desktop / Cursor / etc.) use the callosum library **through callosum** (keeping callosum the
provenance + grounding authority), read-only.

- `mcp_server/client.py` — `CallosumClient(base_url, *, token=None, http=None)`: a thin httpx wrapper with five
  **read** methods (`search`, `get_paper`, `fulltext`, `find_passages`, `format_citation`), each hitting one
  hardcoded read endpoint; `_ok` maps 401 → a token hint and ≥400 → a clean error; httpx errors → `CallosumUnavailable`
  (never a fabricated result). `default_client()` reads `CALLOSUM_BASE_URL` (default `http://127.0.0.1:8080`) +
  `CALLOSUM_MCP_TOKEN`. `http` is injectable so tests drive an `httpx.MockTransport` (no live app).
- `mcp_server/server.py` — `create_server(client) -> FastMCP` registers the five `@mcp.tool()`s (their docstrings are
  the tool descriptions the agent sees) + `build()` = `create_server(default_client())`.
- `mcp_server/__main__.py` — `python -m mcp_server` → `build().run(transport="stdio")`.
- `mcp_server/requirements.txt` (`mcp>=1.2`, `httpx>=0.27`) + `mcp_server/README.md` (the host-setup runbook).
- `requirements-dev.txt` += `mcp` (so CI can run the hermetic test).
- `tests/test_mcp_server.py` — 9 hermetic tests.

The five tools → endpoints: `search_library`→`GET /papers`; `get_paper`→`GET /papers/{id}`;
`full_text_search`→`GET /papers/fulltext` (strips the U+E000/U+E001 FTS bold markers);
`find_passages`→`POST /citations/suggest {evaluate:false}` (grounded passages: quote + page + `coordinate_precision`);
`format_citation`→`POST /papers/export`.

**No app change** — `app/` is untouched; `app/` never imports `mcp_server/` and `mcp_server/` never imports `app/`
(it talks HTTP). So: no migration, no new app endpoint, QA surface-map unchanged (145/145 API + 685/685 FE).

## Key technical detail
The installed `mcp` SDK's `FastMCP.call_tool(name, args)` is **shape-inconsistent by return type**: a non-dict tool
return (list / str) comes back as a `(content_blocks, structured)` tuple where `structured = {"result": <value>}`,
but a **dict** return comes back as a bare `list[TextContent]` (length 1, JSON in `.text`). The test helper `_call`
handles both: tuple → unwrap `structured["result"]` (or `structured` if not the single-key wrapper); else
`json.loads(content[0].text)`. (Documented in the test + the spec's verify-note.)

Read-only is **structural**: `CallosumClient` exposes only the five read methods — there is no write/scan/delete
method anywhere — and `test_server_only_issues_readonly_calls` drives every tool through a recording transport and
asserts only the four allowlisted `(method, path)` pairs (+ the `GET /papers/{id}` detail) are ever issued.

## Manual verification script (live MCP↔host — the maintainer's check)
1. `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080` (have callosum running with a library).
2. `python -m venv .mcp-venv && . .mcp-venv/bin/activate && pip install -r mcp_server/requirements.txt`.
3. Add the `mcpServers.callosum` block from `mcp_server/README.md` to Claude Desktop / Cursor (absolute paths;
   `CALLOSUM_MCP_TOKEN` only if Remote access is on). Restart the host.
4. Ask the agent to "search the library for X" / "find passages grounding <claim>" → confirm results carry the
   paper, quote, and page; confirm there is no tool that tags/edits/deletes.

In-repo (no host needed): `python -c "from mcp_server import create_server, default_client; create_server(default_client())"`
(smoke import) + `HF_HUB_OFFLINE=1 python -m pytest tests/test_mcp_server.py -q` (9 passed).

## Gates
- **Audit:** `.claude/security-audits/2026-06-30_mcp-server.md` **PASS** (read-only by construction; local stdio,
  no listener; one configured [not arg-derived] target → no SSRF; token write-only from env, never logged/returned;
  no egress of its own; honest failures; one justified/fenced/pinned dependency; app surface unchanged).
- **Principles/values:** the values gate ran in the spec (APPROACH-AVOIDANCE — emergent value "callosum as MCP
  provider", adopted deliberately; read-first carries evidence [A2]; default-off/opt-in [A5]; SP1 mutates nothing
  [A4]; no A-A veto). Non-triggering at the code level (no new claim/signal).
- **QA (rule #10):** no new app API/FE surface (an external process reusing existing endpoints) → surface map
  unchanged, no new QA route (the inc-157 LO-suggest-macro / inc-170 GDocs-add-on precedent).
- pytest **+9**; ruff clean; help corpus +1 paragraph (`HELP-DOCS-SYNCED` → 213).

## Pytest
733 → **742 passed, 1 skipped** (+9 `tests/test_mcp_server.py`).

## NEXT
**SP2 (gated writes)** — `add_tag` / `add_to_axis` / `save_reference` / `annotate`, each provenance-stamped
(`imported_source="ai-agent"` in the inc-49 don't-clobber set), reversible, and gated (a writes-enabled opt-in +
per-write confirmation) + an agent audit log. Its own design spec + a heavy A4/A-A pass (the A4 "user owns every
irreversible act" value makes the gate mandatory). Other B-items (B2 collaboration, B3 OCR, B4 citation-context
classifier, B5 mobile) remain larger, own design passes.
