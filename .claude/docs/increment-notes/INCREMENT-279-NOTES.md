# Increment 279 — Overlooked-work lens (backlog #37, equity/integrity)

A per-axis discovery lens — "the Matthew effect, inverted" — that surfaces external works highly relevant to one of
the user's axes but **under-cited for their vintage** ("work you're likely missing because the field overlooked it,
not because it's weak"). Mechanically distinct from the gap-finder (which follows citation *links*): this follows the
gap between **relevance and attention**. Spec: `.claude/docs/specs/2026-07-16-overlooked-work-lens-design.md`; plan:
`.claude/docs/plans/2026-07-16-overlooked-work-lens-plan.md`.

## Implemented (TDD, one commit per task)

**Task 1 — `fetch_topic_works` (`integrations/openalex/sources.py`).** A new client read path returning `TopicWork`
stubs (`openalex_work_id`, `doi`, `title`, `year`, `cited_by_count`, `abstract`) from
`/works?filter=primary_topic.id:{topic}` (select `id,doi,title,publication_year,cited_by_count,abstract_inverted_index`).
Topic id validated `^T\d+$` before any request; work ids `^W\d+$`. `_abstract_from_inverted_index` reconstructs the
abstract from OpenAlex's `{word: [positions]}` map. Bounded (`WORKS_SAMPLE`=200), cached, fail-closed. Identity-agnostic
by construction — no author field is fetched.

**Task 2 — `compute_overlooked` engine (`app/backend/methods/overlooked.py`, new).** axis label → topic
(`fetch_topic_for_subject`) → topic works → drop in-library (`find_existing_paper_by_identity`) → **relevance** =
cosine(axis vector via `_embed_axis`, on-device-embedded abstract) → **percentile** of `cited_by_count` among
same-`publication_year` peers in the fetched sample → keep candidates at/below `low_percentile` (0.25) with a
non-null percentile, rank by relevance, cap (25). Returns `OverlookedCandidate` (the two separate inputs + metadata;
**no author field, no composite score**).

**Task 3 — cache table + repo.** `overlooked_candidates` (`schema_findings.py`, migration `0046`, re-exported from
`schema.py`) scoped by `axis_id`, storing `relevance` + `year_percentile` (NULL-able) — **no author column**.
`overlooked_repo.replace_overlooked_candidates` (authoritative refresh) / `read_overlooked_candidates` (ranked by
relevance), mirroring `gap_repo`.

**Task 4 — async job + endpoints (`routers/overlooked.py`, new).** `POST /overlooked/refresh {axis_id}` (202 → job),
`GET /overlooked/refresh/{job_id}`, `GET /overlooked?axis_id=` (reads the cache, filtering dismissed / now-in-library
at read time). New `overlooked_lens_jobs` JobStore. The refresh runs its fetch phase **fetch-outside-lock** (inc D):
`OpenAlexSourcesClient` gained `cache_engine`/`with_cache_engine`, so the topic+works fetches self-commit to the cache
and the final persist is a short `run_write`. Add/Dismiss **reuse** `/gaps/add` + `/gaps/dismiss`.

**Task 5 — frontend (`app/frontend/js/36b_overlooked.jsx`, new).** `OverlookedLensModal` (a header **Overlooked**
button beside **Gaps**; wired through `40_app.jsx` + `10_pdf_layer.jsx`). Per axis; each row shows **two distinct
chips** — `relevance {cosine}` and `cited N · Nth-percentile for {year}` — never a fused number; a DOI-linked title;
Add/Dismiss. Honest empty state. Reuses the existing `gap-row`/`axis-modal` CSS (no new styles). Placed at `36b`
(beside the sibling gap-finder `36`) rather than the plan's `08z` (which sits among the citation-equity chunks).

**Task 6 — gates.** Security audit `2026-07-16_overlooked-work-lens.md` **PASS**; QA **route 72** (0 uncovered API
surfaces); credit-the-lineage (Merton 1968 in-panel + NOTICES); help section "Finding work the field overlooked";
changes.md + this note.

## Key technical detail

- **The two inputs are never fused.** `relevance` (a local cosine, checkable) and `year_percentile` (citations vs.
  same-year topic peers) are stored, transported, and rendered as **two separate values**; there is no code path that
  multiplies or sums them, and no `score` field anywhere. `_percentile_rank(x, peers)` = fraction of same-year peers
  cited *fewer* times than `x` (low = under-cited). A year with `< min_year_peers` (5) yields a **null** percentile →
  that work is **withheld**, not surfaced with a guessed rank (silence-not-a-certificate).
- **Identity-agnostic by construction.** No author/identity is fetched (`fetch_topic_works` doesn't select it),
  stored (no column), transported (no response field), or shown. Authors are re-fetched only if the user chooses to
  **Add** (via the existing `import_citing_work`/Crossref path).
- **Egress = public metadata only.** Only the axis label (→ `/topics?search=`) and the topic id (→ `/works`) leave;
  candidate abstracts come back and are embedded **on-device**. Not the Gemini gate. Proven by
  `test_fetch_topic_works_transmits_only_the_topic_id`.
- **Naming collision avoided.** A pre-existing `overlooked_jobs` / `/methods/citation-equity/overlooked` /
  `methods/overlooked_work.py` feature (#25 SP2 — a per-paper reference-list *remediation*) is unrelated; this lens
  uses `overlooked_lens_jobs`, `/overlooked/*`, and `methods/overlooked.py`.

## Manual verification script (UI — OWED; no browser automation in-session)

1. Start the app (`uvicorn … --port 8888`); open the library. Confirm an **Overlooked** button in the header beside
   **Gaps**.
2. Click it → the modal opens with an axis picker defaulting to "Choose an axis…"; **Refresh** is disabled until an
   axis is chosen.
3. Pick an axis with scored members → **Refresh**. Confirm it POSTs `/overlooked/refresh`, polls, then lists rows —
   each with **two separate chips** (relevance + `cited N · Nth-percentile for {year}`), a DOI-linked title, Add/Dismiss.
4. Confirm no composite/"hidden-gem" score, no author field, and the honest empty/low-peer hint.
5. **Dismiss** a row → it doesn't resurface; **Add** → it imports metadata-only and drops from the list on re-GET.
6. Confirm (network tab) only OpenAlex `/topics` + `/works` requests fire (the axis label + topic id) — no abstract/
   library text, no genai host.

(Flagged as owed per the verification protocol — a static + esbuild-compile pass verified the JSX assembles, but a
live visual check was not run this session.)

## Pytest

`tests/test_overlooked.py` — 9 passing (fetch_topic_works incl. egress-shape; compute_overlooked surfaces/percentile/
exclude; repo round-trip; endpoints refresh→list, dismiss filter, validation). `tests/test_frontend_assembly.py` —
+1 overlooked-panel guard. Full suite: <filled in Task 7>.
