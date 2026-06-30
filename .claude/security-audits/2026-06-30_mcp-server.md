# Security audit — read-first MCP server (B1 SP1, inc 213)

**Date:** 2026-06-30
**Feature:** a new in-repo deployable `mcp_server/` — a Model Context Protocol **stdio** server exposing five
**read-only** tools (`search_library`, `get_paper`, `full_text_search`, `find_passages`, `format_citation`) to an
external agent host (Claude Desktop / Cursor). Each tool makes one HTTP call to the running callosum app
(`CALLOSUM_BASE_URL`, default `http://127.0.0.1:8080`) via an injectable `httpx.Client` and shapes the response.
**Audit triggers:** a new external-facing surface (a process other tools connect to); a new dependency (the `mcp`
SDK); 3+ files.

## Threat review

- **Read-only by construction.** `CallosumClient` exposes exactly five methods, each hitting a hardcoded read
  endpoint: `GET /papers`, `GET /papers/{id}`, `GET /papers/fulltext`, `POST /citations/suggest` (read-only,
  no-egress per its docstring), `POST /papers/export` (read-only). There is **no** write/scan method — no
  `PUT`/`PATCH`/`DELETE`, no `/library/scan`, no `/papers/{id}/pdf`. `test_server_only_issues_readonly_calls`
  drives every tool through a recording transport and asserts only those four `(method, path)` pairs (plus the
  one `GET /papers/{id}` detail) are ever issued; `test_tool_registry_is_exactly_the_five_read_tools` pins the
  exposed set. So an agent cannot mutate, delete, scan a folder, or read an arbitrary file via this server.
- **Input validation.** Tool args are typed by FastMCP (`query: str`, `limit: int`, `paper_id: int`,
  `paper_ids: list[int]`, `format: str`). `paper_id` / `paper_ids` are coerced with `int(...)` before reaching
  the path/body. The query/text/format reach callosum only as bound query-params / JSON-body values, which the
  app's already-audited endpoints validate (e.g. `/papers/export` rejects any `format` outside
  `bibtex`/`ris`/`csl-json` → 422; `/papers/fulltext` sanitizes the FTS MATCH; `/citations/suggest` caps text).
  The MCP server itself builds no SQL and no filesystem path.
- **SSRF / external calls.** The only outbound target is `CALLOSUM_BASE_URL` — an **operator-set env var**
  (default loopback), never derived from a tool argument. No tool argument can redirect the request to another
  host; the path is one of the five hardcoded literals. httpx has a 30s timeout. (This mirrors the
  `sync_server`/`HttpSyncTransport` posture: one configured base URL, fail-closed.)
- **Secret handling.** `CALLOSUM_MCP_TOKEN` (used only when callosum's opt-in Remote access, inc 168, is on) is
  read from the env once and set as a constant `Authorization: Bearer` header on the httpx client. It is never
  logged, never returned to the agent, and never placed in a tool result. (The token is the **user's own**
  access token, supplied by the user in the host config — the same opt-in posture as the Google Docs add-on.)
- **Data egress.** The server returns the **user's own library** (metadata, snippets, grounded quotes, formatted
  citations) to the agent host the user chose to connect. This is not a new automated egress vector: nothing
  leaves the machine except in response to an explicit tool call the agent makes on the user's behalf, and the
  server has no network listener (stdio only — the host spawns it). The Gemini library-text egress gate
  (invariant #3) is a *separate* channel, untouched. Onward egress of a tool result is the agent's/user's
  decision, as for any read tool.
- **Resource caps.** `limit` / `top_k` flow through to the endpoints' own caps (`/papers` ≤ 200, `/citations/suggest`
  ≤ its Pydantic bound). No unbounded loop; one HTTP call per tool invocation.
- **File-path safety.** No filesystem access of any kind in `mcp_server/`.
- **Supply-chain.** One new dependency, the official `mcp` Python SDK (FastMCP), pinned to `mcp>=1.2` in
  `mcp_server/requirements.txt` (a separate file — it never enters the app's prod `requirements.txt`); added to
  `requirements-dev.txt` only so CI can run the hermetic test. httpx is already a root dependency. Justified — an
  MCP server cannot be built without the protocol SDK (cf. `PyJWT[crypto]` for OIDC, `citeproc` for citations).
- **App isolation.** `app/` does not import `mcp_server/`, and `mcp_server/` does not import `app/` (verified) —
  it communicates only over HTTP, so the app's attack surface and dependency set are unchanged.

## Negative-path checks (run)

- callosum down (httpx `ConnectError`) → `CallosumUnavailable("…isn't reachable…")`, not a fabricated result
  (`test_app_down_and_401_are_clean_errors`).
- 401 from a required-but-missing/bad token → `CallosumUnavailable("…set CALLOSUM_MCP_TOKEN…")`, not a result
  (same test).
- A configured token → sent verbatim as `Authorization: Bearer` and nowhere else
  (`test_bearer_token_is_sent_when_configured`).
- Every tool invocation issues only read-verb calls to the allowlisted endpoints; no write verb, no scan/pdf path
  (`test_server_only_issues_readonly_calls`).

## Verification reality

The live MCP↔host handshake runs only inside the agent host (Claude Desktop/Cursor), so the live connection is the
maintainer's manual check. What is proven in-repo: the request/response mapping + the read-only allowlist +
honest-failure handling (`tests/test_mcp_server.py`, hermetic via `httpx.MockTransport`), and the endpoints the
tools call are themselves covered by the main suite.

## Pre-public note

This server targets the single-user local setup (a host spawning a stdio subprocess on the same machine). If
callosum is ever exposed remotely, the MCP server should run only against a loopback `CALLOSUM_BASE_URL` and the
Remote-access token control (inc 168) applies as for any client.

**Security Audit: PASS** — read-only by construction; local stdio with no listener; one configured (not
arg-derived) target → no SSRF; token write-only from env, never logged/returned; no egress of its own; honest
failures; one justified, fenced, pinned dependency; the app's surface is unchanged.
