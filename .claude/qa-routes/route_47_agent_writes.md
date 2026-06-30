<!-- qa-coverage
api: /agent/status, /agent/papers/{paper_id}/tags, /agent/axes/{axis_id}/papers, /agent/references, /agent/papers/{paper_id}/notes, /agent/writes, /agent/writes/{write_id}/revert
fe:
-->

# ROUTE 47 - Gated MCP agent writes (B1 SP2)

**Tier:** 1 local-stateful
**Goal:** Exhaust the `/agent/*` write surface and its safety boundaries — the opt-in gate, additive-only +
reversible writes, `ai-agent` provenance, the audit log + revert, the My-Publications refusal, and the
DOI-verified `save_reference`. The live MCP↔host round-trip is the maintainer's MANUAL check (configure Claude
Desktop/Cursor per `mcp_server/README.md`); this route verifies everything callosum enforces. The Settings →
"AI agent" toggle + activity/revert view live in `35_settings.jsx` (covered by route_35).

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** Agent writes are **off** by default. For
the write/revert steps, enable them via `PUT /settings {agent_writes_enabled:true}` (the test analogue of the
Settings toggle). Register console/pageerror/request listeners if any page is opened.

## Standing assertions

- **Default-OFF opt-in (the core SP2 promise).** On a clean instance `GET /agent/status` →
  `{writes_enabled:false}`, and **every** write endpoint returns **403** until the user enables agent writes.
  A write succeeding while disabled is **Critical**.
- **Additive + reversible only.** The only write actions are tag / add-to-axis / save-reference / note — there is
  **no** delete/overwrite/merge/scan agent endpoint. Every write is recorded in `agent_writes` and undoable via
  `POST /agent/writes/{id}/revert`. A destructive or non-revertible agent capability is **Critical**.
- **Provenance is visible.** An agent tag carries `source:"ai-agent"` (in `GET /papers/{id}.tags`); an
  agent-saved paper has `imported_source:"ai-agent"`. Agent-origin must never be indistinguishable from the
  user's own work.
- **Authorship is the user's, never an agent's.** `POST /agent/axes/{id}/papers` to a `kind="my_publications"`
  axis is refused (**422**). An agent asserting authorship is **High**.
- **Grounded saves, no fabrication.** `POST /agent/references` resolves the DOI (Crossref) and saves the **real**
  record metadata-only; an unresolvable identifier is refused (**422**); no PDF is fetched (the OA-acquire lane is
  untouched — no paywall circumvention). A fabricated/unverified paper entering the library is **High**.
- **Dedup-safe revert.** Reverting a `save_reference` that merely *re-found* an existing paper (`created:false`)
  must **not** trash that paper; only a paper the agent *created* (`created:true`) is soft-deleted on revert.
- **No egress on a local write.** With egress unset, an agent write/revert must make **no** request to a
  `generativelanguage`/genai host (these are local library mutations). Any such request is **Critical**.

## Steps

1. `GET /agent/status` on a clean instance → `{writes_enabled:false}`; `POST /agent/papers/{id}/tags` → **403**.
2. `PUT /settings {agent_writes_enabled:true}`; `GET /agent/status` → `{writes_enabled:true}`.
3. `POST /agent/papers/{id}/tags {tag:"from-agent"}` → 200 + a `write_id`; `GET /papers/{id}.tags` shows the tag
   with `source:"ai-agent"`; `GET /agent/writes` lists the write (action `tag`, not reverted).
4. `POST /agent/axes/{standard_axis_id}/papers {paper_id}` → 200; against a `my_publications` axis → **422**.
5. `POST /agent/references {identifier:"<unresolvable>"}` → **422** (with a fake/empty Crossref); a resolvable DOI
   → 200 `created:true` + the paper's `imported_source:"ai-agent"`.
6. `POST /agent/writes/{id}/revert` → `{reverted:true}`; the effect is undone (tag gone / member removed / created
   paper trashed); reverting again → still `{reverted:true}` (idempotent). A re-found reference's revert leaves the
   paper live.

## Pass criteria

- All `/agent/*` writes gate on the opt-in (403 off, 200 on); provenance stamped; My-Pubs refused;
  save_reference verified; revert undoes + is idempotent + dedup-safe.
- 0 console/page errors and 0 genai-host requests across any opened page.
