<!-- qa-coverage
api: /library/scan*, /library/watched*, /library/import*
fe: 27_scan.jsx, 28_import.jsx
-->

# ROUTE 27 - Scan, watched folders, and import

**Tier:** 1 local-stateful
**Goal:** Exhaust local folder scan, watched-folder rescan/delete, and explicit file import jobs.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation. Use only the throwaway QA fixture folders prepared by the route runner.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected; garbage file on import/scan
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open Add -> Scan folder (`27_scan.jsx`). Submit a valid disposable fixture folder (`POST /library/scan`) and poll (`GET /library/scan/{job_id}`).
2. Navigate away mid-scan and return. Confirm progress/result state recovers and imported papers appear only once.
3. Submit an empty path, whitespace path, and forbidden/outside path. Confirm clean validation and no server traceback.
4. Open watched folders. Confirm list loads (`GET /library/watched`) and **always includes the pinned library-folder default** (inc 160): an `is_default` row shown as "default · always watched" with **no remove button**; `DELETE /library/watched/0` must be refused (**422**). Run rescan (`POST /library/watched/rescan`, `GET /library/watched/rescan/{job_id}`), rapid-click rescan/scan and confirm a second request reuses the active job instead of spawning another writer, and delete a disposable *user-added* watched folder (`DELETE /library/watched/{folder_id}`) — the default remains.
5. Put a byte-identical PDF under a different name/path from a non-scan provenance fixture. Confirm scan reports it unchanged by content and does not create another paper.
6. Open Add -> Import (`28_import.jsx`). Import valid BibTeX, RIS, and CSL-JSON citation fixtures (`POST
   /library/import`) and poll (`GET /library/import/{job_id}`). Confirm each creates metadata-only papers and a
   second import reports duplicates rather than copies.
7. Import a `.txt` RIS stand-in using Clarivate's documented alternate tags (`CPAPER`, `A4`, `BT`, `J1`, `Y2`),
   matching the EndNote/RefMan export guidance in Help. Confirm auto-detection, conference-paper type, author,
   title, container, year, and DOI. This synthetic contract fixture does not substitute for the backlog's pending
   verification with a real EndNote-created export.
8. Import garbage content and malformed/truncated entries. Confirm explicit unrecognized/skipped messaging, not
   a crash; submit an over-5MB file directly and confirm the resource cap returns a readable error.

## Pass criteria

- Scan, watched rescan/delete, and import jobs complete through UI polling.
- 0 console/page errors and 0 genai-host requests.
- Invalid paths/files fail closed with user-visible messages.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_27_scan_import.md` + `screenshots/` (see `_TEMPLATE.md`).
