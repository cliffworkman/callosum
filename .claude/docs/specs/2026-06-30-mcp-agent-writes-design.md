# MCP agent writes (backlog B1 SP2) — design

**Status:** approved for implementation (brainstorm 2026-06-30).
**Builds on:** B1 SP1 — the read-first MCP server (`.claude/docs/specs/2026-06-30-mcp-server-design.md`, inc 213).
**Scope:** the **write** half — four **additive, reversible, gated** write tools on the existing `mcp_server/`
stdio adapter, so an external agent can *organize* the library (and add verified references) **through callosum**,
under the user's explicit control. One cohesive sub-project (no decomposition).

## Goal

Let an agent **add a tag**, **add a paper to an axis**, **save a (verified) reference**, and **annotate a paper**
— while the user owns every change: opt-in (default-off), additive-only, provenance-stamped, fully reversible, and
visible in a callosum **"AI agent activity"** review surface with one-click revert. SP2 deliberately exposes **no
destructive tool** (no delete / overwrite / merge) — those stay human-only.

## Values gate (heavy pass — A4 is the spine; the user flagged this)

- **A4 — the user owns every irreversible act; data is never silently overwritten.** Honored structurally, not by
  convention: (1) every SP2 tool is **additive + reversible** (a tag link, an axis membership, a metadata-only
  paper, a note — each trivially undone), so no *irreversible* act is exposed; (2) **opt-in, default-off**; (3)
  every write is **provenance-stamped `ai-agent`** (visible, filterable, and kept out of the enrich-clobber path);
  (4) an **audit log + one-click revert** lets the user see and undo anything the agent did. The destructive acts
  A4 most protects (delete/purge/overwrite) are simply **not in the write client** — the same structural guarantee
  as SP1's read-only allowlist.
- **A1 — the human is the filter / the AI is the funnel.** The agent *organizes + proposes*; the user reviews and
  reverts. The agent never auto-judges what belongs (it adds to an axis the user named; it never scores/ranks).
- **A2 — every claim carries its evidence; facts ≠ candidates.** `save_reference` is **grounded**: callosum
  resolves the identifier (Crossref) and saves the **real** record — it refuses to mint a hallucinated paper.
- **A5 — defaults are the user's; opt-in; local; swappable.** Default-off; a local Settings toggle; the writes go
  to loopback callosum; no new egress channel.
- **Veto-level (no accusation of individuals).** No agent tool judges a person. **My-Publications axes are
  off-limits to the agent** — authorship is the user's to assert, never an agent's.
- **Drift typology → emergent, adopted deliberately:** "the agent as a *user-controlled library contributor*" is a
  posture beyond SP1's read-first. It's adopted with the gate + reversibility + audit that make it A4-safe, not
  drifted into.

## Architecture — consistent with SP1; writes isolated behind `/agent/*`

SP2 extends `mcp_server/` with four write tools, each making **one HTTP call** via the injectable httpx client —
but writes flow through **new dedicated endpoints** in a new **`app/backend/api/routers/agent.py`**, NOT the
human-facing routes. That isolates the agent-write concern — the **opt-in gate**, the **`ai-agent` provenance
stamp**, the **audit-log write**, and the **revert hooks** — in one place, and leaves SP1's read tools untouched.

- **The MCP server advertises the write tools only when agent-writes are enabled** (checked once at startup via a
  new `GET /agent/status`; if callosum is unreachable at startup, it degrades to read-only — no write tools). The
  endpoints **enforce the gate in real time** regardless (403 when off) — so a flag flipped off mid-session
  fails closed even though the tool is still advertised.
- `CallosumClient` gains four **write methods** used only by the write tools; the SP1 read methods + their
  read-only-allowlist test are unchanged. A new test asserts the write tools only ever hit `/agent/*`.

## The four write tools → `/agent/*` endpoints

1. **`add_tag(paper_id, tag)`** → `POST /agent/papers/{paper_id}/tags` → `add_tag_to_paper(import_source="ai-agent")`
   (`tags_repo`, inc 73/100 — get-or-create + idempotent link). Audit + return the tag.
2. **`add_to_axis(paper_id, axis_id)`** → `POST /agent/axes/{axis_id}/papers` → `add_manual_assignment`
   (`axis_assignments`, the inc-50 manual override; `confidence IS NULL`). **My-Publications axes → 422**
   (authorship is not an agent's to assert). Audit.
3. **`save_reference(identifier)`** → `POST /agent/references` → resolve the DOI/PMID/arXiv id via the existing
   Crossref path; **dedup** via `find_existing_paper_by_identity` (already in library → return that id with
   `created:false`); else `create_paper` **metadata-only** + enrich, `imported_source="ai-agent"` (`created:true`).
   **Unresolvable → 422** (no fabrication). **No PDF** (the OA-acquire lane is untouched — no paywall circumvention).
   An audit row is recorded either way (carrying `created`); revert soft-deletes **only when `created:true`** (a
   re-found paper is left alone — revert is a no-op for it).
4. **`annotate(paper_id, text)`** → `POST /agent/papers/{paper_id}/notes` → a **paper-level note** (the `notes`
   table: `body` + `import_source="ai-agent"`; **no PDF-highlight geometry** — an agent has no pixel coordinates,
   and a note is not a coordinate claim, so the coordinate-honesty contract is not in play). A page reference, if
   any, lives in the note text. Audit.

## Opt-in (default OFF)

A new `app_settings` flag **`agent_writes_enabled`** (default false) — mirrors the inc-168 Remote-access pattern:
`set_agent_writes_enabled` / `stored_agent_writes` (force-off via **`CALLOSUM_DISABLE_AGENT_WRITES=1`**). A
**Settings → "AI agent" section** toggles it (and hosts the activity/revert view, below). `/agent/*` write
endpoints return **403** when off. **Single global toggle** (not per-capability) — proportionate since every write
is reversible + audited; per-capability is a possible later refinement. Under Remote access (inc 168) the bearer
token still gates every request; agent writes do **not** require Remote access (they reach loopback callosum
directly when it's off).

## Provenance + the don't-clobber guard

New constant **`AI_AGENT_SOURCE = "ai-agent"`** (`metadata/enrichment.py`), added to the set
`_can_update_from_crossref` **excludes** (alongside `user-edited`/`merged`) — so a later batch enrich never
clobbers an agent-saved paper. Agent tags carry `import_source="ai-agent"`; the inc-100 tag-source styling already
renders them visibly distinct. Net: agent-origin is always **visible** and **filterable**.

## Audit log + one-click revert (the A4 spine)

- **New `agent_writes` table** (migration; additive + guarded + no-op downgrade, the 0021 pattern):
  `id, created_at, action` (`tag`|`axis`|`reference`|`note`), `target_paper_id`, `detail_json` (the args + the
  created/affected ids — everything needed to undo), `reverted_at` (nullable). New `persistence/agent_repo.py`
  (`record_agent_write` / `list_agent_writes` / `mark_reverted`). Re-exported via `schema_findings.py`'s shared
  metadata (the inc-137 pattern), so `metadata.create_all` builds it on fresh DBs.
- **`POST /agent/writes/{id}/revert`** dispatches by action: `tag`→remove the link (+ orphan prune); `axis`→remove
  the manual assignment; `reference`→**soft-delete only if `detail_json.created` is true** (dedup-safe — never
  trash a paper the agent merely re-found); `note`→delete the row. **Idempotent** (already-reverted → no-op); the
  revert is itself recorded (`reverted_at`).
- **Review surface:** **Settings → "AI agent activity"** lists recent agent writes (action · paper title · when ·
  the args/evidence) with a **Revert** button per row + a **"Revert all since…"**. This is where the user *sees*
  and *owns* every agent change. `GET /agent/writes` backs it.

## Safety posture (in code)

- **Additive + reversible by construction** — no destructive method exists in the write client; the `/agent/*`
  routes only add/annotate/save-verified. Delete/overwrite/merge/scan are unreachable to the agent.
- **Opt-in + default-off + fail-closed** (403 when disabled; degrade-to-read-only when callosum is unreachable at
  the server's startup).
- **Grounded** — `save_reference` saves only a Crossref-resolvable record; bounded inputs (identifier/tag/text
  length caps, rule #4); bound-param SQL (rule #3).
- **No new egress vector** — writes go to loopback callosum (or, under Remote access, the same audited tunnel +
  token as SP1). `save_reference`'s resolve uses the **existing, already-audited** Crossref path (constant host →
  no SSRF). No PDF retrieval.
- **Visible + auditable + revertible** — provenance stamp + the `agent_writes` log + the revert surface.

## Dependency

**None new** — reuses the `mcp` SDK + httpx (already fenced in `mcp_server/requirements.txt`) and callosum's
existing service functions (`add_tag_to_paper`, `add_manual_assignment`, the Crossref resolve, `create_note`-style
insert). One new migration (the audit table).

## Testing & verification

- **MCP hermetic tests** (`tests/test_mcp_server.py`, httpx.MockTransport): each write tool maps to its `/agent/*`
  call + args; the gate (a 403 → a clear "enable agent writes in callosum Settings" tool error, not a crash);
  `save_reference` surfaces a 422 cleanly; **the SP1 read-only allowlist still holds**, and the write tools only
  ever issue calls to `/agent/*`.
- **Backend tests** (`tests/test_agent_writes.py`, TestClient against the real app): the opt-in gate (403 off →
  200 on); the `ai-agent` provenance stamp on tag/paper; an `agent_writes` row per write; **revert per action +
  idempotent + dedup-safe** (a save that re-found an existing paper does not trash it on revert); **My-Pubs axis
  refused**; `save_reference` rejects an unresolvable id (injected fake Crossref).
- **The live MCP↔host write round-trip is the maintainer's manual check** (enable the toggle → ask the agent to
  tag/annotate a paper → see it in the library + the Agent-activity view → revert it). The contracts + gate +
  revert are pytest-proven; the Settings toggle + revert UI are headed-verified (no egress).

## Gates / acceptance

- **Security audit** `.claude/security-audits/2026-06-30_mcp-agent-writes.md`: default-off opt-in; additive-only
  (no destructive tool); provenance + don't-clobber; the audit log + revert (only-undo-what-it-created);
  `save_reference` verification (no fabrication; resolve via the existing Crossref path → no SSRF); bounded inputs;
  the bearer token under Remote access. → PASS.
- **Principles/A-A:** the heavy pass above (A4/A1/A2/A5 + the no-accusation veto + My-Pubs off-limits; emergent
  value adopted deliberately).
- **Migration:** the `agent_writes` table (head via `alembic_head()`).
- **QA (rule #10):** the new `/agent/*` endpoints (`status`, the four writes, `writes` list, `writes/{id}/revert`)
  + the Settings "AI agent" toggle + activity view are end-user surfaces → a new `route_NN_agent_writes.md`
  (the API hard-gate) asserting the honesty invariants (opt-in default-off; additive/reversible; provenance;
  My-Pubs refused). Surface map → 0 uncovered.
- **Help corpus:** an "Letting an agent edit your library (MCP writes)" note + the opt-in/review/revert flow
  (`HELP-DOCS-SYNCED`).
- **Acceptance:** with the toggle on, an agent can tag / add-to-axis / save-a-verified-reference / annotate, each
  stamped `ai-agent`, logged, and one-click-revertible in Settings; with the toggle off, every write 403s and the
  tools aren't advertised; an unresolvable `save_reference` is refused; a My-Pubs-axis add is refused; nothing
  destructive is possible; the SP1 read tools + read-only allowlist are unchanged.

## Key code anchors

- SP1 to extend: `mcp_server/{client.py, server.py, __main__.py}`, `tests/test_mcp_server.py` (the
  read-only-allowlist + registry tests).
- Write services to reuse: `tags_repo.add_tag_to_paper` (`:93`, `import_source=`), `axis_assignments.add_manual_assignment`
  (`:32`), `repository.find_existing_paper_by_identity` (`:432`, dedup), `discovery.search.save_item` (`:52`,
  the metadata-only dedup-aware save pattern) + the Crossref resolve (`metadata/enrichment`,
  `import_missing_work` `clustering/my_publications.py:500` as the resolve-and-create reference), `notes` table
  (`schema.py:184` — `body` + `import_source`).
- Provenance: constants `metadata/enrichment.py:17-30`; the don't-clobber guard `_can_update_from_crossref`
  (`enrichment.py:171`).
- Opt-in pattern to mirror: `app_settings.set_remote_access_enabled` / `stored_remote_access` (`:310-321`) +
  `CALLOSUM_DISABLE_REMOTE_ACCESS`; the Settings router + `35_settings.jsx` Remote-access section (inc 168).
- Audit-table home: `persistence/schema_findings.py` (shared metadata, inc 137) + a new `agent_repo.py`.
