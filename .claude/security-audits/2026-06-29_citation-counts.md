# Security audit — library-wide per-paper citation counts (A2, inc 210)

**Date:** 2026-06-29
**Feature:** `POST /papers/citation-counts/refresh` (async batch) + `GET …/{job_id}` (poll) fetch each live
paper's OpenAlex `cited_by_count` (by DOI) into a new `paper_citation_counts` table; the library card shows the
verbatim count + an "as of <date>" and an explicit "Most cited" sort.
**Audit triggers:** new API endpoints (#1); a new external-fetch *caller* (#2 — though it reuses the
already-audited OpenAlex adapter); a new file-write path (#3 — a DB table); 3+ files (#5).

## Threat review

- **Input validation.** The POST takes **no body**. The GET's `job_id` is an opaque in-memory key (→ 404 if
  absent). The batch's input is `papers.doi` from our own DB (not request data); each DOI is passed to the
  already-audited `OpenAlexClient._fetch_work`, which `quote(doi, safe="/")`s it into the path. The returned
  count is validated `isinstance(int)` before storage (a non-int / missing field → None → not stored).
- **SSRF / external calls.** Host is the **constant** `https://api.openalex.org/works` (never built from
  request/DB data). The DOI is a path-quoted segment, not the host. httpx has a 10s timeout; the fetch is
  **fail-closed** (any exception → cached as a miss → None). No user- or DB-supplied URL is ever fetched. This
  is the inc-74/119/135 OpenAlex posture, unchanged.
- **Data egress.** What leaves the machine is the paper's **DOI** (already-public bibliographic data) → OpenAlex,
  exactly like the existing My-Pubs (inc 119) + gap-finder (inc 135/137) fetches. **No library text leaves** →
  this is **NOT** the Gemini `CALLOSUM_ALLOW_DATA_EGRESS` gate (which governs library-text generation). Bounded
  (live-papers-with-DOI), cached (`external_api_cache` under `doi:<doi>` → re-runs hit cache, no re-egress),
  on-demand (the user clicks "Citations ↻"). The polite-pool `mailto` is a non-secret contact (inc 158).
- **Resource caps.** The batch iterates only live papers **with a DOI** (the reliable identifier; title-search
  counts are deliberately excluded — unreliable + costly). Each `_fetch_work` is cache-first, so a re-run is
  near-free. Bounded by the user's own library size; runs in a BackgroundTask (one job per click).
- **SQL.** `upsert_citation_count` uses SQLAlchemy bound params + `INSERT … OR REPLACE` on the `paper_id` PK
  (rule #3). The list projection / sort use correlated scalar subqueries over the table metadata (no interpolation).
- **File-path safety.** None — no filesystem write; the only write is the DB row.
- **Output encoding.** The count is an integer; the "as of" is an ISO date sliced to `YYYY-MM-DD` in a `title`
  tooltip — React escapes both; no `dangerouslySetInnerHTML`.
- **Supply chain.** No new dependency (reuses httpx + the existing OpenAlex adapter).
- **Migration.** `0027_paper_citation_counts` is additive + guarded (`if "paper_citation_counts" in table_names:
  return`) with a no-op downgrade (0001's `metadata.create_all` builds it on fresh DBs + its loop drops it) — the
  0021/0022 pattern. FK CASCADE → a purged paper's count row is removed automatically.

## Principles (gate run inline — Example 3 "surfacing effect sizes", the per-paper-number case)

- **#7 no opaque composite:** the count is stored + shown **raw**, never folded into any other score; it feeds
  no ranking except the one explicit user-chosen sort.
- **#2 signal not verdict / no silent rank:** "Most cited" is an **explicit, labeled, user-invoked** sort — never
  the default and never auto-applied. The chip says "N cited-by", attributed to OpenAlex; no "high-impact" label.
- **#6 silence is not a certificate:** a paper with no DOI / no OpenAlex record shows **no chip** (honest "—"),
  never "0 citations". A real 0 (the work exists, 0 cites) is stored + shown as 0 — distinct from "unknown".
- **#8 inspectability + #10 local-first/bounded/on-demand:** the source ("per OpenAlex · as of <date>") is
  visible on the control + each chip's tooltip; the fetch is bounded/cached/on-demand behind the swappable adapter.
- **Declined (the easy misaligned path):** an "evidence strength" composite or a default citations-ranked library.

## Negative-path checks (run)

- Unknown `job_id` → **404** (`test_refresh_status_404_for_unknown_job`).
- OpenAlex 404 / no work → **None → not stored** → the card shows no chip, never a fabricated 0
  (`test_refresh_stores_counts_and_shows_on_list`: the `10.1/miss` paper has `cited_by_count is None`).
- A real 0 count → stored + shown as 0 (`…/c2`), distinct from unknown.
- No-DOI papers are **excluded** from the fetch set (`test_list_live_papers_with_doi_only`,
  `summary.total == 3` for 3 DOI papers + 1 no-DOI).
- Re-fetch replaces idempotently (`upsert` OR-REPLACE; `test_upsert_projection_and_most_cited_sort`).

**Security Audit: PASS.**
