# Overlooked-work lens (backlog #37, equity/integrity) — design spec

**Status:** approved via brainstorming (2026-07-16), after the rule-#9 Principles + A-A gate (below). Backlog #37,
Part 1, Signal 1 — "the Matthew effect, inverted" (`.claude/docs/future-tracks/opus4.8_future-tracks_equityintegritysignals.md`).

## Context / why

Callosum has a strong deterministic-audit spine; #37 imports HACKADEMIA's *attention/credit equity* commitment into
a **reading** tool in a principled form: make the literature's prestige/attention machinery inspectable so citation
counts don't silently do the user's thinking. This lens is that idea's headline instance — a **discovery** signal
that surfaces **external works highly relevant to one of the user's axes but under-cited for their vintage** ("work
you're likely missing because the field overlooked it, not because it's weak"). It is **mechanically distinct from
the gap-finder** (which follows citation *links*): this follows the gap between **relevance and attention**.

## Principles + A-A gate (rule #9)

- **Principles touched:** #2 signal-not-verdict, #6 silence-not-a-certificate, #7 no-opaque-score, #8 inspectability,
  #9 defaults-are-the-user's. **Closest worked example: #3 (Surfacing effect sizes)** — show each item beside its
  benchmark + provenance and let the user read the distribution; the misaligned twin fuses inputs into one composite
  and ranks.
- **Values layer:** deliberately **adopts an emergent value — the attention/credit face of equity** (A-A: adopt on
  purpose, in the *repointed non-accusatory* form, not by drift). Sits on the **no-accusation standalone veto**.
- **Misaligned easy path (declined):** a **"hidden-gem score"** (relevance × inverse-citations fused into one number,
  library ranked by it) or a model pronouncing "this is an overlooked gem"; and the **equity-as-exposure** trap —
  "the field wrongly buried this," or sorting *authors* by category (the exact error #25/inc-229 removed).
- **Aligned design (built):** a **surfacing signal with two separate, visible inputs** — per candidate, its **axis
  relevance** (local cosine similarity, checkable) *and* its **citations vs. a same-vintage baseline** (the raw count
  + the percentile) shown side by side, **never fused**; framed *"relevant to [axis]; low citations for its year —
  possibly overlooked, possibly just low-impact; your call"* (honors #6). **Identity-agnostic** (measures the *work's*
  attention-vs-relevance, never who wrote it), **pull-not-push** (a panel you open), **augment-never-filter** (never
  auto-adds/drops), provenance one click away.

## Scope (v1, approved)

**External discovery**, **relevance by local embedding similarity**. Per axis, on demand.

## Pipeline

1. **Axis → topic.** Resolve the axis label to an OpenAlex topic id via the existing
   `integrations/openalex/sources.py::fetch_topic_for_subject(conn, subject)` (`/topics?search=`; only the label
   leaves the machine). No topic → honest empty state.
2. **Candidate works.** Fetch the topic's works — `/works?filter=primary_topic.id:{topic}` selecting
   `id,doi,title,publication_year,cited_by_count,abstract_inverted_index` — capped (~200; bounded, cached, fail-closed,
   the inc-74 pattern). Add a `fetch_topic_works` method to the sources client (mirrors `fetch_candidate_sources`).
3. **Exclude in-library.** Drop candidates whose DOI is already in the library (`find_existing_paper_by_identity`) —
   this is *discovery*, so only works you lack.
4. **Relevance (local).** Reconstruct each candidate's abstract from its inverted index (a small local helper), embed
   it locally with the app embed model, and score cosine similarity to the **axis vector** (reuse
   `axis_scoring._embed_axis` / the axis's local embedding). Abstracts are embedded **on-device**; nothing but the
   topic id/label egresses.
5. **Vintage baseline (local, honest).** Within the fetched topic sample, compute the `cited_by_count` distribution
   **per `publication_year`**; each candidate gets a **percentile among same-year topic peers**. "Under-cited for its
   vintage" = below a stated cutoff (e.g. 25th percentile), computed only where a year has enough same-year peers to
   be meaningful (else the work is shown without a percentile, stated honestly).
6. **Surface.** Keep low-percentile candidates, rank by **relevance** (descending), cap the list. Each row shows the
   two separable inputs (relevance + `cited_by N · Nth-percentile for {year}`), the title/authors/year, and a DOI
   link. **Add** (reuse the gap-import flow → metadata-only into the general library) + **Dismiss** (reuse the
   gap-dismiss store so it can't resurface). Honest empty state ("nothing surfaced — not evidence none exists").

## Surfaces / architecture

- **Backend:** a pure `methods/overlooked.py::compute_overlooked(conn, *, axis_id, openalex_client, embed_model,
  vector_store, …)` (candidate fetch + local relevance + local percentile + exclude-in-library → ranked candidates),
  a persistent cache (reuse `gap_candidates`-style storage, scoped by `axis_id`, or a small sibling table), and an
  **async job** + `POST/GET /overlooked/refresh` + `GET /overlooked?axis_id=` (mirrors the gap-finder router, and —
  inc D — runs its fetch phase **fetch-outside-lock** via the OpenAlex client's `cache_engine`).
- **Frontend:** an "Possibly overlooked" panel (a new METHODS/discovery surface or a tab beside the gap-finder),
  each row with its two visible inputs + source link + Add/Dismiss. Pull-not-push (opened on demand per axis).
- **Credit the lineage** (`.claude/CREDIT-THE-LINEAGE.md`): the lens operationalizes the Matthew-effect literature —
  credit it in-context + offer the source(s) to the library.

## Non-goals (v1)

A trained "expected-citations" trajectory model (the doc's honest caveat — v1 uses the local same-year percentile,
not a model); any composite "hidden-gem"/quality score; any author-identity or category signal; auto-add; a global
default that pushes results (it's a lens the user opens).

## Testing / gates

- Unit: topic resolution + `fetch_topic_works` (injected fetcher, no network); inverted-index → abstract; the
  per-year percentile (a work low among same-year peers surfaces; a high one doesn't; too-few-peers → no percentile);
  in-library exclusion; **no composite-score field** + **no author/identity field** on any output (guard tests);
  honest "not overlooked, possibly low-impact" copy present (`test_no_hidden_gem_language`, mirrors transparency's
  `test_no_accusatory_language`).
- **Security audit** (new OpenAlex fetch path + async job + endpoint): input validation on `axis_id`/topic id
  (`^T\d+$`), egress bounded/cached/fail-closed, no library text transmitted (only topic id/label), resource caps.
- **QA route** (new `/overlooked/*` surfaces + honesty assertions: no score, no accusation, signal-not-verdict,
  provenance). **Experience pass** (the *corpus builder* persona — does the lens help them find overlooked work
  without moralizing/scoring). Increment notes + changes.md + backlog (#37 signal 1 done).
