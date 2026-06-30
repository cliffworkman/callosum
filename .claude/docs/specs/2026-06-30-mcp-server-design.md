# Read-first MCP server (backlog B1) — design

**Status:** approved for implementation (brainstorm 2026-06-30).
**Design home:** `future-tracks/opus4.8_future-tracks_benchmarkrevisions.md` §B1 (the one genuinely-new architectural
item; this doc is the detail the backlog asked for).
**Scope:** decomposed into **SP1** (this spec — the **read-only** stdio MCP server) + **SP2** (gated writes —
confirmation + provenance-stamp + session-undo/audit log; its own later spec + a heavy A4/A-A pass).

## Goal

Expose callosum's own **MCP server** so external agents (Claude Desktop / Cursor / etc.) use the library **through
callosum** — keeping it the **provenance + grounding authority** — rather than bypassing it as a dumb store (or
inheriting Zotero's "full access to your computer" problem). SP1 ships the **read-first** half: an agent can search,
read, full-text-search, **retrieve grounded passages (verbatim quote + page anchor)**, and format citations — all
local, no library mutation.

## Values gate (run — APPROACH-AVOIDANCE, since this is a novel/architectural change)

- **Drift typology → emergent**, adopted deliberately: "callosum as an MCP provider to an agent" is a posture shift
  absent from the built artifact. The aligned framing is B1's own rationale — callosum stays the authority agents
  route *through*, which **strengthens** A2 (every read carries its evidence: quote + page) and A1/A4 (the human
  stays the filter; SP1 mutates nothing).
- **Load-bearing constraints (honored below):** read-first carries evidence (A2); **default-off / opt-in** (the user
  must configure the host to spawn it; A5 sovereignty); **local** stdio, no network listener (A5); a **new dependency
  justified + fenced + egress-considered** (heuristic #5); **state coverage** — reads expose only the curated subset,
  and the grounded-passage tool is honest about `coordinate_precision` (#6/A3).
- **No A-A veto in play:** it reads the user's *own* library (not another tool's store), no paywall circumvention, no
  accusation. SP1 has no write path (the A4-sensitive surface is deferred to SP2's own gate).

## Architecture — a thin stdio adapter over the running app (NOT a direct-DB reader)

A new **`mcp_server/`** package, a **separate in-repo deployable** mirroring `sync_server/` (`sync_server/README.md:3-4`:
"the local callosum app never imports it"; its own `requirements.txt`). The MCP server is a **protocol adapter**: an
`mcp`-SDK **stdio** server whose each tool makes **one HTTP call** to an existing callosum endpoint
(`CALLOSUM_BASE_URL`, default `http://127.0.0.1:8080`) via **httpx**, then shapes the response into the tool's return.

**Why over the HTTP API, not the DB directly:** it reuses the **audited endpoints**, their honesty/egress contracts,
and the **embedding model + vector store already cached on `app.state`** (`find_passages` needs them —
`citations.py:183-207`). Opening the SQLite directly would duplicate the read logic, load a *second* copy of the
heavy `SentenceTransformerEmbeddingModel`, and bypass the audited surface. The HTTP-adapter choice literally keeps
callosum the authority (every MCP op runs callosum's own logic) — exactly B1's point, and the `sync_server`-over-HTTP
shape generalized. (`app/` never imports `mcp_server/`; `mcp_server/` never imports `app/` — it talks HTTP.)

- **`app/` is untouched** by SP1 (no new endpoint, no migration) — every tool calls an endpoint that already exists.
- **Auth:** if Remote access (inc 168) is on, the server sends `Authorization: Bearer <token>` (from
  `CALLOSUM_MCP_TOKEN` env). Default (localhost, gate off) needs no token.
- **Module-level + injectable:** `create_server(client) -> FastMCP` (an injected httpx client/base-url for tests) +
  `server = create_server(default_client())` (mirrors `sync_server.create_server` / the app's `create_app`).

## SP1 — the read tools (all local, no egress, no mutation)

Each tool is a typed `@mcp.tool()` that calls the named endpoint and returns a compact JSON-able dict/list.

1. **`search_library(query: str, limit: int = 20)`** → `GET /papers?q={query}&limit={limit}` → a list of
   `{id, title, authors, year, venue, doi}` (from `PaperListItem`, `papers.py:42-53`). *"Search the callosum library
   by keyword (title/author/journal/abstract)."*
2. **`get_paper(paper_id: int)`** → `GET /papers/{paper_id}` → `{id, title, authors, year, doi, venue, abstract,
   item_type, tags, citation_key}` (from `PaperDetailResponse`, `papers.py:85-110`; use `abstract_text` plain text).
   *"Full metadata for one paper."* 404 → a clean "not found" tool error.
3. **`full_text_search(query: str, limit: int = 20)`** → `GET /papers/fulltext?q={query}&limit={limit}` → a list of
   `{paper_id, title, page_start, page_end, snippet}` (from `FulltextHit`, `fulltext.py:22-31`). *"Find a verbatim
   phrase inside your PDFs."*
4. **`find_passages(query: str, top_k: int = 5)`** → `POST /citations/suggest {text: query, top_k, evaluate: false}`
   → a list of `{paper_id, title, quote, page_start, page_end, coordinate_precision, match_score}` (from the
   `Suggestion`/`SuggestResponse` shape, `suggest.py:34-48` / `citations.py:119-135`). **The grounding primitive** —
   each passage carries its verbatim quote + page so an agent can ground a claim in the user's library. *"Retrieve the
   library passages most relevant to a claim or question, each with its verbatim quote + page."* `evaluate:false` →
   skip the NLI stance pass (pure retrieval).
5. **`format_citation(paper_ids: list[int], format: str = "bibtex")`** → `POST /papers/export {paper_ids, format}`
   (`format` ∈ `{"bibtex","ris","csl-json"}`, `papers.py:335-352`) → the formatted citation text. *"Format references
   from the library as BibTeX / RIS / CSL-JSON."*

(Axes/tags browsing tools are trivially addable later; SP1 stays the core search + ground + cite set.)

## Safety posture (read-only, in code)

- **Read-only by construction:** the adapter has a **hardcoded allowlist** of exactly the five endpoints above (all
  read; `/citations/suggest` + `/papers/export` are read-only/no-egress per their docstrings). It **never** calls a
  write/mutating route, the file-read/scan routes (`/library/scan`, `/papers/{id}/pdf`), or `DELETE`/`PATCH`. There
  are **no write tools** in SP1.
- **Local + default-off:** stdio transport only (no network listener); the server runs **only** when the user
  configures their agent host to spawn it (`command: python -m mcp_server`) **and** the app is running. No egress of
  its own — it returns the user's own library; onward egress is the agent's/user's decision, as for any read tool.
- **Honest failures:** the app down / a 4xx-5xx → a clear tool error ("callosum isn't running at <base_url>" / the
  endpoint's detail), never a fabricated result. A 401 (remote-access on, no/Bad token) → "set CALLOSUM_MCP_TOKEN".
- **Logging:** the server logs each tool call (name + args summary) to **stderr** (the MCP convention — stdout is the
  protocol channel) for transparency; no library text in the logs.

## Dependency

The official **`mcp` Python SDK** (provides `FastMCP` + the stdio server) + **httpx** — in a **separate
`mcp_server/requirements.txt`** (the `sync_server` fencing: never enters the root `requirements.txt`'s pinned
web-stack; `app/` gains nothing). Justified — required to speak MCP (like `PyJWT[crypto]` for OIDC, citeproc for
citations). **Security audit applies** (a new external-facing surface + a new dependency).

## Testing & verification

- **Pure-mapping tests** (`tests/test_mcp_server.py`, hermetic): build the server with an **injected fake httpx
  client** that returns canned callosum responses; assert (a) the tool registry (the 5 tools are registered), (b)
  each tool builds the right request (path + params/body) and shapes the response correctly, (c) read-only — no tool
  issues a write/DELETE/PATCH/scan call (assert the fake client only ever saw the allowlisted read calls), (d) a 404 /
  app-down → a clean tool error. The `mcp` SDK supports calling tools in-process for tests.
- **Verification reality (like the Word/Docs adapters):** the MCP↔host handshake runs only inside the agent host
  (Claude Desktop/Cursor), so the **live connection is the maintainer's manual check** (configure the host → call a
  tool → see grounded results). The value proven in-repo is the pure mapping + the already-audited endpoints it calls.

## Gates / acceptance (SP1)

- **No app change** → no migration, no new app endpoint, **QA surface-map unchanged** (a separate process calling
  existing endpoints adds no app API/FE surface; no new QA route — the LO-suggest-macro / GDocs-add-on precedent).
- **Security audit** `.claude/security-audits/2026-06-30_mcp-server.md`: read-only allowlist (no write/scan calls);
  local stdio (no network listener); token handling (write-only, from env, never logged); SDK supply-chain (pin it);
  no egress of its own; honest failures. → PASS.
- **pytest:** `tests/test_mcp_server.py` green; the full suite unaffected (`app/` untouched). **No new dependency in
  the main app** (the SDK is in `mcp_server/requirements.txt`; the *test* imports it — so `requirements-dev.txt` gets
  the `mcp` SDK, the only dev-side add, to run the hermetic tests in CI; flag this in the audit).
- **Principles/A-A:** the values gate above (aligned; emergent-adopted-deliberately; reads carry evidence; local;
  default-off). **Help/README:** `mcp_server/README.md` (the setup runbook — wire Claude Desktop/Cursor, env vars,
  the read-only/local note); a short pointer in the help corpus (`HELP-DOCS-SYNCED`).
- **Acceptance:** with the app running, an agent host configured to spawn `python -m mcp_server` can call
  `search_library` / `get_paper` / `full_text_search` / `find_passages` / `format_citation` and get correct,
  page-anchored results; the server issues only read calls; nothing in the library is mutated; the app being down or
  a bad token yields a clear error. Pure-mapping tests cover the request/response/allowlist contract.

## SP2 (follow-on — its own spec + heavy A4/A-A pass)

Gated **write** tools (`add_tag`, `add_to_axis`, `save_reference`, `annotate`) — each **provenance-stamped** (a new
`imported_source="ai-agent"` added to the inc-49 don't-clobber guard set, `enrichment.py:171-175`), **reversible**
(soft-delete / a session-undo log — net-new machinery), and **gated** (an explicit writes-enabled opt-in, like
remote-access; per-write confirmation via MCP elicitation where the host supports it) + an **agent audit log** ("what
did the agent change, on what evidence"). The A4 "user owns every irreversible act" value makes the gate mandatory,
not optional — hence its own design pass.

## Key code anchors (from the B1 map)

- Precedent: `sync_server/{app.py:60-89 create_server, 112-117 _build_from_env}`, `requirements.txt:1-2`,
  `README.md:3-4,23-38`.
- Read endpoints: `routers/papers.py:170-205` (search, `PaperListItem` 42-53) · `routers/fulltext.py:22-53`
  (`FulltextHit`) · `routers/papers.py:220-234` + `PaperDetailResponse` 85-110 · `routers/citations.py:138-155` +
  `citations/suggest.py:34-59` (`Suggestion`; `evaluate=false`) · `routers/papers.py:335-352` (`/papers/export`).
- Auth: `app/backend/api/access_control.py:70-90` (bearer gate, default-off) + `app_settings.py:306-321`.
- DB/engine (not used by SP1's HTTP adapter, but the read-only-open precedent): `persistence/database.py:8-20`;
  `CALLOSUM_DB_URL` (`app.py:99,68`).
- Provenance (SP2): `imported_source` constants (`metadata/enrichment.py:17-30`, `discovery/search.py:15`); the
  don't-clobber guard `_can_update_from_crossref` (`enrichment.py:171-175`).
- No existing MCP code / no `mcp` SDK dependency anywhere (confirmed) → both are net-new.
