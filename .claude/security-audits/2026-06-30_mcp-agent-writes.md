# Security audit — gated MCP agent writes (B1 SP2, inc 216)

**Date:** 2026-06-30
**Feature:** `/agent/*` write endpoints (tag / add-to-axis / save-reference / annotate) + an audit log + revert, an
opt-in (`agent_writes_enabled`, default OFF), and the four MCP write tools that call them. Spec:
`.claude/docs/specs/2026-06-30-mcp-agent-writes-design.md`.

**Audit gate triggers:** (1) new API endpoints (`/agent/*` — 7); (2) a new file-write/DB-write path (the first writes
the MCP server can drive); (5) a net-new feature spanning 3+ files; (a request-schema change). No new external fetch
*type* (save_reference reuses the already-audited Crossref client), no new dependency on the **app** side (the `mcp`
SDK was added + audited in inc 213; the write methods are new client code in the same package).

---

## Threat review

### Authorization / opt-in gate (the core control)

- **Default OFF.** `app_settings.stored_agent_writes()` returns `False` unless the user explicitly enabled it in
  Settings → AI agent, and **also** honors a kill switch: `CALLOSUM_DISABLE_AGENT_WRITES=1` forces it off regardless
  of the stored flag (mirrors the inc-168 `CALLOSUM_DISABLE_REMOTE_ACCESS` recovery hatch).
- **Every write gates on it.** `_require_writes` is a FastAPI `dependencies=[…]` on all four write endpoints **and**
  the revert endpoint → **403** when disabled, *before* any DB mutation. `GET /agent/status` + `GET /agent/writes`
  are reads and are not gated (they expose only whether writes are on + the agent's own audit log).
- **Verified negative path:** `test_write_endpoints_403_when_disabled` drives every write endpoint on a clean
  instance (writes OFF) and asserts 403 + that no row was written. The MCP layer mirrors this structurally —
  `create_server` calls `client.agent_status()` at build and registers the write tools **only** when it returns
  `True` (`test_write_tools_registered_only_when_enabled`); a host that connected while writes were on and then the
  user disabled them still hits the 403 at the endpoint (the gate is server-side, not just tool-advertisement).

### Additive + reversible by construction (the A4 guarantee)

- **No destructive endpoint exists.** The router exposes only add-tag / add-to-axis / save-reference / annotate +
  revert. There is no delete/overwrite/merge/scan/purge agent route — delete/merge/scan stay human-only, the same
  structural guarantee as SP1's read-only `CallosumClient`. The MCP write client (`mcp_server/client.py`) likewise
  exposes only `add_tag`/`add_to_axis`/`save_reference`/`annotate` (+ `agent_status`); `test_write_tools_only_hit_agent_paths`
  asserts every write tool issues only `/agent/*` requests.
- **Every write is recorded + revertible.** `record_agent_write` writes an `agent_writes` row (action, target paper,
  tool, detail JSON, `created_at`); `POST /agent/writes/{id}/revert` dispatches per action: tag→`remove_tag_from_paper`,
  axis→`remove_assignment`, reference→`soft_delete_paper` **only if the agent created the paper** (`detail.created`;
  a re-found existing paper is left live), note→`delete_note`. Revert is **idempotent** (a `reverted_at` row returns
  `{reverted:true}` without re-acting) and stamps `reverted_at`. `save_reference`'s revert is **dedup-safe** — proven
  by `test_revert_save_reference_dedup_safe` (reverting a `created:false` reference does not trash the paper).
- The agent never performs the irreversible act: even `save_reference` soft-deletes (Trash, restorable) on revert,
  never a hard purge.

### Provenance (no agent edit masquerades as the user's)

- Tags created by the agent carry `import_source="ai-agent"` (`AI_AGENT_SOURCE`); agent-saved papers carry
  `imported_source="ai-agent"`; agent notes carry `import_source="ai-agent"`. `ai-agent` is **not** in
  `_can_update_from_crossref`'s allowlist (it's an allowlist of `pdf-scaffold`/`crossref`/`crossref-unresolved`/None),
  so a later batch enrich will not silently overwrite an agent-saved record — the same protection user-edited papers
  get. `test_agent_tag_carries_ai_agent_source` + `test_save_reference_creates_ai_agent_paper` pin the provenance.

### Authorship boundary (A-A veto: no accusation / no authorship claim)

- `POST /agent/axes/{axis_id}/papers` refuses a `kind="my_publications"` axis with **422** — an agent must not assert
  that the user authored a paper. `test_agent_cannot_add_to_my_publications` covers it. (Standard + curated axes are
  fine — they're the user's own organizational lenses.)

### Input validation (rule #4)

- All bodies are typed Pydantic models with bounds: tag `1..200`, note `1..10000`, reference identifier `1..255`,
  axis `paper_id: int`. Out-of-bounds → 422 at the boundary.
- `paper_id`/`axis_id` are path/body ints; a missing paper → 404 (`_paper_or_404`), a missing axis → 404. No
  unsanitized string reaches a filesystem path or a SQL string.
- `save_reference` normalizes the identifier (`strip().lower()`, strips `https://doi.org/`/`doi:` prefixes) and
  **rejects an unresolvable DOI with 422** — the agent cannot fabricate a paper. The DOI is resolved via the existing
  audited `crossref_client.resolve_doi`; the paper is built from the **resolved** CSL (`_paper_values_from_csl` with
  `imported_source="ai-agent"`), so no agent-supplied free text becomes bibliographic metadata.
  `test_save_reference_unresolvable_422` covers the reject path (fake/empty Crossref).

### Injection / SQL (rule #3)

- All DB access is SQLAlchemy Core with bound parameters (`agent_repo` inserts/selects, `tags_repo`, `repository`,
  the `notes` insert via `.values(...)`, the `axes.c.kind` select). No string interpolation into SQL. Table/column
  names are constants from `schema`. `detail_json` is stored as a JSON column (bound), not concatenated.

### Output encoding

- `GET /agent/writes` returns JSON (action, target title, detail, timestamps) consumed by the React Settings pane via
  normal text rendering (no `dangerouslySetInnerHTML`). The target title comes from the DB (`papers.title`), already
  sanitized at ingest.

### SSRF / external calls

- The only outbound call is `save_reference` → `crossref_client.resolve_doi`, which hits the **constant** Crossref
  host with the DOI as a path/param (the inc-49/183 pattern) — no user-supplied URL is fetched, no SSRF surface. No
  PDF is fetched (the OA-acquire lane is untouched → no paywall circumvention).

### Data egress

- The four writes are **local DB mutations** — nothing leaves the machine. `save_reference`'s DOI→Crossref lookup is
  **public-metadata egress** (a DOI string to a public registry), the same posture as discovery/enrichment — **not**
  the Gemini library-text gate (no library text leaves). With egress unset, the route_47 standing assertion is that a
  write/revert makes zero genai-host request; the headed driver confirmed it.

### Secret handling

- No new secret. The MCP write tools reuse the inc-213 `CALLOSUM_MCP_TOKEN` (write-only env → `Authorization: Bearer`,
  never logged/returned). The opt-in flag is a non-secret boolean in `app-settings.json` (same store as the audited
  egress flag), reported by `GET /settings.agent_writes_enabled`.

### Resource caps / abuse

- Field length caps bound input size. Each write is one row + at most one Crossref lookup; no unbounded loop. Under
  **Remote access** (inc 168) the existing bearer-token gate + sliding-window rate limiter already throttle the whole
  surface, including `/agent/*`. (`/agent/*` carries library-mutation capability, so — like the scan/edit routes — it
  must stay off the cloudflared cite-only ingress allowlist; recorded for the pre-hosted-deploy pass.)

### File-path safety

- No path is built from request data; no new file-ingestion path (save_reference is metadata-only).

### Supply chain

- No new dependency on the app side. `mcp>=1.2` (the SDK) was added + fenced in inc 213 (`mcp_server/requirements.txt`,
  dev-side for CI); SP2 only adds methods to the existing `CallosumClient` + tool registrations.

---

## Negative-path checks run

- Writes disabled (clean instance) → every write endpoint 403, no row written. ✓ (`test_write_endpoints_403_when_disabled`)
- `add_to_axis` to a My-Publications axis → 422; to a missing axis → 404. ✓
- `save_reference` with an unresolvable identifier → 422, no paper created. ✓
- Revert of a `created:false` (re-found) reference → paper stays live. ✓
- Revert twice → idempotent `{reverted:true}`, no double-action. ✓
- MCP write tools absent when `agent_status()=false`; present when true; only `/agent/*` paths issued. ✓
- Headed (egress unset): enable → agent tag write → activity row → Revert → tag removed → `reverted_at` set; 0
  console/page errors, 0 genai-host requests. ✓ (`.local/visual/drive_inc216_agent_writes.py`)

---

**Security Audit: PASS.**

Residual / deferred (recorded, not blocking): a per-write host-side confirmation is the MCP **host's** native
tool-call prompt (out of callosum's control by design — the in-the-moment gate); a future agent rate-limit distinct
from the inc-168 limiter is unneeded while writes stay opt-in + reversible + audited; the `/agent/*` ingress exclusion
is folded into the standing pre-hosted-deploy gate.
