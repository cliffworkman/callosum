<!-- qa-coverage
api: /funding-discovery/*
fe: 08k_funding_discovery.jsx, 08m_funding_results.jsx
-->

# ROUTE 69 - Funding Discovery

**Tier:** 2 local-stateful + public funding-metadata egress
**Goal:** Exercise the Theory-pane Funding Discovery flow and prove it keeps prospects, recurring schemes, and open
opportunities epistemically separate.

## Environment

Use a seeded library with one paper that has a rich abstract and one no-abstract paper with a descriptive title.
Configure a test Grants.gov adapter or a known low-risk query, plus local historical-award fixtures. Do not enable
licensed providers unless testing a licensed-provider policy route.

## Standing Assertions

- Console-error budget = 0.
- Funding Discovery appears directly beneath **Where to submit** in the Theory pane.
- Results are segmented into **Open Opportunities**, **Recurring Schemes**, and **Funding Prospects**.
- UI/API must not say recommended grant, likely to fund, funding probability, best match, perfect fit, or expected to
  reopen.
- A historical award is never rendered as an open opportunity.
- A recurring scheme always states that no current application window was verified unless a current source supplies one.
- Source coverage remains visible when a provider fails or is unavailable.
- Individual 990-PF donee names and home addresses are not shown in default UI.
- **Recent runs** can reload a completed run, including persisted AI-fit labels, without re-running discovery.
- Each result card shows a display-only fit triage panel that separates **Why this surfaced** from **What may need
  review** and states the evidence class without changing ranking, eligibility, saved state, or opportunity status.
- Display filters include review-oriented slices for eligibility review, missing current application surface, identity
  uncertainty, and stale AI-fit labels; these only hide/show visible cards.
- The **Saved funding** queue includes display-only filters for open/current items, prospects, needs-review items,
  changed-since-saved items, provider issues, no-current-window items, applying/planning items, and archived items.
- Saved funding rows show compact queue cues for status/current opportunity, workflow state, next deadline or linked
  opportunity, and latest refresh outcome before the row is expanded.
- The saved funding queue can be sorted by recently saved, deadline soon, changed-since-saved first, workflow state,
  open/current first, and archived last; sorting is display-only.
- Saved funding bulk actions can mark the currently visible saved rows as reviewing or archived. The scope line must
  state how many visible saved items will be affected; only saved marker workflow state changes.

## Adversarial Checklist

- Unknown paper id -> 404, not a crash.
- Empty manual description -> 422.
- Overlong description -> 422.
- Provider failure -> partial/failed source status, successful local results remain.
- Grants.gov empty result -> "No current opportunity records were surfaced from the sources searched," not "no grants
  exist."
- Mobile `375x812` -> no horizontal overflow.
- Save the same prospect twice -> idempotent saved item.

## Steps

1. Select a paper. Open **Theory -> Funding Discovery** and confirm it appears beneath **Where to submit**.
2. Run **Selected paper**. Confirm source coverage, segmented lanes, and evidence detail disclosures.
3. Switch to **Describe research**, paste a cross-domain research description, add field context, and run.
4. Confirm each card's **Why this surfaced** signals are inspectable and categorical.
5. Confirm each card's **What may need review** panel calls out weak/unresolved signals, eligibility uncertainty,
   identity uncertainty, stale AI-fit labels, or missing current application surfaces when present.
6. Exercise the display filters **Eligibility review**, **No current surface**, **Identity uncertain**, and **Stale
   AI-fit** when matching records are present; confirm exports and saved markers are unchanged.
7. Confirm an open federal opportunity has provider-backed status/deadline/source evidence.
8. Confirm a recurring scheme shows observed years and "No current application window verified."
9. Confirm a prospect shows historical funding evidence and no current application surface.
10. Save one opportunity/scheme/prospect and reload; saved state persists. Exercise the saved funding filters and sort
   controls and confirm they only hide/show/reorder saved rows. Confirm each visible saved row has compact queue cues
   before expansion. Use a bulk action on a filtered subset and confirm only visible saved rows change workflow state.
11. Open **Recent runs**, reload the completed run, and confirm result lanes, source coverage, saved markers, AI-fit labels
   where present, and **Export CSV** still use the reloaded run.

## Pass Criteria

- The tool works from selected paper and pasted description.
- Partial provider failure is non-destructive.
- Provider coverage is explicit.
- No hidden score, funding probability, or eligibility verdict appears.
- Journal Search, Meta Reference List, and methods-QA sections remain functional.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_69_funding_discovery.md` + `screenshots/`.
