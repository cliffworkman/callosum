<!-- qa-coverage
api: /library/scan*, /library/watched*, /library/import*, /library/capture-updates, /capture/session, /capture/item, /capture/item/{capture_id}/pdf
fe: 27_scan.jsx, 28_import.jsx, 03a_capture_updates.jsx, 10l_import_queue.jsx
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
6. Open **+ Add → Import citations file… (EndNote RIS)** (`28_import.jsx`). Import valid BibTeX, RIS, and
   CSL-JSON citation fixtures (`POST
   /library/import`) and poll (`GET /library/import/{job_id}`). Confirm each creates metadata-only papers and a
   second import reports duplicates rather than copies.
7. Import a `.txt` RIS stand-in using Clarivate's documented alternate tags (`CPAPER`, `A4`, `BT`, `J1`, `Y2`),
   matching the EndNote/RefMan export guidance in Help. Confirm auto-detection, conference-paper type, author,
   title, container, year, and DOI. This synthetic contract fixture does not substitute for the backlog's pending
   verification with a real EndNote-created export.
8. Import garbage content and malformed/truncated entries. Confirm explicit unrecognized/skipped messaging, not
   a crash; submit an over-5MB file directly and confirm the resource cap returns a readable error.

## Pass criteria

### Browser capture visibility regression (#103)

Use a fresh disposable Library and the real extension/native host for the manual packaged run.
Capture a known public PDF and return to the app both (a) after the extension reports completion
and (b) while upload is still underway. The Import Queue must appear automatically when the
backend commits the capture, without focus changes, right-click Refresh or reload. Record backend
response and visible-chip timestamps separately; target sub-second visibility after completion.
An idle `/library/capture-updates` request may remain held for 20 seconds, but must wake immediately
on a change; that timeout is not an accepted completion delay. Authoritative queue/paper GETs must
follow a changed revision, including after reconnect. Unchanged idle responses must not repeatedly
fetch the queue. Close/reopen the app view to exercise observer cleanup/reconnection.

Confirm the identity only after recording the provisional state. The paper must appear in Library
without reload, preserve the source checksum and user-confirmation provenance, and leave exactly
one canonical attachment with the queued copy removed. For repeated stimuli, use isolated DBs or
distinct PDFs so content deduplication cannot masquerade as queue-update success.

`tests/e2e/test_capture_updates.py` covers the HTTP-to-render notification path locally. It is
explicitly not evidence of a real extension click or packaged macOS acceptance.

- Scan, watched rescan/delete, and import jobs complete through UI polling.
- 0 console/page errors and 0 genai-host requests.
- Invalid paths/files fail closed with user-visible messages.
- Mobile viewport has no horizontal overflow.

### Observed DOI review regression (Ioannidis)

In an isolated Library, capture `tests/fixtures/capture/ioannidis-pmed.0020124.pdf`.
The artifact must remain provisional. Open Import Queue: it must say DOI text was found,
show the observed article DOI, page 1 and its body classification, and offer **Review DOI**.
Do not claim automatic verification or select any `.tNNN`/`.gNNN` DOI as the article.
Review prefills the DOI; no confirm button exists until **Look up** succeeds. First inject
an unresolved provider: no identity or paper is created. Then resolve the fixture record:
inspect its title and explicitly confirm. Original observations/resolutions must survive;
record candidate provenance for an unchanged suggestion and manual provenance after editing.
References-only, component-only and equally plausible article DOIs must not yield an
arbitrarily chosen article. Misleading internal PDF metadata must not override a prominent
visible title. Run `tests/e2e/test_doi_review.py` for the assembled local browser regression;
it does not establish packaged Intel-Mac acceptance of this new fix.

Fault-inject an extraction exception after the PDF is durably saved: the card must say
Callosum could not inspect the identifiers, not that no DOI was found. Compare with a
successfully inspected DOI-free PDF and with a recorded DOI whose resolver failed. No raw
exception, token or local path may appear in the review copy; all remain saved for review.

## Deposit

### Extensionless publisher PDF and responsive capture

Use an isolated packaged desktop Library and the original Ioannidis fixture served at
`https://journals.plos.org/plosmedicine/article/file?id=10.1371/journal.pmed.0020124&type=printable`.
Verify its SHA-256 against the fixture before acceptance. With preview 0.1.2 prepared and
reloaded in Chrome, make one genuine capture click. Record click/upload/queue-commit/UI
times; require no refresh and no title-only `PLME0208_696-701.indd` Library admission.
Pause before lookup and again before confirmation to preserve provisional state and
zero canonical papers. Continue through the DOI review regression above only after
those checkpoints. Do not count Node mocks or TestClient requests as hardware acceptance.

Automated scheduling regressions deliberately block admission or metadata indexing while
checking live health, response completion, committed notifications and same-key replay.
Concurrent real-fixture uploads must store one provisional artifact and two encounters,
with no model inference or canonical paper. Test HTML, unknown MIME, invalid PDF,
oversize bytes, fetch/body timeout, stream cleanup and inaccessible-document refusal.
Existing failed acceptance rows and parked user data must not be silently removed.

### Post-admission paper index (increment 604)

After canonical confirmation, inspect paper and chunk indexes separately: one current paper-level
metadata embedding with a real vector, plus one current vector for every PDF chunk. A chunked
Library card alone is not evidence of the paper index. Cover new papers, existing unindexed papers,
and already-indexed papers without recomputation or duplication, including automatic promotion and
retry. Unresolved capture and DOI preview must not index a candidate as a canonical paper.
Use only disposable data. The Oct 2 Windows receipt remains PARTIAL for paper indexing; preserve it.
The minimum follow-up is in `docs/research/2026-10-02_capture-paper-index.md`, not a repeat of all
previous browser/native-host acceptance steps.

Write `.claude/qa-inbox/<RUN_ID>/route_27_scan_import.md` + `screenshots/` (see `_TEMPLATE.md`).
