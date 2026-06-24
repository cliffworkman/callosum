<!-- qa-coverage
api: GET /papers, GET /papers/item-types, GET /papers/{paper_id}, GET /papers/{paper_id}/chunks, PATCH /papers/{paper_id}, POST /papers/{paper_id}/re-resolve, DELETE /papers/{paper_id}, POST /papers/{paper_id}/restore, DELETE /papers/{paper_id}/permanent, POST /papers/trash/empty, POST /papers/export
fe: 10_pdf_layer.jsx, 25_detail.jsx
-->

# ROUTE 40 - Papers CRUD and trash lifecycle

**Tier:** 1 local-stateful
**Goal:** Exhaust paper listing, detail reads, edits, soft delete, restore, permanent delete, empty trash, and export on the disposable fixture DB.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation. This route mutates and deletes only the throwaway QA library.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected; bad DOI on re-resolve
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Load the library (`GET /papers`) and item-type filters (`GET /papers/item-types`). Confirm sorting, filtering, pagination, and empty states.
2. Open a paper (`GET /papers/{paper_id}`) and chunks (`GET /papers/{paper_id}/chunks`). Confirm details, chunks, and citation evidence remain transparent.
3. Edit metadata (`PATCH /papers/{paper_id}`) and reload. Confirm persistence and the user-edited guard.
4. Re-resolve DOI (`POST /papers/{paper_id}/re-resolve`) with a valid and invalid DOI. Confirm graceful resolved/unresolved/409 states.
5. Export selected papers (`POST /papers/export`) in visible formats. Confirm no hidden filtering or ranking affects exported rows.
6. Soft-delete a disposable paper (`DELETE /papers/{paper_id}`). Confirm it leaves normal library view and appears in trash/deleted filter.
7. Restore it (`POST /papers/{paper_id}/restore`). Confirm it returns to the library.
8. Soft-delete again, then permanent-delete (`DELETE /papers/{paper_id}/permanent`). Confirm direct detail links handle 404/deleted state cleanly.
9. Soft-delete multiple disposable papers and empty trash (`POST /papers/trash/empty`). Confirm count and UI state update.

## Pass criteria

- Listing, detail, edit, re-resolve, export, delete, restore, permanent delete, and empty trash complete.
- 0 console/page errors and 0 genai-host requests.
- Deleted/permanently deleted deep links fail cleanly.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_40_papers_crud_trash.md` + `screenshots/` (see `_TEMPLATE.md`).

