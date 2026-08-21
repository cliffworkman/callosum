<!-- qa-coverage
api: /library/zotero/*
fe: 27b_zotero_import.jsx, 10b_libmenus.jsx, 04e_onboarding.jsx
-->

# ROUTE 93 — Native Zotero library import (backlog #57 Phase 1)

**Tier:** 1 local-stateful
**Goal:** Exhaust the shipped entry point for the already-built, full-fidelity Zotero importer — the Library
"+ Add" → "Read Zotero library…" modal and the onboarding wizard's own "Read my Zotero library…" choice — both
riding `ZoteroImportModalBody` (`27b_zotero_import.jsx`) unchanged. The sharpest checks: the source
`zotero.sqlite` (and the whole Zotero data directory) is provably untouched by the run, the whole operation is
zero-egress, an unreadable directory produces an honest job error rather than a raw traceback, a re-run against
the same directory is a true no-op, and the modal's own coordinate-honesty disclosure about imported annotation
positions actually renders.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** Register listeners before navigation.

**Build the Zotero fixture directories via the existing test helpers rather than hand-rolling a
`zotero.sqlite`** — they already produce a real, schema-correct Zotero data directory with a real on-disk PDF:

- `tests.test_zotero_importer._make_zotero_fixture(path)` — a 3-item library (one DOI'd article with a real
  stored PDF at `storage/ATTACHPDF/stored.pdf`, one key-only article with a *linked* PDF path that does **not**
  exist on disk at fixture-build time, one URL-only attachment), one collection, two tags
  (`important`/`review`), and one note. Use this as the **primary** fixture for the happy-path/idempotence/
  coordinate-honesty steps below.
- `tests.test_library_zotero_import._make_empty_zotero_fixture(path)` — a syntactically valid, zero-item Zotero
  schema (no rows). Use this for the "empty-but-valid" step.
- A plain empty directory (no `zotero.sqlite` at all) for the "not a Zotero directory" negative-path step.

Either invoke these helpers directly from a short Python setup script (mirroring how `_TEMPLATE.md` points at
`tests.api_helpers._seed_library`), or hand-build an equivalent directory if running from a context with no
Python import access — but prefer the real helpers; they are exactly what the shipped tests already validate
against.

## Standing assertions (apply to EVERY step)

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.** Any visible control that can't be completed through the UI is a bug.
- **Zero-egress importer/adapter, ONE already-audited exception (Critical, invariant #3).** The importer/adapter
  code itself (`app/backend/importers/zotero.py`, `integrations/zotero/adapter.py`) makes **zero** network calls
  of its own — confirmed by direct grep: zero `httpx`/`requests`/`urllib` matches in either file. But a real
  import run is **not** zero-egress end to end: the shipped job (`_run_zotero_import_job` in
  `app/backend/api/routers/library_zotero.py`) calls `auto_check_retractions` for every newly created paper,
  which — for a paper with a DOI — makes a real Crossref/OpenAlex metadata lookup, exactly like every other
  library-import path in this app already does (`DEFAULT_RETRACTION_CHECKERS`, wired at `app/backend/api/app.py`).
  The primary fixture used throughout this route (`_make_zotero_fixture`) contains a DOI'd item, so this egress
  **will** happen on a real happy-path run — it is disclosed and covered by its own separate audit, not a bug in
  this feature. **Flag anything ELSE** as Critical: any non-loopback request to a host that isn't Crossref/
  OpenAlex, and especially any AI/genai provider host — the retraction lookup itself is expected and must NOT be
  flagged.
- **Copy-then-read, proven not just observed (Critical).** Before starting a run, record the source
  `zotero.sqlite`'s file size, mtime, and (if you can compute it locally) its SHA-256. After the job reaches
  `done`, re-check all three — they must be **byte-for-byte, timestamp-for-timestamp unchanged**. Also confirm
  no new file appears anywhere under the Zotero fixture directory itself (the temp copy lives and dies entirely
  under the OS temp directory, per `tempfile.TemporaryDirectory`, never inside the source directory). Any
  detectable write to the source directory or its `zotero.sqlite` is Critical — it would mean callosum touched
  the user's live Zotero database.
- **Honest job error, never a raw traceback (High).** A directory that exists but has no `zotero.sqlite` must
  fail the job with a plain, readable message naming `zotero.sqlite` — the word "Traceback" or a Python
  exception's file/line noise appearing anywhere in the surfaced error text is a bug.
- **Idempotent re-run (High).** Running the same fixture directory twice in a row must report `0` newly-created
  papers on the second run, and the library's total paper count must not grow. Confirm via both the modal's own
  summary line and a follow-up `GET /papers` count.
- **Status findability (invariant #5).** While a run is in progress, the global Status popover must show a row
  for it (`zotero_import_jobs`, labeled "Zotero library import") with real, non-invented progress. Clicking that
  row must land back on the Library workspace with the "Read my Zotero library…" modal reopened — not a bare
  Library landing with the modal closed.
- **Coordinate-honesty disclosure actually renders (Medium+, invariant #2 in spirit).** The modal's own
  explanatory copy must state, in the modal body itself (not just in code comments), that imported highlight
  *positions* aren't yet mappable to callosum's PDF-space coordinates — confirm the live wording rather than
  assuming it matches this description verbatim; the substantive claim to verify is that it discloses "can't
  yet be jumped-to or drawn on the PDF," not a specific sentence.
- **Signal not verdict.** The completion summary is plain counts (new/matched/attachments/chunks/errors) —
  never a quality judgment about the imported library.

## Adversarial checklist

- A fabricated job id (`GET /library/zotero/import/does-not-exist`) → **404**, not a hang or 500.
- An empty or whitespace-only path in the directory field → **422** rendered inline in the modal (the
  "Read library" button itself should also be disabled while the field is empty — confirm both the client-side
  disabled-state and the server-side 422 independently, e.g. by posting whitespace directly).
- A path that doesn't exist on disk at all → **422**, not a job that starts and then fails.
- Double-clicking **Read library** rapidly → confirm only one job is created (the button disables to "Importing…"
  once a run starts) — not two concurrent jobs against the same directory.
- Navigate away from the Library workspace mid-job (or reload the page entirely) and return → the modal's
  `localStorage`-backed resume (`callosum.zoteroImportJob`) must pick the same job back up on remount and show
  its current/final state, not silently drop it or restart a duplicate run. (The modal also persists the
  last-used folder path in `callosum.zoteroDataDir`, pre-filling the field on next open — `callosum.zoteroImportJob`
  and `callosum.zoteroDataDir` are the exact two localStorage keys this feature writes; scope test-state
  cleanup to precisely those two.)
- Paste a ~50KB string into the directory field → the length cap (`max_length=4096`) rejects it cleanly with a
  422, not a crash or a hung request.
- Mobile viewport `375x812`, hard refresh → no horizontal overflow in the modal.

## Steps

### Library "+ Add" menu

1. Baseline screenshot: Library → "+ Add" ▾ menu → confirm "Read Zotero library…" appears above "Import file…"
   with its own explanatory tooltip.
2. Open it. Confirm the modal's copy names the Zotero data directory (where `zotero.sqlite` lives), explains the
   copy-before-read safety property in the modal body itself, and includes the coordinate-honesty disclosure
   (see Standing assertions).
3. Point it at the primary 3-item fixture (`_make_zotero_fixture`). Click **Read library**. Confirm: a Status
   popover entry appears and clicks back correctly (see Standing assertions); the `ProgressBar` shows real
   progress, not an invented percentage; on completion, the summary reads "3 new · 0 already in your library"
   plus non-zero attachment/chunk counts.
4. Confirm the source `zotero.sqlite`'s size/mtime/hash are unchanged (see Standing assertions), and that the
   request listener recorded no non-loopback requests other than the expected Crossref/OpenAlex retraction
   lookup for the newly created DOI'd paper (see the Standing-assertions egress note).
5. Open the newly-imported DOI'd paper. Confirm its PDF is full-text searchable (the extracted chunk's content
   is findable) and its tags (`important`/`review`) and collection membership carried over.
6. Re-run the import against the **same** fixture directory. Confirm the idempotent-re-run assertion above (0
   new papers, library count unchanged).
7. Point the modal at the empty-but-valid fixture (`_make_empty_zotero_fixture`). Confirm a clean "done" summary
   with every count at 0 — not an error state.
8. Point the modal at a plain empty directory with no `zotero.sqlite`. Confirm the honest job error naming
   `zotero.sqlite`, with no traceback text anywhere in the surfaced message.
9. Run the adversarial checklist above (fabricated job id, empty/whitespace path, nonexistent path, double-click
   Start, navigate-away-and-return resume, oversized input, mobile viewport).

### Onboarding wizard

10. Force the first-run wizard to reappear (`route_77_onboarding_wizard.md`'s own Environment note — clear
    `onboarding_completed`). Step to the **Import** step. Confirm the choice screen now offers **"Read my Zotero
    library…"** as the leading option, above "Import citations file…" and "Import a callosum bundle…", and that
    its explanatory copy mentions full fidelity (PDFs, notes, tags, collections).
11. Pick it. Confirm the same `ZoteroImportModalBody` renders inline in the wizard card (identical behavior to
    the standalone modal — reuse, not a re-implementation). Run a small import against the primary fixture;
    confirm it completes and the wizard's "Next →" (or the modal's own close) advances to the axis step.
12. Click **Back** from the axis step to the import step — confirm the Zotero choice/modal state doesn't get
    stuck or double-submit a second job.

## Pass criteria

- Both entry points (Library "+ Add" menu and the onboarding wizard's import step) reach the same working
  `ZoteroImportModalBody` and complete a real import through UI polling.
- The source Zotero data directory is provably untouched (size/mtime/hash) after every run, including a failed
  one.
- No non-loopback network requests observed other than the expected Crossref/OpenAlex retraction-check lookup
  for a newly created DOI'd paper (the same already-audited lookup every other import path makes); any other
  non-loopback host, especially an AI/genai provider, is Critical.
- A non-Zotero directory fails with an honest, traceback-free message; an empty-but-valid one succeeds with an
  all-zero summary; a re-run against the same directory is a true no-op.
- Status findability and nav-click-through hold; the coordinate-honesty disclosure copy is present and readable
  in the modal itself.
- 0 console/page errors; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_93_zotero_library_import.md` + `screenshots/` (see `_TEMPLATE.md`).
