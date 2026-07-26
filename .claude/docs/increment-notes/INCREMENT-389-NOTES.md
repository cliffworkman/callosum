# Increment 389 — domain-scoped My Publications citation gaps

**Date:** 2026-07-26
**Status:** implemented; local gates complete

## Outcome

My Publications Layer 4 can now bound grounded citation-gap discovery to one or more existing research domains.
The default remains **All publications**. Selecting domain chips scans the union of their confirmed
My-Publications members, and each all/domain combination keeps its own atomic local snapshot. Switching back to
a computed scope is a cache-only read; it never silently performs OpenAlex work.

The candidate contract is unchanged: every surfaced work carries the shared references and exact clickable own
publications that caused it to surface, directly cited/own/existing/dismissed works remain excluded, ordering uses
only visible evidence counts, and silence is never presented as completeness.

## Architecture and boundaries

- `my_publication_gap_scope.py` derives a stable domain key from sorted membership ids. The browser submits at
  most eight of those opaque keys; the backend resolves them against the current persisted decomposition and
  rejects malformed/stale keys before cache access or background work. It never accepts a caller-authored paper
  list or domain label.
- The citation-gap service accepts an optional server-resolved paper-id set and intersects it with confirmed
  My-Publications membership before DOI/OpenAlex work. Coverage distinguishes scoped totals from the full
  confirmed-publication count and names the selected domains.
- The dashboard API exposes each domain's membership-stable key. Renaming a domain therefore preserves its cache;
  a decomposition that changes membership naturally produces a new key and leaves the stale scope unreachable.
- `GET /my-publications/citation-gaps?domain_key=...` remains cache-only. Refresh accepts the selected key list,
  passes an immutable resolved scope into the job, and replaces only that scope after successful computation.
- Migration 0053 converts the original single-row table into keyed snapshots and preserves the existing row as
  `all`. Legacy SQLite JSON text is decoded before insertion rather than double-encoded; malformed rebuildable
  cache JSON falls back to an empty value instead of blocking database upgrade.
- The cache retains at most 16 all/domain combinations, pruning the oldest computed rows. Existing per-scan caps
  remain 75 DOI-backed publications, 20 shared anchors, 200 citing works per anchor through the adapter,
  25 candidates, and bounded strings/authors/evidence sources.
- There is no new external host, dependency, LLM use, file access, or manuscript/PDF text egress.

## User experience

The Citation gaps panel now places an **All publications** chip beside each named research domain. Multi-select
is explicitly described as a union, selected chips expose `aria-pressed`, and the action changes to **Find/Refresh
scoped gaps**. The coverage line names the active domain scope and its confirmed-publication denominator, so the
same candidate list cannot be mistaken for a library-wide scan.

A corpus builder's goal-in-the-moment pass asked: “Can I investigate this research program without findings from
my other work bleeding in, and can I switch back without paying for another scan?” Chromium proved the Domain A
click issued the exact domain-keyed request, replaced the all-publications candidate with the scoped result,
retained the expandable evidence trail, and stayed within 375×812 with zero console/page errors. The intended
next action—inspect, add, or dismiss a grounded candidate—is unchanged. Persona-agent dispatch was unavailable
under the session's no-delegation constraint, so the pass was driven directly.

## Manual verification

1. Generate at least two My Publications research domains, each with two DOI-backed confirmed publications.
2. Open **My Publications → Citation gaps**. Confirm **All publications** is selected and an ordinary read makes
   no OpenAlex request.
3. Select one domain. Confirm the action says **Find scoped gaps** and the refresh payload contains only its
   stable domain key.
4. Run the scan. Confirm coverage names that domain and every source paper in **Why this surfaced** belongs to it.
5. Select a second domain and confirm the scope is their union; deselect it and confirm the first cached result
   returns without recomputation.
6. Return to **All publications** and confirm its independent snapshot remains intact.
7. Rename a domain and confirm its membership-stable scope remains available. Change decomposition membership
   and confirm the stale key fails closed rather than selecting arbitrary publications.
8. Resize to 375×812 and confirm the chips wrap without horizontal overflow.

## Verification

- Focused service/API/domain/shared-gap/migration/frontend suite: **135 passed**.
- Post-review empty-domain control guard slice: **105 passed**.
- Chromium smoke: **5 passed**, including a real domain-keyed scope switch, evidence expansion, and 375×812
  overflow check with zero console/page errors.
- Alembic fresh upgrade, Increment-386 snapshot preservation, startup migration, and zero model-drift checks:
  pass.
- Ruff check/format, 394-file source line budget, frontend build/assembly, help sync, and diff hygiene: pass.
- QA surface map: **312/312 API** and **1382/1403 frontend**; the 21 frontend items remain explicitly
  report-only and every gated surface is claimed.
- Full project suite against the exact final tree: **1613 passed, 1 skipped** in 1555.59 seconds.
