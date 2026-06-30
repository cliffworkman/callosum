# callosum MCP server (read-first)

A small [Model Context Protocol](https://modelcontextprotocol.io) server that lets an AI agent
(Claude Desktop, Cursor, etc.) **use your callosum library through callosum** — so callosum stays
the provenance + grounding authority, rather than being bypassed as a dumb file store.

**Read tools are always on:** an agent can search, read, full-text-search, retrieve **grounded passages
(verbatim quote + page)**, and format citations. **Write tools are opt-in and OFF by default** (SP2): when
you enable *AI-agent writes* in callosum Settings, the agent can also add tags, add papers to an axis, save a
reference by DOI, and add a note — each **additive, reversible, and provenance-stamped `ai-agent`**, with a
revert in Settings. It can never delete, overwrite, merge, or scan — those stay human-only.

## How it works

`mcp_server/` is a **separate deployable** that mirrors `sync_server/`: the local callosum app does
not import it, and it does not import the app — each tool just makes one HTTP call to the running
callosum API (default `http://127.0.0.1:8080`) over the standard MCP **stdio** transport. There is no
network listener; the agent host spawns it as a subprocess.

## Setup

1. **Have callosum running** (the server reads from the live API):
   ```
   uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
   ```
2. **Install the MCP deps** (in any Python 3.11+ env — they're kept out of callosum's own deps):
   ```
   python -m venv .mcp-venv && . .mcp-venv/bin/activate    # Windows: .mcp-venv\Scripts\activate
   pip install -r mcp_server/requirements.txt
   ```
3. **Point your agent host at it.** Add this to the host's MCP config (Claude Desktop:
   `claude_desktop_config.json`; Cursor: its MCP settings), using the **absolute** path to your repo
   and Python:
   ```json
   {
     "mcpServers": {
       "callosum": {
         "command": "/abs/path/to/.mcp-venv/bin/python",
         "args": ["-m", "mcp_server"],
         "cwd": "/abs/path/to/callosum",
         "env": {
           "CALLOSUM_BASE_URL": "http://127.0.0.1:8080",
           "CALLOSUM_MCP_TOKEN": ""
         }
       }
     }
   }
   ```
   - `CALLOSUM_BASE_URL` — where callosum is listening (default `http://127.0.0.1:8080`).
   - `CALLOSUM_MCP_TOKEN` — **only** if you enabled **Remote access** in callosum's Settings (inc 168);
     set it to that access token. For a normal localhost setup, leave it empty.

Restart the host; the **callosum** tools appear.

## Tools

| Tool | What it does |
|---|---|
| `search_library(query, limit=20)` | Keyword search over title/authors/journal/abstract. |
| `get_paper(paper_id)` | Full metadata for one paper (title, authors, year, DOI, venue, abstract, tags, type). |
| `full_text_search(query, limit=20)` | Search the **verbatim** text inside your PDFs; per-occurrence hits with page + snippet. |
| `find_passages(query, top_k=5)` | **Grounded** retrieval — the library passages most relevant to a claim, each with its verbatim quote + page so the agent can cite the source. |
| `format_citation(paper_ids, format="bibtex")` | Format papers as `bibtex` / `ris` / `csl-json`. |

## Write tools (opt-in)

These appear **only** when you turn on **AI-agent writes** in callosum Settings → AI agent (default OFF). Each
write is additive, recorded in an audit log, and reversible from that same Settings panel (one-click Revert). The
agent's host shows you its native confirmation prompt before each tool call — that's the in-the-moment gate.

| Tool | What it does |
|---|---|
| `add_tag(paper_id, tag)` | Tag a paper (stamped `ai-agent`; revert removes the tag). |
| `add_to_axis(paper_id, axis_id)` | Add a paper to one of your axes (not My Publications — authorship is yours to assert; revert removes it). |
| `save_reference(identifier)` | Save a reference by **DOI** — resolved against Crossref; an unresolvable DOI is refused, never fabricated. Metadata-only (no PDF). Revert trashes a newly-created paper; a re-found existing paper is left alone. |
| `annotate(paper_id, text)` | Add a note to a paper (stamped `ai-agent`; revert deletes the note). |

To enable: Settings → **AI agent** → turn on *Allow agent writes*. To revert anything an agent did, the same
panel lists recent agent writes with a per-row **Revert** (and **Revert all**). Kill switch:
`CALLOSUM_DISABLE_AGENT_WRITES=1` forces writes off regardless of the setting.

## Notes

- **Read tools are read-only by construction; write tools touch only `/agent/*`.** The read methods call a
  hardcoded allowlist; the write methods call only the gated, audited, reversible `/agent/*` endpoints. There is
  no delete/overwrite/merge/scan method anywhere in the client — those stay human-only.
- **Local, no egress of its own.** It returns your own library; any onward egress is the agent's/your
  decision, as with any read tool.
- **Honest failures.** If callosum isn't running, or a token is required and missing, the tool returns
  a clear error — never a fabricated result.
- **Verification reality:** the MCP↔host handshake runs only inside the agent host, so the live
  connection is a manual check. The request/response mapping + the read-only allowlist are covered by
  `tests/test_mcp_server.py` (hermetic, no live app), and the endpoints it calls are themselves tested
  in the main suite.
- Built against the `mcp` Python SDK (FastMCP). `mcp>=1.2` is pinned in `mcp_server/requirements.txt`.
