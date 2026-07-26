# Increment 390 — grounded emerging My Publications citing topics

**Date:** 2026-07-26
**Status:** implemented; local gates complete

## Outcome

My Publications Layer 4 now includes **Emerging citing topics** beside Citation gaps. An explicit refresh compares
works citing the user's confirmed publications in the last three complete calendar years with the preceding three.
A topic surfaces only when its OpenAlex primary-topic count is at least two in the recent window and exceeds the
earlier count.

The card exposes recent count, earlier count, and their plain difference. Expanding it shows every retrieved citing
work behind both surfaced counts and the exact confirmed own publications each work cites. The increase is framed as
a bounded description of OpenAlex records, not a forecast that a field is growing, an importance ranking, or a
quality score.

## Architecture and boundaries

- `OpenAlexCitingTopicsClient` takes at most 50 validated own-work ids and performs one union query per three-year
  window, reading at most two current 100-result cursor pages per window. It selects only work identity, title/year,
  authorships, primary topic, and referenced works needed to reconstruct the local evidence link.
- The service resolves confirmed DOI-backed My Publications members only. One citing work contributes to one
  OpenAlex primary topic, is deduplicated by validated `W…` id, and retains the intersection of its references with
  the scanned own-work ids.
- Topics sort by the visible absolute increase, then recent count, then stable label/id; there is no hidden score.
  At most six topics surface. Because a work has one primary topic, every retrieved work behind a surfaced aggregate
  can remain in the snapshot without an evidence-list truncation.
- The last completed year anchors both equal windows, avoiding a partially completed current year. Coverage exposes
  DOI omissions, unresolved own works, missing primary topics, the 50-publication cap, both 200-work window caps,
  active scope, and the exact year ranges.
- The all-publications and multi-domain-union controls reuse Increment 389's server-validated membership keys.
  Independent atomic snapshots are capped at 16. GET and scope switching are local-only; only explicit Find/Refresh
  runs OpenAlex work.
- A provider/partial-window failure or wholly unresolved DOI-backed scope fails the job and preserves the prior
  snapshot. A genuine empty 200 result remains distinguishable and replaces successfully.
- Migration 0054 adds the scoped JSON snapshot table. Like the additive Increment-386 cache migration, downgrade is
  intentionally non-destructive because migration 0001 creates current metadata on fresh databases.
- There is no LLM use, new external host, dependency, PDF/manuscript text egress, file access, or credential surface.

## Principles, values, and experience

The change primarily touches Principles 1, 2, 4, 6, 7, 8, and 10. The nearest worked example is effect-size
surfacing: keep the inputs separable and inspectable instead of collapsing them into a composite verdict. The easy
misalignment would have been a fluent “hot topics” forecast or opaque trend score over uninspectable classifications.
The aligned implementation keeps the deterministic OpenAlex substrate authoritative, exposes both window counts,
routes the aggregate to every retrieved work and own-publication link, and states what the scan did not cover.

The future-track drift pass classifies this as **confirmed**: it extends the already-built provenance, local-first,
and explicit-refresh prospection posture. It adopts no new emergent value, triggers no divergent value tension, and
does not approach a veto-level boundary.

A corpus builder's goal-in-the-moment pass asked: “What is newly showing up around the work that cites this research
program, and can I verify that impression before acting on it?” Chromium found the panel discoverable beside Citation
gaps; the recent/earlier comparison was legible; domain scope switched through the exact encoded key; and expanding
the card reached a citing work and its own-publication source. The 375×812 pass had no horizontal overflow and the
console/page-error budget stayed zero. No follow-up UX finding remains.

## Manual verification

1. Configure My Publications with at least two confirmed DOI-backed works and optionally generate two research
   domains.
2. Open **My Publications → Emerging citing topics**. Confirm the uncomputed state makes no OpenAlex request.
3. Leave **All publications** selected or select one/more domain chips. Confirm multi-select is an explicit union
   and switching to a cached scope performs a local GET only.
4. Click **Find emerging topics** / **Find scoped topics**. Confirm progress is visible while the job runs.
5. Confirm coverage names the active scope, both complete three-year windows, resolved/total publications,
   retrieved work counts, omissions, and caps.
6. Confirm every card shows a recent count, earlier count, and plain positive difference; there is no score or
   forecast language.
7. Expand a topic. Open its OpenAlex topic/work links and click each own-publication title; confirm the expected
   local library record becomes selected.
8. Exercise provider failure and a real empty result. Confirm failure preserves the prior snapshot while empty
   success stores honest no-result language.
9. Resize to 375×812 and confirm the scope chips, count block, and expanded evidence do not overflow.

## Verification

- Focused My Publications/OpenAlex/migration/frontend/help/startup suite: **144 passed**.
- Full Chromium smoke: **5 passed**, including grounded-prospection domain scope, evidence expansion, local source
  routing, 375×812 overflow, and zero console/page errors.
- Ruff check/format, 399-file source line budget, frontend build/assembly, help sync, QA surface map, Alembic fresh
  upgrade/model drift/full downgrade, and diff hygiene: pass.
- QA surface map: **315/315 API** and **1390/1411 frontend**; the same 21 frontend items remain report-only and
  every gated surface is claimed.
- Full project suite against the final tree: **1623 passed, 1 skipped** in 731.09 seconds.
