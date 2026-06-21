# Increment 83 — My Publications Part 2: domain decomposition (Layer 2)

## Implemented
The spec's Layer-2 "differentiator," on the inc-81 dashboard: cluster the researcher's own corpus into research
**domains**, show **impact-by-domain** (citations per domain), and **select a domain to re-filter** the
publications-by-year chart. **LLM-free** (local clustering); the only network call is the OpenAlex works refresh
(metadata egress, not the Gemini gate).

**Backend**
- Migration **0011** + `schema.py` — `profile.research_domains` (JSON; the decomposition
  `[{label, terms, paper_ids}]`, overwritten wholesale). `profile_repo.set_research_domains`.
- `integrations/openalex/author.py` — `AuthorWork.cited_by_count` (parsed from the works `select`, now incl.
  `cited_by_count`; default keeps old caches valid) + `fetch_author_works(..., refresh=False)` (refresh →
  bypass + re-cache, upgrading an old cache that lacks citations).
- `app/backend/clustering/my_publications.py` — `decompose_domains(conn, *, model, author_client)`: cluster the
  axis's **confirmed** members (confidence NULL or ≥ 0.95 — excludes the 0.25 name-only candidates) exactly like
  inc-52 axis suggestion (`model.encode_texts` → `_l2_normalize` → `AgglomerativeAbstractClusterer`, k≈√n cap),
  label via the **shared** `axis_suggestion` helpers (`_paper_tokens`/`_top_terms_per_cluster`/`_label_from_terms`),
  freshen works (refresh=True), persist to `profile.research_domains`. `build_dashboard` gained a `domains`
  field (`_dashboard_domains`: map each domain's paper_ids → DOI → cached work's `cited_by_count` + year →
  `{label, terms, paper_count, citation_count, paper_years}`, sorted by citations).
- `routers/my_publications.py` — `POST /my-publications/domains` (async, `mypubs_domain_jobs` JobStore) +
  `GET /my-publications/domains/{job_id}`; `DashboardResponse.domains`; a local `_embedding_model` resolver
  (mirrors the axis-suggest job). `app.py` adds the JobStore.

**Frontend** (`31_mypubs_dashboard.jsx` + `styles.css`)
- A **Research domains** section: **Break down by domain** (async → `ProgressBar`) → a horizontal impact-by-domain
  bar list (label · `Np · M cites`, bar scaled by citations) + **Re-decompose**. Clicking a domain selects it
  (multi-select); the pubs-by-year chart re-filters client-side to the union of selected domains' `paper_years`
  with a "N papers · M citations in selected domain(s)" summary + a clear link. The four author-level tiles stay
  whole-record (per the spec's denominator rule — no per-domain h-index recompute).

## Key technical detail
Domains are stored as an **isolated JSON artifact on the profile, NOT as child `cluster_nodes`** — because
`axis_score_state` counts members **by `axis_id` across all of an axis's nodes**, child nodes would double-count
the My Pubs card badge + skew the inc-79 `uncertain_count`. The JSON blob (like `name_variants`) delivers
Layer-2's value with **zero impact** on the inc-78/79 membership machinery. The dashboard read stays
cache-only/egress-free; the per-domain citations come from the cached works (the decompose action freshens them
via `refresh=True`, an explicit, already-audited OpenAlex metadata call). Impact-by-domain is an honest citation
**sum**, never a composite score; domains show their member papers + the c-TF-IDF terms that named them.

## Manual verification script
1. Hard-refresh; open the My Pubs dashboard (📊) — needs a prior Settings → Refresh.
2. Click **Break down by domain** → domains appear ranked by citations, each with paper count + citation sum.
3. Click a domain → the pubs-by-year chart + summary re-filter to that domain; click again → restores;
   multi-select unions; **Re-decompose** recomputes. _(Visual check delegated to the user.)_

## Pytest
**375 passed, 1 skipped** (+5: works `cited_by_count` + refresh; `decompose_domains` clusters confirmed members
/ excludes candidates; too-few; `build_dashboard` domains sorted by citations; the domains endpoint). `ruff`
clean; `alembic upgrade head` → `0011`. Audit `.claude/security-audits/2026-06-20_my-publications-domains.md`
**PASS**.
