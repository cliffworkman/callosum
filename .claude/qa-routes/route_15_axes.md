<!-- qa-coverage
api: /axes*
fe: 14_axes_edit.jsx, 15_axes.jsx, 16_axes_merge.jsx, 17_axes_suggest.jsx
-->

# ROUTE 15 - Axes, assignments, merge, and suggestions

**Tier:** 1 local-stateful
**Goal:** Exhaust axis creation, editing, scoring, assignment correction, merge, and egress-gated suggestion controls without allowing unapproved genai traffic.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register console/pageerror/request listeners before navigating.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open the axes sidebar. Confirm existing axes render with assigned/uncertain counts and no rank/verdict language.
2. Create an axis with label + description (`POST /axes`). Confirm it appears immediately, reload, and confirm persistence.
3. Edit label and description (`PATCH /axes/{axis_id}`). Confirm stale state is shown until re-score, not silently hidden.
4. Run score (`POST /axes/{axis_id}/score`, `GET /axes/score/{job_id}`). Poll through pending/running/done. Navigate away during one run and return; no orphan spinner.
5. Open clusters (`GET /axes/{axis_id}/clusters`). Confirm assigned, uncertain, and manual statuses are visible as signals, never truth labels.
6. Add and remove a manual paper assignment (`POST/DELETE /axes/{axis_id}/papers...`). Confirm manual rows are marked and survive re-score.
7. Open merge view (`16_axes_merge.jsx`). Merge two disposable axes (`POST /axes/merge`) and confirm the survivor has the combined label/description and assignments.
8. Open suggestion UI (`17_axes_suggest.jsx`). With egress unset, term suggestions and optimal-axis suggestions (`POST /axes/suggest-terms`, `POST /axes/suggest`, `GET /axes/suggest/{job_id}`) must fail closed with a clear egress-disabled message and no genai request.
9. Delete a disposable axis (`DELETE /axes/{axis_id}`). Confirm the UI removes it and a direct deep link to it handles 404 cleanly.

## Pass criteria

- Every declared surface is reachable and completable.
- 0 console errors / 0 page errors; no unexpected 4xx/5xx except deliberate validation/egress-disabled cases.
- No genai-host requests with egress unset.
- Axis counts and statuses remain signal-only; no composite quality verdict.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_15_axes.md` + `screenshots/` (see `_TEMPLATE.md`).

