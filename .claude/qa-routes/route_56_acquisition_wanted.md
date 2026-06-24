<!-- qa-coverage
api: POST /papers/{paper_id}/acquire-oa, /papers/acquire-oa*, /wanted*
fe: 26_wanted.jsx
-->

# ROUTE 56 - Acquisition and wanted list

**Tier:** 2 egress/external
**Goal:** Exhaust OA acquisition, wanted-list management, coverage, sync, and re-check flows while keeping the default run hermetic.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Run hermetically by default:** use `create_app(...)` with injected fake OpenAlex/Crossref/acquire registry clients and fixture PDF downloads so no real external fetch is needed. Keep `CALLOSUM_ALLOW_DATA_EGRESS` unset unless running an explicit integration pass. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected; bad DOI on re-resolve/import-like fields
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open Wanted (`26_wanted.jsx`). Confirm list (`GET /wanted`) and coverage (`GET /wanted/coverage`) render with transparent counts.
2. Add wanted items by paper id, DOI, PMID, and title (`POST /wanted`). Confirm invalid blank item returns validation and no crash.
3. Delete a wanted item (`DELETE /wanted/{item_id}`), reload, and confirm it stays removed.
4. Sync from library (`POST /wanted/sync-library`). Confirm added count is visible and repeat sync is idempotent.
5. Start wanted re-check (`POST /wanted/recheck`) with fake registry and poll (`GET /wanted/recheck/{job_id}`). Navigate away mid-job and return.
6. Trigger per-paper OA acquisition (`POST /papers/{paper_id}/acquire-oa`) and poll (`GET /papers/acquire-oa/{job_id}`). Confirm found/not-found/imported states and OA color/version/source are displayed without overstating legality.
7. Directly open fake job ids and non-existent wanted ids. Confirm clean 404 states.

## Pass criteria

- Wanted add/delete/sync/recheck and per-paper acquire complete through UI polling.
- Hermetic default uses injected fake clients; no genai-host requests with egress unset.
- OA status is evidence/count based; no verdict language or hidden score.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_56_acquisition_wanted.md` + `screenshots/` (see `_TEMPLATE.md`).

