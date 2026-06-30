# Changes

Running human-readable log of non-trivial changes (newest first). The increment notes
are the design diary; this is the chronological "what & why" record.

> **Help-doc sync markers:** a `<!-- HELP-DOCS-SYNCED … -->` line marks where the served help corpus
> (`app/backend/help/help_content.md`) was last brought current. Because this log is newest-first, **every
> entry _above_ the topmost marker is a change made since the last help sync** — the set to review when
> deciding whether the help docs need updating (see CLAUDE.md Session kickoff). When an increment updates
> the corpus, it moves the marker forward to the top of its entry (replacing the prior one).

## 2026-06-30 — Increment 218: metadata enrichment SP2 — Europe PMC + PubMed sources
<!-- HELP-DOCS-SYNCED 2026-06-30 inc 218 — the gap-fill-enrichment section's source list is now present-tense (Crossref, OpenAlex, Europe PMC, PubMed) -->
- **Files:** `integrations/europepmc/adapter.py` (+`lookup_metadata` + `_csl_from_record`), `app/backend/metadata/enrich_sources.py` (+`EuropePmcEnrichSource` + `PubMedEnrichSource` + `_title_overlap`; register both → 4-source default), `app/backend/api/app.py` (+`enrich_registry` seam), `app/backend/api/routers/library.py` + `routers/papers.py` (use `app.state.enrich_registry` if set), `tests/test_metadata_multi_enrich.py` (+3, endpoint tests → stub registry), `.claude/security-audits/2026-06-30_metadata-enrich.md` (addendum), help corpus, CLAUDE, `INCREMENT-218-NOTES.md`.
- **What:** two more enrichment sources — **Europe PMC** (DOI/PMID → its cached `resultType=core` record, reusing the OA resolver's fetch) + **PubMed** (PMID → efetch abstract; else title-search → matched record + abstract, conservative title match) — each one `register()` + a mapper. Mainly add abstract coverage when Crossref/OpenAlex leave it blank. Default cascade is now `crossref → openalex → europepmc → pubmed`.
- **Why:** completes the maintainer's chosen v1 source set (Eileen's "fields consistently included"); purely additive to the SP1 cascade.
- **Gates:** **no new endpoint/host/dependency/migration** (reuses audited adapters/hosts). Audit **addendum PASS** (same posture — public-metadata egress not the Gemini gate; SSRF-safe constant hosts + bound params; PubMed title-match guard + regex-not-XML abstract parse; fail-closed; gap-fill non-destructive). **Principles non-triggering.** QA surface unchanged **155/155 API + 697/697 FE, 0 uncovered** (sources behind the existing endpoints). pytest **+3** (14 in `test_metadata_multi_enrich.py`: EPMC mapper, PubMed PMID/title-adopt/title-reject, the 4-source registry; endpoint tests repointed to a stub `enrich_registry` for hermeticity now the default cascade has live EPMC/PubMed clients). The live run over the real library is the maintainer's spot-check. **This completes the multi-pass enrichment feature (SP1 inc 217 + SP2 inc 218).**
- **Revert:** `git revert` the inc-218 commit (no schema change).

## 2026-06-30 — Increment 217: multi-pass, gap-filling metadata enrichment (SP1)
<!-- inc 217 help marker (superseded by inc 218 above) — added the "Filling in missing metadata (gap-fill enrichment)" section -->
- **Files:** `app/backend/metadata/enrich_sources.py` (NEW — `EnrichRef`/`EnrichmentSource`/`EnrichmentRegistry` + Crossref/OpenAlex sources + `build_default_enrich_registry`), `app/backend/metadata/enrichment.py` (+`enrich_paper_metadata_multi` + `gap_merge`/`_gap_fill_columns`/`MultiEnrichResult` + DOI-recovery helpers), `app/backend/metadata/__init__.py` (re-export), `integrations/openalex/adapter.py` (+`fetch_work_csl` + `_csl_from_work`/`_reconstruct_abstract`/`_OA_TYPE_TO_CSL`), `app/backend/api/routers/library.py` (+`POST/GET /library/enrich/refresh` + worker), `app/backend/api/routers/papers.py` (+`POST /papers/{id}/fill-metadata`), `app/backend/api/app.py` (`metadata_enrich_jobs` + `enrich_search_provider` seam), `app/frontend/js/10b_libmenus.jsx` (+`EnrichMetadataButton`) + `10_pdf_layer.jsx` + `40_app.jsx` (`onEnriched`; folded back under the 600 cap) + `25_detail.jsx` (+Fill-missing-fields) + `styles.css` (`.detail-fill`) + `callosum-app.html`; `tests/test_metadata_multi_enrich.py` (NEW), `.claude/qa-routes/route_48_metadata_enrich.md` (NEW), `.claude/security-audits/2026-06-30_metadata-enrich.md`, help corpus, CLAUDE, `INCREMENT-217-NOTES.md`.
- **What:** a multi-source, **gap-filling** enricher — recover a missing DOI (PDF scan → Crossref title-search, conservative match), then fill **only the empty fields** from a source cascade (Crossref-by-DOI → OpenAlex), **never overwriting a value the user typed** and **never downgrading** a hand-edited/merged/agent record's provenance. Shipped as a per-paper **Fill missing fields** (Details) + a library-wide **Enrich metadata ↻** async batch (progress + a recovered/filled/still-missing summary).
- **Why:** Eileen's beta feedback — metadata "fails to populate in full"; the old enrichment was Crossref-only + wholesale-overwrite. Gap-fill is the honest, non-destructive answer + the "run across the whole library" ask.
- **Gates:** **no migration, no new dependency** (reuses existing clients). Audit `2026-06-30_metadata-enrich.md` **PASS** (public-metadata egress not the Gemini gate; SSRF-safe constant hosts; gap-fill non-destructive; wrong-DOI + duplicate-DOI guards; fail-closed). **Principles non-triggering / strengthening** (bibliographic facts; gap-fill is *more* honest than overwrite). QA surface **155/155 API + 697/697 FE, 0 uncovered** (`route_48`). Rule-#1: `40_app.jsx` folded back to **598**; engine in new `enrich_sources.py` (122) + `enrichment.py` (380). Headed-verified (`.local/visual/drive_inc217_enrich.py`). **SP2 (inc 218): Europe PMC + PubMed sources** (each one `register()` + a mapper). The live Crossref/OpenAlex run over the real library is the maintainer's spot-check.
- **Revert:** `git revert` the inc-217 commit (no schema change).

## 2026-06-30 — Increment 216: gated MCP agent writes (B1 SP2)
<!-- inc 216 help marker (superseded by inc 217 above) — "Using Callosum from an AI agent (MCP)" covers the opt-in write tools -->
- **Files:** `app/backend/app_settings.py` (+`set_agent_writes_enabled`/`stored_agent_writes` + `CALLOSUM_DISABLE_AGENT_WRITES` kill switch), `app/backend/api/routers/settings.py` (+`agent_writes_enabled` on GET/PUT), `app/backend/persistence/schema_findings.py` (+`agent_writes` table) + `schema.py` (re-export) + `alembic/versions/0029_agent_writes.py` (guarded additive, no-op downgrade), `app/backend/persistence/agent_repo.py` (NEW — record/list/get/mark-reverted + delete_note), `app/backend/metadata/enrichment.py` (+`AI_AGENT_SOURCE`), `app/backend/api/routers/agent.py` (NEW — 7 `/agent/*` endpoints) + `app/backend/api/app.py` (include), `mcp_server/client.py` (+`agent_status`/`add_tag`/`add_to_axis`/`save_reference`/`annotate`) + `mcp_server/server.py` (register write tools only when enabled), `app/frontend/js/35_settings.jsx` (+`AgentSettings`) + `styles.css` (`.agent-activity*`) + `callosum-app.html` (rebuilt); `tests/test_settings.py` + `tests/test_agent_writes.py` (NEW) + `tests/test_mcp_server.py`; `.claude/qa-routes/route_47_agent_writes.md` (NEW), `.claude/security-audits/2026-06-30_mcp-agent-writes.md`, `mcp_server/README.md`, help corpus, CLAUDE, `INCREMENT-216-NOTES.md`.
- **What:** let an MCP agent **add a tag / add a paper to an axis / save a reference by DOI / add a note** — each gated behind an opt-in (`agent_writes_enabled`, **default OFF** → 403), stamped `imported_source="ai-agent"`, recorded in `agent_writes`, and **reversible** from Settings → AI agent (per-row + Revert-all). No destructive agent route exists (delete/merge/scan stay human-only); My-Publications axes are refused (422); `save_reference` resolves the DOI against Crossref and **refuses an unresolvable identifier** (no fabrication); revert is idempotent + dedup-safe.
- **Why:** B1 SP2 — the maintainer chose the **review+revert-after** model (writes apply immediately but are additive/reversible/audited; the host's per-call prompt is the in-the-moment gate) and **DOI-verified** save_reference. The A4 value ("the user owns every irreversible act") is honored structurally: nothing the agent does is irreversible.
- **Gates:** **migration 0029** (head via `alembic_head()`); audit `2026-06-30_mcp-agent-writes.md` **PASS** (default-off gate; additive+reversible by construction; ai-agent provenance; authorship boundary; bound-param SQL; DOI-verified, no SSRF; no library-text egress; no new app dependency). New QA route `route_47_agent_writes.md` → surface **152/152 API + 693/693 FE, 0 uncovered**. **Principles** non-triggering at code level (no new claim/signal); the **A4/A-A** pass ran in the spec. Headed-verified (`.local/visual/drive_inc216_agent_writes.py` — enable → agent tag write → activity row → Revert → tag removed + `reverted_at` set; 0 console/page/genai). The live MCP↔host write round-trip is the maintainer's manual check.
- **Revert:** `git revert` the inc-216 commit, then `alembic downgrade -1` (the `agent_writes` table drop is guarded).

## 2026-06-30 — Increment 215: PDF highlight minimap (the last close-out dreg)
- **Files:** `app/frontend/js/30_viewer.jsx` (a `MinimapTrack` component + the render hook) + `styles.css`
  (`.pdf-minimap` / `.pdf-minimap-tick`, tokens only) + `callosum-app.html` (rebuilt); `.claude/DESIGN.md`,
  `.claude/qa-routes/route_32_viewer_annotations.md`, CLAUDE, `INCREMENT-215-NOTES.md`.
- **What:** a thin gutter beside the page-scroller with one tick per highlight, positioned by **page fraction**
  (not pixel offset → never touches the inc-34/35 render core), tinted by the highlight's color; clicking a tick
  jumps to + flashes it. Shown only when the Notes panel is closed (the panel supersedes it).
- **Why:** the maintainer's "mop up the dregs" — the reading-pane minimap (the chosen option). No split was needed
  (`30_viewer.jsx` was 557, not the stale-noted 599/600 → 580 with the minimap).
- **Gates:** **frontend-only** — pytest **748** unchanged (`test_frontend_assembly` in sync); no backend/endpoint/
  migration/egress/dependency/audit; Principles non-triggering (coordinate-honest navigation overlay). QA surface
  **145/145 API + 687/687 FE, 0 uncovered**. Headed-verified (`.local/visual/drive_inc215_minimap.py` — 2 ticks,
  click→jump+flash, hidden while Notes open; 0 console/page/genai). **This empties the autonomous close-out band.**
- **Revert:** `git revert` the inc-215 commit (frontend-only; no schema/endpoint change).

## 2026-06-30 — Increment 214: close-out mop-up — per-file scan progress + first-class extra URLs (+ a forced split)
- **Files:** `app/backend/pdf_processing/library_scan.py` (on_progress → `(current,total,filename)`),
  `app/backend/api/routers/library.py` (the scan/rescan lambdas put the basename in the label),
  `app/backend/metadata/paper_edits.py` (+`extra_urls` field + `_apply_extra_urls` + reserved key),
  `app/backend/api/routers/papers.py` (610→510: extra_urls req/resp field + `_extra_urls_from_csl`; **the
  request-normalisation cluster extracted** → new `app/backend/api/routers/paper_edit_input.py`),
  `app/frontend/js/25_detail.jsx` (a "More URLs" `EditableText`) + `callosum-app.html` (rebuilt);
  `tests/test_library_scan.py`, `tests/test_paper_edits.py`, `tests/test_papers.py`; `INCREMENT-214-NOTES.md`.
- **What:** (#4) scan progress now shows "Reading <file> — X / N" (the basename threads through the existing
  `JobProgress.label`; no frontend change). (#5) a paper records additional URLs beyond the primary CSL `URL`
  (`csl_json["extra_urls"]`, a list; a "More URLs" editable field, one-per-line) — reserved against the generic
  "More" passthrough. The #5 field pushed `papers.py` over the 600-line cap → the request-normalisers were split
  out to `paper_edit_input.py` (rule #1; the inc-91/207 pattern; behavior-preserving).
- **Why:** the maintainer's "mop up the dregs" — clear the last small autonomous close-out items (#4 + #5).
- **Gates:** pytest **748 passed, 1 skipped** (+6); ruff clean; QA surface unchanged (145/145 API + 685/685 FE);
  no migration / endpoint / egress / dependency / audit trigger; Principles non-triggering. Headed-verified
  (`.local/visual/drive_inc214_extra_urls.py` — the More-URLs field persists `extra_urls`; 0 console/page/genai).
- **Revert:** `git revert` the inc-214 commit (re-inlines the normalisers; drops `extra_urls` + the progress filename).

## 2026-06-30 — Google Docs tunnel hostname renamed `callosum` → `callosum-tunnel`.clffwrkmn.net
- **Files:** `adapters/googledocs/{cloudflared-config.yml, cloudflared-config.local.yml [gitignored], Code.gs,
  sidebar.html, README.md, callosum-gdocs.gs [rebuilt via tools/build_gdocs_addon.py]}`, `tools/run_tunnel.py`,
  `.claude/CLAUDE.md` (directory-layout line).
- **What:** the Google Docs cite bridge now serves **`callosum-tunnel.clffwrkmn.net`** (was `callosum.clffwrkmn.net`)
  — a pure hostname rename across config + the add-on default URL + the runbook. The cloudflared **tunnel name**
  stays `callosum` (id `653c4da3…`); only the public hostname changed. Cite-only ingress + the bearer-token gate are
  unchanged (cloudflared `ingress validate` OK on the new host; `/papers`→forward, `/settings`→404).
- **Why:** free up `callosum.clffwrkmn.net` for Cliff's website (a hostname = one origin; the bridge moves to a
  clearly-named subdomain).
- **Not a security change:** the cite-only allowlist (path-based) + token are the controls, both intact; no audit
  trigger. No app code / migration / egress-posture change; pytest unchanged (`test_gdocs_bundle` in sync); node
  tests green.
- **Live steps (Cliff's, in Cloudflare):** `cloudflared tunnel route dns callosum callosum-tunnel.clffwrkmn.net`;
  delete/repoint the old `callosum` CNAME; re-set the add-on's base URL to the new host (or clear it → it now
  defaults there). Restart the tunnel (`python tools/run_tunnel.py`).
- **Revert:** `git revert` this commit + re-run `cloudflared tunnel route dns callosum callosum.clffwrkmn.net`.

<!-- HELP-DOCS-SYNCED 2026-06-30 inc 213 — privacy section: added "Using Callosum from an AI agent (MCP)" -->
## 2026-06-30 — Increment 213: read-first MCP server (backlog B1, SP1)
- **Files (new):** `mcp_server/{__init__,client,server,__main__}.py` + `mcp_server/requirements.txt` +
  `mcp_server/README.md`; `tests/test_mcp_server.py`; `.claude/security-audits/2026-06-30_mcp-server.md`;
  `.claude/docs/specs/2026-06-30-mcp-server-design.md`; `INCREMENT-213-NOTES.md`.
  **(modified):** `requirements-dev.txt` (+`mcp`), `app/backend/help/help_content.md`, CLAUDE,
  `.claude/docs/INCREMENT-BACKLOG.md`.
- **What:** a SEPARATE in-repo deployable (mirrors `sync_server/`) — a Model Context Protocol **stdio** server
  exposing five **read-only** tools (`search_library`/`get_paper`/`full_text_search`/`find_passages`/
  `format_citation`) to an agent host. Each tool makes one HTTP call to the running app via an injectable httpx
  client; read-only by construction (hardcoded read-endpoint allowlist; no write/scan method exists).
- **Why:** B1 SP1 — let agents use the library *through* callosum (provenance + grounding authority), read-first.
- **Gates:** **no app change** → no migration, no new app endpoint, QA surface unchanged (145/145 API + 685/685
  FE); audit `2026-06-30_mcp-server.md` PASS; new dep `mcp` fenced in `mcp_server/requirements.txt` (+ dev for CI).
  pytest +9 (`tests/test_mcp_server.py`, hermetic via httpx.MockTransport); ruff clean. Live MCP↔host handshake is
  the maintainer's manual check. SP2 (gated writes) = a separate spec + heavy A4/A-A pass.
- **Revert:** `git revert` the inc-213 commit + `rm -r mcp_server/` (the app never imports it; nothing else depends).

## 2026-06-30 — Increment 212: A7 SP2 — drag-to-reorder curated members
- **Files:** `app/frontend/js/15_axes.jsx` (↑/↓ → a ⠿ grip + HTML5 drag-source/drop-target rows; `reorderToIndex`
  replaces `reorderPaper`) + `styles.css` (`.axis-grip` + `.axis-member-drag.dragover`) + `callosum-app.html`
  (rebuilt); `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_15_axes.md`,
  CLAUDE, `.claude/docs/INCREMENT-BACKLOG.md`, `INCREMENT-212-NOTES.md`.
- **What:** curated-axis members reorder by **dragging the ⠿ grip** (was per-row ↑/↓). Member-drag uses a distinct
  MIME (`…-axismember`) so it never triggers the A6 card-level drop-to-add; reuses `PUT /axes/{id}/order`.
- **Why:** A7 SP2 — the drag-reorder the spec planned; completes the Curated Axis feature (and the A1–A10 list).
- **Gates:** **frontend-only** — pytest unchanged (733/1 skipped; `test_frontend_assembly` in sync); ruff clean;
  **no backend/endpoint/migration/audit/dependency**; QA surface **145/145 API + 685/685 FE, 0 uncovered**.
  Headed-verified (`.local/visual/drive_inc212_dragreorder.py` — drag Alpha onto Gamma → [Beta,Alpha,Gamma],
  persists across reload, no ↑/↓ remain; 0 console/page/genai). `15_axes.jsx` 562.
- **Revert:** `git revert` the inc-212 commit (frontend-only; no schema/endpoint change).

## 2026-06-30 — Increment 211: A7 SP1 — the Curated Axis primitive
- **Files:** `alembic/versions/0028_cluster_node_paper_position.py` (NEW) + `persistence/schema.py` (the column),
  `clustering/axis_assignments.py` (`CURATED_KIND`/`CREATABLE_KINDS`, `append_member_position`, `set_member_order`,
  `freeze_to_curated`, `revert_to_keyword`, curated short-circuit), `clustering/axis_scoring.py` (`create_axis(kind=)`),
  `persistence/repository.py` (ordered reads), `api/routers/axes.py` (`kind` on create/patch + `PUT /axes/{id}/order`
  + position-append + `ClusterPaperResponse.position`), `discovery/relevance.py` (exclude curated),
  `app/frontend/js/15_axes.jsx` + `styles.css` + `callosum-app.html` (rebuilt), `app/backend/help/help_content.md`,
  `.claude/DESIGN.md`, `.claude/qa-routes/route_15_axes.md`, `tests/test_curated_axis.py` (NEW), `tests/test_axes.py`,
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-211-NOTES.md`; spec `…/specs/2026-06-30-curated-axis-design.md`.
- **What:** a hand-populated, hand-ordered axis (`kind="curated"`) — hidden scoring UI, a 📌 cue, ↑/↓ ordering,
  drag-to-add, and the bidirectional **freeze** (❄) / warned **convert** (↩) switch. Membership stays in
  `cluster_node_papers` (a new `position` column) so synthesis/A6/merge keep working unchanged.
- **Why:** A7 — the bounded "manual container" path the axis model needs, without becoming a folder.
- **Gates:** pytest **733 passed, 1 skipped** (+9); ruff clean; migration head **0028**; QA surface **145/145 API**
  (+1) **+ 689/689 FE, 0 uncovered**; **no audit / no new dependency**. Headed-verified
  (`.local/visual/drive_inc211_curated.py` — freeze drops uncertain + 📌 + neutral badge + no scoring UI; ↓ reorder
  persists; create-by-name; convert restores; 0 console/page/genai). `15_axes.jsx` 551; `40_app.jsx` untouched (599).
- **Revert:** `git revert` the inc-211 commits + `alembic downgrade -1` (no-op; the column drops on a base downgrade).

<!-- HELP-DOCS-SYNCED 2026-06-29 inc 210 — browsing section: a "Citation counts" paragraph (Citations ↻ + Most cited) -->
## 2026-06-29 — Increment 210: A2 — library-wide per-paper citation counts
- **Files:** `alembic/versions/0027_paper_citation_counts.py` (NEW), `persistence/schema_findings.py` +
  `schema.py` (the table + re-export), `integrations/openalex/adapter.py` (`fetch_cited_by_count`),
  `persistence/repository.py` (list projection + `citations_desc` sort + `upsert_citation_count` +
  `list_live_papers_with_doi`), `api/routers/papers.py` (`PaperListItem` fields), `api/routers/citation_counts.py`
  (NEW — async batch) + `app.py` (register before papers), `app/frontend/js/10b_libmenus.jsx`
  (`CitationCountsButton`) + `10_pdf_layer.jsx` (chip + Most-cited option + control) + `40_app.jsx`
  (`onCitationsRefreshed`) + `callosum-app.html` (rebuilt), `app/backend/help/help_content.md`,
  `.claude/qa-routes/route_23_citation_counts.md` (NEW), `.claude/security-audits/2026-06-29_citation-counts.md`
  (NEW), `tests/test_citation_counts.py` (NEW), `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-210-NOTES.md`.
- **What:** every library card can show its OpenAlex cited-by count (verbatim + "as of <date>") via a
  **"Citations ↻"** header refresh, plus an explicit opt-in **Most cited** sort. A displayed fact, attributed —
  never a composite/silent rank; no DOI/record → honest "—" (a real 0 shows "0 cited-by").
- **Why:** A2 — see how often the literature cites each paper, honestly, without a leaderboard.
- **Gates:** pytest **724 passed, 1 skipped** (+5); ruff clean; migration head **0027**; QA surface **144/144 API**
  (+2) **+ 679/679 FE, 0 uncovered**; **audit PASS**; **no new dependency** (reuses the OpenAlex adapter).
  Headed-verified (`.local/visual/drive_inc210_citations.py` — Citations ↻ → 2 chips + "Citations · <date>" →
  Most cited → "99 cited-by" first; unknown job → 404; 0 console/page/genai). `40_app.jsx` stays 599/600.
- **Revert:** `git revert` the inc-210 commit + `alembic downgrade -1` (no-op; the table is dropped by a base downgrade).

## 2026-06-29 — Increment 209: A3 — full-text PDF search (SQLite FTS5)
- **Files:** `alembic/versions/0026_chunks_fts.py` (NEW — external-content FTS5 + sync triggers + backfill),
  `persistence/fulltext_repo.py` (NEW — sanitize + MATCH query), `api/routers/fulltext.py` (NEW — GET /papers/fulltext)
  + `app.py` (register before papers), `app/frontend/js/10c_fulltext.jsx` (NEW — FulltextResults) + `10_pdf_layer.jsx`
  (scope option + swap the list when active) + `styles.css` (`.fulltext-*`/`.ft-mark`) + `callosum-app.html` (rebuilt),
  `app/backend/help/help_content.md`, `.claude/DESIGN.md`, `.claude/qa-routes/route_22_fulltext.md` (NEW),
  `.claude/security-audits/2026-06-29_fulltext-search.md` (NEW), `tests/test_fulltext.py` (NEW),
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-209-NOTES.md`.
- **What:** verbatim search over the extracted PDF chunk text (FTS5 `MATCH`) — the exact-string complement to the
  semantic axes. A **"Full text (PDFs)"** search scope swaps the library list for per-occurrence snippet hits (matched
  terms bolded, page, **Open at page** → region-precision scroll). External-content FTS5 + a sync trigger trio (the
  AFTER DELETE trigger catches the inc-65 FK CASCADE purge). The query is sanitized (token-quoted → no FTS5 syntax
  error/injection) + bound + try/except (never 500). No claim/rank/score (bm25 = internal ordering).
- **Why:** A3 — find an exact phrase inside papers (axes/synthesis remain the meaning surface).
- **Gates:** pytest **719 passed, 1 skipped** (+4); ruff clean; migration head **0026**; QA surface **142/142 API**
  (+1) **+ 677/677 FE, 0 uncovered**; **audit `2026-06-29_fulltext-search.md` PASS**; **no new dependency** (FTS5 is
  core SQLite). Headed-verified (`.local/visual/drive_inc209_fulltext.py` — search → hit p.2 → Open at page; malformed
  `"` → 0 hits no error; 0 console/page/genai). `40_app.jsx` untouched (self-contained component); `10_pdf_layer.jsx` 555.
- **Revert:** `git revert` the inc-209 commit + `alembic downgrade -1` (drops chunks_fts + triggers).

## 2026-06-29 — Increment 208: A1 — saved searches + split the library-header menus → 10b_libmenus.jsx
- **Files:** `alembic/versions/0025_saved_searches.py` (+ `schema.py` saved_searches table), `persistence/saved_search_repo.py`
  (NEW), `api/routers/saved_searches.py` (NEW) + `app.py` (register), `app/frontend/js/10b_libmenus.jsx` (NEW — AddMenu +
  SavedSearchMenu extracted) + `10_pdf_layer.jsx` (split + SavedSearchMenu render) + `40_app.jsx` (gather/apply/save/delete)
  + `styles.css` (`.saved-search-*`) + `callosum-app.html` (rebuilt), `app/backend/help/help_content.md`,
  `.claude/qa-routes/route_21_saved_searches.md` (NEW) + `route_00` (claim 10b), `tests/test_saved_searches.py` (NEW),
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-208-NOTES.md`.
- **What:** a **saved search** persists a named bundle of the existing library facets (q/search_field/item_type/axis/tag/
  needs_review/signal/sort) — recalled from a **Saved ▾** header menu (apply / save current / delete). A `saved_searches`
  table (params a JSON blob, validated by a typed `extra="forbid"` model → unknown key 422). **Distinct from an axis**
  (a semantic lens); it replays the GET /papers filters, computes no claim/score. **Rule-#1 split:** SavedSearchMenu
  pushed `10_pdf_layer.jsx` to 602/600 → both header dropdowns extracted → **10b_libmenus.jsx** (→ 547).
- **Why:** A1 — recall a working view in one click (the metadata-predicate complement to axes/tags).
- **Gates:** pytest **715 passed, 1 skipped** (+1); ruff clean; migration head **0025**; QA surface **141/141 API**
  (+3) **+ 675/675 FE, 0 uncovered**; **no audit** (local table + 3 local endpoints, no egress/fetch/dependency).
  Headed-verified 4/4 (`.local/visual/drive_inc208_saved_search.py` — save → apply restores → delete; 0 console/page/genai).
- **Revert:** `git revert` the inc-208 commit + `alembic downgrade -1` (drops `saved_searches`).

## 2026-06-29 — Increment 207: A5 — color tags (no ratings) + split TagsRow → 25b_tags.jsx
- **Files:** `alembic/versions/0024_tag_color.py` (+ `schema.py` color column), `persistence/tags_repo.py` (TAG_COLORS +
  `set_tag_color` + color in reads), `api/routers/tags.py` (GET /tags/colors + POST /tags/{id}/color + color in models),
  `api/routers/papers.py` (PaperTagRef.color), `app/frontend/js/25b_tags.jsx` (NEW — TagsRow extracted) + `25_detail.jsx`
  (split) + `10_pdf_layer.jsx` (sidebar dot) + `styles.css` (palette + recipes) + `callosum-app.html` (rebuilt),
  `.claude/DESIGN.md`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_20_tags.md`, `tests/test_tags.py` (+1),
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-207-NOTES.md`.
- **What:** tags carry an optional **color** (a fixed 8-key palette, stored as a key not hex; theme-aware via
  `color-mix`). A swatch popover off each chip's color dot (Details) sets/clears it (`POST /tags/{id}/color`, allowlisted
  → 422); colored chips override the inc-100 provenance styling; the sidebar Tags tab shows a color dot. **Ratings were
  declined** (Cliff): a star flattens a paper to one dimension; tags stay orthogonal/inspectable (#7). **Rule-#1 split:**
  the picker pushed `25_detail.jsx` to 609/600 → extracted **TagsRow → 25b_tags.jsx** (→ 522).
- **Why:** A5 organizational polish, charter-aligned (color = a user label, never an AI score).
- **Gates:** pytest **714 passed, 1 skipped** (+1); ruff clean; migration head **0024**; QA surface **138/138 API**
  (+2) **+ 667/667 FE, 0 uncovered**; **no audit** (color column + 2 local endpoints, no egress/fetch/dependency).
  Headed-verified (`.local/visual/drive_inc207_tag_color.py` — pick blue → chip recolors + persists; 0 console/page/genai).
- **Revert:** `git revert` the inc-207 commit + `alembic downgrade -1` (drops `tags.color`).

## 2026-06-29 — Increment 206: A6 — drag-and-drop a library paper onto an axis to add it
- **Files:** `app/frontend/js/10_pdf_layer.jsx` (PaperCard `draggable` + `onDragStart`), `app/frontend/js/15_axes.jsx`
  (AxisItem drop target + `dropPaper` handler), `app/frontend/styles.css` (`.axis.drag-over`) + `callosum-app.html`
  (rebuilt), `.claude/DESIGN.md` (drop-invite recipe), `app/backend/help/help_content.md`, `.claude/qa-routes/route_15_axes.md`,
  `.claude/docs/INCREMENT-BACKLOG.md`, CLAUDE, `INCREMENT-206-NOTES.md`.
- **What:** drag a library card onto a (non-My-Pubs) axis card → a manual override via the existing
  `POST /axes/{id}/papers` (`status:"manual"`); the axis card shows a dashed-accent `.drag-over` invite; the badge
  count + open card refresh. The drag payload rides the native `dataTransfer` (custom MIME `application/x-callosum-paper`),
  so it works cross-pane with no React state plumbing. **My-Pubs is not a drop target** (authorship is resolved, ✓/✕).
- **Why:** A6 — a faster input for the existing manual-add path (no focus-mode round-trip).
- **Gates:** pytest **713** (unchanged — frontend-only; the endpoint is already tested, DnD is headed-verified); ruff
  clean; QA surface unchanged (136/136 API + 661/661 FE — handlers ride existing claimed elements); **no backend /
  migration / endpoint / egress / dependency**. Headed-verified (`.local/visual/drive_inc206_drag_axis.py` — drag a
  card onto an axis → badge 0→1; 0 console/page/genai).
- **Revert:** `git revert` the inc-206 commit (removes the drag affordance; the ＋ focus-mode add path is unchanged).

## 2026-06-29 — Increment 205: close A8 (covered) + remove the redundant THEORY → Discover placeholder
- **Files:** `app/frontend/js/09_placeholders.jsx` (drop the 3 Discover `registerPaneTab` blocks) + `callosum-app.html`
  (rebuilt), `tests/test_papers.py` (ruff-format the inc-204 A10 test — CI lint fix), `.claude/docs/INCREMENT-BACKLOG.md`
  (A8 closed-as-covered + A9/A10 marked done + the Discover item), CLAUDE, `INCREMENT-205-NOTES.md`.
- **What:** (1) **A8** — the synthesis scope label is **already covered**: the pre-run scope note ("N selected papers
  …", inc 145) + the inc-153 post-run coverage readout. A literal "uncertain excluded" claim would be **dishonest**
  (synthesis summarizes the *exact* selection regardless of certainty; A10 already enforces the boundary at selection
  time) → closed, not built. (2) **Removed the THEORY → Discover `<ComingSoon>` placeholder** (Cliff's queued request)
  — the real Discover/Search (inc 184) + Feed (inc 188) ship as center-pane library-frame tabs, so the stub was stale
  (inc-163 convention: drop a stub when its feature lands). (3) **Folded in:** ruff-format `tests/test_papers.py` (the
  inc-204 push went red on `ruff format --check` only — the suite was green; the A10 test's insert needed wrapping).
- **Why:** *shown = summarized* honesty (A8) + a clean THEORY accordion (no duplicative placeholder) + green CI.
- **Gates:** pytest **713 passed, 1 skipped** (unchanged); ruff check + format clean; QA surface unchanged (136/136 API
  + 661/661 FE — inert stubs, no route claimed them); **no migration / endpoint / egress / dependency**. Headed-verified
  (`.local/visual/drive_inc205_no_discover.py` — no "Discover" header, METHODS stubs survive; 0 console/page/genai).
- **Revert:** `git revert` the inc-205 commit (restores the Discover placeholder + the unwrapped test line).

## 2026-06-29 — Increment 204: carry "hide uncertain" through to the library-pane axis filter (backlog A10 close-out)
- **Files:** `app/backend/persistence/repository.py` (`axis_hide_uncertain` param + `DEFAULT_AXIS_CUTOFF`),
  `app/backend/api/routers/papers.py` (`GET /papers` query param), `app/frontend/js/15_axes.jsx` + `40_app.jsx` +
  `10_pdf_layer.jsx` (thread the boolean + banner note) + `callosum-app.html` (rebuilt), `tests/test_papers.py` (+1),
  `.claude/qa-routes/route_15_axes.md` (A10 step), `app/backend/help/help_content.md`, CLAUDE, `INCREMENT-204-NOTES.md`.
- **What:** the axis count-badge filter returned **every** axis member even when the card's 👁 hide-uncertain view was
  on, so *select-all → summarize* could include papers the card hid. The badge now carries the card's hide state →
  `GET /papers?axis_id=&axis_hide_uncertain=true` filters to the same assigned (≥ cutoff) + manual (NULL) set the card
  shows; the banner reads "… · assigned only". Cutoff = `axes.scoring_gain` (else 0.35), matching the card's tiering.
- **Why:** *shown == summarized* — the filtered Library must match what the card displays (a straight consistency bug).
- **Gates:** pytest **713 passed, 1 skipped** (+1); ruff clean; QA surface unchanged (136/136 API + 661/661 FE);
  Principles non-triggering (filter-consistency, the inc-66 class); **no migration / endpoint / egress / dependency**.
  Headed-verified (`.local/visual/drive_inc204_hide_uncertain.py`, 0 console/page/genai). Swept 4 stray
  `app/frontend/js/*.tmp.*` orphans.
- **Revert:** `git revert` the inc-204 commit (pure code/CSS; the badge filter reverts to all-members, inc-63 behavior).

## 2026-06-29 — Increment 203: activate the dormant `contradicted` verification status (backlog A9 close-out)
- **Files:** `app/backend/summarization/verification.py` (contradiction read + `_status` contradicted + config),
  `app/frontend/js/20_synthesis.jsx` + `styles.css` (distinct `contradicted` pill) + `callosum-app.html` (rebuilt),
  `.claude/DESIGN.md` (red-on-one-status-pill exception), `app/backend/help/help_content.md` (synthesis status),
  `.claude/qa-routes/route_55_synthesis_verification.md` (assertion), `tests/test_nli_support.py` (+3), CLAUDE,
  `INCREMENT-203-NOTES.md`.
- **What:** the verifier could flag *not-supported* but couldn't surface that a cited source **actively disagrees**.
  Now the NLI softmax's contradiction probability (already computed, previously discarded) yields a `contradicted`
  status when it dominates support — rendered as a distinct red "⚠ source disagrees" pill with its quote/page intact.
  **Signal, not verdict** — never "this claim is false."
- **Why:** the single most consequential citation error a verify-everything tool exists to catch — a completeness gap
  in the existing verification spine (the schema + NLI already supported it).
- **Gates:** pytest **712 passed, 1 skipped** (+3); ruff clean; QA surface unchanged (132/132 + 661/661); Principles
  gate aligned (signal-not-verdict, evidence shown); **no migration / endpoint / egress / dependency**. Swept 2 stray
  `tests/*.tmp.*` orphans.
- **Revert:** `git revert` the inc-203 commit (pure code/CSS; `contradicted` reverts to the amber "flagged" lump).

## 2026-06-29 — Increment 202: accounts SP3b — the reference sync-server + client transport + opt-in (the egress slice)
- **Files:** new `sync_server/` (`__init__`, `schema`, `auth`, `store`, `app`, `requirements.txt`, `README.md`),
  `app/backend/sync/transport.py` (new), `app/backend/api/routers/sync.py` (new) + wired in `app.py`
  (`include_router` + `create_app(sync_transport=…)`), `app/backend/app_settings.py` (sync config + sealed keyring +
  cursor), `tests/test_sync_server.py` (+9), `tests/test_sync_endpoints.py` (+8), `.claude/qa-routes/route_46_sync.md`
  (new), `.claude/security-audits/2026-06-29_sync-server.md` (PASS), `.claude/docs/specs/2026-06-29-sync-server-design.md`
  (the design), CLAUDE (layout/decision-log/footer), `INCREMENT-202-NOTES.md`.
- **What:** the first path where data leaves the machine — a self-hostable **sync-server** (`sync_server/`, FastAPI +
  Postgres-in-prod / SQLite-in-tests, an OIDC resource server storing **opaque AES-GCM blobs** per user), a client
  **`HttpSyncTransport`** (httpx), and the **opt-in** local `/sync/{status,settings,setup,run}` endpoints that drive
  `run_sync` over the transport. Default-off, E2E (the DEK never leaves), fully gated.
- **Why:** SP3b's server slice (the maintainer's chosen scope: server + transport + opt-in together) — the engine
  (incs 197–201) now has a real backend to sync against.
- **Gates:** pytest **709 passed, 1 skipped** (+17); ruff clean; QA surface **136/136 API + 661/661 FE, 0 uncovered**
  (new `route_46_sync.md`); audit PASS; **no migration; no new dependency in the local app** (server-only deps in
  `sync_server/requirements.txt`). The live deploy + live-Authentik token validation is the maintainer's manual step.
- **Revert:** `git revert` the inc-202 commit (removes `sync_server/` + the transport/router/settings additions; the
  inc-197–201 engine + the local sync tables are untouched).

## 2026-06-29 — Increment 201: accounts SP3b cont. — natural-key identity for tags (cross-device collision fix)
- **Files:** `app/backend/sync/changeset.py` (`SyncableCollection.natural_key`; `_natural_uid` helper;
  `ensure_identities` deterministic uid; tags `natural_key="name"`), `tests/test_sync_engine.py` (+2),
  `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` (addendum 3), CLAUDE (layout/decision-log/footer),
  `INCREMENT-201-NOTES.md`.
- **What:** a tag's `sync_uid` is now **deterministic from its (UNIQUE) name** instead of random — so two devices that
  independently created a same-named tag pick the same uid and **converge** on apply (UPDATE), instead of colliding on
  the `tags.name` UNIQUE constraint (an `IntegrityError` on first sync). The fix lives in `ensure_identities`;
  collect/apply/merge are untouched.
- **Why:** closes the one real correctness gap flagged in inc 200 (the addendum-2 known limitation) — robustness
  before any live sync.
- **Gates:** pytest **692 passed, 1 skipped** (+2); ruff clean; QA surface unchanged; audit addendum 3 PASS; **no
  migration / endpoint / egress / dependency / UI**.
- **Revert:** `git revert` the inc-201 commit (pure code; tags fall back to random uids — the pre-inc-201 behavior).

## 2026-06-29 — Increment 200: accounts SP3b cont. — the link-table model (paper_tags)
- **Files:** `app/backend/sync/changeset.py` (`SyncableCollection.pk` → `str|None`; `_outbound` helper; `SYNCABLE`
  += paper_tags `pk=None`; ensure_identities skips links), `app/backend/sync/engine.py` (`_apply_link`; dispatch;
  guard push-tombstone forget_identity), `tests/test_sync_engine.py` (+1 link test),
  `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` (addendum 2), CLAUDE (layout/decision-log/footer),
  `INCREMENT-200-NOTES.md`.
- **What:** sync the composite-PK link table **paper_tags** (tag assignments). A link has no own id → its identity is
  **derived from its endpoints** (record_id = the joined `paper_uid|tag_uid`, identical on every device); apply
  resolves the endpoints → local ids → INSERT-OR-IGNORE / DELETE. Also recorded `summaries` as **not synced**
  (derived) + manual `cluster_node_papers` as deferred.
- **Why:** completes the engine's user-authored relational coverage (papers · tags · axes · notes · annotations ·
  tag assignments) before the reference sync-server.
- **Gates:** pytest **690 passed, 1 skipped** (+1); ruff clean; QA surface unchanged; audit addendum 2 PASS; **no
  migration / endpoint / egress / UI**. Known limitation: `tags.name` UNIQUE → cross-device same-name-tag collision
  (a pre-existing inc-198 concern; natural-key reconciliation is a follow-on).
- **Revert:** `git revert` the inc-200 commit (pure code; `SYNCABLE` drops paper_tags; link path is additive).

## 2026-06-29 — Increment 199: accounts SP3b cont. — FK-translation layer + the child tables (notes, annotations)
- **Files:** `app/backend/sync/changeset.py` (+`SyncableCollection.fks`/`.drop`; `collect_local` FK-translates +
  drops; `SYNCABLE` += notes/annotations), `app/backend/sync/engine.py` (`_apply_record` FK-translates + skips
  unresolved; apply referenced-first), `tests/test_sync_engine.py` (+1 child-FK test),
  `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` (addendum), CLAUDE (layout/decision-log/footer),
  `INCREMENT-199-NOTES.md`.
- **What:** extend the sync engine to the FK-bearing child tables **notes + annotations** — a row's `paper_id` FK
  travels as the referenced paper's `sync_uid` and is translated back to each device's local id on apply (applied
  referenced-first); `annotations.attachment_id` (a per-device PDF pointer) is dropped from the synced payload.
- **Why:** SP3b cont. — sync the user's notes + highlights (the high-value relational data). The FK-translation layer
  is the generic mechanism the remaining FK tables will reuse.
- **Gates:** pytest **689 passed, 1 skipped** (+1); ruff clean; QA surface unchanged (132/132 API + 661/661 FE, no
  new route); audit addendum PASS; **no migration, no new dependency, no egress, no UI**.
- **Revert:** `git revert` the inc-199 commit (pure code; `SYNCABLE` reverts to papers/tags/axes; `sync_identity`
  rows for notes/annotations are harmless if left).

## 2026-06-29 — Increment 198: accounts SP3b — the client sync engine + `sync_uid` identity (top-level collections)
- **Files:** `app/backend/sync/engine.py` (new), `app/backend/sync/changeset.py` (revised → sync_uid keying),
  `app/backend/persistence/schema_sync.py` (+`sync_identity`) + re-export in `schema.py`,
  `alembic/versions/0023_sync_identity.py` (new), `tests/test_sync_engine.py` (new, +4),
  `tests/test_sync_crypto.py` (the changeset test updated → sync_uid), `.claude/security-audits/2026-06-29_sync-engine-sp3b.md`
  (new), CLAUDE (layout/decision-log/footer), `INCREMENT-198-NOTES.md`.
- **What:** the **client sync engine** (pull → decrypt → merge → apply → push) over an injectable `SyncTransport`
  (a fake in tests; **no live egress** — the reference server is the next slice), keyed on a global **`sync_uid`**
  (UUID, the new `sync_identity` map) so two devices with independent local ids converge. Scope = the top-level,
  FK-free collections (papers, tags, axes); apply is UPDATE-in-place/INSERT-and-bind/DELETE-and-forget by sync_uid,
  conflicts surfaced into `sync_conflicts` (A4), failing closed on a foreign/tampered blob.
- **Why:** SP3b — the maintainer chose "engine first, server next" + "top-level collections first". The cross-device
  identity problem (local int ids aren't global) needed the `sync_uid` layer; the engine proves convergence locally
  before any ciphertext leaves.
- **Gates:** pytest **688 passed, 1 skipped** (+4 engine tests; SP3a changeset test repointed to sync_uid); ruff
  clean; QA surface unchanged (132/132 API + 661/661 FE, no new route); audit PASS; migration 0023 (additive/guarded,
  head via `alembic_head()`); no new dependency (`uuid`/`json`/`cryptography` already present); no egress, no UI.
- **Revert:** `git revert` the inc-198 commit; the 0023 migration is additive (no down-migration; the table is
  local-only + unused without the engine). `sync_identity` is harmless if left.

## 2026-06-29 — Increment 197: accounts SP3a — E2E sync crypto + local change-tracking foundation (no egress)
- **Files:** `app/backend/sync/` (new: `__init__.py`, `crypto.py`, `changeset.py`), `app/backend/persistence/schema_sync.py`
  (new) + re-export in `schema.py`, `alembic/versions/0022_sync.py` (new), `tests/test_sync_crypto.py` (new, +14),
  `.claude/security-audits/2026-06-29_sync-crypto-sp3a.md` (new), `.claude/docs/specs/2026-06-29-accounts-sync-design.md`
  (new, the SP3 design), CLAUDE (layout/decision-log), `INCREMENT-197-NOTES.md`.
- **What:** the local, no-egress foundation for opt-in **E2E-encrypted multi-device sync**: `crypto.py` (random DEK →
  AES-256-GCM records; DEK sealed under a passphrase KEK + a recovery-code KEK via scrypt; fail-closed; no
  server-side reset), `changeset.py` (hash-diff change-tracking + per-record LWW that **surfaces conflicts**, not
  clobbers — A4), `sync_state`/`sync_conflicts` tables (local-only, migration 0022).
- **Why:** SP3 (the invariant-touching feature) — design-first, Principles/A-A gate run (E2E + opt-in honors A5;
  conflict-surfacing honors A4). SP3a is the security-critical core, proven locally before any data leaves (SP3b).
- **Gates:** pytest **684 passed, 1 skipped** (+14); ruff clean; QA surface unchanged (132/132 + 661/661, no new
  route); audit PASS; migration 0022 (additive/guarded); no new dependency (`cryptography` via `PyJWT[crypto]`).
- **Revert:** `git revert` the inc-197 commit; the 0022 migration is additive (no down-migration; tables are
  local-only + unused if reverted).

<!-- HELP-DOCS-SYNCED 2026-06-29 inc 196 -->
## 2026-06-29 — Increment 196: accounts SP2 — more login methods (email/password + Google), method-agnostic
- **Files:** `ops/accounts-authentik-setup.md` (SP2 connectors section), `app/backend/api/auth/oidc.py` +
  `router.py` (email claim; My-Pubs only on ORCID login), `app/backend/app_settings.py` + `routers/settings.py`
  (`account.email`), `app/frontend/js/35_settings.jsx` (+ `callosum-app.html`: "Sign in" + method-agnostic copy),
  `app/backend/help/help_content.md`, `tests/test_auth_oidc.py` (+1), `.claude/security-audits/2026-06-29_orcid-account.md`
  (addendum), `INCREMENT-196-NOTES.md`.
- **What:** add **email/password + Google** sign-in. The methods are **Authentik connectors** (runbook) — callosum is
  unchanged functionally; its refinement is a **method-agnostic "Sign in"** entry, capturing `email` for display, and
  populating My-Pubs **only on an ORCID login** (a Google/email login sets the account identity, leaves My-Pubs alone).
- **Why:** the maintainer asked to get SP2 underway (parking superuser capabilities). Approved single-entry design.
- **Gates:** pytest **670 passed, 1 skipped** (+1); ruff clean; QA surface unchanged (132/132 + 661/661, no new
  route); audit addendum PASS; no migration; headed driver re-verified.
- **Revert:** `git revert` the inc-196 commit; no migration.

## 2026-06-29 — Increment 195: superuser role (verified-ORCID flag) + Authentik standup runbook
- **Files:** `ops/accounts-authentik-setup.md` (new runbook), `app/backend/app_settings.py` (superuser allowlist +
  `is_superuser`), `app/backend/api/routers/settings.py` (`AccountStatus.is_superuser`), `app/frontend/js/35_settings.jsx`
  (+ `callosum-app.html`), `.env` (gitignored: `CALLOSUM_SUPERUSER_ORCIDS`), `tests/test_auth_oidc.py` (+3),
  `.claude/security-audits/2026-06-29_orcid-account.md` (addendum), README + design spec (runbook refs), backlog,
  `INCREMENT-195-NOTES.md`. Also corrected inc-194's "+12"→"+10" test-count references.
- **What:** (A) a maintainer runbook to stand up Authentik + wire ORCID so live sign-in works; (B) a **superuser**
  flag keyed off the **verified ORCID claim** (`CALLOSUM_SUPERUSER_ORCIDS` env allowlist → `account.is_superuser` +
  a "· superuser" indicator). Verified, not self-asserted; env-config, not hardcoded; capabilities deferred.
- **Why:** the maintainer asked to register their ORCID (`0000-0002-2206-0325`) as a superuser + needed a way to
  light up the live ORCID sign-in. Both approved ("both in sequence").
- **Gates:** pytest **669 passed, 1 skipped** (+3); ruff clean; QA surface unchanged (132/132 + 661/661, no new
  route); audit addendum PASS; no migration; headed driver re-verified (no regression).
- **Revert:** `git revert` the inc-195 commit; remove `CALLOSUM_SUPERUSER_ORCIDS` from `.env` (not committed).

## 2026-06-29 — Increment 194: accounts SP1 — optional "Sign in with ORCID" (OIDC, identity-only)
- **Files:** `app/backend/api/auth/` (new: `__init__.py`, `oidc.py`, `router.py`), `app/backend/app_settings.py`
  (OIDC config + flow/session storage), `app/backend/api/access_control.py` (exempt `/oauth/callback`),
  `app/backend/api/routers/settings.py` (`account` status block), `app/backend/api/app.py` (wire + `oidc_client`
  injectable), `app/frontend/js/35_settings.jsx` (Account section) → `callosum-app.html`, `requirements.txt`
  (`PyJWT[crypto]`), `tests/test_auth_oidc.py` (new, +10), `.claude/qa-routes/route_45_account.md` (new),
  `.claude/security-audits/2026-06-29_orcid-account.md`, help corpus + README + CLAUDE + the design spec/eval/notes.
- **What:** an opt-in, default-off, **identity-only** OIDC sign-in (authorization-code + PKCE, loopback redirect,
  JWKS id-token verify) to the callosum account platform (Authentik), which brokers ORCID; a successful sign-in's
  **verified ORCID + name populate My Publications**. Tokens are write-only (never in `GET /settings`); the callback
  is exempt from the inc-168 gate (a navigation); **no library data leaves the machine**.
- **Why:** backlog #15 — the maintainer wants a callosum account created several ways (ORCID/Google/email), with
  ORCID populating My Pubs. Local-first stays the default; the account is additive. SP1 = the de-risked first slice.
- **Gates:** pytest **666 passed, 1 skipped**; ruff clean; QA surface 132/132 API + 661/661 FE, 0 uncovered; audit
  PASS; Principles → A-A consent value. No migration. The live ORCID round-trip is the maintainer's manual check
  (platform standup, host-agnostic); the flow + pure helpers are pytest-covered + the unconfigured UI headed-verified.
- **Revert:** restore the files above from git (`git revert` the inc-194 commit); no migration to undo. The 204
  logout-route bug fix + the superuser ▲ NEXT-UP backlog entry (ORCID `0000-0002-2206-0325`) are part of this.

## 2026-06-29 — Increment 193: Google Docs setup automation — Quick Tunnel + one-file add-on bundle
- **Files:** `tools/run_tunnel.py` (--quick/--port), `tools/build_gdocs_addon.py` (new), `adapters/googledocs/callosum-gdocs.gs`
  (new generated bundle), `adapters/googledocs/README.md` (easiest-setup section), `tests/test_gdocs_bundle.py` (new, +2),
  `.claude/security-audits/2026-06-28_googledocs-tunnel.md` (addendum), `INCREMENT-193-NOTES.md`.
- **What:** cut the Google Docs install from "migrate a domain + paste 3 files" to "run a quick tunnel + paste 1 file."
  `run_tunnel.py --quick` = a zero-setup Cloudflare Quick Tunnel (throwaway URL, no account/domain/config);
  `build_gdocs_addon.py` bundles the 3 Apps Script sources (sidebar inlined) into one paste-able `callosum-gdocs.gs`.
- **Why:** the user flagged the setup as too much for an end user; user-approved scope = both.
- **Gates:** pytest 656 (+2 bundle sync/inline tests); ruff clean; QA surface unchanged (no API/FE surface — tools +
  adapter file); audit addendum PASS (the --quick mode drops cite-only ingress → token-only, opt-in + informed +
  non-default; named cite-only path remains; bundle is not a security change). node --check on the bundle. No app
  code/frontend/migration/dependency change. **The real quick-tunnel + in-Docs round-trip is the user's manual check.**
- **Also (this turn):** pointed the user's gitignored `cloudflared-config.local.yml` cite rule at `localhost:8888`
  (their port; was 8080).
- **Revert:** drop build_gdocs_addon.py + callosum-gdocs.gs + the test, revert the run_tunnel --quick block + README.

<!-- HELP-DOCS-SYNCED: 2026-06-29 (inc 192) — the "Following sources (Feed)" section now covers all four source types + the Auto-refresh-on-open toggle; covers inc 191/190/189/188 (Feed) + 186 (PubMed in Discover) + 184/185 + the inc 175–179 reading-pane catch-up. -->
## 2026-06-29 — Increment 192: Feed SP2c-3 (part 2) — auto-refresh cadence (#28 complete)
- **Files:** `app/frontend/js/30e_feed.jsx` (auto-refresh toggle + staleness-gated effect), `app/frontend/js/30c_frame.jsx`
  (pass `active`), `app/frontend/styles.css` (.feed-autorefresh), `callosum-app.html`, `app/backend/help/help_content.md`,
  `INCREMENT-192-NOTES.md`.
- **What:** an opt-in **"Auto-refresh on open"** toggle (default off, localStorage) — when the Feed tab is opened and a
  source is stale (newest poll >6h ago, or never), it fires the existing refresh; throttled ≤1/min, self-quiescing.
  Pull-first, no background daemon. **Closes #28 entirely.**
- **Why:** backlog #28 SP2c-3 (the last open item).
- **Gates:** frontend-only; pytest 654 unchanged; test_frontend_assembly 5/5; QA surface 132/132 API + 657/657 FE, 0
  uncovered; Principles non-triggering (UI convenience over the audited /feed/refresh; no audit gate). Headed-verified,
  no egress (drive_inc192_autorefresh.py: toggle off → 0 items; tick → stale sub auto-polls → 1 item; 0
  console/page/genai). No backend/migration/endpoint/dependency change.
- **Revert:** revert the autoRefresh state/effect/toggle in 30e_feed.jsx + the `active` prop + the CSS; rebuild.

## 2026-06-29 — Increment 191: Feed SP2c-3 (part 1) — medRxiv source + PubMed abstracts (efetch)
- **Files:** `app/backend/discovery/biorxiv_source.py` (server-configurable + medRxiv), `app/backend/discovery/pubmed_provider.py`
  (efetch abstracts), `app/backend/discovery/feed.py` (register medRxiv), `app/backend/help/help_content.md`,
  `tests/test_feed.py`, `.claude/security-audits/2026-06-28_feed.md` (addendum 3), `INCREMENT-191-NOTES.md`.
- **What:** two backend Feed enrichments — **medRxiv** (the preprint source is now server-configurable → kinds
  biorxiv_category + medrxiv_category; the data-driven picker shows both) + **PubMed abstracts** via NCBI efetch
  (targeted-regex parse, no XML parser → no XXE; injectable + fail-closed). No frontend change.
- **Why:** backlog #28 SP2c-3 (round out the Feed's sources + content).
- **Gates:** pytest 654 (+2); ruff clean; QA surface unchanged 132/132 API + 655/655 FE; audit addendum 3 PASS
  (medRxiv = audited host + fixed-literal server segment; efetch = audited host + digit-validated ids + regex parse,
  fail-closed). Live spot-checks (medRxiv epidemiology → 3; PubMed crispr → 3/4 abstracts). No migration/dependency/
  endpoint/frontend change.
- **Revert:** revert the biorxiv_source server param + the medRxiv register line + the efetch additions + the tests.

## 2026-06-29 — Increment 190: Feed SP2c-2 — the journal-by-ISSN source
- **Files:** `app/backend/discovery/journal_issn_source.py` (new), `app/backend/discovery/feed.py` (register),
  `app/backend/help/help_content.md`, `tests/test_feed.py`, `.claude/security-audits/2026-06-28_feed.md` (addendum 2),
  `INCREMENT-190-NOTES.md`.
- **What:** a third Feed source — follow a journal by its ISSN → its recent articles (Crossref
  `filter=issn:…&sort=published`); ISSN validated before the fetch. **No frontend/endpoint/surface change** (the
  data-driven Follow picker rendered the new option automatically — the registry promise, proven backend→UI).
- **Why:** backlog #28 SP2c-2; rounds out the Feed sources.
- **Gates:** pytest 652 (+1); ruff clean; QA surface unchanged 132/132 API + 655/655 FE; audit addendum 2 PASS
  (Crossref host already audited; ISSN validated + bound filter → no SSRF). Live spot-check (Nature 1476-4687 → 3) +
  headed-verified (real source + fake fetcher: "Journal (ISSN)" option, follow → Journal-tagged sub, Refresh polls;
  0 console/page/genai). No migration/dependency/endpoint/frontend change.
- **Revert:** delete `journal_issn_source.py` + the register line + the test; revert the help/audit edits.

## 2026-06-28 — Increment 189: Feed SP2c-1 — PubMed-keyword source + data-driven Follow picker
- **Files:** `app/backend/discovery/pubmed_provider.py` (+ PubMedKeywordFeedSource + record_to_feed_entry + sort param),
  `app/backend/discovery/feed.py` (FeedSource metadata + source_meta + register PubMed), `app/backend/discovery/biorxiv_source.py`
  (categories + metadata), `app/backend/api/routers/feed.py` (source_meta on GET), `app/frontend/js/30e_feed.jsx` +
  `styles.css` (data-driven source picker), `callosum-app.html`, `app/backend/help/help_content.md`,
  `tests/test_feed.py`, `.claude/security-audits/2026-06-28_feed.md` (addendum), `INCREMENT-189-NOTES.md`.
- **What:** the Feed is now multi-source — a saved **PubMed query** joins bioRxiv (esearch sorted by date); the Follow
  UI is a **data-driven** source picker (a `<select>` + per-kind placeholder/datalist from backend `source_meta`), so
  the next source needs no frontend edit.
- **Why:** backlog #28 SP2c — more Feed sources + the multi-kind UI the registry was built for.
- **Gates:** pytest 651 (+1); ruff clean; QA surface 132/132 API + 655/655 FE, 0 uncovered; audit addendum PASS
  (PubMed reuses the audited NCBI host; sort=date is a bound param; source_meta non-secret). Live spot-check (crispr
  off-target → 3 recent) + headed-verified (2 fake sources: select shows both, switch updates placeholder, Follow →
  PubMed-tagged sub, Refresh polls; 0 console/page/genai). No migration/dependency/endpoint.
- **Revert:** drop PubMedKeywordFeedSource + the register line + the source_meta/metadata + the frontend picker rework.

## 2026-06-28 — Increment 188: literature Feed SP2b — the Feed tab UI
- **Files:** `app/frontend/js/30e_feed.jsx` (new — FeedPane), `app/frontend/js/30c_frame.jsx` (Feed tab + pane),
  `app/frontend/styles.css` (.feed-* recipe), `callosum-app.html`, `app/backend/help/help_content.md`,
  `.claude/qa-routes/route_44_feed.md` (fe: + UI flow), `INCREMENT-188-NOTES.md`.
- **What:** the Feed center tab — follow bioRxiv categories (chips), Refresh to poll, triage items (unread dot /
  read-dim / ★ star / Save / ✓ in library / Abstract; All/Unread/Starred filter; Mark all read). Pull-only, opt-in;
  the complete polled list is shown. Save reuses /discovery/save (metadata-only, no PDF) + refreshes the Library.
- **Why:** backlog #28 SP2's frontend half (backend was inc 187); completes #28 (Search + Feed).
- **Gates:** frontend-only; pytest 650 unchanged; test_frontend_assembly 5/5; QA route_44 fe-claimed → surface
  132/132 API + 653/653 FE, 0 uncovered; Principles non-triggering. Headed-verified, no egress
  (drive_inc188_feed.py: follow → refresh → 3 items → read/star → Save flips + lands in Library; 0 console/page/genai).
- **Revert:** delete `30e_feed.jsx`, revert the 30c/styles/help/route edits, rebuild `callosum-app.html`.

## 2026-06-28 — Increment 187: literature Feed SP2a — engine + store + endpoints + bioRxiv source
- **Files:** `app/backend/persistence/schema_feed.py` (new) + `alembic/versions/0021_feed.py` (new migration) +
  `schema.py` (re-export), `app/backend/persistence/feed_repo.py` (new), `app/backend/discovery/feed.py` (new),
  `app/backend/discovery/biorxiv_source.py` (new), `app/backend/api/routers/feed.py` (new), `app/backend/api/app.py`
  (wire feed registry + jobs + router), `tests/test_feed.py` (new, +7), `.claude/qa-routes/route_44_feed.md` (new),
  `.claude/security-audits/2026-06-28_feed.md`, `INCREMENT-187-NOTES.md`.
- **What:** the Feed backend — subscriptions (pull-only, opt-in; get-or-create), an async refresh that polls each
  followed source, a read/starred item store (re-poll idempotent + non-destructive), and the flagship
  **bioRxiv-by-category** source; 8 `/feed/*` endpoints. `in_library` computed at read time; save reuses
  `/discovery/save` (metadata-only, no PDF). The Feed tab UI is SP2b.
- **Why:** backlog #28 SP2 (user greenlit pull-only / no auto-subscribe).
- **Gates:** pytest 650 (+7); ruff clean; QA route_44 → surface 132/132 API + 631/631 FE, 0 uncovered; audit PASS
  (constant host + server-derived path + client-side category filter → no SSRF; bound-param; public-metadata, not the
  Gemini gate; additive guarded migration 0021; no new dependency). Values aligned (pull-only/opt-in/augment-never-filter).
  Live spot-check (neuroscience, 10-day window → 5 real preprints) confirms the mapping.
- **Revert:** drop the new discovery/feed + persistence/feed + routers/feed files + migration 0021, revert the app.py
  + schema.py re-export, delete the test + route + audit.

## 2026-06-28 — Increment 186: literature discovery SP1a — the PubMed source
- **Files:** `app/backend/discovery/pubmed_provider.py` (new), `app/backend/discovery/providers.py` (register PubMed),
  `tests/test_pubmed_provider.py` (new, +4), `tests/test_discovery.py` (registry test → crossref+pubmed),
  `app/backend/help/help_content.md`, `.claude/qa-routes/route_43_discovery.md`,
  `.claude/security-audits/2026-06-28_pubmed-provider.md`, `INCREMENT-186-NOTES.md`.
- **What:** a PubMed Search source (NCBI E-utilities, esearch → esummary; injectable fetcher) registered into the
  discovery registry — search now covers Crossref **+** PubMed with **no endpoint/UI change** (the registry promise);
  a Crossref+PubMed overlap (same DOI) merges to one row with both source pills.
- **Why:** backlog #28 SP1a (a second source; the registry was built for exactly this).
- **Gates:** pytest 643 (+4); ruff clean; QA surface unchanged (124/124 API + 631/631 FE — a provider, not a new
  surface); audit PASS (constant host + query-as-param → no SSRF; fail-closed; public-metadata, not the Gemini gate;
  no new dependency). Principles non-triggering. Live schema spot-check (crispr query → 3 real records) confirms the
  mapping. No migration/endpoint/frontend change.
- **Revert:** delete `pubmed_provider.py` + `test_pubmed_provider.py`, revert the providers.py register line + the
  registry test + help/route edits.

<!-- HELP-DOCS-SYNCED: 2026-06-28 (inc 185) — the "Finding new papers (Discover)" section now describes the axis-relevance highlight badge (hint, not a filter); covers inc 184 (Discover section) + the inc 175–179 reading-pane catch-up. -->
## 2026-06-28 — Increment 185: literature discovery SP1b — axis-relevance highlight
- **Files:** `app/backend/discovery/relevance.py` (new), `app/backend/api/routers/discovery.py` (+ `/discovery/relevance`
  + `_discovery_model`), `app/frontend/js/30d_discover.jsx` (relevance fetch + `.discover-relevance` badge),
  `app/frontend/styles.css` (.discover-relevance), `callosum-app.html`, `app/backend/help/help_content.md`,
  `tests/test_discovery_relevance.py` (new, +5), `.claude/qa-routes/route_43_discovery.md`,
  `.claude/security-audits/2026-06-28_discovery-relevance.md`, `INCREMENT-185-NOTES.md`.
- **What:** `POST /discovery/relevance` scores each search result's title+abstract against the user's axis embeddings
  (local, no egress, no DB write) → the Discover tab **highlights** likely matches in place ("likely: &lt;axis&gt; ·
  match 0.NN"). A hint, **never** a filter/reorder; below-cutoff = no badge (≠ irrelevant); my-publications excluded.
- **Why:** backlog #28 SP1b (the design-blessed fast-follow; user-chosen).
- **Gates:** pytest 639 (+5); ruff clean; QA surface 124/124 API + 631/631 FE, 0 uncovered; audit PASS + Principles
  gate run (signal feature — augment-never-filter, single-similarity, silence-≠-certificate). Headed-verified, no
  egress (drive_inc185_relevance.py: 3 rows shown, exactly 1 badge, 0 console/page/genai). No migration/dependency.
- **Revert:** delete `relevance.py` + `test_discovery_relevance.py`, revert the discovery-router/30d/styles/help/route
  edits, rebuild `callosum-app.html`.

<!-- HELP-DOCS-SYNCED: 2026-06-28 (inc 184) — added a "Finding new papers (Discover)" help section (the Search tab: keyword search of Crossref, keyboard triage, metadata-only save, complete-list-never-filtered); also brought "Highlights and notes" current for the reading-pane run (inc 175–179: Notes search/Noted filter, Copy/Export digest, ◂/▸ mark nav + [ / ] keys, remembered scroll). -->
## 2026-06-28 — Increment 184: literature discovery SP1 frontend — the Discover (Search) tab
- **Files:** `app/frontend/js/30d_discover.jsx` (new — DiscoverPane), `app/frontend/js/30c_frame.jsx` (Discover tab +
  pane), `app/frontend/js/40_app.jsx` (onDiscoverSaved → libRefresh), `app/frontend/styles.css` (.discover-* recipe),
  `callosum-app.html`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_43_discovery.md` (fe: + UI flow),
  `INCREMENT-184-NOTES.md`.
- **What:** the Discover center tab — a query box → `GET /discovery/search` → a dense keyboard-triage results list
  (j/k move, s save, Enter abstract; source pills; ✓ in library marker) → one-click metadata-only **Save** →
  `POST /discovery/save` (refreshes the Library). The complete deduped list is always shown (nothing filtered).
- **Why:** backlog #28 SP1's frontend half (the backend was inc 183).
- **Gates:** frontend-only; QA route_43 fe-claimed → surface 123/123 API + 631/631 FE, 0 uncovered; assembly 5/5;
  pytest 634 unchanged. Headed-verified, no egress (drive_inc184_discover.py: 3 rows, in-library marker, j-nav, Save →
  library; 0 console/page/genai). Principles non-triggering (augment-never-filter; metadata-only; human saves).
- **Revert:** delete `30d_discover.jsx`, revert the 30c/40_app/styles/help/route edits, rebuild `callosum-app.html`.

## 2026-06-28 — Increment 183: literature discovery SP1 (registry + Crossref search + save endpoints)
- **Files:** `app/backend/discovery/{__init__,providers,crossref_provider,search}.py` (new),
  `app/backend/api/routers/discovery.py` (new), `app/backend/api/app.py` (wire registry + router),
  `tests/test_discovery.py` (new, +15), `.claude/qa-routes/route_43_discovery.md` (new),
  `.claude/security-audits/2026-06-28_discovery-search.md`, `INCREMENT-183-NOTES.md`.
- **What:** the discovery backend — a SourceProvider registry + a normalized `Item` (cross-provider dedup,
  `in_library` marking), a Crossref search provider, and `GET /discovery/search` + `POST /discovery/save`
  (metadata-only, deduped, **no PDF fetch**). AI augments-never-filters (complete list); the Search tab UI is inc 184.
- **Why:** backlog #28 (Discover/Search), SP1 — engine-first (like inc-107→108) before the in-app tab.
- **Gates:** pytest +15 (test_discovery); ruff check + format clean; QA surface 123/123 API + 618/618 FE, 0 uncovered
  (route_43); audit PASS (constant Crossref host, query-as-param → no SSRF; bound-param persistence; public-metadata
  egress, not the Gemini gate; no new dependency; no migration). Principles non-triggering (no claim/judgment).
- **Revert:** remove `app/backend/discovery/`, `routers/discovery.py`, the 5 app.py wiring lines, the test + route +
  audit; or restore from a `.claude/backups/` snapshot.

## 2026-06-28 — Increment 182: extract LibraryFrame from 30_viewer (discovery SP0 prereq)
- **Files:** `app/frontend/js/30c_frame.jsx` (new — LibraryFrame), `app/frontend/js/30_viewer.jsx` (remove it),
  `.claude/qa-routes/route_00_smoke_readonly.md` (fe: repoint), `callosum-app.html`,
  `.claude/docs/specs/2026-06-28-discovery-search-design.md` (the design spec), `INCREMENT-182-NOTES.md`.
- **What:** behavior-preserving split — LibraryFrame (the center tab shell) → its own chunk; 30_viewer 599→557
  (clears the maxed cap) + gives the discovery Search tab a home. Wrote the discovery design spec.
- **Why:** prerequisite for the literature-discovery track (#28, approved with Cliff) + relieves the rule-#1 cap.
- **Gates:** frontend-only; QA surface 618/618 (route_00 claims the new chunk); assembly 5/5; pytest 619.
  Behavior-preserving (inc-176 driver re-run: PDF tab opens via LibraryFrame, 0 errors).
- **Revert:** inline LibraryFrame back into 30_viewer; revert the route fe:.

## 2026-06-28 — Increment 181: third-party software NOTICE pass (credit-the-lineage Lane B, backlog #8)
- **Files:** `THIRD-PARTY-NOTICES.md`, `INCREMENT-181-NOTES.md`.
- **What:** added a "Runtime & build dependencies" section crediting every shipped Python + JS dependency with its
  license (grouped by license; PyMuPDF=AGPL noted as reinforcing callosum's license; first-run models noted as
  author-distributed). The NOTICE previously listed only citeproc/CSL/methods.
- **Why:** AGPL compliance + credit-the-lineage Lane B (backlog #8).
- **Gates:** docs-only; no app/migration/egress/surface change; pytest 619. Completes #8 (Lane A = inc 180).
- **Revert:** remove the new section.

## 2026-06-28 — Increment 180: credit-the-lineage for statcheck + shared .method-credit recipe (backlog #8)
- **Files:** `app/frontend/js/06_methods_statcheck.jsx` (STATCHECK_CSL + StatcheckCredit), `app/frontend/js/07_methods_grim.jsx`
  + `app/frontend/js/29_pcurve.jsx` (className repoint), `app/frontend/styles.css` (consolidate), `callosum-app.html`,
  `INCREMENT-180-NOTES.md`.
- **What:** gave statcheck the in-context credit block (Nuijten et al. 2016) + one-click "＋ add to library" that
  GRIM/p-curve already had (credit-the-lineage). Consolidated the byte-identical `.grim-credit`/`.pcurve-credit`
  into one canonical `.method-credit` (DESIGN Pass-2), repointing all three methods.
- **Why:** honor the credit-the-lineage commitment for the one method that lacked it + kill a CSS duplicate.
- **Gates:** frontend-only, reuses the inc-93 import (no new endpoint/migration/egress); Principles-aligned
  (strengthens credit); QA surface 121/618; assembly 5/5; pytest 619. Headed-verified
  (`.local/visual/drive_inc180_credit.py`: statcheck add-to-library → the paper lands; GRIM credit still styles).
- **Revert:** drop StatcheckCredit + STATCHECK_CSL; revert the className/CSS consolidation.

## 2026-06-28 — Increment 179: mark-nav keyboard hotkeys (reading-pane)
- **Files:** `app/frontend/js/30_viewer.jsx` (keydown effect + button tooltip hints), `callosum-app.html`,
  `INCREMENT-179-NOTES.md`.
- **What:** `[` / `]` step to the prev/next highlight (gated to the visible viewer + not-while-typing) — the
  keyboard pairing for the inc-177 Mark buttons; tooltips show the keys.
- **Why:** complete the reading-pane mark-nav ("keep pushin").
- **Gates:** frontend-only; QA surface 121/616; assembly 5/5; pytest 619; headed-verified (`[`/`]` flash prev/next).
  **⚠ 30_viewer is now 599/600 — maxed; further viewer features need another split first.**
- **Revert:** drop the keydown effect + the tooltip key hints.

## 2026-06-28 — Increment 178: README front-door (backlog #11)
- **Files:** `README.md`, `INCREMENT-178-NOTES.md`.
- **What:** rewrote the stale ("Increment 73") README into a current contributor front door — brought the feature
  list current (word-processor adapters, BYOK, retraction/p-curve/GRIM, gap-finder, My Pubs, OA acquisition, merge,
  reading-pane, import) + added the missing onboarding essentials (the `npm install` + `build_frontend` step, venv +
  cross-platform commands, first-run model-download + auto-migrate notes, a Configuration & privacy table, a
  Security note, Known limitations, an AI-assistance note, credit/license pointers).
- **Why:** backlog #11 — the public repo's front door was ~100 increments stale + lacked the JS/build step.
- **Gates:** docs-only; no app/migration/egress/surface change; pytest 619. Shipped as a draft per #11's "your
  voice" boundary — **voice + a screenshot left to the maintainer** (a TODO placeholder marks the screenshot spot).
- **Revert:** `git checkout <prev> -- README.md`.

## 2026-06-28 — Increment 177: next/prev-mark navigation (reading-pane)
- **Files:** `app/frontend/js/30_viewer.jsx` (markCursorRef + stepMark + 2 toolbar buttons), `callosum-app.html`,
  `INCREMENT-177-NOTES.md`.
- **What:** **◂ Mark** / **Mark ▸** toolbar buttons cycle through the paper's highlights in page order (wrapping),
  flashing each via the existing `jumpToAnnotation`. Reuses `.pdf-annot-toggle` (no new CSS).
- **Why:** review marks in sequence without hunting the Notes panel ("follow your heart" reading-pane run).
- **Gates:** frontend-only; QA surface 121/616 (buttons covered by route_32); assembly 5/5; pytest 619.
  Headed-verified (`.local/visual/drive_inc177_marknav.py`: Mark ▸/◂ flash the next/prev highlight; 0 console/page/genai).
- **Revert:** drop stepMark/markCursorRef + the 2 buttons.

## 2026-06-28 — Increment 176: Notes-panel extraction + noted-only filter + note search (reading-pane)
- **Files:** `app/frontend/js/30b_notes.jsx` (new — `AnnotationsPanel`), `app/frontend/js/30_viewer.jsx` (use it),
  `app/frontend/styles.css` (filter-row CSS), `.claude/qa-routes/route_32_viewer_annotations.md` (fe: repoint),
  `callosum-app.html`, `INCREMENT-176-NOTES.md`.
- **What:** extracted the presentational Notes panel out of the viewer (30_viewer 595→573, clears the rule-#1
  watch; behavior-preserving — verified via the inc-144 driver), then added a **noted-only** checkbox + a **note &
  text search** box to it.
- **Why:** "follow your heart" — relieve the cap + ship the first reading-pane filters the close-reader wanted.
- **Gates:** frontend-only, no backend/migration/egress; QA surface 121/612 (route_32 repointed to claim the new
  chunk); assembly 5/5; pytest 619. Headed-verified (`.local/visual/drive_inc176_notesfilter.py`:
  search-by-text/by-note + noted-only each → 1 item; 0 console/page/genai).
- **Revert:** inline `AnnotationsPanel` back into 30_viewer + drop the filter/search + CSS; revert the route fe:.

## 2026-06-28 — Increment 175: remembered scroll position per paper (reading-pane follow-up)
- **Files:** `app/frontend/js/30_viewer.jsx` (save in onScroll + restore in the render block + 2 refs),
  `app/frontend/js/00_lib.jsx` (relocated `buildAnnotationDigest`), `callosum-app.html`, `INCREMENT-175-NOTES.md`.
- **What:** reopening a PDF resumes where you left off — `onScroll` persists `scrollTop` per paper (throttled) to
  localStorage; the render block restores it once per open (a citation `target` wins; not on zoom re-renders).
  Relocated the pure `buildAnnotationDigest` to 00_lib for the rule-#1 headroom (30_viewer 595→back to 595 with the
  feature; was over at 602 before compacting).
- **Why:** Close-reader quality-of-life; chosen over keyboard-zoom (which fights browser Ctrl+± zoom).
- **Gates:** frontend-only, no backend/migration/egress; QA surface unchanged (121/608); assembly 5/5; pytest 619.
  Headed-verified (`.local/visual/drive_inc175_scroll.py`): scroll→600, reload+reopen→restored 600, 0 console/page/genai.
- **Revert:** drop the save/restore + the 2 refs in 30_viewer; move `buildAnnotationDigest` back (optional).

## 2026-06-28 — Increment 174: confirm before re-resolve overwrites hand-edited metadata (backlog #3)
- **Files:** `app/frontend/js/25_detail.jsx` (DoiRow re-resolve guard), `callosum-app.html`, `INCREMENT-174-NOTES.md`.
- **What:** 🔎 re-resolve force-overwrites metadata from Crossref; for a hand-edited paper (`imported_source ==
  "user-edited"`) it now requires a `window.confirm` first, so edits aren't lost on a misclick. Non-edited papers
  are unaffected.
- **Why:** librarian-pass finding (backlog #3) — silent data loss on hand-edited papers.
- **Gates:** frontend-only, no backend/migration/egress; QA surface unchanged (121/608); assembly 5/5; pytest 619.
- **Revert:** drop the confirm in `DoiRow.resolve`.

## 2026-06-28 — Increment 173: import reports parse-time skipped records (backlog #4)
- **Files:** `app/backend/metadata/citation_import.py` (parsers → `(records, skipped)`), `app/backend/api/routers/library.py`
  (`ImportSummary.skipped`), `app/frontend/js/28_import.jsx` (show skipped; fix failed/skipped mislabel),
  `tests/test_citation_import.py`, `callosum-app.html`, `INCREMENT-173-NOTES.md`.
- **What:** the BibTeX/RIS/CSL-JSON import silently dropped entries with no title AND no DOI at parse; now the
  parsers count those drops (+ record-cap overflow) and the import summary reports "N skipped (no title or DOI)" —
  symmetric with inc-155's scan "which files couldn't be read." `failed` (per-record errors) + `skipped` (parse
  drops) are now distinct.
- **Why:** "silence is not a certificate" — an import that drops 3 of 50 entries should say so (backlog #4).
- **Gates:** backend-additive (one response field), no migration/egress/endpoint; QA surface unchanged (121/608);
  `test_citation_import` 9/9; pytest 619; ruff clean.
- **Revert:** restore the parsers' `list[dict]` returns + drop `ImportSummary.skipped` + the modal line.

## 2026-06-28 — Increment 172: download links carry the access token under Remote access (bug fix)
- **Files:** `app/frontend/js/00_lib.jsx` (new `downloadAsset`), `app/frontend/js/35_settings.jsx` (the two
  download links → buttons), `callosum-app.html` (rebuilt), `INCREMENT-172-NOTES.md`.
- **What:** while debugging a user "Couldn't install: Not Found" on the LibreOffice plugin (root cause: a **stale
  running uvicorn** predating the inc-162 routes → restart fixes it; current code serves them, confirmed via
  TestClient), fixed a related latent bug: the **Download .oxt** + **Download manifest** plain `<a download>` links
  bypassed the inc-168 auth shim → 401 under Remote access. They now fetch via the shim (`downloadAsset`) so they
  carry the token.
- **Why:** the user enabled Remote access for Google Docs; plain-anchor downloads silently broke under it.
- **Gates:** frontend-only, no backend/migration/egress; QA surface covered (121/121 API + 608/608 FE);
  `test_frontend_assembly` 5/5; pytest 619 unchanged. No audit/Principles trigger.
- **Revert:** restore the two `<a … download>` links + drop `downloadAsset`.

## 2026-06-28 — Increment 171: Google Docs SP3 — Suggest-from-the-selection + Flatten
<!-- HELP-DOCS-SYNCED: inc 171 — no corpus change needed; the Remote-access note's add-on pointer (inc 170) covers it. -->
- **Files:** `adapters/googledocs/Code.gs` (suggestFromSelection + flattenCitations + selection→cursor-end helpers),
  `adapters/googledocs/gdocs_core.js` (+ pickQueryText/buildSuggestRequest/formatSuggestRows — mirrors the Word core),
  `adapters/googledocs/gdocs_core.test.js` (13/13), `adapters/googledocs/sidebar.html` (Suggest + Flatten buttons),
  `adapters/googledocs/README.md` (§7), `INCREMENT-171-NOTES.md`. (No callosum app code.)
- **What:** Google Docs add-on parity (mirrors Word SP3). **Suggest** — select a sentence → `/citations/suggest`
  (inc 156) → ranked rows (stance + verbatim quote) → Insert (which now collapses a selection to its END so the cite
  lands after the sentence). **Flatten** — drop all citation + bibliography NamedRanges (text stays; Apps Script
  `remove()` keeps content) → plain text, one-way, two-click confirm.
- **Why:** complete the cite-while-you-write loop in Google Docs ("carry on with the plugin").
- **Gates:** no new audit (reuses `/citations/suggest` over the audited bridge); Principles non-triggering
  (signal-not-verdict display, author picks); QA surface unchanged (121/121 API + 604/604 FE); pytest 619 unchanged
  (no Python); node --test 13/13. **Deferred:** true document-order on Refresh (insertion-order v1).
- **Revert:** revert the SP3 additions in `Code.gs` / `gdocs_core.js` / `sidebar.html` (the SP2 add-on stands
  without them).

## 2026-06-28 — Increment 170: Google Docs SP2 — the Apps Script add-on (+ the SP1 bridge live-verified)
<!-- HELP-DOCS-SYNCED: inc 170 — Remote-access help note points to the Google Docs add-on (adapters/googledocs/). -->
- **Files:** `adapters/googledocs/Code.gs` (new — sidebar glue), `adapters/googledocs/gdocs_core.js` (new — pure
  mapping, node-tested + GAS-loaded), `adapters/googledocs/gdocs_core.test.js` (new — `node --test` 10/10),
  `adapters/googledocs/sidebar.html` (new), `adapters/googledocs/appsscript.json` (new),
  `adapters/googledocs/README.md` (§7 + status), `tools/run_tunnel.py` (SP1 refinement — prefer a gitignored local
  config), `.gitignore` (+ `cloudflared-config.local.yml`), `app/backend/help/help_content.md` (Remote-access note),
  `.claude/security-audits/2026-06-28_googledocs-addon.md`, `INCREMENT-170-NOTES.md`. (No callosum app code.)
- **What:** (1) **Completed + live-verified the SP1 bridge** — the user migrated `clffwrkmn.net` to Cloudflare
  (DKIM/SPF/MX verified by nslookup vs HostGator), then `cloudflared login`/`create`/`route dns`; I ran the tunnel +
  an isolated throwaway callosum on :8080 and confirmed through `https://callosum.clffwrkmn.net`: no-token→401,
  token→200, `/citations/styles`→200, `/settings` + `/`→404 (both boundaries hold live). `run_tunnel.py` now prefers
  a gitignored `cloudflared-config.local.yml` so the tunnel id never gets committed. (2) **Built the Google Docs
  add-on** — an Apps Script sidebar (search → insert → refresh+bibliography → style switch) reaching callosum over
  the bridge with the bearer token; citations as NamedRange + DocumentProperties (the Zotero pattern); the pure
  request/response mapping is in `gdocs_core.js` (node-tested + loaded by GAS as `CallosumCore` — no duplication).
- **Why:** make the local library citable from Google Docs (the third word-processor surface, after LibreOffice +
  Word) — the user's "keep pushing" through SP1 setup + SP2 build.
- **Gates:** audit `2026-06-28_googledocs-addon.md` PASS; Principles non-triggering (field-placer); QA surface
  unchanged (121/121 API + 604/604 FE — no new callosum endpoint); pytest 619 unchanged (adapter-only);
  `node --test` 10/10; ruff clean.
- **Revert:** delete the new `adapters/googledocs/{Code.gs,gdocs_core.js,gdocs_core.test.js,sidebar.html,appsscript.json}`;
  revert `tools/run_tunnel.py` + `.gitignore` + the help note. The cloudflared tunnel/CNAME live in the user's
  Cloudflare account (delete with `cloudflared tunnel delete callosum`). v1 limit: citations renumber in
  insertion-order (cut/paste-reorder not reflected on Refresh); Suggest + Flatten are SP3.

## 2026-06-28 — Increment 169: Google Docs SP1 — cloudflared bridge (cite-only) for callosum.clffwrkmn.net
- **Files:** `adapters/googledocs/cloudflared-config.yml` (new — the cite-only ingress), `adapters/googledocs/README.md`
  (new — the setup runbook), `tools/run_tunnel.py` (new — the runner), `.claude/security-audits/2026-06-28_googledocs-tunnel.md`,
  `INCREMENT-169-NOTES.md`. (No callosum app code — cloudflared is an external binary.)
- **What:** the bridge from Google's cloud → local callosum. Recon (via the user's granted SSH) confirmed
  clffwrkmn.net (HostGator shared hosting) prohibits `ssh -R` → can't relay; chose **Cloudflare subdomain
  delegation** (only `callosum.clffwrkmn.net` delegated via 2 NS records at HostGator) + a local **cloudflared**
  tunnel with a **cite-only ingress** (only `/papers`, `/papers/export`, `/citations/{render-document,suggest,styles}`
  → localhost:8080; else 404 — validated). Two boundaries: the inc-168 token + the cite-only ingress.
- **Why:** the user chose Google Docs + callosum.clffwrkmn.net + "only touch the callosum element"; cloudflared
  installed via the permitted winget.
- **Revert:** delete `adapters/googledocs/` + `tools/run_tunnel.py`. No app/schema change. The live tunnel needs the
  user's Cloudflare account (manual); the cite-only ingress + the install were verified, not the live tunnel.
- **Correction (post-build):** Cloudflare **free needs the ROOT domain** (subdomain-only zones are paid) — so the DNS
  side is a careful **whole-domain clffwrkmn.net → Cloudflare migration** (keep existing A/MX/SPF/DKIM "DNS only" →
  site+email unchanged; reversible), not subdomain delegation. `README.md` updated; current DNS enumerated (A→
  50.87.149.75, MX→mail, SPF, DKIM `default._domainkey`) to make the migration email-safe. cloudflared config unchanged.

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 168) — privacy section gained a "Remote access (for the Google Docs add-on)" note (off by default; the access token; the recovery hatch). -->
## 2026-06-27 — Increment 168: Google Docs SP0 — remote-access security foundation (auth + rate-limiting)
- **Files:** `app/backend/api/access_control.py` (new — `AccessControlMiddleware` + `RateLimiter`), `app/backend/api/app.py`
  (wire after CORS), `app/backend/app_settings.py` (`remote_access_enabled` + `access_token`; `_get_secret`/`_set_secret`
  refactor), `app/backend/api/routers/settings.py` (status/update + `POST /settings/access-token`),
  `app/frontend/js/00_lib.jsx` (same-origin bearer fetch shim + token accessors), `app/frontend/js/35_settings.jsx`
  (`RemoteAccessSettings`) + `callosum-app.html`, `tests/test_access_control.py` (new, +8), `tests/test_health.py`
  (route-surface), `.claude/security-audits/2026-06-27_remote-access-auth.md`, `.claude/qa-routes/route_35_settings.md`,
  `app/backend/help/help_content.md`, `INCREMENT-168-NOTES.md`.
- **What:** an opt-in, **default-OFF** bearer-token gate + rate-limiting so callosum can be safely reached by the
  Google Docs add-on via a (later) cloudflared tunnel. cloudflared forwards to localhost → the app can't distinguish
  tunnel from local browser → the token is the only safe boundary, applied to every endpoint (except health/shell/
  preflight). Token stored like the BYOK key (write-only over the wire); the frontend sends it via a same-origin
  fetch shim. The Security-baseline prerequisite for exposure; SP1 (tunnel) + SP2 (add-on) follow.
- **Why:** the user approved Google Docs ("build what's needed, be safe") + chose cloudflared-on-local.
- **Revert:** remove `access_control.py` + unwire in `app.py`; revert the settings/app_settings/frontend additions;
  rebuild. No migration. **Default-off means reverting is low-risk; the feature is inert until a user enables it.**

## 2026-06-27 — Increment 167: split 40_app.jsx (clear the carried 600-line violation)
- **Files:** `app/frontend/js/39_focus.jsx` (new — `useFocusMode` hook), `app/frontend/js/00_lib.jsx`
  (+`downloadCitationExport`/`downloadBibliography`/`_downloadBlob`), `app/frontend/js/40_app.jsx`
  (630→551: focus state/callbacks → the hook; the two download bodies → 00_lib; thin wrappers), `callosum-app.html`,
  `INCREMENT-167-NOTES.md`.
- **What:** a behavior-preserving refactor — lift the axis focus-mode subsystem into a `useFocusMode` hook
  (`39_focus.jsx`) and the citation-download helpers into `00_lib.jsx`, dropping `40_app.jsx` from **630 to 551**
  (under the 600-line cap with margin). The inc-128 precedent (extract a hook into an earlier chunk).
- **Why:** clears the rule-#1 violation flagged as "the immediate next chore" across the last six increment footers
  (the App god-component had crept back over 600).
- **Revert:** `git checkout` `40_app.jsx`/`39_focus.jsx`/`00_lib.jsx` + rebuild. No backend/schema/surface change.
  Verified headed (`.local/visual/drive_inc167_app_split.py`: render + bulk-export download + focus-mode + axis
  filter, 0 console/page/genai). New rule-#1 watch: `30_viewer.jsx` at 595/600.

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 166) — "Citing in Microsoft Word" help section now covers Suggest / one-click style switch / Flatten (SP3, full parity). -->
## 2026-06-27 — Increment 166: Word add-in SP3 — parity (Suggest + one-click style switch + Flatten)
- **Files:** `adapters/word/taskpane.js` (Suggest + style-onChange + Flatten + collapse-to-end insert),
  `adapters/word/taskpane_core.js` (SP3 pure helpers: `pickQueryText`/`buildSuggestRequest`/`formatSuggestRows`),
  `adapters/word/taskpane.{html,css}` (Suggest + Flatten buttons + suggestions list), `adapters/word/taskpane_core.test.js`
  (+3 tests → 11), `adapters/word/README.md`, `app/backend/help/help_content.md` (cite-in-word → SP3), `INCREMENT-166-NOTES.md`.
- **What:** complete Word parity — **Suggest from the sentence** (read selection/paragraph → `/citations/suggest` →
  ranked candidates with stance + quote → insert *after* the sentence), **one-click whole-doc style switch** (style
  dropdown re-renders + persists per-document), and **Flatten** (live → static, two-click confirm). Insert now
  collapses to the selection END (so Suggest doesn't overwrite the sentence).
- **Why:** the user's roadmap — finish the Word adapter (SP1+SP2+SP3).
- **Revert:** `git checkout` the `adapters/word/` files to the inc-165 state; no backend/schema touched.
  **Verification reality:** the user has no Word, so the Office.js glue is exercised by no one (best-effort-correct);
  the pure logic is `node --test` 11/11 and the called endpoints (`/citations/suggest`, render-document, export,
  styles) are all pytest-proven.

## 2026-06-27 — Increment 165: Word add-in SP2 — live cite-while-you-write (Content Controls + Refresh/renumber + bibliography)
- **Files:** `adapters/word/taskpane.js` (rewrite: live insert + Refresh loop), `adapters/word/taskpane_core.js`
  (SP2 pure helpers — tag encode/decode, render-document request/response mapping; SP1-only helpers removed),
  `adapters/word/taskpane.{html,css}` (Refresh button), `adapters/word/taskpane_core.test.js` (SP2 node tests),
  `adapters/word/README.md`, `app/backend/help/help_content.md` (cite-in-word → SP2), `INCREMENT-165-NOTES.md`.
- **What:** upgrade the SP1 static-text insert to the Zotero-style loop — each citation is a Word **Content Control**
  whose `.tag` carries the cluster's CSL-JSON (base64); **Insert** = `/papers/export` csl-json → wrap a CC → Refresh;
  **Refresh** scans citation CCs in document order → `POST /citations/render-document` → writes back position-aware
  in-text + a managed **References** CC. Style dropdown feeds Refresh. (Suggest / style-switch / flatten = SP3.)
- **Why:** the user's roadmap — the real cite-while-you-write feature (after SP1 de-risked the platform).
- **Revert:** `git checkout` the `adapters/word/` files to the inc-164 state; no backend/schema touched.
  **Verification reality:** the user has no Word, so the Office.js glue is exercised by no one (best-effort-correct);
  the pure logic is `node --test` 8/8 and the `/citations/render-document` contract is pytest-proven (inc 107).

## 2026-06-27 — Increment 164: Microsoft Word add-in (Office.js), SP1 — HTTPS spine + search-and-insert task pane
- **Files:** `adapters/word/{manifest.xml,taskpane.html,taskpane.js,taskpane_core.js,taskpane.css,icon.png,README.md,taskpane_core.test.js}`
  (new — the add-in, shipped client code), `app/backend/api/routers/word.py` (new — serve the task pane + manifest +
  install) + `app/backend/api/app.py` (register), `tools/run_https.py` (new — HTTPS run-mode helper),
  `app/frontend/js/35_settings.jsx` (`WordSettings` section) + `callosum-app.html`, `tests/test_word_addin.py` (new, +7),
  `.claude/security-audits/2026-06-27_word-addin.md`, `.claude/qa-routes/route_35_settings.md`,
  `app/backend/help/help_content.md` (cite-in-word), `INCREMENT-164-NOTES.md`.
- **What:** the first Word adapter — a desktop-Word task pane (served by callosum over HTTPS, **same-origin** with the
  API → **no egress, no CORS change**) that searches the library (`/papers?q=`) and inserts a formatted citation as
  static text via `/citations/render` + `Word.run`. SP1 of a 3-SP arc (SP2 = live fields + renumber; SP3 = suggest/
  style/flatten). Architecture A (user-chosen): zero-egress, desktop-only; one-time local-cert + sideload setup.
- **Why:** the user's roadmap — the second word-processor adapter after LibreOffice (inc 108/162); honors local-first.
- **Revert:** delete `adapters/word/`, `routers/word.py` (+ unregister in `app.py`), `tools/run_https.py`, the
  `WordSettings` block, `tests/test_word_addin.py`; rebuild. No migration/schema; restore from a backups snapshot.

## 2026-06-27 — Increment 163: "Coming soon" accordion placeholders (a visible roadmap)
- **Files:** `app/frontend/js/09_placeholders.jsx` (new), `app/frontend/styles.css` (`.coming-soon*`),
  `callosum-app.html`, `.claude/DESIGN.md` (§5 placeholder convention), `INCREMENT-163-NOTES.md`.
- **What:** Scaffold the planned THEORY/METHODS accordion sections + subsection tabs as honest, inert "Coming soon"
  stubs (a visible roadmap): THEORY → **Discover** (tabs Beyond library / Feed / Search, #30/#28); METHODS →
  **Mixed-model reporting** (#23), **Bayesian statistics** (#24), **Meta-analysis** (#37), **Citation equity** (#25);
  + a **"More checks"** tab appended to the shipped Statistics check (#27). Each names a real backlog item, is placed
  by the DESIGN §5 cognitive-task rubric, bakes in its signal-not-verdict framing, and shows no data.
- **Why:** the user wanted the roadmap visible in-GUI "to keep me psyched about all of the stuff we're gonna build."
- **Revert:** delete `09_placeholders.jsx` + the `.coming-soon*` CSS + rebuild. (Frontend-only; no backend/schema.)

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 162) — new "Citing in LibreOffice Writer" help section (install from Settings + the Callosum menu/toolbar; Add vs Suggest); the suggesting-citations "on the way" line corrected. -->
## 2026-06-27 — Increment 162: LibreOffice adapter v2 — discoverable, installable cite flow
- **Files:** `adapters/libreoffice/oxt/{description.xml,META-INF/manifest.xml,Addons.xcu}` (new — the extension),
  `adapters/libreoffice/callosum_addon.py` (new — the XJobExecutor dispatcher), `adapters/libreoffice/callosum_cite.py`
  (configurable server URL + Add-citation search + `_ACTIONS`/dispatch + `_DISPATCH_CTX`), `tools/build_libreoffice_oxt.py`
  (new), `app/backend/api/routers/libreoffice.py` (new — install/download endpoints) + `app.py` (register),
  `app/frontend/js/35_settings.jsx` (LibreOffice-plugin section) + `callosum-app.html`, `adapters/libreoffice/README.md`,
  `tests/test_libreoffice_oxt.py` + `tests/test_libreoffice_install.py` (new, +10), `.claude/qa-routes/route_35_settings.md`,
  `.claude/security-audits/2026-06-27_libreoffice-install.md`, help corpus, `.gitignore` (dist/), `INCREMENT-162-NOTES.md`.
- **What:** Package the LibreOffice citation macro as a one-click extension (`.oxt`) that adds a **Callosum** menu +
  toolbar to Writer (Add citation = search the library / Suggest from the sentence / Refresh / Style / Flatten /
  Server URL), installable from **Settings → LibreOffice plugin** (or a double-clickable `.oxt`). Replaces the
  buried "Organize Macros → Python" + insert-by-id flow with the Zotero/Mendeley-style toolbar + search-to-cite.
- **Why:** the routing was unusable for a real end user — "no end user is going to find this intuitive."
- **Revert:** revert the commit, or remove `adapters/libreoffice/{oxt,callosum_addon.py}` + `tools/build_libreoffice_oxt.py`
  + `routers/libreoffice.py` (+ its app.py registration) + the 35_settings section + the new tests. (No schema change.)

## 2026-06-27 — Increment 161: non-destructive merge of duplicate papers
- **Files:** `app/backend/metadata/paper_merge.py` (new engine), `app/backend/api/routers/duplicates.py`
  (+`POST /papers/merge`), `app/backend/metadata/enrichment.py` (+`MERGED_SOURCE`),
  `app/backend/persistence/profile_repo.py` (+`replace_paper_id`), `app/frontend/js/38_merge.jsx` (new),
  `19_duplicates.jsx` / `10_pdf_layer.jsx` / `40_app.jsx` + `styles.css` (`.merge-*`) + `callosum-app.html`,
  `tests/test_paper_merge.py` (+10), `.claude/qa-routes/route_24_duplicates.md`,
  `.claude/security-audits/2026-06-27_paper-merge.md`, help corpus, `INCREMENT-161-NOTES.md`.
- **What:** Merge two+ duplicate papers (a preprint + its published copy) into one **without deleting anything** —
  launched from the Duplicates modal or the library bulk bar (≥2 selected). The survivor absorbs **both PDFs** +
  every link/tag/highlight/axis-membership/external-id; the user picks the survivor + resolves differing fields +
  the primary PDF; a **"Merged from…"** note records each merged copy's identifiers (so the OSF link survives); the
  merged-away copies go to **Trash** (restorable husks). `POST /papers/merge` (422/409 on bad requests); local;
  no migration; no egress.
- **Why:** the user's real workflow — keep the preprint's PDF + ensure the OSF link survives — which the old
  delete-the-redundant-copy flow couldn't do without risking data loss.
- **Revert:** revert the commit, or remove `paper_merge.py` + the `/papers/merge` endpoint + `38_merge.jsx` + the
  four wiring edits. (No schema change to undo.)

## 2026-06-27 — Increment 160: the library folder is watched by default
- **Files:** `app/backend/acquisition/fetch.py` (`library_dir()` public), `app/backend/api/routers/library.py`
  (rescan always scans `library_dir()`; `GET /library/watched` pins it as the `is_default` entry; `DELETE 0`→422),
  `app/frontend/js/27_scan.jsx` + `styles.css` + `callosum-app.html`, `tests/conftest.py` (isolate
  `CALLOSUM_LIBRARY_DIR`), `tests/test_watched_folders.py` (+3), help corpus, `INCREMENT-160-NOTES.md`.
- **What:** The library folder (`library_dir()` = `CALLOSUM_LIBRARY_DIR` or the project `library/`) is now
  **watched by default** — the auto-rescan (launch/focus) always scans it even with no registered rows, and the
  Watched Folders modal shows it pinned as "default · always watched" (not removable). User-added folders work
  as before; one equal to the library folder folds into the pin.
- **Why:** the user dropped a (retracted) PDF into the library folder and it never appeared — root cause: the
  library folder was never a *registered* watched folder (harness-ingested as `pdf-scaffold`, never UI-scanned),
  and the rescan only scans registered folders. The user's design: the library folder should be watched by
  default + shown as such.
- **Notes:** no new endpoint (`is_default` additive); no migration/egress/dependency; conftest now isolates the
  library dir per-test (also stops OA tests writing the real `library/`). pytest 581; surface 110/110 + 577/577.
  Verified headed (`drive_inc160_library_watched.py`): pinned default row (no remove) + a drop → Re-scan all →
  "1 added"; 0 console/page/genai. **For the user:** restart uvicorn → the library folder auto-rescans →
  Whitehouse ingests + Crossref-enriches + retraction-checks.
- **Revert:** revert the rescan/GET changes in `routers/library.py` + the modal; from git.

## 2026-06-27 — Increment 159: formatted "Cite as…" in the Cite pane (#30 follow-on)
- **Files:** `app/frontend/js/37_cite.jsx` + `styles.css` + `callosum-app.html`, `INCREMENT-159-NOTES.md`.
- **What:** The in-app Cite pane gains a **style picker** + a per-card formatted **Cite** button that renders the
  paper (APA/MLA/IEEE/…) via the inc-106 citeproc engine and copies the reference; the BibTeX copy stays as a
  secondary action. Completes the deadline-writer persona's ask (a formatted citation, not just BibTeX).
- **Why:** #30 — a writer hand-citing in prose wants a formatted human citation, not a reference-manager BibTeX.
- **Notes:** frontend-only; reuses `/citations/render` + `/citations/styles` (local, no egress); no backend/
  endpoint/migration/gate. pytest 578 unchanged; surface 110/110 + 577/577, 0 uncovered. Verified headed
  (`drive_inc159_cite_format.py`): Cite click fires a render (200), 0 console/page/genai.
- **Revert:** drop `FormattedCiteButton` + the style picker from `37_cite.jsx`; from git.

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 158) — Settings + Retraction Watch sections now point to Settings → Metadata access (contact email) instead of the env var. -->
## 2026-06-27 — Increment 158: contact email (polite-pool mailto) in Settings
- **Files:** `app/backend/app_settings.py` (`set_contact_email`/`stored_contact_email`/`resolved_mailto`),
  `app/backend/api/routers/settings.py` (contact_email status + update), `integrations/{crossref,retraction_watch,
  openalex}/adapter.py` + `openalex/author.py` (mailto via `resolved_mailto`), `app/frontend/js/35_settings.jsx`
  (Metadata access section) + `callosum-app.html`, `tests/test_settings.py` (+6), `route_35_settings.md` +
  `route_40_retraction_watch.md`, the BYOK audit (addendum), help corpus, `INCREMENT-158-NOTES.md`.
- **What:** One **Contact email** in Settings → Metadata access overlays `CALLOSUM_CROSSREF_MAILTO` /
  `CALLOSUM_OPENALEX_MAILTO` for Crossref, OpenAlex, and the **Retraction Watch download** — so the RW download
  no longer needs an env var (the user's report).
- **Why:** the RW download was env-only; everything else configurable lives in Settings (the BYOK pattern).
- **Notes:** not a secret (sent to public metadata APIs; `GET /settings` returns it); no new egress vector,
  endpoint, dependency, or migration; audit addendum PASS. pytest 578; surface 110/110 + 573/573, 0 uncovered.
  Verified headed (`drive_inc158_contact_email.py`, isolated settings path): save → persists, 0 console/page/genai.
- **Revert:** drop the contact_email setting + revert the 4 clients to `os.environ.get`; from git.

## 2026-06-27 — Increment 157: highlight-to-suggest, SP1b (LibreOffice "Suggest citations" macro)
- **Files:** `adapters/libreoffice/callosum_cite.py` (new `CallosumSuggestCitations` macro + `fetch_suggestions`/
  `build_suggest_rows`/`current_query_text`/`_suggest_listbox`/`suggest_and_insert`), `adapters/libreoffice/README.md`,
  `adapters/libreoffice/selftest_uno.py` (+ suggest→insert round-trip), `.local/lo_roundtrip/run_roundtrip.py`
  (seed+embed chunks; gitignored), `tests/test_libreoffice_adapter.py` (+4), the inc-108 audit (addendum),
  `INCREMENT-157-NOTES.md`.
- **What:** A LibreOffice writer selects (highlights) a sentence → the macro POSTs it to the inc-156
  `/citations/suggest` → a pick-list (stance + quote + match per row) → the chosen paper inserts as a live
  citation via the existing inc-108 flow. Client-side only; no server change.
- **Why:** #30 SP1b — surface the suggest+evaluate contract inside the word processor (the user's "from the
  LibreOffice document" intent); the inc-107→108 pattern (contract → adapter).
- **Notes:** addendum to the inc-108 adapter audit PASS (same local-only/no-egress posture; the new flow = doc
  text → 127.0.0.1); `SUGGEST_TIMEOUT=90s` (first call loads the embed+NLI models). **Verified: headless UNO
  round-trip SELFTEST OK** (suggest→insert through real LibreOffice; both seeded papers, `support` stance from the
  real NLI). The interactive dialog is the user's manual eyeball. pytest 572. No migration/surface/help change.
- **Revert:** drop the suggest macro + helpers from `callosum_cite.py` + revert the harness/README; from git.

## 2026-06-27 — Increment 156: highlight-to-suggest / evaluate (Track C, SP1a)
- **Files:** `app/backend/citations/suggest.py` (new), `app/backend/summarization/verification.py` (NLI stance),
  `app/backend/api/routers/citations.py` (`POST /citations/suggest`), `app/backend/api/app.py` (`stance_scorer`),
  `app/frontend/js/37_cite.jsx` (new) + `styles.css` + `callosum-app.html`, `tests/test_citations_suggest.py` (new)
  + `tests/test_health.py`, `.claude/qa-routes/route_42_cite.md` (new),
  `.claude/security-audits/2026-06-27_citation-suggest.md`, help corpus, `INCREMENT-156-NOTES.md`, the design spec.
- **What:** Given a draft sentence, **suggest** library papers to cite (retrieval in reverse) + **evaluate** each
  candidate's stance (supports/contrasts/mentions via local NLI). A new **Cite** pane (THEORY accordion) pastes a
  sentence → ranked cards (stance pill · match · verbatim quote · Open source region · Copy BibTeX). The
  `POST /citations/suggest` contract is what the LibreOffice macro (SP1b) will call. Fully local — **no egress**;
  no migration.
- **Why:** Track C (#30) — the highest-value novel capability; SP1a (engine + contract + in-app surface), then
  SP1b (the LibreOffice insert macro), per the inc-107→108 pattern.
- **Notes:** Principles gate run (candidates-not-verdicts, stance-with-quote, region-honest, no opaque score);
  audit PASS; experience pass (deadline-writer persona) → added the Copy-BibTeX extract + visible
  stance-unavailable + de-duped boilerplate in-increment. pytest 568; surface 110/110 + 569/569, 0 uncovered.
- **Revert:** drop the suggest engine/endpoint/pane + the stance scorer; from git.

## 2026-06-27 — Increment 155: scan done-summary surfaces which files couldn't be read (#4)
- **Files:** `app/backend/api/routers/library.py`, `app/frontend/js/27_scan.jsx` + `styles.css` + `callosum-app.html`,
  `tests/test_library_scan.py`, `INCREMENT-155-NOTES.md`.
- **What:** The folder-scan done-summary now lists **which files failed and why** (a `ScanError{path,error}` model +
  `ScanSummary.error_details`, populated from the scan's already-collected per-file errors; a collapsible in the
  scan modal). Scan side only — import parse-drops need a parser change (deferred, noted on #4).
- **Why:** the Migrator experience-pass (#4): "which entries were skipped/failed, and why."
- **Revert:** drop `error_details`/`ScanError` + the `.scan-errors` render; from git.

## 2026-06-27 — Increment 154: statcheck flagged-chip deep-link flashes the specific inconsistent test
- **Files:** `app/frontend/js/06_methods_statcheck.jsx` + `styles.css` + `callosum-app.html`, `INCREMENT-154-NOTES.md`.
- **What:** When a per-paper statcheck run finishes, the first inconsistent row scrolls into view + flashes
  (marked `.flagged-row`) — so the "⚠ flagged" chip path lands on the specific result that doesn't recompute.
  Frontend-only.
- **Why:** the statcheck experience-pass finding (d) — "flagged" → "the specific bad number."
- **Revert:** restore `06_methods_statcheck.jsx` + `styles.css` from git + rebuild.

## 2026-06-27 — Increment 153: synthesis coverage readout + top_k + answerability (#7)
- **Files:** `app/frontend/js/20_synthesis.jsx` + `styles.css` + `callosum-app.html`, `INCREMENT-153-NOTES.md`.
- **What:** After a papers-scope synthesis, a coverage line — "Drew from M of N selected papers · top K chunks
  (· K contributed no cited passage)" — computed from the result's citation `paper_id`s + a new `scopeMeta`; plus
  an answerability note when no claim clears verification. Frontend-only display.
- **Why:** the Skeptical-synthesizer pass (#7): show how much of the selection actually fed the summary.
- **Revert:** restore `20_synthesis.jsx` + `styles.css` from git + rebuild.

## 2026-06-27 — Backlog reconciliation (docs-only; no increment)
- **Files:** `.claude/docs/INCREMENT-BACKLOG.md`, `.claude/docs/INCREMENT-BACKLOG-DONE.md`.
- **What:** Reconciled the open backlog against what actually shipped in inc 109–152 (it had drifted — many items
  listed open/partial were done). Relocated the fully-shipped items to DONE (full entries) + the breadcrumb list:
  #1 brand-assets (non-issue, 109), #2 page-view (110), #10 Gemini key (146), #39 BYOK arc (146–152); tightened the
  partial tracks to their true remainder (#5 Translators-done; #22; #27 GRIM/p-curve/facet-done; #29 gap-finder
  v2-done; #31 findings-done; #35 My-Pubs L1–3-done); retired the shipped "NEXT MAJOR UPGRADE" (121). Number gaps
  (#1/#2/#10/#39) kept for cross-ref stability.
- **Why:** so the OPEN list shows only genuine remaining work ("a good sense of what remains").
- **Verified read-only:** #1 is a non-bug (`inline_brand_assets.py` reads `.claude/media/` correctly); no app code touched.
- **Revert:** from git.

<!-- HELP-DOCS-SYNCED: 2026-06-27 (inc 152) — help corpus current as of OS-keychain key storage -->
## 2026-06-27 — Increment 152: OS-keychain key storage (optional keyring, file fallback)
- **Files:** `app/backend/app_settings.py`, `integrations/gemini/generator.py`, `app/backend/api/routers/settings.py`,
  `app/frontend/js/35_settings.jsx` + `callosum-app.html`, `requirements.txt`, `app/backend/help/help_content.md`,
  `tests/test_settings.py`, `.claude/security-audits/2026-06-27_keychain-storage.md`, `INCREMENT-152-NOTES.md`.
- **What:** BYOK provider keys can live in the **OS keychain** (`keyring`, optional) instead of the gitignored file.
  `get/set_provider_key` are keychain-aware (keychain → file fallback; migrate-on-save; fail-closed to file). `GET
  /settings` reports `key_storage` ("keychain"/"file"); the UI shows where keys live. No hard new dependency.
- **Why:** the deferred #39 hardening — encrypted-at-rest key storage when available, with a graceful fallback.
- **Revert:** restore the file-only `set/get_provider_key` + `_resolve_key`/`_stored_key`; from git.

## 2026-06-27 — Increment 151: validation-lock disclaimer + help-assistant toggle in Settings
- **Files:** `app/backend/api/routers/settings.py`, `app/backend/app_settings.py`, `integrations/gemini/generator.py`,
  `app/frontend/js/35_settings.jsx` + `styles.css` + `callosum-app.html`, `app/backend/help/help_content.md`,
  `tests/test_settings.py`, `INCREMENT-151-NOTES.md`.
- **What:** (A) A standing "verified locally — your model affects quality, not which citations pass" disclaimer in
  Settings → AI features (the validation-lock made visible). (B) The AI help assistant (already per-provider via the
  inc-149 seam) is now toggleable in Settings, not env-only — `help_assistant_enabled` stored + overlaid like egress.
- **Why:** set expectations for non-flagship/local models (quality vs correctness); finish moving AI config to the UI.
- **Revert:** drop the help-toggle field + the disclaimer note from the settings router + `35_settings.jsx`; from git.

## 2026-06-26 — Increment 150: multi-provider Settings UI (#39 part 2 — completes #39)
- **Files:** `app/backend/api/routers/settings.py`, `app/frontend/js/35_settings.jsx` + `callosum-app.html`,
  `app/backend/help/help_content.md`, `tests/test_settings.py`, `tests/test_providers.py`,
  `.claude/qa-routes/route_35_settings.md`, `.claude/security-audits/2026-06-26_multi-provider-llm.md` (addendum),
  `INCREMENT-150-NOTES.md`.
- **What:** A **Model provider** dropdown (Gemini / OpenAI / Anthropic / Local) in Settings → AI features. Cloud →
  key field + egress toggle; Local → a loopback `base_url` + "nothing leaves your machine" (no egress toggle).
  `PUT /settings` extended (provider allowlist, loopback-422, per-provider write-only keys); test-key is
  provider-aware. Completes #39.
- **Why:** Use OpenAI/Anthropic, or a local model for AI summaries with **zero egress**, all from the UI.
- **Revert:** restore `35_settings.jsx` + the settings router from git; rebuild.

## 2026-06-26 — Increment 149: multi-provider LLM engine (#39 part 1)
- **Files:** `app/backend/llm/providers.py` (new), `integrations/gemini/generator.py` (+ the 5 other
  `integrations/gemini/*.py` generators), `app/backend/llm/egress.py`, `app/backend/app_settings.py`,
  `app/backend/api/routers/{summaries,axes,my_publications}.py`, `tests/test_providers.py` (new),
  `.claude/security-audits/2026-06-26_multi-provider-llm.md`, `INCREMENT-149-NOTES.md`.
- **What:** One `complete(config, prompt)` seam routes all 6 generators to Gemini/OpenAI/Anthropic/local (httpx,
  no new dep). `GeminiConfig`→`LLMConfig` (+alias) gains `provider`/`base_url` + per-provider key resolution; the
  `EgressGated*` gate is provider-aware (`requires_egress`); a **loopback** local provider runs with **zero egress**.
- **Why:** BYOK beyond Gemini (#39) — and a local model means AI summaries that never leave the machine.
- **Revert:** revert the 6 generators to the genai call + drop providers.py + the gate `provider` field; from git.

## 2026-06-26 — Increment 148: synthesis pane "AI is off" nudge (frontend-only)
- **Files:** `app/frontend/js/{40_app,20_synthesis}.jsx` + `styles.css` + `callosum-app.html`,
  `app/backend/help/help_content.md`, `INCREMENT-148-NOTES.md`.
- **What:** When AI is off, the Synthesis pane shows an **"AI summaries are off — Enable in Settings →"** nudge
  (proactive + in place of the raw `DataEgressDisabledError`) instead of a dead-end. `paneCtx.onOpenSettings` +
  a `settingsNonce` (re-read egress on Settings close) wire it; the button opens the Settings modal.
- **Why:** A user who tries to summarize with egress off got a developer-y error with no path to fix it.
- **Revert:** restore the two frontend chunks + `styles.css` from git + rebuild.

## 2026-06-26 — Increment 147: "Test this key" — egress-gated key validation
- **Files:** `app/backend/api/routers/settings.py`, `app/frontend/js/35_settings.jsx` + `styles.css` +
  `callosum-app.html`, `app/backend/help/help_content.md`, `tests/test_settings.py`, `tests/test_health.py`,
  `.claude/qa-routes/route_35_settings.md`, `.claude/security-audits/2026-06-26_test-key.md`, `INCREMENT-147-NOTES.md`.
- **What:** A **Test key** button (Settings → AI features) validates a saved Gemini key via a tiny non-library
  ping. `POST /settings/test-key` → `{ok, detail}`; gated on egress ON (off ⟹ no outbound call); key never
  logged/returned (errors redacted).
- **Why:** A BYOK user wants to confirm a pasted key works before relying on it — without running a full summary.
- **Revert:** remove the endpoint + the Settings button; restore from git.

## 2026-06-26 — Increment 146: BYOK — Gemini API key + egress consent from the Settings UI
- **Files:** `app/backend/app_settings.py` (new), `app/backend/api/routers/settings.py` (new),
  `app/backend/api/app.py`, `integrations/gemini/generator.py`, `app/frontend/js/35_settings.jsx` + `styles.css` +
  `callosum-app.html`, `app/backend/help/help_content.md`, `tests/conftest.py`, `tests/test_settings.py`,
  `tests/test_health.py`, `.claude/qa-routes/route_35_settings.md`,
  `.claude/security-audits/2026-06-26_byok-api-key.md`, `INCREMENT-146-NOTES.md`.
- **What:** Bring-your-own-key — set the Gemini API key **and** toggle data egress from **Settings → AI features**,
  not just env vars. A local store (`~/.callosum/app-settings.json`, outside the repo + synced Dropbox) overlays the
  env defaults in `GeminiConfig.from_environment()` (so every AI feature picks it up with zero call-site changes).
  `GET /settings` returns status only (never the key value); `PUT /settings` sets/clears the key + toggles egress.
- **Why:** A GitHub user shouldn't have to edit a `.env` to use AI. The key never leaves the machine except to
  Google; egress stays default-OFF + explicit (invariant #3 unchanged); the key is write-only over the wire.
- **Revert:** delete the two new backend files + the router include + the `GeminiConfig` overlay + the frontend
  section; restore from git. (No migration.)


- **Files:** `app/frontend/js/10_pdf_layer.jsx` + `20_synthesis.jsx` + `40_app.jsx` + `styles.css` +
  `callosum-app.html`, `app/backend/help/help_content.md`, `.claude/qa-routes/route_55_synthesis_verification.md`,
  `.claude/docs/INCREMENT-BACKLOG.md`, `INCREMENT-145-NOTES.md`. (Help corpus also brought current for inc 143/144.)
- **What:** Ran the **Skeptical synthesizer** persona pass on the select→summarize flow → the focus query (a
  query-ranked multi-paper synthesis, inc 111) **already worked but was invisible** (the focus lived in the
  Synthesis textarea, not the selection bar; the help even misframed it). Added a **"Focus on… (optional)"** input
  to the selection bar → threads to the multi-paper synthesis as `query` (query-ranked) + reflects into the
  textarea + the "focused on …" scope-note. Frontend + a help fix.
- **Why:** A skeptic would never discover the focused path and walk away thinking it only does generic summaries.
- **Revert:** restore the listed frontend files from git + rebuild.

## 2026-06-26 — Increment 144: export / copy a paper's highlights + notes (Close reader dogfood)
- **Files:** `app/frontend/js/30_viewer.jsx` + `styles.css` + `callosum-app.html`,
  `.claude/qa-routes/route_32_viewer_annotations.md`, `.claude/docs/INCREMENT-BACKLOG.md`, `INCREMENT-144-NOTES.md`.
- **What:** Ran the **Close reader** persona pass on the read→highlight→note→return flow → reading + marking +
  re-finding all work well, but the marks were trapped in the panel (no way to get them out). Added **Copy** +
  **Export .md** buttons in the Notes panel head → a Markdown digest of the paper's highlights + notes (built from
  the loaded annotations; `navigator.clipboard` + blob-download, the inc-70 pattern). Frontend-only.
- **Why:** A close reader's payoff is the marked-up artifact — "show me everything I marked, as a list I can carry
  elsewhere."
- **Revert:** restore `30_viewer.jsx` + `styles.css` from git + rebuild.

## 2026-06-26 — Increment 143: deleting an imported keyword tag is durable (Librarian pass + backlog #3)
- **Files:** `app/backend/persistence/schema.py` + `alembic/versions/0020_suppressed_paper_tags.py` (new),
  `app/backend/persistence/tags_repo.py`, `app/backend/metadata/enrichment.py`, `tests/test_tags.py`,
  `.claude/qa-routes/route_20_tags.md`, `INCREMENT-143-NOTES.md`.
- **What:** Ran the **Librarian** persona pass on the tag-curation flow → found deleting an imported keyword tag
  wasn't durable (🔎 re-resolve silently re-added it; tags don't duplicate + mine-vs-imported is clear — those
  work). Built a per-paper **suppressed-keyword** set (`suppressed_paper_tags`, migration 0020): removing an
  imported `keyword:*` tag records a suppression; `apply_crossref_subject_tags` skips suppressed names; re-adding a
  tag clears it. Backend-only.
- **Why:** A librarian must trust curation is non-destructive — a deliberate keyword removal shouldn't be undone by
  the next enrich.
- **Revert:** restore the listed files from git; `suppressed_paper_tags` is additive (migration 0020).

## 2026-06-26 — Increment 142: determinate import/scan progress (Migrator experience pass + backlog #4)
- **Files:** `app/backend/api/job_store.py`, `app/backend/embeddings/pipeline.py`,
  `app/backend/pdf_processing/library_scan.py`, `app/backend/api/routers/library.py`,
  `app/frontend/js/10_pdf_layer.jsx` (ProgressBar) + `27_scan.jsx` + `28_import.jsx` + `40_app.jsx` + `styles.css`
  + `callosum-app.html`, `tests/test_job_store.py` (new) + `test_embeddings.py`, `INCREMENT-142-NOTES.md`.
- **What:** Ran the **Migrator** persona pass on the import/scan onboarding flow → found the bar was an opaque
  indeterminate pulse ("looks identical at item 3 and item 380"). Built **determinate "X / N" progress**
  (`JobStore.mark_progress` + `on_progress` callbacks through `embed_papers`/`embed_chunks`/`scan_library_folder`
  → the modals render a real fill + "Embedding papers — X / N") + a **"Review unsorted →"** door in the scan
  done-summary → the inc-80 Unsorted view.
- **Why:** A few-hundred-item import felt like a black box; the migrator's #1 anxiety is "is it stuck / how far".
  Opt-in + additive (other jobs stay indeterminate).
- **Revert:** restore the listed files from git + rebuild.

## 2026-06-26 — Increment 141: statcheck flagged→detail path (the experience-pass fix)
- **Files:** `app/frontend/js/40_app.jsx` + `06_methods_statcheck.jsx` + `callosum-app.html`,
  `.claude/qa-routes/route_33_methods_statcheck.md`, `.claude/docs/INCREMENT-BACKLOG.md`, `INCREMENT-141-NOTES.md`.
- **What:** The inc-140 experience-pass dogfood found "this paper is flagged" never linked to "the specific result
  that doesn't recompute." Fix (frontend-only): the "⚠ N flagged" chip now opens the METHODS **Statistics check**
  section, re-targets the top *flagged* paper (a deferred-select ref, so it uses the filtered list not the stale
  one), and the per-paper check **auto-runs** when that section is open — so the inconsistent rows (reported vs
  recomputed *p* + page) show with no manual "Check statistics" click.
- **Why:** Close the experience gap the persona agent surfaced — the deadline citer's exact frustration.
- **Revert:** restore the two frontend files from git + rebuild.

## 2026-06-26 — Increment 140: the end-user experience pass (a 4th gate) + its first dogfood
- **Files:** `.claude/EXPERIENCE-PASS.md` (new), `.claude/CLAUDE.md` (rule #11 + reference row + footer),
  `.claude/docs/INCREMENT-BACKLOG.md` (the dogfood finding), `INCREMENT-140-NOTES.md`.
- **What:** Codifies a standing orientation — before any user-facing change is "done," make a pass *inhabiting the
  end user* (reception + intended-use, the latter bounded by the #9 + A-A vetoes) via **persona-grounded
  experience agents** (a subagent in-character as a concrete user with a goal-in-the-moment). The 4th gate beside
  DESIGN (looks) / PRINCIPLES (honest) / QA (works+covered): **EXPERIENCE (serves the user).** Dogfooded it on
  statcheck (the deadline-citer persona) → found the "this paper is flagged → the specific result that doesn't
  recompute" path is hidden; filed it **▲ BUILD FIRST** to the backlog.
- **Why:** A change can pass DESIGN/PRINCIPLES/QA and still strand a real person mid-task (the statcheck case the
  user kept raising). This gate catches that.
- **Revert:** delete `EXPERIENCE-PASS.md` + the rule #11 / reference-row / backlog additions. Docs-only.

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 139) — help corpus current as of the Tags-tab / accordion-tabs rewrite -->
## 2026-06-26 — Increment 139: accordion tabs-within-a-section (Tags → a tab of AXES; METHODS reordered)
- **Files:** `app/frontend/js/05_panes.jsx` + `15_axes.jsx` + `10_pdf_layer.jsx` + `06_methods_statcheck.jsx` +
  `07_methods_grim.jsx` + `styles.css` + `callosum-app.html`, `.claude/DESIGN.md`, `app/backend/help/help_content.md`,
  `.claude/qa-routes/route_00_smoke_readonly.md` + `route_20_tags.md`, `INCREMENT-139-NOTES.md`.
- **What:** The pane registry gains **tabs-within-a-section** (`registerPaneTab`); **Tags** moves from its own
  THEORY section to the **second tab of AXES** (`[Axes | Tags]`); METHODS reordered so **Data consistency (GRIM)**
  precedes **Statistics check**. Tab strip reuses the `.tags-srcfilter` chip recipe; tabs mount-but-hide + persist.
- **Why:** Codify the IA rule (accordion sections = broad categories, tabs = like-with-like submenus, order by
  cognitive task) so the accordion stays shallow as more METHODS modules land (user request).
- **Revert:** restore the listed frontend files from git + rebuild.

## 2026-06-26 — Increment 138: auto-select the top library paper on load (Details populated)
- **Files:** `app/frontend/js/40_app.jsx`, `callosum-app.html`, `.claude/qa-routes/route_00_smoke_readonly.md`,
  `INCREMENT-138-NOTES.md`.
- **What:** On load the top library paper is auto-selected, so the METHODS → DETAILS section starts populated
  (its editable Details) instead of the "Select a paper …" hint. Fires only when nothing is selected and the
  (non-trash) list is ready; never overrides a user's selection. Frontend-only.
- **Why:** The right pane started empty until the user clicked a paper; auto-selecting the top one makes Details
  immediately useful on load (user request).
- **Revert:** remove the auto-select effect from `40_app.jsx` + rebuild.

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 137) — help corpus current as of the gap-finder v2 (direction/axis/cache) rewrite -->
## 2026-06-26 — Increment 137: gap-finder v2 (forward gap + axis-scoped + persistent cache)
- **Files:** `app/backend/clustering/gapfinder.py`, `integrations/openalex/adapter.py`,
  `app/backend/persistence/gap_repo.py` (new) + `schema_base.py` (new) + `schema_findings.py` (new) +
  `schema.py` (split) + `alembic/versions/0019_gap_candidates.py` (new), `app/backend/api/routers/gaps.py`,
  `app/frontend/js/36_gaps.jsx` + `10_pdf_layer.jsx` + `styles.css` + `callosum-app.html`, `tests/test_gapfinder.py`
  + `test_health.py`, `app/backend/help/help_content.md`, `.claude/security-audits/2026-06-26_gapfinder.md`
  (addendum), `.claude/qa-routes/route_41_gaps.md`, `INCREMENT-137-NOTES.md`.
- **What:** Extends the gap-finder with a **forward** direction (works that *cite* your papers), **axis-scoped**
  scanning, and a **persistent `gap_candidates` cache** (GET reads instantly + filters dismissed/in-library at
  read time; Refresh recomputes). New OpenAlex `fetch_work_id` + `fetch_citing_works`; new `GET /gaps` +
  `POST/GET /gaps/refresh` (replacing `/gaps/find*`). Frontend gains a direction toggle + axis dropdown + Refresh.
- **Why:** The user chose "persistent cache + axis-scoped + forward gap" — surface newer work building on the
  library, scope discovery to a topic, and open the modal instantly without re-scanning.
- **Also:** Split `schema.py` (611 → 558, over the 600-line cap from inc 130/132) — the findings/signals/retraction
  + gap tables moved to `schema_findings.py` on a shared `schema_base.metadata`, re-exported (zero blast radius).
- **Revert:** restore the listed files from git (this commit); `gap_candidates` is additive (migration 0019).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 136) — help corpus current as of the watched-folder focus-rescan line -->
## 2026-06-26 — Increment 136: watched folders rescan on window focus (live-ish pickup)
- **Files:** `app/frontend/js/40_app.jsx`, `app/backend/help/help_content.md`, `INCREMENT-136-NOTES.md`.
- **What:** Watched-folder rescans now also fire when the window regains focus (throttled 20s + in-flight guard),
  not just on launch — so a PDF dropped into a watched folder appears when you switch back to Callosum (its DOI is
  read from the file → enriched → retraction-checked, all already wired). Frontend-only.
- **Why:** A user dropped a PDF expecting it to appear; rescans only ran on launch, so nothing happened
  mid-session. A reasonable user expects a watched folder to feel live.
- **Revert:** restore `40_app.jsx` from git (this commit).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 135) — help corpus current as of the "Finding gaps" section -->
## 2026-06-26 — Increment 135: literature gap-finder (backward citation gap)
- **Files:** `integrations/openalex/adapter.py`, `app/backend/clustering/gapfinder.py` (new),
  `app/backend/api/routers/gaps.py` (new), `app/backend/persistence/profile_repo.py` + `schema.py` +
  `alembic/versions/0018_profile_dismissed_gaps.py` (new), `app/backend/clustering/my_publications.py`,
  `app/backend/api/app.py`, `app/frontend/js/36_gaps.jsx` (new) + `10_pdf_layer.jsx` + `40_app.jsx` + `styles.css`,
  `tests/test_gapfinder.py` (new) + `test_health.py`, `.claude/security-audits/2026-06-26_gapfinder.md` (new),
  `.claude/qa-routes/route_41_gaps.md` (new), `help_content.md`, `INCREMENT-135-NOTES.md`.
- **What:** Aggregate each library paper's OpenAlex `referenced_works` → surface works cited by ≥N of your papers
  that you don't have ("cited by N of your papers") as Add/Dismiss candidates. New OpenAlex fetches
  (`fetch_referenced_works` + `fetch_work_meta`); `clustering/gapfinder.compute_gaps`; an ephemeral async job
  (`POST/GET /gaps/find`); `POST /gaps/add` (metadata-only into the general library, reusing import_citing_work) +
  `POST /gaps/dismiss` (persisted in `profile.dismissed_gap_works`, migration 0018); a "Gaps" library-header
  button + modal. The count is the user's-library citing, never a quality rank; coverage stated.
- **Why:** A long-wanted discovery capability — find the important references your library leans on but is missing.
- **Revert:** restore the listed files from git (commits `…t1` adapter/compute, `…t2` migration+endpoints, `…t3`
  UI, + this docs commit); migration 0018 is additive (drop the `dismissed_gap_works` column to revert).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 134) — help corpus current as of the on-import/staleness lines -->
## 2026-06-26 — Increment 134: retraction lifecycle (on-import auto-check + RW staleness nudge)
- **Files:** `app/backend/methods/retraction.py` (`auto_check_retractions`), `app/backend/api/routers/library.py`
  (scan + import hooks), `app/frontend/js/08_methods_findings.jsx` + `styles.css`, `tests/test_retraction.py`,
  `.claude/security-audits/2026-06-26_retraction.md` (addendum), `help_content.md`, `INCREMENT-134-NOTES.md`.
- **What:** New papers are auto-checked for retraction on import (the scan + citation-import jobs, guarded
  best-effort over the new paper ids, reusing the inc-131 checkers) so a freshly imported retracted paper flags
  immediately; the Retraction Watch panel surfaces its snapshot age and nudges a refresh past 30 days.
- **Why:** Completes the producer's world-state lifecycle — automatic at import, with staleness visible — beyond
  the on-demand batch/per-paper.
- **Revert:** restore the listed files from git (commits `…t1` backend, `…t2` frontend, + this docs commit); no
  migration/endpoint to undo.

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 133) — help corpus current as of the review-queue lines -->
## 2026-06-26 — Increment 133: activate the candidate-review half (statcheck candidates + "N to review" facet)
- **Files:** `app/backend/api/routers/methods.py` (statcheck batch), `repository.py` (the `finding` filter),
  `routers/papers.py` (the `finding` param), `app/frontend/js/{40_app,10_pdf_layer}.jsx` + `styles.css`,
  `tests/test_findings_review.py` (new), `.claude/qa-routes/route_38_findings.md`, `help_content.md`, `INCREMENT-133-NOTES.md`.
- **What:** The statcheck batch now also emits a CANDIDATE finding per flagged paper (coexisting with the inc-97
  signal — candidate = the user's reviewable work-state, signal = the persistent fact), and a unified "📋 N to
  review" library chip + filter (`GET /papers?finding=needs-review` → `FINDING_FILTERS` bound subquery) surfaces
  every paper with an unreviewed candidate; reviewing one drops it from the queue live.
- **Why:** The inc-130 Confirmed/Accepted/Noted candidate-review machinery was built but unexercised (retraction
  writes facts); this gives it real content + a place to triage it library-wide.
- **Revert:** restore the listed files from git (commits `…t1` backend, `…t2` frontend, + this docs commit); no
  migration to undo (reuses `paper_findings` + a query param).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 132) — help corpus current as of the RW-database paragraph -->
## 2026-06-26 — Increment 132: Retraction Watch DB (SP2) — the bulk third retraction source
- **Files:** `app/backend/persistence/schema.py` + `retraction_repo.py` (new), `alembic/versions/0017_retraction_records.py`
  (new), `integrations/retraction_watch/{__init__,adapter}.py` (new), `app/backend/methods/retraction.py`,
  `app/backend/api/routers/methods.py`, `app.py`, `app/frontend/js/08_methods_findings.jsx` + `styles.css`,
  `tests/test_retraction_watch.py` (new) + `test_health.py`, `.claude/qa-routes/route_40_retraction_watch.md` (new),
  `.claude/security-audits/2026-06-26_retraction-watch.md` (new), `help_content.md`, `INCREMENT-132-NOTES.md`.
- **What:** Download the Crossref-hosted Retraction Watch DB (CC0 CSV) into a local `retraction_records` mirror
  (migration 0017) + a third checker (`RETRACTION_WATCH_CHECKER`, prepended to DEFAULT_CHECKERS — richest source,
  its reason/date/notice wins the merge) + `GET /methods/retraction/database` + async `POST`/`GET
  /methods/retraction/database/refresh` + a "Refresh database" UI with an as-of line. Reinstatements never flagged;
  replace-all keeps the mirror honest.
- **Why:** Completes the user's "all three sources" ask — the RW DB is the authoritative, richest retraction
  source; matching offline scales to the whole library from one download.
- **Revert:** restore the listed files from git (commits `…t1` storage+adapter, `…t2` checker+endpoints, `…t3` UI,
  + this docs/gates commit); migration 0017 is additive (drop `retraction_records` to revert the schema).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 131) — help corpus current as of the "Retraction checks" section -->
## 2026-06-26 — Increment 131: retraction producer (SP1: Crossref + OpenAlex) — the first findings producer
- **Files:** `app/backend/methods/retraction.py` (new), `integrations/crossref/adapter.py`,
  `integrations/openalex/adapter.py`, `app/backend/persistence/signals_repo.py`, `repository.py`,
  `app/backend/api/routers/methods.py`, `app.py`, `app/frontend/js/{08_methods_findings,10_pdf_layer,40_app}.jsx`,
  `styles.css`, `tests/test_retraction.py` (new) + `test_health.py`, `.claude/qa-routes/route_39_retraction.md` (new),
  `.claude/security-audits/2026-06-26_retraction.md` (new), `DESIGN.md`, `help_content.md`, `INCREMENT-131-NOTES.md`.
- **What:** Multi-source (Crossref + OpenAlex) per-DOI retraction detection → a FACT in `paper_findings`
  (Review-pane FactMark + notice link + ◆ card mark) + an honest per-paper check status in
  `open_science_signals` (silence ≠ clean) + a library "Retracted" chip/filter + a library-wide batch. `GET
  /papers/{id}/retraction`, `POST`/`GET /methods/retraction/run`, `GET /methods/retraction/summary`. No migration.
- **Why:** The first real findings producer; retractions are high-stakes to know before citing. A registry FACT
  relayed verbatim (no LLM), evidence-carried (sources + notice), no-accusation (the A-A veto), silence-honest.
- **Revert:** restore the listed files from git (commits `…t1` core, `…t2` endpoints, `…t3` UI, + this docs/gates
  commit); no migration to undo (reuses `paper_findings` + `open_science_signals`).

<!-- HELP-DOCS-SYNCED: 2026-06-26 (inc 130) — help corpus current as of the findings "Review" section -->
## 2026-06-26 — Increment 130: findings subsystem (FACT-vs-CANDIDATE backbone), foundation only
- **Files:** `app/backend/persistence/schema.py` + `findings_repo.py` (new), `alembic/versions/0016_paper_findings.py`
  (new), `app/backend/api/routers/findings.py` (new) + `app.py`, `app/frontend/js/08_methods_findings.jsx` (new) +
  `10_pdf_layer.jsx` + `40_app.jsx` + `styles.css`, `tests/test_findings.py` (new) + `test_health.py`,
  `.claude/qa-routes/route_38_findings.md` (new) + `route_00_smoke_readonly.md`, `.claude/DESIGN.md`,
  `app/backend/help/help_content.md`, `.claude/security-audits/2026-06-26_findings.md` (new), `INCREMENT-130-NOTES.md`.
- **What:** A persistent, typed, per-paper **findings** store (`paper_findings`, migration 0016) + a review surface.
  Producers call `upsert_findings` (idempotent by `content_key` — supersede + preserve unchanged reviews); the
  METHODS "Review" section renders **facts** as neutral marks and **candidates** as reviewable cards (Confirmed /
  Accepted[reason] / Noted); the library card shows a `◆ fact` mark + an `N to review` work-state badge from
  `GET /findings/overview`. Endpoints: `GET /papers/{id}/findings`, `GET /findings/overview`,
  `POST /findings/{id}/review`. **Contract + UI only — no producer wired yet** (retraction is next).
- **Why:** The FACT-vs-CANDIDATE backbone the data-detective features (statcheck/p-curve/GRIM/retraction) plug into;
  encodes the honesty distinction structurally (signal-not-verdict, no score, no accusation, human-is-the-filter).
- **Revert:** restore the listed files from git (commits `8aa278d` schema+repo, `1006513` endpoints, `7c3a87c` UI, +
  the docs/gates commit); migration 0016 is additive (drop `paper_findings` to fully revert the schema).

## 2026-06-25 — Increment 125: strengthen the front-matter classifier (live-validated)
- **Files:** `app/backend/summarization/chunk_filtering.py`, `tests/test_chunk_filtering.py`,
  `INCREMENT-125-NOTES.md`.
- **What:** A live real-Gemini synthesis (user-authorized token spend) showed inc-123's classifier still let
  paper titles, author/affiliation lines, journal running-headers, and funding lines into the verified claims.
  Strengthened `is_front_matter_chunk` to catch those (name-attached + digit-prefix author superscripts;
  funding/grant-id lines; Title-Case-without-terminal-punctuation titles/headers — safe for prose). Real leaked
  examples are now regression tests.
- **Why:** inc 123 (front-matter fix) was too conservative on real data; the verified claims (and the inc-124
  Overview built on them) must be body text. Confirmed live: clean claims + a real 3-sentence Overview with
  per-sentence claim traces.
- **Revert:** restore the inc-123 `is_front_matter_chunk` body (commit `e446b46`).

## 2026-06-25 — Increment 129: multi-item GRIMMER
- **Files:** `app/backend/methods/grim.py`, `app/frontend/js/07_methods_grim.jsx`, `callosum-app.html`,
  `app/backend/help/help_content.md`, `tests/test_grim.py`, `INCREMENT-129-NOTES.md`.
- **What:** Completes inc-127 GRIMMER — `grimmer_test` now supports `items > 1` (multi-item scales): the same
  analytic check with an `items²` factor on the variance term + the total over `N*items` responses + the same
  parity refinement. Validated against the scrutiny reference (2.74/0.96/63/items=2 → consistent). `supported` is
  now always true; removed the dead frontend "unsupported" branch (rule #5).
- **Why:** GRIMMER shipped single-item-only in inc 127; this finishes it. Errs toward leniency (safe,
  non-accusatory direction).
- **Revert:** restore the `items != 1 → supported=False` guard + the single-item SS formula in `grimmer_test`.

## 2026-06-25 — Increment 128: split 40_app.jsx (relieve the 600-line cap)
- **Files:** NEW `app/frontend/js/04_layout.jsx`; `app/frontend/js/40_app.jsx`, `callosum-app.html`,
  `INCREMENT-128-NOTES.md`.
- **What:** Behavior-preserving refactor — moved the layout helpers (`_loadLayout`/`_saveLayout`/`_clampW`/
  `_beginDrag`/`Divider` + the `LEFT_*`/`RIGHT_*` consts) and a new `useUiPrefs()` hook (theme + axis/scan prefs +
  panel layout + accordion-open + Reading mode) out of `40_app.jsx` into a new early-loading chunk. `40_app.jsx`
  **590 → 514**; `04_layout.jsx` 107.
- **Why:** `40_app.jsx` was at 590/600 (rule-#1 risk flagged since inc 126/127); cleared before the next feature
  lands there. No user-facing change, no API change, no new surface.
- **Revert:** restore the helper block + the inline pref/layout state in `40_app.jsx`; delete `04_layout.jsx`.

## 2026-06-25 — Increment 127: GRIM + GRIMMER data-consistency calculator
<!-- HELP-DOCS-SYNCED: app/backend/help/help_content.md current as of increment 127 (2026-06-25) — added a "Data consistency (GRIM / GRIMMER)" section. Entries ABOVE this line are newer than the last help sync. -->
- **Files:** NEW `app/backend/methods/grim.py`, `app/frontend/js/07_methods_grim.jsx`,
  `.claude/security-audits/2026-06-25_grim.md`, `.claude/qa-routes/route_37_methods_grim.md`,
  `INCREMENT-127-NOTES.md`; `app/backend/api/routers/methods.py`, `app/frontend/styles.css`, `callosum-app.html`,
  `app/backend/help/help_content.md`, `THIRD-PARTY-NOTICES.md`, `tests/{test_grim.py, test_health.py}`.
- **What:** The second GRIM/p-curve "data-detective" METHODS feature — an **assisted, per-value GRIM + GRIMMER
  calculator** (METHODS pane → "Data consistency (GRIM)"): enter a reported mean (+ SD), N, items → is it
  mathematically possible for integer data, with nearest-possible values + caveats + credit/add-to-library.
- **Why:** The user asked for GRIM (via the Lakens catalog). An assisted calculator (not an auto-scanner) is
  reliable + honest — extraction of mean+N+granularity from prose is unreliable. Inherently non-accusatory.
- **Gates:** Principles #9 aligned; audit `2026-06-25_grim.md` PASS; rule #10 route_37 + surface 91 API / 484 FE,
  0 uncovered; credit-the-lineage (THIRD-PARTY-NOTICES + in-context + add-to-library). No DB/migration/egress.
  GRIMMER is items=1 in v1 (multi-item deferred); GRIM supports items.
- **Revert:** `git revert` the inc-127 range, or drop `methods/grim.py` + the endpoint + the METHODS section.

## 2026-06-25 — Increment 126: p-curve (collection-level evidential-value check)
<!-- (prior help-sync marker for inc 126; superseded by the inc-127 marker above) added a "p-curve: evidential value" section. -->
- **Files:** NEW `app/backend/methods/pcurve.py`, `app/frontend/js/29_pcurve.jsx`,
  `.claude/security-audits/2026-06-25_pcurve.md`, `.claude/qa-routes/route_36_methods_pcurve.md`,
  `INCREMENT-126-NOTES.md`; `app/backend/api/{routers/methods.py, app.py}`, `app/frontend/js/{10_pdf_layer,40_app}.jsx`,
  `styles.css`, `callosum-app.html`, `app/backend/help/help_content.md`, `THIRD-PARTY-NOTICES.md`,
  `tests/{test_pcurve.py, test_health.py}`.
- **What:** The first GRIM/p-curve "data-detective" METHODS feature (p-curve first). Select papers → a **p-curve**
  bulk action → an async job (reusing the statcheck extractor) → a modal with the right-skew/binomial statistics +
  a hand-rolled SVG curve + the included tests + coverage + a credit block (add-to-library). Collection-level
  only; never per-paper; never "p-hacked"; the interpretation is the user's.
- **Why:** The user asked for GRIM/p-curve (via the Lakens automated-review catalog); p-curve reuses the proven
  statcheck p-value extraction (low risk). GRIM is the deliberate follow-up.
- **Gates:** Principles #9 aligned; audit `2026-06-25_pcurve.md` PASS; rule #10 route_36 + surface 90 API / 472 FE,
  0 uncovered; credit-the-lineage (THIRD-PARTY-NOTICES + in-context credit + library-add). No persistence/migration,
  no egress. **Note:** `40_app.jsx` now 590/600 — split overdue.
- **Revert:** `git revert` the inc-126 range, or drop `methods/pcurve.py` + the endpoint + the bulk action/modal.

## 2026-06-25 — Increment 124: synthesis evidence-traceable Overview (Part B)
<!-- (prior help-sync marker for inc 124; superseded by the inc-126 marker above) the synthesis-verification section gained an "Overview" paragraph. -->
- **Files:** NEW `app/backend/summarization/overview.py`, `integrations/gemini/overview.py`,
  `alembic/versions/0015_summary_overview.py`, `.claude/security-audits/2026-06-25_synthesis-overview.md`,
  `INCREMENT-124-NOTES.md`; `app/backend/{llm/egress.py, summarization/pipeline.py, persistence/schema.py,
  api/app.py, api/routers/summaries.py, help/help_content.md}`, `app/frontend/js/20_synthesis.jsx`, `styles.css`,
  `callosum-app.html`, `.claude/qa-routes/route_55_synthesis_verification.md`, `tests/{test_summary_overview.py,
  api_helpers.py}`.
- **What:** After a synthesis is generated + verified, a second LLM pass narrativizes ONLY the verified claims
  into a short **Overview** shown above them, where **each Overview sentence links back to the verified claim(s)
  it restates** (per-sentence trace; click → the claim flashes). Stored in a new `summaries.overview_json`
  column; egress-gated (`EgressGatedOverviewGenerator`); claim refs validated ⊆ the verified set + mapped to
  ordinals (citations inherited, never LLM-invented); 0 verified or egress-off → no overview.
- **Why:** Root cause #2 of "synthesis gives no real summary" — there was no synthesis-prose surface. Part B of
  the inc-123/124 design; framed "synthesized from the verified claims below" (traceable, not "unverified"), per
  the user's refinement.
- **Gates:** Principles #9 aligned; audit `2026-06-25_synthesis-overview.md` PASS; rule #10 route_55 extended;
  surface check 88 API / 462 FE, 0 uncovered. Migration head → 0015.
- **Revert:** `git revert` the inc-124 range, or drop the overview pass in `summarize_scope` + the
  `overview` response field + the `OverviewBlock` render.

## 2026-06-25 — Increment 123: synthesis no-query scope prefers content over front matter (Part A)
- **Files:** NEW `app/backend/summarization/chunk_filtering.py`; `app/backend/summarization/pipeline.py`,
  `tests/{test_chunk_filtering,test_summarize_selected}.py`, `INCREMENT-123-NOTES.md`.
- **What:** A conservative `is_front_matter_chunk` classifier + a two-phase `_select_no_query` so the no-query
  papers (and single-paper) synthesis scope feeds real body content, not title-page mastheads/DOIs/author lines.
- **Why:** Root cause #1 of "synthesis gives no real summary, just front matter" (validation summary #7) — the
  old `_round_robin_by_paper(rows)[:top_k]` fed the first chunk of each paper (its masthead). Part A of the
  inc-123/124 synthesis-overview design; Part B (the evidence-traceable Overview) is inc 124.
- **Revert:** restore the `_round_robin_by_paper(rows)[:top_k]` return in `_source_chunks_for_scope`.

## 2026-06-25 — Increment 122: statcheck relocated to a METHODS "Statistics check" section
<!-- HELP-DOCS-SYNCED: app/backend/help/help_content.md current as of increment 122 (2026-06-25) — the "Checking statistics (statcheck)" section's per-paper + library-wide passages were repointed from "Details pane" / "Settings → Statistics check" to "METHODS pane → Statistics check section". Entries ABOVE this line are newer than the last help sync. -->

- **Files:** NEW `app/frontend/js/06_methods_statcheck.jsx`; `app/frontend/js/{40_app,35_settings,25_detail}.jsx`,
  `callosum-app.html`, `.claude/DESIGN.md`, `.claude/qa-routes/{route_33_methods_statcheck,route_30_detail_pane,route_32_viewer_annotations}.md`,
  `app/backend/help/help_content.md`, `INCREMENT-122-NOTES.md`, `RECOVERY-LOG.md`, `.claude/CLAUDE.md`.
- **What:** Moved both statcheck surfaces — the library-wide batch (from `StatcheckSettings` in Settings) and the
  per-paper check (from `StatcheckRow` in the Details pane) — into a dedicated **METHODS accordion section**
  ("Statistics check", `06_methods_statcheck.jsx`, `order: 20`, after DETAILS). Added `onShowStatcheckFlagged` +
  `onStatcheckRan` to `paneCtx`; rewired the header **"⚠ N flagged" chip** refresh from "on Settings close" to
  "on mount + after a batch run". Removed statcheck from Settings and Details; kept the library chip + filter.
  Also swept stray `app/frontend/js/*.jsx.tmp.*` atomic-write orphans (rule #5).
- **Why:** The first real **METHODS** module on the inc-121 pane registry; co-locates the per-paper and
  library-wide statcheck; relieves the `25_detail.jsx` >600-line rule-#1 violation (625 → 579).
- **Honesty posture preserved verbatim** (Principles non-triggering): counts never a composite score; "a prompt
  to look, not a verdict"; non-accusatory; per-test rows open the page at region precision (no fake exact rect).
  Frontend-only — no backend/endpoint/migration/egress change. pytest 437. Surface check 0 uncovered (88/460).
- **Revert:** restore the `StatcheckSettings`/`StatcheckRow` blocks + the Settings-close-keyed chip effect (see
  commits `7bebfbc`/`44c6d76`/`5182419`), or `git revert` the inc-122 range.

## 2026-06-25 — Increment 121: THEORY/METHODS accordion side-panes on a module registry

- **Files:** NEW `app/frontend/js/05_panes.jsx`; `app/frontend/js/{40_app,10_pdf_layer,15_axes,20_synthesis,25_detail}.jsx`,
  `app/frontend/styles.css`, `callosum-app.html`, `.claude/DESIGN.md`, `.claude/qa-routes/route_00_smoke_readonly.md`,
  `app/backend/help/help_content.md`, `tests/qa surface-map (regen)`, `INCREMENT-121-NOTES.md`.
- **What:** Replaced the two fixed side-pane wrappers with **accordions** on an extensible **module registry**
  (`registerPaneSection({id,label,paneId,order,render})` + `<PaneAccordion>`). **Left** = THEORY accordion
  (Axes/Synthesis/Tags, one open at a time, AXES default); **right** = METHODS accordion (Details, with a
  select-a-paper hint). Sections self-register from their chunks; **mount-but-hide** keeps an in-progress synthesis
  alive across a switch; open section persists (`callosum.theoryOpen`/`methodsOpen`). Retired the inc-57 RightPane
  drag-split. **Soft labels** (section headers only; `paneId` is the internal THEORY/METHODS architecture).
  One intentional behavior change: **Tags always shows** (empty-state hint) instead of vanishing — discoverability.
- **Why:** the designated "next major upgrade" (the THEORY/METHODS future-track, UI-shell half) — place tools by
  the user's cognitive task; make the pane sections an additive registry for future METHODS modules.
- **Gate:** frontend-only; no backend/migration/egress; Principles gate non-triggering (behavior-preserving
  arrangement). DESIGN.md §5 added. Verified headed on `:8097` (switch/persist/synthesis-survives/details-on-select,
  0 console errors) + an additivity proof (a dummy chunk's section appeared with zero PaneAccordion edits).
- **Revert:** `git revert` the six inc-121 commits (`8b234d0`/`9022849`/`39508cb`/`0058ac0`/`ce35fb1` + this docs commit).
- **NB:** `25_detail.jsx` was already 625 (>600 pre-inc-121); the Details registration lives in `05_panes.jsx` to
  avoid worsening it — a split is queued (the statcheck→METHODS move will relieve it). **Next (user-queued):**
  (1) statcheck Settings→METHODS accordion section; (2) investigate synthesis showing no text summary.

## 2026-06-24 — Increment 120: QA mechanism — surface-coverage gate + Codex-exec supervisor

- **Files:** NEW `tools/qa/{build_surface_map.py, supervisor.py, _qa_serve.py, route_runner_prompt.md, __init__.py}`;
  `.claude/QA-POLICY.md`; `.claude/qa-routes/{_TEMPLATE.md + 15 route_NN_*.md}`; `.claude/CLAUDE.md` (rule #10 +
  kickoff #10 + layout/reference rows); `.gitignore`; `.github/workflows/ci.yml`; `INCREMENT-120-NOTES.md`.
- **What:** Installed the QA mechanism from `qa_routes.zip` (authored out-of-band): a **computed surface-coverage
  gate** (`build_surface_map.py` — static AST of the routers + JSX scan; `check` diffs vs. the `qa-routes/`
  `qa-coverage` blocks; API hard-gate, FE checklist), a **Codex-`exec` supervisor** that drives each route in a
  seeded throwaway browser and deposits severity-ranked reports to the watched `.claude/qa-inbox/`, and the
  **fixture/policy** that pins it to a disposable seeded DB + asserts the honesty invariants (egress gate,
  coordinate honesty, signal-not-verdict). New **rule #10** + kickoff #10 (triage the inbox). Had **Codex author
  the 13 missing routes** until the gate went green (**88/88 API + 460/460 FE covered**).
- **Why:** turn "no stone unturned" QA into a computed coverage guarantee + drop dev monitoring (Codex executes,
  a Claude session triages the inbox).
- **Verification:** `check` exits 0; `_qa_serve.py` serves a seeded throwaway DB (egress unset) + tears down;
  `supervisor --dry-run` emits a valid codex command; pytest 436 (additive, unchanged); ruff clean (incl. tools/qa).
- **Revert:** `git revert` `c95b791` + this commit; remove `tools/qa/` + `.claude/{QA-POLICY.md,qa-routes/}`.
- **Follow-on (same session):** ran the first **Tier-0** QA pass — clean (honesty invariants held: 0 egress with
  egress off, 0 page errors; no real app bugs). Fixed 3 Windows-portability bugs in the bundled supervisor
  (UTF-8 console, `shutil.which` for the codex shim, prompt-via-stdin — all caught before any credits spent; commit
  `5adc5e6`). Enriched `_seed_library` with a **real-PDF "Renderable Seed Paper"** (`tests/fixtures/seed.pdf`,
  truthful bboxes) + a tag so QA can exercise the viewer + coordinate-honesty + Tags panel, and calibrated
  `route_00` + the `_TEMPLATE` "Seed contract" (commit `ce934ed`; pytest 437; verified headed via `qa_server`).

## 2026-06-24 — Increment 119: My Publications overhaul, SP3 — citing articles & citation counts
- **Files:** `integrations/openalex/author.py`, `app/backend/clustering/my_publications.py`,
  `app/backend/api/routers/my_publications.py`, `app/frontend/js/{10_pdf_layer,31_mypubs_dashboard,33_mypubs_pubs,34_mypubs_citing [new]}.jsx`,
  `app/frontend/styles.css`, `app/backend/help/help_content.md`, `callosum-app.html`,
  `tests/{test_my_publications,test_health}.py`,
  `.claude/docs/specs/2026-06-24-mypubs-sp3-{citing-design,plan}.md`,
  `.claude/security-audits/2026-06-24_mypubs-citing.md`, `INCREMENT-119-NOTES.md`.
- **What:** Final My-Pubs sub-project (#14). Each own-pub card shows its **OpenAlex cited-by count** (verbatim +
  attributed); a **"Most cited"** sort; clicking the count opens a **citing-articles modal** (the papers OpenAlex
  records as citing it — discovery candidates, coverage stated) with per-row **Import** + a confirm-gated **Import
  all** (metadata-only, deduped, into the general library; the PDF stays the OA-acquire lane). Backend: capture the
  OpenAlex work id, `paper_citations` on the dashboard, `GET /my-publications/citing/{work_id}` (cached, capped 100,
  fail-closed) + `POST /my-publications/citing/import`; **Refresh now re-fetches works** so counts/ids stay fresh.
- **Why:** TDL #14 — surface who cites your work and let you pull those papers in.
- **Gate:** Principles gate run (spec §2 — aligned: verbatim+attributed count, candidates not verdicts, human-selected
  metadata-only import, OA-only PDFs); security audit PASS (new OpenAlex `cites:` fetch + 2 endpoints). No migration;
  public-metadata egress only (NOT the Gemini gate).
- **Revert:** `git revert` the six SP3 commits (`e695dd4`, `2cbbfc8`, `be41163`, `26c3ffa`, `d90dc2c`, + this docs commit).
- **NB:** **completes the My Publications overhaul (SP1 inc 117 + SP2 inc 118 + SP3 inc 119 = TDL #1 + #3–18).**

## 2026-06-24 — Increment 118: My Publications overhaul, SP2 — domain organization
<!-- (help sync marker moved to inc 119 above) -->

- **Files:** `app/backend/api/routers/{my_publications,axes}.py`, `app/backend/clustering/my_publications.py`,
  `app/backend/persistence/profile_repo.py`, `app/frontend/js/{15_axes,31_mypubs_dashboard,33_mypubs_pubs}.jsx`,
  `app/frontend/styles.css`, `app/backend/help/help_content.md`, `callosum-app.html`,
  `tests/{test_my_publications,test_axes,test_health}.py`,
  `.claude/docs/specs/2026-06-24-mypubs-sp2-{domains-design,plan}.md`,
  `.claude/security-audits/2026-06-24_mypubs-domain-rename.md`, `INCREMENT-118-NOTES.md`.
- **What:** Organize the My Publications corpus by research domain. A **Group by domain** toggle (dashboard list +
  sidebar axis card) regroups the publications under per-domain headers/subheadings with an **Other** group;
  **starred-first** sorting; **rename domains** inline (pre-suggesting the closest axis name) with names that
  **persist across Re-decompose** by paper-overlap; and **#18** — selecting a domain locks the Overview chart to
  Publications (filtered) and disables the Citations flip. Backend additive: `Domain.paper_ids`, `starred_ids`,
  per-paper `domain` on the my-pubs clusters response, and `POST /my-publications/domains/rename` (local profile-JSON
  edit). No migration, no egress.
- **Why:** TDL #9/#15/#16/#17/#18 — make the own-corpus navigable by research area, in both the dashboard and the
  pinned sidebar card.
- **Revert:** `git revert` the six SP2 commits (`8eb3e52`, `f028939`, `df0ef22`, `1078d42`, `922c063`, + this docs commit).
- **NB:** this docs commit also applies a `ruff format` pass the T1/T2 commits had missed (whitespace-only).

## 2026-06-24 — Increment 117: My Publications overhaul, SP1 — dashboard restructure & publication cards

- **Files:** `integrations/openalex/author.py`, `app/backend/clustering/my_publications.py`,
  `app/backend/api/routers/my_publications.py`, `app/frontend/js/{10_pdf_layer,30_viewer,31_mypubs_dashboard,
  32_mypubs_missing [new],33_mypubs_pubs [new],40_app}.jsx`, `app/frontend/styles.css`,
  `app/backend/help/help_content.md`, `callosum-app.html`, `tests/test_my_publications.py`,
  `.claude/docs/specs/2026-06-24-mypubs-sp1-{restructure-design,plan}.md`, `INCREMENT-117-NOTES.md`.
- **What:** First sub-project of the My Publications overhaul. Restructured the dashboard into author-priority order
  — **Overview** (collapsible 2×2 metrics + one **Publications⇄Citations** flip-chart, last 10 yrs `'NN`) →
  **Research summary** (⭐-only toggle hidden when 0 starred) → **Publications** (axis-scoped library cards via
  `/papers?axis_id`, search/sort + checkbox bulk bar [summarize/export/bibliography/delete] + copy + open, relocated
  Decompose button) → Research domains → **OpenAlex footer card** (as-of provenance, gap, 2-yr mean citedness +
  affiliation + profile link, Refresh, the missing-works **modal** trigger). Extracted a shared `PaperCard` from
  `PaperList`. Backend additive only: `openalex_extra` + `starred_count` on the dashboard response (parsed from the
  already-cached OpenAlex author object — no new endpoint, migration, or egress).
- **Why:** TDL line 1 + #1/#3/#4/#5/#6/#7/#8/#10/#11/#12/#13 — make the author's own corpus a first-class,
  browsable publications library; metrics & pubs first, OpenAlex provenance last.
- **Revert:** `git revert` the six SP1 commits (`870a96b`, `0fcd198`, `abea7a1`, `df3c10d`, `c189f83`, + this docs commit).
- **NB:** increments **109–116** (frontend/UX TDL items incl. the inc-110 PDF page-view) are journaled in
  `RECOVERY-LOG.md`, not folded into this log or the CLAUDE.md footer.

## 2026-06-21 — Increment 108: LibreOffice (UNO) citation adapter — word-processor track, first adapter

- **Files:** NEW `adapters/` tree — `adapters/libreoffice/{callosum_cite.py [the macro], README.md,
  selftest_uno.py [headless harness]}`; `tests/test_libreoffice_adapter.py` (+5); `THIRD-PARTY-NOTICES.md`
  (Zotero `CSL_CITATION` pattern credit); the audit; `INCREMENT-108-NOTES.md`.
- **What:** a drop-in LibreOffice Writer Python macro for cite-while-you-write — insert live citation fields
  (ReferenceMarks carrying CSL-JSON), refresh/restyle/renumber, build/maintain the bibliography, and flatten to
  static text — all riding the inc-107 `POST /citations/render-document`. The adapter places fields; the backend
  citeproc engine formats (so output matches the in-app "Cite as…").
- **Why:** the first piece of the word-processor track that's visible *inside a word processor*; proves the
  render→place→read-back→write-back loop + the field abstraction the Word/Docs adapters reuse.
- **Scope:** client-side, **no server change** (no new endpoint/migration/route/egress; local 127.0.0.1 only); no
  third-party dep (stdlib `urllib` in LO's bundled Python). Verified by the **headless UNO round-trip** (real
  LibreOffice: IEEE `[1]`/`[2]`, APA author-date, flatten preserves text — SELFTEST OK) + 5 pytest pure-logic
  tests. Four UNO traps found+fixed (Hidden-load crash; bib stale-anchor; ReferenceMark write-back deleting the
  mark; stale-collection-ref hang / flatten deleting text). pytest **424** (+5); `ruff` clean. Audit
  `.claude/security-audits/2026-06-21_libreoffice-adapter.md` PASS.
- **Revert:** delete the `adapters/` tree + `tests/test_libreoffice_adapter.py` + the `THIRD-PARTY-NOTICES.md`
  adapter section. (No app code touched.)

## 2026-06-21 — Increment 107: position-aware document-render layer — word-processor track, Phase 2

- **Files:** `app/backend/citations/citeproc_runner.js` (new `mode:"document"` branch), `render.py`
  (`_run_engine`→`_run`; new `render_document`), `app/backend/api/routers/citations.py` (new endpoint + models);
  `tests/{test_citations,test_health}.py`; the audit; `INCREMENT-107-NOTES.md`.
- **What:** `POST /citations/render-document` renders a word-processor document's **ordered citation clusters**
  position-aware via citeproc's `rebuildProcessorState` — numeric renumbering `[1][2][3]`, author-date
  disambiguation `2020a`/`2020b`, + the bibliography. The shared contract every word-processor adapter (LibreOffice
  → Word → Google Docs) will call; the adapter places fields, the engine formats. Self-contained (renders from the
  passed CSL-JSON; no library lookup).
- **Why:** the inc-106 engine renders each cite in isolation (right for a *selection*, wrong for a live document).
  This is the substrate before any LibreOffice client — fully pytest-testable, de-risks render correctness.
- **Scope:** backend-only; **no frontend change** (no rebuild); no new dependency, no egress, no migration; output
  sanitized (`_safe_html`); input capped (clusters/items/total). pytest **419** (+3); `ruff` clean. Audit
  `.claude/security-audits/2026-06-21_citation-render-document.md` PASS.
- **Revert:** drop the `mode:"document"` branch in the runner, `render_document` + the `_run` rename, the
  `/citations/render-document` endpoint + models, and the test + route-allowlist additions.

## 2026-06-21 — Increment 106: citation & bibliography engine (citeproc-js) — word-processor track, Phase 1


- **Files:** NEW `app/backend/citations/` (`render.py`, `citeproc_runner.js`, `csl/{styles,locales}` bundled CSL
  data) + `app/backend/api/routers/citations.py`; `app/backend/api/app.py` (router include); `package.json` +
  `package-lock.json` (citeproc); `25_detail.jsx` (Cite-as), `10_pdf_layer.jsx` + `40_app.jsx` (bulk
  bibliography), `styles.css`; `callosum-app.html`; `tests/{test_citations,test_health}.py`; `THIRD-PARTY-NOTICES.md`;
  the audit; help corpus.
- **What:** formatted citations + bibliographies (APA/MLA/Chicago/IEEE/Nature/Harvard) rendered from
  `papers.csl_json` by **citeproc-js** (Node sidecar) over bundled CSL styles. In-app: Details **"Cite as …"**
  (style dropdown + live sanitized preview + copy) + a bulk **"bibliography…"** `.html` download.
  `GET /citations/styles` + `POST /citations/render`.
- **Why:** the foundation of word-processor integration (the citation engine every adapter rides) — and it closes
  the "no formatted styles" gap inside the app (inc-70 export was machine-readable only).
- **Scope:** new dep `citeproc` (pinned; audit gate → PASS); **no egress** (bundled styles); citeproc HTML
  sanitized server-side before in-app render. pytest **416** (+5); `ruff` clean; opt-in e2e (0 console errors).
- **Revert:** drop the `citations` package + router (+ app.py include), the frontend Cite-as/bibliography wiring,
  `citeproc` from package.json, and the bundled `csl/` data; rebuild.

## 2026-06-21 — Increment 105: default axis cutoff in Settings + a tag source filter (2 chores)

- **Files:** `40_app.jsx` (axisCutoffDefault state + threading), `15_axes.jsx` (AxisItem cutoff fallback + AxesPanel
  key), `35_settings.jsx` (Default-axis-cutoff slider), `10_pdf_layer.jsx` (Sidebar/AxesPanel threading +
  TagsPanel All/Yours/Keywords filter), `styles.css` (`.settings-cutoff`, `.tags-srcfilter`); `callosum-app.html`;
  help corpus.
- **What:** (1) a **Default axis cutoff** slider in Settings → Axes (persisted; a new/unscored axis's re-score
  flipper starts there; per-axis gain still wins). (2) an **All / Yours / Keywords** segmented filter in the
  sidebar Tags panel (filters by the inc-100 tag `source`; shown only when both kinds exist).
- **Why:** the "2 chores" of a fresh patter (carrot = the literature gap-finder, next, plan-mode).
- **Scope:** both **frontend-only** over existing data — no Python, no migration, no egress, no new endpoint.
  pytest **411** unchanged; `ruff` clean; opt-in Playwright smoke (2) passed (0 console errors).
- **Revert:** restore the touched frontend files (drop `axisCutoffDefault` threading + the TagsPanel `src` filter
  + the two CSS blocks); rebuild.

## 2026-06-21 — Tweak: hover outline matches the icon color (gear/help + axis edit/add)

- **Files:** `app/frontend/styles.css` (`.icon-gear:hover`, `.icon-help:hover`, new `.axis-icon-btn:hover`);
  `callosum-app.html`.
- **What:** on hover, the **settings/help** buttons and the axis **edit/add** (and dashboard/eye) buttons now turn
  their **outline the same accent (icon) color** as the svg — `border-color: var(--line-2)` → `var(--accent)` for
  gear/help; a scoped `.axis-icon-btn:hover { border-color: var(--accent) }` for the axis icons. The axis
  **delete** (`.axis-icon-danger`) is unchanged (icon + outline amber — already ideal); the canonical `.btn-icon`
  recipe is untouched (only `.axis-icon-btn` is used in JSX, so the override is scoped).
- **Why:** user request — outline should match the icon color on mouseover (delete already did this).
- **Scope:** CSS-only (tokens; rule #8 — canonical recipe unchanged). pytest unaffected (411).
- **Revert:** restore the three hover rules' `border-color` to `var(--line-2)` / remove the `.axis-icon-btn:hover`.

## 2026-06-21 — Process: future-tracks inbox processed (8 specs filed + 1 principle captured)

- **What:** ran the inbox-processing pass on `.claude/docs/future-tracks-import/` (10 content files + README).
  Moved the **8 capability/build specs** (citation-bibliography engine, Bayesian auditor, LMM auditor,
  citation-equity, CRediT builder, meta-analysis extraction workbench, BYOK provider keys, credit-help backfill)
  → `.claude/docs/future-tracks/`; added them to `future-tracks/README.md` (index) + `INCREMENT-BACKLOG.md`
  (longer-horizon tracks + a near-term credit-backfill maintenance note). Captured the cross-cutting
  **credit-the-lineage principle** into the values layer at **`.claude/CREDIT-THE-LINEAGE.md`** (registered in
  CLAUDE.md's tree + reference-docs table). Left the **parked** `…_acquisitiondeferred.md` (counsel-gated) + the
  inbox `README.md` in place, untouched.
- **Why:** the user dropped 10 md files in the inbox; the documented Phase-8 protocol is audit → fold into the
  backlog/index → move to `future-tracks/` (parked items stay). The future-state characterization had *covered*
  all 9 genuine specs but hadn't *integrated* them — this closes that.
- **Scope:** docs/process only; no app/code/test change. **Open decision flagged:** whether credit-the-lineage
  should be elevated to a hard rule-#9 gate trigger (currently a values-layer commitment, not yet wired); and the
  principle could be folded into `APPROACH-AVOIDANCE.md` instead of a standalone file if preferred.
- **Revert:** move the 8 files back to the inbox + `CREDIT-THE-LINEAGE.md` back; undo the index/backlog/CLAUDE.md
  additions.

## 2026-06-21 — Increment 104: panel min-widths + Spotify pull-to-collapse + sidebar-button reposition

- **Files:** `app/frontend/js/40_app.jsx` (min/collapse constants + init clamps + both divider drag handlers),
  `app/frontend/styles.css` (`.icon-gear`/`.icon-help` positions); `callosum-app.html`.
- **What:** (1) left (AXES) panel min drag width **300px**, right (Synthesis/Details) **415px**; (2) dragging a
  resizer ~80px past its min **auto-collapses** that panel (no chevron); (3) repositioned the header buttons —
  help down 7px / left 4px then both nudged left 15px (`top:19;right:33`), settings to the same height 27px left of
  help (`top:19;right:60`, was top-left); (4) both buttons now show an **always-on outline** (`border: 1px solid currentColor` — the icon
  color at rest), hover look unchanged.
- **Why:** user request (wider, Spotify-like resizable panels + a button-layout tweak).
- **Scope:** frontend-only — no backend/migration/egress. pytest **411** unchanged; `ruff` clean; opt-in
  Playwright smoke (incl. reading-mode panel test) passed (0 console errors). Thresholds + button offsets are
  one-line tunables.
- **Revert:** restore the two `40_app.jsx` divider handlers + init lines (and drop the constants), and the two
  `.icon-*` CSS rules; rebuild.

## 2026-06-21 — Increment 103: per-card "copy BibTeX" clipboard button

- **Files:** `app/frontend/js/10_pdf_layer.jsx` (`PaperCopyButton` + `ClipboardIcon`/`CheckIcon` + render before
  the checkbox), `app/frontend/styles.css` (`.paper-copy` + `.paper-title` padding-right); `callosum-app.html`;
  help corpus.
- **What:** each Library card now shows a small **clipboard SVG button** just left of its checkbox that copies the
  paper's **BibTeX** to the clipboard in one click (icon → ✓ ~1.5s).
- **Why:** inc-98's `.paper { user-select:none }` (which fixed the double-click word-select) removed the ability
  to select/copy card text — this restores a one-click citation copy.
- **Scope:** frontend-only; reuses the tested inc-70 `POST /papers/export {format:"bibtex"}` → `navigator.clipboard`
  (mirrors the Details `CiteRow`); `stopPropagation` so it never selects/opens the card; shown only in the normal
  library `selecting` view. **No backend/endpoint/migration/egress.** pytest **411** unchanged; `ruff` clean;
  opt-in Playwright smoke passed (0 console errors). Also synced the help corpus (per-card copy + Reading mode +
  a stale "chunk count" fix) → `HELP-DOCS-SYNCED` moved to 103.
- **Revert:** remove `PaperCopyButton`/the two icons + the card render line + the two CSS blocks; rebuild.

## 2026-06-21 — Chore: ruff format hygiene pass (pre-existing drift)

- **Files:** `app/backend/api/routers/papers.py`, `app/backend/metadata/citation_import.py`,
  `app/backend/methods/statcheck.py`, `app/backend/persistence/tags_repo.py`, `tests/test_papers.py`,
  `tests/test_citation_import.py`, `tests/test_statcheck.py`.
- **What:** ran `ruff format .` — 7 files had pre-existing formatting drift (compact multi-arg calls from
  incs 91–97 that ruff 0.9.6 expands to one-arg-per-line). Pure formatting, no logic change.
- **Why:** surfaced while adding the inc-102 CI `npm ci` step; CI runs `ruff format --check .`, so this would
  have failed it. CLAUDE.md convention is to run `ruff format .` before committing. (Likely undetected because
  CI billing isn't active yet — a known inc-74 follow-on.)
- **Scope:** formatting only; `ruff check` clean; the reformatted test files re-run green (61 passed). pytest 411.
- **Revert:** the change is mechanical formatting; re-running the prior ruff version would differ — leave as-is.

## 2026-06-21 — Increment 102: precompile the JSX with esbuild (drop in-browser Babel)

- **Files:** NEW `package.json` + `package-lock.json` + `.gitignore` (`node_modules/`); `app/backend/api/frontend.py`
  (`assemble_jsx` + `_transpile_jsx` esbuild + `build_frontend_document`); `app/frontend/index.html` (drop babel
  CDN, plain `<script>`); `app/backend/api/app.py` (live-fallback try/except); `tests/test_frontend_assembly.py`
  + `tests/e2e/test_smoke.py`; `.github/workflows/ci.yml` (setup-node + npm ci); `callosum-app.html`; the audit.
- **What:** the frontend JSX is now **precompiled to plain JS by esbuild at build time** and served as a normal
  `<script>`; the `babel-standalone` CDN + `<script type="text/babel">` runtime transform are gone.
- **Why:** the in-browser Babel transformer emitted two dev-console messages (a "precompile for production"
  warning + a `babel.min.js.map` 404) and cost a ~500KB download — user asked to clear them. (The third console
  line, `XrayWrapper … content-script.js`, is an external browser extension — not callosum.)
- **Scope:** new **build-time** dependency (esbuild 0.28.1, pinned; `npm install`/`npm ci`; audit gate → PASS);
  the **server stays Python-only** (serves the prebuilt file). No app-behavior change (esbuild IIFE preserves the
  shared scope). pytest **411** unchanged; `ruff` clean; **opt-in Playwright smoke passed with 0 console errors**;
  `node --check` on the output clean.
- **Revert:** restore `index.html` (re-add the babel `<script>` + `type="text/babel"`), `frontend.py`
  (concatenate-only `build_frontend_document`), `app.py`, the tests + CI; remove `package.json`/lockfile; rebuild.

## 2026-06-21 — Fix (post-inc-101): double-click no longer word-selects a library card's title

- **Files:** `app/frontend/styles.css` (`.paper` rule), `10_pdf_layer.jsx` (comment), `callosum-app.html`.
- **What:** added `-webkit-user-select: none; user-select: none;` to the `.paper` card so double-clicking a card
  opens the PDF (inc-98) **without** the browser also highlighting the title word under the cursor.
- **Why:** inc-98 made `onDoubleClick` always open but never suppressed the browser's default double-click
  word-selection, so the title flashed highlighted on every open — user-reported.
- **Scope:** frontend-only CSS; interaction property, not a token/color/recipe (no DESIGN.md concern). Trade-off
  (user-confirmed): card text is no longer drag-selectable — it stays copyable in the **Details** pane. Card
  buttons/checkbox unaffected (`user-select` governs text selection only). pytest unchanged **411**; `ruff` clean.
- **Revert:** remove the `user-select: none` line from `.paper` and rebuild.

## 2026-06-21 — Increment 101: Reading mode (one-click distraction-free reader)

- **Files:** `40_app.jsx` (readingMode state + toggle + Esc + `cols`/className), `30_viewer.jsx` (`LibraryFrame`
  `.frame-reading` toggle), `styles.css` (`.frame-reading` + `.app.reading .divider`); `callosum-app.html`.
- **What:** a **⛶ Read** toggle at the right of the center tab bar hides both side panels and their dividers to
  maximize the open PDF; **⤢ Exit** or **Esc** restores the prior layout. Transient (a reload returns to normal).
- **Why:** the carrot of the inc 100–101 patter — a focused reading view, built on the inc-42 collapsible panels.
- **Scope:** frontend-only — no backend/migration/egress/new token (tokens-only CSS, rule #8). pytest **411**
  unchanged; `ruff` clean. Visual QA delegated (no Playwright MCP this session). No help-corpus change (the labeled
  toggle + tooltip are self-evident).
- **Revert:** restore the three frontend files (drop `readingMode`/`toggleReading` + the `.frame-reading` button +
  the two CSS rules) and rebuild.

## 2026-06-21 — Increment 100: statcheck "flagged" header chip + tag-source aesthetic differentiation

- **Files:** `persistence/signals_repo.py` (+`count_statcheck_flagged`), `routers/methods.py` (+`GET
  /methods/statcheck/summary`); `persistence/tags_repo.py` + `routers/papers.py` + `routers/tags.py` (expose tag
  `source`/`import_source`); `00_lib.jsx` (`tagIsImported`/`tagSourceLabel`), `25_detail.jsx`, `10_pdf_layer.jsx`
  (chip + sidebar/Details tag styling), `40_app.jsx` (flagged count + wiring), `styles.css`; `callosum-app.html`;
  `tests/{test_tags,test_statcheck,test_health}.py`; help corpus (tags + statcheck sections).
- **What:** (1) a **⚠ N flagged** chip in the Library header (when the inc-97 batch run flagged any papers) that
  jumps to the flagged-papers filter — a more prominent door to a feature previously only in Settings. (2) Tags
  from different sources (imported Crossref/OpenAlex/Zotero keywords vs the ones you typed) are now distinguished
  by a **muted visual style + a source tooltip** instead of an on-screen label — declutters the Details pane.
- **Why:** user request — surface the library-wide statcheck result more visibly, and "use aesthetic means of
  differentiating tags from different sources to avoid cluttering up the details view."
- **Scope:** both are read-only projections of already-persisted facts (inc-97 signals; inc-73 `import_source`) —
  **no migration, no egress, no LLM, no new dependency.** The tag `source` field is additive (default null).
  pytest **411** (+1 `test_tag_source_exposed_on_responses`; statcheck-summary assertion folded into an existing
  test); `ruff` clean. Principles gate: chip = a more prominent path to a *filter* (no rank/verdict; no-accusation
  boundary holds); tag styling = provenance made visible (inspectability).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `count_statcheck_flagged` +
  the `/methods/statcheck/summary` route + the tag `source` plumbing + the two CSS blocks.

## 2026-06-21 — Increment 99: tests derive the Alembic head, not a hardcoded revision

- **Files:** `tests/api_helpers.py` (new `alembic_head()`), `tests/test_health.py`, `tests/test_startup_migration.py`.
- **What:** added `alembic_head()` (reads the head from the migration scripts) and repointed the two test files'
  head assertions to it, replacing hardcoded `"00NN_…"` revision constants.
- **Why:** a migration that bumps the head used to require editing those constants, and a missed edit only failed
  on the *full* suite (bit inc 91 + inc 98). Now a new migration needs zero test edits for the head.
- **Scope:** tests-only — no app code, no migration, no behavior change. pytest **410** unchanged; `ruff` clean.
- **Revert:** restore the three test files (re-hardcode the head constant).

## 2026-06-21 — Increment 98: double-click-to-open fix + watched library folders

- **Files:** `10_pdf_layer.jsx` (double-click always opens + the "Watched folders…" menu label); NEW
  `persistence/watched_repo.py` + `alembic/versions/0014_watched_folders.py` + `schema.py` (watched_folders table);
  `routers/library.py` (register-on-scan + watched endpoints + rescan worker + shared `_process_scan_result`);
  `27_scan.jsx` (Watched-folders modal), `40_app.jsx` (auto-rescan on launch + toggle), `35_settings.jsx`
  (toggle); `callosum-app.html`; `tests/{test_watched_folders,test_health,test_persistence_core}.py`; help corpus;
  backlog; the audit.
- **What:** (A) **bug** — double-clicking a paper's title selected the word instead of opening (inc-82 guard);
  double-click now always opens. (B) **feature** — Zotero/Mendeley-style **watched folders**: scanning a folder
  watches it, and watched folders are re-scanned automatically on launch (+ a manual "Re-scan all") so new PDFs
  appear without re-adding; manage them in "+ Add → Watched folders…".
- **Why:** the user reported the double-click regression and asked for real folder-watching.
- **Scope:** migration **0014** (additive/guarded); reuses the inc-87 scan (content-dedup → no dupes); only egress
  is Crossref (not the Gemini gate); **no live OS file-watcher** (on-launch + manual). pytest **410** (+2);
  `ruff` clean; audit PASS. Server-side folder read now persisted + auto-read → deployment-gate note extended.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `watched_repo.py` + the
  watched endpoints + the 0014 table + the auto-rescan effect (and restore the inc-82 double-click guard).

## 2026-06-21 — Increment 97: statcheck as a library-wide lens

- **Files:** NEW `app/backend/persistence/signals_repo.py`; `repository.py` (`signal` filter + `SIGNAL_FILTERS` +
  `list_live_paper_ids`), `routers/methods.py` (batch endpoints + worker), `routers/papers.py` (`signal` param),
  `api/app.py` (JobStore); frontend `35_settings.jsx` (`StatcheckSettings`), `40_app.jsx` (`librarySignalFilter`
  view + wiring), `10_pdf_layer.jsx` (banner); `callosum-app.html`; `tests/{test_statcheck,test_health}.py`; help
  corpus; backlog; the audit.
- **What:** a batch **Check all papers** (Settings) persists each paper's statcheck summary to
  `open_science_signals`, and a library **filter** shows only papers with reporting inconsistencies (reached via
  "Show flagged papers" + a banner). The inc-95 per-paper check is unchanged.
- **Why:** the patter's carrot — turn statcheck into whole-library triage.
- **Scope:** a **filter, never a rank/score or a "bad papers" list** (Principles gate run). No migration (the
  table existed since 0001), no egress, no LLM, no new dependency. pytest **408** (+3); `ruff` clean; audit PASS.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `signals_repo.py` + the batch
  endpoints + the `signal` filter + the Settings section + the `librarySignalFilter` view.

## 2026-06-21 — Increment 96: sidebar Tags browser + Details "More → + add field"

- **Files:** `app/frontend/js/10_pdf_layer.jsx` (`TagsPanel` + Sidebar), `40_app.jsx` (`tagRefresh` + wiring),
  `20_synthesis.jsx` + `25_detail.jsx` (`onTagsChanged`; `AddFieldRow` + always-on More), `styles.css`;
  `callosum-app.html`; help corpus.
- **What:** (1) a sidebar **Tags** browser (every tag + count → click to filter the library; live-refreshed on
  per-paper tag edits); (2) a **"+ add field"** control in the Details **More** section (add an arbitrary CSL
  field by hand, via the inc-49 validated `csl` patch).
- **Why:** the patter's two chores — make the tag vocabulary browsable (it was per-paper only), and complete the
  inc-49 "More add-field" deferral (reference-manager parity).
- **Scope:** **frontend-only** (both reuse tested endpoints — `GET /tags`, the `csl` patch); no migration, no
  egress, no new endpoint. pytest **405** unchanged; `ruff` clean.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `TagsPanel` + the
  `tagRefresh`/`onTagsChanged` wiring + `AddFieldRow`.

## 2026-06-21 — Increment 95: statcheck — deterministic statistics-reporting signal

- **Files:** NEW `app/backend/methods/{__init__,statcheck}.py`, NEW `app/backend/api/routers/methods.py`;
  `api/app.py` (register), `requirements.txt` (scipy explicit); frontend `25_detail.jsx` (`StatcheckRow`) +
  `styles.css`; `callosum-app.html`; `tests/{test_statcheck,test_health}.py`; help corpus; backlog; the audit.
- **What:** a Details-pane **"Check statistics"** action that recomputes reported APA NHST p-values (t/F/r/χ²/z)
  from the paper's extracted text and flags reported-vs-computed disagreements (consistent / inconsistent /
  decision-error), with rounding + one-tailed tolerance, per-test rows + counts (no composite score), a
  non-accusatory caveat, and route-to-page. Deterministic, local, no LLM.
- **Why:** the patter's carrot; Track A's v1 — the project's verification ethos on the Methods side.
- **Scope:** `GET /papers/{id}/statcheck` (sync, read-only); `scipy` made explicit (already transitive); no
  migration, no egress, no persistence (deferred to the findings subsystem). pytest **405** (+10); `ruff` clean;
  audit PASS. Principles gate run (Example 3 / value A6; no-accusation veto honored).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `methods/statcheck.py` +
  `routers/methods.py` + the `StatcheckRow` + the scipy line.

## 2026-06-21 — Increment 94: library-header "+ Add ▾" menu + persistent/descending Sort

- **Files:** `app/frontend/js/10_pdf_layer.jsx` (`AddMenu` + Sort options), `app/frontend/js/40_app.jsx` (persist
  `librarySort`), `app/frontend/styles.css` (`.add-menu*`), `app/backend/persistence/repository.py`
  (`title_desc`/`author_desc` sort keys), `callosum-app.html`, `tests/test_papers.py` (+2 sort assertions).
- **What:** (1) folded the header's Scan folder + Import into one **"+ Add ▾"** dropdown (6 header actions → 5);
  (2) the library **Sort** choice now persists across reloads (localStorage) and offers **Title/Author (Z–A)**.
- **Why:** the patter's two chores — declutter the header I flagged last round + remove the sort-resets papercut.
- **Scope:** frontend-only bar one backend allowlist line; no migration/egress/endpoint. pytest **395** unchanged;
  `ruff` clean. Help corpus unchanged (control relocation / sort options aren't described there).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `AddMenu` + the
  `title_desc`/`author_desc` keys + the localStorage persistence.

## 2026-06-21 — Increment 93: BibTeX / RIS / CSL-JSON import

- **Files:** NEW `app/backend/metadata/citation_import.py`, NEW `app/frontend/js/28_import.jsx`;
  `routers/library.py` (import endpoint + worker), `api/app.py` (JobStore), `10_pdf_layer.jsx` (Import button),
  `40_app.jsx` (wiring); `callosum-app.html`; `tests/{test_citation_import,test_health}.py`; help corpus; backlog;
  the security audit.
- **What:** import a BibTeX / RIS / CSL-JSON file → parse (hand-rolled, no new dep) → dedup → create metadata-only
  library papers → embed. The inverse of inc-70 export; reference-manager-first parity (also covers
  Mendeley/EndNote, which export these). An **Import** button in the library header opens a file-picker modal.
- **Why:** the patter's carrot; the only importer was Zotero.
- **Scope:** **entirely local — no egress** (the file is authoritative; no Crossref/Gemini), no multipart/upload
  surface (browser POSTs the file text as JSON), no new dependency, no migration. pytest **395** (+9); `ruff` clean;
  audit PASS. Completes the inc 91–93 patter.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `citation_import.py` +
  `28_import.jsx` + the `/library/import` endpoint + JobStore + the Import button.

## 2026-06-21 — Increment 92: un-dismiss for My-Publications missing works

- **Files:** `persistence/profile_repo.py` (`undismiss_work`), `clustering/my_publications.py`
  (`_dashboard_dismissed_works` + `build_dashboard`), `routers/my_publications.py` (`dismissed_works` field +
  `/works/undismiss` endpoint); frontend `31_mypubs_dashboard.jsx`; `callosum-app.html`;
  `tests/{test_my_publications,test_health}.py`; docs + backlog.
- **What:** completes inc-85's missing-works review queue with an **undo** for Dismiss — the dashboard now shows a
  "Previously dismissed (N)" section, and **Restore** sends a work back to the review queue (`POST
  /my-publications/works/undismiss`).
- **Why:** chore 2 of the patter; the inc-85 deferred follow-on (mirrors inc-67's un-dismiss-duplicates).
- **Scope:** pure `profile.dismissed_work_dois` JSON edit — no migration, no egress (dashboard stays cache-only).
  pytest **386** (+1); `ruff` clean.
- **Revert:** restore the touched files from a `.claude/backups/` snapshot, or drop `undismiss_work` +
  `dismissed_works` + the `/works/undismiss` endpoint + the dashboard section.

## 2026-06-21 — Increment 91: filter the library by type (+ prerequisite module splits)

- **Files:** NEW `app/backend/persistence/annotations_repo.py`, NEW `app/backend/api/routers/paper_files.py`;
  `repository.py`, `routers/papers.py`, `routers/annotations.py`, `api/app.py`; frontend `40_app.jsx`,
  `10_pdf_layer.jsx`, `styles.css`; `callosum-app.html`; `tests/{test_persistence_core,test_health,test_papers}.py`;
  docs + backlog.
- **What:** (1) **Rule-#1 splits** (behavior-preserving): native-annotations data-access moved out of
  `repository.py` (625→538) → `annotations_repo.py`; PDF file-serving moved out of `papers.py` (600→539) →
  `routers/paper_files.py`. (2) **Feature:** filter the library by CSL item type — a Type dropdown in the header,
  an `item_type` query param on `GET /papers` (bound `WHERE`), and a `GET /papers/item-types` facet endpoint
  (distinct live types + counts).
- **Why:** chore 1 of a "2 chores + 1 carrot" patter; adding the filter surfaced that two core files had drifted
  over the 600-line hard limit, so they were modularized first (rule #1).
- **Scope:** no migration, no egress; the PDF route kept its path so the only new route is `/papers/item-types`.
  pytest **385** (+1); `ruff` clean. Backlog reconciled (Unsorted→inc 80, re-score-wrap→inc 86, filter-by-type→inc 91).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot; the splits can be undone by moving the
  functions back and repointing imports, the feature by dropping the `item_type` param + `list_item_types` + the
  dropdown.

## 2026-06-21 — Increment 90: sidebar header redesign (horizontal logo + larger wordmark)

- **Files:** `app/frontend/styles.css` (`.brand`, `.brand h1`, `.icon-help`, `.icon-gear`), `callosum-app.html`
  (rebuilt).
- **What:** the sidebar brand header became a **horizontal lockup** — logo on the left, a **36px** "Callosum"
  wordmark to its right — with the `⚙` settings button in the **top-left** corner and the `?` help button in the
  **top-right**. Was a vertical stack (logo over a 19px wordmark). _(Two same-day tweaks after the user saw it:
  wordmark trimmed ~10% 40→36px; the buttons split back into the two corners — settings left, help right.)_
- **Why:** user request (a more prominent, conventional brand lockup that reclaims vertical space) — matched to
  the user's mockup + alignment guides.
- **Scope:** **CSS-only** (the JSX already supported it — buttons are absolute, `.brand` is a flex container);
  connection-status logo (inc 47) untouched; no new tokens/hexes (serif wordmark + `--ink`, existing `.icon-*`
  recipes). pytest **384** unchanged (frontend-only). Visual QA delegated to the user; font-size 36px is the
  flagged tunable.
- **Revert:** restore `styles.css` from a `.claude/backups/` snapshot, or revert the 4 rules (`.brand` →
  `flex-direction: column`, `.brand h1` → 19px, `.icon-gear` → `right: 14px`, `.icon-help` → `left: 14px`).

## 2026-06-21 — Increment 89: search across all fields + a search-scope dropdown

- **Files:** `app/backend/persistence/repository.py` (`_search_clause` + `search_field` on `list_papers`),
  `app/backend/api/routers/papers.py` (`search_field` query param); frontend `40_app.jsx` (`librarySearchField`
  state + fetch) + `10_pdf_layer.jsx` (scope dropdown + placeholder); `callosum-app.html`; help corpus;
  `tests/test_papers.py` (+1).
- **What:** the library search now covers **all** stored fields (every author, journal, year, DOI, abstract, the
  whole `csl_json` record) instead of only title + first author, and a **scope dropdown** (All / Title / Author /
  Journal) lets the user narrow it. Fixes the bug where searching a co-author's surname found only first-authored
  papers (6 instead of 40).
- **Why:** user request — non-first authors were unsearchable, and the Detail pane has since gained many fields
  the search never covered.
- **Scope:** no migration, no new endpoint (a query param), no egress; the `field` key is an allowlist (rule #3),
  the pattern is bound. pytest **384** (+1); `ruff` clean.
- **Revert:** restore `repository.py`/`papers.py`/the two JSX chunks from a `.claude/backups/` snapshot, or drop
  the `search_field` param + `_search_clause` (reverting to the old title/first-author `OR`).

## 2026-06-21 — Increment 88: search + sort on one row

- **Files:** `app/frontend/js/10_pdf_layer.jsx`, `app/frontend/styles.css`, `callosum-app.html` (rebuilt).
- **What:** moved the **Sort** control inline to the right of the search box (into the `.searchbar` flex row;
  dropped the `.lib-sort-row` wrapper), reclaiming a vertical row in the library pane.
- **Why:** user request (tighter library header).
- **Scope:** frontend-only — no migration/endpoint/egress. pytest **383** unchanged.
- **Revert:** restore `10_pdf_layer.jsx` + `styles.css` from a `.claude/backups/` snapshot.

## 2026-06-21 — Increment 87: scan / refresh a library folder

- **Files:** `app/backend/pdf_processing/library_scan.py` (NEW), `app/backend/api/routers/library.py` (NEW),
  `app/backend/api/app.py` (router + JobStore); frontend `27_scan.jsx` (NEW) + `10_pdf_layer.jsx` +
  `40_app.jsx` + `styles.css`; `callosum-app.html`; help corpus; tests; the security audit.
- **What:** point Callosum at a folder of PDFs → ingest new ones (extract+chunk+embed, Crossref-enriched), skip
  unchanged (checksum dedup), flag removed (`availability="missing"`). Linked in-place (nothing copied). Async
  `POST/GET /library/scan` + a **Scan folder** button → modal in the library head.
- **Why:** the user's top-priority `callosum_TDL.txt` item — the Zotero-free way to keep a library current.
- **Scope:** no migration (reuses `attachments`); 2 new endpoints; only egress is the Crossref DOI lookup (NOT
  the Gemini gate); the folder is read server-side (gate before any hosted deploy — noted). pytest **383** (+3);
  `ruff` clean; audit PASS.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `library_scan.py` + `routers/library.py` +
  the `27_scan.jsx` wiring + the JobStore.

## 2026-06-21 — Increment 86: axis re-score line-wrap fix + button-cleanup resolution

- **Files:** `app/frontend/styles.css`, `.claude/DESIGN.md`, `callosum-app.html` (rebuilt).
- **What:** (1) the axis re-score control row no longer wraps badly — `flex-wrap: nowrap` + a shrinkable Cutoff
  slider keep it on one line at any sidebar width. (2) DESIGN §3 #5 resolved — the remaining divergent buttons
  are intentional distinct variants (folding declined as value-shifting); the safe unification applied was
  tokenizing every `border-radius: 5px` → `var(--radius-sm)` (zero visual change; advances §3 #6).
- **Why:** two UI-polish chores (re-score wrap bug + the .btn-* worklist item).
- **Scope:** frontend-only — no migration/endpoint/egress. pytest **380** unchanged. Visual QA delegated.
- **Revert:** restore `styles.css` from a `.claude/backups/` snapshot.

## 2026-06-21 — Increment 85: My Publications — missing-works review + import

- **Files:** migration `0013_my_publication_dismissed_works.py` + `schema.py` (`profile.dismissed_work_dois`);
  `profile_repo.py` (`dismiss_work`); `clustering/my_publications.py` (`build_dashboard.missing_works`,
  `import_missing_work`, `_add_confirmed_member`); `routers/my_publications.py` (`POST /works/import` +
  `/works/dismiss` + `DashboardResponse.missing_works`); `31_mypubs_dashboard.jsx` + `styles.css`;
  `callosum-app.html`; help corpus; tests; the security audit.
- **What:** the dashboard's indexed-vs-library gap becomes a review queue — OpenAlex works not in your library,
  each with Import (metadata-only, guardrailed to your own indexed works → auto-joins My Pubs) or Dismiss
  (persisted).
- **Why:** the carrot from the user's My-Pubs follow-ups — the 79-indexed vs 40-in-library gap, made actionable.
- **Scope:** migration 0013; 2 new POST endpoints; import reuses the inc-74–76 lane (Crossref DOI lookup, NOT
  the Gemini gate; no PDF/file write). pytest **380** (+3); `ruff` clean; audit PASS.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `import_missing_work`/`_dashboard_missing_works`
  + the 2 endpoints + the dashboard section + migration 0013.

## 2026-06-21 — Increment 84: star key publications + scope the AI summary to starred

- **Files:** migration `0012_my_publication_stars.py` + `schema.py` (`profile.starred_paper_ids`); `profile_repo.py`
  (`set_starred`); `routers/my_publications.py` (`POST /star` + `starred_only` on generate); `routers/axes.py`
  (`ClusterPaperResponse.starred`, my-pubs only); `clustering/my_publications.py` (`my_publication_documents(only_paper_ids=)`);
  `15_axes.jsx` (★ toggle) + `31_mypubs_dashboard.jsx` (⭐-only checkbox) + `styles.css`; `callosum-app.html`;
  help corpus; tests.
- **What:** ⭐ star key publications in the My Pubs sidebar card; a "⭐ only" toggle scopes the AI research
  summary to the starred set.
- **Why:** the chore from the user's My-Pubs follow-ups — focus the summary on flagship work.
- **Scope:** migration 0012; one new endpoint (`POST /star`, local) + a `starred_only` body on generate.
  pytest **377** (+2); `ruff` clean; no new egress (the summary path is the inc-81 gated seam).
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `set_starred` + the `/star` endpoint +
  `starred_only` + the `starred` cluster field + the frontend star UI + migration 0012.

## 2026-06-20 — Increment 83: My Publications Part 2 — domain decomposition (Layer 2)

- **Files:** migration `0011_my_publication_domains.py` + `schema.py` (`profile.research_domains`);
  `profile_repo.py`; `integrations/openalex/author.py` (`AuthorWork.cited_by_count` + `fetch_author_works(refresh=)`);
  `app/backend/clustering/my_publications.py` (`decompose_domains` + `_dashboard_domains`);
  `routers/my_publications.py` (2 endpoints + `DashboardResponse.domains`) + `app.py` (JobStore); frontend
  `31_mypubs_dashboard.jsx` + `styles.css`; `callosum-app.html` (rebuilt); help corpus; tests; the audit.
- **What:** a **Research domains** section on the My Pubs dashboard — cluster your confirmed own-papers into
  domains, show **impact-by-domain** (citation sums), and click a domain to re-filter the publications-by-year
  chart. LLM-free local clustering; the only egress is the OpenAlex works refresh (metadata, not the Gemini gate).
- **Why:** the chosen carrot — My Pubs Part 2 Layer 2 (the spec's differentiator).
- **Scope:** migration 0011; 2 new endpoints (1 read-only GET poll + 1 POST decompose job); stored as isolated
  `profile.research_domains` JSON (NOT child cluster_nodes — avoids double-counting the inc-78/79 card badge).
  pytest **375** (+5); `ruff` clean; audit PASS.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `decompose_domains`/`_dashboard_domains` +
  the 2 endpoints + the `31_mypubs_dashboard.jsx` domains section + migration 0011.

## 2026-06-20 — Increment 82: library-card tidy + double-click/text-select fix

- **Files:** `app/frontend/js/10_pdf_layer.jsx`, `callosum-app.html` (rebuilt).
- **What:** (1) dropped the "N chunks" chip from library cards (processing-internal, not bibliographic);
  (2) a card's double-click opens the PDF only when it didn't select text (`getSelection().isCollapsed`), so
  double-clicking a title word selects it instead of opening.
- **Why:** two `callosum_TDL.txt` UX chores — cleaner cards + stop double-click-to-open hijacking text selection.
- **Scope:** frontend-only — no migration/endpoint/egress/CSS. pytest **370** unchanged.
- **Revert:** restore the chunks chip + the unconditional `onDoubleClick` in `10_pdf_layer.jsx`.

## 2026-06-20 — Increment 81: My Publications Part 2 — the impact dashboard (Layer 1)

- **Files:** migration `0010_my_publications_summary.py` + `schema.py` (`profile.research_summary`);
  `integrations/openalex/author.py` (enriched `ResolvedAuthor` + cache-only `cached_author`);
  `app/backend/clustering/my_publications.py` (`build_dashboard` + `my_publication_documents`);
  `integrations/gemini/research_summary.py` + `app/backend/llm/egress.py` (egress seam) + `app.py` wiring;
  `app/backend/api/routers/my_publications.py` (3 endpoints); `profile_repo.py`; frontend
  `31_mypubs_dashboard.jsx` + `40_app.jsx`/`30_viewer.jsx`/`15_axes.jsx`/`10_pdf_layer.jsx`/`styles.css`;
  `callosum-app.html` (rebuilt); help corpus; tests; the security audit.
- **What:** a 📊 impact **dashboard tab** for the My Publications axis — headline OpenAlex metrics, a
  publications-by-year SVG chart (+ citations-by-year), the indexed-vs-library gap, and an editable AI research
  summary. The dashboard read is **cache-only / egress-free** (gated on a prior Settings→Refresh); the AI
  summary is the only egress (library text → the `CALLOSUM_ALLOW_DATA_EGRESS` gate at the inc-58 seam; off → 503).
- **Why:** the chosen "carrot" — make the user's own corpus a first-class impact surface (My Pubs Part 2,
  Layer 1; Layers 2–4 deferred).
- **Scope:** migration 0010 (additive); 3 new endpoints (1 read-only GET + generate POST + persist PUT); a new
  egress path (the summary), gated. pytest **370** (+8); `ruff` clean; audit PASS.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop the 3 endpoints + `build_dashboard` +
  `research_summary.py` + the `31_mypubs_dashboard.jsx` wiring + migration 0010.

## 2026-06-20 — Increment 80: the "Unsorted" library view (needs-review filter)

- **Files:** `app/backend/persistence/repository.py`, `app/backend/api/routers/papers.py`,
  `app/frontend/js/40_app.jsx`, `app/frontend/js/10_pdf_layer.jsx`, `tests/test_papers.py`,
  `app/backend/help/help_content.md`, `callosum-app.html` (rebuilt).
- **What:** an **Unsorted** toggle in the Library header (+ a clearable banner) that filters to papers whose
  metadata still needs review — raw PDF scaffolds, Crossref-unresolved imports, and papers with no recorded
  source. Backend: a `needs_review` query param on `GET /papers` → `list_papers(needs_review=…)` filters
  `imported_source IN ("pdf-scaffold","crossref-unresolved") OR IS NULL` (local allowlist, bound-param). A view
  like Trash (clears axis/tag filters) but keeps checkbox-select on for bulk re-resolve/export/delete.
- **Why:** surface unresolved/under-catalogued papers instead of letting them disappear into the library
  ("silence is not a certificate"); the chosen "UNSORTED cluster" chore.
- **Scope:** read-only query param — no migration, no new endpoint, no egress. pytest **362** (+1); `ruff` clean.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `needs_review` from `list_papers` + the router
  and the `libraryNeedsReview` wiring from the two frontend chunks.

## 2026-06-20 — Increment 79: count badge subtracts hidden uncertain papers

- **Files:** `app/backend/clustering/axis_assignments.py`, `app/backend/api/routers/axes.py`,
  `app/frontend/js/15_axes.jsx`, `tests/test_axes.py`, `callosum-app.html` (rebuilt).
- **What:** when an axis is in the assigned/manual-only view (inc-51 👁 toggle / inc-77 Settings default), its
  count badge now shows the **visible** count (total − uncertain) instead of the full assignment count, with a
  tooltip noting how many uncertain are hidden. `axis_score_state(cutoff=…)` returns a new `uncertain_count`
  (scored `confidence < cutoff`); `AxisResponse.uncertain_count` exposes it; the frontend subtracts it per the
  per-axis view state.
- **Why:** the badge number should match what the list actually shows once uncertain papers are hidden (user
  nomination).
- **Scope:** additive read-only field on the existing `/axes` response — no migration, no new endpoint, no egress.
  pytest **361** (assertions added to two existing axis tests, count unchanged); `ruff` clean.
- **Revert:** restore from a `.claude/backups/` snapshot, or drop `uncertain_count` from `AxisResponse` +
  `axis_score_state` and revert the badge to `axis.assignment_count`.

> Also committed earlier this session as small **unnumbered UI chores**: a consistent indeterminate
> `ProgressBar` wired into the long async jobs (axis score / suggest / duplicates / synthesis / acquire-OA /
> wanted re-check / my-pubs refresh); moving the My Publications card below the filter/sort controls; bumping
> inter-axis-card spacing 2→5px; and the CI Node-24 action bumps (checkout@v5 / setup-python@v6).

## 2026-06-20 — CI fix: pin ruff + the web stack + apply ruff format (CI now green)

- **Result:** both CI jobs **green** — `lint-and-test` ✓ + `e2e-smoke` ✓ (browser smoke, 0 console errors).
- **Two unpinned-dep drifts**, both first exposed once the billing lock was cleared (CI had never run before):
  (1) **ruff** resolved to 0.15.18 vs local 0.9.6 → I001 import-ordering + format diffs; (2) **fastapi/starlette**
  resolved to 0.138/1.x vs local 0.115.8/0.45.3, and **starlette 1.0 restructured routing** → the route-surface
  introspection test (`test_api_exposes_only_read_only_get_routes`) saw only `/` (endpoints worked; 360 passed).
- **Fix:** pin `ruff==0.9.6` (`requirements-dev.txt`) + `ruff format .` (12 files, cosmetic); pin
  `fastapi==0.115.8` + `starlette==0.45.3` (`requirements.txt`). CI now installs the tested versions.
- **Non-blocking:** a Node-20 deprecation **warning** on `actions/checkout@v4` + `actions/setup-python@v5`
  (GitHub runs them on Node 24) — bump to checkout@v5/setup-python@v6 whenever; not a failure.
- **Follow-up:** a full lockfile (uv) / exact pins of the rest of the toolchain is the deferred *harness
  hardening* track; this pinned only the two tools that broke.
- **Revert:** restore from a `.claude/backups/` snapshot.

## 2026-06-20 — Increment 78: My Publications — the auto-axis of your own papers (Part 1)

- **What:** a pinned, OpenAlex-resolved, **LLM-free** axis of the researcher's own papers. Set a **profile**
  (name / published-name variants / ORCID) in Settings → **Refresh** resolves via OpenAlex (ORCID-first) →
  DOI/ORCID matches become **confirmed members**, name-only matches become **candidates** you ✓ confirm / ✕
  reject (**persisted** — a rejection never re-appears, a confirmation survives re-matching). An **import hook**
  adds new matching papers incrementally; the pinned 📄 card reuses `AxisItem` branched on the new `axes.kind`.
- **Why:** the satisfying personal feature — your own corpus as a first-class lens; the foundation for a future
  impact dashboard (Part 2, deferred).
- **Files:** migration **0009** (`axes.kind` + `profile` + `my_publication_decisions`) + `schema.py`;
  `integrations/openalex/author.py` (`OpenAlexAuthorClient`, fail-closed + cached); `persistence/profile_repo.py`;
  `clustering/my_publications.py` (resolver + cache-based import hook); `metadata/enrichment.py` (the guarded
  hook); `routers/my_publications.py` + `app.py` wiring + `AxisResponse.kind`; frontend `35_settings.jsx`
  (profile section), `15_axes.jsx` (pinned card + kind branch + ✓/× → `/decide`), `40_app.jsx`, `00_lib.jsx`
  (`apiPut`), `styles.css`; rebuilt `callosum-app.html`.
- **Principles / egress:** facts-vs-candidates + confirm-and-learn; **no model tokens**; OpenAlex author lookup
  is **metadata egress (public identifiers), NOT the Gemini gate**; strictly additive (the import hook is a
  guarded no-op when unused). Audit `.claude/security-audits/2026-06-20_my-publications.md` — **PASS**.
- **Verify:** `ruff` clean; `pytest` **361 passed, 1 skipped** (+14); migration head **0009**; route surface
  +`/my-publications/*`. Notes: `INCREMENT-78-NOTES.md`. Live OpenAlex resolution delegated to the user (needs
  their name/ORCID).
- **NEXT:** Part 2 — the impact dashboard tab (charts / citation graph / prospection), deferred.
- **Revert:** restore from a `.claude/backups/` snapshot; no down-migration (0009 is additive).

## 2026-06-20 — Increment 77: hide uncertain axis papers by default (Settings)

- **What:** the inc-51 per-axis 👁 hide-uncertain view can now be the **default** via a new **Settings → Axes**
  toggle; axis cards start in the assigned/manual-only view and surface uncertain papers on demand. Persisted to
  `localStorage["callosum.hideUncertainDefault"]` (mirrors the theme pattern).
- **Why:** a backlog quick-win — declutter the axes panel by default for users who treat uncertain papers as noise.
- **Files:** `35_settings.jsx` (the toggle row), `40_app.jsx` (state + persist; threaded to Sidebar + the
  SettingsModal), `10_pdf_layer.jsx` (Sidebar pass-through), `15_axes.jsx` (AxisItem initial `hideUncertain` reads
  the default; AxesPanel keys each card on it so a toggle remounts them live), `styles.css` (`.settings-sub`);
  rebuilt `callosum-app.html`.
- **Verify:** frontend-only; `pytest` **347** unchanged; **visual check delegated to the user** (no in-repo
  browser this session) — Settings → Axes → toggle on; expanded cards hide uncertain; persists across reload.
- **Revert:** restore from a `.claude/backups/` snapshot.

## 2026-06-20 — Backlog split: open vs closed

- **What:** split `INCREMENT-BACKLOG.md` so the open queue stays scannable — shipped/closed `[x]` items moved
  to a new **`INCREMENT-BACKLOG-DONE.md`** archive (what landed + which increment); `INCREMENT-BACKLOG.md` now
  holds **open `[ ]` items only** (+ the guiding-principle intro + a pointer to the archive). Also refreshed a
  few stale lines (Crossref-subject tags shipped inc 73; Track-D acquisition largely shipped inc 74–76).
- **Why:** a session no longer has to read past ~250 lines of finished work to see what remains (user's idea).
- **Files:** `INCREMENT-BACKLOG.md` (rewritten open-only), `INCREMENT-BACKLOG-DONE.md` (new), `docs/README.md`
  + `CLAUDE.md` reference table (both repointed).
- **Verify:** docs-only; no code/test change.
- **Revert:** restore from a `.claude/backups/` snapshot; the prior combined backlog is in Dropbox history.

## 2026-06-20 — Phase 8: future-tracks watched-inbox auto-rule (+ folded 2 pending specs)

- **What:** the release-readiness arc's final phase. A **session-kickoff watch rule** (CLAUDE.md Session kickoff
  #9) makes a fresh session check `.claude/docs/future-tracks-import/` on its own — anything beyond its README +
  the README's **Parked** list is unprocessed input to surface to the user and handle per the inbox README
  (genuine track → gate-frame → fold into the backlog + `future-tracks/` index → **move**; meta directive →
  action + remove; counsel-gated → leave **parked**, never published).
- **Why:** the inbox existed but relied on the user pointing the assistant at it; now a fresh session notices a
  non-empty inbox without being told.
- **Ran the rule once:** folded the two pending specs — **PUBLISHERS (where-to-submit METHODS tool)** + its
  **first-use choice gate** — into `INCREMENT-BACKLOG.md` + the `future-tracks/README.md` index, and **moved**
  them from the inbox to `future-tracks/`. Both are principles-aligned (facts-not-verdicts, no composite score,
  **no "predatory" label** [A-A no-accusation], local-only / never-transmitted, equity first-class) and carried
  explicit "capture into the backlog" dispositions. The counsel-gated **acquisitiondeferred** spec stays
  **parked** in the gitignored inbox (named in the README's Parked list — never folded or published).
- **Files:** `.claude/CLAUDE.md` (Session kickoff #9 + directory-layout note), `future-tracks-import/README.md`
  (rule-landed + Parked list; local-only), `docs/README.md`, `future-tracks/README.md` (+2 index rows),
  `INCREMENT-BACKLOG.md` (+1 entry); moved 2 specs; swept a stray `*.tmp.*` inbox orphan.
- **Verify:** docs-only — no code/test/schema change (pytest unaffected at 347). The inbox now sits at its README
  + the parked spec. **This closes the release-readiness arc (Phases 1–8).**
- **Revert:** restore from a `.claude/backups/` snapshot; move the 2 specs back to the inbox to un-fold.

## 2026-06-20 — Increment 76: literature acquisition — the wanted list + OA re-check + coverage (C)

- **What:** completes the acquisition arc's *track* loop — a persistent **wanted list** of papers you want an
  OA copy of (unified: auto-includes PDF-less library papers AND external papers you add by DOI), a manual
  async **Re-check OA** job that runs the resolver cascade over the list and **auto-acquires** any authorized
  copy, and a **coverage readout**. Opened from a **Wanted** button in the library head.
- **Why:** turns the per-paper acquire into a standing "fill my gaps" workflow + a way to watch for copies of
  papers you don't own yet (preprints get published, embargoes lift, repositories deposit).
- **How:** `wanted_items` table (migration **0008**; `paper_id` set = library, NULL = external w/ doi/pmid/title).
  The re-check service `acquisition/wanted.py::run_recheck` (kept out of the router → directly testable) resolves
  each open want through the **same `ResolverRegistry`** and on a hit downloads + imports — library wants fill
  the paper; external wants `create_paper` then `import_oa_pdf` (enriches from Crossref). OA-only is **free +
  structural** (registry-only → no non-OA/arbitrary-URL path, test-pinned); external wants need a doi/pmid
  (title-only → skipped `needs-id`, never a fuzzy mint); per-item errors never abort a run; a logged per-run cap.
- **Files:** `persistence/wanted_repo.py` + `schema.py`/migration 0008; `acquisition/wanted.py`;
  `routers/wanted.py` (`GET/POST/DELETE /wanted`, `POST /wanted/sync-library`, `GET /wanted/coverage`, async
  `POST /wanted/recheck` + poll) + `app.py` wiring (`wanted_jobs` + an `acquire_registry` test seam);
  `26_wanted.jsx` + a **Wanted** button in `10_pdf_layer.jsx` + `40_app.jsx`; rebuilt `callosum-app.html`.
- **Gates:** security audit `.claude/security-audits/2026-06-20_wanted-list.md` — **PASS** (OA-only structural,
  input validation, no fuzzy-mint, bulk-fetch politeness, bound-param, no new dep, no new egress).
- **Verify:** `ruff` clean; `pytest` **347 passed, 1 skipped** (+13); migration head `0008`; route surface
  extended with `/wanted*`. Notes: `INCREMENT-76-NOTES.md`. **Completes Acquisition A/B/C.**
- **Revert:** restore touched files from a `.claude/backups/` snapshot; no down-migration by design (the
  `wanted_items` table is additive + inert if unused).

## 2026-06-20 — Increment 75: literature acquisition — fan out the resolver cascade (B)

- **What:** the inc-74 OA lane gains a **7-source resolver cascade** (gold→green→preprint, first authorized
  copy wins) behind the unchanged `OaLocation` seam: OpenAlex (primary) → **DOAJ** → **Europe PMC** →
  **Crossref-OA** → **CORE** → **arXiv** → **bioRxiv/medRxiv** → **OSF/PsyArXiv**. Now a PDF-less paper has many
  authorized OA sources tried in turn, not just OpenAlex.
- **Why:** OpenAlex misses copies (new preprints, DOAJ gold, repository green, Europe PMC OA); the cascade
  fills the gaps while keeping OA judgment with the databases.
- **How (additive to a proven seam):** each source = the OpenAlex-adapter shape — an `integrations/<source>/`
  client (injectable `fetcher` Protocol, `external_api_cache` under a distinct provider, `lookup_oa →
  OaLocation|None`, fail-closed, https-only) + a thin `resolvers/<source>_resolver.py` + one `register(...)` in
  `build_default_registry`. The `resolve()` loop is untouched. OA-ness stays each database's assertion — a
  source with no honest https direct-PDF returns None (DOAJ needs a real PDF link; Europe PMC needs
  `isOpenAccess=Y`; Crossref-OA needs a registered license → CC=gold else bronze; never a guess).
- **Files:** `integrations/api_cache.py` (shared cache helper) + `integrations/{doaj,europepmc,core,arxiv,
  biorxiv,osf}/` + `integrations/crossref/oa.py`; `app/backend/acquisition/resolvers/{doaj,europepmc,crossref,
  core,arxiv,biorxiv,osf}_resolver.py` + the `build_default_registry` cascade; help corpus +
  "Acquiring an open-access copy" section.
- **Secrets:** **CORE** uses `CALLOSUM_CORE_API_KEY` (env only; Bearer header, never in a URL/cache/log;
  **absent → silent no-op**). The key value is in no file/code/doc/git. (Rotate it after testing — pasted in chat.)
- **No new dependency:** arXiv's Atom id is read with a targeted regex, **not** a stdlib XML parser (XXE/entity
  surface on untrusted input, rule #4). No new endpoint, no migration (head stays 0007), no frontend change.
- **Gates:** security audit `.claude/security-audits/2026-06-20_oa-acquisition-b.md` — **PASS** (per-source
  OA-assertion delegation, https/SSRF, CORE key handling, fail-closed, no new dep).
- **Verify:** `ruff` clean; `pytest` **334 passed, 1 skipped** (+31 hermetic per-source + cascade + structural).
  Notes: `INCREMENT-75-NOTES.md`.
- **NEXT:** Increment C (wanted-list + an OA-DB-only re-check job + a coverage readout).
- **Revert:** restore touched files from a `.claude/backups/` snapshot; no migration to undo.

## 2026-06-20 — Increment 74: literature acquisition — the legally-clear open-access lane (A)

- **What:** the keystone of the *track → acquire → read → interrogate → cite* ecosystem (**clean lane only** —
  the legally-ambiguous lane is deferred/counsel-gated, not built or scaffolded). A per-paper **"Acquire OA
  copy"** button on a PDF-less paper resolves it (DOI/PMID/title) → an **OpenAlex-asserted authorized
  open-access** PDF → downloads + validates → imports locally as a **`managed`** attachment named per the
  library convention (`Authors - Year - Venue.pdf`) + labeled OA color/version/source (bronze flagged unstable).
- **Why:** turns callosum from a reference manager into a full acquire→cite ecosystem, while keeping OA
  judgment with the databases (realizes the A8 access-equity value; honors the no-paywall-circumvention veto).
- **Bright lines enforced structurally** (not by convention): the `OaLocation` seam — required OA color (**no
  "closed" member**), the downloader takes an `OaLocation` not a URL → **no arbitrary/non-OA fetch is
  expressible**; OA-ness delegated to OpenAlex; fetched copies local-only. Same idea as the inc-58 egress gate.
- **Files:** `app/backend/acquisition/{registry,fetch}.py` + `resolvers/openalex_resolver.py`;
  `integrations/openalex/adapter.py`; `app/backend/pdf_processing/ingest.py` (extracted reusable
  `attach_pdf_to_paper`, behavior-preserving); migration **0007** + `schema.py` +
  `persistence/acquisition_repo.py` + `AttachmentResponse` OA fields; `app/backend/api/routers/acquisition.py`
  (async `POST /papers/{id}/acquire-oa` + `GET /papers/acquire-oa/{job_id}`, included before `papers.router`) +
  `app.py` wiring (`openalex_client` + `acquire_jobs`); `25_detail.jsx` button + OA chips + `styles.css` +
  rebuilt `callosum-app.html`. New env: `CALLOSUM_OPENALEX_MAILTO` (polite pool), `CALLOSUM_LIBRARY_DIR`
  (managed dir, default `library/`).
- **Gates:** Principles + values gate — clean pass. Security audit
  `.claude/security-audits/2026-06-20_oa-acquisition.md` — **PASS** (SSRF guard, 80 MiB size cap, PDF
  magic + PyMuPDF validation, structural OA-only, no new dependency, polite-pool/cache).
- **Verify:** `ruff` clean; `pytest` **303 passed, 1 skipped** (+24); e2e smoke green; migration head `0007`.
  Notes: `INCREMENT-74-NOTES.md`.
- **Help-docs:** ⚠️ the served help corpus does **not** yet cover acquisition — add an "Acquiring open-access
  copies" section (this entry sits above the `HELP-DOCS-SYNCED` marker → flagged for review).
- **NEXT:** Increment B (resolver cascade — DOAJ/CORE/arXiv·bioRxiv·PsyArXiv·PMC/Crossref) then C (wanted-list
  + OA-only re-check + coverage).
- **Revert:** restore the touched files from a `.claude/backups/` snapshot; no down-migration by design — the
  0007 columns are additive nullable and inert if unused.

## 2026-06-20 — Phase 7: published to GitHub + follow-up (inbox 3rd batch, README badges)

- **PUBLISHED:** `https://github.com/cliffworkman/callosum` (public, AGPL-3.0), initial commit `58c4ce3`,
  307 files, **verified secret-free** (the `git init` secret-gate caught + fixed a `.gitignore` inline-comment
  bug that had leaked `callosum_TDL.txt` into staging; remote-tree re-check clean). Push needed two fixes: the
  `workflow` token scope (`gh auth refresh -s workflow`) and the git credential helper (`gh auth setup-git` →
  push as the active `cliffworkman` account instead of the cached personal account). **CI is configured but
  blocked by a GitHub account billing lock** ("account locked due to a billing issue") — not a code/config
  issue; resolve at github.com/settings/billing, then re-run.
- **Local prep:** `LICENSE` (verbatim AGPL-3.0), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/`
  (`workflows/ci.yml` = ruff + pytest + the opt-in e2e job; PR template; bug/feature issue templates;
  `CODEOWNERS` → `@cliffworkman`), `.gitignore` finalized (+ `callosum_TDL.txt`).
- **Inbox (3rd batch) processed:** filed two **process/dev-infra roadmaps** → `future-tracks/`
  (`harnesshardening.md` = post-git hardening — uv / pre-commit / CI-ratchet / `staged-harnesses/` registry /
  branch protection / repo furniture; `readmescopeaudit.md` = expand the README into a full contributor front
  door) + indexed them + captured both in a new backlog section *Dev-infra & repo hardening (post-git)*.
  Removed the re-synced already-actioned `approachavoidanceharness.md` dupe again. Inbox empty.
- **README badges:** added CI-status + AGPL-3.0 license badges.
- **Verify:** repo live + public; remote tree secret-clean; follow-up commit pushed.

## 2026-06-20 — Phase 6 (cont.): scrubbed key values out of the backup zips (user-requested)

- Removed the key-bearing entry `.claude/GEMINI_API.txt` from all **16** affected backup zips via a **validated
  atomic rewrite** (each temp zip `testzip`-checked before `os.replace`, with a lock retry; 0 corrupt). Re-scan of
  all **43** zips' contents = **0 key-pattern matches**. With the `.gitignore` rules + the `git check-ignore`
  proof, the backups now carry no secrets and cannot reach GitHub.
- **Key rotation** (the 4 keys still in Dropbox history) was added to `INCREMENT-BACKLOG.md` → *Security follow-up*
  as **non-blocking**, at the user's request.
- **Files:** the 16 `.claude/backups/callosum_claudecode_inc{43–48,64–73}.zip` (gitignored; never committed).
- **Verify:** content re-scan = 0 matches; all 43 zips pass `testzip`.

## 2026-06-20 — Phase 6 (cont.): backups secret exposure verified + .gitignore hardened (user-flagged)

- **User flagged** that `.claude/backups/` zips predate the keys→`.env` move and could carry secrets. Verified:
  scanning zip **contents** found the 4 key values in **16 backup zips** (inc43–48 ×1, inc64–73 ×4) — embedded in
  the **old `.claude/GEMINI_API.txt`** filename (which predated `GEMINI_API_KEYS.md`, so the earlier name-only
  check missed it). **The live tree is clean** (only `.env`).
- **GitHub path neutralized + PROVEN.** `.gitignore` already excluded `.claude/backups/`; hardened further with
  `*.zip`, `*GEMINI_API*` (catches the old filename if Dropbox resurrects it), and `*.key`. A throwaway
  `git init` + **`git check-ignore`** confirmed `.claude/backups/`, every `*.zip`, `.env`, and the key files are
  ignored; the throwaway `.git/` was removed (working tree is not a repo). → **the keys cannot reach GitHub.**
- **Residual (local/Dropbox only):** the keys persist in those 16 local zips + Dropbox version history →
  **key rotation RECOMMENDED** (revoke + reissue in Google AI Studio, update `.env`) as the only way to neutralize
  copies outside git. Recorded in the security audit.
- **Files:** `.gitignore` (`*.zip` / `*GEMINI_API*` / `*.key`); `.claude/security-audits/2026-06-20_pre-github-fullsweep.md`.
- **Verify:** `git check-ignore` PASS for all secret-bearing paths; live-tree sweep clean.

## 2026-06-20 — Phase 6 (cont.): 2nd inbox round + codex doc-refresh accepted

- **Codex doc-refresh reviewed + accepted.** The 7 refreshed `docs/*.md` (architecture, data-contracts,
  product-scope, ux-scope, risk-register, glossary, docs-README) verified accurate against the code — they even
  capture the *contrasted* (product term) vs `contradicted` (storage status) nuance and flag the PyMuPDF-AGPL
  redistribution risk; no overclaiming. (`build-log.md` left as a historical record.)
- **2nd inbox round** (the user dropped more material mid-session): **Research-impact analytics** track folded →
  `future-tracks/` + the index + a Longer-horizon backlog bullet (opt-in, local-first, **commons**; HSR-grade
  consent; Project A = zero-egress instrumentation seam + personal dashboard near-term, Project B = far-future
  gated). The re-synced `approachavoidanceharness.md` (already actioned in the 1st round) was removed again — its
  reappearance is **Dropbox restoring my earlier delete**; if it recurs, delete it from Dropbox so the delete
  propagates. Inbox empty again.
- **Files:** moved `…_researchimpactanalytics.md` → `future-tracks/`; `future-tracks/README.md`;
  `INCREMENT-BACKLOG.md`.
- **Verify:** docs-only; `pytest` unaffected (279 passed, 1 skipped).

## 2026-06-20 — Phase 6 (cont.): stdlib .env auto-loader; archived/refreshed stale planning docs

- **.env auto-loader (functional completion of the keys relocation).** `startup.load_local_env()` (+ pure,
  tested `_parse_dotenv`) populates the process env from a gitignored `.env` for any **unset** key (an exported
  shell var always wins — handy for swapping BYO test keys); called once in `app.py` before the default
  `create_app()`. **Skipped under pytest** (guarded on `"pytest" in sys.modules`) so the suite stays hermetic and
  never ingests a real `.env`. No new dependency (stdlib `KEY=VALUE` parser; `#` comments + quotes handled).
  Tested by `tests/test_env_loader.py` (+4). So `.env` now "just works": set `GOOGLE_API_KEY` there + run.
- **Archived stale planning docs.** `roadmap.md` (stale since ~inc 7) + `backlog-future-tracks.md` (superseded by
  `future-tracks/`) → `.claude/deprecated/`; the reference rows in CLAUDE.md + the INCREMENT-BACKLOG scope note
  were redirected. The 7 still-useful planning docs (architecture / data-contracts / product-scope / ux-scope /
  risk-register / glossary / docs-README) were **refreshed to current reality via `codex exec`, reviewed against
  the code** (same pattern as the Phase-3 README refresh).
- **Files:** `app/backend/api/startup.py` (+ loader), `app/backend/api/app.py` (call it),
  `tests/test_env_loader.py` (new); moved `roadmap.md` + `backlog-future-tracks.md` → `deprecated/`; refreshed
  the 7 `docs/*.md`; `CLAUDE.md` + `INCREMENT-BACKLOG.md` reference updates.
- **Verify:** `ruff` clean; `pytest` → **279 passed, 1 skipped** (+4 env-loader).

## 2026-06-20 — Phase 6: Gemini API keys relocated to .env (security gate)

- **What:** moved the **4** Gemini keys (newer `AQ.*` format) from `.claude/GEMINI_API_KEYS.md` → a **gitignored
  `.env`** (`GOOGLE_API_KEY` + 3 alternates for BYO-key testing); **deleted** the md; hardened `.gitignore` to
  exclude `.env` / `.env.*` / the md + `.ruff_cache/` / `.playwright-mcp/` / `*.tmp.*` / `library/` +
  `.claude/{backups,deprecated,plans}`.
- **How (no leak):** a masking Python script did the read→write — **no key value was ever read or printed** to
  the transcript (only counts + masked structure). Whole-tree secret sweep (`AQ.*` / `AIza*` patterns) = **clean**
  (only `.env`, which is gitignored; binary backup zips are skipped by grep + are gitignored).
- **Note:** the app reads `GOOGLE_API_KEY` from the **process env** and does **not** auto-load `.env` yet — so the
  run workflow is unchanged (set the env var before `uvicorn`). A tiny **stdlib `.env` loader** (no new dep,
  shell-override-preserving) is offered as the functional follow-up. Keys still live in local backup zips +
  Dropbox history (not git); optional key **rotation** is the user's call.
- **Files:** **new** `.env` (gitignored); `.gitignore`; **deleted** `.claude/GEMINI_API_KEYS.md`.
- **Why:** the security audit's hard pre-commit gate; enables the BYO-key model.

## 2026-06-20 — Release-readiness arc, Phase 6 (start): processed the future-tracks inbox + TDL; wired the values layer

Collaborative `.claude/` phase (user chose: process the inbox/TDL now + a full per-item inventory). Docs-only.

- **Values layer wired in.** Actioned the inbox's `…_approachavoidanceharness.md` directive (a meta task, not a
  track): **`APPROACH-AVOIDANCE.md`** (the value substrate beneath PRINCIPLES) is now the Principles gate's
  **deeper, *conditional* layer** — consulted only for novel / value-level / future-track changes (derive the
  check from the value; veto-level hard boundaries = no paywall circumvention / no reaching into other tools'
  stores / no accusation of individuals; the confirmed/extended/emergent/divergent drift typology). CLAUDE.md
  gate section + rule #9 + kickoff #8 + reference table + directory layout updated; explicitly **not** a second
  mandatory gate. The harness directive was removed from the inbox (actioned).
- **Equity & integrity signals track folded in.** Moved `…_equityintegritysignals.md` → `future-tracks/`; added
  it to the `future-tracks/` index + a "Longer-horizon" backlog bullet (HACKADEMIA-derived, **repointed to
  non-accusatory inspectable signals**; OpenAlex + findings-subsystem dependent; gated by the A-A no-accusation
  veto). Inbox now empty; added `future-tracks-import/README.md` documenting the inbox convention.
- **`callosum_TDL.txt` folded.** ~12 net-new near-term UX items captured into a new backlog section (watch
  library folders; UNSORTED/DOI-failed cluster; filter-by-type; card tidy-ups; viewer page-views; reading mode;
  **Gemini API key in Settings = BYO-key**; account/login + publishing name; hide-uncertain-by-default; progress
  bars; re-score wrap fix), deduped against shipped increments.
- **Files:** `.claude/CLAUDE.md`; `.claude/docs/INCREMENT-BACKLOG.md`; `.claude/docs/future-tracks/README.md` +
  the moved-in equity doc; **new** `.claude/docs/future-tracks-import/README.md`.
- **Still TODO this phase:** the full per-item `.claude/` inventory (user ruling on each) + the
  **Gemini-keys → `.env`** relocation (security gate before any commit).
- **Why:** the user pre-loaded the watched inbox + a TDL; integrate so the plan captures everything, and wire
  the values layer the harness doc requested. **Verify:** docs-only; `pytest` unaffected (275/1).

## 2026-06-20 — Release-readiness arc, Phase 5.5 (README coverage + planned→backlog reconciliation)

User-requested docs sweep (docs-only; no code touched).

- **Hygiene:** removed 3 atomic-write orphans (`app/backend/api/routers/*.tmp.26380.*`) + emptied the stray
  `.playwright-mcp/` MCP-scratch dir (dir handle was locked; files cleared). **Phase-7 `.gitignore` must add
  `.playwright-mcp/` + `*.tmp.*`.**
- **planned→backlog reconciliation:** swept every README for "planned / not-yet-implemented" items and checked
  each against `INCREMENT-BACKLOG.md` + `future-tracks/`. openalex/semantic-scholar/grobid were already
  **visible** (they cite future-tracks). Two were **invisible** → now captured:
  - **Mendeley** — its README correctly said *no track depends on it*, yet the backlog mis-framed it as "shared
    infra these unlock." It's **import coverage**, not track infra → new **"Import coverage — additional
    sources"** item (Theme 2: Mendeley via Zotero-bridge/exports + BibTeX/RIS/CSL-JSON import); backlog line
    328 corrected; mendeley README points at the item.
  - **Desktop-shell (Tauri) + OS keychain + desktop distribution** (desktop-shell + ops READMEs) — entirely
    absent from the plan → new **"Packaging & distribution (post-V1)"** item (Theme 4); both READMEs point at it.
- **README coverage:** added `tests/e2e/README.md` (the one genuine gap — the opt-in browser smoke +
  `CALLOSUM_RUN_E2E`). **Did NOT** blanket-add per-Python-package READMEs: the component READMEs (app/,
  app/backend/, integrations/, tests/) already map their subpackages, and per-package stubs would duplicate
  CLAUDE.md's directory layout and risk drift (rule #6). Offered deeper coverage if wanted.
- **Files:** `tests/e2e/README.md` (new); `.claude/docs/INCREMENT-BACKLOG.md`; `integrations/mendeley/README.md`,
  `app/desktop-shell/README.md`, `ops/README.md`.
- **Why:** docs better-scoped + the plan now captures all README-described planned functionality (user ask).
- **Verify:** no code touched (`pytest` unaffected at 275 passed, 1 skipped).

## 2026-06-20 — Release-readiness arc, Phase 5 (modularize · dedup · dead-code · lint/format · security audit)

Pre-GitHub code hardening (no API/schema/behavior change; increment counter stays 73).

- **Linting adopted — ruff.** Config in `pyproject.toml` (line-length 120, `select=E,F,W,I,B`, `ignore=E501`,
  bugbear `extend-immutable-calls` for FastAPI `Depends`/`Query`/… to kill B008 false positives). Applied
  **318 auto-fixes** (229 unused-import, import-sort, whitespace, etc.) + 7 manual (unused loop var, B023
  loop-capture, an `# noqa: E402` for the `sys.path` shim) + **`ruff format` repo-wide** (58 files). `ruff
  check` + `ruff format --check` now clean & idempotent. `requirements-dev.txt` carries pytest/httpx/ruff/
  pip-audit/playwright/pytest-playwright.
- **Modularize (600-line cap).** Only one app-source file was over: `axis_scoring.py` (617). Split the
  manual-assignment + read-state API → new **`app/backend/clustering/axis_assignments.py`** (167);
  `axis_scoring.py` → 463 (scoring engine only). Importers repointed (router, axis_operations, tests).
  **No app/integrations file now exceeds 600** (largest: repository 577, papers 576).
- **Dedup (lizard + difflib).** difflib flagged the 4 async-job subsystems as 0.87–0.92 similar — they each
  carried a near-identical `_XJob`/`_XJobStore` (differing only in result type). Consolidated into a generic
  **`app/backend/api/job_store.py`** (`Job`/`JobStore[R]`); `create_app` instantiates one per subsystem;
  routers type them `JobStore[XResponse]`. Removed ~130 lines of duplication. lizard complexity hotspots
  (clustering/dedup/merge fns) are inherent algorithmic complexity, left as-is (not duplication).
- **Dead code.** ruff F-series clean; removed one genuinely-unused back-compat alias
  (`canonicalize_quote_text_variants` in extraction.py). Hardcoded-secret grep: none.
- **Security audit:** `.claude/security-audits/2026-06-20_pre-github-fullsweep.md` — **PASS** for the local
  single-user model. Two tracked follow-ups: (1) secrets hygiene before first commit (`.env` relocation +
  `.gitignore` + working-tree secret scan — Phase 6/7 publication gates); (2) `pip-audit` found transitive
  CVEs in `transformers`/`urllib3` (LOW risk locally — trusted models + trusted endpoints; requirements use
  ranges so fresh installs patch) — upgrade + wire pip-audit into CI before any hosted deployment. (`yt-dlp`
  flagged but is NOT a callosum dependency — environment noise.)
- **Files:** `pyproject.toml` (ruff config); `requirements-dev.txt`; **new** `axis_assignments.py`,
  `job_store.py`; `axis_scoring.py`, `axis_operations.py`, `routers/{axes,summaries,duplicates}.py`,
  `app.py`, `extraction.py`, `tests/test_axes.py`, + ~60 files reformatted; security-audit doc.
- **Why:** ship a lint-clean, duplication-reduced, cap-compliant, audited codebase for the public repo.
- **Verify:** `ruff check` clean; `pytest` → **275 passed, 1 skipped**. **Revert:** restore from
  `.claude/backups/callosum_pre-phase5_20260620_1242.zip`.

## 2026-06-20 — Release-readiness arc, Phase 4 (test-harness audit + extension; usage-logging prod fix)

Pre-GitHub test hardening (docs/infra/test-only; increment counter stays 73).

- **New automated coverage (+19 tests, 256 → 275):**
  - `tests/test_egress_gate.py` (9) — direct unit tests of the inc-58 `EgressGated*` wrappers (the
    authoritative egress boundary): when egress is OFF each wrapper raises **and the inner provider is
    never invoked** (a spy inner records calls); ON delegates + passes metadata. Pins the security
    property the API-level tests could only imply, including the help assistant's independent toggle.
  - `tests/test_usage_logging.py` (5) — `llm/usage.py` was untested: logs the token counts, is silent on
    missing/None `usage_metadata`, never raises on malformed metadata, **and survives an Alembic
    migration** (regression for the fix below).
  - `tests/test_frontend_assembly.py` (5) — deterministic, offline frontend smoke: assembles without
    error, both `{{STYLES}}`/`{{SCRIPT}}` placeholders consumed, `#root` + babel script present, all 3
    CDN scripts carry SRI, **every** `app/frontend/js/*.jsx` chunk is included, and `callosum-app.html`
    is byte-in-sync with the live assembly (catches a forgotten `build_frontend.py`).
  - `tests/e2e/test_smoke.py` (1, **opt-in**) — committed Playwright browser smoke: launches the real
    `app:app` against a seeded temp DB, loads `/` in headless Chromium, asserts React mounts with **zero**
    console errors. Skipped unless `CALLOSUM_RUN_E2E=1` (keeps the default suite offline/deterministic);
    CI runs it after `playwright install chromium`. Verified green locally (23s).
- **Production fix surfaced by the new usage test:** `alembic/env.py` now calls
  `fileConfig(..., disable_existing_loggers=False)`. The default (`True`) disabled every app logger not
  named in `alembic.ini` on each migrate — so a real startup auto-migration left `callosum.llm.usage`
  disabled, **silently killing inc-61 token-usage logging until the next restart** (`_loud` only revived
  the `callosum` parent). `_loud` kept as defense-in-depth.
- **`requirements-dev.txt` created** (pytest, httpx, ruff, pip-audit, playwright, pytest-playwright) —
  also resolves a stale CLAUDE.md reference to a file that didn't exist.
- **Files:** `tests/test_egress_gate.py`, `tests/test_usage_logging.py`, `tests/test_frontend_assembly.py`,
  `tests/e2e/{__init__,test_smoke}.py` (new); `alembic/env.py` (logging fix); `requirements-dev.txt`
  (new); `tests/README.md` (codex Phase-3 draft + browser-smoke section); `.claude/CLAUDE.md` (test count,
  tree, migration-logging decision row).
- **Why:** close the survey-flagged gaps (egress-gate isolation, usage logging, no committed frontend
  test) before exposing the repo + CI; the audit also caught a live observability bug.
- **Verify:** `pytest` → **275 passed, 1 skipped** (e2e gated); `CALLOSUM_RUN_E2E=1 pytest tests/e2e` →
  1 passed. **Revert:** delete the new test files + `requirements-dev.txt`; restore `alembic/env.py` from
  Dropbox history.

## 2026-06-20 — Release-readiness arc, Phases 1–3 (principles gate · future-tracks fold-in · README/dir cleanup)

Pre-GitHub prep (docs/infra only; no app-code or schema change — increment counter stays 73).

- **Phase 1 — principles gate.** Added a **Principles alignment gate** section + **rule #9 (Principle
  fidelity)** + session-kickoff item #8 to `.claude/CLAUDE.md`, keyed to the new `.claude/PRINCIPLES.md`
  charter (10 commitments + THEORY contract + 4 worked examples). The gate is a *reflective pause* before
  adding/removing a literature-claim/signal feature: name the principle(s) + worked example, name the
  misalignment risk, and **propose the aligned alternative** (not just the objection). Added PRINCIPLES.md +
  future-tracks rows to the reference table.
- **Phase 2 — backlog reflects the full vision.** Moved the 7 root `opus4.8_future-tracks*.md` docs →
  **`.claude/docs/future-tracks/`** (+ a `README.md` index table); `INCREMENT-BACKLOG.md` now references each
  track (statcheck, Word/LibreOffice plugin, highlight-to-suggest/evaluate, acquisition, my-publications,
  theory/methods, plugins, gapfinder, Feed/Search) + shared deps
  (OpenAlex/Unpaywall/Semantic-Scholar/GROBID/mendeley); reconciled the stale
  `opus4.8_callosum_backlog-future-tracks.md` reference. Relocated increment notes 65–73 into
  `.claude/docs/increment-notes/`.
- **Phase 3 — GitHub strip-down + README refresh.** Archived vestigial planning-only `pipelines/` (+6
  subdirs) and `data/` (+library-store/sqlite/vector-store) → **`.claude/deprecated/`** (kept, not deleted —
  their real code lives in `app/backend/`). Removed 3 `.tmp.26380.*` crash orphans. Refreshed all **13 kept
  READMEs** (root front door + `app/**`, `integrations/**`, `tests/**`, `research/`, `ops/`) to current
  reality via `codex exec`, **each draft reviewed against the code** (root README rewritten from the stale
  "planning skeleton" to an accurate, principles-linked front door). Updated the CLAUDE.md root directory
  tree (dropped `pipelines/`; added `research/`, `ops/`).
- **Files:** `.claude/CLAUDE.md`; `.claude/docs/future-tracks/` (7 moved docs + new README);
  `.claude/docs/INCREMENT-BACKLOG.md`; `.claude/docs/increment-notes/` (65–73 moved); `.claude/deprecated/`
  (pipelines/, data/ moved); `README.md`, `app/README.md`, `app/frontend/README.md`,
  `app/desktop-shell/README.md`, `integrations/README.md` + the 4 planned stubs, `tests/README.md`,
  `tests/fixtures/README.md`, `research/README.md`, `ops/README.md`.
- **Why:** prepare an honest, principle-coherent, clutter-free tree for a public **AGPL-3.0** GitHub release
  without losing institutional memory (vestigial dirs are archived, never destroyed).
- **Revert:** restore moved dirs from `.claude/deprecated/`; READMEs/CLAUDE.md from Dropbox version history or
  `.claude/backups/`.

## 2026-06-20 — Import Crossref subjects as first-order keyword tags (increment 73)

- **Files:** `integrations/crossref/adapter.py` (capture `subject`); `app/backend/persistence/tags_repo.py`
  (`import_source` param + `add_tags_to_paper`); `app/backend/metadata/enrichment.py`
  (`apply_crossref_subject_tags` + hook); **new** `tools/backfill_keyword_tags.py`;
  `app/frontend/js/25_detail.jsx` (TagsRow re-sync bugfix) + rebuilt `callosum-app.html`;
  `app/backend/help/help_content.md`; `tests/{test_papers,test_tags,test_backfill_keyword_tags}.py`. Audit:
  `.claude/security-audits/2026-06-20_keyword-tags.md`. Notes: `INCREMENT-73-NOTES.md`.
- **What:** a paper's **Crossref subject categories** are imported as **first-order tags**
  (`import_source="keyword:crossref"`) — automatically on 🔎 re-resolve / batch enrich, and across the
  existing library via `python tools/backfill_keyword_tags.py` (full: cache-first, re-resolve the rest).
- **Why:** authors/indexers already did the concept work of naming a paper's dimensions — privilege it; the
  inc-72 c-TF-IDF suggester is the second-order gap-filler. (Zotero tags already imported via inc 71.)
- **How:** adapter keeps `subject` in `csl_json`; `apply_crossref_subject_tags` mirrors it to tags
  (additive, idempotent, **never clobbers metadata**). DOI-only to public Crossref (NOT the egress gate);
  no migration; no new endpoint. **Bugfix:** TagsRow now re-syncs on detail refetch so 🔎-added chips show.
- **Verify:** pytest **256** (+5: adapter dedupe, re-resolve→tags + provenance preserved, backfill
  cache/fetch/idempotent/metadata-safe); live E2E (`.local/keyword_tags_e2e/`) 0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc73.zip` (or revert the adapter/enrichment/
  tags_repo edits + remove the tool, rebuild).
- **Help docs:** user-facing → tags section now covers Crossref keyword tags + the backfill (`HELP-DOCS-SYNCED`
  → inc 73).
- **NEXT (deferred):** the **provenance UI** (style/group tags by source — "author keywords" vs "your tags"
  vs system facts), OpenAlex/PubMed keyword sources, and the tags↔findings cross-cut. See `INCREMENT-BACKLOG.md`.

## 2026-06-20 — Auto-suggest tags via local c-TF-IDF (increment 72)

- **Files:** **new** `app/backend/clustering/tag_suggestion.py` + `app/backend/api/routers/tags.py`
  (`GET /papers/{id}/suggested-tags`); `app/frontend/js/25_detail.jsx` + `styles.css` (✨ Suggest + candidate
  chips) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (tags section);
  `tests/{test_tag_suggestion,test_health}.py`. Audit: `.claude/security-audits/2026-06-20_tag-suggest.md`.
  Notes: `INCREMENT-72-NOTES.md`.
- **What:** a **✨ Suggest** button on the Details Tags row proposes candidate tags via **local c-TF-IDF**
  (terms most distinctive of the paper vs the library); the user clicks to accept (added via the inc-71 path).
  The per-paper analogue of inc-52's axis suggestion.
- **Why:** speeds tagging by mining the paper's own text; complements manual tags + (future) imported keywords.
- **Backend:** `suggest_tags_for_paper` (tf·idf, reuses `axis_suggestion._paper_tokens`; excludes existing
  tags; trashed/missing → []); `GET /papers/{id}/suggested-tags`. **Purely local — no embeddings, no Gemini,
  no egress** (user's explicit choice). No migration.
- **Verify:** pytest **251** (+3: distinctive ranking, idf demotes common terms, exclude-existing, endpoint);
  route-surface +1; live E2E (`.local/tag_suggest_e2e/`) — Suggest → accept a candidate, 0 console errors;
  audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc72.zip` (or remove `tag_suggestion.py` + the
  endpoint + the TagsRow Suggest UI, rebuild).
- **Help docs:** user-facing → tags section now covers ✨ Suggest + **moved the `HELP-DOCS-SYNCED` marker to
  inc 72**.
- **FOLLOW-UP (user, 2026-06-20):** **author/expert keywords as first-order tags** — privilege the authors'
  own concept work; the c-TF-IDF pass is the *second-order* gap-filler. Recorded in `INCREMENT-BACKLOG.md`
  with the **tag-provenance** model + the **tags ↔ findings/system-facts** cross-cut (e.g. a future RETRACTED
  tag from the retraction producer). See that file + the future-tracks "Tags hook" notes.

## 2026-06-20 — Tags: per-paper labels + filter the library by tag (increment 71)

- **Files:** **new** `app/backend/persistence/tags_repo.py` + `app/backend/api/routers/tags.py` +
  `app/backend/api/app.py` (include router); `app/backend/persistence/repository.py` (`list_papers` tag_id) +
  `app/backend/api/routers/papers.py` (detail `tags` field + `tag_id` param);
  `app/frontend/js/{25_detail,40_app,10_pdf_layer,20_synthesis}.jsx` + `styles.css` (Tags row + filter
  banner) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (tags section);
  `tests/{test_tags,test_health}.py`. Audit: `.claude/security-audits/2026-06-20_tags.md`. Notes:
  `INCREMENT-71-NOTES.md`.
- **What:** lightweight free-form **tags** on papers — view/add/remove on the Details pane, click a tag to
  **filter the library** to it. Surfaces the tags the Zotero importer already populates (previously invisible).
- **Why:** a reference-manager basic — manual labels complementing the heavyweight semantic axes; the
  `tags`/`paper_tags` tables existed but had no UI.
- **Backend:** new `tags_repo.py` (get/list/add[get-or-create+idempotent]/remove[+orphan prune]);
  `GET /tags`, `POST`/`DELETE /papers/{id}/tags*`; `tag_id` filter on `GET /papers` (IN subquery, mirrors
  inc-63). **No migration, local, bound-param.** Name trimmed/capped, rendered as plain text.
- **Frontend:** Details `TagsRow` (chips: name→filter, ×→remove; add input + `/tags` datalist); the inc-63
  axis-filter mirrored for tags (`libraryTagFilter`, mutually exclusive with the axis filter) + a "Filtered
  to tag …" banner.
- **Verify:** pytest **248** (+4); route-surface +3; live E2E (`.local/tags_e2e/`) — add→filter→clear→remove,
  0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc71.zip` (or remove `tags_repo.py`/
  `routers/tags.py` + the detail field + the four frontend edits, rebuild).
- **Help docs:** user-facing → added a "Tagging papers" section + **moved the `HELP-DOCS-SYNCED` marker to
  inc 71**.
- **NEXT (chosen):** inc 72 — **auto-suggest tags** per paper via **local c-TF-IDF** (no Gemini), reusing the
  inc-52 axis-suggestion machinery; candidates curated → added through this increment's tag path.

## 2026-06-20 — Citation export: BibTeX + RIS + CSL-JSON (increment 70)

- **Files:** **new** `app/backend/metadata/citation_export.py` (formatters) + `app/backend/persistence/repository.py`
  (`get_papers_for_export`) + `app/backend/api/routers/papers.py` (`POST /papers/export`);
  `app/frontend/js/{10_pdf_layer,40_app,25_detail}.jsx` + `styles.css` (bulk export picker + Details "Cite"
  row) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (new export section);
  `tests/{test_citation_export,test_papers,test_health}.py`. Audit:
  `.claude/security-audits/2026-06-20_citation-export.md`. Notes: `INCREMENT-70-NOTES.md`.
- **What:** export papers' citations in **BibTeX / RIS / CSL-JSON** from the stored `csl_json` — a **bulk
  file download** (select papers → export… → a `.bib`/`.ris`/`.json`) and a **per-paper clipboard copy**
  (Details → Cite row). The first way to get citations *out* of the library.
- **Why:** callosum is a reference manager you import into but couldn't export from — a core gap.
- **Backend:** `POST /papers/export {paper_ids, format:Literal}` → `render_citations`; live papers only
  (trashed never exported); 422 on bad format / no live ids. Read-only, **local (no egress)**, no migration;
  formatters escape their output; constant download filename. BibTeX deduped author+year key fallback.
- **Frontend:** `apiPost` forces `.json()`, so export uses a **raw fetch** → blob→`<a download>` (bulk) or
  →`navigator.clipboard` (per-paper copy, secure context on 127.0.0.1). Cite links reuse the inc-68
  canonical `.btn-link`.
- **Verify:** pytest **244** (+8: 7 formatter unit + 1 endpoint, route-surface +1); live E2E
  (`.local/citation_export_e2e/`) — bulk `.bib` download (both papers) + clipboard copy, 0 console errors;
  audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc70.zip` (or remove the endpoint +
  `citation_export.py` + the three frontend edits, rebuild).
- **Help docs:** user-facing → added an "Exporting citations" section + **moved the `HELP-DOCS-SYNCED` marker
  to inc 70**.

## 2026-06-20 — Sort the library (increment 69)

- **Files:** `app/backend/persistence/repository.py` (`_paper_sort_order` + `list_papers(sort=…)`) +
  `app/backend/api/routers/papers.py` (`sort` query param); `app/frontend/js/{10_pdf_layer,40_app}.jsx` +
  `styles.css` (Sort dropdown) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (library
  section); `tests/test_papers.py`. Notes: `INCREMENT-69-NOTES.md`.
- **What:** a **Sort** dropdown orders the library by date added (oldest/recent), title (A–Z), publication
  year (newest/oldest), or first author (A–Z). NULL year/author sort last; `id` is the stable tiebreak.
- **Why:** the library only ever listed in import order — sorting is a reference-manager basic (the axes
  panel had it since inc 43; the library didn't).
- **Backend:** the sort key indexes an **allowlist** (rule #3 — never interpolated into SQL); unknown →
  default `added` (= prior `id ASC` behavior). No new route, no migration, no egress; composes with
  q/deleted/axis_id/pagination.
- **Verify:** pytest **236** (+1: every sort order + NULL-last + unknown→default); live E2E
  (`.local/library_sort_e2e/`) — list re-orders by title/year/recency, 0 console errors. No audit gate
  (read-only query param).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc69.zip` (or revert the `sort` param +
  the frontend dropdown, rebuild).
- **Help docs:** user-facing → documented the Sort control + **moved the `HELP-DOCS-SYNCED` marker to inc 69**.

## 2026-06-20 — Canonical .btn-* button classes (DESIGN.md §3 #5) (increment 68)

- **Files:** `app/frontend/styles.css` (canonical button layer + consolidation) + `.claude/DESIGN.md` (§2
  Buttons rewritten, §3 #5 → PARTIAL); rebuilt `callosum-app.html`. Notes: `INCREMENT-68-NOTES.md`.
- **What:** added canonical `.btn`/`.btn-primary`/`.btn-ghost`/`.btn-link`/`.btn-icon` + `.danger` classes
  and folded the cleanly-identical ad-hoc button blocks into them (primary: `.axis-btn` + `.synth-actions
  button`; ghost: `.pginate button`; link: `.axis-link`; icon: `.axis-icon-btn`). **CSS-only, zero visual
  change, no JSX touched.**
- **Why:** DESIGN.md §3 #5 standing worklist item — ~10 near-duplicate button blocks re-typing the same
  recipe. Establishes the single source of truth so new buttons conform instead of drifting.
- **How (safety):** consolidation by **selector grouping** (alias the existing class names into the canonical
  rules) only where every grouped property is byte-identical to the original — near-zero regression risk,
  no className churn (`.axis-link` has dozens of call sites). Size-divergent ghost/icon buttons left as-is
  (value-shifting → deferred to a per-button JSX-className migration).
- **Verify:** no Python changed → pytest unchanged at **235**; live E2E (`.local/btn_dry_e2e/`) asserts each
  canonical class's computed style equals the intended recipe + a real `.synth-actions button` keeps its
  sizing delta, 0 console errors. No audit gate (styling only).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc68.zip` (or revert the styles.css button
  section, rebuild).

## 2026-06-20 — Un-dismiss / manage dismissals for duplicate detection (increment 67)

- **Files:** **new** `app/backend/persistence/dedup_repo.py` (the dedup-dismiss data access, extracted from
  `repository.py`) + `app/backend/api/routers/duplicates.py` (GET dismissed + POST undismiss) +
  `app/backend/clustering/duplicate_detection.py` (import repoint); `app/frontend/js/19_duplicates.jsx` +
  `styles.css` ("Previously dismissed" section) + rebuilt `callosum-app.html`;
  `app/backend/help/help_content.md` (duplicates section); `tests/{test_papers,test_health}.py`. Audit:
  `.claude/security-audits/2026-06-20_undismiss-duplicates.md`. Notes: `INCREMENT-67-NOTES.md`.
- **What:** the Duplicates modal now has a **Previously dismissed (N)** section listing the pairs you marked
  "not a duplicate" (inc 64), each with an **un-dismiss** button that lets the scan flag them again. Adds the
  in-app undo inc-64 deferred.
- **Why:** a persistent dismiss with no way to see or reverse it was a trust gap.
- **Backend:** `GET /papers/duplicates/dismissed` (registered before `/{job_id}` so "dismissed" isn't a job
  id) + `POST /papers/duplicates/undismiss {paper_ids}` (non-destructive, idempotent, local, bound-param).
  No migration (reuses the inc-64 table).
- **Module split (rule #1):** the two new data-access fns pushed `repository.py` to **604** (>600), so the
  dedup-dismiss concern (4 fns) was **moved verbatim** to new `persistence/dedup_repo.py` (63);
  `repository.py` → **555**; two importers repointed. Behavior-preserving.
- **Verify:** pytest **235** (+1: list → undismiss → re-flag, idempotent, 422); route-surface +2; live E2E
  (`.local/undismiss_e2e/`) — dismiss → previously-dismissed → un-dismiss → re-flagged, 0 console errors;
  audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc67.zip` (or revert the two endpoints +
  frontend section, fold `dedup_repo.py` back into `repository.py`, rebuild).
- **Help docs:** user-facing → added un-dismiss to the duplicates section + **moved the `HELP-DOCS-SYNCED`
  marker to inc 67**.

## 2026-06-20 — Exclude trashed papers from synthesis retrieval (increment 66)

- **Files:** `app/backend/summarization/pipeline.py` (`_source_chunks_for_scope` live-paper filter) +
  `app/backend/embeddings/retrieval.py` (`_candidate_embedding_ids` excludes trashed);
  `app/backend/help/help_content.md` (trash gotcha); `tests/{test_summaries,test_papers}.py`. Notes:
  `INCREMENT-66-NOTES.md`.
- **What:** a paper in **Trash** (soft-deleted, not yet purged) is no longer a retrieval candidate, so it
  can't be cited in a **new** synthesis. Closes the last soft-delete leak (inc-65 deferred item).
- **Why:** a trashed paper surfacing in a fresh synthesis is wrong; the user deleted it.
- **Where it actually was:** the synthesis pipeline doesn't use `search_similar` — `_source_chunks_for_scope`
  builds its own candidate SQL, and the **query** scope was `select(chunks)` with no paper filter (pulled
  every paper). Fixed there (covers query + hardens papers/cluster scopes); also hardened the general
  `_candidate_embedding_ids` primitive (defense-in-depth, used by the validation harness).
- **Verify:** pytest **234** (+2: query-scope `_source_chunks_for_scope` + `search_similar` both drop a paper
  after it's trashed, keep the live one). Backend-only — no migration/endpoint/egress/frontend; no audit
  gate; behavior-preserving when nothing is trashed (harness unaffected).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc66.zip` (or revert the two filter edits).
- **Help docs:** user-facing → updated the trash gotcha + **moved the `HELP-DOCS-SYNCED` marker to inc 66**.

## 2026-06-20 — Permanent delete: delete forever / empty Trash (increment 65)

- **Files:** `app/backend/embeddings/vector_store.py` (`VectorStore.delete`) +
  `app/backend/persistence/repository.py` (`purge_paper`/`purge_all_trashed`/`_purge_paper_embeddings`) +
  `app/backend/api/routers/papers.py` (`DELETE /papers/{id}/permanent`, `POST /papers/trash/empty`,
  `_vector_store`); `app/frontend/js/{10_pdf_layer,40_app}.jsx` + `styles.css` (Delete forever / Empty Trash,
  danger-styled, confirm) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (trash section);
  `tests/{test_papers,test_health}.py`. Audit: `.claude/security-audits/2026-06-20_permanent-delete.md`.
  Notes: `INCREMENT-65-NOTES.md`.
- **What:** a **trashed** paper can now be **permanently deleted** — per-paper **Delete forever** or
  **Empty Trash** — removing the paper, its dependent rows, AND its embeddings + sqlite-vec vectors. Finishes
  inc-54's soft-delete (Trash had no way to be emptied).
- **Why:** completes the library-delete feature; a real reference manager must be able to free space / truly
  remove a record.
- **Orphan-safety:** `embeddings.target_id` has no FK and the store had no delete, so a naive paper delete
  left embeddings + vectors behind → an orphaned paper-embedding crashes `retrieval._resolve_hit`. Purge now
  deletes the paper's embeddings + vectors **before** the paper row (CASCADE handles the rest), in one
  transaction → no orphan, no crash (unit-proven via a post-purge `search_similar`).
- **Safety:** **only reachable from Trash** (`purge_paper` returns False for a live paper → 404), so a live
  paper can never be purged in one step; the UI double-confirms. Local-only, no egress; bound-param SQL.
  **No migration** (pure DML; head stays 0006).
- **Verify:** pytest **232** (+4); live E2E (`.local/permanent_delete_e2e/`) — delete-forever + empty-trash,
  live paper survives, 0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc65.zip` (or revert the vector_store/repo/
  router/frontend edits + rebuild; no schema to undo).
- **Help docs:** user-facing → updated the trash-and-restore section + **moved the `HELP-DOCS-SYNCED` marker
  to inc 65**.

## 2026-06-20 — Persistent "not a duplicate" dismiss (increment 64)

- **Files:** `app/backend/persistence/schema.py` (+`dismissed_duplicate_pairs`) +
  `alembic/versions/0006_dismissed_duplicate_pairs.py` (head 0005→0006) +
  `app/backend/persistence/repository.py` (`get_dismissed_duplicate_pairs`/`dismiss_duplicate_pairs`) +
  `app/backend/clustering/duplicate_detection.py` (drop dismissed pairs before union-find);
  **new** `app/backend/api/routers/duplicates.py` (the dedup concern extracted from `papers.py`) +
  `app/backend/api/app.py` (include it before `papers.router`); `app/frontend/js/19_duplicates.jsx`
  (dismiss → persist) + rebuilt `callosum-app.html`; `app/backend/help/help_content.md` (duplicates section);
  `tests/{test_papers,test_health,test_startup_migration}.py`. Audit:
  `.claude/security-audits/2026-06-20_dedup-dismiss.md`. Notes: `INCREMENT-64-NOTES.md`.
- **What:** marking a duplicate group **"not a duplicate"** is now **persistent** — the scan stores the
  group's pairs in `dismissed_duplicate_pairs` and drops them on every future scan, so a legitimate
  preprint+published pair stops re-flagging. Finishes inc-56's deferred "persistent dedup-dismiss."
- **Why:** session-only dismiss meant the same false positives reappeared every scan.
- **Backend:** `POST /papers/duplicates/dismiss {paper_ids}` (≥2 existing live papers → else 422) stores all
  canonical `(low<high)` pairs; bound-param `INSERT OR IGNORE` (rule #3); local-only (no egress);
  non-destructive (records a preference, never deletes). The drop happens in `find_duplicate_groups` before
  the union-find, so a dismissed pair never links its papers into a group.
- **Module split (rule #1):** extending dedup pushed `routers/papers.py` to **636** (>600), so the duplicates
  concern (models + `_DedupJobStore` + the 3 endpoints + `_run_dedup_job`) was **moved verbatim** to the new
  `routers/duplicates.py` (157); `papers.py` → **497**. Behavior-preserving (full suite green); `app.py`
  includes `duplicates.router` before `papers.router` so `/papers/duplicates*` still wins over
  `/papers/{paper_id}`.
- **Verify:** pytest **228** (+1: dismiss → re-scan flags 0; idempotent; <2 ids → 422); migration-head +
  route-surface asserts bumped to `0006` / +`/papers/duplicates/dismiss`; live E2E
  (`.local/dedup_dismiss_e2e/`) — dismiss → reopen modal → "No likely duplicates found.", 0 console errors;
  audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc64.zip` (or drop migration 0006 + the
  `dismissed_duplicate_pairs` table, revert the duplicate_detection filter, and fold `duplicates.py` back
  into `papers.py`).
- **Help docs:** user-facing → corrected the duplicates section (dismiss is persistent, not session-only) +
  **moved the `HELP-DOCS-SYNCED` marker to inc 64**.

## 2026-06-20 — Filter the library by axis (+ select-all) (increment 63)

- **Files:** `app/backend/persistence/repository.py` (`list_papers` `axis_id` filter) +
  `app/backend/api/routers/papers.py` (`axis_id` query param); `app/frontend/js/{40_app,10_pdf_layer,15_axes}.jsx`
  + `styles.css` (clickable count badge → filter; "Filtered to axis …" banner; "select all");
  `app/backend/help/help_content.md` (axis-review section); `tests/test_papers.py`; rebuilt
  `callosum-app.html`. Notes: `INCREMENT-63-NOTES.md`.
- **What:** click an axis's **count badge** → the Library narrows to that axis's papers (with a clearable
  "Filtered to axis …" banner). Server-side filter (pagination/search compose). Pairs with inc-62: filter →
  **select all → summarize** = a verified synthesis of a whole topic cluster.
- **Why:** completes the axes-as-a-navigation-lens vision (backlog "open proposal: filter the library by
  axis").
- **Backend:** bound-param `IN` subquery over `cluster_node_papers`→`cluster_nodes` (rule #3); no new
  endpoint/egress/ingestion/migration; trashed papers stay excluded.
- **Verify:** pytest **227** (+1); live E2E (`.local/library_axis_filter_e2e/`) — filter narrows 2→1 +
  banner + select-all→summarize verified + clear restores, 0 console errors. Read-only feature → security
  note in the increment notes (no separate audit doc).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc63.zip` (or revert the `axis_id` filter +
  the three frontend files, rebuild).
- **Help docs:** user-facing → updated the axis-review section + **moved the `HELP-DOCS-SYNCED` marker to inc
  63**.

## 2026-06-20 — Summarize selected papers: multi-paper verified synthesis from the library (increment 62)

- **Files:** `app/backend/summarization/pipeline.py` (`_round_robin_by_paper` coverage fix);
  `app/frontend/js/{10_pdf_layer,40_app,20_synthesis}.jsx` + `styles.css` (bulk-bar **summarize** button →
  papers-scope synthesis + scope-note badge); `app/backend/help/help_content.md` (synthesis section);
  `tests/test_summarize_selected.py`; rebuilt `callosum-app.html`. Audit:
  `.claude/security-audits/2026-06-20_summarize-selected.md`. Notes: `INCREMENT-62-NOTES.md`.
- **What:** checkbox-select papers in the Library → click **summarize** → a **verified, citation-grounded
  synthesis of just that subset** runs in the always-on Synthesis pane (with an "N selected papers" note).
  Reuses the existing `/summarize` papers scope + local verification + the inc-61 cache.
- **Why:** the verified-synthesis crown jewel, applied to a user-chosen subset — backlog item "Multi-paper
  summary from a library selection" (the selection→summarize half; the critical-review supplement stays
  deferred behind the Auditability standard).
- **Backend fix:** a multi-paper, no-query summary previously took the first `top_k` chunks by id (filling
  from the lowest-id paper, ignoring the rest); now **round-robin across the selected papers** so the
  summary covers them all. Single-paper / query scopes unchanged.
- **Verify:** pytest **226** (+3); live E2E (`.local/summarize_selected_e2e/`) — select 2 → summarize →
  verified result + scope note, 0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc62.zip` (or revert the four frontend files
  + the `_round_robin_by_paper` block, rebuild).
- **Help docs:** user-facing → updated the synthesis section + **moved the `HELP-DOCS-SYNCED` marker to inc
  62** (the convention working).

## 2026-06-20 — Backlog curation: record future objectives (docs only, no code)

- **Files:** `.claude/docs/INCREMENT-BACKLOG.md` (new "Multi-paper summary from a library selection"
  item [Partial] under Theme 3 + a cross-cutting "Auditability standard" gating note + fixed a stale
  future-tracks path pointer); `.claude/docs/backlog-future-tracks.md` (augmented Track C with the captured
  verification-funnel / low-friction / flow-state design intent; Track B cross-ref; an Auditability-standard
  note in the intro).
- **What:** recorded three stated future objectives as tracked commitments — (2) word-processor plugin
  [Not started → already designed as Track B + C], (3) in-flow accuracy/meaning check [Not started → Track C
  "Evaluate"], (4) multi-paper summary from a library selection [Partial] — each WITH its design intent +
  the cross-cutting auditability gate. Item 1 (automatic axis nomination) confirmed **[Done]** (inc 52) and
  not re-added.
- **Why:** make future objectives tracked commitments rather than undocumented intentions (user request);
  deduped against the existing Tracks B/C (augmented in place, not duplicated).
- **Revert:** restore the three docs from `.claude/backups/callosum_claudecode_inc61.zip` (or remove the new
  blocks). No code/app/API change; no increment bump.
- **Noted (not fixed):** `README.md` is still stale ("planning skeleton"); `CLAUDE.md`'s reference-table row
  for the future-tracks doc points at a stale path (the canonical doc is `.claude/docs/backlog-future-tracks.md`).

## 2026-06-20 — Reduce LLM token spend: content-addressed summary cache + usage logging (increment 61)

- **Files:** new `app/backend/llm/{cache.py, usage.py}`; `alembic/versions/0005_llm_generation_cache.py` +
  `schema.py` (`llm_cache` table); `summarization/generators.py` + `integrations/gemini/generator.py` +
  `llm/egress.py` (thread `conn` through `generate`; `SUMMARY_PROMPT_VERSION` + `cache_signature`);
  `routers/summaries.py` (wrap with `CachedSummaryGenerator`); `summarization/pipeline.py` (pass `conn`);
  usage logging in the 4 gemini modules; `tests/test_llm_cache.py` + head bumps. Audit:
  `.claude/security-audits/2026-06-20_llm-cache.md`. Notes: `INCREMENT-61-NOTES.md`.
- **What:** a **persistent content-addressed cache** on the token-expensive **summary generation** step (a
  cache hit costs zero tokens) — keyed by a content hash of model + prompt-version + the chunk set +
  scope, so any input change misses automatically (no explicit invalidation). Plus lightweight **token-usage
  logging** at all 4 LLM call sites.
- **Why:** cut LLM token spend (the summary path is the top offender) without degrading the
  citation-verification guarantees. The cache wraps generation ONLY — local verification re-runs on every
  result; the egress gate stays byte-for-byte unchanged (cache layered inside it).
- **Verify:** pytest **223** (+6); audit PASS. Other levers (cache extension, output caps, top_k, provider
  prefix caching, Batch API) are **proposed with a measurement plan and deferred for review** (see notes).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc61.zip` (or remove `app/backend/llm/{cache,
  usage}.py` + migration 0005 + the `conn`/`cache_signature` plumbing + the factory wrap).
- **Help docs:** backend-only, **no user-facing change** → the `HELP-DOCS-SYNCED` marker is NOT moved (this
  entry sits above it as a since-sync change that does not warrant a help update — the convention working).

## 2026-06-20 — AI help assistant, separate gate (increment 60)

- **Files:** new `app/backend/help/assistant.py`, `integrations/gemini/help_assistant.py`;
  `app/backend/llm/egress.py` (+`HelpAssistantDisabledError` + `EgressGatedHelpAssistant`);
  `integrations/gemini/generator.py` (`GeminiConfig.help_assistant_enabled`); `routers/help.py` (`POST
  /help/ask` + factory), `app.py` (param/state); `app/frontend/js/18_help.jsx` + `styles.css` (chat);
  `app/backend/help/help_content.md` (+`ai-help-assistant` section); `tests/test_help.py`,
  `tests/test_health.py`, `tests/conftest.py`. Audit: `.claude/security-audits/2026-06-20_help-assistant.md`.
  Notes: `INCREMENT-60-NOTES.md`.
- **What:** an AI help assistant in the help modal — ask a question, get an answer + reference chips that
  scroll to and highlight the matching help section (reusing inc-59's `flashHelpSection`). Multi-turn, NO
  RAG (whole corpus stuffed), defensive parse (failure → answer, no refs, never 500); the router drops
  hallucinated section ids.
- **Why:** condition the synthesis "probe → route to source" workflow over the app's own help; close the
  help loop started in inc 59.
- **Separate gate (the key constraint):** keyed on a NEW **`CALLOSUM_HELP_ASSISTANT_ENABLED`** (off by
  default), **independent** of `CALLOSUM_ALLOW_DATA_EGRESS` — the bot sends only the question + the public
  help docs, never library text, so it works with the library gate off. Enforced at the inc-58 seam.
- **Verify:** pytest **217** (+7: answer+refs, gate-independence, hole-closed 503, unknown-id drop, 422,
  parse degradation, provider self-check); live E2E (`.local/help_assistant_e2e/`, **library egress off**)
  — ask → answer + chips → chip scroll+flash, 0 console errors; audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc60.zip` (or remove the new files + the
  `18_help.jsx` chat + the egress wrapper + the `/help/ask` handler + the config field, rebuild).

## 2026-06-20 — Help corpus + navigable help modal (increment 59)

- **Files:** new `app/backend/help/{help_content.md, corpus.py, __init__.py}`,
  `app/backend/api/routers/help.py` (`GET /help/corpus`), `app/backend/api/app.py` (wire router);
  `app/frontend/js/18_help.jsx` (rewrite) + `styles.css`; `tests/test_help.py`, `tests/test_health.py`
  (route surface); rebuilt `callosum-app.html`. Audit: `.claude/security-audits/2026-06-19_help-corpus.md`.
  Notes: `INCREMENT-59-NOTES.md`.
- **What:** the in-app help is now extensive end-user documentation served as a structured **corpus**
  (22 sections, stable anchor ids) and rendered in a **navigable two-column modal** (TOC + sections +
  scroll-to-flash). Replaces the old single hard-coded tips block.
- **Why:** a real help surface (groundwork for the inc-60 AI help assistant, whose references deep-link to
  these stable section ids); first pass generated by **Codex** to save Claude-Code tokens, then reviewed
  against the real code and shipped.
- **Also:** introduced the `HELP-DOCS-SYNCED` changelog-marker convention (above) + a CLAUDE.md
  start-of-session check, so future sessions can tell from the changelog whether the corpus needs updating.
- **Verify:** pytest **210** (+7); live E2E (`.local/help_e2e/`) — 22 sections render, TOC scroll+flash,
  0 console errors; audit PASS. Backend-only egress posture (the corpus endpoint is ungated, app-owned).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc59.zip` (or remove `app/backend/help/`
  + `routers/help.py` + the `18_help.jsx` rewrite, restore the static HelpModal, rebuild).

## 2026-06-19 — Provider-agnostic egress gate at the DI seam (increment 58)

- **Files:** new `app/backend/llm/egress.py` (+`__init__.py`); `integrations/gemini/generator.py`
  (re-export `DataEgressDisabledError`); `app/backend/api/routers/summaries.py` + `routers/axes.py`
  (wrap at `_summary_generator` / `_axis_term_suggester` / `_axis_cluster_labeler`);
  `tests/conftest.py` (autouse egress-consent default); `tests/test_summaries.py` + `tests/test_axes.py`
  (+4 tests). Audit: `.claude/security-audits/2026-06-19_egress-gate-seam.md`. Notes:
  `INCREMENT-58-NOTES.md`.
- **What:** moved data-egress enforcement from per-provider self-checks to a **provider-neutral gate at
  the DI seam**, applied in all three Gemini provider factories so an **injected** provider can no longer
  bypass the egress check. `DataEgressDisabledError`'s canonical home is now the neutral module
  (re-exported from Gemini). Provider self-checks kept as defense-in-depth.
- **Why:** closed the hole where `create_app(summary_generator=…)`/suggester/labeler instances were
  returned unchecked — invariant #3 is now enforced at the boundary, not by convention.
- **Verify:** pytest **203** (+4: hole-closed + behavior-preserved for the generator/suggester/labeler);
  re-export identity smoke test; route-surface invariant green; audit PASS. Behavior-preserving for the
  real Gemini path (egress-on → identical; egress-off → same `DataEgressDisabledError` → same 503).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc58.zip` (or remove `app/backend/llm/`,
  restore the local `DataEgressDisabledError` in `generator.py`, and revert the three factories +
  conftest fixture).
- **Housekeeping:** removed 25 stray `*.tmp.26380.*` atomic-write orphans left across the tree by an
  earlier crashed process.

## 2026-06-19 — Always-on Synthesis + contextual Details split (increment 57)

- **Files:** `app/frontend/js/20_synthesis.jsx` (`RightPane` tabs → vertical split); `app/frontend/js/40_app.jsx`
  (`_beginDrag` passes clientX **and** clientY); `app/frontend/styles.css` (`.pane-split`/`.rp-synth`/
  `.rp-detail`/`.divider-h`; removed dead `.pane-tabs`); rebuilt `callosum-app.html`. Notes:
  `INCREMENT-57-NOTES.md`.
- **What:** the right pane is no longer tabbed — **Synthesis stays on top always**, and selecting a paper
  shows its (editable) **Details in a lower section** with a draggable divider between them (height
  persisted to localStorage). No tab-switching; Details auto-appear when a paper is selected.
- **Why:** backlog F — elevate the inc-49 editable Details into the daily flow + keep the crown-jewel
  synthesis always visible (a coherent research workspace).
- **Verify:** pytest 199 (unchanged, frontend-only); live E2E (`.local/synthesis_split_e2e/`) — no-paper→
  Synthesis only, paper→both, drag resizes + persists across reload, 0 console errors. No audit gate.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc57.zip` (or revert RightPane + the CSS +
  the 1-line _beginDrag change, rebuild).

## 2026-06-19 — Duplicate detection (layered, flag-only) + review modal (increment 56)

- **Files:** `app/backend/clustering/duplicate_detection.py` (new — layered pairs + union-find);
  `api/routers/papers.py` (`_DedupJobStore`, `POST`/`GET /papers/duplicates`, models, `_run_dedup_job`,
  `_embedding_model`); `api/app.py` (`dedup_jobs` store); frontend `19_duplicates.jsx` (new modal) +
  `10_pdf_layer.jsx` ("Duplicates" button) + `40_app.jsx` (mount); `styles.css`; rebuilt
  `callosum-app.html`. Tests: `test_duplicate_detection.py` (+7), `test_papers.py` (+2), `test_health.py`
  (route surface). Docs: `INCREMENT-56-NOTES.md`, `.claude/security-audits/2026-06-19_duplicate-detection.md`.
- **What:** a **"Duplicates"** scan surfaces likely-duplicate paper groups with a confidence + reason,
  layered (shared PMID/arXiv → title+author+year → embedding ≥0.92, union-find). Flag-only: the user
  reviews each group and deletes the redundant copy (soft-delete → Trash) or inspects it; **merge deferred**.
- **Why:** backlog E — retroactively catch dups (preprint↔published, unresolved re-imports) that import-time
  identity dedup missed. Now well-set-up by G (clean identifiers) + inc-54 (trash as the resolution).
- **Verify:** pytest 199 (+9); live E2E (`.local/duplicates_e2e/`) — scan→group→delete→resolve, 0 console
  errors. Audit PASS (read-only, local, flag-only).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc56.zip` (or delete the new module +
  chunk, revert the endpoints/wiring, rebuild). No migration.

## 2026-06-19 — Fix: strip JATS from the editable abstract + suggest-axes terms (increment 55)

- **Files:** `app/backend/metadata/abstract_display.py` (new `abstract_plain_text`); `api/routers/papers.py`
  (`PaperDetailResponse.abstract_text`); `clustering/axis_suggestion.py` (`_paper_tokens` strips JATS);
  `app/frontend/js/25_detail.jsx` (abstract textarea → `abstract_text`); rebuilt `callosum-app.html`.
  Tests: `test_abstract_display.py` (+6), `test_papers.py` (+assertions), `test_axes.py` (+1). Notes:
  `INCREMENT-55-NOTES.md`.
- **What:** raw Crossref JATS XML was leaking — as `<jats:p>` tags in the editable abstract textarea
  (inc-49) and as the term "jats" in suggested axes (the c-TF-IDF tokenizer). A shared plain-text strip
  (`abstract_plain_text`) now feeds both (the textarea via a new `abstract_text` field; the tokenizer
  directly).
- **Why:** two user-reported leaks with one root cause (the abstract is stored raw JATS, inc-33).
- **Verify:** pytest 190 (+7); live E2E (`.local/jats_fix_e2e/`) — abstract textarea is tag-free, 0 console
  errors. Deferred: cleaning the abstract in the embedding text (`paper_embedding_text`) — needs a
  re-embed.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc55.zip` (or revert the 4 files, rebuild).

## 2026-06-19 — Library delete (soft) + multi-select + Trash / Restore (increment 54)

- **Files:** `alembic/versions/0004_paper_soft_delete.py` (new); `app/backend/persistence/schema.py`
  (`papers.deleted_at`); `repository.py` (`soft_delete_paper`/`restore_paper`, `list_papers` only_deleted,
  cluster-node filter); `clustering/axis_suggestion.py` (exclude trashed); `api/routers/papers.py`
  (`?deleted` listing + `DELETE /papers/{id}` + `POST /papers/{id}/restore`); frontend `40_app.jsx`
  (multi-select + trashView + handlers) + `10_pdf_layer.jsx` (checkboxes + bulk bar + Trash toggle +
  Restore) + `styles.css`; rebuilt `callosum-app.html`. Tests: `test_papers.py` (+4), `test_health.py`
  (route surface), `test_health.py`/`test_startup_migration.py` (head→0004). Docs:
  `INCREMENT-54-NOTES.md`, `.claude/security-audits/2026-06-19_library-delete.md`.
- **What:** the first way to delete a paper — checkbox multi-select + a bulk-delete bar (mirrors the
  inc-43 axis pattern) → **soft-delete** (a `deleted_at` stamp; hidden from library/axes/clustering but
  kept), with a **Trash ⇄ Library** toggle + per-row **Restore**.
- **Why:** the biggest CRUD gap. Soft because hard-delete orphans embeddings/vectors (no FK +
  no vector-store delete) and crashes retrieval — and soft is reversible, which the user wanted.
- **Verify:** pytest 183 (+4); live E2E (`.local/library_delete_e2e/`) — select→delete→trash→restore,
  0 console errors. Audit PASS. Permanent-delete/empty-trash deferred (needs vector cleanup).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc54.zip` (the additive `deleted_at`
  migration can stay; or revert the endpoints + frontend, rebuild).

## 2026-06-19 — Polish pass: SRI · radius scale · in-app HELP · favicon dark-swap (increment 53)

- **Files:** `app/frontend/index.html` (SRI integrity+crossorigin on React/ReactDOM/Babel; favicon split
  into 2 media-query links); `app/frontend/styles.css` (`--radius-sm/-lg/-pill` tokens + migrate
  pills/modal); `app/frontend/js/18_help.jsx` (new HelpModal) + `10_pdf_layer.jsx` (? button) +
  `40_app.jsx` (helpOpen + mount); `tools/inline_brand_assets.py` (two favicon targets); rebuilt
  `callosum-app.html`. Notes: `INCREMENT-53-NOTES.md`.
- **What:** four deferred quick wins — (1) Subresource Integrity hashes on the CDN scripts; (2) a radius
  scale (`--radius-sm/-lg/-pill`) with the clean pill/modal values migrated; (3) an in-app **? Help**
  viewer surfacing the axes/tiers tips from HELP.md; (4) the favicon swaps to the OS color scheme via
  `media="(prefers-color-scheme:…)"` links (no JS).
- **Why:** hardening (SRI) + DESIGN.md hygiene (radius tokens) + discoverability (help) + a dark-mode finish.
- **Verify:** pytest 179 (unchanged, frontend-only); live E2E (`.local/polish_e2e/`) — app renders under
  SRI (hashes correct), both favicon links present, help modal opens, 0 console errors. No audit gate.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc53.zip` (or revert the index.html SRI +
  favicon, the styles.css radius tokens, delete 18_help.jsx + its wiring, rebuild).

## 2026-06-19 — Suggest optimal axes (unsupervised discovery + coverage-with-diversity) (increment 52)

- **Files:** `app/backend/clustering/axis_suggestion.py` (new — cluster + novelty filter + MMR-lite +
  local c-TF-IDF labels + `apply_labels`); `integrations/gemini/axis_cluster_labeler.py` (new,
  egress-gated) + `__init__.py`; `app/backend/api/routers/axes.py` (`_AxisSuggestJobStore`, `POST
  /axes/suggest`, `GET /axes/suggest/{job_id}`, accessor, models); `app/backend/api/app.py` (inject
  labeler + suggest job store); `app/frontend/js/17_axes_suggest.jsx` (new) + `15_axes.jsx` (✨ button +
  modal) + `styles.css`; rebuilt `callosum-app.html`. Tests: `tests/test_axes.py` (+5),
  `tests/test_health.py` (route surface). Docs: `INCREMENT-52-NOTES.md`,
  `.claude/security-audits/2026-06-19_suggest-axes.md`.
- **What:** a ✨ Suggest button mines the library's embeddings → proposes a diverse set of candidate axes
  that don't duplicate each other or existing axes → the user curates (rename + toggle term chips) and
  creates the ones they like. Labels are local-from-your-papers (always) with optional egress-gated
  Gemini polish (degrades to local; never 503).
- **Why:** the AI-clustering finally surfaces *as discovery* — a new user no longer faces a blank axes
  panel; coverage-with-diversity ensures suggestions blanket the literature.
- **Verify:** pytest 179 (+5); live E2E (`.local/suggest_axes_e2e/`, fake model, no network) — ✨ → cards
  → create → axis appears, 0 console errors. Audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc52.zip` (or delete the two new modules
  + the new frontend chunk, revert the axes.py/app.py/15_axes.jsx wiring, rebuild). No migration.

## 2026-06-19 — B′: eyeball toggle to hide/show UNCERTAIN papers (increment 51)

- **Files:** `app/frontend/js/15_axes.jsx` (`AxisItem` `hideUncertain` state + 👁 toggle in the
  re-score row + filtered list + "show" restore hint); `app/frontend/styles.css` (`.axis-eye`,
  `.axis-eye-hint`); rebuilt `callosum-app.html`. Notes: `INCREMENT-51-NOTES.md`.
- **What:** an eye toggle (shown only when an axis has uncertain papers) collapses the list to an
  assigned/manual-only view; a "N uncertain hidden — show" hint restores them.
- **Why:** a focused, assigned-only view of an axis once the user has triaged the uncertain tier
  (pairs with inc-45's cutoff + inc-50's ✓-confirm). Pure display filter — no backend.
- **Verify:** pytest 174 (unchanged); live E2E (`.local/eye_e2e/`) — hide/show works, 0 console errors.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc51.zip` (or revert the 15_axes.jsx +
  styles.css changes, rebuild).

## 2026-06-19 — Axes manual-assignment cleanup (B) + library focus-mode add (C) (increment 50)

- **Files:** `app/backend/clustering/axis_scoring.py` (`add_manual_assignment` upsert-to-NULL;
  `restore_manual_assignments` force-NULL even when present); `app/frontend/js/15_axes.jsx`
  (AxisTierBadge drops the assigned tag; AxisPaperRow ✓-confirm; ＋ enters focus; AddPaperPicker
  removed; `axisRefresh`); `10_pdf_layer.jsx` (Sidebar forwards focus props; PaperList focus card +
  per-row add buttons); `40_app.jsx` (focus state + handlers); `styles.css` (`.axis-confirm`,
  `.focus-card`, `.paper-axis-add`); rebuilt `callosum-app.html`. Tests: `tests/test_axes.py` (+2).
  Docs: `INCREMENT-50-NOTES.md`, `.claude/security-audits/2026-06-19_axes-manual-assignment.md`.
- **What:** (B) the redundant ASSIGNED tag is gone (assigned = no tag; amber = uncertain; dashed =
  manual) and a **✓** on uncertain rows promotes them to a manual override; (C) the axis **＋** opens a
  **library focus-mode** (reminder card + per-row +add/−remove buttons) to add the papers the scorer
  missed, **staged and committed on Save**. The inc-38 in-card AddPaperPicker is retired.
- **Why:** the axes panel is the AI-clustering surface; its manual-override UX was cramped + the tags
  obscured titles. Confirms/manual-adds must survive re-scores → `confidence IS NULL` is now the single,
  durable encoding of a human override (fixes a latent revert-on-re-score bug too).
- **Verify:** pytest 174 (+2); live E2E (`.local/axes_manual_e2e/`, fake model) — no ASSIGNED tag,
  ✓→manual, focus card + Save commits, 0 console errors. Audit PASS (no new endpoint/surface).
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc50.zip` (or revert the two
  axis_scoring.py functions + the four frontend files, rebuild). No migration to undo.

## 2026-06-19 — Editable Details pane (Mendeley-style) + DOI correction / re-resolve (increment 49)

- **Files:** `app/backend/metadata/paper_edits.py` (new — `build_paper_update`, the safe partial
  csl_json merge + column projection); `app/backend/metadata/enrichment.py` (`USER_EDITED_SOURCE` +
  `force` flag); `app/backend/api/routers/papers.py` (`PaperUpdateRequest`, `PATCH /papers/{id}`,
  `POST /papers/{id}/re-resolve`, `_crossref` accessor); `app/backend/api/app.py`
  (`crossref_client` injectable); `app/frontend/js/25_detail.jsx` (new — inline-editable pane),
  `20_synthesis.jsx` (DetailContent removed → forwards `onOpenPaper`), `40_app.jsx`
  (`onOpenPaper=openPdf`), `styles.css` (`.detail-edit*` recipe; dead `.detail-title`/`.author-list`/
  `.abstract` removed); rebuilt `callosum-app.html`. Tests: `tests/test_paper_edits.py` (new),
  `tests/test_papers.py` (+9), `tests/test_health.py` (route surface). Docs: `INCREMENT-49-NOTES.md`,
  `.claude/security-audits/2026-06-19_paper-edit-doi.md`, `.claude/DESIGN.md` (§2 inline-editable variant).
- **What:** The Detail pane is now a Mendeley-style **always-editable** bibliographic editor (inline
  fields, "Add …" placeholders, auto-save on blur, Literature Type dropdown, collapsible Identifiers,
  a "More" section that auto-surfaces extra DOI-populated fields, a Files list, honest provenance). A
  wrong/missing **DOI can be corrected and re-fetched from Crossref** (🔎). No schema migration —
  `csl_json` is already the canonical record; scalar columns are projections kept in sync.
- **Why:** "reference manager first" — metadata quality is upstream of everything (clustering, dedup,
  citations, synthesis); fixing a DOI and re-resolving is table-stakes for a Zotero/Mendeley replacement.
- **Verify:** pytest 172 (+22); live E2E (`.local/detail_edit_e2e/`, fake Crossref) — inline edit
  auto-saves (prov→user-edited), re-resolve fills metadata (prov→crossref), 0 console errors. Audit PASS.
- **Revert:** restore from `.claude/backups/callosum_claudecode_inc49.zip` (or delete `paper_edits.py` +
  `25_detail.jsx`, revert the PATCH/re-resolve routes + `crossref_client`, restore DetailContent in
  `20_synthesis.jsx`, rebuild). No migration to undo (`scoring_gain` head 0003 unchanged).

## 2026-06-19 — Sidebar density (axis filter + green "+") + cutoff acts on displayed precision (increment 48)

- **Files:** `app/frontend/js/10_pdf_layer.jsx` (drop "local reference workbench" subtitle);
  `app/frontend/js/15_axes.jsx` (filter state + `Filter axes…` input, "+ new"→green "+", one no-wrap
  controls row, `visibleAxes` filter, no-match hint); `app/frontend/styles.css` (`.axis-controls`/
  `.axis-filter`, green `.axis-new`, removed dead `.axis-head-actions` + `.brand .sub`);
  `app/backend/clustering/axis_scoring.py` (`_confidence_from_cosine_distance` rounds to 2dp);
  `tests/test_axes.py` (+1) → rebuilt `callosum-app.html`. Notes: `INCREMENT-48-NOTES.md`.
- **What:** (1) Rest of B″ density — removed the subtitle, added an axis **filter** (matches title or
  terms), turned "+ new" into a green **"+"**, all controls on one no-wrap row → more axes visible.
  (2) **Cutoff rounding:** confidences now stored/compared at the 2 decimals the UI shows, so a paper
  displayed as "0.35" can't be tagged UNCERTAIN because its raw score was 0.349 (user-caught).
- **Why:** density (power-user sees more axes) + honesty (displayed number == the number that decides the
  tier).
- **Verify:** pytest 150 (+1 rounding unit test); live E2E (`.local/density_e2e/`) — subtitle gone, filter
  narrows/restores, controls one row (no wrap), 0 console errors. Frontend density is rebuild-only; the
  rounding affects new scores (re-score to apply).
- **Revert:** restore the listed files from `.claude/backups/callosum_claudecode_inc47.zip` + rebuild.

## 2026-06-19 — Connection status shown by the logo (increment 47)

- **Files:** `app/frontend/styles.css` (4 `--logo-*` bg-image tokens + `.brand-logo` div rules
  theme×.connected; removed dead `.brand-logo-light/dark` + `.conn`/`.led*`); `app/frontend/js/10_pdf_layer.jsx`
  (two `<img>` → one status `<div>`; removed `ConnStatus` + usage); `tools/inline_brand_assets.py` (logo
  targets → 4 CSS tokens); recompressed `app/media/logo_on.png` + `logo_dm_on.png` (423KB→~57KB) → rebuilt
  `callosum-app.html`. Notes: `INCREMENT-47-NOTES.md`.
- **What:** The brand logo now indicates connection — a green dot in the brain's cell-body when connected
  (the user's `logo_on`/`logo_dm_on` assets) — replacing the `● connected · local-verifier-v1` text line.
  Driven as a 4-state CSS background-image (theme × `.connected`); base64 lives in CSS (not the Babel
  script, avoiding the 500KB deopt).
- **Why:** declutter the header (B″ density step) while keeping the signal, using the user's assets.
- **Verify:** pytest 149 (frontend-only); live E2E (`.local/conn_logo_e2e/`) — `.connected` class, `.conn`
  text gone, bg-image swaps on connection + theme, 0 console errors (no Babel note); dark screenshot shows
  the green dot. No backend/migration/egress.
- **Revert:** restore `styles.css`/`10_pdf_layer.jsx`/`inline_brand_assets.py` + `logo_on.png`/`logo_dm_on.png`
  from `.claude/backups/callosum_claudecode_inc46.zip`, + rebuild.

## 2026-06-19 — DESIGN.md token consolidation + dark mode + Settings modal (increment 46)

- **Files:** `app/frontend/styles.css` (new chrome tokens + `:root[data-theme="dark"]` override + hex→token
  replacements + `--on-fill` + settings/logo-toggle CSS); `app/frontend/index.html` (no-flash theme
  bootstrap in `<head>`); `app/frontend/js/10_pdf_layer.jsx` (two themed brand logos + gear button); new
  `app/frontend/js/35_settings.jsx` (`SettingsModal`); `app/frontend/js/40_app.jsx` (theme + settings
  state); `tools/inline_brand_assets.py` (light+dark logo targets); recompressed `app/media/logo_dm.png`
  (427KB→57KB, lossless) → rebuilt `callosum-app.html`. Docs: `.claude/DESIGN.md` (tokens + §1b Dark theme
  + §3 status), `.claude/CLAUDE.md`, audit `.claude/security-audits/2026-06-19_dark-mode-settings.md`,
  `INCREMENT-46-NOTES.md`.
- **What:** Finished DESIGN.md's color-token consolidation (scattered hex → tokens; split destructive color
  reconciled to `--danger`) and added a **warm-dark theme** via `data-theme` + CSS-variable overrides,
  toggled in a new sparse **Settings modal** (gear icon in the sidebar). No-flash bootstrap; theme-matched
  logo swap; the **rendered PDF page stays light** in both themes; `--on-fill` keeps text legible on the
  now-light semantic fills.
- **Why:** "wrap up DESIGN.md" + add dark mode — the token consolidation IS the dark-mode groundwork; the
  Settings modal establishes the prefs surface (backlog H).
- **Verify:** pytest 149 (frontend-only, unchanged); live E2E (`.local/dark_mode_e2e/`) — toggle dark→
  `data-theme=dark` + `--bg`=#1a1815 + logo swap, persists across reload (no flash), back to light, 0
  console errors; audit PASS. HTML 989KB→495KB after the dark-logo recompress.
- **Revert:** restore the listed frontend files + `inline_brand_assets.py` + `logo_dm.png` from
  `.claude/backups/callosum_claudecode_inc45.zip`, delete `35_settings.jsx`, + rebuild.

## 2026-06-19 — Design dictionary (`DESIGN.md`) + badge-encodes-scoring-status

- **Files:** new `.claude/DESIGN.md`; `.claude/CLAUDE.md` (rule #8 "read DESIGN.md before any CSS change" +
  reference-table + 2 decision-log rows); `.claude/docs/INCREMENT-BACKLOG.md`; `app/frontend/js/15_axes.jsx`
  (badge status class, removed the `.axis-state` text line) + `styles.css` (badge color modifiers; dropped
  the dead `.axis-state`/`.axis-flag-*` rules) → rebuilt `callosum-app.html`.
- **What:** (1) Created **`DESIGN.md`** — a two-pass design dictionary (Pass 1 = the CSS as-is: tokens +
  element recipes; Pass 2 = inconsistencies + canonical rules + a consolidation worklist, e.g. the split
  destructive colors `--flag` vs `#b3261e`, three indigos, repeated hover/border hexes, ~10 near-duplicate
  buttons). CLAUDE.md now **requires reading it before any CSS/inline-style edit** (rule #8). (2) The axis
  **count badge now encodes scoring status by color** — green `--verified` (scored & fresh), amber `--flag`
  (`.is-stale`, edited → re-score), muted `--line-2` (not scored) — and the textual `.axis-state` status
  line was **removed** (status lives in the badge color + tooltip; reclaims sidebar density).
- **Why:** set the design tether *before* the upcoming UI wave (sidebar density, settings + dark mode,
  synthesis redesign) to prevent design-by-committee drift; the badge change is a first dictionary-driven
  consistency decision (status-by-color, not by text).
- **Verify:** live check (`.local/badge_status_e2e/`) — `.axis-state` gone, badge neutral→green on score,
  0 console errors; build clean (`15_axes.jsx` 376). No backend change (pytest unaffected, 149).
- **Revert:** delete `DESIGN.md`, revert the CLAUDE.md rule/rows + the `15_axes.jsx`/`styles.css` badge
  edits, + rebuild.

## 2026-06-19 — Adjustable assignment cutoff ("gain") + axis-card redesign (increment 45)

- **Files:** `schema.py` (`axes.scoring_gain`); `alembic/versions/0003_axis_scoring_gain.py`;
  `app/backend/clustering/axis_scoring.py` (absolute-cutoff badge + shared never-empty helper);
  `app/backend/api/routers/axes.py` (`DEFAULT_AXIS_CUTOFF`, score `gain` param + clamp + persist, read
  re-tiers by axis cutoff, `AxisResponse.scoring_gain`); `tests/test_axes.py`, `tests/test_health.py`,
  `tests/test_startup_migration.py`; `app/frontend/js/15_axes.jsx` (card icon buttons + red count badge +
  Re-score/cutoff-flipper row, tip removed) + `styles.css` → rebuilt `callosum-app.html`. New
  `.claude/HELP.md`. Audit: `.claude/security-audits/2026-06-19_axis-gain.md`. Notes: `INCREMENT-45-NOTES.md`.
- **What:** Replaced inc-39's relative natural-break badge (which assigned only the top 2–6 papers — the
  largest gap sits near the top of smooth declines) with an **absolute cutoff** (default 0.35), now a
  **per-axis, persisted, user-adjustable** value (a "Cutoff" flipper on the Re-score row). Redesigned the
  axis card: ✎/＋/🗑 icon buttons (＋ auto-expands + opens the picker; ✎ doesn't expand) + a circular red
  count badge; Re-score is the lone in-list control. Moved the relative-tiers tip to `.claude/HELP.md`.
- **Why:** the dynamic cut was systematically too exclusive (user evidence across 3 axes); 0.35 captures
  the relevant ~half, and the user wanted it tunable as the library grows.
- **Verify:** pytest 149 (+1 cutoff-persistence; recalibrated fake model; head→0003); live E2E
  (`.local/axis_gain_e2e/`) — card icons + badge, ✎ no-expand, ＋ expands, flipper persists `scoring_gain`
  across reload, tip gone, 0 console errors; audit PASS. Additive migration 0003 (auto-applies on startup);
  existing axes re-tier at 0.35 on read — no re-score needed.
- **Revert:** restore the listed files from `.claude/backups/callosum_claudecode_inc44.zip`, drop the
  `scoring_gain` column (or `alembic downgrade`), + rebuild.

## 2026-06-19 — Fix (interim): axis edit modal lost its term pills on reopen when the description was blank

- **Files:** `app/frontend/js/16_axes_merge.jsx` (`_axisBase`/`_axisRelatedTerms` parser) → rebuilt
  `callosum-app.html`; also removed stray `app/frontend/js/*.jsx.tmp.*` files (interrupted-write leftovers).
- **What:** Editing an axis to clear the description prose, then saving, composed the description as just
  `"Related: …"` (no leading blank line, since the empty prose is dropped before `join("\n\n")`). The
  parser split only on the literal `"\n\nRelated:"`, so on reopen it failed to recover the terms — the
  pills vanished and the whole `"Related: …"` string showed up in the description box. Fixed the parser to
  split on any `Related:` marker (with/without leading newlines, multiple blocks) + case-insensitively
  dedupe; it now round-trips empty-prose axes and also cleans up the double-`Related:` descriptions old
  merges left.
- **Why:** user hit it on resting-state after clearing the description and adding many terms; the string
  *looked* editable so they deleted it (a UX trap any user would fall into).
- **Verify:** live E2E (`.local/axis_terms_roundtrip_e2e/`) — empty-prose axis with 3 terms survives
  save→reopen as 3 pills, description box empty, 0 console errors. Frontend-only (hard-reload). pytest 148
  (unchanged).
- **Note:** this is the **interim** fix. The real fix (next increment) promotes the terms to a first-class
  field separate from the description prose, so the `"Related:"`-in-description convention — and this whole
  class of parsing bug — goes away. (Per the user: "the pills should effectively replace 'Related:'
  tracking via string in the description.")
- **Revert:** restore `16_axes_merge.jsx` from `.claude/backups/callosum_claudecode_inc44.zip` + rebuild.

## 2026-06-19 — Fix: axis perpetually "re-score" after merge + restore the 600-line cap

- **Files:** `app/backend/clustering/axis_scoring.py` (`axis_score_state` membership check; trimmed
  `_axis_text`/`_embed_axis` comments back under 600); `tests/test_axes.py` (+1 regression test).
- **What:** An axis could show "description changed — re-score" forever even right after re-scoring.
  Root cause: `_embed_axis` adds one embedding row per distinct scored text version and never prunes, and
  `axis_score_state` judged freshness from the **newest row by id**. A merge/edit cycle that revisits a
  prior text version leaves a stale row with a *higher* id than the row matching the current text →
  perpetually stale. Fix: an axis is fresh if **any** stored embedding matches the current text
  (`score_axis` always embeds the current text, so a match means the live assignments reflect it).
  Self-heals existing DBs on the next `/axes` read — no re-score needed. Also fixes a 600-line-cap
  violation: the inc-44 `_axis_text` comment had pushed `axis_scoring.py` to 603 → trimmed to 598.
- **Why:** user hit it on `anomalous-is-bad` after merging two related axes (`resting-state` was unaffected
  because its newest row happened to match); confirmed by replaying `axis_score_state` on the live DB
  (now `stale=False`). The newest-by-id heuristic was simply wrong given accumulating embedding rows.
- **Verify:** pytest 148 (+1: freshness survives text revisiting a prior scored version); read-only replay
  on `.local/validation-summarize/validation.sqlite` → anomalous-is-bad/resting-state/major-depression all
  `stale=False`. Backend-only (restart uvicorn; no rebuild). Known minor follow-up: embedding rows still
  accumulate per axis (harmless — axis vectors aren't read for scoring; a future prune could tidy them).
- **Revert:** restore `axis_scoring.py` + `tests/test_axes.py` from `.claude/backups/callosum_claudecode_inc44.zip`.

## 2026-06-19 — Axis edit modal + title/term decoupling + click-to-open (increment 44, backlog A + A′)

- **Files:** `app/backend/clustering/axis_scoring.py` (`_axis_text` embeds description-only w/ label
  fallback); new `app/frontend/js/14_axes_edit.jsx` (`AxisEditModal`); `app/frontend/js/15_axes.jsx`
  (quick-name create, removed inline create/edit forms + old terms modal + `.axis-desc` preview, A′
  openPaper); `app/frontend/js/40_app.jsx` + `10_pdf_layer.jsx` (thread `onOpenPaper`); `styles.css`;
  `tests/test_axes.py` (+2 tests) → rebuilt `callosum-app.html`. Audit:
  `.claude/security-audits/2026-06-19_axis-edit-modal.md`. Notes: `INCREMENT-44-NOTES.md`.
- **What:** One **Edit Axis modal** for create/edit/term-search. The **title is now a cosmetic display
  name**; the search vocabulary is a curated terms list (stored in the description's `Related:` block,
  primary term first, embedded — the label is no longer the query). Suggested terms are **deselected by
  default** (selected sort to top). Clicking an axis-listed article **opens its PDF** (A′).
- **Why:** name a lens naturally without the name polluting the embedding; consolidate scattered forms;
  keep the human in the loop on AI terms; make the axes panel a clickable library overview.
- **Verify:** pytest 147 (+2: scoring keys on description not label; label-only fallback); live E2E
  (`.local/axis_edit_e2e/`) — deselect-by-default, no `.axis-desc`, click-to-open PDF, 0 console errors;
  audit PASS. No migration, no new egress/endpoint (existing axes show stale → re-score once).
- **Revert:** delete `14_axes_edit.jsx`, restore `axis_scoring.py`/`15_axes.jsx`/`40_app.jsx`/
  `10_pdf_layer.jsx`/`styles.css`/`tests/test_axes.py` from `.claude/backups/callosum_claudecode_inc43.zip`
  + rebuild.

## 2026-06-19 — Axis management: sort + multi-select + bulk delete + curated merge (increment 43)

- **Files:** new `app/backend/clustering/axis_operations.py` (`merge_axes`); `app/backend/api/routers/axes.py`
  (`POST /axes/merge` + `MergeAxesRequest` + `created_at` on `AxisResponse`); `tests/test_axes.py`,
  `tests/test_health.py`; `app/frontend/js/15_axes.jsx` (sort select + checkbox multi-select + bulk bar) +
  new `app/frontend/js/16_axes_merge.jsx` (`MergeAxesModal` comparison view) + `styles.css` → rebuilt
  `callosum-app.html`. Audit: `.claude/security-audits/2026-06-19_axis-merge.md`. Notes: `INCREMENT-43-NOTES.md`.
- **What:** The Axes panel is now sortable (name / paper count / newest), supports checkbox multi-select with a
  bulk-action bar (delete N, or merge ≥2), and a **merge** that consolidates axes into one surviving axis via a
  comparison/curation view — you pick which axis's identity survives and curate the merged label + description.
  Each folded axis's label is carried into the survivor's `Related:` terms by default, so a re-score keeps the
  papers each source axis used to surface discoverable; manual assignments are unioned; the survivor auto-re-scores.
- **Why:** as axes accumulate (esp. after the inc-41 synonym suggester), the user needs to order, bulk-act on, and
  consolidate near-duplicate lenses without losing the vocabulary that made each one find its papers.
- **Verify:** pytest 145 (merge + validation tests; route-surface invariant adds `/axes/merge`); live E2E
  (`.local/axes_manage_e2e/`) — sort, multi-select, comparison-view merge (folded label → `Related:`), bulk delete,
  0 console errors; security audit PASS. No migration, no egress.
- **Revert:** delete `axis_operations.py` + `16_axes_merge.jsx`, restore `axes.py`/`15_axes.jsx`/`styles.css`/tests
  from `.claude/backups/callosum_claudecode_inc42.zip` + rebuild.

## 2026-06-19 — Resizable + collapsible side panels (increment 42)

- **Files:** `app/frontend/js/40_app.jsx` (Divider component + drag/collapse + persisted layout state),
  `app/frontend/styles.css` (divider/collapsed styles; removed the narrow-screen media query) → rebuilt
  `callosum-app.html`. Notes: `INCREMENT-42-NOTES.md`.
- **What:** The left (Axes) and right (Synthesis) panels are now drag-resizable and collapsible via a
  divider with a grip + chevron toggle; the center PDF/library area expands as a side collapses. Widths +
  open/closed state persist to localStorage. Frontend-only; no backend/migration/egress (no audit).
- **Why:** let users focus on the PDF viewer and tune the layout.
- **Verify:** pytest 143 (Python untouched); live E2E — collapse/expand both panels, drag-resize, center
  widens, 0 console errors.
- **Revert:** restore the two frontend files from `.claude/backups/callosum_claudecode_inc41.zip` + rebuild.

## 2026-06-19 — Gemini axis synonym suggester (increment 41)

- **Files:** new `integrations/gemini/axis_terms.py` + `__init__` export; `app/backend/api/app.py`
  (`axis_term_suggester` wiring); `app/backend/api/routers/axes.py` (`POST /axes/suggest-terms` + accessor
  + models); `tests/test_axes.py`, `tests/test_health.py`; `app/frontend/js/15_axes.jsx` + `styles.css`
  (suggest-terms modal) → rebuilt `callosum-app.html`. Audit:
  `.claude/security-audits/2026-06-19_axis-term-suggester.md`. Notes: `INCREMENT-41-NOTES.md`.
- **What:** Optional AI assist to broaden niche axes: Gemini proposes related terms, the user curates
  them in a **modal**, and the chosen terms fold into the axis description (re-score to apply). New
  `POST /axes/suggest-terms` (sync, stateless) is **egress-gated** (off → 503 guidance; other failure →
  502, never 500); untrusted model output is deduped/capped/echo-stripped. Human-in-the-loop + transparent
  (terms are visible/editable text in the description). No migration.
- **Why:** raise recall on niche axes (e.g. surface more than the literal phrasing matches) while keeping
  the human in control and the default local-first path intact.
- **Verify:** pytest **143** (140 + 3 new: terms returned, empty-label 422, egress-off→503 hermetic,
  `_parse_terms` cleaning); live E2E (curate → apply → description folded, 0 console errors). Audit: PASS.
- **Usage:** set `CALLOSUM_ALLOW_DATA_EGRESS=1` + `GOOGLE_API_KEY`, restart, then "suggest terms" on an axis.
- **Revert:** restore the listed files (and delete `integrations/gemini/axis_terms.py`) from
  `.claude/backups/callosum_claudecode_inc40.zip`.

## 2026-06-19 — Axis punctuation normalization (increment 40)

- **Files:** `app/backend/embeddings/models.py` (`strip_punctuation`), `app/backend/clustering/axis_scoring.py`
  (apply to `_embed_axis` + `axis_score_state`), `tests/test_axes.py`. Notes: `INCREMENT-40-NOTES.md`.
- **What:** Axes differing only in punctuation/spacing scored differently ("anomalous-is-bad" vs
  "anomalous is bad"; "resting-state" vs "resting state") because `normalize_text` keeps punctuation, so
  MiniLM tokenizes them differently. Now the axis text is run through a new `strip_punctuation` util
  (punctuation/underscores → spaces, unicode-aware) before embedding + text-versioning, so equivalent
  phrasings produce an identical axis embedding → identical results. Axis-side only — no paper re-embed,
  no migration, no frontend change.
- **Why:** equivalent axis phrasings should give the same results.
- **Verify:** pytest **140** (138 + 2 new: a `strip_punctuation` unit test + an integration test where
  two punctuation-variant axes score identically under a punctuation-sensitive fake model).
- **User action:** re-score existing punctuated axes once (they'll show stale).
- **Revert:** restore the two source files from `.claude/backups/callosum_claudecode_inc39.zip`.

## 2026-06-18 — Axis scoring calibration: natural-break relative tiering (increment 39)

- **Files:** `app/backend/clustering/axis_scoring.py` (+`natural_break` mode + 2 helpers),
  `app/backend/api/routers/axes.py` (`SUPERVISED_AXIS_CONFIG`; relative read tier),
  `app/frontend/js/15_axes.jsx` + `styles.css` (relative caption) → rebuilt `callosum-app.html`,
  `tests/test_axes.py`. Notes: `INCREMENT-39-NOTES.md`.
- **What:** Inc-38's absolute thresholds (assigned ≥0.7 / uncertain ≥0.5) assigned **nothing** on real
  data — `all-MiniLM-L6-v2` axis-vs-paper-metadata cosine maxes ~0.37 (median 0.02), though the ranking
  is correct. Switched to **natural-break relative tiering**: assigned = the cluster above the largest
  gap in the axis's ranking (above a 0.2 MiniLM-calibrated noise floor), uncertain = the rest of the
  eligible, never-empty fallback shows the closest few. Tiers are **recomputed on read** from the
  stored confidences (no migration; read == score). Raw similarity still shown honestly.
- **Why:** make supervised axes actually surface relevant papers (validated: the anomalous-is-bad axis
  now assigns its facial-difference papers, excludes off-topic ones).
- **Verify:** pytest **138** (136 + 2 new); real-data read-only check + live E2E (tiers populate, 0
  console errors). Users must **re-score** axes scored under the old logic.
- **Revert:** restore the listed files from `.claude/backups/callosum_claudecode_inc38.zip`.

## 2026-06-17 — Axes increment 1: create / browse / score / correct user-defined axes (increment 38)

- **Files:** `app/backend/clustering/axis_scoring.py` (new reuse helpers), `app/backend/api/routers/axes.py`
  (6 new mutations + 1 GET + async score job + extended reads), `app/backend/api/app.py`
  (`axis_score_jobs` wiring), `tests/test_health.py` (route surface), `tests/test_axes.py` (hermetic
  suite), `app/frontend/js/15_axes.jsx` (new AxesPanel) + `10_pdf_layer.jsx`/`40_app.jsx`/`styles.css`,
  rebuilt `callosum-app.html`. Notes: `INCREMENT-38-NOTES.md`; audit:
  `.claude/security-audits/2026-06-17_axes-supervised.md`.
- **What:** Exposed the existing `axis_scoring.py` engine as write endpoints + UI. Create an axis from
  a label + description; score it (async job, `assignment_mode="absolute"` → assigned ≥0.7 / uncertain
  ≥0.5 / below-threshold not stored); browse assigned papers by honest tier + confidence; manually
  add/remove papers (human override, `confidence IS NULL` = manual vs scored float); edit (→ stale until
  re-scored, via the axis embedding's text-version) and delete (CASCADE, axis-tree only). Re-score
  preserves manual adds. **No migration, no egress** (scoring is fully local).
- **Why:** the Axes sidebar panel was read-only/inert; this makes user-defined axes usable end-to-end
  (increment 1 of a staged feature; unsupervised clustering / synthesis-scope / multi-pole deferred).
- **Verify:** pytest **136 passed** (129 + 7 new, route-surface updated); hermetic fake-model tiers,
  stale, re-score-preserves-manual, manual add/remove, narrow cascade, graceful model-unavailable.
  Live browser E2E: create → score → tiers (1 assigned / 1 uncertain, far excluded) → manual-add,
  **0 console errors**. Security audit: PASS.
- **Revert:** restore the listed files from `.claude/backups/callosum_claudecode_inc37.zip` (pre-inc-38).

## 2026-06-17 — Restore `callosum-app.html` as a generated build artifact (inc 37 follow-up)

- **Files:** new `tools/build_frontend.py`; `app/backend/api/app.py` (serve precedence); regenerated
  `callosum-app.html`.
- **What:** Kept the modular `app/frontend/` source, but `tools/build_frontend.py` now rebuilds the
  single-file `callosum-app.html` from it (verified **byte-identical** to the pre-split original,
  CRLF and all). The `/` route serves that file by default (restoring the prior behavior file-based
  UI testing relies on), with live assembly as the fallback when it's absent.
- **Why:** preserve the user's existing frontend-testing workflow, which expects that particular file.
- **Verify:** `python tools/build_frontend.py` → 375312 bytes, identical to the original; `GET /`
  serves it (200, text/html, app markers present); pytest **129**.
- **Revert:** delete `callosum-app.html` + `tools/build_frontend.py` and restore the default-assembly
  `/` route.

## 2026-06-17 — Modularize the monolith files (increment 37)

- **Files:** new `app/backend/api/{dependencies,startup,frontend}.py` + `app/backend/api/routers/*.py`;
  new `app/backend/pdf_processing/quote_matching.py`; new `tools/validation/{reports,report_renderer}.py`;
  new `app/frontend/{index.html,styles.css,js/*.jsx}`; new `tests/{conftest,api_helpers,test_papers,
  test_annotations,test_axes,test_summaries,test_health}.py`. Slimmed `app/backend/api/app.py`,
  `extraction.py`, `tools/validation_harness.py`. Deleted `callosum-app.html` + `tests/test_api.py`.
  Updated importers + `tools/inline_brand_assets.py`. Notes: `INCREMENT-37-NOTES.md`; audit:
  `.claude/security-audits/2026-06-17_frontend-assembly.md`.
- **What:** Behavior-preserving split of the oversized files at their natural joints into
  descriptively-named modules so directed code reviews touch one concern at a time. `app.py`
  1108→113 (factory + per-resource routers; only logic change: `/summarize*` read the job store via
  `request.app.state`). `extraction.py` 662→555 (+`quote_matching.py`). `test_api.py` →
  conftest + per-resource files. `validation_harness.py` 1298→898 (report dataclasses + markdown
  renderer extracted; probes stay — exempt tool). `callosum-app.html` 2023 → modular `app/frontend/`
  **assembled at serve time** into one document at `/` (no build step, no new file-serving surface;
  JSX concatenated into one `<script>` so the shared scope is identical).
- **Why:** `app.py`/`extraction.py` were over the 600-line hard limit (overdue standing-split tasks);
  the rest were unwieldy for review. Now **no file under `app/`/`integrations/` exceeds 600** (largest
  `extraction.py` 555).
- **Verify:** `pytest` **129 passed** after every phase; route-surface invariant green (no endpoint
  drift); inc-36 E2E re-run against the **assembled** frontend — reload-drift **0.0px**, **0 console
  errors** (faithful in-browser reassembly). Security audit: PASS.
- **Revert:** restore the affected files from `.claude/backups/callosum_claudecode_inc36.zip`
  (pre-increment-37 snapshot).

## 2026-06-17 — Synthesis → annotation bridge: save a citation as a highlight (increment 36 / suite C)

- **Files:** `app/backend/api/app.py`, `callosum-app.html`, `tests/test_api.py`,
  `INCREMENT-36-NOTES.md`, `.claude/security-audits/2026-06-17_synthesis-source.md`.
- **What:** A verified, exact-coordinate synthesis citation can now be **saved as a durable
  annotation** (`source="synthesis"`). Backend: `POST /papers/{id}/annotations` accepts an optional
  `source`, allowlist-validated (`NATIVE_ANNOTATION_SOURCES`, forged → 422), defaulting to `"user"`;
  the handler stopped hardcoding `"user"`. No new route, no migration. Frontend: a "Save as
  highlight" control on each `CitationCard`, **enabled only for exact+verified** citations and
  otherwise **disabled with a tooltip** (honesty contract); `App.saveCitationHighlight` POSTs the
  citation's bboxes/quote as a synthesis annotation and bumps an `annoRefresh` nonce so an open
  `PdfViewer` refetches **without a reload** (no-flicker effect). Synthesis highlights render with a
  distinct **dashed `.pdf-synthesis-outline`** marker (user choice: outline only; fill palette
  unchanged), drawn outside the multiply group so it stays crisp.
- **Why:** unite the ephemeral citation-overlay system with durable user highlights, so a machine-
  found passage becomes a first-class, annotatable highlight — without ever presenting a
  region/null/flagged citation as a precise highlight.
- **Verify:** pytest **129 passed** (126 + 3 new source accept/default/forged tests). Headless E2E
  (`.local/inc36_e2e/`, real uvicorn + real PDF, Chromium): gating proof (1 enabled / 1 disabled+
  tooltip), save persists `source="synthesis"`, **live refresh** (`.pdf-synthesis-outline` 0→1 with
  the tab open), **reload-drift 0.0px**, 0 console errors. Security audit: PASS.
- **Revert:** restore `app/backend/api/app.py` + `callosum-app.html` + `tests/test_api.py` from the
  pre-increment snapshot `.claude/backups/callosum_claudecode_inc33-35.zip`.

## 2026-06-17 — Fix multi-line highlight opacity doubling (increment 35)

- **Files:** `callosum-app.html`, `INCREMENT-35-NOTES.md`.
- **What:** A multi-line highlight's overlapping per-line rects double-filled the interior (darker
  band); the pre-existing per-fill `mix-blend-mode: multiply` didn't help (multiply compounds at
  overlap). Fix: wrap each annotation's rects in an isolated per-annotation group
  (`.pdf-user-highlight-group{position:absolute;inset:0;isolation:isolate;mix-blend-mode:multiply;opacity:0.7}`)
  with **opaque** per-line fills that union with no doubling; the group composites once → uniform on
  every row, darkening toward the text. Removed the per-fill multiply + inset border (would seam the
  union). No geometry change.
- **Why:** even, legible highlighting (worsens with the longer passages increment C will create).
- **Verify (headless):** 60-rect highlight — gap-row luminance top/mid/bottom 250.7/253.1/251.9 →
  **spread 2.4 (~1%)**, uniform; screenshot confirms no interior band; reload-drift **0.0px**; zoom
  unchanged. Citation overlay (low-alpha/bordered, transient) left as-is; text layer untouched.
  pytest **126 passed**.
- **Revert:** restore `callosum-app.html` from the pre-increment zip snapshot in `.claude/backups/`.

## 2026-06-17 — Fix PDF text-layer/canvas misalignment (scale + DPR sync) (increment 34)

- **Files:** `callosum-app.html`, `INCREMENT-34-NOTES.md`.
- **What:** The invisible text layer drifted from the rendered PDF text (worse toward the page
  bottom) and desynced under zoom/HiDPI. Root causes: `Math.floor` truncation of the canvas/text
  containers vs un-floored span coords; responsive `width:100%`/`max-width:100%` shrinking the canvas
  but not the fixed-px text layer; no `devicePixelRatio`. Fix: every layer now derives from one
  `getViewport({scale})` with **exact un-floored CSS dims**; canvas backing store at device
  resolution (`round(css*dpr)` + a `[dpr,0,0,dpr,0,0]` render transform) with the exact CSS box;
  text layer + wrapper + overlays sized identically; removed the responsive shrink (too-wide pages
  scroll, `overflow:auto`); a `matchMedia` DPR listener re-renders on browser zoom/HiDPI change.
- **Why:** selection/highlighting requires the text layer to sit exactly over the visible text.
- **Verify (headless):** bottom-of-page drift **−7.97px → −0.20px** (wide@115%; regression across the
  full page −0.83px); narrow pane went from desynced to −0.20px; HiDPI dpr=2 backing now 2× with the
  exact CSS box (bottom offset −0.10). **Highlight reload-drift = 0.0px at 50/75/115/195% and dpr=2.**
  pytest 126 passed (frontend-only).
- **Revert:** restore `callosum-app.html` from the pre-increment zip snapshot in `.claude/backups/`.

## 2026-06-17 — Loud startup auto-migration + honest /health migration check

- **Files:** `app/backend/api/app.py`, `tests/test_api.py`, `tests/test_startup_migration.py` (new).
- **What:** (1) The startup auto-migrate now **announces itself** — INFO "startup migration check:
  db=… current=… head=…", a WARNING "database auto-migrated … X -> Y" when it actually migrates, an
  INFO "already at head …" when not, and an ERROR (non-fatal) on failure. A minimal stdout logging
  setup + a `_loud()` helper keep these visible even though Alembic's `env.py` runs
  `fileConfig(disable_existing_loggers=True)` on every migrate (which had been silencing our logger
  mid-startup — the post-upgrade line would otherwise never appear). (2) `/health` is now **honest**:
  `db_migrated` means *at head* (compares the DB's current Alembic revision to head), not merely
  "some version stamped"; added `db_revision` + `db_head_revision` so a behind-DB is diagnosable from
  /health alone.
- **Why:** a silent schema mutation on the user's DB must be surfaced, and the health check that was
  supposed to warn of a behind-DB was lying (this is what hid the earlier silent-500).
- **Verify:** pytest 126 passed (behind-DB reports not-at-head; at-head reports up-to-date; startup
  emits the from→to WARNING + at-head INFO; a forced migration failure logs ERROR but is non-fatal and
  the app still serves /health). Sample real log lines captured (from→to + at-head). No schema change;
  env.py untouched; non-fatal-on-failure preserved.
- **Revert:** restore the two app/test files from the pre-change zip snapshot in `.claude/backups/`.

## 2026-06-17 — Clean JATS abstract rendering (increment 33)

- **Files:** `app/backend/metadata/abstract_display.py` (new), `app/backend/api/app.py`,
  `callosum-app.html`, `tests/test_abstract_display.py` (new), `tests/test_api.py`,
  `INCREMENT-33-NOTES.md`, `.claude/security-audits/2026-06-17_jats-abstract-display.md`.
- **What:** Crossref abstracts (stored raw as JATS XML) now render as clean structured text in the
  Detail pane instead of literal `<jats:…>` tags. New pure transform `clean_abstract_for_display`
  emits a small allowlist of attribute-free HTML (`p/em/strong/sub/sup`); `PaperDetailResponse`
  gains a derived `abstract_display` (raw `abstract` unchanged); the frontend renders it via the
  app's only `dangerouslySetInnerHTML` (allowlisted backend output).
- **Why:** readable abstracts (italics, bold, sub/sup for formulae/p-values) without mutating the
  faithful stored value (store raw, render structured).
- **Verify:** pytest 122 passed (real HBM + Alves fixtures, plain-text, malformed, entities/sub-sup,
  allowlist/security, purity, stored-unchanged API test); headless Firefox renders clean, no console
  errors. No schema/migration change.
- **Revert:** restore the listed files from the pre-increment zip snapshot in `.claude/backups/`.

## 2026-06-17 — Fix: highlight create 500'd on stale (un-migrated) DBs + robustness

- **Files:** `app/backend/api/app.py`, `callosum-app.html`; plus migrated all
  `.local/**/validation.sqlite` to head.
- **Root cause:** the running DB predated increments 30/31 and lacked the `annotations`
  columns (`color`, …); every create-annotation INSERT returned **500**, and the frontend
  **swallowed the error silently** → "highlighting does nothing." Found via the user's
  uvicorn traceback (`table annotations has no column named color`).
- **What:** (B) **auto-migrate on startup** — `create_app`'s lifespan now runs
  `alembic upgrade head` (absolute `script_location`, defensive) against the configured DB,
  so the app self-heals any DB it opens. (C) **surface API errors** — `apiPost/apiPatch/apiDelete`
  `console.warn` on failure, and the annotation actions show a transient `.pdf-toast`
  ("Couldn't save highlight — …") instead of failing silently. (A) ran `alembic upgrade head`
  on all 10 existing `.local` validation DBs (`color` now present).
- **Why:** the code/migration were correct; the DB just hadn't run `0002`. Auto-migrate +
  visible errors prevent this class of silent failure recurring.
- **Verify:** end-to-end — a stale DB copy auto-migrated on startup (`color` false→true) and
  an HTTP create returned 201; Firefox highlight renders; a forced 500 shows the toast +
  console.warn. `pytest` 113 passed (lifespan auto-migrate doesn't affect the non-`with`
  TestClient tests). No schema/migration change (single head stays `0002`).
- **Revert:** restore the two files from the pre-change zip snapshot in `.claude/backups/`.

## 2026-06-17 — Highlight visibility + note-on-create affordance (annotation UX)

- **Files:** `callosum-app.html`.
- **What:** (1) Made user highlights clearly visible — overlay fill 0.38 → **0.55** alpha and a
  crisper inset edge (the old marker was so faint over the page that, since clicking a swatch also
  clears the blue text-selection, it read as "nothing happened"). (2) Added a **"✎ note" button to
  the create picker** (`createHighlightWithNote`) that makes the highlight and immediately opens the
  note editor — notes are no longer only reachable by clicking an existing highlight.
- **Why:** User reported highlighting "doesn't highlight" (it did — it persisted to the DB — but was
  too subtle) and that the create menu had no way to add a note.
- **Verify:** headless **Firefox** — highlight renders at 0.55 alpha (screenshot confirmed),
  "✎ note" → POST 201 → editor opens → note saves (PATCH) → note-dot shows; no console errors.
  No Python changed (suite unaffected).
- **Revert:** restore `callosum-app.html` from the pre-change zip snapshot in `.claude/backups/`.

## 2026-06-16 — Brand logo + favicon (increment 32)

- **Files:** `callosum-app.html` (+ user-added `app/media/logo.png`, `app/media/favicon.png`),
  `INCREMENT-32-NOTES.md`.
- **What:** Brand lockup in the sidebar header — the brain logo (62px) stacked **above** the
  "Callosum" wordmark, centered, with the subtitle/status centered under it; favicon wired. Both
  PNGs inlined as base64 `data:` URIs (favicon `<link rel="icon">` + a `.brand-logo` `<img>`);
  replaced the old accent `.dot` (rule removed); `.brand` is a centered column and the sidebar
  header is centered.
- **Why:** Branding. Inline data URIs (matching the existing `data:,` favicon placeholder) avoid a
  new file-serving route/surface and keep the single-file, offline frontend self-contained.
- **Verify:** headless Chromium PASS (logo decodes 348px → 62px, stacked centered above the
  wordmark, favicon is a PNG data URI, no console errors); `pytest` still 113 passed (no Python touched).
- **Revert:** restore `callosum-app.html` from the pre-increment zip snapshot in `.claude/backups/`.

## 2026-06-16 — Annotation notes + management panel (increment 31 / suite B)

- **Files:** `app/backend/api/app.py`, `app/backend/persistence/repository.py`,
  `callosum-app.html`, `tests/test_api.py`, `tests/test_persistence_core.py`,
  `INCREMENT-31-NOTES.md`, `.claude/security-audits/2026-06-16_annotation-notes.md`.
- **What:** Comments/notes on highlights + a per-paper annotation panel. `note` accepted on
  create; new `PATCH /annotations/{id}` (note and/or color; note capped at 4000) — the
  project's first update endpoint; `update_annotation` repo helper. Frontend: clicking a
  highlight opens a note+color editor (replaces delete-only), a note dot marks commented
  highlights, and a collapsible in-viewer panel lists/edits/deletes/jumps-to annotations.
- **Why:** Suite increment B; activates the `note` column scaffolded in A. No migration (the
  column already exists). Synthesis-sourcing + re-anchoring remain later increments.
- **Verify:** `pytest` (113 passed); headless E2E PASS — note persists across reload with the
  highlight still at **0.0 px** drift; two PATCH round-trips; delete-from-panel clears UI + DB.
- **Revert:** restore the listed files from the pre-increment zip snapshot in `.claude/backups/`
  (no schema/migration change to undo).

## 2026-06-16 — Annotation highlights (increment 30 / annotation suite A)

- **Files:** `app/backend/persistence/schema.py`, `alembic/versions/0002_annotation_highlights.py`,
  `app/backend/persistence/repository.py`, `app/backend/api/app.py`, `callosum-app.html`,
  `tests/test_api.py`, `tests/test_persistence_core.py`, `INCREMENT-30-NOTES.md`,
  `.claude/security-audits/2026-06-16_annotations.md`.
- **What:** First user-authored persistent data + first mutating endpoints. PDF.js text
  layer added so text is selectable; selecting text offers a color and creates a durable
  highlight (POST), highlights load + render on open and stay zoom-aligned (reusing the
  increment-29 coordinate model), and can be deleted. Backend: extended the existing
  `annotations` table with native columns (color/bboxes_json/anchor_text/prefix/suffix/
  source/note/updated_at), repository CRUD, and `POST/GET /papers/{id}/annotations` +
  `DELETE /annotations/{id}`.
- **Why:** Foundation of the staged annotation suite (comments, synthesis-linking,
  re-anchoring come later). `note`/`source` columns scaffold those without building them.
- **Verify:** `pytest` (107 passed); headless Playwright E2E PASS (highlight lands on
  text 98.6%, persists at 0px after reload, 0% zoom drift, delete clears UI + DB).
- **Revert:** restore the listed files from the pre-increment zip snapshot in
  `.claude/backups/`; on any already-migrated DB, the 0002 columns are additive/nullable
  and can be left in place (downgrade available via `alembic downgrade 0001_persistence_core`).
