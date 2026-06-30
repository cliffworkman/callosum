# Increment 216 — gated MCP agent writes (B1 SP2)

The second slice of the read-first MCP server (SP1 = inc 213): let an external agent **write** to the library —
add a tag, add a paper to an axis, save a reference by DOI, add a note — under a default-off opt-in, with every
write provenance-stamped `ai-agent`, recorded in an audit log, and reversible from Settings. The chosen
human-in-loop model (maintainer): **review + revert after** — writes apply immediately but are
additive/reversible/audited; the agent host's native per-call prompt is the in-the-moment gate (no elicitation,
no queue). `save_reference` is **DOI-verified** (resolve via Crossref, refuse the unresolvable).

## Implemented

- **Opt-in flag** — `app/backend/app_settings.py`: `set_agent_writes_enabled` / `stored_agent_writes`
  (default `False`; `CALLOSUM_DISABLE_AGENT_WRITES=1` forces off — the inc-168 recovery-hatch pattern).
  Surfaced on `GET /settings.agent_writes_enabled` + settable via `PUT /settings`
  (`app/backend/api/routers/settings.py`).
- **Audit table** — `agent_writes` (`schema_findings.py`, re-exported from `schema.py`): id, created_at,
  action (`tag`|`axis`|`reference`|`note`), `target_paper_id` (**no FK** — outlives a paper purge), tool,
  `detail_json` (JSON), `reverted_at`; `Index ix_agent_writes_created`. **Migration 0029** (guarded additive,
  no-op downgrade — the 0021/0022 pattern). `persistence/agent_repo.py` (NEW): `record_agent_write` /
  `list_agent_writes` / `get_agent_write` / `mark_reverted` / `delete_note`.
- **Gated endpoints** — `app/backend/api/routers/agent.py` (NEW), included after `settings.router`:
  `GET /agent/status`, `POST /agent/papers/{id}/tags`, `POST /agent/axes/{axis_id}/papers`
  (My-Pubs → 422), `POST /agent/references` (DOI-verified), `POST /agent/papers/{id}/notes`,
  `GET /agent/writes`, `POST /agent/writes/{id}/revert`. Writes gate via the `_require_writes` dependency
  (403 off). `metadata/enrichment.py` gained `AI_AGENT_SOURCE = "ai-agent"` (already outside the
  `_can_update_from_crossref` allowlist → batch enrich won't clobber an agent record).
- **MCP write tools** — `mcp_server/client.py`: `agent_status` (fail-closed `try/except → False`) +
  `add_tag`/`add_to_axis`/`save_reference`/`annotate`. `mcp_server/server.py`: `create_server` calls
  `client.agent_status()` at build and registers the four write tools **only when enabled**.
- **Settings UI** — `app/frontend/js/35_settings.jsx`: an `AgentSettings` component (the toggle bound to
  `/settings`, the activity list from `GET /agent/writes`, per-row + Revert-all) + `.agent-activity*` CSS
  (tokens only). `callosum-app.html` rebuilt.

## Key technical detail

- **Additive + reversible by construction (the A4 guarantee).** There is no delete/overwrite/merge/scan agent
  endpoint, and the MCP write client exposes only the four write methods — so an irreversible agent act is
  structurally inexpressible, the same shape as SP1's read-only `CallosumClient`. Revert dispatches per action;
  `save_reference`'s revert soft-deletes **only** a paper the agent *created* (`detail.created`) — a re-found
  existing paper (`created:false`) is left live (dedup-safe). Revert is idempotent (a `reverted_at` row returns
  `{reverted:true}` without re-acting).
- **`save_reference` can't fabricate.** It normalizes the identifier to a DOI, dedups against the library
  (`find_existing_paper_by_identity`), else resolves via `crossref_client.resolve_doi` and **422s an
  unresolvable DOI**. The paper is built from the **resolved** CSL via `_paper_values_from_csl({**csl, "DOI":
  doi}, imported_source="ai-agent")` — building from the resolved record (not a second enrich call) is what keeps
  the `ai-agent` stamp from being overwritten back to `crossref`.
- **`add_manual_assignment` returns a node id, not an assignment-row id**, so axis-revert keys on
  `(axis_id, paper_id)` via `remove_assignment`, not a row delete.
- **GOTCHA (from SP1, still live):** the `mcp` SDK's `FastMCP.call_tool` is shape-inconsistent — a non-dict
  return is `(content, {"result": value})`, a dict return is a bare `list[TextContent]`; the test helper `_call`
  handles both.

## Manual verification script

1. `uvicorn app.backend.api.app:app --port 8888` → open `http://127.0.0.1:8888/`.
2. **Disabled (default):** `curl -s localhost:8888/agent/status` → `{"writes_enabled":false}`;
   `curl -s -XPOST localhost:8888/agent/papers/1/tags -d '{"tag":"x"}' -H 'content-type:application/json'`
   → **403**.
3. Settings (gear) → **AI agent** → turn on *Allow agent writes*. `/agent/status` → `true`.
4. `POST /agent/papers/1/tags {"tag":"from-agent"}` → `{write_id,…}`; `GET /papers/1` shows the tag with
   `source:"ai-agent"`; the AI-agent panel lists the write.
5. Click **Revert** on that row → the tag is gone, the row shows reverted.
6. `POST /agent/axes/<my-pubs-axis>/papers {"paper_id":1}` → **422**; a standard axis → 200.
7. `POST /agent/references {"identifier":"<bad>"}` → **422**; a real DOI → 200 + the paper's
   `imported_source:"ai-agent"`; revert → the created paper is in Trash.
8. For the live agent: configure Claude Desktop/Cursor per `mcp_server/README.md` with writes ON → the four
   write tools appear; with writes OFF → only the five read tools.

Headed driver: `.local/visual/drive_inc216_agent_writes.py` (PASS — toggle on, activity row, Revert removes the
tag + sets `reverted_at`; 0 console/page/genai).

## Pytest

Full suite green. New: `tests/test_agent_writes.py` (the repo round-trip + the gated endpoints + revert dispatch
+ My-Pubs refusal + DOI-verify + dedup-safe revert); `tests/test_settings.py` (+ the toggle round-trip);
`tests/test_mcp_server.py` (+ the write-tools-only-when-enabled / add_tag mapping / write-tools-only-hit-`/agent/`
/ the `/agent/status` read in the allowlist). Migration head asserted via `alembic_head()`.
