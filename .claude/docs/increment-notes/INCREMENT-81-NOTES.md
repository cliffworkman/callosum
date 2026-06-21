# Increment 81 — My Publications Part 2: the impact dashboard (Layer 1)

## Implemented
An **Overview dashboard tab** for the pinned My Publications axis (the inc-78 own-papers axis), opened by a 📊
button on the card. It turns the user's own corpus into a first-class impact surface — headline OpenAlex
metrics, a publications-by-year chart, the indexed-vs-library gap, and an editable AI-written research summary.
Layers 2–4 (domain decomposition, enriched paper cards, grounded prospection) remain deferred.

**Backend**
- `alembic/versions/0010_my_publications_summary.py` + `schema.py` — `profile.research_summary` (Text,
  nullable, additive/idempotent; head 0009 → **0010**). `profile_repo.set_research_summary`.
- `integrations/openalex/author.py` — `ResolvedAuthor` gained `cited_by_count`/`h_index`/`i10_index`/
  `counts_by_year` (parsed from the **already-fetched** author object — no new call; defaults keep existing
  construction valid). New **cache-only** `cached_author(conn, *, orcid, name)` (reads via `get_cached`, never
  fetches) + a shared `_author_cache_key` so `resolve_author` (write) and `cached_author` (read) can't drift.
- `app/backend/clustering/my_publications.py` — `build_dashboard(conn, *, author_client)` (a cache-only
  assembler: status `ok`/`no-identity`/`not-resolved`; metrics, `pubs_by_year`, `counts_by_year`, the gap,
  `as_of` from the cached works row's `fetched_at`) + `my_publication_documents` (the axis members' titles +
  JATS-stripped abstracts — the grounded input for the summary).
- `integrations/gemini/research_summary.py` — `ResearchSummaryGenerator` Protocol +
  `GeminiResearchSummaryGenerator` (mirrors the inc-41 term suggester; input-capped; output cleaned/capped).
  `EgressGatedResearchSummaryGenerator` in `app/backend/llm/egress.py`; injected via
  `create_app(research_summary_generator=…)` + the `_research_summary_generator` seam factory in the router.
- `app/backend/api/routers/my_publications.py` — `GET /my-publications/dashboard` (sync, cache-only),
  `POST /my-publications/summary/generate` (egress-gated → 503 off / 502 on failure / 422 no members),
  `PUT /my-publications/summary` (persist, capped 4000).

**Frontend**
- `app/frontend/js/31_mypubs_dashboard.jsx` — `MyPubsDashboard` (status branch; metric tiles; **hand-rolled
  SVG bar charts** for pubs-by-year + citations-by-year, token-themed, no chart library; the research-summary
  textarea with Generate [egress-gated] + Save, reusing the inc-79 `ProgressBar`).
- Tab wiring: `40_app.jsx` `openMyPubsDashboard` (a `type:"dashboard"` frame tab) → `30_viewer.jsx`
  `LibraryFrame` render branch; the 📊 button + `onOpenMyPubsDashboard` threaded App → Sidebar
  (`10_pdf_layer.jsx`) → AxesPanel (`15_axes.jsx`). CSS in `styles.css` (tokens only). Rebuilt
  `callosum-app.html`.

## Key technical detail
The dashboard is a **cache-only, egress-free read**. The OpenAlex author object that inc-78's resolve already
fetched + cached (provider `openalex_author`) carries `cited_by_count`, `summary_stats.{h_index,i10_index}`,
and `counts_by_year`; the cached works (provider `openalex_works`) carry years. So Layer-1 needs **no new
OpenAlex call** — it re-parses the cached author object (existing caches self-heal) via the enriched
`_author_from_obj`, and `cached_author` reads the cache under the *same key* as `resolve_author` (shared
`_author_cache_key`) but never fetches. The read is gated on `profile.openalex_author_id` being set (⟹ the
cache is warm), so opening the tab honors "explicit refresh, never on plain tab open." Headline metrics are
OpenAlex's authoritative figures over the **whole indexed record** (not the library subset — the spec forbids
the subset because it would disagree with Scholar), shown verbatim + attributed. The only egress is the
research summary, gated by the library `CALLOSUM_ALLOW_DATA_EGRESS` flag at the inc-58 seam.

## Manual verification script
1. Hard-refresh the app (Ctrl+Shift+R).
2. ⚙ Settings → My Publications → set your name + ORCID → **Refresh** (warms the OpenAlex cache).
3. In the sidebar, on the **📄 My Publications** card, click **📊** → a "My Publications" tab opens with the
   metric tiles (citations / h-index / i10 / indexed works), the gap line, and the pubs-by-year (+ citations-by-year) bars.
4. With egress **on** (`CALLOSUM_ALLOW_DATA_EGRESS=1` + `GOOGLE_API_KEY`): click **Generate** → a draft summary
   appears; edit it → **Save**; reopen the tab → it persists. With egress **off**: the charts/metrics still
   render and **Generate** returns the 503 consent note (the dashboard itself never fetches).
   _(Visual check delegated to the user — no in-repo browser automation this session.)_

## Pytest
**370 passed, 1 skipped** (+8: OpenAlex stats parse + cache-only `cached_author` no-fetch; `build_dashboard`
ok/not-resolved/no-identity; dashboard endpoint; summary generate+persist, egress-off → 503, no-members → 422).
`ruff` clean; `alembic upgrade head` → `0010`. Audit `.claude/security-audits/2026-06-20_my-publications-dashboard.md`
**PASS**.
