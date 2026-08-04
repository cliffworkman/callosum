<!-- qa-coverage
api: /papers/{paper_id}/reference-integrity*, /reference-integrity/*, /wip/manuscripts/{manuscript_id}/reference-integrity*, /wip/reference-integrity/*
fe: 08j_reference_integrity.jsx, 10b_libmenus.jsx, 10_pdf_layer.jsx, 37b_meta_reference.jsx, 10f_wip.jsx
-->

# ROUTE 68 - Meta Reference List (reference-integrity signals)

**Tier:** 2 local-stateful + public metadata egress
**Goal:** Exercise the Meta Reference List subsection of **Work -> Meta-Reference** and prove it stays a narrow reference-signal surface:
detectors remain distinct, review state is per citation instance, stale dismissals reopen on materially new signals,
and clearing signals never promotes a paper into a positive state.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). Use papers with DOI-backed Semantic Scholar references,
plus a paper whose Semantic Scholar reference edge is empty but whose OpenAlex `referenced_works` returns at least
one cited work. Include one reference that cannot be resolved by the available metadata clients and one DOI that
appears in the retraction registry fixture. Register listeners before navigation.

## Standing Assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **Signal, not verdict.** UI/API must not say fake, fabricated, invalid, bad citation, verified good, or clean paper.
- **Detector distinction.** Could-not-verify, known-retraction, and local-propagation signals use different labels and
  evidence; a retraction must not render as the same generic warning as a search miss.
- **Per-instance review.** Dismissal in Paper A must not suppress the same referenced entity in Paper B.
- **No positive promotion.** After every reference signal is dismissed, the only change is the reference-derived active
  count; no paper quality/category/status becomes positive.
- **WIP is a separate local-only path with its own persistence (inc 447).** A WIP manuscript's reference-integrity
  signals persist in dedicated `wip_reference_signals`/`wip_reference_reviews` tables, never in `reference_instances`
  (whose `citing_paper_id` is a Library-paper-only FK). The candidate list is the manuscript's own "cited"
  `wip_references` links, never a Semantic-Scholar/OpenAlex discovery call — no manuscript file text or path leaves
  the machine at any point in this flow.

## Adversarial Checklist

- Unknown paper id / job id / citation-instance id -> 404, not a crash.
- Selected paper with no DOI -> honest 422/no-reference-list message.
- Double-click **Check references**; navigate away and return during polling.
- Select several Library papers, including at least one no-DOI paper, and run bulk **check refs**.
- Force or simulate one provider returning empty/failed data; confirm source coverage stays visible and fallback results
  are not erased.
- Resize to `375x812`; no horizontal overflow and controls remain keyboard-reachable native buttons.
- Refresh after dismissing an unchanged signal set -> dismissal persists.
- Add a new retraction signal after a prior dismissal -> item reopens as unreviewed.

## Steps

1. Select a DOI'd paper. Open **Work -> Meta-Reference**. Confirm the **Meta Reference List** subsection appears
   first (above Citation concentration and How it's cited, on the same scrollable panel).
2. Click **Check references** (`POST /papers/{id}/reference-integrity/run`, poll `GET /reference-integrity/run/{job}`).
   Confirm the poll response and UI show determinate progress, then rows show cited reference, signal type, reason,
   evidence source, review state, and optional context hint.
3. Expand **Source coverage for last run**. Confirm Semantic Scholar/OpenAlex/retraction/detector status is visible,
   including empty/not-searched/failed/partial states, and the summary shows a last-checked timestamp when references
   were processed.
4. Confirm a metadata search miss is labeled **Could not verify** / **Could not verify with available sources** and is
   not described as proof of absence.
5. Confirm a known retraction row says **Known retraction signal** and exposes registry/source evidence.
6. Run a paper with no Semantic Scholar reference contexts but with OpenAlex `referenced_works`. Confirm OpenAlex is
   shown as the source, and a retrieved OpenAlex work record is not downgraded into a could-not-verify signal.
7. Trigger partial/failed coverage and confirm the button reads **Retry reference check**.
8. Run the checker on a second paper citing the same active referenced entity. Confirm it gets a
   **Previously flagged in your library** propagation signal.
9. Use the check control on Paper A (`POST /reference-integrity/instances/{id}/review`, `dismissed`). Confirm Paper B
   remains unreviewed/active.
10. Use the X control on another row (`confirmed_problem`). Confirm confirmed concerns keep the active count.
11. Dismiss every valid signal in one paper. Confirm the reference warning count clears, with no positive paper state.
12. Trigger a materially new retraction signal for a previously dismissed citation. Confirm `reopened` is visible and
   the item returns to **Requires review**.
13. Select multiple Library papers and click **check refs** in the bulk bar (`POST /reference-integrity/run-selected`).
   Confirm the poll shows paper-level progress, no-DOI papers are skipped visibly in the completed summary/API payload,
   DOI papers get the same per-paper Meta Reference List results, and paper-card warning badges refresh afterward.
   Confirm the Library switches to a clearable **Reference checks** filter containing papers with active reference
   signals.
14. Click a paper-card **ref signal** badge. Confirm the paper is selected, **Work -> Meta-Reference** opens scrolled
    to the **Meta Reference List** subsection, and the badge text/tooltips frame the count as active signals rather
    than a paper-quality verdict.
15. Open a WIP manuscript with at least one Library paper linked as **cited** (one retracted, one clean) via the
    References tab. Open **Work -> Meta-Reference** for the manuscript. Confirm **Check references**
    (`POST /wip/manuscripts/{id}/reference-integrity/run`, poll `GET /wip/reference-integrity/run/{job}`) surfaces the
    retracted reference with a **Known retraction signal** badge and clicking its title opens the Library paper.
16. Dismiss/confirm the WIP reference's signal (`POST /wip/reference-integrity/{reference_id}/review`). Confirm the
    same receipt appears in the manuscript's own **Checks** tab (`WipDetails`), not just in Work -> Meta-Reference.
17. Link a paper as **background-reading** (not cited). Re-run the check. Confirm it is never included in
    `checked_count` or the results — only "cited" references are checked.
18. Confirm **How it's cited** shows the plain no-DOI explanatory note with no interactive controls for a WIP
    manuscript (citation-context stays permanently out of scope for WIP).

## Pass Criteria

- Meta Reference List runs, persists, and survives reload/restart.
- Review controls expose the exact three-state model: unreviewed, dismissed, confirmed concern.
- Warning overview follows active-count rules exactly.
- No hidden score, global whitelist, positive verification state, or methods-QA side effect is introduced.
- Mobile and keyboard interaction remain usable.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_68_reference_integrity.md` + `screenshots/` (see `_TEMPLATE.md`).
