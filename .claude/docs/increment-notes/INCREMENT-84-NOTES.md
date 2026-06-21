# Increment 84 — Star key publications + scope the AI summary to starred

## Implemented
A My-Publications curation chore: ⭐ **star** key publications and a **"⭐ only"** toggle that scopes the inc-81
AI research-summary generation to just the starred papers (so the summary centers your flagship work). LLM-free
plumbing; the summary generation itself is the existing egress-gated path.

**Backend**
- Migration **0012** + `schema.py` — `profile.starred_paper_ids` (JSON; a sorted id list, like `name_variants`).
  `profile_repo.set_starred(conn, paper_id, starred)` (read → add/remove → write).
- `routers/my_publications.py` — `POST /my-publications/star {paper_id, starred}` (local, idempotent); the
  generate endpoint gained a `SummaryGenerateRequest {starred_only}` body → reads `starred_paper_ids` →
  `my_publication_documents(only_paper_ids=…)`; empty starred set + `starred_only` → 422.
- `clustering/my_publications.py::my_publication_documents(conn, *, only_paper_ids=None)` — restricts the
  grounded summary input to a subset.
- `routers/axes.py` — `ClusterPaperResponse.starred`; `axis_clusters` populates it from
  `profile.starred_paper_ids` **only for the `my_publications` axis** (every other axis → empty set, no extra
  query); `_cluster_paper_response(..., starred_ids=…)`.

**Frontend**
- `15_axes.jsx` — `AxisPaperRow` gains a ★/☆ button shown only for My Pubs (reads `paper.starred`; `onStar` →
  `POST /star` → reload the card detail). `starPaper` threaded through the AxesPanel handlers.
- `31_mypubs_dashboard.jsx` — a "⭐ only" checkbox in the research-summary header → passes `starred_only` to
  generate (title hints to star papers in the sidebar card).
- `styles.css` — `.axis-star` (★ uses `--accent`, the selection color — NOT amber `--flag`, which is reserved
  for status) + `.mypubs-starred-toggle`. Rebuilt `callosum-app.html`.

## Key technical detail
Starring is stored as an isolated `profile.starred_paper_ids` JSON list (consistent with `research_domains` /
`name_variants`) — no new table, no coupling to the axis-membership machinery. The star state surfaces on the
**My Publications axis clusters** response (where the card already lists papers), gated to that axis so the
generic `/axes/{id}/clusters` endpoint does no extra work for standard axes. The summary scope reuses the
existing `my_publication_documents` (just a subset filter) + the existing egress-gated generator — no new
egress path.

## Manual verification script
1. Hard-refresh; open the My Publications **sidebar card** (expand it).
2. Click ☆ next to a paper → it fills (★) and persists across a reload.
3. Open the dashboard (📊) → tick **⭐ only** → **Generate**: the draft is built from only the starred papers
   (with none starred, it shows "star some first"). Untick → it uses all members. _(Visual check delegated.)_

## Pytest
**377 passed, 1 skipped** (+2: star toggles + surfaces on the my-pubs clusters; generate scoped to starred
+ 422 when none). `ruff` clean; `alembic upgrade head` → `0012`. No new egress; no audit gate (the star
endpoint is local; the summary path is the already-audited inc-81 egress seam).
