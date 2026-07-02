# Increment 245 — PUBLISHERS "where to submit" journal-finder (backlog #40, SP1a: backend engine + endpoint)

## Implemented

The graduation of backlog #40 — the deliberately-controversial "where to submit" tool, built to the principled shape
its two future-track docs (`opus4.8_future-tracks_publishersmethodstool.md` + `…_publisherschoicegate.md`) worked out.
**SP1a = the backend engine + the async endpoint** (SP1b = the METHODS panel + the visible open-science weighting +
the first-use no-default choice gate). Maintainer scoping (AskUserQuestion): **full principled core · OpenAlex + DOAJ ·
both inputs (a library paper OR a pasted abstract)**.

**What it does:** from an abstract, derive a candidate-journal pool **from a topic** (never the abstract), enrich each
journal's facts (OpenAlex `/sources` + DOAJ), embed the abstract **locally** (SPECTER), and return a **uniform,
fully-sourced factual profile** per journal ranked by local fit — optionally re-ordered by an open-science `weighting`
(0.0 = fit-only). **No composite score, no "predatory" label; every candidate appears (incl. closed journals); the
abstract never leaves the machine.**

Files:
- `integrations/openalex/sources.py` (NEW) — `OpenAlexSourcesClient` (root host `https://api.openalex.org`; injectable
  `fetcher`; `integrations.api_cache`; `resolved_mailto`; fail-closed):
  - `fetch_topic_for_subject(conn, subject)` — `/topics?search=` → top topic id (`^T\d+$`); subject a bound param.
  - `fetch_candidate_sources(conn, topic_id, cap)` — `/works?filter=primary_topic.id:<T>&select=primary_location`,
    aggregate distinct `primary_location.source` by frequency → `list[SourceStub]` (validated `^T\d+$`/`^S\d+$`).
  - `fetch_source_details(conn, source_ids)` — batch `/sources?filter=openalex_id:S1|S2|…` (≤50/call) → `{sid:
    SourceMeta}` (is_oa, is_in_doaj, apc_usd, summary_stats 2yr-mean-citedness + h-index, works_count, homepage,
    x_concepts, issn/issn_l, type).
- `integrations/doaj/journals.py` (NEW) — `DoajJournalsClient.fetch_journal(conn, issn)` → `DoajJournal` (apc
  amount+currency, waiver, license family, Seal, subjects, keywords); ISSN `^\d{4}-\d{3}[\dX]$`-validated; cached;
  fail-closed; optional `CALLOSUM_DOAJ_API_KEY` header (write-only).
- `app/backend/methods/publishers.py` (NEW, pure) — `JournalProfile` + `PublishersReport` (+ `to_dict`);
  `derive_oa_color` (diamond/gold/oa-other/closed); `build_profiles(candidates, doaj_by_issn, *, abstract,
  embedding_model, weighting, top_k)` — local unit-cosine fit + an internal openness ordering key (never displayed) +
  `elevated_for` (goods shown only when weighting>0). No `*score*` field anywhere.
- `app/backend/api/routers/publishers.py` (NEW) — async `POST /methods/publishers/run` (paper_id XOR abstract+subject;
  422 on ambiguous/missing/no-DOI, 404 on missing paper) + `GET /methods/publishers/run/{job_id}`;
  `_run_publishers_job` (resolve topic + abstract → sources → details → per-OA DOAJ enrich → `build_profiles`);
  `_publishers_model` (injected `embedding_model` wins else cached SPECTER); `_resolve_topic_and_abstract`.
- `app/backend/api/app.py` — import `publishers`; `create_app(openalex_sources_client=None, doaj_journals_client=None)`
  → `api.state.*`; `api.state.publishers_jobs = JobStore()`; `include_router(publishers.router)` before `papers`.

## Key technical detail

**The abstract-never-transmitted architecture** (the load-bearing constraint). The candidate pool is seeded from a
*topic* — a library paper's OpenAlex `primary_topic` (paper path) or an OpenAlex `/topics?search=<subject>` resolution
of a user-typed subject keyword (paste path) — never from the abstract. The abstract is embedded **locally** (SPECTER)
and only re-ranks the pool. Only topic ids / a coarse subject keyword / source ids / ISSNs leave the machine (public
bibliographic metadata — the inc-183/227 posture, **NOT** the Gemini library-text gate). A recording-transport test
proves the abstract text appears in no outbound request.

**No composite score, structurally.** `build_profiles` computes an internal openness ordering key (OA color + Seal
bump) used only to blend with fit-rank when `weighting>0`; it is never emitted. The response carries per-journal facts
+ one labeled `fit` + `elevated_for` (the goods that moved a journal up). A test asserts no `*score*` key and no
"predator" substring in the response.

**No new dependency:** SPECTER rides the existing sentence-transformers stack (a ~440 MB first-use model download,
like MiniLM/overlooked-work); httpx already present. **No migration** (ephemeral job result).

## Manual verification script

1. `HF_HUB_OFFLINE=1 python -m pytest tests/test_publishers.py -q` → 13 passed.
2. `python tools/qa/build_surface_map.py check` → API 176/176, FE 771/771, 0 uncovered.
3. Live spot-check (the maintainer's, needs network): start the app, in a REPL call
   `OpenAlexSourcesClient().fetch_topic_for_subject(conn, "cognitive neuroscience")` → a `T…` id; then
   `fetch_candidate_sources` + `fetch_source_details` + a `DoajJournalsClient().fetch_journal(conn, "<issn>")` to
   confirm the live `/works?select=primary_location`, `/sources?filter=openalex_id:`, and `/api/search/journals/issn:`
   schemas the hermetic tests assume. (SP1b will drive this from the METHODS panel.)

## Pytest

909 → **922 passed, 1 skipped** (+13 new tests, all in `tests/test_publishers.py`). `ruff check` +
`ruff format --check` clean. No frontend build (SP1a is backend-only).

## Gates

- **Security audit** `.claude/security-audits/2026-07-01_publishers.md` — **PASS** (SSRF closed; abstract never
  transmitted; egress = public metadata not the Gemini gate; fail-closed + bounded; no new dependency; no migration).
- **Principles + A-A (rule #9)** — the future-track docs are the gate output; the vetoes (no composite score, no
  "predatory" label, every candidate listed, elevate-don't-denigrate) are encoded as acceptance-criteria tests.
- **QA (rule #10)** — new `route_60_publishers.md` declares the 2 API endpoints (`api: /methods/publishers*`) + the
  honesty assertions; the `fe:` panel claim lands in SP1b.

## Next (SP1b)

The METHODS **"Where to submit"** panel (`08e_methods_publishers.jsx`, `registerPaneSection` + `hideInReadOnly`): a
paper-picker OR abstract+subject input → async run/poll → uniform per-journal profile cards (each fact links to its
source; positive framing) + a visible **open-science weighting** slider (re-runs, always shows its state inline) + the
**first-use no-pre-selected-default choice gate** (local `app_settings` `publisher_weighting`/`publisher_sort`/
`publisher_defaults_set`, never transmitted; force the weighting AND ≥1 other publisher default together so the
weighting isn't the lone forced choice); headed-verified; help corpus "Where to submit". Deferred within #40 (no data
source yet): green-route / TOP-factor / regional-index legitimacy signals; user exclusion/filtering.
