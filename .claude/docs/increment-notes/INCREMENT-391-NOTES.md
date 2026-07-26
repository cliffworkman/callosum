# Increment 391 — grounded authors citing your work

**Date:** 2026-07-26
**Status:** implemented; local gates complete

## Outcome

My Publications Layer 4 now includes **Authors citing your work**. An explicit refresh reuses the same bounded
OpenAlex citing-work windows as Emerging citing topics, then surfaces a stable author identity only when that
author appears on at least two retrieved citing works that together cite at least two confirmed own publications.

Cards show the two visible counts and no composite score. Expanding a card opens every retrieved citing work and
the exact local publications behind the counts. The author name links to the stable OpenAlex profile. The profile
author and author identities found on checked own-work authorships are excluded.

This closes deterministic My Publications Layer 4 for now. Optional LLM narration over already-grounded data remains
deferred.

## Architecture and boundaries

- `OpenAlexCitingTopicsClient` now retains up to 25 stable `{id, name}` author records per citing work while
  preserving its existing eight-name display list. Its normalized window cache key moved to `v2`, so older
  name-only cache rows cannot be mistaken for author-identity evidence.
- `OpenAlexCitingAuthorsClient` delegates the two cached three-year citing windows and adds one fixed,
  at-most-50-work `openalex:` batch query selecting only own-work ids and authorships. Results use the existing
  external API cache and fixed OpenAlex host/fetcher.
- `compute_citing_authors` resolves confirmed DOI-backed My Publications members, requires a valid server-stored
  OpenAlex profile id, excludes self/checked coauthors, deduplicates citing works, and applies both visible
  thresholds. Authors sort by cited-publication count, then citing-work count, then stable name/id; at most 12
  surface.
- Coverage names the six complete calendar years, scoped/DOI/resolved publication counts, retrieved citing works,
  own works whose authorships were returned, excluded coauthor identities, missing retained author ids, and
  publication/window/per-work authorship caps.
- Migration 0055 adds `my_publication_citing_author_cache`. All/domain-union scopes reuse Increment 389's
  server-validated membership keys, atomic replacement, and 16-scope bound. Ordinary reads are local-only.
- Read-time filtering removes deleted/no-longer-confirmed sources, recomputes both eligibility counts, and excludes
  the current profile id again. Provider failure or wholly unresolved DOI-backed scope preserves the prior snapshot.
- No LLM, new host, dependency, credential, PDF/manuscript egress, filesystem, parser, upload, or executable surface
  was added.

## Principles, values, and experience

The change touches Principles 1, 2, 4, 6, 7, 8, and 10. The closest worked example is evidence-backed effect-size
surfacing: expose separable inputs and their basis rather than collapsing them into a verdict. The easy
misalignment was a ranked “best collaborators” list or an inferred fit score over names. The aligned surface is
instead titled **Authors citing your work**, uses stable provider identities, exposes both counts and every paper
behind them, and offers only inspect-the-work navigation.

The future-track drift pass classifies the graph/evidence mechanics as **confirmed**. The people-facing label is
where the A-A standalone no-accusation boundary is load-bearing: the surface is private, makes no judgment about a
person, and treats “no coauthorship found” as a bounded metadata result rather than a historical fact. No emergent
value was adopted and no divergent tension remains.

A corpus builder persona, driven directly against a migrated and seeded disposable fixture, asked: “Who is
repeatedly engaging with more than one part of this research program, and can I inspect the exact work before
deciding whether it matters?” The author/work evidence and active coverage were legible, and the 375×812 expanded
view had no horizontal overflow. The walkthrough found a real dead end inherited by all three prospection panels:
local publication buttons passed an object to numeric selection state and triggered `/papers/[object Object]`.
The same-increment fix now sends `paper_id`; a repeat walkthrough selected **Own publication A**, issued numeric
`/papers/1` requests, and found no object-valued request. No UX follow-up remains.

## Manual verification

1. Configure My Publications with a resolved OpenAlex profile and at least two confirmed DOI-backed works.
2. Open **My Publications → Authors citing your work**. Confirm an uncomputed scope performs a local GET only.
3. Leave **All publications** selected or select one/more domain chips. Confirm every combination has an independent
   local snapshot and stale membership keys fail with 422.
4. Click **Find citing authors** / **Find scoped authors**. Confirm progress is visible while OpenAlex is queried.
5. Confirm coverage names the six complete years, resolved publications, returned own-work authorships, excluded
   coauthors, missing ids, and caps.
6. Confirm every card shows cited-publication count plus citing-work count, with no fit/recommendation score.
7. Expand a card. Open the author and every citing work in OpenAlex; select every local own-publication link and
   confirm the correct record opens in Details.
8. Exercise provider failure and a real empty result. Failure must preserve the prior snapshot; empty success must
   store honest no-result language.
9. Resize to 375×812 with evidence expanded and confirm no document or panel overflow.

## Verification

- Affected My Publications/OpenAlex/API/persistence/migration/frontend/help suite: **143 passed**.
- Full project suite: **1632 passed, 1 skipped** in 716.72 seconds.
- Headed desktop + 375×812 disposable-fixture walkthrough: stable author/work links, numeric local-paper routing,
  expanded evidence, no object-valued request, and zero horizontal overflow.
- Ruff check/format, 404-file source line budget, frontend build/assembly, help sync, Alembic fresh/model/startup
  gates, security audit, QA surface map, and diff hygiene: pass.
- QA surface map: **318/318 API** and **1398/1419 frontend**; the same 21 frontend items remain report-only and
  every gated surface is claimed.
