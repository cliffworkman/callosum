<!-- qa-coverage
api: POST /papers/{paper_id}/acquire-oa, /papers/acquire-oa*, POST /papers/by-doi, GET /papers/{paper_id}/library-link, /wanted*
fe: 26_wanted.jsx, 25_detail.jsx, 28e_add_doi.jsx
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
- **OA candidate fallback ≠ opaque failure (backlog #59).** A single 403/404 candidate must not terminate
  acquisition when other legitimate candidates remain; the pipeline tries the next resolver's candidate and
  never re-fetches the same known-bad URL. The user-facing result must **distinguish** three states — a copy
  was imported, **no OA candidate was found**, and **candidates were found but none downloaded** (the last
  carrying a structured reason, e.g. HTTP 403 from a named source) — plus a 4th, unexpected error. Collapsing
  "candidates exhausted" into either "no OA copy" or an opaque error is **High**. Candidate URLs are validated
  (https, `%PDF-`, opens) before acceptance; no partial temp file survives a failed attempt.
- **Metadata import vs OA fetch are separate (backlog #58).** Add-with-DOI resolves metadata and OA-fetches as
  two distinct results; a failed PDF fetch presented as a failed DOI import is **High**. An unresolvable/invalid
  DOI must fail honestly (422) and create **no** record — never an invented placeholder.
- **Link hand-off, not fetch (inc 263).** `Get via my library` must only `window.open` the built OpenURL in the user's browser. callosum must make **no server-side request** to the resolver/publisher, store no credentials, drive no login, and auto-download nothing. Any server-side fetch of the resolver, cookie/session capture, or auto-fetch is **Critical** (the deferred credentialed-connector veto lines). `GET /papers/{paper_id}/library-link` returns a URL string only.

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
6. Trigger per-paper OA acquisition (`POST /papers/{paper_id}/acquire-oa`) and poll (`GET /papers/acquire-oa/{job_id}`). Confirm found/not-found/imported states and OA color/version/source are displayed without overstating legality. **Candidate fallback (backlog #59):** with a fake registry whose first candidate 403s and a later one succeeds, confirm the import still succeeds via the later candidate; with all candidates 403/404, confirm the distinct `candidates_exhausted` state (a structured HTTP-status reason, not "no OA copy" and not an opaque error).
7. **Add with DOI (backlog #58).** In the Library **+ Add → Add with DOI…** (`28e_add_doi.jsx`), paste a bare DOI, a `doi:` form, and a `https://doi.org/…` URL (`POST /papers/by-doi`): each adds the resolved paper. An already-present DOI is **surfaced, not duplicated** (`status:"existing"`). An unresolvable/garbage DOI returns 422 and adds nothing. Confirm OA acquisition starts automatically afterward as a **distinct** job (`acquire_job_id`), and that its success/failure is reported separately from the metadata add.
8. Directly open fake job ids and non-existent wanted ids. Confirm clean 404 states.
9. **Library hand-off (inc 263).** In Settings -> Library access, confirm the OpenURL resolver field is empty by default and that a bad base (`ftp://x`) is rejected 422; set a valid `https://…` base. On a PDF-less paper, run acquire-OA to a miss, then click `Get via my library` (`GET /papers/{paper_id}/library-link`): confirm it opens a new tab to the resolver with the built OpenURL (DOI in `rft_id=info:doi/…`) and that **no server-side fetch** of the resolver occurs. Clear the base and confirm the honest "add your library's link resolver in Settings" prompt (feature dormant by default).

## Pass criteria

- Wanted add/delete/sync/recheck and per-paper acquire complete through UI polling.
- Hermetic default uses injected fake clients; no genai-host requests with egress unset.
- OA status is evidence/count based; no verdict language or hidden score.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_56_acquisition_wanted.md` + `screenshots/` (see `_TEMPLATE.md`).
