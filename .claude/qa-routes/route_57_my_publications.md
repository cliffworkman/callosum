<!-- qa-coverage
api: /my-publications*
fe: 31_mypubs_dashboard.jsx, 32_mypubs_missing.jsx, 33_mypubs_pubs.jsx, 34_mypubs_citing.jsx
-->

# ROUTE 57 - My Publications

**Tier:** 2 egress/external
**Goal:** Exhaust profile, refresh, decisions, dashboard, domains, works import/dismiss, summary, starring, citing-paper import, and reset flows.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Run hermetically by default:** use `create_app(...)` with injected fake Crossref/OpenAlex/domain/summary clients so refresh, domain labeling, citing, and summary flows do not contact external providers. Keep `CALLOSUM_ALLOW_DATA_EGRESS` unset unless running an explicit integration pass. Register listeners before navigation.

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

1. Open My Publications dashboard (`31_mypubs_dashboard.jsx`). Load profile (`GET /my-publications/profile`) and dashboard (`GET /my-publications/dashboard`).
2. Edit profile (`PUT /my-publications/profile`) with ORCID/name variants. Confirm blank/invalid values validate cleanly.
3. Refresh publications (`POST /my-publications/refresh`, `GET /my-publications/refresh/{job_id}`) using fake clients. Navigate away mid-job and return.
4. Review missing/ambiguous works (`32_mypubs_missing.jsx`). Decide matches (`POST /my-publications/decide`), import (`POST /my-publications/works/import`), dismiss and undismiss works.
5. Open publications (`33_mypubs_pubs.jsx`). Star/unstar (`POST /my-publications/star`) and confirm key-publication state is visibly user controlled.
6. Generate domains (`POST /my-publications/domains`, `GET /my-publications/domains/{job_id}`), rename a domain (`POST /my-publications/domains/rename`), and confirm labels are editable signals, not truth.
7. Generate and edit public summary (`POST /my-publications/summary/generate`, `PUT /my-publications/summary`) with fake generator. Confirm provenance and user-edit state.
8. Open citing works (`34_mypubs_citing.jsx`). Load citing list (`GET /my-publications/citing/{work_id}`) and import one (`POST /my-publications/citing/import`).
9. Reset My Publications (`DELETE /my-publications`) only at the end of the disposable run; confirm dashboard returns to setup state.

## Pass criteria

- Every My Publications panel and endpoint completes through the UI.
- Hermetic default uses injected fake clients; no genai-host requests with egress unset.
- Domains, stars, and summaries are transparent signals/user choices, never hidden verdicts.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_57_my_publications.md` + `screenshots/` (see `_TEMPLATE.md`).
