# Increment 85 — Missing-works review + import (the indexed-vs-library gap, made actionable)

## Implemented
The carrot from the user's My-Pubs follow-ups: the dashboard's "N indexed · M in library" gap becomes a
**review queue** — the OpenAlex-attributed works **not** in your library, each with **Import** (accept) or
**Dismiss** (reject). Import reuses the inc-74–76 lane (metadata-only). The user noted 79 over-attributes
(dismiss the false ones) and 40 under-counts (import the true-but-missing ones).

**Backend**
- Migration **0013** + `schema.py` — `profile.dismissed_work_dois` (JSON). `profile_repo.dismiss_work(conn, doi)`
  (normalized, idempotent).
- `clustering/my_publications.py`:
  - `build_dashboard` → `missing_works`: cached author works whose normalized DOI is ∉ live library
    (`select(papers.c.doi)…`) and ∉ dismissed → `[{doi, title, year, cited_by_count}]`, sorted by citations,
    capped (100). Cache-only / egress-free.
  - `import_missing_work(conn, *, doi, author_client, crossref_client)`: **guardrail** — the DOI must be one of
    the author's cached works; then `create_paper(imported_source="openalex-import")` +
    `enrich_paper_metadata_from_crossref(force=True)` + `_add_confirmed_member` (a cache-independent confirmed
    My-Pubs add). Idempotent (`exists` if already in the library). Statuses: imported / exists / not-author-work
    / not-resolved / invalid.
- `routers/my_publications.py` — `POST /my-publications/works/import {doi}` (not-author-work/invalid → 422;
  not-resolved → 409) + `POST /my-publications/works/dismiss {doi}` (204); `DashboardResponse.missing_works`.

**Frontend** (`31_mypubs_dashboard.jsx` + `styles.css`)
- A **collapsible** "Review N indexed works not in your library" section (anchored off the gap line): each row
  `title · year · N cites · doi` + **Import** / **Dismiss**; both refetch the dashboard (the work then leaves
  the list). Token-based CSS; rebuilt `callosum-app.html`.

## Key technical detail
Import is **metadata-only and guardrailed**: `import_missing_work` only proceeds if the DOI is among the
resolved author's cached OpenAlex works (no arbitrary-DOI minting), then creates a paper + Crossref-enriches it
(`force=True`, since `openalex-import` isn't in the auto-update allowlist — this is an explicit user action, like
re-resolve). Its only egress is the Crossref DOI lookup (metadata, **not** the Gemini gate); **no PDF/file write**
(the OA-PDF path stays the separate per-paper "Acquire OA copy"). The My-Pubs membership is added **directly**
via `_add_confirmed_member` (not via `maybe_add_to_my_publications`, which re-derives from the cached works) so it
works regardless of cache warmth or whether Crossref resolved. Once imported, the work's DOI matches a live
paper → it drops out of `missing_works`. Dismiss persists the DOI in `profile.dismissed_work_dois` (normalized).

## Principles gate
OpenAlex-attributed works are **candidates** (facts-vs-candidates): shown attributed + inspectable (title/year/
citations/DOI), the **human imports or dismisses** — nothing auto-imports. Extends the inc-78 confirm/reject
posture to external works; no composite score; no-accusation honored (the user's own works).

## Manual verification script
1. Hard-refresh; open the My Publications dashboard (📊) after a Settings → Refresh.
2. Expand **"Review N indexed works not in your library."** Click **Dismiss** on a non-yours work → it vanishes
   (and stays gone on reload). Click **Import** on a real one → it joins the library + My Publications and drops
   from the list. _(Visual check delegated.)_

## Pytest
**380 passed, 1 skipped** (+3: `missing_works` excludes matched + dismissed sorted by citations; import →
library + My Pubs + drops + idempotent; import rejects a non-author DOI [422] + the dismiss endpoint). `ruff`
clean; `alembic upgrade head` → `0013`. Audit `.claude/security-audits/2026-06-21_my-pubs-missing-works.md`
**PASS**.
