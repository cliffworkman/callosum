# Increment 386 — My Publications grounded citation gaps

**Date:** 2026-07-25
**Status:** implemented; local gates complete

## Outcome

My Publications Layer 4 now starts with an LLM-free **Citation gaps** panel. An explicit refresh identifies
references shared by at least two confirmed own publications, follows the bounded OpenAlex citing-work
neighborhood for those anchors, and surfaces external works that none of the scanned own publications directly
cites.

Each candidate shows visible shared-reference and source-publication counts. **Why this surfaced** expands to
the exact shared references and the user's clickable publications behind each one. A candidate opens in
OpenAlex; **Add** imports DOI-backed metadata into the general library through the existing deduplicating
Crossref-enrichment path, and **Dismiss** uses the existing reversible local gap preference.

## Key technical detail

- `app/backend/clustering/my_publication_gaps.py` scans confirmed My Publications memberships only; name-only
  candidates cannot characterize the user's citation neighborhood.
- The bounded graph walk checks at most 75 DOI-backed own publications, retains at most 20 references shared by
  two or more, reads at most the existing adapter's 200 citing works per anchor, returns 25 candidates, and caps
  authors, strings, and evidence sources.
- Candidate OpenAlex IDs must be `W\d+`. Directly cited works, the user's own works, existing library records,
  dismissed keys, and malformed metadata are excluded.
- Ordering is deterministic by the two visible graph facts—shared-reference count, then distinct source-
  publication count—followed by title/id. There is no hidden importance or quality score.
- Migration `0052_my_publication_citation_gaps` adds one JSON snapshot row. A full candidate/evidence/coverage
  set, including a genuine empty result, replaces atomically after successful computation. A failed refresh
  leaves the prior snapshot intact.
- `GET /my-publications/citation-gaps` is cache-only, revalidates cached models/IDs, filters newly imported,
  dismissed, or source-deleted rows at read time, and drops malformed cache content rather than returning 500.
- Only `POST /my-publications/citation-gaps/refresh` performs OpenAlex metadata work. It sends public DOI/work
  identifiers only—never PDFs, manuscript text, abstracts, notes, or an LLM prompt.

## Principles and experience

This is a retrieval candidate, not a verdict. The panel uses provenance indigo rather than verified green,
states OpenAlex/cap limitations, and explicitly says that no result is not a certificate of completeness.
Shared references are presented as a retrieval trail, not proof that the candidate belongs in a bibliography.

A corpus builder trying to expand their own intellectual neighborhood can discover the panel in My Publications,
see why each work surfaced, inspect both the external graph nodes and their own source records, then Add or
Dismiss without leaving a dead end. The browser walkthrough found those paths direct. The remaining friction is
topic scope: a user with several research programs will naturally want one or more existing research domains to
bound the scan. That is recorded in backlog #35 as the next Layer-4 slice because it requires a scoped cache/API
contract, not a cheap dropdown. Persona-agent dispatch was unavailable under the session's no-delegation
constraint, so the same goal-in-the-moment pass was driven directly.

## Manual verification

1. Set up My Publications with at least two confirmed DOI-backed publications that share OpenAlex references.
2. Open **My Publications** and find **Citation gaps** below Research domains.
3. Before clicking anything, confirm the panel says it is uncomputed and no OpenAlex request fires.
4. Click **Find citation gaps**. Confirm progress appears, then the coverage line names checked/total
   publications, DOI omissions, shared anchors, and any scan cap.
5. Expand **Why this surfaced** on a candidate. Open the shared reference in OpenAlex and click each own-
   publication title; confirm the corresponding local record becomes selected.
6. Add a DOI-backed candidate and dismiss another. Confirm both leave the cached list without another scan and
   the added record appears in the general library, not My Publications.
7. Exercise an empty-result fixture and confirm the panel refuses to imply completeness.
8. Resize to 375×812 and confirm the panel, actions, disclosure, and coverage copy do not overflow.

## Verification

- Focused citation-gap/gap-finder/My-Publications/migration/frontend suite: **114 passed**.
- Browser smoke: **4 passed**; focused grounded-evidence path also passed at **375×812** with zero console/page
  errors.
- Alembic upgrade + model-drift check: pass.
- Ruff check/format, source line budget, QA surface map, help sync, and diff hygiene: pass.
- Full project suite: **1597 passed, 1 skipped** in 744.59 seconds.

## Remaining Layer-4 scope

Domain-scoped citation gaps, emerging citing-topics, candidate collaborators, and optional LLM narration over
already-grounded data remain. The first three deterministic surfaces should exist before narration is considered.
